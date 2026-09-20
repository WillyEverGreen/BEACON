🧠 PART 1 — FUTURE IMPROVEMENTS (Phase 1 + Phase 2)

These are not urgent now, but they are your upgrade roadmap after Phase 3.

🔧 PHASE 1 (DETECTION ENGINE) — FUTURE IMPROVEMENTS

You’ve done Group 1–3. What remains:

🚀 1. GROUP 4 (ADVANCED RULES)

These are high-impact, harder problems:

🔥 Focus Areas:
keyboard accessibility (tab flow, traps)
focus management (missing focus states)
modal/dialog accessibility
dynamic content announcements (ARIA live regions)

👉 Why important:

Most tools are weak here
Huge real-world impact
🧠 2. CROSS-ELEMENT LOGIC (VERY POWERFUL)

Example:

label exists BUT not connected correctly
button inside clickable div (nested interaction issues)
form grouping issues

👉 These are not single-element rules

📊 3. RULE PRIORITIZATION SYSTEM

Right now:

all issues treated similarly

Future:

critical > major > minor

Based on:

user impact
WCAG level
interaction importance
🔄 4. DEDUP + PATTERN DETECTION

Instead of:

100 same issues → show 100

Do:

"100 buttons missing label (same pattern)"

👉 This is HUGE for usability

🧪 5. REAL RECALL MEASUREMENT (VERY IMPORTANT)

Replace ACT-only dependency with:

real-world dataset
synthetic dataset
rule coverage metrics

👉 This solves your “recall confusion” permanently

⚙️ PHASE 2 (RELIABILITY & PERFORMANCE) — FUTURE IMPROVEMENTS

You passed Phase 2, but here’s what comes next:

🌐 1. SMART CRAWLING (BIG UPGRADE) — **[IMPLEMENTED]** ✅
- Full site crawling with multi-engine discovery (Sitemap + BFS + DOM SPA Crawler)
- Detects site topology (single_page, thin, deep_uniform, paginated, multi_template)
- Gives site-level intelligence

⚡ 2. ADAPTIVE SCAN MODES — **[IMPLEMENTED]** ✅
- Adaptive budgets, timeouts, and page selection based on classified topology
- Saves time + improves reliability

🧠 3. FAILURE PREDICTION — **[IMPLEMENTED]** ✅
- Lightweight preflight checks test connection health before crawler execution
- Predicts and handles early blocks (e.g. Cloudflare walls) and timeouts

📦 4. CACHING INTELLIGENCE
reuse results across pages
avoid re-scanning identical components

👉 Massive speed boost

🔍 5. DEEP ERROR ANALYSIS — **[IMPLEMENTED]** ✅
- Explicit status and taxonomy classification mapping blocks (bot_wall), timeouts, CSP injections, and page loading states.
- Helps debugging + product quality
