import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _settings():
    from redress_fastapi_upstream_proxy.config import Settings

    return Settings(
        service_name="proxy",
        host="127.0.0.1",
        port=8000,
        upstream_base_url="http://upstream.test",
        upstream_timeout_s=5.0,
        upstream_operation_name="proxy_upstream_demo",
        retry_attempt_timeout_s=0.20,
        retry_deadline_s=0.45,
        retry_max_attempts=3,
        retry_backoff_s=0.05,
    )


@asynccontextmanager
async def _app_client(app: FastAPI, *, base_url: str) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=base_url) as client:
            yield client


@pytest.fixture
def upstream_app() -> FastAPI:
    from upstream.main import create_app as create_upstream_app

    return create_upstream_app()


@pytest.fixture
def proxy_app(upstream_app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    import redress_fastapi_upstream_proxy.main as proxy_main_module
    from redress_fastapi_upstream_proxy.main import create_app as create_proxy_app

    def upstream_async_client(*args, **kwargs) -> httpx.AsyncClient:
        kwargs.setdefault("transport", httpx.ASGITransport(app=upstream_app))
        return httpx.AsyncClient(*args, **kwargs)

    monkeypatch.setattr(
        proxy_main_module,
        "httpx",
        SimpleNamespace(AsyncClient=upstream_async_client),
    )
    return create_proxy_app(_settings())


@pytest_asyncio.fixture
async def upstream_client(upstream_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with _app_client(upstream_app, base_url="http://upstream.test") as client:
        yield client


@pytest_asyncio.fixture
async def proxy_client(proxy_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with _app_client(proxy_app, base_url="http://proxy.test") as client:
        yield client
