import pytest


@pytest.mark.asyncio
async def test_upstream_health_returns_ok(upstream_client):
    response = await upstream_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "upstream"}


@pytest.mark.asyncio
async def test_proxy_health_returns_ok(proxy_client):
    response = await proxy_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "proxy"}
