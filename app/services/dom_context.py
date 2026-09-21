"""
DOM Context Extraction Service for Accessibility Verification.

Extracts programmatically determined context surrounding detected accessibility concerns:
- Link Context (WCAG 2.4.4): enclosing sentence, parent paragraph, preceding heading, nearest landmark.
- Form Context (WCAG 1.3.1, 4.1.2): associated labels, adjacent text, fieldset legends, ARIA attributes.
- Structural / Landmark Context (WCAG 1.3.1, 2.4.1): landmark hierarchy, headings tree, repeated blocks.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup, NavigableString, Tag

logger = logging.getLogger(__name__)

LANDMARK_ROLES = {
    "main",
    "navigation",
    "banner",
    "contentinfo",
    "complementary",
    "search",
    "region",
    "form",
}

LANDMARK_TAGS = {
    "main",
    "nav",
    "header",
    "footer",
    "aside",
    "section",
    "article",
}


GENERIC_LINK_TEXTS = {
    "learn more",
    "read more",
    "click here",
    "click this",
    "more",
    "details",
    "link",
    "go",
    "here",
    "view",
    "continue",
    "see more",
    "find out more",
    "info",
    "more info",
    "get started",
}


class DOMContextExtractor:
    """Extracts contextual information from DOM for accurate WCAG verification."""

    def __init__(self, html: str) -> None:
        self.raw_html = html or ""
        self.soup = BeautifulSoup(self.raw_html, "lxml")
        clean_html = self.raw_html.lower().strip()
        self.dom_is_complete = bool(
            ("<html" in clean_html or "<body" in clean_html or "<main" in clean_html)
            and len(self.raw_html) > 60
        )

    def _find_target_tag(self, selector: str, html_snippet: str) -> Optional[Tag]:
        """Locate the target Tag in the parsed soup using selector or snippet."""
        target: Optional[Tag] = None

        if selector and selector != "body" and selector != "<html>":
            try:
                target = self.soup.select_one(selector)
            except Exception:
                target = None

        if target is None and html_snippet:
            clean_snippet = html_snippet.strip()
            # Extract opening tag signature
            match = re.match(r"<([a-zA-Z0-9_-]+)([^>]*)>", clean_snippet)
            if match:
                tag_name = match.group(1).lower()
                attrs_raw = match.group(2)
                id_match = re.search(r'id=["\']([^"\']+)["\']', attrs_raw)
                if id_match:
                    target = self.soup.find(id=id_match.group(1))
                if target is None:
                    candidates = self.soup.find_all(tag_name)
                    for cand in candidates:
                        cand_str = str(cand)
                        if clean_snippet[:80] in cand_str or cand_str[:80] in clean_snippet:
                            target = cand
                            break

        return target

    def _resolve_ids_to_text(self, id_refs: str) -> str:
        """Resolve space-separated ID references (e.g. aria-labelledby) to their DOM text."""
        if not id_refs:
            return ""
        resolved_parts: List[str] = []
        for ref_id in id_refs.split():
            clean_id = ref_id.strip()
            if not clean_id:
                continue
            ref_tag = self.soup.find(id=clean_id)
            if ref_tag:
                t = ref_tag.get_text(" ", strip=True)
                if t:
                    resolved_parts.append(t)
        return " ".join(resolved_parts)

    def _is_semantically_informative_sentence(self, sentence: str, link_text: str) -> bool:
        """Evaluate whether sentence context semantically identifies link purpose without arbitrary char counts."""
        clean_s = sentence.strip()
        if not clean_s:
            return False
        # Remove the link text itself from the sentence
        remaining = re.sub(re.escape(link_text), "", clean_s, flags=re.IGNORECASE).strip()
        # Find informative words excluding generic stop/navigation phrases
        words = re.findall(r"\b[a-zA-Z0-9_-]+\b", remaining.lower())
        stop_words = {
            "the", "a", "an", "to", "for", "and", "or", "in", "on", "at", "by", "of", "is", "it",
            "please", "click", "here", "this", "link", "page", "our", "your", "more", "learn", "read"
        }
        informative_words = [w for w in words if w not in GENERIC_LINK_TEXTS and w not in stop_words]
        # At least one concrete informative noun/verb indicating destination/action
        return len(informative_words) >= 1

    def _get_nearest_landmark(self, tag: Tag) -> Optional[str]:
        """Find the enclosing landmark role or semantic tag."""
        curr = tag.parent
        while curr and curr.name not in ("[document]", "html"):
            role = curr.get("role", "")
            if role in LANDMARK_ROLES:
                return f"{curr.name}[role='{role}']"
            if curr.name in LANDMARK_TAGS:
                return curr.name
            curr = curr.parent
        return None

    def _get_preceding_heading(self, tag: Tag) -> Optional[Dict[str, Any]]:
        """Find the proximate preceding heading element (h1-h6) per WCAG Technique H80.
        
        Technique H80 requires the heading to provide context for links in the same
        section, list, paragraph, or content block. A distant heading across isolated
        landmark boundaries (e.g. <footer> vs <main>) is not proximate context.
        """
        # 1. Look within the nearest structural block container
        container = tag.find_parent(["section", "article", "aside", "li", "dd", "td", "figure", "div"])
        if container and container.name not in ("[document]", "html", "body"):
            headings = container.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
            for h in reversed(headings):
                if tag in h.find_all_next():
                    text = h.get_text(" ", strip=True)
                    if text:
                        return {"level": h.name, "text": text[:120], "proximate": True}

        # 2. Look for the closest preceding heading in document order
        prev_h = tag.find_previous(["h1", "h2", "h3", "h4", "h5", "h6"])
        if prev_h:
            # Check landmark isolation (e.g. footer link vs main/header heading)
            tag_landmark = tag.find_parent(["footer", "nav", "aside", "header"])
            h_landmark = prev_h.find_parent(["footer", "nav", "aside", "header"])
            if tag_landmark != h_landmark and tag_landmark is not None:
                # Disparate semantic region -> cannot serve as proximate context
                return None

            text = prev_h.get_text(" ", strip=True)
            if text:
                return {"level": prev_h.name, "text": text[:120], "proximate": True}

        return None

    def _get_nearest_heading(self, tag: Tag) -> Optional[Dict[str, str]]:
        """Find the physically closest heading preceding or following the tag."""
        prev_h = tag.find_previous(["h1", "h2", "h3", "h4", "h5", "h6"])
        next_h = tag.find_next(["h1", "h2", "h3", "h4", "h5", "h6"])
        chosen = prev_h or next_h
        if chosen:
            text = chosen.get_text(" ", strip=True)
            if text:
                return {"level": chosen.name, "text": text[:120]}
        return None

    def _get_enclosing_sentence(self, tag: Tag) -> str:
        """Extract the full enclosing sentence or paragraph text per WCAG Technique G53."""
        parent = tag.find_parent(["p", "li", "td", "th"])
        if parent:
            full_text = parent.get_text(" ", strip=True)
            link_text = tag.get_text(" ", strip=True)
            if link_text and link_text in full_text:
                sentences = re.split(r"(?<=[.!?])\s+", full_text)
                for s in sentences:
                    if link_text in s:
                        return s.strip()
            return full_text[:250]

        immediate_parent = tag.parent
        if immediate_parent and immediate_parent.name in ("div", "span"):
            child_blocks = immediate_parent.find_all(["p", "div", "section", "article", "header", "footer", "nav", "ul", "ol", "table"])
            if not child_blocks:
                full_text = immediate_parent.get_text(" ", strip=True)
                return full_text[:200]
        return ""

    def extract_link_context(self, selector: str, html_snippet: str) -> Dict[str, Any]:
        """Extract surrounding programmatic context for WCAG 2.4.4."""
        tag = self._find_target_tag(selector, html_snippet)
        if not tag:
            return {
                "element": "",
                "link_text": "",
                "href": "",
                "aria_label": "",
                "aria_labelledby": "",
                "resolved_labelledby_text": "",
                "resolved_describedby_text": "",
                "parent_element": "",
                "parent_text": "",
                "enclosing_sentence": "",
                "preceding_heading": None,
                "nearest_heading": None,
                "nearest_landmark": None,
                "landmark_role": "",
                "siblings": [],
                "ancestor_chain": [],
                "relevant_ids": [],
                "has_context": False,
                "dom_is_complete": self.dom_is_complete,
                "title": "",
            }

        link_text = tag.get_text(" ", strip=True)
        href = str(tag.get("href", "") or "").strip()
        aria_label = str(tag.get("aria-label", "") or "").strip()
        aria_labelledby = str(tag.get("aria-labelledby", "") or "").strip()
        aria_describedby = str(tag.get("aria-describedby", "") or "").strip()
        title = str(tag.get("title", "") or "").strip()
        tag_id = str(tag.get("id", "") or "").strip()

        resolved_labelledby_text = self._resolve_ids_to_text(aria_labelledby)
        resolved_describedby_text = self._resolve_ids_to_text(aria_describedby)

        parent_p = tag.find_parent(["p", "li", "td", "div"])
        parent_text = parent_p.get_text(" ", strip=True)[:250] if parent_p else ""
        parent_element = tag.parent.name if tag.parent else ""

        sentence = self._get_enclosing_sentence(tag)
        preceding_h = self._get_preceding_heading(tag)
        nearest_h = self._get_nearest_heading(tag)
        landmark = self._get_nearest_landmark(tag)
        landmark_role = ""
        if landmark:
            landmark_role = landmark.split("[role='")[-1].replace("']", "") if "role=" in landmark else landmark

        # Siblings
        siblings: List[str] = []
        prev_sib = tag.find_previous_sibling()
        next_sib = tag.find_next_sibling()
        if prev_sib:
            siblings.append(f"prev:<{prev_sib.name}>:{prev_sib.get_text(' ', strip=True)[:60]}")
        if next_sib:
            siblings.append(f"next:<{next_sib.name}>:{next_sib.get_text(' ', strip=True)[:60]}")

        # Ancestor chain
        ancestor_chain: List[str] = []
        curr = tag.parent
        while curr and curr.name not in ("[document]"):
            ancestor_chain.append(curr.name)
            curr = curr.parent

        # Relevant IDs
        relevant_ids: List[str] = []
        if tag_id:
            relevant_ids.append(tag_id)
        if aria_labelledby:
            relevant_ids.extend(aria_labelledby.split())
        if aria_describedby:
            relevant_ids.extend(aria_describedby.split())

        # Determine if context genuinely clarifies purpose per WCAG 2.4.4
        is_generic_text = link_text.lower() in GENERIC_LINK_TEXTS
        has_sufficient_context = False

        if not is_generic_text and len(link_text) > 2:
            # Descriptive text in link itself
            has_sufficient_context = True
        elif aria_label and (len(aria_label) > len(link_text) + 3 or aria_label.lower() not in GENERIC_LINK_TEXTS):
            has_sufficient_context = True
        elif resolved_labelledby_text and len(resolved_labelledby_text) > 3:
            has_sufficient_context = True
        elif self._is_semantically_informative_sentence(sentence, link_text):
            has_sufficient_context = True
        elif preceding_h and len(preceding_h.get("text", "")) > 3:
            has_sufficient_context = True
        elif self._is_semantically_informative_sentence(parent_text, link_text):
            has_sufficient_context = True

        return {
            "element": str(tag)[:200],
            "link_text": link_text,
            "href": href,
            "aria_label": aria_label,
            "aria_labelledby": aria_labelledby,
            "aria_describedby": aria_describedby,
            "resolved_labelledby_text": resolved_labelledby_text,
            "resolved_describedby_text": resolved_describedby_text,
            "title": title,
            "parent_element": parent_element,
            "parent_text": parent_text,
            "enclosing_sentence": sentence,
            "preceding_heading": preceding_h,
            "nearest_heading": nearest_h,
            "nearest_landmark": landmark,
            "landmark_role": landmark_role,
            "siblings": siblings,
            "ancestor_chain": ancestor_chain,
            "relevant_ids": relevant_ids,
            "has_context": has_sufficient_context,
            "dom_is_complete": self.dom_is_complete,
        }

    def extract_form_context(self, selector: str, html_snippet: str) -> Dict[str, Any]:
        """Extract surrounding programmatic label and association context for form controls.
        
        BEACON implementation of relevant accessible-name semantics (derived from W3C AccName principles).
        """
        tag = self._find_target_tag(selector, html_snippet)
        if not tag:
            return {
                "id": "",
                "name": "",
                "type": "",
                "associated_label": "",
                "label_for": "",
                "wrapping_label": "",
                "aria_label": "",
                "aria_labelledby": "",
                "resolved_labelledby_text": "",
                "resolved_accessible_name": "",
                "accessible_name_source": "none",
                "placeholder": "",
                "fieldset": "",
                "legend": "",
                "nearby_text": "",
                "has_label": False,
                "label_text": "",
                "enclosing_label": False,
                "dom_is_complete": self.dom_is_complete,
            }

        input_id = tag.get("id", "")
        name = tag.get("name", "")
        input_type = tag.get("type", "text")
        aria_label = str(tag.get("aria-label", "") or "").strip()
        aria_labelledby = str(tag.get("aria-labelledby", "") or "").strip()
        placeholder = str(tag.get("placeholder", "") or "").strip()
        title = str(tag.get("title", "") or "").strip()

        resolved_labelledby_text = self._resolve_ids_to_text(aria_labelledby)

        # Check for <label for="id">
        associated_label = ""
        label_for = ""
        if input_id:
            label_tag = self.soup.find("label", attrs={"for": input_id})
            if label_tag:
                associated_label = label_tag.get_text(" ", strip=True)
                label_for = input_id

        # Check for wrapping <label>
        wrapping_label = ""
        enclosing_label = False
        wrapping_label_tag = tag.find_parent("label")
        if wrapping_label_tag:
            enclosing_label = True
            raw_text = wrapping_label_tag.get_text(" ", strip=True)
            input_val = str(tag.get("value", "") or "").strip()
            if input_val and input_val in raw_text:
                raw_text = raw_text.replace(input_val, "").strip()
            wrapping_label = raw_text

        # Check for <fieldset><legend>
        fieldset_tag = tag.find_parent("fieldset")
        fieldset_name = fieldset_tag.name if fieldset_tag else ""
        legend_text = ""
        if fieldset_tag:
            legend = fieldset_tag.find("legend")
            if legend:
                legend_text = legend.get_text(" ", strip=True)

        # Nearby text (adjacent sibling text nodes)
        nearby_parts: List[str] = []
        prev_sib = tag.find_previous_sibling()
        if prev_sib and prev_sib.name in ("span", "p", "label", "div"):
            t = prev_sib.get_text(" ", strip=True)
            if t:
                nearby_parts.append(t)
        nearby_text = " ".join(nearby_parts)

        # BEACON accessible-name semantics resolution (AccName priority):
        # 1. aria-labelledby
        # 2. aria-label
        # 3. <label for>
        # 4. wrapping <label>
        # 5. title
        # (placeholder is NOT a valid programmatic label per WCAG 1.3.1 / 4.1.2)
        resolved_name = ""
        accessible_name_source = "none"

        if resolved_labelledby_text:
            resolved_name = resolved_labelledby_text
            accessible_name_source = "aria-labelledby"
        elif aria_label:
            resolved_name = aria_label
            accessible_name_source = "aria-label"
        elif associated_label:
            resolved_name = associated_label
            accessible_name_source = "label_for"
        elif wrapping_label:
            resolved_name = wrapping_label
            accessible_name_source = "wrapping_label"
        elif title:
            resolved_name = title
            accessible_name_source = "title"

        has_programmatic_label = bool(resolved_name)

        return {
            "element": str(tag)[:200],
            "id": input_id,
            "input_id": input_id,
            "name": name,
            "tag_name": tag.name,
            "type": input_type,
            "input_type": input_type,
            "associated_label": associated_label,
            "label_for": label_for,
            "wrapping_label": wrapping_label,
            "aria_label": aria_label,
            "aria_labelledby": aria_labelledby,
            "resolved_labelledby_text": resolved_labelledby_text,
            "resolved_accessible_name": resolved_name,
            "accessible_name_source": accessible_name_source,
            "placeholder": placeholder,
            "title": title,
            "fieldset": fieldset_name,
            "legend": legend_text,
            "fieldset_legend": legend_text,
            "nearby_text": nearby_text,
            "has_label": has_programmatic_label,
            "label_text": resolved_name,
            "enclosing_label": enclosing_label,
            "dom_is_complete": self.dom_is_complete,
        }

    def extract_landmark_context(self) -> Dict[str, Any]:
        """Extract page-level landmark topology and bypass capabilities."""
        mains = self.soup.find_all("main") + self.soup.find_all(attrs={"role": "main"})
        navs = self.soup.find_all("nav") + self.soup.find_all(attrs={"role": "navigation"})
        headers = self.soup.find_all("header") + self.soup.find_all(attrs={"role": "banner"})
        footers = self.soup.find_all("footer") + self.soup.find_all(attrs={"role": "contentinfo"})
        asides = self.soup.find_all("aside") + self.soup.find_all(attrs={"role": "complementary"})
        h1s = self.soup.find_all("h1")

        all_headings = self.soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
        heading_hierarchy = [{"level": h.name, "text": h.get_text(" ", strip=True)[:80]} for h in all_headings]
        top_level_headings = [h.get_text(" ", strip=True) for h in h1s]

        # Structured document landmarks
        document_landmarks: List[Dict[str, Any]] = []
        landmark_groups = [
            (mains, "main"),
            (navs, "navigation"),
            (headers, "banner"),
            (footers, "contentinfo"),
            (asides, "complementary"),
        ]
        for tag_list, default_role in landmark_groups:
            for el in tag_list:
                role = el.get("role", default_role)
                el_id = el.get("id", "")
                acc_name = el.get("aria-label") or el.get("aria-labelledby", "")
                document_landmarks.append({
                    "tag": el.name,
                    "role": role,
                    "id": el_id,
                    "accessible_name": str(acc_name),
                })

        main_landmarks = [m.name if not m.get("role") else f"{m.name}[role='{m.get('role')}']" for m in mains]
        nav_landmarks = [n.name if not n.get("role") else f"{n.name}[role='{n.get('role')}']" for n in navs]
        header_landmarks = [h.name if not h.get("role") else f"{h.name}[role='{h.get('role')}']" for h in headers]
        footer_landmarks = [f.name if not f.get("role") else f"{f.name}[role='{f.get('role')}']" for f in footers]

        # Skip links
        first_links = self.soup.find_all("a", limit=8)
        skip_links: List[Dict[str, str]] = []
        for a in first_links:
            href = str(a.get("href", "")).strip()
            text = a.get_text(" ", strip=True).lower()
            if href.startswith("#") and any(k in text for k in ("skip", "main", "content", "navigation")):
                skip_links.append({"href": href, "text": text})

        # Repeated blocks detection
        repeated_blocks: List[Dict[str, Any]] = []
        for n in navs:
            links = n.find_all("a")
            if len(links) >= 4:
                repeated_blocks.append({"type": "nav", "links_count": len(links)})
        if headers:
            repeated_blocks.append({"type": "header", "count": len(headers)})

        primary_content_region = mains[0].name if mains else ("h1" if h1s else None)
        has_repeated_blocks = bool(repeated_blocks)

        # Bypass mechanism evaluation per W3C guidance:
        # 1. Skip link targeting primary content
        # 2. Main landmark (<main> or role='main')
        # 3. Structural heading hierarchy providing bypass:
        # Demarcates sections after navigation, rather than a lone top-level site title h1
        has_skip_link = bool(skip_links)
        has_main_landmark = bool(mains)
        has_heading_bypass = False
        if len(h1s) >= 1 and len(all_headings) >= 2:
            if navs:
                last_nav = navs[-1]
                heading_after_nav = last_nav.find_next(["h1", "h2", "h3"])
                if heading_after_nav:
                    has_heading_bypass = True
            else:
                has_heading_bypass = True

        has_bypass_mechanism = bool(has_skip_link or has_main_landmark or has_heading_bypass or not has_repeated_blocks)

        return {
            "document_landmarks": document_landmarks,
            "main_landmarks": main_landmarks,
            "nav_landmarks": nav_landmarks,
            "header_landmarks": header_landmarks,
            "footer_landmarks": footer_landmarks,
            "top_level_headings": top_level_headings,
            "heading_hierarchy": heading_hierarchy,
            "repeated_blocks": repeated_blocks,
            "skip_links": skip_links,
            "primary_content_region": primary_content_region,
            "main_count": len(mains),
            "nav_count": len(navs),
            "header_count": len(headers),
            "footer_count": len(footers),
            "h1_count": len(h1s),
            "h1_text": h1s[0].get_text(" ", strip=True)[:80] if h1s else "",
            "has_repeated_blocks": has_repeated_blocks,
            "has_bypass_mechanism": has_bypass_mechanism,
            "dom_is_complete": self.dom_is_complete,
        }

    def extract_context_for_issue(self, issue: dict) -> Dict[str, Any]:
        """Route to appropriate context extractor based on rule_id and category."""
        rule_id = str(issue.get("rule_id", "") or "").lower()
        category = str(issue.get("category", "") or "").lower()
        selector = str(issue.get("element", "") or issue.get("selector", "") or "")
        snippet = str(issue.get("html_snippet", "") or "")

        context: Dict[str, Any] = {
            "rule_id": rule_id,
            "selector": selector,
            "dom_is_complete": self.dom_is_complete,
        }

        if any(k in rule_id for k in ("landmark", "region", "bypass", "skip")) or "2.4.1" in str(issue.get("wcag_criterion", "")):
            context["landmark_context"] = self.extract_landmark_context()

        if (
            any(k in rule_id for k in ("generic-link", "link-name", "link-text", "empty-link"))
            or "2.4.4" in str(issue.get("wcag_criterion", ""))
            or ("link" in rule_id and not any(s in rule_id for s in ("skip", "bypass")) and str(issue.get("wcag_criterion", "")) != "2.4.1")
        ):
            context["link_context"] = self.extract_link_context(selector, snippet)
        elif any(k in rule_id for k in ("label", "input", "form", "button-name")):
            context["form_context"] = self.extract_form_context(selector, snippet)

        # Add DOM tag and parent summary
        tag = self._find_target_tag(selector, snippet)
        if tag:
            context["tag_name"] = tag.name
            context["parent_tag"] = tag.parent.name if tag.parent else ""
            context["nearest_landmark"] = self._get_nearest_landmark(tag)
            preceding_h = self._get_preceding_heading(tag)
            if preceding_h:
                context["preceding_heading"] = preceding_h

        return context
