"""tests/unit/e_management/core/test_common: exporting prunes free common units (and their tests), cascades, and refuses required ones — proved on a synthetic Survey so the mechanism is independent of what api happens to wire."""

import pytest

from e_management.core.blueprint import Blueprint
from e_management.core.plan import PrunePaths
from e_management.models.manifest import Common, Template
from e_management.ops.scan import Survey, Unit


def _survey() -> Survey:
    core = Unit(
        area="core",
        name="settings",
        package=False,
        source="systems/core/src/e_core/core/settings.py",
        tests=(("systems/core/tests/unit/e_core/core/test_settings.py", "tests/unit/core/test_settings.py"),),
    )
    extra = Unit(
        area="core",
        name="proxy",
        package=False,
        source="systems/core/src/e_core/core/proxy.py",
        tests=(("systems/core/tests/unit/e_core/core/test_proxy.py", "tests/unit/core/test_proxy.py"),),
    )
    return Survey(
        root="systems/core",
        package="e_core",
        areas=(("core", (core, extra)),),
        required=frozenset({"core/settings"}),
        dependents=(("core/settings", frozenset({"core/proxy"})), ("core/proxy", frozenset())),
    )


def _template() -> Template:
    return Template(
        source="systems/api", package="e_api", brand="e-api", common=Common(root="systems/core", package="e_core")
    )


def test_dropping_a_free_unit_prunes_it_and_its_test() -> None:
    plan = Blueprint(_template(), "demo", _survey()).plan(drop=frozenset({"core/proxy"}))
    pruned = next(a for a in plan.actions if isinstance(a, PrunePaths))
    assert "src/core/proxy.py" in pruned.paths
    assert "tests/unit/core/test_proxy.py" in pruned.paths
    assert "src/core/settings.py" not in pruned.paths


def test_dropping_a_required_unit_is_refused() -> None:
    with pytest.raises(ValueError, match="cannot be dropped"):
        Blueprint(_template(), "demo", _survey()).plan(drop=frozenset({"core/settings"}))


def test_empty_drop_adds_no_prune_action() -> None:
    plan = Blueprint(_template(), "demo", _survey()).plan()
    assert "PrunePaths" not in {type(a).__name__ for a in plan.actions}
