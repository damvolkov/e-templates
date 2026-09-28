"""Auto-discoverable settings submodule: the redis edge — REDIS_URL."""

from e_core.core.settings.base import BaseSettings


class RedisSettings(BaseSettings, frozen=True):
    """REDIS_URL — anything redis.asyncio.from_url understands."""

    redis_url: str = "redis://localhost:6379/0"
