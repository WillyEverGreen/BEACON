#!/usr/bin/env python3
"""
Decide which relaxed rules to keep using delta TP vs FP.

Decision rule:
- keep if delta_tp > delta_fp (or stricter: delta_tp >= ratio * delta_fp)

Usage:
python evaluation/rule_recovery_decision.py \
  --baseline evaluation/rule_level_metrics_strict_full.json \
  --candidate evaluation/rule_level_metrics_balanced_full.json \
  --safe-rules text-spacing video-transcript semantic-html link-purpose aria-valid-attr-value \
  --ratio 2.0 \
  --out evaluation/rule_recovery_decision.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rule recovery decision via TP/FP deltas")
    parser.add_argument("--baseline", required=True, help="Rule-level metrics JSON for strict baseline")
    parser.add_argument("--candidate", required=True, help="Rule-level metrics JSON for relaxed candidate")
    parser.add_argument("--safe-rules", nargs="*", default=[], help="Rules allowed for recovery analysis")
    parser.add_argument("--ratio", type=float, default=2.0, help="Keep if delta_tp >= ratio * delta_fp")
    parser.add_argument("--out", required=True, help="Output report path")
    args = parser.parse_args()

    baseline = _load(Path(args.baseline)).get("per_rule", {})
    candidate = _load(Path(args.candidate)).get("per_rule", {})

    rule_ids = sorted(set(baseline) | set(candidate))
    if args.safe_rules:
        rule_ids = [r for r in rule_ids if r in set(args.safe_rules)]

    keep, reject, neutral = [], [], []

    for r in rule_ids:
        b = baseline.get(r, {})
        c = candidate.get(r, {})
        dtp = int(c.get("tp", 0)) - int(b.get("tp", 0))
        dfp = int(c.get("fp", 0)) - int(b.get("fp", 0))
        dfn = int(c.get("fn", 0)) - int(b.get("fn", 0))

        row = {
            "rule_id": r,
            "baseline": {"tp": int(b.get("tp", 0)), "fp": int(b.get("fp", 0)), "fn": int(b.get("fn", 0))},
            "candidate": {"tp": int(c.get("tp", 0)), "fp": int(c.get("fp", 0)), "fn": int(c.get("fn", 0))},
            "delta": {"tp": dtp, "fp": dfp, "fn": dfn},
        }

        if dtp > 0 and dtp >= args.ratio * max(dfp, 0):
            keep.append(row)
        elif dtp <= 0 and dfp >= 0:
            reject.append(row)
        else:
            neutral.append(row)

    report = {
        "baseline": args.baseline,
        "candidate": args.candidate,
        "ratio": args.ratio,
        "safe_rules": args.safe_rules,
        "keep": keep,
        "reject": reject,
        "neutral": neutral,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=== Rule Recovery Decision ===")
    print(f"Safe rules analyzed: {len(rule_ids)}")
    print(f"Keep: {len(keep)} | Reject: {len(reject)} | Neutral: {len(neutral)}")
    if keep:
        print("Keep rules:")
        for r in keep:
            d = r["delta"]
            print(f"  {r['rule_id']}: ΔTP={d['tp']} ΔFP={d['fp']} ΔFN={d['fn']}")
    print(f"Saved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
