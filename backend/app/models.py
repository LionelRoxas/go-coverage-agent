# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Types shared across the backend. Pydantic for anything serialized; dataclass for hot internals."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FuncKey(BaseModel):
    """Unique identity of a function: (file, receiver, name). `Mean` != `Float64Data.Mean`."""

    model_config = ConfigDict(frozen=True)
    file: str
    receiver: str = ""
    name: str

    def label(self) -> str:
        return f"{self.receiver}.{self.name}" if self.receiver else self.name


class FuncInfo(BaseModel):
    key: FuncKey
    package: str
    start_line: int
    end_line: int
    exported: bool


@dataclass(frozen=True)
class Block:
    file: str  # module-relative, e.g. "mean.go" or "sub/x.go"
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    statements: int

    @property
    def id(self) -> str:
        return f"{self.file}:{self.start_line}.{self.start_col},{self.end_line}.{self.end_col}"


class FuncCoverage(BaseModel):
    key: FuncKey
    statements: int
    covered: int
    uncovered_lines: list[tuple[int, int]] = Field(default_factory=list)

    @property
    def uncovered(self) -> int:
        return self.statements - self.covered


class FileCoverage(BaseModel):
    file: str
    statements: int
    covered: int
    percent: float


class CoverageReport(BaseModel):
    total_statements: int
    covered_statements: int
    percent: float
    files: list[FileCoverage]
    functions: list[FuncCoverage]
    covered_block_ids: list[str]

    def covered_set(self) -> frozenset[str]:
        return frozenset(self.covered_block_ids)

    def public(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"covered_block_ids"})


class PlanItem(BaseModel):
    file: str
    functions: list[FuncKey]
    uncovered_statements: int


# --- LLM I/O. Strict-schema friendly: every field required, no defaults. ---
class TestScenario(BaseModel):
    __test__ = False  # stop pytest from collecting this class
    scenario: str = Field(description="One behaviour being tested, e.g. 'empty input returns EmptyInputErr'")
    target: str = Field(description="Function label being tested, e.g. 'Mean' or 'Float64Data.Mean'")


class SuspectedBug(BaseModel):
    function: str
    description: str


class TestSnippet(BaseModel):
    __test__ = False
    test_plan: list[TestScenario] = Field(description="What you decided to test and why, one entry per scenario")
    # suspected_bugs comes before code, so the strict schema asks for the claims first and the code can leave
    # those cases out (the prompts' rule: never assert behaviour you report in suspected_bugs)
    suspected_bugs: list[SuspectedBug] = Field(description="Behaviour that looks wrong in the source; empty if none")
    imports: list[str] = Field(description="Import paths the new code needs, e.g. ['testing', 'math']")
    code: str = Field(description="ONLY new top-level Go declarations: Test functions and helpers. No package clause, no imports.")


# --- End-of-run AI summary (strict schema: every field required) ---
class BusinessSummary(BaseModel):
    headline: str = Field(description="One sentence: the outcome in plain words")
    outcome: str = Field(description="Short paragraph: what the run achieved against the goal")
    efficiency: str = Field(description="Short paragraph: time, tokens and, when given, cost for the gain")
    risks: list[str] = Field(description="Short plain-language risks or limits; empty if none")
    recommendation: str = Field(description="One or two sentences: what the stakeholder should do next")


class SummaryGap(BaseModel):
    file: str = Field(description="A source file name from the facts")
    detail: str = Field(description="What is still untested there, from the facts")


class TechnicalSummary(BaseModel):
    headline: str = Field(description="One sentence for engineers: the coverage change and where the tests are")
    what_was_tested: str = Field(description="Short paragraph: which files and areas the new tests exercise")
    where_tests_live: str = Field(description="Where the generated test files are and how to bring them into the repo")
    gaps: list[SummaryGap] = Field(description="Least-covered files and what remains; empty if none")
    suspected_bugs: list[str] = Field(description="Suspected bugs exactly as reported in the facts; empty if none")
    rejected_or_failed: str = Field(description="Short paragraph: rejected targets, fixes, repairs and pruned tests")
    how_to_run: str = Field(description="The commands to run the tests")
    next_steps: list[str] = Field(description="Concrete next steps for the receiving team")


class RunSummary(BaseModel):
    business: BusinessSummary
    technical: TechnicalSummary


# --- Jobs ---
class JobOptions(BaseModel):
    max_iterations: int = Field(20, ge=1, le=30)
    min_gain: float = Field(1.0, ge=0, le=10)
    patience: int = Field(2, ge=1, le=5)
    targets_per_iteration: int = Field(3, ge=1, le=5)
    max_fix_attempts: int = Field(2, ge=0, le=4)
    delete_existing_tests: bool = True
    max_llm_tokens: int = Field(1_000_000, ge=10_000, le=2_000_000)
    exclude_patterns: list[str] = Field(default_factory=lambda: ["examples/**", "testdata/**"])
    write_summary: bool = True  # an LLM-written business + technical summary after the run
    # PARALLEL_WRITERS, set by the server from its settings (any value sent by a client is replaced); recorded here so
    # each run says whether its writer requests went out together.
    parallel_writers: bool = False


class JobRequest(BaseModel):
    repo_path: str = Field(min_length=1)
    target_coverage: float = Field(80, ge=1, le=100)
    options: JobOptions = Field(default_factory=JobOptions)


class StopReason(StrEnum):
    TARGET_REACHED = "target_reached"
    MARGINAL_GAINS = "marginal_gains"
    MAX_ITERATIONS = "max_iterations"
    NO_REMAINING_TARGETS = "no_remaining_targets"
    BUDGET_EXHAUSTED = "budget_exhausted"
    CANCELLED = "cancelled"
    LLM_UNAVAILABLE = "llm_unavailable"  # Groq unreachable (timeouts, 5xx, connection errors) past the outage window


class JobStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"  # a run reloaded from ./output with no terminal event: the app stopped mid-run


class Event(BaseModel):
    seq: int
    ts: float
    type: str
    data: dict[str, Any]


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def add(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(prompt_tokens=self.prompt_tokens + other.prompt_tokens,
                          completion_tokens=self.completion_tokens + other.completion_tokens)


class IterationRecord(BaseModel):
    index: int
    start_percent: float
    end_percent: float
    accepted: int
    rejected: int
    deferred: int = 0  # items that met a Groq outage: neither accepted nor rejected, planned again later


class Disagreement(BaseModel):
    """A new test that failed because the value the model predicted and the value the code returned differ; at that
    point it was pruned (or, when every new test failed, sent to the Fixer). Either may be wrong; it is reported for
    a person to look at, not as a bug."""
    file: str  # the target source file
    functions: list[str]  # the planned functions of the item
    test: str  # the removed top-level Test function
    lines: list[str] = Field(default_factory=list)  # its first got/want (or panic) lines from `go test`, clipped
    pruned: bool = True  # removed so the rest could be kept; False: every new test failed and all went to the Fixer
    # what became of the candidate: "kept" (the accepted code has a test of this name, rewritten after it failed:
    # it may now expect the code's value), "dropped" (accepted without it), "not_accepted"; "" in older reports
    outcome: str = ""


class FileDelta(BaseModel):
    file: str
    before: float
    after: float


class Summary(BaseModel):
    stop_reason: StopReason
    message: str
    target: float
    baseline_percent: float
    final_percent: float
    iterations: list[IterationRecord]
    test_files: list[str]
    tests_added: list[str]
    suspected_bugs: list[SuspectedBug]
    # failing new tests pruned or sent to the Fixer during the run (older reports lack it); never confirmed bugs
    disagreements: list[Disagreement] = Field(default_factory=list)
    per_file: list[FileDelta]
    tokens: TokenUsage
    duration_s: float
