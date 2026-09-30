"""tests/unit/e_management/adapters/draft: the session survives terminals — round-trip, absent, and corrupt all answer cleanly."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from e_management.adapters.draft import DraftStore
from e_management.core.session import Session, Step


def test_draft_round_trips_decisions(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "draft.json")
    session = Session(template="api", name="myapp", off=("websockets",), seen=(Step.SYSTEM,))
    store.save(session)
    assert store.load() == session


def test_draft_load_is_none_without_a_file(tmp_path: Path) -> None:
    assert DraftStore(tmp_path / "draft.json").load() is None


def test_draft_load_is_none_on_a_corrupt_file(tmp_path: Path) -> None:
    broken = tmp_path / "draft.json"
    broken.write_text("[1,2]")
    assert DraftStore(broken).load() is None


def test_draft_drop_makes_it_absent(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "draft.json")
    store.save(Session())
    store.drop()
    assert store.load() is None
    store.drop()
