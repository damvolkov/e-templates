"""tests/unit/e_app: the app under test — bare graph (no redis), temp sqlite, crypto from env."""

from collections.abc import Iterator
from datetime import timedelta

import pytest
from litestar.testing import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("CRYPTO__SECRET", "unit-test-secret-0123456789")
    monkeypatch.setenv("DB__PATH", str(tmp_path / "test.db"))
    from e_app.adapters.sqlite import SQLiteAdapter
    from e_app.main import create_app

    with TestClient(create_app(adapters=(SQLiteAdapter(),))) as test_client:
        yield test_client


@pytest.fixture
def bearer(client):
    """Mint real tokens with the live crypto engine — the fake check accepts exactly what crypto signs."""

    def make(subject: str) -> dict[str, str]:
        token = client.app.state.graph.crypto.create_token({"sub": subject}, expires_in=timedelta(minutes=5))
        return {"Authorization": f"Bearer {token}"}

    return make


@pytest.fixture
def created_user(client) -> dict:
    response = client.post(
        "/users",
        json={"username": "alice", "email": "alice@example.com", "password": "correct-horse-1", "quota": "12.50"},
    )
    assert response.status_code == 201, response.text
    return response.json()
