# Margin as a First-Class Backtest Output

Code and data-availability statement for:

> **Margin Is Not a Footnote: Reg-T Feasibility as a First-Class Backtest Output**
> Charlie Yan, 2026. [`paper/p5_margin_first_class.pdf`](paper/p5_margin_first_class.pdf)

## What the paper claims

A margined strategy's collateral requirement is a separate stochastic process from its P&L and can terminate the strategy independently of its returns. A book that backtests well peaks at 151–154% of its own net liquidation value.

**Headline result.** Peak-to-median requirement ratio runs **6.7–16.1×** across configurations; a far call wing costing ~1/15th of the equivalent put wing halves the book's peak from 154% to 77%.

## Reproducibility

**FIGURE REPRODUCIBLE from the published table** (`python code/make_p5_figure.py`). The underlying daily margin series is derived from licensed data and is not shipped.

**Standing caveat, also stated in the paper:** these are our Reg-T implementation's numbers, hand-verified against published formulas and cross-checked between two independent builds, but **not yet validated against broker-computed requirements**. House minimums and add-ons can bind earlier.

## What is here

`code/make_p5_figure.py` — the requirement-distribution exhibit.
`paper/` — paper and exhibit.

## Evidence conventions used throughout

Every performance figure in the paper carries its accounting basis inline. Unless labelled
otherwise: **line 3** = full cross-spread fills (buy at ask, sell at bid, every leg both ways),
ex-commission, marked to market daily, padded to the full business calendar. Figures labelled
**screen** are descriptive or information-coefficient statistics and are never annualised into a
Sharpe ratio. Numbers marked **invalid** appear only as invalidated examples, with the corrected
figure alongside.

All tests reported in the paper were pre-registered — horizons, controls, nulls and decision bars
fixed before execution — and deviations are recorded rather than edited away. Where pre-registration
documents exist in this repository they are included verbatim.

## Citation

```bibtex
@techreport{yan2026marginfirstclass,
  title  = {Margin Is Not a Footnote: Reg-T Feasibility as a First-Class Backtest Output},
  author = {Yan, Charlie},
  year   = {2026},
  type   = {Working paper}
}
```

## License

Code MIT (see `LICENSE`). The paper PDF is © 2026 Charlie Yan, all rights reserved.
