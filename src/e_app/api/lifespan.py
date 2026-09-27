"""api.lifespan: everything that lives is born here and dies in reverse — one AsyncExitStack over the graph."""

from collections.abc import AsyncIterator, Sequence
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from typing import TYPE_CHECKING, ClassVar

import msgspec
import structlog
from authlib.integrations.starlette_client import OAuth
from litestar import Litestar

from e_app.adapters.base import StoreAdapter
from e_app.adapters.redis import RedisAdapter
from e_app.adapters.sqlite import SQLiteAdapter
from e_app.core.crypto import Crypto
from e_app.core.settings import BaseSettings, Secret
from e_app.core.state import State

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger()


##### SETTINGS #####
class OAuthSettings(BaseSettings, frozen=True):
    """OAUTH__NAME / OAUTH__CLIENT_ID / OAUTH__CLIENT_SECRET / OAUTH__SERVER_METADATA_URL."""

    env_prefix: ClassVar[str] = "OAUTH__"
    name: str = "dev"
    client_id: str = ""
    client_secret: Secret = Secret("")
    server_metadata_url: str = ""


##### BUILDERS #####
def default_adapters() -> tuple[StoreAdapter, ...]:
    """The template ships both KV stores so the graph shows interchangeability."""
    return (RedisAdapter(), SQLiteAdapter())


def build_oauth(settings: OAuthSettings | None = None) -> OAuth:
    """Empty registry until an IdP is configured — the app still boots without one."""
    st = settings or OAuthSettings.load()
    oauth = OAuth()
    match st.server_metadata_url:
        case "":
            pass
        case url:
            oauth.register(
                st.name,
                client_id=st.client_id,
                client_secret=st.client_secret,
                server_metadata_url=url,
            )
    return oauth


##### LIFESPAN #####
def build_lifespan(
    adapters: Sequence[StoreAdapter] | msgspec.UnsetType = msgspec.UNSET,
) -> "Callable[[Litestar], AbstractAsyncContextManager[None]]":
    """Factory so tests can pass `adapters=()` and run without external services.

    `UNSET` is the sentinel: default full stack, `()` an honest bare graph — no None overloading.
    """
    wanted = default_adapters() if isinstance(adapters, msgspec.UnsetType) else tuple(adapters)

    @asynccontextmanager
    async def lifespan(app: Litestar) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            graph = State(adapters=State(), crypto=Crypto.load(), oauth=build_oauth())
            for adapter in wanted:
                await stack.enter_async_context(adapter)
                setattr(graph.adapters, adapter.name, adapter)
            graph.seal()
            app.state.graph = graph
            logger.info("graph ready", nodes=repr(graph), step="START")
            yield
            logger.info("graph closed", step="STOP")

    return lifespan
