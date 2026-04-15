import argparse
import ast
import asyncio
import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from curl_cffi import AsyncSession

from app.audit.failure_taxonomy import normalize_reason
from app.crawlers.crawl_orchestrator import CrawlConfig, crawl_site
from app.services.audit_runner import run_audit


LOGGER = logging.getLogger(__name__)
CRAWLER_LOGGER_NAME = "app.crawlers.crawl_orchestrator"


@dataclass
class SiteInput:
    name: str
    url: str
    validation_category: str
    classification_reason: str
    special_assertion: str | None = None


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


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "site"


def _load_sites(path: Path) -> list[SiteInput]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_sites = payload.get("sites", []) if isinstance(payload, dict) else []
    sites: list[SiteInput] = []
    for row in raw_sites:
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or "").strip()
        name = str(row.get("name") or url).strip()
        category = str(row.get("validation_category") or "unknown").strip()
        reason = str(row.get("classification_reason") or "").strip()
        special = str(row.get("special_assertion") or "").strip() or None
        if not url:
            continue
        sites.append(
            SiteInput(
                name=name,
                url=url,
                validation_category=category,
                classification_reason=reason,
                special_assertion=special,
            )
        )
    return sites


async def _capture_http_evidence(site: SiteInput, artifact_dir: Path) -> dict[str, Any]:
    headers_subset: dict[str, str] = {}
    status_code: int | None = None
    artifact_path: str | None = None
    error_text: str | None = None

    try:
        async with AsyncSession(impersonate="chrome", allow_redirects=True) as client:
            response = await client.get(site.url, timeout=25.0)
        status_code = int(response.status_code)

        keep_headers = {
            "content-security-policy",
            "retry-after",
            "server",
            "cf-ray",
            "x-datadome",
            "x-akamai-session-info",
            "x-cache",
        }
        for key, value in dict(response.headers or {}).items():
            lowered = str(key).strip().lower()
            if lowered in keep_headers:
                headers_subset[lowered] = str(value)

        body = response.text or ""
        artifact_file = artifact_dir / f"{_slugify(site.name)}.html"
        artifact_file.write_text(body[:200000], encoding="utf-8", errors="ignore")
        artifact_path = str(artifact_file).replace("\\", "/")
    except Exception as exc:
        error_text = str(exc)

    return {
        "status_code": status_code,
        "headers": headers_subset,
        "artifact_path": artifact_path,
        "error": error_text,
    }


def _validate_site_integrity(site: SiteInput, http_evidence: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not site.validation_category:
        errors.append("missing_validation_category")
    if not site.classification_reason:
        errors.append("missing_classification_reason")
    if http_evidence.get("status_code") is None:
        errors.append("missing_http_status")
    if not http_evidence.get("headers"):
        errors.append("missing_http_headers")
    if not http_evidence.get("artifact_path"):
        errors.append("missing_response_artifact")
    return len(errors) == 0, errors


def _validate_structured_fields(
    max_result: dict[str, Any],
    crawl_result: dict[str, Any],
    adaptive_events: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if "confidence_score" not in max_result:
        errors.append("missing_confidence_score")
    if "degraded_reason" not in max_result:
        errors.append("missing_degraded_reason")

    site_failure_profile = crawl_result.get("site_failure_profile") if isinstance(crawl_result, dict) else None
    if not isinstance(site_failure_profile, dict):
        errors.append("missing_site_failure_profile")
    elif "dominant_failure" not in site_failure_profile:
        errors.append("missing_site_failure_profile.dominant_failure")

    if not adaptive_events:
        errors.append("missing_adaptive_decision_logs")
    else:
        for idx, event in enumerate(adaptive_events):
            if "adaptive_action" not in event:
                errors.append(f"adaptive_event_{idx}_missing_adaptive_action")
            if "trigger" not in event:
                errors.append(f"adaptive_event_{idx}_missing_trigger")

    return len(errors) == 0, errors


def _validate_special_detection(
    site: SiteInput,
    max_result: dict[str, Any],
    crawl_result: dict[str, Any],
    adaptive_events: list[dict[str, Any]],
) -> tuple[bool, str]:
    special = (site.special_assertion or "").strip().lower()
    if not special:
        return True, "not_applicable"

    degraded_reason = normalize_reason(max_result.get("degraded_reason"))
    early_stop = str((crawl_result.get("crawl_meta") or {}).get("early_stop_reason") or "")

    if special == "csp":
        ok = degraded_reason in {"csp_blocked", "csp_injection_blocked"}
        return ok, f"expected_csp_family got={degraded_reason or 'none'}"

    if special == "rate_limited":
        has_slowdown = any(
            str(event.get("adaptive_action") or "") == "reduced_concurrency" for event in adaptive_events
        )
        ok = degraded_reason == "rate_limited" and has_slowdown
        return ok, (
            f"expected rate_limited + reduced_concurrency; "
            f"reason={degraded_reason or 'none'} has_slowdown={has_slowdown}"
        )

    if special == "bot_wall":
        has_stop = any(str(event.get("adaptive_action") or "") == "stopped_crawl" for event in adaptive_events)
        ok = degraded_reason == "bot_wall" and (has_stop or "non_recoverable:bot_wall" in early_stop)
        return ok, (
            f"expected bot_wall + early_stop; reason={degraded_reason or 'none'} "
            f"has_stop={has_stop} early_stop={early_stop or 'none'}"
        )

    return True, "unknown_special_assertion_ignored"


def _validate_adaptive_effect(site: SiteInput, adaptive_events: list[dict[str, Any]]) -> tuple[bool, str]:
    special = (site.special_assertion or "").strip().lower()
    if special == "rate_limited":
        has_effect = any(str(event.get("adaptive_action") or "") == "reduced_concurrency" for event in adaptive_events)
        return has_effect, f"rate_limited adaptive effect observed={has_effect}"

    if special == "csp":
        has_effect = any(
            str(event.get("adaptive_action") or "") == "disabled_browser_engines" for event in adaptive_events
        )
        return has_effect, f"csp adaptive effect observed={has_effect}"

    return True, "not_applicable"


def _validate_confidence_correlation(max_result: dict[str, Any]) -> tuple[bool, str]:
    degraded = bool(max_result.get("degraded_mode", False))
    confidence = float(max_result.get("confidence_score", 0.0) or 0.0)

    if degraded and confidence >= 0.7:
        return False, f"degraded=true but confidence_score={confidence} >= 0.7"
    if (not degraded) and confidence < 0.7:
        return False, f"degraded=false but confidence_score={confidence} < 0.7"

    if confidence < 0.3 and max_result.get("score") is not None:
        return False, "confidence_score<0.3 but score is not null"

    return True, "ok"


async def _run_single_site(site: SiteInput, artifact_dir: Path) -> dict[str, Any]:
    started = time.time()

    http_evidence = await _capture_http_evidence(site, artifact_dir)
    integrity_ok, integrity_errors = _validate_site_integrity(site, http_evidence)

    max_result: dict[str, Any] = {}
    crawl_result: dict[str, Any] = {}
    adaptive_events: list[dict[str, Any]] = []
    runtime_error: str | None = None

    try:
        max_result = await run_audit(
            url=site.url,
            scan_mode="max",
            precision_profile="balanced",
            enable_enrichment=False,
            enable_cognitive=False,
            await_enrichment=False,
            use_cache=False,
            run_id=f"phase17-max::{_slugify(site.name)}::{int(time.time())}",
        )

        handler = AdaptiveDecisionLogHandler()
        crawler_logger = logging.getLogger(CRAWLER_LOGGER_NAME)
        crawler_logger.addHandler(handler)
        old_level = crawler_logger.level
        crawler_logger.setLevel(logging.INFO)
        try:
            crawl_result = await crawl_site(
                site.url,
                CrawlConfig(
                    max_pages=6,
                    max_depth=2,
                    timeout_per_page_s=20,
                    global_timeout_s=70,
                    concurrency=2,
                    await_enrichment=False,
                    scan_mode="max",
                ),
            )
        finally:
            crawler_logger.removeHandler(handler)
            crawler_logger.setLevel(old_level)

        adaptive_events = list(handler.events)
    except Exception as exc:
        runtime_error = str(exc)

    structured_ok, structured_errors = _validate_structured_fields(max_result, crawl_result, adaptive_events)
    special_ok, special_note = _validate_special_detection(site, max_result, crawl_result, adaptive_events)
    adaptive_ok, adaptive_note = _validate_adaptive_effect(site, adaptive_events)
    confidence_ok, confidence_note = _validate_confidence_correlation(max_result)

    duration = round(time.time() - started, 2)

    passed = (
        runtime_error is None
        and integrity_ok
        and structured_ok
        and special_ok
        and adaptive_ok
        and confidence_ok
    )

    return {
        "site": asdict(site),
        "runtime_error": runtime_error,
        "http_evidence": http_evidence,
        "max_result": {
            "degraded_mode": max_result.get("degraded_mode"),
            "degraded_reason": max_result.get("degraded_reason"),
            "confidence_score": max_result.get("confidence_score"),
            "score": max_result.get("score"),
            "scan_time_seconds": max_result.get("scan_time_seconds"),
            "engines_used": max_result.get("engines_used"),
            "summary": max_result.get("summary"),
        },
        "crawl_result": {
            "crawl_status": crawl_result.get("crawl_status") if isinstance(crawl_result, dict) else None,
            "crawl_meta": crawl_result.get("crawl_meta") if isinstance(crawl_result, dict) else {},
            "site_failure_profile": crawl_result.get("site_failure_profile") if isinstance(crawl_result, dict) else {},
        },
        "adaptive_events": adaptive_events,
        "checks": {
            "site_validation_integrity": {"passed": integrity_ok, "errors": integrity_errors},
            "structured_log_validation": {"passed": structured_ok, "errors": structured_errors},
            "special_failure_detection": {"passed": special_ok, "detail": special_note},
            "adaptive_effect_validation": {"passed": adaptive_ok, "detail": adaptive_note},
            "confidence_correlation": {"passed": confidence_ok, "detail": confidence_note},
        },
        "duration_seconds": duration,
        "passed": passed,
    }


async def run_validation(subset_path: Path, output_path: Path, artifact_dir: Path) -> dict[str, Any]:
    sites = _load_sites(subset_path)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for site in sites:
        LOGGER.info("[MAX] validating %s (%s)", site.name, site.url)
        rows.append(await _run_single_site(site, artifact_dir))

    total = len(rows)
    passed = sum(1 for row in rows if row.get("passed"))
    runtime_success = sum(1 for row in rows if not row.get("runtime_error"))

    summary = {
        "total_sites": total,
        "passed_sites": passed,
        "runtime_success_sites": runtime_success,
        "pass_rate": round((passed / total) * 100, 1) if total else 0.0,
        "runtime_success_rate": round((runtime_success / total) * 100, 1) if total else 0.0,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    report = {
        "summary": summary,
        "results": rows,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 17 max-mode validation harness")
    parser.add_argument(
        "--subset",
        default="tests/subsets/phase17_realworld_sites.json",
        help="Subset JSON with site list and category metadata",
    )
    parser.add_argument(
        "--output",
        default="tests/phase17_max_mode_report.json",
        help="Output report JSON path",
    )
    parser.add_argument(
        "--artifact-dir",
        default="tests/artifacts/phase17_http",
        help="Directory for per-site HTTP artifacts",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    subset_path = Path(args.subset)
    output_path = Path(args.output)
    artifact_dir = Path(args.artifact_dir)

    if not subset_path.exists():
        raise FileNotFoundError(f"Subset not found: {subset_path}")

    report = asyncio.run(run_validation(subset_path, output_path, artifact_dir))
    print("=== Phase 17 Max-Mode Validation ===")
    print(f"Sites: {report['summary']['total_sites']}")
    print(f"Pass rate: {report['summary']['pass_rate']}%")
    print(f"Runtime success rate: {report['summary']['runtime_success_rate']}%")
    print(f"Report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
