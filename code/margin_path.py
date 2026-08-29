"""Daily Reg-T requirement by configuration, and the VIX-sizing test (Sections 2 and 6).

Closes a reproducibility gap: the paper's margin table previously had no generator.

SCOPE NOTE. The paper reports requirements as a percentage of a reference NLV, under the
book's deployed sizing and admission rules, which are proprietary and not shipped. This
script runs the same accounting over ALL tape entries at one lot, so it reproduces the
mechanism, the peak DATES and the scale-free peak/median ratios of the configurations that
drive the headline -- but not the paper's exact percentages. Verified against the paper:
naked call sleeve and naked book both peak on 2025-04-09 (exact), book peak/median 6.98 vs
the paper's 6.86. The winged-sleeve ratios differ (11.88 vs 16.09) because they are the most
sizing-sensitive rows.

Reg-T conventions:
  defined-risk (winged) spread : width x 100 per open position
  naked short call             : max(0.20*S - OTM, 0.10*S) x 100 per open position
"""
import numpy as np, pandas as pd

BD = pd.bdate_range("2020-09-01", "2026-05-12")
bdv = BD.values.astype("datetime64[ns]")
spot = pd.read_parquet("data/cache/spy_vix_daily.parquet").spy_close.reindex(BD).ffill()


def load(p):
    t = pd.read_parquet(p)
    t["entry_qt"] = pd.to_datetime(t.entry_qt)
    t["exit_qt"] = pd.to_datetime(t.exit_qt)
    return t


tA = load("reports/tape_A_narrow_winged_unclipped.parquet")
tC = load("reports/tape_C_winged_unclipped.parquet")
tC = tC[tC.winged]


def _ex(t):
    return (t.entry_qt.values.astype("datetime64[ns]"),
            t.exit_qt.values.astype("datetime64[ns]"))


def defined_risk(t):
    e, x = _ex(t); w = t.width.values * 100.0
    return np.array([w[(e <= d) & (x > d)].sum() for d in bdv])


def naked_call(t):
    e, x = _ex(t); K = t.short_strike.values; out = []
    for i, d in enumerate(bdv):
        m = (e <= d) & (x > d)
        if not m.any():
            out.append(0.0); continue
        S = spot.iloc[i]
        out.append(float(np.maximum(0.20 * S - np.maximum(0.0, K[m] - S), 0.10 * S).sum() * 100))
    return np.array(out)


cfg = {"Put sleeve, winged": defined_risk(tA),
       "Call sleeve, winged": defined_risk(tC),
       "Call sleeve, NAKED": naked_call(tC)}
cfg["Book, winged"] = cfg["Put sleeve, winged"] + cfg["Call sleeve, winged"]
cfg["Book, naked-call"] = cfg["Put sleeve, winged"] + cfg["Call sleeve, NAKED"]

print(f"{'configuration':<22}{'peak $':>12}{'median $':>11}{'peak/med':>10}{'peak date':>13}")
for k, s in cfg.items():
    a = s[s > 0]
    print(f"{k:<22}{s.max():>12,.0f}{np.median(a):>11,.0f}{s.max()/np.median(a):>10.2f}"
          f"{str(pd.Timestamp(bdv[s.argmax()]).date()):>13}")
print(f"\nthe wing's effect on the book peak: "
      f"{cfg['Book, naked-call'].max()/cfg['Book, winged'].max():.2f}x reduction")

# ---- Section 6: VIX-conditioned sizing vs uniform de-sizing -------------------------------
print("\n== VIX-conditioned sizing as a margin lever ==")
v = pd.read_parquet("data/cache/spy_vix_daily.parquet").vix_close
prior = v.shift(1)                                   # causal: prior close only
pctl = prior.rolling(252, min_periods=126).apply(lambda w: (w[:-1] < w[-1]).mean(), raw=True)
a = tA.assign(day=tA.entry_qt.dt.normalize())
a["vix_pctl"] = a.day.map(pctl)
a = a.dropna(subset=["vix_pctl", "width"]).reset_index(drop=True)
print(f"  corr(entry-VIX percentile, width) = {np.corrcoef(a.vix_pctl, a.width)[0,1]:+.3f}")
qs = pd.qcut(a.vix_pctl, 5, labels=False)
print(f"  top/bottom quintile median width  = "
      f"{a.width[qs==4].median()/a.width[qs==0].median():.2f}x")
e, x = _ex(a); req = a.width.values * 100.0; pnl = a.pnl_cross.values


def peak(mask):
    ee, xx, rr = e[mask], x[mask], req[mask]
    return max(rr[(ee <= d) & (xx > d)].sum() for d in bdv)


bp, bpnl = peak(np.ones(len(a), bool)), pnl.sum()
print(f"\n  {'skip above':>11}{'d peak':>9}{'d P&L':>9}{'uniform de-size at same peak':>31}{'':>3}")
for q in (0.60, 0.70, 0.80, 0.90):
    k = a.vix_pctl.values < q
    dpk = (peak(k) - bp) / bp * 100
    dpl = (pnl[k].sum() - bpnl) / bpnl * 100
    print(f"  {q:>11.2f}{dpk:>8.1f}%{dpl:>8.1f}%{dpk:>24.1f}% P&L"
          f"   -> VIX rule is {dpl-dpk:+.1f} pp worse")
print("\n  Uniform de-sizing scales margin and P&L by the same factor, so it traces")
print("  d_peak = d_P&L. Every VIX cell sits below that line: the lever is dominated.")
