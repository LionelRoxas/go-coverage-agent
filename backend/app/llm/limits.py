# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""Client-side pacing for Groq's tokens-per-minute limit and a local tokens-per-day ledger."""
from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Mapping

_DUR = re.compile(r"(?P<v>\d+(?:\.\d+)?)(?P<u>ms|h|m|s)")
_UNIT = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}


def parse_duration(text: str) -> float:
    return sum(float(m["v"]) * _UNIT[m["u"]] for m in _DUR.finditer(text or ""))


class RateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._remaining: int | None = None
        self._reset_at = 0.0

    def update(self, headers: Mapping[str, str]) -> None:
        remaining = headers.get("x-ratelimit-remaining-tokens")
        if remaining is None:
            return
        try:
            self._remaining = int(float(remaining))
        except ValueError:
            return
        reset = headers.get("x-ratelimit-reset-tokens")
        self._reset_at = self._clock() + (parse_duration(reset) if reset else 60.0)

    def wait_needed(self, tokens: int) -> float:
        if self._remaining is None or self._remaining >= tokens:
            return 0.0
        wait = self._reset_at - self._clock()
        if wait <= 0:
            self.reset()
            return 0.0
        return wait

    def reset(self) -> None:
        self._remaining = None


class UsageLedger:
    def __init__(self, path: Path, daily_budget: int, today: Callable[[], str] | None = None):
        self.path = path
        self.daily_budget = daily_budget
        self._today = today or (lambda: datetime.now(UTC).date().isoformat())

    def _load(self) -> dict[str, int]:
        try:
            data = json.loads(self.path.read_text())
            return {k: int(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def used_today(self) -> int:
        return self._load().get(self._today(), 0)

    def remaining(self) -> int:
        return max(0, self.daily_budget - self.used_today())

    def add(self, tokens: int) -> None:
        day = self._today()
        data = {day: self._load().get(day, 0) + tokens}  # keep only today; old days are irrelevant
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data))
