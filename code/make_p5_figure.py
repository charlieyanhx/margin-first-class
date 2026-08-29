"""P5 exhibit — audited margin distribution by configuration, normalized to % of reference NLV."""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, numpy as np
plt.rcParams.update({"font.size": 9, "figure.dpi": 150})

cfg = ["Put sleeve\n(winged)", "Call sleeve\n(winged)", "Call sleeve\n(NAKED)",
       "Book\n(winged)", "Book\n(naked call)"]
med = [5.5, 2.2, 11.2, 11.5, 22.0]
p90 = [17.5, 7.8, 38.0, np.nan, np.nan]
peak = [44.1, 35.4, 109.5, 76.9, 152.5]

fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.6, 3.2),
                             gridspec_kw={"width_ratios": [1.35, 1]})
x = np.arange(len(cfg)); w = 0.26
a1.bar(x - w, med, w, label="median", color="#b7c6d4")
a1.bar(x, p90, w, label="90th pct", color="#7f9bb5")
a1.bar(x + w, peak, w, label="peak", color="#a63d40")
a1.axhline(100, color="black", lw=1.1, ls="--")
a1.text(4.35, 103, "account capital", fontsize=7.5, ha="right")
for i, v in enumerate(peak):
    a1.text(x[i] + w, v + 3, f"{v:.0f}", ha="center", fontsize=7.5, color="#a63d40")
a1.set_ylabel("Reg-T requirement (% of reference NLV)")
a1.set_xticks(x); a1.set_xticklabels(cfg, fontsize=7.5)
a1.set_ylim(0, 170); a1.legend(frameon=False, fontsize=7.5, loc="upper left")
a1.spines[["top", "right"]].set_visible(False)
a1.set_title("Two configurations breach their own capital", fontsize=9)

mult = [p / m for p, m in zip(peak, med)]
a2.barh(range(len(cfg)), mult, 0.55, color="#31567a")
for i, v in enumerate(mult):
    a2.text(v + 0.15, i, f"{v:.1f}x", va="center", fontsize=8)
a2.set_yticks(range(len(cfg))); a2.set_yticklabels(cfg, fontsize=7.5)
a2.set_xlabel("peak / median requirement")
a2.set_xlim(0, max(mult) * 1.25)
a2.spines[["top", "right"]].set_visible(False)
a2.set_title("What a 'typical utilization'\nfigure conceals", fontsize=9)
fig.tight_layout(); fig.savefig("fig_p5_margin.pdf")
print("peak/median multipliers:", [f"{m:.1f}" for m in mult])
