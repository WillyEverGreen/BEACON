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
from app.services.fix_cache import get_cached_fix, store_fix

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


async def generate_remediation_batch(issues_group: list[dict], context_str: str, wcag_criterion: str) -> list[dict]:
    client = get_client()
    
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
                return validated_results
            
        logger.warning("Could not parse batch remediation response as JSON array")
        return []

    except Exception as e:
        logger.error(f"Batch remediation generation failed: {e}")
        return []


async def enrich_issues(issues: list[dict], max_issues: int = 20) -> list[dict]:
    """
    Enrich the top issues using FixCache and batched RAG remediation.
    """
    from app.services.retrieval import retrieve_for_issue

    severity_order = {"critical": 4, "serious": 3, "moderate": 2, "minor": 1}
    sorted_issues = sorted(
        issues,
        key=lambda x: severity_order.get(x.get("severity", "minor"), 0),
        reverse=True,
    )[:max_issues]

    cache_misses = []
    enriched_count = 0

    # 1. Check FixCache first
    for issue in sorted_issues:
        # Skip if already has a good code fix
        if issue.get("code_fix") and len(issue["code_fix"]) > 50:
            continue
            
        rule_id = issue.get("rule_id", "unknown")
        html_snippet = issue.get("html_snippet", "")
        
        cached_fix = get_cached_fix(rule_id, html_snippet)
        if cached_fix:
            # Apply cached fix
            issue["code_fix"] = cached_fix.get("fixes", {}).get("vanilla", "")
            issue["framework_fixes"] = cached_fix.get("fixes", {})
            expl = cached_fix.get("explanation", {})
            issue["description"] = expl.get("what_is_broken", issue.get("description", ""))
            issue["human_impact"] = expl.get("impact", "")
            issue["wcag_intent"] = expl.get("intent", "")
            issue["test_procedure"] = expl.get("verification", "")
            issue["wcag_criterion"] = expl.get("wcag_sc", issue.get("wcag_criterion", ""))
            enriched_count += 1
        else:
            cache_misses.append(issue)

    if not cache_misses:
        logger.info(f"All {len(sorted_issues)} issues fulfilled from cache.")
        return issues

    # 2. Batch misses by criterion
    grouped_misses = {}
    for issue in cache_misses:
        # Best effort group by WCAG criterion or rule_id
        group_key = issue.get("wcag_criterion") or issue.get("rule_id") or "unknown"
        grouped_misses.setdefault(group_key, []).append(issue)

    semaphore = asyncio.Semaphore(2)

    async def process_batch(group_key: str, group_iss: list[dict]):
        async with semaphore:
            try:
                # Retrieve context (use the first issue as representative for the group)
                context_chunks = await retrieve_for_issue(group_iss[0])
                
                # Format context string (context_chunks is list[dict] with content, metadata, score)
                context_parts = []
                for chunk in context_chunks:
                    context_parts.append(chunk.get('content', ''))
                context_str = "\n\n---\n\n".join(context_parts) if context_parts else "No reference material."
                
                # Generate batched array
                results = await generate_remediation_batch(group_iss, context_str, group_key)
                if not results:
                    # LLM returned nothing — use rule-based fallback
                    logger.warning(f"LLM returned empty for batch '{group_key}'. Applying rule-based fallback.")
                    fallback_count = 0
                    for issue in group_iss:
                        fb = _get_fallback_remediation(issue)
                        fixes = fb.get("fixes", {})
                        if fixes:
                            issue["code_fix"] = fixes.get("vanilla", "")
                            issue["framework_fixes"] = fixes
                            expl = fb.get("explanation", {})
                            if isinstance(expl, dict) and expl.get("what_is_broken"):
                                issue["description"] = expl["what_is_broken"]
                                issue["human_impact"] = expl.get("impact", "")
                            issue["_enrichment_source"] = "rule_fallback"
                            fallback_count += 1
                    return fallback_count
                    
                saved_count = 0
                for idx, issue in enumerate(group_iss):
                    if idx >= len(results):
                        break  # Partial batch — LLM returned fewer than expected
                    remediation = results[idx]
                    
                    # Apply
                    fixes = remediation.get("fixes", {})
                    issue["code_fix"] = fixes.get("vanilla", "")
                    issue["framework_fixes"] = fixes
                    
                    expl = remediation.get("explanation", {})
                    if expl.get("what_is_broken"):
                        issue["description"] = expl["what_is_broken"]
                        issue["human_impact"] = expl.get("impact", "")
                        issue["wcag_intent"] = expl.get("intent", "")
                        issue["test_procedure"] = expl.get("verification", "")
                        issue["wcag_criterion"] = expl.get("wcag_sc", issue.get("wcag_criterion", ""))
                    
                    issue["_enrichment_source"] = "llm"
                    # Store to cache for future audits
                    store_fix(issue.get("rule_id", "unknown"), issue.get("html_snippet", ""), remediation)
                    saved_count += 1
                    
                return saved_count
            except Exception as e:
                logger.error(f"LLM batch failed for {group_key}: {e}. Applying rule-based fallback.")
                fallback_count = 0
                for issue in group_iss:
                    fb = _get_fallback_remediation(issue)
                    fixes = fb.get("fixes", {})
                    if fixes:
                        issue["code_fix"] = fixes.get("vanilla", "")
                        issue["framework_fixes"] = fixes
                        expl = fb.get("explanation", {})
                        if isinstance(expl, dict) and expl.get("what_is_broken"):
                            issue["description"] = expl["what_is_broken"]
                            issue["human_impact"] = expl.get("impact", "")
                        issue["_enrichment_source"] = "rule_fallback"
                        fallback_count += 1
                return fallback_count

    batch_tasks = [process_batch(k, v) for k, v in grouped_misses.items()]
    batch_results = await asyncio.gather(*batch_tasks)
    
    enriched_count += sum(batch_results)
    logger.info(f"Enriched {enriched_count}/{len(sorted_issues)} issues ({len(sorted_issues) - len(cache_misses)} from cache)")
    
    return issues
