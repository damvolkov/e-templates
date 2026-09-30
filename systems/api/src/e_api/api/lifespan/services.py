"""api.lifespan.services: assemble the engines that travel with the app.

Crypto and the IdP-backed oauth registry are written into `app.state`; they are pure in-process
objects, so this concern owns no resource to close.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from authlib.integrations.starlette_client import OAuth
from litestar import Litestar

from core.crypto import Crypto
from core.logger import logger
from core.settings import settings as st
from core.state import State


@asynccontextmanager
async def lifespan(app: Litestar) -> AsyncIterator[None]:
    """Assemble the engines that travel with the app: crypto and the IdP-backed oauth registry."""
    state = cast("State", app.state)
    state.crypto = Crypto(st.crypto)
    state.oauth = OAuth()
    match st.oauth.server_metadata_url:
        case "":
            ### dev mode: empty registry, the app boots without an IdP
            pass
        case url:
            state.oauth.register(
                st.oauth.oauth_name,
                client_id=st.oauth.client_id,
                client_secret=st.oauth.client_secret,
                server_metadata_url=url,
            )
    logger.info("services ready", step="START")
    yield
