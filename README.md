# redress-fastapi-upstream-proxy

`redress-fastapi-upstream-proxy` demonstrates Redress as explicit service-level
failure policy in a normal FastAPI + `httpx` application.

The point of the repo is not "here is a retry decorator." The point is:

- semantic failure classification at the transport boundary
- one explicit retry policy object
- bounded retries with per-attempt timeout and overall deadline
- compact exception-first flow with `policy.call(...)`
- structured outcome flow with `policy.execute(...)`
- intentional contrast path with no retry at all
- visible stop reasons and lightweight debug events

## What This Example Demonstrates

This repo is meant to answer four practical questions:

1. How hard is it to add Redress to a normal FastAPI service?
2. Does the compact path still read well in application code?
3. What does Redress add beyond "retry this exception a few times"?
4. How do structured outcomes and explicit no-retry paths look in practice?

## Why This Is More Than A Retry Decorator

The proxy does not branch on raw upstream status codes in its route handlers.
Instead:

1. The upstream client raises semantic exceptions such as
   `UpstreamTransientError` and `UpstreamRateLimitedError`.
2. A small classifier maps those exceptions into Redress `ErrorClass` values.
3. A centralized `AsyncPolicy(retry=AsyncRetry(...))` decides whether to retry,
   stop, or expose a structured outcome.
4. The service layer can choose between:
   - `policy.call(...)` for compact exception-first code
   - `policy.execute(...)` for a structured `RetryOutcome`-style response
   - no Redress at all for an intentional contrast path

That separation is the core value proposition of the example.

## Architecture

```text
client
  |
  v
proxy FastAPI app
  |
  +--> UpstreamDemoClient (httpx)
  |      |
  |      +--> semantic upstream exceptions
  |
  +--> classify_upstream_error(...)
  |
  +--> AsyncPolicy(retry=AsyncRetry(...))
  |      |
  |      +--> /proxy/call
  |      +--> /proxy/execute
  |
  +--> EventRecorder
         |
         +--> /debug/events

upstream FastAPI app
  |
  +--> named deterministic demo modes under /demo/{mode}
```

The key files are:

- [`src/redress_fastapi_upstream_proxy/upstream_client.py`](src/redress_fastapi_upstream_proxy/upstream_client.py)
- [`src/redress_fastapi_upstream_proxy/classifiers.py`](src/redress_fastapi_upstream_proxy/classifiers.py)
- [`src/redress_fastapi_upstream_proxy/policies.py`](src/redress_fastapi_upstream_proxy/policies.py)
- [`src/redress_fastapi_upstream_proxy/service.py`](src/redress_fastapi_upstream_proxy/service.py)
- [`src/redress_fastapi_upstream_proxy/observability.py`](src/redress_fastapi_upstream_proxy/observability.py)
- [`upstream/main.py`](upstream/main.py)

## The Three Primary Routes

### `GET /proxy/call`

This is the compact, ergonomic path.

It uses `policy.call(...)` and returns either:

- the successful upstream payload
- or a downstream HTTP error translated from terminal Redress semantics

This is the route to look at if you want the shortest plausible "good
integration" path.

### `GET /proxy/execute`

This is the structured-outcome path.

It uses `policy.execute(...)` and returns fields such as:

- `ok`
- `attempts`
- `stop_reason`
- `last_class`
- `cause`
- `elapsed_s`
- `next_sleep_s`
- `operation`
- `value`
- `last_error`

This route is where Redress becomes visibly different from a decorator-first
retry library.

### `GET /proxy/no-retry`

This is the intentional contrast path.

It calls the upstream client directly and does not use Redress. The point is to
show that retry is a policy choice, not a reflex.

## Supporting Routes

- `GET /health` on both services
- `GET /proxy/ping` as a minimal proxy-to-upstream smoke check
- `GET /debug/events` for recent Redress lifecycle events

## Upstream Demo Modes

The upstream service exposes deterministic named modes under
`GET /demo/{mode}`:

- `success`
  Immediate `200`.
- `transient_then_success`
  Returns `503` for the first `failures` attempts for a given `scenario_id`,
  then succeeds.
- `retry_after_then_success`
  Returns `429` with `Retry-After` for the first `failures` attempts for a
  given `scenario_id`, then succeeds.
- `permanent_fail`
  Always returns a configured 4xx such as `404`.
- `slow_timeout`
  Sleeps for `delay_s` and then returns `200`. The proxy's attempt timeout is
  what turns this into retry or deadline behavior.

The upstream keeps per-scenario state in memory. Reusing the same `(mode,
scenario_id)` with different parameters returns `409`, which keeps the demo
deterministic.

## Quickstart

### Local `uv` workflow

Install dependencies:

```bash
uv sync --dev
```

Start the upstream service:

```bash
make upstream
```

Start the proxy service in a second terminal:

```bash
make proxy
```

The equivalent direct commands are:

```bash
uv run uvicorn upstream.main:app --reload --host 127.0.0.1 --port 8080
UPSTREAM_BASE_URL=http://127.0.0.1:8080 \
uv run uvicorn redress_fastapi_upstream_proxy.main:app --reload --host 127.0.0.1 --port 8000
```

### Docker Compose

```bash
docker compose up --build
```

## Example Curl Commands

Health and smoke checks:

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/proxy/ping
```

Compact `call()` path recovering from transient failures:

```bash
curl "http://127.0.0.1:8000/proxy/call?mode=transient_then_success&scenario_id=call-a&failures=2"
```

Structured `execute()` path showing a permanent stop reason:

```bash
curl "http://127.0.0.1:8000/proxy/execute?mode=permanent_fail&scenario_id=exec-a&status_code=404"
```

Intentional no-retry contrast:

```bash
curl "http://127.0.0.1:8000/proxy/no-retry?mode=transient_then_success&scenario_id=no-retry-a&failures=2"
```

Rate-limit handling with `Retry-After`:

```bash
curl "http://127.0.0.1:8000/proxy/call?mode=retry_after_then_success&scenario_id=rate-a&failures=1&retry_after_s=1"
```

Deadline-driven timeout outcome:

```bash
curl "http://127.0.0.1:8000/proxy/execute?mode=slow_timeout&scenario_id=timeout-a&delay_s=0.3"
```

Recent Redress events:

```bash
curl "http://127.0.0.1:8000/debug/events"
```

## What To Observe

- `/proxy/call` stays compact even though retries are bounded and semantic.
- `/proxy/execute` exposes stop reasons directly instead of forcing you to infer
  them from exceptions.
- `/proxy/no-retry` fails immediately on the same upstream behavior that
  `/proxy/call` can recover from.
- `retry_after_then_success` uses rate-limit semantics instead of generic
  transient retry behavior.
- `slow_timeout` reaches `DEADLINE_EXCEEDED` with the configured defaults.
- `/debug/events` shows event names plus `class`, `stop_reason`, `err`, and
  `cause`.

## Default Policy Values

The demo uses these explicit defaults from [`.env.example`](.env.example):

- `UPSTREAM_OPERATION_NAME=proxy_upstream_demo`
- `RETRY_ATTEMPT_TIMEOUT_S=0.20`
- `RETRY_DEADLINE_S=0.45`
- `RETRY_MAX_ATTEMPTS=3`
- `RETRY_BACKOFF_S=0.05`

Those values are intentionally small so the demo and tests stay fast and so the
deadline behavior is easy to see.

## Where Redress Shows Up In The Code

- [`src/redress_fastapi_upstream_proxy/errors.py`](src/redress_fastapi_upstream_proxy/errors.py)
  defines semantic upstream exceptions plus the service-level `ProxyFailure`.
- [`src/redress_fastapi_upstream_proxy/classifiers.py`](src/redress_fastapi_upstream_proxy/classifiers.py)
  maps semantic exceptions into Redress `ErrorClass` values.
- [`src/redress_fastapi_upstream_proxy/policies.py`](src/redress_fastapi_upstream_proxy/policies.py)
  creates the single reusable `AsyncPolicy(retry=AsyncRetry(...))`.
- [`src/redress_fastapi_upstream_proxy/service.py`](src/redress_fastapi_upstream_proxy/service.py)
  shows the three application paths: `call`, `execute`, and no-retry.
- [`src/redress_fastapi_upstream_proxy/observability.py`](src/redress_fastapi_upstream_proxy/observability.py)
  records recent Redress lifecycle events without requiring a telemetry stack.

## Redress Vs Tenacity

See [docs/redress-vs-tenacity.md](docs/redress-vs-tenacity.md) for a small
side-by-side comparison of the "retry decorator" style versus the "semantic
classifier + explicit policy object" style used here.

## Validation

The local validation contract for this repo is:

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

## Extensions / Next Steps

- add a real metrics/logging backend behind the same hook shape
- extend the demo with result-based retry conditions
- add circuit breaker or budget examples as a separate phase
- swap the demo upstream for a real service adapter while keeping the same
  client/classifier/policy structure
