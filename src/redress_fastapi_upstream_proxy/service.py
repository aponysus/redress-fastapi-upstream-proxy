from typing import Any

import httpx
from redress import AsyncPolicy, AttemptContext, ErrorClass, RetryExhaustedError, StopReason

from .errors import (
    ProxyFailure,
    UpstreamPermanentError,
    UpstreamRateLimitedError,
    UpstreamTimeoutError,
    UpstreamTransientError,
)
from .upstream_client import UpstreamDemoClient


class ProxyService:
    def __init__(
        self,
        *,
        upstream_client: UpstreamDemoClient,
        policy: AsyncPolicy,
        operation_name: str,
    ) -> None:
        self._upstream_client = upstream_client
        self._policy = policy
        self._operation_name = operation_name

    async def proxy_call(
        self,
        *,
        mode: str,
        scenario_id: str | None = None,
        failures: int | None = None,
        retry_after_s: float | None = None,
        status_code: int | None = None,
        delay_s: float | None = None,
    ) -> dict[str, Any]:
        last_attempt: AttemptContext | None = None

        def capture_attempt(ctx: AttemptContext) -> None:
            nonlocal last_attempt
            last_attempt = ctx

        async def call_upstream() -> dict[str, Any]:
            return await self._upstream_client.get_demo(
                mode,
                scenario_id=scenario_id,
                failures=failures,
                retry_after_s=retry_after_s,
                status_code=status_code,
                delay_s=delay_s,
            )

        try:
            return await self._policy.call(
                call_upstream,
                operation=self._operation_name,
                on_attempt_end=capture_attempt,
            )
        except RetryExhaustedError as exc:
            raise self._map_terminal_failure(exc, last_attempt) from exc
        except (
            UpstreamPermanentError,
            UpstreamRateLimitedError,
            UpstreamTimeoutError,
            UpstreamTransientError,
            TimeoutError,
            httpx.HTTPError,
            ValueError,
        ) as exc:
            raise self._map_terminal_failure(exc, last_attempt) from exc

    def _map_terminal_failure(
        self,
        exc: BaseException,
        last_attempt: AttemptContext | None,
    ) -> ProxyFailure:
        stop_reason = _stop_reason_from(exc, last_attempt)
        last_class = _error_class_from(exc, last_attempt)
        detail = _detail_from(exc, stop_reason, last_class)
        status_code = _status_code_from(stop_reason, last_class)
        return ProxyFailure(
            status_code=status_code,
            detail=detail,
            stop_reason=stop_reason,
            last_class=last_class,
        )


def _stop_reason_from(
    exc: BaseException,
    last_attempt: AttemptContext | None,
) -> StopReason | None:
    if isinstance(exc, RetryExhaustedError):
        return exc.stop_reason
    if last_attempt is not None:
        return last_attempt.stop_reason
    return None


def _error_class_from(
    exc: BaseException,
    last_attempt: AttemptContext | None,
) -> ErrorClass | None:
    if isinstance(exc, RetryExhaustedError):
        return exc.last_class

    if last_attempt is not None and last_attempt.classification is not None:
        return last_attempt.classification.klass

    if isinstance(exc, UpstreamRateLimitedError):
        return ErrorClass.RATE_LIMIT
    if isinstance(exc, (UpstreamTimeoutError, UpstreamTransientError, TimeoutError)):
        return ErrorClass.TRANSIENT
    if isinstance(exc, UpstreamPermanentError):
        return ErrorClass.PERMANENT

    return ErrorClass.UNKNOWN


def _status_code_from(
    stop_reason: StopReason | None,
    last_class: ErrorClass | None,
) -> int:
    if stop_reason is StopReason.DEADLINE_EXCEEDED:
        return 504

    if last_class is ErrorClass.RATE_LIMIT:
        return 503

    if last_class in (ErrorClass.TRANSIENT, ErrorClass.SERVER_ERROR):
        return 504

    if last_class in (ErrorClass.PERMANENT, ErrorClass.AUTH, ErrorClass.PERMISSION):
        return 502

    return 502


def _detail_from(
    exc: BaseException,
    stop_reason: StopReason | None,
    last_class: ErrorClass | None,
) -> str:
    if stop_reason is StopReason.DEADLINE_EXCEEDED:
        return "Upstream call exceeded the configured retry deadline."

    if last_class is ErrorClass.RATE_LIMIT:
        return "Upstream rate limit prevented the call from succeeding."

    if last_class in (ErrorClass.TRANSIENT, ErrorClass.SERVER_ERROR):
        return "Upstream transient failure prevented the call from succeeding."

    if last_class in (ErrorClass.PERMANENT, ErrorClass.AUTH, ErrorClass.PERMISSION):
        return "Upstream permanent failure was not retried."

    if isinstance(exc, (httpx.HTTPError, ValueError)):
        return "Upstream communication failed."

    return str(exc) or "Upstream call failed."
