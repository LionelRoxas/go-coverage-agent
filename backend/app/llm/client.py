# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Groq chat completions with strict structured output, pacing, budgets and clear failure modes."""
from __future__ import annotations

import asyncio
import math
import re
from contextvars import ContextVar
from typing import Any, Awaitable, Callable, Protocol, TypeVar

import groq
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.llm.limits import RateLimiter, UsageLedger
from app.llm.schema import to_strict_schema
from app.models import TokenUsage

T = TypeVar("T", bound=BaseModel)
Emit = Callable[[str, dict[str, Any]], Awaitable[None]]
OnRequest = Callable[[str], Awaitable[None]]  # called with the reasoning effort right before each request to Groq
# Set by a caller running concurrently with others (PARALLEL_WRITERS): `rate_limited` then names its item
# ({index, file, role}). Unset (sequential runs, the summary): the event is unchanged.
LLM_CALL: ContextVar[dict[str, Any] | None] = ContextVar("LLM_CALL", default=None)


class LLMError(Exception):
    """The current item failed; the loop can continue. `spent`: tokens Groq billed for this call before it failed
    (e.g. truncated answers retried at a lower effort); they are already in the daily ledger."""

    spent: TokenUsage = TokenUsage()
    local: bool = False  # raised before Groq was contacted (says nothing about whether Groq is reachable)


class LLMOutputTooLarge(LLMError):
    """The answer did not fit in the output limit (truncated, or Groq could not finish the JSON): ask for less."""


class LLMTransportError(LLMError):
    """Groq could not be reached or did not answer (not a problem with this item): the orchestrator retries the item
    later instead of counting it as a failure, and stops the run if Groq stays unreachable."""


class LLMTimeout(LLMTransportError):
    """Groq did not answer within GROQ_TIMEOUT_S, and again on the one retry at low effort."""


class LLMUnavailable(LLMTransportError):
    """Connection errors or 5xx responses persisted through the network retries."""


class LLMBudgetExhausted(LLMError):
    """No more tokens available (job budget, daily ledger, or Groq daily cap). Stop gracefully."""


class LLMFatal(LLMError):
    """Configuration problem (e.g. invalid key). Fail the job."""


class LLMCancelled(LLMError):
    """The job was cancelled while waiting on the LLM (e.g. during a rate-limit pause)."""


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / 3.5)


def _retry_after(headers: Any) -> float:
    """Seconds from a Retry-After header; 60s when missing, unparseable (e.g. an HTTP-date), or non-finite."""
    try:
        value = float(headers.get("retry-after", "60"))
    except (TypeError, ValueError):
        return 60.0
    if not math.isfinite(value):
        return 60.0
    return max(0.0, value)


_SIZE_HINT = re.compile(r"limit\D{0,3}(\d+)\D+requested\D{0,3}(\d+)", re.IGNORECASE)
_MIN_COMPLETION = 1024
_LOWER_EFFORT = {"high": "medium", "medium": "low"}  # step-down after a truncated answer
_SIZE_GUIDANCE = ("Groq rejected the request size for this key's tokens-per-minute limit; "
                  "set GROQ_MAX_COMPLETION_TOKENS lower (e.g. 4000), and on a free-trial key (8K tokens/min) "
                  "also set MAX_PROMPT_TOKENS=4500.")


def _size_rejection(e: groq.APIStatusError) -> tuple[bool, int | None]:
    """(is this a request-size rejection, the TPM limit named in its message). Plain rate-limit 429s are not size errors."""
    text = f"{e.message} {e.body}"
    hint = _SIZE_HINT.search(text)
    limit = int(hint[1]) if hint else None
    if e.status_code == 413 or "request too large" in text.lower():
        return True, limit
    return (hint is not None and int(hint[2]) > int(hint[1])), limit  # asked for more than a minute can ever hold


class LLMClient(Protocol):
    last_effort: str | None  # reasoning effort of the last successful call

    async def complete(self, *, role: str, system: str, user: str, schema: type[T],
                       on_request: OnRequest | None = None) -> tuple[T, TokenUsage]: ...


class GroqLLM:
    MAX_RATE_RETRIES = 5
    MAX_NET_RETRIES = 3
    MAX_RETRY_AFTER_S = 90.0

    def __init__(self, settings: Settings, ledger: UsageLedger, limiter: RateLimiter,
                 emit: Emit | None = None, client: Any = None,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 cancel: asyncio.Event | None = None):
        self.s, self.ledger, self.limiter = settings, ledger, limiter
        self._emit, self._sleep, self._cancel = emit, sleep, cancel
        self._client = client or groq.AsyncGroq(api_key=settings.groq_api_key, max_retries=0,
                                                       timeout=settings.groq_timeout_s)
        self.last_effort: str | None = None

    async def _wait(self, seconds: float, reason: str) -> None:
        if self._emit:
            await self._emit("rate_limited", {"seconds": round(seconds, 1), "reason": reason, **(LLM_CALL.get() or {})})
        await self._sleep_cancellable(seconds)

    async def _wait_for_inflight(self, seconds: float) -> None:
        """Wait for the requests in flight (PARALLEL_WRITERS) to free the headroom: until one ends or new headers
        arrive, or at most `seconds` (the window). Cancel wakes it at once."""
        until = self.limiter.now() + seconds
        if self._emit:
            await self._emit("rate_limited", {"seconds": round(seconds, 1), "reason": "tpm", **(LLM_CALL.get() or {})})
        changed = asyncio.ensure_future(self.limiter.changed().wait())
        timer = asyncio.ensure_future(self._sleep(seconds))
        stop = asyncio.ensure_future(self._cancel.wait()) if self._cancel is not None else None
        waits = {t for t in (changed, timer, stop) if t is not None}
        try:
            await asyncio.wait(waits, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in waits:
                if not t.done():
                    t.cancel()
            await asyncio.gather(*waits, return_exceptions=True)
        if stop is not None and stop.done() and not stop.cancelled():
            raise LLMCancelled("cancelled while waiting")
        if timer.done() and not timer.cancelled():  # the whole window passed
            self.limiter.waited(until)

    async def _sleep_cancellable(self, seconds: float) -> None:
        if self._cancel is None:
            await self._sleep(seconds)
            return
        try:  # wake up immediately if the user cancels during a pause
            await asyncio.wait_for(self._cancel.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            return
        raise LLMCancelled("cancelled while waiting")

    async def _request(self, **kwargs: Any) -> Any:
        call = asyncio.ensure_future(self._client.chat.completions.with_raw_response.create(**kwargs))
        if self._cancel is None:
            return await call
        stop = asyncio.ensure_future(self._cancel.wait())
        try:
            done, _ = await asyncio.wait({call, stop}, return_when=asyncio.FIRST_COMPLETED)
            if call in done:
                return call.result()
            raise LLMCancelled("cancelled during an LLM request")
        finally:
            pending = [t for t in (call, stop) if not t.done()]
            for t in pending:
                t.cancel()
            if pending:  # let the cancelled tasks finish so none are left orphaned
                await asyncio.wait(pending)

    async def complete(self, *, role: str, system: str, user: str, schema: type[T],
                       on_request: OnRequest | None = None) -> tuple[T, TokenUsage]:
        prompt_tokens = estimate_tokens(system) + estimate_tokens(user)
        if prompt_tokens > self.s.max_prompt_tokens:
            error = LLMError(f"prompt is ~{prompt_tokens} tokens, over the {self.s.max_prompt_tokens} limit")
            error.local = True
            raise error

        effort: str = (self.s.groq_fixer_reasoning_effort if role == "fixer"
                       else self.s.groq_writer_reasoning_effort)
        rate_retries = net_retries = 0
        json_retried = timeout_retried = False
        spent = TokenUsage()
        response_format = {"type": "json_schema", "json_schema": {
            "name": schema.__name__, "strict": True, "schema": to_strict_schema(schema)}}

        size_retried = False

        def completion_allowance() -> dict[str, Any]:
            cap = self.s.groq_max_completion_tokens
            if cap is None:
                return {}
            if self.limiter.limit_tokens is not None:
                cap = min(cap, max(_MIN_COMPLETION, self.limiter.limit_tokens - prompt_tokens - 256))
            return {"max_completion_tokens": cap}

        def size_rejected(e: groq.APIStatusError) -> bool:
            """True when the request should be retried once with a clamped allowance; raises on a repeat."""
            nonlocal size_retried
            rejected, limit = _size_rejection(e)
            if not rejected:
                return False
            self.limiter.update(e.response.headers)
            if self.limiter.limit_tokens is None and limit is not None:
                self.limiter.limit_tokens = limit
            if size_retried or self.limiter.limit_tokens is None:
                raise LLMError(_SIZE_GUIDANCE) from e
            size_retried = True
            return True

        # The daily ledger: checked and reserved in one step, so calls running at the same time cannot all pass the
        # same headroom; released when this call ends (what Groq billed is added to the ledger as it comes).
        if not self.ledger.try_reserve(self.s.call_token_reservation):
            exhausted = LLMBudgetExhausted("The daily Groq token budget is used up. It resets at 00:00 UTC.")
            exhausted.local = True
            raise exhausted
        try:
            while True:
                try:
                    raw = await self._send(on_request, effort, lambda: dict(
                        model=self.s.groq_model,
                        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                        response_format=response_format,
                        reasoning_effort=effort,
                        temperature=0.2,
                        **completion_allowance(),
                    ))
                except groq.AuthenticationError as e:
                    raise LLMFatal("Groq rejected the API key (401). Check GROQ_API_KEY in .env.") from e
                except groq.RateLimitError as e:
                    if size_rejected(e):
                        continue
                    retry_after = _retry_after(e.response.headers)
                    if retry_after > self.MAX_RETRY_AFTER_S or rate_retries >= self.MAX_RATE_RETRIES:
                        raise LLMBudgetExhausted(
                            f"Groq asked us to wait {retry_after:.0f}s, which usually means the daily token cap was hit."
                        ) from e
                    rate_retries += 1
                    until = self.limiter.pause(retry_after)  # every other call waits it out too
                    await self._wait(retry_after, "429")
                    self.limiter.resume(until)
                    continue
                except groq.APITimeoutError as e:  # before APIConnectionError, its base class (also covers connect timeouts)
                    if not timeout_retried:  # one retry at the lowest effort, whatever the role's setting: it answers fastest
                        timeout_retried, effort = True, "low"
                        continue
                    raise LLMTimeout(f"Groq did not answer within {self.s.groq_timeout_s:g} s, twice") from e
                except (groq.APIConnectionError, groq.InternalServerError) as e:
                    if net_retries >= self.MAX_NET_RETRIES:
                        raise LLMUnavailable(f"Groq is unreachable: {e}") from e
                    net_retries += 1
                    await self._sleep_cancellable(2.0 ** net_retries)
                    continue
                except groq.APIStatusError as e:
                    if size_rejected(e):
                        continue
                    if e.status_code == 400 and not json_retried and "json_validate_failed" in f"{e.body} {e.message}":
                        json_retried = True  # strict-mode flake: the model skipped required fields; sample once more
                        continue
                    if e.status_code == 400 and "json_validate_failed" in f"{e.body} {e.message}":
                        raise LLMOutputTooLarge(f"Groq returned {e.status_code}: {e.message}") from e
                    raise LLMError(f"Groq returned {e.status_code}: {e.message}") from e

                self.limiter.update(raw.headers)
                self.limiter.recovered()
                completion = await raw.parse()
                if not completion.choices:
                    raise LLMError("Groq returned no choices")
                if completion.usage is None:
                    raise LLMError("Groq response carried no usage data")
                usage = TokenUsage(prompt_tokens=completion.usage.prompt_tokens,
                                   completion_tokens=completion.usage.completion_tokens)
                spent = spent.add(usage)
                self.ledger.add(usage.total)
                choice = completion.choices[0]
                if choice.finish_reason == "length":
                    # Retrying only helps at a lower reasoning effort (high -> medium -> low); otherwise it re-spends
                    # the same tokens.
                    if effort not in _LOWER_EFFORT:
                        raise LLMOutputTooLarge("the model's answer was truncated; skipping this target")
                    effort = _LOWER_EFFORT[effort]
                    continue
                try:
                    parsed = schema.model_validate_json(choice.message.content or "")
                except ValidationError as e:
                    raise LLMError(f"model output does not match {schema.__name__} ({e.error_count()} errors)") from e
                self.last_effort = effort
                return parsed, spent
        except LLMError as e:
            e.spent = spent
            raise
        finally:
            self.ledger.release(self.s.call_token_reservation)

    async def _send(self, on_request: OnRequest | None, effort: str, request: Callable[[], dict[str, Any]]) -> Any:
        """Pace, then send one request. Its reservation counts against the TPM headroom until it is answered. After
        a 429, until a request succeeds again, one request is sent at a time (the probe)."""
        reservation = self.s.call_token_reservation
        probe: asyncio.Lock | None = None
        try:
            while True:  # every pass re-reads the pause, the probe and the headroom: others may have changed them
                if probe is None and self.limiter.probing:
                    await self.limiter.probe.acquire()
                    probe = self.limiter.probe
                if probe is not None and not self.limiter.probing:  # the probe ahead succeeded: go together again
                    probe.release()
                    probe = None
                if probe is not None and self._cancel is not None and self._cancel.is_set():
                    raise LLMCancelled("cancelled while waiting")
                wait = self.limiter.wait_needed(reservation)
                if wait <= 0:
                    break
                if probe is not None:  # never hold the probe while sleeping
                    probe.release()
                    probe = None
                if self.limiter.held_by_inflight(reservation):  # wake as soon as one of them answers
                    await self._wait_for_inflight(wait)
                    continue
                until = self.limiter.now() + wait
                await self._wait(wait, "429" if self.limiter.paused() else "tpm")
                self.limiter.waited(until)
            self.limiter.begin(reservation)  # no await since wait_needed: the check and the reservation are one step
            try:
                if on_request is not None:
                    await on_request(effort)
                return await self._request(**request())
            finally:
                self.limiter.end(reservation)
        finally:
            if probe is not None:
                probe.release()
