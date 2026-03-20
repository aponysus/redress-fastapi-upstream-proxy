import pytest


@pytest.mark.asyncio
async def test_proxy_call_maps_slow_timeout_to_deadline_exceeded(proxy_client):
    response = await proxy_client.get(
        "/proxy/call",
        params={
            "mode": "slow_timeout",
            "scenario_id": "timeout-call",
            "delay_s": 0.3,
        },
    )

    assert response.status_code == 504

    payload = response.json()
    assert payload["detail"]["message"] == "Upstream call exceeded the configured retry deadline."
    assert payload["detail"]["stop_reason"] == "DEADLINE_EXCEEDED"
    assert payload["detail"]["last_class"] == "TRANSIENT"

    events_response = await proxy_client.get("/debug/events")
    assert events_response.status_code == 200

    events = events_response.json()["events"]
    assert [event["event"] for event in events] == ["retry", "deadline_exceeded"]
    assert events[-1]["klass"] == "TRANSIENT"
    assert events[-1]["stop_reason"] == "DEADLINE_EXCEEDED"
    assert events[-1]["err"] == "TimeoutError"
    assert events[-1]["cause"] == "exception"


@pytest.mark.asyncio
async def test_proxy_execute_exposes_deadline_exceeded_for_timeout_scenario(proxy_client):
    response = await proxy_client.get(
        "/proxy/execute",
        params={
            "mode": "slow_timeout",
            "scenario_id": "timeout-execute",
            "delay_s": 0.3,
        },
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["ok"] is False
    assert payload["attempts"] == 2
    assert payload["stop_reason"] == "DEADLINE_EXCEEDED"
    assert payload["last_class"] == "TRANSIENT"
    assert payload["cause"] == "exception"
    assert payload["elapsed_s"] >= 0.45
    assert payload["last_error"]["type"] == "TimeoutError"
    assert payload["last_error"]["message"] == "TimeoutError"
