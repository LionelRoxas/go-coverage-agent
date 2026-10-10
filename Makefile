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
HARDENING := --cap-drop ALL --security-opt no-new-privileges:true --pids-limit 512 --memory 4g --read-only --tmpfs /tmp:exec --tmpfs /work:exec,uid=1000,gid=1000 --tmpfs /home/app/.cache:exec,uid=1000,gid=1000
.PHONY: up backend-image backend-test-image test test-go test-backend test-integration test-frontend build-frontend lint lint-backend lint-frontend
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
	docker run --rm $(HARDENING) --env-file .env.example -v "$(CURDIR)/backend/tests/fixtures:/host-repos:ro" $(BACKEND_TEST_IMAGE) pytest -m integration
test-frontend:
	cd frontend && npm ci && npm test
build-frontend:
	cd frontend && npm ci && npm run build
lint: lint-backend lint-frontend
lint-backend: backend-test-image
	docker run --rm $(BACKEND_TEST_IMAGE) ruff check --no-cache .
lint-frontend:
	cd frontend && npm ci && npm run lint && npx tsc --noEmit
