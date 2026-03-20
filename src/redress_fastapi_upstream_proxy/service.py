from typing import Any

import httpx
from redress import (
    AsyncPolicy,
    AttemptContext,
    ErrorClass,
    RetryExhaustedError,
    RetryOutcome,
    StopReason,
)

from .errors import (
    ProxyFailure,
    UpstreamPermanentError,
    UpstreamRateLimitedError,
    UpstreamTimeoutError,
    UpstreamTransientError,
)
from .schemas import ProxyExecuteResponse, ProxyLastError
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
        capture_attempt = _attempt_recorder()
        call_upstream = self._build_upstream_operation(
            mode=mode,
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
                on_attempt_end=capture_attempt.record,
            )
        except RetryExhaustedError as exc:
            raise self._map_terminal_failure(exc, capture_attempt.last_attempt) from exc
        except (
            UpstreamPermanentError,
            UpstreamRateLimitedError,
            UpstreamTimeoutError,
            UpstreamTransientError,
            TimeoutError,
            httpx.HTTPError,
            ValueError,
        ) as exc:
            raise self._map_terminal_failure(exc, capture_attempt.last_attempt) from exc

    async def proxy_execute(
        self,
        *,
        mode: str,
        scenario_id: str | None = None,
        failures: int | None = None,
        retry_after_s: float | None = None,
        status_code: int | None = None,
        delay_s: float | None = None,
    ) -> ProxyExecuteResponse:
        call_upstream = self._build_upstream_operation(
            mode=mode,
            scenario_id=scenario_id,
            failures=failures,
            retry_after_s=retry_after_s,
            status_code=status_code,
            delay_s=delay_s,
        )

        outcome = await self._policy.execute(
            call_upstream,
            operation=self._operation_name,
        )
        return _serialize_outcome(outcome, operation=self._operation_name)

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

    def _build_upstream_operation(
        self,
        *,
        mode: str,
        scenario_id: str | None,
        failures: int | None,
        retry_after_s: float | None,
        status_code: int | None,
        delay_s: float | None,
    ):
        async def call_upstream() -> dict[str, Any]:
            return await self._upstream_client.get_demo(
                mode,
                scenario_id=scenario_id,
                failures=failures,
                retry_after_s=retry_after_s,
                status_code=status_code,
                delay_s=delay_s,
            )

        return call_upstream


class _AttemptRecorder:
    def __init__(self) -> None:
        self.last_attempt: AttemptContext | None = None

    def record(self, ctx: AttemptContext) -> None:
        self.last_attempt = ctx


def _attempt_recorder() -> _AttemptRecorder:
    return _AttemptRecorder()


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


def _serialize_outcome(
    outcome: RetryOutcome[dict[str, Any]],
    *,
    operation: str,
) -> ProxyExecuteResponse:
    return ProxyExecuteResponse(
        ok=outcome.ok,
        attempts=outcome.attempts,
        stop_reason=outcome.stop_reason.value if outcome.stop_reason is not None else None,
        last_class=outcome.last_class.name if outcome.last_class is not None else None,
        cause=outcome.cause,
        elapsed_s=outcome.elapsed_s,
        next_sleep_s=outcome.next_sleep_s,
        operation=operation,
        value=outcome.value,
        last_error=_summarize_exception(outcome.last_exception),
    )


def _summarize_exception(exc: BaseException | None) -> ProxyLastError | None:
    if exc is None:
        return None

    payload_summary = getattr(exc, "payload_summary", None)
    retry_after_s = getattr(exc, "retry_after_s", None)
    status_code = getattr(exc, "status_code", None)
    message = getattr(exc, "message", None) or str(exc) or type(exc).__name__

    return ProxyLastError(
        type=type(exc).__name__,
        message=message,
        status_code=status_code if isinstance(status_code, int) else None,
        retry_after_s=retry_after_s if isinstance(retry_after_s, (int, float)) else None,
        payload_summary=payload_summary if isinstance(payload_summary, dict) else None,
    )
