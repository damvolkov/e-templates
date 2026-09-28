"""tests/unit/e_api: the live app on the real graph — SECRET and DB_PATH from the source, before any import."""

import os
import tempfile
from pathlib import Path

os.environ.setdefault("SECRET", "unit-test-secret-0123456789")
os.environ.setdefault("DB_PATH", str(Path(tempfile.mkdtemp(prefix="e-api-tests-")) / "test.db"))

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from litestar.testing import TestClient

from e_api.main import create_app

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        store = test_client.app.state.adapters.sqlite
        with test_client.portal() as portal:  # one shared file per process: every test starts from empty
            for key in portal.call(store.keys):
                portal.call(store.delete, key)
        yield test_client


@pytest.fixture
def bearer(client):
    """Mint real tokens with the live crypto engine — the fake check accepts exactly what crypto signs."""

    def make(subject: str) -> dict[str, str]:
        token = client.app.state.crypto.create_token({"sub": subject}, expires_in=timedelta(minutes=5))
        return {"Authorization": f"Bearer {token}"}

    return make


@pytest.fixture
def created_user(client) -> dict:
    response = client.post(
        "/users",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "correct-horse-1",
            "quota": "12.50",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
