# test_rag.py — Comprehensive RAG Reliability Test Suite
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from query import hybrid_retrieve, rerank, answer, expand_query

# ─────────────────────────────────────────────
# TEST CASES
# ─────────────────────────────────────────────

# (test_name, query_string, required_keywords_in_result, silo_hint)
RETRIEVAL_TESTS = [
    # WCAG SC Coverage
    ("Alt Text (1.1.1)",          "img element missing alt attribute non-text content",             ["alt", "1.1.1"],              "wcag"),
    ("Captions (1.2.2)",          "video captions prerecorded synchronized",                        ["caption", "1.2.2"],          "wcag"),
    ("Info & Relationships(1.3.1)","semantic HTML heading landmark structure",                      ["heading", "1.3.1"],          "wcag"),
    ("Colour Only (1.4.1)",       "color not sole means conveying information",                     ["color", "1.4.1"],            "wcag"),
    ("Contrast Min (1.4.3)",      "contrast ratio 4.5:1 normal text foreground background",        ["contrast", "1.4.3"],         "wcag"),
    ("Resize Text (1.4.4)",       "resize text viewport meta zoom 200 percent",                    ["resize", "1.4.4"],           "wcag"),
    ("Non-text Contrast (1.4.11)","UI component icon non-text contrast 3:1 focus ring",            ["contrast", "1.4.11"],        "wcag"),
    ("Reflow (1.4.10)",           "reflow 320px horizontal scroll responsive",                     ["reflow", "1.4.10"],          "wcag"),
    ("Text Spacing (1.4.12)",     "text spacing line height letter word spacing override",          ["spacing", "1.4.12"],         "wcag"),
    ("Keyboard (2.1.1)",          "keyboard accessible all functionality mouse-only",               ["keyboard", "2.1.1"],         "wcag"),
    ("No Keyboard Trap (2.1.2)",  "keyboard trap focus escape modal dialog",                       ["keyboard", "2.1.2"],         "wcag"),
    ("Skip Navigation (2.4.1)",   "skip navigation link bypass blocks first link",                 ["skip", "bypass", "2.4.1"],   "wcag"),
    ("Page Titled (2.4.2)",       "page title unique descriptive HTML document",                   ["title", "2.4.2"],            "wcag"),
    ("Focus Order (2.4.3)",       "focus order logical tabindex sequence",                         ["focus", "2.4.3"],            "wcag"),
    ("Link Purpose (2.4.4)",      "link text descriptive purpose context",                         ["link", "2.4.4"],             "wcag"),
    ("Focus Visible (2.4.7)",     "focus visible indicator keyboard navigation",                   ["focus", "2.4.7"],            "wcag"),
    ("Language (3.1.1)",          "lang attribute html element page language",                     ["lang", "3.1.1"],             "wcag"),
    ("Labels/Instructions (3.3.2)","form field label required input instruction",                  ["label", "3.3.2"],            "wcag"),
    ("Error ID (3.3.1)",          "error identification accessible message input",                 ["error", "3.3.1"],            "wcag"),
    ("Name Role Value (4.1.2)",   "ARIA role state button widget accessible name",                 ["aria", "4.1.2"],             "wcag"),
    ("Status Messages (4.1.3)",   "aria-live dynamic content status message screen reader",        ["aria-live", "4.1.3"],        "wcag"),
    ("Target Size (2.5.8)",       "target size minimum 24px touch pointer",                        ["target", "2.5.8"],           "wcag"),
    # ARIA-specific
    ("ARIA labelledby",           "aria-labelledby association form control custom widget",        ["aria-labelledby"],           "aria"),
    ("ARIA expanded",             "aria-expanded state toggle button disclosure",                  ["aria-expanded"],             "aria"),
    ("ARIA live regions",         "aria-live polite assertive dynamic content update",             ["aria-live"],                 "aria"),
    ("ARIA modal",                "aria-modal dialog focus trap role dialog",                      ["dialog", "aria"],            "aria"),
    # MDN
    ("MDN tabindex",              "tabindex focusable element keyboard accessibility",             ["tabindex"],                  "mdn"),
    ("MDN role attribute",        "role attribute HTML ARIA accessibility",                       ["role"],                      "mdn"),
    ("MDN input label",           "label element for attribute input HTML form",                  ["label"],                     "mdn"),
    # WebAIM practical guidance
    ("WebAIM screen reader",      "screen reader testing JAWS NVDA VoiceOver",                    ["screen reader", "voiceover"], "webaim"),
    ("WebAIM contrast checker",   "contrast checker tool color luminance ratio",                  ["contrast"],                  "webaim"),
    ("WebAIM skip nav",           "skip navigation link bypass repeated blocks technique",         ["skip"],                      "webaim"),
    # Engineering corpus / toolkit
    ("Toolkit WCAG design",       "wcag aaa web design engineering implementation",               ["wcag"],                      "toolkit"),
    # Edge cases
    ("Empty query",               "accessibility",                                                ["accessibility"],             None),
    ("Gibberish",                 "fdjhgkdfhgkdf html",                                          [],                            None),  # should return something, not crash
    ("Very long query",           "The img element is missing an alt attribute which is required by WCAG 2.2 Success Criterion 1.1.1 Non-text Content to ensure screen readers can describe images to users who are blind or have low vision", ["alt", "1.1.1"], "wcag"),
]

# ─────────────────────────────────────────────
# RUNNER
# ─────────────────────────────────────────────

def check_keywords(text: str, keywords: list[str]) -> tuple[list[str], list[str]]:
    lower = text.lower()
    found   = [k for k in keywords if k.lower() in lower]
    missing = [k for k in keywords if k.lower() not in lower]
    return found, missing

def run_tests():
    print("=" * 70)
    print("  COMPREHENSIVE RAG RELIABILITY TEST SUITE")
    print("=" * 70)

    results = []

    for name, query, keywords, expected_silo in RETRIEVAL_TESTS:
        t0 = time.time()
        try:
            candidates = hybrid_retrieve(query)
            top3 = rerank(query, candidates)
            elapsed = time.time() - t0

            if not top3:
                results.append({
                    "name": name, "status": "FAIL", "reason": "No results returned",
                    "time": elapsed, "keyword_hits": 0, "total_keywords": len(keywords),
                    "silo_hit": False
                })
                print(f"  ✗ {name:<40} | FAIL | No results | {elapsed:.2f}s")
                continue

            # Combine all top-3 text into one string for keyword searching
            combined = " ".join(c["text"] for c in top3).lower()
            found, missing = check_keywords(combined, keywords)

            # Check silo coverage
            silos_found = {c["meta"].get("silo") for c in top3}
            silo_hit = (expected_silo is None) or (expected_silo in silos_found)

            keyword_score = len(found) / len(keywords) if keywords else 1.0

            if keyword_score >= 0.5 and (expected_silo is None or silo_hit):
                status = "PASS"
                symbol = "✓"
            elif keyword_score > 0:
                status = "PARTIAL"
                symbol = "~"
            else:
                status = "FAIL"
                symbol = "✗"

            results.append({
                "name": name, "status": status,
                "keyword_hits": len(found), "total_keywords": len(keywords),
                "missing_keywords": missing, "silos_found": list(silos_found),
                "silo_hit": silo_hit, "time": elapsed
            })
            silo_str = ",".join(silos_found) if silos_found else "none"
            print(f"  {symbol} {name:<40} | {status:<7} | keywords {len(found)}/{len(keywords)} | silos [{silo_str}] | {elapsed:.2f}s")

        except Exception as e:
            elapsed = time.time() - t0
            results.append({"name": name, "status": "ERROR", "reason": str(e), "time": elapsed})
            print(f"  ✗ {name:<40} | ERROR | {str(e)[:60]} | {elapsed:.2f}s")

    # ─── Summary ─────────────────────────────
    print("\n" + "=" * 70)
    total   = len(results)
    passed  = sum(1 for r in results if r["status"] == "PASS")
    partial = sum(1 for r in results if r["status"] == "PARTIAL")
    failed  = sum(1 for r in results if r["status"] in ("FAIL","ERROR"))
    avg_time = sum(r.get("time", 0) for r in results) / total

    print(f"  PASS   : {passed}/{total}")
    print(f"  PARTIAL: {partial}/{total}")
    print(f"  FAIL   : {failed}/{total}")
    print(f"  Score  : {(passed + 0.5*partial)/total*100:.1f}%")
    print(f"  Avg Retrieval Time: {avg_time:.2f}s")
    print("=" * 70)

    if failed > 0:
        print("\n  FAILURES / ERRORS TO INVESTIGATE:")
        for r in results:
            if r["status"] in ("FAIL","ERROR"):
                print(f"  - {r['name']}: {r.get('reason', 'missing keywords: ' + str(r.get('missing_keywords', [])))}")

    # Write JSON report
    report_path = os.path.join(os.path.dirname(__file__), "test_report.json")
    with open(report_path, "w") as f:
        json.dump({
            "summary": {"total": total, "passed": passed, "partial": partial, "failed": failed,
                        "score_pct": round((passed + 0.5*partial)/total*100, 1), "avg_time_s": round(avg_time, 3)},
            "tests": results
        }, f, indent=2)
    print(f"\n  Full report saved → {report_path}")

if __name__ == "__main__":
    run_tests()
