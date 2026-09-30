"""e-core settings base: frozen, typed, layered config — msgspec schema, e-serde codecs (Rust).

This module is the foundation of the dynamic settings composer in this package. It provides BaseSettings,
Secret, dotenv parsing, and the reader that feeds every layer. All sub-settings inherit from here."""

import os
import re
from collections.abc import Mapping
from functools import reduce
from pathlib import Path, PurePath
from typing import Any, ClassVar, Self

import eserde
import msgspec

from e_core.core.errors import SettingsLoadError

##### DEFAULTS #####
REDACTION: str = "**********"
JSON_MARKERS: frozenset[str] = frozenset({"[", "{"})  # env values starting like JSON are decoded before nesting
DOTENV: re.Pattern[str] = re.compile(r"\s*(?:export\s+)?([^\s=#]+)\s*=\s*(.*)")
DOTENV_QUOTES: str = "\"'"


##### TYPES #####
class Secret(str):
    """String that never leaks through repr/str/f-strings/logs; use `.reveal()` to read it."""

    __slots__ = ()

    def __repr__(self) -> str:
        return f"Secret('{REDACTION}')"

    __str__ = __repr__

    def reveal(self) -> str:
        return str.__str__(self)


class BaseSettings(msgspec.Struct, frozen=True, kw_only=True):
    """Subclass and declare typed fields. One reader feeds every layer.

    Precedence, lowest first: config file < secrets < .env < environment < kwargs.
    e-serde opens any config file by suffix; unknown suffixes read as dotenv.
    Subclasses add their own fields and receive a shared ``load()`` that merges layers once.
    """

    env_prefix: ClassVar[str] = ""
    nested_delimiter: ClassVar[str] = "__"  # E_DB__PORT -> db.port
    env_file: ClassVar[Path] = Path(".env")
    config_file: ClassVar[Path | None] = None
    secrets_dir: ClassVar[Path] = Path("/run/secrets")

    @classmethod
    def load(cls, **overrides: Any) -> Self:
        """Merge the five layers and build the model in one non-strict msgspec pass ("8080" → 8080)."""
        layers = (
            cls.read(cls.config_file),
            cls.read(cls.secrets_dir),
            cls.read(cls.env_file),
            cls.read(os.environ),
            overrides,
        )
        return msgspec.convert(reduce(cls.merge, layers, {}), cls, strict=False, dec_hook=cls.decode)

    @classmethod
    def read(cls, source: Path | Mapping[str, str] | None) -> dict[str, Any]:
        """One layer as a nested dict: file → e-serde (dotenv fallback on unknown suffix,
        SettingsLoadError on corrupt); directory → one secret per file; mapping → raw pairs; missing → {}."""
        match source:
            case None:
                return {}
            case Mapping():
                return cls.nest(source)
            case Path() if not source.exists():
                return {}
            case Path() if source.is_dir():
                return cls.nest({file.name: file.read_text().strip() for file in source.glob("*") if file.is_file()})
            case Path():
                try:
                    return eserde.loads(source)
                except eserde.FormatError:
                    return cls.nest(cls.dotenv(source))
                except eserde.LoadError as exc:
                    msg = f"Cannot decode config file: {source}"
                    raise SettingsLoadError(msg, source=source) from exc
            case unknown:
                msg = f"Unsupported settings source: {unknown!r}"
                raise TypeError(msg)

    @classmethod
    def dotenv(cls, path: Path) -> dict[str, str]:
        """`KEY=value` lines, export-tolerant, comments and junk dropped."""
        return {
            key: value.strip(DOTENV_QUOTES)
            for line in path.read_text().splitlines()
            if (match := DOTENV.match(line))
            for key, value in [match.groups()]
        }

    @classmethod
    def nest(cls, pairs: Mapping[str, str]) -> dict[str, Any]:
        """`{"E_DB__PORT": "1"}` → `{"db": {"port": "1"}}`: prefix-filtered,
        case-insensitive, JSON-looking values decoded."""

        def _dig(node: dict[str, Any], part: str) -> dict[str, Any]:
            """The child dict for `part` under `node`, created and empty on first touch."""
            return node.setdefault(part, {})

        prefix = cls.env_prefix.lower()
        root: dict[str, Any] = {}
        for key, raw in pairs.items():
            if (name := key.lower()).startswith(prefix):
                value = msgspec.json.decode(raw) if raw[:1] in JSON_MARKERS else raw
                *parents, leaf = name.removeprefix(prefix).split(cls.nested_delimiter)
                reduce(_dig, parents, root)[leaf] = value
        return root

    @staticmethod
    def merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
        """Deep merge, lowest layer first: nested dicts fuse key by key, anything else is replaced."""
        for key, value in override.items():
            match (base.get(key), value):
                case (dict() as sub_base, Mapping() as sub_override):
                    BaseSettings.merge(sub_base, sub_override)
                case _:
                    base[key] = value
        return base

    @staticmethod
    def decode(tp: type, obj: Any) -> Any:
        """msgspec dec_hook: the types the C decoder cannot build itself — `Secret` and path-like."""
        match tp:
            case type() if issubclass(tp, Secret):
                return tp(obj)
            case type() if issubclass(tp, PurePath):
                return tp(obj)
            case _:
                msg = f"Unsupported settings type: {tp!r}"
                raise NotImplementedError(msg)
