from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from .errors import (
    UpstreamPermanentError,
    UpstreamRateLimitedError,
    UpstreamTimeoutError,
    UpstreamTransientError,
)


class UpstreamDemoClient:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http_client = http_client

    async def ping(self) -> dict[str, Any]:
        response = await self._http_client.get("/ping")
        response.raise_for_status()
        return _parse_json_object(response)

    async def get_demo(
        self,
        mode: str,
        *,
        scenario_id: str | None = None,
        failures: int | None = None,
        retry_after_s: float | None = None,
        status_code: int | None = None,
        delay_s: float | None = None,
    ) -> dict[str, Any]:
        params = _build_params(
            scenario_id=scenario_id,
            failures=failures,
            retry_after_s=retry_after_s,
            status_code=status_code,
            delay_s=delay_s,
        )

        try:
            response = await self._http_client.get(f"/demo/{mode}", params=params)
        except httpx.TimeoutException as exc:
            raise UpstreamTimeoutError("Upstream request timed out.") from exc

        if 200 <= response.status_code < 300:
            return _parse_json_object(response)

        payload_summary = _extract_payload_summary(response)

        if response.status_code == 429:
            raise UpstreamRateLimitedError(
                "Upstream rate limited the request.",
                status_code=response.status_code,
                retry_after_s=_parse_retry_after(response),
                payload_summary=payload_summary,
            )

        if 500 <= response.status_code < 600:
            raise UpstreamTransientError(
                "Upstream returned a transient server failure.",
                status_code=response.status_code,
                payload_summary=payload_summary,
            )

        if 400 <= response.status_code < 500:
            raise UpstreamPermanentError(
                "Upstream returned a permanent client-style failure.",
                status_code=response.status_code,
                payload_summary=payload_summary,
            )

        response.raise_for_status()
        return _parse_json_object(response)


def _build_params(
    *,
    scenario_id: str | None,
    failures: int | None,
    retry_after_s: float | None,
    status_code: int | None,
    delay_s: float | None,
) -> dict[str, str | int | float]:
    params: dict[str, str | int | float] = {}
    if scenario_id is not None:
        params["scenario_id"] = scenario_id
    if failures is not None:
        params["failures"] = failures
    if retry_after_s is not None:
        params["retry_after_s"] = retry_after_s
    if status_code is not None:
        params["status_code"] = status_code
    if delay_s is not None:
        params["delay_s"] = delay_s
    return params


def _parse_json_object(response: httpx.Response) -> dict[str, Any]:
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise ValueError("Expected upstream JSON object response.")
    return dict(payload)


def _extract_payload_summary(response: httpx.Response) -> dict[str, Any] | None:
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        if not text:
            return None
        return {"text": text[:200]}

    if isinstance(payload, Mapping):
        keys = ("service", "mode", "scenario_id", "attempt", "outcome", "message", "detail")
        summary = {key: payload[key] for key in keys if key in payload}
        return summary or dict(payload)

    return {"type": type(payload).__name__}


def _parse_retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None

    try:
        return max(0.0, float(value))
    except ValueError:
        pass

    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None

    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)

    seconds = (when - datetime.now(UTC)).total_seconds()
    return max(0.0, seconds)
