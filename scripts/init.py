#!/usr/bin/env python3
"""e-stack scaffold: rename this template to a new project, deterministically.

Reads the current project name from pyproject.toml, then rewrites every path
and text occurrence (dist name, module name, UPPER name, env_prefix) to the
target name, refreshes the lock, and syncs the env. Stdlib only: it must run
on a fresh clone, before any dependency exists.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

##### CONFIG #####
ROOT: Final[Path] = Path(__file__).resolve().parent.parent
SKIP_DIRS: Final[frozenset[str]] = frozenset(
    {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".benchmarks", ".mypy_cache", "site"}
)
STALE_DIRS: Final[tuple[str, ...]] = ("__pycache__", ".pytest_cache", ".ruff_cache", ".benchmarks")
NAME_RE: Final[re.Pattern[str]] = re.compile(r'(?m)^name\s*=\s*["\']([^"\']+)["\']')
PROHIBITED: Final[frozenset[str]] = frozenset(sys.stdlib_module_names)


##### HELPERS #####
def module_of(dist: str) -> str:
    return dist.replace("-", "_")


def prefix_of(dist: str) -> str:
    return dist.split("-", maxsplit=1)[0].upper() + "_"


def validate(raw: str) -> str:
    """Return the normalized dist name; fail if unusable as project name."""
    dist = re.sub(r"[\s_]+", "-", raw.strip().lower())
    bad = (not dist, not module_of(dist).isidentifier(), module_of(dist) in PROHIBITED)
    if any(bad):
        sys.exit(f"x invalid project name {raw!r}: needs a non-numeric, importable name (e.g. my-svc)")
    return dist


def purge_stale(top: Path) -> None:
    """Drop caches whose pickles still embed the old module name."""
    for path in sorted(top.rglob("*"), key=lambda p: -len(p.parts)):
        if path.name in STALE_DIRS and not any(part in SKIP_DIRS for part in path.relative_to(top).parts[:-1]):
            shutil.rmtree(path, ignore_errors=True)


def rename_paths(top: Path, cur: str, tar: str) -> list[str]:
    """Rename files and dirs bottom-up so parents stay valid while walking."""
    renamed = []
    for path in sorted(top.rglob("*"), key=lambda p: (-len(p.parts), str(p))):
        if path == top or any(part in SKIP_DIRS for part in path.parts):
            continue
        if (name := rename_item(path.name, cur, tar)) != path.name:
            path.rename(path.with_name(name))
            renamed.append(str(path.with_name(name).relative_to(top)))
    return renamed


def substitute(text: str, cur: str, tar: str) -> str:
    """Rewrite one text blob in a single regex pass (substitutions are never re-scanned).

    Ambiguity rule: when module == dist (single-token names), bare occurrences are
    the dist name; module occurrences are only those in structural contexts
    (imports, src paths, module-valued config keys, URLs). Multi-token names are
    unambiguous but flow through the same pass for uniformity.
    """
    cm, tm = module_of(cur), module_of(tar)
    cp, tp = prefix_of(cur), prefix_of(tar)
    e = re.escape
    pat = re.compile(
        rf"(?m)"
        rf'(?P<pfxp>env_prefix\s*=\s*")(?P<pfx>{e(cp)})'
        rf"|(?P<up>\b{e(cm.upper())}\b)"
        rf"|(?P<env>\b{e(cp)})(?=[A-Z0-9])"
        rf'|(?P<namep>name\s*=\s*")(?P<name>{e(cur)})'
        rf'|(?P<pathp>path\s*=\s*")(?P<path>{e(cm)})'
        rf"|(?P<urlp>https?://[^\s\"']*?/)(?P<url>\b{e(cur)}\b)"
        rf"|(?P<makep>MODULE\s*\?=\s*|PACKAGE\s*\?=\s*src/)(?P<make>{e(cm)})"
        rf'|(?P<listp>(?:known-first-party|source_pkgs)\s*=\s*\[")(?P<list>{e(cm)})'
        rf"|(?P<clip>-m |import\ )(?P<cli>{e(cm)}\b)"
        rf"|(?P<seg>\b{e(cm)})(?=[./])"
        rf'|(?<=[/"])(?P<tail>\b{e(cm)}\b)'
        rf"|(?P<rest>\b{e(cur)}\b)"
    )
    forms = {
        "pfx": tp,
        "up": tm.upper(),
        "env": tp,
        "name": tar,
        "path": tm,
        "url": tar,
        "make": tm,
        "list": tm,
        "cli": tm,
        "seg": tm,
        "tail": tm,
        "rest": tar,
    }
    pres = {
        "pfx": "pfxp",
        "name": "namep",
        "path": "pathp",
        "url": "urlp",
        "make": "makep",
        "list": "listp",
        "cli": "clip",
    }
    return pat.sub(lambda m: (m[pres[m.lastgroup]] if m.lastgroup in pres else "") + forms[m.lastgroup], text)


def rename_item(name: str, cur: str, tar: str) -> str:
    """New name for a path item: structural names are module form, UPPER is module form too."""
    cm, tm = module_of(cur), module_of(tar)
    return re.sub(
        rf"\b{re.escape(cm.upper())}\b|\b{re.escape(cm)}\b", lambda m: tm if m.group(0) == cm else tm.upper(), name
    )


def rewrite_contents(top: Path, cur: str, tar: str) -> list[str]:
    touched = []
    for path in sorted(top.rglob("*")):
        if path.is_dir() or any(part in SKIP_DIRS for part in path.relative_to(top).parts[:-1]):
            continue
        try:
            text = path.read_text("utf-8")
        except UnicodeDecodeError, OSError:
            continue
        new = substitute(text, cur, tar)
        if new != text:
            path.write_text(new, "utf-8")
            touched.append(str(path.relative_to(top)))
    return touched


##### MAIN #####
def main() -> None:
    raw = sys.argv[1] if len(sys.argv) > 1 else read_prompt()
    target = validate(raw)
    match = NAME_RE.search((ROOT / "pyproject.toml").read_text("utf-8"))
    if match is None:
        sys.exit("x no [project] name in pyproject.toml: run this from the template root")
    current = match.group(1)
    if current == target:
        sys.exit(f"x already named {current}")

    purge_stale(ROOT)
    renamed = rename_paths(ROOT, current, target)
    touched = rewrite_contents(ROOT, current, target)

    subprocess.run(["uv", "lock"], cwd=ROOT, check=True)
    subprocess.run(["uv", "sync"], cwd=ROOT, check=True)
    print(f"\nOK {current} -> {target}")
    print(f"   renamed: {', '.join(renamed)}")
    print(f"   rewritten: {', '.join(touched)}")
    print(f"   ready: make check | make run -> python -m {module_of(target)}")


def read_prompt() -> str:
    try:
        return input("Project name? ")
    except EOFError:
        sys.exit("x no name given: make init <name>")


if __name__ == "__main__":
    main()
