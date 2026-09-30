"""tests/unit/e_management/adapters/scaffold: the executor against the real api template — every choice must leave a project that parses and references nothing deleted."""

import ast
import re
from typing import TYPE_CHECKING

import pytest

from e_management.adapters.scaffold import Scaffold
from e_management.cli import commands

if TYPE_CHECKING:
    from pathlib import Path

    from e_management.models.manifest import Manifest

GUARDS = (re.compile(r"(?<!\w)e_api(?!\w)"), re.compile(r"(?<!\w)e-app(?!\w)"))

CASES = [
    ("websockets", "src/e_myapp/websockets", "telemetry"),
    ("docker", "Dockerfile", "docker"),
    ("docs", "properdocs.yml", "docs"),
]


def texts(tree: Path) -> list[Path]:
    return [p for p in tree.rglob("*") if p.is_file() and ".venv" not in p.parts and _decodable(p)]


def _decodable(p: Path) -> bool:
    try:
        p.read_text()
    except SyntaxError, UnicodeDecodeError:
        return False
    return True


def generate(repo: Path, spec: Manifest, off: frozenset[str], dest: Path) -> Path:
    return commands.gen(repo, spec, "api", "myapp", dest, off=off)


def assert_parses(dest: Path) -> None:
    for path in dest.rglob("*.py"):
        ast.parse(path.read_text(), filename=str(path))


def test_scaffold_gen_full_tree_is_clean_and_materialized(tmp_path: Path, repo: Path, spec: Manifest) -> None:
    dest = generate(repo, spec, frozenset(), tmp_path / "e-myapp")
    assert (dest / "src" / "e_myapp" / "main.py").is_file()
    assert (dest / "src" / "core" / "settings" / "__init__.py").is_file()
    assert not (dest / "uv.lock").exists()
    assert not (dest / "src" / "ops" / "tui.py").exists()
    leftovers = {str(p.relative_to(dest)) for p in texts(dest) for guard in GUARDS if guard.search(p.read_text())}
    assert not leftovers, f"unrenamed sources: {sorted(leftovers)}"
    assert_parses(dest)


def test_scaffold_finalizes_tooling_files(tmp_path: Path, repo: Path, spec: Manifest) -> None:
    dest = generate(repo, spec, frozenset(), tmp_path / "e-myapp")
    makefile = (dest / "Makefile").read_text()
    assert "# — common —" not in makefile
    assert "core-check" not in makefile
    assert "CORE_SRC" not in makefile
    assert "check: lint type arch validate test" in makefile
    gitignore = (dest / ".gitignore").read_text()
    assert ".venv/" in gitignore
    assert "src/core/" not in gitignore
    assert "shared core materialized from systems/core" not in (dest / "pyproject.toml").read_text()


@pytest.mark.parametrize(("off_name", "gone", "kept"), CASES)
def test_scaffold_drops_each_choice(
    tmp_path: Path, repo: Path, spec: Manifest, off_name: str, gone: str, kept: str
) -> None:
    dest = generate(repo, spec, frozenset({off_name}), tmp_path / "e-myapp")
    assert not (dest / gone).exists()
    assert_parses(dest)
    _assert_wiring_gone(dest, off_name, kept)


def _assert_wiring_gone(dest: Path, off_name: str, kept: str) -> None:
    match off_name:
        case "websockets":
            assert kept not in (dest / "src" / "e_myapp" / "main.py").read_text()
            assert kept not in (dest / "tach.toml").read_text()
        case "docs":
            assert "docs-build" not in (dest / "Makefile").read_text()
            assert "DOCS_DEPLOY" not in (dest / ".github/ci.vars.example").read_text()
        case "docker":
            assert "PUBLISH_IMAGE" not in (dest / ".github/ci.vars.example").read_text()
            assert "image:" not in (dest / ".github/workflows/release.yml").read_text()


def test_scaffold_all_choices_off_keeps_every_mandatory_test(tmp_path: Path, repo: Path, spec: Manifest) -> None:
    off = frozenset(c.name for c in spec.templates["api"].choices)
    dest = generate(repo, spec, off, tmp_path / "e-myapp")
    assert_parses(dest)
    for mandatory in spec.templates["api"].mandatory:
        assert (dest / mandatory.replace("e_api", "e_myapp")).exists()


def test_scaffold_apply_refuses_existing_destination(tmp_path: Path, repo: Path, spec: Manifest) -> None:
    (tmp_path / "e-myapp").mkdir()
    with pytest.raises(FileExistsError):
        generate(repo, spec, frozenset(), tmp_path / "e-myapp")


def test_scaffold_drift_reports_in_sync_for_the_real_systems(repo: Path, spec: Manifest) -> None:
    assert Scaffold(repo).drift(spec.templates["api"]) == []
