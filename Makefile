# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
GO_IMAGE := golang:$(shell cat .go-version)
.PHONY: up backend-image test test-go test-backend test-integration test-frontend
up:
	docker compose up --build
backend-image:
	docker build -f backend/Dockerfile --build-arg GO_IMAGE=$(GO_IMAGE) -t gca-backend .
test: test-go test-backend test-integration test-frontend
test-go:
	MSYS_NO_PATHCONV=1 docker run --rm -v "$(CURDIR)/tools/gohelper:/src" -w /src $(GO_IMAGE) go test ./...
test-backend: backend-image
	docker run --rm gca-backend uv run --no-sync pytest
test-integration: backend-image
	docker run --rm gca-backend uv run --no-sync pytest -m integration
test-frontend:
	cd frontend && npm ci && npm test
