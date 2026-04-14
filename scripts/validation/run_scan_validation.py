import argparse
import asyncio
import json
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.audit.scan_mode_runner import run_scan_mode_audit
from app.routers.dashboard_api import _normalize_site_scan_result, _resolve_site_scan_page_budget
from app.services.audit_runner import run_audit


SITES: list[dict[str, Any]] = [
    {"url": "https://example.com/", "category": ["static", "accessibility-good"]},
    {"url": "https://www.iana.org/domains/reserved", "category": ["static"]},
    {"url": "https://www.w3.org/WAI/", "category": ["static", "accessibility-good"]},
    {"url": "https://www.gov.uk/", "category": ["static", "accessibility-good"]},
    {"url": "https://www.python.org/", "category": ["static"]},
    {"url": "https://developer.mozilla.org/en-US/", "category": ["csp-heavy"]},
    {"url": "https://react.dev/", "category": ["spa", "react"]},
    {"url": "https://nextjs.org/", "category": ["spa", "react", "csp-heavy"]},
    {"url": "https://vuejs.org/", "category": ["spa"]},
    {"url": "https://www.spacejam.com/1996/", "category": ["static", "accessibility-poor"]},
]

RELIABLE_RULES = {
    "button-name",
    "image-alt",
    "empty-link",
    "form-label",
    "color-contrast",
    "heading-order",
    "label",
    "input-image-alt",
    "html-has-lang",
    "meta-viewport",
}

NOISY_RULES = {
    "readability",
    "nav-complexity",
    "cognitive-overload",
    "content-density",
    "layout-instability",
}


@dataclass
class ModeMetrics:
    mode: str
    pages_scanned: int
    total_issues: int
    issue_types_count: int
    scan_time_seconds: float
    engines_used: list[str]
    degraded_mode: bool
    degraded_reason: str | None
    has_axe: bool
    raw: dict[str, Any]



def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default



def _i(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default



def _confidence(issue: dict[str, Any]) -> float:
    return _f(issue.get("confidence"), 0.0)



def _bucket(conf: float) -> str:
    if conf >= 0.9:
        return "high"
    if 0.7 <= conf <= 0.85:
        return "medium"
    if conf < 0.6:
        return "low"
    return "other"



def _manual_verdict(issue: dict[str, Any]) -> tuple[str, str]:
    rule_id = str(issue.get("rule_id") or "unknown")
    severity = str(issue.get("severity") or "").lower()
    conf = _confidence(issue)
    source_count = len(set(issue.get("confidence_sources") or []))

    if conf >= 0.92 and rule_id in RELIABLE_RULES:
        return "Valid", f"{rule_id} is high-signal and confidence is {conf:.2f}"

    if rule_id in NOISY_RULES:
        if conf < 0.7:
            return "False Positive", f"{rule_id} is historically noisy and confidence is {conf:.2f}"
        return "Likely", f"{rule_id} can be noisy, but confidence is {conf:.2f}"

    if severity == "critical" and conf >= 0.8:
        return "Valid", f"Critical severity with confidence {conf:.2f}"

    if source_count >= 2 and conf >= 0.75:
        return "Likely", f"Multiple corroborating sources ({source_count})"

    if conf < 0.6:
        return "False Positive", f"Low confidence {conf:.2f}"

    return "Likely", f"Moderate confidence {conf:.2f} with standard rule behavior"



def _pick_issue_samples(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    high = sorted((i for i in issues if _confidence(i) >= 0.9), key=_confidence, reverse=True)
    medium = sorted((i for i in issues if 0.7 <= _confidence(i) <= 0.85), key=_confidence, reverse=True)
    low = sorted((i for i in issues if _confidence(i) < 0.6), key=_confidence)

    picked: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()

    def add_from(pool: list[dict[str, Any]], count: int) -> None:
        for issue in pool:
            if len([p for p in picked if p.get("_bucket") == issue.get("_bucket")]) >= count:
                continue
            key = (str(issue.get("rule_id") or ""), str(issue.get("selector") or ""))
            if key in seen_keys:
                continue
            picked.append(issue)
            seen_keys.add(key)
            if len([p for p in picked if p.get("_bucket") == issue.get("_bucket")]) >= count:
                break

    def tag(pool: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
        tagged = []
        for issue in pool:
            item = dict(issue)
            item["_bucket"] = label
            tagged.append(item)
        return tagged

    high_t = tag(high, "high")
    medium_t = tag(medium, "medium")
    low_t = tag(low, "low")

    add_from(high_t, 2)
    add_from(medium_t, 2)
    add_from(low_t, 1)

    # Backfill if any bucket is sparse.
    if len(picked) < 5:
        backfill = tag(sorted(issues, key=_confidence, reverse=True), "other")
        for issue in backfill:
            key = (str(issue.get("rule_id") or ""), str(issue.get("selector") or ""))
            if key in seen_keys:
                continue
            picked.append(issue)
            seen_keys.add(key)
            if len(picked) >= 5:
                break

    return picked[:5]



def _to_mode_metrics(mode: str, result: dict[str, Any]) -> ModeMetrics:
    pages_scanned = _i(result.get("pages_scanned") or result.get("pages_audited") or 1, 1)
    total_issues = _i(result.get("total_issues"), 0)
    issue_types_count = _i(result.get("issue_types_count") or len(result.get("issues") or []), 0)
    scan_time_seconds = _f(result.get("scan_time_seconds"), 0.0)
    engines_used = [str(x) for x in (result.get("engines_used") or [])]
    degraded_mode = bool(result.get("degraded_mode"))
    degraded_reason = str(result.get("degraded_reason") or result.get("degradation_reason") or "") or None
    has_axe = "axe-core" in engines_used

    return ModeMetrics(
        mode=mode,
        pages_scanned=pages_scanned,
        total_issues=total_issues,
        issue_types_count=issue_types_count,
        scan_time_seconds=scan_time_seconds,
        engines_used=engines_used,
        degraded_mode=degraded_mode,
        degraded_reason=degraded_reason,
        has_axe=has_axe,
        raw=result,
    )


async def _run_fast(url: str) -> ModeMetrics:
    started = time.perf_counter()
    result = await run_audit(
        url=url,
        scan_mode="fast",
        max_pages=1,
        enable_enrichment=False,
        use_cache=False,
    )
    result["scan_time_seconds"] = round(time.perf_counter() - started, 2)
    return _to_mode_metrics("fast", result)


async def _run_site_mode(url: str, mode: str) -> ModeMetrics:
    started = time.perf_counter()
    payload = await run_scan_mode_audit(
        seed_url=url,
        scan_mode=mode,
        max_pages=_resolve_site_scan_page_budget(mode),
    )
    elapsed = time.perf_counter() - started
    result = _normalize_site_scan_result(payload, mode, elapsed)

    # Mirror production single-page fallback behavior used by dashboard scans.
    if _i(result.get("pages_scanned"), 1) <= 1:
        direct_result = await run_audit(
            url=url,
            scan_mode=mode,
            max_pages=1,
            enable_enrichment=False,
            use_cache=False,
        )
        if _i(direct_result.get("total_issues"), 0) > _i(result.get("total_issues"), 0):
            result = direct_result
            result["_single_page_fallback_used"] = True

    result["scan_time_seconds"] = round(elapsed, 2)
    return _to_mode_metrics(mode, result)


def _timeout_metrics(mode: str, url: str, reason: str) -> ModeMetrics:
    payload = {
        "url": url,
        "scan_mode": mode,
        "pages_scanned": 0,
        "total_issues": 0,
        "issue_types_count": 0,
        "scan_time_seconds": 0.0,
        "engines_used": [],
        "degraded_mode": True,
        "degraded_reason": reason,
        "issues": [],
        "summary": reason,
    }
    return _to_mode_metrics(mode, payload)


async def _run_mode_with_timeout(
    *,
    mode: str,
    url: str,
    timeout_seconds: int,
) -> ModeMetrics:
    try:
        if mode == "fast":
            return await asyncio.wait_for(_run_fast(url), timeout=float(timeout_seconds))
        return await asyncio.wait_for(_run_site_mode(url, mode), timeout=float(timeout_seconds))
    except asyncio.TimeoutError:
        return _timeout_metrics(mode, url, f"timeout_{mode}_{timeout_seconds}s")
    except Exception as exc:
        return _timeout_metrics(mode, url, f"exception_{mode}_{type(exc).__name__}")


async def run_site(
    url: str,
    category: list[str],
    *,
    fast_timeout_seconds: int,
    deep_timeout_seconds: int,
    max_timeout_seconds: int,
) -> dict[str, Any]:
    print(f"[SITE] {url} categories={','.join(category)}")

    fast = await _run_mode_with_timeout(mode="fast", url=url, timeout_seconds=fast_timeout_seconds)
    print(f"  [FAST] issues={fast.total_issues} pages={fast.pages_scanned} time={fast.scan_time_seconds}s")

    deep = await _run_mode_with_timeout(mode="deep", url=url, timeout_seconds=deep_timeout_seconds)
    print(f"  [DEEP] issues={deep.total_issues} pages={deep.pages_scanned} time={deep.scan_time_seconds}s axe={deep.has_axe}")

    max_mode = await _run_mode_with_timeout(mode="max", url=url, timeout_seconds=max_timeout_seconds)
    print(f"  [MAX]  issues={max_mode.total_issues} pages={max_mode.pages_scanned} time={max_mode.scan_time_seconds}s axe={max_mode.has_axe}")

    anomalies: list[str] = []

    scaling_ok = fast.total_issues < deep.total_issues <= max_mode.total_issues
    if not scaling_ok:
        anomalies.append("Scaling violation: expected Fast < Deep <= Max")

    growth_ok = deep.total_issues >= (2 * max(1, fast.total_issues)) and max_mode.total_issues >= deep.total_issues
    if not growth_ok:
        anomalies.append("Issue growth violation: expected Deep >= 2x Fast and Max >= Deep")

    if deep.total_issues <= 20 or deep.total_issues <= max(fast.total_issues + 5, int(fast.total_issues * 1.2)):
        anomalies.append("Possible CSP/axe suppression: Deep unusually close to Fast or too low")

    if "axe-core" in fast.engines_used:
        anomalies.append("Engine coverage violation: Fast mode should not include axe-core")

    if not deep.has_axe:
        anomalies.append("Engine coverage violation: Deep mode missing axe-core")

    if not max_mode.has_axe:
        anomalies.append("Engine coverage violation: Max mode missing axe-core")

    sampled = _pick_issue_samples(max_mode.raw.get("issues") or [])
    reviewed_samples: list[dict[str, Any]] = []
    for issue in sampled:
        verdict, rationale = _manual_verdict(issue)
        reviewed_samples.append(
            {
                "rule_id": issue.get("rule_id"),
                "severity": issue.get("severity"),
                "confidence": round(_confidence(issue), 4),
                "selector": issue.get("selector"),
                "description": issue.get("description"),
                "bucket": issue.get("_bucket") or _bucket(_confidence(issue)),
                "verdict": verdict,
                "rationale": rationale,
            }
        )

    return {
        "url": url,
        "category": category,
        "fast": fast.__dict__,
        "deep": deep.__dict__,
        "max": max_mode.__dict__,
        "scaling_ok": scaling_ok,
        "growth_ok": growth_ok,
        "anomalies": anomalies,
        "reviewed_samples": reviewed_samples,
    }



def _overall_accuracy(samples: list[dict[str, Any]]) -> float:
    if not samples:
        return 0.0
    good = sum(1 for s in samples if s.get("verdict") in {"Valid", "Likely"})
    return round((good / len(samples)) * 100.0, 1)



def _bucket_accuracy(samples: list[dict[str, Any]]) -> dict[str, float]:
    grouped: dict[str, list[dict[str, Any]]] = {"high": [], "medium": [], "low": []}
    for sample in samples:
        b = str(sample.get("bucket") or "other")
        if b in grouped:
            grouped[b].append(sample)

    out: dict[str, float] = {}
    for bucket_name, rows in grouped.items():
        if not rows:
            out[bucket_name] = 0.0
            continue
        good = sum(1 for row in rows if row.get("verdict") in {"Valid", "Likely"})
        out[bucket_name] = round((good / len(rows)) * 100.0, 1)
    return out



def _mode_avg(site_rows: list[dict[str, Any]], mode: str, field: str) -> float:
    vals = [_f(row.get(mode, {}).get(field), 0.0) for row in site_rows if row.get(mode)]
    if not vals:
        return 0.0
    return round(statistics.mean(vals), 2)



def _build_report(results: list[dict[str, Any]], output_md: Path) -> None:
    all_samples = [sample for row in results for sample in row.get("reviewed_samples", [])]

    high_med_low = _bucket_accuracy(all_samples)
    overall_accuracy = _overall_accuracy(all_samples)

    scaling_ok_all = all(row.get("scaling_ok") for row in results)
    growth_ok_all = all(row.get("growth_ok") for row in results)

    deep_axe_ok = all(bool(row.get("deep", {}).get("has_axe")) for row in results)
    max_axe_ok = all(bool(row.get("max", {}).get("has_axe")) for row in results)

    csp_flags = [
        {"url": row.get("url"), "anomalies": [a for a in row.get("anomalies", []) if "CSP" in a or "axe" in a.lower()]}
        for row in results
        if any("CSP" in a or "axe" in a.lower() for a in row.get("anomalies", []))
    ]

    rule_counts = Counter(sample.get("rule_id") or "unknown" for sample in all_samples)
    fp_counts = Counter(sample.get("rule_id") or "unknown" for sample in all_samples if sample.get("verdict") == "False Positive")

    reliable_rules = [rule for rule, count in rule_counts.most_common() if fp_counts.get(rule, 0) == 0][:8]
    noisy_rules = [rule for rule, count in fp_counts.most_common(8)]

    valid_system = (
        scaling_ok_all
        and growth_ok_all
        and deep_axe_ok
        and max_axe_ok
        and high_med_low.get("high", 0.0) >= 80.0
        and len(csp_flags) <= 2
    )

    verdict = "VALID" if valid_system else "PARTIALLY VALID / NEEDS TUNING"

    lines: list[str] = []
    lines.append("# Scan Validation Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append("## 1. Summary")
    lines.append(f"- Total sites tested: {len(results)}")
    lines.append(f"- Overall sampled issue accuracy estimate (Valid+Likely): {overall_accuracy}%")
    lines.append(f"- System reliability verdict: **{verdict}**")
    lines.append(f"- Scaling consistency (Fast < Deep <= Max): {'PASS' if scaling_ok_all else 'FAIL'}")
    lines.append(f"- Growth consistency (Deep >= 2x Fast and Max >= Deep): {'PASS' if growth_ok_all else 'FAIL'}")
    lines.append(f"- Axe coverage reliability (Deep/Max): {'PASS' if (deep_axe_ok and max_axe_ok) else 'FAIL'}")
    lines.append("")

    lines.append("## 2. Mode Comparison Table")
    lines.append("| Site | Fast Issues | Deep Issues | Max Issues | Scaling OK |")
    lines.append("| ---- | ----------- | ----------- | ---------- | ---------- |")
    for row in results:
        lines.append(
            f"| {row['url']} | {row['fast']['total_issues']} | {row['deep']['total_issues']} | {row['max']['total_issues']} | {'YES' if row['scaling_ok'] else 'NO'} |"
        )
    lines.append("")

    lines.append("## 3. Performance Metrics")
    lines.append(f"- Avg Fast scan time (s): {_mode_avg(results, 'fast', 'scan_time_seconds')}")
    lines.append(f"- Avg Deep scan time (s): {_mode_avg(results, 'deep', 'scan_time_seconds')}")
    lines.append(f"- Avg Max scan time (s): {_mode_avg(results, 'max', 'scan_time_seconds')}")
    lines.append(f"- Avg Fast pages scanned: {_mode_avg(results, 'fast', 'pages_scanned')}")
    lines.append(f"- Avg Deep pages scanned: {_mode_avg(results, 'deep', 'pages_scanned')}")
    lines.append(f"- Avg Max pages scanned: {_mode_avg(results, 'max', 'pages_scanned')}")
    lines.append("")

    lines.append("## 4. False Positive Analysis")
    lines.append(f"- High confidence accuracy: {high_med_low.get('high', 0.0)}%")
    lines.append(f"- Medium confidence accuracy: {high_med_low.get('medium', 0.0)}%")
    lines.append(f"- Low confidence accuracy: {high_med_low.get('low', 0.0)}%")
    lines.append("")
    lines.append("### Sampled Issue Reviews")
    for row in results:
        lines.append(f"#### {row['url']}")
        for sample in row.get("reviewed_samples", []):
            lines.append(
                "- "
                + f"[{sample['bucket']}] {sample['rule_id']} (conf={sample['confidence']}, sev={sample['severity']}): "
                + f"{sample['verdict']} — {sample['rationale']}"
            )
        lines.append("")

    lines.append("## 5. CSP / Engine Reliability")
    if not csp_flags:
        lines.append("- No major CSP/axe reliability anomalies were detected by the configured checks.")
    else:
        for item in csp_flags:
            lines.append(f"- {item['url']}")
            for anomaly in item.get("anomalies", []):
                lines.append(f"  - {anomaly}")
    lines.append("")

    lines.append("## 6. Key Insights")
    lines.append("### Most Common Sampled Issue Types")
    for rule, count in rule_counts.most_common(10):
        lines.append(f"- {rule}: {count}")
    lines.append("")
    lines.append("### Reliable Issue Types (sampled)")
    if reliable_rules:
        for rule in reliable_rules:
            lines.append(f"- {rule}")
    else:
        lines.append("- No strong reliable set emerged from sampled issues")
    lines.append("")
    lines.append("### Noisy Issue Types (sampled false positives)")
    if noisy_rules:
        for rule in noisy_rules:
            lines.append(f"- {rule}")
    else:
        lines.append("- No strongly noisy issue type emerged in sampled set")
    lines.append("")

    lines.append("## 7. Recommendations")
    lines.append("- Downgrade confidence impact for repeatedly noisy cognitive/readability rules in dashboards.")
    lines.append("- Keep Fast mode static+heuristic only and explicitly expose this in UI labels.")
    lines.append("- For Deep/Max low-growth anomalies, trigger a UI warning: 'Possible CSP/blocked render reduced coverage'.")
    lines.append("- Add a per-site reproducibility check in CI (rerun one pilot site daily across all modes).")
    lines.append("- In results UI, expose engines actually executed vs planned engines to make CSP failures obvious.")
    lines.append("")

    output_md.write_text("\n".join(lines), encoding="utf-8")


async def run_validation(
    limit_sites: int | None = None,
    *,
    fast_timeout_seconds: int,
    deep_timeout_seconds: int,
    max_timeout_seconds: int,
) -> dict[str, Any]:
    sites = SITES[:limit_sites] if limit_sites else SITES

    # Step 1: pilot single-site run for pipeline validation.
    pilot_site = sites[0]
    print(f"[PILOT] Running initial pipeline check on {pilot_site['url']}")
    pilot_result = await run_site(
        pilot_site["url"],
        pilot_site["category"],
        fast_timeout_seconds=fast_timeout_seconds,
        deep_timeout_seconds=deep_timeout_seconds,
        max_timeout_seconds=max_timeout_seconds,
    )
    print(f"[PILOT] Completed with anomalies={len(pilot_result.get('anomalies', []))}")

    # Step 2: full run.
    all_results: list[dict[str, Any]] = [pilot_result]
    for site in sites[1:]:
        result = await run_site(
            site["url"],
            site["category"],
            fast_timeout_seconds=fast_timeout_seconds,
            deep_timeout_seconds=deep_timeout_seconds,
            max_timeout_seconds=max_timeout_seconds,
        )
        all_results.append(result)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "site_count": len(all_results),
        "results": all_results,
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run BEACON scan validation across Fast/Deep/Max modes.")
    parser.add_argument("--limit-sites", type=int, default=None, help="Optional limit for quick runs.")
    parser.add_argument("--fast-timeout", type=int, default=120, help="Timeout in seconds for Fast mode per site.")
    parser.add_argument("--deep-timeout", type=int, default=300, help="Timeout in seconds for Deep mode per site.")
    parser.add_argument("--max-timeout", type=int, default=480, help="Timeout in seconds for Max mode per site.")
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("scan_validation_report.md"),
        help="Path to write markdown report.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("scripts/validation/scan_validation_results.json"),
        help="Path to write raw JSON results.",
    )
    args = parser.parse_args()

    payload = asyncio.run(
        run_validation(
            limit_sites=args.limit_sites,
            fast_timeout_seconds=int(args.fast_timeout),
            deep_timeout_seconds=int(args.deep_timeout),
            max_timeout_seconds=int(args.max_timeout),
        )
    )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    _build_report(payload["results"], args.output_md)

    print(f"[DONE] Wrote JSON: {args.output_json}")
    print(f"[DONE] Wrote report: {args.output_md}")


if __name__ == "__main__":
    main()
