"""tests/unit/e_core/ops/tui: HeaderTui behavior — render and content height at every width, never internals."""

from typing import TYPE_CHECKING

import pytest

from e_core.ops.tui import HeaderTui

if TYPE_CHECKING:
    from collections.abc import Callable

    from textual.app import App

##### SIZES: huge, wide, medium, narrow, tiny, absurd #####
SIZES: list[tuple[int, int]] = [(200, 50), (90, 22), (40, 16), (20, 12), (8, 6), (3, 4)]
FRAMED: list[tuple[int, int]] = [(200, 50), (60, 20), (10, 8)]


@pytest.mark.parametrize(("width", "height"), SIZES, ids=["huge", "wide", "medium", "narrow", "tiny", "absurd"])
async def test_tui_render_never_overflows(host_app: Callable[[HeaderTui], App[None]], width: int, height: int) -> None:
    """No line crosses the terminal width, no block crosses its height, and the height promise holds."""
    app = host_app(HeaderTui())
    async with app.run_test(size=(width, height)):
        header = app.screen.query_one(HeaderTui)
        lines = str(header.render()).splitlines()
        assert lines
        assert all(len(line) <= width for line in lines)
        assert len(lines) <= height
        assert header.get_content_height(0, 0, width) == len(lines)


@pytest.mark.parametrize(("width", "height"), FRAMED, ids=["huge", "medium", "compact"])
async def test_tui_frames_the_logo(host_app: Callable[[HeaderTui], App[None]], width: int, height: int) -> None:
    """Art or compact fallback: the outer rows are pure frame, and the logo paints inside them."""
    app = host_app(HeaderTui())
    async with app.run_test(size=(width, height)):
        header = app.screen.query_one(HeaderTui)
        lines = [line.lstrip() for line in str(header.render()).splitlines()]
        assert set(lines[0]) <= {"█", "▀"}
        assert lines[0][0] == lines[0][-1] == "█"
        assert set(lines[-1]) <= {"█", "▄"}
        assert lines[-1][0] == lines[-1][-1] == "█"
        assert any(any(cell in line for cell in "▀▄█") for line in lines[1:-1])


async def test_tui_sub_is_a_tagline_not_a_second_logo(host_app: Callable[[HeaderTui], App[None]]) -> None:
    """At the same scale, the sub grows the block by less than the title already is."""
    bare = host_app(HeaderTui("AB", "", max_height=1))
    tagged = host_app(HeaderTui("AB", "cd", max_height=1))
    async with bare.run_test(size=(120, 40)):
        title_rows = bare.screen.query_one(HeaderTui).get_content_height(0, 0, 120)
    async with tagged.run_test(size=(120, 40)):
        full_rows = tagged.screen.query_one(HeaderTui).get_content_height(0, 0, 120)
    assert 0 < full_rows - title_rows < title_rows


async def test_tui_falls_back_to_compact_frame(host_app: Callable[[HeaderTui], App[None]]) -> None:
    """Where not even scale 1 fits, a framed plain-text block answers within the width."""
    app = host_app(HeaderTui())
    async with app.run_test(size=(8, 6)):
        header = app.screen.query_one(HeaderTui)
        lines = str(header.render()).splitlines()
        assert len(lines) == 4
        assert all(len(line) == 8 for line in lines)
        assert "E" in lines[1]
        assert "e" in lines[2]


async def test_tui_reacts_to_new_text(host_app: Callable[[HeaderTui], App[None]]) -> None:
    """The main reactive always renders uppercase and repaints through the same contract."""
    app = host_app(HeaderTui("AB", "cd"))
    async with app.run_test(size=(90, 22)) as pilot:
        header = app.screen.query_one(HeaderTui)
        header.main = "zz"
        header.sub = ""
        await pilot.pause()
        assert header.main == "ZZ"
        assert str(header.render()).strip()
