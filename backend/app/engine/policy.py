# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
from __future__ import annotations

from dataclasses import dataclass

from app.models import JobRequest, StopReason


@dataclass
class StopPolicy:
    target: float
    min_gain: float
    patience: int

    def target_reached(self, percent: float) -> bool:
        return percent + 1e-9 >= self.target

    def marginal(self, gains: list[float]) -> bool:
        return len(gains) >= self.patience and all(g < self.min_gain for g in gains[-self.patience:])


def stop_message(reason: StopReason, request: JobRequest, detail: str = "") -> str:
    o = request.options
    target = f"{request.target_coverage:g}"
    text = {
        StopReason.TARGET_REACHED: f"Reached the {target}% coverage target.",
        StopReason.MARGINAL_GAINS: f"Stopped early: the last {o.patience} iterations each added less than {o.min_gain:g} percentage points.",
        StopReason.MAX_ITERATIONS: f"Stopped after the maximum of {o.max_iterations} iterations.",
        StopReason.NO_REMAINING_TARGETS: "Stopped: every remaining uncovered function was attempted without success or is too large for one request.",
        StopReason.BUDGET_EXHAUSTED: "Stopped: the LLM token budget ran out. Accepted tests were kept.",
        StopReason.CANCELLED: "Cancelled. Accepted tests were kept.",
    }[reason]
    return f"{text} {detail}".strip() if detail else text
