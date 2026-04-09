from app.crawlers.page_selector import select_links_for_enqueue


def test_interaction_page_detected_from_url_keyword():
    selected, skipped = select_links_for_enqueue(
        [{"href": "/login", "text": "", "in_nav": False, "in_header_footer": False}],
        current_fetch_url="https://example.com/",
        seed_url="https://example.com/",
        next_depth=1,
    )

    assert skipped == []
    assert len(selected) == 1
    assert selected[0].page_type == "interaction"
    assert selected[0].page_weight == 0.9


def test_interaction_page_detected_from_link_text():
    selected, _ = select_links_for_enqueue(
        [{"href": "/start", "text": "Get started", "in_nav": False, "in_header_footer": False}],
        current_fetch_url="https://example.com/",
        seed_url="https://example.com/",
        next_depth=1,
    )

    assert len(selected) == 1
    assert selected[0].page_type == "interaction"


def test_external_links_are_excluded():
    selected, skipped = select_links_for_enqueue(
        [{"href": "https://other.example.com/page", "text": "External", "in_nav": False, "in_header_footer": False}],
        current_fetch_url="https://example.com/",
        seed_url="https://example.com/",
        next_depth=1,
    )

    assert selected == []
    assert len(skipped) == 1
    assert skipped[0]["reason"] == "external"


def test_file_extension_exclusions_are_applied():
    selected, skipped = select_links_for_enqueue(
        [{"href": "/assets/report.pdf", "text": "PDF", "in_nav": False, "in_header_footer": False}],
        current_fetch_url="https://example.com/",
        seed_url="https://example.com/",
        next_depth=1,
    )

    assert selected == []
    assert len(skipped) == 1
    assert skipped[0]["reason"] == "exclusion_rule"


def test_infinite_space_patterns_are_excluded_beyond_allowed_depth():
    selected, skipped = select_links_for_enqueue(
        [
            {"href": "/page/2", "text": "Page 2", "in_nav": False, "in_header_footer": False},
            {"href": "/blog?cursor=abc", "text": "Next", "in_nav": False, "in_header_footer": False},
            {"href": "/tag/accessibility", "text": "Tag", "in_nav": False, "in_header_footer": False},
        ],
        current_fetch_url="https://example.com/blog",
        seed_url="https://example.com/",
        next_depth=3,
    )

    assert selected == []
    assert len(skipped) == 3
    reasons = {item["reason"] for item in skipped}
    assert reasons == {"exclusion_rule", "low_value_pattern"}


def test_standard_pages_are_skipped_at_depth_two_or_more():
    selected, skipped = select_links_for_enqueue(
        [
            {"href": "/docs", "text": "Documentation", "in_nav": False, "in_header_footer": False},
            {"href": "/contact", "text": "Contact", "in_nav": False, "in_header_footer": False},
            {"href": "/site-map", "text": "Map", "in_nav": True, "in_header_footer": False},
        ],
        current_fetch_url="https://example.com/",
        seed_url="https://example.com/",
        next_depth=2,
    )

    selected_types = {row.page_type for row in selected}
    selected_urls = {row.fetch_url for row in selected}

    assert "https://example.com/docs" not in selected_urls
    assert selected_types == {"interaction", "nav"}
    assert any(item["reason"] == "low_value_depth" for item in skipped)
