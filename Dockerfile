FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY pyproject.toml README.md .python-version ./
COPY src ./src
COPY upstream ./upstream

RUN uv sync --no-dev

ENV PATH="/app/.venv/bin:${PATH}"
