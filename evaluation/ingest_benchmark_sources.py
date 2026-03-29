"""
Ingest benchmark sources (Tier 1/2) and normalize into benchmark_cases.json.

Output schema:
{
  "cases": [
    {
      "name": str,
      "url": str,
      "expected_rule_ids": [str],
      "known_valid_rule_ids": [str],
      "known_invalid_rule_ids": [str],
      "source_id": str,
      "source_tier": int
    }
  ]
}
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


DEFAULT_SOURCES = Path("evaluation/benchmark_sources.json")
DEFAULT_OUT = Path("evaluation/benchmark_cases.json")
DEFAULT_REPORT = Path("evaluation/benchmark_ingestion_report.json")
DEFAULT_ACT_MAP = Path("evaluation/act_rule_mapping.json")

RULE_MAP = {
    "image-alt": "missing-alt",
    "label": "missing-label",
    "button-name": "button-no-name",
    "link-name": "empty-link",
    "bypass": "missing-skip-link",
    "video-caption": "missing-captions",
    "color-contrast": "color-contrast"
}


def fetch_json(url: str) -> object:
    req = Request(url, headers={"User-Agent": "A11y-Benchmark-Ingest/1.0"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def normalize_rule_id(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    return RULE_MAP.get(raw, raw)


def load_act_mapping(path: Path) -> dict[str, list[str]]:
    """Load ACT hash -> internal rule IDs mapping JSON."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    out: dict[str, list[str]] = {}
    for k, v in (data or {}).items():
        if not isinstance(k, str):
            continue
        vals = []
        for item in _ensure_list(v):
            if isinstance(item, str) and item.strip():
                vals.append(item.strip())
        if vals:
            out[k.strip()] = sorted(set(vals))
    return out


def _ensure_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def parse_act_testcases(
    payload: object,
    source: dict,
    act_map: dict[str, list[str]] | None = None,
) -> tuple[list[dict], dict]:
    """
    ACT JSON structure varies; parse conservatively.
    We only emit URL-based benchmark cases that fit existing evaluator.
    """
    emitted = []
    stats = {
        "input_items": 0,
        "emitted": 0,
        "skipped": 0,
        "mapped_hashes": 0,
        "unmapped_hashes": 0,
    }
    act_map = act_map or {}

    if isinstance(payload, dict):
        # Common pattern: object with a list under a known key.
        candidates = None
        for key in ("testcases", "cases", "items", "rules"):
            if isinstance(payload.get(key), list):
                candidates = payload[key]
                break
        if candidates is None:
            # fallback: flatten list values in dict
            candidates = []
            for v in payload.values():
                if isinstance(v, list):
                    candidates.extend(v)
    elif isinstance(payload, list):
        candidates = payload
    else:
        candidates = []

    for item in candidates:
        stats["input_items"] += 1
        if not isinstance(item, dict):
            stats["skipped"] += 1
            continue

        url = item.get("url") or item.get("page") or item.get("testUrl")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            stats["skipped"] += 1
            continue

        raw_rules = []
        for key in ("rule", "rule_id", "ruleId", "rules", "violations"):
            val = item.get(key)
            if isinstance(val, str):
                raw_rules.append(val)
            elif isinstance(val, list):
                for v in val:
                    if isinstance(v, str):
                        raw_rules.append(v)
                    elif isinstance(v, dict):
                        rid = v.get("id") or v.get("rule") or v.get("ruleId")
                        if isinstance(rid, str):
                            raw_rules.append(rid)

        mapped_rules = []
        unmapped_hashes = []
        for r in raw_rules:
            r = (r or "").strip()
            if not r:
                continue
            if r in act_map:
                mapped_rules.extend(act_map[r])
                stats["mapped_hashes"] += 1
            else:
                normalized = normalize_rule_id(r)
                if re.fullmatch(r"[0-9a-f]{6}", r):
                    unmapped_hashes.append(r)
                    stats["unmapped_hashes"] += 1
                elif normalized:
                    mapped_rules.append(normalized)

        rules = sorted({x for x in mapped_rules if x})
        if not rules:
            stats["skipped"] += 1
            continue

        name = item.get("name") or item.get("title") or f"ACT case {stats['input_items']}"

        emitted.append(
            {
                "name": str(name),
                "url": url,
                "expected_rule_ids": rules,
                "known_valid_rule_ids": rules,
                "known_invalid_rule_ids": [],
                "source_id": source["id"],
                "source_tier": source["tier"],
                "unmapped_act_rule_ids": sorted(set(unmapped_hashes)),
            }
        )
        stats["emitted"] += 1

    return emitted, stats


def parse_alphagov_tests(payload: object, source: dict) -> tuple[list[dict], dict]:
    emitted = []
    stats = {"input_items": 0, "emitted": 0, "skipped": 0}

    tests = payload if isinstance(payload, list) else payload.get("tests", []) if isinstance(payload, dict) else []

    for item in tests:
        stats["input_items"] += 1
        if not isinstance(item, dict):
            stats["skipped"] += 1
            continue

        url = item.get("url") or item.get("page")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            stats["skipped"] += 1
            continue

        violations = item.get("violations") or item.get("issues") or []
        raw_rules = []
        for v in _ensure_list(violations):
            if isinstance(v, str):
                raw_rules.append(v)
            elif isinstance(v, dict):
                rid = v.get("id") or v.get("rule") or v.get("ruleId")
                if isinstance(rid, str):
                    raw_rules.append(rid)

        rules = sorted({normalize_rule_id(r) for r in raw_rules if normalize_rule_id(r)})
        if not rules:
            stats["skipped"] += 1
            continue

        name = item.get("name") or item.get("title") or item.get("label") or f"alphagov case {stats['input_items']}"

        emitted.append(
            {
                "name": str(name),
                "url": url,
                "expected_rule_ids": rules,
                "known_valid_rule_ids": rules,
                "known_invalid_rule_ids": [],
                "source_id": source["id"],
                "source_tier": source["tier"],
            }
        )
        stats["emitted"] += 1

    return emitted, stats


def parse_generic_dataset_optional(payload: object, source: dict) -> tuple[list[dict], dict]:
    # Placeholder parser for user-provided local dataset files.
    # Expected optional schema:
    # {"cases": [{"name":..., "url":..., "known_valid_rule_ids":[...], ...}]}
    emitted = []
    stats = {"input_items": 0, "emitted": 0, "skipped": 0}

    if isinstance(payload, dict) and isinstance(payload.get("cases"), list):
        for c in payload["cases"]:
            stats["input_items"] += 1
            if not isinstance(c, dict):
                stats["skipped"] += 1
                continue
            url = c.get("url")
            rules = c.get("known_valid_rule_ids") or c.get("expected_rule_ids") or []
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                stats["skipped"] += 1
                continue
            rules = sorted({normalize_rule_id(r) for r in _ensure_list(rules) if normalize_rule_id(r)})
            if not rules:
                stats["skipped"] += 1
                continue
            emitted.append(
                {
                    "name": c.get("name") or url,
                    "url": url,
                    "expected_rule_ids": rules,
                    "known_valid_rule_ids": rules,
                    "known_invalid_rule_ids": _ensure_list(c.get("known_invalid_rule_ids")),
                    "source_id": source["id"],
                    "source_tier": source["tier"],
                }
            )
            stats["emitted"] += 1

    return emitted, stats


def parse_repo_fixtures_stub(_payload: object, _source: dict) -> tuple[list[dict], dict]:
    # Repo fixtures need source-specific adapters (file layout + expected labels).
    return [], {"input_items": 0, "emitted": 0, "skipped": 0, "note": "adapter_not_implemented"}


PARSERS = {
    "act_testcases": parse_act_testcases,
    "alphagov_tests": parse_alphagov_tests,
    "generic_dataset_optional": parse_generic_dataset_optional,
    "repo_fixtures_stub": parse_repo_fixtures_stub,
}


def dedupe_cases(cases: list[dict]) -> tuple[list[dict], int]:
    deduped = {}
    merged_count = 0

    for case in cases:
        key = (case.get("url", "").strip().lower(), tuple(sorted(case.get("known_valid_rule_ids", []))))
        if key in deduped:
            merged_count += 1
            # merge source provenance
            prev = deduped[key]
            prev_sources = _ensure_list(prev.get("source_id"))
            curr_sources = _ensure_list(case.get("source_id"))
            prev["source_id"] = sorted(set(prev_sources + curr_sources))
        else:
            deduped[key] = case

    return list(deduped.values()), merged_count


def ingest_all(sources_cfg: dict, act_map: dict[str, list[str]] | None = None) -> tuple[list[dict], dict]:
    all_cases = []
    report = {"sources": [], "totals": {"emitted_raw": 0, "emitted_deduped": 0, "merged": 0, "errors": 0}}

    for src in sources_cfg.get("sources", []):
        sid = src.get("id", "unknown")
        parser_name = src.get("parser", "")
        parser = PARSERS.get(parser_name)

        src_report = {
            "id": sid,
            "tier": src.get("tier"),
            "kind": src.get("kind"),
            "parser": parser_name,
            "status": "ok",
            "error": "",
            "stats": {},
        }

        if parser is None:
            src_report["status"] = "error"
            src_report["error"] = f"unknown parser: {parser_name}"
            report["totals"]["errors"] += 1
            report["sources"].append(src_report)
            continue

        try:
            payload = None
            kind = src.get("kind")

            if kind == "json_url":
                payload = fetch_json(src["url"])
            elif kind == "local_file":
                p = Path(src["path"])
                if not p.exists():
                    raise FileNotFoundError(f"local file not found: {p}")
                payload = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
            elif kind == "github_repo":
                payload = {}
            else:
                raise ValueError(f"unsupported source kind: {kind}")

            if src.get("parser") == "act_testcases":
                cases, stats = parser(payload, src, act_map)
            else:
                cases, stats = parser(payload, src)
            src_report["stats"] = stats
            all_cases.extend(cases)
            report["totals"]["emitted_raw"] += stats.get("emitted", 0)

        except (URLError, HTTPError, TimeoutError, FileNotFoundError, ValueError) as e:
            src_report["status"] = "error"
            src_report["error"] = str(e)
            report["totals"]["errors"] += 1
        except Exception as e:
            src_report["status"] = "error"
            src_report["error"] = f"unexpected: {e}"
            report["totals"]["errors"] += 1

        report["sources"].append(src_report)

    deduped, merged = dedupe_cases(all_cases)
    report["totals"]["emitted_deduped"] = len(deduped)
    report["totals"]["merged"] = merged
    return deduped, report


def main():
    ap = argparse.ArgumentParser(description="Ingest benchmark sources into benchmark_cases.json")
    ap.add_argument("--sources", default=str(DEFAULT_SOURCES), help="Path to source manifest JSON")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="Output benchmark cases JSON")
    ap.add_argument("--report", default=str(DEFAULT_REPORT), help="Output ingestion report JSON")
    ap.add_argument("--act-map", default=str(DEFAULT_ACT_MAP), help="ACT hash to internal rule mapping JSON")
    args = ap.parse_args()

    src_path = Path(args.sources)
    if not src_path.exists():
        raise FileNotFoundError(f"Sources manifest not found: {src_path}")

    cfg = json.loads(src_path.read_text(encoding="utf-8", errors="ignore"))
    act_map = load_act_mapping(Path(args.act_map))
    cases, report = ingest_all(cfg, act_map=act_map)
    report["act_mapping"] = {
        "mapping_file": str(args.act_map),
        "entries": len(act_map),
    }

    out_payload = {"cases": cases}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_payload, indent=2), encoding="utf-8")

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=== Benchmark Ingestion ===")
    print(f"Raw emitted:      {report['totals']['emitted_raw']}")
    print(f"Deduped emitted:  {report['totals']['emitted_deduped']}")
    print(f"Merged duplicates:{report['totals']['merged']}")
    print(f"Source errors:    {report['totals']['errors']}")
    print(f"Saved cases:      {out_path}")
    print(f"Saved report:     {report_path}")


if __name__ == "__main__":
    main()
