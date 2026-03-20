from dataclasses import dataclass
from typing import Any

from redress import ErrorClass, StopReason


class UpstreamError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retry_after_s: float | None = None,
        payload_summary: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.retry_after_s = retry_after_s
        self.payload_summary = payload_summary


class UpstreamRateLimitedError(UpstreamError):
    pass


class UpstreamTransientError(UpstreamError):
    pass


class UpstreamPermanentError(UpstreamError):
    pass


class UpstreamTimeoutError(UpstreamError):
    pass


@dataclass(frozen=True)
# Ruff wants Exception subclasses to end with Error, but ProxyFailure is the
# clearest service-layer name for this demo.
class ProxyFailure(Exception):  # noqa: N818
    status_code: int
    detail: str
    stop_reason: StopReason | None = None
    last_class: ErrorClass | None = None
