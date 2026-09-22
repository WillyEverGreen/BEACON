"""
Cognitive & UX accessibility checks.
Readability scoring, jargon detection, CTA clarity, navigation complexity,
form usability, and error message quality analysis.
"""
import hashlib
import logging
import re

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── Try to import textstat for readability scoring ─────────────
_TEXTSTAT_AVAILABLE = False
try:
    import textstat
    _TEXTSTAT_AVAILABLE = True
except ImportError:
    logger.info("textstat not installed. Using built-in readability estimates. Install with: pip install textstat")


# ── Built-in readability (fallback if textstat not available) ──

def _count_syllables(word: str) -> int:
    """Estimate syllable count for a word."""
    word = word.lower().strip()
    if len(word) <= 3:
        return 1
    count = 0
    vowels = "aeiouy"
    if word[0] in vowels:
        count += 1
    for i in range(1, len(word)):
        if word[i] in vowels and word[i - 1] not in vowels:
            count += 1
    if word.endswith("e"):
        count -= 1
    if word.endswith("le") and len(word) > 2 and word[-3] not in vowels:
        count += 1
    return max(1, count)


def _flesch_kincaid_grade(text: str) -> float:
    """Calculate Flesch-Kincaid Grade Level."""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    words = re.findall(r'\b\w+\b', text)

    if not sentences or not words:
        return 0.0

    avg_sentence_len = len(words) / len(sentences)
    avg_syllables = sum(_count_syllables(w) for w in words) / len(words)

    return 0.39 * avg_sentence_len + 11.8 * avg_syllables - 15.59


def _flesch_reading_ease(text: str) -> float:
    """Calculate Flesch Reading Ease (0-100, higher = easier)."""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    words = re.findall(r'\b\w+\b', text)

    if not sentences or not words:
        return 100.0

    avg_sentence_len = len(words) / len(sentences)
    avg_syllables = sum(_count_syllables(w) for w in words) / len(words)

    return 206.835 - 1.015 * avg_sentence_len - 84.6 * avg_syllables


def _gunning_fog(text: str) -> float:
    """Calculate Gunning Fog Index."""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    words = re.findall(r'\b\w+\b', text)

    if not sentences or not words:
        return 0.0

    complex_words = sum(1 for w in words if _count_syllables(w) >= 3)
    avg_sentence_len = len(words) / len(sentences)
    percent_complex = (complex_words / len(words)) * 100

    return 0.4 * (avg_sentence_len + percent_complex)


# ── Jargon detection ───────────────────────────────────────────

COMMON_JARGON = {
    "api", "sdk", "cli", "gui", "ui", "ux", "saas", "paas", "iaas",
    "crud", "rest", "graphql", "webhook", "middleware", "backend",
    "frontend", "fullstack", "devops", "cicd", "microservices",
    "containerize", "orchestrate", "provisioning", "scalability",
    "throughput", "latency", "idempotent", "polymorphism",
    "encapsulation", "abstraction", "refactor", "deprecated",
    "boilerplate", "scaffold", "payload", "endpoint", "schema",
    "serialization", "deserialization", "authentication", "authorization",
    "tokenization", "hashing", "encryption", "decryption",
    "asynchronous", "synchronous", "concurrent", "parallelism",
    "bandwidth", "protocol", "repository", "deployment",
    "leverage", "synergy", "paradigm", "optimization",
    "utilize", "implementation", "functionality", "methodology",
}


def _make_issue(url, rule_id, severity, description, wcag_criterion, wcag_level,
                suggested_fix, evidence=None, fix_effort="medium", coga_pattern_ref=""):
    issue_id = hashlib.sha256(f"{url}|cognitive|{rule_id}".encode()).hexdigest()[:16]
    return {
        "issue_id": issue_id,
        "rule_id": rule_id,
        "issue_type": "needs-review",
        "element": "<body>",
        "html_snippet": "",
        "page_url": url,
        "severity": severity,
        "wcag_criterion": wcag_criterion,
        "wcag_level": wcag_level,
        "category": "cognitive",
        "confidence": 0.6,
        "confidence_sources": ["cognitive"],
        "needs_manual_review": True,
        "description": description,
        "suggested_fix": suggested_fix,
        "code_fix": "",
        "fix_effort": fix_effort,
        "coga_pattern_ref": coga_pattern_ref,
        "group_id": "",
        "domain": "cognitive",
        "evidence": evidence or {},
        "reproducibility": "",
    }


class CognitiveAnalyzer:
    """Cognitive and UX accessibility analysis."""

    def __init__(self, html: str, url: str):
        self.soup = BeautifulSoup(html, "lxml")
        self.url = url
        self.body_text = ""
        body = self.soup.find("body")
        if body:
            self.body_text = body.get_text(separator=" ", strip=True)

    def run_all(self) -> dict:
        """
        Run all cognitive checks.
        Returns dict with 'scores' (CognitiveScore data) and 'issues' list.
        """
        issues = []
        scores = {
            "readability_grade": 0.0,
            "readability_ease": 100.0,
            "gunning_fog": 0.0,
            "jargon_density": 0.0,
            "nav_complexity": "low",
            "form_usability": "good",
            "overall_cognitive_score": 100.0,
        }

        if not self.body_text or len(self.body_text) < 50:
            scores["issues"] = issues
            return scores

        # Readability
        r_issues, r_scores = self._analyze_readability()
        issues.extend(r_issues)
        scores.update(r_scores)

        # Jargon
        j_issues, j_score = self._analyze_jargon()
        issues.extend(j_issues)
        scores["jargon_density"] = j_score

        # CTA clarity
        issues.extend(self._analyze_cta_clarity())

        # Navigation complexity
        nav_issues, nav_level = self._analyze_nav_complexity()
        issues.extend(nav_issues)
        scores["nav_complexity"] = nav_level

        # Form usability
        form_issues, form_level = self._analyze_form_usability()
        issues.extend(form_issues)
        scores["form_usability"] = form_level

        # Error message quality
        issues.extend(self._analyze_error_messages())

        # Heading hierarchy (Cognitive Focus)
        issues.extend(self._analyze_heading_sequence())

        # Visual clutter & complexity
        issues.extend(self._analyze_visual_clutter())

        # ── Phase 2 COGA rules (Objective 4: Help users focus) ─────────────
        issues.extend(self._analyze_auto_carousel())
        issues.extend(self._analyze_focus_disruption())
        issues.extend(self._analyze_autoplay_media())

        # Calculate overall cognitive score
        penalties = 0
        if scores["readability_grade"] > 8:
            penalties += min(20, (scores["readability_grade"] - 8) * 5)
        if scores["jargon_density"] > 5:
            penalties += min(15, scores["jargon_density"] * 2)
        if nav_level == "high":
            penalties += 15
        elif nav_level == "medium":
            penalties += 5
        if form_level == "poor":
            penalties += 15
        elif form_level == "fair":
            penalties += 5
        penalties += len([i for i in issues if i["severity"] in ("critical", "serious")]) * 5
        penalties += len([i for i in issues if i["severity"] in ("moderate",)]) * 2

        scores["overall_cognitive_score"] = max(0, 100 - penalties)
        scores["issues"] = issues

        return scores

    def _analyze_readability(self) -> tuple[list[dict], dict]:
        """Analyze text readability using Flesch-Kincaid and Gunning Fog."""
        issues = []
        scores = {}

        if _TEXTSTAT_AVAILABLE:
            grade = textstat.flesch_kincaid_grade(self.body_text)
            ease = textstat.flesch_reading_ease(self.body_text)
            fog = textstat.gunning_fog(self.body_text)
        else:
            grade = _flesch_kincaid_grade(self.body_text)
            ease = _flesch_reading_ease(self.body_text)
            fog = _gunning_fog(self.body_text)

        scores["readability_grade"] = round(grade, 1)
        scores["readability_ease"] = round(max(0, min(100, ease)), 1)
        scores["gunning_fog"] = round(fog, 1)

        if grade > 12:
            issues.append(_make_issue(
                self.url, "readability", "serious",
                f"Content readability is at grade level {grade:.1f} (college level). "
                f"COGA recommends grade 8 or below for broad accessibility.",
                "3.1.5", "AAA",
                "Simplify language: use shorter sentences, common words, active voice.",
                evidence={"flesch_kincaid_grade": grade, "reading_ease": ease, "gunning_fog": fog},
                coga_pattern_ref="Clear Language"
            ))
        elif grade > 8:
            issues.append(_make_issue(
                self.url, "readability", "moderate",
                f"Content readability grade level {grade:.1f} is above recommended level 8. "
                f"Consider simplifying for broader cognitive accessibility.",
                "3.1.5", "AAA",
                "Use plain language, break long sentences, explain technical terms.",
                evidence={"flesch_kincaid_grade": grade, "reading_ease": ease, "gunning_fog": fog},
                coga_pattern_ref="Clear Language"
            ))

        return issues, scores

    def _analyze_jargon(self) -> tuple[list[dict], float]:
        """Detect technical jargon density."""
        issues = []
        words = re.findall(r'\b\w+\b', self.body_text.lower())
        if not words:
            return issues, 0.0

        jargon_found = [w for w in words if w in COMMON_JARGON]
        density = (len(jargon_found) / len(words)) * 100

        if density > 10:
            issues.append(_make_issue(
                self.url, "jargon", "moderate",
                f"High technical jargon density ({density:.1f}%). "
                f"Users with cognitive disabilities may struggle with technical terminology.",
                "3.1.3", "AAA",
                "Define technical terms on first use, or provide a glossary.",
                evidence={"jargon_density_percent": round(density, 1),
                          "sample_jargon": list(set(jargon_found))[:10]},
                coga_pattern_ref="Explain Complex Terms"
            ))
        elif density > 5:
            issues.append(_make_issue(
                self.url, "jargon", "minor",
                f"Moderate jargon density ({density:.1f}%). Consider providing definitions.",
                "3.1.3", "AAA",
                "Add tooltips or a glossary for technical terms.",
                evidence={"jargon_density_percent": round(density, 1)},
                coga_pattern_ref="Explain Complex Terms"
            ))

        return issues, round(density, 1)

    def _analyze_cta_clarity(self) -> list[dict]:
        """Evaluate call-to-action button clarity."""
        issues = []
        vague_ctas = {"submit", "go", "ok", "click", "continue", "next", "send", "done"}

        for btn in self.soup.find_all(["button", "input"]):
            if btn.name == "input" and btn.get("type") not in ("submit", "button"):
                continue
            text = btn.get_text(strip=True).lower() or btn.get("value", "").lower()
            if text in vague_ctas:
                issues.append(_make_issue(
                    self.url, "cta-clarity", "moderate",
                    f'CTA button text "{text}" is vague. Users may not understand the action.',
                    "2.4.6", "AA",
                    f'Use specific text like "Submit application", "Save changes" instead of "{text}".',
                    fix_effort="low",
                    coga_pattern_ref="Clear Purpose"
                ))

        return issues

    def _analyze_nav_complexity(self) -> tuple[list[dict], str]:
        """Assess navigation complexity."""
        issues = []
        navs = self.soup.find_all("nav")
        total_links = 0
        max_depth = 0

        for nav in navs:
            links = nav.find_all("a")
            total_links += len(links)
            # Check nesting depth
            nested = nav.find_all("ul")
            for ul in nested:
                depth = 0
                parent = ul.parent
                while parent and parent != nav:
                    if parent.name == "ul":
                        depth += 1
                    parent = parent.parent
                max_depth = max(max_depth, depth)

        level = "low"
        if total_links > 30 or max_depth > 3:
            level = "high"
            issues.append(_make_issue(
                self.url, "nav-complexity", "moderate",
                f"Navigation is complex: {total_links} links, {max_depth} nesting levels. "
                f"Users with cognitive disabilities may be overwhelmed.",
                "2.4.5", "AA",
                "Simplify navigation: limit top-level items to 7±2, reduce nesting depth.",
                evidence={"total_nav_links": total_links, "max_nesting_depth": max_depth},
                coga_pattern_ref="Clear Navigation"
            ))
        elif total_links > 15 or max_depth > 2:
            level = "medium"

        return issues, level

    def _analyze_form_usability(self) -> tuple[list[dict], str]:
        """Analyze form complexity and usability."""
        issues = []
        forms = self.soup.find_all("form")
        level = "good"

        for form in forms:
            fields = form.find_all(["input", "textarea", "select"])
            visible_fields = [f for f in fields if f.get("type") != "hidden"]
            field_count = len(visible_fields)

            if field_count > 10:
                level = "poor"
                issues.append(_make_issue(
                    self.url, "form-usability", "moderate",
                    f"Form has {field_count} visible fields. Long forms cause cognitive overload.",
                    "3.3.2", "A",
                    "Break form into logical steps with a progress indicator, or reduce fields.",
                    evidence={"field_count": field_count},
                    fix_effort="high",
                    coga_pattern_ref="Help Users Complete Forms"
                ))
            elif field_count > 5:
                if level != "poor":
                    level = "fair"

            # Check for progress indicators in multi-step forms
            has_progress = bool(
                form.find(class_=re.compile(r'progress|step|wizard', re.IGNORECASE)) or
                form.find(attrs={"role": "progressbar"})
            )
            if field_count > 5 and not has_progress:
                issues.append(_make_issue(
                    self.url, "form-no-progress", "needs-review", "minor",
                    f"Form has {field_count} fields but no progress indicator.",
                    "3.3.2", "A",
                    "Add a progress indicator or step counter for longer forms.",
                    fix_effort="medium",
                    coga_pattern_ref="Provide Clear Steps"
                ))

        return issues, level

    def _analyze_error_messages(self) -> list[dict]:
        """Check error message quality."""
        issues = []
        error_elements = self.soup.find_all(
            class_=re.compile(r'error|invalid|alert', re.IGNORECASE)
        )

        generic_patterns = [
            re.compile(r'^error\.?$', re.IGNORECASE),
            re.compile(r'^invalid\.?$', re.IGNORECASE),
            re.compile(r'^required\.?$', re.IGNORECASE),
            re.compile(r'^this field is required\.?$', re.IGNORECASE),
        ]

        for elem in error_elements:
            text = elem.get_text(strip=True)
            if not text:
                continue
            for pattern in generic_patterns:
                if pattern.match(text):
                    issues.append(_make_issue(
                        self.url, "error-message-quality", "moderate",
                        f'Error message "{text}" is too generic. Users need specific guidance.',
                        "3.3.1", "A",
                        'Provide specific messages: "Email must include @" instead of just "Error".',
                        fix_effort="low",
                        coga_pattern_ref="Help Users Avoid Mistakes"
                    ))
                    break

        return issues

    def _analyze_auto_carousel(self) -> list[dict]:
        """COGA Objective 4 — Help users focus: Detect auto-advancing carousels.

        Auto-play content (carousels, sliders without pause controls) forces
        users to track moving content against their will, harming cognitive
        accessibility.  Reference: COGA-Usable Pattern 4.2.3.
        """
        issues = []
        carousel_signals = self.soup.find_all(
            class_=re.compile(r"carousel|slider|slideshow|swiper|glide|splide", re.IGNORECASE)
        )
        for elem in carousel_signals:
            # Heuristic: auto-advancing if data-autoplay or interval attributes
            # are present without a visible pause button nearby.
            has_autoplay = (
                elem.get("data-autoplay")
                or elem.get("data-auto-play")
                or elem.get("data-interval")
                or elem.get("data-delay")
                or elem.get("autoplay") is not None
            )
            has_pause = bool(
                elem.find(class_=re.compile(r"pause|stop", re.IGNORECASE))
                or elem.find(attrs={"aria-label": re.compile(r"pause|stop", re.IGNORECASE)})
            )
            if has_autoplay and not has_pause:
                issues.append(_make_issue(
                    self.url, "auto-carousel", "moderate",
                    "Auto-advancing carousel detected without a visible pause control. "
                    "Users with cognitive disabilities cannot stop moving content.",
                    "2.2.2", "A",
                    "Add a pause/stop button to the carousel. "
                    "Alternatively, disable auto-play by default and let users opt in.",
                    evidence={"element": str(elem)[:300]},
                    fix_effort="medium",
                    coga_pattern_ref="Stop or Limit Time (COGA Obj 4, Pattern 4.2.3)"
                ))
        return issues

    def _analyze_focus_disruption(self) -> list[dict]:
        """COGA Objective 4 — Help users focus: Detect popup/overlay triggers on focus.

        Dialogs or overlays that open on focus events disorient users with
        cognitive disabilities.  Reference: COGA-Usable Pattern 4.1.2.
        """
        issues = []
        # Detect elements wired to trigger dialogs/popups
        focus_triggers = self.soup.find_all(
            attrs={"onfocus": re.compile(r"modal|popup|dialog|overlay|show\(", re.IGNORECASE)}
        )
        focus_triggers += self.soup.find_all(
            attrs={"data-toggle": re.compile(r"modal|popup|dropdown", re.IGNORECASE),
                   "tabindex": True}
        )
        if focus_triggers:
            issues.append(_make_issue(
                self.url, "focus-disruption", "moderate",
                f"Detected {len(focus_triggers)} element(s) that may trigger dialogs or overlays "
                "on focus events. This disrupts the reading flow for users with cognitive disabilities.",
                "3.2.1", "A",
                "Avoid triggering popups or modals on focus. "
                "Use explicit user actions (click/enter) to open dialogs instead.",
                evidence={"trigger_count": len(focus_triggers)},
                fix_effort="medium",
                coga_pattern_ref="Avoid Interruptions (COGA Obj 4, Pattern 4.1.2)"
            ))
        return issues

    def _analyze_autoplay_media(self) -> list[dict]:
        """COGA Objective 4 — Help users focus: Detect autoplay audio/video without controls.

        Autoplay media competes for attention and is a significant barrier for
        users with cognitive disabilities.  Reference: COGA-Usable Pattern 4.2.1.
        """
        issues = []
        # <video autoplay> or <audio autoplay> without controls or muted
        for tag_name in ("video", "audio"):
            for elem in self.soup.find_all(tag_name):
                if elem.get("autoplay") is None:
                    continue
                has_controls = elem.get("controls") is not None
                is_muted = elem.get("muted") is not None
                # Muted video autoplay (e.g. hero background) is generally OK.
                # Non-muted audio/video autoplay is a barrier.
                if not has_controls and not is_muted:
                    issues.append(_make_issue(
                        self.url, "autoplay-media", "serious",
                        f"<{tag_name}> element autoplays without controls or muted attribute. "
                        "Unexpected audio/video disturbs users with cognitive disabilities.",
                        "1.4.2", "A",
                        f"Add the 'controls' attribute to the <{tag_name}> element "
                        "so users can pause or stop media, or add 'muted' for background video.",
                        evidence={"element": str(elem)[:300]},
                        fix_effort="low",
                        coga_pattern_ref="Control Media (COGA Obj 4, Pattern 4.2.1)"
                    ))
        return issues

    def _analyze_visual_clutter(self) -> list[dict]:
        """COGA Objective 3 — Help users focus: Detect visual clutter.
        
        Excessive elements or dense layouts can overwhelm users with 
        cognitive disabilities. Reference: COGA-Usable Pattern 4.4.1.
        """
        issues = []
        # Check for link density in non-nav areas
        content_links = 0
        for p in self.soup.find_all(["p", "div", "section"]):
            if p.find_parent("nav") or p.find_parent("footer"):
                continue
            content_links += len(p.find_all("a"))
            
        if content_links > 50:
            issues.append(_make_issue(
                self.url, "visual-clutter", "moderate",
                f"Detected high link density ({content_links} links) in content areas. "
                "Too many links can be distracting and cause 'choice paralysis'.",
                "2.4.5", "AA",
                "Reduce the number of links in main content or group them logically into sub-sections.",
                evidence={"content_link_count": content_links},
                coga_pattern_ref="Provide a Clear Hierarchy (COGA Obj 3, Pattern 4.4.1)"
            ))
            
        return issues

    def _analyze_heading_sequence(self) -> list[dict]:
        """COGA Objective 3 — Help users focus: Check for logical heading sequences.
        
        Predictable structure helps users with cognitive disabilities build 
        a mental map of the content. Reference: COGA-Usable Pattern 4.3.3.
        """
        issues = []
        import re
        headings = self.soup.find_all(re.compile(r'^h[1-6]$'))
        last_level = 0
        
        for h in headings:
            level = int(h.name[1])
            if level > last_level + 1 and last_level > 0:
                issues.append(_make_issue(
                    self.url, "heading-gap", "moderate",
                    f"Skipped heading level: {h.name} followed {last_level}. "
                    "Gaps in hierarchy disrupt the mental model for users with cognitive disabilities.",
                    "1.3.1", "A",
                    f"Change {h.name} to H{last_level + 1} to maintain a logical sequence.",
                    evidence={"gap": f"H{last_level} -> {h.name}"},
                    coga_pattern_ref="Provide a Clear Structure (COGA Obj 3, Pattern 4.3.3)"
                ))
            last_level = level
            
        return issues
