# redress-fastapi-upstream-proxy

Small FastAPI + httpx scaffold for the Redress upstream proxy example.

Task 1 sets up two services:

- `proxy` with `GET /health`
- `upstream` with `GET /health`
- temporary proxy passthrough route `GET /proxy/ping`

Task 2 adds deterministic upstream demo modes behind `GET /demo/{mode}`:

- `success`
- `transient_then_success`
- `retry_after_then_success`
- `permanent_fail`
- `slow_timeout`

## Quickstart

Install dependencies:

```bash
uv sync --dev
```

Run the upstream service:

```bash
uv run uvicorn upstream.main:app --reload --host 127.0.0.1 --port 8080
```

Run the proxy service in a second terminal:

```bash
uv run uvicorn redress_fastapi_upstream_proxy.main:app --reload --host 127.0.0.1 --port 8000
```

Or start both services with Docker Compose:

```bash
docker compose up --build
```

## Smoke checks

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/proxy/ping
curl "http://127.0.0.1:8080/demo/transient_then_success?scenario_id=demo-a&failures=2"
curl "http://127.0.0.1:8080/demo/retry_after_then_success?scenario_id=demo-b&failures=1&retry_after_s=2"
```

## Environment

See [.env.example](.env.example) for the supported settings.
