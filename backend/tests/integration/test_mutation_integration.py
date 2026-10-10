# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Run mutation test with real Go: a strong test catches its mutant, a weak one lets its mutant survive."""
import asyncio

import pytest

from app.models import JobRequest
from app.mutation import run_mutation
from tests.integration.conftest import FIXTURES
from tests.integration.test_run_job import settings_for

pytestmark = pytest.mark.integration

KEPT = """package mut

import "testing"

func TestAdd(t *testing.T) {
	if Add(2, 3) != 5 {
		t.Fatal("Add")
	}
}

func TestIsAdult(t *testing.T) {
	if !IsAdult(30) { // weak: never checks the boundary at 18
		t.Fatal("IsAdult")
	}
}
"""


async def test_weak_test_lets_its_mutant_survive(tmp_path):
    settings = settings_for(tmp_path, "mutation")
    tests = settings.output_dir / "j" / "tests"
    tests.mkdir(parents=True)
    (tests / "mut_test.go").write_text(KEPT)
    events = []

    async def emit(t, d):
        events.append((t, d))

    r = await run_mutation("j", JobRequest(repo_path="mutation"), settings, emit, asyncio.Event())
    assert events[0] == ("mutation_started", {"total": 2})
    assert [(m["line"], m["original"], m["mutated"], m["status"]) for m in r["mutants"]] == [
        (7, "+", "-", "killed"), (12, ">=", ">", "survived")]
    assert (r["mutants"][1]["before"], r["mutants"][1]["after"]) == ("return age >= 18", "return age > 18")
    assert (r["killed"], r["survived"], r["invalid"], r["timeouts"], r["score"]) == (1, 1, 0, 0, 50.0)
    assert r["per_file"] == [{"file": "mut.go", "killed": 1, "survived": 1, "score": 50.0}]
    assert not (settings.work_dir / "j-mutation").exists()
    assert (settings.repos_dir / "mutation" / "mut.go").read_text() == (FIXTURES / "mutation" / "mut.go").read_text()
