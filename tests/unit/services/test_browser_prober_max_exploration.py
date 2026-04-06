import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from app.services.browser_probes import BrowserProber


class _FakePage:
    url = "https://example.com/login"


@pytest.mark.asyncio
async def test_max_exploration_runs_login_fallback_and_marks_phases(monkeypatch):
    async def _fake_detect_login_wall(page, current_url=""):
        return {"requires_auth": True, "reason": "login"}

    async def _fake_attempt_fallback(page, seed_url, max_attempts=4):
        return {
            "used": True,
            "fallback_url": "https://example.com/about",
            "html": "<html><body><main>public</main></body></html>",
            "checked_urls": ["https://example.com/about"],
        }

    async def _fake_dismiss_cookie_banner(page, settle_ms=800):
        return True

    class _FakePack:
        def __init__(self, *args, **kwargs):
            pass

        async def run_exploration(self, page, detected_framework=None):
            return {
                "exploration_quality": {
                    "actions_taken": 3,
                    "new_states": 2,
                    "dom_change_ratio": 0.67,
                    "early_stopped": False,
                },
                "route_change": {"actions_taken": 1, "route_changes": 1},
                "modal": {"actions_taken": 1, "modal_checks_run": 1},
                "lazy_load": {"actions_taken": 1, "growth_steps": 1, "infinite_scroll_detected": True},
            }

    import app.audit.dynamic_handling as dynamic_handling
    import app.audit.exploration as exploration

    monkeypatch.setattr(dynamic_handling, "detect_login_wall", _fake_detect_login_wall)
    monkeypatch.setattr(dynamic_handling, "attempt_public_fallback_scan", _fake_attempt_fallback)
    monkeypatch.setattr(dynamic_handling, "dismiss_cookie_banner", _fake_dismiss_cookie_banner)
    monkeypatch.setattr(exploration, "SPAStrategyPack", _FakePack)

    prober = BrowserProber("https://example.com")
    meta = await prober._run_max_exploration(_FakePage(), framework="react")

    assert meta["login_wall_detected"] is True
    assert meta["auth_fallback_attempted"] is True
    assert meta["auth_fallback_used"] is True
    assert meta["auth_fallback_url"] == "https://example.com/about"
    assert bool(meta["fallback_html"])
    assert meta["interaction_phase_ran"] is True
    assert meta["scroll_phase_ran"] is True
    assert meta["exploration_layer_ran"] is True
