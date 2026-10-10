# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
export MSYS_NO_PATHCONV := 1
GO_VERSION := $(strip $(file <.go-version))
ifeq ($(GO_VERSION),)
GO_VERSION := $(strip $(shell cat .go-version))
endif
GO_IMAGE := golang:$(GO_VERSION)
BACKEND_IMAGE ?= gca-backend
BACKEND_TEST_IMAGE ?= gca-backend-test
# The backend hardening from docker-compose.yml (keep the two in sync), so CI proves the hardened container still runs Go.
# The Go cache is a fresh named volume, as compose's `gocache` (created from the image, owned by app), removed afterwards.
IT_CACHE_VOLUME ?= gca-it-gocache
HARDENING := --cap-drop ALL --security-opt no-new-privileges:true --pids-limit 4096 --memory 4g --read-only --tmpfs /tmp:exec,size=512m --tmpfs /work:exec,uid=1000,gid=1000,size=2g -v $(IT_CACHE_VOLUME):/home/app/.cache
.PHONY: up backend-image backend-test-image test test-go test-backend test-integration frontend-deps test-frontend build-frontend lint lint-backend lint-frontend verify-evidence
# Frontend targets install dependencies only when node_modules is missing (CI runs `make frontend-deps` once first);
# `npm ci` would delete node_modules, which fails while a local Next server holds files in it.
FRONTEND_DEPS := [ -d node_modules ] || npm ci
up:
	docker compose up --build
backend-image:
	docker build -f backend/Dockerfile --build-arg GO_IMAGE=$(GO_IMAGE) -t $(BACKEND_IMAGE) .
backend-test-image:
	docker build -f backend/Dockerfile --build-arg GO_IMAGE=$(GO_IMAGE) --target test -t $(BACKEND_TEST_IMAGE) .
test: test-go test-backend test-integration test-frontend
test-go:
	docker run --rm -v "$(CURDIR)/tools/gohelper:/src" -w /src $(GO_IMAGE) sh -c "go vet ./... && go test ./..."
test-backend: backend-test-image
	docker run --rm $(BACKEND_TEST_IMAGE) pytest
test-integration: backend-test-image
	docker volume rm -f $(IT_CACHE_VOLUME) >/dev/null; \
	docker run --rm $(HARDENING) --env-file .env.example -v "$(CURDIR)/backend/tests/fixtures:/host-repos:ro" $(BACKEND_TEST_IMAGE) pytest -m integration; \
	status=$$?; docker volume rm -f $(IT_CACHE_VOLUME) >/dev/null; exit $$status
frontend-deps:
	cd frontend && npm ci
test-frontend:
	cd frontend && { $(FRONTEND_DEPS); } && npm test
build-frontend:
	cd frontend && { $(FRONTEND_DEPS); } && npm run build
lint: lint-backend lint-frontend
lint-backend: backend-test-image
	docker run --rm $(BACKEND_TEST_IMAGE) ruff check --no-cache .
lint-frontend:
	cd frontend && { $(FRONTEND_DEPS); } && npm run lint && npx tsc --noEmit
# Re-measures the committed evidence tests (docs/evidence) on a fresh clone of montanaflynn/stats; needs network.
verify-evidence:
	bash scripts/verify-evidence.sh docs/evidence/stats-e2de1ca387cb
	bash scripts/verify-evidence.sh docs/evidence/stats-73d630a6dd05
