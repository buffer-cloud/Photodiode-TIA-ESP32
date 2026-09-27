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
