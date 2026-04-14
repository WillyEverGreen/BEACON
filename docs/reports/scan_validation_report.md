# Scan Validation Report

Generated: 2026-04-14T16:07:05.490880+00:00

## 1. Summary
- Total sites tested: 10
- Overall sampled issue accuracy estimate (Valid+Likely): 80.0%
- System reliability verdict: **PARTIALLY VALID / NEEDS TUNING**
- Scaling consistency (Fast < Deep <= Max): FAIL
- Growth consistency (Deep >= 2x Fast and Max >= Deep): FAIL
- Axe coverage reliability (Deep/Max): FAIL

## 2. Mode Comparison Table
| Site | Fast Issues | Deep Issues | Max Issues | Scaling OK |
| ---- | ----------- | ----------- | ---------- | ---------- |
| https://example.com/ | 1 | 10 | 136 | YES |
| https://www.iana.org/domains/reserved | 6 | 87 | 493 | YES |
| https://www.w3.org/WAI/ | 1 | 5 | 88 | YES |
| https://www.gov.uk/ | 7 | 88 | 0 | NO |
| https://www.python.org/ | 8 | 193 | 902 | YES |
| https://developer.mozilla.org/en-US/ | 7 | 93 | 126 | YES |
| https://react.dev/ | 7 | 100 | 224 | YES |
| https://nextjs.org/ | 6 | 110 | 86 | NO |
| https://vuejs.org/ | 5 | 147 | 222 | YES |
| https://www.spacejam.com/1996/ | 10 | 88 | 0 | NO |

## 3. Performance Metrics
- Avg Fast scan time (s): 2.48
- Avg Deep scan time (s): 99.79
- Avg Max scan time (s): 206.64
- Avg Fast pages scanned: 1.0
- Avg Deep pages scanned: 9.7
- Avg Max pages scanned: 10.6

## 4. False Positive Analysis
- High confidence accuracy: 100.0%
- Medium confidence accuracy: 100.0%
- Low confidence accuracy: 0.0%

### Sampled Issue Reviews
#### https://example.com/
- [high] no-nav-landmark (conf=0.95, sev=minor): Likely — Moderate confidence 0.95 with standard rule behavior
- [high] no-header-landmark (conf=0.95, sev=minor): Likely — Moderate confidence 0.95 with standard rule behavior
- [medium] region (conf=0.795, sev=moderate): Likely — Moderate confidence 0.80 with standard rule behavior
- [medium] no-footer-landmark (conf=0.772, sev=minor): Likely — Moderate confidence 0.77 with standard rule behavior
- [low] landmark-one-main (conf=0.429, sev=moderate): False Positive — Low confidence 0.43

#### https://www.iana.org/domains/reserved
- [medium] no-lang (conf=0.85, sev=serious): Likely — Moderate confidence 0.85 with standard rule behavior
- [medium] empty-heading (conf=0.824, sev=minor): Likely — Moderate confidence 0.82 with standard rule behavior
- [low] div-itis-missing-semantics (conf=0.428, sev=minor): False Positive — Low confidence 0.43
- [other] color-contrast (conf=0.896, sev=serious): Likely — Moderate confidence 0.90 with standard rule behavior
- [other] link-purpose (conf=0.818, sev=moderate): Likely — Moderate confidence 0.82 with standard rule behavior

#### https://www.w3.org/WAI/
- [high] no-nav-landmark (conf=0.95, sev=minor): Likely — Moderate confidence 0.95 with standard rule behavior
- [high] semantic-html (conf=0.94, sev=moderate): Likely — Multiple corroborating sources (2)
- [medium] meta-refresh (conf=0.794, sev=serious): Likely — Moderate confidence 0.79 with standard rule behavior
- [low] landmark-unique (conf=0.429, sev=moderate): False Positive — Low confidence 0.43
- [other] landmark-no-duplicate-contentinfo (conf=0.695, sev=moderate): Likely — Moderate confidence 0.69 with standard rule behavior

#### https://www.gov.uk/

#### https://www.python.org/
- [high] aria-role (conf=0.99, sev=serious): Likely — Multiple corroborating sources (2)
- [high] aria-required-children (conf=0.95, sev=critical): Valid — Critical severity with confidence 0.95
- [medium] heading-order (conf=0.85, sev=moderate): Likely — Moderate confidence 0.85 with standard rule behavior
- [medium] aria-valid-attr-value (conf=0.85, sev=serious): Likely — Multiple corroborating sources (2)
- [low] timeout-no-warning (conf=0.441, sev=serious): False Positive — Low confidence 0.44

#### https://developer.mozilla.org/en-US/
- [high] svg-no-accessible-name (conf=0.99, sev=serious): Likely — Multiple corroborating sources (2)
- [high] responsive-reflow (conf=0.95, sev=serious): Likely — Moderate confidence 0.95 with standard rule behavior
- [medium] nested-interactive (conf=0.842, sev=serious): Likely — Moderate confidence 0.84 with standard rule behavior
- [medium] region (conf=0.795, sev=moderate): Likely — Moderate confidence 0.80 with standard rule behavior
- [low] unsafe-external-link (conf=0.484, sev=moderate): False Positive — Low confidence 0.48

#### https://react.dev/
- [high] svg-no-accessible-name (conf=0.99, sev=serious): Likely — Multiple corroborating sources (2)
- [medium] missing-skip-link (conf=0.85, sev=moderate): Likely — Moderate confidence 0.85 with standard rule behavior
- [medium] div-itis-missing-semantics (conf=0.85, sev=minor): Likely — Moderate confidence 0.85 with standard rule behavior
- [low] unsafe-external-link (conf=0.454, sev=moderate): False Positive — Low confidence 0.45
- [other] color-contrast (conf=0.896, sev=serious): Likely — Moderate confidence 0.90 with standard rule behavior

#### https://nextjs.org/
- [medium] heading-order (conf=0.85, sev=moderate): Likely — Moderate confidence 0.85 with standard rule behavior
- [medium] empty-link (conf=0.85, sev=serious): Likely — Moderate confidence 0.85 with standard rule behavior
- [low] short-link-text (conf=0.5, sev=minor): False Positive — Low confidence 0.50
- [other] link-purpose (conf=0.85, sev=moderate): Likely — Moderate confidence 0.85 with standard rule behavior
- [other] autocomplete-missing (conf=0.85, sev=moderate): Likely — Moderate confidence 0.85 with standard rule behavior

#### https://vuejs.org/
- [medium] no-footer-landmark (conf=0.85, sev=minor): Likely — Moderate confidence 0.85 with standard rule behavior
- [medium] landmark-roles (conf=0.85, sev=serious): Likely — Moderate confidence 0.85 with standard rule behavior
- [low] short-link-text (conf=0.5, sev=minor): False Positive — Low confidence 0.50
- [other] unsafe-external-link (conf=0.85, sev=moderate): Likely — Moderate confidence 0.85 with standard rule behavior
- [other] link-purpose (conf=0.85, sev=moderate): Likely — Moderate confidence 0.85 with standard rule behavior

#### https://www.spacejam.com/1996/

## 5. CSP / Engine Reliability
- https://example.com/
  - Possible CSP/axe suppression: Deep unusually close to Fast or too low
- https://www.w3.org/WAI/
  - Possible CSP/axe suppression: Deep unusually close to Fast or too low
- https://www.spacejam.com/1996/
  - Engine coverage violation: Max mode missing axe-core

## 6. Key Insights
### Most Common Sampled Issue Types
- link-purpose: 3
- unsafe-external-link: 3
- no-nav-landmark: 2
- region: 2
- no-footer-landmark: 2
- div-itis-missing-semantics: 2
- color-contrast: 2
- heading-order: 2
- svg-no-accessible-name: 2
- short-link-text: 2

### Reliable Issue Types (sampled)
- link-purpose
- no-nav-landmark
- region
- no-footer-landmark
- color-contrast
- heading-order
- svg-no-accessible-name
- no-header-landmark

### Noisy Issue Types (sampled false positives)
- unsafe-external-link
- short-link-text
- landmark-one-main
- div-itis-missing-semantics
- landmark-unique
- timeout-no-warning

## 7. Recommendations
- Downgrade confidence impact for repeatedly noisy cognitive/readability rules in dashboards.
- Keep Fast mode static+heuristic only and explicitly expose this in UI labels.
- For Deep/Max low-growth anomalies, trigger a UI warning: 'Possible CSP/blocked render reduced coverage'.
- Add a per-site reproducibility check in CI (rerun one pilot site daily across all modes).
- In results UI, expose engines actually executed vs planned engines to make CSP failures obvious.
