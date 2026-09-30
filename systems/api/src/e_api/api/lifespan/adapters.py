"""api.lifespan.adapters: open every external edge — sqlite, redis, http — on one exit stack.

The concern owns its subtree as a typed section: `AdaptersState` names each edge by the Port the
consumers (api.deps, routers) may ask of it, so the graph carries contracts, not classes. Each
adapter is a singleton built here, enters the shared `AsyncExitStack`, and they close in reverse
order when the stack unwinds."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import cast

from litestar import Litestar

from adapters.http import HttpAdapter
from adapters.ports import HttpPort, StorePort
from adapters.redis import RedisAdapter
from adapters.sqlite import SQLiteAdapter
from core.logger import logger
from core.state import State


##### SECTION #####
@dataclass(frozen=True, slots=True)
class AdaptersState:
    """The typed adapters section: fields named by role, typed by the port the role speaks.

    `store` is the KV edge the app's records live on (currently sqlite); `redis` keeps its own
    adapter name because it is a second, interchangeable StorePort; `http` is the outbound client.
    The adapters are singletons — factory machinery comes later, this section wires what exists."""

    store: StorePort
    redis: StorePort
    http: HttpPort


@asynccontextmanager
async def lifespan(app: Litestar) -> AsyncIterator[None]:
    """Open every external edge on the exit stack, then mount the typed section under `state.adapters`."""
    state = cast("State", app.state)
    store, redis, http = SQLiteAdapter(), RedisAdapter(), HttpAdapter()
    async with AsyncExitStack() as stack:
        ### concrete adapters enter the stack; the section narrows them to the ports consumers may ask.
        ### enter order is close order reversed: http unwinds first, sqlite — the app's own store — last.
        await stack.enter_async_context(store)
        await stack.enter_async_context(redis)
        await stack.enter_async_context(http)
        state.adapters = AdaptersState(store=store, redis=redis, http=http)
        logger.info("adapters ready", edges=sorted(edge.name for edge in (store, redis, http)), step="START")
        yield
    logger.info("adapters closed", step="STOP")
