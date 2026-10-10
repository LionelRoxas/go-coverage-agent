# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import asyncio
import errno
import os
import time

import httpx
import pytest

from app import uploads as uploads_mod
from app.config import Settings
from app.engine import setup as engine_setup
from app.jobs import JobManager
from app.main import create_app
from app.models import JobRequest
from app import repos as repos_mod
from app.uploads import UploadError, sanitize_name, split_upload_path
from app.workspace import WorkspaceError
from app.workspace import resolve_repo

GOMOD = b"module example.com/myproj\n\ngo 1.22\n"
PROJECT = {
    "myproj/go.mod": GOMOD,
    "myproj/a.go": b"package myproj\n",
    "myproj/a_test.go": b"package myproj\n",
    "myproj/pkg/b.go": b"package pkg\n",
}


def make_app(tmp_path, **overrides):
    repos = tmp_path / "repos"
    repos.mkdir()
    kw = dict(groq_api_key="k", repos_dir=repos, work_dir=tmp_path / "work", output_dir=tmp_path / "out")
    kw.update(overrides)
    settings = Settings(**kw)
    return create_app(settings, JobManager(settings)), repos


async def post(app, files: dict[str, bytes], name: str | None = None, headers: dict | None = None):
    data = {"name": name} if name is not None else None
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        return await c.post("/api/repos/upload", files=[("files", (p, b)) for p, b in files.items()],
                            data=data, headers=headers)


def leftovers(repos):
    uploads = repos / "uploads"
    return sorted(p.name for p in uploads.iterdir() if p.name != ".gca-uploads") if uploads.exists() else []


def own_uploads_dir(repos):
    """repos/uploads as an earlier upload left it: created by the app, with its marker."""
    (repos / "uploads").mkdir()
    (repos / "uploads" / ".gca-uploads").write_text("")
    return repos / "uploads"


async def test_upload_saves_project_lists_it_and_resolves(tmp_path):
    app, repos = make_app(tmp_path)
    r = await post(app, PROJECT)
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["path"], body["module"], body["go_files"], body["test_files"]) == \
        ("uploads/myproj", "example.com/myproj", 2, 1)
    assert body["skipped"] == {"git": 0, "vendor": 0, "node_modules": 0, "hidden": 0, "too_large": 0, "binary": 0}
    dest = repos / "uploads" / "myproj"
    assert (dest / "pkg" / "b.go").read_bytes() == b"package pkg\n"
    assert (dest / ".gca-upload").is_file()
    assert leftovers(repos) == ["myproj"]  # no .tmp-* directory left behind
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        listed = (await c.get("/api/repos")).json()
    assert [x["path"] for x in listed] == ["uploads/myproj"]
    assert resolve_repo(repos, "uploads/myproj") == dest.resolve()


async def test_upload_uses_sanitized_name_field(tmp_path):
    app, repos = make_app(tmp_path)
    r = await post(app, PROJECT, name="  My Proj!  ")
    assert r.status_code == 200, r.text
    assert r.json()["path"] == "uploads/my-proj"
    assert (repos / "uploads" / "my-proj" / "go.mod").is_file()


async def test_reupload_replaces_a_marked_directory(tmp_path):
    app, repos = make_app(tmp_path)
    assert (await post(app, {**PROJECT, "myproj/old.go": b"package myproj\n"})).status_code == 200
    r = await post(app, {**PROJECT, "myproj/new.go": b"package myproj\n"})
    assert r.status_code == 200, r.text
    dest = repos / "uploads" / "myproj"
    assert (dest / "new.go").is_file() and not (dest / "old.go").exists()
    assert leftovers(repos) == ["myproj"]


async def test_existing_unmarked_directory_is_never_replaced(tmp_path):
    app, repos = make_app(tmp_path)
    mine = own_uploads_dir(repos) / "myproj"
    mine.mkdir()
    (mine / "precious.go").write_text("package mine\n")
    r = await post(app, PROJECT)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "name_taken"
    assert (mine / "precious.go").read_text() == "package mine\n"
    assert leftovers(repos) == ["myproj"]


@pytest.mark.parametrize("bad", [
    "../x/go.mod", "/etc/x", "C:/x/go.mod", "myproj/../../b", "myproj\\..\\..\\b",
    "C:\\x\\go.mod", "\\\\srv\\share\\go.mod", "myproj//b.go", "myproj/./b.go", "myproj/", "go.mod",
    "myproj/sub/Z:evil.go", "myproj/a.go:x", "myproj/a?.go", "myproj/" + "d/" * 70 + "deep.go",
    "myproj/" + "/".join(c * 250 for c in "xyzwv") + ".go",  # 1,267 bytes: over the 1,024-byte path cap
])
async def test_unsafe_paths_are_rejected_and_nothing_is_written(tmp_path, bad):
    app, repos = make_app(tmp_path)
    before = {p for p in tmp_path.rglob("*")}
    r = await post(app, {**PROJECT, bad: b"package evil\n"})
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "invalid_path"
    assert {p for p in tmp_path.rglob("*")} - before <= {repos / "uploads"}
    assert leftovers(repos) == []


@pytest.mark.parametrize("bad", ["my\x00proj/go.mod", "/abs/x", "\\abs\\x", "D:rel/x", "a/../b", "a/b/..", "a\\.\\b", "a",
                                 "a/Z:x", "a/b.go:stream", 'a/b"c', "a/b|c", "a/b\tc", "a/" + "b/" * 63 + "c",
                                 "a/" + "é" * 600])
def test_split_upload_path_rejects(bad):
    with pytest.raises(UploadError) as e:
        split_upload_path(bad)
    assert e.value.status == 400 and e.value.code == "invalid_path"


def test_split_upload_path_normalizes_backslashes():
    assert split_upload_path("myproj\\pkg\\a.go") == ("myproj", "pkg", "a.go")


def test_split_upload_path_accepts_the_depth_limit():
    assert len(split_upload_path("a/" + "b/" * 62 + "c")) == 64


@pytest.mark.parametrize("raw,want", [("MyProj", "myproj"), ("my proj", "my-proj"), (".hidden", "hidden"),
                                      ("a" * 80, "a" * 64), ("v1.2_x-y", "v1.2_x-y")])
def test_sanitize_name(raw, want):
    assert sanitize_name(raw) == want


@pytest.mark.parametrize("raw", ["", ".", "..", "!!!", "---"])
def test_sanitize_name_rejects_empty(raw):
    with pytest.raises(UploadError) as e:
        sanitize_name(raw)
    assert e.value.code == "invalid_name"


async def test_mixed_top_folders_are_rejected(tmp_path):
    app, repos = make_app(tmp_path)
    r = await post(app, {**PROJECT, "other/c.go": b"package other\n"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "mixed_folders"
    assert leftovers(repos) == []


async def test_missing_top_level_go_mod_is_rejected(tmp_path):
    app, repos = make_app(tmp_path)
    r = await post(app, {"myproj/a.go": b"package a\n", "myproj/sub/go.mod": GOMOD})
    assert r.status_code == 400
    assert r.json()["error"] == {"code": "not_a_go_module", "message":
                                 "No go.mod at the top of the folder you chose. Pick the folder that contains go.mod."}
    assert leftovers(repos) == []


async def test_go_mod_without_module_directive_is_rejected(tmp_path):
    app, repos = make_app(tmp_path)
    r = await post(app, {**PROJECT, "myproj/go.mod": b"go 1.22\n"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "not_a_go_module"
    assert leftovers(repos) == []


async def test_empty_upload_is_rejected(tmp_path):
    app, _ = make_app(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/repos/upload", data={"name": "x"}, files=[])
    assert r.status_code == 400


async def test_duplicate_paths_are_rejected(tmp_path):
    app, repos = make_app(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/repos/upload", files=[("files", (p, b)) for p, b in PROJECT.items()]
                         + [("files", ("myproj/a.go", b"package dup\n"))])
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_path"
    assert leftovers(repos) == []


async def test_too_many_files_is_413_and_cleans_up(tmp_path):
    app, repos = make_app(tmp_path, upload_max_files=3)
    r = await post(app, PROJECT)  # 4 accepted files
    assert r.status_code == 413 and r.json()["error"]["code"] == "upload_too_large"
    assert "3 files" in r.json()["error"]["message"]
    assert leftovers(repos) == []


async def test_too_many_bytes_is_413_and_cleans_up(tmp_path):
    app, repos = make_app(tmp_path, upload_max_bytes=100)
    r = await post(app, {**PROJECT, "myproj/big.go": b"// x\n" * 30})
    assert r.status_code == 413 and r.json()["error"]["code"] == "upload_too_large"
    assert leftovers(repos) == []


async def test_oversized_request_body_is_413_before_parsing(tmp_path):
    app, repos = make_app(tmp_path, upload_max_bytes=1000, upload_max_files=2)
    r = await post(app, {**PROJECT, "myproj/huge.go": b"x" * 10_000})
    assert r.status_code == 413 and r.json()["error"]["code"] == "upload_too_large"
    assert leftovers(repos) == []


async def test_too_many_parts_is_413(tmp_path):
    app, repos = make_app(tmp_path, upload_max_files=2)
    junk = {f"myproj/.git/objects/{i}": b"x" for i in range(10)}
    r = await post(app, {**PROJECT, **junk})
    assert r.status_code == 413 and r.json()["error"]["code"] == "upload_too_large"
    assert leftovers(repos) == []


async def test_skipped_files_are_counted_and_not_written(tmp_path):
    app, repos = make_app(tmp_path, upload_max_file_bytes=1000)
    extra = {
        "myproj/.git/HEAD": b"ref: refs/heads/main\n",
        "myproj/.git/config": b"[core]\n",
        "myproj/vendor/x/y.go": b"package y\n",
        "myproj/node_modules/z/index.js": b"//\n",
        "myproj/.github/ci.yml": b"on: push\n",
        "myproj/.env": b"SECRET=1\n",
        "myproj/big.go": b"x" * 1001,
        "myproj/logo.png": b"\x89PNG\x00\x00data",
        "myproj/testdata/in.txt": b"kept\n",
    }
    r = await post(app, {**PROJECT, **extra})
    assert r.status_code == 200, r.text
    assert r.json()["skipped"] == {"git": 2, "vendor": 1, "node_modules": 1, "hidden": 2, "too_large": 1, "binary": 1}
    dest = repos / "uploads" / "myproj"
    written = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    assert written == [".gca-upload", "a.go", "a_test.go", "go.mod", "pkg/b.go", "testdata/in.txt"]


async def test_wrong_origin_is_forbidden_and_writes_nothing(tmp_path):
    app, repos = make_app(tmp_path)
    r = await post(app, PROJECT, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden_origin"
    assert not (repos / "uploads").exists()
    r = await post(app, PROJECT, headers={"Origin": "http://localhost:3000"})
    assert r.status_code == 200


async def test_non_multipart_body_is_400(tmp_path):
    app, _ = make_app(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/repos/upload", json={"files": []})
    assert r.status_code == 400


async def test_streamed_body_without_length_is_cut_off_at_the_limit(tmp_path):
    app, repos = make_app(tmp_path, upload_max_bytes=1000, upload_max_files=2)
    boundary = "b0undary"
    head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"myproj/go.mod\"\r\n"
            "Content-Type: application/octet-stream\r\n\r\n").encode()

    async def body():
        yield head
        for _ in range(100):  # 100 KB, far over the ~6 KB raw limit
            yield b"x" * 1024

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/repos/upload", content=body(),
                         headers={"content-type": f"multipart/form-data; boundary={boundary}"})
    assert r.status_code == 413 and r.json()["error"]["code"] == "upload_too_large"
    assert "content-length" not in r.request.headers
    assert leftovers(repos) == []


async def test_uploaded_marker_file_is_skipped_and_the_app_writes_its_own(tmp_path):
    app, repos = make_app(tmp_path)
    r = await post(app, {**PROJECT, "myproj/.gca-upload": b"forged"})
    assert r.status_code == 200, r.text
    assert r.json()["skipped"]["hidden"] == 1
    assert (repos / "uploads" / "myproj" / ".gca-upload").read_text().startswith("Created by a Go Coverage Agent upload")


async def test_case_only_duplicates_are_kept_or_refused_cleanly(tmp_path):
    app, repos = make_app(tmp_path)
    r = await post(app, {**PROJECT, "myproj/A.go": b"package a\n", "myproj/a2.go": b"package a\n",
                         "myproj/pkg/B.go": b"package pkg\n"})
    if r.status_code == 200:  # case-sensitive filesystem (Linux): both names kept
        assert (repos / "uploads" / "myproj" / "pkg" / "B.go").is_file()
    else:  # case-insensitive (Windows, macOS): the second create clashes and nothing is kept
        assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_path"
        assert leftovers(repos) == []


async def test_top_folder_of_dots_is_an_invalid_name(tmp_path):
    app, repos = make_app(tmp_path)
    r = await post(app, {"...": b"", **{p.replace("myproj", "...", 1): b for p, b in PROJECT.items()}})
    assert r.status_code == 400 and r.json()["error"]["code"] in ("invalid_name", "invalid_path")
    r = await post(app, {p.replace("myproj", "...", 1): b for p, b in PROJECT.items()})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_name"
    assert leftovers(repos) == []


async def test_unwritable_name_is_400_without_host_paths(tmp_path, monkeypatch):
    app, repos = make_app(tmp_path)
    real_open = open

    def fake_open(path, mode="r", *a, **k):
        if str(path).endswith("a.go") and "x" in mode:
            raise OSError(errno.ENAMETOOLONG, "File name too long", str(path))
        return real_open(path, mode, *a, **k)

    monkeypatch.setattr(uploads_mod, "open", fake_open, raising=False)
    r = await post(app, PROJECT)
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_path"
    assert "can't be saved on this system" in r.json()["error"]["message"]
    assert str(tmp_path) not in r.text and "tmp-" not in r.text
    assert leftovers(repos) == []


async def test_unreadable_go_mod_message_has_no_paths(tmp_path):
    app, repos = make_app(tmp_path)
    r = await post(app, {**PROJECT, "myproj/go.mod": b"\xff\xfe module x\n"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "not_a_go_module"
    assert str(tmp_path) not in r.text and "tmp-" not in r.text
    assert leftovers(repos) == []


async def test_stale_temp_folders_are_removed_and_fresh_ones_kept(tmp_path):
    app, repos = make_app(tmp_path)
    uploads = own_uploads_dir(repos)
    old, fresh = uploads / ".tmp-deadbeef", uploads / ".tmp-old-cafe"
    for d in (old, fresh):
        (d / "pkg").mkdir(parents=True)
        (d / "pkg" / "x.go").write_text("package pkg\n")
    hour_ago = time.time() - 2 * 3600
    os.utime(old, (hour_ago, hour_ago))
    assert (await post(app, PROJECT)).status_code == 200
    assert not old.exists() and fresh.exists()


async def test_foreign_uploads_folder_is_never_written_into(tmp_path):
    app, repos = make_app(tmp_path)
    theirs = repos / "uploads"
    theirs.mkdir()
    (theirs / "go.mod").write_text("module example.com/uploads\n")
    r = await post(app, PROJECT)
    assert r.status_code == 409 and r.json()["error"]["code"] == "uploads_dir_taken"
    assert sorted(p.name for p in theirs.iterdir()) == ["go.mod"]


def _symlink_or_skip(link, target):
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available on this host")


async def test_symlinked_uploads_folder_is_refused(tmp_path):
    app, repos = make_app(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / ".gca-uploads").write_text("")
    _symlink_or_skip(repos / "uploads", elsewhere)
    r = await post(app, PROJECT)
    assert r.status_code == 500 and r.json()["error"]["code"] == "upload_failed"
    assert sorted(p.name for p in elsewhere.iterdir()) == [".gca-uploads"]


async def test_symlinked_destination_is_name_taken(tmp_path):
    app, repos = make_app(tmp_path)
    uploads = own_uploads_dir(repos)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / ".gca-upload").write_text("")
    _symlink_or_skip(uploads / "myproj", elsewhere)
    r = await post(app, PROJECT)
    assert r.status_code == 409 and r.json()["error"]["code"] == "name_taken"
    assert sorted(p.name for p in elsewhere.iterdir()) == [".gca-upload"]


async def test_job_copies_the_repo_only_while_holding_the_repo_lock(tmp_path, monkeypatch):
    repos = tmp_path / "repos"
    (repos / "m").mkdir(parents=True)
    (repos / "m" / "go.mod").write_text("module m\n")
    settings = Settings(groq_api_key="k", repos_dir=repos, work_dir=tmp_path / "w", output_dir=tmp_path / "o")
    held = []

    def fake_create(*a, **k):
        held.append(repos_mod.repo_lock.locked())
        raise WorkspaceError("stop here")

    monkeypatch.setattr(engine_setup.Workspace, "create", fake_create)
    async with repos_mod.repo_lock:
        task = asyncio.create_task(engine_setup.prepare("j", JobRequest(repo_path="m", target_coverage=80), settings,
                                                        None, None, asyncio.Event()))
        await asyncio.sleep(0.05)
        assert held == []  # waits while an upload swap (or clone) holds the lock
    with pytest.raises(engine_setup.JobFailed):
        await task
    assert held == [True]
