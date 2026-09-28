"""Dynamic settings: discover every ``*Settings`` in this package and compose them into one ``Settings``.

Each subsystem keeps its own sources (``env_prefix``, ``config_file``, ``secrets_dir``), so adding a
scope is just dropping a file here — ``__init__`` and ``base`` are the only things skipped.
Consumers import the loaded singleton: ``from e_core.core.settings import settings as st`` → ``st.crypto.alg``."""

import re
from typing import Any

import msgspec

from e_core.core.settings.base import (
    DOTENV,
    DOTENV_QUOTES,
    JSON_MARKERS,
    REDACTION,
    BaseSettings,
    Secret,
    SettingsLoadError,
)
from e_core.ops.file import FileFinder

__all__ = [
    "DOTENV",
    "DOTENV_QUOTES",
    "JSON_MARKERS",
    "REDACTION",
    "BaseSettings",
    "Secret",
    "Settings",
    "SettingsLoadError",
    "settings",
]

_SETTINGS_RE = re.compile(r"^([A-Z]\w*)Settings$")
_SCOPES: dict[str, type[BaseSettings]] = {
    name.removesuffix("Settings").lower(): cls
    for name, cls in FileFinder(__name__, skip=frozenset({"base"})).discover(BaseSettings, pattern=_SETTINGS_RE).items()
}


##### COMPOSITE #####
Settings: Any = msgspec.defstruct(
    "Settings",
    list(_SCOPES.items()),
    bases=(BaseSettings,),
    frozen=True,
    kw_only=True,
)


def _load(cls: type, **overrides: dict[str, Any]) -> Any:
    """Build the composite by loading every subsystem from its own sources, then wiring the pieces."""
    parts = {scope: sub.load(**overrides.pop(scope, {})) for scope, sub in _SCOPES.items()}
    return cls(**parts, **overrides)


### the flat base loader cannot honour a per-subsystem config_file: each scope loads itself.
Settings.load = classmethod(_load)  # type: ignore[method-assign]
settings: Any = _load(Settings)
