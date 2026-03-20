import httpx
from fastapi import APIRouter, HTTPException, Query, Request

from ..errors import ProxyFailure
from ..service import ProxyService
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


@router.get("/call")
async def proxy_call(
    request: Request,
    mode: str = Query(..., min_length=1),
    scenario_id: str | None = Query(default=None, min_length=1),
    failures: int | None = Query(default=None, ge=0),
    retry_after_s: float | None = Query(default=None, ge=0.0),
    status_code: int | None = Query(default=None, ge=400, le=499),
    delay_s: float | None = Query(default=None, ge=0.0),
) -> dict[str, object]:
    service: ProxyService = request.app.state.proxy_service

    try:
        upstream = await service.proxy_call(
            mode=mode,
            scenario_id=scenario_id,
            failures=failures,
            retry_after_s=retry_after_s,
            status_code=status_code,
            delay_s=delay_s,
        )
    except ProxyFailure as exc:
        detail: dict[str, object] = {"message": exc.detail}
        if exc.stop_reason is not None:
            detail["stop_reason"] = exc.stop_reason.value
        if exc.last_class is not None:
            detail["last_class"] = exc.last_class.name
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc

    return upstream
