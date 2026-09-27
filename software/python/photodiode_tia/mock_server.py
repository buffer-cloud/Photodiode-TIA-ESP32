"""SYNTHETIC telemetry v1 mock server for testing the client/dashboard without hardware.

Every packet this module emits carries `"calibration": "SYNTHETIC..."` and
every log line says SYNTHETIC. Nothing produced here may be copied into
measurements/ (see measurements/raw/README.md and .gitignore) -- it exists
purely to exercise protocol.py, client.py, analysis.py and dashboard.py end
to end on localhost.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
from dataclasses import dataclass
from typing import Optional

import numpy as np
import websockets

logger = logging.getLogger(__name__)

SYNTHETIC_CALIBRATION_TAG = "SYNTHETIC-mock-server-v1"
DEFAULT_DARK_MV = 1650.0  # matches VREF dark baseline in docs/design-contract.md


@dataclass(frozen=True)
class SyntheticSignalConfig:
    fs_hz: float = 4000.0
    batch_size: int = 256
    gain_ohm: int = 100_000
    dark_mv: float = DEFAULT_DARK_MV
    amplitude_mv: float = 50.0
    freq_hz: float = 10.0
    noise_std_mv: float = 2.0
    drop_every_n_batches: int = 0  # 0 disables synthetic drops
    seed: Optional[int] = None


def _dt_us_grid(n: int, fs_hz: float) -> np.ndarray:
    """Strictly increasing integer dt_us starting at 0, spaced ~1e6/fs_hz apart."""
    raw = np.arange(n, dtype=np.float64) * (1e6 / fs_hz)
    dt_us = np.round(raw).astype(np.int64)
    for i in range(1, n):
        if dt_us[i] <= dt_us[i - 1]:
            dt_us[i] = dt_us[i - 1] + 1
    dt_us -= dt_us[0]
    return dt_us


def make_synthetic_packet(
    seq: int,
    t0_us: int,
    config: SyntheticSignalConfig = SyntheticSignalConfig(),
    *,
    rng: Optional[np.random.Generator] = None,
) -> dict:
    """Build one telemetry v1 packet (as a plain dict) of synthetic samples.

    Signal model: dark baseline + sine tone + Gaussian noise, all in mV,
    clearly not a physical measurement. `raw` is a labelled-approximate
    12-bit encoding of `mv` assuming a 3.3 V / 4095-count ADC, purely so the
    raw-counts subplot has something plausible to draw -- it is not a claim
    about real ADC behavior.
    """
    rng = rng or np.random.default_rng()
    n = config.batch_size
    dt_us = _dt_us_grid(n, config.fs_hz)
    t_s = (t0_us + dt_us) / 1e6

    mv = (
        config.dark_mv
        + config.amplitude_mv * np.sin(2.0 * math.pi * config.freq_hz * t_s)
        + rng.normal(0.0, config.noise_std_mv, size=n)
    )
    mv = np.clip(mv, 0.0, 5000.0)
    raw = np.clip(np.round(mv / 3300.0 * 4095.0), 0, 4095).astype(np.int64)

    dropped = 0
    if config.drop_every_n_batches and seq > 0 and seq % config.drop_every_n_batches == 0:
        dropped = 1

    return {
        "v": 1,
        "seq": seq,
        "t0_us": int(t0_us),
        "fs_hz": config.fs_hz,
        "gain_ohm": config.gain_ohm,
        "dropped": dropped,
        "raw": raw.tolist(),
        "mv": [round(float(x), 3) for x in mv],
        "dt_us": dt_us.tolist(),
        "calibration": SYNTHETIC_CALIBRATION_TAG,
    }


class MockTelemetryServer:
    """websockets server at ws://host:port/ that streams SYNTHETIC batches."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8081,
        config: SyntheticSignalConfig = SyntheticSignalConfig(),
        *,
        max_batches: Optional[int] = None,
    ):
        self.host = host
        self.port = port
        self.config = config
        self.max_batches = max_batches
        self._server = None
        self._t0_us_base = 0

    async def _handler(self, websocket):
        logger.info("SYNTHETIC client connected from %s", websocket.remote_address)
        rng = np.random.default_rng(self.config.seed)
        seq = 0
        batch_period_s = self.config.batch_size / self.config.fs_hz
        t0_us = 0
        cumulative_dropped = 0
        try:
            while self.max_batches is None or seq < self.max_batches:
                packet = make_synthetic_packet(seq, t0_us, self.config, rng=rng)
                cumulative_dropped += packet["dropped"]
                packet["dropped"] = cumulative_dropped
                await websocket.send(json.dumps(packet))
                seq += 1
                t0_us += int(round(batch_period_s * 1e6))
                await asyncio.sleep(batch_period_s)
        except websockets.exceptions.ConnectionClosed:
            logger.info("SYNTHETIC client disconnected")

    async def serve_forever(self) -> None:
        async with websockets.serve(self._handler, self.host, self.port):
            logger.info("SYNTHETIC mock server listening on ws://%s:%d/", self.host, self.port)
            await asyncio.Future()  # run until cancelled


def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SYNTHETIC telemetry v1 mock server (no hardware).")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8081)
    p.add_argument("--fs-hz", type=float, default=4000.0)
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--gain-ohm", type=int, default=100_000, choices=[10_000, 100_000, 1_000_000])
    p.add_argument("--dark-mv", type=float, default=DEFAULT_DARK_MV)
    p.add_argument("--amplitude-mv", type=float, default=50.0)
    p.add_argument("--freq-hz", type=float, default=10.0)
    p.add_argument("--noise-std-mv", type=float, default=2.0)
    p.add_argument("--drop-every-n-batches", type=int, default=0)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--max-batches", type=int, default=None, help="stop after N batches per client (testing)")
    return p.parse_args(argv)


def main(argv=None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s SYNTHETIC %(message)s")
    args = _parse_args(argv)
    config = SyntheticSignalConfig(
        fs_hz=args.fs_hz,
        batch_size=args.batch_size,
        gain_ohm=args.gain_ohm,
        dark_mv=args.dark_mv,
        amplitude_mv=args.amplitude_mv,
        freq_hz=args.freq_hz,
        noise_std_mv=args.noise_std_mv,
        drop_every_n_batches=args.drop_every_n_batches,
        seed=args.seed,
    )
    server = MockTelemetryServer(args.host, args.port, config, max_batches=args.max_batches)
    asyncio.run(server.serve_forever())


if __name__ == "__main__":
    main()
