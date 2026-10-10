# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

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


@pytest.mark.parametrize("value", ["0", "-5"])
def test_groq_timeout_must_be_positive(monkeypatch, value):
    monkeypatch.setenv("GROQ_TIMEOUT_S", value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_upload_limits_default_and_env(monkeypatch):
    for k in ("UPLOAD_MAX_BYTES", "UPLOAD_MAX_FILES", "UPLOAD_MAX_FILE_BYTES"):
        monkeypatch.delenv(k, raising=False)
    s = Settings(_env_file=None)
    assert (s.upload_max_bytes, s.upload_max_files, s.upload_max_file_bytes) == (25 * 1024 * 1024, 3000, 1024 * 1024)
    monkeypatch.setenv("UPLOAD_MAX_BYTES", "1000")
    monkeypatch.setenv("UPLOAD_MAX_FILES", "5")
    monkeypatch.setenv("UPLOAD_MAX_FILE_BYTES", "10")
    s = Settings(_env_file=None)
    assert (s.upload_max_bytes, s.upload_max_files, s.upload_max_file_bytes) == (1000, 5, 10)
    monkeypatch.setenv("UPLOAD_MAX_FILES", "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_groq_prices_are_unset_by_default_and_read_from_env(monkeypatch):
    for name in ("GROQ_PRICE_INPUT_PER_M", "GROQ_PRICE_OUTPUT_PER_M"):
        monkeypatch.delenv(name, raising=False)
    s = Settings(_env_file=None)
    assert (s.groq_price_input_per_m, s.groq_price_output_per_m) == (None, None)
    monkeypatch.setenv("GROQ_PRICE_INPUT_PER_M", "0.15")
    monkeypatch.setenv("GROQ_PRICE_OUTPUT_PER_M", "0.60")
    s = Settings(_env_file=None)
    assert (s.groq_price_input_per_m, s.groq_price_output_per_m) == (0.15, 0.60)
    monkeypatch.setenv("GROQ_PRICE_INPUT_PER_M", "-1")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_host_repos_dir_in_env_does_not_move_the_container_mount(monkeypatch):
    """compose passes .env into the container, and .env sets HOST_REPOS_DIR to a host path for compose itself."""
    monkeypatch.setenv("HOST_REPOS_DIR", "./my-repos")
    assert Settings(_env_file=None).host_repos_mount == Path("/host-repos")
    monkeypatch.setenv("HOST_REPOS_MOUNT", "/elsewhere")
    assert Settings(_env_file=None).host_repos_mount == Path("/elsewhere")


def test_no_setting_reads_a_compose_only_variable(monkeypatch):
    """Variables compose interpolates (${...} in docker-compose.yml) are host-side; .env also reaches the backend,
    so no setting may read one of them."""
    compose = Path(__file__).resolve().parents[2] / "docker-compose.yml"
    if not compose.is_file():
        pytest.skip("docker-compose.yml is not in this checkout (backend image)")
    names = set(re.findall(r"\$\{([A-Z_][A-Z0-9_]*)", compose.read_text(encoding="utf-8")))
    assert {"HOST_REPOS_DIR", "BACKEND_PORT", "FRONTEND_PORT"} <= names
    for name in names:
        monkeypatch.setenv(name, "./host-side-value")
    s = Settings(_env_file=None)
    for name in names:
        monkeypatch.delenv(name)
    assert s.model_dump() == Settings(_env_file=None).model_dump(), "a setting reads a compose-only variable"
