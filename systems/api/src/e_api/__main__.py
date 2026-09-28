"""python -m e_api: dev runner — granian (Rust HTTP), ASGI interface, app-factory target, auto-reload."""

from granian import Granian
from granian.constants import Interfaces

from core.settings import settings as st

if __name__ == "__main__":
    Granian(
        target="e_api.main:create_app",
        address=st.app.app_host,
        port=st.app.app_port,
        interface=Interfaces.ASGI,
        factory=True,
        reload=True,
    ).serve()
