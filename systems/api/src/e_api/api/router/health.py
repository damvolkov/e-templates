"""api.router.health: liveness, plus the oauth chain exercised by a real (tiny) consumer."""

from authlib.integrations.starlette_client import OAuth
from litestar import get
from litestar.di import NamedDependency, Provide
from litestar.handlers import HTTPRouteHandler

from e_api.api.deps import graph, oauth


async def health() -> dict[str, str]:
    """Liveness probe — no graph access, must answer even while backends are down."""
    return {"status": "ok"}


async def providers(oauth: NamedDependency[OAuth]) -> dict[str, list[str]]:
    """Identities registered with authlib — empty until OAUTH__* is configured."""
    return {"providers": sorted(oauth._registry)}


##### CHAINS — endpoint-local wiring #####
OAUTH_DEPS: dict[str, Provide] = {
    "graph": Provide(graph, sync_to_thread=False),
    "oauth": Provide(oauth, sync_to_thread=False),
}

ROUTES: tuple[HTTPRouteHandler, ...] = (
    get("/health", name="health")(health),
    get("/oauth/providers", name="oauth.providers", dependencies=OAUTH_DEPS)(providers),
)
