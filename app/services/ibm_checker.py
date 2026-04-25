"""IBM Equal Access wrapper.

Runs the Node.js accessibility-checker script and converts results into
BEACON-friendly intermediate findings.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _scripts_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "scripts"


def _ibm_script_path() -> Path:
    return _scripts_dir() / "ibm_scan.js"


def _best_effort_selector(raw: Any) -> str:
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, str):
            return first.strip()
    return ""


def parse_ibm_report(report: dict[str, Any], *, page_url: str) -> list[dict[str, Any]]:
    """Extract flat finding records from IBM report payloads.

    The IBM API report shape can vary between versions, so extraction is
    intentionally defensive.
    """
    findings: list[dict[str, Any]] = []

    result_blocks = report.get("results")
    if not isinstance(result_blocks, list):
        result_blocks = report.get("items") if isinstance(report.get("items"), list) else []

    for item in result_blocks:
        if not isinstance(item, dict):
            continue

        raw_rule_id = str(
            item.get("ruleId")
            or item.get("rule_id")
            or item.get("id")
            or ""
        ).strip()
        if not raw_rule_id:
            continue

        message = str(
            item.get("message")
            or item.get("reason")
            or item.get("description")
            or ""
        ).strip()

        severity = str(item.get("level") or item.get("severity") or "moderate").strip().lower()

        paths = item.get("path")
        selector = _best_effort_selector(paths)
        if not selector:
            selector = _best_effort_selector(item.get("target"))

        findings.append(
            {
                "rule_id": raw_rule_id,
                "selector": selector,
                "message": message,
                "severity": severity,
                "page_url": page_url,
                "engine": "ibm",
            }
        )

    return findings


async def run_ibm_scan_url(url: str, *, timeout_seconds: float = 90.0) -> list[dict[str, Any]]:
    """Run IBM Equal Access for a URL or file:// URI."""
    script_path = _ibm_script_path()
    if not script_path.exists():
        logger.warning("IBM scan script missing at %s", script_path)
        return []

    cmd = ["node", str(script_path), str(url)]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
    except (OSError, asyncio.TimeoutError) as exc:
        logger.warning("IBM checker invocation failed for %s: %s", url, exc)
        return []

    if proc.returncode != 0:
        logger.warning("IBM checker returned non-zero exit code (%s): %s", proc.returncode, stderr.decode("utf-8", errors="ignore"))
        return []

    raw_output = stdout.decode("utf-8", errors="ignore").strip()
    if not raw_output:
        return []

    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError:
        logger.warning("IBM checker produced non-JSON output for %s", url)
        return []

    if not isinstance(payload, dict):
        return []

    return parse_ibm_report(payload, page_url=url)


async def run_ibm_scan_file(file_path: str | Path, *, timeout_seconds: float = 90.0) -> list[dict[str, Any]]:
    path = Path(file_path)
    if not path.exists():
        return []
    return await run_ibm_scan_url(path.resolve().as_uri(), timeout_seconds=timeout_seconds)


def run_ibm_scan_file_sync(file_path: str | Path, *, timeout_seconds: float = 25.0) -> list[dict[str, Any]]:
    return asyncio.run(run_ibm_scan_file(file_path, timeout_seconds=timeout_seconds))
