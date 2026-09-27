"""Session recorder: timestamped CSV + metadata JSON for a batch stream.

Sessions are written under software/python/sessions/YYYYmmdd-HHMMSS/, which
is gitignored (see .gitignore: `software/python/sessions/`). This is
deliberately separate from measurements/, which is reserved for reviewed,
intentionally-published hardware data -- recorder.py never writes there and
mock_server.py (SYNTHETIC) sessions must not be copied there either.
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from . import protocol

CSV_FIELDS = ("host_time", "seq", "t_us", "raw", "mv", "gain_ohm", "fs_hz", "epoch", "dropped", "seq_gap", "seq_reordered", "dropped_delta", "calibration")

DEFAULT_SESSIONS_ROOT = Path(__file__).resolve().parents[1] / "sessions"


def new_session_dir(root: Path = DEFAULT_SESSIONS_ROOT, *, when: Optional[datetime] = None) -> Path:
    when = when or datetime.now()
    name = when.strftime("%Y%m%d-%H%M%S-%f")
    path = root / name
    path.mkdir(parents=True, exist_ok=False)
    return path


@dataclass
class SessionRecorder:
    """Writes one CSV row per sample and a metadata.json summary on close().

    Usage:
        rec = SessionRecorder(root=..., notes="dark noise baseline", synthetic=False)
        for batch, event in client.stream():
            rec.write_batch(batch, event)
        rec.close()
    """

    root: Path = DEFAULT_SESSIONS_ROOT
    notes: str = ""
    calibration_provenance: str = ""
    synthetic: bool = False
    session_dir: Path = field(init=False)
    _csv_file: Any = field(init=False, default=None)
    _writer: Any = field(init=False, default=None)
    _rows_written: int = field(init=False, default=0)
    _epoch_state: protocol.EpochState = field(init=False, default_factory=lambda: protocol.INITIAL_EPOCH_STATE)
    _gains_seen: set = field(init=False, default_factory=set)
    _fs_seen: set = field(init=False, default_factory=set)
    _calibration_strings_seen: set = field(init=False, default_factory=set)
    _seq_gaps_total: int = field(init=False, default=0)
    _dropped_last: Optional[int] = field(init=False, default=None)
    _started_at: str = field(init=False, default="")

    def __post_init__(self):
        self.session_dir = new_session_dir(self.root)
        self._started_at = datetime.now(timezone.utc).isoformat()
        csv_path = self.session_dir / "samples.csv"
        self._csv_file = csv_path.open("w", newline="")
        self._writer = csv.writer(self._csv_file)
        self._writer.writerow(CSV_FIELDS)

    def write_batch(self, batch: protocol.Batch, event: Optional[protocol.BatchEvent] = None) -> None:
        if event is None:
            self._epoch_state, event = protocol.classify_batch(self._epoch_state, batch)
        else:
            self._epoch_state = protocol.EpochState(
                epoch=event.epoch,
                last_seq=batch.seq,
                last_t0_us=batch.t0_us,
                last_dropped=batch.dropped,
            )
        self._seq_gaps_total += event.seq_gap
        self._dropped_last = batch.dropped
        self._gains_seen.add(batch.gain_ohm)
        self._fs_seen.add(batch.fs_hz)
        if batch.calibration:
            self._calibration_strings_seen.add(batch.calibration)
            if "SYNTHETIC" in batch.calibration:
                # Auto-detect mock_server.py sources so metadata.json never mislabels
                # a synthetic session as real hardware, even if the caller forgot
                # to pass synthetic=True explicitly.
                self.synthetic = True

        host_time = time.time()
        for dt, raw, mv in zip(batch.dt_us, batch.raw, batch.mv):
            self._writer.writerow(
                (
                    f"{host_time:.6f}",
                    batch.seq,
                    batch.t0_us + dt,
                    raw,
                    mv,
                    batch.gain_ohm,
                    batch.fs_hz,
                    event.epoch,
                    batch.dropped, event.seq_gap, event.seq_reordered, event.dropped_delta, batch.calibration or "",
                )
            )
            self._rows_written += 1

    def close(self, extra_metadata: Optional[Dict[str, Any]] = None) -> Path:
        if self._csv_file is not None:
            self._csv_file.close()
            self._csv_file = None

        metadata: Dict[str, Any] = {
            "started_at_utc": self._started_at,
            "closed_at_utc": datetime.now(timezone.utc).isoformat(),
            "rows_written": self._rows_written,
            "epochs_seen": self._epoch_state.epoch + 1,
            "seq_gaps_total": self._seq_gaps_total,
            "dropped_last_reported": self._dropped_last,
            "gain_ohm_seen": sorted(self._gains_seen),
            "fs_hz_seen": sorted(self._fs_seen),
            "firmware_calibration_provenance": sorted(self._calibration_strings_seen),
            "python_calibration_provenance": self.calibration_provenance,
            "notes": self.notes,
            "synthetic": self.synthetic,
            "csv_fields": list(CSV_FIELDS),
            "protocol_version": protocol.PROTOCOL_VERSION,
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        meta_path = self.session_dir / "metadata.json"
        with meta_path.open("w") as f:
            json.dump(metadata, f, indent=2, sort_keys=True)
            f.write("\n")
        return self.session_dir


def read_session_csv(session_dir: Path):
    """Read samples.csv from a session dir back into a pandas DataFrame."""
    import pandas as pd

    return pd.read_csv(Path(session_dir) / "samples.csv")


def read_session_metadata(session_dir: Path) -> Dict[str, Any]:
    with (Path(session_dir) / "metadata.json").open() as f:
        return json.load(f)
