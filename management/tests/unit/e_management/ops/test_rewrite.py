"""tests/unit/e_management/ops/rewrite: the guard is the whole point — a rename must never eat a substring."""

from e_management.models.manifest import Strip
from e_management.ops.rewrite import rewrite_segment, rewrite_text

RULES = (Strip(frm="e_app", to="e_api"), Strip(frm="e-app", to="e-api"))


def test_rewrite_text_renames_whole_words() -> None:
    assert rewrite_text("from e_app.main import x", RULES) == "from e_api.main import x"
    assert rewrite_text('"e-app"', RULES) == '"e-api"'
    assert rewrite_text("e_app", RULES) == "e_api"


def test_rewrite_text_keeps_substring_identifiers() -> None:
    for untouched in ("create_app", "not_the_app", "evolve_applies", "granian", "the_app"):
        assert rewrite_text(untouched, RULES) == untouched


def test_segment_renames_only_whole_segment_words() -> None:
    assert rewrite_segment("e_app", RULES) == "e_api"
    assert rewrite_segment("test_stress.py", RULES) == "test_stress.py"
