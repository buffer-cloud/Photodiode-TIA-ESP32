"""Preliminary live ESP32 stream-health capture (not optical measurement).

Run: python -m photodiode_tia.stream_benchmark --host <ESP32-IP> --seconds 10 --output result.json
The host address is deliberately omitted from the saved report.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

import websockets

from .protocol import parse_batch


async def capture(host: str, seconds: float) -> dict:
    if seconds <= 0:
        raise ValueError("duration must be positive")
    batches = 0
    received_samples = 0
    sequence_gaps = 0
    first_dropped = last_dropped = None
    first_sequence = last_sequence = None
    first_device_us = last_device_us = None
    rate_hz = set()
    perf_serialize_us = []
    perf_broadcast_us = []
    queue_batches = []
    ws_clients = []
    elapsed = 0.0
    async with websockets.connect(f"ws://{host}:81/", open_timeout=8, max_size=1_000_000) as socket:
        started = time.monotonic()
        while time.monotonic() - started < seconds:
            remaining = seconds - (time.monotonic() - started)
            try:
                message = await asyncio.wait_for(socket.recv(), timeout=max(0.01, remaining))
            except asyncio.TimeoutError:
                break
            payload = json.loads(message)
            batch = parse_batch(payload)
            for key, values in (("perf_ser_us", perf_serialize_us), ("perf_tx_us", perf_broadcast_us),
                                ("queue_batches", queue_batches), ("ws_clients", ws_clients)):
                value = payload.get(key)
                if isinstance(value, int) and value >= 0:
                    values.append(value)
            if first_sequence is None:
                first_sequence = batch.seq
                first_dropped = batch.dropped
                first_device_us = batch.t0_us
            elif batch.seq > last_sequence + 1:
                sequence_gaps += batch.seq - last_sequence - 1
            elif batch.seq <= last_sequence:
                raise RuntimeError("device sequence reset; repeat capture as a separate epoch")
            last_sequence = batch.seq
            last_dropped = batch.dropped
            last_device_us = batch.t0_us + batch.dt_us[-1]
            batches += 1
            received_samples += batch.n
            rate_hz.add(batch.fs_hz)
        elapsed = time.monotonic() - started
    return {
        "provenance": "PHYSICAL ESP32 STREAM; GPIO34 open; not photodiode/optical data",
        "conditions": "Opportunistic local Wi-Fi run; other clients and RF environment uncontrolled",
        "duration_s": round(elapsed, 3),
        "packets_received": batches,
        "samples_received": received_samples,
        "observed_sample_delivery_per_s": round(received_samples / elapsed, 1),
        "device_time_span_s": round((last_device_us - first_device_us) / 1_000_000, 3) if first_device_us is not None else None,
        "receiver_backlog_growth_s": round(elapsed - (last_device_us - first_device_us) / 1_000_000, 3) if first_device_us is not None else None,
        "first_sequence": first_sequence,
        "last_sequence": last_sequence,
        "missing_packet_sequences": sequence_gaps,
        "device_dropped_samples_during_capture": (last_dropped - first_dropped) if first_dropped is not None else None,
        "configured_sample_rates_hz": sorted(rate_hz),
        "max_serialize_us": max(perf_serialize_us, default=None),
        "max_broadcast_us": max(perf_broadcast_us, default=None),
        "max_queued_batches": max(queue_batches, default=None),
        "max_connected_clients": max(ws_clients, default=None),
        "interpretation_limit": "Device dropped counter includes transport and acquisition losses; this run does not isolate causes or establish ADC accuracy.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(capture(args.host, args.seconds))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
