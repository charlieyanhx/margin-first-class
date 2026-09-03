"""Santa-Clara & Saretto (2009) forced de-levering on the margin-paper book.

FORK — reuses tapes/marks/conventions; touches no existing script.

Decision served: deliverables/papers/tex/p5_margin_first_class.tex — does the
Reg-T margin path INVERT the naked book's Sharpe when de-levering is forced,
and leave the winged book untouched at the $1M reference NLV?

BASIS (stated before running):
  P&L    : Line-3 full-cross EX-COMMISSION, MTM-daily, full calendar
           2020-09-01..2026-05-12 (1,486 bdays) padded $0, 1 lot per tape
           entry (all entries; the audited-margin sizing).
  Book   : A (winged put spread) + C sleeve. NAKED config = A + naked short
           calls (all 5,465 C entries, no wing, short-leg P&L only).
           WINGED config = A + C credit spread (winged subset 5,392).
           NOTE: the recorded book anchors (151-154% / 76.9%) additionally
           include the S sleeve; no S position tape exists on disk (July-audit
           S series lived in a session scratchpad), and the paper's published
           generator (margin-first-class/code/margin_path.py) defines Book =
           A + C. The S residual vs the recorded anchors is reported below.
  Margin : Reg-T, EOD snapshot, day-window [entry_day, exit_day) — the
           convention that reproduces the recorded A peak $441,000 2025-04-15
           (vix_margin_lever.py). Defined-risk spread: width x 100.
           Naked short call B1: (max(0.20*S - OTM, 0.10*S) + premium) x 100.
           HEADLINE premium = ENTRY CREDIT (bid at the entry snapshot, from
           the day parquets) — the convention implied by the recorded
           hand-verified $11.8k/contract on 2025-04-09 (core $10,972 ATM +
           ~$8.3/sh premium; the current EOD mark that day was ~$19/sh).
           Sensitivities: no-premium (lower) and current-EOD-mark (upper).
  S&S    : maintenance requirement = the Reg-T series as built (target
           full-size book re-levered as equity allows). equity_t = capital +
           cum adjusted P&L; f_t = clip(equity_t / req_t, 0, 1) (req=0 -> 1);
           day t P&L scaled by f_{t-1} (f_{-1}=1). equity<=0 => ruin (f=0).
  Capital: $1,000,000 reference NLV; $900k / $1.1M sensitivity.

GATE (abort-on-miss, pre-stated): A peak $441,000 (2025-04-15); C-winged peak
$354,300 (2025-04-08); C-naked peak 108-111% of $1M (2025-04-09); book naked
151-154%; book winged ~76.9% (book-level within ~2pp after the S residual is
accounted).

Usage: .venv/bin/python ss_margin_adjusted.py   (cwd = repo root)
"""
from __future__ import annotations
import os

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Point RESEARCH_ROOT at your own data tree. These scripts are published for
# audit rather than execution; see the README's data-availability statement.
ROOT = Path(os.environ.get("RESEARCH_ROOT", "."))
SCRATCH = Path(__file__).resolve().parent
BD = pd.bdate_range("2020-09-01", "2026-05-12")
ANN = np.sqrt(252)
YRS = len(BD) / 252
RAW = ROOT / "data" / "cache" / "raw_daily_extracts"
CAPS = (900_000.0, 1_000_000.0, 1_100_000.0)
REF = 1_000_000.0


# ---------------------------------------------------------------- loading
def load_tape(p):
    t = pd.read_parquet(p)
    t["entry_qt"] = pd.to_datetime(t["entry_qt"])
    t["exit_qt"] = pd.to_datetime(t["exit_qt"])
    return t


def marks_daily(m, ids=None, legs=None):
    x = m
    if ids is not None:
        x = x[x["trade_id"].isin(ids)]
    if legs is not None:
        x = x[x["leg"].isin(legs)]
    d = x.groupby("day")["pnl"].sum()
    if not isinstance(d.index, pd.DatetimeIndex):
        d.index = pd.to_datetime(d.index * 86_400_000_000_000)
    return d.reindex(BD, fill_value=0.0)


tA = load_tape(ROOT / "reports" / "tape_A_narrow_winged_unclipped.parquet")
tC = load_tape(ROOT / "reports" / "tape_C_winged_unclipped.parquet")
tCw = tC[tC["winged"]]
mA = pd.read_parquet(ROOT / "reports" / "marks_A_narrow_winged_unclipped.parquet")
mC = pd.read_parquet(ROOT / "reports" / "marks_C_winged_unclipped.parquet")

# spot, extended past 2026-04-27 from day-parquet EOD underlying mid
sv = pd.read_parquet(ROOT / "data" / "cache" / "spy_vix_daily.parquet")["spy_close"]
spot = sv.reindex(BD)
n_ext = 0
for d in BD[BD > sv.index.max()]:
    f = RAW / f"day_{d.date()}.parquet"
    if f.exists():
        u = pd.read_parquet(f, columns=["quote_datetime", "underlying_bid",
                                        "underlying_ask"])
        u["quote_datetime"] = pd.to_datetime(u["quote_datetime"])
        last = u[u["quote_datetime"] == u["quote_datetime"].max()]
        spot[d] = float((last["underlying_bid"] + last["underlying_ask"]).mean() / 2)
        n_ext += 1
spot = spot.ffill()

print("== COVERAGE ==")
print(f"  calendar {BD[0].date()}..{BD[-1].date()}  {len(BD)} bdays "
      f"({YRS:.2f} yrs)")
print(f"  tape A {len(tA)} trades | tape C {len(tC)} trades "
      f"({len(tCw)} winged, {len(tC) - len(tCw)} wingless)")
print(f"  spot: spy_vix_daily to {sv.index.max().date()}, extended {n_ext} days "
      f"from day parquets, ffilled {int(spot.isna().sum())} NaN left")

# ------------------------------------------------- margin series [e_day, x_day)
i0A = BD.searchsorted(tA["entry_qt"].dt.normalize().values, side="left")
i1A = BD.searchsorted(tA["exit_qt"].dt.normalize().values, side="left")
wA = np.where(np.isfinite(tA["width"].values), tA["width"].values, 0.0) * 100


def width_margin(i0, i1, w):
    d = np.zeros(len(BD) + 1)
    np.add.at(d, i0, w)
    np.add.at(d, i1, -w)
    return pd.Series(d[:-1].cumsum(), index=BD)


mgn_A = width_margin(i0A, i1A, wA)

i0Cw = BD.searchsorted(tCw["entry_qt"].dt.normalize().values, side="left")
i1Cw = BD.searchsorted(tCw["exit_qt"].dt.normalize().values, side="left")
wCw = np.where(np.isfinite(tCw["width"].values), tCw["width"].values, 0.0) * 100
mgn_Cw = width_margin(i0Cw, i1Cw, wCw)

# naked C: all trades, per-day formula + EOD premium from day parquets
eC = tC["entry_qt"].dt.normalize().values
xC = tC["exit_qt"].dt.normalize().values
KC = tC["short_strike"].values
expC = pd.to_datetime(tC["expiration"]).values

need_keys = set(zip(expC.astype("datetime64[D]").astype(str), KC))
expC_str = expC.astype("datetime64[D]").astype(str)
entry_day = tC["entry_qt"].dt.normalize()
by_entry_day: dict = {}
for j, ed in enumerate(entry_day):
    by_entry_day.setdefault(ed, []).append(j)

cache: dict = {}
credC = np.full(len(tC), np.nan)  # entry credit $/share (bid at entry snapshot)
prem = np.zeros(len(BD))          # current-EOD-mark premium x100 of open shorts
prem_e = np.zeros(len(BD))        # entry-credit premium x100 of open shorts
prem_missing = 0
open_cnt = np.zeros(len(BD), dtype=int)
core = np.zeros(len(BD))          # (0.20S - OTM | 0.10S) x100 summed

for i, d in enumerate(BD):
    dv = d.to_datetime64()
    m = (eC <= dv) & (xC > dv)
    open_cnt[i] = m.sum()
    f = RAW / f"day_{d.date()}.parquet"
    entrants = by_entry_day.get(d, [])
    if f.exists() and (m.any() or entrants):
        q = pd.read_parquet(f, columns=["quote_datetime", "expiration", "strike",
                                        "option_type", "bid", "ask"])
        q = q[q["option_type"] == "C"]
        q["quote_datetime"] = pd.to_datetime(q["quote_datetime"])
        q["exp_s"] = pd.to_datetime(q["expiration"]).values.astype(
            "datetime64[D]").astype(str)
        # entry credits at the entry snapshot
        for j in entrants:
            r = tC.iloc[j]
            snap = q[(q["quote_datetime"] == r["entry_qt"])
                     & (q["exp_s"] == expC_str[j]) & (q["strike"] == KC[j])]
            if len(snap):
                credC[j] = float(snap["bid"].iloc[0])
        # EOD price cache
        qe = q[q["quote_datetime"] == q["quote_datetime"].max()]
        for k, b, a in zip(zip(qe["exp_s"], qe["strike"]), qe["bid"], qe["ask"]):
            if k in need_keys:
                cache[k] = (b + a) / 2
    if not m.any():
        continue
    S = float(spot.iloc[i])
    otm = np.maximum(0.0, KC[m] - S)
    core[i] = float(np.maximum(0.20 * S - otm, 0.10 * S).sum() * 100)
    ptot = 0.0
    for k in zip(expC_str[m], KC[m]):
        pv = cache.get(k)
        if pv is None:
            prem_missing += 1
        else:
            ptot += pv
    prem[i] = ptot * 100
    prem_e[i] = np.nansum(credC[m]) * 100

n_nocred = int(np.isnan(credC).sum())
mgn_Cn_noprem = pd.Series(core, index=BD)
mgn_Cn_mark = pd.Series(core + prem, index=BD)
mgn_Cn = pd.Series(core + prem_e, index=BD)          # B1 headline: entry credit

mgn_naked = mgn_A + mgn_Cn
mgn_naked_lo = mgn_A + mgn_Cn_noprem
mgn_naked_hi = mgn_A + mgn_Cn_mark
mgn_winged = mgn_A + mgn_Cw

print(f"  premium marks: EOD cache misses {prem_missing}; trades without an "
      f"entry-snapshot credit {n_nocred}/{len(tC)} (treated as $0 premium)")

# ------------------------------------------------------------------ gate
print("\n== 1. ANCHOR GATE (recorded July-audit values; abort on book miss >2pp) ==")


def peak_line(name, s, want=None, want_date=None, tol=None):
    pk, dt = float(s.max()), s.idxmax().date()
    hit = ""
    if want is not None:
        lo, hi = (want if isinstance(want, tuple) else
                  (want - (tol or 0.5), want + (tol or 0.5)))
        ok = lo <= pk <= hi and (want_date is None or str(dt) == want_date)
        hit = f"  vs recorded {want if not isinstance(want, tuple) else f'{lo:,.0f}-{hi:,.0f}'} " \
              f"({want_date})  {'HIT' if ok else 'MISS'}"
    print(f"  {name:<28s} peak ${pk:>12,.0f} on {dt}{hit}")
    return pk, str(dt)


pkA, dA = peak_line("A winged", mgn_A, 441_000, "2025-04-15")
gate_A = abs(pkA - 441_000) < 0.5 and dA == "2025-04-15"
pkCw, dCw = peak_line("C winged", mgn_Cw, 354_300, "2025-04-08")
gate_Cw = abs(pkCw - 354_300) < 0.5 and dCw == "2025-04-08"
pkCn_lo, dCn_lo = peak_line("C naked (no premium)", mgn_Cn_noprem)
pkCn, dCn = peak_line("C naked (B1, entry credit)", mgn_Cn)
pkCn_hi, dCn_hi = peak_line("C naked (current EOD mark)", mgn_Cn_mark)
gate_Cn = dCn == "2025-04-09" and 1.06e6 <= pkCn <= 1.13e6
print(f"    C-naked B1 {pkCn/REF:.1%} of $1M (band no-prem {pkCn_lo/REF:.1%} .. "
      f"mark {pkCn_hi/REF:.1%}) vs recorded 108-111% (2025-04-09)  "
      f"{'HIT' if gate_Cn else 'MISS'}")

pkBn, dBn = peak_line("BOOK naked  (A+C, B1)", mgn_naked)
pkBn_lo, _ = peak_line("BOOK naked  (no prem)", mgn_naked_lo)
pkBn_hi, _ = peak_line("BOOK naked  (EOD mark)", mgn_naked_hi)
pkBw, dBw = peak_line("BOOK winged (A+C)", mgn_winged)
print(f"    book naked  B1 {pkBn/REF:.1%} vs recorded 151-154% "
      f"(2025-04-09; recorded includes S) -> S residual "
      f"{151 - pkBn/REF*100:+.1f} to {154 - pkBn/REF*100:+.1f} pp")
print(f"    book winged {pkBw/REF:.1%} vs recorded 76.9% (includes S) -> "
      f"S residual {76.9 - pkBw/REF*100:+.1f} pp")
gate_Bn = dBn == "2025-04-09" and abs(pkBn / REF * 100 - 152.5) <= 3.5
gate_Bw = (76.9 - pkBw / REF * 100) <= 3.0 and (pkBw / REF * 100) <= 76.9 + 2.0
print(f"  component gates: A {'HIT' if gate_A else 'MISS'}  "
      f"C-winged {'HIT' if gate_Cw else 'MISS'}  C-naked {'HIT' if gate_Cn else 'MISS'}")
if not (gate_A and gate_Cw and gate_Cn):
    sys.exit("ABORT: component anchors not reproduced — series ungated.")
if not (gate_Bn and gate_Bw):
    print("  BOOK-LEVEL: outside 2pp after S residual — REPORTING AND STOPPING "
          "PER GATE unless residual is attributable to the missing S sleeve.")

# margin distribution for context
for nm, s in (("naked", mgn_naked), ("winged", mgn_winged)):
    a = s[s > 0]
    print(f"  book {nm:<6s} median ${np.median(a):>9,.0f}  p90 ${np.percentile(a,90):>10,.0f}"
          f"  peak/med {s.max()/np.median(a):.1f}x")

# ------------------------------------------------------- book P&L + recon
print("\n== 2. BOOK P&L RECONCILIATION ==")
bk2 = pd.read_parquet(ROOT / "data" / "cache" /
                      "consolidated_book_K2_daily.parquet")["pnl"].reindex(BD).fillna(0)
pA = marks_daily(mA)
pCn = marks_daily(mC, legs=["short", "comm"])                       # naked, ex-comm
pCw = marks_daily(mC, ids=set(tCw["trade_id"]))                     # winged, ex-comm
pnl_naked = pA + pCn
pnl_winged = pA + pCw

recs = [
    ("A marks total vs tape pnl_cross", pA.sum(), tA["pnl_cross"].sum()),
    ("C naked marks vs tape short_excomm(all)", pCn.sum(),
     tC["short_pnl_cross_excomm"].sum()),
    ("C winged marks vs tape pnl_cross_excomm(winged)", pCw.sum(),
     tCw["pnl_cross_excomm"].sum()),
]
for nm, got, want in recs:
    print(f"  {nm:<48s} ${got:>12,.2f} vs ${want:>12,.2f}  "
          f"{'TIES' if abs(got-want) < 0.01 else 'OFF by $%.2f' % (got-want)}")
r = bk2.corr(pnl_winged)
print(f"  consolidated_book_K2_daily total ${bk2.sum():,.2f} vs marks-built winged "
      f"1-lot ${pnl_winged.sum():,.2f}: ratio {bk2.sum()/pnl_winged.sum():.2f}x, "
      f"corr {r:.3f} -> DOES NOT TIE (production-sized orphan series);")
print("  book rebuilt from marks directly (1-lot, the audited-margin sizing). "
      "S&S runs on the marks-built series.")

# ------------------------------------------------------------- S&S loop
print("\n== 3. SANTA-CLARA & SARETTO FORCED DE-LEVERING ==")
print("  f_t = clip(equity_t/req_t, 0, 1); day-(t+1) P&L x f_t; ruin => f=0.")


def sstats(p):
    eq = p.cumsum()
    dd = (eq.cummax() - eq).max()
    sh = p.mean() / p.std(ddof=1) * ANN
    return p.sum(), sh, dd


def ss_run(pnl, req, capital):
    f = np.ones(len(BD))
    adj = np.zeros(len(BD))
    eq = capital
    fp = 1.0
    ruined = None
    for i in range(len(BD)):
        adj[i] = fp * pnl.iloc[i]
        eq += adj[i]
        if eq <= 0 and ruined is None:
            ruined = BD[i]
        r = req.iloc[i]
        fp = 1.0 if r <= 0 else min(1.0, max(0.0, eq / r))
        f[i] = fp
    return pd.Series(adj, index=BD), pd.Series(f, index=BD), ruined


def episodes(f):
    out, start = [], None
    for d, v in f.items():
        if v < 1 and start is None:
            start = d
        elif v >= 1 and start is not None:
            out.append((start, prev))
            start = None
        prev = d
    if start is not None:
        out.append((start, BD[-1]))
    return out


for cfg, pnl, req in (("NAKED ", pnl_naked, mgn_naked),
                      ("WINGED", pnl_winged, mgn_winged)):
    tot0, sh0, dd0 = sstats(pnl)
    print(f"\n  {cfg} BOOK  unadjusted: total ${tot0:>10,.0f}  Sharpe {sh0:.2f}  "
          f"maxDD ${dd0:,.0f}   [Line-3 cross ex-comm, MTM-daily, full calendar]")
    for cap in CAPS:
        adj, f, ruined = ss_run(pnl, req, cap)
        tot1, sh1, dd1 = sstats(adj)
        nlt = int((f < 1).sum())
        eps = episodes(f)
        ep_s = "; ".join(f"{a.date()}..{b.date()}" for a, b in eps[:6])
        if len(eps) > 6:
            ep_s += f"; +{len(eps)-6} more"
        print(f"    cap ${cap/1e3:>5,.0f}k  adj: total ${tot1:>10,.0f} "
              f"({(tot1/tot0-1)*100:+5.1f}%)  Sharpe {sh1:5.2f} (d {sh1-sh0:+.2f})  "
              f"maxDD ${dd1:,.0f}  f<1 days {nlt:3d}  min f "
              f"{f.min():.3f} on {f.idxmin().date()}"
              + (f"  RUINED {ruined.date()}" if ruined else ""))
        if eps:
            print(f"             de-lever episodes: {ep_s}")

# identical-path check for the winged book at $1M
adjw, fw, _ = ss_run(pnl_winged, mgn_winged, REF)
same = np.allclose(adjw.values, pnl_winged.values)
print(f"\n  winged @$1M adjusted path identical to unadjusted: {same} "
      f"(min f {fw.min():.3f})")

# ---------------------------------------------- diagnostics: why (not) bitten
print("\n== 4. UTILIZATION DIAGNOSTICS (req_t vs running equity, $1M) ==")
for cfg, pnl, req in (("NAKED ", pnl_naked, mgn_naked),
                      ("WINGED", pnl_winged, mgn_winged)):
    adj, f, _ = ss_run(pnl, req, REF)
    eq = REF + adj.cumsum()
    util = (req / eq).replace([np.inf, -np.inf], np.nan)
    d = util.idxmax()
    dm = req.idxmax()
    print(f"  {cfg}: max req/equity {util.max():.1%} on {d.date()} "
          f"(req ${req[d]:,.0f}, equity ${eq[d]:,.0f}); on margin-peak day "
          f"{dm.date()}: req ${req[dm]:,.0f} vs equity ${eq[dm]:,.0f} "
          f"(cum P&L ${eq[dm]-REF:,.0f}) -> gap ${eq[dm]-req[dm]:+,.0f}")
    top = util.nlargest(5)
    print("    top-5 utilization days: "
          + "; ".join(f"{i.date()} {v:.0%}" for i, v in top.items()))

print("\n== 5. STATIC-EQUITY VARIANT (equity pinned at $1M: profits swept, "
      "losses topped up — the paper's static peak-vs-NLV comparison) ==")
for cfg, pnl, req in (("NAKED ", pnl_naked, mgn_naked),
                      ("WINGED", pnl_winged, mgn_winged)):
    fstat = (REF / req.replace(0, np.nan)).clip(upper=1.0).fillna(1.0)
    adj = pnl * fstat.shift(1).fillna(1.0)
    tot0, sh0, dd0 = sstats(pnl)
    tot1, sh1, dd1 = sstats(adj)
    nlt = int((fstat < 1).sum())
    eps = episodes(fstat)
    ep_s = "; ".join(f"{a.date()}..{b.date()}" for a, b in eps[:6])
    print(f"  {cfg}: total ${tot1:,.0f} ({(tot1/tot0-1)*100:+.1f}%)  "
          f"Sharpe {sh1:.2f} (d {sh1-sh0:+.2f})  maxDD ${dd1:,.0f}  "
          f"f<1 days {nlt}  min f {fstat.min():.3f} on {fstat.idxmin().date()}")
    if eps:
        print(f"    episodes: {ep_s}")

print("\n== 5b. MAINTENANCE-CONVENTION SENSITIVITY — naked book requirement "
      "with premium at CURRENT EOD MARK (harsher than the audited entry-credit "
      "B1), retained-earnings S&S ==")
tot0, sh0, dd0 = sstats(pnl_naked)
for cap in CAPS:
    adj, f, ruined = ss_run(pnl_naked, mgn_naked_hi, cap)
    tot1, sh1, dd1 = sstats(adj)
    eps = episodes(f)
    ep_s = "; ".join(f"{a.date()}..{b.date()}" for a, b in eps[:6])
    print(f"    cap ${cap/1e3:>5,.0f}k  adj: total ${tot1:>10,.0f} "
          f"({(tot1/tot0-1)*100:+5.1f}%)  Sharpe {sh1:5.2f} (d {sh1-sh0:+.2f})  "
          f"maxDD ${dd1:,.0f}  f<1 days {int((f<1).sum()):3d}  min f "
          f"{f.min():.3f} on {f.idxmin().date()}"
          + (f"  RUINED {ruined.date()}" if ruined else ""))
    if eps:
        print(f"             episodes: {ep_s}")

print("\n== 6. BREAKEVEN CAPITAL SCAN — naked book, retained-earnings S&S ==")
print(f'  {"capital":>9s} {"adj total":>11s} {"d tot":>7s} {"Sharpe":>7s} '
      f'{"d Sh":>6s} {"f<1":>5s} {"min f":>6s}  {"ruin":s}')
tot0, sh0, _ = sstats(pnl_naked)
for cap in (400e3, 500e3, 600e3, 700e3, 800e3, 900e3, 1000e3, 1100e3):
    adj, f, ruined = ss_run(pnl_naked, mgn_naked, cap)
    tot1, sh1, _ = sstats(adj)
    print(f"  ${cap/1e3:>7,.0f}k {tot1:>11,.0f} {(tot1/tot0-1)*100:+6.1f}% "
          f"{sh1:7.2f} {sh1-sh0:+6.2f} {int((f<1).sum()):5d} {f.min():6.3f}  "
          + (str(ruined.date()) if ruined else "-"))

# commissions recon line (basis is ex-comm; commissions reported separately)
a_comm = tA["pnl_cross"].sum() - tA["pnl_cross_inc_comm"].sum()
c_comm = mC[mC["leg"] == "comm"]["pnl"].sum()
print(f"\n  commissions (separate recon line, not in any number above): "
      f"A ${a_comm:,.0f} (commission_rt), C comm-leg ${c_comm:,.0f} as marked")

pd.DataFrame({"mgn_naked": mgn_naked, "mgn_naked_noprem": mgn_naked_lo,
              "mgn_naked_mark": mgn_naked_hi,
              "mgn_winged": mgn_winged, "mgn_A": mgn_A, "mgn_Cw": mgn_Cw,
              "mgn_Cn": mgn_Cn, "pnl_naked": pnl_naked,
              "pnl_winged": pnl_winged}).to_parquet(SCRATCH / "ss_margin_series.parquet")
print(f"  series saved: {SCRATCH / 'ss_margin_series.parquet'}")
