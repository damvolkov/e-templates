"""ui.screens: thin forms over the session — one decision per stage, saved to the draft; back never destroys what still holds."""

from typing import TYPE_CHECKING, cast

from msgspec import UNSET
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from e_management.core.errors import ManagementError
from e_management.core.session import Step
from e_management.models.manifest import Group
from e_management.ui.view import render_plan
from ops.tui import HeaderTui

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from textual.app import ComposeResult

    from e_management.models.manifest import Choice
    from e_management.ops.scan import Unit
    from e_management.ui.app import ManagementApp


##### TYPES #####
class Section(Static):
    """Two-line sub-header inside the stage box: the family (COMMON/SYSTEM) and the member."""

    DEFAULT_CSS = """
    Section { text-style: bold; margin-bottom: 1; }
    Section .member { color: #6f9bff; }
    """


class WizardScreen(Screen[None]):
    """Shared plumbing: masthead, stage box, typed app, error line and the draft-saving confirmation."""

    @property
    def management(self) -> ManagementApp:
        return cast("ManagementApp", self.app)

    def compose(self) -> ComposeResult:
        yield HeaderTui(max_height=6)
        with Vertical(id="stage"):
            yield from self.body()

    def fail(self, message: str) -> None:
        self.query_one("#error", Static).update(f"✗ {message}")

    def mark(self, step: str) -> None:
        """Confirm a stage: recorded in the session and persisted — the unit of the wizard's memory."""
        self.management.session.seen = (*self.management.session.seen, step)
        self.management.save_draft()

    def body(self) -> ComposeResult:
        """The stage's own widgets."""
        raise NotImplementedError
        yield


class ToggleScreen(WizardScreen):
    """A stage of ON/OFF tiles: each item carries a key, a label and a locked flag; the flow is a class fact."""

    STEP: str
    FAMILY = "SYSTEM"

    def items(self) -> Iterator[tuple[str, str, bool]]:
        raise NotImplementedError
        yield

    def disabled(self) -> set[str]:
        raise NotImplementedError

    def commit(self, disabled: set[str]) -> None:
        raise NotImplementedError

    def toggle(self, key: str) -> set[str]:
        """The disabled set after flipping ``key`` — overridable by stages with cascades."""
        off = self.disabled()
        if key in off:
            off.discard(key)
        else:
            off.add(key)
        return off

    def next_screen(self) -> Screen:
        return self.management.advance(self.STEP)

    @staticmethod
    def tile_id(key: str) -> str:
        return "tile-" + key.replace("/", "-")

    @staticmethod
    def tile_key(tile_id: str) -> str:
        return tile_id.removeprefix("tile-").replace("-", "/")

    def body(self) -> ComposeResult:
        yield Section(f"{self.FAMILY}\n{self._member()}", classes="section")
        for key, label, locked in self.items():
            off = key in self.disabled()
            yield Button(
                self._label(key, label, locked=locked),
                id=self.tile_id(key),
                variant="primary" if locked else "error" if off else "success",
            )
        yield Button("continue", id="next", variant="primary")
        yield Static("", id="error", classes="error")

    def _label(self, key: str, label: str, *, locked: bool) -> str:
        prefix = "LOCK" if locked else "OFF" if key in self.disabled() else "ON "
        return f"{prefix}  {label}"

    def _member(self) -> str:
        return self.STEP

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if not event.button.id.startswith("tile-"):
            self._advance()
            return
        key = self.tile_key(event.button.id)
        if any(k == key and locked for k, _, locked in self.items()):
            self.fail(f"{key} is imported by the system itself — it stays")
            return
        try:
            self.commit(self.toggle(key))
        except ValueError as exc:
            self.fail(str(exc))
            return
        self.management.save_draft()
        for button in self.query(Button):
            if button.id.startswith("tile-"):
                self._repaint(button)

    def _repaint(self, button: Button) -> None:
        key = self.tile_key(button.id)
        _, label, locked = next(item for item in self.items() if item[0] == key)
        button.label = self._label(key, label, locked=locked)
        button.variant = "primary" if locked else "error" if key in self.disabled() else "success"

    def _advance(self) -> None:
        app = self.management
        try:
            app.plan()
        except (ManagementError, ValueError) as exc:
            self.fail(str(exc))
        else:
            self.mark(self.STEP)
            self.app.push_screen(self.next_screen())


class SystemScreen(WizardScreen):
    """Stage 1: pick the template and name the project — the name is validated by the domain's own Blueprint."""

    def body(self) -> ComposeResult:
        app = self.management
        picked = str(app.session.template)
        stored = app.session.name
        yield Section("SYSTEM\nchoose", classes="section")
        yield Static("pick a template, name it (slug: lowercase, digits, underscores) and press enter", classes="hint")
        for name in sorted(app.spec.templates):
            yield Button(f"{'▶' if name == picked else ' '} {name}", id=f"template-{name}", variant="primary")
        yield Input(placeholder="myapp", value="" if stored is UNSET else str(stored), id="name")
        yield Static("", id="error", classes="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        app = self.management
        app.session.template = event.button.id.removeprefix("template-")
        app.save_draft()
        for button in self.query(Button):
            if button.id.startswith("template-"):
                name = button.id.removeprefix("template-")
                button.label = f"{'▶' if name == app.session.template else ' '} {name}"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        app = self.management
        try:
            app.blueprint(event.value)
        except ManagementError as exc:
            self.fail(str(exc))
        else:
            app.session.name = event.value
            app.begin_flow()
            self.mark(Step.SYSTEM)
            self.app.push_screen(app.advance(Step.SYSTEM))


class CommonAreaScreen(ToggleScreen):
    """One stage per discovered COMMON area: a tile per unit, ON by default, dropping cascades over dependents."""

    FAMILY = "COMMON"

    def __init__(self, area: str) -> None:
        super().__init__()
        self.STEP = f"common-{area}"
        self.area = area

    def _member(self) -> str:
        return self.area

    def items(self) -> Iterator[tuple[str, str, bool]]:
        unit: Unit
        for unit in self.management.survey().units(self.area):
            yield (
                unit.key,
                f"{unit.name}  ({len(unit.tests)} test files)" if unit.tests else unit.name,
                unit.key in self.management.survey().required,
            )

    def disabled(self) -> set[str]:
        return set(self.management.session.drop)

    def commit(self, disabled: set[str]) -> None:
        self.management.session.drop = tuple(sorted(self.management.survey().cascade(frozenset(disabled))))

    def toggle(self, key: str) -> set[str]:
        return set(self.disabled()) ^ {key}


class ChoiceAreaScreen(ToggleScreen):
    """A stage over the template's declared choices of one group (modules, infra, cicd)."""

    GROUPS: tuple[Group, ...] = ()

    def __init__(self, step: str = "modules") -> None:
        super().__init__()
        self.STEP = step

    def _member(self) -> str:
        return self.STEP

    def choices(self) -> tuple[Choice, ...]:
        app = self.management
        declared = app.spec.templates[str(app.session.template)].choices
        return tuple(choice for choice in declared if choice.group in self.GROUPS)

    def items(self) -> Iterator[tuple[str, str, bool]]:
        choice: Choice
        for choice in self.choices():
            yield choice.name, choice.label or choice.name, False

    def disabled(self) -> set[str]:
        return set(self.management.session.off)

    def commit(self, disabled: set[str]) -> None:
        self.management.session.off = tuple(sorted(disabled))


class ConfirmScreen(WizardScreen):
    """Final stage: destination, unit tests post-export, the full plan — algorithms run only on generate."""

    def compose(self) -> ComposeResult:
        yield HeaderTui(max_height=6)
        app = self.management
        stored = app.session.dest
        with Vertical(id="stage"):
            yield Section("SYSTEM\nconfirm", classes="section")
            yield Input(
                value="" if stored is UNSET else str(stored),
                placeholder=str(app.suggested()),
                id="dest",
            )
            tests_on = app.session.verify_tests
            with Horizontal(id="actions"):
                yield Button(
                    f"{'RUN ' if tests_on else 'SKIP '}unit tests after export",
                    id="tests",
                    variant="success" if tests_on else "error",
                )
                yield Button("generate", id="go", variant="primary")
            with VerticalScroll(id="planbox"):
                yield Static(self._plan_text(), id="plan")
            yield Static("", id="error", classes="error")

    def on_input_submitted(self, event: Input.Submitted) -> None:  # noqa: ARG002 — the signature is the message contract
        self._take_dest()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        app = self.management
        match event.button.id:
            case "tests":
                app.session.verify_tests = not app.session.verify_tests
                app.save_draft()
                button = self.query_one("#tests", Button)
                button.label = f"{'RUN ' if app.session.verify_tests else 'SKIP '}unit tests after export"
                button.variant = "success" if app.session.verify_tests else "error"
            case "go":
                self._generate()

    def _take_dest(self) -> Path | None:
        app = self.management
        field = self.query_one(Input)
        app.session.dest = str(app.suggested() if not field.value else field.value)
        try:
            app.check_target(app.session.target())
        except OSError as exc:
            self.fail(str(exc))
            return None
        return app.session.target()

    def _generate(self) -> None:
        app = self.management
        if self._take_dest() is not None and (plan := app.plan()) is not None:
            self.mark("confirm")
            app.start_generate(plan)

    def _plan_text(self) -> str:
        app = self.management
        try:
            plan = app.plan()
        except (ManagementError, ValueError) as exc:
            return f"stale session: {exc}"
        return render_plan(plan)


class ProgressScreen(WizardScreen):
    """The pipeline's log: every emitted line of every step, streaming while generation and verification run."""

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def compose(self) -> ComposeResult:
        yield HeaderTui(max_height=6)
        with VerticalScroll(id="stage"):
            yield Static("generating…  ctrl+q quits; the draft survives", classes="title")
            yield Static("", id="log")

    async def line(self, text: str) -> None:
        self.lines.append(text)
        self.query_one("#log", Static).update("\n".join(self.lines))


class ReportScreen(WizardScreen):
    """The verdict: ready to work — or the failed steps, verbatim, with a way back to fix and retry."""

    def __init__(self, *, ok: bool, dest: Path, failures: list[str]) -> None:
        super().__init__()
        self.ok, self.dest, self.failures = ok, dest, failures

    def body(self) -> ComposeResult:
        verdict = (
            f"✓ {self.dest} is ready to work — cd in and start"
            if self.ok
            else "✗ stopped:\n" + "\n".join(self.failures[-40:])
        )
        yield Static(verdict, id="verdict")
        if self.ok:
            yield Button("finish", id="finish", variant="primary")
        else:
            yield Button("back to review", id="retry", variant="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "finish":
                self.app.exit()
            case _:
                self.app.pop_screen()


class ModulesScreen(ChoiceAreaScreen):
    """The functional modules the service itself ships with."""

    def __init__(self) -> None:
        super().__init__("modules")
        self.GROUPS = (Group.MODULES,)


class OptionsScreen(ChoiceAreaScreen):
    """Infrastructure and CI/CD surfaces of the service."""

    def __init__(self) -> None:
        super().__init__("options")
        self.GROUPS = (Group.INFRA, Group.CICD)
