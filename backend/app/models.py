# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
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
    imports: list[str] = Field(description="Import paths the new code needs, e.g. ['testing', 'math']")
    code: str = Field(description="ONLY new top-level Go declarations: Test functions and helpers. No package clause, no imports.")
    suspected_bugs: list[SuspectedBug] = Field(description="Behaviour that looks wrong in the source; empty if none")


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


class JobStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


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
    per_file: list[FileDelta]
    tokens: TokenUsage
    duration_s: float
