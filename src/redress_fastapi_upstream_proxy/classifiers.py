import httpx
from redress import Classification, ErrorClass

from .errors import (
    UpstreamPermanentError,
    UpstreamRateLimitedError,
    UpstreamTimeoutError,
    UpstreamTransientError,
)


def classify_upstream_error(exc: BaseException) -> ErrorClass | Classification:
    if isinstance(exc, UpstreamRateLimitedError):
        return Classification(
            klass=ErrorClass.RATE_LIMIT,
            retry_after_s=exc.retry_after_s,
        )

    if isinstance(exc, UpstreamTransientError):
        return ErrorClass.TRANSIENT

    if isinstance(exc, (UpstreamTimeoutError, TimeoutError, httpx.TimeoutException)):
        return ErrorClass.TRANSIENT

    if isinstance(exc, UpstreamPermanentError):
        return ErrorClass.PERMANENT

    return ErrorClass.UNKNOWN
