from app.crawlers.crawler import CrawlSession, normalize_url_for_dedup


def test_fragment_is_removed_from_dedup_key():
    value = normalize_url_for_dedup("https://Example.com/path#section")
    assert value == "https://example.com/path"


def test_trailing_slash_is_stripped_from_path():
    value = normalize_url_for_dedup("https://Example.com/account/")
    assert value == "https://example.com/account"


def test_query_parameters_are_sorted_for_canonicalization():
    value = normalize_url_for_dedup("https://example.com/search?b=2&a=1")
    assert value == "https://example.com/search?a=1&b=2"


def test_fetch_url_is_preserved_while_dedup_uses_normalized_key():
    session = CrawlSession()
    fetch_url = "https://Example.com/path/?b=2&a=1#frag"
    enqueued, dedup_key = session.enqueue(
        fetch_url=fetch_url,
        depth=0,
        page_type="homepage",
        page_weight=1.0,
    )

    assert enqueued is True
    assert dedup_key == "https://example.com/path?a=1&b=2"

    entry = session.dequeue()
    assert entry is not None
    assert entry.fetch_url == fetch_url
    assert entry.dedup_key == dedup_key
