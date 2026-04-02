import re

with open("README.md", "r", encoding="utf-8") as f:
    text = f.read()

# Clean up broken table chunk using regex
text = re.sub(r"\-\-\-\-\-\|.*?gold standard validated\| \*\*`100/100`\*\* \| tested against expert sites \(gov\.uk, inclusive components\) yielding zero false flags \|\n\n\-\-\-\n\n", "", text, flags=re.IGNORECASE | re.DOTALL)


scoring_section = """
## 🧮 Proprietary Scoring & Prioritization Logic

BEACON doesn't just list 500 errors; it calculates a holistic health score and prioritizes exactly what to fix first.

### 1. The Hollistic Accessibility Score (0-100)
A single noisy rule (e.g., a missing `alt` tag repeated 300 times in a footer) normally instantly drops generic accessibility scores to 0. BEACON uses a **capped penalty model**:
* Each severity level carries a weight (Critical=4, Serious=3, Moderate=2, Minor=1).
* Grouped issues count as a single finding.
* **Per-Rule Cap:** No single rule can reduce the score by more than the `max_penalty_per_rule` threshold. This ensures a site with a single recurring mistake still receives a proportional score, rather than an immediate zero.

### 2. The 5-Variable "Fix-First" Prioritization Engine
BEACON computes a `priority_score` for every issue to generate a Top-5 "Fix First" action plan:
```python
priority_score = impact × frequency × visibility × confidence × effort
```
* **Impact**: Critical issues multiply up.
* **Visibility**: Hard violations (e.g., syntax) > Visual violations > Contextual heuristics.
* **Confidence**: Based on our 5-Signal Confidence Formula (Source + Signal + Agreement + Evidence + User Impact).
* **Effort**: Low-hanging fruit (`effort: low`) gets an immediate 1.2x boost to encourage quick wins.
* ***Guardrail***: Critical and Serious issues are never demoted by effort scaling.

**Impact Projection:** When identifying the top 5 issues, BEACON actively projects the `expected_score_after_fix`, showing developers exactly how many points their score will jump if they merge the suggested fixes.

---

## 🧠 Core Architecture Pipelines
"""

text = text.replace("## 🧠 Core Architecture Pipelines\n", scoring_section)

with open("README.md", "w", encoding="utf-8") as f:
    f.write(text)
