"""Load recorder.py session folders back into per-epoch arrays for offline analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import numpy as np

from . import recorder
from .labels import MEASURED, SYNTHETIC


@dataclass(frozen=True)
class SessionEpoch:
    epoch: int
    t_us: np.ndarray
    raw: np.ndarray
    mv: np.ndarray
    fs_hz: float
    gain_ohm: int

    @property
    def n(self) -> int:
        return len(self.mv)


def load_session(session_dir: Union[str, Path]) -> Tuple[List[SessionEpoch], Dict[str, Any]]:
    """Read samples.csv + metadata.json from a session dir, split by epoch."""
    session_dir = Path(session_dir)
    df = recorder.read_session_csv(session_dir)
    metadata = recorder.read_session_metadata(session_dir)

    epochs: List[SessionEpoch] = []
    for epoch_id, group in df.groupby("epoch"):
        if len(group["fs_hz"].unique()) != 1 or len(group["gain_ohm"].unique()) != 1:
            raise ValueError("gain/rate changes within epoch; select a contiguous fixed-setting record")
        for column in ("seq_gap", "seq_reordered", "dropped_delta"):
            if column not in group or group[column].astype(float).abs().sum() > 0:
                raise ValueError("missing diagnostics or discontinuous record: " + column)
        epochs.append(
            SessionEpoch(
                epoch=int(epoch_id),
                t_us=group["t_us"].to_numpy(dtype=np.int64),
                raw=group["raw"].to_numpy(dtype=float),
                mv=group["mv"].to_numpy(dtype=float),
                fs_hz=float(group["fs_hz"].iloc[0]),
                gain_ohm=int(group["gain_ohm"].iloc[0]),
            )
        )
    epochs.sort(key=lambda e: e.epoch)
    return epochs, metadata


def largest_epoch(epochs: List[SessionEpoch]) -> SessionEpoch:
    if not epochs:
        raise ValueError("session has no epochs/samples")
    return max(epochs, key=lambda e: e.n)


def label_for_session(metadata: Dict[str, Any]) -> str:
    """MEASURED unless the session's own metadata says it came from mock_server.py."""
    return SYNTHETIC if metadata.get("synthetic") else MEASURED
