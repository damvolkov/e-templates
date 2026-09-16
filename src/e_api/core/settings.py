"""e-stack settings: typed, frozen, layered config on msgspec (C-backed, zero deps)."""

import os
import tomllib
from collections.abc import Mapping
from functools import reduce
from pathlib import Path
from typing import Any, ClassVar, Self

import msgspec

##### DEFAULTS #####
REDACTION: str = "**********"
JSON_MARKERS: frozenset[str] = frozenset({"[", "{"})  # env values starting with these decode as JSON
DOTENV_EXPORT: str = "export "
DOTENV_COMMENT: str = "#"
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


##### BASE #####
class BaseSettings(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=False):
    """Subclass and declare typed fields, repeating `frozen=True`. Precedence: kwargs > env > .env > secrets > config file > defaults."""

    env_prefix: ClassVar[str] = ""
    nested_delimiter: ClassVar[str] = "__"  # E_DB__PORT -> db.port
    env_file: ClassVar[Path] = Path(".env")
    config_file: ClassVar[Path | None] = None  # .toml / .json / .yaml / .env, picked from the suffix
    secrets_dir: ClassVar[Path] = Path("/run/secrets")

    @classmethod
    def load(cls, **overrides: Any) -> Self:
        """Build the instance: merge every source lowest-to-highest, then bulk-convert in one C pass."""
        layers = (  # lowest to highest priority
            cls.load_config(cls.config_file),
            cls.nest(cls.load_secrets(cls.secrets_dir)),
            cls.nest(cls.load_dotenv(cls.env_file)),
            cls.nest(os.environ),
            overrides,
        )
        merged = reduce(cls.merge, layers, {})
        return msgspec.convert(merged, cls, strict=False, dec_hook=cls.decode)  # "8080" -> int, "true" -> bool

    @classmethod
    def load_config(cls, path: Path | None) -> dict[str, Any]:
        """Parse a config file, format chosen on the fly from its suffix. Missing -> {}."""
        match path:
            case None:
                return {}
            case Path() if not path.is_file():
                return {}
            case Path(suffix=ext) if ext.lower() == ".toml":
                return tomllib.loads(path.read_text())
            case Path(suffix=ext) if ext.lower() == ".json":
                return msgspec.json.decode(path.read_bytes())
            case Path(suffix=ext) if ext.lower() in {".yaml", ".yml"}:
                import yaml  # noqa: PLC0415 -- optional dep, paid only by yaml users

                loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)  # C loader: ~10x the pure-Python one
                return yaml.load(path.read_bytes(), loader)  # noqa: S506 -- safe by construction
            case Path():
                return cls.nest(cls.load_dotenv(path))

    @classmethod
    def load_dotenv(cls, source: Path | str) -> dict[str, str]:
        """Parse dotenv text or file (missing file -> {}), `export`-tolerant."""
        match source:
            case Path() if not source.is_file():
                return {}
            case Path():
                source = source.read_text()
            case _:
                pass
        pairs: dict[str, str] = {}
        for raw in source.splitlines():
            match raw.strip().removeprefix(DOTENV_EXPORT).partition("="):
                case (key, "=", value) if key and not key.startswith(DOTENV_COMMENT):
                    pairs[key.strip()] = value.strip().strip(DOTENV_QUOTES)
                case _:
                    pass
        return pairs

    @classmethod
    def load_secrets(cls, directory: Path) -> dict[str, str]:
        """Docker/K8s secrets mount: {filename: value}. glob() on a missing dir yields nothing."""
        return {file.name: file.read_text().strip() for file in directory.glob("*") if file.is_file()}

    @classmethod
    def nest(cls, flat: Mapping[str, str]) -> dict[str, Any]:
        """`{"E_DB__PORT": "1"}` -> `{"db": {"port": "1"}}`, case-insensitive, prefix-filtered."""
        root: dict[str, Any] = {}
        prefix_lower = cls.env_prefix.lower()
        for key, value in flat.items():
            match key.lower():
                case name if name.startswith(prefix_lower):
                    *parents, leaf = name.removeprefix(prefix_lower).split(cls.nested_delimiter)
                    reduce(lambda node, part: node.setdefault(part, {}), parents, root)[leaf] = cls.coerce(value)
                case _:  # foreign variables are ignored
                    pass
        return root

    @staticmethod
    def coerce(value: str) -> Any:
        """Lists/dicts arrive as JSON strings; scalars stay str, msgspec converts them in non-strict mode."""
        match value[:1]:
            case marker if marker in JSON_MARKERS:
                return msgspec.json.decode(value)
            case _:
                return value

    @staticmethod
    def merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
        """Deep merge: nested tables merge key by key, anything else is replaced."""
        for key, value in override.items():
            match (base.get(key), value):
                case (dict() as current, Mapping()):
                    BaseSettings.merge(current, value)
                case _:
                    base[key] = value
        return base

    @staticmethod
    def decode(tp: type, obj: Any) -> Any:
        """msgspec dec_hook: build the types the C decoder cannot construct itself."""
        match tp:
            case type() if issubclass(tp, Secret):
                return tp(obj)
            case _:
                msg = f"Unsupported settings type: {tp!r}"
                raise NotImplementedError(msg)
