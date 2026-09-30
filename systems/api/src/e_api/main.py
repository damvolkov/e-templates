"""e-api entrypoint: assembly by explicit registration only — importing this module does nothing.

`create_app` is the composition root and the factory granian calls per worker. Routers and
websockets enter through `register` calls — the include_router shape; middleware, the lifespan
chain and CORS enter through the constructor, and the order of `lifespan=[...]` is the startup
order: core first (every later concern may depend on the loaded singletons), then the edges and
services, sealed last. Dependency chains are wired by each endpoint, never here. Nothing loads at
import; the core singletons load on the first touch, which the core lifespan makes.
"""

from importlib.metadata import version
from typing import cast

from litestar import Litestar
from litestar.openapi.config import OpenAPIConfig
from litestar.openapi.spec import Components
from litestar.router import Router
from litestar.types import Middleware

from core.state import State
from e_api.api.lifespan import adapters, sealed, services
from e_api.api.lifespan.core import lifespan as core_lifespan
from e_api.api.middlewares import MIDDLEWARES, cors_config
from e_api.api.router import health, user
from e_api.api.security import BEARER_SCHEME, SecuritySchemeName
from e_api.websockets import telemetry


def create_app() -> Litestar:
    """Composition root: granian calls this per worker. Nothing here builds — the lifespans write the graph."""
    ##### STATE #####
    state = State()

    ##### APP #####
    app = Litestar(
        route_handlers=[],
        lifespan=[core_lifespan, adapters.lifespan, services.lifespan, sealed.lifespan],
        ### the declared union of middlewares crosses into litestar's looser `Middleware` alias here;
        ### asgi_correlation_id types its scope narrower than the protocol — wiring is exact, upstream typing is not.
        middleware=cast("list[Middleware]", list(MIDDLEWARES)),
        cors_config=cors_config(),
        openapi_config=OpenAPIConfig(
            title="e-api",
            ### pyproject is the version source of truth: uv-dynamic-versioning stamps it, dev reads 0.0.0.
            version=version("e-api"),
            components=Components(security_schemes={SecuritySchemeName.BEARER.value: BEARER_SCHEME}),
        ),
    )
    ### litestar's default wrapper replaced by our dynamic graph — every lifespan writes into it
    app.state = state

    ##### ROUTERS #####
    app.register(Router(path="/", route_handlers=list(health.ROUTES)))
    app.register(Router(path="/", route_handlers=list(user.ROUTES)))
    app.register(Router(path="/", route_handlers=list(telemetry.ws_routes())))
    return app
