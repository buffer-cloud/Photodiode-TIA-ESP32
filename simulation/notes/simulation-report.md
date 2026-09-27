# Rev A analog simulation report

Every number here is **SIMULATED** unless marked otherwise. Nothing here is measured. Simulator: LTspice 17.2.4 (macOS, batch mode). Main model: TI OPAx320 PSpice model, Final 1.6 (not redistributed; see [models/README.md](../models/README.md)). GBW sensitivity uses the tracked [behavioral model](../models/opamp_behavioral.sub), which is AC small-signal only.

To reproduce everything: `cd simulation && ../.venv/bin/python run_all.py`. This regenerates `results/summary.{csv,json}` and `plots/01…09_*.png` in under a minute.

## Testbench

- Photodiode: ideal current source from VCC to SUM, plus `Cdiode = CT − 9 pF` from SUM to VCC. The vendor model already contains 9 pF of input capacitance. Dark current is 2 nA as a scenario.
- Stages: TIA (U1A), then 3.3 kΩ/100 nF, follower, 3.3 kΩ/100 nF, follower, then 1 kΩ/10 nF at the ADC pin. Every stage uses the vendor model.
- Loop gain: the loop is broken at the op-amp output with a 1 TH DC path and a 1 F AC coupling cap, and a 1 V series source `Vtest` from the amplifier side (`cx`) to the network side (`tia`). T = −V(tia_amp)/V(tia) = −(1+V(tia))/V(tia), and PM = 180° + ∠T at |T| = 1.
- Sweeps: RF/CF ∈ {10k/1n, 100k/100p, 1M/10p}. CF ∈ {0.5, 1, 2}× the analytical minimum (8.0/2.5/0.8 pF) and {0.5, 1, 2}× the selected value. CT ∈ {40, 80, 120} pF. GBW ∈ {10, 20, 30} MHz (behavioral model).
- VREF: 10 kΩ/10 kΩ divider with 10 µF‖100 nF at the midpoint and an OPAx320 follower, with no capacitor on the follower output (as in the contract).

Fixes made while reviewing (coordinator, 2026-09-27):
1. The loop-gain formula was wrong (`1/V − 1`), which gave NaN or 270° phase margins. Corrected to the expression above.
2. The VREF netlists had 1 µF directly on the buffer output and no midpoint capacitor, which contradicts the contract. Corrected, and the startup run was lengthened to 600 ms.
3. The behavioral model's `IF()` rail clamp stopped the DC operating point from converging. Replaced with a linear output, since that model is only used for AC.
4. Python 3.12/numpy 2.x compatibility: the log files use UTF-16LE with no byte-order mark, and `np.trapz` is now `np.trapezoid`.

## Headline results, selected CF, CT = 80 pF, GBW 20 MHz (vendor model)

| Check | 10 kΩ / 1 nF | 100 kΩ / 100 pF | 1 MΩ / 10 pF |
|---|---|---|---|
| DC transimpedance | 9.99999 kΩ (80.0 dBΩ) | 99.9999 kΩ (100.0 dBΩ) | 999.9998 kΩ (120.0 dBΩ) |
| Dark V(tia) / V(adc), 2 nA | 1.6500 / 1.6501 V | 1.6498 / 1.6499 V | 1.6480 / 1.6481 V |
| −3 dB at TIA_OUT | 15.88 kHz | 15.89 kHz | 15.98 kHz |
| −3 dB at ADC pin | 309.5 Hz | 309.5 Hz | 309.5 Hz |
| Peaking (TIA / ADC) | 0.00 / 0.00 dB | 0.00 / 0.00 dB | 0.00 / 0.00 dB |
| Loop phase margin | 79.4° | 85.5° | 90.4° |
| Loop crossover | 12.7 MHz | 9.44 MHz | 2.33 MHz |
| 10 %-FS step overshoot | 0 % | 0 % | 0 % |
| 1 % settling at TIA_OUT | 46 µs | 46 µs | 46 µs |
| Recovery from 3× FS overload, to 2 % | 64 µs | 80 µs | 240 µs |
| Current for output = 0.25 V | 140.0 µA | 14.00 µA | 1.400 µA |
| Output floor in saturation (DC, filter load) | 12 mV | 10 mV | 10 mV |
| V(adc) range, dark → 2× FS | 0.012–1.650 V | 0.010–1.650 V | 0.010–1.648 V |
| Integrated noise at ADC, 0.1 Hz–100 kHz, dark | 1.57 µV rms | 1.74 µV rms | 2.95 µV rms |
| Input-referred density at 100 Hz | 2.26 pA/√Hz | 0.448 pA/√Hz | 0.130 pA/√Hz |

## CF sweep: peaking dB / phase margin ° (vendor model, GBW 20 MHz)

| RF | CF case | CT 40 pF | CT 80 pF | CT 120 pF |
|---|---|---|---|---|
| 10k | 0.5× min (4 pF) | 2.72 / 44.1 | 5.18 / 32.9 | 6.76 / 27.4 |
| 10k | 1× min (8 pF) | 0.00 / 67.6 | 0.98 / 55.2 | 2.14 / 47.5 |
| 10k | 2× min (16 pF) | 0.00 / 82.3 | 0.00 / 77.1 | 0.00 / 72.0 |
| 10k | 0.5× / 1× / 2× sel | 0 / 80.9–80.0 | 0 / 80.5–78.7 | 0 / 80.7–78.1 |
| 100k | 0.5× min (1.25 pF) | 3.26 / 41.3 | 5.89 / 30.2 | 7.52 / 25.0 |
| 100k | 1× min (2.5 pF) | 0.00 / 67.5 | 1.14 / 54.0 | 2.39 / 46.0 |
| 100k | 2× min (5 pF) | 0.00 / 83.9 | 0.00 / 77.9 | 0.00 / 72.4 |
| 100k | 0.5× / 1× / 2× sel | 0 / 86.1–82.4 | 0 / 87.7–83.1 | 0 / 88.6–83.9 |
| 1M | 0.5× min (0.4 pF) | 3.36 / 40.9 | 6.03 / 29.7 | 7.68 / 24.5 |
| 1M | 1× min (0.8 pF) | 0.00 / 68.0 | 1.12 / 54.3 | 2.38 / 46.1 |
| 1M | 2× min (1.6 pF) | 0.00 / 84.7 | 0.00 / 78.5 | 0.00 / 72.9 |
| 1M | 0.5× / 1× / 2× sel | 0 / 90.0–88.6 | 0 / 89.8–89.8 | 0 / 89.2–90.3 |

TIA bandwidth with the selected CF is 31.8 / 15.9 / 7.9 kHz at 0.5× / 1× / 2×, regardless of CT. With the analytical-minimum CF it is 0.1–3.8 MHz, far above the design point. **Marginal cases (PM < 45° or peaking > 1 dB) occur only with the analytical-minimum CF.** At 0.5× every CT corner is marginal. At 1× the CT = 80 pF case is at the ~1 dB threshold, and CT = 120 pF is 2.1–2.4 dB. None of the selected-CF cases is marginal.

## GBW sensitivity (behavioral model, CT = 80 pF), peaking dB / TIA −3 dB

| RF | CF | 10 MHz | 20 MHz | 30 MHz |
|---|---|---|---|---|
| 10k | selected | 0.00 / 15.9 kHz | 0.00 / 15.9 kHz | 0.00 / 15.9 kHz |
| 10k | 1× min | 2.64 / 1.91 MHz | 0.89 / 2.43 MHz | 0.15 / 2.65 MHz |
| 100k | selected | 0.00 / 15.9 kHz | 0.00 / 15.9 kHz | 0.00 / 15.9 kHz |
| 100k | 1× min | 3.19 / 634 kHz | 1.07 / 803 kHz | 0.20 / 873 kHz |
| 1M | selected | 0.00 / 16.1 kHz | 0.00 / 16.0 kHz | 0.00 / 15.9 kHz |
| 1M | 1× min | 3.27 / 203 kHz | 1.05 / 256 kHz | 0.17 / 276 kHz |

Cross-check at 20 MHz with the selected CF: behavioral and vendor TIA bandwidths agree within 0.01 %. The vendor 1×-min peaking (0.98–1.14 dB) agrees with the behavioral result (0.89–1.07 dB).

## VREF and supply coupling (100 kΩ range)

- VREF 1 % startup settling after a 1 ms 0→3.3 V ramp: **233 ms**. The calculated value is 4.6 × 5 kΩ × 10.1 µF = 232 ms. Wait at least 0.5 s after power-up before taking baseline data.
- VCC → V(adc) transfer: −6.0 dB at DC (the divider's half-scale response, as expected), −16.4 dB at 10 Hz, −34.3 dB at 100 Hz, −41.2 dB at 1 kHz, −58.3 dB at 10 kHz and −60.7 dB at 100 kHz. The 1 MΩ range was not simulated for supply coupling. Its photodiode-capacitance path is larger and is calculated in [analog-calculation-review.md](../../docs/analog-calculation-review.md) §3.

## Comparison with the calculations ([analog-calculation-review.md](../../docs/analog-calculation-review.md))

| Quantity | Calculated | Simulated | Agreement |
|---|---|---|---|
| TIA −3 dB with selected CF | 15.92 / 15.98 / 16.57 kHz | 15.88 / 15.89 / 15.98 kHz | ≤ 4 % |
| System −3 dB | ≈ 310 Hz | 309.5 Hz | < 0.2 % |
| PM with selected CF (f2 = 3×GBW) | 73.5 / 79.6 / 87.5° | 79.4 / 85.5 / 90.4° | Simulation is 3–6° higher; the calculation is the conservative one |
| Full-scale current to 0.25 V | 140 / 14 / 1.4 µA | 140.0 / 14.00 / 1.400 µA | exact |
| VREF settling | 232 ms | 233 ms | < 1 % |
| Noise at ADC, dark | 0.85 / 1.14 / 2.68 µV rms | 1.57 / 1.74 / 2.95 µV rms | 1M within 10 %. 10k/100k are 1.5–1.9× higher in simulation (see below) |
| Dominant noise at 1 MΩ | RF Johnson (0.129 pA/√Hz) | 0.130 pA/√Hz total at 100 Hz | consistent |

Noise discrepancy at 10k/100k: the simulation includes the vendor model's frequency-dependent en (including 1/f) for all four amplifier channels. The calculation used white-noise approximations for the followers and the reference. The difference is below 1 µV rms. It does not affect any decision, because the ESP32 ADC is expected to contribute mV-level noise (one 12-bit LSB ≈ 0.8 mV at 11 dB), which is more than 100× larger. This is noted, not resolved further.

## Model limitations

- The photodiode is modeled as a fixed capacitance. BPW34 C(V) at 1.65 V, dark current, responsivity and temperature behavior are not modeled.
- PCB parasitics appear only as the CT corners (40–120 pF). The 0.5–2 pF feedback parasitic adds to CF, which is benign for the selected values (for example, 10 pF + 1 pF at 1 MΩ gives about 14.5 kHz, CALCULATED).
- The vendor model is not a guarantee of silicon behavior, and the behavioral model has no noise, slew limit or rail limit.
- ESP32 ADC sampling, clamp-diode leakage, Wi-Fi coupling and LDO dynamics are not simulated.
