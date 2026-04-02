"""
Verification script for the 5 pipeline integrity fixes.
Tests: imports, duplicate removal, cache key isolation, counter lifecycle, strict semantics.
"""
import sys
import os
import asyncio

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} -- {detail}")
        failed += 1

print("=" * 60)
print("BEACON Pipeline Integrity Verification")
print("=" * 60)

# ── Test 1: All imports succeed ─────────────────────────────
print("\n1. Import checks:")
try:
    import app.config
    check("app.config imports", True)
except Exception as e:
    check("app.config imports", False, str(e))

try:
    import app.services.page_cache
    check("app.services.page_cache imports", True)
except Exception as e:
    check("app.services.page_cache imports", False, str(e))

try:
    import app.services.audit_runner
    check("app.services.audit_runner imports", True)
except Exception as e:
    check("app.services.audit_runner imports", False, str(e))

try:
    import app.services.confidence
    check("app.services.confidence imports", True)
except Exception as e:
    check("app.services.confidence imports", False, str(e))

# ── Test 2: No duplicate strict profile ─────────────────────
print("\n2. Duplicate strict profile (Fix 3):")
from app.config import PRECISION_PROFILES
strict = PRECISION_PROFILES.get("strict")
check("strict profile exists", strict is not None)
check("strict has NO exclude_rules", "exclude_rules" not in strict,
      f"Found exclude_rules: {strict.get('exclude_rules')}")
check("strict min_confidence is 0.75", strict.get("min_confidence") == 0.75)

# ── Test 3: Cache key isolation by precision_profile ────────
print("\n3. Cache key isolation (Fix 2):")
from app.services.page_cache import get_url_hash, get_dom_hash

h_balanced = get_url_hash("http://example.com", "fast", "balanced")
h_strict   = get_url_hash("http://example.com", "fast", "strict")
check("URL hash differs by profile", h_balanced != h_strict,
      f"balanced={h_balanced}, strict={h_strict}")

d_balanced = get_dom_hash("<html><body>test</body></html>", "fast", "balanced")
d_strict   = get_dom_hash("<html><body>test</body></html>", "fast", "strict")
check("DOM hash differs by profile", d_balanced != d_strict,
      f"balanced={d_balanced}, strict={d_strict}")

# Backwards compat: default param should match explicit "balanced"
h_default = get_url_hash("http://example.com", "fast")
check("Default profile matches 'balanced'", h_default == h_balanced)

# ── Test 4: Counter lifecycle (Fix 1) ───────────────────────
print("\n4. Counter lifecycle (Fix 1):")
from app.services.audit_runner import _active_audits, run_audit

async def test_counter_on_failed_fetch():
    """Three failed fetches should NOT leak the counter."""
    import app.services.audit_runner as ar
    ar._active_audits = 0  # reset

    for i in range(3):
        result = await run_audit(
            f"http://this-url-will-never-resolve-{i}.invalid",
            scan_mode="fast",
            precision_profile="balanced",
            enable_enrichment=False,
            enable_cognitive=False,
        )

    final = ar._active_audits
    return final

final_count = asyncio.run(test_counter_on_failed_fetch())
check("Counter returns to 0 after 3 failed fetches", final_count == 0,
      f"Counter leaked to {final_count}")

# ── Test 5: Strict profile not in adaptive threshold list ───
print("\n5. Strict profile semantics (Fix 4):")
import inspect
source = inspect.getsource(app.services.audit_runner._apply_precision_profile)
# The adaptive threshold block should NOT include "strict"
# Find the line with the adaptive check
adaptive_line = [l for l in source.split("\n") if "Adaptive thresholds" in l]
if adaptive_line:
    check("'strict' NOT in adaptive threshold list",
          '"strict"' not in adaptive_line[0],
          f"Found 'strict' in: {adaptive_line[0].strip()}")
else:
    check("Found adaptive threshold line", False, "Could not find adaptive threshold comment")

# ── Test 6: No duplicate CACHE_STATS ───────────────────────
print("\n6. Duplicate config definitions (Fix 5):")
import ast
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "config.py")
with open(config_path, "r", encoding="utf-8") as f:
    config_source = f.read()

# Count top-level assignments of CACHE_STATS
cache_stats_count = config_source.count("CACHE_STATS")
# Should appear exactly twice: the dict definition + the type hint line
# Actually: one dict definition. Let's count "CACHE_STATS: dict" or "CACHE_STATS ="
cache_stats_defs = [l.strip() for l in config_source.split("\n")
                    if l.strip().startswith("CACHE_STATS")]
check(f"CACHE_STATS defined once (found {len(cache_stats_defs)})",
      len(cache_stats_defs) == 1,
      f"Definitions: {cache_stats_defs}")

user_impact_defs = [l.strip() for l in config_source.split("\n")
                    if l.strip().startswith("USER_IMPACT_SCORES")]
check(f"USER_IMPACT_SCORES defined once (found {len(user_impact_defs)})",
      len(user_impact_defs) == 1,
      f"Definitions: {user_impact_defs}")

impact_summary_defs = [l.strip() for l in config_source.split("\n")
                       if l.strip().startswith("IMPACT_SUMMARIES")]
check(f"IMPACT_SUMMARIES defined once (found {len(impact_summary_defs)})",
      len(impact_summary_defs) == 1,
      f"Definitions: {impact_summary_defs}")

# ── Summary ─────────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL CHECKS PASSED ✓")
else:
    print(f"WARNING: {failed} check(s) failed!")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
