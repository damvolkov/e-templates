"""Auto-discoverable settings submodule: the OAuth2 identity provider — OAUTH_NAME, CLIENT_ID, CLIENT_SECRET, SERVER_METADATA_URL."""

from e_core.core.settings.base import BaseSettings, Secret


class OAuthSettings(BaseSettings, frozen=True):
    """An empty SERVER_METADATA_URL means "no IdP configured": the registry stays empty and the app boots."""

    oauth_name: str = "dev"
    client_id: str = ""
    client_secret: Secret = Secret("")
    server_metadata_url: str = ""
