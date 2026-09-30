"""adapters.draft: persistence of the in-progress session — a decision is never lost by closing the terminal."""

from typing import TYPE_CHECKING

import msgspec

from e_management.core.session import Session

if TYPE_CHECKING:
    from pathlib import Path


##### TYPES #####
class DraftStore:
    """One JSON file holding the wizard's current ``Session``; ``load`` answers None when there is no draft."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, session: Session) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(msgspec.json.encode(session))

    def load(self) -> Session | None:
        if not self.path.exists():
            return None
        try:
            return msgspec.json.decode(self.path.read_bytes(), type=Session)
        except msgspec.DecodeError:
            return None

    def drop(self) -> None:
        self.path.unlink(missing_ok=True)
