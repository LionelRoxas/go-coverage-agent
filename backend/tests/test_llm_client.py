# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import httpx
import groq
import pytest
from pydantic import BaseModel

from app.config import Settings
from app.llm.client import GroqLLM, LLMBudgetExhausted, LLMError, LLMFatal
from app.llm.limits import RateLimiter, UsageLedger


class Out(BaseModel):
    answer: str


class Msg:
    def __init__(self, content): self.content = content


class Choice:
    def __init__(self, content, finish): self.message, self.finish_reason = Msg(content), finish


class Usage:
    prompt_tokens, completion_tokens = 100, 50


class Completion:
    def __init__(self, content, finish): self.choices, self.usage = [Choice(content, finish)], Usage()


class Raw:
    def __init__(self, completion, headers=None): self._c, self.headers = completion, headers or {}
    async def parse(self): return self._c  # the real AsyncAPIResponse.parse is a coroutine


def http_error(cls, status, headers=None, message="err", body=None):
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return cls(message, response=httpx.Response(status, headers=headers or {}, request=req), body=body)


class FakeGroq:
    """Mimics client.chat.completions.with_raw_response.create(...)."""

    def __init__(self, script):
        self.script, self.calls = list(script), []
        self.chat = self
        self.completions = self
        self.with_raw_response = self

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


async def _no_sleep(seconds): return None


def make(tmp_path, script, events=None):
    slept = []
    async def sleep(s): slept.append(s)
    async def emit(t, d): (events if events is not None else []).append((t, d))
    fake = FakeGroq(script)
    llm = GroqLLM(Settings(groq_api_key="k"), UsageLedger(tmp_path / "u.json", 190_000), RateLimiter(),
                  emit=emit, client=fake, sleep=sleep)
    return llm, fake, slept


async def call(llm):
    return await llm.complete(role="writer", system="sys", user="usr", schema=Out)


async def test_success_parses_and_counts_usage(tmp_path):
    llm, fake, _ = make(tmp_path, [Raw(Completion('{"answer": "hi"}', "stop"))])
    out, usage = await call(llm)
    assert out.answer == "hi" and usage.total == 150
    kw = fake.calls[0]
    assert kw["response_format"]["json_schema"]["strict"] is True
    assert kw["reasoning_effort"] == "low"
    assert "max_completion_tokens" not in kw
    assert llm.ledger.used_today() == 150


async def test_configured_completion_cap_is_sent_verbatim(tmp_path):
    llm, fake, _ = make(tmp_path, [Raw(Completion('{"answer": "hi"}', "stop"))])
    llm.s = Settings(groq_api_key="k", groq_max_completion_tokens=1234)
    await call(llm)
    assert fake.calls[0]["max_completion_tokens"] == 1234


async def test_401_is_fatal(tmp_path):
    llm, _, _ = make(tmp_path, [http_error(groq.AuthenticationError, 401)])
    with pytest.raises(LLMFatal, match="API key"):
        await call(llm)


async def test_short_429_waits_and_retries(tmp_path):
    events = []
    llm, _, slept = make(tmp_path, [http_error(groq.RateLimitError, 429, {"retry-after": "12"}),
                                    Raw(Completion('{"answer": "ok"}', "stop"))], events)
    out, _ = await call(llm)
    assert out.answer == "ok" and slept == [12.0]
    assert ("rate_limited", {"seconds": 12.0, "reason": "429"}) in events


async def test_long_429_means_daily_cap(tmp_path):
    llm, _, _ = make(tmp_path, [http_error(groq.RateLimitError, 429, {"retry-after": "3600"})])
    with pytest.raises(LLMBudgetExhausted):
        await call(llm)


async def test_truncation_at_low_effort_fails_without_retry(tmp_path):
    llm, fake, _ = make(tmp_path, [Raw(Completion("{", "length"))])
    with pytest.raises(LLMError, match="truncated"):
        await call(llm)
    assert len(fake.calls) == 1


async def test_schema_mismatch_is_llm_error(tmp_path):
    llm, _, _ = make(tmp_path, [Raw(Completion('{"wrong": 1}', "stop"))])
    with pytest.raises(LLMError, match="does not match"):
        await call(llm)


async def test_daily_budget_checked_before_calling(tmp_path):
    llm, fake, _ = make(tmp_path, [])
    llm.ledger.add(190_000)
    assert llm.ledger.remaining() < llm.s.call_token_reservation
    with pytest.raises(LLMBudgetExhausted):
        await call(llm)
    assert fake.calls == []


async def test_cancel_interrupts_rate_limit_wait(tmp_path):
    import asyncio
    from app.llm.client import LLMCancelled
    cancel = asyncio.Event()
    fake = FakeGroq([http_error(groq.RateLimitError, 429, {"retry-after": "60"})])
    llm = GroqLLM(Settings(groq_api_key="k"), UsageLedger(tmp_path / "u.json", 190_000), RateLimiter(),
                  client=fake, cancel=cancel)
    asyncio.get_running_loop().call_later(0.05, cancel.set)
    with pytest.raises(LLMCancelled):
        await asyncio.wait_for(call(llm), timeout=2)  # must not sleep the full 60s


async def test_oversized_prompt_rejected(tmp_path):
    llm, _, _ = make(tmp_path, [])
    with pytest.raises(LLMError, match="prompt"):
        await llm.complete(role="writer", system="s", user="x" * 20_000, schema=Out)


async def test_http_date_retry_after_falls_back_to_60s(tmp_path):
    llm, _, slept = make(tmp_path, [http_error(groq.RateLimitError, 429, {"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"}),
                                    Raw(Completion('{"answer": "ok"}', "stop"))])
    out, _ = await call(llm)
    assert out.answer == "ok" and slept == [60.0]


async def test_network_errors_back_off_then_fail(tmp_path):
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    script = [groq.APIConnectionError(request=req) for _ in range(4)]
    llm, fake, slept = make(tmp_path, script)
    with pytest.raises(LLMError, match="unreachable"):
        await call(llm)
    assert len(fake.calls) == 4 and slept == [2.0, 4.0, 8.0]


async def test_higher_effort_truncation_retries_once_at_low(tmp_path):
    fake = FakeGroq([Raw(Completion("{", "length")), Raw(Completion('{"answer": "ok"}', "stop"))])
    llm = GroqLLM(Settings(groq_api_key="k", groq_reasoning_effort="medium"),
                  UsageLedger(tmp_path / "u.json", 190_000), RateLimiter(),
                  client=fake, sleep=_no_sleep)
    out, usage = await call(llm)
    assert out.answer == "ok"
    assert [c["reasoning_effort"] for c in fake.calls] == ["medium", "low"]
    assert usage.total == 300 and llm.ledger.used_today() == 300


async def test_missing_choices_is_llm_error(tmp_path):
    empty = Completion('{"answer": "x"}', "stop")
    empty.choices = []
    llm, _, _ = make(tmp_path, [Raw(empty)])
    with pytest.raises(LLMError, match="no choices"):
        await call(llm)


async def test_cancel_during_hanging_request_leaves_no_tasks(tmp_path):
    import asyncio
    from app.llm.client import LLMCancelled

    class Hanging:
        def __init__(self):
            self.cancelled = False
            self.chat = self.completions = self.with_raw_response = self

        async def create(self, **kwargs):
            try:
                await asyncio.Event().wait()  # never fires
            except asyncio.CancelledError:
                self.cancelled = True
                raise

    cancel = asyncio.Event()
    fake = Hanging()
    llm = GroqLLM(Settings(groq_api_key="k"), UsageLedger(tmp_path / "u.json", 190_000), RateLimiter(),
                  client=fake, cancel=cancel)
    asyncio.get_running_loop().call_later(0.05, cancel.set)
    with pytest.raises(LLMCancelled):
        await asyncio.wait_for(call(llm), timeout=2)
    assert fake.cancelled
    others = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    assert others == []


def _json_failed():
    return http_error(groq.BadRequestError, 400, message="Error code: 400 - json_validate_failed",
                      body={"error": {"code": "json_validate_failed"}})


async def test_json_validate_failed_is_retried_once(tmp_path):
    llm, fake, _ = make(tmp_path, [_json_failed(), Raw(Completion('{"answer": "ok"}', "stop"))])
    out, _ = await call(llm)
    assert out.answer == "ok" and len(fake.calls) == 2


async def test_second_json_validate_failed_raises(tmp_path):
    llm, fake, _ = make(tmp_path, [_json_failed(), _json_failed()])
    with pytest.raises(LLMError, match="400"):
        await call(llm)
    assert len(fake.calls) == 2


async def test_other_400_fails_immediately(tmp_path):
    llm, fake, _ = make(tmp_path, [http_error(groq.BadRequestError, 400)])
    with pytest.raises(LLMError, match="400"):
        await call(llm)
    assert len(fake.calls) == 1
