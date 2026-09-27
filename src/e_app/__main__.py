"""python -m e_app: dev runner — granian (Rust HTTP), ASGI interface, auto-reload, settings-driven bind."""

from granian import Granian
from granian.constants import Interfaces

from e_app.core.settings import settings as st

if __name__ == "__main__":
    Granian(
        target="e_app.main:app",
        address=st.host,
        port=st.port,
        interface=Interfaces.ASGI,
        reload=True,
    ).serve()
