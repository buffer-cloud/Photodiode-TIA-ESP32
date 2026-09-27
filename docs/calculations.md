# Analog calculations — estimates, not measurements

## Transfer and range

VOUT = VREF − (IPHOTO + IDARK + signed input leakage) RF, neglecting amplifier offset. Positive photocurrent flows from BPW34 cathode on 3V3A toward its anode on SUM, which feedback holds near 1.65 V. Nominal diode reverse bias is 1.65 V. With a 0.25 V minimum, usable total positive current is 1.40/RF:

| RF | CF selected | Total current max | Output change for 1 nA | Initial 1 mV resolution example |
|---|---|---|---|---|
| 10 kΩ | 1 nF | 140 µA | 10 µV | 100 nA |
| 100 kΩ | 100 pF | 14 µA | 100 µV | 10 nA |
| 1 MΩ | 10 pF | 1.4 µA | 1 mV | 1 nA |

Maxima include dark current and background; subtract both to obtain remaining signal headroom. RF 0.1% tolerance initially gives 0.1% slope uncertainty. The resolution column is an example for a measured 1 mV system fluctuation, not a guaranteed ADC step. Minimum detectable current is determined by measured noise/drift divided by RF, with a declared bandwidth and SNR criterion. The ESP32 calibration table lists up to ±60 mV error at highest attenuation; this does not support precision absolute current without local calibration. [Espressif ADC range/calibration](https://docs.espressif.com/projects/esp-idf/en/v4.4/esp32/api-reference/peripherals/adc.html).

## Compensation and filters

Provisional total input capacitance CT = 80 pF includes diode, 9 pF amplifier input and layout. BPW34 specifies 70 pF typical at zero bias and 25 pF typical/40 pF maximum at 3 V; neither is a guaranteed value at 1.65 V. Sweep CT = 40, 80, 120 pF and allow cable capacitance only with a revised model. A first-order compensation estimate is CF ≈ sqrt(CT/(2π RF GBW)) at 20 MHz: 8.0, 2.5, 0.8 pF for the three RF values. This is a starting estimate, not a guaranteed phase margin. Selected values 1000/100/10 pF deliberately reduce bandwidth to approximately 1/(2πRF CF) = 15.9 kHz in all ranges and exceed that minimum. Sweep CF from 0.5× through nominal to 2×, CT corners and GBW 10–30 MHz. Include 0.5–2 pF feedback/layout parasitics and nonideal amplifier poles. High-frequency noise gain tends toward 1+CT/CF, approximately 1.08/1.8/9. Validate loop margin with the vendor model and actual PCB; one-pole models cannot certify stability.

Two isolated RC poles use R=3.3 kΩ, C=100 nF: fp=482.3 Hz and H(s)=1/(1+sRC)^2. Combined −3 dB ≈310 Hz; amplitude at 100 Hz is 0.9588 (−0.37 dB), at 2 kHz 0.0550 (−25.2 dB), at 4 kHz 0.0143 (−36.9 dB). ADC 1 kΩ/10 nF adds a 15.9 kHz pole and a sample charge reservoir, not the main anti-alias filter. At 1 ksps Nyquist=500 Hz, main rejection is only −6.34 dB. Strong out-of-band illumination can alias; shielding, faster sampling or a higher-order filter is required. Digital filtering cannot undo aliasing. For two equal RC poles, white-noise equivalent bandwidth B=πfp/4=378.8 Hz; downstream noise sources see different bandwidths.

## Noise and error budget

At 300 K use k=1.380649e−23 J/K and q=1.602176634e−19 C. Feedback resistor input noise sqrt(4kT/RF) = 1.287/0.407/0.129 pA/√Hz; integrated through B=378.8 Hz gives 25.1/7.92/2.51 pA rms, or 0.251/0.792/2.51 µV rms at output. These exclude ADC and all other sources.

Shot density sqrt(2q(Ilight+Idark)); at 2 nA dark it is 25.3 fA/√Hz or 0.493 pA rms over B; at 1 µA total it is 0.566 pA/√Hz or 11.0 pA rms. BPW34's 2 nA typical/30 nA maximum dark values are specified at 10 V, not our 1.65 V; treat 2 nA as a scenario only. Dark offset at that scenario is 20 µV/200 µV/2 mV. Temperature, contamination and optical background can dominate this.

OPA2320 input current noise typical 0.6 fA/√Hz is small here; approximate 0.012 pA rms over B. Its 8.5 nV/√Hz at 1 kHz gives ~0.165 µV rms if white and noise gain near one. Correct calculation integrates en(f)^2 × |NG(f)|^2 × |H(f)|^2, with NG=(1+s RF(CT+CF))/(1+s RF CF). Include low-frequency excess noise; 0.1–10 Hz specification is peak-to-peak and must not be treated as an rms density. Offset 150 µV maximum corresponds to 15 nA/1.5 nA/0.15 nA input error before baseline subtraction; temperature drift can remain after subtraction.

The reference divider has 5 kΩ Thevenin resistance, 9.1 nV/√Hz white noise before its approximately 3.15 Hz pole (10.1 µF), giving ~20 nV rms integrated. Reference buffer noise is added after that pole and reaches TIA via noise gain; its low-frequency drift matters. Analog rail noise couples through the divider (half-scale at low frequency), photodiode capacitance and amplifier PSRR: a divider is not a precision reference. Both 0.1% resistors at opposite tolerance extremes cause roughly ±1.65 mV reference error. Measure dark baseline, supply ripple and VREF with Wi-Fi active.

Each 3.3 kΩ filter resistor contributes thermal noise. First stage is filtered twice; second once. Integrated rms values are approximately sqrt(kT/(2C))=0.144 µV and sqrt(kT/C)=0.204 µV respectively. The ADC 1 kΩ/10 nF gives sqrt(kT/C)=0.644 µV. Capacitors have no independent thermal noise in the ideal lossless model; kT/C is resistor-generated noise stored on a capacitor, not an extra additive source. Dielectric loss/leakage and microphonics are omitted and require component selection/testing. Use C0G feedback capacitors; avoid high-K ceramics in the feedback path.

U2A follower voltage noise is filtered by one main RC stage, whereas U2B noise is filtered only by the ADC RC; approximate white contributions using 8.5 nV/√Hz are 0.234 and 1.34 µV rms respectively. These are preliminary; high-frequency amplifier noise and ADC sampling require full integration. RSS the independent contributions only after giving every source its actual transfer function. Do not RSS correlated reference/supply effects as independent. ADC quantization, INL, calibration residuals, sampling jitter and Wi-Fi coupling are additional system terms and likely dominate the analog microvolt budget. Compare measured dark records with Wi-Fi off/on and external digitization before reporting sensitivity.
