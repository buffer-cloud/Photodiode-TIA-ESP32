"""Timestamp-aware, single-frequency digital lock-in estimator.

The input is an ADC-pin voltage time series, not inferred optical power.
Use a measured electrical or optical reference before making physical claims.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LockInResult:
    amplitude: float
    phase_rad: float
    dc: float
    residual_rms: float
    amplitude_se: float
    samples: int
    frequency_hz: float


def estimate(t_s, values, frequency_hz: float) -> LockInResult:
    """Fit DC + cosine + sine using actual timestamps.

    Amplitude is peak amplitude in the same unit as ``values``. The standard
    error assumes independent, equal-variance residuals; it is descriptive,
    not a substitute for repeated hardware trials with correlated noise.
    """
    t = np.asarray(t_s, dtype=float)
    y = np.asarray(values, dtype=float)
    if t.ndim != 1 or y.ndim != 1 or len(t) != len(y) or len(t) < 8:
        raise ValueError("timestamps and values must be equal-length 1D arrays with at least 8 samples")
    if not np.isfinite(t).all() or not np.isfinite(y).all() or not np.isfinite(frequency_hz) or frequency_hz <= 0:
        raise ValueError("all data and the positive reference frequency must be finite")
    if np.any(np.diff(t) <= 0):
        raise ValueError("timestamps must be strictly increasing; split gaps and reboot epochs first")
    phase = 2 * np.pi * frequency_hz * (t - t[0])
    design = np.column_stack((np.ones(len(t)), np.cos(phase), np.sin(phase)))
    beta, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
    if rank != 3 or np.linalg.cond(design) > 1e6:
        raise ValueError("reference is not identifiable over this timestamp window")
    residual = y - design @ beta
    amplitude = float(np.hypot(beta[1], beta[2]))
    sigma2 = float(np.dot(residual, residual) / (len(t) - 3))
    cov = sigma2 * np.linalg.inv(design.T @ design)
    if amplitude > 0:
        gradient = np.array([beta[1], beta[2]]) / amplitude
        amplitude_se = float(np.sqrt(max(0.0, gradient @ cov[1:, 1:] @ gradient)))
    else:
        amplitude_se = float(np.sqrt(max(0.0, np.trace(cov[1:, 1:]))))
    return LockInResult(
        amplitude=amplitude,
        phase_rad=float(np.arctan2(-beta[2], beta[1])),
        dc=float(beta[0]),
        residual_rms=float(np.sqrt(np.mean(residual**2))),
        amplitude_se=amplitude_se,
        samples=len(t),
        frequency_hz=frequency_hz,
    )
