import httpx
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/proxy", tags=["proxy"])


@router.get("/ping")
async def proxy_ping(request: Request) -> dict[str, object]:
    http_client: httpx.AsyncClient = request.app.state.http_client

    try:
        response = await http_client.get("/ping")
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Upstream ping failed.") from exc

    return {
        "service": "proxy",
        "upstream": response.json(),
    }
