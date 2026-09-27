"""api.router.user: CRUD over the User DTO family — guard, three injection chains, msgspec at both edges.

Handlers are plain async functions with no knowledge of HTTP; the ROUTES tuple at the bottom is the
single place where routes, guards and dependencies meet them — declarative registration, not decorators.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import msgspec
import structlog
from litestar import delete, get, patch, post
from litestar.di import Provide
from litestar.exceptions import NotFoundException

from e_app.api.deps import USER_KEY, load_record, provide_current_user, to_user
from e_app.api.security import SECURITY, auth_guard
from e_app.core.state import State
from e_app.models.user import User, UserCreate, UserRecord, UserUpdate

logger = structlog.get_logger()


##### HANDLERS #####
async def create_user(data: UserCreate, graph: State) -> User:
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


async def list_users(graph: State) -> list[User]:
    """Collection read through the store's key prefix — no ORM, no magic."""
    store = graph.adapters.sqlite
    ids = (key.removeprefix(USER_KEY) for key in await store.keys(USER_KEY))
    return [to_user(r) for r in (await load_record(store, user_id) for user_id in ids) if r is not None]


async def read_user(user_id: UUID, graph: State, current_user: User, correlation_id: str) -> User:
    """Behind the bearer: `current_user` is chain 2 (fake check), `correlation_id` chain 3, `graph` the navigation."""
    match await load_record(graph.adapters.sqlite, str(user_id)):
        case None:
            raise NotFoundException(detail="No such user")
        case record:
            logger.info("user read", user_id=str(user_id), by=current_user.username, correlation=correlation_id)
            return to_user(record)


async def update_user(user_id: UUID, data: UserUpdate, graph: State) -> User:
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
            updated = msgspec.evolve(record, **changes)
            await store.set(USER_KEY + str(user_id), msgspec.json.encode(updated))
            return to_user(updated)


async def delete_user(user_id: UUID, graph: State) -> None:
    """Idempotent removal — 204 whether or not it existed."""
    await graph.adapters.sqlite.delete(USER_KEY + str(user_id))


##### ROUTES #####
ROUTES = (
    post("/users", name="user.create", status_code=201, tags=["users"])(create_user),
    get("/users", name="user.list", tags=["users"], guards=[auth_guard], security=SECURITY)(list_users),
    get(
        "/users/{user_id:uuid}",
        name="user.read",
        tags=["users"],
        guards=[auth_guard],
        security=SECURITY,
        dependencies={"current_user": Provide(provide_current_user)},
    )(read_user),
    patch("/users/{user_id:uuid}", name="user.update", tags=["users"], guards=[auth_guard], security=SECURITY)(
        update_user
    ),
    delete("/users/{user_id:uuid}", name="user.delete", status_code=204, tags=["users"], guards=[auth_guard], security=SECURITY)(
        delete_user
    ),
)
