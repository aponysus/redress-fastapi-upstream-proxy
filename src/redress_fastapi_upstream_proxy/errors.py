from typing import Any


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
