"""adapters.redis: StoreAdapter over redis.asyncio (the official client, async driver)."""

from typing import TYPE_CHECKING, ClassVar, cast

import redis.asyncio as redis

from core.settings import settings as st
from e_api.adapters.base import StoreAdapter

if TYPE_CHECKING:
    from core.settings.redis import RedisSettings


##### TYPES #####
class RedisAdapter(StoreAdapter):
    """Thin KV over a redis connection pool; bytes in, bytes out — decode stays off."""

    name: ClassVar[str] = "redis"

    def __init__(self, settings: RedisSettings = st.redis) -> None:
        self._url = settings.redis_url
        self._client: redis.Redis | None = None

    async def connect(self) -> None:
        self._client = redis.from_url(self._url)

    async def close(self) -> None:
        match self._client:
            case None:
                return
            case client:
                await client.aclose()
                self._client = None

    async def get(self, key: str) -> bytes | None:
        return cast("bytes | None", await self._connected().get(key))

    async def set(self, key: str, value: bytes) -> None:
        await self._connected().set(key, value)

    async def delete(self, key: str) -> None:
        await self._connected().delete(key)

    async def keys(self, prefix: str = "") -> list[str]:
        found = cast("list[bytes]", await self._connected().keys(f"{prefix}*"))
        return sorted(key.decode() for key in found)

    def _connected(self) -> redis.Redis:
        match self._client:
            case None:
                msg = "RedisAdapter not connected: the lifespan opens it, handlers never do"
                raise RuntimeError(msg)
            case client:
                return client
