"""
LLM service: Featherless AI (OpenAI-compatible) for query expansion
and RAG response generation.
"""
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
You help developers fix accessibility issues by providing clear explanations, WCAG references, and ready-to-use code fixes.

You MUST respond using the following context retrieved from the WCAG 2.2 guidelines and the wcag-aaa-web-design toolkit repository.

Your response MUST be in valid JSON format with these exact fields:
{
  "explanation": "Clear explanation of why this is an accessibility issue and what it means for users with disabilities",
  "wcag_references": [
    {
      "criterion_id": "e.g. 1.4.3",
      "name": "e.g. Contrast (Minimum)",
      "level": "A or AA or AAA",
      "description": "Brief description of what this criterion requires"
    }
  ],
  "code_fix": "Complete, ready-to-use HTML/CSS/JS code snippet that resolves the issue. Include all necessary attributes, ARIA roles, and styles. Must be production-ready.",
  "practical_assets": [
    {
      "asset_type": "template OR aria-pattern OR script OR reference",
      "name": "Name of the referenced resource from the toolkit",
      "content": "The relevant snippet or instruction from the toolkit"
    }
  ],
  "validation_hint": "How to verify the fix: describe automated checks (scripts) and manual checks the developer should perform"
}

Rules:
1. ALWAYS cite specific WCAG criterion IDs (e.g., 1.4.3, 2.1.1)
2. ALWAYS provide a working code fix, not just explanations
3. ALWAYS reference practical toolkit resources (templates, scripts, ARIA patterns) when available in context
4. If the context mentions check_contrast.py or validate_accessibility.sh, reference them in validation_hint
5. If ARIA patterns are relevant, include them in practical_assets
6. Respond ONLY with valid JSON, no markdown, no explanation outside the JSON"""


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
    """Validate and normalize the LLM response."""
    result = {
        "explanation": data.get("explanation", ""),
        "wcag_references": [],
        "code_fix": data.get("code_fix", ""),
        "practical_assets": [],
        "validation_hint": data.get("validation_hint", ""),
    }

    # Validate WCAG references
    for ref in data.get("wcag_references", []):
        if isinstance(ref, dict) and "criterion_id" in ref:
            result["wcag_references"].append({
                "criterion_id": ref.get("criterion_id", ""),
                "name": ref.get("name", ""),
                "level": ref.get("level", ""),
                "description": ref.get("description", ""),
            })

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
  "practical_assets": [
    {
      "asset_type": "template | aria-pattern | script | reference",
      "name": "Name of the resource",
      "content": "Relevant code snippet or instruction"
    }
  ],
  "validation_hint": "How to verify the fix: specific steps for automated and manual testing"
}

Rules:
1. The code_fix MUST be specific to the element identified in the issue
2. ALWAYS cite the specific WCAG criterion (e.g., 1.4.3, 2.1.1)
3. Include ARIA patterns when relevant
4. Reference practical toolkit resources from context when available
5. Respond ONLY with valid JSON"""


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


async def enrich_issues_with_remediation(
    issues: list[dict],
    max_issues: int = 10,
) -> list[dict]:
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

    enriched_count = 0
    for issue in sorted_issues[:max_issues]:
        try:
            # Skip if already has a good code fix
            if issue.get("code_fix") and len(issue["code_fix"]) > 50:
                continue

            # Retrieve context
            context = await retrieve_for_issue(issue)

            # Generate remediation
            remediation = await generate_remediation(issue, context)

            # Merge remediation into issue
            if remediation.get("code_fix"):
                issue["code_fix"] = remediation["code_fix"]
            if remediation.get("explanation") and len(remediation["explanation"]) > len(issue.get("description", "")):
                issue["suggested_fix"] = remediation["explanation"]
            if remediation.get("validation_hint"):
                issue["reproducibility"] = remediation["validation_hint"]

            enriched_count += 1

        except Exception as e:
            logger.warning(f"Remediation enrichment failed for {issue.get('rule_id')}: {e}")

    logger.info(f"Enriched {enriched_count}/{min(max_issues, len(issues))} issues with RAG remediation")
    return issues
