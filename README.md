# Photodiode TIA + ESP32 Optical Sensor

Photodiode transimpedance amplifier with ESP32 wireless acquisition and Python-based signal analysis. The analog noise budget is quantified in µV (CALCULATED); end-to-end resolution is expected to be limited by the ESP32 ADC, so no system-level "low-noise" claim is made until measured.

**Status:** Revision A analog design and simulation gate PASS; schematic, PCB, firmware and Python tools complete. The BOM and fabrication exports are complete for bare-board prototype fabrication. Component qualification and physical validation remain pending. BPW34 remains the provisional detector. All physical results are **TBD — HARDWARE MEASUREMENT REQUIRED**. See [implementation verification](docs/implementation-verification.md), [manufacturing notes](hardware/manufacturing/rev-a/fabrication-notes.md) and the [bring-up plan](docs/bringup-plan.md).

## Repository structure

- `docs/`: requirements, architecture, calculations and verification
- `simulation/`: LTspice circuits and reproducible analysis
- `hardware/`: KiCad design, BOM and manufacturing notes
- `firmware/esp32/`: acquisition and WebSocket telemetry
- `software/python/`: dashboard and analysis
- `measurements/`: real bench data only
- `portfolio/`: case study and factual résumé entry
