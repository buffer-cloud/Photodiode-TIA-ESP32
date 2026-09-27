# Rev A requirements

This is a design and verification project, not a claim of fabricated or measured hardware. Demonstrate photodiode current conversion, selectable range, repeatable sampling, wireless transport and honest analysis of analog and ADC limitations.

| Requirement | Rev A acceptance criterion | Evidence required |
|---|---|---|
| Input | Provisional Vishay BPW34, reverse biased approximately 1.65 V | Part marking, pinout and polarity inspection |
| Ranges | 10 kΩ, 100 kΩ, 1 MΩ; power-off selection of exactly one feedback pair | Resistance inspection and injected-current sweep |
| Transfer | Increasing light decreases voltage, nominal slope −RF | DC sweep against calibrated current source |
| Headroom | Normal light signal 0.25–1.65 V; flag ADC outside 0.25–2.40 V | Scope and calibrated ADC sweep |
| Band | DC–100 Hz useful; approximately 310 Hz combined filter −3 dB | Sine sweep per gain |
| Sampling | Default 4 ksps; 1–8 ksps configurable, actual times recorded | Timing histogram and queue loss counter |
| Stability | No sustained oscillation; target <10% small-signal overshoot | Model sweep then oscilloscope check |
| Digitization | Original ESP32 ADC1 GPIO34, calibration retained | Compare calibrated mV to DMM; raw data saved |
| Noise | Quantify darkness spectrum with Wi-Fi on/off | Actual data, acquisition settings and processing saved |
| Safety of connection | Common ground and coordinated power; disconnect ADC link for separate powering | Bring-up inspection |

No numeric detection-limit claim is accepted until measured. Gain calibration must include resistor tolerance and dark offset. Firmware gain metadata is manually matched to hardware; no electronic gain control exists. The 1 ksps option has substantially weaker analog alias rejection and is intended only for known slowly varying inputs. No external ADC is fitted in Rev A.
