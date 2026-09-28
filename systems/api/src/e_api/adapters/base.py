"""adapters.base: the minimum async contract for external services — connect, close, and one shared CRUD shape.

Subclasses own whatever the client needs internally; the lifespan only ever talks to `connect`/`close`
(through the async-context bridge), so any backend drops into the `AsyncExitStack` unchanged.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Self

if TYPE_CHECKING:
    from types import TracebackType


##### TYPES #####
class BaseAdapter(ABC):
    """Lifecycle edge: connect before use, close after; usable as an async context manager."""

    name: ClassVar[str]

    @abstractmethod
    async def connect(self) -> None:
        """Open the connection/pool. Idempotency is the implementation's problem."""

    @abstractmethod
    async def close(self) -> None:
        """Release everything connect() took."""

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(
        self, _exc_type: type[BaseException] | None, _exc: BaseException | None, _tb: TracebackType | None
    ) -> None:
        await self.close()


class StoreAdapter(BaseAdapter):
    """Byte-keyed store: the same minimum CRUD across backends, so redis and sqlite are interchangeable."""

    @abstractmethod
    async def get(self, key: str) -> bytes | None:
        """Missing key reads as None, never an exception."""

    @abstractmethod
    async def set(self, key: str, value: bytes) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Missing key is a no-op."""

    @abstractmethod
    async def keys(self, prefix: str = "") -> list[str]:
        """Keys starting with `prefix`, sorted."""
