# Photodiode TIA desktop tools

From this directory, use Python 3.10 or newer:

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest
.venv/bin/python -m photodiode_tia.mock_server --port 8081 --seed 1
```

In another terminal:

```sh
.venv/bin/python -m photodiode_tia.dashboard --host 127.0.0.1 --port 8081 --record
```

For hardware use `--host <ESP32-IP>` (default port 81). A desktop Matplotlib backend such as TkAgg or QtAgg must be installed for interactive windows. `MPLBACKEND=Agg` enables headless operation; use `--duration 3 --save-snapshot dashboard.png`. The mock server is explicitly SYNTHETIC; it does not emulate measured ADC transfer accuracy.

Controls: Connect/Disconnect manage the connection. Start/Stop resume/pause display capture locally, without commanding firmware. `--record` records continuously while connected, including while the display is paused. Save writes the retained display batch buffer (at most 1024 batches), with original telemetry voltage and provenance, to a new timestamped CSV session. Clear empties this buffer and plot. Window changes the visible duration (0–60 seconds). Closing the figure disconnects and closes recording. CSV sessions are in `software/python/sessions/`; they are not published bench measurements.

Raw counts and baseline calibrated ADC-pin millivolts are plotted separately. Firmware `mv` is the Espressif calibration baseline, not an ideal count conversion, light intensity or photocurrent. To apply measured DMM correction, pass `--calibration-csv table.csv` with at least five `raw_mv_reported,dmm_mv` points across 250–2400 mV (alternatively `raw_counts,dmm_mv`). Interpolation is piecewise linear; outside-table inputs are invalid (NaN), never extrapolated. Save preserves original `mv`, and records the correction table name in metadata; retain the table alongside the session. Calibration tables must come from your bench; none are supplied as measured evidence.

Mean, total RMS, AC RMS, peak-to-peak, Hann FFT, dominant frequency and DC–100 Hz integrated PSD are calculated from the visible window. The PSD integral includes signal energy: call it noise only for a dark/no-signal acquisition. Nonuniform timing rejects FFT by default (5% interval jitter tolerance and maximum 1.5 nominal sample intervals). Sequence gaps, dropped changes, epoch resets and gain/rate changes clear the live window, so separate acquisitions are not joined. CSV retains stream diagnostics; offline processing refuses diagnostic gaps, setting changes, duplicate timestamps and excessive jitter. No automatic interpolation is performed. Reboot epochs remain separate. A bounded display queue can omit plots under overload; continuous recording retains received batches, and subsequent display sequence checks reveal omissions.

Offline tools operate on an explicitly selected epoch (default zero):

```sh
python analysis_fft.py sessions/<timestamp> --epoch 0
python analysis_noise.py sessions/<timestamp> --epoch 0
python analysis_gain.py sessions/<timestamp> --dark-mv 1650 --rf-ohm 100000
python analysis_frequency_response.py sessions/<timestamp> --input-amplitude-ua 0.5
```

Values in these commands are illustrative, not measured. Gain analysis requires the measured dark baseline and measured feedback resistance. Frequency-response analysis returns one magnitude point from a known sinusoidal injected current; repeat across a bench frequency sweep. Spectral leakage and the analog filter influence this estimate. Offline tools use saved baseline `mv`; apply your reviewed calibration to a derived dataset before using it for calibrated-current claims. All derived results are CALCULATED or SYNTHETIC; hardware accuracy, noise floor, network limits and bandwidth remain TBD until bench validation.
