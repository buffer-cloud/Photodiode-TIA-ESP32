# Rev A implementation verification

Baseline: analog design gate PASS at `b1b1bc1`. This report concerns implementation; it does not repeat or replace the analog analysis. All hardware performance results remain **TBD — HARDWARE MEASUREMENT REQUIRED**.

| Check | Required evidence | Status |
|---|---|---|
| Schematic | KiCad ERC with no unresolved violations | **PASS** 2026-09-29: `--severity-all` ERC 0 errors / 0 warnings, no exclusions (fresh parent run; preserved export baseline [erc.rpt](../hardware/manufacturing/rev-a/exports/erc.rpt)). Netlist-export annotation warning resolved (numeric refs; contract names in Value) |
| Critical pin mappings | Independent exported-netlist check for OPA2320, TPS7A2033, BAT54S, BPW34 and connector | **PASS**: `tools/check_hardware_contract.py` on [schematic.xml](../hardware/kicad/verification/schematic.xml). Negative tests (renamed TIA_OUT, swapped D1 pins) fail as intended. Capture recipe regenerates an identical netlist. Visual PDF check of D1, U1A, D2 and gain links done |
| PCB | Parent-run DRC with all severities and schematic parity | **PASS** 2026-09-29; 0 violations, 0 unconnected, 0 parity issues |
| Analog placement | Parent visual and geometric review of actual saved PCB | PASS for prototype fabrication; see notes below |
| Firmware | Parent-run build using pinned PlatformIO environment | **PASS** 2026-09-29: regression build, 70,480 B RAM / 780,037 B flash; espressif32@7.1.3 + Arduino-ESP32 2.0.17, 0 warnings, RAM 21.5 %, flash 59.5 %. Not flashed: runtime timing and Wi-Fi throughput are **TBD — HARDWARE MEASUREMENT REQUIRED** |
| Python | Parent-run offline tests and synthetic capture/analysis smoke check | **PASS** 2026-09-29: 7 pytest tests (3.74 s). CLI smoke: mock server → dashboard `--record` → `analysis_fft.py` recovered the SYNTHETIC 10 Hz / 50 mV tone. Firmware emits all 10 contract keys |
| Fabrication package | BOM, seven Gerbers, plated and nonplated drills; independent review and hash verification | **PASS**: 7 Gerbers, 41 PTH holes and 4 NPTH mounting holes. Parent source/output manifest hashes and BOM netlist reference/quantity coverage PASS; see [manufacturing notes](../hardware/manufacturing/rev-a/fabrication-notes.md) and [footprint review](../hardware/manufacturing/rev-a/footprint-review.md) |
| Publishing | No secrets or restricted vendor models; repository content and publication checks | Hardware package `c5b42ac` committed/pushed; repository content check PASS. Documentation is included in the commit containing this report; final post-push acceptance checks are clean working tree and HEAD equal to origin/main |

ERC and DRC are necessary checks, not evidence of measured noise, stability, ADC accuracy or RF immunity. The approved simulation remains model evidence. Fabrication release requires reviewing the actual board and exact purchased parts; this task does not place an order.

## Parent manual layout review

Reviewed the actual native board, final top render and pad/track geometry. BPW34 anode/input separation is 3.42 mm, shortened from approximately 7 mm; SUM branches total 22.72 mm and use no vias. Three feedback pairs are clustered, with the highest-gain pair closest to the input. The longer output-side connections to manual selection headers remain a documented layout tradeoff, not a measured parasitic-capacitance result. Both-layer copper-pour keepout follows SUM and feedback; digital connector and 5 V routing are at the opposite side. VREF uses front copper without vias. Local amplifier bypasses have short ground fanouts.

All 25 vias were checked against SMD pad bounding boxes: minimum drill-edge separation is 0.375 mm (minimum copper-edge separation 0.225 mm). No filled/capped via-in-pad process is required. Cathode/pin-1 markings, accessible test pads, gain shunts, ADC link and connector orientation were inspected. Numeric assembly references remain on F.Fab and the assembly drawing. The source board is 60 × 45 mm, 2 layers and nominal 1.6 mm thickness.

Firmware regression emitted no new warnings in its successful incremental build. GPIO34, 11 dB attenuation, timer acquisition and WebSocket81 remain unchanged. Python regression passed all seven tests. Software and locked analog documents were not modified from the approved baseline.

## Fabrication release review

Independent inspection parsed all seven Gerber layers and both drill files. Top and bottom copper and solder mask were rendered and viewed: registration, pads and holes were plausible, with no observed missing tracks or mask. Edge.Cuts forms one closed 60 × 45 mm outline. Back silkscreen is intentionally empty; mounting holes are present. Source/output SHA-256 checks bind the reviewed native board to the export package. The BOM covers schematic references and quantities; manufacturer package/pin review is recorded in the linked footprint review.

Bare-board prototype fabrication review PASS. The specified capacitors retain their locked values and packages. Primary-source typical bias evidence supports the LDO output capacitance margin, but does not guarantee lot qualification. Effective capacitance, reference settling and actual LDO behavior remain component/physical qualification items. This release does not claim measured system performance.
