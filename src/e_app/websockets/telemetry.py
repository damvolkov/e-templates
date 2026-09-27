"""websockets.telemetry: active listener — Heartbeat in, TelemetryEvent out, msgspec per frame.

`websocket_listener` owns accept/receive/loop and serializes the return value automatically; for pure
server push the sibling pattern is `websocket_stream` (async generator + DI), registered the same way.
"""

from datetime import UTC, datetime

import structlog
from litestar import websocket_listener

from e_app.models.telemetry import TelemetryEvent, Heartbeat, Status

logger = structlog.get_logger()


async def telemetry(data: Heartbeat, correlation_id: str) -> TelemetryEvent:
    """Grade one heartbeat's arrival latency and answer with the round's verdict."""
    latency_ms = max(0.0, (datetime.now(UTC) - data.sent_at).total_seconds() * 1000)
    event = TelemetryEvent(
        seq=data.seq,
        status=Status.from_latency(latency_ms),
        latency_ms=latency_ms,
        emitted_at=datetime.now(UTC),
    )
    logger.info(
        "telemetry",
        seq=event.seq,
        status=event.status.value,
        latency_ms=round(event.latency_ms, 1),
        correlation=correlation_id,
    )
    return event


WS_ROUTES = (websocket_listener("/ws/telemetry", name="telemetry")(telemetry),)
