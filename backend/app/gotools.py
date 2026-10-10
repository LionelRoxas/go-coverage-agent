# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
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


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    file: str
    start_line: int
    end_line: int


_MARKER = "\n…[output truncated]"
_CHUNK = 64 * 1024
_REAP_TIMEOUT = 5.0
JSON_MAX_CHARS = 50_000_000


async def _drain(stream: asyncio.StreamReader | None, max_chars: int) -> tuple[str, bool]:
    """Read to EOF, keeping at most ~max_chars of output; the rest is discarded so the child never blocks."""
    limit = max_chars * 4  # a char is at most 4 bytes of UTF-8
    buf = bytearray()
    truncated = False
    while stream is not None:
        chunk = await stream.read(_CHUNK)
        if not chunk:
            break
        room = limit - len(buf)
        if room > 0:
            buf += chunk[:room]
        if len(chunk) > room:
            truncated = True
    text = bytes(buf).decode("utf-8", errors="replace")
    if truncated or len(text) > max_chars:
        return text[:max_chars] + _MARKER, True
    return text, False


def _kill_group(proc: asyncio.subprocess.Process) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


async def _reap(proc: asyncio.subprocess.Process, io: asyncio.Future[Any]) -> None:
    """After a kill, wait (bounded) for the process and readers so run() can never hang."""
    try:
        await asyncio.wait_for(asyncio.shield(proc.wait()), _REAP_TIMEOUT)
    except (asyncio.TimeoutError, ProcessLookupError):
        pass
    if not io.done():
        io.cancel()


async def run(argv: list[str], cwd: Path, timeout: float, env: dict[str, str],
              cancel: asyncio.Event | None = None, max_chars: int = 20_000) -> CommandResult:
    started = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        *argv, cwd=str(cwd), env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    io = asyncio.gather(_drain(proc.stdout, max_chars), _drain(proc.stderr, max_chars), proc.wait())
    waiters: set[asyncio.Future[Any]] = {io}
    cancel_wait = asyncio.ensure_future(cancel.wait()) if cancel else None
    if cancel_wait:
        waiters.add(cancel_wait)
    out, err = "", ""
    try:
        done, _ = await asyncio.wait(waiters, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        finished = io in done
        if not finished:
            _kill_group(proc)
            await _reap(proc, io)
        if io.done() and not io.cancelled():
            (out, _), (err, _), _ = io.result()
    except BaseException:
        # The awaiting task was cancelled (or something broke): never orphan the process group.
        _kill_group(proc)
        await _reap(proc, io)
        raise
    finally:
        if cancel_wait:
            cancel_wait.cancel()
    return CommandResult(
        argv=argv,
        exit_code=proc.returncode if finished and proc.returncode is not None else -1,
        stdout=out, stderr=err,
        duration_ms=int((time.monotonic() - started) * 1000),
        timed_out=not finished and not (cancel is not None and cancel.is_set()),
        cancelled=cancel is not None and cancel.is_set(),
    )


# stage -> (what timed out, the Settings field that bounds it; its env var is the field name in upper case)
_STAGES = {"list": ("go list (loading the module)", "command_timeout_s"),
           "compile": ("the compile step (go test -run=^$)", "compile_timeout_s"),
           "vet": ("go vet", "vet_timeout_s"),
           "test": ("go test", "test_timeout_s")}


def timeout_message(settings: Settings, stage: str) -> str:
    """'<what> timed out after N s (ENV_VAR)' for a command killed at its stage's timeout."""
    what, field = _STAGES[stage]
    return f"{what} timed out after {getattr(settings, field):g} s ({field.upper()})"


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
    def __init__(self, root: Path, settings: Settings, cancel: asyncio.Event | None = None,
                 tmp_dir: Path | None = None):
        """`tmp_dir`: Go's temporary build directories (GOTMPDIR) go here instead of /tmp, so the ones a killed
        build leaves behind are removed with the job's work folder."""
        self.root = root.resolve()
        self.settings = settings
        self.cancel = cancel
        self._env = go_env(settings)
        if tmp_dir is not None:
            tmp_dir.mkdir(parents=True, exist_ok=True)
            self._env["GOTMPDIR"] = str(tmp_dir)

    async def _run(self, argv: list[str], timeout: float | None = None,
                   max_chars: int | None = None) -> CommandResult:
        return await run(argv, self.root, timeout or self.settings.command_timeout_s, self._env,
                         self.cancel, max_chars or self.settings.max_output_chars)

    async def list_packages(self, exclude: list[str]) -> list[GoPackage]:
        r = await self._run(["go", "list", "-json", "./..."], max_chars=JSON_MAX_CHARS)
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
        return await self._run(["go", "test", "-count=1", "-run=^$", *[p.import_path for p in pkgs]],
                               timeout=self.settings.compile_timeout_s)

    async def vet(self, pkgs: list[GoPackage]) -> CommandResult:
        return await self._run(["go", "vet", *[p.import_path for p in pkgs]], timeout=self.settings.vet_timeout_s)

    async def test(self, pkgs: list[GoPackage], profile: Path) -> CommandResult:
        return await self._run(["go", "test", "-count=2", "-covermode=set", f"-coverprofile={profile}",
                                f"-timeout={self.settings.test_timeout}", *[p.import_path for p in pkgs]],
                               timeout=self.settings.test_timeout_s)

    async def funcs(self) -> list[FuncInfo]:
        r = await self._run(["gohelper", "funcs", "."], max_chars=JSON_MAX_CHARS)
        if r.exit_code != 0:
            raise GoToolError("gohelper funcs failed", r)
        return [FuncInfo(key=FuncKey(file=o["file"], receiver=o["receiver"], name=o["name"]),
                         package=o["package"], start_line=o["start_line"], end_line=o["end_line"],
                         exported=o["exported"]) for o in json.loads(r.stdout)]

    async def decls(self, rel_dir: str) -> list[str]:
        r = await self._run(["gohelper", "decls", rel_dir], max_chars=JSON_MAX_CHARS)
        if r.exit_code != 0:
            raise GoToolError("gohelper decls failed", r)
        return json.loads(r.stdout)

    async def symbols(self) -> list[Symbol]:
        r = await self._run(["gohelper", "symbols", "."], max_chars=JSON_MAX_CHARS)
        if r.exit_code != 0:
            raise GoToolError("gohelper symbols failed", r)
        return [Symbol(**o) for o in json.loads(r.stdout)]

    async def merge(self, test_file: str, snippet: Path) -> CommandResult:
        return await self._run(["gohelper", "merge", test_file, str(snippet)])

    async def prune(self, test_file: str, names: list[str]) -> CommandResult:
        return await self._run(["gohelper", "prune", test_file, *names])

    async def asserts(self, go_file: Path) -> CommandResult:
        """`gohelper asserts`: a JSON list of the file's Test functions that never check a result."""
        return await self._run(["gohelper", "asserts", str(go_file)])

    async def mutate(self, go_file: str) -> list[dict[str, Any]]:
        """`gohelper mutate`: the file's operator mutation sites (file, line, col, offset, original, mutated, op)."""
        r = await self._run(["gohelper", "mutate", go_file], max_chars=JSON_MAX_CHARS)
        if r.exit_code != 0:
            raise GoToolError("gohelper mutate failed", r)
        return json.loads(r.stdout)

    async def test_package(self, pkg: GoPackage, timeout_s: float) -> CommandResult:
        """One mutant: `go test -count=1 -timeout=<t>` on one package; the build of a mutated file may take a while too."""
        return await self._run(["go", "test", "-count=1", f"-timeout={timeout_s:g}s", pkg.import_path],
                               timeout=self.settings.compile_timeout_s + timeout_s)
