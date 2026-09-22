"""
Vendored Axe-Core Runtime Manager (§7)
Ensures offline-safe axe execution without CDN dependency.
Targets assets/vendor/axe.min.js.
Provides offline execution, missing vendor asset handling, fallback behavior, and version reporting.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Primary candidate paths for vendored axe runtime
_CANDIDATE_PATHS = [
    Path(__file__).resolve().parents[2] / "assets" / "vendor" / "axe.min.js",
    Path(__file__).resolve().parents[2] / "axe-core" / "axe.min.js",
    Path(__file__).resolve().parents[2] / "frontend" / "node_modules" / "axe-core" / "axe.min.js",
]

_CDN_URL = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.11.1/axe.min.js"


def get_vendored_axe_path() -> Path | None:
    """Resolve the local vendored axe runtime path."""
    for path in _CANDIDATE_PATHS:
        if path.exists() and path.stat().st_size > 10000:
            return path
    return None


def get_axe_version() -> str:
    """Return the version of the vendored or configured axe runtime."""
    # Check package.json near vendored asset
    for candidate in _CANDIDATE_PATHS:
        pkg = candidate.parent / "package.json"
        if pkg.exists():
            try:
                with open(pkg, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("version"):
                        return data["version"]
            except Exception:
                pass

    from app.services.engine_manifest import get_engine_manifest
    manifest = get_engine_manifest()
    return manifest.get("scan_engine_versions", {}).get("axe", "4.11.1")


async def inject_axe(page: Any, allow_cdn_fallback: bool = False) -> tuple[bool, str, str]:
    """
    Inject axe-core into a Playwright page.
    Returns: (success: bool, source: "vendored" | "cdn" | "none", version: str)
    """
    local_path = get_vendored_axe_path()
    
    if local_path is not None:
        try:
            await page.add_script_tag(path=str(local_path))
            version = await page.evaluate("typeof axe !== 'undefined' ? axe.version : ''")
            return True, "vendored", version or get_axe_version()
        except Exception as e:
            logger.warning(f"Failed to inject local vendored axe: {e}")

    if allow_cdn_fallback:
        try:
            logger.info("Local axe runtime missing/failed; falling back to CDN")
            await page.add_script_tag(url=_CDN_URL)
            version = await page.evaluate("typeof axe !== 'undefined' ? axe.version : ''")
            return True, "cdn", version or "4.11.1"
        except Exception as e:
            logger.error(f"CDN axe fallback failed: {e}")
            return False, "none", ""

    logger.error(
        "Axe vendored runtime missing at assets/vendor/axe.min.js and offline safe execution is enforced."
    )
    return False, "none", ""


async def run_axe_core(page: Any, allow_cdn_fallback: bool = False) -> dict[str, Any]:
    """
    Execute axe-core in page with version tracking and offline enforcement.
    Returns: {"violations": [...], "version": "...", "source": "vendored" | "cdn", "success": bool}
    """
    success, source, version = await inject_axe(page, allow_cdn_fallback=allow_cdn_fallback)
    if not success:
        return {
            "violations": [],
            "version": "",
            "source": "none",
            "success": False,
            "error": "Axe runtime could not be injected (offline vendored asset missing).",
        }

    try:
        await page.wait_for_timeout(300)
        results = await page.evaluate("axe.run()")
        violations = results.get("violations", []) if isinstance(results, dict) else []
        return {
            "violations": violations,
            "version": version or get_axe_version(),
            "source": source,
            "success": True,
        }
    except Exception as e:
        logger.warning(f"axe.run() evaluation failed: {e}")
        return {
            "violations": [],
            "version": version,
            "source": source,
            "success": False,
            "error": str(e),
        }
