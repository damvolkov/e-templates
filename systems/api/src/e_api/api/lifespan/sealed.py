"""api.lifespan.sealed: last link of the chain — seal the graph once every concern has written its subtree."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from litestar import Litestar

from core.state import State


@asynccontextmanager
async def lifespan(app: Litestar) -> AsyncIterator[None]:
    """Last link of the chain: from here on the graph is read-only for every request."""
    cast("State", app.state).seal()
    yield
