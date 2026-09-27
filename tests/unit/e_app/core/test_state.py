"""tests/unit: the resource graph — attribute navigation, nested categories, seal."""

import pytest

from e_app.core.state import State


def test_navigation_is_attribute_first() -> None:
    crypto = object()
    state = State(adapters=State(sqlite=object()), crypto=crypto)
    assert state.crypto is crypto
    assert state["crypto"] is crypto
    assert "sqlite" in state.adapters
    assert sorted(state) == ["adapters", "crypto"]
    assert len(state) == 2


def test_missing_node_names_what_exists() -> None:
    state = State(crypto=object())
    with pytest.raises(AttributeError, match="crypto"):
        _ = state.nope


def test_seal_blocks_mutation() -> None:
    state = State()
    state.adapters = State()
    state.seal()
    with pytest.raises(RuntimeError, match="Sealed"):
        state.extra = 1
    with pytest.raises(RuntimeError, match="Sealed"):
        del state.adapters
