# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""HOST_REPOS_DIR is mounted read-only at /host-repos. Run with the fixtures mounted there, as `make test-integration`
does: docker run -v "<repo>/backend/tests/fixtures:/host-repos:ro" <image> uv run --no-sync pytest -m integration"""
import asyncio
import errno

import pytest

from app.config import Settings
from app.engine.run import run_job
from app.models import JobRequest, StopReason
from tests.fakes import FakeLLM, snippet
from tests.integration.test_run_job import FULL

pytestmark = pytest.mark.integration

HOST = Settings().host_repos_dir


@pytest.fixture(autouse=True)
def _needs_mount():
    if not (HOST / "gomod" / "go.mod").is_file():
        pytest.skip(f"mount backend/tests/fixtures at {HOST} (read-only) to run")


def test_writing_to_host_repos_fails_read_only():
    with pytest.raises(OSError) as exc:
        (HOST / "gomod" / "probe.txt").write_text("x")
    assert exc.value.errno == errno.EROFS


async def test_run_on_a_host_repo_works_on_a_copy(tmp_path):
    settings = Settings(repos_dir=tmp_path / "repos", work_dir=tmp_path / "work", output_dir=tmp_path / "output")
    before = sorted(p.name for p in (HOST / "gomod").iterdir())

    async def emit(t, d): pass

    llm = FakeLLM([snippet(FULL, imports=["testing", "errors"])])
    summary = await run_job("h1", JobRequest(repo_path="host/gomod", target_coverage=90), settings, llm, emit,
                            asyncio.Event(), lambda: [])
    assert summary.stop_reason is StopReason.TARGET_REACHED, summary
    assert (settings.output_dir / "h1" / "tests" / "calc_test.go").is_file()
    assert sorted(p.name for p in (HOST / "gomod").iterdir()) == before
