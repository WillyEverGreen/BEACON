"""Per-page audit runner with multi-state scanning and DOM-hash suppression."""

from __future__ import annotations

import hashlib
import re
import time
from typing import Any, Optional

from bs4 import BeautifulSoup

from app.config import CRAWLER_CONFIG
from app.audit.dynamic_handling import (
    apply_anti_bot_delay,
    apply_anti_bot_headers,
    attempt_public_fallback_scan,
    detect_framework_and_wait,
    detect_login_wall,
    dismiss_cookie_banner,
    install_third_party_script_blocking,
)
from app.audit.exploration import SPAStrategyPack
from app.audit.fingerprint import stable_selector_fingerprint
from app.audit.models import PageAuditResult, PageContext, PageStateMeta, state_meta_to_dict


_STATE_SEQUENCE = ("initial", "after_interaction", "after_scroll")

_DYNAMIC_ATTR_NAME_PATTERN = re.compile(
    r"(?:timestamp|nonce|random|rand|uuid|guid|token|session|cache|build|version|ts)",
    re.IGNORECASE,
)
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_ISO_TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}t\d{2}:\d{2}:\d{2}", re.IGNORECASE)


def _looks_dynamic_value(value: str) -> bool:
    raw = (value or "").strip().lower()
    if not raw:
        return False

    if _UUID_PATTERN.match(raw):
        return True

    if _ISO_TIMESTAMP_PATTERN.match(raw):
        return True

    if raw.isdigit() and len(raw) >= 10:
        return True

    if re.match(r"^[a-f0-9]{10,}$", raw):
        return True

    if len(raw) >= 10 and re.search(r"[a-z]", raw) and re.search(r"\d", raw):
        return True

    return False


def _canonicalize_dom_for_hash(dom: str) -> str:
    soup = BeautifulSoup(dom or "", "html.parser")

    for node in soup(["script", "style", "noscript"]):
        node.decompose()

    for tag in soup.find_all(True):
        normalized_attrs: dict[str, Any] = {}

        for attr_name, attr_value in list(tag.attrs.items()):
            lowered_name = str(attr_name).lower()

            if _DYNAMIC_ATTR_NAME_PATTERN.search(lowered_name):
                continue

            if isinstance(attr_value, list):
                values = [" ".join(str(item).split()) for item in attr_value if str(item).strip()]
            else:
                values = [" ".join(str(attr_value).split())]

            if lowered_name == "class":
                stable_classes = sorted(
                    cls for cls in values if cls and not _looks_dynamic_value(cls)
                )
                if stable_classes:
                    normalized_attrs[lowered_name] = stable_classes
                continue

            merged_value = " ".join(values).strip()
            if not merged_value:
                continue

            if lowered_name in {"id", "for", "aria-controls", "aria-labelledby", "aria-describedby"}:
                if _looks_dynamic_value(merged_value):
                    normalized_attrs[lowered_name] = "__dynamic__"
                    continue

            if _looks_dynamic_value(merged_value):
                normalized_attrs[lowered_name] = "__dynamic__"
            else:
                normalized_attrs[lowered_name] = merged_value

        tag.attrs = {key: normalized_attrs[key] for key in sorted(normalized_attrs)}

    canonical = str(soup)
    canonical = re.sub(r"\s+", " ", canonical).strip()
    return canonical


def _compact_dom_hash(dom: str) -> str:
    canonical_dom = _canonicalize_dom_for_hash(dom)
    return hashlib.sha256(canonical_dom.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _issue_confidence(issue: dict[str, Any]) -> float:
    try:
        return float(issue.get("confidence", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _issue_merge_key(issue: dict[str, Any]) -> tuple[str, str, str]:
    selector = (
        issue.get("element_selector_fingerprint")
        or issue.get("selector")
        or issue.get("element")
        or ""
    )
    stable_selector = stable_selector_fingerprint(str(selector))
    return (
        str(issue.get("rule_id", "")),
        str(issue.get("wcag_criterion", "")),
        stable_selector,
    )


def _normalize_state_payload(payload: dict[str, Any] | str | None) -> tuple[str, str]:
    if payload is None:
        return "", "unknown"

    if isinstance(payload, str):
        return payload, "unknown"

    html = str(payload.get("html") or payload.get("dom") or "")
    hydration_status = str(payload.get("hydration_status") or "unknown")
    return html, hydration_status


async def _ensure_playwright_browser(page_context: PageContext) -> Any:
    if page_context.playwright_browser is not None:
        return page_context.playwright_browser

    if page_context.browser_factory is None:
        return None

    browser = await page_context.browser_factory()
    page_context.playwright_browser = browser
    page_context.owns_browser = True
    return browser


async def _default_state_provider(url: str, state: str, page_context: PageContext) -> dict[str, Any] | str:
    """Best-effort state provider that reuses a shared Playwright browser from PageContext."""
    browser = await _ensure_playwright_browser(page_context)
    if browser is None:
        return {"html": "", "hydration_status": "unavailable"}

    cfg = CRAWLER_CONFIG["dom"]
    network_idle_timeout_ms = int(cfg["network_idle_timeout_ms"])
    ready_state_timeout_ms = int(cfg["ready_state_timeout_ms"])
    interaction_wait_ms = int(cfg["interaction_wait_ms"])
    scroll_wait_ms = int(cfg["scroll_wait_ms"])

    page = await browser.new_page()
    hydration_status = "uncertain"
    try:
        allow_intercom = page_context.cognitive_engine is not None
        blocking_enabled = await install_third_party_script_blocking(
            page,
            url,
            allow_intercom=allow_intercom,
        )
        anti_bot_headers = await apply_anti_bot_headers(page, url)
        anti_bot_delay = await apply_anti_bot_delay(page, url)

        await page.goto(url, wait_until="domcontentloaded")

        detected_framework, hydration_status = await detect_framework_and_wait(
            page,
            network_idle_timeout_ms=network_idle_timeout_ms,
            ready_state_timeout_ms=ready_state_timeout_ms,
        )

        cookie_dismissed = await dismiss_cookie_banner(page)

        auth_state = await detect_login_wall(page, current_url=str(getattr(page, "url", url) or url))
        if auth_state.get("requires_auth"):
            fallback = await attempt_public_fallback_scan(page, url)
            if fallback.get("used"):
                return {
                    "html": str(fallback.get("html", "")),
                    "hydration_status": "auth_wall_fallback",
                    "detected_framework": detected_framework,
                    "requires_auth": True,
                    "auth_reason": auth_state.get("reason", "auth_wall"),
                    "auth_fallback_used": True,
                    "auth_fallback_url": fallback.get("fallback_url", ""),
                    "checked_fallback_urls": fallback.get("checked_urls", []),
                    "cookie_banner_dismissed": cookie_dismissed,
                    "third_party_blocking_enabled": blocking_enabled,
                    "anti_bot_delay_ms": anti_bot_delay,
                    "anti_bot_headers": anti_bot_headers,
                    "actions_taken": 0,
                }

            html = await page.content()
            return {
                "html": html,
                "hydration_status": "requires_auth",
                "detected_framework": detected_framework,
                "requires_auth": True,
                "auth_reason": auth_state.get("reason", "auth_wall"),
                "auth_fallback_used": False,
                "cookie_banner_dismissed": cookie_dismissed,
                "third_party_blocking_enabled": blocking_enabled,
                "anti_bot_delay_ms": anti_bot_delay,
                "anti_bot_headers": anti_bot_headers,
                "actions_taken": 0,
            }

        strategy_pack = SPAStrategyPack(
            seed_url=url,
            interaction_budget=int(cfg["interaction_budget_per_page"]),
            max_route_clicks=min(3, int(cfg["interaction_budget_per_page"])),
            route_settle_ms=interaction_wait_ms,
            scroll_wait_ms=scroll_wait_ms,
            lazy_scroll_steps=max(1, min(int(cfg["scroll_steps"]), 3)),
        )

        actions_taken = 0
        exploration_quality: dict[str, Any] = {
            "actions_taken": 0,
            "new_states": 0,
            "dom_change_ratio": 0.0,
            "early_stopped": False,
        }
        modal_checks: dict[str, Any] = {}

        if state == "after_interaction":
            route_result = await strategy_pack.trigger_route_change(page, detected_framework=detected_framework)
            actions_taken += int(route_result.get("actions_taken", 0))

            remaining = max(0, int(cfg["interaction_budget_per_page"]) - actions_taken)
            modal_checks = await strategy_pack.trigger_modals(page, max_actions=remaining)
            actions_taken += int(modal_checks.get("actions_taken", 0))

            new_states = int(route_result.get("route_changes", 0))
            if int(modal_checks.get("modal_checks_run", 0)) > 0:
                new_states += 1
            exploration_quality = {
                "actions_taken": actions_taken,
                "new_states": new_states,
                "dom_change_ratio": round(new_states / max(actions_taken, 1), 2),
                "early_stopped": actions_taken >= 2 and new_states == 0,
            }

        if state == "after_scroll":
            lazy_result = await strategy_pack.trigger_lazy_load(page, max_actions=int(cfg["scroll_steps"]))
            actions_taken += int(lazy_result.get("actions_taken", 0))
            growth_steps = int(lazy_result.get("growth_steps", 0))
            exploration_quality = {
                "actions_taken": actions_taken,
                "new_states": growth_steps,
                "dom_change_ratio": round(growth_steps / max(actions_taken, 1), 2),
                "early_stopped": actions_taken >= 2 and growth_steps == 0,
                "infinite_scroll_detected": bool(lazy_result.get("infinite_scroll_detected", False)),
            }

        html = await page.content()
        return {
            "html": html,
            "hydration_status": hydration_status,
            "detected_framework": detected_framework,
            "requires_auth": False,
            "cookie_banner_dismissed": cookie_dismissed,
            "third_party_blocking_enabled": blocking_enabled,
            "anti_bot_delay_ms": anti_bot_delay,
            "anti_bot_headers": anti_bot_headers,
            "actions_taken": actions_taken,
            "exploration_quality": exploration_quality,
            "modal_checks": modal_checks,
        }
    finally:
        await page.close()


async def audit_page(url: str, scan_mode: str, page_context: PageContext) -> PageAuditResult:
    """Run multi-state page auditing and merge findings across discovered states."""
    scan_mode_key = (scan_mode or "").lower()
    if scan_mode_key not in {"fast", "deep", "max"}:
        scan_mode_key = "fast"

    state_sequence = ("initial",) if scan_mode_key == "fast" else _STATE_SEQUENCE
    state_provider = page_context.state_provider or _default_state_provider

    def static_engine(dom: str, page_url: str) -> list[dict[str, Any]]:
        if page_context.static_engine is None:
            return []
        return page_context.static_engine(dom, page_url)

    async def interactive_engine(dom: str, page_url: str) -> list[dict[str, Any]]:
        if page_context.interactive_engine is None:
            return []
        return await page_context.interactive_engine(dom, page_url, page_context)

    async def axe_engine(dom: str, page_url: str) -> list[dict[str, Any]]:
        if page_context.axe_engine is None:
            return []
        return await page_context.axe_engine(dom, page_url, page_context)

    async def cognitive_engine(dom: str, page_url: str) -> list[dict[str, Any]]:
        if page_context.cognitive_engine is None:
            return []
        return await page_context.cognitive_engine(dom, page_url, page_context)

    seen_state_hashes: set[str] = set()
    merged_issues: dict[tuple[str, str, str], dict[str, Any]] = {}

    states_meta: list[dict[str, Any]] = []
    engine_timings: dict[str, float] = {}

    degraded_mode = False
    skipped_engines: list[str] = []
    hydration_status = "unknown"
    page_dom = ""

    for state in state_sequence:
        state_start = time.perf_counter()

        try:
            payload = await state_provider(url, state, page_context)
        except Exception:
            degraded_mode = True
            payload = {"html": "", "hydration_status": "failed"}

        dom, state_hydration = _normalize_state_payload(payload)
        if state_hydration not in {"unknown", ""}:
            hydration_status = state_hydration
        if not page_dom and dom:
            page_dom = dom

        dom_hash = _compact_dom_hash(dom)
        duplicate_state = dom_hash in seen_state_hashes
        if duplicate_state:
            state_duration_ms = int((time.perf_counter() - state_start) * 1000)
            states_meta.append(
                state_meta_to_dict(
                    PageStateMeta(
                        state=state,
                        duration_ms=state_duration_ms,
                        dom_hash=dom_hash,
                        issues_count=0,
                        duplicate_state=True,
                    )
                )
            )
            continue

        seen_state_hashes.add(dom_hash)

        static_start = time.perf_counter()
        try:
            static_issues = static_engine(dom, url)
        except Exception:
            static_issues = []
            degraded_mode = True
            if "static" not in skipped_engines:
                skipped_engines.append("static")
        engine_timings[f"static_{state}_ms"] = round((time.perf_counter() - static_start) * 1000, 2)

        interactive_issues: list[dict[str, Any]] = []
        axe_issues: list[dict[str, Any]] = []
        cognitive_issues: list[dict[str, Any]] = []

        if state != "initial" and scan_mode_key in {"deep", "max"}:
            interactive_start = time.perf_counter()
            if page_context.interactive_engine is None:
                degraded_mode = True
                if "interactive" not in skipped_engines:
                    skipped_engines.append("interactive")
            else:
                try:
                    interactive_issues = await interactive_engine(dom, url)
                except Exception:
                    degraded_mode = True
                    if "interactive" not in skipped_engines:
                        skipped_engines.append("interactive")
            engine_timings[f"interactive_{state}_ms"] = round((time.perf_counter() - interactive_start) * 1000, 2)

            axe_start = time.perf_counter()
            if page_context.axe_engine is None:
                degraded_mode = True
                if "axe" not in skipped_engines:
                    skipped_engines.append("axe")
            else:
                try:
                    axe_issues = await axe_engine(dom, url)
                except Exception:
                    degraded_mode = True
                    if "axe" not in skipped_engines:
                        skipped_engines.append("axe")
            engine_timings[f"axe_{state}_ms"] = round((time.perf_counter() - axe_start) * 1000, 2)

            if scan_mode_key == "max":
                cognitive_start = time.perf_counter()
                if page_context.cognitive_engine is None:
                    degraded_mode = True
                    if "cognitive" not in skipped_engines:
                        skipped_engines.append("cognitive")
                else:
                    try:
                        cognitive_issues = await cognitive_engine(dom, url)
                    except Exception:
                        degraded_mode = True
                        if "cognitive" not in skipped_engines:
                            skipped_engines.append("cognitive")
                engine_timings[f"cognitive_{state}_ms"] = round((time.perf_counter() - cognitive_start) * 1000, 2)

        state_issues = [*static_issues, *interactive_issues, *axe_issues, *cognitive_issues]

        for issue in state_issues:
            issue_data = dict(issue)
            issue_data.setdefault("affected_states", [state])
            issue_data.setdefault("state", state)

            key = _issue_merge_key(issue_data)
            existing = merged_issues.get(key)
            if existing is None:
                merged_issues[key] = issue_data
                continue

            affected_states = sorted(set(existing.get("affected_states", []) + [state]))

            if _issue_confidence(issue_data) > _issue_confidence(existing):
                replacement = dict(issue_data)
                replacement["affected_states"] = affected_states
                replacement.setdefault("state", existing.get("state", state))
                merged_issues[key] = replacement
            else:
                existing["affected_states"] = affected_states
                if issue_data.get("html_snippet") and not existing.get("html_snippet"):
                    existing["html_snippet"] = issue_data["html_snippet"]

        state_duration_ms = int((time.perf_counter() - state_start) * 1000)
        states_meta.append(
            state_meta_to_dict(
                PageStateMeta(
                    state=state,
                    duration_ms=state_duration_ms,
                    dom_hash=dom_hash,
                    issues_count=len(state_issues),
                    duplicate_state=False,
                )
            )
        )

    total_issues = len(merged_issues)
    score = round(max(0.0, 100.0 - min(95.0, float(total_issues) * 2.0)), 1)

    return PageAuditResult(
        url=url,
        score=score,
        issues=list(merged_issues.values()),
        engine_timings=engine_timings,
        degraded_mode=degraded_mode,
        skipped_engines=skipped_engines,
        hydration_status=hydration_status,
        enrichment_status="pending",
        states_meta=states_meta,
        page_dom=page_dom,
    )
