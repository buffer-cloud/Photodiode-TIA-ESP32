"""DMM piecewise-linear ADC-pin voltage correction and photocurrent reconstruction.

Per docs/design-contract.md "Interface lock additions": calibration is a
DMM multi-point user calibration (DC source -> TP_ADC, >=5 points across
0.25-2.40 V) stored as a piecewise-linear correction table and applied here
in Python; firmware only reports a `calibration` provenance *string*, it does
not apply the DMM table itself. Gain (photocurrent) calibration additionally
needs a measured RF and a measured dark baseline -- both are explicit,
required inputs; nothing here assumes a nominal/ideal value silently.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence, Union

import numpy as np

from .labels import CALCULATED, MEASURED, Labeled

ArrayLike = Union[float, Sequence[float], np.ndarray]


class CalibrationError(ValueError):
    pass


@dataclass(frozen=True)
class CalibrationTable:
    """Piecewise-linear DMM correction table.

    `x` is the raw reading axis (either firmware-reported ADC-pin mV, or raw
    12-bit counts -- see `x_mode`); `y` is the DMM ground-truth mV at TP_ADC
    for each of those points. Both arrays are sorted ascending by x.
    """

    x: np.ndarray
    y: np.ndarray
    x_mode: str  # "mv" or "counts"
    provenance: str = ""

    def __post_init__(self):
        if self.x_mode not in ("mv", "counts"):
            raise CalibrationError(f"x_mode must be 'mv' or 'counts', got {self.x_mode!r}")
        if not np.all(np.isfinite(self.x)) or not np.all(np.isfinite(self.y)):
            raise CalibrationError("calibration points must be finite")
        if len(self.x) != len(self.y):
            raise CalibrationError("x and y must have equal length")
        if len(self.x) < 2:
            raise CalibrationError("need at least 2 calibration points for interpolation")
        if np.any(np.diff(self.x) <= 0):
            raise CalibrationError("x values must be strictly increasing (deduplicate/sort input)")

    def correct(self, x_raw: ArrayLike) -> np.ndarray:
        """Return DMM-corrected pin voltage (mV) for raw reading(s) `x_raw`.

        Uses linear interpolation between measured calibration points.
        Out-of-range inputs return NaN so uncalibrated voltages cannot appear
        as valid calibrated samples. Use in_range() to flag them explicitly.
        """
        arr = np.atleast_1d(np.asarray(x_raw, dtype=float))
        return np.interp(arr, self.x, self.y, left=np.nan, right=np.nan)

    def in_range(self, x_raw: ArrayLike) -> np.ndarray:
        """Boolean mask: True where x_raw falls within the calibrated span."""
        arr = np.atleast_1d(np.asarray(x_raw, dtype=float))
        return (arr >= self.x[0]) & (arr <= self.x[-1])

    @classmethod
    def from_csv(cls, path: Union[str, Path]) -> "CalibrationTable":
        """Load a calibration table from CSV.

        Expected header: either `raw_mv_reported,dmm_mv` or
        `raw_counts,dmm_mv`. Rows are sorted by the raw column; the CSV path
        (basename) is recorded as provenance.
        """
        path = Path(path)
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise CalibrationError(f"{path}: empty CSV, no header row")
            fields = set(reader.fieldnames)
            if "raw_mv_reported" in fields:
                x_mode = "mv"
                x_key = "raw_mv_reported"
            elif "raw_counts" in fields:
                x_mode = "counts"
                x_key = "raw_counts"
            else:
                raise CalibrationError(
                    f"{path}: header must contain 'raw_mv_reported' or 'raw_counts', "
                    f"got {reader.fieldnames}"
                )
            if "dmm_mv" not in fields:
                raise CalibrationError(f"{path}: header must contain 'dmm_mv', got {reader.fieldnames}")

            rows = []
            for i, row in enumerate(reader):
                try:
                    rows.append((float(row[x_key]), float(row["dmm_mv"])))
                except (TypeError, ValueError) as exc:
                    raise CalibrationError(f"{path}: bad numeric value on data row {i}: {row}") from exc

        if len(rows) < 5:
            raise CalibrationError(
                f"{path}: design contract requires >=5 calibration points, got {len(rows)}"
            )
        rows.sort(key=lambda pair: pair[0])
        xs = np.array([r[0] for r in rows], dtype=float)
        ys = np.array([r[1] for r in rows], dtype=float)
        if np.any(np.diff(xs) <= 0):
            raise CalibrationError(f"{path}: duplicate raw values after sorting, cannot interpolate")
        return cls(x=xs, y=ys, x_mode=x_mode, provenance=f"MEASURED DMM table: {path.name}")

    @classmethod
    def identity(cls, x_mode: str = "mv") -> "CalibrationTable":
        """A pass-through table (no correction applied) for use before calibration exists."""
        return cls(
            x=np.array([0.0, MV_IDENTITY_SPAN]),
            y=np.array([0.0, MV_IDENTITY_SPAN]),
            x_mode=x_mode,
            provenance="UNCALIBRATED identity table -- no DMM correction applied",
        )


MV_IDENTITY_SPAN = 5000.0


@dataclass(frozen=True)
class DarkBaseline:
    """Explicit dark (no-light) baseline voltage at TP_ADC, required for I reconstruction.

    Per docs/design-contract.md: VOUT = VREF - (IPHOTO + IDARK) * RF, so the
    baseline captured here already includes the dark-current term; only the
    delta from this baseline is attributed to IPHOTO by `photocurrent_a`.
    """

    v_dark_mv: float
    n_samples: int
    std_mv: float
    provenance: str  # e.g. "MEASURED: session 20260101-000000, RF=100k, LED off"

    def as_labeled(self) -> Labeled:
        return Labeled(
            value=self.v_dark_mv,
            label=MEASURED,
            unit="mV",
            provenance=f"{self.provenance}; n={self.n_samples}, std={self.std_mv:.4g} mV",
        )


def dark_baseline_from_samples(mv_samples: ArrayLike, provenance: str) -> DarkBaseline:
    """Build a DarkBaseline from a block of dark-condition mV samples."""
    arr = np.asarray(mv_samples, dtype=float)
    if arr.size == 0:
        raise CalibrationError("cannot compute a dark baseline from zero samples")
    if not np.all(np.isfinite(arr)):
        raise CalibrationError("dark baseline samples contain non-finite values")
    return DarkBaseline(
        v_dark_mv=float(np.mean(arr)),
        n_samples=int(arr.size),
        std_mv=float(np.std(arr)),
        provenance=provenance,
    )


def photocurrent_a(
    v_mv: ArrayLike,
    baseline: DarkBaseline,
    rf_measured_ohm: float,
    *,
    rf_label: str = MEASURED,
) -> np.ndarray:
    """Reconstruct photocurrent (A) from calibrated pin voltage (mV).

    I = (V_dark_baseline - V) / RF_measured

    `rf_measured_ohm` must be an explicit, named value -- pass the nominal
    resistor value with `rf_label=CALCULATED` if no bench measurement of RF
    exists yet, so downstream labelling stays honest; the default assumes a
    MEASURED RF per the design contract's "Gain calibration uses measured RF
    plus a measured dark baseline."
    """
    if not np.isfinite(rf_measured_ohm) or rf_measured_ohm <= 0:
        raise CalibrationError(f"rf_measured_ohm must be positive, got {rf_measured_ohm}")
    arr = np.atleast_1d(np.asarray(v_mv, dtype=float))
    v_delta_v = (baseline.v_dark_mv - arr) / 1000.0
    return v_delta_v / rf_measured_ohm


def photocurrent_labeled(
    v_mv: ArrayLike,
    baseline: DarkBaseline,
    rf_measured_ohm: float,
    rf_label: str = MEASURED,
) -> Labeled:
    """Same reconstruction as photocurrent_a, wrapped with an evidence label.

    The overall label is MEASURED only if both the baseline and RF are
    MEASURED; if RF is CALCULATED (nominal, unverified), the result is
    downgraded to CALCULATED so it is never mistaken for a bench result.
    """
    i_a = photocurrent_a(v_mv, baseline, rf_measured_ohm, rf_label=rf_label)
    overall = MEASURED if rf_label == MEASURED else CALCULATED
    return Labeled(
        value=i_a,
        label=overall,
        unit="A",
        provenance=(
            f"baseline={baseline.provenance}; RF={rf_measured_ohm} ohm [{rf_label}]"
        ),
    )
