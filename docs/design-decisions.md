# Analog decisions and alternatives

Manufacturer tables are authoritative; headline white-noise numbers can hide substantial low-frequency noise. Values below are typical unless marked max, generally 25 °C with the datasheet test conditions; they do not imply worst-case performance at 3.3 V.

| Device | Supply | GBW | Voltage noise | Bias current | Offset | Current/channel | Decision |
|---|---|---|---|---|---|---|---|
| OPA380 | 2.7–5.5 V | 90 MHz | 67 nV/√Hz at 10 kHz; 5.8 above 1 MHz | 3 pA typ, 50 pA max | 25 µV max, test at 5 V/VCM 0 | 7.5 mA | Common-mode ceiling 1.5 V at 3.3 V excludes 1.65 V baseline |
| OPA381 | 2.7–5.5 V | 18 MHz | 70 nV/√Hz at 10 kHz; 10 above 1 MHz | 3 pA typ, 50 pA max | 25 µV max, test at 5 V/VCM 0 | 0.8 mA | Same common-mode restriction; lower power but not compatible here |
| OPA320 | 1.8–5.5 V | 20 MHz | 8.5 nV/√Hz at 1 kHz; 7 at 10 kHz | 0.2 pA typ, 0.9 pA max | 150 µV max | 1.45 mA | Electrically suitable; separate single packages increase area |
| OPA2320 | 1.8–5.5 V | 20 MHz | Same family | Same at 25 °C | Same family | 1.45 mA | Selected; two dual packages implement four stages |

OPA320/2320 input range extends 0.1 V beyond both rails; operation here stays inside them. Family voltage noise includes 2.8 µV peak-to-peak over 0.1–10 Hz, so a white-noise-only budget is optimistic at DC. Bias limit rises to 50 pA over −40 to 85 °C; OPA2320 reaches 400 pA over the full −40 to 125 °C range. Output swing depends on load; the family specifies open-loop gain over 0.1 V to V+−0.1 V with 10 kΩ, and 0.2 V to V+−0.2 V with 2 kΩ. Rev A keeps 0.25 V minimum and uses high-impedance followers.

OPA380/381 are not drop-in alternatives despite photodiode marketing: they require lower VREF or a higher supply and ADC interface redesign. Their exceptional offset/drift can be useful for another architecture. OPA320 single helps isolate reference/TIA supplies or routing but costs package count. No live price or stock is claimed; compare distributor quotations at purchase, exact SOIC order codes and lead times.

Sources checked 2026-09-26: [TI OPA380 datasheet, electrical characteristics](https://www.ti.com/lit/ds/symlink/opa380.pdf), [TI OPA381 datasheet](https://www.ti.com/lit/ds/symlink/opa381.pdf), [TI OPA320/2320 datasheet](https://www.ti.com/lit/ds/symlink/opa320.pdf). Compensation and power figures are design calculations rather than vendor application guarantees.
