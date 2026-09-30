"""tests/unit/e_management: the real repository and its real registry — the engine is tested against what it must produce."""

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from e_management.adapters.manifest import ManifestReader

if TYPE_CHECKING:
    from e_management.models.manifest import Manifest


def _find_repo(start: Path) -> Path:
    return next(p for p in start.parents if (p / "systems" / "api" / "pyproject.toml").exists())


@pytest.fixture(scope="session")
def repo() -> Path:
    return _find_repo(Path(__file__).resolve())


@pytest.fixture(scope="session")
def spec(repo: Path) -> Manifest:
    return ManifestReader(repo / "management" / "data" / "templates.yml").load()
