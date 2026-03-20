from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from .config import Settings, get_settings
from .policies import build_upstream_policy
from .routes.health import router as health_router
from .routes.proxy import router as proxy_router
from .upstream_client import UpstreamDemoClient


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient(
            base_url=app_settings.upstream_base_url,
            timeout=app_settings.upstream_timeout_s,
        ) as http_client:
            app.state.upstream_client = UpstreamDemoClient(http_client)
            yield

    app = FastAPI(
        title="redress-fastapi-upstream-proxy",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.upstream_policy = build_upstream_policy(app_settings)
    app.include_router(health_router)
    app.include_router(proxy_router)
    return app


app = create_app()
