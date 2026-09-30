"""core.session: the wizard's accumulated decisions as one typed value — nothing touches the filesystem until the plan runs."""

from pathlib import Path

from msgspec import UNSET, Struct, UnsetType


##### TYPES #####
class Step:
    """The wizard's stages, in order: pick a system, shape its modules, its infra and its CI, confirm."""

    SYSTEM = "system"
    MODULES = "modules"
    OPTIONS = "options"
    CONFIRM = "confirm"
    ORDER: tuple[str, ...] = (SYSTEM, MODULES, OPTIONS, CONFIRM)


class Session(Struct, kw_only=True):
    """Every decision made so far. Mutable on purpose: screens fill it stage by stage; back never erases what still holds."""

    template: str | UnsetType = UNSET
    name: str | UnsetType = UNSET
    off: tuple[str, ...] = ()
    drop: tuple[str, ...] = ()
    steps: tuple[str, ...] = ()
    dest: str | UnsetType = UNSET
    seen: tuple[str, ...] = ()
    verify_tests: bool = True

    @property
    def ready(self) -> bool:
        """All mandatory decisions are taken: the plan can be previewed and applied."""
        return not (self.template is UNSET or self.name is UNSET or self.dest is UNSET)

    def stage(self) -> str:
        """The next unconfirmed stage of this session's own flow (dynamic areas included)."""
        flow = self.steps or Step.ORDER
        return next((step for step in flow if step not in self.seen), flow[-1])

    def target(self) -> Path:
        return Path(str(self.dest))
