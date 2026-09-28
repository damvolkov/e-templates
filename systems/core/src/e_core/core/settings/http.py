"""Auto-discoverable settings submodule: the outbound HTTP edge — HTTP_BASE_URL, HTTP_TIMEOUT."""

from datetime import timedelta

from e_core.core.settings.base import BaseSettings


class HttpSettings(BaseSettings, frozen=True):
    """HTTP_BASE_URL / HTTP_TIMEOUT (seconds, decoded to `timedelta`)."""

    http_base_url: str = "https://httpbin.org"
    http_timeout: timedelta = timedelta(seconds=10)
