"""Per-page audit runner with multi-state scanning and DOM-hash suppression."""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Any, Optional

from bs4 import BeautifulSoup

from app.config import CRAWLER_CONFIG, SEVERITY_WEIGHTS
from app.audit.dynamic_handling import (
    apply_anti_bot_delay,
    apply_anti_bot_headers,
    attempt_public_fallback_scan,
    detect_framework_and_wait,
    detect_login_wall,
    dismiss_cookie_banner,
    install_request_interception,
    resolve_adaptive_timeouts,
)
from app.audit.failure_taxonomy import classify_failure_reason, normalize_failure, normalize_reason
from app.audit.exploration import SPAStrategyPack
from app.audit.fingerprint import stable_selector_fingerprint
from app.audit.models import PageAuditResult, PageContext, PageStateMeta, state_meta_to_dict
from app.crawlers.common import normalize_scan_mode


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


logger = logging.getLogger(__name__)


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
    raw_dom = dom or ""
    soup = None
    for parser_name in ("lxml", "html.parser"):
        try:
            soup = BeautifulSoup(raw_dom, parser_name)
            break
        except Exception:
            soup = None

    if soup is None:
        return re.sub(r"\s+", " ", raw_dom).strip()[:50000]

    try:
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
    except Exception:
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


def _pick_degraded_reason(reasons: set[str]) -> str:
    if not reasons:
        return ""
    normalized_reasons = {
        normalize_reason(reason) or "extraction_failure"
        for reason in reasons
        if str(reason or "").strip()
    }
    for preferred in (
        "dom_parse_error",
        "render_timeout",
        "dns_failure",
        "blocked_request",
        "network_error",
        "extraction_failure",
    ):
        if preferred in normalized_reasons:
            return preferred
    for preferred in (
        "dom_parse_error",
        "render_timeout",
        "dns_failure",
        "blocked_request",
        "network_error",
        "extraction_failure",
    ):
        if preferred in reasons:
            return preferred
    return sorted(normalized_reasons)[0] if normalized_reasons else ""


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
    scan_mode_key = str(page_context.cache.get("scan_mode", "deep") if isinstance(page_context.cache, dict) else "deep")
    adaptive_timeouts = resolve_adaptive_timeouts(
        url,
        scan_mode_key,
        page_timeout_seconds=int(cfg["page_timeout_seconds"]),
        network_idle_timeout_ms=int(cfg["network_idle_timeout_ms"]),
        ready_state_timeout_ms=int(cfg["ready_state_timeout_ms"]),
    )

    network_idle_timeout_ms = int(adaptive_timeouts["network_idle_timeout_ms"])
    ready_state_timeout_ms = int(adaptive_timeouts["ready_state_timeout_ms"])
    page_timeout_ms = int(adaptive_timeouts["page_timeout_seconds"]) * 1000

    interaction_wait_ms = int(cfg["interaction_wait_ms"])
    scroll_wait_ms = int(cfg["scroll_wait_ms"])
    complexity = str(adaptive_timeouts.get("complexity", "moderate"))
    if complexity == "simple":
        interaction_wait_ms = max(400, int(interaction_wait_ms * 0.7))
        scroll_wait_ms = max(600, int(scroll_wait_ms * 0.8))
    elif complexity == "heavy":
        interaction_wait_ms = min(2000, int(interaction_wait_ms * 1.2))
        scroll_wait_ms = min(2500, int(scroll_wait_ms * 1.2))

    page = await browser.new_page()
    hydration_status = "uncertain"
    detected_framework: Optional[str] = None
    render_retry_used = False

    async def _snapshot_current_dom() -> str:
        try:
            html = await page.content()
            if isinstance(html, str) and html.strip():
                return html
        except Exception:
            pass

        try:
            html = await page.evaluate(
                "() => document.documentElement ? document.documentElement.outerHTML : ''"
            )
            if isinstance(html, str) and html.strip():
                return html
        except Exception:
            pass

        return "<html><body><main>Partial snapshot unavailable.</main></body></html>"

    def _partial_payload(reason: str, html: str, *, cookie_dismissed: bool = False) -> dict[str, Any]:
        return {
            "html": html,
            "hydration_status": "partial",
            "detected_framework": detected_framework,
            "requires_auth": False,
            "cookie_banner_dismissed": cookie_dismissed,
            "third_party_blocking_enabled": blocking_enabled,
            "request_interception": interception,
            "adaptive_timeout_policy": adaptive_timeouts,
            "anti_bot_delay_ms": anti_bot_delay,
            "anti_bot_headers": anti_bot_headers,
            "actions_taken": 0,
            "degraded_reason": normalize_failure(reason).value,
            "partial_mode": True,
            "render_retry_used": render_retry_used,
        }

    blocking_enabled = False
    interception: dict[str, Any] = {"installed": False}
    anti_bot_headers: dict[str, str] = {}
    anti_bot_delay = 0

    try:
        set_timeout = getattr(page, "set_default_timeout", None)
        if callable(set_timeout):
            set_timeout(page_timeout_ms)
        set_navigation_timeout = getattr(page, "set_default_navigation_timeout", None)
        if callable(set_navigation_timeout):
            set_navigation_timeout(page_timeout_ms)

        allow_intercom = page_context.cognitive_engine is not None
        interception = await install_request_interception(
            page,
            url,
            allow_intercom=allow_intercom,
        )
        blocking_enabled = bool(interception.get("installed", False))
        anti_bot_headers = await apply_anti_bot_headers(page, url)
        anti_bot_delay = await apply_anti_bot_delay(page, url)

        nav_error: Exception | None = None
        nav_timeouts = [page_timeout_ms, max(4000, int(page_timeout_ms * 0.65))]
        for idx, nav_timeout in enumerate(nav_timeouts):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=nav_timeout)
                if idx > 0:
                    render_retry_used = True
                nav_error = None
                break
            except Exception as exc:
                nav_error = exc
                reason = classify_failure_reason(exc)
                logger.warning(
                    "State render navigation failure: %s",
                    {
                        "url": url,
                        "failure_stage": "render_navigation",
                        "degraded_reason": normalize_failure(reason).value,
                    },
                )
                if idx == 0 and reason in {"render_timeout", "extraction_failure"}:
                    continue
                break

        if nav_error is not None:
            reason = classify_failure_reason(nav_error)
            snapshot = await _snapshot_current_dom()
            return _partial_payload(reason, snapshot)

        try:
            effective_network_idle_ms = (
                max(2000, int(network_idle_timeout_ms * 0.75))
                if render_retry_used
                else network_idle_timeout_ms
            )
            effective_ready_timeout_ms = (
                max(1800, int(ready_state_timeout_ms * 0.75))
                if render_retry_used
                else ready_state_timeout_ms
            )
            detected_framework, hydration_status = await detect_framework_and_wait(
                page,
                network_idle_timeout_ms=effective_network_idle_ms,
                ready_state_timeout_ms=effective_ready_timeout_ms,
            )
        except Exception as exc:
            reason = classify_failure_reason(exc)
            logger.warning(
                "State hydration failure: %s",
                {
                    "url": url,
                    "failure_stage": "render_hydration",
                    "degraded_reason": normalize_failure(reason).value,
                },
            )
            snapshot = await _snapshot_current_dom()
            return _partial_payload(reason, snapshot)

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
                    "request_interception": interception,
                    "adaptive_timeout_policy": adaptive_timeouts,
                    "anti_bot_delay_ms": anti_bot_delay,
                    "anti_bot_headers": anti_bot_headers,
                    "actions_taken": 0,
                    "render_retry_used": render_retry_used,
                }

            html = await _snapshot_current_dom()
            return {
                "html": html,
                "hydration_status": "requires_auth",
                "detected_framework": detected_framework,
                "requires_auth": True,
                "auth_reason": auth_state.get("reason", "auth_wall"),
                "auth_fallback_used": False,
                "cookie_banner_dismissed": cookie_dismissed,
                "third_party_blocking_enabled": blocking_enabled,
                "request_interception": interception,
                "adaptive_timeout_policy": adaptive_timeouts,
                "anti_bot_delay_ms": anti_bot_delay,
                "anti_bot_headers": anti_bot_headers,
                "actions_taken": 0,
                "render_retry_used": render_retry_used,
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
        partial_reason = ""
        exploration_quality: dict[str, Any] = {
            "actions_taken": 0,
            "new_states": 0,
            "dom_change_ratio": 0.0,
            "early_stopped": False,
        }
        modal_checks: dict[str, Any] = {}

        if state == "after_interaction":
            try:
                route_result = await strategy_pack.trigger_route_change(page, detected_framework=detected_framework)
            except Exception as exc:
                partial_reason = classify_failure_reason(exc)
                logger.warning(
                    "State interaction route failure: %s",
                    {
                        "url": url,
                        "failure_stage": "interaction_route",
                        "degraded_reason": normalize_failure(partial_reason).value,
                    },
                )
                route_result = {"actions_taken": 0, "route_changes": 0}
            actions_taken += int(route_result.get("actions_taken", 0))

            remaining = max(0, int(cfg["interaction_budget_per_page"]) - actions_taken)
            try:
                modal_checks = await strategy_pack.trigger_modals(page, max_actions=remaining)
            except Exception as exc:
                if not partial_reason:
                    partial_reason = classify_failure_reason(exc)
                logger.warning(
                    "State interaction modal failure: %s",
                    {
                        "url": url,
                        "failure_stage": "interaction_modal",
                        "degraded_reason": normalize_failure(partial_reason).value,
                    },
                )
                modal_checks = {"actions_taken": 0, "modal_checks_run": 0}
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
            try:
                lazy_result = await strategy_pack.trigger_lazy_load(page, max_actions=int(cfg["scroll_steps"]))
            except Exception as exc:
                partial_reason = classify_failure_reason(exc)
                logger.warning(
                    "State interaction scroll failure: %s",
                    {
                        "url": url,
                        "failure_stage": "interaction_scroll",
                        "degraded_reason": normalize_failure(partial_reason).value,
                    },
                )
                lazy_result = {"actions_taken": 0, "growth_steps": 0, "infinite_scroll_detected": False}
            actions_taken += int(lazy_result.get("actions_taken", 0))
            growth_steps = int(lazy_result.get("growth_steps", 0))
            exploration_quality = {
                "actions_taken": actions_taken,
                "new_states": growth_steps,
                "dom_change_ratio": round(growth_steps / max(actions_taken, 1), 2),
                "early_stopped": actions_taken >= 2 and growth_steps == 0,
                "infinite_scroll_detected": bool(lazy_result.get("infinite_scroll_detected", False)),
            }

        html = await _snapshot_current_dom()
        if not html.strip():
            partial_reason = partial_reason or "extraction_failure"

        return {
            "html": html,
            "hydration_status": hydration_status,
            "detected_framework": detected_framework,
            "requires_auth": False,
            "cookie_banner_dismissed": cookie_dismissed,
            "third_party_blocking_enabled": blocking_enabled,
            "request_interception": interception,
            "adaptive_timeout_policy": adaptive_timeouts,
            "anti_bot_delay_ms": anti_bot_delay,
            "anti_bot_headers": anti_bot_headers,
            "actions_taken": actions_taken,
            "exploration_quality": exploration_quality,
            "modal_checks": modal_checks,
            "degraded_reason": normalize_failure(partial_reason).value if partial_reason else "",
            "partial_mode": bool(partial_reason),
            "render_retry_used": render_retry_used,
        }
    except Exception as exc:
        reason = classify_failure_reason(exc)
        logger.warning(
            "State provider fallback triggered: %s",
            {
                "url": url,
                "failure_stage": "state_provider",
                "degraded_reason": normalize_failure(reason).value,
            },
        )
        snapshot = await _snapshot_current_dom()
        return _partial_payload(reason, snapshot)
    finally:
        # Playwright may already have closed this page during browser teardown.
        try:
            await page.close()
        except Exception:
            pass


async def audit_page(url: str, scan_mode: str, page_context: PageContext) -> PageAuditResult:
    """Run multi-state page auditing and merge findings across discovered states."""
    try:
        scan_mode_key = normalize_scan_mode(scan_mode)
    except ValueError:
        scan_mode_key = "fast"

    state_sequence = ("initial",) if scan_mode_key == "fast" else _STATE_SEQUENCE
    state_provider = page_context.state_provider or _default_state_provider
    if not isinstance(page_context.cache, dict):
        page_context.cache = {}
    page_context.cache["scan_mode"] = scan_mode_key

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
    degraded_reasons: set[str] = set()
    hydration_status = "unknown"
    page_dom = ""

    for state in state_sequence:
        state_start = time.perf_counter()

        try:
            payload = await state_provider(url, state, page_context)
        except Exception as exc:
            degraded_mode = True
            reason = classify_failure_reason(exc)
            degraded_reasons.add(reason)
            logger.warning(
                "State provider exception: %s",
                {
                    "url": url,
                    "failure_stage": f"state_provider:{state}",
                    "degraded_reason": normalize_failure(reason).value,
                },
            )
            fallback_html = page_dom or str(page_context.cache.get("last_successful_dom", "") or "")
            payload = {
                "html": fallback_html,
                "hydration_status": "failed",
                "degraded_reason": normalize_failure(reason).value,
                "partial_mode": bool(fallback_html),
            }

        dom, state_hydration = _normalize_state_payload(payload)
        payload_data = payload if isinstance(payload, dict) else {}
        payload_reason = normalize_reason(payload_data.get("degraded_reason"))
        if payload_reason:
            degraded_mode = True
            degraded_reasons.add(payload_reason)
        elif payload_data.get("partial_mode"):
            degraded_mode = True
            degraded_reasons.add("extraction_failure")

        if state_hydration not in {"unknown", ""}:
            hydration_status = state_hydration
        if not page_dom and dom:
            page_dom = dom
        if isinstance(page_context.cache, dict) and dom:
            page_context.cache["last_successful_dom"] = dom

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
        except Exception as exc:
            static_issues = []
            degraded_mode = True
            reason = classify_failure_reason(exc)
            degraded_reasons.add(reason)
            logger.warning(
                "Static engine failed: %s",
                {
                    "url": url,
                    "failure_stage": f"static:{state}",
                    "degraded_reason": normalize_failure(reason).value,
                },
            )
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
                except Exception as exc:
                    degraded_mode = True
                    reason = classify_failure_reason(exc)
                    degraded_reasons.add(reason)
                    logger.warning(
                        "Interactive engine failed: %s",
                        {
                            "url": url,
                            "failure_stage": f"interactive:{state}",
                            "degraded_reason": normalize_failure(reason).value,
                        },
                    )
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
                except Exception as exc:
                    degraded_mode = True
                    reason = classify_failure_reason(exc)
                    degraded_reasons.add(reason)
                    logger.warning(
                        "Axe engine failed: %s",
                        {
                            "url": url,
                            "failure_stage": f"axe:{state}",
                            "degraded_reason": normalize_failure(reason).value,
                        },
                    )
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
                    except Exception as exc:
                        degraded_mode = True
                        reason = classify_failure_reason(exc)
                        degraded_reasons.add(reason)
                        logger.warning(
                            "Cognitive engine failed: %s",
                            {
                                "url": url,
                                "failure_stage": f"cognitive:{state}",
                                "degraded_reason": normalize_failure(reason).value,
                            },
                        )
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


    penalty = sum(
        float(SEVERITY_WEIGHTS.get(str(issue.get("severity") or "minor").lower(), 1.0))
        for issue in merged_issues.values()
        if bool(issue.get("scoring", True))
    )
    score = round(max(0.0, 100.0 - min(95.0, penalty)), 1)

    return PageAuditResult(
        url=url,
        score=score,
        issues=list(merged_issues.values()),
        engine_timings=engine_timings,
        degraded_mode=degraded_mode,
        degraded_reason=normalize_failure(_pick_degraded_reason(degraded_reasons)).value if degraded_reasons else "",
        skipped_engines=skipped_engines,
        hydration_status=hydration_status,
        enrichment_status="pending",
        states_meta=states_meta,
        page_dom=page_dom,
    )
