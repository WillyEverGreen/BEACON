import argparse
import asyncio
import csv
import copy
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.audit_runner import run_audit
from app.services.prioritizer import build_scoring_summary


SEVERITY_RANK = {
    "critical": 4,
    "serious": 3,
    "moderate": 2,
    "minor": 1,
}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip()).strip("-").lower()
    return slug or "audit"


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return fallback


def _as_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return fallback


def _first_non_empty(values: list[Any], fallback: str = "") -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return fallback


def _extract_first_sample_node(issue: dict[str, Any]) -> dict[str, Any]:
    sample_nodes = _safe_list(issue.get("sample_nodes"))
    if sample_nodes and isinstance(sample_nodes[0], dict):
        return sample_nodes[0]
    return {}


def _extract_selector(issue: dict[str, Any]) -> str:
    sample = _extract_first_sample_node(issue)
    return _first_non_empty(
        [
            issue.get("selector"),
            issue.get("target"),
            issue.get("css_selector"),
            sample.get("selector"),
            sample.get("target"),
        ]
    )


def _extract_snippet(issue: dict[str, Any]) -> str:
    sample = _extract_first_sample_node(issue)
    return _first_non_empty(
        [
            issue.get("code_snippet"),
            issue.get("snippet"),
            sample.get("snippet"),
            sample.get("html"),
            issue.get("html"),
        ]
    )


def _extract_fix(issue: dict[str, Any]) -> str:
    return _first_non_empty(
        [
            issue.get("suggested_fix"),
            issue.get("recommendation"),
            issue.get("fix"),
            issue.get("explanation", {}).get("fix"),
        ]
    )


def _dedup_summary(result: dict[str, Any], issue_count: int) -> dict[str, Any]:
    quality = _safe_dict(result.get("quality_gates"))
    before = _as_int(quality.get("total_before_dedup"), issue_count)
    after = _as_int(quality.get("total_after_dedup"), issue_count)
    removed = max(0, before - after)
    duplicate_rate = quality.get("duplicate_rate")

    return {
        "before_dedup": before,
        "after_dedup": after,
        "removed_by_dedup": removed,
        "duplicate_rate": _as_float(duplicate_rate, 0.0) if duplicate_rate is not None else None,
        "duplicate_rate_passed": quality.get("duplicate_rate_passed"),
    }


def _wcag_summary(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    for issue in issues:
        criterion = _first_non_empty([issue.get("wcag_criterion")], "unmapped")
        level = _first_non_empty([issue.get("wcag_level")], "unknown")
        rule_id = _first_non_empty([issue.get("rule_id")], "unknown")
        entry = grouped.setdefault(
            criterion,
            {
                "criterion": criterion,
                "count": 0,
                "levels": Counter(),
                "rules": Counter(),
            },
        )
        entry["count"] += 1
        entry["levels"][level] += 1
        entry["rules"][rule_id] += 1

    rows: list[dict[str, Any]] = []
    for entry in grouped.values():
        rows.append(
            {
                "criterion": entry["criterion"],
                "count": entry["count"],
                "levels": dict(entry["levels"]),
                "top_rules": [
                    {"rule_id": rule_id, "count": count}
                    for rule_id, count in entry["rules"].most_common(5)
                ],
            }
        )

    rows.sort(key=lambda row: (-int(row["count"]), str(row["criterion"])))
    return rows


def _group_summary(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for group in groups:
        summary.append(
            {
                "group_id": _first_non_empty([group.get("group_id")], "unknown"),
                "domain": _first_non_empty([group.get("domain")], ""),
                "rule_family": _first_non_empty([group.get("rule_family")], ""),
                "count": _as_int(group.get("count"), 0),
                "worst_severity": _first_non_empty([group.get("worst_severity")], "unknown"),
            }
        )
    summary.sort(key=lambda row: (-int(row["count"]), row["group_id"]))
    return summary


def _rank_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(issue: dict[str, Any]) -> tuple[float, int, int, str]:
        priority = _as_float(issue.get("priority_score"), 0.0)
        severity = str(issue.get("severity") or "moderate").lower()
        severity_rank = SEVERITY_RANK.get(severity, 0)
        affected = _as_int(issue.get("affected_count") or issue.get("count"), 1)
        rule_id = _first_non_empty([issue.get("rule_id")], "unknown")
        return (priority, severity_rank, affected, rule_id)

    return sorted(issues, key=key, reverse=True)


def _flatten_issue(index: int, issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": index,
        "issue_id": _first_non_empty([issue.get("issue_id")], ""),
        "rule_id": _first_non_empty([issue.get("rule_id")], "unknown"),
        "severity": _first_non_empty([issue.get("severity")], "unknown"),
        "domain": _first_non_empty([issue.get("domain")], ""),
        "wcag_criterion": _first_non_empty([issue.get("wcag_criterion")], ""),
        "wcag_level": _first_non_empty([issue.get("wcag_level")], ""),
        "confidence": _as_float(issue.get("confidence"), 0.0),
        "confidence_tier": _first_non_empty([issue.get("confidence_tier")], ""),
        "priority_score": _as_float(issue.get("priority_score"), 0.0),
        "affected_count": _as_int(issue.get("affected_count") or issue.get("count"), 0),
        "group_id": _first_non_empty([issue.get("group_id")], ""),
        "selector": _extract_selector(issue),
        "snippet": _extract_snippet(issue),
        "message": _first_non_empty([issue.get("message")], ""),
        "impact_summary": _first_non_empty([issue.get("impact_summary")], ""),
        "fix_suggestion": _extract_fix(issue),
        "confidence_reason": _first_non_empty([issue.get("confidence_reason")], ""),
        "source": _first_non_empty([issue.get("source"), issue.get("engine")], ""),
    }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "index",
        "issue_id",
        "rule_id",
        "severity",
        "domain",
        "wcag_criterion",
        "wcag_level",
        "confidence",
        "confidence_tier",
        "priority_score",
        "affected_count",
        "group_id",
        "selector",
        "snippet",
        "message",
        "impact_summary",
        "fix_suggestion",
        "confidence_reason",
        "source",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _sanitize_cell(value: Any) -> str:
    text = str(value or "")
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _compute_strict_score_from_all_issues(
    issues: list[dict[str, Any]],
    *,
    degraded_mode: bool,
) -> dict[str, Any]:
    """Compute a conservative score using all reported issues.

    The core score excludes low-confidence issues by design. For operator clarity,
    we re-score with confidence gates neutralized so every reported issue contributes.
    """
    strict_issues = copy.deepcopy(issues)
    for issue in strict_issues:
        issue["confidence"] = max(0.8, _as_float(issue.get("confidence"), 0.0))
        issue["confidence_tier"] = "high"
        issue["report_in_summary"] = True

    strict_summary = build_scoring_summary(strict_issues, degraded_mode=degraded_mode)
    strict_explanation = _safe_dict(strict_summary.get("score_explanation"))
    strict_score = _as_float(strict_summary.get("overall_score"), 100.0)

    return {
        "strict_score": round(strict_score, 1),
        "strict_score_explanation": strict_explanation,
        "strict_scorable_issue_count": _as_int(strict_explanation.get("scorable_issue_count"), len(strict_issues)),
    }


def _shorten(value: Any, max_len: int = 260) -> str:
    text = str(value or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _build_cli_markdown(
    result: dict[str, Any],
    analysis: dict[str, Any],
    top_rows: list[dict[str, Any]],
    bundle_dir: Path,
) -> str:
    lines: list[str] = []
    lines.append("# Detailed Accessibility Audit (CLI)")
    lines.append("")
    lines.append(f"- URL: {result.get('url')}")
    lines.append(f"- Scan mode: {result.get('scan_mode')}")
    lines.append(f"- Precision profile: {result.get('precision_profile')}")
    lines.append(f"- Degraded mode: {result.get('degraded_mode')}")
    lines.append(f"- Degraded reason: {result.get('degraded_reason')}")
    score_model = _safe_dict(analysis.get("score_model"))
    lines.append(f"- Score (calibrated): {result.get('score')} (raw={result.get('score_raw')})")
    lines.append(f"- Score (strict, all issues): {score_model.get('strict_score')}")
    lines.append(f"- Recommended operator score: {score_model.get('operator_score')}")
    lines.append(f"- Confidence: {result.get('confidence_score')} ({result.get('confidence_note')})")
    lines.append(f"- Scan time (s): {result.get('scan_time_seconds')}")
    lines.append("")

    lines.append("## Engine Coverage")
    lines.append("")
    lines.append(f"- Engines used: {', '.join(_safe_list(result.get('engines_used')))}")
    lines.append(f"- Skipped components: {', '.join(_safe_list(result.get('skipped_components')))}")
    lines.append("")

    lines.append("## Score Model")
    lines.append("")
    lines.append(f"- Calibrated score: {score_model.get('calibrated_score')}")
    lines.append(f"- Strict score: {score_model.get('strict_score')}")
    lines.append(f"- Operator score (conservative): {score_model.get('operator_score')}")
    lines.append(f"- Low-confidence excluded count (calibrated): {score_model.get('low_confidence_excluded_count')}")
    lines.append(f"- Low-confidence excluded ratio: {score_model.get('low_confidence_excluded_ratio')}")
    lines.append(f"- Calibrated scorable issue count: {score_model.get('calibrated_scorable_issue_count')}")
    lines.append(f"- Strict scorable issue count: {score_model.get('strict_scorable_issue_count')}")
    lines.append("")

    dedup = _safe_dict(analysis.get("dedup_summary"))
    lines.append("## Deduplication")
    lines.append("")
    lines.append(f"- Before dedup: {dedup.get('before_dedup')}")
    lines.append(f"- After dedup: {dedup.get('after_dedup')}")
    lines.append(f"- Removed by dedup: {dedup.get('removed_by_dedup')}")
    lines.append(f"- Duplicate rate: {dedup.get('duplicate_rate')}")
    lines.append(f"- Duplicate rate gate passed: {dedup.get('duplicate_rate_passed')}")
    lines.append("")

    severity_counts = _safe_dict(analysis.get("severity_counts"))
    lines.append("## Severity Breakdown")
    lines.append("")
    for severity in ("critical", "serious", "moderate", "minor"):
        lines.append(f"- {severity}: {severity_counts.get(severity, 0)}")
    lines.append("")

    lines.append("## WCAG Coverage")
    lines.append("")
    lines.append("| WCAG criterion | Count | Levels |")
    lines.append("|---|---:|---|")
    for row in _safe_list(analysis.get("wcag_summary"))[:30]:
        criterion = _sanitize_cell(row.get("criterion"))
        count = _as_int(row.get("count"), 0)
        levels = _sanitize_cell(json.dumps(_safe_dict(row.get("levels")), ensure_ascii=False))
        lines.append(f"| {criterion} | {count} | {levels} |")
    lines.append("")

    lines.append("## Issue Groups")
    lines.append("")
    lines.append("| Group ID | Domain | Rule family | Count | Worst severity |")
    lines.append("|---|---|---|---:|---|")
    for row in _safe_list(analysis.get("group_summary"))[:40]:
        lines.append(
            "| {group_id} | {domain} | {rule_family} | {count} | {worst_severity} |".format(
                group_id=_sanitize_cell(row.get("group_id")),
                domain=_sanitize_cell(row.get("domain")),
                rule_family=_sanitize_cell(row.get("rule_family")),
                count=_as_int(row.get("count"), 0),
                worst_severity=_sanitize_cell(row.get("worst_severity")),
            )
        )
    lines.append("")

    lines.append("## Top Issues (Priority)")
    lines.append("")
    if not top_rows:
        lines.append("No issues were reported.")
    for row in top_rows:
        lines.append(f"### {row['index']}. {row['rule_id']}")
        lines.append("")
        lines.append(f"- Severity: {row['severity']}")
        lines.append(f"- Domain: {row['domain']}")
        lines.append(f"- WCAG: {row['wcag_criterion']} ({row['wcag_level']})")
        lines.append(f"- Confidence: {row['confidence']} ({row['confidence_tier']})")
        lines.append(f"- Priority score: {row['priority_score']}")
        lines.append(f"- Affected count: {row['affected_count']}")
        lines.append(f"- Selector: {_shorten(row['selector'], 220)}")
        lines.append(f"- Message: {_shorten(row['message'], 280)}")
        lines.append(f"- Suggested fix: {_shorten(row['fix_suggestion'], 320)}")
        snippet = _shorten(row["snippet"], 400)
        if snippet:
            lines.append("")
            lines.append("Snippet:")
            lines.append("```")
            lines.append(snippet)
            lines.append("```")
        lines.append("")

    lines.append("## Artifacts")
    lines.append("")
    lines.append(f"- Bundle directory: {bundle_dir}")
    lines.append("- Raw payload: audit_result.raw.json")
    lines.append("- Engine markdown report: audit_report.engine.md")
    lines.append("- CLI markdown report: audit_report.cli.md")
    lines.append("- Flat issues CSV: issues_flat.csv")
    lines.append("- Group data: issue_groups.json")
    lines.append("- Priority ranking: priority_ranking.json")
    lines.append("- Derived analysis: audit_analysis.json")

    return "\n".join(lines) + "\n"


async def _run_cli(args: argparse.Namespace) -> int:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = args.slug or _slugify(args.url)
    output_root = Path(args.output_dir).expanduser().resolve()
    bundle_dir = output_root / f"{timestamp}_{slug}_{args.scan_mode}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    result = await run_audit(
        url=args.url,
        scan_mode=args.scan_mode,
        max_pages=args.max_pages,
        precision_profile=args.precision_profile,
        enable_enrichment=args.enable_enrichment,
        max_enrich_issues=args.max_enrich_issues,
        enable_cognitive=(not args.disable_cognitive),
        await_enrichment=args.await_enrichment,
        use_cache=args.use_cache,
        run_id=args.run_id,
    )

    issues = [item for item in _safe_list(result.get("issues")) if isinstance(item, dict)]
    groups = [item for item in _safe_list(result.get("groups")) if isinstance(item, dict)]
    ranked_issues = _rank_issues(issues)

    flat_rows = [_flatten_issue(idx + 1, issue) for idx, issue in enumerate(ranked_issues)]
    dedup_summary = _dedup_summary(result, len(issues))
    severity_counts = Counter(str(item.get("severity") or "unknown") for item in issues)
    rule_counts = Counter(_first_non_empty([item.get("rule_id")], "unknown") for item in issues)

    calibrated_score = _as_float(result.get("score"), _as_float(result.get("score_raw"), 100.0))
    score_explanation = _safe_dict(result.get("score_explanation"))
    low_conf_excluded = _as_int(score_explanation.get("low_confidence_excluded_count"), 0)
    calibrated_scorable = _as_int(score_explanation.get("scorable_issue_count"), len(issues))
    low_conf_ratio = round((low_conf_excluded / len(issues)), 3) if issues else 0.0

    strict_score_meta = _compute_strict_score_from_all_issues(
        issues,
        degraded_mode=bool(result.get("degraded_mode", False)),
    )
    strict_score = _as_float(strict_score_meta.get("strict_score"), calibrated_score)
    operator_score = round(min(calibrated_score, strict_score), 1)

    analysis = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "url": result.get("url"),
            "scan_mode": result.get("scan_mode"),
            "precision_profile": result.get("precision_profile"),
            "score": result.get("score"),
            "score_raw": result.get("score_raw"),
            "confidence_score": result.get("confidence_score"),
            "confidence_note": result.get("confidence_note"),
            "degraded_mode": result.get("degraded_mode"),
            "degraded_reason": result.get("degraded_reason"),
            "degradation_reason": result.get("degradation_reason"),
            "scan_time_seconds": result.get("scan_time_seconds"),
            "total_issues": len(issues),
            "total_groups": len(groups),
        },
        "score_model": {
            "calibrated_score": round(calibrated_score, 1),
            "strict_score": round(strict_score, 1),
            "operator_score": operator_score,
            "calibrated_scorable_issue_count": calibrated_scorable,
            "strict_scorable_issue_count": _as_int(strict_score_meta.get("strict_scorable_issue_count"), len(issues)),
            "low_confidence_excluded_count": low_conf_excluded,
            "low_confidence_excluded_ratio": low_conf_ratio,
            "strict_score_explanation": strict_score_meta.get("strict_score_explanation", {}),
        },
        "severity_counts": dict(severity_counts),
        "top_rule_counts": [
            {"rule_id": rule_id, "count": count}
            for rule_id, count in rule_counts.most_common(50)
        ],
        "dedup_summary": dedup_summary,
        "wcag_summary": _wcag_summary(issues),
        "group_summary": _group_summary(groups),
        "pipeline_snapshot": {
            "engines_used": result.get("engines_used"),
            "skipped_components": result.get("skipped_components"),
            "score_explanation": result.get("score_explanation"),
            "quality_gates": result.get("quality_gates"),
            "precision_profile_telemetry": result.get("precision_profile_telemetry"),
            "rule_activity": result.get("rule_activity"),
            "trust": result.get("trust"),
            "browser_probe_metadata": result.get("browser_probe_metadata"),
            "priority_ranking": result.get("priority_ranking"),
            "issue_groupings": result.get("issue_groupings"),
            "top_issue_types": result.get("top_issue_types"),
            "recommendations": result.get("recommendations"),
            "enrichment_status": result.get("enrichment_status"),
            "enrichment_meta": result.get("enrichment_meta"),
        },
    }

    top_n = max(0, args.show_top)
    top_rows = flat_rows[:top_n]

    _write_json(bundle_dir / "audit_result.raw.json", result)
    _write_json(bundle_dir / "audit_analysis.json", analysis)
    _write_json(bundle_dir / "issue_groups.json", groups)
    _write_json(bundle_dir / "priority_ranking.json", result.get("priority_ranking") or [])
    _write_json(bundle_dir / "issues.full.json", issues)
    _write_csv(bundle_dir / "issues_flat.csv", flat_rows)

    engine_markdown = str(result.get("markdown_report") or "")
    (bundle_dir / "audit_report.engine.md").write_text(engine_markdown, encoding="utf-8")

    cli_markdown = _build_cli_markdown(result, analysis, top_rows, bundle_dir)
    (bundle_dir / "audit_report.cli.md").write_text(cli_markdown, encoding="utf-8")

    print("Audit complete.")
    print(f"Bundle: {bundle_dir}")
    print(f"Score (calibrated): {round(calibrated_score, 1)} (raw={result.get('score_raw')})")
    print(f"Score (strict/all issues): {round(strict_score, 1)}")
    print(f"Recommended operator score: {operator_score}")
    print(f"Confidence: {result.get('confidence_score')} ({result.get('confidence_note')})")
    print(f"Degraded: {result.get('degraded_mode')} reason={result.get('degraded_reason')}")
    print(f"Issues: {len(issues)} | Groups: {len(groups)}")
    print(
        "Scoring coverage: calibrated_scorable={calibrated} excluded_low_conf={excluded} ({ratio:.1%})".format(
            calibrated=calibrated_scorable,
            excluded=low_conf_excluded,
            ratio=low_conf_ratio,
        )
    )
    print(
        "Dedup: before={before} after={after} removed={removed}".format(
            before=dedup_summary.get("before_dedup"),
            after=dedup_summary.get("after_dedup"),
            removed=dedup_summary.get("removed_by_dedup"),
        )
    )

    if args.fail_on_degraded and bool(result.get("degraded_mode")):
        print("Fail condition met: degraded_mode=true")
        return 2

    if args.min_confidence is not None:
        confidence = _as_float(result.get("confidence_score"), 0.0)
        if confidence < float(args.min_confidence):
            print(
                f"Fail condition met: confidence_score={confidence:.3f} < min_confidence={args.min_confidence:.3f}"
            )
            return 3

    if args.fail_on_threshold is not None:
        if calibrated_score < float(args.fail_on_threshold):
            print(
                f"Fail condition met: calibrated_score={calibrated_score:.1f} < fail_on_threshold={args.fail_on_threshold:.1f}"
            )
            return 4

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a detailed accessibility audit for any URL and scan mode, then export a full report bundle "
            "(raw JSON, markdown, CSV, dedup/group/WCAG summaries, and pipeline telemetry)."
        )
    )
    parser.add_argument("url", help="Target URL to audit")
    parser.add_argument(
        "--scan-mode",
        choices=["minimal", "fast", "deep", "max"],
        default="deep",
        help="Audit depth and engine coverage",
    )
    parser.add_argument("--precision-profile", default="balanced", help="Precision profile for filtering")
    parser.add_argument("--max-pages", type=int, default=None, help="Optional max pages hint")
    parser.add_argument("--enable-enrichment", action="store_true", help="Enable RAG enrichment")
    parser.add_argument("--await-enrichment", action="store_true", help="Wait for enrichment completion")
    parser.add_argument("--max-enrich-issues", type=int, default=20, help="Max issues to enrich")
    parser.add_argument("--disable-cognitive", action="store_true", help="Disable cognitive checks")
    parser.add_argument("--use-cache", action="store_true", help="Allow cache reads/writes")
    parser.add_argument("--run-id", default=None, help="Optional run identifier")
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "tests" / "artifacts" / "cli_audits"),
        help="Directory where the report bundle is written",
    )
    parser.add_argument("--slug", default=None, help="Optional slug override for bundle folder name")
    parser.add_argument("--show-top", type=int, default=25, help="Top N issues to include in CLI markdown")
    parser.add_argument("--fail-on-degraded", action="store_true", help="Exit non-zero when degraded_mode=true")
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=None,
        help="Exit non-zero if confidence_score is below this threshold",
    )
    parser.add_argument(
        "--fail-on-threshold",
        type=float,
        default=None,
        help="Exit non-zero (exit code 4) if the calibrated accessibility score drops below this threshold value",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(_run_cli(args))
    except KeyboardInterrupt:
        print("Interrupted by user.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
