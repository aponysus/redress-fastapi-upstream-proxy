from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class RecordedEvent:
    event: str
    attempt: int
    sleep_s: float
    klass: str | None
    stop_reason: str | None
    operation: str | None
    err: str | None
    cause: str | None
    timestamp: str


class EventRecorder:
    def __init__(self, *, max_events: int = 200) -> None:
        self._events: deque[RecordedEvent] = deque(maxlen=max_events)
        self._lock = Lock()

    def record_metric(
        self,
        event: str,
        attempt: int,
        sleep_s: float,
        tags: Mapping[str, Any],
    ) -> None:
        record = RecordedEvent(
            event=event,
            attempt=attempt,
            sleep_s=sleep_s,
            klass=_string_tag(tags, "class"),
            stop_reason=_string_tag(tags, "stop_reason"),
            operation=_string_tag(tags, "operation"),
            err=_string_tag(tags, "err"),
            cause=_string_tag(tags, "cause"),
            timestamp=_timestamp(),
        )
        self._append(record)

    def record_log(self, event: str, fields: Mapping[str, Any]) -> None:
        record = RecordedEvent(
            event=event,
            attempt=_int_field(fields, "attempt"),
            sleep_s=_float_field(fields, "sleep_s"),
            klass=_string_tag(fields, "class"),
            stop_reason=_string_tag(fields, "stop_reason"),
            operation=_string_tag(fields, "operation"),
            err=_string_tag(fields, "err"),
            cause=_string_tag(fields, "cause"),
            timestamp=_timestamp(),
        )
        self._append(record)

    def list_events(self) -> list[RecordedEvent]:
        with self._lock:
            return list(self._events)

    def metric_hook(self):
        def hook(event: str, attempt: int, sleep_s: float, tags: dict[str, Any]) -> None:
            self.record_metric(event, attempt, sleep_s, tags)

        return hook

    def log_hook(self):
        def hook(event: str, fields: dict[str, Any]) -> None:
            self.record_log(event, fields)

        return hook

    def _append(self, record: RecordedEvent) -> None:
        with self._lock:
            self._events.append(record)


def _timestamp() -> str:
    return datetime.now(tz=UTC).isoformat()


def _string_tag(values: Mapping[str, Any], key: str) -> str | None:
    value = values.get(key)
    return value if isinstance(value, str) else None


def _int_field(values: Mapping[str, Any], key: str) -> int:
    value = values.get(key)
    return value if isinstance(value, int) else 0


def _float_field(values: Mapping[str, Any], key: str) -> float:
    value = values.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0
