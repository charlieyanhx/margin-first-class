"""VIX-managed sizing as a MARGIN lever on the full A tape — CLOSED, negative.

Pre-registered in docs/PREREG_VIX_MARGIN_2026_08.md (filed 2026-08-29 before
running). The original computation was run but never checked in; this script
re-creates it and must reproduce the recorded closure table (skipped counts
exactly, percentages within rounding) — see RECORDED below. It is a
reproduction, not a re-run: no parameter may be tuned to force agreement.

Basis (margin machinery matches scripts/research/rung_margin_levers.py:
margin = width x 100 per open A position, no netting):
  - Tape: reports/tape_A_narrow_winged_unclipped.parquet, Line-3 cross
    EX-COMMISSION per-trade P&L (pnl_cross), full calendar 2020-09-01..
    2026-05-12.
  - Margin day-window: EOD snapshot [entry_day, exit_day) on business days —
    an intraday exit frees margin by that day's EOD mark. This convention
    (not the closed-interval walk used for the cap-8 rung) is what the
    recorded baseline peak $441,000 (2025-04-15) was computed on; the
    closed interval gives $504,300 (2026-03-10) instead.
  - VIX: data/cache/spy_vix_daily.parquet vix_close (2018-01-02..2026-04-27).
    Strictly causal: prior close only. Skip an entry at quantile q when
    prior close > np.quantile(trailing 252 closes ending at AND INCLUDING
    that prior close, q)  [linear interpolation]. The series ends
    2026-04-27, so the 48 tape entries after 2026-04-28 have no prior
    close and are excluded — exactly the recorded n=4,150 baseline.

RECORDED (research memory, run of 2026-08-29 — the bar this must hit):
  baseline peak margin $441,000, P&L $537,236 L3 ex-comm, n=4,150
  q=0.60: skip 2,324  dPeak -60.8%  dPnL -73.0%  passes   -12.2pp vs uniform
  q=0.70: skip 1,920  dPeak -55.5%  dPnL -65.4%  passes    -9.9pp
  q=0.80: skip 1,390  dPeak -17.6%  dPnL -52.4%  FAILS    -34.8pp
  q=0.90: skip   815  dPeak -10.1%  dPnL -30.6%  FAILS    -20.5pp
  corr(entry-VIX pctile, width) +0.665; top-quintile median width 51.0 vs
  bottom 30.0. Uniform de-sizing traces dPeak = dPnL exactly; every VIX
  cell sits below that line (the vs-uniform column, computed from the
  rounded deltas as recorded).
  NOTE: the duty-matched random control's 95th-pct values depend on the
  draw seed (the original's was not recorded); the pass/fail verdicts do
  not — margins are >8pp in every cell.

Usage: .venv/bin/python scripts/research/vix_margin_lever.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BD = pd.bdate_range("2020-09-01", "2026-05-12")
QS = (0.60, 0.70, 0.80, 0.90)
WIN = 252
N_DRAWS = 200
SEED = 0

RECORDED = {  # q: (skipped, dpeak_pct, dpnl_pct, verdict)
    0.60: (2324, -60.8, -73.0, "passes"),
    0.70: (1920, -55.5, -65.4, "passes"),
    0.80: (1390, -17.6, -52.4, "FAILS"),
    0.90: (815, -10.1, -30.6, "FAILS"),
}
REC_PEAK, REC_PNL, REC_N = 441_000.0, 537_236.0, 4_150


def load_tape():
    t = pd.read_parquet(ROOT / "reports" / "tape_A_narrow_winged_unclipped.parquet")
    t["entry_qt"] = pd.to_datetime(t["entry_qt"])
    t["exit_qt"] = pd.to_datetime(t["exit_qt"])
    return t


def vix_gate(tape, vix):
    """Per-entry prior close, trailing-252d percentile, and per-q skip masks."""
    v, idx = vix.values, vix.index
    eday = tape["entry_qt"].dt.normalize()
    loc = idx.searchsorted(eday.values) - 1  # last VIX date STRICTLY before entry
    if (loc < WIN - 1).any():
        raise SystemExit("VIX history too short for the trailing window")
    prior = v[loc]
    pct = np.array([(v[i - WIN + 1:i + 1] <= v[i]).mean() for i in loc])
    skip = {q: np.array([v[i] > np.quantile(v[i - WIN + 1:i + 1], q) for i in loc])
            for q in QS}
    return prior, pct, skip


def margin_arrays(tape):
    """Diff-array margin path: [entry_day, exit_day) EOD-snapshot convention."""
    i0 = BD.searchsorted(tape["entry_qt"].dt.normalize().values, side="left")
    i1 = BD.searchsorted(tape["exit_qt"].dt.normalize().values, side="left")
    w100 = np.where(np.isfinite(tape["width"].values), tape["width"].values, 0.0) * 100
    return i0, i1, w100


def peak_margin(i0, i1, w100, mask=None):
    if mask is None:
        mask = np.ones(len(i0), dtype=bool)
    d = np.zeros(len(BD) + 1)
    np.add.at(d, i0[mask], w100[mask])
    np.add.at(d, i1[mask], -w100[mask])
    return d[:-1].cumsum().max()


def main() -> None:
    tape = load_tape()
    vix = pd.read_parquet(ROOT / "data" / "cache" / "spy_vix_daily.parquet")["vix_close"]
    n_raw, d_lo, d_hi = len(tape), tape["entry_qt"].min(), tape["entry_qt"].max()
    has_prior = tape["entry_qt"].dt.normalize() > vix.index.min()
    covered = tape["entry_qt"].dt.normalize() <= vix.index.max() + pd.Timedelta(days=1)
    tape = tape[has_prior & covered].copy()

    print("== COVERAGE ==")
    print(f"  tape entries {n_raw} ({d_lo.date()} .. {d_hi.date()}), VIX closes "
          f"{vix.index.min().date()} .. {vix.index.max().date()}")
    print(f"  entries with a causal prior VIX close: {len(tape)} "
          f"({n_raw - len(tape)} after VIX end-date dropped)")

    prior, pct, skip = vix_gate(tape, vix)
    i0, i1, w100 = margin_arrays(tape)
    pnl = tape["pnl_cross"].values

    base_peak = peak_margin(i0, i1, w100)
    base_pnl = pnl.sum()
    print("\n== 0. BASELINE REPRODUCTION GATE (abort on mismatch) ==")
    ok = True
    for nm, got, want, tol in (("entries", len(tape), REC_N, 0),
                               ("peak margin $", base_peak, REC_PEAK, 0.5),
                               ("P&L L3 ex-comm $", base_pnl, REC_PNL, 0.5)):
        good = abs(got - want) <= tol
        ok &= good
        print(f"  {nm:18s} {got:>12,.0f} vs recorded {want:>10,.0f}  "
              f"{'OK' if good else 'MISMATCH'}")
    if not ok:
        raise SystemExit("ABORT: baseline does not reproduce the recorded run.")

    print("\n== 1. WIDTH CHANNEL (C1, measured before any rule) ==")
    corr = np.corrcoef(pct, tape["width"].values)[0, 1]
    qmed = tape.groupby(pd.qcut(pct, 5, labels=False))["width"].median()
    print(f"  corr(entry-VIX percentile, A width) = {corr:+.3f}   (recorded +0.665)")
    print(f"  quintile median widths {qmed.tolist()}  "
          f"top/bottom {qmed.iloc[-1] / qmed.iloc[0]:.2f}x  (recorded 51.0/30.0 = 1.70x)")

    print(f"\n== 2. SKIP-ABOVE-q TABLE (duty-matched random: {N_DRAWS} draws, "
          f"seed {SEED}) ==")
    print(f'  {"q":>4s} {"skipped":>8s} {"dPeak":>7s} {"dPnL":>7s} '
          f'{"rand95":>7s} {"control":>8s} {"vs-unif":>8s}  {"recorded":s}')
    rng = np.random.default_rng(SEED)
    all_ok = True
    for q in QS:
        kept = ~skip[q]
        dpeak = 100 * (peak_margin(i0, i1, w100, kept) / base_peak - 1)
        dpnl = 100 * (pnl[kept].sum() / base_pnl - 1)
        reds = np.empty(N_DRAWS)
        for j in range(N_DRAWS):
            m = np.zeros(len(tape), dtype=bool)
            m[rng.choice(len(tape), size=int(kept.sum()), replace=False)] = True
            reds[j] = 100 * (1 - peak_margin(i0, i1, w100, m) / base_peak)
        p95 = np.percentile(reds, 95)
        verdict = "passes" if -dpeak > p95 else "FAILS"
        vs_unif = round(dpnl, 1) - round(dpeak, 1)  # recorded column differences
        rec = RECORDED[q]
        row_ok = (int(skip[q].sum()) == rec[0]
                  and abs(round(dpeak, 1) - rec[1]) < 0.05
                  and abs(round(dpnl, 1) - rec[2]) < 0.05
                  and verdict == rec[3])
        all_ok &= row_ok
        print(f"  {q:4.2f} {skip[q].sum():8d} {dpeak:+6.1f}% {dpnl:+6.1f}% "
              f"{-p95:+6.1f}% {verdict:>8s} {vs_unif:+7.1f}pp  "
              f"{'REPRODUCED' if row_ok else 'MISMATCH ' + str(rec)}")

    print("\n== 3. VERDICT ==")
    print(f"  table reproduction: {'FULL' if all_ok else 'INCOMPLETE — see rows above'}")
    print("  uniform de-sizing traces dPeak = dPnL exactly; every VIX cell above")
    print("  gives up MORE P&L than margin saved (vs-unif < 0) -> the lever is")
    print("  dominated. q>=0.80 also fails the duty-matched random control.")
    print("  Lane stays CLOSED: VIX-managed sizing is not a margin lever here.")


if __name__ == "__main__":
    main()
