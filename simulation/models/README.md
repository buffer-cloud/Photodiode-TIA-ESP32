# Vendor simulation models (not redistributed)

Download manufacturer models locally into this folder. They are gitignored because redistribution rights are not granted.

| File | Source | Version | SHA-256 of the copy used |
|---|---|---|---|
| `OPAx320.lib` | [TI OPA320 product page](https://www.ti.com/product/OPA320) → Design & development → PSpice model | Final 1.6, 22 JUL 2021 | `a3ecb23eb81d73b9d03cc4d44ef0e06ffdaadc995301bad1cb4882ba8a0f3b8c` |

Subcircuit pin order: `IN+ IN- VCC VEE OUT`. The model already contains 4 pF common-mode capacitance on each input and 5 pF differential capacitance, so testbenches must subtract 9 pF from the total input capacitance CT.
