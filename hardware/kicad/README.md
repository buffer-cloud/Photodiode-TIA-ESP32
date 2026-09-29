# Photodiode TIA / ESP32 — native KiCad 9

Open `photodiode-tia-esp32.kicad_pro`. The native schematic is the editable source of truth. It uses one A3 sheet with supply, reference, bypass, detector/TIA, paired gain branches, buffered filter/ADC and test-point sections. `Photodiode.kicad_sym` and both library tables are project-relative; install standard KiCad 9 footprint libraries.

`verification/pin-review.md` records manufacturer pin checks and executed ERC/export checks. Generated `verification/schematic.xml`, `schematic.pdf`, and `erc.rpt` are local review outputs and can be regenerated with KiCad CLI.

`build_schematic.py` preserves the initial capture recipe, not an automatic synchronization mechanism. It refuses to replace an existing schematic unless `--overwrite` is explicitly passed. **That flag discards manual schematic/library edits.** Make a backup or use a separate checkout first. Symbol-library discovery supports `--symbol-library PATH`, `KICAD_SYMBOL_DIR`, then conventional Linux/macOS/Windows KiCad 9 installation paths. The checked-in native schematic does not require Python or this recipe to open/edit.

The custom Vishay BPW34 footprint defines pin1=cathode, pin2=anode, 5.1 mm pitch; see the pin-review evidence. No PCB is created by this capture recipe.

Operate with exactly one gain shunt. Power off before changing it. Open JP_ADC for independent powering; clamps are not powered-off isolation. Prototype checks and rail-ramp verification are required before connecting the ADC link.

## Routed PCB

The native PCB is fully routed on two layers, 60 × 45 mm, 1.6 mm thick. Executed all-severity DRC with schematic parity passes with zero violations, zero unconnected items and zero parity issues; see `verification/drc.rpt` and `verification/layout-review.md`. `verification/board-top.png` is the reviewed top rendering. `verification/assembly-top.svg` supplies visible numeric component references. Vias are off SMD pads; manufacturing-output review and bench-validation limits are documented in the layout review.

Use the saved PCB as the authoritative design. `repair_pcb.py --output NEW_PATH` creates a separate candidate without overwriting any existing file. The native project does not run this script on opening. The defective initial routing recipe and intermediate candidates are retained only in ignored local recovery storage.
