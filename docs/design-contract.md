# Shared engineering contract — Rev A electrical baseline

All disciplines must use this file. Analog architect may revise electrical fields with reasons before review; coordinator freezes them before simulation/hardware implementation.

- Photodiode: Vishay BPW34, provisional; ANODE to summing node, CATHODE to 3V3A. Reverse photocurrent flows cathode to anode into summing node; VOUT = VREF − (IPHOTO + IDARK) RF. Nominal reverse bias 1.65 V.
- Analog supply: regulated 3.3 V from USB 5 V, separate from ESP32 digital rail.
- Reference: buffered 1.65 V from two 10 kΩ 0.1% divider resistors, 10 µF || 100 nF at divider midpoint, OPA2320 unity buffer; no large capacitor directly on buffer output.
- TIA operating window: 0.25–2.40 V acquisition window; useful positive light response 0.25–1.65 V, decreases from reference.
- ADC: original ESP32 DevKit, ADC1 GPIO34; calibrated attenuation setting; target signal window 0.25–2.40 V; 11 dB attenuation, documented suggested range 0.15–2.45 V.
- Gains: manual mutually exclusive 10 kΩ/1 nF, 100 kΩ/100 pF, 1 MΩ/10 pF paired RF/CF networks (C0G/NP0). Power off to change; never operate with feedback open.
- Amplifiers: two OPA2320 dual SOIC-8 packages; U1A TIA, U1B reference buffer, U2A/U2B unity-gain RC filter buffers.
- Filter: TIA → 3.3 kΩ → 100 nF to GND → U2A follower → 3.3 kΩ → 100 nF to GND → U2B follower → 1 kΩ series → ADC; 10 nF ADC to GND. Each main pole 482 Hz; useful science band DC–100 Hz. ADC clamp diodes to GND and ESP32 3V3D; removable ADC connection link. Both rails powered together; verify ramp sequencing, no hot plugging. Open ADC link before independent powering; clamps are not powered-off isolation.
- Model baseline: CT=80 pF total (including amplifier 9 pF input), corners 40/80/120 pF; GBW=20 MHz nominal with 10–30 MHz sensitivity; CF 0.5×/1×/2×. Do not double-count capacitance in vendor models.
- Sampling: 4000 samples/s default, configuration 1000–8000 samples/s; timer task, measured timing and lost-sample accounting; analog anti-alias response fixed and documented.
- Network: WebSocket TCP 81, path `/`; ESP32 server and Python client.
- Packet: JSON batch version 1, keys `v`, `seq`, `t0_us`, `fs_hz`, `gain_ohm`, `dropped`, `raw`, `mv`, `dt_us`. Arrays raw/mv/dt_us same length; dt_us actual sample offset from t0_us. Raw 12-bit counts preserved. mv is calibrated millivolts, never ideal counts-to-volts claim. t0_us monotonic boot time; seq increments for each emitted batch; dropped cumulative acquisition/queue losses.
- Test points: TP_3V3A, TP_VREF, TP_TIA, TP_FILTER, TP_ADC, TP_GND.
- Naming: lowercase-hyphen documentation, snake_case Python, photodiode-tia-esp32 KiCad project; source relative paths only.
- Evidence: calculated, model-simulated, expected and measured explicitly labeled. All measured results TBD until bench testing. Do not invent LTspice execution or ERC/DRC results.

## Interface lock additions (coordinator, 2026-09-26)

Added before implementation handoff. Fields above are unchanged.

- Target bandwidth: TIA closed-loop pole 1/(2π RF CF) = 15.9 kHz in every range; system −3 dB ≈ 310 Hz set by the two 482 Hz RC poles; useful band DC–100 Hz.
- Expected output range: TIA_OUT 1.65 V (dark) falling to 0.25 V at full-scale current 1.40/RF (140 µA / 14 µA / 1.4 µA).
- Analog LDO: **TPS7A2033PDBVR** (SOT-23-5, 3.3 V fixed, 1 µF input and 1 µF output C0G/X7R), from J_ESP32 VBUS_5V; analog load ≈6 mA calculated. Locked 2026-09-26 per docs/analog-calculation-review.md §4. Alternates: LP5907MFX-3.3, ADP150-3.3.
- ADC clamp diodes: BAT54S dual Schottky (series pair, common node ADC_OUT); leakage error through 1 kΩ is sub-mV calculated, characterize on bench.
- CF sweep scope (resolves ambiguity in "CF 0.5×/1×/2×"): simulate both (a) 0.5×/1×/2× the analytical minimum-stable CF and (b) 0.5×/1×/2× the selected CF. The selected CF sets bandwidth; the analytical CF is evidence of stability margin.
- Sampling buffer: batches of 256 samples (64 ms at 4 ksps); firmware ring buffer holds at least 8 batches; overflow increments `dropped`.
- Firmware framework: PlatformIO, `espressif32` platform, Arduino framework, board `esp32dev`. Primary acquisition is timer-driven (hardware timer or ADC continuous/DMA), never `delay()` paced. Wi-Fi credentials are in `firmware/esp32/include/secrets.h` (gitignored) with a committed `secrets.example.h`.
- Calibration method: ADC 11 dB, eFuse-based Espressif calibration for `mv` as a baseline; then a DMM multi-point user calibration (DC source → TP_ADC, ≥5 points across 0.25–2.40 V) that stores a piecewise-linear correction table applied in Python (firmware reports `calibration` provenance string). Gain calibration uses measured RF plus a measured dark baseline.
- Connectors and links: J_ESP32 1×6 2.54 mm header — 1 VBUS_5V, 2 GND, 3 3V3D (clamp rail sense from DevKit), 4 GND, 5 ADC_LINK (to GPIO34), 6 GND. JP_ADC 2-pin link between ADC_OUT and ADC_LINK. Gain links JP_G10K, JP_G100K, JP_G1M (exactly one closed). D1 BPW34 mounted on board only; no photodiode cable in Rev A.
- Python stack: numpy, scipy, matplotlib, pandas, websockets; client connects to `ws://<esp32-ip>:81/`.
- Vendor models: TI OPAx320 PSpice model is used locally in `simulation/models/` but not committed (redistribution not granted); `simulation/models/README.md` gives source and SHA-256.
