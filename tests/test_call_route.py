import pytest


@pytest.mark.asyncio
async def test_proxy_call_retries_transient_failure_and_emits_retry_events(proxy_client):
    response = await proxy_client.get(
        "/proxy/call",
        params={
            "mode": "transient_then_success",
            "scenario_id": "call-route",
            "failures": 2,
        },
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["mode"] == "transient_then_success"
    assert payload["scenario_id"] == "call-route"
    assert payload["attempt"] == 3
    assert payload["outcome"] == "recovered"

    events_response = await proxy_client.get("/debug/events")
    assert events_response.status_code == 200

    events = events_response.json()["events"]
    assert [event["event"] for event in events] == ["retry", "retry", "success"]
    assert [event["attempt"] for event in events] == [1, 2, 3]

    first_retry = events[0]
    assert first_retry["class"] == "TRANSIENT"
    assert first_retry["err"] == "UpstreamTransientError"
    assert first_retry["cause"] == "exception"
    assert first_retry["operation"] == "proxy_upstream_demo"
