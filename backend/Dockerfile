# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
ARG GO_IMAGE=golang:1.27-bookworm
FROM ${GO_IMAGE} AS go
WORKDIR /src
COPY tools/gohelper/ ./
RUN CGO_ENABLED=0 go build -o /out/gohelper .

FROM python:3.12-slim-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY --from=go /usr/local/go /usr/local/go
COPY --from=go /out/gohelper /usr/local/bin/gohelper
ENV PATH=/usr/local/go/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy
RUN pip install --no-cache-dir uv==0.12.24
RUN useradd --create-home --uid 1000 app \
 && mkdir -p /work /output /repos /home/app/.cache/go-build /home/app/.cache/go-mod /opt/venv \
 && chown -R app:app /work /output /repos /home/app/.cache /opt/venv
WORKDIR /app
COPY --chown=app:app backend/pyproject.toml backend/uv.lock ./
USER app
RUN uv sync --frozen --no-install-project
COPY --chown=app:app backend/ ./
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
