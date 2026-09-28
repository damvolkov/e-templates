"""tests/unit: adapter contract — sqlite and redis full lifecycles, http against a local server: all offline-safe."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import fakeredis.aioredis
import pytest
import wreq

from core.settings.db import DbSettings
from core.settings.http import HttpSettings
from core.settings.redis import RedisSettings
from e_api.adapters import redis as redis_module
from e_api.adapters.http import HttpAdapter
from e_api.adapters.redis import RedisAdapter
from e_api.adapters.sqlite import SQLiteAdapter

if TYPE_CHECKING:
    from collections.abc import Iterator


##### HTTP SERVER — a real socket on localhost: wreq speaks HTTP, no transport can be injected #####
class _JSONHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self._respond(200, b'{"hello": "world"}') if self.path == "/ok" else self._respond(500, b'{"error": "boom"}')

    def do_POST(self) -> None:
        self._respond(200, self.rfile.read(int(self.headers["content-length"])))  # echo the payload

    def _respond(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 — name imposed by http.server
        """Quiet: http.server's per-request stderr noise stays out of the test output."""


@pytest.fixture
def http_server() -> Iterator[str]:
    with ThreadingHTTPServer(("127.0.0.1", 0), _JSONHandler) as srv:
        worker = threading.Thread(target=srv.serve_forever, daemon=True)
        worker.start()
        yield f"http://127.0.0.1:{srv.server_port}"
        srv.shutdown()
        worker.join()


async def test_sqlite_crud_cycle(tmp_path) -> None:
    adapter = SQLiteAdapter(DbSettings(db_path=tmp_path / "kv.db"))
    async with adapter:
        await adapter.set("user:1", b"one")
        assert await adapter.get("user:1") == b"one"
        assert await adapter.get("missing") is None

        await adapter.set("user:2", b"two")
        await adapter.set("other:1", b"x")
        assert await adapter.keys("user:") == ["user:1", "user:2"]

        await adapter.delete("user:1")
        assert await adapter.get("user:1") is None
        await adapter.delete("user:1")  # idempotent


async def test_close_survives_double(tmp_path) -> None:
    adapter = SQLiteAdapter(DbSettings(db_path=tmp_path / "kv.db"))
    await adapter.connect()
    await adapter.close()
    await adapter.close()  # closing a closed store is a no-op, not an error


async def test_closed_adapter_refuses(tmp_path) -> None:
    adapter = SQLiteAdapter(DbSettings(db_path=tmp_path / "kv.db"))
    async with adapter:
        pass
    with pytest.raises(RuntimeError, match="not connected"):
        await adapter.get("anything")


async def test_redis_offline_contract() -> None:
    adapter = RedisAdapter(RedisSettings(redis_url="redis://localhost:1/0"))  # never connected on purpose
    assert adapter.name == "redis"
    with pytest.raises(RuntimeError, match="not connected"):
        await adapter.get("anything")


async def test_http_adapter_lifecycle_needs_no_network() -> None:
    """wreq opens a pool, not a connection: the cycle is pure client construction and drop."""
    adapter = HttpAdapter(HttpSettings())
    async with adapter:
        assert adapter.name == "http"
    with pytest.raises(RuntimeError, match="not connected"):
        await adapter.get("/get")


async def test_http_roundtrip_and_status_error(http_server: str) -> None:
    """Real bytes over a real socket: decode on success, the library's own error on non-2xx, no-op close after."""
    adapter = HttpAdapter(HttpSettings(http_base_url=http_server))
    async with adapter:
        assert await adapter.get("/ok") == {"hello": "world"}
        assert await adapter.post("/echo", {"ping": 1}) == {"ping": 1}
        with pytest.raises(wreq.StatusError):
            await adapter.get("/bad")
    await adapter.close()  # the stack already closed it: second close is the None branch, not an error


async def test_redis_connected_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """fakeredis answers from_url: the full KV cycle without a server, exactly as the lifespan would open it."""
    monkeypatch.setattr(redis_module.redis, "from_url", fakeredis.aioredis.FakeRedis.from_url)
    adapter = RedisAdapter(RedisSettings(redis_url="redis://fake:6379/0"))
    async with adapter:
        await adapter.set("user:1", b"one")
        assert await adapter.get("user:1") == b"one"
        assert await adapter.get("missing") is None
        await adapter.set("user:2", b"two")
        assert await adapter.keys("user:") == ["user:1", "user:2"]
        await adapter.delete("user:1")
        assert await adapter.get("user:1") is None
    await adapter.close()  # idempotent, as with every member of the family
