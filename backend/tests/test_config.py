# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
from app.config import Settings


def test_llm_configured_reflects_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert Settings().llm_configured is False
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    s = Settings()
    assert s.llm_configured is True
    assert s.groq_model == "openai/gpt-oss-120b"
    assert s.call_token_reservation == 16000
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


EFFORT_VARS = ("GROQ_REASONING_EFFORT", "GROQ_WRITER_REASONING_EFFORT", "GROQ_FIXER_REASONING_EFFORT")


def _clear_effort(monkeypatch):
    for name in EFFORT_VARS:
        monkeypatch.delenv(name, raising=False)


def test_reasoning_effort_defaults_per_role(monkeypatch):
    _clear_effort(monkeypatch)
    s = Settings(_env_file=None)
    assert (s.groq_writer_reasoning_effort, s.groq_fixer_reasoning_effort) == ("medium", "medium")


def test_role_effort_env_vars(monkeypatch):
    _clear_effort(monkeypatch)
    monkeypatch.setenv("GROQ_WRITER_REASONING_EFFORT", "low")
    monkeypatch.setenv("GROQ_FIXER_REASONING_EFFORT", "high")  # still accepted
    s = Settings(_env_file=None)
    assert (s.groq_writer_reasoning_effort, s.groq_fixer_reasoning_effort) == ("low", "high")


def test_old_single_effort_variable_is_ignored(monkeypatch):
    _clear_effort(monkeypatch)
    monkeypatch.setenv("GROQ_REASONING_EFFORT", "low")
    s = Settings(_env_file=None)
    assert (s.groq_writer_reasoning_effort, s.groq_fixer_reasoning_effort) == ("medium", "medium")
    assert not hasattr(s, "groq_reasoning_effort")


def test_groq_timeout_default_and_env(monkeypatch):
    monkeypatch.delenv("GROQ_TIMEOUT_S", raising=False)
    assert Settings(_env_file=None).groq_timeout_s == 240
    monkeypatch.setenv("GROQ_TIMEOUT_S", "90")
    assert Settings(_env_file=None).groq_timeout_s == 90
