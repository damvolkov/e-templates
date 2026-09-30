"""tests/unit/e_management/ui/banner: the agnostic HeaderTui, mounted as the constant masthead of the wizard."""

from e_management.ui.app import ManagementApp
from ops.tui import HeaderTui


async def test_masthead_mounts_and_paints_bitmap_blocks(repo, spec, tmp_path) -> None:
    app = ManagementApp(spec, repo, tmp_path / "draft.json")
    async with app.run_test(size=(90, 22)) as pilot:
        await pilot.pause()
        header = app.screen.query_one(HeaderTui)
        painted = str(header.render())
        assert any(cell in painted for cell in ("█", "▄", "▀"))
