# Photodiode TIA + ESP32 Optical Sensor

Photodiode transimpedance amplifier with ESP32 wireless acquisition and Python-based signal analysis. The analog noise budget is quantified in µV (CALCULATED); end-to-end resolution is expected to be limited by the ESP32 ADC, so no system-level "low-noise" claim is made until measured.

**Status:** Revision A engineering development. BPW34 is provisional. Hardware measurements are **TBD — requires fabricated hardware**. No performance or fabrication readiness is claimed at this stage.

## Repository structure

- `docs/`: requirements, architecture, calculations and verification
- `simulation/`: LTspice circuits and reproducible analysis
- `hardware/`: KiCad design, BOM and manufacturing notes
- `firmware/esp32/`: acquisition and WebSocket telemetry
- `software/python/`: dashboard and analysis
- `measurements/`: real bench data only
- `portfolio/`: case study and factual résumé entry
