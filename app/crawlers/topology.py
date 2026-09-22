"""Native Multi-Signal DOM Tag-Tree Topology Intelligence for BEACON.

Extracts multi-signal structural and interactive fingerprints:
- Structural DOM tag hierarchy
- Landmark signatures (header, nav, main, footer, aside)
- ARIA role distribution
- Interactive element counts (buttons, links, form inputs)
- Form density and text-to-tag ratios

Supports adaptive template sampling and frontier-aware low-information-gain stopping.
"""

from __future__ import annotations

import hashlib
import logging
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

from app.models.contracts import Fingerprint

logger = logging.getLogger(__name__)

_STRUCTURAL_TAGS = frozenset({
    "html", "body", "header", "nav", "main", "aside", "section", "article",
    "footer", "form", "table", "thead", "tbody", "tr", "div", "ul", "ol",
    "dl", "dialog", "h1", "h2", "h3"
})

_LANDMARK_TAGS = frozenset({"header", "nav", "main", "aside", "footer"})
_INTERACTIVE_TAGS = frozenset({"button", "a", "input", "select", "textarea"})

_MAX_TAG_DEPTH = 12
_DEFAULT_MAX_PER_TEMPLATE = 2
_ADAPTIVE_MAX_PER_TEMPLATE = 4
_DEFAULT_EARLY_STOP_CONSECUTIVE = 5


class _MultiSignalParser(HTMLParser):
    """Fast HTML parser extracting structural tags, landmarks, roles, and interactive counts."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.structural_tags: list[str] = []
        self.landmarks: set[str] = set()
        self.roles: set[str] = set()
        self.interactive_counts: dict[str, int] = {"button": 0, "link": 0, "input": 0}
        self.form_count = 0
        self.total_chars = 0
        self.text_chars = 0
        self._current_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        attr_map = {k.lower(): (v or "").strip().lower() for k, v in attrs}

        # Landmarks
        if tag_lower in _LANDMARK_TAGS:
            self.landmarks.add(tag_lower)

        # ARIA Roles
        role = attr_map.get("role")
        if role:
            self.roles.add(role)
            if role in {"banner", "navigation", "main", "complementary", "contentinfo"}:
                self.landmarks.add(role)

        # Interactive controls
        if tag_lower == "button" or role == "button":
            self.interactive_counts["button"] += 1
        elif tag_lower == "a" and "href" in attr_map:
            self.interactive_counts["link"] += 1
        elif tag_lower in {"input", "select", "textarea"}:
            self.interactive_counts["input"] += 1
        elif tag_lower == "form":
            self.form_count += 1

        # Structural skeleton
        if tag_lower in _STRUCTURAL_TAGS and self._current_depth < _MAX_TAG_DEPTH:
            self.structural_tags.append(tag_lower)
            self._current_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in _STRUCTURAL_TAGS and self._current_depth > 0:
            self._current_depth -= 1

    def handle_data(self, data: str) -> None:
        content = data.strip()
        if content:
            self.text_chars += len(content)


def extract_multi_signal_fingerprint(html: str) -> Fingerprint:
    """Extract a multi-signal Fingerprint from an HTML string."""
    if not html or not html.strip():
        return Fingerprint(dom_hash="empty")

    parser = _MultiSignalParser()
    sample_length = min(len(html), 150_000)
    try:
        parser.feed(html[:sample_length])
    except Exception as exc:
        logger.debug("Failed extracting multi-signal fingerprint: %s", exc)
        return Fingerprint(dom_hash=hashlib.sha256(html[:1000].encode("utf-8", errors="ignore")).hexdigest()[:16])

    skeleton = ">".join(parser.structural_tags[:120])
    dom_hash = hashlib.sha256(skeleton.encode("utf-8")).hexdigest()[:16] if skeleton else "empty"

    text_ratio = 0.0
    if sample_length > 0:
        text_ratio = round(parser.text_chars / sample_length, 3)

    return Fingerprint(
        dom_hash=dom_hash,
        landmarks=tuple(sorted(parser.landmarks)),
        roles=tuple(sorted(parser.roles)),
        interactive_counts=dict(parser.interactive_counts),
        form_count=parser.form_count,
        text_density_ratio=text_ratio,
    )


class AdaptiveTopologyTracker:
    """Tracks structural templates with adaptive sampling and frontier-aware early stopping."""

    def __init__(
        self,
        base_max_per_template: int = _DEFAULT_MAX_PER_TEMPLATE,
        adaptive_cap: int = _ADAPTIVE_MAX_PER_TEMPLATE,
        early_stop_consecutive: int = _DEFAULT_EARLY_STOP_CONSECUTIVE,
        min_archetypes_before_early_stop: int = 3,
    ) -> None:
        self.base_max_per_template = base_max_per_template
        self.adaptive_cap = adaptive_cap
        self.early_stop_consecutive = early_stop_consecutive
        self.min_archetypes_before_early_stop = min_archetypes_before_early_stop

        # template_id -> list of (url, Fingerprint)
        self.templates: dict[str, list[tuple[str, Fingerprint]]] = {}
        self.consecutive_low_gain = 0
        self.total_evaluated = 0
        self.total_sampled = 0
        self.stopped_early = False
        self.stop_reason: str | None = None

    def evaluate_page(
        self,
        url: str,
        html: str,
        unexplored_frontier_urls: list[str] | None = None,
    ) -> tuple[Fingerprint, bool, bool]:
        """Evaluate a page's multi-signal archetype and determine whether to audit it.

        Returns:
            (fingerprint, is_new_template, should_sample)
        """
        self.total_evaluated += 1
        fp = extract_multi_signal_fingerprint(html)
        template_id = fp.dom_hash

        if template_id not in self.templates:
            # Entirely new archetype
            self.templates[template_id] = [(url, fp)]
            self.consecutive_low_gain = 0
            self.total_sampled += 1
            return fp, True, True

        existing_samples = self.templates[template_id]
        sampled_count = len(existing_samples)

        # Baseline quota not yet reached
        if sampled_count < self.base_max_per_template:
            existing_samples.append((url, fp))
            self.consecutive_low_gain = 0
            self.total_sampled += 1
            return fp, False, True

        # Adaptive variance check: did interactive elements vary significantly?
        baseline_fp = existing_samples[0][1]
        baseline_interactive = sum(baseline_fp.interactive_counts.values())
        current_interactive = sum(fp.interactive_counts.values())

        variance = 0.0
        if baseline_interactive > 0:
            variance = abs(current_interactive - baseline_interactive) / baseline_interactive

        if variance > 0.25 and sampled_count < self.adaptive_cap:
            logger.info("Adaptive sampling triggered for %s (variance=%.1f%%)", url, variance * 100)
            existing_samples.append((url, fp))
            self.consecutive_low_gain = 0
            self.total_sampled += 1
            return fp, False, True

        # Low information gain
        self.consecutive_low_gain += 1

        # Check early stopping conditions safely
        if self.consecutive_low_gain >= self.early_stop_consecutive:
            # Condition 1: Must have discovered at least minimum expected archetypes
            archetypes_sufficient = len(self.templates) >= self.min_archetypes_before_early_stop
            
            # Condition 2: Frontier diversity check (no unexplored path prefixes)
            frontier_diversity_low = self._is_frontier_diversity_low(unexplored_frontier_urls)

            if archetypes_sufficient and frontier_diversity_low:
                self.stopped_early = True
                self.stop_reason = "low_information_gain_frontier_exhausted"

        return fp, False, False

    def _is_frontier_diversity_low(self, frontier: list[str] | None) -> bool:
        """Returns True if remaining unexplored URLs belong to already-seen path prefixes."""
        if not frontier:
            return True

        sampled_paths = {
            urlparse(url).path.strip("/").split("/")[0]
            for samples in self.templates.values()
            for url, _ in samples
        }

        unexplored_paths = {
            urlparse(url).path.strip("/").split("/")[0]
            for url in frontier
        }

        # If frontier has URLs with novel top-level path segments, diversity is still high!
        new_paths = unexplored_paths - sampled_paths
        return len(new_paths) == 0

    def should_terminate_crawl(self) -> bool:
        return self.stopped_early

    def get_summary(self) -> dict[str, Any]:
        reduction_rate = 0.0
        if self.total_evaluated > 0:
            reduction_rate = (self.total_evaluated - self.total_sampled) / self.total_evaluated

        return {
            "total_evaluated": self.total_evaluated,
            "total_sampled": self.total_sampled,
            "unique_templates_count": len(self.templates),
            "stopped_early": self.stopped_early,
            "stop_reason": self.stop_reason,
            "request_reduction_rate": round(reduction_rate, 4),
            "archetypes": {
                t: {
                    "count": len(samples),
                    "landmarks": list(samples[0][1].landmarks),
                    "interactive_total": sum(samples[0][1].interactive_counts.values()),
                }
                for t, samples in self.templates.items()
            },
        }
