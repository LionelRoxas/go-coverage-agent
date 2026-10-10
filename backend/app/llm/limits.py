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
    (`probe`), so the waiting calls do not all retry at once. A caller that waited checks again before sending
    (`waited`, then `wait_needed`): a window that has passed rolls over to the key's full limit instead of being
    forgotten, so callers waking together still share the headroom one reservation at a time."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._remaining: int | None = None
        self._reset_at = 0.0
        self.limit_tokens: int | None = None
        self._inflight = 0  # tokens reserved by requests sent and not answered yet
        self._rolled = False  # the headroom is an assumed fresh window (rolled over), not one Groq reported
        self._paused_until = 0.0
        self.probing = False  # after a 429, until a request succeeds
        self.probe = asyncio.Lock()  # held by the one call sent while probing
        self._changed = asyncio.Event()  # pulsed when a request ends or Groq reports new headroom

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
        self._rolled = False
        reset = headers.get("x-ratelimit-reset-tokens")
        self._reset_at = self._clock() + (parse_duration(reset) if reset else 60.0)
        self._pulse()

    def _pulse(self) -> None:
        self._changed.set()
        self._changed = asyncio.Event()

    def changed(self) -> asyncio.Event:
        """Set the next time a request ends or the headroom is updated (a waiter checks again then)."""
        return self._changed

    def held_by_inflight(self, tokens: int) -> bool:
        """The known headroom would fit `tokens` if the requests in flight were not counted: their answers will
        report the real headroom, so waiting for them beats sleeping a whole window."""
        return (not self.paused() and self._inflight > 0 and self._remaining is not None
                and self._remaining >= tokens > self._remaining - self._inflight)

    def now(self) -> float:
        return self._clock()

    def wait_needed(self, tokens: int) -> float:
        if self.paused():
            return self._paused_until - self._clock()
        if self._remaining is None or self._remaining - self._inflight >= tokens:
            return 0.0
        if self._rolled and self._inflight == 0:  # a fresh window and nothing in flight: a lone caller always goes
            return 0.0
        now = self._clock()
        if self._reset_at <= now:
            self._roll(now)
            return self.wait_needed(tokens)
        return self._reset_at - now

    def _roll(self, now: float) -> None:
        """The window has passed: assume the key's full limit for the next one (unknown limit: no pacing)."""
        self._remaining = self.limit_tokens
        self._reset_at = now + 60.0
        self._rolled = True

    def waited(self, until: float) -> None:
        """A caller slept until `until` (by its own timer, which a test clock may not show): a pause or a window that
        ended by then is over. The caller then asks `wait_needed` again before it sends."""
        if self._paused_until and self._paused_until <= until + 1e-3:
            self._paused_until = 0.0
        if self._remaining is not None and self._reset_at <= until + 1e-3:
            self._roll(until)

    def begin(self, tokens: int) -> None:
        """A request is about to be sent (call right after `wait_needed` returned 0, with no await in between)."""
        self._inflight += tokens

    def end(self, tokens: int) -> None:
        self._inflight -= tokens
        self._pulse()

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
