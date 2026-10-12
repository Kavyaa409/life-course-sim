"""
Generates charts and a results table for the 5-page writeup.
Run with:  python generate_charts.py
Outputs go to the charts/ folder.
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from plots import final_distribution, gini_comparison, top_vs_bottom
from simulation import SCENARIOS, batch_stats, run_batch

N, SEED = 2000, 42
os.makedirs("charts", exist_ok=True)

hist, stats = {}, {}
for name, (sc, cfg) in SCENARIOS.items():
    hist[name] = run_batch(sc, cfg, n=N, seed=SEED)
    stats[name] = batch_stats(hist[name])

charts = {
    "1_gini_over_life.png": gini_comparison(stats),
    "2_unequal_top_vs_bottom.png": top_vs_bottom(stats["Unequal start"],
                                                 "Unequal start: top vs bottom 20%"),
    "3_policies_top_vs_bottom.png": top_vs_bottom(stats["Unequal + policies"],
                                                  "With policies: top vs bottom 20%"),
    "4_final_distribution.png": final_distribution(hist),
}
for fname, fig in charts.items():
    fig.savefig(os.path.join("charts", fname), dpi=200)
    plt.close(fig)

lines = [f"Results from {N} simulated lives per scenario (seed {SEED})", ""]
for name, s in stats.items():
    mob = "n/a" if s["mobility_pct"] is None else f"{s['mobility_pct']:.1f}%"
    lines += [
        name,
        f"  Gini: {s['start_gini']:.2f} at birth -> {s['end_gini']:.2f} in old age",
        "  Top vs bottom 20% gap: n/a (everyone starts equal)" if s["start_gap"] is None
        else f"  Top vs bottom 20% gap: {s['start_gap']:.1f} -> {s['end_gap']:.1f}",
        f"  In poverty in old age: {s['poverty_pct']:.1f}%",
        f"  Bottom starters reaching top 20%: {mob}",
        "",
    ]
with open(os.path.join("charts", "results.txt"), "w") as f:
    f.write("\n".join(lines))
print("\n".join(lines))
print("Charts saved in charts/")
