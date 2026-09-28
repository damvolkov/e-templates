"""e_core.core.logger: renderer, serializer and startup wiring."""

import io
import json
from typing import TYPE_CHECKING, cast

import pytest

from e_core.core import logger as lg

if TYPE_CHECKING:
    from structlog.typing import EventDict, WrappedLogger


##### SETUP #####
@pytest.mark.parametrize("env", ["prod", "dev", "local"], ids=["prod", "dev", "local"])
async def test_setup(env: str) -> None:
    lg.setup(env=env)


async def test_setup_unknown_env() -> None:
    with pytest.raises(ValueError, match="Unknown env"):
        lg.setup(env="nope")


##### ENCODE_JSON #####
async def test_encode_json() -> None:
    assert json.loads(lg.encode_json({"event": "ok", "n": 1})) == {"event": "ok", "n": 1}


async def test_encode_json_default_hook() -> None:
    raw = lg.encode_json({"obj": object()}, default=str)
    assert "object object at" in raw.decode()


##### ELOGGER #####
class _TTYStream(io.TextIOWrapper):
    def isatty(self) -> bool:
        return True


def _sink(*, tty: bool = False) -> io.TextIOWrapper:
    return _TTYStream(io.BytesIO()) if tty else io.TextIOWrapper(io.BytesIO())


async def test_elogger_order() -> None:
    renderer = lg.ELogger(order=("request_id",), stream=_sink())
    event: EventDict = {"timestamp": "T", "level": "info", "event": "hello", "zeta": 1, "request_id": "r1"}
    assert renderer(cast("WrappedLogger", None), "info", event) == "T | INFO     | hello || request_id: r1 || zeta: 1"


async def test_elogger_colors() -> None:
    renderer = lg.ELogger(stream=_sink(tty=True))
    event: EventDict = {"timestamp": "T", "level": "warning", "event": "hi"}
    assert "\033[33m" in renderer(cast("WrappedLogger", None), "warning", event)


async def test_elogger_unknown_level() -> None:
    renderer = lg.ELogger(stream=_sink())
    event: EventDict = {"timestamp": "T", "level": "notice", "event": "hi"}
    assert "NOTICE" in renderer(cast("WrappedLogger", None), "notice", event)


async def test_elogger_traceback_appended() -> None:
    renderer = lg.ELogger(stream=_sink())
    event: EventDict = {"timestamp": "T", "level": "error", "event": "boom", "exception": "Traceback..."}
    line = renderer(cast("WrappedLogger", None), "error", event)
    assert line.endswith("Traceback...")
