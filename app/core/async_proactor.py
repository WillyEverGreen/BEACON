"""
Utility to safely run asyncio coroutines requiring Windows ProactorEventLoop (such as subprocesses/Playwright)
even when the main thread event loop is a SelectorEventLoop (common in uvicorn on Windows).
"""
import asyncio
import sys
from typing import Any, TypeVar

T = TypeVar("T")


def _run_in_proactor_thread(coro_factory, *args, **kwargs) -> Any:
    """Creates a new thread, instantiates ProactorEventLoop on Windows, runs the coroutine, and returns the result."""
    loop = asyncio.ProactorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro_factory(*args, **kwargs))
    finally:
        try:
            # Clean up pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        finally:
            loop.close()


async def run_subprocess_safe(coro_factory, *args, **kwargs) -> Any:
    """
    Executes an async function that creates subprocesses (Playwright, Node scripts, etc.).
    If running on Windows and the current loop does not support subprocess_exec (i.e. SelectorEventLoop),
    offloads execution to a background worker thread with a ProactorEventLoop.
    """
    if sys.platform == "win32":
        try:
            current_loop = asyncio.get_running_loop()
            # Check if current loop is SelectorEventLoop
            if not isinstance(current_loop, asyncio.ProactorEventLoop):
                return await asyncio.to_thread(_run_in_proactor_thread, coro_factory, *args, **kwargs)
        except RuntimeError:
            pass

    # If we already have a ProactorEventLoop or we're on Unix/Linux/macOS, run directly
    return await coro_factory(*args, **kwargs)
