"""tests/unit: the assembly itself — lazy factory, declarative registration, composite settings."""

import msgspec

import e_api.main as entrypoint
from core.settings import settings as st


def test_importing_main_has_no_side_effects() -> None:
    assert callable(entrypoint.create_app)
    assert not hasattr(entrypoint, "app"), "the factory must stay lazy: granian builds it per worker"


def test_composite_settings_expose_every_scope() -> None:
    scopes = {f.name for f in msgspec.structs.fields(type(st))}
    assert {"api", "app", "crypto", "db", "http", "oauth", "redis"} <= scopes
    assert st.redis.redis_url.startswith("redis://")
    assert st.app.app_port == 8000


def test_create_app_registers_every_router(client) -> None:
    paths = {route.path for route in client.app.routes}
    assert {"/health", "/oauth/providers", "/users", "/users/{user_id:uuid}", "/ws/telemetry", "/schema"} <= paths


def test_chains_wire_endpoints_not_the_app(client) -> None:
    assert client.app.dependencies == {}  # every dependency link is declared by the route that consumes it
