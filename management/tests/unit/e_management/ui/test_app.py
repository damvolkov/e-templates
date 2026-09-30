"""tests/unit/e_management/ui/app: the wizard's flow and memory — driven through the screens' own handlers (headless-click dispatch is flaky on pushed screens, the logic is not)."""

from typing import TYPE_CHECKING, cast

from textual.widgets import Button, Input

from e_management.core.session import Step
from e_management.ui.app import ManagementApp
from e_management.ui.screens import (
    CommonAreaScreen,
    ConfirmScreen,
    ModulesScreen,
    OptionsScreen,
    SystemScreen,
    ToggleScreen,
)

if TYPE_CHECKING:
    from pathlib import Path

    from e_management.models.manifest import Manifest


def pick(app: ManagementApp, button_id: str) -> Button:
    return next(b for b in app.screen.query(Button) if b.id == button_id)


async def press(app: ManagementApp, pilot, button_id: str) -> None:
    """Invoke the active screen's real handler for one button, then let the loop settle."""
    cast("ToggleScreen", app.screen).on_button_pressed(Button.Pressed(pick(app, button_id)))
    await pilot.pause()


async def submit_name(app: ManagementApp, pilot, value: str) -> None:
    field = app.screen.query_one(Input)
    field.value = value
    cast("SystemScreen", app.screen).on_input_submitted(Input.Submitted(field, value))
    await pilot.pause()


async def test_wizard_walks_the_dynamic_flow(tmp_path: Path, repo: Path, spec: Manifest) -> None:
    draft = tmp_path / "draft.json"
    app = ManagementApp(spec, repo, draft)
    async with app.run_test(size=(100, 60)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, SystemScreen)

        await press(app, pilot, "template-api")
        assert app.session.template == "api"
        assert draft.exists()

        await submit_name(app, pilot, "Bad Name")
        assert isinstance(app.screen, SystemScreen), "an invalid slug must not advance"

        await submit_name(app, pilot, "myapp")
        assert app.session.steps[:3] == (Step.SYSTEM, "common-adapters", "common-core")
        assert isinstance(app.screen, CommonAreaScreen)
        assert app.screen.area == "adapters"

        for step in ("common-adapters", "common-core", "common-ops"):
            assert step == app.screen.STEP, (app.screen.STEP, step)
            await press(app, pilot, "next")

        assert isinstance(app.screen, ModulesScreen)
        await press(app, pilot, "tile-websockets")
        assert app.session.off == ("websockets",)
        await press(app, pilot, "next")

        assert isinstance(app.screen, OptionsScreen)
        await press(app, pilot, "tile-docker")
        assert set(app.session.off) == {"docker", "websockets"}
        await press(app, pilot, "next")

        assert isinstance(app.screen, ConfirmScreen)
        assert app.session.stage() == "confirm"


async def test_back_returns_without_losing_decisions(tmp_path: Path, repo: Path, spec: Manifest) -> None:
    app = ManagementApp(spec, repo, tmp_path / "draft.json")
    async with app.run_test(size=(100, 60)) as pilot:
        await pilot.pause()
        await press(app, pilot, "template-api")
        await submit_name(app, pilot, "myapp")
        assert isinstance(app.screen, CommonAreaScreen)

        app.action_step_back()
        await pilot.pause()
        assert isinstance(app.screen, SystemScreen)
        assert app.session.name == "myapp"


async def test_app_resumes_on_the_first_unseen_step(tmp_path: Path, repo: Path, spec: Manifest) -> None:
    draft = tmp_path / "draft.json"
    first = ManagementApp(spec, repo, draft)
    async with first.run_test(size=(100, 60)) as pilot:
        await pilot.pause()
        await press(first, pilot, "template-api")
        await submit_name(first, pilot, "myapp")
        await press(first, pilot, "next")

    resumed = ManagementApp(spec, repo, draft)
    async with resumed.run_test(size=(100, 60)):
        assert isinstance(resumed.screen, CommonAreaScreen)
        assert resumed.screen.area == "core"
        assert resumed.session.seen == (Step.SYSTEM, "common-adapters")
