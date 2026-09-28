"""tests/unit: the lifespan contract — exit stack opens, seals, and closes in reverse."""

import inspect
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
from litestar.testing import TestClient

from core.settings import Settings
from core.state import State
from e_api.api.lifespan import adapters, sealed, services
from e_api.main import create_app

if TYPE_CHECKING:
    from litestar import Litestar


def test_lifespans_are_declared_not_built() -> None:
    assert all(callable(cm) for cm in (adapters.lifespan, services.lifespan, sealed.lifespan))
    assert list(inspect.signature(create_app).parameters) == []


def test_graph_carries_the_three_edges(client) -> None:
    adapters = client.app.state.adapters
    assert sorted(adapters) == ["http", "redis", "sqlite"]
    assert adapters.sqlite.name == "sqlite"


def test_graph_opens_sealed(client) -> None:
    graph = client.app.state
    assert "crypto" in graph
    assert "oauth" in graph
    with pytest.raises(RuntimeError, match="Sealed"):
        graph.held_by_the_lifespan_only = 1
    with pytest.raises(AttributeError, match="Sealed state has no node"):
        _ = graph.typo_of_a_node


async def test_adapters_close_when_the_lifespan_exits() -> None:
    with TestClient(create_app()) as client:
        store = client.app.state.adapters.sqlite
        assert client.get("/health").status_code == 200
        await store.get("anything")  # alive inside the cycle
    with pytest.raises(RuntimeError, match="not connected"):
        await store.get("anything")  # the stack closed it on shutdown


async def test_services_register_configured_idp(monkeypatch: pytest.MonkeyPatch) -> None:
    """The non-empty branch of the match: a metadata url means a named client in the registry."""
    monkeypatch.setattr(
        services,
        "st",
        Settings.load(
            oauth={"client_id": "cid", "client_secret": "sec", "server_metadata_url": "https://idp.test/openid"}
        ),
    )
    app = SimpleNamespace(state=State())
    async with services.lifespan(cast("Litestar", app)):
        assert app.state.crypto is not None
    assert "dev" in app.state.oauth._registry
