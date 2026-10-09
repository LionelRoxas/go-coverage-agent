# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import ApiError, router
from app.config import Settings
from app.jobs import JobManager

log = logging.getLogger(__name__)


async def detect_go_version() -> str:
    try:
        proc = await asyncio.create_subprocess_exec("go", "version", stdout=asyncio.subprocess.PIPE)
        out, _ = await proc.communicate()
        return out.decode().split()[2] if proc.returncode == 0 else "unknown"
    except (FileNotFoundError, IndexError):
        return "unknown"


def create_app(settings: Settings | None = None, manager: JobManager | None = None) -> FastAPI:
    settings = settings or Settings()
    manager = manager or JobManager(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.go_version = await detect_go_version()
        for d in (settings.output_dir, settings.repos_dir):
            if not os.access(d, os.W_OK):
                log.warning("%s is not writable by this container user; on Linux run "
                            "`sudo chown -R 1000:1000 repos output` on the host.", d)
        yield

    app = FastAPI(title="Go Coverage Agent", lifespan=lifespan)
    app.state.settings, app.state.manager, app.state.go_version = settings, manager, "unknown"
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, e: ApiError) -> JSONResponse:
        return JSONResponse({"error": {"code": e.code, "message": e.message}}, status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def _invalid(_: Request, e: RequestValidationError) -> JSONResponse:
        first = e.errors()[0]
        where = ".".join(str(p) for p in first.get("loc", [])[1:])
        return JSONResponse({"error": {"code": "invalid_request", "message": f"{where}: {first.get('msg')}"}},
                            status_code=400)

    return app


app = create_app()
