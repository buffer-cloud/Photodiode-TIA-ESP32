# Rev A prototype fabrication and manual assembly

60 × 45 mm rectangular PCB, two copper layers, nominal 1.6 mm FR-4, 1 oz finished copper, lead-free HASL finish, green solder mask both sides, white front silkscreen. No controlled impedance, buried/blind vias, slots, castellations, or filled/capped via-in-pad construction. Request electrical bare-board testing. Manufacturer must preserve the supplied geometry; do not silently substitute components or change copper.

Upload only the seven Gerbers and two `.drl` files in `exports/` to the fabricator. The empty back silkscreen is intentional. `.gbrjob` is supplementary job metadata; SVG maps/drawings and reports are documentation, not copper. No stencil/paste files are supplied because this revision targets hand assembly. Finished holes: 25 plated 0.30 mm vias; 16 plated 1.00 mm component holes; four 3.20 mm nonplated mounting holes. Via copper diameter 0.60 mm (0.15 mm nominal annular ring). Design rules: 0.20 mm minimum clearance and track width, 0.50 mm copper-to-edge; routed tracks are 0.25 mm. Verify the chosen manufacturer's standard process accepts these values. Excellon units are mm with absolute origin; negative Y is the KiCad convention shared by the Gerbers.

Fresh full-severity DRC, connectivity/parity and ERC pass in `exports/`. `export-check.json` records tool sizes, hole counts and coordinate extents. Edge.Cuts defines one closed 60 ×45 mm outline. The manifest binds sources and outputs by SHA-256; rerun `python3 hardware/manufacturing/regenerate.py` from any directory to export this exact release. It discovers the CLI on PATH, then the standard macOS application, or accepts `KICAD_CLI`. Changed PCB, schematic or project settings are rejected until a new independent review updates `source-lock.json`. It never rebuilds the PCB. It replaces only `rev-a/exports/` after successful checks.

## Assembly

Use `../../bom/rev-a.csv` and `exports/assembly-top.svg` (top/component view, numeric references and pad outlines). All components are on the front. Install SMD parts first, then the detector and headers. Avoid contamination at the SUM region; clean flux residue and dry thoroughly. Keep the photodiode optical window clean and unobstructed. No component is fitted to TP1–TP6: these are exposed 1.5 mm copper probe pads. Four 3.2 mm mounting holes accept optional enclosure-specific M3 nylon fasteners; those are not mandatory electrical BOM items.

- U1/U2 pin 1 is upper-left in the drawing, at (15.525,19.095) / (34.525,19.095) mm. Match package pin-1 dot/notch to the board marker; use OPA2320AID SOIC-8 only.
- U3 pin 1 is upper-left at (49.8625,13.05) mm; pad4 is NC. Do not use the differently pinned DQN package.
- D2 has two pads on the left and the single midpoint pad3 on the right. Pad1 upper-left is GND; pad2 lower-left is 3V3D. Use BAT54S series pair, marking L48 for the specified Vishay part.
- D1 cathode goes to the LEFT rectangular pad1 marked K (7.75,22.5 mm); anode to right pad2/SUM. The manufacturer's A/C polarity drawing is authoritative; lead length alone is not a polarity identifier.
- J1 is a generic 1×6 cable header, NOT a mechanical DevKit socket. Top square pad1: USB 5V; 2 GND; 3 ESP32 3V3D; 4 GND; 5 GPIO34/ADC1; 6 GND. Check continuity before connecting the original ESP32 DevKit. The DevKit and USB cable are external equipment, not fitted PCB BOM items.
- Fit exactly ONE gain shunt: JP2=10k/1nF, JP3=100k/100pF, JP4=1M/10pF. Never leave all open during powered operation or fit several. Power off before changing gain.
- Supply the second shunt loose for JP1/ADC. Leave JP1 open for initial analog bring-up and independent powering. Close only after rail/voltage checks; power both rails together, no hot plugging. Diode clamps are not powered-off isolation.

This package supports prototype fabrication. Analog performance, effective capacitance, rail ramp behavior, gain/noise/stability and ADC calibration remain unmeasured; perform bench validation before science use.
