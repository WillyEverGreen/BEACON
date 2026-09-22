"""Unit tests for BEACON Native Multi-Signal DOM Topology & Adaptive Sampling."""

from app.crawlers.topology import (
    AdaptiveTopologyTracker,
    extract_multi_signal_fingerprint,
)

HTML_PRODUCT_BASE = """
<!DOCTYPE html>
<html>
<head><title>Product Base</title></head>
<body>
  <header role="banner"><nav role="navigation"><a href="/">Home</a><a href="/catalog">Catalog</a></nav></header>
  <main role="main">
    <article>
      <h1>Item Alpha</h1>
      <button>Add to Cart</button>
      <form><input type="text" name="coupon"><button type="submit">Apply</button></form>
    </article>
  </main>
  <footer role="contentinfo"><p>&copy; 2026</p></footer>
</body>
</html>
"""

# Same structural skeleton, but vastly different interactive controls (e.g. customized product with 10 form fields)
HTML_PRODUCT_HIGH_VARIANCE = """
<!DOCTYPE html>
<html>
<head><title>Product High Variance</title></head>
<body>
  <header role="banner"><nav role="navigation"><a href="/">Home</a><a href="/catalog">Catalog</a></nav></header>
  <main role="main">
    <article>
      <h1>Item Configurable</h1>
      <button>Add to Cart</button>
      <form>
        <input type="text" name="f1">
        <input type="text" name="f2">
        <input type="text" name="f3">
        <input type="text" name="f4">
        <input type="text" name="f5">
        <button type="button">Opt1</button>
        <button type="button">Opt2</button>
        <button type="button">Opt3</button>
        <button type="submit">Customize</button>
      </form>
    </article>
  </main>
  <footer role="contentinfo"><p>&copy; 2026</p></footer>
</body>
</html>
"""

HTML_BLOG = """
<!DOCTYPE html>
<html>
<body>
  <header><nav><a href="/">Home</a></nav></header>
  <main><article><h1>Blog</h1><p>Text</p></article></main>
  <footer><p>&copy; 2026</p></footer>
</body>
</html>
"""

HTML_CONTACT = """
<!DOCTYPE html>
<html>
<body>
  <header><nav><a href="/">Home</a></nav></header>
  <main><form action="/contact"><input type="text"><button>Send</button></form></main>
  <footer><p>&copy; 2026</p></footer>
</body>
</html>
"""


def test_multi_signal_fingerprint_extraction():
    fp = extract_multi_signal_fingerprint(HTML_PRODUCT_BASE)
    assert "header" in fp.landmarks
    assert "main" in fp.landmarks
    assert "banner" in fp.landmarks
    assert "navigation" in fp.landmarks
    assert fp.interactive_counts["button"] >= 2
    assert fp.interactive_counts["link"] >= 2
    assert fp.interactive_counts["input"] >= 1
    assert fp.form_count >= 1
    assert fp.dom_hash != "empty"


def test_adaptive_sampling_triggers_on_interactive_variance():
    tracker = AdaptiveTopologyTracker(base_max_per_template=2, adaptive_cap=4)

    # 1st sample
    fp1, is_new1, s1 = tracker.evaluate_page("https://store.com/item1", HTML_PRODUCT_BASE)
    assert is_new1 is True and s1 is True

    # 2nd sample (identical variance)
    fp2, is_new2, s2 = tracker.evaluate_page("https://store.com/item2", HTML_PRODUCT_BASE)
    assert is_new2 is False and s2 is True

    # 3rd sample with identical baseline -> rejected (cap=2 reached)
    fp3, is_new3, s3 = tracker.evaluate_page("https://store.com/item3", HTML_PRODUCT_BASE)
    assert is_new3 is False and s3 is False

    # 4th sample with HIGH VARIANCE (>25% more interactive elements) -> ADAPTIVELY SAMPLED!
    fp4, is_new4, s4 = tracker.evaluate_page("https://store.com/item4_custom", HTML_PRODUCT_HIGH_VARIANCE)
    assert is_new4 is False
    assert s4 is True, "High interactive variance must trigger adaptive sampling up to adaptive_cap"


def test_frontier_awareness_prevents_premature_termination():
    tracker = AdaptiveTopologyTracker(
        base_max_per_template=2,
        early_stop_consecutive=3,
        min_archetypes_before_early_stop=3,
    )

    # Sample archetype 1 (Product) twice
    tracker.evaluate_page("https://store.com/products/1", HTML_PRODUCT_BASE)
    tracker.evaluate_page("https://store.com/products/2", HTML_PRODUCT_BASE)

    # Sample archetype 2 (Blog) twice
    tracker.evaluate_page("https://store.com/blog/1", HTML_BLOG)
    tracker.evaluate_page("https://store.com/blog/2", HTML_BLOG)

    # 4 redundant products evaluated, BUT unexplored frontier has "/contact" which is unexplored!
    frontier = ["https://store.com/contact/form", "https://store.com/products/99"]
    for i in range(4):
        tracker.evaluate_page(f"https://store.com/products/{i+10}", HTML_PRODUCT_BASE, unexplored_frontier_urls=frontier)

    # Should NOT terminate because frontier still has unexplored "/contact" path!
    assert tracker.should_terminate_crawl() is False

    # Now explore archetype 3 (Contact)
    tracker.evaluate_page("https://store.com/contact/form", HTML_CONTACT)

    # Now frontier has NO novel path prefixes
    exhausted_frontier = ["https://store.com/products/100", "https://store.com/blog/50"]
    for i in range(5):
        tracker.evaluate_page(f"https://store.com/products/{i+20}", HTML_PRODUCT_BASE, unexplored_frontier_urls=exhausted_frontier)

    # Now all conditions met: >= 3 archetypes, >= 5 low gain, frontier diversity low
    assert tracker.should_terminate_crawl() is True
    summary = tracker.get_summary()
    assert summary["stop_reason"] == "low_information_gain_frontier_exhausted"
