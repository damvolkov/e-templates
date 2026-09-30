"""tests/unit/e_management/__main__: the argparse surface — codes returned, reports rendered, nothing else."""

from typing import TYPE_CHECKING

from e_management.__main__ import main

if TYPE_CHECKING:
    from pathlib import Path


def test_main_plan_prints_the_actions(tmp_path: Path, capsys) -> None:
    assert main(["plan", "api", "myapp"]) == 0
    out = capsys.readouterr().out
    assert '"actions"' in out
    assert '"src": "systems/api"' in out


def test_main_gen_creates_and_reports_next(tmp_path: Path, capsys) -> None:
    dest = tmp_path / "e-myapp"
    assert main(["gen", "api", "myapp", "--dest", str(dest)]) == 0
    assert "make install" in capsys.readouterr().out
    assert (dest / "src" / "e_myapp" / "main.py").is_file()


def test_main_drift_is_in_sync(capsys) -> None:
    assert main(["drift"]) == 0
    assert "api: in sync" in capsys.readouterr().out
