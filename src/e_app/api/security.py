"""api.security: bearer enforcement and the OpenAPI contract — `core.crypto` is the only source of truth.

The guard verifies the token and parks its claims in the connection scope; `provide_current_user`
(api.deps) turns those claims into a `User`. Guards run before dependencies, so a handler that
depends on `current_user` is automatically behind the bearer check once `auth_guard` is attached.
"""

from typing import TYPE_CHECKING, Any

from litestar.exceptions import NotAuthorizedException
from litestar.openapi.spec import SecurityScheme

from e_app.core.crypto import TokenError

if TYPE_CHECKING:
    from litestar.connection import Request
    from litestar.types import Scope

##### CONTRACT #####
BEARER_SCHEME = SecurityScheme(type="http", scheme="bearer", bearer_format="JWT")
SECURITY: list[dict[str, list[str]]] = [{"bearerAuth": []}]


##### HELPERS #####
def bearer_claims(request: "Request") -> dict[str, Any]:
    """Verified claims for the request's bearer token, or 401."""
    match request.headers.get("authorization", "").split():
        case ["Bearer", token]:
            try:
                return request.app.state.graph.crypto.verify_token(token)
            except TokenError as exc:
                raise NotAuthorizedException(detail=str(exc)) from exc
        case _:
            raise NotAuthorizedException(detail="Bearer token required")


def auth_guard(request: "Request", scope: "Scope") -> None:
    """Litestar guard: authenticate, then expose claims to the dependency chain."""
    scope["claims"] = bearer_claims(request)
