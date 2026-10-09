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
    def parse(self): return self._c


def http_error(cls, status, headers=None):
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return cls("err", response=httpx.Response(status, headers=headers or {}, request=req), body=None)


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
    assert kw["max_completion_tokens"] == 7000 - 2  # "sys"+"usr" ≈ 2 tokens
    assert llm.ledger.used_today() == 150


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
