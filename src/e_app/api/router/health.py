"""api.router.health: liveness, plus the oauth chain exercised by a real (tiny) consumer."""

from authlib.integrations.starlette_client import OAuth
from litestar import get


async def health() -> dict[str, str]:
    """Liveness probe — no graph access, must answer even while backends are down."""
    return {"status": "ok"}


async def providers(oauth: OAuth) -> dict[str, list[str]]:
    """Identities registered with authlib — empty until OAUTH__* is configured."""
    return {"providers": sorted(oauth._registry)}


ROUTES = (
    get("/health", name="health")(health),
    get("/oauth/providers", name="oauth.providers")(providers),
)
