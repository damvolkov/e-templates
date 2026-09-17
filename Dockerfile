##### BUILDER #####
FROM ghcr.io/astral-sh/uv:0.12.15-python3.14-trixie-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY README.md ./
COPY src /app/src
RUN uv sync --frozen --no-dev --no-editable

##### DEPLOY #####
FROM python:3.14-slim-trixie AS deploy
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
COPY --from=builder /app/.venv .venv
USER nobody
EXPOSE 8000
CMD ["uvicorn", "e_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
