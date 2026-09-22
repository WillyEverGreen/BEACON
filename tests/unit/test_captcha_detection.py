import pytest

from app.services.static_checks import StaticChecker

CAPTCHA_FIXTURES = [
    (
        "recaptcha",
        """<html><body>
            <div class="g-recaptcha" data-sitekey="your_site_key"></div>
            <script src="https://www.google.com/recaptcha/api.js" async defer></script>
        </body></html>"""
    ),
    (
        "hcaptcha",
        """<html><body>
            <form action="?" method="POST">
                <div class="h-captcha" data-sitekey="your-site-key"></div>
                <script src="https://js.hcaptcha.com/1/api.js" async defer></script>
            </form>
        </body></html>"""
    ),
    (
        "turnstile",
        """<html><body>
            <div class="cf-turnstile" data-sitekey="your-site-key"></div>
            <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
        </body></html>"""
    )
]

@pytest.mark.parametrize("name,html", CAPTCHA_FIXTURES)
def test_captcha_detection(name: str, html: str) -> None:
    checker = StaticChecker(html, "http://example.com")
    issues = checker.run_all(["captcha"])
    
    assert len(issues) > 0, f"Failed to detect {name} CAPTCHA"
    assert any(i["rule_id"] == "captcha-detected" for i in issues), f"Missing captcha-detected rule for {name}"
