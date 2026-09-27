"""adapters.sqlite: StoreAdapter over aiosqlite (stdlib sqlite3 is sync-only on 3.14) — one kv table."""

from pathlib import Path
from typing import ClassVar

import aiosqlite

from e_app.adapters.base import StoreAdapter
from e_app.core.settings import BaseSettings

KV_SCHEMA: str = "CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value BLOB NOT NULL)"


##### TYPES #####
class DbSettings(BaseSettings, frozen=True):
    """DB__PATH — the file is created on connect, parent dirs included."""

    env_prefix: ClassVar[str] = "DB__"
    path: Path = Path("data/app.db")


class SQLiteAdapter(StoreAdapter):
    """Same KV contract as redis, backed by one embedded database."""

    name: ClassVar[str] = "sqlite"

    def __init__(self, settings: DbSettings | None = None) -> None:
        self._settings = settings or DbSettings.load()
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._settings.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._settings.path)
        await self._db.executescript(KV_SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        match self._db:
            case None:
                return
            case db:
                await db.close()
                self._db = None

    async def get(self, key: str) -> bytes | None:
        async with self._connected().execute("SELECT value FROM kv WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
        return None if row is None else row[0]

    async def set(self, key: str, value: bytes) -> None:
        await self._connected().execute("INSERT OR REPLACE INTO kv (key, value) VALUES (?, ?)", (key, value))
        await self._connected().commit()

    async def delete(self, key: str) -> None:
        await self._connected().execute("DELETE FROM kv WHERE key = ?", (key,))
        await self._connected().commit()

    async def keys(self, prefix: str = "") -> list[str]:
        async with self._connected().execute("SELECT key FROM kv WHERE key LIKE ? ORDER BY key", (f"{prefix}%",)) as cursor:
            rows = await cursor.fetchall()
        return [row[0] for row in rows]

    def _connected(self) -> aiosqlite.Connection:
        match self._db:
            case None:
                msg = "SQLiteAdapter not connected: the lifespan opens it, handlers never do"
                raise RuntimeError(msg)
            case db:
                return db
