"""Auto-discoverable settings submodule: the HTTP edge of this app — ALLOW_ORIGINS, ALLOW_METHODS."""

import msgspec

from e_core.core.settings.base import BaseSettings

DEFAULT_ORIGINS: list[str] = ["*"]
DEFAULT_METHODS: list[str] = ["GET", "POST", "PATCH", "DELETE"]


class ApiSettings(BaseSettings, frozen=True):
    """ALLOW_ORIGINS / ALLOW_METHODS — JSON lists via env or config file."""

    allow_origins: list[str] = msgspec.field(default_factory=lambda: list(DEFAULT_ORIGINS))
    allow_methods: list[str] = msgspec.field(default_factory=lambda: list(DEFAULT_METHODS))
