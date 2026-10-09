# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import asyncio
import shutil

import pytest

from app.config import Settings
from app.engine.run import JobFailed, run_job
from app.models import JobOptions, JobRequest, StopReason
from tests.fakes import FakeLLM, snippet
from tests.integration.conftest import FIXTURES

pytestmark = pytest.mark.integration

FULL = """func TestAbs(t *testing.T) {
	if Abs(-3) != 3 || Abs(2) != 2 {
		t.Fatal("abs")
	}
}

func TestSqrt(t *testing.T) {
	cases := []struct {
		name string
		in   int
		want int
		err  error
	}{
		{"negative", -1, 0, ErrNegative},
		{"zero", 0, 0, nil},
		{"perfect", 9, 3, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Sqrt(tc.in)
			if got != tc.want || !errors.Is(err, tc.err) {
				t.Fatalf("Sqrt(%d) = %d, %v", tc.in, got, err)
			}
		})
	}
}"""


def settings_for(tmp_path, fixture: str) -> Settings:
    repos = tmp_path / "repos"
    repos.mkdir()
    shutil.copytree(FIXTURES / fixture, repos / fixture)
    return Settings(repos_dir=repos, work_dir=tmp_path / "work", output_dir=tmp_path / "output")


async def test_full_run_reaches_target_with_fake_llm(tmp_path):
    settings = settings_for(tmp_path, "gomod")
    events = []

    async def emit(t, d):
        events.append(t)

    llm = FakeLLM([snippet(FULL, imports=["testing", "errors"])])
    summary = await run_job("j1", JobRequest(repo_path="gomod", target_coverage=90), settings, llm, emit,
                            asyncio.Event(), lambda: [])
    assert summary.stop_reason is StopReason.TARGET_REACHED, summary
    assert summary.final_percent == 100.0
    assert (settings.output_dir / "j1" / "tests" / "calc_test.go").exists()
    assert events[:2] == ["workspace_ready", "baseline_measured"]


async def test_broken_repo_fails_fast(tmp_path):
    settings = settings_for(tmp_path, "broken")

    async def emit(t, d): pass

    with pytest.raises(JobFailed) as exc:
        await run_job("j2", JobRequest(repo_path="broken"), settings, FakeLLM([]), emit, asyncio.Event(), lambda: [])
    assert exc.value.reason == "repo_does_not_build"
    assert "broken.go" in exc.value.output
    assert (settings.output_dir / "j2" / "events.jsonl").exists()


async def _fail_reason(tmp_path, fixture, **request):
    settings = settings_for(tmp_path, fixture)

    async def emit(t, d): pass

    with pytest.raises(JobFailed) as exc:
        await run_job("j3", JobRequest(repo_path=fixture, **request), settings, FakeLLM([]), emit, asyncio.Event(),
                      lambda: [])
    return exc.value


async def test_vet_failing_repo_is_rejected(tmp_path):
    assert (await _fail_reason(tmp_path, "vetfail")).reason == "repo_vet_fails"


async def test_existing_failing_tests_are_reported(tmp_path):
    failed = await _fail_reason(tmp_path, "failingtests", options=JobOptions(delete_existing_tests=False))
    assert failed.reason == "existing_tests_fail"


async def test_everything_excluded_means_no_packages(tmp_path):
    failed = await _fail_reason(tmp_path, "gomod", options=JobOptions(exclude_patterns=["*"]))
    assert failed.reason == "no_packages"
