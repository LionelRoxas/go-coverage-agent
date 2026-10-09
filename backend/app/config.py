# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import os
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_ignore_empty=True)

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, *a, **kw):
        """env_ignore_empty drops empty values; GROQ_MAX_COMPLETION_TOKENS= (empty) must instead mean "send no cap"."""
        def no_cap_when_empty() -> dict:
            empty = os.environ.get("GROQ_MAX_COMPLETION_TOKENS") == "" or                 dotenv_settings.env_vars.get("groq_max_completion_tokens") == ""
            return {"groq_max_completion_tokens": None} if empty else {}
        return init_settings, env_settings, no_cap_when_empty, dotenv_settings, *a

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_reasoning_effort: Literal["low", "medium", "high"] = "low"
    groq_max_completion_tokens: int | None = 65536  # model maximum; empty env value -> None: omit the field (Groq then applies a smaller default)
    call_token_reservation: int = 16000  # pacing/ledger reserve per call (>= MAX_PROMPT_TOKENS + expected output); never sent to Groq
    max_prompt_tokens: int = 12000  # MAX_PROMPT_TOKENS; free-trial keys (8K tokens/min) should set 4500
    daily_token_budget: int = 2_000_000
    min_daily_tokens_to_start: int = 20_000

    repos_dir: Path = Path("/repos")
    output_dir: Path = Path("/output")
    work_dir: Path = Path("/work")
    gocache: Path = Path("/home/app/.cache/go-build")
    gomodcache: Path = Path("/home/app/.cache/go-mod")

    command_timeout_s: float = 120.0
    test_timeout: str = "60s"
    max_output_chars: int = 20_000
    cors_origins: list[str] = ["http://localhost:3000"]
    host_repos_dir_display: str | None = None  # display only (HOST_REPOS_DIR_DISPLAY); never used as a path

    @property
    def llm_configured(self) -> bool:
        return bool(self.groq_api_key.strip())
