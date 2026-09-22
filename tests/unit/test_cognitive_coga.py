from app.services.cognitive_checks import CognitiveAnalyzer


def test_cognitive_rules_have_coga_pattern_refs():
    # Construct HTML to trigger all 7 cognitive rules
    html = """
    <html>
      <body>
        <nav>
          <ul>
            """ + ("<li><a href='#'>Link</a></li>" * 35) + """
          </ul>
        </nav>
        <p>The pedagogical methodology underlying this synergistic infrastructure requires polymorphic encapsulation and idempotent serialization to optimize bandwidth latency and throughput scalability across the entire deployment paradigm.</p>
        <button>submit</button>
        <form>
            """ + ("<input type='text' name='f'>" * 12) + """
        </form>
        <div class="error">Error</div>
      </body>
    </html>
    """
    
    analyzer = CognitiveAnalyzer(html, "http://example.com")
    scores = analyzer.run_all()
    issues = scores.get("issues", [])
    
    found_rules = set()
    for issue in issues:
        found_rules.add(issue["rule_id"])
        assert "coga_pattern_ref" in issue, f"Issue {issue['rule_id']} missing coga_pattern_ref"
        assert issue["coga_pattern_ref"] != "", f"Issue {issue['rule_id']} has empty coga_pattern_ref"
        
    expected_rules = {
        "readability", 
        "jargon", 
        "cta-clarity", 
        "nav-complexity", 
        "form-usability", 
        "form-no-progress", 
        "error-message-quality"
    }
    
    missing_rules = expected_rules - found_rules
    assert not missing_rules, f"Failed to trigger rules: {missing_rules}"
