# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import pytest


@pytest.fixture(autouse=True)
def _reset_sse_app_status():
    try:
        from sse_starlette.sse import AppStatus
    except ImportError:  # internals moved in a newer sse-starlette; nothing to reset
        yield
        return
    if hasattr(AppStatus, "should_exit_event"):
        AppStatus.should_exit_event = None
    yield


@pytest.fixture(autouse=True)
def _fresh_repo_lock(monkeypatch):
    """app.repos.repo_lock is process-wide; an asyncio.Lock binds to the first loop that waits on it, and each
    test runs in its own loop, so every test gets a fresh one."""
    import asyncio

    from app import repos
    monkeypatch.setattr(repos, "repo_lock", asyncio.Lock())
