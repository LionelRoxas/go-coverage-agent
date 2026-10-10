# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import ApiError, router
from app.config import Settings
from app.jobs import JobManager

log = logging.getLogger(__name__)


async def detect_go_version() -> str:
    try:
        proc = await asyncio.create_subprocess_exec("go", "version", stdout=asyncio.subprocess.PIPE)
        out, _ = await proc.communicate()
        return out.decode().split()[2] if proc.returncode == 0 else "unknown"
    except (OSError, IndexError):
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
        await asyncio.to_thread(manager.load_history)  # runs saved in OUTPUT_DIR stay viewable after a restart
        yield

    app = FastAPI(title="Go Coverage Agent", lifespan=lifespan)
    app.state.settings, app.state.manager, app.state.go_version = settings, manager, "unknown"
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)

    @app.middleware("http")
    async def _block_cross_origin_writes(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and origin is not None                 and origin not in settings.cors_origins:
            return JSONResponse({"error": {"code": "forbidden_origin", "message": "Cross-origin request blocked."}},
                                status_code=403)
        return await call_next(request)

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, e: ApiError) -> JSONResponse:
        return JSONResponse({"error": {"code": e.code, "message": e.message}}, status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def _invalid(_: Request, e: RequestValidationError) -> JSONResponse:
        first = e.errors()[0]
        where = ".".join(str(p) for p in first.get("loc", [])[1:])
        return JSONResponse({"error": {"code": "invalid_request", "message": f"{where}: {first.get('msg')}"}},
                            status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, e: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(e.status_code, "http_error")
        return JSONResponse({"error": {"code": code, "message": str(e.detail)}},
                            status_code=e.status_code, headers=getattr(e, "headers", None))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, e: Exception) -> JSONResponse:
        log.error("Unhandled error", exc_info=e)
        return JSONResponse({"error": {"code": "internal_error", "message": "Internal server error"}},
                            status_code=500)

    return app


app = create_app()
