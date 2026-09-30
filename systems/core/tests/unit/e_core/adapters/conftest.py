"""tests/unit/e_core/adapters: the http harness — a real stdlib socket on localhost, offline-safe."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator


class JsonHandler(BaseHTTPRequestHandler):
    """Answers /ok with a JSON body, echoes POST payloads, 500 on everything else."""

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
    """A live base_url served from a daemon thread, shut down with the test."""
    with ThreadingHTTPServer(("127.0.0.1", 0), JsonHandler) as srv:
        worker = threading.Thread(target=srv.serve_forever, daemon=True)
        worker.start()
        yield f"http://127.0.0.1:{srv.server_port}"
        srv.shutdown()
        worker.join()
