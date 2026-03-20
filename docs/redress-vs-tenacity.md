# Redress vs Tenacity In This Repo

This repo is not trying to prove that one library is universally better than
the other. The comparison is narrower than that:

- Tenacity is a strong fit when the main problem is "retry this callable."
- Redress is a strong fit when the application needs explicit failure
  semantics, reusable policy objects, stop reasons, and structured outcomes.

## Tenacity-Style Example

A typical Tenacity-oriented version of the compact path looks roughly like this:

```python
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed


@retry(
    retry=retry_if_exception_type(
        (UpstreamTransientError, UpstreamRateLimitedError, UpstreamTimeoutError)
    ),
    wait=wait_fixed(0.05),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def fetch_demo():
    return await upstream_client.get_demo(
        "transient_then_success",
        scenario_id="call-a",
        failures=2,
    )
```

That is compact, and for many workloads it is enough.

The tradeoff is that application semantics still tend to live outside the retry
object:

- rate limits and transient failures are often both "retryable exceptions"
- overall stop reasons are not usually part of the application response model
- structured success/failure outcomes are something the app has to invent
- no-retry cases often become "just do not use the decorator here"

## Redress-Style Example

This repo uses semantic exceptions plus an explicit policy object:

```python
from redress import AsyncPolicy, AsyncRetry, Classification, ErrorClass, retry_after_or


def classify_upstream_error(exc: BaseException):
    if isinstance(exc, UpstreamRateLimitedError):
        return Classification(ErrorClass.RATE_LIMIT, retry_after_s=exc.retry_after_s)
    if isinstance(exc, (UpstreamTransientError, UpstreamTimeoutError)):
        return ErrorClass.TRANSIENT
    if isinstance(exc, UpstreamPermanentError):
        return ErrorClass.PERMANENT
    return ErrorClass.UNKNOWN


policy = AsyncPolicy(
    retry=AsyncRetry(
        classifier=classify_upstream_error,
        strategy=retry_after_or(lambda _: 0.05, jitter_s=0.0),
        attempt_timeout_s=0.20,
        deadline_s=0.45,
        max_attempts=3,
    )
)


async def proxy_execute():
    outcome = await policy.execute(
        lambda: upstream_client.get_demo("transient_then_success", scenario_id="call-a"),
        operation="proxy_upstream_demo",
    )
    return {
        "ok": outcome.ok,
        "stop_reason": None if outcome.stop_reason is None else outcome.stop_reason.value,
        "last_class": None if outcome.last_class is None else outcome.last_class.name,
        "cause": outcome.cause,
    }
```

The key difference is not just "different syntax." The policy object is working
at the same level as the service's failure semantics.

## Short Comparison

### Semantic classification

- Tenacity usually retries based on exception type or predicate.
- Redress makes the semantic class explicit: `RATE_LIMIT`, `TRANSIENT`,
  `PERMANENT`, `UNKNOWN`, and so on.

### Explicit policy object

- Tenacity commonly centers configuration on a decorator or wrapped callable.
- Redress centers configuration on a reusable policy object that the service can
  pass around and apply intentionally.

### Structured outcomes

- Tenacity is primarily exception-first.
- Redress supports exception-first `call()` and structured `execute()` without
  the application building its own parallel outcome model.

### Stop reasons

- Tenacity can tell you that retries stopped, but applications often need extra
  work to turn that into stable user-facing semantics.
- Redress gives the application a small, explicit stop-reason vocabulary such as
  `DEADLINE_EXCEEDED` and `NON_RETRYABLE_CLASS`.

### Intentional no-retry paths

- With Tenacity, the contrast path is often just "do not use the decorator."
- With Redress, the distinction is clearer because the retrying path and the
  no-retry path can sit side by side behind the same semantic client boundary.

## Why This Repo Picks Redress

This example wants to show all of these in one place:

- a compact route that still reads well
- a structured-outcome route that surfaces stop reasons directly
- a no-retry route that is intentionally different
- lightweight event visibility through `/debug/events`

That combination is exactly the kind of problem where an explicit policy object
and semantic classifier are more useful than a generic retry decorator.
