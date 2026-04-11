import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.abspath("."))

from app.services.audit_runner import run_audit
from app.services.static_checks import StaticChecker

GROUP3_RULES = [
    "missing-alt",
    "input-label",
    "input-name",
    "clickable-no-role",
    "svg-accessible-name",
    "missing-lang",
    "autocomplete-missing",
    "duplicate-label",
]

RULE_TO_CHECK = {
    "missing-alt": ["images"],
    "input-label": ["forms"],
    "input-name": ["forms"],
    "clickable-no-role": ["buttons"],
    "svg-accessible-name": ["svg_accessible_name"],
    "missing-lang": ["language"],
    "autocomplete-missing": ["forms"],
    "duplicate-label": ["forms"],
}

RULE_EXPECTED_ALIASES = {
    "missing-alt": {"missing-alt", "image-alt", "image-alt-present", "image-alt-name", "image-alt-value"},
    "input-label": {"input-label", "missing-label", "form-label-missing"},
    "input-name": {"input-name", "aria-input-field-name", "label"},
    "clickable-no-role": {"clickable-no-role", "button-name", "aria-allowed-role"},
    "svg-accessible-name": {"svg-accessible-name", "svg-no-accessible-name", "svg-img-alt"},
    "missing-lang": {"missing-lang", "no-lang", "html-has-lang"},
    "autocomplete-missing": {"autocomplete-missing", "missing-autocomplete", "autocomplete-valid"},
    "duplicate-label": {"duplicate-label", "attribute-duplication", "label"},
}

REAL_WORLD_SITES = [
    "https://www.apple.com/",
    "https://www.wikipedia.org/",
    "https://www.amazon.com/",
    "https://www.reddit.com/",
    "https://www.gov.uk/",
]


def _fetch_html(url: str, timeout: int = 25) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _first_candidate_snippet(html: str, rule_id: str) -> str:
    checker = StaticChecker(html, "https://snippet.local")
    soup = checker.soup

    if rule_id == "missing-alt":
        node = soup.find("img")
        if node:
            return str(node)[:320]

    if rule_id in {"input-label", "input-name", "autocomplete-missing", "duplicate-label"}:
        node = soup.find(["input", "textarea", "select", "label"])
        if node:
            return str(node)[:320]

    if rule_id == "clickable-no-role":
        node = soup.find(["div", "span"], attrs={"onclick": True})
        if node:
            return str(node)[:320]

    if rule_id == "svg-accessible-name":
        node = soup.find("svg")
        if node:
            return str(node)[:320]

    if rule_id == "missing-lang":
        node = soup.find("html")
        if node:
            return str(node)[:320]

    body = soup.find("body")
    return str(body)[:320] if body else html[:320]


def _merge_samples(target: list[str], incoming: list[str], cap: int = 5) -> None:
    for item in incoming:
        clean = str(item or "").strip()
        if not clean or clean in target:
            continue
        target.append(clean)
        if len(target) >= cap:
            return


async def _run_real_world_coverage() -> list[dict]:
    rows = []
    for url in REAL_WORLD_SITES:
        entry = {
            "url": url,
            "error": None,
            "rule_hits": {},
        }
        try:
            result = await run_audit(
                url,
                scan_mode="deep",
                precision_profile="high_precision",
                enable_enrichment=False,
                enable_cognitive=False,
                use_cache=False,
            )
            issues = result.get("issues", [])
            for rule_id in GROUP3_RULES:
                matched = [i for i in issues if i.get("rule_id") == rule_id]
                entry["rule_hits"][rule_id] = {
                    "violations_found": len(matched),
                    "example_cases": [
                        {
                            "element": i.get("element"),
                            "html_snippet": (i.get("html_snippet") or "")[:220],
                            "description": i.get("description"),
                        }
                        for i in matched[:3]
                    ],
                }
        except Exception as exc:
            entry["error"] = str(exc)
        rows.append(entry)
    return rows


def _select_act_cases(cases: list[dict], rule_id: str, limit: int = 6) -> list[dict]:
    selected = []
    alias_set = RULE_EXPECTED_ALIASES.get(rule_id, {rule_id})
    per_act_rule_cap = 2
    per_act_rule_counts: dict[str, int] = {}

    for case in cases:
        expected = set(case.get("expected_rule_ids", [])) | set(case.get("known_valid_rule_ids", []))
        if not (expected & alias_set):
            continue

        url = str(case.get("url") or "")
        act_case_id = "unknown"
        if "/testcases/" in url:
            suffix = url.split("/testcases/", 1)[1]
            act_case_id = suffix.split("/", 1)[0] if suffix else "unknown"

        if per_act_rule_counts.get(act_case_id, 0) >= per_act_rule_cap:
            continue

        selected.append(case)
        per_act_rule_counts[act_case_id] = per_act_rule_counts.get(act_case_id, 0) + 1

        if len(selected) >= limit:
            break

    return selected


async def main() -> None:
    root = Path(".")
    benchmark_path = root / "evaluation" / "benchmark_cases.json"
    output_path = root / "evaluation" / "phase1_group3_diagnostics_after.json"

    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    cases = benchmark.get("cases", [])

    step1_summary = []
    step2_mapping = []

    for rule_id in GROUP3_RULES:
        act_cases = _select_act_cases(cases, rule_id)

        rule_checked = 0
        rule_violations = 0
        rule_high_conf = 0
        rule_medium_conf = 0
        sample_elements_checked: list[str] = []
        sample_violations: list[str] = []
        per_case_rows = []

        for case in act_cases:
            url = case.get("url")
            case_row = {
                "name": case.get("name", "unknown"),
                "url": url,
                "expected_rule_ids": case.get("expected_rule_ids", []),
                "known_valid_rule_ids": case.get("known_valid_rule_ids", []),
                "manual_violations_found": 0,
                "status": "LOGIC GAP",
                "html_snippet": "",
                "rule_activity": {},
                "error": None,
            }

            if not url:
                case_row["error"] = "missing_url"
                per_case_rows.append(case_row)
                continue

            try:
                html = _fetch_html(url)
                checker = StaticChecker(html, url)
                issues = checker.run_all(checks=RULE_TO_CHECK[rule_id])
                issues_for_rule = [i for i in issues if i.get("rule_id") == rule_id]
                activity = checker.get_rule_activity().get(
                    rule_id,
                    {
                        "elements_checked": 0,
                        "violations_found": 0,
                        "confidence_bucket": {"high": 0, "medium": 0, "low": 0},
                        "sample_elements_checked": [],
                        "sample_violations": [],
                    },
                )

                case_row["manual_violations_found"] = len(issues_for_rule)
                case_row["status"] = "TRIGGERED" if len(issues_for_rule) > 0 else "LOGIC GAP"
                case_row["rule_activity"] = activity
                case_row["html_snippet"] = (
                    (activity.get("sample_violations") or [""])[0]
                    or (issues_for_rule[0].get("html_snippet") if issues_for_rule else "")
                    or _first_candidate_snippet(html, rule_id)
                )[:320]

                rule_checked += int(activity.get("elements_checked", 0) or 0)
                rule_violations += int(activity.get("violations_found", 0) or 0)
                confidence_bucket = activity.get("confidence_bucket") or {}
                rule_high_conf += int(confidence_bucket.get("high", 0) or 0)
                rule_medium_conf += int(confidence_bucket.get("medium", 0) or 0)
                _merge_samples(sample_elements_checked, list(activity.get("sample_elements_checked") or []))
                _merge_samples(sample_violations, list(activity.get("sample_violations") or []))
            except (HTTPError, URLError, TimeoutError, ValueError) as exc:
                case_row["error"] = str(exc)
            except Exception as exc:
                case_row["error"] = f"unexpected: {exc}"

            per_case_rows.append(case_row)

        step1_summary.append(
            {
                "rule_id": rule_id,
                "elements_checked": rule_checked,
                "violations_found": rule_violations,
                "high_confidence_count": rule_high_conf,
                "medium_confidence_count": rule_medium_conf,
                "sample_elements_checked": sample_elements_checked,
                "sample_violations": sample_violations,
                "status": "NOT FIRING" if rule_violations == 0 else "FIRING",
                "act_cases_used": len(act_cases),
            }
        )

        step2_mapping.append(
            {
                "rule_id": rule_id,
                "cases": per_case_rows,
            }
        )

    step3_rows = await _run_real_world_coverage()

    step3_summary = []
    for rule_id in GROUP3_RULES:
        total_violations = 0
        example_cases = []
        for site_row in step3_rows:
            hit = (site_row.get("rule_hits") or {}).get(rule_id) or {}
            total_violations += int(hit.get("violations_found", 0) or 0)
            examples = hit.get("example_cases") or []
            for ex in examples:
                example_cases.append({"url": site_row.get("url"), **ex})
                if len(example_cases) >= 5:
                    break
            if len(example_cases) >= 5:
                break

        step3_summary.append(
            {
                "rule_id": rule_id,
                "violations_found": total_violations,
                "example_cases": example_cases,
                "status": "NOT FIRING" if total_violations == 0 else "FIRING",
            }
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "phase1_group3_refinement",
        "step1_rule_firing_diagnostics": step1_summary,
        "activation_audit": [
            {
                "rule_id": row.get("rule_id"),
                "elements_checked": row.get("elements_checked", 0),
                "violations_found": row.get("violations_found", 0),
                "high_confidence_count": row.get("high_confidence_count", 0),
                "medium_confidence_count": row.get("medium_confidence_count", 0),
            }
            for row in step1_summary
        ],
        "step2_act_test_mapping": step2_mapping,
        "step3_real_world_site_results": step3_rows,
        "step3_real_world_rule_summary": step3_summary,
    }

    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "step1": step1_summary,
                "step3_summary": step3_summary,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
