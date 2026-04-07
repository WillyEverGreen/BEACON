"""
LLM service: Featherless AI (OpenAI-compatible) for query expansion
and RAG response generation.
"""
import asyncio
import json
import logging
import re
from typing import Any, Optional
from openai import AsyncOpenAI

from app.config import CACHE_STATS, settings
from app.services.fix_cache import get_cache_key, get_cached_fix, store_fix

logger = logging.getLogger(__name__)

# ── Rule-Based Fallback Fixes ─────────────────────────────────────
# Used when Featherless/LLM is completely unreachable.
# These are NOT LLM-generated — they are static, hand-written remediation
# for the top-15 most common rule IDs. This ensures the report is never
# empty even during total LLM outage.
RULE_BASED_FALLBACK_FIXES: dict[str, dict] = {
    "missing-alt": {
        "explanation": {"what_is_broken": "This image has no alt attribute.", "impact": "Screen reader users cannot perceive the image content.", "wcag_sc": "1.1.1 Non-text Content", "intent": "All non-text content must have a text alternative.", "verification": "Inspect the <img> element and confirm alt attribute exists and is descriptive."},
        "fixes": {"vanilla": '<img src="..." alt="Descriptive text about the image">', "react": '<img src={src} alt="Descriptive text" />', "vue": '<img :src="src" alt="Descriptive text" />', "angular": '<img [src]="src" alt="Descriptive text">'},
    },
    "empty-alt": {
        "explanation": {"what_is_broken": "This image has an empty alt attribute but appears to be meaningful.", "impact": "Screen readers skip this image entirely.", "wcag_sc": "1.1.1 Non-text Content", "intent": "Meaningful images must have descriptive alt text.", "verification": "If the image conveys information, add descriptive alt text."},
        "fixes": {"vanilla": '<img src="..." alt="Description of what this image shows">', "react": '<img src={src} alt="Description" />', "vue": '<img :src="src" alt="Description" />', "angular": '<img [src]="src" alt="Description">'},
    },
    "missing-label": {
        "explanation": {"what_is_broken": "This form input has no associated label.", "impact": "Screen reader users don't know what to enter.", "wcag_sc": "1.3.1 Info and Relationships", "intent": "Form controls must have programmatic labels.", "verification": "Check that a <label for='id'> matches the input's id attribute."},
        "fixes": {"vanilla": '<label for="inputId">Field name</label><input id="inputId">', "react": '<label htmlFor="inputId">Field name</label><input id="inputId" />', "vue": '<label for="inputId">Field name</label><input id="inputId" />', "angular": '<label for="inputId">Field name</label><input id="inputId">'},
    },
    "color-contrast": {
        "explanation": {"what_is_broken": "Text does not have enough contrast against its background.", "impact": "Low-vision users cannot read this text.", "wcag_sc": "1.4.3 Contrast (Minimum)", "intent": "Text must have at least 4.5:1 contrast ratio (3:1 for large text).", "verification": "Use a contrast checker tool to verify the foreground/background ratio."},
        "fixes": {"vanilla": "Increase text color darkness or lighten background to meet 4.5:1 ratio.", "react": "Use a CSS variable or theme token with sufficient contrast.", "vue": "Use a CSS variable or theme token with sufficient contrast.", "angular": "Use a CSS variable or theme token with sufficient contrast."},
    },
    "empty-link": {
        "explanation": {"what_is_broken": "This link has no visible or accessible text.", "impact": "Screen users hear 'link' with no description of where it goes.", "wcag_sc": "2.4.4 Link Purpose", "intent": "Every link must have discernible text.", "verification": "Add text content or aria-label to the anchor element."},
        "fixes": {"vanilla": '<a href="...">Descriptive link text</a>', "react": '<a href={url}>Descriptive link text</a>', "vue": '<a :href="url">Descriptive link text</a>', "angular": '<a [href]="url">Descriptive link text</a>'},
    },
    "button-no-name": {
        "explanation": {"what_is_broken": "This button has no accessible name.", "impact": "Screen reader users don't know what the button does.", "wcag_sc": "4.1.2 Name, Role, Value", "intent": "All interactive elements must have accessible names.", "verification": "Add visible text or aria-label to the button."},
        "fixes": {"vanilla": '<button aria-label="Action description">Action</button>', "react": '<button aria-label="Action description">Action</button>', "vue": '<button aria-label="Action description">Action</button>', "angular": '<button aria-label="Action description">Action</button>'},
    },
    "no-focus-style": {
        "explanation": {"what_is_broken": "This focusable element has no visible focus indicator.", "impact": "Keyboard-only users cannot see which element is active.", "wcag_sc": "2.4.7 Focus Visible", "intent": "Focus indicators must be visible for keyboard navigation.", "verification": "Tab to the element and confirm a visible outline or ring appears."},
        "fixes": {"vanilla": ":focus { outline: 2px solid #005fcc; outline-offset: 2px; }", "react": "Apply focus-visible CSS or use a FocusRing component.", "vue": "Apply focus-visible CSS or use a FocusRing component.", "angular": "Apply focus-visible CSS to the component."},
    },
    "keyboard-unreachable": {
        "explanation": {"what_is_broken": "This interactive element cannot be reached via keyboard.", "impact": "Keyboard-only users are completely blocked.", "wcag_sc": "2.1.1 Keyboard", "intent": "All functionality must be operable via keyboard.", "verification": "Tab through the page and verify the element receives focus."},
        "fixes": {"vanilla": "Use a native <button> or <a> element, or add tabindex='0' and keydown handlers.", "react": "Use a native button element instead of div onClick.", "vue": "Use a native button element instead of div @click.", "angular": "Use a native button element instead of (click) on a div."},
    },
    "heading-skip": {
        "explanation": {"what_is_broken": "Heading levels are skipped (e.g. h1 → h3).", "impact": "Screen reader users lose the logical document outline.", "wcag_sc": "1.3.1 Info and Relationships", "intent": "Heading hierarchy must be sequential.", "verification": "Check that headings flow h1 → h2 → h3 without gaps."},
        "fixes": {"vanilla": "Change the heading level to follow sequential order.", "react": "Ensure heading levels are sequential in the component tree.", "vue": "Ensure heading levels are sequential in the component tree.", "angular": "Ensure heading levels are sequential in the component tree."},
    },
    "generic-link-text": {
        "explanation": {"what_is_broken": "Link text is generic ('click here', 'read more').", "impact": "Screen reader users navigating by links cannot understand link destinations.", "wcag_sc": "2.4.4 Link Purpose", "intent": "Link text must describe its destination or function.", "verification": "Read the link text in isolation — does it make sense?"},
        "fixes": {"vanilla": "Replace 'click here' with descriptive text like 'View pricing plans'.", "react": "Use descriptive children text in the Link component.", "vue": "Use descriptive text in the router-link.", "angular": "Use descriptive text in the routerLink."},
    },
}


def _get_fallback_remediation(issue: dict) -> dict:
    """Return a static rule-based fix when LLM is unreachable."""
    rule_id = issue.get("rule_id", "")
    fallback = RULE_BASED_FALLBACK_FIXES.get(rule_id)
    if fallback:
        return {
            **fallback,
            "issue_id": issue.get("issue_id", ""),
            "confidence": 0.6,
            "needs_manual_review": True,
            "practical_assets": [],
            "_fallback": True,
        }
    # Generic fallback for unknown rules
    return {
        "issue_id": issue.get("issue_id", ""),
        "explanation": f"Rule '{rule_id}' violation detected. Refer to WCAG criterion {issue.get('wcag_criterion', '')} for guidance.",
        "fixes": {},
        "practical_assets": [],
        "confidence": 0.0,
        "needs_manual_review": True,
        "_fallback": True,
    }


# Async client (cached)
_client: Optional[AsyncOpenAI] = None
_llm_response_cache: dict[str, dict[str, Any]] = {}
_ENRICHMENT_SEMAPHORE: Optional[asyncio.Semaphore] = None
_ENRICHMENT_SEMAPHORE_LIMIT = 0


def get_client() -> AsyncOpenAI:
    """Get or init the Featherless (OpenAI-compatible) async client."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.featherless_api_key,
            base_url=settings.featherless_base_url,
        )
    return _client


def _estimate_llm_cost(prompt_tokens: int, completion_tokens: int) -> float:
    prompt_rate = max(0.0, float(getattr(settings, "llm_prompt_cost_per_1k_tokens", 0.0) or 0.0))
    completion_rate = max(0.0, float(getattr(settings, "llm_completion_cost_per_1k_tokens", 0.0) or 0.0))
    return round(
        (max(0, int(prompt_tokens)) / 1000.0) * prompt_rate
        + (max(0, int(completion_tokens)) / 1000.0) * completion_rate,
        6,
    )


def _normalize_usage(response_usage: Any) -> dict[str, float | int]:
    prompt_tokens = int(getattr(response_usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(response_usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(response_usage, "total_tokens", prompt_tokens + completion_tokens) or 0)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": _estimate_llm_cost(prompt_tokens, completion_tokens),
    }


def _enrichment_semaphore() -> asyncio.Semaphore:
    global _ENRICHMENT_SEMAPHORE, _ENRICHMENT_SEMAPHORE_LIMIT
    limit = max(1, int(getattr(settings, "enrichment_max_concurrency", 2) or 2))
    if _ENRICHMENT_SEMAPHORE is None or _ENRICHMENT_SEMAPHORE_LIMIT != limit:
        _ENRICHMENT_SEMAPHORE = asyncio.Semaphore(limit)
        _ENRICHMENT_SEMAPHORE_LIMIT = limit
    return _ENRICHMENT_SEMAPHORE


def _llm_cache_key(issue: dict) -> str:
    return get_cache_key(issue.get("rule_id", "unknown"), issue.get("html_snippet", ""))


def _get_llm_cached_remediation(issue: dict) -> Optional[dict]:
    if not bool(getattr(settings, "enrichment_enable_llm_cache", True)):
        return None
    return _llm_response_cache.get(_llm_cache_key(issue))


def _store_llm_cached_remediation(issue: dict, remediation: dict) -> None:
    if not bool(getattr(settings, "enrichment_enable_llm_cache", True)):
        return

    key = _llm_cache_key(issue)
    max_entries = max(1, int(getattr(settings, "llm_cache_max_entries", 2000) or 2000))
    if len(_llm_response_cache) >= max_entries and key not in _llm_response_cache:
        # Keep eviction cheap and deterministic for repeatable tests.
        oldest_key = next(iter(_llm_response_cache), None)
        if oldest_key is not None:
            _llm_response_cache.pop(oldest_key, None)

    _llm_response_cache[key] = remediation
    CACHE_STATS["llm_writes"] = int(CACHE_STATS.get("llm_writes", 0) or 0) + 1


def _framework_hints(fixes: dict[str, Any] | None) -> dict[str, str]:
    src = fixes if isinstance(fixes, dict) else {}
    return {
        "vanilla": str(src.get("vanilla", "")),
        "react": str(src.get("react", "")),
        "vue": str(src.get("vue", "")),
        "angular": str(src.get("angular", "")),
    }


def _build_fix_object(issue: dict, fixes: dict[str, str]) -> dict[str, Any]:
    return {
        "description": str(issue.get("description", "") or "").strip(),
        "before": str(issue.get("html_snippet", "") or "").strip()[:500],
        "after": str(fixes.get("vanilla", "") or "").strip(),
        "framework_hints": _framework_hints(fixes),
    }


def _fix_object_valid(fix: dict[str, Any]) -> bool:
    if not isinstance(fix, dict):
        return False

    description = str(fix.get("description", "") or "").strip()
    before = str(fix.get("before", "") or "").strip()
    after = str(fix.get("after", "") or "").strip()
    framework_hints = fix.get("framework_hints")

    if not isinstance(framework_hints, dict):
        return False
    if not description or not before or not after:
        return False
    for key in ("vanilla", "react", "vue", "angular"):
        if key not in framework_hints:
            return False
    return True


def _apply_remediation_to_issue(issue: dict, remediation: dict, source: str) -> None:
    fixes = _framework_hints(remediation.get("fixes", {}))
    issue["code_fix"] = fixes.get("vanilla", "")
    issue["framework_fixes"] = fixes

    expl = remediation.get("explanation", {})
    if isinstance(expl, dict):
        if expl.get("what_is_broken"):
            issue["description"] = expl.get("what_is_broken", issue.get("description", ""))
        if expl.get("impact"):
            issue["human_impact"] = expl.get("impact", "")
        if expl.get("intent"):
            issue["wcag_intent"] = expl.get("intent", "")
        if expl.get("verification"):
            issue["test_procedure"] = expl.get("verification", "")
        if expl.get("wcag_sc"):
            issue["wcag_criterion"] = expl.get("wcag_sc", issue.get("wcag_criterion", ""))

    fix_obj = _build_fix_object(issue, issue.get("framework_fixes", {}))
    if not _fix_object_valid(fix_obj):
        if not str(fix_obj.get("description", "") or "").strip():
            fix_obj["description"] = str(issue.get("description", "") or "Accessibility issue requires remediation.").strip()
        if not str(fix_obj.get("before", "") or "").strip():
            fix_obj["before"] = str(issue.get("element", "") or "<unknown-element>").strip()
        if not str(fix_obj.get("after", "") or "").strip():
            fix_obj["after"] = str(issue.get("suggested_fix", "") or issue.get("code_fix", "") or "Refer to WCAG techniques for compliant remediation.").strip()
        fix_obj["framework_hints"] = _framework_hints(issue.get("framework_fixes", {}))

    issue["fix"] = fix_obj
    issue["_enrichment_source"] = source


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
You help developers fix accessibility issues by providing clear explanations, WCAG references, and code fixes.

Your response MUST be in valid JSON format with these exact fields:
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
            timeout=30.0,
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

BATCH_REMEDIATION_SYSTEM_PROMPT = """You are an expert web accessibility remediation engine.
Given multiple related accessibility issues sharing the same WCAG criterion, along with reference material, produce a structured batched remediation array.

Your response MUST be a valid JSON array of objects. Each object must contain:
[
  {
    "explanation": {
      "what_is_broken": "One sentence description of the violation",
      "impact": "Who it affects and how",
      "wcag_sc": "Success Criterion number and name",
      "intent": "Why this criterion exists",
      "verification": "Test procedure"
    },
    "fixes": {
      "vanilla": "Plain HTML/CSS/JS fix specific to the element",
      "react": "React fix",
      "vue": "Vue fix",
      "angular": "Angular fix"
    },
    "practical_assets": []
  }
]
The array MUST have exactly the same number of elements as the issues provided, in the exact same order."""

BATCH_REMEDIATION_USER_PROMPT = """
WCAG Criterion: {wcag_criterion}

=== KNOWLEDGE BASE CONTEXT ===
{context}
==============================

I have found {count} instances of the exact same vulnerability.
For each of the following HTML snippets, generate a strict remediation packet. Keep explanations tight.

ISSUES TO FIX:
{issues_list}
"""

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
            timeout=30.0,
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


async def generate_remediation_batch(
    issues_group: list[dict],
    context_str: str,
    wcag_criterion: str,
) -> tuple[list[dict], dict[str, float | int]]:
    client = get_client()
    usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
    }
    
    # Build list of HTML snippets
    snippets = []
    for idx, iss in enumerate(issues_group):
        html_snip = iss.get("html_snippet", "")[:300]
        snippets.append(f"[{idx+1}] {html_snip}")
    issues_list_str = "\n".join(snippets)

    try:
        response = await client.chat.completions.create(
            model=settings.featherless_model,
            messages=[
                {"role": "system", "content": BATCH_REMEDIATION_SYSTEM_PROMPT},
                {"role": "user", "content": BATCH_REMEDIATION_USER_PROMPT.format(
                    wcag_criterion=wcag_criterion,
                    context=context_str,
                    count=len(issues_group),
                    issues_list=issues_list_str,
                )},
            ],
            max_tokens=3000,
            temperature=0.2,
            timeout=40.0,
        )
        usage = _normalize_usage(getattr(response, "usage", None))

        text = response.choices[0].message.content.strip()
        
        # Extract JSON array
        json_text = text
        if "```" in text:
            match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
            if match:
                json_text = match.group(1).strip()

        match = re.search(r'\[[\s\S]*\]', json_text)
        if match:
            parsed_array = json.loads(match.group())
            if isinstance(parsed_array, list) and len(parsed_array) > 0:
                if len(parsed_array) != len(issues_group):
                    logger.warning(f"Batch generation length mismatch! Expected {len(issues_group)}, got {len(parsed_array)}. Using partial results.")
                validated_results = [_validate_response(item) for item in parsed_array]
                return validated_results, usage
            
        logger.warning("Could not parse batch remediation response as JSON array")
        return [], usage

    except Exception as e:
        logger.error(f"Batch remediation generation failed: {e}")
        return [], usage


async def enrich_issues(
    issues: list[dict],
    max_issues: int = 20,
    *,
    max_tokens_per_audit: Optional[int] = None,
    max_llm_cost_per_audit: Optional[float] = None,
    return_meta: bool = False,
) -> list[dict] | tuple[list[dict], dict[str, Any]]:
    """Enrich the top issues using cache-first and bounded batched RAG remediation."""
    from app.services.retrieval import retrieve_for_issue

    severity_order = {"critical": 4, "serious": 3, "moderate": 2, "minor": 1}
    sorted_issues = sorted(
        issues,
        key=lambda x: severity_order.get(x.get("severity", "minor"), 0),
        reverse=True,
    )[:max_issues]

    max_token_budget = int(
        settings.max_tokens_per_audit if max_tokens_per_audit is None else max_tokens_per_audit
    )
    max_cost_budget = float(
        settings.max_llm_cost_per_audit if max_llm_cost_per_audit is None else max_llm_cost_per_audit
    )

    enrichment_meta: dict[str, Any] = {
        "cache": {
            "llm_hits": 0,
            "llm_misses": 0,
            "fix_hits": 0,
            "fix_misses": 0,
        },
        "llm": {
            "calls": 0,
            "retries": 0,
        },
        "retrieval_debug": [],
        "budget": {
            "max_tokens_per_audit": max_token_budget,
            "max_llm_cost_per_audit": max_cost_budget,
            "tokens_used": 0,
            "cost_used": 0.0,
            "budget_exhausted": max_token_budget <= 0 or max_cost_budget <= 0,
        },
    }

    cache_misses: list[dict] = []
    enriched_count = 0
    semaphore = _enrichment_semaphore()
    budget_lock = asyncio.Lock()

    def _apply_rule_fallback(group_issues: list[dict], source: str) -> int:
        applied = 0
        for issue in group_issues:
            fallback = _get_fallback_remediation(issue)
            _apply_remediation_to_issue(issue, fallback, source)
            applied += 1
        return applied

    async def _budget_available() -> bool:
        async with budget_lock:
            token_budget_ok = max_token_budget > 0 and enrichment_meta["budget"]["tokens_used"] < max_token_budget
            cost_budget_ok = max_cost_budget > 0 and enrichment_meta["budget"]["cost_used"] < max_cost_budget
            available = token_budget_ok and cost_budget_ok
            if not available:
                enrichment_meta["budget"]["budget_exhausted"] = True
            return available

    async def _record_usage(usage: dict[str, float | int]) -> None:
        async with budget_lock:
            enrichment_meta["budget"]["tokens_used"] += int(usage.get("total_tokens", 0) or 0)
            enrichment_meta["budget"]["cost_used"] = round(
                float(enrichment_meta["budget"]["cost_used"]) + float(usage.get("estimated_cost_usd", 0.0) or 0.0),
                6,
            )
            if (
                enrichment_meta["budget"]["tokens_used"] >= max_token_budget
                or enrichment_meta["budget"]["cost_used"] >= max_cost_budget
            ):
                enrichment_meta["budget"]["budget_exhausted"] = True

    # 1) Strict cache-first chain: LLM cache -> Fix Library -> LLM call
    for issue in sorted_issues:
        if issue.get("code_fix") and len(str(issue.get("code_fix", ""))) > 50:
            _apply_remediation_to_issue(
                issue,
                {
                    "explanation": {
                        "what_is_broken": issue.get("description", ""),
                        "impact": issue.get("human_impact", ""),
                        "wcag_sc": issue.get("wcag_criterion", ""),
                        "intent": issue.get("wcag_intent", ""),
                        "verification": issue.get("test_procedure", ""),
                    },
                    "fixes": issue.get("framework_fixes", {"vanilla": issue.get("code_fix", "")}),
                },
                source="existing_fix",
            )
            continue

        llm_cached = _get_llm_cached_remediation(issue)
        if llm_cached:
            CACHE_STATS["llm_hits"] = CACHE_STATS.get("llm_hits", 0) + 1
            enrichment_meta["cache"]["llm_hits"] += 1
            _apply_remediation_to_issue(issue, llm_cached, source="llm_cache")
            enriched_count += 1
            continue

        CACHE_STATS["llm_misses"] = CACHE_STATS.get("llm_misses", 0) + 1
        enrichment_meta["cache"]["llm_misses"] += 1

        rule_id = issue.get("rule_id", "unknown")
        html_snippet = issue.get("html_snippet", "")
        cached_fix = get_cached_fix(rule_id, html_snippet)
        if cached_fix:
            CACHE_STATS["fix_hits"] = CACHE_STATS.get("fix_hits", 0) + 1
            enrichment_meta["cache"]["fix_hits"] += 1
            _apply_remediation_to_issue(issue, cached_fix, source="fix_library_cache")
            _store_llm_cached_remediation(issue, cached_fix)
            enriched_count += 1
            continue

        CACHE_STATS["fix_misses"] = CACHE_STATS.get("fix_misses", 0) + 1
        enrichment_meta["cache"]["fix_misses"] += 1
        cache_misses.append(issue)

    if not cache_misses:
        logger.info(f"All {len(sorted_issues)} issues fulfilled from cache.")
        if return_meta:
            return issues, enrichment_meta
        return issues

    # 2) Batch misses by criterion
    grouped_misses: dict[str, list[dict]] = {}
    for issue in cache_misses:
        group_key = issue.get("wcag_criterion") or issue.get("rule_id") or "unknown"
        grouped_misses.setdefault(group_key, []).append(issue)

    async def process_batch(group_key: str, group_iss: list[dict]) -> int:
        async with semaphore:
            try:
                if not await _budget_available():
                    return _apply_rule_fallback(group_iss, "rule_fallback_budget")

                try:
                    context_chunks = await retrieve_for_issue(group_iss[0])
                except Exception:
                    context_chunks = []

                primary_issue = group_iss[0] if group_iss else {}
                query_hint_parts = [
                    str(primary_issue.get("wcag_criterion", "") or "").strip(),
                    str(primary_issue.get("rule_id", "") or "").strip(),
                    str(primary_issue.get("description", "") or "").strip()[:160],
                ]
                query_hint = " | ".join(part for part in query_hint_parts if part)
                enrichment_meta["retrieval_debug"].append(
                    {
                        "group": group_key,
                        "query": query_hint,
                        "retrieved_chunks": len(context_chunks),
                        "similarity_scores": [
                            round(float(chunk.get("score", 0.0) or 0.0), 4)
                            for chunk in context_chunks[:5]
                        ],
                    }
                )

                context_parts = [chunk.get("content", "") for chunk in context_chunks]
                context_str = "\n\n---\n\n".join(context_parts) if context_parts else "No reference material."

                attempts = max(1, int(getattr(settings, "enrichment_retry_attempts", 3) or 3))
                base_delay = max(0.0, float(getattr(settings, "enrichment_retry_base_delay_seconds", 0.4) or 0.4))
                max_delay = max(base_delay, float(getattr(settings, "enrichment_retry_max_delay_seconds", 3.0) or 3.0))

                results: list[dict] = []
                for attempt in range(attempts):
                    if not await _budget_available():
                        break

                    enrichment_meta["llm"]["calls"] += 1
                    batch_results, usage = await generate_remediation_batch(group_iss, context_str, group_key)
                    await _record_usage(usage)

                    if batch_results:
                        results = batch_results
                        break

                    if attempt < attempts - 1:
                        enrichment_meta["llm"]["retries"] += 1
                        delay = min(max_delay, base_delay * (2 ** attempt))
                        if delay > 0:
                            await asyncio.sleep(delay)

                if not results:
                    source = "rule_fallback_budget" if enrichment_meta["budget"]["budget_exhausted"] else "rule_fallback"
                    logger.warning(f"LLM unavailable for batch '{group_key}'. Applying {source} remediation.")
                    return _apply_rule_fallback(group_iss, source)

                saved_count = 0
                for idx, issue in enumerate(group_iss):
                    if idx >= len(results):
                        break

                    remediation = results[idx]
                    _apply_remediation_to_issue(issue, remediation, source="llm")
                    _store_llm_cached_remediation(issue, remediation)
                    store_fix(issue.get("rule_id", "unknown"), issue.get("html_snippet", ""), remediation)
                    saved_count += 1

                return saved_count
            except Exception as e:
                logger.error(f"LLM batch failed for {group_key}: {e}. Applying rule-based fallback.")
                return _apply_rule_fallback(group_iss, "rule_fallback")

    batch_tasks = [process_batch(k, v) for k, v in grouped_misses.items()]
    batch_results = await asyncio.gather(*batch_tasks)
    enriched_count += sum(batch_results)

    logger.info(
        f"Enriched {enriched_count}/{len(sorted_issues)} issues "
        f"({len(sorted_issues) - len(cache_misses)} from cache, "
        f"{enrichment_meta['budget']['tokens_used']} tokens, "
        f"${enrichment_meta['budget']['cost_used']:.4f})"
    )

    if return_meta:
        return issues, enrichment_meta
    return issues
