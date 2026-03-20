import httpx
from fastapi import APIRouter, HTTPException, Request

from ..upstream_client import UpstreamDemoClient

router = APIRouter(prefix="/proxy", tags=["proxy"])


@router.get("/ping")
async def proxy_ping(request: Request) -> dict[str, object]:
    upstream_client: UpstreamDemoClient = request.app.state.upstream_client

    try:
        upstream = await upstream_client.ping()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Upstream ping failed.") from exc

    return {
        "service": "proxy",
        "upstream": upstream,
    }
