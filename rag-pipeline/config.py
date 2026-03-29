# config.py

SOURCES = [
  # WCAG — rules, understanding, techniques, failures
  { "silo": "wcag", "url": "https://w3c.github.io/wcag/guidelines/22/",                        "depth": 2 },
  { "silo": "wcag", "url": "https://w3c.github.io/wcag/understanding/22/",                     "depth": 3 },
  { "silo": "wcag", "url": "https://www.w3.org/TR/WCAG22/",                                    "depth": 1 },
  { "silo": "wcag", "url": "https://www.w3.org/WAI/WCAG22/Techniques/html/",                   "depth": 1 },
  { "silo": "wcag", "url": "https://www.w3.org/WAI/WCAG22/Techniques/css/",                    "depth": 1 },
  { "silo": "wcag", "url": "https://www.w3.org/WAI/WCAG22/Techniques/aria/",                   "depth": 1 },
  { "silo": "wcag", "url": "https://www.w3.org/WAI/WCAG22/Techniques/failures/",               "depth": 1 },  # critical
  { "silo": "wcag", "url": "https://www.w3.org/WAI/WCAG2/supplemental/#cognitiveaccessibilityguidance", "depth": 1 },

  # ARIA — spec and full APG pattern library
  { "silo": "aria", "url": "https://w3c.github.io/aria/",                                      "depth": 3 },
  { "silo": "aria", "url": "https://www.w3.org/WAI/ARIA/apg/patterns/",                        "depth": 2 },  # all widget patterns

  # COGA — cognitive accessibility
  { "silo": "coga", "url": "https://w3c.github.io/coga/content-usable/",                       "depth": 3 },

  # MDN — practical developer reference
  { "silo": "mdn",  "url": "https://developer.mozilla.org/en-US/docs/Web/Accessibility",       "depth": 2 },

  # HTML Spec — complete semantic element coverage
  { "silo": "mdn",  "url": "https://html.spec.whatwg.org/multipage/forms.html",                "depth": 1 },
  { "silo": "mdn",  "url": "https://html.spec.whatwg.org/multipage/interactive-elements.html", "depth": 1 },
  { "silo": "mdn",  "url": "https://html.spec.whatwg.org/multipage/text-level-semantics.html", "depth": 1 },
  { "silo": "mdn",  "url": "https://html.spec.whatwg.org/multipage/grouping-content.html",     "depth": 1 },

  # WebAIM — real-world guidance
  { "silo": "webaim","url": "https://webaim.org/techniques/",                                  "depth": 2 },

  # Deque University — axe rule explanations + pass/fail examples
  { "silo": "axe",  "url": "https://dequeuniversity.com/rules/axe/html",                       "depth": 1 },

  # Inclusive Components — production-ready accessible patterns (check robots.txt)
  { "silo": "aria", "url": "https://inclusive-components.design/",                             "depth": 1 },

  # Scott O'Hara — edge case expertise (check robots.txt)
  { "silo": "aria", "url": "https://www.scottohara.me/",                                       "depth": 1 },
]

ALLOWED_DOMAINS = [
  "w3c.github.io",
  "www.w3.org",
  "developer.mozilla.org",
  "html.spec.whatwg.org",
  "webaim.org",
  "dequeuniversity.com",
  "inclusive-components.design",
  "www.scottohara.me",
]

BLOCKED_DOMAINS = ["github.com"]
