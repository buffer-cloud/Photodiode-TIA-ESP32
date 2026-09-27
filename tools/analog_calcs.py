"""Deterministic analog design-review calculations for the photodiode TIA.

Reproduces every numbered result quoted in docs/analog-calculation-review.md.
No SPICE, no measured data. All formulas are shown alongside the code that
evaluates them so the derivation is auditable. Run with the project venv:

    .venv/bin/python tools/analog_calcs.py

Only numpy/scipy are used (both already in the venv). This script does not
modify any locked or simulation/firmware/hardware files; it is read-only
analysis support for docs/analog-calculation-review.md.
"""
import numpy as np
from scipy.optimize import brentq

# ---------------------------------------------------------------------------
# Constants (CALCULATED section constants, not datasheet values)
# ---------------------------------------------------------------------------
kB = 1.380649e-23          # J/K
T = 300.0                   # K
q = 1.602176634e-19         # C
VT4kT = 4 * kB * T           # 4kT, for Johnson-noise current PSD 4kT/R

# ---------------------------------------------------------------------------
# Locked circuit values (docs/design-contract.md) -- DO NOT EDIT THE CONTRACT
# ---------------------------------------------------------------------------
GAINS = [
    dict(name="10k",  RF=10e3, CF_sel=1e-9),
    dict(name="100k", RF=100e3, CF_sel=100e-12),
    dict(name="1M",   RF=1e6, CF_sel=10e-12),
]
CT_CORNERS = [40e-12, 80e-12, 120e-12]
CT_NOM = 80e-12
GBW_CORNERS = [10e6, 20e6, 30e6]
GBW_NOM = 20e6

RF_FILT = 3.3e3
CF_FILT = 100e-9
F_POLE_FILT = 1 / (2 * np.pi * RF_FILT * CF_FILT)      # 482.3 Hz (contract value)
R_ADC = 1e3
C_ADC = 10e-9
F_POLE_ADC = 1 / (2 * np.pi * R_ADC * C_ADC)            # 15.9 kHz (contract value)

VREF = 1.65
V_ADC_FLOOR = 0.25
V_ADC_CEIL = 2.40
DELTA_V_FS = VREF - V_ADC_FLOOR                          # 1.40 V (contract)

# OPA320/OPA2320 datasheet values (TI SBOS513F, https://www.ti.com/lit/ds/symlink/opa320.pdf)
OPA_EN_10K = 7.0e-9      # V/rtHz at 10 kHz (DATASHEET, TI product collateral + SBOS513F)
OPA_EN_1K = 8.5e-9       # V/rtHz at 1 kHz (DATASHEET, SBOS513F; matches docs/design-decisions.md)
OPA_IN = 0.6e-15         # A/rtHz current noise (DATASHEET, SBOS513F)
OPA_IB_TYP = 0.2e-12     # A, 25 C typical (DATASHEET, SBOS513F electrical table)
OPA_IB_MAX = 0.9e-12     # A (DATASHEET/marketing headline; flagged for confirmation, see report)
OPA_VOS_MAX = 150e-6     # V (DATASHEET, SBOS513F)
OPA_GBW = 20e6           # Hz (DATASHEET)
OPA_CDIFF = 5e-12        # F differential input capacitance (DATASHEET)
OPA_CCM = 4e-12          # F common-mode input capacitance (DATASHEET)
OPA_IQ = 1.45e-3         # A per channel (DATASHEET)
OPA_01_10HZ_PP = 2.8e-6  # V pk-pk, 0.1-10 Hz (DATASHEET)

# ---------------------------------------------------------------------------
# Core transfer functions
# ---------------------------------------------------------------------------

def s_of(f):
    return 1j * 2 * np.pi * f


def Zf(f, RF, CF):
    """Feedback impedance RF || CF."""
    s = s_of(f)
    return RF / (1 + s * RF * CF)


def NG(f, RF, CF, CT):
    """Noise gain 1 + Zf/Zin, Zin = 1/(sCT).
    = [1 + sRF(CT+CF)] / [1 + sRF CF]
    Zero at fz = 1/(2 pi RF (CT+CF)); pole at fp = 1/(2 pi RF CF);
    high-frequency asymptote 1 + CT/CF.
    """
    s = s_of(f)
    return (1 + s * RF * (CT + CF)) / (1 + s * RF * CF)


def Aol(f, GBW, f2=None):
    """Open-loop gain, single dominant pole Aol(s)=GBW/s, optional 2nd real pole."""
    a = GBW / (1j * f)
    if f2 is not None:
        a = a / (1 + 1j * f / f2)
    return a


def loop_gain(f, RF, CF, CT, GBW, f2=None):
    return Aol(f, GBW, f2) / NG(f, RF, CF, CT)


def phase_margin(RF, CF, CT, GBW, f2=None, f_lo=1.0, f_hi=None):
    """Numeric loop-gain crossover and phase margin (degrees)."""
    if f_hi is None:
        f_hi = 20 * GBW
    def mag_db(lf):
        f = 10 ** lf
        return 20 * np.log10(np.abs(loop_gain(f, RF, CF, CT, GBW, f2)))
    lo, hi = np.log10(f_lo), np.log10(f_hi)
    if mag_db(lo) < 0:
        return None, None  # never above unity: loop gain too low, unstable/no crossover
    if mag_db(hi) > 0:
        f_hi *= 100
        hi = np.log10(f_hi)
    lf_cross = brentq(mag_db, lo, hi, xtol=1e-6)
    f_cross = 10 ** lf_cross
    T = loop_gain(f_cross, RF, CF, CT, GBW, f2)
    pm = 180 + np.degrees(np.angle(T))
    return f_cross, pm


def closed_loop_2pole(RF, CF, CT, GBW):
    """Analytic 2nd-order closed-loop TIA response (single dominant-pole Aol).
    H(s) = -RF / [ a2 s^2 + a1 s + 1 ],  a2 = RF(CT+CF)/GBW, a1 = 1/GBW + RF*CF
    wo = 1/sqrt(a2); zeta = a1*wo/2 ; Q = 1/(2 zeta)
    """
    a2 = RF * (CT + CF) / GBW
    a1 = 1 / GBW + RF * CF
    wo = 1 / np.sqrt(a2)
    fo = wo / (2 * np.pi)
    zeta = a1 * wo / 2
    Q = 1 / (2 * zeta)
    # -3 dB frequency of standard 2nd-order lowpass, normalized x=(f/fo)^2
    b = 4 * zeta ** 2 - 2
    x = (-b + np.sqrt(b ** 2 + 4)) / 2
    f_3db = fo * np.sqrt(max(x, 0))
    if zeta < 1:
        overshoot = np.exp(-np.pi * zeta / np.sqrt(1 - zeta ** 2))
    else:
        overshoot = 0.0
    return dict(fo=fo, zeta=zeta, Q=Q, f_3db=f_3db, overshoot_pct=100 * overshoot)


def cf_for_target_pm(RF, CT, GBW, target_pm, f2=None):
    """Bisection: minimum CF that delivers >= target_pm degrees of phase margin."""
    def pm_of_cf(cf):
        _, pm = phase_margin(RF, cf, CT, GBW, f2)
        return pm if pm is not None else -999
    lo, hi = 1e-15, 1e-8
    if pm_of_cf(hi) < target_pm:
        hi = 1e-6
    # Monotonic increasing PM with CF assumed over this bracket.
    return brentq(lambda cf: pm_of_cf(cf) - target_pm, lo, hi, xtol=1e-16)


def cf_for_butterworth(RF, CT, GBW):
    """Bisection: CF giving closed-loop Q = 1/sqrt(2) (maximally flat)."""
    target_Q = 1 / np.sqrt(2)
    def Q_of_cf(cf):
        return closed_loop_2pole(RF, cf, CT, GBW)["Q"] - target_Q
    lo, hi = 1e-15, 1e-8
    return brentq(Q_of_cf, lo, hi, xtol=1e-16)


def cf_graeme_formula(RF, CT, GBW):
    return np.sqrt(CT / (2 * np.pi * RF * GBW))


# ---------------------------------------------------------------------------
# Section 1: CF analysis
# ---------------------------------------------------------------------------

def section1():
    print("=" * 78)
    print("SECTION 1: Feedback capacitor CF analysis")
    print("=" * 78)
    print(
        "\nNoise gain NG(s) = [1 + sRF(CT+CF)] / [1 + sRF CF]\n"
        "  zero fz = 1/(2*pi*RF*(CT+CF)), pole fp = 1/(2*pi*RF*CF)\n"
        "  high-freq asymptote NGhf = 1 + CT/CF\n"
        "Loop gain T(s) = Aol(s)/NG(s), Aol(s) = GBW/s (single dominant pole)\n"
        "Closed loop (2nd order): H(s) = -RF/[a2 s^2 + a1 s + 1]\n"
        "  a2 = RF(CT+CF)/GBW, a1 = 1/GBW + RF*CF, wo=1/sqrt(a2), Q=1/(2*zeta)\n"
    )

    print("-- CF for 45 deg phase margin (Graeme exact loop-gain form), and for")
    print("   closed-loop Butterworth Q=0.707, vs the doc's CF = sqrt(CT/(2 pi RF GBW)) --\n")
    hdr = f"{'RF':>8} {'CT(pF)':>7} {'GBW(MHz)':>9} {'CF_45(pF)':>10} {'CF_butter(pF)':>14} {'CF_doc(pF)':>11} {'CF45/CFdoc':>11}"
    print(hdr)
    doc_rows = {}
    for g in GAINS:
        RF = g["RF"]
        for CT in CT_CORNERS:
            for GBW in GBW_CORNERS:
                cf45 = cf_for_target_pm(RF, CT, GBW, 45.0)
                cfb = cf_for_butterworth(RF, CT, GBW)
                cfdoc = cf_graeme_formula(RF, CT, GBW)
                print(f"{g['name']:>8} {CT*1e12:7.0f} {GBW/1e6:9.0f} {cf45*1e12:10.3f} "
                      f"{cfb*1e12:14.3f} {cfdoc*1e12:11.3f} {cf45/cfdoc:11.3f}")
                if CT == CT_NOM and GBW == GBW_NOM:
                    doc_rows[g["name"]] = cfdoc
    print(
        "\nInterpretation: CF_doc = sqrt(CT/(2*pi*RF*GBW)) is the CF that places the\n"
        "noise-gain pole fp exactly at the frequency where the RISING noise-gain\n"
        "asymptote (using CT alone as the input zero, i.e. ignoring CF's own\n"
        "contribution to that zero) crosses Aol(f)=GBW/f. That is the boundary\n"
        "between a 40 dB/decade loop-gain closure (poor/marginal phase margin,\n"
        "double-pole intersection) and a 20 dB/decade closure (good margin). It is\n"
        "a STABILITY-BOUNDARY estimate, not a guaranteed-45-degree design value --\n"
        "the table above shows CF_45 (exact, from the full NG(s) including CF in\n"
        "the zero) is typically within roughly a factor of ~1.5-2x of CF_doc,\n"
        "confirming CF_doc is the right order of magnitude but optimistic at low\n"
        "RF*CT*GBW products. Docs/calculations.md values (8.0/2.5/0.8 pF at\n"
        f"CT=80pF, GBW=20MHz) reproduce here as {doc_rows}."
    )

    print("\n-- Selected CF (1n/100p/10p): NG zero/pole, loop crossover, phase margin,")
    print("   closed-loop -3dB/Q/overshoot, at CT=80pF nominal, GBW=20MHz nominal --\n")
    print("ASSUMPTION: OPA320/2320 second real pole not separately tabulated in the")
    print("datasheet's electrical-characteristics table; only a graphical open-loop")
    print("gain/phase plot is given (SBOS513F Fig. 'Open-Loop Gain and Phase vs")
    print("Frequency'), which could not be digitized from this environment. We")
    print("assume a second pole at f2 = 3x GBW = 60 MHz as a typical CMOS-input")
    print("op-amp rule of thumb, and sweep 2x/3x/5x GBW to bound the sensitivity.\n")

    for g in GAINS:
        RF, CF = g["RF"], g["CF_sel"]
        fz = 1 / (2 * np.pi * RF * (CT_NOM + CF))
        fp = 1 / (2 * np.pi * RF * CF)
        cl = closed_loop_2pole(RF, CF, CT_NOM, GBW_NOM)
        print(f"RF={g['name']}: NG zero={fz:9.2f} Hz, NG pole={fp:12.1f} Hz, "
              f"NGhf={1+CT_NOM/CF:6.3f}")
        for mult, label in [(None, "single-pole Aol"), (2, "f2=2xGBW"), (3, "f2=3xGBW"), (5, "f2=5xGBW")]:
            f2 = None if mult is None else mult * GBW_NOM
            fcross, pm = phase_margin(RF, CF, CT_NOM, GBW_NOM, f2)
            print(f"    {label:16s}: crossover={fcross:10.1f} Hz  PM={pm:6.2f} deg")
        print(f"    closed-loop (single-pole Aol): f_3dB={cl['f_3db']:10.1f} Hz  "
              f"Q={cl['Q']:.3f}  zeta={cl['zeta']:.3f}  overshoot={cl['overshoot_pct']:.2f}%")
        print(f"    contract target f_3dB = 1/(2*pi*RF*CF) = {1/(2*np.pi*RF*CF):.1f} Hz "
              f"(bare RC pole, ~= closed-loop f_3dB above since PM is large)\n")

    print("-- Sensitivity sweep: 0.5x/1x/2x of analytical CF_45(CT=80,GBW=20) AND")
    print("   0.5x/1x/2x of the selected CF, for comparison with the SPICE sweep --\n")
    print(f"{'RF':>6} {'CF basis':>10} {'mult':>5} {'CF(pF)':>9} {'PM(deg,f2=3xGBW)':>18} "
          f"{'Q':>6} {'f3dB(Hz)':>10} {'overshoot%':>11} {'flag':>8}")
    marginal_notes = []
    for g in GAINS:
        RF, CF_sel = g["RF"], g["CF_sel"]
        cf45 = cf_for_target_pm(RF, CT_NOM, GBW_NOM, 45.0)
        for basis_name, cf_base in [("CF_45", cf45), ("CF_sel", CF_sel)]:
            for mult in (0.5, 1.0, 2.0):
                cf = cf_base * mult
                _, pm = phase_margin(RF, cf, CT_NOM, GBW_NOM, 3 * GBW_NOM)
                cl = closed_loop_2pole(RF, cf, CT_NOM, GBW_NOM)
                flag = "MARGINAL" if (pm is not None and pm < 45) or cl["overshoot_pct"] > 10 else "ok"
                if flag == "MARGINAL":
                    marginal_notes.append((g["name"], basis_name, mult, pm, cl["overshoot_pct"]))
                pm_s = f"{pm:6.1f}" if pm is not None else "  none"
                print(f"{g['name']:>6} {basis_name:>10} {mult:5.1f} {cf*1e12:9.3f} {pm_s:>18} "
                      f"{cl['Q']:6.3f} {cl['f_3db']:10.1f} {cl['overshoot_pct']:11.2f} {flag:>8}")
    print("\nMarginal cases (PM<45 deg or overshoot>10%):")
    for row in marginal_notes:
        print(f"  RF={row[0]} basis={row[1]} mult={row[2]}x  PM={row[3]}  overshoot={row[4]:.2f}%")
    if not marginal_notes:
        print("  none")
    return doc_rows


# ---------------------------------------------------------------------------
# Section 2: per-gain table
# ---------------------------------------------------------------------------

def section2():
    print("\n" + "=" * 78)
    print("SECTION 2: Per-gain transfer, saturation, bandwidth, dark offset")
    print("=" * 78 + "\n")
    print(f"{'RF':>6} {'CF':>7} {'TZ(V/A)':>10} {'Ifs_ADC(uA)':>12} {'Ifs_opamp(uA)':>14} "
          f"{'BW(kHz)':>8} {'Vout_range(V)':>14}")
    results = []
    for g in GAINS:
        RF, CF = g["RF"], g["CF_sel"]
        i_fs_adc = DELTA_V_FS / RF                       # to 0.25 V floor (contract)
        # Output swing floor with light (>10k) load per OPA2320 datasheet: 0.1 V from
        # V- rail (RL=10kOhm spec; our downstream load is a 3.3k RC into a follower,
        # effectively light loading). Available swing before op-amp saturates:
        v_swing_opamp = VREF - 0.10
        i_fs_opamp = v_swing_opamp / RF
        bw = 1 / (2 * np.pi * RF * CF)
        results.append((g["name"], CF, RF, i_fs_adc, i_fs_opamp, bw))
        print(f"{g['name']:>6} {CF*1e12:6.0f}p {RF:10.0f} {i_fs_adc*1e6:12.2f} "
              f"{i_fs_opamp*1e6:14.2f} {bw/1e3:8.2f} {'0.25-1.65':>14}")
    print(
        "\nADC window (0.25 V floor) is the binding saturation limit in every gain\n"
        "(Ifs_ADC < Ifs_opamp): the op-amp's own output stage has ~1.55 V of\n"
        "additional headroom below 0.25 V (down to ~0.10 V) that the ADC spec\n"
        "cannot use, i.e. TIA_OUT can run into the amplifier's own rail limit\n"
        "under overload before it hits 0 V, which matters for recovery time but\n"
        "not for the defined full-scale.\n"
    )
    print("-- Dark-offset scenarios (BPW34 dark current at 10V bias, illustrative; not")
    print("   valid at our 1.65V bias -- see hardware/datasheets/README.md) --\n")
    print(f"{'RF':>6} {'Idark=2nA(uV)':>14} {'Idark=30nA(uV)':>15} {'Ib_typ=0.2pA(uV)':>17} "
          f"{'Ib_max=0.9pA(uV)':>17} {'Vos_max=150uV contribution':>27}")
    for g in GAINS:
        RF = g["RF"]
        print(f"{g['name']:>6} {2e-9*RF*1e6:14.1f} {30e-9*RF*1e6:15.1f} "
              f"{OPA_IB_TYP*RF*1e6:17.4f} {OPA_IB_MAX*RF*1e6:17.4f} {OPA_VOS_MAX*1e6:27.1f}")
    return results


# ---------------------------------------------------------------------------
# Section 3: noise budget
# ---------------------------------------------------------------------------

def sys_filter_mag2(f, stage="adc"):
    """|H|^2 of the downstream RC chain, stage in {"tia","filter1","filter2","adc"}
    tia: no filtering (at TIA_OUT)
    filter1: one 482 Hz pole (signal at node between RC1 and its follower)
    filter2 / adc-pre: two 482 Hz poles (at FILTER_OUT, before ADC RC)
    adc: two 482 Hz poles + one 15.9 kHz ADC pole (at ADC pin)
    """
    h1 = 1 / (1 + 1j * f / F_POLE_FILT)
    h_adc = 1 / (1 + 1j * f / F_POLE_ADC)
    if stage == "tia":
        h = 1.0
    elif stage == "filter1":
        h = h1
    elif stage == "filter2":
        h = h1 ** 2
    elif stage == "adc":
        h = (h1 ** 2) * h_adc
    else:
        raise ValueError(stage)
    return np.abs(h) ** 2


def integrate_psd(f, psd2):
    """Integrate a one-sided PSD (already squared, V^2/Hz or A^2/Hz) over f
    (log-spaced) using d(ln f) with the f Jacobian, trapezoidal."""
    lnf = np.log(f)
    integrand = psd2 * f
    trapz = getattr(np, "trapezoid", None) or np.trapz
    return np.sqrt(trapz(integrand, lnf))


def en_of_f(f):
    """OPA320 en(f): white 7 nV/rtHz above ~10kHz flattening to 8.5 nV/rtHz at 1kHz,
    with a 1/f term whose corner is fit so that the integral 0.1-10 Hz matches the
    datasheet's 2.8 uVpp spec (assumption: Gaussian peak-to-peak ~ 6.6x rms, i.e.
    rms_0.1_10Hz = 2.8/6.6 = 0.42 uVrms -> fc solved once, see main()).
    """
    global _EN_FC
    return OPA_EN_10K * np.sqrt(1 + _EN_FC / f)


_EN_FC = 200.0  # Hz, solved in main() from the 0.1-10Hz pk-pk spec


def solve_en_fc():
    """Solve 1/f corner fc so white(1+fc/f) integrated 0.1-10Hz rms matches
    2.8 uVpp / 6.6 (approx pk-pk to rms factor for Gaussian noise, ~6.6x is the
    commonly used engineering approximation for 0.1-10 Hz specs)."""
    global _EN_FC
    target_rms = OPA_01_10HZ_PP / 6.6
    f = np.logspace(np.log10(0.1), np.log10(10), 4000)
    def resid(fc):
        psd2 = (OPA_EN_10K ** 2) * (1 + fc / f)
        rms = integrate_psd(f, psd2)
        return rms - target_rms
    try:
        fc = brentq(resid, 1e-3, 1e6)
    except ValueError:
        fc = 200.0
    _EN_FC = fc
    return fc


def divider_buffer_noise_psd(f):
    """VREF divider (5k Thevenin, 9.1 nV/rtHz white) filtered by its own 3.15 Hz
    pole (10.1 uF at the midpoint), plus the OPA2320 buffer's own en (unfiltered
    by that pole, added after it), all referred to VREF (pre-NG)."""
    f_div_pole = 1 / (2 * np.pi * 5e3 * 10.1e-6)  # ~3.15 Hz
    e_div = 9.1e-9 / np.sqrt(1 + (f / f_div_pole) ** 2)
    e_buf = en_of_f(f)
    return e_div ** 2 + e_buf ** 2


def section3(ldo_noise_density_vrthz=100e-9):
    print("\n" + "=" * 78)
    print("SECTION 3: Noise budget (input-referred and output-referred)")
    print("=" * 78 + "\n")
    fc = solve_en_fc()
    print(f"OPA320 en(f) 1/f corner solved from 2.8 uVpp(0.1-10Hz) spec: fc={fc:.1f} Hz "
          "(ASSUMPTION: pk-pk/rms=6.6 Gaussian-crest-factor conversion)\n")

    print(f"LDO noise density used for supply-coupling estimate: {ldo_noise_density_vrthz*1e9:.0f} "
          "nV/rtHz flat approximation (placeholder; parametrized, see Section 4 for candidates)\n")
    print("NOTE: en(f)*NG(f) and the reference-buffer noise do not roll off at high")
    print("frequency (NG plateaus at 1+CT/CF instead of decaying); physically this")
    print("plateau only persists while loop gain Aol/NG > 1. Each gain's integration")
    print("upper bound is therefore capped at its own single-pole loop-gain crossover")
    print("(from Section 1) rather than a single fixed frequency, else the 1M-ohm")
    print("case would be over-integrated by roughly the ratio of a fixed 20MHz cap to")
    print("its actual ~2.2MHz crossover (~3x too high at TIA_OUT).\n")

    hdr = (f"{'RF':>6} {'level':>10} {'i_in(pArms)':>12} {'v_TIAOUT(uVrms)':>16} "
           f"{'v_ADC(uVrms)':>13} {'dominant':>28}")
    print(hdr)

    summary = {}
    for g in GAINS:
        RF, CF = g["RF"], g["CF_sel"]
        i_fs = DELTA_V_FS / RF
        levels = [("dark(2nA)", 2e-9), ("10%FS", 0.1 * i_fs), ("50%FS", 0.5 * i_fs), ("100%FS", i_fs)]

        f_cross, _ = phase_margin(RF, CF, CT_NOM, GBW_NOM)
        f_max = max(3 * f_cross, 10 * F_POLE_ADC)
        f = np.logspace(-1, np.log10(f_max), 6000)

        zf2 = np.abs(Zf(f, RF, CF)) ** 2
        ng2 = np.abs(NG(f, RF, CF, CT_NOM)) ** 2
        sys_adc2 = sys_filter_mag2(f, "adc")
        sys_tia2 = sys_filter_mag2(f, "tia")

        # RF Johnson (white current PSD 4kT/RF), via Zf
        i_rf2 = VT4kT / RF
        v_rf_tia2 = i_rf2 * zf2
        v_rf_adc2 = v_rf_tia2 * sys_adc2

        # op-amp current noise, via Zf
        i_inamp2 = OPA_IN ** 2
        v_inamp_tia2 = i_inamp2 * zf2
        v_inamp_adc2 = v_inamp_tia2 * sys_adc2

        # op-amp voltage noise, via NG
        en2 = en_of_f(f) ** 2
        v_en_tia2 = en2 * ng2
        v_en_adc2 = v_en_tia2 * sys_adc2

        # reference divider + buffer, via NG
        vref2 = divider_buffer_noise_psd(f)
        v_ref_tia2 = vref2 * ng2
        v_ref_adc2 = v_ref_tia2 * sys_adc2

        # supply noise coupling through CD (photodiode+amp input cap ~ CT) into SUM:
        # transfer = j*2pi*f*CD*Zf(f); flat LDO density assumed.
        CD = CT_NOM
        supply_psd2 = ldo_noise_density_vrthz ** 2
        h_supply2 = np.abs(1j * 2 * np.pi * f * CD * Zf(f, RF, CF)) ** 2
        v_sup_cd_tia2 = supply_psd2 * h_supply2
        v_sup_cd_adc2 = v_sup_cd_tia2 * sys_adc2
        # supply noise via divider attenuation (~0.5 at DC, ideal equal resistors)
        # then through NG and PSRR path combined order-of-magnitude (kept separate,
        # not RSS'd with the CD path per docs/calculations.md correlated-source note)
        v_sup_div_tia2 = (0.5 * ldo_noise_density_vrthz) ** 2 * ng2
        v_sup_div_adc2 = v_sup_div_tia2 * sys_adc2

        for label, i_level in levels:
            i_shot2 = 2 * q * abs(i_level)               # white shot PSD (A^2/Hz)
            v_shot_tia2 = i_shot2 * zf2
            v_shot_adc2 = v_shot_tia2 * sys_adc2

            # Totals (RSS of independent sources; supply paths kept out of the
            # headline RSS and reported separately as they are correlated with
            # each other, per docs/calculations.md guidance)
            v_tia2 = v_shot_tia2 + v_rf_tia2 + v_inamp_tia2 + v_en_tia2 + v_ref_tia2
            v_adc2 = v_shot_adc2 + v_rf_adc2 + v_inamp_adc2 + v_en_adc2 + v_ref_adc2

            v_tia_rms = integrate_psd(f, v_tia2)
            v_adc_rms = integrate_psd(f, v_adc2)
            i_in_rms = v_tia_rms / RF  # input-referred current, TIA-output convention

            contributions = {
                "shot": integrate_psd(f, v_shot_adc2),
                "RF_johnson": integrate_psd(f, v_rf_adc2),
                "opamp_in": integrate_psd(f, v_inamp_adc2),
                "opamp_en": integrate_psd(f, v_en_adc2),
                "vref_divider_buffer": integrate_psd(f, v_ref_adc2),
            }
            dominant = max(contributions, key=contributions.get)
            summary[(g["name"], label)] = dict(i_in_rms=i_in_rms, v_tia_rms=v_tia_rms,
                                                v_adc_rms=v_adc_rms, dominant=dominant,
                                                contributions=contributions)
            print(f"{g['name']:>6} {label:>10} {i_in_rms*1e12:12.3f} {v_tia_rms*1e6:16.3f} "
                  f"{v_adc_rms*1e6:13.3f} {dominant:>28}")

        # supply coupling reported separately (order-of-magnitude, correlated source)
        v_sup_cd_adc_rms = integrate_psd(f, v_sup_cd_adc2)
        v_sup_div_adc_rms = integrate_psd(f, v_sup_div_adc2)
        print(f"    -> supply coupling via CD into SUM (uVrms at ADC): {v_sup_cd_adc_rms*1e6:.4f}  "
              f"via divider attenuation+NG (uVrms at ADC): {v_sup_div_adc_rms*1e6:.4f}  "
              f"[LDO density {ldo_noise_density_vrthz*1e9:.0f} nV/rtHz]")

    # ADC quantization
    fs_v = 2.45  # 11 dB suggested max per Espressif guide
    lsb = fs_v / 4096
    q_rms = lsb / np.sqrt(12)
    print(f"\nESP32 ADC quantization (CALCULATED): LSB={lsb*1e3:.3f} mV, "
          f"quant noise rms = LSB/sqrt(12) = {q_rms*1e6:.1f} uVrms")
    print("ESP32 ADC noise floor beyond quantization: no Espressif-published RMS")
    print("noise-density spec found (SAR ADC characteristics table absent in public")
    print("ESP-IDF/datasheet search results). Community measurement (esp32.com forum,")
    print("single-ended GPIO34-class pin, stable ~1mV input): raw code spread of")
    print("roughly +/-15 LSB about the mode was reported; at 11dB atten LSB~=0.6mV,")
    print("giving an order-of-magnitude unfiltered noise floor of a few mV (peak-to-")
    print("peak), i.e. roughly 5-15x the calculated quantization noise. This figure is")
    print("COMMUNITY-SOURCED, not an Espressif datasheet number, and is cited in the")
    print("report as UNCERTAIN / needs bench confirmation (matches docs/calculations.md).")
    return summary


# ---------------------------------------------------------------------------
# Section 4: LDO current budget
# ---------------------------------------------------------------------------

def section4():
    print("\n" + "=" * 78)
    print("SECTION 4: Analog rail current budget for LDO selection")
    print("=" * 78 + "\n")
    n_channels = 4  # U1A, U1B, U2A, U2B (two OPA2320 duals)
    i_amps = n_channels * OPA_IQ
    i_divider = VREF * 2 / (10e3 + 10e3) * 1e3  # not used directly; divider current below
    i_div = 3.3 / (10e3 + 10e3)
    i_total_typ = i_amps + i_div
    print(f"4x OPA2320 channel Iq (typ, DATASHEET) = {i_amps*1e3:.2f} mA")
    print(f"10k/10k divider current (3.3V/20k)      = {i_div*1e3:.3f} mA")
    print(f"Total analog-rail steady current (typ)  = {i_total_typ*1e3:.2f} mA")
    print("Design margin recommendation: budget >=2x typ for inrush/tolerance -> "
          f"target LDO Iout_max >= {2*i_total_typ*1e3:.0f} mA (spec candidates are 150-300 mA, ample).")
    return i_total_typ


if __name__ == "__main__":
    section1()
    section2()
    section3(ldo_noise_density_vrthz=100e-9)   # generic placeholder density, see report
    section3(ldo_noise_density_vrthz=20e-9)    # ~ candidate low-noise LDO order-of-magnitude
    section4()
