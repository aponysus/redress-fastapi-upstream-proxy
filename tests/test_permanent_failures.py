import pytest


@pytest.mark.asyncio
async def test_proxy_call_does_not_retry_permanent_failure(proxy_client):
    response = await proxy_client.get(
        "/proxy/call",
        params={
            "mode": "permanent_fail",
            "scenario_id": "permanent-call",
            "status_code": 404,
        },
    )

    assert response.status_code == 502

    payload = response.json()
    assert payload["detail"]["message"] == "Upstream permanent failure was not retried."
    assert payload["detail"]["stop_reason"] == "NON_RETRYABLE_CLASS"
    assert payload["detail"]["last_class"] == "PERMANENT"

    events_response = await proxy_client.get("/debug/events")
    assert events_response.status_code == 200

    events = events_response.json()["events"]
    assert len(events) == 1
    assert events[0]["event"] == "permanent_fail"
    assert events[0]["class"] == "PERMANENT"
    assert events[0]["stop_reason"] == "NON_RETRYABLE_CLASS"
    assert events[0]["err"] == "UpstreamPermanentError"
    assert events[0]["cause"] == "exception"


@pytest.mark.asyncio
async def test_proxy_execute_marks_permanent_failure_as_non_retryable(proxy_client):
    response = await proxy_client.get(
        "/proxy/execute",
        params={
            "mode": "permanent_fail",
            "scenario_id": "permanent-execute",
            "status_code": 404,
        },
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["ok"] is False
    assert payload["attempts"] == 1
    assert payload["stop_reason"] == "NON_RETRYABLE_CLASS"
    assert payload["last_class"] == "PERMANENT"
    assert payload["cause"] == "exception"
