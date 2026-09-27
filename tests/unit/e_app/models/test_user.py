"""tests/unit: the User DTO family — validation at the edge, UNSET semantics, credential redaction."""

from datetime import date
from decimal import Decimal
from uuid import UUID

import msgspec
import pytest

from e_app.models.user import Password, User, UserCreate, UserRecord, UserUpdate


def sample_create(**overrides) -> UserCreate:
    payload = {"username": "alice", "email": "alice@example.com", "password": "correct-horse-1"}
    return msgspec.convert({**payload, **overrides}, UserCreate, strict=False)


def test_valid_payload_keeps_exact_decimal() -> None:
    created = sample_create(quota="0.10")
    assert created.quota == Decimal("0.10")
    assert isinstance(created.password, Password)


@pytest.mark.parametrize(
    "field",
    [
        {"username": "AB"},
        {"username": "1alice"},
        {"email": "not-an-email"},
        {"password": "short1"},
        {"quota": "-1"},
        {"surprise": "field"},
    ],
)
def test_rejects_at_the_edge(field: dict) -> None:
    with pytest.raises(msgspec.ValidationError):
        sample_create(**field)


def test_password_never_leaks_but_stays_usable() -> None:
    password = Password("correct-horse-1")
    assert repr(password) == "Password('**********')"
    assert f"{password}" == "Password('**********')"
    assert msgspec.json.encode(password) == b'"correct-horse-1"'


def test_read_model_has_no_credential_surface() -> None:
    field_names = {f.name for f in msgspec.structs.fields(User)}
    assert "password" not in field_names and "password_hash" not in field_names


def test_update_sentinel_distinguishes_absent_from_null() -> None:
    patch = msgspec.convert({"birth": None}, UserUpdate, strict=False)
    assert patch.birth is None
    assert patch.email is msgspec.UNSET
    assert patch.quota is msgspec.UNSET


def test_evolve_applies_only_sentinel_changes() -> None:
    record = UserRecord(
        id="0" * 32,
        username="alice",
        email="alice@example.com",
        password_hash="$argon2id$v=hash",
        birth=date(1990, 1, 1),
        quota=Decimal("0"),
    )
    patch = msgspec.convert({"email": "new@example.com", "birth": None}, UserUpdate, strict=False)
    changes = {f.name: v for f in msgspec.structs.fields(patch) if (v := getattr(patch, f.name)) is not msgspec.UNSET}
    updated = msgspec.evolve(record, **changes)
    assert updated.email == "new@example.com"
    assert updated.birth is None
    assert updated.password_hash == record.password_hash
