"""api.deps: chained dependency providers — litestar resolves the graph recursively per request.

No FastAPI `Depends()` sugar: binding is by *name*. Each link declares what it consumes in its own
signature (`oauth` and `store` take `graph`, `current_user` takes `request` + `store`), every route
wires the chains it uses in a local `dependencies` mapping, and the app itself registers nothing.
Links run once per request, in resolved order; independent links run concurrently.
"""

from typing import Any, cast

import msgspec
from asgi_correlation_id import correlation_id as correlation_id_var
from authlib.integrations.starlette_client import OAuth
from litestar.connection import Request
from litestar.di import NamedDependency
from litestar.exceptions import NotAuthorizedException

from core.state import State
from e_api.adapters.base import StoreAdapter
from e_api.api.security import bearer_claims
from e_api.models.user import User, UserRecord

USER_KEY: str = "user:"


##### LINKS — each names its injection parameter and consumes other links by name #####
def graph(request: Request) -> State:
    """Root of every chain: the app's dynamic state graph, filled by the lifespan and sealed."""
    return cast("State", request.app.state)


def oauth(graph: NamedDependency[State]) -> OAuth:
    """The authlib registry — empty while no IdP is configured. Chain: graph."""
    return graph.oauth


def store(graph: NamedDependency[State]) -> StoreAdapter:
    """The KV edge the user records live on; swap scope here to send a route elsewhere. Chain: graph."""
    return graph.adapters.sqlite


async def current_user(request: Request, store: NamedDependency[StoreAdapter]) -> User:
    """The placeholder authz: bearer claims (guard already verified) mapped to a live `User`.

    Chain: request + store. Swap the lookup for the real session when it exists."""
    claims: dict[str, Any] = bearer_claims(request)
    match await load_record(store, str(claims.get("sub", ""))):
        case None:
            raise NotAuthorizedException(detail="Unknown subject")
        case record:
            return to_user(record)


def correlation_id() -> str:
    """Request id propagated by `CorrelationIdMiddleware`; empty only when the middleware is off. Chain: none."""
    return correlation_id_var.get() or ""


##### HELPERS — shared by handlers and links, never injected #####
async def load_record(store: StoreAdapter, user_id: str) -> UserRecord | None:
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
