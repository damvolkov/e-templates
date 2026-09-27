"""api.middlewares: the ASGI stack, declared once as data — correlation, CORS, and the house access log.

`ApiSettings` follows the co-location rule: the struct lives with the module that consumes it,
exactly like `CryptoSettings` beside the engine.
"""

import time
from typing import TYPE_CHECKING, Any, ClassVar

import structlog
from asgi_correlation_id import CorrelationIdMiddleware
from litestar.config.cors import CORSConfig

from e_app.core.settings import BaseSettings

if TYPE_CHECKING:
    from litestar.types import Receive, Scope, Send

logger = structlog.get_logger()


##### SETTINGS #####
class ApiSettings(BaseSettings, frozen=True):
    """API__ALLOW_ORIGINS / API__ALLOW_METHODS — JSON lists via env or config file."""

    env_prefix: ClassVar[str] = "API__"
    allow_origins: list[str] = ["*"]
    allow_methods: list[str] = ["GET", "POST", "PATCH", "DELETE"]


##### MIDDLEWARES #####
class AccessLogMiddleware:
    """House standard for pure-ASGI middleware: one structured line per request, correlation id included."""

    def __init__(self, app: Any) -> None:  # noqa: ANN401 — ASGI apps are arbitrary callables by contract
        self._app = app

    async def __call__(self, scope: "Scope", receive: "Receive", send: "Send") -> None:
        match scope["type"]:
            case "http":
                started = time.perf_counter()
                status = 0

                async def send_and_watch(message: dict[str, Any]) -> None:
                    nonlocal status
                    status = message.get("status", status)
                    await send(message)

                await self._app(scope, receive, send_and_watch)
                logger.info(
                    "request",
                    method=scope["method"],
                    path=scope["path"],
                    status=status,
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                )
            case _:
                await self._app(scope, receive, send)


def cors_config(settings: ApiSettings | None = None) -> CORSConfig:
    """Translate the msgspec struct into litestar's config object — data in, behaviour out."""
    st = settings or ApiSettings.load()
    return CORSConfig(allow_origins=st.allow_origins, allow_methods=st.allow_methods, allow_headers=["*"])


MIDDLEWARES: tuple[type, ...] = (CorrelationIdMiddleware, AccessLogMiddleware)
