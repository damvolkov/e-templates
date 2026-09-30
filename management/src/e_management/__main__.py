"""python -m e_management: the tool's entry — no arguments opens the Textual wizard; the subcommands keep the headless surface."""

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import msgspec

from e_management.cli import commands
from e_management.ui.app import ManagementApp

if TYPE_CHECKING:
    from collections.abc import Sequence

##### DEFAULTS #####
MANAGEMENT = Path(__file__).resolve().parents[2]
REPO = MANAGEMENT.parent


def _off(pieces: str) -> frozenset[str]:
    return frozenset(name for name in pieces.split(",") if name)


def _run(args: argparse.Namespace) -> int:
    spec = commands.registry(args.manifest)
    match args.command:
        case "ui":
            ManagementApp(spec, args.root, MANAGEMENT / "data" / "draft.json").run()
        case "plan":
            actions = commands.plan(args.root, spec, args.template, args.name, off=_off(args.off), drop=_off(args.drop))
            print(json.dumps(msgspec.to_builtins(actions), indent=2))
        case "gen":
            dest = commands.gen(
                args.root, spec, args.template, args.name, args.dest.resolve(), off=_off(args.off), drop=_off(args.drop)
            )
            print(f"created {dest}\nnext: cd {dest} && make install")
        case "drift":
            report = commands.drift(args.root, spec)
            for name, issues in report.items():
                print(f"{name}: {'in sync' if not issues else chr(10).join('  ' + i for i in issues)}")
            return int(any(report.values()))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="e_management", description="e-templates boilerplate manager")
    parser.add_argument("--root", type=Path, default=REPO, help="repository root the registry paths hang from")
    parser.add_argument("--manifest", type=Path, default=MANAGEMENT / "data" / "templates.yml")
    subs = parser.add_subparsers(dest="command")
    subs.add_parser("ui")
    for name in ("plan", "gen"):
        sub = subs.add_parser(name)
        sub.add_argument("template")
        sub.add_argument("name")
        sub.add_argument("--off", default="", help="comma-separated choices to drop")
        sub.add_argument("--drop", default="", help="comma-separated common units to drop (area/unit)")
        if name == "gen":
            sub.add_argument("--dest", type=Path, required=True)
    subs.add_parser("drift")
    args = parser.parse_args(list(argv) if argv is not None else None)
    args.command = args.command or "ui"
    return _run(args)


if __name__ == "__main__":
    sys.exit(main())
