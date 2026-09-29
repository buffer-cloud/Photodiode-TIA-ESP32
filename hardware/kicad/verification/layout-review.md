# Rev A PCB routing and analog review

Layout reviewed 2026-09-27; final DRC rerun 2026-09-28 with KiCad 9.0.0. The frozen native schematic was not edited.

## Executed verification

`kicad-cli pcb drc --severity-all --schematic-parity --exit-code-violations -o hardware/kicad/verification/drc.rpt hardware/kicad/photodiode-tia-esp32.kicad_pcb`

Exit code **0**: **0 DRC violations, 0 unconnected items, 0 schematic parity issues**. No DRC exclusions or severity suppression were added. Ground zones were filled before checking. Board is 60 × 45 mm, two copper layers, 1.6 mm nominal thickness; tracks 0.25 mm, vias 0.6/0.3 mm. Existing outline, mounting arrangement, functional floorplan and all schematic components were retained; defective crossing tracks were replaced and local courtyard conflicts repaired. All footprint library identifiers and schematic instance paths match the frozen schematic. Mounting holes are board-only.

## Manual analog assessment

- D1 BPW34 pad 2/anode connects to U1 pin 2/SUM; pad 1/cathode connects to 3V3A. U1/U2 remain OPA2320 SOIC-8; U3 remains the locked TPS7A2033PDBVR footprint/pin assignment. D2 remains BAT54S. Netlist parity verifies the connector and paired gain mappings.
- SUM was routed first entirely on front copper: **zero vias**, total branch copper length **22.72 mm** across the detector, amplifier and six feedback terminations. The direct detector-to-input distance is approximately 3.42 mm (D1 anode at 12.85,22.5 mm; U1 pin 2 at 15.525,20.365 mm); the remaining copper serves the three selectable pairs. It is a compact three-range prototype, not a measured minimum-capacitance layout.
- Each RF/CF pair is adjacent in the compact two-column, three-row cluster above the detector/TIA, with the 1 MΩ pair nearest the input. The gain selector is on the output side of each pair. Gain branch route lengths are 11.44/15.22/21.79 mm, with 0/0/1 layer transitions respectively; these output-side connections are a tradeoff of the retained manual header architecture. They are not part of the SUM node. Exactly one shunt is required.
- Front and back ground-pour keepout covers the feedback/SUM region using a shaped polygon around the feedback cluster (x=9.5–14 mm, y=9.8–19.8 mm) and the short input/detector connection (extending to x=16.8 mm and y=23.5 mm) to reduce shunt plane capacitance. The rest of the board has common filled ground planes. No digital or USB-power traces enter this region. The capacitance assumption still requires bench validation; DRC does not validate loop stability.
- U1/U2 100 nF decouplers sit immediately above their supply pads; each has a short explicit fanout to an off-pad ground via and the plane. Bulk 1 µF capacitors sit beside them. The reference divider and shunt capacitors remain beside U1B, with buffered VREF routed entirely on front copper. There is no added capacitive load on the buffer output.
- Filter flow remains left-to-right through R6/C12, U2A, R7/C13, U2B, R8/C14, BAT54S, JP1 and J1. The ADC/digital connector remains at the right edge. VBUS routing stays at x≥47.5 mm; 3V3D routing stays at x≥45 mm, away from the detector/TIA. Power and ground are connected, not only airwires or reserved routing channels.
- Reviewed `board-top.png`: no visible footprint/body conflicts, required gain/ADC power-off instructions and all six contract test-point names are readable. Standard 3D models render where installed; no BPW34 model is provided. Numeric references are visible on F.Fab and in `assembly-top.svg`, with contract names on the silkscreen. Cathode and IC pin-1 markings remain visible.

## Fabrication and bench handoff

This is a DRC-clean engineering prototype, not evidence of measured analog performance. The next manufacturing review should inspect the drill/mask exports and assembly drawings. All ground vias now use off-pad fanouts; signal vias also avoid SMD pad apertures. An executed geometric check found 25 total vias and at least 0.225 mm between via copper and every SMD-pad bounding box. This layout does not require filled/capped via-in-pad construction. Final fabrication review should still check the selected vendor’s mask, drill and assembly outputs.

Bench checks remain necessary: dark offset, all three gains, noise and oscillation, rail sequencing, reference voltage, ADC calibration and clamp behavior. All measured results remain TBD.

## Safe regeneration

The native PCB is the deliverable. `repair_pcb.py --output NEW_PATH` reads it and writes a separate candidate; it refuses to replace an existing output. It uses the board's existing footprints and the frozen netlist and does not require an absolute footprint-library path. Review any candidate and run full DRC before adopting it. The defective initial-placement recipe and intermediate boards are preserved only in ignored local recovery storage, not distributed as build instructions.
