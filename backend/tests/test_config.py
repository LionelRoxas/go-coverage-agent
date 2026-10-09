# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
from app.config import Settings


def test_llm_configured_reflects_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert Settings().llm_configured is False
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    s = Settings()
    assert s.llm_configured is True
    assert s.groq_model == "openai/gpt-oss-120b"
    assert s.call_token_reservation == 8000
    assert s.groq_max_completion_tokens == 65536
    assert s.daily_token_budget == 2_000_000


def test_empty_max_completion_tokens_means_unset(monkeypatch):
    monkeypatch.setenv("GROQ_MAX_COMPLETION_TOKENS", "")
    assert Settings().groq_max_completion_tokens is None


def test_max_prompt_tokens_default_and_env(monkeypatch):
    monkeypatch.delenv("MAX_PROMPT_TOKENS", raising=False)
    assert Settings(_env_file=None).max_prompt_tokens == 12000
    monkeypatch.setenv("MAX_PROMPT_TOKENS", "4500")
    assert Settings(_env_file=None).max_prompt_tokens == 4500
