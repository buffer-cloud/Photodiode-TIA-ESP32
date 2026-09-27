# Analog design gate — Rev A

**ANALOG DESIGN REVIEW: PASS**

Date: 2026-09-27. Evidence comes from [analog-calculation-review.md](analog-calculation-review.md) (CALCULATED, script `tools/analog_calcs.py`) and [simulation-report.md](../simulation/notes/simulation-report.md) (SIMULATED, script `simulation/run_all.py`, TI OPAx320 vendor model). **No hardware has been measured.** This gate authorizes schematic capture and PCB layout. It does not authorize fabrication.

Opus escalation was not used. The calculations and simulation agree on every stability question, and the one numerical discrepancy (µV-level noise) doesn't affect any decision.

## Locked values

| Item | Locked value |
|---|---|
| Photodiode | Vishay BPW34 (provisional reference device), cathode to 3V3A, anode to SUM, reverse bias ≈ 1.65 V |
| TIA / buffers | 2 × OPA2320 (SOIC-8): U1A TIA, U1B VREF buffer, U2A/U2B filter followers |
| RF / CF pairs | **10 kΩ / 1 nF**, **100 kΩ / 100 pF**, **1 MΩ / 10 pF**. RF 0.1 % thin film; CF C0G/NP0. Exactly one pair is linked (JP_G10K / JP_G100K / JP_G1M) |
| VREF | 10 kΩ / 10 kΩ 0.1 % divider, 10 µF ‖ 100 nF at the midpoint, OPA2320 follower, no capacitor on the follower output |
| Filter / ADC drive | 3.3 kΩ / 100 nF → follower → 3.3 kΩ / 100 nF → follower → 1 kΩ / 10 nF → JP_ADC → GPIO34 |
| Analog LDO | **TPS7A2033PDBVR**, 1 µF in / 1 µF out (alternates LP5907MFX-3.3, ADP150-3.3) |
| ADC clamp | **BAT54S** dual Schottky, ADC_OUT to 3V3D and to GND |
| Expected output range | TIA_OUT and ADC pin: 1.65 V dark, falling to 0.25 V at full scale (140 µA / 14 µA / 1.4 µA). ADC acquisition window 0.25–2.40 V. Readings outside it are flagged, not converted |

## Gate questions

| Question | Answer | Evidence |
|---|---|---|
| Is the TIA stable? | **Yes.** PM is 79.4° / 85.5° / 90.4° with zero peaking at nominal values. Every selected-CF case across CT 40–120 pF and 0.5–2× CF has PM ≥ 78° | SIMULATED. Calculated worst case is 66.9° under a pessimistic second-pole assumption |
| Is CF justified? | **Yes.** CF sets the 15.9 kHz TIA bandwidth: 12.5×, 40× and 125× above the analytical minimum of 0.8 / 2.5 / 8.0 pF. At the minimum, the design would sit at ~54° PM and 1 dB peaking at 80 pF, falling to ~25° at 0.5×. The margin is deliberate | CALCULATED + SIMULATED (18-case sweep per gain) |
| Is the target bandwidth realistic? | **Yes.** TIA −3 dB is 15.9–16.0 kHz and the system −3 dB is 309.5 Hz for all gains, regardless of GBW (10–30 MHz) and CT | SIMULATED, within 4 % of CALCULATED |
| Is output swing compatible with the supply? | **Yes.** The normal window of 0.25–1.65 V is inside the op-amp's linear range. It saturates at about 10 mV only beyond ~1.18× full scale, and recovers from 3× overload in 64–240 µs | SIMULATED |
| Is the ESP32 ADC protected? | **Yes, with a procedural limitation.** Signals stay inside 0–3.3 V in simulation, and the 1 kΩ series resistor plus BAT54S to 3V3D/GND limit faults. There is no powered-off isolation, so JP_ADC must be opened for independent powering | CALCULATED + SIMULATED. Procedure in [architecture.md](architecture.md) |
| Is the reference low-noise enough? | **Yes, for this ADC.** The divider pole is 3.15 Hz, and supply-to-ADC transfer is −34 dB at 100 Hz and −41 dB at 1 kHz (100 kΩ range). TPS7A2033 noise (7 µV rms, datasheet) contributes sub-µV. Startup settling is 233 ms | SIMULATED + CALCULATED |
| Are all gain settings usable? | **Yes.** Every range is linear to 0.25 V with a slope of −RF. Noise at the ADC pin is 1.6–3.0 µV rms, which is far below the expected ESP32 ADC noise | SIMULATED |
| Are component values commercially practical? | **Yes.** All values are standard E-series parts: RF 0.1 % thin film, CF C0G 0603 (1 nF C0G is a common part), and the 10 µF midpoint capacitor may be X7R because it is outside the signal path. Nothing is custom | Engineering judgement. The BOM is produced in the PCB phase |
| Are datasheet limits respected? | **Yes.** OPA2320 input common-mode range includes 1.65 V on 3.3 V. The output is kept ≥ 0.25 V from the rail. The ADC window is inside Espressif's 150–2450 mV at 11 dB | DATASHEET, cited in [design-decisions.md](design-decisions.md) |

## Discrepancies between calculation and simulation

1. **Selected-CF phase margin:** the calculation gives 73.5–87.5°, the simulation 79.4–90.4°. The calculation uses an assumed second pole and is the conservative number. **Resolved:** use the calculated value as the design floor.
2. **Dark noise at the ADC pin** (10k/100k ranges): calculated 0.85 / 1.14 µV rms, simulated 1.57 / 1.74 µV rms. The likely cause is that the vendor model includes 1/f and frequency-dependent en in all four amplifiers. **Not resolved further:** it is below 1 µV and irrelevant next to the ADC contribution. The 1 MΩ range agrees within 10 %.
3. **Overshoot figures for the analytical-minimum CF cases in the calculation script** (for example, 25 % at PM 66.5°) are inconsistent with the simulation, which shows 0 dB peaking at 2× minimum CF. They are also inconsistent with standard second-order theory, where 66° corresponds to roughly 5 %. **Resolved:** this is an error in the script's overshoot column. It affects only the non-selected evaluation cases, not the locked design. Correct it in `tools/analog_calcs.py` when that file is next touched.
4. **Simulation defects found and fixed during review:** the loop-gain formula, and VREF netlists that contradicted the contract. See the simulation report. After the fixes, the results match the calculations.

## Remaining analog risks (hardware verification required)

- BPW34 capacitance and dark current at 1.65 V bias are not specified by the datasheet. The CT corners cover 40–120 pF. Measure them.
- PCB parasitics on SUM and the feedback parasitic are covered only by the corner sweep. Layout must keep SUM short and avoid ground pour under RF/CF. An unselected gain branch leaves a floating node on SUM through RF‖CF, adding ≤ ~1 pF (CALCULATED), which is inside the CT sweep.
- At 1 MΩ, supply noise reaching SUM through the photodiode capacitance isn't simulated. It is CALCULATED to be negligible with TPS7A2033, but it is still a Wi-Fi coupling path to check on the bench.
- Measurement resolution will be set by the ESP32 ADC (mV level, nonlinear, calibration-dependent). Do not claim any detection limit until one is measured.
- The 1 ksps option has only −6.3 dB alias rejection at Nyquist (CALCULATED). 4 ksps is the default.
- Clamp leakage, overload recovery and startup sequencing need to be checked on the bench. Wait 0.5 s after power-up before baselining.
- The datasheet figures flagged in [analog-calculation-review.md](analog-calculation-review.md) §5 need to be re-read from the primary PDF tables before ordering.

All measured values are **TBD — hardware measurement required**.
