"""core/state: the app resource graph — one attribute-access container over a dict, nothing more.

Categories are nested `State`s (`state.adapters.redis`), leaves are plain objects (`state.crypto`).
The lifespan builds and seals it; after seal, writes raise — no runtime drift.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator


##### TYPES #####
class State:
    """Dynamic node graph navigated by attribute, like the state flowing through a langgraph."""

    __slots__ = ("_nodes", "_sealed")

    def __init__(self, **nodes: Any) -> None:
        object.__setattr__(self, "_nodes", dict(nodes))
        object.__setattr__(self, "_sealed", False)

    def __getattr__(self, name: str) -> Any:
        try:
            return self._nodes[name]
        except KeyError:
            msg = f"State has no node {name!r}: {sorted(self._nodes)}"
            raise AttributeError(msg) from None

    def __setattr__(self, name: str, value: Any) -> None:
        self._check_writable()
        self._nodes[name] = value

    def __delattr__(self, name: str) -> None:
        self._check_writable()
        self._nodes.pop(name, None)

    def __getitem__(self, name: str) -> Any:
        return self._nodes[name]

    def __contains__(self, name: object) -> bool:
        return name in self._nodes

    def __iter__(self) -> Iterator[str]:
        return iter(self._nodes)

    def __len__(self) -> int:
        return len(self._nodes)

    def __repr__(self) -> str:
        return f"State({', '.join(sorted(self._nodes))})"

    def get(self, name: str, default: Any = None) -> Any:
        return self._nodes.get(name, default)

    def values(self) -> list[Any]:
        return list(self._nodes.values())

    def seal(self) -> None:
        """Close the graph: from now on, reads only."""
        object.__setattr__(self, "_sealed", True)

    def _check_writable(self) -> None:
        match self._sealed:
            case True:
                msg = "Sealed state: the graph is built at startup, mutated never"
                raise RuntimeError(msg)
            case _:
                pass
