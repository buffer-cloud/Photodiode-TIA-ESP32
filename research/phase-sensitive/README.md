# Phase-sensitive optical sensing research track

**Status (2026-10-11):** Analysis and a synthetic comparison are reproducible. The standalone ESP32 streams an open ADC input, but optical hardware is not connected. No measured light sensitivity, noise floor, or detection limit is claimed.

## Research question

At a specified false-alarm rate, what is the minimum modulated optical signal detectable by a low-cost ESP32 photodiode receiver under changing ambient illumination? How do acquisition loss, timing error, and analog front-end noise alter that limit?

The aim is a measured, open, repeatable instrument and an honest comparison with simpler processing. The project does not claim the lock-in estimator is a new algorithm. Its research value depends on the characterized system and the experimental evidence.

## What is implemented now

- A timestamp-aware fit of DC, cosine, and sine at a known modulation frequency. It reports peak amplitude, phase, residual RMS, and a model-based standard error.
- A seeded **SYNTHETIC** study with 60 Hz interference, Gaussian noise, timestamp jitter, and simple voltage quantization. It compares the fit with both an unreferenced raw range and an informed known-frequency FFT bin. The FFT should agree on contiguous, nearly uniform samples.
- A live ESP32 stream-health capture tool. It saves packet counts, sequence gaps, and the *change* in the device loss counter without saving the local network address or presenting an open ADC input as optical data.

Reproduce from the repository root after installing `software/python` as described in its README:

```sh
PYTHONPATH=software/python python -m photodiode_tia.lockin_experiment --output research/phase-sensitive/results
PYTHONPATH=software/python python -m photodiode_tia.stream_benchmark --host <ESP32-IP> --seconds 10 --output research/phase-sensitive/results/new-stream-check.json
python -m pytest -q software/python/tests/test_lockin.py
```

The committed `results/synthetic_*` files are generated examples, never bench evidence. The preliminary ESP32 result is a local-network observation with other clients and RF conditions uncontrolled. Do not use it as a throughput specification.

## Experimental protocol for the next hardware stage

1. **Electrical input validation:** Use a known, current-limited modulation source and review the ADC voltage range before connecting a signal. Verify the reference frequency, sampling timestamps, and no clipping with an independent instrument where available.
2. **Optical setup:** Modulate an LED; measure its signal with a BPW34 and a reviewed resistor or TIA front end. Keep source-detector spacing and shielding fixed, and log LED current, ambient illumination, gain, temperature, and acquisition settings.
3. **Controls:** Collect LED-off/dark, LED-on, wrong-reference-frequency, and 50/60 Hz ambient-interference runs. Randomize run order and repeat on separate days.
4. **Metrics:** Report threshold at a predeclared false-alarm rate, detection probability, amplitude error, timing jitter, sample/packet loss, and power use with uncertainty intervals. Compare against raw range and known-frequency FFT on the same saved samples.
5. **Reproducibility:** Preserve raw ADC counts, actual timestamps, firmware commit, circuit revision, calibration records, scripts, plots, and failed trials. Separate synthetic, electrical, and optical measurements in all figures.

## Hardware needed

The existing ESP32 is enough for the software and stream baseline. Optical testing additionally needs a photodiode, LED, current-limiting parts, breadboard/jumpers, and a reviewed analog input circuit. The designed PCB can be used later, but its fabrication and optical performance are pending. Do not connect an LED or external voltage directly to GPIO34 without reviewing the electrical limits and circuit.

## Evidence boundary and current limitation

The first live stream check showed that configured sample rate and delivered sample rate can differ substantially. Before optical claims, run controlled single-client captures across rates, distinguish acquisition drops from intentional no-client transport drops, and verify sustained delivery. The current cumulative `dropped` field combines several causes and cannot alone diagnose the failure.

## Sources

- [Caltech EE research areas](https://www.ee.caltech.edu/research): circuits, devices, sensing, and photonics provide context for the research direction, not an admissions guarantee.
- [Espressif ESP32 continuous ADC driver](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/adc_continuous.html): candidate hardware-supported acquisition route for a later firmware comparison.
- [OLIA open-source lock-in amplifier paper](https://arxiv.org/abs/2211.08889): prior work establishing that a low-cost digital lock-in is feasible. This project must compare against, not claim to originate, that method.
