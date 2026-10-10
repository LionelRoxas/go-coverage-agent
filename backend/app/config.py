# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import os
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Effort = Literal["low", "medium", "high"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_ignore_empty=True)

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, *a, **kw):
        """env_ignore_empty drops empty values; GROQ_MAX_COMPLETION_TOKENS= (empty) must instead mean "send no cap"."""
        def no_cap_when_empty() -> dict:
            empty = os.environ.get("GROQ_MAX_COMPLETION_TOKENS") == "" or \
                dotenv_settings.env_vars.get("groq_max_completion_tokens") == ""
            return {"groq_max_completion_tokens": None} if empty else {}
        return init_settings, env_settings, no_cap_when_empty, dotenv_settings, *a

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_writer_reasoning_effort: Effort = "medium"
    groq_fixer_reasoning_effort: Effort = "medium"  # "high" was too slow (job 86b6d88b558c: still waiting after ~114 s)
    groq_max_completion_tokens: int | None = 65536  # model maximum; empty env value -> None: omit the field (Groq then applies a smaller default)
    groq_timeout_s: float = Field(240.0, gt=0)  # GROQ_TIMEOUT_S: per request; retried once at low effort, then the item fails
    # LLM_UNAVAILABLE_AFTER_S: stop the run (llm_unavailable) once Groq has been unreachable this long in a row
    llm_unavailable_after_s: float = Field(600.0, gt=0)
    # PARALLEL_WRITERS: send each round's writer requests at once (validation stays one at a time, in plan order)
    parallel_writers: bool = False
    call_token_reservation: int = 16000  # pacing/ledger reserve per call (>= MAX_PROMPT_TOKENS + expected output); never sent to Groq
    max_prompt_tokens: int = 12000  # MAX_PROMPT_TOKENS; free-trial keys (8K tokens/min) should set 4500
    # USD per 1M tokens, for the cost estimate in the end-of-run summary; unset -> no cost is shown
    groq_price_input_per_m: float | None = Field(None, ge=0)
    groq_price_output_per_m: float | None = Field(None, ge=0)
    daily_token_budget: int = 2_000_000
    min_daily_tokens_to_start: int = 20_000

    repos_dir: Path = Path("/repos")  # app-managed, read-write: downloaded samples and browser uploads
    # HOST_REPOS_MOUNT: the user's own code, mounted read-only (never written). Not named host_repos_dir on purpose:
    # HOST_REPOS_DIR is the host path compose mounts, and compose's env_file also passes it (e.g. ./my-repos) in here.
    host_repos_mount: Path = Path("/host-repos")
    output_dir: Path = Path("/output")
    work_dir: Path = Path("/work")
    gocache: Path = Path("/home/app/.cache/go-build")
    gomodcache: Path = Path("/home/app/.cache/go-mod")

    command_timeout_s: float = 120.0  # COMMAND_TIMEOUT_S: go list and gohelper
    # Per stage, for the whole command (a cold module cache downloads modules during the first compile):
    compile_timeout_s: float = Field(300.0, gt=0)  # COMPILE_TIMEOUT_S: go test -run=^$ (builds every test binary)
    vet_timeout_s: float = Field(180.0, gt=0)  # VET_TIMEOUT_S: go vet
    test_timeout_s: float = Field(300.0, gt=0)  # TEST_TIMEOUT_S: go test -count=2 -cover over every package
    test_timeout: str = "60s"  # TEST_TIMEOUT: go test's own -timeout, per test binary
    max_output_chars: int = 20_000
    cors_origins: list[str] = ["http://localhost:3000"]
    host_repos_dir_display: str | None = None  # display only (HOST_REPOS_DIR_DISPLAY); never used as a path

    # Folder uploads (POST /api/repos/upload); counted over the files kept after skipping .git, vendor, etc.
    upload_max_bytes: int = Field(25 * 1024 * 1024, gt=0)  # UPLOAD_MAX_BYTES
    upload_max_files: int = Field(3000, gt=0)  # UPLOAD_MAX_FILES
    upload_max_file_bytes: int = Field(1024 * 1024, gt=0)  # UPLOAD_MAX_FILE_BYTES: larger files are skipped

    history_max_runs: int = Field(500, ge=0)  # HISTORY_MAX_RUNS: the most recent runs in ./output reloaded on startup

    @property
    def llm_configured(self) -> bool:
        return bool(self.groq_api_key.strip())
