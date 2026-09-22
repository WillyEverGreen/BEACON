"""
Unit tests for Batch 4: Site Intelligence (§22–§24).
Verifies:
- §22: build_site_topology and navigation relationship inference
- §23: classify_page_type, compute_template_hash, and mark_findings_as_template_inferred
- §24: get_scan_mode_capabilities for FAST, DEEP, and MAX modes
"""


from app.services.site_intelligence import (
    build_site_topology,
    classify_page_type,
    compute_template_hash,
    get_scan_mode_capabilities,
    mark_findings_as_template_inferred,
)


class TestBatch4SiteIntelligence:

    def test_scan_mode_capabilities(self):
        # FAST mode: lightweight, no browser, fast latency
        fast = get_scan_mode_capabilities("fast")
        assert fast["name"] == "FAST"
        assert fast["browser_required"] is False
        assert "beacon_static" in fast["engines_enabled"]
        assert fast["assistive_tech_enabled"] is False

        # DEEP mode: browser required, AI adjudication, visual
        deep = get_scan_mode_capabilities("deep")
        assert deep["name"] == "DEEP"
        assert deep["browser_required"] is True
        assert deep["visual_analysis_enabled"] is True
        assert "ai_adjudicator" in deep["engines_enabled"]

        # MAX mode: maximal audit with AT integration and full interaction
        max_mode = get_scan_mode_capabilities("max")
        assert max_mode["name"] == "MAX"
        assert max_mode["browser_required"] is True
        assert max_mode["assistive_tech_enabled"] is True
        assert "guidepup_sr" in max_mode["engines_enabled"]
        assert max_mode["guaranteed_confidence_floor"] == 0.95

    def test_classify_page_type(self):
        assert classify_page_type("https://example.com/") == "homepage"
        assert classify_page_type("https://example.com/login") == "login"
        assert classify_page_type("https://example.com/checkout/step1") == "checkout"
        assert classify_page_type("https://example.com/docs/api-reference") == "documentation"
        assert classify_page_type("https://example.com/blog/2026/09/update") == "blog"
        assert classify_page_type("https://example.com/product/48201") == "product"
        assert classify_page_type("https://example.com/contact-us") == "form"

    def test_compute_template_hash_slug_normalization(self):
        # Product items with different IDs must resolve to the SAME template hash
        hash1 = compute_template_hash("https://example.com/product/101")
        hash2 = compute_template_hash("https://example.com/product/202")
        assert hash1 == hash2

        # A documentation page must resolve to a DIFFERENT template hash
        hash_docs = compute_template_hash("https://example.com/docs/getting-started")
        assert hash1 != hash_docs

    def test_build_site_topology(self):
        urls = [
            "https://example.com/",
            "https://example.com/about",
            "https://example.com/product/1",
            "https://example.com/product/2",
            "https://example.com/contact",
            "https://external.com/page",  # should be filtered out
        ]

        topo = build_site_topology("https://example.com/", urls, max_representatives_per_template=1)
        assert topo["domain"] == "example.com"
        assert topo["total_pages_discovered"] == 5
        assert len(topo["representative_urls"]) >= 3

        # Check node relationships
        nodes = {n["page_url"]: n for n in topo["topology_nodes"]}
        assert nodes["https://example.com/"]["navigation_relationship"] == "root"
        assert nodes["https://example.com/about"]["navigation_relationship"] == "direct_child"
        assert nodes["https://example.com/product/1"]["navigation_relationship"] == "descendant"

    def test_mark_findings_as_template_inferred(self):
        sample_findings = [
            {
                "rule_id": "image-alt",
                "element": "img#header-logo",
                "confidence": 0.90,
                "wcag_criterion": "1.1.1",
            }
        ]

        inferred = mark_findings_as_template_inferred(
            findings=sample_findings,
            template_hash="tmpl_abc123",
            source_url="https://example.com/product/1",
            confidence_discount=0.80,
        )

        assert len(inferred) == 1
        item = inferred[0]
        assert item["is_template_inferred"] is True
        assert item["template_hash"] == "tmpl_abc123"
        assert item["inference_source_url"] == "https://example.com/product/1"
        assert item["confidence"] == 0.72  # 0.90 * 0.80
        assert "template_inference" in item["evidence"]
