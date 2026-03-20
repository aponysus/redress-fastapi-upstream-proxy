import asyncio

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from .schemas import DemoConfigPayload, DemoMode, DemoResponse
from .state import ScenarioConfig, ScenarioConfigMismatchError, ScenarioStore


def create_app() -> FastAPI:
    app = FastAPI(title="redress-demo-upstream", version="0.1.0")
    app.state.scenarios = ScenarioStore()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "upstream",
        }

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {
            "service": "upstream",
            "message": "pong",
        }

    @app.get("/demo/{mode}", response_model=DemoResponse)
    async def demo_mode(
        mode: DemoMode,
        scenario_id: str = Query(default="default", min_length=1),
        failures: int = Query(default=2, ge=0),
        retry_after_s: float = Query(default=1.0, ge=0.0),
        status_code: int = Query(default=404, ge=400, le=499),
        delay_s: float = Query(default=1.0, ge=0.0),
    ) -> DemoResponse | JSONResponse:
        if mode is DemoMode.PERMANENT_FAIL and status_code == 429:
            raise HTTPException(
                status_code=422,
                detail="Use retry_after_then_success for 429 behavior.",
            )

        config = _build_config(
            mode=mode,
            failures=failures,
            retry_after_s=retry_after_s,
            status_code=status_code,
            delay_s=delay_s,
        )

        try:
            attempt = app.state.scenarios.next_attempt(
                mode=mode,
                scenario_id=scenario_id,
                config=config,
            )
        except ScenarioConfigMismatchError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        payload = DemoResponse(
            mode=mode,
            scenario_id=scenario_id,
            attempt=attempt,
            outcome="success",
            message="Upstream responded successfully.",
            config=DemoConfigPayload(
                failures=config.failures,
                retry_after_s=config.retry_after_s,
                status_code=config.status_code,
                delay_s=config.delay_s,
            ),
        )

        if mode is DemoMode.SUCCESS:
            return payload

        if mode is DemoMode.TRANSIENT_THEN_SUCCESS:
            if attempt <= config.failures:
                return JSONResponse(
                    status_code=503,
                    content=payload.model_copy(
                        update={
                            "outcome": "transient_error",
                            "message": "Transient failure before eventual success.",
                        }
                    ).model_dump(mode="json"),
                )
            return payload.model_copy(
                update={
                    "outcome": "recovered",
                    "message": "Transient failures exhausted; request now succeeds.",
                }
            )

        if mode is DemoMode.RETRY_AFTER_THEN_SUCCESS:
            if attempt <= config.failures:
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": _format_retry_after(config.retry_after_s)},
                    content=payload.model_copy(
                        update={
                            "outcome": "rate_limited",
                            "message": "Rate limited before eventual success.",
                        }
                    ).model_dump(mode="json"),
                )
            return payload.model_copy(
                update={
                    "outcome": "recovered",
                    "message": "Rate-limit window passed; request now succeeds.",
                }
            )

        if mode is DemoMode.PERMANENT_FAIL:
            return JSONResponse(
                status_code=config.status_code,
                content=payload.model_copy(
                    update={
                        "outcome": "permanent_error",
                        "message": "Permanent client-style failure.",
                    }
                ).model_dump(mode="json"),
            )

        await asyncio.sleep(config.delay_s)
        return payload.model_copy(
            update={
                "outcome": "slow_success",
                "message": "Delayed success after sleeping.",
            }
        )

    return app


app = create_app()


def _build_config(
    *,
    mode: DemoMode,
    failures: int,
    retry_after_s: float,
    status_code: int,
    delay_s: float,
) -> ScenarioConfig:
    if mode is DemoMode.SUCCESS:
        return ScenarioConfig(
            mode=mode,
            failures=0,
            retry_after_s=0.0,
            status_code=200,
            delay_s=0.0,
        )

    if mode is DemoMode.TRANSIENT_THEN_SUCCESS:
        return ScenarioConfig(
            mode=mode,
            failures=failures,
            retry_after_s=0.0,
            status_code=503,
            delay_s=0.0,
        )

    if mode is DemoMode.RETRY_AFTER_THEN_SUCCESS:
        return ScenarioConfig(
            mode=mode,
            failures=failures,
            retry_after_s=retry_after_s,
            status_code=429,
            delay_s=0.0,
        )

    if mode is DemoMode.PERMANENT_FAIL:
        return ScenarioConfig(
            mode=mode,
            failures=0,
            retry_after_s=0.0,
            status_code=status_code,
            delay_s=0.0,
        )

    return ScenarioConfig(
        mode=mode,
        failures=0,
        retry_after_s=0.0,
        status_code=200,
        delay_s=delay_s,
    )


def _format_retry_after(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return str(value)
