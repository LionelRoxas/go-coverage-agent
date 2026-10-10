# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
# Targets: `runtime` (the last stage, so the default: compose and the Trivy scan build it) and `test` (dev deps + tests,
# built with `--target test` by `make test-backend` / `make test-integration`).
ARG GO_IMAGE=golang:1.27-bookworm
FROM ${GO_IMAGE} AS go
WORKDIR /src
COPY tools/gohelper/ ./
RUN CGO_ENABLED=0 go build -o /out/gohelper .

FROM python:3.12-slim-bookworm AS base
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY --from=go /usr/local/go /usr/local/go
COPY --from=go /out/gohelper /usr/local/bin/gohelper
ENV PATH=/opt/venv/bin:/usr/local/go/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy
# uv manages all Python packages; pip (bundled with the base image, with known CVEs) is removed once uv is in place.
RUN pip install --no-cache-dir uv==0.12.24 \
 && pip uninstall -y pip \
 && rm -rf /usr/local/lib/python3.12/ensurepip/_bundled
# uid 1000 runs untrusted generated tests, so it may write only its data folders. /app and /opt/venv stay owned by
# root and read-only to it: a test cannot plant code that the API server would load on its next start.
RUN useradd --create-home --uid 1000 app \
 && mkdir -p /work /output /repos /home/app/.cache/go-build /home/app/.cache/go-mod \
 && chown -R app:app /work /output /repos /home/app/.cache
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev --no-cache
COPY backend/app ./app
COPY backend/scripts ./scripts
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"]

FROM base AS test
RUN uv sync --frozen --no-install-project --no-cache
COPY backend/tests ./tests
# /app is read-only to `app`, so pytest keeps no .pytest_cache.
ENV PYTEST_ADDOPTS="-p no:cacheprovider"
USER app
CMD ["pytest"]

FROM base AS runtime
USER app
# The venv's uvicorn directly (on PATH): `uv run` may try to write to the venv, which is read-only to `app`.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
