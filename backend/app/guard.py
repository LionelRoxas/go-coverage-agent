# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Static checks on LLM-written test code before anything is compiled or executed.

This is defence in depth, not a sandbox. A pattern list over model-written source cannot prove what the code does:
string concatenation, reflection or another standard-library package can rebuild much of what it refuses. It turns
the obvious mistakes and the obvious attacks into a clear `guard_rejected` the Fixer can act on. The boundary is the
container (Task 54): read-only application code, dropped capabilities, no new privileges, pid and memory limits.
Generated tests still run in the backend container, which holds the Groq key and has network access; a separate
runner without the key and without network is production work, not part of this project."""
from __future__ import annotations

import re

from app.models import TestSnippet

DENIED_IMPORTS = {"C", "os/exec", "runtime/cgo", "syscall", "unsafe", "plugin", "runtime/debug",
                  "crypto/tls", "log/syslog"}  # tls.Dial and syslog.Dial open network connections
DENIED_IMPORT_TREES = ("net", "golang.org/x/net")  # the package and every package under it
_IMPORT_PATH = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]*")
_TEST_FUNC = re.compile(r"^func (Test(?!Main\()[A-Z0-9_]\w*)\(", re.M)
_KEYWORD = re.compile(r"\b(import|package)\b")
_DIRECTIVE = re.compile(r"^\s*//go:", re.M)
_START_PROCESS = re.compile(r"\bStartProcess\b")
_FLOAT_TO_INT = re.compile(r"\b(?:u?int(?:8|16|32|64)?|uintptr)\(\s*math\.(?:Inf|NaN)\(")
_BUILD_TAG = re.compile(r"^\s*//\s*(go:build|\+build)", re.M)
_SPECIAL_FUNC = re.compile(r"^func\s+(init|TestMain)\s*\(", re.M)
_ROOT_JOIN = re.compile(r"\b(?:filepath|path)\.Join\(\s*(?:\"/\"|`/`)\s*[,)]")
_ENVIRON = re.compile(r"\benviron\b")  # the word only: "environment" in a message is fine
_ABS_PATH_OP = re.compile(r"\bos\.(?:WriteFile|Create|OpenFile|Mkdir|MkdirAll|Remove|RemoveAll|Rename|Symlink|Link|"
                          r"Chmod|Chown|Truncate)\(\s*[\"`]/")


def _is_stdlib(path: str) -> bool:
    return "." not in path.split("/")[0]


def go_segments(code: str) -> list[tuple[str, str | None]]:
    """Split Go source into (text, blank) pieces. `blank` is None for code and the stand-in for comments/literals."""
    out: list[tuple[str, str | None]] = []
    i, n, start = 0, len(code), 0

    def flush(upto: int) -> None:
        if upto > start:
            out.append((code[start:upto], None))

    while i < n:
        if code.startswith("//", i):
            end = code.find(chr(10), i)
            j, blank = (n if end == -1 else end), " "
        elif code.startswith("/*", i):
            end = code.find("*/", i + 2)
            j, blank = (n if end == -1 else end + 2), " "
        elif code[i] in "\"'":
            quote, j = code[i], i + 1
            while j < n and code[j] not in (quote, chr(10)):
                j += 2 if code[j] == "\\" else 1
            blank = quote * 2
            j = j + 1 if j < n and code[j] == quote else j
        elif code[i] == "`":
            end = code.find("`", i + 1)
            j, blank = (n if end == -1 else end + 1), "``"
        else:
            i += 1
            continue
        flush(i)
        out.append((code[i:j], blank))
        i = start = j
    flush(n)
    return out


def _strip_go(code: str) -> str:
    """Blank out comments and literal contents so keyword checks only see code tokens."""
    return "".join(text if blank is None else blank for text, blank in go_segments(code))


def _is_comment(text: str, blank: str | None) -> bool:
    return blank is not None and text.startswith(("//", "/*"))


def _matches_in_code(pattern: re.Pattern[str], code: str) -> bool:
    """A match that starts in code, not inside a comment or a string literal (e.g. Go source held in a raw string).
    The match may run on into literals: that is where the arguments it checks are."""
    spans, pos = [], 0
    for text, blank in go_segments(code):
        if blank is None:
            spans.append((pos, pos + len(text)))
        pos += len(text)
    return any(a <= m.start() < b for m in pattern.finditer(code) for a, b in spans)


def _denied_import(imp: str) -> bool:
    return imp in DENIED_IMPORTS or any(imp == tree or imp.startswith(tree + "/") for tree in DENIED_IMPORT_TREES)


def check_snippet(snippet: TestSnippet, module: str, max_bytes: int = 40_000) -> list[str]:
    problems: list[str] = []
    for imp in snippet.imports:
        if not _IMPORT_PATH.fullmatch(imp):
            problems.append(f"invalid import path {imp!r}")
        elif _denied_import(imp):
            problems.append(f"import {imp!r} is not allowed in generated tests")
        elif not _is_stdlib(imp) and imp != module and not imp.startswith(module + "/"):
            problems.append(f"import {imp!r} is not in the standard library or this module")
    code = snippet.code
    if _KEYWORD.search(_strip_go(code)):
        problems.append("`code` must not contain a package clause or import declarations; list import paths in `imports`")
    if _FLOAT_TO_INT.search(_strip_go(code)):
        problems.append("asserts a platform-dependent float->int conversion of NaN/Inf (x86 and ARM give different results); drop that case")
    if _START_PROCESS.search(_strip_go(code)):
        problems.append("`StartProcess` is not allowed in generated tests (tests must not start processes)")
    segments = go_segments(code)
    if any("/proc/" in text for text, blank in segments if not _is_comment(text, blank)):
        problems.append("the path `/proc/` is not allowed in generated tests (tests must not read process state)")
    if any(_ENVIRON.search(text) for text, blank in segments if blank is not None and not _is_comment(text, blank)):
        problems.append("string literals containing the word `environ` are not allowed (tests must not read the process "
                        "environment); reword or drop that string")
    if _matches_in_code(_ROOT_JOIN, code):
        problems.append('building a path from the filesystem root (`filepath.Join("/", ...)` or `path.Join("/", ...)`) '
                        "is not allowed; start file paths with `t.TempDir()`")
    if _matches_in_code(_ABS_PATH_OP, code):
        problems.append("file operations on an absolute path literal are not allowed; write only under `t.TempDir()`")
    for name in dict.fromkeys(_SPECIAL_FUNC.findall(_strip_go(code))):
        what = "an init function" if name == "init" else "TestMain"
        problems.append(f"`func {name}(` is not allowed: generated tests must not declare {what}; "
                        "put any setup inside the Test functions")
    if _BUILD_TAG.search(code):
        problems.append("build constraints are not allowed")
    if _DIRECTIVE.search(code):
        problems.append("compiler directives (//go:...) are not allowed")
    if "#cgo" in code:
        problems.append("cgo directives are not allowed")
    if len(code.encode()) > max_bytes:
        problems.append(f"code is larger than {max_bytes} bytes")
    if not _TEST_FUNC.search(code):
        problems.append("no `func TestXxx(t *testing.T)` found")
    return problems


def render_snippet(package: str, snippet: TestSnippet) -> str:
    imports = sorted(set(snippet.imports))
    block = "import (\n" + "".join(f'\t"{p}"\n' for p in imports) + ")\n\n" if imports else ""
    return f"package {package}\n\n{block}{snippet.code.strip()}\n"


def test_names(code: str) -> list[str]:
    return _TEST_FUNC.findall(code)


test_names.__test__ = False  # not a pytest test
