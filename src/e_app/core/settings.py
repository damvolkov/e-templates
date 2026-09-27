"""e-stack settings: frozen, typed, layered config — msgspec schema, e-serde file codecs (Rust)."""

import os
import re
from collections.abc import Mapping
from functools import reduce
from pathlib import Path
from typing import Any, ClassVar, Self

import eserde
import msgspec

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


class SettingsLoadError(RuntimeError):
    """A config file exists but cannot be decoded: its suffix promises a format and the bytes break it."""


##### BASE #####
class BaseSettings(msgspec.Struct, frozen=True, kw_only=True):
    """Subclass and declare typed fields. One reader feeds every layer.

    Precedence, lowest first: config file < secrets < .env < environment < kwargs.
    e-serde opens any config file by suffix; unknown suffixes read as dotenv.
    """

    env_prefix: ClassVar[str] = ""
    nested_delimiter: ClassVar[str] = "__"  # E_DB__PORT -> db.port
    env_file: ClassVar[Path] = Path(".env")
    config_file: ClassVar[Path | None] = None
    secrets_dir: ClassVar[Path] = Path("/run/secrets")

    @classmethod
    def load(cls, **overrides: Any) -> Self:
        """Merge the five layers and build the model in one non-strict msgspec pass ("8080" -> 8080)."""
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
        """One layer as a nested dict: file -> e-serde (dotenv fallback on unknown suffix, SettingsLoadError on corrupt); directory -> one secret per file; mapping -> raw pairs; missing -> {}."""
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
                    raise SettingsLoadError(msg) from exc
            case unknown:
                msg = f"Unsupported settings source: {unknown!r}"
                raise TypeError(msg)

    @classmethod
    def dotenv(cls, path: Path) -> dict[str, str]:
        """`KEY=value` lines, `export`-tolerant, comments and junk dropped."""
        return {
            key: value.strip(DOTENV_QUOTES)
            for line in path.read_text().splitlines()
            if (match := DOTENV.match(line))
            for key, value in [match.groups()]
        }

    @classmethod
    def nest(cls, pairs: Mapping[str, str]) -> dict[str, Any]:
        """`{"E_DB__PORT": "1"}` -> `{"db": {"port": "1"}}`: prefix-filtered, case-insensitive, JSON-looking values decoded."""
        prefix = cls.env_prefix.lower()
        root: dict[str, Any] = {}
        for key, raw in pairs.items():
            if (name := key.lower()).startswith(prefix):
                value = msgspec.json.decode(raw) if raw[:1] in JSON_MARKERS else raw
                *parents, leaf = name.removeprefix(prefix).split(cls.nested_delimiter)
                reduce(lambda node, part: node.setdefault(part, {}), parents, root)[leaf] = value
        return root

    @staticmethod
    def merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
        """Deep merge, lowest layer first: nested dicts fuse key by key, anything else is replaced."""
        for key, value in override.items():
            if isinstance(base.get(key), dict) and isinstance(value, Mapping):
                BaseSettings.merge(base[key], value)
            else:
                base[key] = value
        return base

    @staticmethod
    def decode(tp: type, obj: Any) -> Any:
        """msgspec dec_hook: the types the C decoder cannot build itself — currently only `Secret`."""
        if isinstance(tp, type) and issubclass(tp, Secret):
            return tp(obj)
        msg = f"Unsupported settings type: {tp!r}"
        raise NotImplementedError(msg)


##### APP #####
class Settings(BaseSettings, frozen=True):
    """Process-level knobs for the runner and the logger (APP__ENV, APP__HOST, APP__PORT)."""

    env_prefix: ClassVar[str] = "APP__"
    env: str = "dev"
    host: str = "127.0.0.1"
    port: int = 8000
