"""tests/unit/e_management/ops/scan: the dynamic survey of the live common tree — what discovery finds, locks and cascades."""

from typing import TYPE_CHECKING

import pytest

from e_management.cli import commands

if TYPE_CHECKING:
    from pathlib import Path

    from e_management.models.manifest import Manifest


@pytest.fixture(scope="module")
def api_survey(repo: Path, spec: Manifest):
    found = commands.survey(repo, spec, "api")
    assert found is not None
    return found


def test_survey_discovers_the_three_areas_in_order(api_survey) -> None:
    assert api_survey.area_names() == ("adapters", "core", "ops")


def test_skip_hides_the_wizard_header_from_export(api_survey) -> None:
    assert "ops/tui" not in {u.key for u in api_survey.all_units()}
    assert "ops/file" in {u.key for u in api_survey.all_units()}


def test_each_free_unit_carries_its_test_mates(api_survey) -> None:
    units = {u.key: u for u in api_survey.all_units()}
    assert any("test_settings" in dest for _, dest in units["core/settings"].tests)
    assert any("test_sqlite" in dest for _, dest in units["adapters/sqlite"].tests)


def test_units_the_service_wires_are_locked(api_survey) -> None:
    for key in ("core/settings", "core/logger", "core/crypto", "adapters/redis", "adapters/sqlite"):
        assert key in api_survey.required, f"{key} should be pinned by e_api"


def test_dependents_graph_is_built_forward(api_survey) -> None:
    deps = dict(api_survey.dependents)
    assert "core/crypto" in deps["core/errors"]  # crypto imports errors → errors has crypto as a dependent
    assert "core/settings" in deps["core/errors"]


def test_dropping_a_locked_unit_is_refused(api_survey) -> None:
    with pytest.raises(ValueError, match="cannot be dropped"):
        api_survey.cascade(frozenset({"core/settings"}))


def test_strip_rules_map_the_package_prefix(api_survey) -> None:
    assert ("e_core.core", "core") in api_survey.strip()
    assert ("e_core.adapters", "adapters") in api_survey.strip()
