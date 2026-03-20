from redress import AsyncPolicy, AsyncRetry, BackoffContext, retry_after_or

from .classifiers import classify_upstream_error
from .config import Settings


def build_upstream_policy(settings: Settings) -> AsyncPolicy:
    return AsyncPolicy(
        retry=AsyncRetry(
            classifier=classify_upstream_error,
            strategy=retry_after_or(_fixed_backoff(settings.retry_backoff_s), jitter_s=0.0),
            attempt_timeout_s=settings.retry_attempt_timeout_s,
            deadline_s=settings.retry_deadline_s,
            max_attempts=settings.retry_max_attempts,
        )
    )


def _fixed_backoff(seconds: float):
    delay = max(0.0, seconds)

    def backoff(_: BackoffContext) -> float:
        return delay

    return backoff
