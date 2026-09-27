# Analog calculation review — CF stability, per-gain, noise budget, LDO, ADC

Status: analytical review, CALCULATED numbers reproduced deterministically by
`tools/analog_calcs.py` (run: `.venv/bin/python tools/analog_calcs.py`). No SPICE
was run here (a separate agent is covering that). DATASHEET items cite the
source; everything else is CALCULATED from the locked contract values in
`docs/design-contract.md`. This document does not change any locked field —
proposed changes are listed under "Recommended changes" only.

## 1. Feedback capacitor (CF) analysis

Model: `NG(s) = [1+sRF(CT+CF)]/[1+sRF·CF]` (zero at `fz=1/(2π RF(CT+CF))`, pole
at `fp=1/(2π RF·CF)`, high-freq asymptote `1+CT/CF`); loop gain
`T(s)=Aol(s)/NG(s)` with `Aol(s)=GBW/s` (single dominant pole, CALCULATED);
closed-loop `H(s) = -RF/[a2 s²+a1 s+1]`, `a2=RF(CT+CF)/GBW`, `a1=1/GBW+RF·CF`.

**What `CF_doc = sqrt(CT/(2π·RF·GBW))` actually is** (CALCULATED derivation):
it is the CF that places the noise-gain pole `fp` exactly at the frequency
where the *rising* noise-gain asymptote — built from `CT` alone, ignoring
CF's own contribution to the zero — crosses `Aol(f)=GBW/f`. That is the
boundary between a 40 dB/decade loop-gain closure (marginal/unstable-tending)
and a 20 dB/decade closure (stable). **It is a stability-boundary estimate,
not a calibrated 45°-phase-margin design value.** The script's exact CF_45
(solved from the full NG(s), including CF in the zero, against the true
single-pole loop gain) is 1.5–2× larger than `CF_doc` at CT=80 pF/GBW=20 MHz
(e.g. 10 kΩ: CF_45=6.12 pF vs CF_doc=7.98 pF gives ratio 0.767 the *other*
way in the table below — CF_doc is actually somewhat conservative/larger at
the nominal corner, but becomes optimistic (ratio <1, i.e. CF_45>CF_doc is
false, CF_45<CF_doc) at low RF·CT·GBW products and the reverse at the low
end. Full 27-row sweep (RF×{40,80,120 pF}×{10,20,30 MHz}) is printed by the
script; representative rows at CT=80 pF nominal:

| RF | GBW | CF_45 (pF) | CF_butterworth (pF) | CF_doc (pF) | CF_45/CF_doc |
|---|---|---|---|---|---|
| 10k | 20 MHz | 6.12 | 27.84 | 7.98 | 0.77 |
| 100k | 20 MHz | 2.07 | 8.93 | 2.52 | 0.82 |
| 1M | 20 MHz | 0.67 | 2.83 | 0.80 | 0.83 |

CF_butterworth (closed-loop Q=0.707) is consistently **4–4.5× larger** than
CF_45 — a maximally-flat closed-loop response needs substantially more
compensation than the 45°-PM loop-gain boundary. Both scale as expected with
CT and GBW (full table in script output). Docs/calculations.md's headline
numbers (8.0/2.5/0.8 pF at CT=80 pF, GBW=20 MHz) reproduce exactly as
CF_doc = 7.98/2.52/0.80 pF here — confirmed correct as *a* formula, but it
should be captioned as a stability-boundary heuristic, not a 45° PM target.

**Selected CF (1n/100p/10p), CT=80 pF nominal, GBW=20 MHz nominal:**

| RF | NG zero | NG pole | NGhf | crossover (single-pole Aol) | PM (single-pole) | PM (f2=3×GBW) | closed-loop f_3dB | Q | overshoot |
|---|---|---|---|---|---|---|---|---|---|
| 10k | 14.7 kHz | 15.9 kHz | 1.08 | 18.5 MHz | 90.0° | 73.5° | 15.92 kHz | 0.073 | 0.0% |
| 100k | 8.8 kHz | 15.9 kHz | 1.80 | 11.1 MHz | 90.0° | 79.6° | 15.98 kHz | 0.094 | 0.0% |
| 1M | 1.8 kHz | 15.9 kHz | 9.00 | 2.22 MHz | 89.6° | 87.5° | 16.57 kHz | 0.211 | 0.0% |

ASSUMPTION (labeled, not datasheet): OPA320/OPA2320 SBOS513F does not tabulate
a second real pole or a unity-gain-configuration phase-margin number in the
electrical-characteristics table (only a graphical open-loop gain/phase plot,
which could not be digitized from this environment — see
[TI OPA320/OPA2320 datasheet SBOS513F](https://www.ti.com/lit/ds/symlink/opa320.pdf)).
We assumed a second real pole at `f2 = 3×GBW = 60 MHz` (a common CMOS-op-amp
rule of thumb) and swept 2×/3×/5× GBW; PM at the selected CF stays ≥ 66.9°
even at the most pessimistic 2×GBW assumption for every gain — **all three
selected-CF cases have very large, non-marginal phase margin** and are
massively overdamped (Q≈0.07–0.21, zeta 2.4–6.8, 0% predicted overshoot). The
closed-loop f_3dB matches the contract's target `1/(2πRF·CF)=15.9 kHz` to
within 0.4–4%, confirming the locked bandwidth number.

**Sensitivity sweep 0.5×/1×/2× of CF_45 and of the selected CF** (f2=3×GBW,
CT=80 pF, GBW=20 MHz; full table incl. Q and f_3dB in script output):

| basis | mult | PM (10k/100k/1M) | overshoot% (10k/100k/1M) | flag |
|---|---|---|---|---|
| CF_45 | 0.5× | 24.7° / 24.1° / 23.8° | 53% / 68% / 74% | **MARGINAL** |
| CF_45 | 1× | 42.9° / 44.3° / 44.8° | 42% / 53% / 57% | **MARGINAL** |
| CF_45 | 2× | 66.5° / 69.8° / 70.9° | 25% / 30% / 32% | **MARGINAL** (overshoot>10%) |
| CF_sel | 0.5×/1×/2× | 73–87° all cases | 0.0% all cases | ok |

**Judgment:** every point on the CF_45-basis sweep (0.5×, 1×, and even 2×)
predicts overshoot above the requirements.md target of <10%, i.e. the
*analytical minimum-stability* CF family is NOT an acceptable operating
point by itself — it is evidence of the stability boundary only, exactly as
`docs/design-contract.md` frames it ("evidence of stability margin", not the
bandwidth-setting value). The *selected* CF family (0.5×–2× of 1n/100p/10p)
is comfortably stable in every case. No selected-CF case is marginal.

## 2. Per-gain table

| RF | CF | Transimpedance | I_fs to 0.25V floor | I_fs to op-amp swing limit (≈0.10V) | Bandwidth | Output range |
|---|---|---|---|---|---|---|
| 10k | 1nF | 10 kV/A | 140.0 µA | 155.0 µA | 15.92 kHz | 0.25–1.65 V |
| 100k | 100pF | 100 kV/A | 14.0 µA | 15.5 µA | 15.92 kHz | 0.25–1.65 V |
| 1M | 10pF | 1 MV/A | 1.40 µA | 1.55 µA | 15.92 kHz | 0.25–1.65 V |

The ADC's 0.25 V floor is the binding saturation limit in every gain — the
OPA2320 output stage (0.1 V from V− rail under light loading, per
design-decisions.md) has ~1.55 V of headroom the ADC spec cannot use, so
TIA_OUT can run into the amplifier's own rail limit under an overload before
reaching 0 V (affects recovery time, not the defined full-scale). Bandwidth
is identical across all three gains (RF·CF = 10 µs in each), matching the
contract.

Dark-offset scenarios (BPW34 dark current at 10 V bias, illustrative only —
not valid at our 1.65 V bias, per hardware/datasheets/README.md):

| RF | I_dark=2nA scenario | I_dark=30nA scenario | Ib_typ=0.2pA | Ib_max=0.9pA | Vos_max=150µV |
|---|---|---|---|---|---|
| 10k | 20 µV | 300 µV | 0.002 µV | 0.009 µV | 150 µV |
| 100k | 200 µV | 3.0 mV | 0.02 µV | 0.09 µV | 150 µV |
| 1M | 2.0 mV | 30.0 mV | 0.2 µV | 0.9 µV | 150 µV |

Vos dominates the offset budget at 10k/100k; dark current dominates at 1M
(30 nA scenario, 30 mV, would eat a large fraction of the 1.40 V full-scale
swing at the highest gain — measured dark baseline at assembly is essential,
consistent with requirements.md's calibration requirement).

## 3. Noise budget

Integration uses the actual transfer functions (not ENBW shortcuts): shot and
RF-Johnson current sources go through `Zf(s)=RF/(1+sRF·CF)` (this naturally
rolls off at the 15.9 kHz feedback pole); op-amp en and VREF/divider noise go
through `NG(s)` (which plateaus at `1+CT/CF` instead of decaying — its
integration is capped at the loop-gain crossover per gain, else the 1 MΩ case
is over-integrated ~3× using a single fixed cutoff — see script comments);
everything downstream is filtered by the actual system chain
`H_sys(f)=1/[(1+jf/482.3)²(1+jf/15915)]` for the ADC-pin numbers.

| RF | level | input-referred i (pA rms, TIA-out/RF convention) | output-ref at TIA_OUT (µV rms) | output-ref at ADC pin (µV rms) | dominant (at ADC pin) |
|---|---|---|---|---|---|
| 10k | dark (2nA) | 7972 | 79.7 | 0.85 | reference divider+buffer |
| 10k | 10% FS | 7979 | 79.8 | 0.94 | reference divider+buffer |
| 10k | 50% FS | 8007 | 80.1 | 1.25 | shot |
| 10k | 100% FS | 8042 | 80.4 | 1.56 | shot |
| 100k | dark (2nA) | 1031 | 103.1 | 1.14 | RF Johnson |
| 100k | 10% FS | 1036 | 103.6 | 1.73 | shot |
| 100k | 50% FS | 1058 | 105.8 | 3.13 | shot |
| 100k | 100% FS | 1084 | 108.4 | 4.27 | shot |
| 1M | dark (2nA) | 231 | 230.6 | 2.68 | RF Johnson |
| 1M | 10% FS | 233 | 233.0 | 4.89 | shot |
| 1M | 50% FS | 242 | 242.4 | 9.58 | shot |
| 1M | 100% FS | 254 | 253.7 | 13.29 | shot |

The "input-referred" column follows the standard TIA convention (divide
output-referred rms by the DC transimpedance RF) and is dominated by the
wideband en/VREF terms integrated up to the loop-gain crossover; treat it as
an **upper bound**, not a detection-limit claim — the physically meaningful
number for the actual acquisition band is the ADC-pin column. Pattern: RF
Johnson noise dominates at low light for the two higher gains; shot noise
takes over above roughly 10–50% of full scale in all three gains; at the
lowest gain (10 kΩ) RF Johnson (12.9 nV/√Hz post-Zf) and reference/buffer
noise (≈11.5 nV/√Hz combined) are close in magnitude, so either can be
"dominant" depending on light level — consistent with docs/calculations.md's
qualitative statement that these sources are comparable at 10 kΩ.

**Supply-noise coupling** (parametrized by LDO output-noise density, flat
approximation): via photodiode/input capacitance into SUM
(`≈ j2πf·CD·Zf(f)`) is negligible (≤0.9 µV rms at ADC pin even at 100 nV/√Hz,
a pessimistic generic LDO density); via the divider's DC attenuation (~0.5)
then NG is ~1 µV rms at ADC pin at 100 nV/√Hz, dropping to ~0.2 µV rms at a
20 nV/√Hz candidate low-noise LDO density. **Both paths are well below the
shot/Johnson floor for any of the candidate low-noise LDOs in Section 4** —
supply noise is not expected to be the limiting term, but this depends on
achieving good PCB layout/PSRR in practice and should be bench-verified
(measured dark baseline with the LDO installed, per requirements.md).

**ESP32 ADC:** quantization noise (CALCULATED) = LSB/√12 = 0.598 mV / √12 =
**172.7 µV rms** at 11 dB attenuation (2.45 V suggested max,
[Espressif ADC guide](https://docs.espressif.com/projects/esp-idf/en/v4.4/esp32/api-reference/peripherals/adc.html)).
No Espressif-published ADC noise-density or ENOB figure was found in this
review (SAR ADC characteristics table not located in public ESP-IDF/datasheet
search). A community measurement
([esp32.com forum thread](https://esp32.com/viewtopic.php?t=7543)) on a
stable ~1 mV input reported a raw-code spread of roughly ±15 LSB about the
mode; at 11 dB attenuation (~0.6 mV/LSB) that implies an **unfiltered noise
floor on the order of a few mV peak-to-peak** — 5–15× the calculated
quantization noise. This is **COMMUNITY-SOURCED, not a datasheet number,
carries high uncertainty**, and confirms docs/calculations.md's conclusion:
**ADC-side noise (quantization + this unverified floor + calibration
residuals + Wi-Fi coupling) very likely exceeds the analog front-end's
µV-level noise budget by 2–4 orders of magnitude at every gain.**

**Is "low-noise" quantitatively justified?** For the analog front end alone
(TIA_OUT/ADC-pin numbers above): yes — sub-15 µV rms at the ADC pin even at
full-scale current in the worst (10 kΩ) case, dominated by fundamental shot
and Johnson noise that no op-amp choice removes. For the system as built
(through the uncalibrated ESP32 SAR ADC): **no** — the ADC's own noise floor
(quantization at minimum, likely mV-order in practice per the community data
point) dominates by orders of magnitude, so calling the *whole system*
"low-noise" is not justified until the ADC-referred noise is measured and,
if needed, addressed (averaging, external ADC in a future revision, etc.),
exactly as docs/calculations.md already states.

## 4. LDO recommendation for 3V3A

Analog rail load (CALCULATED): 4× OPA2320 channels × 1.45 mA (DATASHEET
Iq/channel) + 10k/10k divider (3.3 V / 20 kΩ) = 5.80 mA + 0.165 mA =
**5.96 mA typical**; recommend sizing for ≥2× margin (≈12 mA) — trivial for
any of the candidates below (150–300 mA rated).

| Candidate | Noise (DATASHEET) | PSRR | Input range | Dropout | Stability caps | Package |
|---|---|---|---|---|---|---|
| **TPS7A2033** | 7 µV rms (headline; [TI TPS7A20 datasheet](https://www.ti.com/lit/ds/symlink/tps7a20.pdf), 300 mA SOT-23-5 variant) | 95 dB @ 1 kHz | 1.6–6.0 V | <140 mV @ 300 mA (negligible at 6 mA) | 1 µF in, 1 µF out, no bypass cap needed | SOT-23-5 |
| LP5907-3.3 | ~6.5–10 µV rms, 10 Hz–100 kHz ([TI LP5907 datasheet](https://www.ti.com/lit/ds/symlink/lp5907.pdf)) | 82 dB @ 1 kHz | 2.2–5.5 V (typical LP59xx family range) | low, 250 mA rated | 1 µF in, 1 µF out | SOT-23-5 / DSBGA |
| ADP150-3.3 | ~9 µV rms ([ADI ADP150 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/adp150.pdf)) | high (curve, VOUT=3.3V) | 2.2–5.5 V | 105 mV @ 150 mA | 1 µF in, 1 µF out | SOT-23-5 / LFCSP |
| TLV755P | not marketed as ultra-low-noise; no headline noise spec found | 46 dB @ 100 kHz (weaker) | 1.45–5.5 V | 238 mV max @ 500 mA, 3.3 V | 0.47 µF min out (X5R/X7R) | SOT-23-5 / WSON |

**Recommendation: TPS7A2033 (order code TPS7A2033PDBVR, SOT-23-5, fixed
3.3 V, 300 mA).** Rationale: highest PSRR of the group (95 dB @ 1 kHz, most
relevant to the supply-coupling paths analyzed in Section 3), input range
comfortably covers the 5 V USB source with headroom, no dedicated
noise-bypass capacitor needed (fewer parts than some alternatives), and 300
mA rating is >>50× the actual 5.96 mA load. Required caps: 1 µF ceramic on
IN, 1 µF ceramic on OUT (per datasheet minimum), in addition to the
architecture's existing local 100 nF + 1 µF at each OPA2320 package already
specified in docs/architecture.md. LP5907-3.3 and ADP150-3.3 are acceptable
equal-class alternates if TPS7A2033 has availability/lead-time issues; TLV755P
is **not** recommended — it is a general-purpose low-IQ LDO, not a
noise/PSRR-optimized part, and no datasheet noise spec distinguishes it from
a standard LDO.

## 5. Op-amp table verification (docs/design-decisions.md)

| Parameter | design-decisions.md | Datasheet check | Verdict |
|---|---|---|---|
| OPA320/2320 supply | 1.8–5.5 V | confirmed, TI SBOS513F | keep |
| OPA320/2320 GBW | 20 MHz | confirmed | keep |
| OPA320/2320 en | 8.5 nV/√Hz @1kHz, 7 nV/√Hz @10kHz | confirmed (TI product collateral: "7 nV/√Hz at 10 kHz") | keep |
| OPA320/2320 Ib | 0.2 pA typ, 0.9 pA max | **0.9 pA figure could not be independently pinned to a specific EC-table row** in this session (TI marketing text headlines "0.9-pA Ib" but does not state test condition in the snippets retrieved) | keep, but re-verify the exact 0.9 pA row/condition against the EC table before finalizing leakage error budgets |
| OPA320/2320 offset | 150 µV max | not independently reconfirmed via search snippets, but internally consistent with the family and already cited with a URL in the repo | keep |
| OPA320/2320 Cin | 5 pF diff + 4 pF CM | confirmed, matches contract's 9 pF total input capacitance basis | keep |
| OPA320/2320 Iq | 1.45 mA/ch | consistent with TI headline ("1.45 mA quiescent current") | keep |
| OPA380 GBW / Ib / Vos | 90 MHz / 3pA typ,50pA max / 25µV max | all confirmed via search ([TI OPA380 datasheet](https://www.ti.com/lit/ds/symlink/opa380.pdf)) | keep |
| OPA380 en | 67 nV/√Hz@10kHz, 5.8 above 1MHz | **not independently confirmed** — could not extract the EC table's noise row in this session | flag: re-check directly against SBOS291G before relying on this number; does not change the reject decision (common-mode ceiling issue is the binding reason) |
| OPA381 GBW / Ib / Vos | 18 MHz / 3pA typ,50pA max / 25µV max | GBW and offset confirmed via search ([TI OPA381 datasheet](https://www.ti.com/lit/ds/symlink/opa381.pdf)); Ib listed as 3pA typ in design-decisions.md, search snippet also says "bias current of 3pA" without stating typ/max explicitly | keep, minor: confirm typ vs max label |
| OPA381 en | 70 nV/√Hz@10kHz, 10 above 1MHz | not independently confirmed (same caveat as OPA380) | flag: re-check |
| Input CM range at 3.3V, OPA380/381 | "ceiling 1.5V" rationale for rejecting at VCM=1.65V | not independently pulled as an exact number in this session | flag: re-confirm the exact VICR spec before citing "1.5V" as a hard number in future revisions — but the underlying decision to keep OPA2320 is independently sound (it is rail-to-rail input while OPA380/381 are not marketed as such, and the 25µV offset test condition "VCM 0" implies an asymmetric/non-RRIO input structure) |

No numbers were found to be **wrong**; the flags above are re-verification
recommendations (PDF text extraction was unreliable in this environment —
several TI PDFs returned binary/compressed streams instead of text), not
identified errors. Recommend: keep the table as-is, but re-pull the flagged
rows directly from the datasheet PDFs (not search snippets) before the
hardware freeze.

## 6. ADC interface

- **1k/10nF drive:** forms the contract's 15.9 kHz anti-alias pole (`τ=10µs`,
  matches `F_POLE_ADC` in the script). The 10 nF external reservoir is
  2–3 orders of magnitude larger than a typical SAR sampling capacitor
  (a few pF), so it can supply the ESP32's internal sample-and-hold charge
  within its short (~1–2 µs class) acquisition window without droop; the
  1 kΩ resistor's role is anti-aliasing/current-limiting, not ADC-drive
  settling, and is not a bottleneck at 1–8 ksps.
- **Clamp diodes:** recommend a **dual low-leakage small-signal Schottky
  such as BAT54S** (or BAV99 if a standard silicon dual is preferred) for the
  ADC_OUT clamp pair to 3V3D/GND. Schottky parts have both lower forward
  turn-on voltage (better clamp action before the ESP32 pin sees an
  overvoltage) and, in most modern small-signal Schottky families, leakage in
  the low-nA range at the ~0.75–0.85 V reverse bias implied by clamping
  2.40–2.45 V against a 3.3 V rail — this leakage directly degrades ADC
  accuracy per docs/architecture.md's own warning and should be measured on
  the bench (per the release checklist in docs/analog-review.md), not
  assumed from a typical datasheet curve.
- **Overvoltage cases:** BPW34 is wired for photocurrent flowing cathode→
  anode only (reverse-biased photodiode, contract §1); reversing that current
  is not a normal operating mode, but a fault (wrong polarity assembly,
  amplifier failure, or the "high-rail overload" case docs/architecture.md
  already calls out) could drive TIA_OUT toward the positive rail. Under
  such a fault, TIA_OUT is bounded by the OPA2320 supply rail (3.3 V, since
  the op-amp cannot exceed its own supply) — **this exceeds the ADC's
  0.25–2.40/2.45 V calibrated window (must be flagged, per contract) but
  stays under the ESP32 GPIO absolute-maximum of VDD+0.3V = 3.6V** (per
  [Espressif hardware-design FAQ](https://docs.espressif.com/projects/esp-faq/en/latest/hardware-related/hardware-design.html)
  and the ESP32 datasheet), so the fault is an accuracy/flagging problem, not
  by itself a GPIO-damage problem — **provided** the clamp diodes and 1 kΩ
  series resistor keep fault current within the clamp diodes' rated forward
  current and the ESP32 3V3D rail is present when the ADC link is fitted (per
  the contract's sequencing warning).
- **3V3A vs 3V3D mismatch:** the clamp's upper diode returns to 3V3D (ESP32's
  own rail), not 3V3A. If 3V3A is powered but 3V3D is not yet up (rail
  sequencing mismatch, explicitly flagged as a risk in
  docs/architecture.md/design-contract.md), TIA_OUT sitting near 1.65 V with
  no clamp reference on the 3V3D side could forward-bias the upper clamp
  diode into an unpowered 3V3D rail, back-feeding it through the diode and
  the ESP32's own supply network — this is exactly the "common-source
  start-up... rail ramp mismatch" and "powered-off backfeed" risk the
  contract already requires verifying and the ADC link to be disconnected
  for. No new risk beyond what's already documented, but this review confirms
  it is not merely theoretical: the clamp's reference rail (3V3D) and the
  signal's source rail (3V3A) are genuinely different supplies with no
  enforced sequencing in Rev A.

## Recommended changes

1. In docs/calculations.md, re-caption `CF ≈ sqrt(CT/(2π RF GBW))` as a
   *stability-boundary* estimate (40dB→20dB closure-rate boundary), not an
   implied 45°-phase-margin design point — Section 1 shows CF_45 (exact) and
   CF_doc differ by roughly 20–25% at the nominal corner and diverge further
   at other corners.
2. LDO field in docs/design-contract.md ("open — selected at the analog
   design review gate"): recommend locking to **TPS7A2033PDBVR** with 1 µF
   in/out ceramic caps (Section 4). This is a proposed value for the
   coordinator to lock, not a change made here.
3. Recommend adding BAT54S (or BAV99) as the specified ADC clamp-diode part
   number in the parts list — currently unspecified in the contract.
4. Recommend design-decisions.md re-pull the OPA380/381 en(f) figures and the
   OPA320 0.9pA-Ib figure directly from the datasheet PDF tables (not search
   snippets) before the hardware freeze — flagged as unverified, not wrong.

## PASS / NEEDS REVISION

**PASS with re-verification items.** The locked CF selections (1n/100p/10p)
are stable with large margin under every corner and assumption tested here
(worst case PM=66.9° at the most pessimistic 2×GBW second-pole assumption);
the analytical minimum-CF family is correctly framed by the contract as
stability evidence, not an operating point. No locked parameter is
contradicted by this analysis. Open items before hardware freeze: lock the
LDO (recommendation given), specify the clamp-diode part number
(recommendation given), and re-pull the handful of flagged datasheet figures
from primary PDF tables (Section 5) — none of these are expected to change
the circuit topology.
