"""adapters/ports: what consumers (routers, deps, lifespan) may ask of an external service.

Structural contracts only — a Protocol, never an ABC: an adapter satisfies its port by shape,
and swapping redis for sqlite edits one wiring line, zero domain code."""

from typing import TYPE_CHECKING, ClassVar, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


##### TYPES #####
@runtime_checkable
class StorePort(Protocol):
    """Byte-keyed store: point reads, writes, deletes and a lazy key scan — the whole CRUD a consumer sees."""

    name: ClassVar[str]

    async def get(self, key: str) -> bytes | None:
        """Missing key reads as None, never an exception."""
        ...

    async def set(self, key: str, value: bytes) -> None: ...

    async def delete(self, key: str) -> None:
        """Missing key is a no-op."""
        ...

    def keys(self, prefix: str = "") -> AsyncIterator[str]:
        """Keys starting with `prefix`, streamed lazily: an async generator, never a materialized list."""
        ...


@runtime_checkable
class HttpPort(Protocol):
    """Outbound HTTP: GET and POST against the configured base, non-2xx raising the client's own error."""

    name: ClassVar[str]

    async def get(self, path: str) -> object: ...

    async def post(self, path: str, payload: object) -> object: ...
