"""tests/unit/e_management/ui/view: the plan rendered — what the user reviews is what the engine will do."""

from typing import TYPE_CHECKING

from e_management.cli import commands
from e_management.ui.view import render_plan

if TYPE_CHECKING:
    from pathlib import Path

    from e_management.models.manifest import Manifest


def test_render_plan_shows_every_action_kind(repo: Path, spec: Manifest) -> None:
    plan = commands.plan(repo, spec, "api", "myapp", off=frozenset({"websockets"}))
    out = render_plan(plan)
    assert "e_myapp" in out
    assert "copy template" in out
    assert "materialize" in out
    assert "e_api → e_myapp" in out
    assert "src/e_api/websockets" in out
