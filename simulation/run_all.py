#!/usr/bin/env python3
"""
Run the full LTspice photodiode-TIA simulation suite (batch mode), parse the
binary .raw outputs (small self-contained parser, no external raw-reader
dependency), extract stability/DC/transient/noise metrics, and write:
  simulation/results/summary.csv
  simulation/results/summary.json
  simulation/plots/*.png   (<=10 files, titles contain "SIMULATED")

All numbers produced here are SIMULATED (LTspice), never measured.
"""
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
LTDIR = ROOT / "ltspice"
PLOTDIR = ROOT / "plots"
RESDIR = ROOT / "results"
LTSPICE_BIN = "/Applications/LTspice.app/Contents/MacOS/LTspice"

NETLISTS = [
    "tia_ac.cir",
    "tia_ac_parasitic.cir",
    "tia_behavioral_ac.cir",
    "tia_dc.cir",
    "tia_loop.cir",
    "tia_noise_adc.cir",
    "tia_noise_tia.cir",
    "tia_tran.cir",
    "tia_vref_startup.cir",
    "tia_vref_psrr.cir",
]

GAIN_LABEL = {1: "10k/1n", 2: "100k/100p", 3: "1M/10p"}
RF_VAL = {1: 10e3, 2: 100e3, 3: 1e6}
FS_CURRENT = {1: 1.40 / 10e3, 2: 1.40 / 100e3, 3: 1.40 / 1e6}

# ---------------------------------------------------------------------------
# LTspice runner
# ---------------------------------------------------------------------------

def run_ltspice(name):
    print(f"[run] {name}")
    r = subprocess.run([LTSPICE_BIN, "-b", name], cwd=str(LTDIR),
                        capture_output=True, text=True, timeout=600)
    if r.returncode not in (0, None):
        print(f"  return code {r.returncode}")


# ---------------------------------------------------------------------------
# Minimal binary .raw parser (real + complex, stepped or not)
# ---------------------------------------------------------------------------

def read_log_steps(log_path):
    """Return list of dicts, one per .step run, param name -> float value.
    Returns [{}] if the netlist has no .step."""
    txt = log_path.read_text(encoding="utf-16-le", errors="ignore")
    lines = [l.strip() for l in txt.splitlines() if l.strip().startswith(".step ")]
    if not lines:
        return [{}]
    out = []
    for l in lines:
        d = {}
        for tok in l[len(".step "):].split():
            if "=" in tok:
                k, v = tok.split("=", 1)
                try:
                    d[k] = float(v)
                except ValueError:
                    d[k] = v
        out.append(d)
    return out


def read_raw(raw_path):
    data = raw_path.read_bytes()
    marker = "Binary:\n".encode("utf-16le")
    idx = data.find(marker)
    header_txt = data[:idx].decode("utf-16le", errors="ignore")
    start = idx + len(marker)

    flags_line = re.search(r"^Flags:\s*(.*)$", header_txt, re.M).group(1)
    is_complex = "complex" in flags_line
    nvars = int(re.search(r"^No\. Variables:\s*(\d+)", header_txt, re.M).group(1))
    npoints = int(re.search(r"^No\. Points:\s*(\d+)", header_txt, re.M).group(1))
    varnames = []
    for m in re.finditer(r"^\t(\d+)\t(\S+)\t(\S+)", header_txt, re.M):
        varnames.append(m.group(2))
    assert len(varnames) == nvars, (len(varnames), nvars)

    blob = data[start:]
    if is_complex:
        arr = np.frombuffer(blob, dtype="<c16", count=npoints * nvars)
        arr = arr.reshape(npoints, nvars)
    else:
        dt = np.dtype([("v0", "<f8")] + [(f"v{i}", "<f4") for i in range(1, nvars)])
        rec = np.frombuffer(blob, dtype=dt, count=npoints)
        arr = np.empty((npoints, nvars), dtype=np.complex128)
        arr[:, 0] = rec["v0"].astype(np.complex128)
        for i in range(1, nvars):
            arr[:, i] = rec[f"v{i}"].astype(np.complex128)

    return {"vars": varnames, "data": arr, "complex": is_complex}


def split_runs(raw, steps):
    """Segment the concatenated points by resets in the first (sweep) column."""
    x0 = raw["data"][:, 0].real
    resets = np.where(np.diff(x0) < 0)[0] + 1
    bounds = [0] + list(resets) + [len(x0)]
    segs = []
    for i in range(len(bounds) - 1):
        lo, hi = bounds[i], bounds[i + 1]
        seg = raw["data"][lo:hi, :]
        params = steps[i] if i < len(steps) else {}
        cols = {name: seg[:, j] for j, name in enumerate(raw["vars"])}
        segs.append({"params": params, "cols": cols})
    if len(segs) != max(len(steps), 1):
        print(f"  [warn] segment count {len(segs)} != step count {len(steps)}")
    return segs


def load(name):
    raw = read_raw(LTDIR / (Path(name).stem + ".raw"))
    steps = read_log_steps(LTDIR / (Path(name).stem + ".log"))
    return split_runs(raw, steps)


def sel(runs, **kw):
    """Select runs whose params match all given key/value pairs (float compare)."""
    out = []
    for r in runs:
        ok = True
        for k, v in kw.items():
            if k not in r["params"] or abs(r["params"][k] - v) > 1e-9:
                ok = False
                break
        if ok:
            out.append(r)
    return out


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def db(x):
    return 20 * np.log10(np.maximum(np.abs(x), 1e-30))


def find_3db_bw(freq, mag_db):
    ref = mag_db[0]
    target = ref - 3.0
    below = np.where(mag_db <= target)[0]
    if len(below) == 0:
        return float("nan")
    i = below[0]
    if i == 0:
        return float(freq[0])
    f0, f1 = freq[i - 1], freq[i]
    m0, m1 = mag_db[i - 1], mag_db[i]
    if m1 == m0:
        return float(f1)
    frac = (target - m0) / (m1 - m0)
    return float(np.exp(np.log(f0) + frac * (np.log(f1) - np.log(f0))))


def peaking_db(mag_db):
    return float(np.max(mag_db) - mag_db[0])


def phase_margin(freq, T):
    magdb = db(T)
    below = np.where(magdb <= 0)[0]
    if len(below) == 0:
        return float("nan"), float("nan")
    i = below[0]
    if i == 0:
        fc = freq[0]
    else:
        f0, f1 = freq[i - 1], freq[i]
        m0, m1 = magdb[i - 1], magdb[i]
        frac = (0 - m0) / (m1 - m0) if m1 != m0 else 0
        fc = np.exp(np.log(f0) + frac * (np.log(f1) - np.log(f0)))
    ang = np.degrees(np.unwrap(np.angle(T)))
    ang_at_fc = np.interp(np.log(fc), np.log(freq), ang)
    pm = 180.0 + ang_at_fc
    return float(pm), float(fc)


def interp_at_current(iphoto, vout, target):
    x, y = iphoto.real, vout.real
    if y[-1] < y[0]:
        x, y = x[::-1], y[::-1]
    order = np.argsort(y)
    y_s, x_s = y[order], x[order]
    if target < y_s[0] or target > y_s[-1]:
        return float("nan")
    return float(np.interp(target, y_s, x_s))


def overshoot_settle(t, v, t_edge, t_end):
    mask = t >= t_edge
    tt, vv = t[mask].real, v[mask].real
    v0 = vv[0]
    vf = vv[-1]
    span = vf - v0
    if abs(span) < 1e-15:
        return 0.0, 0.0
    peak = vv[np.argmax(vv)] if span > 0 else vv[np.argmin(vv)]
    overshoot_pct = 100.0 * (peak - vf) / span if span > 0 else 100.0 * (vf - peak) / span
    overshoot_pct = max(overshoot_pct, 0.0)
    tol = 0.01 * abs(span)
    err = np.abs(vv - vf)
    ok = err <= tol
    settle_t = float("nan")
    for i in range(len(ok)):
        if np.all(ok[i:]):
            settle_t = tt[i] - t_edge
            break
    return float(overshoot_pct), settle_t


def recovery_time(t, v, t_mid, t_end, tol_frac=0.02):
    mask = t >= t_mid
    tt, vv = t[mask].real, v[mask].real
    vf = vv[-1]
    span_ref = np.max(np.abs(vv - vf))
    tol = max(tol_frac * span_ref, 1e-6)
    err = np.abs(vv - vf)
    ok = err <= tol
    for i in range(len(ok)):
        if np.all(ok[i:]):
            return float(tt[i] - t_mid)
    return float("nan")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    PLOTDIR.mkdir(parents=True, exist_ok=True)
    RESDIR.mkdir(parents=True, exist_ok=True)

    for nl in NETLISTS:
        run_ltspice(nl)

    ac = load("tia_ac.cir")
    ac_par = load("tia_ac_parasitic.cir")
    beh = load("tia_behavioral_ac.cir")
    dc = load("tia_dc.cir")
    loop = load("tia_loop.cir")
    n_adc = load("tia_noise_adc.cir")
    n_tia = load("tia_noise_tia.cir")
    tran = load("tia_tran.cir")
    vref_start = load("tia_vref_startup.cir")[0]
    vref_psrr = load("tia_vref_psrr.cir")[0]

    rows = []          # detailed CF/CT sensitivity sweep rows
    headline = []       # per-gain headline summary rows
    figs_done = []

    # ---- 1) DC transfer per gain --------------------------------------
    fig, ax = plt.subplots(figsize=(6, 4.5))
    dc_extra = {}
    for gi in (1, 2, 3):
        r = sel(dc, gi=float(gi))[0]
        iph = r["cols"]["iphoto"].real
        vtia = r["cols"]["V(tia)"].real
        vadc = r["cols"]["V(adc)"].real
        ax.plot(iph * 1e6, vtia, label=f"V(TIA) {GAIN_LABEL[gi]}")
        ax.plot(iph * 1e6, vadc, "--", label=f"V(ADC) {GAIN_LABEL[gi]}")
        i_025 = interp_at_current(r["cols"]["iphoto"], r["cols"]["V(tia)"], 0.25)
        i_rail = interp_at_current(r["cols"]["iphoto"], r["cols"]["V(tia)"], 3.05)
        dc_extra[gi] = dict(dark_vtia=float(vtia[0]), dark_vadc=float(vadc[0]),
                            i_at_0p25V=i_025, i_at_rail=i_rail,
                            vtia_min=float(np.min(vtia)), vtia_max=float(np.max(vtia)),
                            vadc_min=float(np.min(vadc)), vadc_max=float(np.max(vadc)))
    ax.set_xlabel("Iphoto (uA)")
    ax.set_ylabel("Output (V)")
    ax.set_title("SIMULATED DC transfer, V(TIA) & V(ADC) vs Iphoto (vendor OPAx320)")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(PLOTDIR / "01_dc_transfer.png", dpi=130)
    plt.close(fig)
    figs_done.append("01_dc_transfer.png")

    # ---- 2) AC transimpedance per gain (selected CF, nominal CT) ------
    fig, axs = plt.subplots(1, 2, figsize=(10, 4.5))
    ac_extra = {}
    for gi in (1, 2, 3):
        r = sel(ac, gi=float(gi), cfi=5.0, cti=2.0)[0]
        f = r["cols"]["frequency"].real
        vtia = r["cols"]["V(tia)"]
        vadc = r["cols"]["V(adc)"]
        dbt, dba = db(vtia), db(vadc)
        axs[0].semilogx(f, dbt, label=GAIN_LABEL[gi])
        axs[1].semilogx(f, dba, label=GAIN_LABEL[gi])
        ac_extra[gi] = dict(dc_gain_dbohm=float(dbt[0]),
                            dc_gain_ohm=float(np.abs(vtia[0])),
                            bw_tia_hz=find_3db_bw(f, dbt),
                            bw_adc_hz=find_3db_bw(f, dba),
                            peaking_tia_db=peaking_db(dbt),
                            peaking_adc_db=peaking_db(dba))
    axs[0].set_title("TIA_OUT |V(tia)/Iphoto| (selected CF, CT=80p)")
    axs[1].set_title("V(ADC) |V(adc)/Iphoto| (selected CF, CT=80p)")
    for a in axs:
        a.set_xlabel("Hz"); a.set_ylabel("dBohm"); a.legend(fontsize=8); a.grid(True, alpha=0.3)
    fig.suptitle("SIMULATED closed-loop transimpedance AC response (vendor OPAx320)")
    fig.tight_layout()
    fig.savefig(PLOTDIR / "02_ac_transimpedance.png", dpi=130)
    plt.close(fig)
    figs_done.append("02_ac_transimpedance.png")

    # ---- 3) CF-sweep peaking & PM, CT corners (all cfi,cti) -----------
    cfi_label = {1: "0.5x CFmin", 2: "1x CFmin", 3: "2x CFmin",
                 4: "0.5x CFsel", 5: "1x CFsel", 6: "2x CFsel"}
    cti_label = {1: "CT=40p", 2: "CT=80p", 3: "CT=120p"}
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.5))
    marginal = []
    for gi in (1, 2, 3):
        for cfi in range(1, 7):
            for cti in (1, 2, 3):
                r_ac = sel(ac, gi=float(gi), cfi=float(cfi), cti=float(cti))
                r_lp = sel(loop, gi=float(gi), cfi=float(cfi), cti=float(cti))
                if not r_ac or not r_lp:
                    continue
                r_ac, r_lp = r_ac[0], r_lp[0]
                f = r_ac["cols"]["frequency"].real
                dbt = db(r_ac["cols"]["V(tia)"])
                pk = peaking_db(dbt)
                Vtia_loop = r_lp["cols"]["V(tia)"]
                T = -(1.0 + Vtia_loop) / Vtia_loop  # T = -V(tia_amp)/V(tia), V(tia_amp)=V(tia)+1
                pm, fc = phase_margin(r_lp["cols"]["frequency"].real, T)
                flag = (pm < 45) or (pk > 1.0)
                rows.append(dict(gain=GAIN_LABEL[gi], RF=RF_VAL[gi], cf_case=cfi_label[cfi],
                                  ct_case=cti_label[cti], peaking_db=pk, phase_margin_deg=pm,
                                  loop_crossover_hz=fc, bw_tia_hz=find_3db_bw(f, dbt),
                                  flag_marginal=flag))
                if flag:
                    marginal.append((GAIN_LABEL[gi], cfi_label[cfi], cti_label[cti], pk, pm))
                if cti == 2:  # plot only nominal CT corner vs CF case
                    axs[0].plot(cfi, pk, "o", color=f"C{gi-1}")
                    axs[1].plot(cfi, pm, "o", color=f"C{gi-1}")
    for gi in (1, 2, 3):
        axs[0].plot([], [], "o", color=f"C{gi-1}", label=GAIN_LABEL[gi])
    axs[0].axhline(1.0, color="r", ls=":", lw=1)
    axs[1].axhline(45.0, color="r", ls=":", lw=1)
    axs[0].set_xticks(range(1, 7)); axs[0].set_xticklabels([cfi_label[i] for i in range(1, 7)], rotation=40, fontsize=7)
    axs[1].set_xticks(range(1, 7)); axs[1].set_xticklabels([cfi_label[i] for i in range(1, 7)], rotation=40, fontsize=7)
    axs[0].set_ylabel("Peaking (dB)"); axs[1].set_ylabel("Phase margin (deg)")
    axs[0].legend(fontsize=7); axs[0].grid(True, alpha=0.3); axs[1].grid(True, alpha=0.3)
    fig.suptitle("SIMULATED CF-sweep peaking & phase margin, CT=80p nominal (vendor OPAx320)")
    fig.tight_layout()
    fig.savefig(PLOTDIR / "03_cf_sweep_peaking_pm.png", dpi=130)
    plt.close(fig)
    figs_done.append("03_cf_sweep_peaking_pm.png")

    # ---- 4) Loop gain / phase (selected CF, nominal CT) ---------------
    fig, axs = plt.subplots(1, 2, figsize=(10, 4.5))
    loop_extra = {}
    for gi in (1, 2, 3):
        r = sel(loop, gi=float(gi), cfi=5.0, cti=2.0)[0]
        f = r["cols"]["frequency"].real
        T = -(1.0 + r["cols"]["V(tia)"]) / r["cols"]["V(tia)"]
        axs[0].semilogx(f, db(T), label=GAIN_LABEL[gi])
        axs[1].semilogx(f, np.degrees(np.unwrap(np.angle(T))), label=GAIN_LABEL[gi])
        pm, fc = phase_margin(f, T)
        loop_extra[gi] = dict(phase_margin_deg=pm, crossover_hz=fc)
    axs[0].axhline(0, color="k", lw=0.5)
    axs[0].set_ylabel("Loop gain |T| (dB)"); axs[1].set_ylabel("Loop phase (deg)")
    for a in axs:
        a.set_xlabel("Hz"); a.legend(fontsize=8); a.grid(True, alpha=0.3)
    fig.suptitle("SIMULATED loop gain/phase T(f)=-V(tia_amp)/V(tia), selected CF, CT=80p (vendor OPAx320)")
    fig.tight_layout()
    fig.savefig(PLOTDIR / "04_loop_gain_phase.png", dpi=130)
    plt.close(fig)
    figs_done.append("04_loop_gain_phase.png")

    # ---- 5) Transient small-step (10% FS) ------------------------------
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    tran_extra = {}
    for gi in (1, 2, 3):
        r = sel(tran, gi=float(gi), cfi=1.0, stepi=1.0)[0]
        t = r["cols"]["time"].real
        v = r["cols"]["V(tia)"].real
        ax.plot(t * 1e6, v, label=GAIN_LABEL[gi])
        tedge = 1.0  # us, matches tedge table cfi=1 -> 1u
        os_pct, settle = overshoot_settle(r["cols"]["time"], r["cols"]["V(tia)"], tedge * 1e-6, None)
        tran_extra[(gi, "small")] = dict(overshoot_pct=os_pct, settle_1pct_s=settle)
    ax.set_xlabel("t (us)"); ax.set_ylabel("V(tia) (V)")
    ax.set_title("SIMULATED transient: 10% FS step, selected CF (vendor OPAx320)")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(PLOTDIR / "05_tran_small_step.png", dpi=130)
    plt.close(fig)
    figs_done.append("05_tran_small_step.png")

    # ---- 6) Transient overload (300% FS) recovery ----------------------
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    for gi in (1, 2, 3):
        r = sel(tran, gi=float(gi), cfi=1.0, stepi=3.0)[0]
        t = r["cols"]["time"].real
        v = r["cols"]["V(tia)"].real
        ax.plot(t * 1e3, v, label=GAIN_LABEL[gi])
        tmid = 3.0e-3  # s, matches tmid table cfi=1
        rec = recovery_time(r["cols"]["time"], r["cols"]["V(tia)"], tmid, None)
        tran_extra[(gi, "overload")] = dict(recovery_2pct_s=rec)
    ax.set_xlabel("t (ms)"); ax.set_ylabel("V(tia) (V)")
    ax.set_title("SIMULATED transient: 300% FS overload + recovery, selected CF (vendor OPAx320)")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(PLOTDIR / "06_tran_overload.png", dpi=130)
    plt.close(fig)
    figs_done.append("06_tran_overload.png")

    # ---- 7) Noise density at ADC ---------------------------------------
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    noise_extra = {}
    for gi in (1, 2, 3):
        r = sel(n_adc, gi=float(gi))[0]
        f = r["cols"]["frequency"].real
        onoise = r["cols"]["V(onoise)"].real
        ax.loglog(f, onoise, label=GAIN_LABEL[gi])
        band = (f >= 0.1) & (f <= 100e3)
        integ = float(np.sqrt(np.trapezoid(onoise[band] ** 2, f[band])))
        r_t = sel(n_tia, gi=float(gi))[0]
        f_t = r_t["cols"]["frequency"].real
        inoise_t = r_t["cols"]["inoise"].real
        in_100hz = float(np.interp(np.log(100.0), np.log(f_t), inoise_t))
        noise_extra[gi] = dict(adc_integrated_rms_V=integ, in_ref_density_100Hz_A_rtHz=in_100hz)
    ax.set_xlabel("Hz"); ax.set_ylabel("V(adc) noise density (V/rtHz)")
    ax.set_title("SIMULATED output noise density at ADC (vendor OPAx320)")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(PLOTDIR / "07_noise_density_adc.png", dpi=130)
    plt.close(fig)
    figs_done.append("07_noise_density_adc.png")

    # ---- 8) VREF startup ------------------------------------------------
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    t = vref_start["cols"]["time"].real
    ax.plot(t * 1e3, vref_start["cols"]["V(vcc)"].real, label="VCC")
    ax.plot(t * 1e3, vref_start["cols"]["V(ref)"].real, label="VREF")
    ax.plot(t * 1e3, vref_start["cols"]["V(tia)"].real, label="V(TIA)")
    ax.plot(t * 1e3, vref_start["cols"]["V(adc)"].real, label="V(ADC)")
    ax.set_xlabel("t (ms)"); ax.set_ylabel("V")
    ax.set_title("SIMULATED VREF power-up transient (mid gain, dark)")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(PLOTDIR / "08_vref_startup.png", dpi=130)
    plt.close(fig)
    figs_done.append("08_vref_startup.png")
    ref_final = float(vref_start["cols"]["V(ref)"].real[-1])
    ref_settle_idx = np.where(np.abs(vref_start["cols"]["V(ref)"].real - ref_final) <= 0.01 * 1.65)[0]
    vref_startup_settle_s = float(t[ref_settle_idx[0]]) if len(ref_settle_idx) else float("nan")

    # ---- 9) Supply-to-ADC AC transfer (PSRR) ---------------------------
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    fp = vref_psrr["cols"]["frequency"].real
    ax.semilogx(fp, db(vref_psrr["cols"]["V(adc)"]), label="V(adc)/V(vcc)")
    ax.semilogx(fp, db(vref_psrr["cols"]["V(ref)"]), label="V(ref)/V(vcc)")
    ax.set_xlabel("Hz"); ax.set_ylabel("dB")
    ax.set_title("SIMULATED supply-ripple-to-ADC transfer (mid gain, dark)")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(PLOTDIR / "09_supply_to_adc_psrr.png", dpi=130)
    plt.close(fig)
    figs_done.append("09_supply_to_adc_psrr.png")
    psrr_dc_db = float(db(vref_psrr["cols"]["V(adc)"])[0])

    # ---- headline summary rows ------------------------------------------
    for gi in (1, 2, 3):
        headline.append(dict(
            gain=GAIN_LABEL[gi], RF_ohm=RF_VAL[gi],
            dc_gain_ohm=ac_extra[gi]["dc_gain_ohm"], dc_gain_dbohm=ac_extra[gi]["dc_gain_dbohm"],
            bw_tia_hz=ac_extra[gi]["bw_tia_hz"], bw_adc_hz=ac_extra[gi]["bw_adc_hz"],
            peaking_tia_db=ac_extra[gi]["peaking_tia_db"], peaking_adc_db=ac_extra[gi]["peaking_adc_db"],
            phase_margin_deg=loop_extra[gi]["phase_margin_deg"], loop_crossover_hz=loop_extra[gi]["crossover_hz"],
            small_step_overshoot_pct=tran_extra[(gi, "small")]["overshoot_pct"],
            small_step_settle_1pct_s=tran_extra[(gi, "small")]["settle_1pct_s"],
            overload_recovery_2pct_s=tran_extra[(gi, "overload")]["recovery_2pct_s"],
            dark_Vtia_V=dc_extra[gi]["dark_vtia"], dark_Vadc_V=dc_extra[gi]["dark_vadc"],
            Vtia_min_V=dc_extra[gi]["vtia_min"], Vtia_max_V=dc_extra[gi]["vtia_max"],
            Vadc_min_V=dc_extra[gi]["vadc_min"], Vadc_max_V=dc_extra[gi]["vadc_max"],
            i_at_0p25V_A=dc_extra[gi]["i_at_0p25V"], i_at_rail_A=dc_extra[gi]["i_at_rail"],
            adc_noise_integrated_rms_V=noise_extra[gi]["adc_integrated_rms_V"],
            input_ref_noise_density_100Hz_A_rtHz=noise_extra[gi]["in_ref_density_100Hz_A_rtHz"],
            flag_marginal=(loop_extra[gi]["phase_margin_deg"] < 45) or (ac_extra[gi]["peaking_tia_db"] > 1.0),
        ))

    # ---- behavioral-model cross-check (GBW sensitivity) -----------------
    beh_check = []
    for gi in (1, 2, 3):
        r = sel(beh, gi=float(gi), cfi=1.0, gbwi=2.0)[0]  # selected CF, GBW=20MHz
        f = r["cols"]["frequency"].real
        dbt = db(r["cols"]["V(tia)"])
        beh_check.append(dict(gain=GAIN_LABEL[gi], bw_tia_hz_behavioral=find_3db_bw(f, dbt),
                              bw_tia_hz_vendor=ac_extra[gi]["bw_tia_hz"],
                              peaking_db_behavioral=peaking_db(dbt)))

    # ---- write results ----------------------------------------------------
    with open(RESDIR / "summary.csv", "w", newline="") as fp_csv:
        w = csv.DictWriter(fp_csv, fieldnames=list(headline[0].keys()))
        w.writeheader()
        for h in headline:
            w.writerow(h)

    summary = {
        "headline_per_gain": headline,
        "cf_ct_sensitivity_sweep": rows,
        "marginal_cases_pm_lt_45_or_peaking_gt_1dB": marginal,
        "behavioral_vs_vendor_bw_crosscheck": beh_check,
        "vref_startup_settle_1pct_s": vref_startup_settle_s,
        "supply_to_adc_dc_gain_dB": psrr_dc_db,
        "note": "All values SIMULATED via LTspice batch runs (vendor OPAx320.lib or behavioral opamp_behavioral.sub); none measured on hardware.",
    }
    with open(RESDIR / "summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=float)

    print(f"Wrote {len(rows)} sensitivity rows, {len(headline)} headline rows, "
          f"{len(marginal)} marginal cases, {len(figs_done)} plots.")
    for p in figs_done:
        assert (PLOTDIR / p).exists()
    assert (RESDIR / "summary.csv").exists()
    assert (RESDIR / "summary.json").exists()
    print("OK")


if __name__ == "__main__":
    main()
