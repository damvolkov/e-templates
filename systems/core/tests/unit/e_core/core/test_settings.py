"""e_core.core.settings: one reader for five layers, frozen msgspec.Struct, e-serde codecs."""

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from pathlib import Path

import msgspec
import pytest

from e_core.core.errors import SettingsLoadError
from e_core.core.settings import BaseSettings, Secret


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
async def test_load_env_layers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("E_PORT", "9000")
    monkeypatch.setenv("E_DEBUG", "true")
    monkeypatch.setenv("E_DB__PORT", "6543")
    settings = Settings.load()
    assert (settings.port, settings.debug, settings.db.port) == (9000, True, 6543)


async def test_load_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("E_PORT", "9000")
    assert Settings.load(port=7000).port == 7000


async def test_load_file_layers_under_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "c.toml"
    path.write_text('port = 5555\n[db]\nhost = "tomlhost"\n')
    monkeypatch.setattr(Settings, "config_file", path)
    monkeypatch.setenv("E_PORT", "6666")
    settings = Settings.load()
    assert (settings.port, settings.db.host) == (6666, "tomlhost")


async def test_load_secrets_never_leaks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "E_TOKEN").write_text("shh\n")
    monkeypatch.setattr(Settings, "secrets_dir", tmp_path)
    settings = Settings.load()
    assert settings.token.reveal() == "shh"
    assert "shh" not in repr(settings)


##### READ: ANY FILE #####
@pytest.mark.parametrize(
    ("name", "body", "expected"),
    [
        ("c.toml", "[db]\nport = 1234\n", {"db": {"port": 1234}}),
        ("c.json", '{"port": 4321}', {"port": 4321}),
        ("c.jsonc", '{"port": 1} // comment\n', {"port": 1}),
        ("c.yaml", "db:\n  host: yhost\n", {"db": {"host": "yhost"}}),
        ("c.ini", "[db]\nport = 4321\n", {"db": {"port": "4321"}}),
        ("c.env", "E_PORT=6000\n# junk line\n", {"port": "6000"}),
    ],
    ids=["toml", "json", "jsonc", "yaml", "ini", "dotenv"],
)
async def test_read_any_config_file(name: str, body: str, expected: object, tmp_path: Path) -> None:
    path = tmp_path / name
    path.write_text(body)
    assert Settings.read(path) == expected


async def test_read_corrupt_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "c.toml"
    path.write_text("port = = =\n")
    with pytest.raises(SettingsLoadError, match="Cannot decode"):
        Settings.read(path)


@pytest.mark.parametrize("path", [None, "absent.toml"], ids=["none", "missing"])
async def test_read_absent_is_empty(path: Path | None, tmp_path: Path) -> None:
    assert Settings.read(tmp_path / path if path else None) == {}


async def test_read_directory_is_secrets(tmp_path: Path) -> None:
    (tmp_path / "E_DB__HOST").write_text("fromfile\n")
    assert Settings.read(tmp_path) == {"db": {"host": "fromfile"}}


async def test_read_rejects_foreign_source() -> None:
    with pytest.raises(TypeError):
        Settings.read(cast("Any", "not-a-path"))


##### NEST #####
async def test_nest_filters_cases_and_splits() -> None:
    flat = {"PATH": "/usr/bin", "E_DB__HOST": "h", "E_PORT": "1"}
    assert Settings.nest(flat) == {"db": {"host": "h"}, "port": "1"}


async def test_nest_decodes_json_values() -> None:
    assert Settings.nest({"E_TAGS": '["a", "b"]', "E_LIMITS": '{"x": 1}'}) == {"tags": ["a", "b"], "limits": {"x": 1}}


async def test_nest_strips_export_and_quotes(tmp_path: Path) -> None:
    path = tmp_path / "e.env"
    path.write_text("export A='one'\nB = two\njunk\n")
    assert BaseSettings.nest(BaseSettings.dotenv(path)) == {"a": "one", "b": "two"}


##### MERGE #####
async def test_merge_deep() -> None:
    base: dict[str, object] = {"db": {"host": "a", "port": 1}, "gone": True}
    assert BaseSettings.merge(base, {"db": {"port": 2}, "gone": False}) == {
        "db": {"host": "a", "port": 2},
        "gone": False,
    }


##### DECODE #####
async def test_secret_never_leaks() -> None:
    secret = Secret("hunter2")
    assert "hunter2" not in repr(secret)
    assert "hunter2" not in f"{secret}"
    assert secret.reveal() == "hunter2"


async def test_decode_secret() -> None:
    assert Settings.decode(Secret, "x") == Secret("x")


async def test_decode_unsupported() -> None:
    with pytest.raises(NotImplementedError, match="Unsupported settings type"):
        Settings.decode(complex, 1)
