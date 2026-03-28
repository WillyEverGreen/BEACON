# evaluate_llm.py — End-to-End LLM Code-Fix Evaluation
# Pipeline: Issue → RAG Retrieval → LLM Generation → Automated Validation
import sys, os, json, time, glob, asyncio, re

sys.path.insert(0, os.path.abspath("rag-pipeline"))
# Also need app modules
sys.path.insert(0, os.path.abspath("."))

from dotenv import load_dotenv
load_dotenv(override=True)

from query import hybrid_retrieve, rerank, expand_query

# We call Featherless AI directly (same as llm.py) to avoid needing FastAPI
from openai import AsyncOpenAI

REPORT_PATH = os.path.join(
    r"C:\Users\advdi\.gemini\antigravity\brain\e9ca9be2-a8f6-4f37-b577-4d2b67ccef88",
    "llm_evaluation_report.md"
)

REMEDIATION_SYSTEM_PROMPT = """You are an expert web accessibility remediation engine. Given a specific accessibility issue found during an audit, along with relevant WCAG/ARIA reference material, produce a structured remediation packet.

Your response MUST be valid JSON with these exact fields:
{
  "explanation": "Clear explanation of why this is an accessibility issue and the impact on users with disabilities",
  "wcag_references": [
    {
      "criterion_id": "e.g. 1.4.3",
      "name": "e.g. Contrast (Minimum)",
      "level": "A or AA or AAA",
      "description": "Brief description of what this criterion requires"
    }
  ],
  "code_fix": "Complete, ready-to-paste HTML/CSS/JS code snippet that resolves the issue. Must be production-ready. Use the element selector from the issue to make the fix specific.",
  "validation_hint": "How to verify the fix: specific steps for automated and manual testing"
}

Rules:
1. The code_fix MUST be specific to the element identified in the issue
2. ALWAYS cite the specific WCAG criterion (e.g., 1.4.3, 2.1.1)
3. Include ARIA patterns when relevant
4. Respond ONLY with valid JSON"""

REMEDIATION_USER_PROMPT = """ACCESSIBILITY ISSUE:
- Rule: {rule_id}
- Severity: {severity}
- WCAG Criterion: {wcag_criterion}
- Element: {element}
- HTML Snippet: {html_snippet}
- Description: {description}

RETRIEVED REFERENCE MATERIAL:
{context}

---

Produce a structured remediation packet for this issue. Respond with valid JSON only."""


async def call_llm(issue: dict, context_str: str) -> dict:
    """Call Featherless AI and parse the JSON response."""
    api_key = os.getenv("FEATHERLESS_API_KEY", "")
    base_url = os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1")
    model = os.getenv("FEATHERLESS_MODEL", "Qwen/Qwen2.5-Coder-32B-Instruct")

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": REMEDIATION_SYSTEM_PROMPT},
            {"role": "user", "content": REMEDIATION_USER_PROMPT.format(
                rule_id=issue.get("rule_id", ""),
                severity=issue.get("severity", ""),
                wcag_criterion=issue.get("wcag_criterion", ""),
                element=issue.get("element", ""),
                html_snippet=issue.get("html_snippet", ""),
                description=issue.get("description", ""),
                context=context_str,
            )},
        ],
        max_tokens=2000,
        temperature=0.2,
    )

    text = response.choices[0].message.content.strip()

    # Parse JSON
    json_text = text
    if "```" in text:
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if match:
            json_text = match.group(1).strip()

    match = re.search(r'\{[\s\S]*\}', json_text)
    if match:
        return json.loads(match.group())

    return {"code_fix": text, "explanation": text, "wcag_references": []}


def evaluate_output(llm_output: dict, test_case: dict) -> dict:
    """Grade the LLM output against expected patterns."""
    code_fix = (llm_output.get("code_fix", "") or "").lower()
    explanation = (llm_output.get("explanation", "") or "").lower()
    combined = f"{code_fix} {explanation}"

    results = {
        "pattern_hits": [],
        "pattern_misses": [],
        "forbidden_found": [],
        "wcag_hits": [],
        "wcag_misses": [],
        "has_code_fix": bool(code_fix.strip()),
        "has_explanation": bool(explanation.strip()),
    }

    # Check expected patterns (at least one match in code_fix OR explanation)
    for pat in test_case.get("expected_patterns", []):
        if pat.lower() in combined:
            results["pattern_hits"].append(pat)
        else:
            results["pattern_misses"].append(pat)

    # Check must_not_include (should NOT appear in code_fix)
    for forbidden in test_case.get("must_not_include", []):
        if forbidden.lower() in code_fix:
            results["forbidden_found"].append(forbidden)

    # Check WCAG references
    wcag_refs = llm_output.get("wcag_references", [])
    cited_ids = set()
    for ref in wcag_refs:
        if isinstance(ref, dict):
            cited_ids.add(ref.get("criterion_id", ""))

    for expected_wcag in test_case.get("must_have_wcag", []):
        if any(expected_wcag in cid for cid in cited_ids):
            results["wcag_hits"].append(expected_wcag)
        elif expected_wcag.lower() in combined:
            results["wcag_hits"].append(expected_wcag + " (in text)")
        else:
            results["wcag_misses"].append(expected_wcag)

    # Calculate scores
    total_patterns = len(test_case.get("expected_patterns", []))
    pattern_score = len(results["pattern_hits"]) / total_patterns if total_patterns else 1.0

    total_wcag = len(test_case.get("must_have_wcag", []))
    wcag_score = len(results["wcag_hits"]) / total_wcag if total_wcag else 1.0

    forbidden_penalty = 1.0 if not results["forbidden_found"] else 0.5
    code_fix_bonus = 1.0 if results["has_code_fix"] else 0.0

    results["pattern_score"] = round(pattern_score, 3)
    results["wcag_score"] = round(wcag_score, 3)
    results["overall_score"] = round(
        (pattern_score * 0.4 + wcag_score * 0.2 + code_fix_bonus * 0.3 + forbidden_penalty * 0.1),
        3
    )

    if results["overall_score"] >= 0.8:
        results["verdict"] = "✅ PASS"
    elif results["overall_score"] >= 0.5:
        results["verdict"] = "⚠️ PARTIAL"
    else:
        results["verdict"] = "❌ FAIL"

    return results


async def run_evaluation():
    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests")
    test_files = sorted(glob.glob(os.path.join(test_dir, "*.json")))

    print("=" * 70)
    print("  LLM END-TO-END CODE-FIX EVALUATION")
    print(f"  Model: {os.getenv('FEATHERLESS_MODEL', 'unknown')}")
    print(f"  Test Cases: {len(test_files)}")
    print("=" * 70)

    md = []
    md.append("# LLM End-to-End Code-Fix Evaluation Report")
    md.append(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    md.append(f"**Model:** `{os.getenv('FEATHERLESS_MODEL', 'unknown')}`")
    md.append(f"**Test Cases:** {len(test_files)}")
    md.append("")
    md.append("> This report validates whether the LLM generates **correct, accessible, production-ready code fixes** when given RAG-retrieved context. This is the true end-to-end product test.")
    md.append("")

    all_scores = []
    total_time = 0

    for tf in test_files:
        with open(tf, encoding="utf-8") as f:
            tc = json.load(f)

        name = tc["name"]
        issue = tc["issue"]
        print(f"\n{'─' * 50}")
        print(f"  Testing: {name}")

        # ── Step 1: RAG Retrieval ──
        t0 = time.time()
        rule_id = issue.get("rule_id", "")
        desc = issue.get("description", "")
        expanded = expand_query(rule_id, desc)
        candidates = hybrid_retrieve(expanded, top_k=20)
        top_chunks = rerank(expanded, candidates, top_n=5)
        retrieval_time = time.time() - t0

        context_parts = []
        for c in top_chunks:
            silo = c["meta"].get("silo", "unknown")
            context_parts.append(f"[{silo.upper()}]\n{c['text']}")
        context_str = "\n\n---\n\n".join(context_parts) if context_parts else "No context available."

        silos_used = list(set(c["meta"].get("silo", "?") for c in top_chunks))
        print(f"  RAG: {len(top_chunks)} chunks from [{', '.join(silos_used)}] in {retrieval_time:.2f}s")

        # ── Step 2: LLM Generation ──
        t1 = time.time()
        try:
            llm_output = await call_llm(issue, context_str)
            llm_time = time.time() - t1
            print(f"  LLM: Response received in {llm_time:.2f}s")
        except Exception as e:
            llm_time = time.time() - t1
            llm_output = {"code_fix": "", "explanation": f"ERROR: {e}", "wcag_references": []}
            print(f"  LLM: ❌ FAILED - {str(e)[:80]}")

        total_elapsed = retrieval_time + llm_time
        total_time += total_elapsed

        # ── Step 3: Automated Validation ──
        eval_result = evaluate_output(llm_output, tc)
        all_scores.append(eval_result["overall_score"])

        verdict = eval_result["verdict"]
        print(f"  {verdict} | Pattern: {eval_result['pattern_score']*100:.0f}% | WCAG: {eval_result['wcag_score']*100:.0f}% | Overall: {eval_result['overall_score']*100:.0f}%")

        # ── Write to report ──
        md.append(f"## {name}")
        md.append(f"**Issue:** `{issue['rule_id']}` — {issue['description'][:100]}...")
        md.append(f"**Input HTML:** `{issue['html_snippet'][:80]}`")
        md.append("")
        md.append(f"| Metric | Result |")
        md.append(f"|---|---|")
        md.append(f"| Verdict | **{verdict}** |")
        md.append(f"| Pattern Score | {eval_result['pattern_score']*100:.0f}% ({len(eval_result['pattern_hits'])}/{len(tc.get('expected_patterns',[]))} patterns matched) |")
        md.append(f"| WCAG Citation Score | {eval_result['wcag_score']*100:.0f}% |")
        md.append(f"| Has Code Fix | {'✅' if eval_result['has_code_fix'] else '❌'} |")
        md.append(f"| Overall Score | **{eval_result['overall_score']*100:.0f}%** |")
        md.append(f"| RAG Silos Used | `{', '.join(silos_used)}` |")
        md.append(f"| Retrieval + LLM Time | {total_elapsed:.2f}s |")

        if eval_result["pattern_hits"]:
            md.append(f"| ✅ Patterns Found | `{'`, `'.join(eval_result['pattern_hits'])}` |")
        if eval_result["pattern_misses"]:
            md.append(f"| ❌ Patterns Missing | `{'`, `'.join(eval_result['pattern_misses'])}` |")
        if eval_result["forbidden_found"]:
            md.append(f"| ⚠️ Forbidden Found | `{'`, `'.join(eval_result['forbidden_found'])}` |")

        # Show the actual code fix (truncated)
        code_fix = llm_output.get("code_fix", "")
        if code_fix:
            md.append("")
            md.append("<details><summary>Generated Code Fix (click to expand)</summary>")
            md.append("")
            md.append("```html")
            md.append(code_fix[:500])
            md.append("```")
            md.append("</details>")

        md.append("")

    # ── Summary ──
    avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
    passed = sum(1 for s in all_scores if s >= 0.8)
    partial = sum(1 for s in all_scores if 0.5 <= s < 0.8)
    failed = sum(1 for s in all_scores if s < 0.5)

    md.append("---")
    md.append("## Overall System Verdict")
    md.append("")
    md.append("| Metric | Result |")
    md.append("|---|---|")
    md.append(f"| Total Test Cases | **{len(all_scores)}** |")
    md.append(f"| ✅ Passed | **{passed}** |")
    md.append(f"| ⚠️ Partial | **{partial}** |")
    md.append(f"| ❌ Failed | **{failed}** |")
    md.append(f"| Average Score | **{avg_score*100:.1f}%** |")
    md.append(f"| Total Pipeline Time | **{total_time:.1f}s** |")
    md.append(f"| Avg per Issue | **{total_time/len(all_scores):.1f}s** |")
    md.append("")

    if avg_score >= 0.85:
        md.append("> ✅ **PRODUCTION READY** — The LLM reliably generates correct, accessible code fixes grounded in RAG context.")
    elif avg_score >= 0.65:
        md.append("> ⚠️ **NEEDS TUNING** — The LLM generates partially correct fixes but misses some patterns. Prompt engineering or retrieval improvements recommended.")
    else:
        md.append("> ❌ **NOT READY** — The LLM frequently fails to generate correct fixes. Major retrieval or prompt changes required.")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"\n{'=' * 70}")
    print(f"  FINAL: {passed} PASS / {partial} PARTIAL / {failed} FAIL")
    print(f"  Average Score: {avg_score*100:.1f}%")
    print(f"  Report → {REPORT_PATH}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
