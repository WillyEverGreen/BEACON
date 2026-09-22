import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# Ensure we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.llm import generate_remediation
from evaluation.act_loader import load_act_cases
from evaluation.fix_quality_eval import run_axe_on_html
from evaluation.gena11y_loader import load_gena11y_cases


async def sample_fixes(snippet: str, sc_id: str, rule_id: str, k: int = 3) -> list[str]:
    """Sample k independent fixes from the LLM."""
    issue = {
        "html_snippet": snippet,
        "wcag_criterion": sc_id,
        "rule_id": rule_id,
        "description": f"Violation of {sc_id} ({rule_id})",
        "severity": "serious",
        "issue_id": "eval-task"
    }
    
    # We use empty context for now to measure pure LLM capability or 
    # we could pull real context if we want to measure RAG.
    # For now, let's assume no context to test the base engine.
    context_chunks = [] 
    
    tasks = [generate_remediation(issue, context_chunks, temperature=0.7) for _ in range(k)]
    results = await asyncio.gather(*tasks)
    
    fixes = []
    for res in results:
        code_fix = res.get("code_fix", "")
        if not code_fix and "fixes" in res:
            code_fix = res["fixes"].get("vanilla", "")
        if not code_fix and "code_example" in res:
            code_fix = res["code_example"].get("vanilla", "")
        fixes.append(code_fix)
        
    return fixes

async def evaluate_case(case: Any, k: int = 3) -> dict[str, Any]:
    """Evaluate a single test case for pass@k."""
    html_content = case.fixture_file.read_text(encoding="utf-8")
    
    print(f"  Evaluating {case.fixture_file.name} (SC {case.sc_id})...")
    
    # 1. Sample k fixes
    fixes = await sample_fixes(html_content, case.sc_id, getattr(case, 'rule_id', ''), k=k)
    
    # 2. Verify each fix
    results = []
    for i, fix_html in enumerate(fixes):
        if not fix_html:
            results.append(False)
            continue
            
        violations = await run_axe_on_html(fix_html)
        # If the original rule_id is not in violations, it's a pass
        # Or if sc_id is not represented in the violations
        is_resolved = True
        for v in violations:
            # Simple heuristic: if the violation ID matches or is related to the SC
            if v.get('id') == getattr(case, 'rule_id', ''):
                is_resolved = False
                break
        
        results.append(is_resolved)
        
    return {
        "fixture": case.fixture_file.name,
        "sc_id": case.sc_id,
        "rule_id": getattr(case, 'rule_id', ''),
        "fixes_sampled": k,
        "successes": sum(results),
        "results": results
    }

async def main():
    parser = argparse.ArgumentParser(description="BEACON LLM Fix Evaluation Harness (pass@k)")
    parser.add_argument("--k", type=int, default=3, help="Number of samples to draw per case")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of cases to evaluate")
    parser.add_argument("--dataset", choices=["gena11y", "act", "both"], default="both")
    args = parser.parse_args()
    
    cases = []
    if args.dataset in ["gena11y", "both"]:
        cases.extend(load_gena11y_cases("evaluation/fixtures/gena11y"))
    if args.dataset in ["act", "both"]:
        cases.extend(load_act_cases("evaluation/fixtures/act"))
        
    # Only evaluate failures (cases that HAVE violations to fix)
    eval_cases = [c for c in cases if c.expected_violation]
    
    if args.limit:
        eval_cases = eval_cases[:args.limit]
        
    print(f"Starting pass@{args.k} evaluation on {len(eval_cases)} cases...")
    
    all_results = []
    for i, case in enumerate(eval_cases):
        res = await evaluate_case(case, k=args.k)
        all_results.append(res)
        
    # Calculate pass@k
    # pass@k = 1/N * sum( 1 - ( (n-s) over k ) / ( n over k ) )
    # where n is the total samples, s is the successful samples.
    # Since we drew exactly k samples, if s > 0, then at least one sample is correct.
    # So for a single case, it's 1 if s > 0, else 0.
    
    pass_at_k_count = sum(1 for r in all_results if r["successes"] > 0)
    pass_at_k_rate = pass_at_k_count / len(all_results) if all_results else 0
    
    avg_success_rate = sum(r["successes"] for r in all_results) / (len(all_results) * args.k) if all_results else 0
    
    print("\n" + "="*40)
    print(f"EVALUATION RESULTS (k={args.k})")
    print("="*40)
    print(f"Total Cases:     {len(all_results)}")
    print(f"Pass@{args.k} Rate:    {pass_at_k_rate:.2%}")
    print(f"Avg Success Rate: {avg_success_rate:.2%}")
    print("="*40)
    
    # Save results
    output_dir = Path("evaluation/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"llm_eval_pass_at_{args.k}.json"
    
    summary = {
        "k": args.k,
        "pass_at_k": pass_at_k_rate,
        "avg_success_rate": avg_success_rate,
        "total_cases": len(all_results),
        "details": all_results
    }
    
    with open(output_file, "w") as f:
        json.dump(summary, f, indent=2)
        
    print(f"Full results saved to {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
