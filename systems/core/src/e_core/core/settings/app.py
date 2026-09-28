"""Auto-discoverable settings submodule: process-level knobs — APP_ENV, APP_HOST, APP_PORT."""

from e_core.core.settings.base import BaseSettings


class AppSettings(BaseSettings, frozen=True):
    """APP_ENV (dev | local | prod) drives the logger; APP_HOST/APP_PORT drive the granian runner."""

    app_env: str = "dev"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
