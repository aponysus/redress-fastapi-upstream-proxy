import pytest


@pytest.mark.asyncio
async def test_proxy_execute_returns_structured_success_outcome(proxy_client):
    response = await proxy_client.get(
        "/proxy/execute",
        params={
            "mode": "transient_then_success",
            "scenario_id": "execute-success",
            "failures": 1,
        },
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["ok"] is True
    assert payload["attempts"] == 2
    assert payload["stop_reason"] is None
    assert payload["last_class"] is None
    assert payload["cause"] is None
    assert payload["elapsed_s"] >= 0.0
    assert payload["next_sleep_s"] is None
    assert payload["operation"] == "proxy_upstream_demo"
    assert payload["last_error"] is None
    assert payload["value"]["mode"] == "transient_then_success"
    assert payload["value"]["outcome"] == "recovered"


@pytest.mark.asyncio
async def test_proxy_execute_surfaces_terminal_stop_reason_on_failure(proxy_client):
    response = await proxy_client.get(
        "/proxy/execute",
        params={
            "mode": "permanent_fail",
            "scenario_id": "execute-failure",
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
    assert payload["elapsed_s"] >= 0.0
    assert payload["value"] is None
    assert payload["last_error"]["type"] == "UpstreamPermanentError"
    assert payload["last_error"]["status_code"] == 404
