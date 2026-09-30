"""tests/unit/e_management/adapters/runner: the subprocess port — every line streamed, the exit code answered."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from e_management.adapters.runner import CommandRunner


async def test_runner_streams_output_and_returns_zero(tmp_path: Path) -> None:
    lines: list[str] = []

    async def emit(line: str) -> None:
        lines.append(line)

    code = await CommandRunner().run(["sh", "-c", "echo first; echo second"], tmp_path, emit)
    assert code == 0
    assert lines == ["first", "second"]


async def test_runner_answers_the_failure_code(tmp_path: Path) -> None:
    async def quiet(_line: str) -> None:
        return None

    code = await CommandRunner().run(["sh", "-c", "exit 3"], tmp_path, quiet)
    assert code == 3
