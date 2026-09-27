"""Async WebSocket client for the ESP32 telemetry server (ws://<ip>:81/).

Reconnects with exponential backoff and yields validated
``(protocol.Batch, protocol.BatchEvent)`` pairs. Malformed packets are
reported via a callback instead of crashing the stream, since a single bad
JSON message from a noisy link should not tear down a live session.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import AsyncIterator, Callable, Optional, Tuple

import websockets

from . import protocol

logger = logging.getLogger(__name__)

DEFAULT_PORT = 81
DEFAULT_PATH = "/"


def default_uri(host: str, port: int = DEFAULT_PORT, path: str = DEFAULT_PATH) -> str:
    if not path.startswith("/"):
        path = "/" + path
    return f"ws://{host}:{port}{path}"


@dataclass
class ClientStats:
    """Running counters, useful for a dashboard status panel."""

    batches_received: int = 0
    parse_errors: int = 0
    reconnects: int = 0
    seq_gaps_total: int = 0
    dropped_total: int = 0
    epochs_seen: int = 0


ErrorCallback = Callable[[Exception, str], None]


class TelemetryClient:
    """Reconnecting WebSocket client that yields validated telemetry batches."""

    def __init__(
        self,
        uri: str,
        *,
        reconnect_delay_s: float = 0.5,
        max_reconnect_delay_s: float = 15.0,
        connect_timeout_s: float = 5.0,
        on_error: Optional[ErrorCallback] = None,
    ):
        self.uri = uri
        self.reconnect_delay_s = reconnect_delay_s
        self.max_reconnect_delay_s = max_reconnect_delay_s
        self.connect_timeout_s = connect_timeout_s
        self.on_error = on_error
        self.stats = ClientStats()
        self._epoch_state = protocol.INITIAL_EPOCH_STATE
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    def _report(self, exc: Exception, context: str) -> None:
        logger.warning("%s: %s", context, exc)
        if self.on_error is not None:
            self.on_error(exc, context)

    async def stream(self) -> AsyncIterator[Tuple[protocol.Batch, protocol.BatchEvent]]:
        """Yield (batch, event) pairs forever, reconnecting on any failure.

        Runs until ``stop()`` is called or the surrounding task is cancelled.
        """
        delay = self.reconnect_delay_s
        while not self._stop.is_set():
            try:
                async with websockets.connect(
                    self.uri, open_timeout=self.connect_timeout_s
                ) as ws:
                    delay = self.reconnect_delay_s  # reset backoff after a successful connect
                    while not self._stop.is_set():
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=0.5)
                        except asyncio.TimeoutError:
                            continue
                        try:
                            batch = protocol.parse_batch(message)
                        except protocol.ProtocolError as exc:
                            self.stats.parse_errors += 1
                            self._report(exc, "dropped invalid packet")
                            continue

                        self._epoch_state, event = protocol.classify_batch(
                            self._epoch_state, batch
                        )
                        self.stats.batches_received += 1
                        self.stats.seq_gaps_total += event.seq_gap
                        self.stats.dropped_total = batch.dropped
                        self.stats.epochs_seen = self._epoch_state.epoch + 1
                        yield batch, event
            except asyncio.CancelledError:
                raise
            except (OSError, websockets.exceptions.WebSocketException) as exc:
                self.stats.reconnects += 1
                self._report(exc, "connection lost, reconnecting")
            if self._stop.is_set():
                return
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
            delay = min(delay * 2, self.max_reconnect_delay_s)


async def stream_batches(
    host: str,
    *,
    port: int = DEFAULT_PORT,
    path: str = DEFAULT_PATH,
    on_error: Optional[ErrorCallback] = None,
) -> AsyncIterator[Tuple[protocol.Batch, protocol.BatchEvent]]:
    """Convenience wrapper: connect to ws://host:port/path and yield batches."""
    client = TelemetryClient(default_uri(host, port, path), on_error=on_error)
    async for item in client.stream():
        yield item
