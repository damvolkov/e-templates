"""e-api entrypoint: assembly by explicit registration only — importing this module does nothing.

`create_app` is the composition root and the factory granian calls per worker. Routers and
websockets enter through `register` calls — the include_router shape; middleware, the lifespan
chain and CORS enter through the constructor, and the order of `lifespan=[...]` is the startup
order. Dependency chains are wired by each endpoint, never here. Nothing loads at import.
"""

from litestar import Litestar
from litestar.openapi.config import OpenAPIConfig
from litestar.openapi.spec import Components
from litestar.router import Router

from core.state import State
from e_api.api.lifespan import adapters, sealed, services
from e_api.api.middlewares import MIDDLEWARES, cors_config
from e_api.api.router import health, user
from e_api.api.security import BEARER_SCHEME
from e_api.websockets import telemetry


def create_app() -> Litestar:
    """Composition root: granian calls this per worker. Nothing here builds — the lifespans write the graph."""
    ##### STATE #####
    state = State()

    ##### APP #####
    app = Litestar(
        route_handlers=[],
        lifespan=[adapters.lifespan, services.lifespan, sealed.lifespan],
        middleware=list(MIDDLEWARES),
        cors_config=cors_config(),
        openapi_config=OpenAPIConfig(
            title="e-api",
            version="0.1.0",
            components=Components(security_schemes={"bearerAuth": BEARER_SCHEME}),
        ),
    )
    app.state = state  # litestar's default wrapper replaced by our dynamic graph — every lifespan writes into it

    ##### ROUTERS #####
    app.register(Router(path="/", route_handlers=list(health.ROUTES)))
    app.register(Router(path="/", route_handlers=list(user.ROUTES)))
    app.register(Router(path="/", route_handlers=list(telemetry.ws_routes())))
    return app
