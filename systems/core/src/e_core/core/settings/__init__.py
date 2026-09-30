"""Dynamic settings: discover every ``*Settings`` in this package and compose them into one ``Settings``.

Each subsystem keeps its own sources (``env_prefix``, ``config_file``, ``secrets_dir``), so adding a
scope is just dropping a file here — ``__init__`` and ``base`` are the only things skipped.
Consumers import the lazy singleton: ``from e_core.core.settings import settings as st`` → ``st.crypto.alg``
(env, secrets and ``.env`` are read on that first access, never at import)."""

import re
from typing import Any

import msgspec

from e_core.core.proxy import LazyProxy
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


### PEP 695 generic instead of `Self`: the loader is module-level, wired as `Settings.load` below — same contract as `Crypto.load`.
def _load[S](cls: type[S], **overrides: Any) -> S:
    """Build the composite by loading every subsystem from its own sources, then wiring the pieces."""
    parts = {scope: sub.load(**overrides.pop(scope, {})) for scope, sub in _SCOPES.items()}
    return cls(**parts, **overrides)


### the flat base loader cannot honour a per-subsystem config_file: each scope loads itself.
Settings.load = classmethod(_load)  # type: ignore[method-assign]
### no I/O at import: env, secrets and .env are read on the first attribute access, once per process.
settings: LazyProxy[Any] = LazyProxy(lambda: _load(Settings))
