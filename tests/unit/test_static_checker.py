from app.services.static_checks import StaticChecker


# 1. Blocked page guard - should suppress landmark/heading checks
def test_blocked_page_suppresses_structural_checks():
    html = "<html><body>Access Denied</body></html>"
    # Note: StaticChecker implementation might use self.fetch_status if provided
    checker = StaticChecker(html, "https://example.com", fetch_status=403)
    issues = checker.run_all()
    rule_ids = [i["rule_id"] for i in issues]
    assert "no-main-landmark" not in rule_ids
    assert "no-headings" not in rule_ids

# 2. SPA shell detection - should not fire structural violations
def test_spa_shell_no_false_positives():
    html = """<html lang="en"><head><title>App</title></head>
    <body><div id="root"></div>
    <script></script><script></script><script></script><script></script>
    </body></html>"""
    checker = StaticChecker(html, "https://spa.example.com")
    issues = checker.run_all()
    rule_ids = [i["rule_id"] for i in issues]
    assert "no-main-landmark" not in rule_ids

# 3. Missing alt - must fire
def test_missing_alt_fires():
    html = '<html lang="en"><body><img src="logo.png"></body></html>'
    checker = StaticChecker(html, "https://example.com")
    issues = checker.run_all()
    assert any(i["rule_id"] == "missing-alt" for i in issues)

# 4. Decorative image with role=presentation - should NOT fire missing-alt
def test_decorative_image_no_false_positive():
    html = '<html lang="en"><body><img src="x.png" role="presentation" alt=""></body></html>'
    checker = StaticChecker(html, "https://example.com")
    issues = checker.run_all()
    assert not any(i["rule_id"] == "missing-alt" for i in issues)

# 5. Contrast finder integration
def test_color_contrast_fires_and_suggests_fix():
    html = '''<html lang="en"><body>
    <p style="color: #aaaaaa; background-color: #ffffff;">Low contrast text</p>
    </body></html>'''
    checker = StaticChecker(html, "https://example.com")
    issues = checker.run_all()
    contrast_issues = [i for i in issues if i["rule_id"] == "color-contrast"]
    assert len(contrast_issues) > 0
    # Check if evidence contains suggested_color from Contrast-Finder integration
    assert "suggested_color" in contrast_issues[0].get("evidence", {})

# 6. Nested interactive - button inside link
def test_nested_interactive_fires():
    html = '<html lang="en"><body><a href="/"><button>Click</button></a></body></html>'
    checker = StaticChecker(html, "https://example.com")
    issues = checker.run_all()
    assert any(i["rule_id"] == "nested-interactive" for i in issues)

# Dedup check for nested interactive
def test_nested_interactive_no_duplicates():
    html = '<html lang="en"><body><a href="/"><button>X</button></a></body></html>'
    checker = StaticChecker(html, "https://example.com")
    issues = [i for i in checker.run_all() if i["rule_id"] == "nested-interactive"]
    issue_ids = [i["issue_id"] for i in issues]
    assert len(issue_ids) == len(set(issue_ids)), "Duplicate nested-interactive findings"
    assert len(issues) == 1, f"Expected 1 issue, found {len(issues)}"

# 7. Duplicate IDs
def test_duplicate_ids_fires():
    html = '<html lang="en"><body><div id="main">A</div><div id="main">B</div></body></html>'
    checker = StaticChecker(html, "https://example.com")
    issues = checker.run_all()
    assert any(i["rule_id"] == "duplicate-id" for i in issues)

# 8. Broken aria-labelledby reference
def test_broken_aria_labelledby_fires():
    html = '<html lang="en"><body><input aria-labelledby="nonexistent"></body></html>'
    checker = StaticChecker(html, "https://example.com")
    issues = checker.run_all()
    assert any(i["rule_id"] == "aria-label-missing-content" or i["rule_id"] == "broken-aria-label" for i in issues)

# 9. Placeholder-only label
def test_placeholder_as_label_fires():
    html = '<html lang="en"><body><input type="text" placeholder="Email"></body></html>'
    checker = StaticChecker(html, "https://example.com")
    issues = checker.run_all()
    # The rule ID in our system is 'form-label-missing' or similar for this pattern
    assert any(i["rule_id"] == "form-label-missing" for i in issues)

# 10. Valid page - zero false positives
def test_clean_page_no_violations():
    html = '''<!DOCTYPE html>
    <html lang="en">
    <head><title>Clean Page</title></head>
    <body>
      <header><nav aria-label="Main"><a href="/">Home</a></nav></header>
      <main><h1>Welcome</h1><p>Content here.</p></main>
      <footer>Footer</footer>
    </body></html>'''
    checker = StaticChecker(html, "https://example.com")
    issues = checker.run_all()
    # Filter for serious/critical violations
    violations = [i for i in issues if i.get("severity") in ("critical", "serious")]
    assert len(violations) == 0, f"False positives on clean page: {[i['rule_id'] for i in violations]}"
