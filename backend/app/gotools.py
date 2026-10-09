# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""The only module that executes commands. Fixed argv lists, scrubbed env, timeouts, process-group kill."""
from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import time
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Iterator

from app.config import Settings
from app.models import FuncInfo, FuncKey

_PASSTHROUGH = ("PATH", "HOME", "TMPDIR", "GOPROXY", "GOPRIVATE", "GONOSUMDB",
                "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY")


@dataclass
class CommandResult:
    argv: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    cancelled: bool = False

    @property
    def combined(self) -> str:
        return "\n".join(part for part in (self.stdout.strip(), self.stderr.strip()) if part)


class GoToolError(RuntimeError):
    def __init__(self, message: str, result: CommandResult):
        super().__init__(f"{message}: {result.combined[:2000]}")
        self.result = result


@dataclass(frozen=True)
class GoPackage:
    import_path: str
    rel_dir: str
    name: str


def _cap(data: bytes, max_chars: int) -> str:
    text = data.decode("utf-8", errors="replace")
    return text if len(text) <= max_chars else text[:max_chars] + "\n…[output truncated]"


def _kill_group(proc: asyncio.subprocess.Process) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


async def run(argv: list[str], cwd: Path, timeout: float, env: dict[str, str],
              cancel: asyncio.Event | None = None, max_chars: int = 20_000) -> CommandResult:
    started = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        *argv, cwd=str(cwd), env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    comm = asyncio.ensure_future(proc.communicate())
    waiters: set[asyncio.Future[Any]] = {comm}
    cancel_wait = asyncio.ensure_future(cancel.wait()) if cancel else None
    if cancel_wait:
        waiters.add(cancel_wait)
    try:
        done, _ = await asyncio.wait(waiters, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        finished = comm in done
        if not finished:
            _kill_group(proc)
        out, err = await comm
    finally:
        if cancel_wait:
            cancel_wait.cancel()
    return CommandResult(
        argv=argv,
        exit_code=proc.returncode if finished else -1,
        stdout=_cap(out, max_chars), stderr=_cap(err, max_chars),
        duration_ms=int((time.monotonic() - started) * 1000),
        timed_out=not finished and not (cancel is not None and cancel.is_set()),
        cancelled=cancel is not None and cancel.is_set(),
    )


def go_env(settings: Settings) -> dict[str, str]:
    env = {k: os.environ[k] for k in _PASSTHROUGH if k in os.environ}
    env.update(
        GOCACHE=str(settings.gocache), GOMODCACHE=str(settings.gomodcache),
        GOFLAGS="-mod=readonly", GOTOOLCHAIN="local", CGO_ENABLED="0", GOTELEMETRY="off",
    )
    return env


def read_module_info(root: Path) -> tuple[str, str]:
    text = (root / "go.mod").read_text()
    module = re.search(r"^module\s+(\S+)", text, re.M)
    go = re.search(r"^go\s+(\S+)", text, re.M)
    if module is None:
        raise ValueError("go.mod has no module directive")
    return module.group(1).strip('"'), go.group(1) if go else "1.16"


def iter_json(text: str) -> Iterator[dict[str, Any]]:
    decoder, i, n = json.JSONDecoder(), 0, len(text)
    while True:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            return
        obj, i = decoder.raw_decode(text, i)
        yield obj


def is_excluded(rel_dir: str, patterns: list[str]) -> bool:
    return any(fnmatchcase(rel_dir, p) or fnmatchcase(rel_dir + "/", p) for p in patterns)


class GoTools:
    def __init__(self, root: Path, settings: Settings, cancel: asyncio.Event | None = None):
        self.root = root.resolve()
        self.settings = settings
        self.cancel = cancel
        self._env = go_env(settings)

    async def _run(self, argv: list[str], timeout: float | None = None) -> CommandResult:
        return await run(argv, self.root, timeout or self.settings.command_timeout_s, self._env,
                         self.cancel, self.settings.max_output_chars)

    async def list_packages(self, exclude: list[str]) -> list[GoPackage]:
        r = await self._run(["go", "list", "-json", "./..."])
        if r.exit_code != 0:
            raise GoToolError("go list failed", r)
        pkgs = []
        for obj in iter_json(r.stdout):
            if obj.get("Name") == "main" or not obj.get("GoFiles"):
                continue
            rel = Path(obj["Dir"]).resolve().relative_to(self.root).as_posix()
            if is_excluded(rel, exclude):
                continue
            pkgs.append(GoPackage(import_path=obj["ImportPath"], rel_dir=rel, name=obj["Name"]))
        return pkgs

    async def compile(self, pkgs: list[GoPackage]) -> CommandResult:
        return await self._run(["go", "test", "-count=1", "-run=^$", *[p.import_path for p in pkgs]])

    async def vet(self, pkgs: list[GoPackage]) -> CommandResult:
        return await self._run(["go", "vet", *[p.import_path for p in pkgs]])

    async def test(self, pkgs: list[GoPackage], profile: Path) -> CommandResult:
        return await self._run(["go", "test", "-count=2", "-covermode=set", f"-coverprofile={profile}",
                                f"-timeout={self.settings.test_timeout}", *[p.import_path for p in pkgs]])

    async def funcs(self) -> list[FuncInfo]:
        r = await self._run(["gohelper", "funcs", "."])
        if r.exit_code != 0:
            raise GoToolError("gohelper funcs failed", r)
        return [FuncInfo(key=FuncKey(file=o["file"], receiver=o["receiver"], name=o["name"]),
                         package=o["package"], start_line=o["start_line"], end_line=o["end_line"],
                         exported=o["exported"]) for o in json.loads(r.stdout)]

    async def decls(self, rel_dir: str) -> list[str]:
        r = await self._run(["gohelper", "decls", rel_dir])
        if r.exit_code != 0:
            raise GoToolError("gohelper decls failed", r)
        return json.loads(r.stdout)

    async def merge(self, test_file: str, snippet: Path) -> CommandResult:
        return await self._run(["gohelper", "merge", test_file, str(snippet)])

    async def prune(self, test_file: str, names: list[str]) -> CommandResult:
        return await self._run(["gohelper", "prune", test_file, *names])
