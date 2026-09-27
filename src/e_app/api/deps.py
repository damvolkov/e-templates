"""api.deps: the request-scoped wiring chains — oauth, fake user check, correlation id, graph navigation.

Everything here is a plain factory litestar injects by name; none of them knows the app.
"""

from typing import TYPE_CHECKING, Any

import msgspec
from asgi_correlation_id import correlation_id
from authlib.integrations.starlette_client import OAuth
from litestar.connection import Request
from litestar.exceptions import NotAuthorizedException
from litestar.types import Scope

from e_app.api.security import bearer_claims
from e_app.core.state import State
from e_app.models.user import User, UserRecord

if TYPE_CHECKING:
    from e_app.adapters.base import StoreAdapter

USER_KEY: str = "user:"


##### CHAIN 1: OAUTH (authlib registry, born in the lifespan) #####
def provide_oauth(request: Request) -> OAuth:
    """The configured OAuth registry — empty while OAUTH__SERVER_METADATA_URL is unset."""
    return request.app.state.graph.oauth


##### CHAIN 2: FAKE USER CHECK (claims -> stored record; swap the store for the real session) #####
async def load_record(store: "StoreAdapter", user_id: str) -> UserRecord | None:
    """Single point where a user is read from the KV store; None means gone."""
    raw = await store.get(f"{USER_KEY}{user_id}")
    return None if raw is None else msgspec.json.decode(raw, type=UserRecord)


def to_user(record: UserRecord) -> User:
    """Projection: the credential is lost by construction — `User` has no hash field to drop."""
    return User(
        id=record.id,
        username=record.username,
        email=record.email,
        birth=record.birth,
        quota=record.quota,
        created=record.created,
    )


async def provide_current_user(request: Request, scope: Scope) -> User:
    """The placeholder authz chain: bearer claims (verified by `auth_guard`) mapped to a live `User`."""
    claims: dict[str, Any] = scope.get("claims") or bearer_claims(request)
    match await load_record(request.app.state.graph.adapters.sqlite, str(claims.get("sub", ""))):
        case None:
            raise NotAuthorizedException(detail="Unknown subject")
        case record:
            return to_user(record)


##### CHAIN 3: CORRELATION (asgi_correlation_id contextvar) #####
def provide_correlation_id() -> str:
    """Request id set by `CorrelationIdMiddleware`; empty only when the middleware is off."""
    return correlation_id.get() or ""


##### GRAPH #####
def provide_graph(request: Request) -> State:
    """The sealed resource graph — the navigation handle for any handler, like langgraph state."""
    return request.app.state.graph
