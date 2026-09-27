"""e-app entrypoint: the app, wired by explicit registration only — no decorators, no hidden magic.

Routers, websockets, middleware, dependency chains, CORS and the lifespan all enter through the
constructor, in the spirit of `include_router`/`register`: one glance here shows the whole system.
"""

from collections.abc import Sequence

import msgspec
from litestar import Litestar
from litestar.di import Provide
from litestar.openapi.config import OpenAPIConfig
from litestar.openapi.spec import Components

from e_app.adapters.base import StoreAdapter
from e_app.api.deps import provide_correlation_id, provide_graph, provide_oauth
from e_app.api.lifespan import build_lifespan
from e_app.api.middlewares import MIDDLEWARES, cors_config
from e_app.api.router import health, user
from e_app.api.security import BEARER_SCHEME
from e_app.core.logger import setup
from e_app.core.settings import Settings
from e_app.websockets.telemetry import WS_ROUTES

##### CONFIG #####
settings = Settings.load()
setup(env=settings.env)

##### APP #####
GLOBAL_DEPS = {
    "correlation_id": Provide(provide_correlation_id),
    "graph": Provide(provide_graph),
    "oauth": Provide(provide_oauth),
}


def create_app(adapters: Sequence[StoreAdapter] | msgspec.UnsetType = msgspec.UNSET) -> Litestar:
    """Composition root. `UNSET` opens the default adapter stack; tests pass their own (or `()`)."""
    return Litestar(
        route_handlers=[*health.ROUTES, *user.ROUTES, *WS_ROUTES],
        lifespan=build_lifespan(adapters),
        middleware=list(MIDDLEWARES),
        cors_config=cors_config(),
        dependencies=GLOBAL_DEPS,
        openapi_config=OpenAPIConfig(
            title="e-app",
            version="0.1.0",
            components=Components(security_schemes={"bearerAuth": BEARER_SCHEME}),
        ),
    )


app = create_app()
