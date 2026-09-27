"""adapters.redis: StoreAdapter over redis.asyncio (the official client, async driver)."""

from typing import ClassVar

import redis.asyncio as aioredis

from e_app.adapters.base import StoreAdapter
from e_app.core.settings import BaseSettings

##### TYPES #####
class RedisSettings(BaseSettings, frozen=True):
    """REDIS__URL — anything `from_url` understands."""

    env_prefix: ClassVar[str] = "REDIS__"
    url: str = "redis://localhost:6379/0"


class RedisAdapter(StoreAdapter):
    """Thin KV over a redis connection pool; bytes in, bytes out — decode stays off."""

    name: ClassVar[str] = "redis"

    def __init__(self, settings: RedisSettings | None = None) -> None:
        self._settings = settings or RedisSettings.load()
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        self._client = aioredis.from_url(self._settings.url)

    async def close(self) -> None:
        match self._client:
            case None:
                return
            case client:
                await client.aclose()
                self._client = None

    async def get(self, key: str) -> bytes | None:
        return await self._connected().get(key)

    async def set(self, key: str, value: bytes) -> None:
        await self._connected().set(key, value)

    async def delete(self, key: str) -> None:
        await self._connected().delete(key)

    async def keys(self, prefix: str = "") -> list[str]:
        found = await self._connected().keys(f"{prefix}*")
        return sorted(map(bytes.decode, found))

    def _connected(self) -> aioredis.Redis:
        match self._client:
            case None:
                msg = "RedisAdapter not connected: the lifespan opens it, handlers never do"
                raise RuntimeError(msg)
            case client:
                return client
