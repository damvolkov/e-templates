"""api.router.user: CRUD over the User DTO family — guard, three injection chains, msgspec at both edges.

Handlers are plain async functions with no knowledge of HTTP; the ROUTES tuple at the bottom is the
single place where routes, guards and dependencies meet them — declarative registration, not decorators.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import msgspec
from litestar import delete, get, patch, post
from litestar.di import NamedDependency, Provide
from litestar.exceptions import NotFoundException
from litestar.handlers import HTTPRouteHandler
from litestar.params import FromPath

from core.logger import logger
from core.state import State
from e_api.api.deps import USER_KEY, correlation_id, current_user, graph, load_record, store, to_user
from e_api.api.security import SECURITY, auth_guard
from e_api.models.user import User, UserCreate, UserRecord, UserUpdate


##### HANDLERS #####
async def create_user(data: UserCreate, graph: NamedDependency[State]) -> User:
    """Public registration: hash through crypto, persist through the store — the credential never returns."""
    record = UserRecord(
        id=uuid4(),
        username=data.username,
        email=data.email,
        password_hash=await graph.crypto.hash_password(data.password),
        birth=data.birth,
        quota=data.quota,
        created=datetime.now(UTC),
    )
    await graph.adapters.sqlite.set(USER_KEY + str(record.id), msgspec.json.encode(record))
    return to_user(record)


async def list_users(graph: NamedDependency[State]) -> list[User]:
    """Collection read through the store's key prefix — no ORM, no magic."""
    store = graph.adapters.sqlite
    return [
        to_user(record)
        for key in await store.keys(USER_KEY)
        if (record := await load_record(store, key.removeprefix(USER_KEY))) is not None
    ]


async def read_user(
    user_id: FromPath[UUID],
    graph: NamedDependency[State],
    current_user: NamedDependency[User],
    correlation_id: NamedDependency[str],
) -> User:
    """Behind the bearer: `current_user` (fake check via `store` ← `graph`) and the request's correlation id."""
    match await load_record(graph.adapters.sqlite, str(user_id)):
        case None:
            raise NotFoundException(detail="No such user")
        case record:
            logger.info("user read", user_id=str(user_id), by=current_user.username, correlation=correlation_id)
            return to_user(record)


async def update_user(user_id: FromPath[UUID], data: UserUpdate, graph: NamedDependency[State]) -> User:
    """PATCH with the UNSET sentinel: absent fields stay, nulls apply."""
    store = graph.adapters.sqlite
    match await load_record(store, str(user_id)):
        case None:
            raise NotFoundException(detail="No such user")
        case record:
            changes = {
                field.name: value
                for field in msgspec.structs.fields(data)
                if (value := getattr(data, field.name)) is not msgspec.UNSET
            }
            updated = msgspec.structs.replace(record, **changes)
            await store.set(USER_KEY + str(user_id), msgspec.json.encode(updated))
            return to_user(updated)


async def delete_user(user_id: FromPath[UUID], graph: NamedDependency[State]) -> None:
    """Idempotent removal — 204 whether or not it existed."""
    await graph.adapters.sqlite.delete(USER_KEY + str(user_id))


##### CHAINS — endpoint-local wiring: each route declares the links it consumes #####
GRAPH_DEPS: dict[str, Provide] = {"graph": Provide(graph, sync_to_thread=False)}
READ_DEPS: dict[str, Provide] = {
    **GRAPH_DEPS,
    "correlation_id": Provide(correlation_id, sync_to_thread=False),
    "store": Provide(store, sync_to_thread=False),
    "current_user": Provide(current_user),
}

##### ROUTES #####
ROUTES: tuple[HTTPRouteHandler, ...] = (
    post("/users", name="user.create", status_code=201, tags=["users"], dependencies=GRAPH_DEPS)(create_user),
    get("/users", name="user.list", tags=["users"], guards=[auth_guard], security=SECURITY, dependencies=GRAPH_DEPS)(
        list_users
    ),
    get(
        "/users/{user_id:uuid}",
        name="user.read",
        tags=["users"],
        guards=[auth_guard],
        security=SECURITY,
        dependencies=READ_DEPS,
    )(read_user),
    patch(
        "/users/{user_id:uuid}",
        name="user.update",
        tags=["users"],
        guards=[auth_guard],
        security=SECURITY,
        dependencies=GRAPH_DEPS,
    )(update_user),
    delete(
        "/users/{user_id:uuid}",
        name="user.delete",
        status_code=204,
        tags=["users"],
        guards=[auth_guard],
        security=SECURITY,
        dependencies=GRAPH_DEPS,
    )(delete_user),
)
