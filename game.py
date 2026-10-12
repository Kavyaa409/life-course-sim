"""
Turn-based game mode: each player makes a life choice, then rolls the dice.

Cumulative advantage shows up in three ways players can FEEL:
  - Dice bonus grows with your score (better odds).
  - Good options cost points, so poorer players find them LOCKED.
  - Gains scale up and losses hurt more when your score is low.
"""

import random
from dataclasses import dataclass, field

from simulation import BACKGROUNDS, BAD_EVENTS, GOOD_EVENTS, STAGES, gini

EFFECT_SCALE = 1.1   # one roll per stage, so effects are slightly larger
DICE = ["", "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]


@dataclass
class Option:
    key: str
    label: str
    desc: str
    cost: float = 0          # points paid now (negative = points earned now)
    min_score: float = 0     # option is locked below this score
    roll_bonus: int = 0      # added to this stage's dice roll
    loss_mult: float = 1.0   # < 1 protects against bad events
    swing: float = 1.0       # > 1 = high risk, high reward
    deferred: float = 0      # points applied at the start of next stage


DECISIONS = {
    "Childhood": ("Which school does your family choose?", [
        Option("private", "Private school", "Better teachers and facilities.",
               cost=15, min_score=45, roll_bonus=2),
        Option("govt", "Government school", "Free, but often under-resourced."),
        Option("work", "Help with the family's work", "Earn a little now, less time to study.",
               cost=-5, roll_bonus=-1),
    ]),
    "Education": ("How do you prepare for college entrance?", [
        Option("coaching", "Paid coaching", "Expensive, but boosts your chances.",
               cost=15, min_score=40, roll_bonus=2),
        Option("loan", "Education loan", "Same boost, but you repay 15 points next stage. "
               "Banks want some security.", min_score=20, roll_bonus=2, deferred=-15),
        Option("self", "Self-study", "Free online resources and library books."),
        Option("job", "Start working after school", "Earn now, but fewer doors open later.",
               cost=-8, roll_bonus=-2),
    ]),
    "Early Career": ("How do you start your career?", [
        Option("intern", "Unpaid internship at a top firm", "Great network, but no salary.",
               cost=12, min_score=45, roll_bonus=2),
        Option("city", "Move to a big city", "More jobs, but rent is high.",
               cost=8, min_score=25, roll_bonus=1),
        Option("local", "Take the first local job", "Safe, but limited growth."),
    ]),
    "Career": ("What do you do with your career?", [
        Option("invest", "Invest your savings", "Returns arrive next stage (+20).",
               cost=10, min_score=55, deferred=20),
        Option("business", "Start your own business", "High risk, high reward: wins and losses double.",
               cost=5, min_score=15, swing=2.0),
        Option("steady", "Stay in a steady job", "No surprises."),
    ]),
    "Middle Age": ("How do you prepare for the future?", [
        Option("insurance", "Buy health insurance", "Bad events this stage cost much less.",
               cost=8, min_score=30, loss_mult=0.4),
        Option("save", "Save for retirement", "Pay now, get +20 in old age.",
               cost=12, min_score=40, deferred=20),
        Option("spend", "Cover today's expenses", "Nothing left over to plan ahead."),
    ]),
    "Old Age": ("How do you support yourself in old age?", [
        Option("pension", "Live on pension and savings", "Only possible if you built enough.",
               min_score=60, roll_bonus=1),
        Option("family", "Move in with family", "Family softens the blows.", loss_mult=0.7),
        Option("work", "Keep working", "Earn a little, but it wears you down.",
               cost=-5, roll_bonus=-1),
    ]),
}

SOCIETY_EVENTS = [
    ("Economic boom", "Jobs are easy to find. Everyone gets +1 on their roll.", {"roll": 1}),
    ("Recession", "Layoffs everywhere. Losses this stage are 50% bigger.", {"loss_mult": 1.5}),
    ("Pandemic", "Everyone with a score below 40 loses 8 points before playing.", {"low_hit": (40, 8)}),
    ("Scholarship drive", "Players with a score below 40 get +1 on their roll.", {"low_roll": (40, 1)}),
]


def dice_bonus(score):
    """Advantage turns into better odds: +1 for every 35 points, max +3."""
    return min(3, int(score // 35))


@dataclass
class GamePlayer:
    name: str
    background: str
    start: float
    score: float = 0.0
    history: list = field(default_factory=list)
    log: list = field(default_factory=list)
    pending: float = 0.0
    locked_count: int = 0

    def __post_init__(self):
        self.score = self.start
        self.history = [self.start]


class Game:
    def __init__(self, names, scenario="Unequal", safety_net=False,
                 free_education=False, seed=42, society_chance=0.5):
        self.rng = random.Random(seed)
        self.safety_net = safety_net
        self.free_education = free_education
        self.society_chance = society_chance
        self.players = self._deal(names, scenario)
        self.stage_idx = 0
        self.turn_idx = 0
        self.phase = "choose"          # choose -> roll -> result -> (next turn)
        self.chosen = None
        self.result = None
        self.notice = None
        self.society = None
        self.stage_news = []           # messages from the society event
        self.finished = False
        self.celebrated = False
        self._start_stage()

    # ------------------------------------------------------------------ setup
    def _deal(self, names, scenario):
        if scenario == "Equal":
            return [GamePlayer(n, "Average family", 50) for n in names]
        cards = BACKGROUNDS[:]
        self.rng.shuffle(cards)
        return [GamePlayer(n, *cards[i % len(cards)]) for i, n in enumerate(names)]

    @property
    def stage(self):
        return STAGES[self.stage_idx]

    @property
    def player(self):
        return self.players[self.turn_idx]

    def _start_stage(self):
        self.turn_idx = 0
        self.stage_news = []
        self.society = None
        if self.rng.random() < self.society_chance:
            self.society = self.rng.choice(SOCIETY_EVENTS)
            effects = self.society[2]
            if "low_hit" in effects:
                limit, hit = effects["low_hit"]
                for p in self.players:
                    if p.score < limit:
                        p.score = max(0.0, p.score - hit)
                        self.stage_news.append(f"{p.name} lost {hit} points")
        self._enter_turn()

    def _enter_turn(self):
        self.phase = "choose"
        self.chosen = None
        self.result = None
        self.notice = None
        p = self.player
        if p.pending:
            p.score = max(0.0, round(p.score + p.pending, 1))
            kind = "Investment returns" if p.pending > 0 else "Loan repayment"
            self.notice = f"{kind}: {p.pending:+.0f} points"
            p.log.append((self.stage, kind.lower(), p.pending))
            p.pending = 0.0

    # ---------------------------------------------------------------- options
    def options(self, player=None):
        """Returns list of (option, locked, reason) for the current stage."""
        player = player or self.player
        out = []
        for opt in DECISIONS[self.stage][1]:
            o = Option(**opt.__dict__)
            if self.free_education and o.key in ("private", "coaching"):
                o.cost, o.min_score = 0, 0
                o.desc += " Free for everyone under the education policy."
            need = max(o.min_score, o.cost)
            locked = player.score < need
            reason = f"Needs {need:.0f} points" if locked else ""
            out.append((o, locked, reason))
        return out

    def question(self):
        return DECISIONS[self.stage][0]

    def choose(self, key):
        for o, locked, _ in self.options():
            if o.key == key and not locked:
                p = self.player
                p.locked_count += sum(1 for _, lk, _ in self.options() if lk)
                p.score = max(0.0, round(p.score - o.cost, 1))
                p.pending += o.deferred
                self.chosen = o
                self.phase = "roll"
                return

    # ------------------------------------------------------------------- dice
    def bonus_parts(self):
        """Dice bonus for the current turn, split by source."""
        p, o = self.player, self.chosen
        effects = self.society[2] if self.society else {}
        society = effects.get("roll", 0)
        if "low_roll" in effects and p.score < effects["low_roll"][0]:
            society += effects["low_roll"][1]
        return {"advantage": dice_bonus(p.score),
                "choice": o.roll_bonus if o else 0,
                "society": society}

    def roll(self):
        p, o = self.player, self.chosen
        effects = self.society[2] if self.society else {}
        die = self.rng.randint(1, 6)
        bonus = sum(self.bonus_parts().values())
        total = die + bonus
        good = die == 6 or (die != 1 and total >= 4)

        s = min(p.score, 100) / 100
        if good:
            text, base = self.rng.choice(GOOD_EVENTS[self.stage])
            change = base * (1 + s) * o.swing * EFFECT_SCALE
            if die == 6:
                change *= 1.5
        else:
            text, base = self.rng.choice(BAD_EVENTS[self.stage])
            change = base * (1 + (1 - s)) * o.swing * o.loss_mult * EFFECT_SCALE
            change *= effects.get("loss_mult", 1.0)
            if self.safety_net and p.score < 50:
                change *= 0.5
        change = round(change, 1)
        p.score = max(0.0, round(p.score + change, 1))
        p.log.append((self.stage, f"chose '{o.label}', then {text}", change))
        self.result = {
            "die": die, "face": DICE[die], "bonus": bonus, "total": total,
            "good": good, "text": text, "change": change,
            "lucky": die == 6, "unlucky": die == 1,
        }
        self.phase = "result"

    # ------------------------------------------------------------------ flow
    def next_turn(self):
        if self.turn_idx < len(self.players) - 1:
            self.turn_idx += 1
            self._enter_turn()
            return
        for p in self.players:
            p.history.append(p.score)
        if self.stage_idx < len(STAGES) - 1:
            self.stage_idx += 1
            self._start_stage()
        else:
            self.finished = True

    def auto_choice(self):
        """Pick the best option the player can afford (or is pushed into)."""
        p = self.player
        # keep a buffer: don't spend money you can't afford to lose
        unlocked = [o for o, locked, _ in self.options()
                    if not locked and (o.cost <= 0 or p.score - o.cost >= 25)]
        if p.score < 25:   # under pressure, take whatever earns money now
            earners = [o for o in unlocked if o.cost < 0]
            if earners:
                return earners[0].key
        best = max(unlocked, key=lambda o: (o.roll_bonus + o.deferred / 10
                                            + (1 - o.loss_mult) * 3, -o.cost))
        return best.key

    def auto_turn(self):
        if self.finished:
            return
        if self.phase == "choose":
            self.choose(self.auto_choice())
        if self.phase == "roll":
            self.roll()
        self.next_turn()

    def auto_stage(self):
        current = self.stage_idx
        while not self.finished and self.stage_idx == current:
            self.auto_turn()

    def auto_all(self):
        while not self.finished:
            self.auto_turn()

    # ---------------------------------------------------------------- stats
    def gini_now(self):
        return gini([p.score for p in self.players])

    def gini_start(self):
        return gini([p.start for p in self.players])
