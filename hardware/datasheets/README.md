# Manufacturer references and provisional photodiode model

Links checked 2026-09-26; fetch current manufacturer copies before ordering. Manufacturer models and PDFs are not redistributed here.

- [Vishay BPW34 datasheet](https://www.vishay.com/docs/81521/bpw34.pdf): reverse dark current 2 nA typ/30 nA max at 10 V; capacitance 70 pF typ at 0 V, 25 pF typ/40 pF max at 3 V, 1 MHz. Neither specifies the exact 1.65 V operating point. Verify cathode marking and lead spacing from package drawing before assembly.
- [TI OPA320/OPA2320 datasheet SBOS513F](https://www.ti.com/lit/ds/symlink/opa320.pdf): electrical table, SOIC-8 pinout, TIA application guidance; 5 pF differential plus 4 pF common-mode input capacitance.
- [TI OPA380 datasheet SBOS291G](https://www.ti.com/lit/ds/symlink/opa380.pdf): comparison only.
- [TI OPA381 datasheet SBOS313B](https://www.ti.com/lit/ds/symlink/opa381.pdf): comparison only.
- [Espressif original ESP32 ADC guide](https://docs.espressif.com/projects/esp-idf/en/v4.4/esp32/api-reference/peripherals/adc.html): ADC1, attenuation and calibration; use 150–2450 mV recommended window at 11 dB.

Provisional circuit model: independent photocurrent source from cathode (3V3A) toward anode (SUM), parallel diode capacitance and independently parameterized dark current. CT=80 pF nominal includes diode+amplifier+PCB; sweep 40/80/120 pF. Do not double-count amplifier capacitance when using a vendor model that already includes it. A fixed capacitance/current-source model does not predict avalanche, wavelength responsivity, temperature, nonlinear junction capacitance or overload recovery. The 2 nA dark scenario is illustrative, not a guarantee at our bias. Replace it with measured C(V), dark current and optical calibration for the actual photodiode. No arbitrary diode saturation-current model should be presented as a manufacturer model.
