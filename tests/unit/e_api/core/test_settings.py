"""e_api.core.settings: layered config, frozen msgspec.Struct, C-pass conversion."""

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import msgspec
import pytest

from e_api.core.settings import BaseSettings, Secret


class DB(msgspec.Struct):
    host: str = "localhost"
    port: int = 5432


class Settings(BaseSettings, frozen=True):
    env_prefix = "E_"
    debug: bool = False
    port: int = 8000
    token: Secret = Secret("")
    db: DB = msgspec.field(default_factory=DB)


##### LOAD #####
async def test_load(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("E_PORT", "9000")
    monkeypatch.setenv("E_DEBUG", "true")
    monkeypatch.setenv("E_DB__PORT", "6543")
    settings = Settings.load()
    assert (settings.port, settings.debug, settings.db.port) == (9000, True, 6543)


async def test_load_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("E_PORT", "9000")
    assert Settings.load(port=7000).port == 7000


##### CONFIG FILES #####
async def test_load_config_toml(tmp_path: Path) -> None:
    path = tmp_path / "c.toml"
    path.write_text("[db]\nport = 1234\n")
    assert Settings.load_config(path) == {"db": {"port": 1234}}


async def test_load_config_json(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"port": 4321}))
    assert Settings.load_config(path) == {"port": 4321}


async def test_load_config_yaml(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text("port: 5000\ndb:\n  host: yhost\n")
    assert Settings.load_config(path) == {"port": 5000, "db": {"host": "yhost"}}


async def test_load_config_dotenv_fallback(tmp_path: Path) -> None:
    path = tmp_path / "c.conf"
    path.write_text("E_PORT=6000\n")
    assert Settings.load_config(path) == {"port": "6000"}


@pytest.mark.parametrize("suffix", [None, ".toml", ".conf"], ids=["none", "toml", "dotenv"])
async def test_load_config_missing(suffix: str | None, tmp_path: Path) -> None:
    path = None if suffix is None else tmp_path / f"absent{suffix}"
    assert Settings.load_config(path) == {}


##### DOTENV #####
async def test_load_dotenv() -> None:
    assert BaseSettings.load_dotenv("A=1\nexport B='two'\n# comment\njunk\n") == {"A": "1", "B": "two"}


async def test_load_dotenv_missing(tmp_path: Path) -> None:
    assert BaseSettings.load_dotenv(tmp_path / "absent") == {}


##### SECRETS #####
async def test_load_secrets(tmp_path: Path) -> None:
    (tmp_path / "E_TOKEN").write_text("s3cret\n")
    assert BaseSettings.load_secrets(tmp_path) == {"E_TOKEN": "s3cret"}


async def test_secret_never_leaks() -> None:
    secret = Secret("hunter2")
    assert "hunter2" not in repr(secret)
    assert "hunter2" not in f"{secret}"
    assert secret.reveal() == "hunter2"


##### NEST #####
async def test_nest() -> None:
    flat = {"PATH": "/usr/bin", "E_DB__HOST": "h", "E_PORT": "1"}
    assert Settings.nest(flat) == {"db": {"host": "h"}, "port": "1"}


##### COERCE #####
@pytest.mark.parametrize(
    ("value", "expected"),
    [('{"a": 1}', {"a": 1}), ('[1, "two"]', [1, "two"]), ("plain", "plain"), ("", "")],
    ids=["object", "array", "scalar", "empty"],
)
async def test_coerce(value: str, expected: object) -> None:
    assert BaseSettings.coerce(value) == expected


##### MERGE #####
async def test_merge_deep() -> None:
    base: dict[str, object] = {"db": {"host": "a", "port": 1}, "gone": True}
    assert BaseSettings.merge(base, {"db": {"port": 2}, "gone": False}) == {
        "db": {"host": "a", "port": 2},
        "gone": False,
    }


##### DECODE #####
async def test_decode_secret() -> None:
    assert Settings.decode(Secret, "x") == Secret("x")


async def test_decode_unsupported() -> None:
    with pytest.raises(NotImplementedError, match="Unsupported settings type"):
        Settings.decode(complex, 1)
