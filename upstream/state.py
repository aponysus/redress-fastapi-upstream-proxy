from dataclasses import dataclass
from threading import Lock

from .schemas import DemoMode


@dataclass(frozen=True)
class ScenarioConfig:
    mode: DemoMode
    failures: int
    retry_after_s: float
    status_code: int
    delay_s: float


@dataclass
class ScenarioRecord:
    config: ScenarioConfig
    attempts: int = 0


class ScenarioConfigMismatchError(Exception):
    """Raised when a scenario is reused with different parameters."""


class ScenarioStore:
    def __init__(self) -> None:
        self._records: dict[tuple[DemoMode, str], ScenarioRecord] = {}
        self._lock = Lock()

    def next_attempt(
        self,
        *,
        mode: DemoMode,
        scenario_id: str,
        config: ScenarioConfig,
    ) -> int:
        key = (mode, scenario_id)

        with self._lock:
            record = self._records.get(key)
            if record is None:
                record = ScenarioRecord(config=config)
                self._records[key] = record
            elif record.config != config:
                raise ScenarioConfigMismatchError(
                    "Scenario parameters are immutable once a scenario has started."
                )

            record.attempts += 1
            return record.attempts

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
