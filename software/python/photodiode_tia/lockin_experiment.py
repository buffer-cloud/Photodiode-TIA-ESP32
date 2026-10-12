"""Reproducible SYNTHETIC comparison for a phase-sensitive detector.

Run: python -m photodiode_tia.lockin_experiment --output research/phase-sensitive/results
No output from this module is hardware measurement.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from .lockin import estimate


def run(output: Path, *, seed: int = 20261011, trials: int = 40) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    fs_hz = 4000
    reference_hz = 137
    amplitudes_mv = (0, 2, 4, 8, 12, 20)
    rows = []
    for amplitude_mv in amplitudes_mv:
        for trial in range(trials):
            t = np.arange(fs_hz) / fs_hz + rng.normal(0, 5e-6, fs_hz)
            phase = rng.uniform(-np.pi, np.pi)
            ambient_phase = rng.uniform(-np.pi, np.pi)
            y = 1420 + amplitude_mv * np.cos(2 * np.pi * reference_hz * t + phase)
            y += 35 * np.sin(2 * np.pi * 60 * t + ambient_phase)
            y += rng.normal(0, 8, fs_hz)
            y = np.round(y)  # simple 1 mV digitization; not an ESP32 ADC model
            lockin_mv = estimate(t, y, reference_hz).amplitude
            fft_bin_mv = 2 * abs(np.fft.rfft(y - np.mean(y))[reference_hz]) / len(y)
            raw_half_range_mv = (np.percentile(y, 95) - np.percentile(y, 5)) / 2
            rows.append({"true_mv": amplitude_mv, "trial": trial,
                         "lockin_mv": lockin_mv, "fft_bin_mv": fft_bin_mv,
                         "raw_half_range_mv": raw_half_range_mv})

    csv_path = output / "synthetic_trials.csv"
    with csv_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    median_error = {}
    for method in ("lockin_mv", "fft_bin_mv", "raw_half_range_mv"):
        median_error[method] = [float(np.median([abs(r[method] - a) for r in rows if r["true_mv"] == a]))
                                for a in amplitudes_mv]
    null = np.array([r["lockin_mv"] for r in rows if r["true_mv"] == 0])
    threshold = float(np.quantile(null, 0.99))
    detection_rate_at_4mv = float(np.mean([r["lockin_mv"] > threshold for r in rows if r["true_mv"] == 4]))
    summary = {
        "provenance": "SYNTHETIC; not measured optical or ESP32 ADC data",
        "seed": seed, "trials_per_amplitude": trials, "sample_rate_hz": fs_hz,
        "duration_s": 1, "reference_hz": reference_hz,
        "ambient_hz": 60, "ambient_peak_mv": 35, "gaussian_noise_sigma_mv": 8,
        "timestamp_jitter_sigma_us": 5, "digitization_step_mv": 1,
        "amplitudes_mv": amplitudes_mv,
        "median_absolute_error_mv": median_error,
        "null_99th_percentile_threshold_mv": threshold,
        "detection_rate_at_4mv": detection_rate_at_4mv,
        "baseline_definition": "half of the 5th-to-95th percentile raw voltage range; does not know the modulation frequency",
        "fft_definition": "known-frequency 137 Hz DFT bin over the same contiguous one-second window",
        "interpretation_limit": "The FFT is an informed baseline and should agree with the lock-in fit on this nearly uniform contiguous data. No method is claimed novel; hardware trials and stronger controls remain pending.",
    }
    (output / "synthetic_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=160)
    ax.plot(amplitudes_mv, median_error["lockin_mv"], "o-", label="Phase-sensitive fit")
    ax.plot(amplitudes_mv, median_error["fft_bin_mv"], "^-", label="Known-frequency FFT bin")
    ax.plot(amplitudes_mv, median_error["raw_half_range_mv"], "s-", label="Unreferenced raw range")
    ax.set(xlabel="Injected synthetic peak amplitude (mV)", ylabel="Median absolute amplitude error (mV)",
           title="Synthetic 60 Hz interference test — no hardware measurement")
    ax.set_yscale("log")
    ax.set_ylim(0.05, 60)
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "synthetic_comparison.png")
    plt.close(fig)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261011)
    parser.add_argument("--trials", type=int, default=40)
    args = parser.parse_args()
    print(json.dumps(run(args.output, seed=args.seed, trials=args.trials), indent=2))


if __name__ == "__main__":
    main()
