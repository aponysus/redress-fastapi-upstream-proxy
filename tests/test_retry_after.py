import pytest


@pytest.mark.asyncio
async def test_retry_after_route_uses_rate_limit_classification_and_header_delay(proxy_client):
    response = await proxy_client.get(
        "/proxy/call",
        params={
            "mode": "retry_after_then_success",
            "scenario_id": "retry-after",
            "failures": 1,
            "retry_after_s": 0.02,
        },
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["mode"] == "retry_after_then_success"
    assert payload["attempt"] == 2
    assert payload["outcome"] == "recovered"

    events_response = await proxy_client.get("/debug/events")
    assert events_response.status_code == 200

    events = events_response.json()["events"]
    assert [event["event"] for event in events] == ["retry", "success"]

    retry_event = events[0]
    assert retry_event["klass"] == "RATE_LIMIT"
    assert retry_event["err"] == "UpstreamRateLimitedError"
    assert retry_event["cause"] == "exception"
    assert retry_event["sleep_s"] == pytest.approx(0.02, abs=0.01)
