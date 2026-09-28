"""api.lifespan.adapters: open every external edge — redis, sqlite, http — on its own exit stack.

The concern writes its subtree under `app.state.adapters` (the graph auto-vivifies it), enters each
adapter into its own `AsyncExitStack`, and closes exactly what it opened when the stack unwinds.
"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import cast

from litestar import Litestar

from core.logger import logger
from core.state import State
from e_api.adapters.http import HttpAdapter
from e_api.adapters.redis import RedisAdapter
from e_api.adapters.sqlite import SQLiteAdapter


@asynccontextmanager
async def lifespan(app: Litestar) -> AsyncIterator[None]:
    """Open every external edge on its own exit stack, mounted under `app.state.adapters`."""
    state = cast("State", app.state)
    state.adapters.redis = RedisAdapter()
    state.adapters.sqlite = SQLiteAdapter()
    state.adapters.http = HttpAdapter()
    async with AsyncExitStack() as stack:
        for adapter in state.adapters.values():
            await stack.enter_async_context(adapter)
        logger.info("adapters ready", edges=sorted(state.adapters), step="START")
        yield
    logger.info("adapters closed", step="STOP")
