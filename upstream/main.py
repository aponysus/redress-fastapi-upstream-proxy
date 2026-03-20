from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="redress-demo-upstream", version="0.1.0")

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

    return app


app = create_app()
