"""
RAG Poisoning Defense & Security Hardening Engine (§58, §59).

Enforces:
- Strict namespace isolation between trusted standards and untrusted scanned content
- Protection against scanned webpage content attempting to write into the normative standards base
- Prompt injection detection and sanitization in untrusted webpage text/DOM
"""

from __future__ import annotations

import re
from enum import Enum


class KnowledgeNamespace(str, Enum):
    TRUSTED_STANDARDS = "trusted_standards"
    CUSTOMER_KNOWLEDGE = "customer_knowledge"
    SCANNED_CONTENT = "scanned_content"
    LLM_OUTPUT = "llm_output"
    HUMAN_FEEDBACK = "human_feedback"


class SecurityPolicyError(PermissionError):
    """Raised when an untrusted origin attempts to write into a protected namespace."""


# Common adversarial prompt injection patterns found in malicious webpages
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+)?wcag(\s+checks)?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a\s+)?(developer|admin|system|dan|unrestricted)", re.IGNORECASE),
    re.compile(r"system\s+prompt\s*:", re.IGNORECASE),
    re.compile(r"treat\s+all\s+(checks|issues|violations)\s+as\s+pass", re.IGNORECASE),
    re.compile(r"<beacon_override>", re.IGNORECASE),
    re.compile(r"disregard\s+accessibility\s+guidelines", re.IGNORECASE),
    re.compile(r"grant\s+(root|admin|elevated)\s+access", re.IGNORECASE),
]


def validate_namespace_write(
    target_namespace: KnowledgeNamespace | str,
    data_origin: KnowledgeNamespace | str,
) -> bool:
    """
    Guarantees that untrusted origins (e.g. scanned content or arbitrary LLM output)
    can NEVER write to or poison the trusted standards knowledge base (§59).
    """
    target = target_namespace.value if isinstance(target_namespace, KnowledgeNamespace) else str(target_namespace)
    origin = data_origin.value if isinstance(data_origin, KnowledgeNamespace) else str(data_origin)

    if target == KnowledgeNamespace.TRUSTED_STANDARDS.value:
        if origin != KnowledgeNamespace.TRUSTED_STANDARDS.value:
            raise SecurityPolicyError(
                f"RAG Poisoning Violation: Origin '{origin}' is forbidden from writing into '{target}'."
            )

    return True


def detect_prompt_injection(content: str) -> tuple[bool, list[str]]:
    """
    Scans untrusted webpage content for prompt injection or LLM manipulation attempts (§58).
    Returns (has_injection: bool, matched_patterns: list[str]).
    """
    if not content or not isinstance(content, str):
        return False, []

    matches: list[str] = []
    for pattern in PROMPT_INJECTION_PATTERNS:
        match = pattern.search(content)
        if match:
            matches.append(match.group(0))

    return len(matches) > 0, matches


def sanitize_untrusted_text(content: str) -> str:
    """
    Sanitizes untrusted webpage text before passing it to LLM adjudication or RAG context (§58).
    Neutralizes detected prompt injection keywords.
    """
    if not content:
        return ""

    sanitized = content
    for pattern in PROMPT_INJECTION_PATTERNS:
        sanitized = pattern.sub("[REDACTED_PROMPT_INJECTION]", sanitized)

    return sanitized
