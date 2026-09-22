import pytest

from app.audit.fingerprint import stable_selector_fingerprint
from app.audit.site_aggregator import _page_weight, detect_page_type


def test_page_type_tiebreaks_and_weights():
    """Verify classification and weight matching for complex layouts (e.g. blog + form)."""
    # 1. Blog page with a newsletter signup form
    # The blog page has <article> tags, and a newsletter form.
    # Because 'form' is checked before 'article', it classifies as 'form' (critical input path).
    blog_with_form_dom = """
    <html>
        <body>
            <nav>Menu</nav>
            <main>
                <article>
                    <h1>Why Accessibility Matters</h1>
                    <p>Lorem ipsum dolor sit amet...</p>
                </article>
                <form action="/subscribe">
                    <label for="email">Newsletter</label>
                    <input type="email" id="email" />
                    <button type="submit">Subscribe</button>
                </form>
            </main>
        </body>
    </html>
    """
    page_type = detect_page_type("https://example.com/blog/post-1", blog_with_form_dom)
    weight = _page_weight(page_type)
    
    assert page_type == "form"
    assert weight == 2.0  # Crucial input path weight

    # 2. Listing page with a product card carousel
    # Matches 'listing' elements and 'add to cart' buttons.
    # Form is not matched. 'product' is step 4, 'listing' is step 5.
    # Therefore, it should classify as 'product' since 'product' is evaluated higher.
    listing_with_product_dom = """
    <html>
        <body>
            <div class="product-grid">
                <div class="product-card">
                    <h2>Wireless Headphones</h2>
                    <button class="add-to-cart">Add to cart</button>
                </div>
            </div>
            <div class="pagination">
                <a href="?page=2">Next</a>
            </div>
        </body>
    </html>
    """
    page_type_listing = detect_page_type("https://example.com/shop/all", listing_with_product_dom)
    weight_listing = _page_weight(page_type_listing)
    
    assert page_type_listing == "product"
    assert weight_listing == 2.0


def test_fingerprint_normalization_real_frameworks():
    """Verify selector normalization strips dynamic Tailwind, styled-components, and keeps bootstrap paths."""
    # Tailwind JIT dynamic selectors (e.g. rounded-[4px], bg-[#f3f3f3])
    tailwind_selector = "div.flex.items-center.rounded-\\[4px\\].bg-\\[\\#f3f3f3\\] > button.btn-primary"
    normalized_tailwind = stable_selector_fingerprint(tailwind_selector)
    assert "rounded" not in normalized_tailwind
    assert "bg" not in normalized_tailwind
    
    # Styled-components hashed selectors (e.g. ScButton-a1b2c3d4)
    styled_selector = "button.ScButton-a1b2c3d4.sc-button-primary"
    normalized_styled = stable_selector_fingerprint(styled_selector)
    assert "a1b2c3d4" not in normalized_styled
    
    # Plain bootstrap paths should remain stable and untouched
    bootstrap_selector = "div.container > div.row > div.col-md-6 > a.btn.btn-success"
    normalized_bootstrap = stable_selector_fingerprint(bootstrap_selector)
    assert normalized_bootstrap == "div.container > div.row > div.col-md-6 > a.btn.btn-success"


@pytest.mark.asyncio
async def test_bot_wall_preflight_check_live_mock():
    """Verify orchestrator's preflight bot wall check detects actual blocking responses without false-positives."""
    from unittest.mock import AsyncMock, patch

    from app.crawlers.orchestrator import CrawlerOrchestrator

    orchestrator = CrawlerOrchestrator()

    # Mock curl_cffi session to return a Cloudflare challenge response page
    mock_cf_response = AsyncMock()
    mock_cf_response.status_code = 403
    mock_cf_response.headers = {"cf-ray": "1234567890", "server": "cloudflare"}
    mock_cf_response.text = "Please enable Javascript and Cookies to proceed. Cloudflare DDOS Protection."

    with patch("curl_cffi.requests.AsyncSession.get", return_value=mock_cf_response):
        with pytest.raises(ValueError) as exc:
            await orchestrator._check_bot_wall("https://example.com")
        assert "protected by bot protection" in str(exc.value)

    # Mock normal response (preflight passes without error)
    mock_ok_response = AsyncMock()
    mock_ok_response.status_code = 200
    mock_ok_response.headers = {"server": "nginx"}
    mock_ok_response.text = "<html><body>Welcome</body></html>"

    with patch("curl_cffi.requests.AsyncSession.get", return_value=mock_ok_response):
        # Should not raise any exception
        await orchestrator._check_bot_wall("https://example.com")
