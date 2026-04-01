import json

d = json.load(open("tests/sugarlabs_audit_report.json", "r", encoding="utf-8"))
ds = d["deep_scan"]
issues = ds["issues"]

sev = {}
src = {}
wcag = set()
conf_tiers = {}
rules = set()

for i in issues:
    s = i.get("severity", "?")
    sev[s] = sev.get(s, 0) + 1
    
    cs = ",".join(i.get("confidence_sources", []))
    src[cs] = src.get(cs, 0) + 1
    
    w = i.get("wcag_criterion", "")
    if w:
        wcag.add(w)
    
    t = i.get("confidence_tier", "?")
    conf_tiers[t] = conf_tiers.get(t, 0) + 1
    
    rules.add(i.get("rule_id", ""))

confs = [i.get("confidence", 0) for i in issues]

print("=" * 60)
print("  DEEP SCAN SUMMARY — sugarlabs.org")
print("=" * 60)
print(f"  Score:        {ds['score']}/100")
print(f"  Total Issues: {ds['total_issues']}")
print(f"  Engines:      {', '.join(ds['engines_used'])}")
print(f"  Scan Time:    {ds['scan_time_seconds']}s")
print()
print("  Severity Distribution:")
for s in ["critical", "serious", "moderate", "minor"]:
    c = sev.get(s, 0)
    bar = "█" * min(c, 50)
    print(f"    {s:10s}: {c:3d} {bar}")

print()
print("  Sources:")
for s, c in sorted(src.items(), key=lambda x: -x[1]):
    print(f"    {s:20s}: {c:3d}")

print()
print(f"  WCAG SCs Covered: {len(wcag)}")
print(f"    {', '.join(sorted(wcag))}")

print()
print("  Confidence Tiers:")
for t in ["high", "medium", "low"]:
    print(f"    {t:10s}: {conf_tiers.get(t, 0):3d}")
print(f"  Avg Confidence:   {sum(confs)/len(confs):.3f}")

print()
print(f"  Unique Rule IDs:  {len(rules)}")
for r in sorted(rules):
    count = sum(1 for i in issues if i.get("rule_id") == r)
    print(f"    {r:30s}: {count:3d} findings")

cog = ds.get("cognitive_scores")
if cog and isinstance(cog, dict):
    print()
    print("  Cognitive Scores:")
    for k, v in cog.items():
        if isinstance(v, (int, float)):
            print(f"    {k:30s}: {v}")

# Quality gates
qg = ds.get("quality_gates", {})
print()
print("  Quality Gates:")
print(f"    Runtime:    {qg.get('runtime_actual', '?')}s / {qg.get('runtime_limit', '?')}s {'PASS' if qg.get('runtime_passed') else 'FAIL'}")
print(f"    Pre-dedup:  {qg.get('total_before_dedup', '?')}")
print(f"    Post-dedup: {qg.get('total_after_dedup', '?')}")
if "duplicate_rate" in qg:
    print(f"    Dup Rate:   {qg['duplicate_rate']*100:.1f}% {'PASS' if qg.get('duplicate_rate_passed') else 'FAIL'}")

pt = ds.get("precision_profile_telemetry", {})
if pt:
    print()
    print("  Precision Profile:")
    print(f"    Input:      {pt.get('input_issues', '?')}")
    print(f"    Reported:   {pt.get('reported_issues', '?')}")
    print(f"    Dropped (low conf):   {pt.get('dropped_low_confidence', 0)}")
    print(f"    Dropped (needs rev):  {pt.get('dropped_needs_review', 0)}")
    print(f"    Dropped (contextual): {pt.get('dropped_contextual_single_source', 0)}")
