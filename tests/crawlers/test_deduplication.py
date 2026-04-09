from app.crawlers.crawler import CrawlSession


def test_same_url_different_fragments_are_crawled_once():
    session = CrawlSession()

    first, _ = session.enqueue(
        fetch_url="https://example.com/page#top",
        depth=1,
        page_type="standard",
        page_weight=0.7,
    )
    second, _ = session.enqueue(
        fetch_url="https://example.com/page#bottom",
        depth=1,
        page_type="standard",
        page_weight=0.7,
    )

    assert first is True
    assert second is False
    assert session.pages_skipped_dedup == 1
    assert len(session) == 1


def test_same_url_different_query_order_is_crawled_once():
    session = CrawlSession()

    first, _ = session.enqueue(
        fetch_url="https://example.com/search?b=2&a=1",
        depth=1,
        page_type="standard",
        page_weight=0.7,
    )
    second, _ = session.enqueue(
        fetch_url="https://example.com/search?a=1&b=2",
        depth=1,
        page_type="standard",
        page_weight=0.7,
    )

    assert first is True
    assert second is False
    assert session.pages_skipped_dedup == 1
    assert len(session) == 1


def test_distinct_urls_are_both_crawled():
    session = CrawlSession()

    first, _ = session.enqueue(
        fetch_url="https://example.com/about",
        depth=1,
        page_type="nav",
        page_weight=0.8,
    )
    second, _ = session.enqueue(
        fetch_url="https://example.com/contact",
        depth=1,
        page_type="interaction",
        page_weight=0.9,
    )

    assert first is True
    assert second is True
    assert session.pages_skipped_dedup == 0
    assert len(session) == 2
