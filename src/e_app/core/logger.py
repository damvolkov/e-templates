"""e-stack logger: structured JSON in prod, ordered plain text in dev/local."""

import logging
import sys
from enum import StrEnum
from typing import TYPE_CHECKING, Any, TextIO

import msgspec
import structlog

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from structlog.typing import EventDict, Processor, WrappedLogger


##### TYPES #####
class Env(StrEnum):
    PROD = "prod"
    DEV = "dev"
    LOCAL = "local"


##### DEFAULTS #####
DEFAULT_ENV: str = Env.DEV
DEFAULT_LEVEL: int = logging.INFO
DEFAULT_ORDER: Sequence[str] = ()
DEFAULT_SEP: str = " || "
DEFAULT_HEAD_SEP: str = " | "
DEFAULT_KV_FMT: str = "{key}: {value}"
DEFAULT_LEVEL_WIDTH: int = 8
DEFAULT_STREAM: TextIO = sys.stdout

##### EVENT DICT KEYS (SET BY STRUCTLOG PROCESSORS) #####
TIMESTAMP_KEY = "timestamp"
LEVEL_KEY = "level"
EVENT_KEY = "event"
EXCEPTION_KEY = "exception"

##### ANSI #####
RESET = "\033[0m"
DIM = "\033[2m"
LEVEL_COLORS: dict[str, str] = {
    "debug": "\033[36m",
    "info": "\033[32m",
    "warning": "\033[33m",
    "error": "\033[31m",
    "critical": "\033[1;31m",
}


##### SERIALIZERS #####
def encode_json(event_dict: EventDict, default: Callable[[Any], Any] | None = None) -> bytes:
    """msgspec (C-backed) serializer, json.dumps-compatible: structlog's `default` hook is msgspec's `enc_hook`."""
    return msgspec.json.encode(event_dict, enc_hook=default)


##### RENDERERS #####
class ELogger:
    """Render `timestamp | LEVEL | event || key: value || ...`, priority keys first, rest sorted."""

    __slots__ = ("_dim", "_head_sep", "_kv_fmt", "_levels", "_order", "_order_set", "_reset", "_sep", "_width")

    def __init__(
        self,
        *,
        order: Sequence[str] = DEFAULT_ORDER,
        sep: str = DEFAULT_SEP,
        head_sep: str = DEFAULT_HEAD_SEP,
        kv_fmt: str = DEFAULT_KV_FMT,
        level_width: int = DEFAULT_LEVEL_WIDTH,
        colors: bool = True,
        stream: TextIO = DEFAULT_STREAM,
    ) -> None:
        self._order = tuple(order)
        self._order_set = frozenset(order)
        self._sep, self._head_sep, self._kv_fmt, self._width = sep, head_sep, kv_fmt, level_width
        match colors and stream.isatty():  # no ANSI codes into pipes or files
            case True:
                palette, self._dim, self._reset = LEVEL_COLORS, DIM, RESET
            case _:
                palette, self._dim, self._reset = dict.fromkeys(LEVEL_COLORS, ""), "", ""
        self._levels = {lvl: f"{color}{lvl.upper():<{level_width}}{self._reset}" for lvl, color in palette.items()}

    def __call__(self, _logger: WrappedLogger, _method: str, event_dict: EventDict) -> str:
        ts = event_dict.pop(TIMESTAMP_KEY, "")
        level = event_dict.pop(LEVEL_KEY, "")
        event = event_dict.pop(EVENT_KEY, "")
        exc = event_dict.pop(EXCEPTION_KEY, "")
        keys = [k for k in self._order if k in event_dict] + sorted(event_dict.keys() - self._order_set)
        label = self._levels.get(level) or f"{level.upper():<{self._width}}"
        head = self._head_sep.join((f"{self._dim}{ts}{self._reset}", label, str(event)))
        line = self._sep.join((head, *(self._kv_fmt.format(key=k, value=event_dict[k]) for k in keys)))
        return "\n".join(filter(None, (line, exc)))


##### SETUP #####
def setup(
    *,
    env: str = DEFAULT_ENV,
    level: int = DEFAULT_LEVEL,
    order: Sequence[str] = DEFAULT_ORDER,
    stream: TextIO = DEFAULT_STREAM,
    **renderer_kwargs: Any,
) -> None:
    """Call once at process startup, before any get_logger(): `setup(env=settings.env)`."""
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    match env.lower():
        case Env.PROD:
            renderer: Processor = structlog.processors.JSONRenderer(serializer=encode_json)
            factory: Any = structlog.BytesLoggerFactory(file=stream.buffer)  # msgspec emits bytes
        case Env.DEV | Env.LOCAL:
            renderer = ELogger(order=order, stream=stream, **renderer_kwargs)
            factory = structlog.PrintLoggerFactory(file=stream)
        case unknown:
            msg = f"Unknown env {unknown!r}; expected one of {[e.value for e in Env]}"
            raise ValueError(msg)

    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=factory,
        cache_logger_on_first_use=True,
    )
