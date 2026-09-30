"""ui.app: the wizard application — one Session holds every decision; only the generate step runs algorithms."""

import asyncio
from typing import TYPE_CHECKING, ClassVar

from textual.app import App
from textual.binding import Binding
from textual.widgets import Footer

from e_management.adapters.draft import DraftStore
from e_management.adapters.runner import CommandRunner
from e_management.adapters.scaffold import Scaffold
from e_management.cli import commands
from e_management.core.session import Session, Step
from e_management.ui.screens import (
    CommonAreaScreen,
    ConfirmScreen,
    ModulesScreen,
    OptionsScreen,
    ProgressScreen,
    ReportScreen,
    SystemScreen,
)

if TYPE_CHECKING:
    from pathlib import Path

    from textual.app import ComposeResult
    from textual.screen import Screen

    from e_management.core.blueprint import Blueprint
    from e_management.core.plan import Plan
    from e_management.models.manifest import Manifest
    from e_management.ops.scan import Survey

##### TYPES #####
SCREENS: dict[str, type] = {
    Step.SYSTEM: SystemScreen,
    "modules": ModulesScreen,
    "options": OptionsScreen,
    "confirm": ConfirmScreen,
}
APPLY = "apply"
TAIL = ("modules", "options", "confirm")


class ManagementApp(App[None]):
    """Owns the session, the draft, the live common survey and the pipeline: decisions accumulate, survive back, and generate on confirmation."""

    TITLE = "e-management"
    CSS: ClassVar[str] = """
    .title, .section { text-style: bold; margin-bottom: 1; }
    .section { color: #6f9bff; }
    .hint { color: #7c8aa5; margin-bottom: 1; }
    .error { color: $text-error; }
    Input { margin-bottom: 1; }
    Button { margin-bottom: 1; }
    #stage {
        width: 100%;
        height: 1fr;
        border: round #2a52e0;
        margin: 1 0;
        padding: 1 2;
        background: #05070c;
    }
    #actions { height: auto; align-horizontal: left; }
    #actions Button { margin-right: 2; }
    #planbox { height: 1fr; border: tall #16294f; padding: 0 1; }
    """
    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "step_back", "back"), Binding("ctrl+q", "quit", "quit")]

    def __init__(self, spec: Manifest, root: Path, draft_path: Path) -> None:
        super().__init__()
        self.spec = spec
        self.root = root
        self.draft = DraftStore(draft_path)
        self.session: Session = self.draft.load() or Session()
        self.plan_value: Plan | None = None
        self._surveys: dict[str, Survey | None] = {}

    ##### PRIVATE #####

    async def _pipeline(self, plan: Plan) -> None:
        progress = ProgressScreen()
        await self.push_screen(progress)
        steps = [(APPLY, ()), *self.verify_steps()]
        ok = True
        for name, argv in steps:
            await progress.line(f"\n▶ {name}")
            ok = await self._run_step(plan, progress, tuple(argv))
            if not ok:
                break
        self.pop_screen()
        self.push_screen(ReportScreen(ok=ok, dest=self.session.target(), failures=progress.lines))

    async def _run_step(self, plan: Plan, progress: ProgressScreen, argv: tuple[str, ...]) -> bool:
        dest = self.session.target()
        if not argv:
            try:
                await asyncio.to_thread(Scaffold(self.root).apply, plan, dest)
            except OSError as exc:
                await progress.line(f"✗ apply: {exc}")
                return False
            return True
        return await CommandRunner().run(list(argv), dest, progress.line) == 0

    ############################################################

    ##### PUBLIC #####

    def compose(self) -> ComposeResult:
        yield Footer()

    def on_mount(self) -> None:
        self.push_screen(self.screen_for(self.session.stage()))

    def action_step_back(self) -> None:
        if len(self.screen_stack) > 1:
            self.pop_screen()

    def save_draft(self) -> None:
        self.draft.save(self.session)

    def common(self) -> Survey | None:
        """The live survey of the chosen template's common tree — cached per template, re-read every app start."""
        template = str(self.session.template)
        if template not in self._surveys:
            self._surveys[template] = commands.survey(self.root, self.spec, template)
        return self._surveys[template]

    def survey(self) -> Survey:
        found = self.common()
        if found is None:
            msg = "the chosen template declares no common tree"
            raise ValueError(msg)
        return found

    def blueprint(self, name: str | None = None) -> Blueprint:
        return commands.blueprint(self.root, self.spec, str(self.session.template), name or str(self.session.name))

    def plan(self) -> Plan:
        """The preview of the whole session — pure until generate."""
        return self.blueprint().plan(frozenset(self.session.off), frozenset(self.session.drop))

    def begin_flow(self) -> None:
        """The step sequence of the chosen template: system, one panel per discovered area, then the fixed tail."""
        found = self.common()
        areas = () if found is None else tuple(f"common-{area}" for area in found.area_names())
        self.session.steps = (Step.SYSTEM, *areas, *TAIL)

    def screen_for(self, step: str) -> Screen:
        if step.startswith("common-"):
            return CommonAreaScreen(step.removeprefix("common-"))
        return SCREENS[step]()

    def advance(self, step: str) -> Screen:
        """The screen of the next step of the session's flow."""
        steps = self.session.steps or (Step.SYSTEM, *TAIL)
        return self.screen_for(steps[steps.index(step) + 1])

    def suggested(self) -> Path:
        """Default destination: sibling of the templates repository, named after the brand."""
        return self.root.parent / f"e-{self.session.name}"

    def check_target(self, dest: Path) -> None:
        if dest.exists() and any(dest.iterdir()):
            msg = f"destination {dest} already exists and is not empty"
            raise FileExistsError(msg)

    def verify_steps(self) -> list[tuple[str, tuple[str, ...]]]:
        """The template's declared verification, obeying the user's choice on unit tests."""
        template = self.spec.templates[str(self.session.template)]
        return [(v.name, v.argv) for v in template.verify if self.session.verify_tests or not v.tests]

    def start_generate(self, plan: Plan) -> None:
        self.plan_value = plan
        self.run_worker(self._pipeline(plan), exclusive=True, group="generate")
