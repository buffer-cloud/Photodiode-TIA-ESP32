# Analog architecture review

Status: analytical review complete; vendor-model stability, schematic, PCB and bench verification remain required.

- Corrected photodiode orientation to cathode 3V3A, anode SUM for decreasing output with increasing light.
- Rejected OPA380/381 at 1.65 V common mode on 3.3 V; selected OPA2320.
- Restricted ADC acquisition range to 0.25–2.40 V; normal positive-light signal uses 0.25–1.65 V.
- Gave each gain a paired feedback capacitor and required exactly one closed feedback branch.
- Chose isolated RC filter sections, low-impedance ADC driver and explicit modest alias attenuation.
- Distinguished analog noise estimates from ESP32 system resolution and unmeasured dark current.
- Identified powered-off backfeed as a connection constraint; clamps alone do not provide isolation.

Release checklist still open: verify footprints/pin numbers against exact order codes; verify supply regulator and decoupling; check clamp leakage; simulate polarity/headroom/CF and CT corners; run schematic ERC and board DRC; check feedback selection links and parasitics; test start-up rail timing before ADC connection; measure gain, offset, noise, overload recovery, anti-alias response and sample timing. Do not fabricate measurement or vendor-model results.

## Coordinator checkpoint

Electrical architecture is internally consistent for the next simulation phase: diode orientation gives the required negative transimpedance, amplifier common mode includes VREF, compensation/filter values have a calculation basis, and the positive-light operating window fits the chosen ADC range. **Approved to simulate; PCB routing remains gated on the SPICE review.** This is not approval to fabricate. Powered-off ADC isolation is procedural in Rev A and must remain explicit in the connector and bring-up instructions.
