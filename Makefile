UV ?= uv
PROXY_HOST ?= 127.0.0.1
PROXY_PORT ?= 8000
UPSTREAM_HOST ?= 127.0.0.1
UPSTREAM_PORT ?= 8080

.PHONY: install proxy upstream docker-up test lint format-check

install:
	$(UV) sync --dev

proxy:
	UPSTREAM_BASE_URL=http://$(UPSTREAM_HOST):$(UPSTREAM_PORT) \
	PROXY_HOST=$(PROXY_HOST) \
	PROXY_PORT=$(PROXY_PORT) \
	$(UV) run uvicorn redress_fastapi_upstream_proxy.main:app --reload --host $(PROXY_HOST) --port $(PROXY_PORT)

upstream:
	UPSTREAM_HOST=$(UPSTREAM_HOST) \
	UPSTREAM_PORT=$(UPSTREAM_PORT) \
	$(UV) run uvicorn upstream.main:app --reload --host $(UPSTREAM_HOST) --port $(UPSTREAM_PORT)

docker-up:
	docker compose up --build

test:
	$(UV) run pytest -q

lint:
	$(UV) run ruff check .

format-check:
	$(UV) run ruff format --check .
