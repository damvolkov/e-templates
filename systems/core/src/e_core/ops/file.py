"""ops/file: agnostic filesystem discovery over an installed package — modules, classes, functions."""

import functools
import importlib
import inspect
import pkgutil
from enum import StrEnum, auto
from types import ModuleType
from typing import TYPE_CHECKING, Any

import anyio

if TYPE_CHECKING:
    import re
    from collections.abc import Callable


##### TYPES #####
class Kind(StrEnum):
    MODULES = auto()
    CLASSES = auto()
    FUNCTIONS = auto()


##### FINDER #####
class FileFinder:
    """Walk a package once; ``discover`` answers whatever ``target`` asks and nothing else.

    Agnostic dispatch on the target's type: a ``Kind`` sweeps a category, a class selects its
    subclasses, a module reads that one module's own symbols, a predicate decides freely.
    ``pattern`` filters the resulting names. ``adiscover`` offloads the import walk to a thread.
    """

    __slots__ = ("_package", "_skip")

    def __init__(self, package: str, *, skip: frozenset[str] = frozenset()) -> None:
        self._package = package
        self._skip = skip | {"__init__"}

    ##### PRIVATE #####

    def _modules(self) -> dict[str, ModuleType]:
        package = importlib.import_module(self._package)
        return {
            info.name: importlib.import_module(f"{self._package}.{info.name}")
            for info in pkgutil.iter_modules(package.__path__)
            if not info.ispkg and info.name not in self._skip
        }

    @staticmethod
    def _own(mod: ModuleType, predicate: Callable[[object], bool]) -> dict[str, Any]:
        return {
            name: obj
            for name, obj in vars(mod).items()
            if not name.startswith("_") and predicate(obj) and getattr(obj, "__module__", None) == mod.__name__
        }

    def _classes(self, modules: dict[str, ModuleType], of_base: type | None = None) -> dict[str, type]:
        return {
            name: obj
            for module in modules.values()
            for name, obj in self._own(module, inspect.isclass).items()
            if of_base is None or issubclass(obj, of_base)
        }

    def _functions(self, modules: dict[str, ModuleType]) -> dict[str, Any]:
        return {name: obj for module in modules.values() for name, obj in self._own(module, inspect.isfunction).items()}

    def _select(self, target: Any, modules: dict[str, ModuleType], pattern: re.Pattern[str] | None) -> dict[str, Any]:
        match target:
            case Kind.MODULES:
                found: dict[str, Any] = modules
            case Kind.CLASSES:
                found = self._classes(modules)
            case Kind.FUNCTIONS:
                found = self._functions(modules)
            case ModuleType() as module:
                found = {**self._own(module, inspect.isclass), **self._own(module, inspect.isfunction)}
            case type() as base:
                found = self._classes(modules, base)
            case predicate if callable(predicate):
                found = {
                    k: v for k, v in {**self._classes(modules), **self._functions(modules)}.items() if predicate(v)
                }
            case unknown:
                msg = f"Unsupported discover target: {unknown!r}"
                raise TypeError(msg)
        match pattern:
            case None:
                return found
            case rx:
                return {name: obj for name, obj in found.items() if rx.search(name)}

    ############################################################

    ##### PUBLIC #####

    def discover(
        self, target: Kind | type | ModuleType | Callable[[Any], bool], *, pattern: re.Pattern[str] | None = None
    ) -> dict[str, Any]:
        """Return ``{name: object}`` for whatever ``target`` selects across the package's modules."""
        return self._select(target, self._modules(), pattern)

    async def adiscover(
        self, target: Kind | type | ModuleType | Callable[[Any], bool], *, pattern: re.Pattern[str] | None = None
    ) -> dict[str, Any]:
        """``discover`` off the event loop: the import walk is CPU/IO work, not async I/O."""
        return await anyio.to_thread.run_sync(functools.partial(self.discover, target, pattern=pattern))
