"""Charts shared by the Streamlit app and the report-chart script."""

import matplotlib.pyplot as plt
from simulation import TIMELINE, gini

INK = "#1F2A44"
GRID = "#D9DEE7"
PALETTE = ["#2E6F95", "#C8553D", "#4F9D69", "#8E5BA8", "#E0A030", "#5C6B7A",
           "#B23A6E", "#3C8D8D"]
SCENARIO_COLORS = {"Equal start": "#5C6B7A", "Unequal start": "#C8553D",
                   "Unequal + policies": "#2E6F95"}


def _style(ax, title):
    ax.set_title(title, loc="left", fontsize=13, color=INK, fontweight="bold")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=INK)


def score_bars(players):
    fig, ax = plt.subplots(figsize=(7, 4))
    ordered = sorted(players, key=lambda p: p.score)
    colors = [PALETTE[players.index(p) % len(PALETTE)] for p in ordered]
    labels = [f"{p.name}\n{p.background}" for p in ordered]
    ax.barh(labels, [p.score for p in ordered], color=colors)
    for i, p in enumerate(ordered):
        ax.text(p.score + 1, i, f"{p.score:.0f}", va="center", color=INK, fontsize=10)
    _style(ax, "Current advantage score")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", labelsize=8)
    fig.tight_layout()
    return fig


def trajectories(players):
    fig, ax = plt.subplots(figsize=(7, 4))
    for i, p in enumerate(players):
        x = TIMELINE[: len(p.history)]
        ax.plot(x, p.history, marker="o", linewidth=2.2,
                color=PALETTE[i % len(PALETTE)], label=p.name)
    ax.set_xticks(range(len(TIMELINE)))
    ax.set_xticklabels(TIMELINE, rotation=25, ha="right", fontsize=9)
    ax.set_ylabel("Advantage score")
    _style(ax, "Life-course trajectories")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    return fig


def live_gini(players):
    steps = len(players[0].history)
    vals = [gini([p.history[t] for p in players]) for t in range(steps)]
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.plot(TIMELINE[:steps], vals, marker="o", color="#C8553D", linewidth=2.5)
    ax.set_xticks(range(len(TIMELINE)))
    ax.set_xticklabels(TIMELINE, rotation=25, ha="right", fontsize=9)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Gini (0 = equal, 1 = unequal)")
    _style(ax, "Inequality among players")
    fig.tight_layout()
    return fig


def gini_comparison(stats_by_scenario):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for name, s in stats_by_scenario.items():
        ax.plot(TIMELINE, s["gini_curve"], marker="o", linewidth=2.5,
                color=SCENARIO_COLORS.get(name, INK), label=name)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Gini coefficient")
    ax.legend(frameon=False)
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    _style(ax, "Inequality across the life course")
    fig.tight_layout()
    return fig


def top_vs_bottom(stats, title):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(TIMELINE, stats["top_mean"], marker="o", linewidth=2.5,
            color="#2E6F95", label="Top 20% starters")
    ax.plot(TIMELINE, stats["bottom_mean"], marker="o", linewidth=2.5,
            color="#C8553D", label="Bottom 20% starters")
    ax.fill_between(range(len(TIMELINE)), stats["bottom_mean"], stats["top_mean"],
                    color="#C8553D", alpha=0.08)
    ax.set_ylabel("Average advantage score")
    ax.legend(frameon=False)
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    _style(ax, title)
    fig.tight_layout()
    return fig


def final_distribution(histories_by_scenario):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for name, hs in histories_by_scenario.items():
        ax.hist([h[-1] for h in hs], bins=40, alpha=0.5,
                color=SCENARIO_COLORS.get(name, INK), label=name)
    ax.set_xlabel("Advantage score in old age")
    ax.set_ylabel("Number of people")
    ax.legend(frameon=False)
    _style(ax, "Where people end up")
    fig.tight_layout()
    return fig
