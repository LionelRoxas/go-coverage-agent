# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
export MSYS_NO_PATHCONV := 1
GO_VERSION := $(strip $(file <.go-version))
ifeq ($(GO_VERSION),)
GO_VERSION := $(strip $(shell cat .go-version))
endif
GO_IMAGE := golang:$(GO_VERSION)
.PHONY: up backend-image test test-go test-backend test-integration test-frontend build-frontend
up:
	docker compose up --build
backend-image:
	docker build -f backend/Dockerfile --build-arg GO_IMAGE=$(GO_IMAGE) -t gca-backend .
test: test-go test-backend test-integration test-frontend
test-go:
	docker run --rm -v "$(CURDIR)/tools/gohelper:/src" -w /src $(GO_IMAGE) sh -c "go vet ./... && go test ./..."
test-backend: backend-image
	docker run --rm gca-backend uv run --no-sync pytest
test-integration: backend-image
	docker run --rm --env-file .env.example -v "$(CURDIR)/backend/tests/fixtures:/host-repos:ro" gca-backend uv run --no-sync pytest -m integration
test-frontend:
	cd frontend && npm ci && npm test
build-frontend:
	cd frontend && npm ci && npm run build
