"""Signal statistics, timing-quality checks and FFT/noise analysis.

Per docs/protocol/README.md: "Consumers inspect actual timestamps, sequence
gaps and dropped before FFT/noise analysis" and "Never join two boot epochs
into a single uniformly sampled record." This module therefore always works
from actual sample timestamps (t0_us + dt_us), always splits multi-batch
data into epochs first, and refuses (rather than silently mis-scales) an
FFT over a record with excessive jitter or gaps unless the caller
explicitly asks to resample.

All outputs from real hardware are CALCULATED from MEASURED samples --
callers/scripts are responsible for attaching the right evidence label
(see photodiode_tia.labels) when presenting results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np
from scipy.signal import windows as scipy_windows

from . import protocol

DEFAULT_SCIENCE_BAND_HZ: Tuple[float, float] = (0.0, 100.0)  # DC-100 Hz useful band per design contract


class AnalysisError(ValueError):
    pass


# --------------------------------------------------------------------------
# Assembling batches into per-epoch time series
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class TimeSeries:
    """One device epoch worth of samples for a single field ('raw' or 'mv')."""

    t_us: np.ndarray  # absolute boot-time microseconds, strictly increasing
    y: np.ndarray
    field: str
    epoch: int
    fs_nominal_hz: float
    gain_ohm: int
    dropped_total: int
    seq_gaps_total: int

    @property
    def n(self) -> int:
        return len(self.y)


def split_into_epochs(batches: Sequence[protocol.Batch]) -> List[List[protocol.Batch]]:
    """Group a batch stream into contiguous per-epoch lists using classify_batch."""
    state = protocol.INITIAL_EPOCH_STATE
    epochs: List[List[protocol.Batch]] = []
    for batch in batches:
        state, event = protocol.classify_batch(state, batch)
        if event.new_epoch or not epochs:
            epochs.append([])
        epochs[-1].append(batch)
    return epochs


def assemble_epoch(batches: Sequence[protocol.Batch], field: str = "mv") -> TimeSeries:
    """Concatenate one epoch's batches into a single TimeSeries.

    Arrival order is preserved, and discontinuities or setting changes are
    rejected. Callers must first use split_into_epochs; sorting could hide
    a reboot or sequence regression.
    """
    if not batches:
        raise AnalysisError("cannot assemble an empty batch list")
    if field not in ("raw", "mv"):
        raise AnalysisError(f"field must be 'raw' or 'mv', got {field!r}")

    ordered = list(batches)
    if len({(b.fs_hz, b.gain_ohm) for b in ordered}) != 1:
        raise AnalysisError("sampling rate or gain changed within record")
    t_chunks = [np.asarray(b.timestamps_us(), dtype=np.int64) for b in ordered]
    y_chunks = [np.asarray(getattr(b, field), dtype=float) for b in ordered]
    t_us = np.concatenate(t_chunks)
    y = np.concatenate(y_chunks)

    if np.any(np.diff(t_us) <= 0):
        raise AnalysisError(
            "assembled epoch has non-increasing timestamps; batches overlap or are duplicated"
        )

    state = protocol.INITIAL_EPOCH_STATE
    seq_gaps_total = 0
    for b in ordered:
        state, event = protocol.classify_batch(state, b)
        if event.new_epoch:
            raise AnalysisError("assemble_epoch received batches spanning more than one epoch")
        if event.new_epoch or event.seq_reordered or event.seq_gap or event.dropped_delta != 0:
            raise AnalysisError("stream discontinuity: " + "; ".join(event.reasons))
        seq_gaps_total += event.seq_gap

    return TimeSeries(
        t_us=t_us,
        y=y,
        field=field,
        epoch=0,
        fs_nominal_hz=ordered[0].fs_hz,
        gain_ohm=ordered[0].gain_ohm,
        dropped_total=ordered[-1].dropped,
        seq_gaps_total=seq_gaps_total,
    )


# --------------------------------------------------------------------------
# Basic time-domain statistics
# --------------------------------------------------------------------------


def mean(y: np.ndarray) -> float:
    return float(np.mean(y))


def rms(y: np.ndarray) -> float:
    """Full RMS including any DC offset: sqrt(mean(y**2))."""
    arr = np.asarray(y, dtype=float)
    return float(np.sqrt(np.mean(np.square(arr))))


def ac_rms(y: np.ndarray) -> float:
    """AC-coupled RMS (DC removed): standard deviation of y."""
    return float(np.std(np.asarray(y, dtype=float)))


def peak_to_peak(y: np.ndarray) -> float:
    arr = np.asarray(y, dtype=float)
    return float(np.max(arr) - np.min(arr))


@dataclass(frozen=True)
class TimeDomainStats:
    n: int
    mean: float
    rms: float
    ac_rms: float
    peak_to_peak: float
    minimum: float
    maximum: float


def time_domain_stats(y: np.ndarray) -> TimeDomainStats:
    arr = np.asarray(y, dtype=float)
    if arr.size == 0:
        raise AnalysisError("cannot compute statistics on an empty array")
    if not np.all(np.isfinite(arr)):
        raise AnalysisError("array contains non-finite values")
    return TimeDomainStats(
        n=int(arr.size),
        mean=mean(arr),
        rms=rms(arr),
        ac_rms=ac_rms(arr),
        peak_to_peak=peak_to_peak(arr),
        minimum=float(np.min(arr)),
        maximum=float(np.max(arr)),
    )


# --------------------------------------------------------------------------
# Timing quality
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class TimingQuality:
    n: int
    fs_nominal_hz: float
    fs_actual_hz: float
    dt_mean_us: float
    dt_std_us: float
    jitter_ratio: float  # dt_std / dt_mean
    max_gap_us: float
    has_gaps: bool
    is_uniform: bool
    span_s: float


def check_timing(
    t_us: np.ndarray,
    fs_nominal_hz: float,
    *,
    jitter_tolerance: float = 0.05,
    gap_tolerance_factor: float = 1.5,
) -> TimingQuality:
    """Assess whether a timestamp series is uniform enough for a plain FFT.

    `jitter_tolerance` bounds dt_std/dt_mean; `gap_tolerance_factor` bounds
    the largest single inter-sample gap relative to the expected spacing.
    Either violation marks the series non-uniform.
    """
    t = np.asarray(t_us, dtype=float)
    if t.size < 2:
        raise AnalysisError("need at least 2 samples to assess timing")
    if not np.all(np.isfinite(t)) or not np.isfinite(fs_nominal_hz) or fs_nominal_hz <= 0:
        raise AnalysisError("timestamps and sample rate must be finite; rate must be positive")
    dt = np.diff(t)
    if np.any(dt <= 0):
        raise AnalysisError("timestamps must be strictly increasing")

    dt_mean = float(np.mean(dt))
    dt_std = float(np.std(dt))
    jitter_ratio = dt_std / dt_mean if dt_mean > 0 else float("inf")
    max_gap = float(np.max(dt))
    expected_dt = 1e6 / fs_nominal_hz
    has_gaps = max_gap > expected_dt * gap_tolerance_factor
    is_uniform = (jitter_ratio <= jitter_tolerance) and not has_gaps
    fs_actual = 1e6 / dt_mean if dt_mean > 0 else float("nan")
    span_s = float((t[-1] - t[0]) / 1e6)

    return TimingQuality(
        n=int(t.size),
        fs_nominal_hz=fs_nominal_hz,
        fs_actual_hz=fs_actual,
        dt_mean_us=dt_mean,
        dt_std_us=dt_std,
        jitter_ratio=jitter_ratio,
        max_gap_us=max_gap,
        has_gaps=has_gaps,
        is_uniform=is_uniform,
        span_s=span_s,
    )


def resample_uniform(t_us: np.ndarray, y: np.ndarray, fs_hz: float) -> Tuple[np.ndarray, np.ndarray]:
    """Linearly resample (t_us, y) onto a uniform grid at fs_hz.

    Only called when a caller explicitly opts in (resample=True) -- silent
    resampling would misrepresent an irregularly sampled record as clean
    data. Returns (t_us_uniform, y_uniform).
    """
    t = np.asarray(t_us, dtype=float)
    y = np.asarray(y, dtype=float)
    dt_us = 1e6 / fs_hz
    n = int(np.floor((t[-1] - t[0]) / dt_us)) + 1
    t_new = t[0] + np.arange(n) * dt_us
    y_new = np.interp(t_new, t, y)
    return t_new, y_new


# --------------------------------------------------------------------------
# FFT with window-corrected amplitude/PSD scaling
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FFTResult:
    freqs_hz: np.ndarray
    amplitude: np.ndarray  # linear amplitude spectrum, same units as input y
    psd: np.ndarray  # power spectral density, (unit)^2/Hz, single-sided
    fs_used_hz: float
    window: str
    n: int
    dominant_freq_hz: float
    timing: TimingQuality
    resampled: bool
    notes: Tuple[str, ...] = ()


def fft_spectrum(
    t_us: np.ndarray,
    y: np.ndarray,
    fs_nominal_hz: float,
    *,
    window: str = "hann",
    detrend: bool = True,
    allow_nonuniform: bool = False,
    resample: bool = False,
) -> FFTResult:
    """Single-sided amplitude/PSD spectrum of (t_us, y) using an actual-timestamp check.

    Refuses (raises AnalysisError) on non-uniform timing unless the caller
    passes `allow_nonuniform=True` (proceed using the mean actual fs, with a
    warning note) or `resample=True` (linearly resample to a uniform grid
    at fs_nominal_hz first, with a warning note). Default behavior refuses.
    """
    y = np.asarray(y, dtype=float)
    if y.ndim != 1 or len(y) != len(t_us) or not np.all(np.isfinite(y)):
        raise AnalysisError("signal must be finite, one dimensional and match timestamps")
    timing = check_timing(t_us, fs_nominal_hz)
    notes = []
    resampled = False

    if not timing.is_uniform:
        msg = (
            f"non-uniform timing: jitter_ratio={timing.jitter_ratio:.3g} "
            f"(tolerance 0.05), has_gaps={timing.has_gaps}, max_gap_us={timing.max_gap_us:.1f}"
        )
        if resample:
            t_us, y = resample_uniform(t_us, y, fs_nominal_hz)
            resampled = True
            notes.append(f"resampled to uniform {fs_nominal_hz} Hz grid because {msg}")
            fs_used = fs_nominal_hz
        elif allow_nonuniform:
            notes.append(f"proceeding on non-uniform data ({msg}); scaling uses mean actual fs")
            fs_used = timing.fs_actual_hz
        else:
            raise AnalysisError(
                f"refusing FFT on non-uniform timing ({msg}); "
                "pass resample=True or allow_nonuniform=True to override"
            )
    else:
        fs_used = timing.fs_actual_hz

    y = np.asarray(y, dtype=float)
    n = y.size
    if n < 8:
        raise AnalysisError(f"need at least 8 samples for a meaningful FFT, got {n}")

    y_proc = y - np.mean(y) if detrend else y

    if window == "hann":
        w = scipy_windows.hann(n, sym=False)
    elif window == "none":
        w = np.ones(n)
    else:
        raise AnalysisError(f"unsupported window {window!r}, expected 'hann' or 'none'")

    y_win = y_proc * w
    spectrum = np.fft.rfft(y_win)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs_used)

    sum_w = np.sum(w)
    sum_w2 = np.sum(w * w)

    amplitude = np.abs(spectrum) * (2.0 / sum_w)
    amplitude[0] /= 2.0
    if n % 2 == 0:
        amplitude[-1] /= 2.0

    psd = (np.abs(spectrum) ** 2) * (2.0 / (fs_used * sum_w2))
    psd[0] /= 2.0
    if n % 2 == 0:
        psd[-1] /= 2.0

    if freqs.size > 1:
        dominant_idx = 1 + int(np.argmax(amplitude[1:]))
        dominant_freq = float(freqs[dominant_idx])
    else:
        dominant_freq = 0.0

    return FFTResult(
        freqs_hz=freqs,
        amplitude=amplitude,
        psd=psd,
        fs_used_hz=fs_used,
        window=window,
        n=n,
        dominant_freq_hz=dominant_freq,
        timing=timing,
        resampled=resampled,
        notes=tuple(notes),
    )


# --------------------------------------------------------------------------
# Noise estimates
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class NoiseSummary:
    std: float  # broadband time-domain std (same unit as input y)
    band_hz: Tuple[float, float]
    band_noise_rms: float  # sqrt(integral of PSD over band), same unit as y
    noise_density_median: float  # median sqrt(PSD) over band, unit/sqrt(Hz)
    unit: str


def integrate_psd_band(
    freqs_hz: np.ndarray, psd: np.ndarray, band_hz: Tuple[float, float]
) -> float:
    """Integrate PSD over [f_lo, f_hi] (Hz) via trapezoidal rule; returns power (unit^2)."""
    f_lo, f_hi = band_hz
    if f_lo < 0 or f_hi <= f_lo:
        raise AnalysisError(f"invalid band {band_hz}")
    mask = (freqs_hz >= f_lo) & (freqs_hz <= f_hi)
    if np.count_nonzero(mask) < 2:
        raise AnalysisError(f"band {band_hz} contains fewer than 2 FFT bins; widen band or record")
    return float(np.trapezoid(psd[mask], freqs_hz[mask]))


def noise_summary(
    y: np.ndarray,
    fft_result: FFTResult,
    band_hz: Tuple[float, float] = DEFAULT_SCIENCE_BAND_HZ,
    unit: str = "mV",
) -> NoiseSummary:
    """Combine time-domain std with PSD-integrated in-band noise and noise density."""
    band_power = integrate_psd_band(fft_result.freqs_hz, fft_result.psd, band_hz)
    f_lo, f_hi = band_hz
    mask = (fft_result.freqs_hz >= f_lo) & (fft_result.freqs_hz <= f_hi)
    density_median = float(np.median(np.sqrt(fft_result.psd[mask])))
    return NoiseSummary(
        std=ac_rms(y),
        band_hz=band_hz,
        band_noise_rms=float(np.sqrt(band_power)),
        noise_density_median=density_median,
        unit=unit,
    )
