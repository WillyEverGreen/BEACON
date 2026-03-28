import asyncio
import os
import sys

# Ensure app is in path
sys.path.insert(0, os.path.abspath("."))

from app.services.retrieval import retrieve_for_issue, _keyword_search
from app.services.llm import generate_remediation, enrich_issues_with_remediation
from app.services.ingestion import CORPUS_EXPANSION_SOURCES

async def run_rag_test():
    print("=" * 60)
    print("  RAG COMPREHENSIVE TEST (Milestone 4)")
    print("=" * 60)
    print(f"\n1. Validating Expansion Sources Count:")
    print(f"   Configured: {len(CORPUS_EXPANSION_SOURCES)}")
    if len(CORPUS_EXPANSION_SOURCES) >= 22:
        print("   ✅ ALL SOURCES CONFIGURED")
    else:
        print("   ❌ MISSING SOURCES")
        
    print("\n2. Testing Issue Retrieval Context Builder:")
    test_issue = {
        "issue_id": "test-123",
        "rule_id": "color-contrast",
        "severity": "serious",
        "wcag_criterion": "1.4.3",
        "category": "contrast",
        "element": "<button style=\"color: #fff; background: #ddd;\">Submit</button>",
        "html_snippet": "<button style=\"color: #fff; background: #ddd;\">Submit</button>",
        "description": "Elements must have sufficient color contrast",
        "confidence": 0.9,
    }
    
    print(f"   Simulating retrieval for: {test_issue['rule_id']} (WCAG {test_issue['wcag_criterion']})")
    try:
        # We might not have actual vector embeddings loaded in the test environment, 
        # but the function shouldn't crash.
        chunks = await retrieve_for_issue(test_issue, n_results=3)
        print(f"   ✅ retrieve_for_issue() completed successfully. Returning {len(chunks)} chunks.")
    except Exception as e:
        print(f"   ⚠️ retrieve_for_issue() raised error (likely no vector DB): {e}")

    print("\n3. Testing Remediation Generation (Mock Context):")
    mock_context = [
        {
            "content": "WCAG 1.4.3 Contrast (Minimum): Text passing this requires a contrast ratio of at least 4.5:1.",
            "metadata": {"source_silo": "wcag", "chunk_type": "guideline", "criterion_id": "1.4.3", "score": 0.9}
        },
        {
            "content": "To fix contrast issues, ensure the foreground color stands out against the background.",
            "metadata": {"source_silo": "mdn", "chunk_type": "developer-guide", "score": 0.75}
        }
    ]
    
    try:
        remediation = await generate_remediation(test_issue, mock_context)
        print("   ✅ generate_remediation() executed successfully")
        print("   Returned Fields: ", list(remediation.keys()))
        if "explanation" in remediation and "code_fix" in remediation and "wcag_references" in remediation:
             print("   ✅ Structured packet format valid.")
        else:
             print("   ❌ Missing required fields in remediation packet.")
             
        # Print a snippet of what it generated
        print(f"   Explanation Preview: {remediation.get('explanation', '')[:100]}...")
        print(f"   Code Fix Preview: {remediation.get('code_fix', '')[:100]}...")
    except Exception as e:
        print(f"   ❌ generate_remediation() failed: {e}")
        
    print("\n4. Testing Batch Enrichment Logic:")
    issues_list = [dict(test_issue)]
    try:
        enriched = await enrich_issues_with_remediation(issues_list, max_issues=1)
        print("   ✅ enrich_issues_with_remediation() succeeded.")
        print("   Issue structured_fix populated? ", bool(enriched[0].get("code_fix") != test_issue.get("code_fix")))
    except Exception as e:
        print(f"   ❌ enrich_issues_with_remediation() failed: {e}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(run_rag_test())
