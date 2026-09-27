# Rev A schematic verification and pin review

2026-09-27, KiCad CLI 9.0.0. Analog design gate b1b1bc1 was accepted; this capture does not revise it.

## Executed checks

- Native `.kicad_sch` loaded by KiCad CLI and exported successfully to PDF and XML netlist.
- `kicad-cli sch erc --severity-all --exit-code-violations -o verification/erc.rpt photodiode-tia-esp32.kicad_sch`: **0 errors, 0 warnings, exit 0**. No ERC exclusions, severity overrides, or hidden suppression were added.
- Exported `verification/schematic.pdf` rendered with Poppler and visually inspected for readable fields, complete section content, absence of title-block overlap, and correct diode/amp symbols.
- `verification/schematic.xml` is available for independent electrical-contract validation and PCB net import.
- **Annotation resolution (2026-09-27):** contract names without a trailing number (JP_G10K, TP_3V3A, …) are treated by KiCad as *unannotated*. Netlist export printed `schematic has annotation errors`, and GUI Update-PCB-from-Schematic would be blocked. This was an annotation issue, not an electrical fault. Fixed by numeric references with the contract name in the Value field: J1=J_ESP32, JP1=JP_ADC, JP2=JP_G10K, JP3=JP_G100K, JP4=JP_G1M, TP1=TP_3V3A, TP2=TP_VREF, TP3=TP_TIA, TP4=TP_FILTER, TP5=TP_ADC, TP6=TP_GND. Connectivity is unchanged: the regenerated netlist is identical in nets and components apart from the references. `tools/check_hardware_contract.py` resolves contract names through Value. Negative tests (renamed TIA_OUT net, swapped BPW34 pins) fail as expected.
- The earlier report of 3 ERC warnings is not reproducible from any saved file. Fresh `--severity-all` ERC on this schematic reports 0 errors and 0 warnings with no exclusions.
- Hardware measurements remain TBD. ERC verifies schematic rules, not analog performance or assembly correctness.

## Manufacturer pin review

| Device | Primary source checked | Captured pins and package |
|---|---|---|
| U1, U2 OPA2320 | [TI SBOS513F, p4](https://www.ti.com/lit/ds/symlink/opa2320.pdf), D/DGK diagram and OPA2320 pin table | SOIC-8: 1 OUT A, 2 −IN A, 3 +IN A, 4 V−/GND, 5 +IN B, 6 −IN B, 7 OUT B, 8 V+/3V3A. Unit C is the explicit power unit, with real power-input pin types. |
| U3 TPS7A2033PDBVR | [TI SBVS338H, p4, DBV diagram/table](https://www.ti.com/lit/ds/symlink/tps7a20.pdf) | SOT-23-5: 1 IN/VBUS_5V, 2 GND, 3 EN/VBUS_5V, 4 NC, 5 OUT/3V3A. Pin 4 has native no-connect electrical type and no wire. DQN pinout is different and was not used. |
| D2 BAT54S | [Vishay 86410 Rev1.1, p1 top-view diagram](https://www.vishay.com/docs/86410/bat54_bat54a_bat54c_bat54s.pdf), PDF rendered and inspected | SOT-23: 1 lower anode/GND, 2 upper cathode/3V3D, 3 series midpoint/ADC_OUT. Thus GND → diode → ADC_OUT → diode → 3V3D. |
| D1 BPW34 | [Vishay 81521 Rev2.1, p4 package drawing](https://www.vishay.com/docs/81521/bpw34.pdf), PDF rendered and inspected | Project convention pad1=K/3V3A; pad2=A/SUM. The manufacturer identifies A/C and a cathode marking, rather than numeric pin identifiers. Footprint pad1 is rectangular and marked K. 5.1 mm lead pitch; body envelope 4.65 × 4.3 mm, 1 mm drill for 0.7(+0.1) ×0.3 mm leads. Confirm physical marking before insertion. |

## Exact electrical mapping

- U1: 1 TIA_OUT, 2 SUM, 3 VREF, 4 GND, 5 VREF_DIV, 6 VREF, 7 VREF, 8 3V3A.
- U2: 1 BUF1, 2 BUF1, 3 LP1, 4 GND, 5 LP2, 6 FILTER_OUT, 7 FILTER_OUT, 8 3V3A.
- R1/C3: 10k/1n, SUM ↔ GAIN_10K; JP2 (JP_G10K): 1 GAIN_10K, 2 TIA_OUT.
- R2/C4: 100k/100p, SUM ↔ GAIN_100K; JP3 (JP_G100K): 1 GAIN_100K, 2 TIA_OUT.
- R3/C5: 1M/10p, SUM ↔ GAIN_1M; JP4 (JP_G1M): 1 GAIN_1M, 2 TIA_OUT.
- R4 3V3A–VREF_DIV and R5 VREF_DIV–GND, both 10k 0.1%; C6 10u and C7 100n from VREF_DIV to GND. No output capacitor on VREF.
- R6 TIA_OUT–LP1; C12 LP1–GND. R7 BUF1–LP2; C13 LP2–GND. R8 FILTER_OUT–ADC_OUT; C14 ADC_OUT–GND.
- C1 VBUS_5V–GND, C2 3V3A–GND, each 1u X7R. C8/C9 (U1), C10/C11 (U2): 100n + 1u 3V3A–GND.
- J1 (J_ESP32) 1 VBUS_5V, 2 GND, 3 3V3D, 4 GND, 5 ADC_LINK, 6 GND. JP1 (JP_ADC) 1 ADC_OUT, 2 ADC_LINK.
- TP1–TP6 (values TP_3V3A, TP_VREF, TP_TIA, TP_FILTER, TP_ADC, TP_GND) follow the locked contract; no SUM test pad.
- Power flags identify externally driven VBUS_5V, 3V3D and GND at the header. The LDO's actual power-output pin drives 3V3A; no power flag masks analog-rail connectivity.

All populated components have assigned footprints. Standard KiCad 9 footprint libraries plus the checked-in `Photodiode.pretty` library are required. No schematic or board fabrication release is implied.
