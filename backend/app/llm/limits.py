# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Client-side pacing for Groq's tokens-per-minute limit and a local tokens-per-day ledger."""
from __future__ import annotations

import asyncio
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
    """Shared by every call. Calls in flight at the same time (PARALLEL_WRITERS) keep the pacing: each holds its
    reservation (`begin`/`end`) until it is answered, so others see the headroom it may still use; a 429 pauses
    everyone for its Retry-After (`pause`), and until a request succeeds again only one call at a time is sent
    (`probe`), so the waiting calls do not all retry at once."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._remaining: int | None = None
        self._reset_at = 0.0
        self.limit_tokens: int | None = None
        self._inflight = 0  # tokens reserved by requests sent and not answered yet
        self._paused_until = 0.0
        self.probing = False  # after a 429, until a request succeeds
        self.probe = asyncio.Lock()  # held by the one call sent while probing

    def update(self, headers: Mapping[str, str]) -> None:
        limit = headers.get("x-ratelimit-limit-tokens")
        if limit is not None:
            try:
                self.limit_tokens = int(float(limit))
            except ValueError:
                pass
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
        if self.paused():
            return self._paused_until - self._clock()
        if self._remaining is None or self._remaining - self._inflight >= tokens:
            return 0.0
        wait = self._reset_at - self._clock()
        if wait <= 0:
            self.reset()
            return 0.0
        return wait

    def reset(self) -> None:
        self._remaining = None

    def begin(self, tokens: int) -> None:
        """A request is about to be sent (call right after `wait_needed` returned 0, with no await in between)."""
        self._inflight += tokens

    def end(self, tokens: int) -> None:
        self._inflight -= tokens

    def paused(self) -> bool:
        return self._paused_until > 0 and self._paused_until > self._clock()

    def pause(self, seconds: float) -> float:
        """A 429 asked to wait `seconds`: nobody sends until then. Returns the pause's end, for `resume`."""
        self._paused_until = max(self._paused_until, self._clock() + seconds)
        self.probing = True
        return self._paused_until

    def resume(self, until: float) -> None:
        """The caller that set the pause ending at `until` has waited it out (unless a later 429 extended it)."""
        if self._paused_until <= until:
            self._paused_until = 0.0

    def recovered(self) -> None:
        """A request succeeded: calls may be sent together again."""
        self.probing = False


class UsageLedger:
    def __init__(self, path: Path, daily_budget: int, today: Callable[[], str] | None = None):
        self.path = path
        self.daily_budget = daily_budget
        self._today = today or (lambda: datetime.now(UTC).date().isoformat())
        self.reserved = 0  # tokens reserved by calls in flight (released when each ends; what Groq billed is added)

    def try_reserve(self, tokens: int) -> bool:
        """Check and reserve in one step (no await): concurrent calls can never jointly pass the same headroom."""
        if self.remaining() - self.reserved < tokens:
            return False
        self.reserved += tokens
        return True

    def release(self, tokens: int) -> None:
        self.reserved -= tokens

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
