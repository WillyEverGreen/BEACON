import argparse
import asyncio
import ast
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.audit.failure_taxonomy import normalize_reason
from app.crawlers.crawl_orchestrator import CrawlConfig, crawl_site
from app.services.audit_runner import run_audit


LOGGER = logging.getLogger(__name__)
CRAWLER_LOGGER_NAME = "app.crawlers.crawl_orchestrator"

TARGET_SITES: list[dict[str, str]] = [
    {"name": "A11y Project", "url": "https://www.a11yproject.com/"},
    {"name": "GOV.UK", "url": "https://www.gov.uk/"},
    {"name": "MDN", "url": "https://developer.mozilla.org/en-US/"},
    {"name": "Reddit", "url": "https://www.reddit.com/"},
    {"name": "NYTimes", "url": "https://www.nytimes.com/"},
    {"name": "Microsoft", "url": "https://www.microsoft.com/"},
    {"name": "Amazon", "url": "https://www.amazon.com/"},
    {"name": "Etsy", "url": "https://www.etsy.com/"},
    {"name": "Wikipedia", "url": "https://www.wikipedia.org/"},
    {"name": "GitHub", "url": "https://github.com/"},
]

MODES = ("fast", "deep", "max")
MODE_TIMEOUT_S = {
    "fast": 60,
    "deep": 180,
    "max": 420,
}

OUTPUT_PATH = Path("tests/multi_mode_validation_results.json")


class AdaptiveDecisionLogHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.events: list[dict[str, Any]] = []

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        marker = "Adaptive crawl decision:"
        if marker not in message:
            return
        payload_text = message.split(marker, 1)[1].strip()
        try:
            payload = ast.literal_eval(payload_text)
            if isinstance(payload, dict):
                self.events.append(payload)
        except Exception:
            self.events.append({"parse_error": payload_text})


def _status_code(result: dict[str, Any]) -> int | None:
    quality = result.get("quality_gates") or {}
    domain_preflight = quality.get("domain_preflight") or {}
    fetch_reliability = quality.get("fetch_reliability") or {}
    for source in (domain_preflight, fetch_reliability):
        code = source.get("status_code") if isinstance(source, dict) else None
        if isinstance(code, int):
            return code
    return None


def _captcha_or_bot_signal(result: dict[str, Any]) -> bool:
    text = " ".join(
        str(part or "")
        for part in (
            result.get("summary"),
            result.get("degradation_reason"),
            result.get("confidence_note"),
            (result.get("quality_gates") or {}).get("domain_preflight", {}).get("message"),
            (result.get("browser_probe_metadata") or {}).get("error"),
        )
    ).lower()
    return any(token in text for token in ("captcha", "challenge", "bot", "turnstile", "cloudflare"))


def _timeout_signal(result: dict[str, Any]) -> bool:
    text = " ".join(
        str(part or "")
        for part in (
            result.get("degradation_reason"),
            result.get("summary"),
            result.get("confidence_note"),
            (result.get("browser_probe_metadata") or {}).get("error"),
            (result.get("browser_probe_metadata") or {}).get("failure_stage"),
        )
    ).lower()
    return bool(re.search(r"timeout|timed out|navigation timeout", text))


def _browser_evidence(result: dict[str, Any]) -> dict[str, bool]:
    engines = set(result.get("engines_used") or [])
    browser_meta = result.get("browser_probe_metadata") or {}
    quality = result.get("quality_gates") or {}
    max_validation = quality.get("max_mode_validation") or {}
    skipped = set(result.get("skipped_components") or [])

    browser_launched = bool(
        "browser-probe" in engines
        or max_validation.get("playwright_invoked")
        or browser_meta.get("navigation_strategy")
        or browser_meta.get("failure_stage") == "render_navigation"
        or browser_meta.get("error") == "navigation_failed"
    )
    navigation_attempted = bool(
        browser_meta.get("navigation_strategy")
        or browser_meta.get("failure_stage") == "render_navigation"
        or browser_meta.get("error") == "navigation_failed"
        or max_validation.get("playwright_invoked")
    )
    dom_rendered = bool("browser-probe" in engines)
    explicit_failure_logged = bool(
        result.get("degraded_mode")
        and result.get("degraded_reason")
        and (
            browser_meta.get("error")
            or browser_meta.get("failure_stage")
            or "browser_probes" in skipped
            or "navigation" in str(result.get("degradation_reason") or "").lower()
        )
    )

    return {
        "browser_launched": browser_launched,
        "navigation_attempted": navigation_attempted,
        "dom_rendered": dom_rendered,
        "explicit_failure_logged": explicit_failure_logged,
    }


def _site_mode_summary(result: dict[str, Any]) -> dict[str, Any]:
    degraded_mode = bool(result.get("degraded_mode", False))
    raw_reason = result.get("degraded_reason")
    normalized_reason = ""
    if degraded_mode and raw_reason not in (None, "", "None", "null", "NULL"):
        normalized_reason = normalize_reason(raw_reason)

    return {
        "degraded_mode": degraded_mode,
        "degraded_reason": normalized_reason or None,
        "confidence_score": result.get("confidence_score"),
        "score": result.get("score"),
        "engines_used": result.get("engines_used") or [],
        "skipped_components": result.get("skipped_components") or [],
        "total_issues": result.get("total_issues"),
    }


async def _run_adaptive_probe(site_url: str, mode: str) -> dict[str, Any]:
    handler = AdaptiveDecisionLogHandler()
    crawler_logger = logging.getLogger(CRAWLER_LOGGER_NAME)
    old_level = crawler_logger.level
    crawler_logger.addHandler(handler)
    crawler_logger.setLevel(logging.INFO)
    try:
        crawl_result = await crawl_site(
            site_url,
            CrawlConfig(
                max_pages=6,
                max_depth=2,
                timeout_per_page_s=20,
                global_timeout_s=70,
                concurrency=2,
                scan_mode=mode,
            ),
        )
    finally:
        crawler_logger.removeHandler(handler)
        crawler_logger.setLevel(old_level)

    return {
        "events": list(handler.events),
        "crawl_meta": crawl_result.get("crawl_meta") if isinstance(crawl_result, dict) else {},
        "site_failure_profile": crawl_result.get("site_failure_profile") if isinstance(crawl_result, dict) else {},
    }


def _validate_mode_consistency(site_name: str, per_mode: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    fast = per_mode.get("fast", {})
    deep = per_mode.get("deep", {})
    max_mode = per_mode.get("max", {})

    for mode_name, mode_data in per_mode.items():
        if mode_data.get("degraded_mode") and not mode_data.get("degraded_reason"):
            errors.append(f"Mode consistency fail: {site_name} {mode_name} degraded but missing degraded_reason")

    if (
        not fast.get("degraded_mode")
        and deep.get("degraded_mode")
        and deep.get("degraded_reason") == "engine_error"
        and not deep.get("degradation_reason")
    ):
        errors.append(
            f"Mode consistency fail: {site_name} fast succeeded but deep hit engine_error without explicit reason"
        )

    deep_reason = deep.get("degraded_reason")
    max_reason = max_mode.get("degraded_reason")
    if deep.get("degraded_mode") and max_mode.get("degraded_mode"):
        allowed_pair = {"render_timeout", "browser_navigation_failed"}
        if deep_reason != max_reason and {deep_reason, max_reason} != allowed_pair:
            errors.append(
                f"Mode consistency fail: {site_name} deep/max degraded_reason mismatch ({deep_reason} vs {max_reason})"
            )

    return errors


def _validate_single_run(
    site_name: str,
    site_url: str,
    mode: str,
    result: dict[str, Any],
    adaptive_probe: dict[str, Any] | None,
) -> list[str]:
    errors: list[str] = []

    degraded = bool(result.get("degraded_mode", False))
    raw_reason = result.get("degraded_reason")
    reason = ""
    if degraded and raw_reason not in (None, "", "None", "null", "NULL"):
        reason = normalize_reason(raw_reason)
    score = result.get("score")
    confidence_raw = result.get("confidence_score")
    confidence = float(confidence_raw or 0.0)
    status_code = _status_code(result)

    if degraded and not reason:
        errors.append(f"Degradation fail: {site_name} {mode} degraded but degraded_reason is missing")

    if status_code == 429 and reason != "rate_limited":
        errors.append(
            f"Taxonomy fail: {site_name} {mode} HTTP 429 must map to rate_limited, got {reason or 'none'}"
        )

    if (status_code == 403 or _captcha_or_bot_signal(result)) and degraded and reason != "bot_wall":
        errors.append(
            f"Taxonomy fail: {site_name} {mode} bot-wall signal must map to bot_wall, got {reason or 'none'}"
        )

    if _timeout_signal(result) and degraded and reason not in {"render_timeout", "browser_navigation_failed"}:
        errors.append(
            f"Taxonomy fail: {site_name} {mode} timeout signal must map to render_timeout/browser_navigation_failed, got {reason or 'none'}"
        )

    if confidence_raw is None:
        errors.append(f"Confidence fail: {site_name} {mode} missing confidence_score")
    if confidence < 0.30 and score is not None:
        errors.append(
            f"Confidence fail: {site_name} {mode} confidence_score={confidence:.2f} but score is not null"
        )
    if degraded and confidence >= 0.70:
        errors.append(
            f"Confidence fail: {site_name} {mode} degraded run has high confidence_score={confidence:.2f}"
        )
    if (not degraded) and confidence < 0.70:
        errors.append(
            f"Confidence fail: {site_name} {mode} non-degraded run has low confidence_score={confidence:.2f}"
        )

    if mode in {"deep", "max"}:
        if bool(result.get("cache_hit", False)):
            errors.append(f"Browser fail: {site_name} {mode} used page cache instead of browser execution")

        evidence = _browser_evidence(result)
        if not evidence["browser_launched"]:
            errors.append(f"Browser fail: {site_name} {mode} browser did not launch")
        if not evidence["navigation_attempted"]:
            errors.append(f"Browser fail: {site_name} {mode} navigation was not attempted")
        if not (evidence["dom_rendered"] or evidence["explicit_failure_logged"]):
            errors.append(
                f"Browser fail: {site_name} {mode} neither DOM rendered nor explicit browser failure logged"
            )

    engines = set(result.get("engines_used") or [])
    skipped = set(result.get("skipped_components") or [])
    if "browser_probes" in skipped and "browser-probe" in engines:
        errors.append(f"Engine fail: {site_name} {mode} browser_probes marked skipped but browser-probe reported as used")
    if "axe-core" in skipped and "axe-core" in engines:
        errors.append(f"Engine fail: {site_name} {mode} axe-core marked skipped but axe-core reported as used")

    total_issues = int(result.get("total_issues") or 0)
    if total_issues <= 0:
        if not (score is not None and float(score) >= 99.0 and not degraded):
            errors.append(f"Output fail: {site_name} {mode} has zero issues without a valid truly-empty scan signal")

    quality = result.get("quality_gates") or {}
    before = quality.get("total_before_dedup")
    after = quality.get("total_after_dedup")
    if before is None or after is None:
        errors.append(f"Output fail: {site_name} {mode} missing dedup telemetry")
    elif isinstance(before, (int, float)) and isinstance(after, (int, float)) and after > before:
        errors.append(f"Output fail: {site_name} {mode} dedup increased issue count ({after} > {before})")

    if result.get("prioritized_issues") is None:
        errors.append(f"Output fail: {site_name} {mode} missing prioritization output")

    if reason in {"rate_limited", "bot_wall", "csp_blocked", "csp_injection_blocked"}:
        if adaptive_probe is None:
            errors.append(f"Adaptive fail: {site_name} {mode} expected adaptive probe but none was executed")
        else:
            events = adaptive_probe.get("events") or []
            actions = {str(event.get("adaptive_action") or "") for event in events if isinstance(event, dict)}
            crawl_meta = adaptive_probe.get("crawl_meta") or {}
            early_stop_reason = str(crawl_meta.get("early_stop_reason") or "")

            if reason == "rate_limited" and "reduced_concurrency" not in actions:
                errors.append(f"Adaptive fail: {site_name} {mode} rate_limited did not trigger reduced_concurrency")
            if reason == "bot_wall":
                if "stopped_crawl" not in actions and "non_recoverable:bot_wall" not in early_stop_reason:
                    errors.append(f"Adaptive fail: {site_name} {mode} bot_wall did not trigger early stop")
            if reason in {"csp_blocked", "csp_injection_blocked"} and "disabled_browser_engines" not in actions:
                errors.append(f"Adaptive fail: {site_name} {mode} CSP degradation did not trigger static fallback")

    return errors


def _write_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run strict BEACON multi-mode validation across target sites")
    parser.add_argument(
        "--output",
        default=str(OUTPUT_PATH),
        help="Output JSON report path",
    )
    args = parser.parse_args()

    output_path = Path(args.output)

    print("=== BEACON FINAL VALIDATION ACROSS MODES ===")
    started_at = time.time()

    per_site_results: list[dict[str, Any]] = []
    degraded_sites: list[str] = []
    failure_distribution: dict[str, int] = {}
    total_runs = 0
    successful_runs = 0
    adaptive_probe_cache: dict[tuple[str, str], dict[str, Any]] = {}

    for site in TARGET_SITES:
        site_name = site["name"]
        site_url = site["url"]
        print(f"\n--- Testing {site_name}: {site_url} ---")

        site_mode_records: dict[str, dict[str, Any]] = {}

        for mode in MODES:
            print(f"  > Running {mode} mode")
            run_id = f"multi-mode::{site_name.lower().replace(' ', '-')}-{mode}-{int(time.time())}"

            try:
                result = await asyncio.wait_for(
                    run_audit(
                        site_url,
                        scan_mode=mode,
                        precision_profile="balanced",
                        enable_enrichment=False,
                        max_enrich_issues=0,
                        enable_cognitive=True,
                        await_enrichment=False,
                        use_cache=False,
                        run_id=run_id,
                    ),
                    timeout=float(MODE_TIMEOUT_S[mode]),
                )
            except asyncio.TimeoutError:
                fatal_report = {
                    "status": "failed",
                    "fatal_error": {
                        "site": site_name,
                        "url": site_url,
                        "mode": mode,
                        "reason": "run_timeout",
                        "detail": f"run_audit exceeded timeout {MODE_TIMEOUT_S[mode]}s",
                    },
                    "partial_results": per_site_results,
                }
                _write_report(fatal_report, output_path)
                print(
                    f"\n[X] FATAL ERROR on {site_name} [{mode}]: "
                    f"run_audit exceeded timeout {MODE_TIMEOUT_S[mode]}s"
                )
                return 1
            except Exception as exc:
                fatal_report = {
                    "status": "failed",
                    "fatal_error": {
                        "site": site_name,
                        "url": site_url,
                        "mode": mode,
                        "reason": "unhandled_exception",
                        "detail": str(exc),
                    },
                    "partial_results": per_site_results,
                }
                _write_report(fatal_report, output_path)
                print(f"\n[X] FATAL ERROR on {site_name} [{mode}]: unhandled exception: {exc}")
                return 1

            adaptive_probe: dict[str, Any] | None = None
            reason = normalize_reason(result.get("degraded_reason"))
            if reason in {"rate_limited", "bot_wall", "csp_blocked", "csp_injection_blocked"}:
                cache_key = (site_url, mode)
                if cache_key not in adaptive_probe_cache:
                    adaptive_probe_cache[cache_key] = await _run_adaptive_probe(site_url, mode)
                adaptive_probe = adaptive_probe_cache[cache_key]

            check_errors = _validate_single_run(site_name, site_url, mode, result, adaptive_probe)
            if check_errors:
                fatal_report = {
                    "status": "failed",
                    "fatal_error": {
                        "site": site_name,
                        "url": site_url,
                        "mode": mode,
                        "reason": "validation_failed",
                        "errors": check_errors,
                    },
                    "last_result": result,
                    "partial_results": per_site_results,
                }
                _write_report(fatal_report, output_path)
                print(f"\n[X] FATAL ERROR on {site_name} [{mode}]")
                for error in check_errors:
                    print(f"    - {error}")
                return 1

            run_summary = _site_mode_summary(result)
            run_summary["degradation_reason"] = result.get("degradation_reason")
            run_summary["scan_time_seconds"] = result.get("scan_time_seconds")
            site_mode_records[mode] = {
                "summary": run_summary,
                "raw": {
                    "quality_gates": result.get("quality_gates"),
                    "browser_probe_metadata": result.get("browser_probe_metadata"),
                    "preflight_cached": result.get("preflight_cached"),
                    "cache_hit": result.get("cache_hit", False),
                },
            }

            total_runs += 1
            if run_summary["degraded_mode"]:
                failure_reason = run_summary["degraded_reason"] or "unknown"
                failure_distribution[failure_reason] = failure_distribution.get(failure_reason, 0) + 1
            else:
                successful_runs += 1

        consistency_input = {
            mode: {
                **site_mode_records[mode]["summary"],
                "degradation_reason": site_mode_records[mode]["summary"].get("degradation_reason"),
            }
            for mode in MODES
        }
        consistency_errors = _validate_mode_consistency(site_name, consistency_input)
        if consistency_errors:
            fatal_report = {
                "status": "failed",
                "fatal_error": {
                    "site": site_name,
                    "url": site_url,
                    "mode": "cross_mode",
                    "reason": "mode_consistency_failed",
                    "errors": consistency_errors,
                },
                "site_results": site_mode_records,
                "partial_results": per_site_results,
            }
            _write_report(fatal_report, output_path)
            print(f"\n[X] FATAL ERROR on {site_name} [cross_mode]")
            for error in consistency_errors:
                print(f"    - {error}")
            return 1

        if any(site_mode_records[m]["summary"]["degraded_mode"] for m in MODES):
            degraded_sites.append(site_name)

        per_site_results.append(
            {
                "site": site_name,
                "url": site_url,
                "fast": site_mode_records["fast"]["summary"],
                "deep": site_mode_records["deep"]["summary"],
                "max": site_mode_records["max"]["summary"],
            }
        )
        print(f"  [PASS] Validation passed for {site_name}")

    success_rate = (successful_runs / total_runs * 100.0) if total_runs else 0.0
    runtime_seconds = round(time.time() - started_at, 2)

    report = {
        "status": "passed",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runtime_seconds": runtime_seconds,
        "sites": per_site_results,
        "overall": {
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "success_rate": round(success_rate, 1),
            "degraded_sites": degraded_sites,
            "failure_types_distribution": failure_distribution,
        },
    }
    _write_report(report, output_path)

    print("\n========================================")
    print("FINAL RESULT FORMAT")
    print("========================================")
    for site_row in per_site_results:
        print(f"\nSite: {site_row['site']} ({site_row['url']})")
        for mode in MODES:
            mode_row = site_row[mode]
            print(
                f"  {mode.upper():4} | "
                f"score={mode_row['score']} | "
                f"confidence={mode_row['confidence_score']} | "
                f"degraded_reason={mode_row['degraded_reason'] or 'none'}"
            )

    print("\nOVERALL")
    print("========================================")
    print(f"success_rate: {report['overall']['success_rate']}%")
    print(f"degraded_sites: {', '.join(degraded_sites) if degraded_sites else 'none'}")
    print("failure_types_distribution:")
    for reason, count in sorted(failure_distribution.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  - {reason}: {count}")
    print(f"\nReport written to: {output_path.as_posix()}")

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    raise SystemExit(asyncio.run(main()))
