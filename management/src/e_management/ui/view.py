"""ui.view: pure renderers — a Plan or a step log becomes text the screens show, nothing else."""

from typing import TYPE_CHECKING

from e_management.core.plan import Action, Copy, Materialize, PrunePaths, PruneTexts, Rename

if TYPE_CHECKING:
    from e_management.core.plan import Plan

##### DEFAULTS #####
TITLE: dict[str, str] = {
    "Copy": "copy template",
    "Materialize": "materialize",
    "PrunePaths": "remove paths",
    "PruneTexts": "rewrite files",
    "Rename": "rename",
}


def render_plan(plan: Plan) -> str:
    """One line per action: what the engine will do when the user confirms."""
    lines = [f"project   {plan.brand}   ·   package {plan.package}", "", "the engine will, in order:"]
    lines += [f"  · {line}" for line in (_line(action) for action in plan.actions)]
    return "\n".join(lines)


def _line(action: Action) -> str:
    match action:
        case Copy(src=src):
            return f"{TITLE['Copy']}  {src}"
        case Materialize(src=src, dst=dst):
            return f"{TITLE['Materialize']}  {src} → {dst}"
        case PrunePaths(paths=paths):
            return f"{TITLE['PrunePaths']}  {', '.join(paths)}"
        case PruneTexts(prunes=prunes):
            files = sorted({prune.file for prune in prunes})
            return f"{TITLE['PruneTexts']}  {len(prunes)} rules over {', '.join(files)}"
        case Rename(rules=rules):
            return f"{TITLE['Rename']}  " + ", ".join(f"{rule.frm} → {rule.to}" for rule in rules)
