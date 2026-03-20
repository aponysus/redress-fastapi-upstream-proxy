import pytest


@pytest.mark.asyncio
async def test_proxy_no_retry_fails_immediately_without_redress_events(proxy_client):
    response = await proxy_client.get(
        "/proxy/no-retry",
        params={
            "mode": "transient_then_success",
            "scenario_id": "no-retry",
            "failures": 2,
        },
    )

    assert response.status_code == 504

    payload = response.json()
    assert (
        payload["detail"]["message"]
        == "Upstream transient failure prevented the call from succeeding."
    )
    assert payload["detail"]["last_class"] == "TRANSIENT"
    assert "stop_reason" not in payload["detail"]

    events_response = await proxy_client.get("/debug/events")
    assert events_response.status_code == 200
    assert events_response.json()["events"] == []
