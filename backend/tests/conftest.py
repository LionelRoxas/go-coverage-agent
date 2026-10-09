# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
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
