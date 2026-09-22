from app.services.heuristics import HeuristicAnalyzer


def test_keyboard_trap_tabindex_and_click_handlers():
    """Verify that HeuristicAnalyzer correctly flags positive tabindex and interactive elements missing tabindex."""
    html_content = """
    <html>
        <body>
            <!-- Positive tabindex (violation) -->
            <div tabindex="3">Positive Tabindex Element</div>
            <div tabindex="0">Normal Focusable Element</div>
            <div tabindex="-1">Programmatically Focusable Element</div>
            
            <!-- Clickable div with no tabindex (violation) -->
            <div onclick="doSomething()">Clickable Div</div>
            <span onclick="doSomethingElse()">Clickable Span</span>
            
            <!-- Normal interactive elements with click handlers (should be ignored) -->
            <button onclick="submit()">Submit</button>
            <a href="#" onclick="navigate()">Link</a>
        </body>
    </html>
    """
    
    analyzer = HeuristicAnalyzer(html_content, "https://example.com/test")
    issues = analyzer.run_all()
    
    # Extract rule IDs flagged
    flagged_rules = [issue["rule_id"] for issue in issues]
    
    # Must flag positive tabindex
    assert "tabindex" in flagged_rules
    
    # Must flag clickable no-tabindex elements
    assert "keyboard-focusable" in flagged_rules
    
    # Check details of tabindex issue
    tabindex_issues = [i for i in issues if i["rule_id"] == "tabindex"]
    assert len(tabindex_issues) == 1
    assert "tabindex='3'" in tabindex_issues[0]["description"]
    
    # Check details of keyboard-focusable issue
    focusable_issues = [i for i in issues if i["rule_id"] == "keyboard-focusable"]
    assert len(focusable_issues) == 2  # one for div, one for span
    assert focusable_issues[0]["element"] == "div" or focusable_issues[0]["element"] == "span"
