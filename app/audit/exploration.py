"""Exploration helpers for dynamic deep/max scanning states."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urljoin, urlparse


_MODAL_TRIGGER_TOKENS = ("modal", "popup", "overlay", "dialog")


def _is_internal_href(href: str, seed_url: str) -> bool:
    raw = (href or "").strip()
    if not raw or raw.startswith(("#", "javascript:", "mailto:", "tel:")):
        return False

    if raw.startswith("/"):
        return True

    target = urlparse(raw)
    if not target.scheme:
        return True

    seed = urlparse(seed_url)
    return bool(target.netloc and target.netloc == seed.netloc)


async def _safe_query_selector_all(page: Any, selector: str) -> list[Any]:
    try:
        values = await page.query_selector_all(selector)
        return values if isinstance(values, list) else []
    except Exception:
        return []


async def _safe_get_attribute(handle: Any, name: str) -> str:
    try:
        value = await handle.get_attribute(name)
        return value if isinstance(value, str) else ""
    except Exception:
        return ""


async def _safe_inner_text(handle: Any) -> str:
    try:
        value = await handle.inner_text()
        return value if isinstance(value, str) else ""
    except Exception:
        return ""


async def _safe_click(handle: Any) -> bool:
    try:
        await handle.click()
        return True
    except Exception:
        return False


async def _safe_wait(page: Any, timeout_ms: int) -> None:
    try:
        await page.wait_for_timeout(int(timeout_ms))
    except Exception:
        return


def _safe_current_url(page: Any) -> str:
    try:
        url = getattr(page, "url", "")
        return str(url or "")
    except Exception:
        return ""


async def _safe_content_hash(page: Any) -> str:
    try:
        content = await page.content()
    except Exception:
        return ""

    if not isinstance(content, str):
        return ""

    return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()[:16]


async def _modal_state(page: Any) -> dict[str, Any]:
    script = """
        () => {
            const dialog = document.querySelector(
                '[role="dialog"], dialog[open], .modal.show, .modal[open], [aria-modal="true"]'
            );
            if (!dialog) {
                return { open: false, focusInside: false, focusableCount: 0 };
            }

            const active = document.activeElement;
            const focusables = dialog.querySelectorAll(
                'a[href], button:not([disabled]), input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
            );

            return {
                open: true,
                focusInside: !!(active && dialog.contains(active)),
                focusableCount: focusables.length,
            };
        }
    """
    try:
        state = await page.evaluate(script)
        return state if isinstance(state, dict) else {"open": False, "focusInside": False, "focusableCount": 0}
    except Exception:
        return {"open": False, "focusInside": False, "focusableCount": 0}


async def _active_focus_descriptor(page: Any) -> str:
    script = """
        () => {
            const active = document.activeElement;
            if (!active) return '';
            const tag = (active.tagName || '').toLowerCase();
            const id = active.id ? `#${active.id}` : '';
            return `${tag}${id}`;
        }
    """
    try:
        value = await page.evaluate(script)
        return value if isinstance(value, str) else ""
    except Exception:
        return ""


async def _scroll_height(page: Any) -> int:
    try:
        value = await page.evaluate("() => (document.body ? document.body.scrollHeight : 0)")
        return int(value)
    except Exception:
        return 0


@dataclass(slots=True)
class SPAStrategyPack:
    """Bounded interaction strategy pack for route/modal/lazy-load exploration."""

    seed_url: str
    interaction_budget: int = 5
    max_route_clicks: int = 3
    route_settle_ms: int = 1000
    scroll_wait_ms: int = 1000
    lazy_scroll_steps: int = 3

    async def trigger_route_change(
        self,
        page: Any,
        detected_framework: Optional[str] = None,
        *,
        max_actions: Optional[int] = None,
    ) -> dict[str, Any]:
        budget = max(0, int(max_actions if max_actions is not None else min(self.interaction_budget, self.max_route_clicks)))
        if budget == 0:
            return {"actions_taken": 0, "route_changes": 0, "visited_urls": []}

        route_changes = 0
        actions_taken = 0
        visited_urls: list[str] = []

        handles = await _safe_query_selector_all(page, "a[href], button[data-router-link], [role='link']")
        for handle in handles:
            if actions_taken >= budget:
                break

            href = await _safe_get_attribute(handle, "href")
            if href and not _is_internal_href(href, self.seed_url):
                continue

            before_url = _safe_current_url(page)
            before_hash = await _safe_content_hash(page)
            clicked = await _safe_click(handle)
            if not clicked:
                continue

            actions_taken += 1
            await _safe_wait(page, self.route_settle_ms)
            after_url = _safe_current_url(page)
            after_hash = await _safe_content_hash(page)

            changed = bool(after_url and after_url != before_url)
            if not changed and before_hash and after_hash:
                changed = before_hash != after_hash

            if changed:
                route_changes += 1
                if after_url:
                    visited_urls.append(after_url)

        return {
            "actions_taken": actions_taken,
            "route_changes": route_changes,
            "visited_urls": list(dict.fromkeys(visited_urls)),
            "framework": detected_framework,
        }

    async def trigger_modals(self, page: Any, *, max_actions: Optional[int] = None) -> dict[str, Any]:
        budget = max(0, int(max_actions if max_actions is not None else self.interaction_budget))
        if budget == 0:
            return {
                "actions_taken": 0,
                "modal_checks_run": 0,
                "focus_trap_missing": False,
                "focus_return_missing": False,
            }

        actions_taken = 0
        modal_checks_run = 0
        focus_trap_missing = False
        focus_return_missing = False

        handles = await _safe_query_selector_all(page, "button, a, [aria-haspopup='dialog'], [aria-controls]")
        for handle in handles:
            if actions_taken >= budget:
                break

            has_dialog_popup = (await _safe_get_attribute(handle, "aria-haspopup")).lower() == "dialog"
            has_controls = bool((await _safe_get_attribute(handle, "aria-controls")).strip())
            text = (await _safe_inner_text(handle)).lower()
            token_match = any(token in text for token in _MODAL_TRIGGER_TOKENS)

            if not (has_dialog_popup or has_controls or token_match):
                continue

            focus_before = await _active_focus_descriptor(page)
            clicked = await _safe_click(handle)
            if not clicked:
                continue

            actions_taken += 1
            await _safe_wait(page, 150)

            state = await _modal_state(page)
            if not state.get("open"):
                continue

            modal_checks_run += 1
            if not state.get("focusInside") or int(state.get("focusableCount", 0)) <= 0:
                focus_trap_missing = True

            keyboard = getattr(page, "keyboard", None)
            if keyboard is not None and hasattr(keyboard, "press"):
                try:
                    await keyboard.press("Tab")
                except Exception:
                    pass

            await _safe_wait(page, 80)
            after_tab = await _modal_state(page)
            if after_tab.get("open") and not after_tab.get("focusInside"):
                focus_trap_missing = True

            if keyboard is not None and hasattr(keyboard, "press"):
                try:
                    await keyboard.press("Escape")
                except Exception:
                    pass

            await _safe_wait(page, 120)
            after_escape = await _modal_state(page)
            focus_after = await _active_focus_descriptor(page)
            if after_escape.get("open") or (focus_before and focus_after and focus_before != focus_after):
                focus_return_missing = True

        return {
            "actions_taken": actions_taken,
            "modal_checks_run": modal_checks_run,
            "focus_trap_missing": focus_trap_missing,
            "focus_return_missing": focus_return_missing,
        }

    async def trigger_lazy_load(self, page: Any, *, max_actions: Optional[int] = None) -> dict[str, Any]:
        budget = max(0, int(max_actions if max_actions is not None else self.interaction_budget))
        if budget == 0:
            return {"actions_taken": 0, "growth_steps": 0, "infinite_scroll_detected": False}

        actions_taken = 0
        growth_steps = 0
        scroll_points = [33, 66, 100][: max(1, min(self.lazy_scroll_steps, 3))]

        for percent in scroll_points:
            if actions_taken >= budget:
                break

            before_height = await _scroll_height(page)
            await _safe_wait(page, 40)
            try:
                await page.evaluate(
                    f"window.scrollTo(0, Math.floor(document.body.scrollHeight * {percent / 100.0}))"
                )
            except Exception:
                try:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                except Exception:
                    pass

            actions_taken += 1
            await _safe_wait(page, self.scroll_wait_ms)
            after_height = await _scroll_height(page)
            if after_height > before_height:
                growth_steps += 1

        return {
            "actions_taken": actions_taken,
            "growth_steps": growth_steps,
            "infinite_scroll_detected": growth_steps > 0,
        }

    async def run_exploration(self, page: Any, detected_framework: Optional[str] = None) -> dict[str, Any]:
        remaining_budget = max(0, int(self.interaction_budget))

        route_result = await self.trigger_route_change(
            page,
            detected_framework,
            max_actions=min(remaining_budget, self.max_route_clicks),
        )
        remaining_budget = max(0, remaining_budget - int(route_result.get("actions_taken", 0)))

        modal_result = await self.trigger_modals(page, max_actions=remaining_budget)
        remaining_budget = max(0, remaining_budget - int(modal_result.get("actions_taken", 0)))

        lazy_result = await self.trigger_lazy_load(page, max_actions=remaining_budget)

        actions_taken = int(route_result.get("actions_taken", 0))
        actions_taken += int(modal_result.get("actions_taken", 0))
        actions_taken += int(lazy_result.get("actions_taken", 0))

        new_states = int(route_result.get("route_changes", 0))
        if int(modal_result.get("modal_checks_run", 0)) > 0:
            new_states += 1
        new_states += int(lazy_result.get("growth_steps", 0))

        dom_change_ratio = round(new_states / max(actions_taken, 1), 2)
        early_stopped = actions_taken >= 2 and new_states == 0

        return {
            "exploration_quality": {
                "actions_taken": actions_taken,
                "new_states": new_states,
                "dom_change_ratio": dom_change_ratio,
                "early_stopped": early_stopped,
            },
            "route_change": route_result,
            "modal": modal_result,
            "lazy_load": lazy_result,
        }


def auth_fallback_urls(seed_url: str) -> list[str]:
    parsed = urlparse(seed_url)
    if parsed.scheme and parsed.netloc:
        base = f"{parsed.scheme}://{parsed.netloc}"
    else:
        base = seed_url.rstrip("/")
    paths = ("/about", "/explore", "/features", "/pricing")
    return [urljoin(f"{base}/", path.lstrip("/")) for path in paths]
