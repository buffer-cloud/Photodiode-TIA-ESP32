# Project Handoff

## Current commit

Hardware fabrication package: `c5b42ac`, committed and pushed. Reviewed PCB baseline: `d31301b`. This handoff accompanies the subsequent documentation release commit. Software baseline: `b2a1eed`; earlier schematic `0da5b3f`, firmware `99d66d4`, analog gate `b1b1bc1`.

## Current phase

Revision A bare-board prototype fabrication release complete. Next phase: procurement, assembly and controlled bench qualification. No analog, PCB or software redesign.

## Completed

Locked requirements and analog design; simulation gate PASS; schematic; routed PCB; firmware; Python tools; BOM; seven Gerbers and separate PTH/NPTH drills; bring-up procedure.

## Verified

Fresh parent checks on 2026-09-29: schematic ERC, PCB DRC and schematic/PCB parity PASS; hardware contract check PASS; firmware build PASS (70,480 B RAM / 780,037 B flash); Python offline suite PASS (7 tests, 3.74 s). Manufacturing evidence is under `hardware/manufacturing/rev-a/`.

## Locked parameters

OPA2320; RF/CF 10 kΩ/1 nF, 100 kΩ/100 pF, 1 MΩ/10 pF; TPS7A2033PDBVR; BAT54S; VREF ≈1.65 V; ADC1/GPIO34 at 11 dB; timer-driven sampling; JSON v1/WebSocket port 81; output ≈1.65 V dark to ≈0.25 V full-scale. Full contract: `docs/design-contract.md`.

## PCB status

Native PCB at `d31301b` is authoritative: fully routed 60 × 45 mm, two layers, nominal 1.6 mm. Parent placement review passed: detector/input separation 3.42 mm, clustered feedback, no SUM vias, all vias off small pads. No board edits required for this release.

## DRC status

PASS on 2026-09-29: zero violations and zero unconnected items; schematic/PCB parity zero issues.

## ERC status

PASS on 2026-09-29: zero errors and zero warnings.

## Firmware status

Pinned Arduino-ESP32 2.0.17 regression build PASS. Runtime timing, losses and throughput await physical hardware.

## Python status

Seven offline tests PASS. Synthetic capture/FFT evidence remains labeled synthetic; physical capture and ADC correction-table qualification await hardware.

## BOM status

`hardware/bom/rev-a.csv` exists with populated parts, package/footprint and sourcing information. Exact-part review and capacitor derating evidence are documented in `hardware/manufacturing/rev-a/footprint-review.md`; no locked part/value substitution.

## Gerber/drill status

Seven Gerbers: F.Cu, B.Cu, F.Mask, B.Mask, F.SilkS, B.SilkS and Edge.Cuts. PTH: 41 holes (25 vias, 16 component holes). NPTH: four mounting holes. Exports are in `hardware/manufacturing/rev-a/exports/`; empty back silkscreen is intentional.

## Manufacturing verification

Source locks, SHA-256 manifest, export checks, footprint review and manufacturing notes accompany the exports. Independent fabrication review PASS: all seven Gerbers and both drills parsed; top/bottom copper and mask viewed; closed 60 × 45 mm outline, registration, pads and holes checked. Parent source/output hash and BOM reference/quantity coverage checks PASS. Package targets bare-board prototype fabrication and hand assembly.

## Open issues

No open bare-board fabrication blocker. Typical capacitor bias evidence is not guaranteed lot qualification: effective capacitance, reference settling and LDO behavior remain physical/component qualification items before validated operation. ADC-only calibration requires JP1 / JP_ADC OPEN and injection at J1 pin 5 / ADC_LINK on the isolated ESP32/GPIO34 side, never the driven TP_ADC.

## Hardware measurements still required

All physical results: **TBD — HARDWARE MEASUREMENT REQUIRED**. Verify rails/current/startup, effective capacitance, VREF, dark offsets, all three gains, stability, bandwidth, overload recovery, ADC calibration, timing/losses, WebSocket/CSV capture, FFT, dark noise and Wi-Fi off/on coupling. Follow `docs/bringup-plan.md`.

## Next exact task

Submit the seven Gerbers and two drill files for a bare-board prototype, obtain the specified parts and qualify them before current-limited bring-up.

## Git status

Release files are committed in focused hardware and documentation commits on main. Final acceptance requires a clean working tree and HEAD matching origin/main; the integration owner verifies both immediately after publishing this documentation commit. No force push.
