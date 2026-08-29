# PRE-REGISTRATION — VIX-managed sizing as a MARGIN lever
Filed 2026-08-29, before running. Decision served: does conditioning A-sleeve entry size on
VIX lower the **capital floor** (a peak statistic), and at what P&L cost?

## Why this is not a reopening
Recorded closures ([[project_regime_control_2026_05]], [[project_overlay_tests_2026_06]],
[[project_contingency_statemachine_2026_06]]) killed vol-targeting and regime overlays on the
**return** path — they lost to flat OOS. This asks about the **collateral** path instead:
feasibility, not Sharpe. [[project_rung_margin_levers_2026_08]] closed every pairing-side lever
and states the only survivors must change A — "wing width or A's vintage/concurrency profile."
VIX-conditioned sizing is a concurrency lever and is untested.

## Gate 0 (run first, already complete)
Was the binding day even a high-VIX day *at entry*? Peak days: book 2025-04-09, rung 2026-03-18.
**Result: VIX 21 trading days before the rung's binding day sat at the 61st percentile** — day-of
VIX (83rd–99th) is the spike caused by the same event as the margin blowup and is not actionable.
Gate 0 is therefore **already discouraging**; the test below proceeds only to quantify by how much.

## Mechanism under test
Margin = width x 100 per open A position. Two channels by which VIX could help:
  (C1) WIDTH — high VIX widens delta-selected strikes, so entries in high vol cost more margin.
  (C2) CONCURRENCY — high VIX clusters entries, raising simultaneous open count.
Both are measured before any rule is fitted.

## Rule family (one variable: the entry filter)
Skip (or half-size) an A entry when VIX at the prior close exceeds its trailing-252d q-quantile,
q in {0.60, 0.70, 0.80, 0.90}. Strictly causal: prior close only, trailing window only.

## PRE-REGISTERED BARS
1. **Duty-matched random control.** A random gate skipping the SAME NUMBER of entries (same
   time-in-market) must be run at every q, 200 draws. The VIX rule passes only if its peak-margin
   reduction exceeds the random gate's **95th percentile**. A rule that merely trades less is not
   a rule.
2. **P&L cost.** Line-3 cross ex-comm total P&L must not fall by more than the margin saved is
   worth: report d(peak margin) and d(P&L) together; a lever that cuts margin 10% while cutting
   P&L 30% fails.
3. **The peak must actually move.** Floor is a peak statistic; a rule that lowers median margin
   and leaves the peak is a null (this is exactly how A5/netting failed).

## Declared in advance
If Gate 0's 61st-percentile finding holds up in the panel — i.e. entry-VIX does not separate
high-margin days from ordinary ones — the lane closes on mechanism regardless of any fitted q.
