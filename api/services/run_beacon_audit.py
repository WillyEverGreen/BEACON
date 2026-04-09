"""Run a BEACON audit and emit JSON to stdout for the Node API layer."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from app.services.audit_runner import run_audit


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\n")
    sys.stdout.flush()


async def _run(url: str, mode: str) -> dict[str, Any]:
    return await run_audit(url=url, scan_mode=mode, await_enrichment=False)


def main() -> int:
    if len(sys.argv) < 3:
        _emit({"__error__": "Usage: run_beacon_audit.py <url> <mode>"})
        return 2

    url = str(sys.argv[1]).strip()
    mode = str(sys.argv[2]).strip().lower() or "balanced"

    try:
        result = asyncio.run(_run(url, mode))
    except Exception as exc:  # pragma: no cover - process-level guard
        _emit({"__error__": f"{exc.__class__.__name__}: {exc}"})
        return 1

    try:
        _emit(result)
    except Exception as exc:  # pragma: no cover - process-level guard
        _emit({"__error__": f"Result serialization failed: {exc}"})
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
