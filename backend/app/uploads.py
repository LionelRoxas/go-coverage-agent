# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Saves a project folder uploaded from the browser under <repos_dir>/uploads/<name>.

Every part's filename is the file's path relative to the parent of the chosen folder ("myproj/pkg/a.go").
Paths are validated before anything is written; files are written into a hidden temp directory that
replaces the destination in one rename, and only a destination that an earlier upload created
(it holds MARKER) is ever replaced. The uploads folder itself is used only if this app created it
(it holds UPLOADS_MARKER).
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import secrets
import shutil
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from fastapi import Request
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from app.config import Settings
from app.gotools import read_module_info
from app import repos
from app.repos import RepoInfo, count_go_files

log = logging.getLogger(__name__)

MARKER = ".gca-upload"
UPLOADS = "uploads"
UPLOADS_MARKER = ".gca-uploads"
SKIP_REASONS = ("git", "vendor", "node_modules", "hidden", "too_large", "binary")
_SKIP_DIRS = {".git": "git", "vendor": "vendor", "node_modules": "node_modules"}
_SNIFF = 8192
_NAME_BAD = re.compile(r"[^a-z0-9._-]+")
# ':' would let a segment carry a drive ("Z:x") or an NTFS stream ("a.go:x") on a Windows host; the rest are
# characters Windows can't store. Rejected everywhere so the rules don't depend on the host.
_BAD_CHARS = frozenset(':<>"|?*')
_MAX_DEPTH = 64
_MAX_PATH_BYTES = 1024
_STALE_TMP_S = 3600  # temp folders left by a crash or kill are removed after an hour
_PART_OVERHEAD = 1024  # multipart headers per file part, for the raw body limit
NO_GO_MOD = "No go.mod at the top of the folder you chose. Pick the folder that contains go.mod."


class UploadError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _too_large(settings: Settings) -> UploadError:
    mb = settings.upload_max_bytes / (1024 * 1024)
    return UploadError(413, "upload_too_large",
                       f"This folder is too large to upload: the limit is {settings.upload_max_files:,} files and "
                       f"{mb:g} MB, after skipping .git, vendor, node_modules, hidden and binary files and files "
                       f"over {settings.upload_max_file_bytes / (1024 * 1024):g} MB. For large projects, set "
                       "HOST_REPOS_DIR in .env instead.")


def sanitize_name(raw: str) -> str:
    """Lowercase letters, digits, '-', '_' and '.'; at most 64 characters; never hidden, '.' or '..'."""
    name = _NAME_BAD.sub("-", raw.strip().lower()).strip("-.")[:64].strip("-.")
    if name in ("", ".", ".."):
        raise UploadError(400, "invalid_name", f"{raw!r} can't be used as a folder name; use letters or digits.")
    return name


def split_upload_path(raw: str) -> tuple[str, ...]:
    """'top/sub/file' -> ('top', 'sub', 'file'), or UploadError for anything that could escape the folder."""
    path = raw.replace("\\", "/")
    parts = tuple(path.split("/"))
    unsafe = (path.startswith("/") or not 2 <= len(parts) <= _MAX_DEPTH
              or len(path.encode("utf-8", "surrogatepass")) > _MAX_PATH_BYTES
              or any(ord(c) < 32 or c in _BAD_CHARS for c in path)
              or any(p in ("", ".", "..") or len(p.encode("utf-8", "surrogatepass")) > 255 for p in parts))
    if unsafe:
        raise UploadError(400, "invalid_path", f"Unsafe or invalid file path {raw!r}; nothing was saved.")
    return parts


def _skip_reason(rel: tuple[str, ...]) -> str | None:
    for part in rel[:-1]:
        if part in _SKIP_DIRS:
            return _SKIP_DIRS[part]
    if any(part.startswith(".") for part in rel):
        return "hidden"
    return None


@dataclass
class _Plan:
    name: str
    files: list[tuple[tuple[str, ...], BinaryIO]]
    skipped: dict[str, int] = field(default_factory=lambda: dict.fromkeys(SKIP_REASONS, 0))


def _plan(paths_and_files: list[tuple[str, BinaryIO]], name: str | None) -> _Plan:
    if not paths_and_files:
        raise UploadError(400, "no_files", "No files were uploaded.")
    tops, rels, seen = set(), [], set()
    for raw, fh in paths_and_files:
        top, *rest = split_upload_path(raw)
        rel = tuple(rest)
        if rel in seen:
            raise UploadError(400, "invalid_path", f"{raw!r} was uploaded twice; nothing was saved.")
        seen.add(rel)
        tops.add(top)
        rels.append((rel, fh))
    if len(tops) > 1:
        raise UploadError(400, "mixed_folders", "All files must come from one folder; choose a single project folder.")
    if ("go.mod",) not in seen:
        raise UploadError(400, "not_a_go_module", NO_GO_MOD)
    return _Plan(sanitize_name(name if name and name.strip() else tops.pop()), rels)


def _create(target: Path, rel: tuple[str, ...]):
    """Opens a new regular file at target, creating its folders; never opens an existing entry."""
    shown = "/".join(rel)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        return open(target, "xb")
    except (FileExistsError, NotADirectoryError, IsADirectoryError) as e:
        raise UploadError(400, "invalid_path", f"{shown!r} clashes with another uploaded path; nothing was saved.") from e
    except (OSError, RecursionError) as e:
        log.warning("upload: cannot create %s: %s", shown, e)
        raise UploadError(400, "invalid_path", f"{shown!r} can't be saved on this system; nothing was saved.") from e


def _write(plan: _Plan, tmp: Path, settings: Settings) -> None:
    """Writes the kept files into tmp (which must not exist yet) and counts the skipped ones."""
    tmp.mkdir()
    root = tmp.resolve()
    count = total = 0
    for rel, fh in plan.files:
        reason = _skip_reason(rel)
        if reason is None:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(0)
            head = fh.read(_SNIFF)
            if size > settings.upload_max_file_bytes:
                reason = "too_large"
            elif b"\x00" in head:
                reason = "binary"
        if reason is not None:
            plan.skipped[reason] += 1
            continue
        count, total = count + 1, total + size
        if count > settings.upload_max_files or total > settings.upload_max_bytes:
            raise _too_large(settings)
        target = tmp.joinpath(*rel)
        if not target.resolve().is_relative_to(root):
            raise UploadError(400, "invalid_path", f"Unsafe file path {'/'.join(rel)!r}; nothing was saved.")
        with _create(target, rel) as out:
            out.write(head)
            shutil.copyfileobj(fh, out)
    if not (tmp / "go.mod").is_file():  # go.mod itself was skipped (binary or too large)
        raise UploadError(400, "not_a_go_module", NO_GO_MOD)
    try:
        read_module_info(tmp)
    except (ValueError, OSError) as e:  # UnicodeDecodeError is a ValueError
        log.info("upload: unreadable go.mod: %s", e)
        raise UploadError(400, "not_a_go_module",
                          "The go.mod at the top of the folder can't be read or has no module line.") from e
    (tmp / MARKER).write_text("Created by a Go Coverage Agent upload; uploading the folder again replaces it.\n")


def _replaceable(dest: Path) -> bool:
    return not dest.is_symlink() and (not dest.exists() or (dest / MARKER).is_file())


def _name_taken(name: str) -> UploadError:
    return UploadError(409, "name_taken",
                       f"repos/{UPLOADS}/{name} already exists and was not created by an upload, so it was left "
                       "untouched. Choose a different name.")


def _swap(tmp: Path, dest: Path) -> None:
    if not _replaceable(dest):
        raise _name_taken(dest.name)
    old = None
    if dest.exists():
        old = dest.with_name(f".tmp-old-{secrets.token_hex(8)}")
        dest.rename(old)
    try:
        tmp.rename(dest)
    except OSError:
        if old is not None:
            old.rename(dest)
        raise
    if old is not None:
        shutil.rmtree(old, ignore_errors=True)


def _uploads_dir(settings: Settings) -> Path:
    """repos/uploads, created with UPLOADS_MARKER on first use; a folder of that name the app didn't create is refused."""
    root = settings.repos_dir.resolve()
    uploads = root / UPLOADS
    try:
        uploads.mkdir()
        (uploads / UPLOADS_MARKER).write_text("Folder uploads from the Go Coverage Agent UI live here.\n")
    except FileExistsError:
        pass
    except OSError as e:
        log.error("upload: cannot create %s: %s", uploads, e)
        raise UploadError(500, "upload_failed", f"Could not create repos/{UPLOADS}; check that the repos folder is writable.") from e
    if uploads.is_symlink() or not uploads.is_dir() or not uploads.resolve().is_relative_to(root):
        raise UploadError(500, "upload_failed", f"repos/{UPLOADS} must be a plain folder inside the repos folder.")
    if not (uploads / UPLOADS_MARKER).is_file():
        raise UploadError(409, "uploads_dir_taken",
                          f"repos/{UPLOADS} already exists and was not created by this app, so nothing was written to "
                          "it. Rename that folder to use uploads.")
    return uploads


def _remove_stale(uploads: Path) -> None:
    """Removes .tmp-* folders that a crashed or killed upload left behind."""
    cutoff = time.time() - _STALE_TMP_S
    for p in uploads.glob(".tmp-*"):
        try:
            if not p.is_symlink() and p.is_dir() and p.stat().st_mtime < cutoff:
                shutil.rmtree(p, ignore_errors=True)
        except OSError:
            continue


def _prepare_uploads(settings: Settings) -> Path:
    uploads = _uploads_dir(settings)
    _remove_stale(uploads)
    return uploads


def _swap_and_describe(tmp: Path, dest: Path, name: str) -> RepoInfo:
    _swap(tmp, dest)
    module, _ = read_module_info(dest)
    go, tests = count_go_files(dest)
    return RepoInfo(path=f"{UPLOADS}/{name}", module=module, go_files=go, test_files=tests)


async def _parse(request: Request, settings: Settings):
    if not request.headers.get("content-type", "").startswith("multipart/form-data"):
        raise UploadError(400, "invalid_upload", "Send the files as multipart/form-data in the field 'files'.")
    max_parts = 2 * settings.upload_max_files  # skipped files still arrive; the kept ones are capped later
    limit = 2 * settings.upload_max_bytes + max_parts * _PART_OVERHEAD
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise _too_large(settings)

    async def counted() -> AsyncGenerator[bytes, None]:
        received = 0
        async for chunk in request.stream():
            received += len(chunk)
            if received > limit:
                raise _too_large(settings)
            yield chunk

    parser = MultiPartParser(request.headers, counted(), max_files=max_parts, max_fields=8, max_part_size=4096)
    try:
        return await parser.parse()
    except MultiPartException as e:
        if str(e).startswith("Too many files"):
            raise _too_large(settings) from e
        raise UploadError(400, "invalid_upload", f"The upload could not be read: {e}") from e


async def receive_upload(request: Request, settings: Settings) -> dict:
    """Parses, validates and saves an uploaded folder; returns RepoInfo fields plus skipped counts."""
    form = await _parse(request, settings)
    try:
        files = form.getlist("files")
        if any(not isinstance(f, UploadFile) for f in files):
            raise UploadError(400, "invalid_upload", "Every 'files' part must be a file.")
        name = form.get("name")
        plan = _plan([(f.filename or "", f.file) for f in files], name if isinstance(name, str) else None)
        async with repos.repo_lock:
            uploads = await asyncio.to_thread(_prepare_uploads, settings)
        dest = uploads / plan.name
        if not _replaceable(dest):  # fail before writing; checked again under the lock
            raise _name_taken(plan.name)
        tmp = uploads / f".tmp-{secrets.token_hex(8)}"
        try:
            await asyncio.to_thread(_write, plan, tmp, settings)
            async with repos.repo_lock:  # jobs copy repos under the same lock, so they never see a half-swapped folder
                info = await asyncio.to_thread(_swap_and_describe, tmp, dest, plan.name)
        finally:
            if tmp.exists():
                await asyncio.to_thread(shutil.rmtree, tmp, ignore_errors=True)
    finally:
        await form.close()
    return {**info.model_dump(), "skipped": plan.skipped}
