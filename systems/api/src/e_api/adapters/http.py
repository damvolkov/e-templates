"""adapters.http: the external-service client on wreq (Rust wreq bindings, browser-fidelity TLS).

The third member of the adapter family: redis and sqlite speak KV, http speaks HTTP — all three
share the connect/close contract and are opened by the lifespan's AsyncExitStack.
"""

from typing import TYPE_CHECKING, Any, ClassVar

import wreq

from core.settings import settings as st
from e_api.adapters.base import BaseAdapter

if TYPE_CHECKING:
    from core.settings.http import HttpSettings


##### TYPES #####
class HttpAdapter(BaseAdapter):
    """One wreq client per app: base_url and timeout come from HttpSettings, responses leave as data."""

    name: ClassVar[str] = "http"

    def __init__(self, settings: HttpSettings = st.http) -> None:
        self._base_url = settings.http_base_url
        self._timeout = settings.http_timeout
        self._client: wreq.Client | None = None

    ##### PRIVATE #####
    def _common_url(self, path: str) -> str:
        ### wreq 0.12 drops the client's base_url for relative paths (BadScheme): join here, one place, both verbs.
        return path if path.startswith(("http://", "https://")) else f"{self._base_url.rstrip('/')}/{path.lstrip('/')}"

    def _connected(self) -> wreq.Client:
        match self._client:
            case None:
                msg = "HttpAdapter not connected: the lifespan opens it, handlers never do"
                raise RuntimeError(msg)
            case client:
                return client

    ############################################################

    ##### PUBLIC #####
    async def connect(self) -> None:
        self._client = wreq.Client(timeout=self._timeout)

    async def close(self) -> None:
        match self._client:
            case None:
                return
            case client:
                client.close()  # sync in wreq: drops the Rust pool; our contract stays async
                self._client = None

    async def get(self, path: str) -> Any:
        """GET against base_url; non-2xx raises the library's own StatusError, never a silent body."""
        response = await self._connected().get(self._common_url(path))
        response.raise_for_status()
        return await response.json()

    async def post(self, path: str, payload: Any) -> Any:
        response = await self._connected().post(self._common_url(path), json=payload)
        response.raise_for_status()
        return await response.json()
