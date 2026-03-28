# config.py
SOURCES = [
  { "silo": "wcag",   "url": "https://w3c.github.io/wcag/guidelines/22/",     "depth": 2 },
  { "silo": "wcag",   "url": "https://w3c.github.io/wcag/understanding/22/",  "depth": 3 },
  { "silo": "wcag",   "url": "https://www.w3.org/TR/WCAG22/",                 "depth": 1 },
  { "silo": "aria",   "url": "https://w3c.github.io/aria/",                   "depth": 3 },
  { "silo": "aria",   "url": "https://w3c.github.io/aria-practices/",         "depth": 3 },
  { "silo": "coga",   "url": "https://w3c.github.io/coga/content-usable/",    "depth": 3 },
  { "silo": "mdn",    "url": "https://developer.mozilla.org/en-US/docs/Web/Accessibility", "depth": 2 },
  { "silo": "webaim", "url": "https://webaim.org/",                           "depth": 2 },
  { "silo": "wcag",   "url": "https://www.w3.org/WAI/WCAG22/Techniques/",     "depth": 2 },
  { "silo": "axe",    "url": "https://dequeuniversity.com/rules/axe/4.9/",    "depth": 1 },
  { "silo": "mdn",    "url": "https://html.spec.whatwg.org/multipage/forms.html", "depth": 1 },
  { "silo": "mdn",    "url": "https://html.spec.whatwg.org/multipage/interactive-elements.html", "depth": 1 },
]

ALLOWED_DOMAINS = [
  "w3c.github.io", "www.w3.org",
  "developer.mozilla.org", "webaim.org",
  "dequeuniversity.com", "html.spec.whatwg.org"
]
BLOCKED_DOMAINS = ["github.com"]
