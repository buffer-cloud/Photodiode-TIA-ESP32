# Photodiode TIA + ESP32 Optical Sensor

Photodiode transimpedance amplifier with ESP32 wireless acquisition and Python-based signal analysis and a live Flutter dashboard. The analog noise budget is quantified in µV (CALCULATED); end-to-end resolution is expected to be limited by the ESP32 ADC, so no system-level "low-noise" claim is made until measured.

**Status:** Revision A analog design and simulation gate PASS; schematic, PCB, firmware and Python tools complete. The BOM and fabrication exports are complete for bare-board prototype fabrication. Component qualification and physical validation remain pending. BPW34 remains the provisional detector. All physical results are **TBD — HARDWARE MEASUREMENT REQUIRED**. See [implementation verification](docs/implementation-verification.md), [manufacturing notes](hardware/manufacturing/rev-a/fabrication-notes.md) and the [bring-up plan](docs/bringup-plan.md).

## Repository structure

- `docs/`: requirements, architecture, calculations and verification
- `simulation/`: LTspice circuits and reproducible analysis
- `hardware/`: KiCad design, BOM and manufacturing notes
- `firmware/esp32/`: acquisition and WebSocket telemetry
- `software/python/`: dashboard and analysis
- `software/flutter/`: responsive live ESP32 dashboard for Chrome
- `measurements/`: real bench data only
- `portfolio/`: case study and factual résumé entry

## ESP32 live dashboard

The standalone ESP32 Dev Module has been built, uploaded, and verified over Wi-Fi/WebSocket. Open the [Flutter dashboard guide](software/flutter/README.md) for Chrome and Android setup. The interface displays live raw ADC counts and packet health, with an explicit warning that GPIO34 is currently unconnected. Physical photodiode performance remains unverified until the PCB is assembled.

## Phase-sensitive sensing research

The [research track](research/phase-sensitive/README.md) adds a reproducible synthetic lock-in comparison and a preliminary physical ESP32 stream-health measurement. It defines the electrical and optical experiments needed to turn the current prototype into a characterized instrument. The synthetic results are not optical measurements, and the first stream check exposed a delivery-rate issue requiring controlled follow-up.
