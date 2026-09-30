"""tests/unit/e_management/core/session: decisions accumulate, the dynamic stage follows the session's own steps."""

from msgspec import UNSET

from e_management.core.session import Session, Step


def test_session_stage_follows_the_default_order_without_steps() -> None:
    session = Session()
    assert session.stage() == Step.SYSTEM
    session.seen = (Step.SYSTEM,)
    assert session.stage() == "modules"


def test_session_stage_follows_dynamic_area_steps_when_present() -> None:
    session = Session(steps=("system", "common-adapters", "common-core", "common-ops", "modules", "options", "confirm"))
    session.seen = (Step.SYSTEM,)
    assert session.stage() == "common-adapters"
    session.seen = ("system", "common-adapters", "common-core")
    assert session.stage() == "common-ops"


def test_session_rests_on_confirm_when_every_step_seen() -> None:
    session = Session(
        steps=("system", "modules", "options", "confirm"), seen=("system", "modules", "options", "confirm")
    )
    assert session.stage() == "confirm"


def test_session_ready_only_with_mandatory_decisions() -> None:
    session = Session(template="api", name="myapp")
    assert session.ready is False
    assert session.dest is UNSET
    session.dest = "somewhere"
    assert session.ready is True


def test_session_defaults_all_common_units_on() -> None:
    session = Session()
    assert session.drop == ()
    assert session.verify_tests is True
