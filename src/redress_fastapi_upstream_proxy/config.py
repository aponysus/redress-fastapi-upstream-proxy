import os
from dataclasses import dataclass
from functools import lru_cache


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


@dataclass(frozen=True)
class Settings:
    service_name: str
    host: str
    port: int
    upstream_base_url: str
    upstream_timeout_s: float


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        service_name="proxy",
        host=os.getenv("PROXY_HOST", "127.0.0.1"),
        port=_get_int("PROXY_PORT", 8000),
        upstream_base_url=os.getenv("UPSTREAM_BASE_URL", "http://127.0.0.1:8080"),
        upstream_timeout_s=_get_float("UPSTREAM_TIMEOUT_S", 5.0),
    )
