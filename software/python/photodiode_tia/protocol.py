"""Telemetry v1 packet parsing and validation.

Implements the wire format documented in docs/protocol/telemetry-v1.schema.json
and docs/protocol/README.md, plus the "application validation" that the schema
explicitly defers to consumers: equal array lengths, strictly increasing
dt_us starting at zero, finite numbers, sequence-number gaps, boot-time
(t0_us) regressions that start a new device epoch, and cumulative-`dropped`
accounting.

Every function here is pure: given the same input it returns the same
output, and none of them perform I/O. Statefulness across a stream of
batches (epoch tracking) is modeled explicitly with an immutable
``EpochState`` that callers thread through ``classify_batch``.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence, Tuple, Union

PROTOCOL_VERSION = 1
GAIN_OHMS = (10_000, 100_000, 1_000_000)
FS_HZ_MIN = 1000.0
FS_HZ_MAX = 8000.0
RAW_MIN = 0
RAW_MAX = 4095
MV_MIN = 0.0
MV_MAX = 5000.0
MAX_ITEMS = 256
REQUIRED_KEYS = ("v", "seq", "t0_us", "fs_hz", "gain_ohm", "dropped", "raw", "mv", "dt_us")


class ProtocolError(ValueError):
    """Raised when a packet fails schema or application validation."""

    def __init__(self, issues: Sequence[str]):
        self.issues = list(issues)
        super().__init__("; ".join(self.issues) if self.issues else "invalid packet")


@dataclass(frozen=True)
class Batch:
    """A validated telemetry v1 batch. Arrays are stored as tuples (immutable)."""

    v: int
    seq: int
    t0_us: int
    fs_hz: float
    gain_ohm: int
    dropped: int
    raw: Tuple[int, ...]
    mv: Tuple[float, ...]
    dt_us: Tuple[int, ...]
    calibration: Optional[str] = None

    @property
    def n(self) -> int:
        return len(self.raw)

    def timestamps_us(self) -> Tuple[int, ...]:
        """Absolute boot-time microseconds for each sample: t0_us + dt_us[i]."""
        return tuple(self.t0_us + d for d in self.dt_us)


def _is_bool(x: Any) -> bool:
    return isinstance(x, bool)


def _is_int_like(x: Any) -> bool:
    # JSON ints decode to Python int; reject bool (subclass of int) and float.
    return isinstance(x, int) and not _is_bool(x)


def _is_number(x: Any) -> bool:
    return (isinstance(x, (int, float)) and not _is_bool(x))


def validate_types(obj: Mapping[str, Any]) -> list:
    """Schema-level validation: required keys present, types and ranges correct.

    Returns a list of human-readable issue strings (empty if valid).
    Does not check cross-field/array consistency; see validate_arrays.
    """
    issues = []

    for key in REQUIRED_KEYS:
        if key not in obj:
            issues.append(f"missing required key '{key}'")
    if issues:
        # Further checks would raise KeyError; bail out early.
        return issues

    if not _is_int_like(obj.get("v")) or obj.get("v") != PROTOCOL_VERSION:
        issues.append(f"v must equal {PROTOCOL_VERSION}, got {obj.get('v')!r}")

    seq = obj.get("seq")
    if not _is_int_like(seq) or seq < 0:
        issues.append(f"seq must be a non-negative integer, got {seq!r}")

    t0_us = obj.get("t0_us")
    if not _is_int_like(t0_us) or t0_us < 0:
        issues.append(f"t0_us must be a non-negative integer, got {t0_us!r}")

    fs_hz = obj.get("fs_hz")
    if not _is_number(fs_hz) or not (FS_HZ_MIN <= fs_hz <= FS_HZ_MAX):
        issues.append(f"fs_hz must be a number in [{FS_HZ_MIN}, {FS_HZ_MAX}], got {fs_hz!r}")

    gain_ohm = obj.get("gain_ohm")
    if gain_ohm not in GAIN_OHMS:
        issues.append(f"gain_ohm must be one of {GAIN_OHMS}, got {gain_ohm!r}")

    dropped = obj.get("dropped")
    if not _is_int_like(dropped) or dropped < 0:
        issues.append(f"dropped must be a non-negative integer, got {dropped!r}")

    raw = obj.get("raw")
    if not isinstance(raw, list) or not (1 <= len(raw) <= MAX_ITEMS):
        issues.append(f"raw must be a list of 1..{MAX_ITEMS} items")
    else:
        for i, v in enumerate(raw):
            if not _is_int_like(v) or not (RAW_MIN <= v <= RAW_MAX):
                issues.append(f"raw[{i}] must be an integer in [{RAW_MIN}, {RAW_MAX}], got {v!r}")
                break

    mv = obj.get("mv")
    if not isinstance(mv, list) or not (1 <= len(mv) <= MAX_ITEMS):
        issues.append(f"mv must be a list of 1..{MAX_ITEMS} items")
    else:
        for i, v in enumerate(mv):
            if not _is_number(v) or not (MV_MIN <= v <= MV_MAX) or not math.isfinite(v):
                issues.append(f"mv[{i}] must be a finite number in [{MV_MIN}, {MV_MAX}], got {v!r}")
                break

    dt_us = obj.get("dt_us")
    if not isinstance(dt_us, list) or not (1 <= len(dt_us) <= MAX_ITEMS):
        issues.append(f"dt_us must be a list of 1..{MAX_ITEMS} items")
    else:
        for i, v in enumerate(dt_us):
            if not _is_int_like(v) or v < 0:
                issues.append(f"dt_us[{i}] must be a non-negative integer, got {v!r}")
                break

    calibration = obj.get("calibration")
    if calibration is not None and not isinstance(calibration, str):
        issues.append(f"calibration must be a string if present, got {calibration!r}")

    return issues


def validate_arrays(obj: Mapping[str, Any]) -> list:
    """Application-level validation deferred by the JSON schema.

    Assumes validate_types(obj) already passed (arrays exist and are lists of
    the right item types); still defensive against missing keys.
    """
    issues = []
    raw = obj.get("raw")
    mv = obj.get("mv")
    dt_us = obj.get("dt_us")
    if not (isinstance(raw, list) and isinstance(mv, list) and isinstance(dt_us, list)):
        return ["raw/mv/dt_us must all be lists to check array consistency"]

    lengths = {"raw": len(raw), "mv": len(mv), "dt_us": len(dt_us)}
    if len(set(lengths.values())) != 1:
        issues.append(f"raw/mv/dt_us must have equal length, got {lengths}")

    if dt_us:
        if dt_us[0] != 0:
            issues.append(f"dt_us must start at 0, got {dt_us[0]!r}")
        for i in range(1, len(dt_us)):
            if not (dt_us[i] > dt_us[i - 1]):
                issues.append(
                    f"dt_us must be strictly increasing: dt_us[{i - 1}]={dt_us[i - 1]!r} "
                    f">= dt_us[{i}]={dt_us[i]!r}"
                )
                break

    for name, arr in (("raw", raw), ("mv", mv)):
        for i, v in enumerate(arr):
            if isinstance(v, (int, float)) and not math.isfinite(v):
                issues.append(f"{name}[{i}] is not finite: {v!r}")
                break

    return issues


def build_batch(obj: Mapping[str, Any]) -> Batch:
    """Validate a decoded JSON object and build a Batch, or raise ProtocolError."""
    issues = validate_types(obj)
    if not issues:
        issues = validate_arrays(obj)
    if issues:
        raise ProtocolError(issues)

    return Batch(
        v=obj["v"],
        seq=obj["seq"],
        t0_us=obj["t0_us"],
        fs_hz=float(obj["fs_hz"]),
        gain_ohm=obj["gain_ohm"],
        dropped=obj["dropped"],
        raw=tuple(obj["raw"]),
        mv=tuple(float(x) for x in obj["mv"]),
        dt_us=tuple(obj["dt_us"]),
        calibration=obj.get("calibration"),
    )


def parse_batch(raw: Union[str, bytes, Mapping[str, Any]]) -> Batch:
    """Parse a telemetry v1 packet from JSON text/bytes or an already-decoded dict.

    Raises ProtocolError (with .issues) on any schema or consistency violation,
    or on malformed JSON.
    """
    if isinstance(raw, (str, bytes, bytearray)):
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ProtocolError([f"invalid JSON: {exc}"]) from exc
    else:
        obj = raw

    if not isinstance(obj, Mapping):
        raise ProtocolError([f"packet must decode to a JSON object, got {type(obj).__name__}"])

    return build_batch(obj)


# --------------------------------------------------------------------------
# Multi-batch stream classification: sequence gaps, dropped-counter deltas,
# and boot-time (t0_us) regression -> new device epoch.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EpochState:
    """Immutable tracker state threaded across successive batches."""

    epoch: int = 0
    last_seq: Optional[int] = None
    last_t0_us: Optional[int] = None
    last_dropped: Optional[int] = None


INITIAL_EPOCH_STATE = EpochState()


@dataclass(frozen=True)
class BatchEvent:
    """Diagnostics produced when folding one Batch into an EpochState."""

    epoch: int
    new_epoch: bool
    seq_gap: int  # number of missing sequence numbers before this batch (>=0); 0 for first batch/new epoch
    seq_reordered: bool  # True if seq did not strictly increase within the same epoch
    dropped_delta: int  # change in cumulative dropped count since previous batch in this epoch
    reasons: Tuple[str, ...] = field(default_factory=tuple)


def classify_batch(state: EpochState, batch: Batch) -> Tuple[EpochState, BatchEvent]:
    """Fold `batch` into `state`, returning (new_state, event).

    A new epoch starts when t0_us regresses (goes backwards) relative to the
    previous batch's t0_us, per docs/protocol/README.md: "A boot-time
    regression starts a new device epoch. Never join two boot epochs into a
    single uniformly sampled record."
    """
    reasons = []
    is_new_epoch = state.last_t0_us is not None and batch.t0_us < state.last_t0_us

    if is_new_epoch:
        reasons.append(f"t0_us regressed ({batch.t0_us} < {state.last_t0_us}); starting new epoch")
        epoch = state.epoch + 1
        seq_gap = 0
        seq_reordered = False
        dropped_delta = batch.dropped
    else:
        epoch = state.epoch
        if state.last_seq is None:
            seq_gap = 0
            seq_reordered = False
        elif batch.seq > state.last_seq:
            seq_gap = batch.seq - state.last_seq - 1
            seq_reordered = False
            if seq_gap > 0:
                reasons.append(f"seq gap of {seq_gap} between {state.last_seq} and {batch.seq}")
        else:
            seq_gap = 0
            seq_reordered = True
            reasons.append(f"seq did not increase: {batch.seq} after {state.last_seq}")

        if state.last_dropped is None:
            dropped_delta = batch.dropped
        else:
            dropped_delta = batch.dropped - state.last_dropped
            if dropped_delta < 0:
                reasons.append(
                    f"dropped counter decreased ({batch.dropped} < {state.last_dropped}) "
                    "without a t0_us regression"
                )
            elif dropped_delta > 0:
                reasons.append(f"{dropped_delta} sample(s) dropped since previous batch")

    new_state = EpochState(
        epoch=epoch,
        last_seq=batch.seq,
        last_t0_us=batch.t0_us,
        last_dropped=batch.dropped,
    )
    event = BatchEvent(
        epoch=epoch,
        new_epoch=is_new_epoch,
        seq_gap=seq_gap,
        seq_reordered=seq_reordered,
        dropped_delta=dropped_delta,
        reasons=tuple(reasons),
    )
    return new_state, event
