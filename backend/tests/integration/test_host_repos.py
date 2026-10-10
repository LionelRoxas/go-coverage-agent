# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""HOST_REPOS_DIR is mounted read-only at /host-repos. Run the way compose runs the backend: with the fixtures mounted
there and .env.example as the env file (it sets HOST_REPOS_DIR to a host-side path), as `make test-integration` does:
docker run --env-file .env.example -v "<repo>/backend/tests/fixtures:/host-repos:ro" <image> uv run --no-sync pytest -m integration"""
import asyncio
import errno
import os
from pathlib import Path

import pytest

from app.config import Settings
from app.engine.run import run_job
from app.models import JobRequest, StopReason
from tests.fakes import FakeLLM, snippet
from tests.integration.test_run_job import FULL

pytestmark = pytest.mark.integration

MOUNT = Path("/host-repos")  # where compose mounts HOST_REPOS_DIR; deliberately not read from Settings


@pytest.fixture(autouse=True)
def _needs_mount():
    if not (MOUNT / "gomod" / "go.mod").is_file():
        pytest.skip(f"mount backend/tests/fixtures at {MOUNT} (read-only) to run")


def listing(root: Path) -> list[tuple[str, int, int]]:
    return sorted((p.relative_to(root).as_posix(), p.stat().st_size, p.stat().st_mtime_ns)
                  for p in root.rglob("*"))


def test_settings_find_the_mount_even_with_compose_style_host_repos_dir():
    if "HOST_REPOS_DIR" not in os.environ:
        pytest.skip("run with --env-file .env.example (it sets HOST_REPOS_DIR, as compose's env_file does)")
    assert not os.environ["HOST_REPOS_DIR"].startswith("/host-repos")
    assert Settings().host_repos_mount == MOUNT


def test_writing_to_host_repos_fails_read_only():
    with pytest.raises(OSError) as exc:
        (MOUNT / "gomod" / "probe.txt").write_text("x")
    assert exc.value.errno == errno.EROFS


async def test_run_on_a_host_repo_works_on_a_copy(tmp_path):
    settings = Settings(repos_dir=tmp_path / "repos", work_dir=tmp_path / "work", output_dir=tmp_path / "output")
    before = listing(MOUNT / "gomod")

    async def emit(t, d): pass

    llm = FakeLLM([snippet(FULL, imports=["testing", "errors"])])
    summary = await run_job("h1", JobRequest(repo_path="host/gomod", target_coverage=90), settings, llm, emit,
                            asyncio.Event(), lambda: [])
    assert summary.stop_reason is StopReason.TARGET_REACHED, summary
    assert (settings.output_dir / "h1" / "tests" / "calc_test.go").is_file()
    assert listing(MOUNT / "gomod") == before
