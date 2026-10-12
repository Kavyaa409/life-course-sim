"""
Life-Course Inequality Simulation - core engine.

Models cumulative advantage/disadvantage:
  1. Probability of a GOOD event rises with current advantage score.
  2. GAINS scale up with the score (advantage earns "returns", like capital).
  3. LOSSES hurt more when the score is low (no buffer to absorb shocks).
"""

import random
from dataclasses import dataclass, field

STAGES = ["Childhood", "Education", "Early Career", "Career", "Middle Age", "Old Age"]
TIMELINE = ["Birth"] + STAGES

# ---------------------------------------------------------------------------
# Event tables: (description, base effect)
# ---------------------------------------------------------------------------
GOOD_EVENTS = {
    "Childhood": [
        ("had books and tutoring at home", 6),
        ("got good nutrition and healthcare", 5),
        ("was admitted to a well-resourced school", 7),
        ("had parents with time to help with homework", 4),
    ],
    "Education": [
        ("won a scholarship", 10),
        ("could afford entrance-exam coaching", 8),
        ("cleared a top college entrance exam", 12),
        ("found a mentor who guided career choices", 6),
    ],
    "Early Career": [
        ("got a campus placement at a good firm", 12),
        ("used family contacts to land an internship", 8),
        ("completed a paid upskilling certification", 6),
    ],
    "Career": [
        ("got promoted", 15),
        ("switched to a higher-paying job", 12),
        ("bought a house that grew in value", 10),
    ],
    "Middle Age": [
        ("saw investments pay off", 12),
        ("received an inheritance", 10),
        ("fully funded their children's education", 6),
    ],
    "Old Age": [
        ("retired on a secure pension and savings", 10),
        ("was covered by good health insurance", 8),
        ("had a strong family support network", 5),
    ],
}

BAD_EVENTS = {
    "Childhood": [
        ("lost family savings to a parent's illness", -7),
        ("attended an under-resourced local school", -6),
        ("had to help with household work instead of studying", -5),
    ],
    "Education": [
        ("dropped out to support the family", -12),
        ("could not afford exam coaching", -7),
        ("missed a key exam due to illness", -8),
    ],
    "Early Career": [
        ("graduated during a recession", -10),
        ("got stuck in informal, unpaid work", -8),
        ("struggled with an education loan", -7),
    ],
    "Career": [
        ("was laid off", -14),
        ("faced workplace discrimination", -9),
        ("had a medical emergency", -12),
    ],
    "Middle Age": [
        ("suffered a business failure", -12),
        ("took on debt for a family wedding", -9),
        ("developed a chronic illness", -10),
    ],
    "Old Age": [
        ("had no pension and watched savings run out", -12),
        ("faced a major health expense", -12),
        ("lived alone without support", -6),
    ],
}

# Starting "background cards" for the unequal scenario
BACKGROUNDS = [
    ("Wealthy urban family", 80),
    ("Upper-middle-class family", 65),
    ("Middle-class family", 50),
    ("Lower-middle-class family", 40),
    ("Rural farming family", 30),
    ("Low-income single-parent family", 20),
]


@dataclass
class Config:
    base_good: float = 0.30          # chance of a good event at score 0
    advantage_slope: float = 0.45    # extra chance gained per 100 points of score
    gain_multiplier: float = 1.0     # how strongly gains scale with score
    vulnerability: float = 1.0       # how strongly losses scale with LOW score
    events_per_stage: int = 2
    safety_net: bool = False         # policy: halves losses for anyone below 50
    free_education: bool = False     # policy: guarantees fair odds in childhood/education


@dataclass
class Player:
    name: str
    background: str
    start: float
    score: float = 0.0
    history: list = field(default_factory=list)   # score after each stage
    log: list = field(default_factory=list)       # (stage, text, change)

    def __post_init__(self):
        self.score = self.start
        self.history = [self.start]


# ---------------------------------------------------------------------------
# Mechanics
# ---------------------------------------------------------------------------
def p_good(score, stage, cfg):
    s = min(score, 100) / 100
    p = cfg.base_good + cfg.advantage_slope * s
    if cfg.free_education and stage in ("Childhood", "Education"):
        p = max(p, 0.55)
    return min(p, 0.90)


def apply_event(player, stage, cfg, rng):
    s = min(player.score, 100) / 100
    if rng.random() < p_good(player.score, stage, cfg):
        text, base = rng.choice(GOOD_EVENTS[stage])
        change = base * (1 + cfg.gain_multiplier * s)
    else:
        text, base = rng.choice(BAD_EVENTS[stage])
        change = base * (1 + cfg.vulnerability * (1 - s))
        if cfg.safety_net and player.score < 50:
            change *= 0.5
    change = round(change, 1)
    player.score = max(0.0, round(player.score + change, 1))
    player.log.append((stage, text, change))
    return text, change


def play_stage(players, stage, cfg, rng):
    """Play one life stage for every player. Returns list of log lines."""
    lines = []
    for p in players:
        for _ in range(cfg.events_per_stage):
            text, change = apply_event(p, stage, cfg, rng)
            sign = "+" if change >= 0 else ""
            lines.append(f"{p.name} {text} ({sign}{change})")
        p.history.append(p.score)
    return lines


def create_players(scenario, names, rng):
    players = []
    if scenario == "Equal":
        for n in names:
            players.append(Player(n, "Average family", 50))
    else:
        cards = BACKGROUNDS[:]
        rng.shuffle(cards)
        for i, n in enumerate(names):
            bg, start = cards[i % len(cards)]
            players.append(Player(n, bg, start))
    return players


def gini(values):
    vals = sorted(max(0.0, v) for v in values)
    n = len(vals)
    total = sum(vals)
    if n == 0 or total == 0:
        return 0.0
    cum = sum((i + 1) * v for i, v in enumerate(vals))
    return (2 * cum) / (n * total) - (n + 1) / n


def outcome_label(score):
    if score >= 100:
        return "Comfortable and secure"
    if score >= 60:
        return "Stable"
    if score >= 30:
        return "Struggling"
    return "In poverty"


# ---------------------------------------------------------------------------
# Batch (Monte Carlo) runs for statistics and the writeup
# ---------------------------------------------------------------------------
def run_batch(scenario, cfg, n=1000, seed=0):
    """Simulate n lives. Returns list of histories (each len 7)."""
    rng = random.Random(seed)
    histories = []
    for i in range(n):
        start = 50.0 if scenario == "Equal" else rng.uniform(20, 80)
        p = Player(f"P{i}", "", round(start, 1))
        for stage in STAGES:
            for _ in range(cfg.events_per_stage):
                apply_event(p, stage, cfg, rng)
            p.history.append(p.score)
        histories.append(p.history)
    return histories


def batch_stats(histories):
    """Summary numbers for one scenario."""
    n_steps = len(histories[0])
    gini_curve = [gini([h[t] for h in histories]) for t in range(n_steps)]
    ranked = sorted(histories, key=lambda h: h[0])
    q = max(1, len(ranked) // 5)
    bottom, top = ranked[:q], ranked[-q:]
    bottom_mean = [sum(h[t] for h in bottom) / q for t in range(n_steps)]
    top_mean = [sum(h[t] for h in top) / q for t in range(n_steps)]

    # Mobility: share of bottom-20% starters who finish in the top 20%
    finals = sorted(h[-1] for h in histories)
    top_cut = finals[-q]
    starts_equal = len({h[0] for h in histories}) == 1
    mobility = None if starts_equal else 100 * sum(h[-1] >= top_cut for h in bottom) / q

    return {
        "gini_curve": gini_curve,
        "bottom_mean": bottom_mean,
        "top_mean": top_mean,
        "start_gini": gini_curve[0],
        "end_gini": gini_curve[-1],
        "start_gap": None if starts_equal else top_mean[0] - bottom_mean[0],
        "end_gap": None if starts_equal else top_mean[-1] - bottom_mean[-1],
        "poverty_pct": 100 * sum(h[-1] < 30 for h in histories) / len(histories),
        "mobility_pct": mobility,
    }


SCENARIOS = {
    "Equal start": ("Equal", Config()),
    "Unequal start": ("Unequal", Config()),
    "Unequal + policies": ("Unequal", Config(safety_net=True, free_education=True)),
}
