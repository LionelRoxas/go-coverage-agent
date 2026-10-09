# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_ignore_empty=True)

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_reasoning_effort: Literal["low", "medium", "high"] = "low"
    groq_max_completion_tokens: int | None = None  # None: send no cap, the model maximum applies
    call_token_reservation: int = 8000  # pacing/ledger reserve per call; never sent to Groq
    max_prompt_tokens: int = 4500
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
    sample_repo_url: str = "https://github.com/montanaflynn/stats"

    @property
    def llm_configured(self) -> bool:
        return bool(self.groq_api_key.strip())
