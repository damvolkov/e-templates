"""tests/unit/e_core/ops: shared textual harness."""

from typing import TYPE_CHECKING

import pytest
from textual.app import App, ComposeResult

if TYPE_CHECKING:
    from collections.abc import Callable

    from e_core.ops.tui import HeaderTui


class HostApp(App[None]):
    """The minimum app that composes the header under test."""

    def __init__(self, masthead: HeaderTui) -> None:
        super().__init__()
        self.masthead = masthead

    def compose(self) -> ComposeResult:
        yield self.masthead


@pytest.fixture
def host_app() -> Callable[[HeaderTui], App[None]]:
    """The app class: tests mount their own HeaderTui through it."""
    return HostApp
