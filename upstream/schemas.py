from enum import StrEnum

from pydantic import BaseModel, Field


class DemoMode(StrEnum):
    SUCCESS = "success"
    TRANSIENT_THEN_SUCCESS = "transient_then_success"
    RETRY_AFTER_THEN_SUCCESS = "retry_after_then_success"
    PERMANENT_FAIL = "permanent_fail"
    SLOW_TIMEOUT = "slow_timeout"


class DemoConfigPayload(BaseModel):
    failures: int = Field(default=0, ge=0)
    retry_after_s: float = Field(default=0.0, ge=0.0)
    status_code: int = Field(default=200, ge=100, le=599)
    delay_s: float = Field(default=0.0, ge=0.0)


class DemoResponse(BaseModel):
    service: str = "upstream"
    mode: DemoMode
    scenario_id: str
    attempt: int = Field(ge=1)
    outcome: str
    message: str
    config: DemoConfigPayload
