"""
LLM service: Featherless AI (OpenAI-compatible) for query expansion
and RAG response generation.
"""
import asyncio
import json
import logging
import re
from typing import Optional
from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# Async client (cached)
_client: Optional[AsyncOpenAI] = None


def get_client() -> AsyncOpenAI:
    """Get or init the Featherless (OpenAI-compatible) async client."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.featherless_api_key,
            base_url=settings.featherless_base_url,
        )
    return _client


# ── Query Expansion ────────────────────────────────────────────

EXPANSION_PROMPT = """You are a web accessibility expert. Given the user's query about web accessibility, generate 2-3 alternative search queries that would help find relevant WCAG guidelines, ARIA patterns, and code fixes.

User query: {query}

Return ONLY a JSON array of strings (the alternative queries), nothing else.
Example: ["WCAG contrast ratio requirements", "ARIA button role pattern", "CSS accessible color palette"]"""


async def expand_query_with_llm(query: str) -> list[str]:
    """
    Use LLM to expand a query into multiple sub-queries for better retrieval.
    """
    client = get_client()

    try:
        response = await client.chat.completions.create(
            model=settings.featherless_model,
            messages=[
                {"role": "system", "content": "You are a web accessibility expert. Respond only with valid JSON."},
                {"role": "user", "content": EXPANSION_PROMPT.format(query=query)},
            ],
            max_tokens=200,
            temperature=0.3,
        )

        text = response.choices[0].message.content.strip()

        # Parse JSON array
        # Try to extract JSON array from response
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            expanded = json.loads(match.group())
            if isinstance(expanded, list):
                return [str(q) for q in expanded[:3]]

    except Exception as e:
        logger.warning(f"Query expansion LLM call failed: {e}")

    return []


# ── Main RAG Generation ───────────────────────────────────────

RAG_SYSTEM_PROMPT = """You are an expert web accessibility assistant specializing in WCAG 2.2 guidelines.
You help developers fix accessibility issues by providing clear explanations, WCAG rYour response MUST be in valid JSON format with these exact fields:
{
  "explanation": {
    "what_is_broken": "One sentence, plain English description of the violation",
    "impact": "Who it affects and how (human-centric story)",
    "wcag_sc": "Success Criterion number and name",
    "intent": "Why this criterion exists and its importance",
    "verification": "Step-by-step test procedure (automated + manual)"
  },
  "fixes": {
    "vanilla": "Plain HTML/CSS/JS fix specific to the element",
    "react": "React component implementation of the fix",
    "vue": "Vue component implementation of the fix",
    "angular": "Angular component/template implementation of the fix"
  },
  "practical_assets": [
    {
      "asset_type": "template OR aria-pattern OR script OR reference",
      "name": "Name of the resource",
      "content": "The relevant snippet or instruction from the toolkit"
    }
  ]
}

Rules:
1. PLAIN ENGLISH FIRST: The 'what_is_broken' and 'impact' fields must be understandable by a non-technical person.
2. SPECIFIC FIXES: The code fixes must use the actual element HTML provided in the query.
3. FRAMEWORK AWARE: Always provide all 4 variants (vanilla, react, vue, angular).
4. VERIFICATION: Provide a test procedure like '1. Inspect element... 2. Run axe... 3. Test with screen reader...'.
5. ONLY VALID JSON: Respond only with the JSON object, no other text.
"""


RAG_USER_PROMPT = """RETRIEVED CONTEXT:
{context}

---

USER QUERY: {query}

Respond with valid JSON only."""


async def generate_rag_response(query: str, context_chunks: list[dict]) -> dict:
    """
    Generate a structured RAG response using the LLM.
    Takes query + retrieved context chunks, returns parsed response dict.
    """
    client = get_client()

    # Build context string
    context_parts = []
    for i, chunk in enumerate(context_chunks):
        meta = chunk.get("metadata", {})
        source_label = meta.get("source", "unknown")
        chunk_type = meta.get("chunk_type", "unknown")
        filename = meta.get("filename", "")
        criterion = meta.get("criterion_id", "")

        header = f"[Source: {source_label} | Type: {chunk_type}"
        if filename:
            header += f" | File: {filename}"
        if criterion:
            header += f" | Criterion: {criterion}"
        header += f" | Relevance: {chunk.get('score', 0):.2f}]"

        context_parts.append(f"{header}\n{chunk['content']}")

    context_str = "\n\n---\n\n".join(context_parts)

    try:
        response = await client.chat.completions.create(
            model=settings.featherless_model,
            messages=[
                {"role": "system", "content": RAG_SYSTEM_PROMPT},
                {"role": "user", "content": RAG_USER_PROMPT.format(
                    context=context_str, query=query
                )},
            ],
            max_tokens=2000,
            temperature=0.2,
        )

        text = response.choices[0].message.content.strip()

        # Parse JSON from response (handle markdown code blocks)
        json_text = text
        if "```" in text:
            match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
            if match:
                json_text = match.group(1).strip()

        # Try to find JSON object
        match = re.search(r'\{[\s\S]*\}', json_text)
        if match:
            parsed = json.loads(match.group())
            return _validate_response(parsed)

        # If parsing fails, return raw as explanation
        logger.warning("Could not parse LLM response as JSON, returning raw text")
        return {
            "explanation": text,
            "wcag_references": [],
            "code_fix": "",
            "practical_assets": [],
            "validation_hint": "",
        }

    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        return {
            "explanation": f"Error generating response: {str(e)}",
            "wcag_references": [],
            "code_fix": "",
            "practical_assets": [],
            "validation_hint": "",
        }


def _validate_response(data: dict) -> dict:
    """Validate and normalize the LLM response for Audit Mastery."""
    expl = data.get("explanation", {})
    if not isinstance(expl, dict): expl = {"what_is_broken": str(expl)}

    fixes = data.get("fixes", {})
    if not isinstance(fixes, dict): fixes = {"vanilla": str(fixes)}

    result = {
        "explanation": {
            "what_is_broken": expl.get("what_is_broken", ""),
            "impact": expl.get("impact", ""),
            "wcag_sc": expl.get("wcag_sc", ""),
            "intent": expl.get("intent", ""),
            "verification": expl.get("verification", ""),
        },
        "fixes": {
            "vanilla": fixes.get("vanilla", ""),
            "react": fixes.get("react", ""),
            "vue": fixes.get("vue", ""),
            "angular": fixes.get("angular", ""),
        },
        "practical_assets": [],
    }

    # Validate practical assets
    for asset in data.get("practical_assets", []):
        if isinstance(asset, dict) and "asset_type" in asset:
            result["practical_assets"].append({
                "asset_type": asset.get("asset_type", "reference"),
                "name": asset.get("name", ""),
                "content": asset.get("content", ""),
            })

    return result


# ── Remediation Generation (Milestone 4) ──────────────────────

REMEDIATION_SYSTEM_PROMPT = """You are an expert web accessibility remediation engine. Given a specific accessibility issue found during an audit, along with relevant WCAG/ARIA/COGA reference material, produce a structured remediation packet.

Your response MUST be valid JSON with these exact fields:
{
  "explanation": {
    "what_is_broken": "One sentence, plain English description of the violation",
    "impact": "Who it affects and how (human-centric story)",
    "wcag_sc": "Success Criterion number and name",
    "intent": "Why this criterion exists and its importance",
    "verification": "Step-by-step test procedure (automated + manual)"
  },
  "fixes": {
    "vanilla": "Plain HTML/CSS/JS fix specific to the element",
    "react": "React component implementation of the fix",
    "vue": "Vue component implementation of the fix",
    "angular": "Angular component/template implementation of the fix"
  },
  "practical_assets": [
    {
      "asset_type": "template OR aria-pattern OR script OR reference",
      "name": "Name of the resource",
      "content": "The relevant snippet or instruction from the toolkit"
    }
  ]
}

Rules:
1. PLAIN ENGLISH FIRST: Prioritize human impact over technical jargon.
2. ELEMENT-SPECIFIC: Use the provided HTML snippet to write the code fixes.
3. FULL COVERAGE: Provide Vanilla, React, Vue, and Angular variants.
4. VALIDATION: Include a clear test procedure in the explanation block.
5. ONLY VALID JSON: No markdown backticks, no conversational filler.
"""


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


async def generate_remediation(issue: dict, context_chunks: list[dict]) -> dict:
    """
    Generate a structured RemediationPacket for a specific accessibility issue.
    Takes an issue dict + retrieved context chunks, returns parsed remediation dict.
    """
    client = get_client()

    # Build context string
    context_parts = []
    for i, chunk in enumerate(context_chunks):
        meta = chunk.get("metadata", {})
        source = meta.get("source", "unknown")
        silo = meta.get("source_silo", "")
        chunk_type = meta.get("chunk_type", "unknown")
        criterion = meta.get("criterion_id", "")

        header = f"[{silo.upper() if silo else source} | {chunk_type}"
        if criterion:
            header += f" | {criterion}"
        header += f" | relevance: {chunk.get('score', 0):.2f}]"

        context_parts.append(f"{header}\n{chunk['content']}")

    context_str = "\n\n---\n\n".join(context_parts) if context_parts else "No reference material available."

    try:
        response = await client.chat.completions.create(
            model=settings.featherless_model,
            messages=[
                {"role": "system", "content": REMEDIATION_SYSTEM_PROMPT},
                {"role": "user", "content": REMEDIATION_USER_PROMPT.format(
                    rule_id=issue.get("rule_id", "unknown"),
                    severity=issue.get("severity", "moderate"),
                    wcag_criterion=issue.get("wcag_criterion", ""),
                    element=issue.get("element", ""),
                    html_snippet=issue.get("html_snippet", "")[:300],
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
            parsed = json.loads(match.group())
            result = _validate_response(parsed)
            result["issue_id"] = issue.get("issue_id", "")
            result["confidence"] = 0.8 if context_parts else 0.4
            result["needs_manual_review"] = len(context_parts) < 2
            return result

        logger.warning("Could not parse remediation response as JSON")
        return {
            "issue_id": issue.get("issue_id", ""),
            "explanation": text[:500],
            "wcag_references": [],
            "code_fix": "",
            "practical_assets": [],
            "validation_hint": "",
            "confidence": 0.3,
            "needs_manual_review": True,
        }

    except Exception as e:
        logger.error(f"Remediation generation failed: {e}")
        return {
            "issue_id": issue.get("issue_id", ""),
            "explanation": f"Remediation generation failed: {str(e)}",
            "wcag_references": [],
            "code_fix": "",
            "practical_assets": [],
            "validation_hint": "",
            "confidence": 0.0,
            "needs_manual_review": True,
        }


async def enrich_issues(issues: list[dict], max_issues: int = 20) -> list[dict]:
    """
    Enrich the top issues with RAG-backed remediation packets.
    Only processes the first max_issues (by severity) to stay within LLM budget.
    """
    from app.services.retrieval import retrieve_for_issue

    severity_order = {"critical": 4, "serious": 3, "moderate": 2, "minor": 1}
    sorted_issues = sorted(
        issues,
        key=lambda x: severity_order.get(x.get("severity", "minor"), 0),
        reverse=True,
    )

    async def _enrich_task(issue):
        try:
            # Skip if already has a good code fix
            if issue.get("code_fix") and len(issue["code_fix"]) > 50:
                return False

            # Retrieve context
            context = await retrieve_for_issue(issue)

            # Generate remediation
            remediation = await generate_remediation(issue, context)

            # Merge Audit Mastery fields into issue
            if remediation.get("fixes"):
                issue["code_fix"] = remediation["fixes"].get("vanilla", "")
                issue["framework_fixes"] = remediation["fixes"]
            
            expl = remediation.get("explanation", {})
            if expl.get("what_is_broken"):
                issue["description"] = expl["what_is_broken"]
                issue["human_impact"] = expl.get("impact", "")
                issue["wcag_intent"] = expl.get("intent", "")
                issue["test_procedure"] = expl.get("verification", "")
                
            if expl.get("wcag_sc"):
                issue["wcag_criterion"] = expl["wcag_sc"]

            return True
        except Exception as e:
            logger.warning(f"Remediation enrichment failed for {issue.get('rule_id')}: {e}")
            return False

    # Prevent 429 Too Many Requests by limiting concurrency (Featherless AI limit is 4 units)
    semaphore = asyncio.Semaphore(2)
    
    async def _safe_enrich(issue):
        async with semaphore:
            return await _enrich_task(issue)

    # Parallelize top issues
    targets = sorted_issues[:max_issues]
    results = await asyncio.gather(*[_safe_enrich(i) for i in targets])
    
    enriched_count = sum(1 for r in results if r)
    logger.info(f"Enriched {enriched_count}/{len(targets)} issues with RAG remediation")
    return issues
