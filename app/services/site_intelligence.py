"""
Site Intelligence & Capability Engine (§22–§24)
Provides:
- §22: Site topology engine (domain -> sitemap -> nav graph -> routes -> templates -> representative pages)
- §23: Template clustering & page classification with template_inferred finding propagation
- §24: Machine-readable capability profiles for FAST, DEEP, and MAX scan modes
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ── §24: Scan Mode Capability Profiles ────────────────────────────────────────

SCAN_MODE_CAPABILITIES: dict[str, dict[str, Any]] = {
    "fast": {
        "name": "FAST",
        "description": "Rapid deterministic scanning using static checks, basic DOM parsing, and lightweight checks.",
        "engines_enabled": ["beacon_static", "axe"],
        "browser_required": False,
        "visual_analysis_enabled": False,
        "interaction_probes_enabled": False,
        "assistive_tech_enabled": False,
        "ai_adjudication_enabled": False,
        "remediation_sandbox_enabled": False,
        "max_pages_default": 1,
        "target_latency_seconds": 3.0,
        "guaranteed_confidence_floor": 0.85,
    },
    "deep": {
        "name": "DEEP",
        "description": "Comprehensive multi-engine audit with Playwright rendering, IBM Equal Access, DOM context, AI adjudication, and rendered visual checks.",
        "engines_enabled": [
            "beacon_static",
            "beacon_heuristics",
            "beacon_browser",
            "beacon_coga",
            "axe",
            "ibm",
            "ai_adjudicator",
        ],
        "browser_required": True,
        "visual_analysis_enabled": True,
        "interaction_probes_enabled": True,
        "assistive_tech_enabled": False,
        "ai_adjudication_enabled": True,
        "remediation_sandbox_enabled": True,
        "max_pages_default": 10,
        "target_latency_seconds": 25.0,
        "guaranteed_confidence_floor": 0.90,
    },
    "max": {
        "name": "MAX",
        "description": "Enterprise-grade maximal audit featuring full site topology crawling, anti-bot escalation, full interaction testing, screen-reader validation, and deep remediation verification.",
        "engines_enabled": [
            "beacon_static",
            "beacon_heuristics",
            "beacon_browser",
            "beacon_coga",
            "beacon_visual",
            "axe",
            "ibm",
            "ai_adjudicator",
            "guidepup_sr",
            "remediation_sandbox",
        ],
        "browser_required": True,
        "visual_analysis_enabled": True,
        "interaction_probes_enabled": True,
        "assistive_tech_enabled": True,
        "ai_adjudication_enabled": True,
        "remediation_sandbox_enabled": True,
        "max_pages_default": 50,
        "target_latency_seconds": 90.0,
        "guaranteed_confidence_floor": 0.95,
    },
}


def get_scan_mode_capabilities(scan_mode: str) -> dict[str, Any]:
    """Retrieve formalized capability profile for a scan mode."""
    mode = str(scan_mode or "fast").lower().strip()
    return SCAN_MODE_CAPABILITIES.get(mode, SCAN_MODE_CAPABILITIES["fast"])


# ── §23: Page Classification & Template Clustering ────────────────────────────

PAGE_TYPE_PATTERNS = [
    ("login", re.compile(r"/(login|signin|auth|session)", re.IGNORECASE)),
    ("account", re.compile(r"/(account|profile|settings|user|my-)", re.IGNORECASE)),
    ("dashboard", re.compile(r"/(dashboard|portal|admin|console)", re.IGNORECASE)),
    ("checkout", re.compile(r"/(checkout|cart|basket|payment|order)", re.IGNORECASE)),
    ("product", re.compile(r"/(product|item|p/|sku|shop/item)", re.IGNORECASE)),
    ("category", re.compile(r"/(category|collection|browse|shop/c/)", re.IGNORECASE)),
    ("documentation", re.compile(r"/(docs|documentation|guide|api|reference)", re.IGNORECASE)),
    ("blog", re.compile(r"/(blog|posts?|news|articles?|stories)", re.IGNORECASE)),
    ("search", re.compile(r"/(search|find|query)", re.IGNORECASE)),
    ("form", re.compile(r"/(contact|inquiry|apply|register|signup)", re.IGNORECASE)),
    ("landing", re.compile(r"/(landing|promo|features|pricing|about)", re.IGNORECASE)),
]


def classify_page_type(url: str, title: str = "", html: str = "") -> str:
    """
    Infers the functional page class based on route path, title, and HTML structure.
    Returns one of: homepage, login, account, dashboard, checkout, product,
    category, documentation, blog, search, form, landing, or generic.
    """
    path = urlparse(url).path.lower().strip()
    if path in ("", "/", "/index.html", "/index.htm"):
        return "homepage"

    # Route pattern check
    for p_type, regex in PAGE_TYPE_PATTERNS:
        if regex.search(path):
            return p_type

    # Title pattern check
    title_lower = title.lower()
    if any(k in title_lower for k in ["log in", "sign in", "authentication"]):
        return "login"
    if any(k in title_lower for k in ["cart", "checkout", "shopping bag"]):
        return "checkout"
    if any(k in title_lower for k in ["docs", "documentation", "api reference"]):
        return "documentation"
    if any(k in title_lower for k in ["search results", "search"]):
        return "search"
    if any(k in title_lower for k in ["contact us", "get in touch", "apply"]):
        return "form"

    # Structural signature check
    if "<article" in html:
        return "article"
    if "<form" in html and ("password" in html or "type='password'" in html):
        return "login"
    if "<form" in html:
        return "form"

    return "article" if len(path.split("/")) > 2 else "landing"


def compute_template_hash(
    url: str,
    tag_hierarchy: list[str] | None = None,
    landmarks: set[str] | None = None,
) -> str:
    """
    Computes a deterministic structural template hash based on DOM hierarchy and path depth.
    Pages with matching template hashes share component layouts.
    """
    path = urlparse(url).path
    segments = [s for s in path.split("/") if s]
    depth = len(segments)

    # Normalize variable segments (IDs, numbers, slugs)
    normalized_segments = []
    for s in segments:
        if re.match(r"^\d+$", s) or re.match(r"^[a-f0-9-]{8,}$", s):
            normalized_segments.append("{id}")
        else:
            normalized_segments.append(s)

    norm_path = "/" + "/".join(normalized_segments)
    raw_sig = f"{norm_path}|depth:{depth}"

    if landmarks:
        raw_sig += f"|landmarks:{','.join(sorted(landmarks))}"
    if tag_hierarchy:
        raw_sig += f"|tags:{','.join(tag_hierarchy[:15])}"

    return hashlib.sha256(raw_sig.encode("utf-8")).hexdigest()[:12]


# ── §22: Site Topology Construction ───────────────────────────────────────────

class TopologyNode:
    """Represents a discovered page node in the site topology."""

    def __init__(
        self,
        url: str,
        page_type: str,
        template_hash: str,
        route_depth: int,
        navigation_relationship: str,
    ):
        self.url = url
        self.page_type = page_type
        self.template_hash = template_hash
        self.route_depth = route_depth
        self.navigation_relationship = navigation_relationship

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_url": self.url,
            "page_type": self.page_type,
            "template_hash": self.template_hash,
            "route_depth": self.route_depth,
            "navigation_relationship": self.navigation_relationship,
        }


def build_site_topology(
    root_url: str,
    discovered_urls: list[str],
    max_representatives_per_template: int = 2,
) -> dict[str, Any]:
    """
    Upgrades crawler intelligence to build a multi-level site topology (§22).
    Discovers:
    domain -> sitemap -> navigation graph -> routes -> templates -> representative pages
    """
    parsed_root = urlparse(root_url)
    root_domain = parsed_root.netloc.lower()

    nodes: list[TopologyNode] = []
    templates: dict[str, list[TopologyNode]] = {}

    for u in discovered_urls:
        p = urlparse(u)
        if p.netloc and p.netloc.lower() != root_domain:
            continue  # ignore off-domain

        path_clean = p.path.strip("/")
        depth = len(path_clean.split("/")) if path_clean else 0

        # Determine navigation relationship relative to root
        if p.path in ("", "/", "/index.html", "/index.htm"):
            rel = "root"
        elif depth == 1:
            rel = "direct_child"
        else:
            rel = "descendant"

        p_type = classify_page_type(u)
        t_hash = compute_template_hash(u)

        node = TopologyNode(
            url=u,
            page_type=p_type,
            template_hash=t_hash,
            route_depth=depth,
            navigation_relationship=rel,
        )
        nodes.append(node)
        templates.setdefault(t_hash, []).append(node)

    # Pick representative pages per template cluster
    representative_pages = []
    for t_hash, t_nodes in templates.items():
        representative_pages.extend(t_nodes[:max_representatives_per_template])

    return {
        "domain": root_domain,
        "total_pages_discovered": len(nodes),
        "total_templates": len(templates),
        "topology_nodes": [n.to_dict() for n in nodes],
        "representative_urls": [n.url for n in representative_pages],
        "template_clusters": {
            t_hash: {
                "count": len(t_nodes),
                "page_type": t_nodes[0].page_type,
                "sample_urls": [n.url for n in t_nodes[:3]],
            }
            for t_hash, t_nodes in templates.items()
        },
    }


# ── §23: Template Finding Inference ───────────────────────────────────────────

def mark_findings_as_template_inferred(
    findings: list[dict[str, Any]],
    template_hash: str,
    source_url: str,
    confidence_discount: float = 0.80,
) -> list[dict[str, Any]]:
    """
    Propagates established findings across matching template cluster pages.
    Marks findings as 'template_inferred' with reduced confidence per §23.
    """
    inferred_findings = []
    for f in findings:
        item = dict(f)
        item["is_template_inferred"] = True
        item["template_hash"] = template_hash
        item["inference_source_url"] = source_url
        orig_conf = float(item.get("confidence", 0.85))
        item["confidence"] = round(orig_conf * confidence_discount, 2)
        
        evidence = item.get("evidence")
        if not isinstance(evidence, dict):
            evidence = {}
        evidence["template_inference"] = {
            "source_url": source_url,
            "template_hash": template_hash,
            "discount_factor": confidence_discount,
        }
        item["evidence"] = evidence
        inferred_findings.append(item)

    return inferred_findings
