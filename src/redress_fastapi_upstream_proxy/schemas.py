from typing import Any

from pydantic import BaseModel


class ProxyLastError(BaseModel):
    type: str
    message: str
    status_code: int | None = None
    retry_after_s: float | None = None
    payload_summary: dict[str, Any] | None = None


class ProxyExecuteResponse(BaseModel):
    ok: bool
    attempts: int
    stop_reason: str | None
    last_class: str | None
    cause: str | None
    elapsed_s: float
    next_sleep_s: float | None
    operation: str | None
    value: dict[str, Any] | None
    last_error: ProxyLastError | None


class DebugEventRecord(BaseModel):
    event: str
    attempt: int
    sleep_s: float
    klass: str | None = None
    stop_reason: str | None = None
    operation: str | None = None
    err: str | None = None
    cause: str | None = None
    timestamp: str | None = None


class DebugEventsResponse(BaseModel):
    events: list[DebugEventRecord]
