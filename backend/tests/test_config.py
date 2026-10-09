# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
from app.config import Settings


def test_llm_configured_reflects_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert Settings().llm_configured is False
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    s = Settings()
    assert s.llm_configured is True
    assert s.groq_model == "openai/gpt-oss-120b"
    assert s.call_token_reservation == 8000
    assert s.groq_max_completion_tokens is None
    assert s.daily_token_budget == 2_000_000
