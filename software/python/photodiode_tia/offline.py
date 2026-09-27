"""Small command-line front end for recorded session analyses."""
import argparse
import json
import numpy as np
from . import analysis, sessions


def main(kind, argv=None):
    parser = argparse.ArgumentParser(description=f"{kind}: CALCULATED from recorded ADC-pin data")
    parser.add_argument("session", help="directory with samples.csv and metadata.json")
    parser.add_argument("--epoch", type=int, default=0)
    parser.add_argument("--dark-mv", type=float)
    parser.add_argument("--rf-ohm", type=float)
    parser.add_argument("--input-amplitude-ua", type=float, help="Known sinusoidal current amplitude for response point")
    args = parser.parse_args(argv)
    epochs, metadata = sessions.load_session(args.session)
    epoch = next((e for e in epochs if e.epoch == args.epoch), None)
    if epoch is None:
        parser.error("requested epoch absent")
    result = {"evidence": "SYNTHETIC" if metadata.get("synthetic") else "CALCULATED from recorded samples; bench provenance requires review", "epoch": epoch.epoch}
    if kind == "gain":
        if args.dark_mv is None or args.rf_ohm is None or not np.isfinite(args.rf_ohm) or args.rf_ohm <= 0:
            parser.error("gain requires explicit --dark-mv and positive --rf-ohm (use measured values)")
        current = (args.dark_mv - epoch.mv) / (1000 * args.rf_ohm)
        result.update(mean_current_a=float(current.mean()), rf_ohm=args.rf_ohm, dark_mv=args.dark_mv)
    else:
        spectrum = analysis.fft_spectrum(epoch.t_us, epoch.mv, epoch.fs_hz)
        result.update(dominant_hz=spectrum.dominant_freq_hz, actual_fs_hz=spectrum.fs_used_hz)
        if kind == "noise":
            result.update(vars(analysis.noise_summary(epoch.mv, spectrum)))
        elif kind == "frequency_response":
            if args.input_amplitude_ua is None or args.input_amplitude_ua <= 0:
                parser.error("response point requires positive --input-amplitude-ua; repeat over a bench sweep")
            peak = float(spectrum.amplitude[1:].max())
            result.update(output_amplitude_mv=peak, transimpedance_magnitude_ohm=1000 * peak / args.input_amplitude_ua,
                          note="Single spectral peak estimate; excludes DC; off-bin leakage and analog filter affect magnitude")
        else:
            result.update(peak_amplitude_mv=float(spectrum.amplitude[1:].max()))
    print(json.dumps(result, indent=2, allow_nan=False))
