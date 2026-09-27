"""models/user: the User DTO family — msgspec contracts for the API edge.

Write model (`UserCreate`) and read model (`User`) are separate structs by construction: the password
and its hash physically do not exist on `User`, so no serializer can leak them. `UserUpdate` uses the
`UNSET` sentinel to tell "field absent" from "field null".
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

import msgspec

##### CONSTANTS #####
REDACTED: str = "**********"
USERNAME_PATTERN: str = r"^[a-z][a-z0-9_]{2,31}$"
EMAIL_PATTERN: str = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
PASSWORD_MIN: int = 12


##### TYPES #####
class Password(str):
    """Password text that never leaks through repr/str/f-strings; the value is still `str(self)`-intact upstream."""

    __slots__ = ()

    def __repr__(self) -> str:
        return f"Password('{REDACTED}')"

    __str__ = __repr__


##### DTOs #####
class UserCreate(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """Inbound registration payload."""

    username: Annotated[str, msgspec.Meta(pattern=USERNAME_PATTERN)]
    email: Annotated[str, msgspec.Meta(max_length=254, pattern=EMAIL_PATTERN)]
    password: Annotated[Password, msgspec.Meta(min_length=PASSWORD_MIN)]
    birth: date | None = None
    quota: Annotated[Decimal, msgspec.Meta(ge=0)] = Decimal("0")


class User(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True):
    """Outbound read model — no credential field exists here."""

    id: UUID
    username: str
    email: str
    birth: date | None = None
    quota: Decimal = Decimal("0")
    created: datetime


class UserUpdate(msgspec.Struct, frozen=True, kw_only=True):
    """Partial mutation: UNSET means "not sent", None means "set to null"."""

    email: msgspec.UnsetType | Annotated[str, msgspec.Meta(max_length=254, pattern=EMAIL_PATTERN)] = msgspec.UNSET
    birth: msgspec.UnsetType | date | None = msgspec.UNSET
    quota: msgspec.UnsetType | Annotated[Decimal, msgspec.Meta(ge=0)] = msgspec.UNSET


class UserRecord(msgspec.Struct, frozen=True, kw_only=True):
    """Storage model — the only type that carries `password_hash`; it never crosses the API boundary."""

    id: UUID
    username: str
    email: str
    password_hash: str
    birth: date | None = None
    quota: Decimal = Decimal("0")
    created: datetime
