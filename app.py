"""
Life-Course Inequality Simulator - live classroom demo.
Run with:  streamlit run app.py
"""

import random

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from plots import (final_distribution, gini_comparison, live_gini, score_bars,
                   top_vs_bottom, trajectories)
from game import Game, dice_bonus
from simulation import (SCENARIOS, STAGES, Config, batch_stats, create_players,
                        gini, outcome_label, play_stage, run_batch)

st.set_page_config(page_title="Life-Course Inequality Simulator", layout="wide")

# ---------------------------------------------------------------------------
# Sidebar: game setup
# ---------------------------------------------------------------------------
st.sidebar.header("Game setup")
scenario = st.sidebar.radio("Starting conditions", ["Unequal", "Equal"],
                            help="Unequal: each player draws a family background card.")
safety_net = st.sidebar.checkbox("Policy: social safety net",
                                 help="Halves losses for anyone with a score below 50.")
free_ed = st.sidebar.checkbox("Policy: free quality education",
                              help="Everyone gets fair odds in childhood and education.")
seed = st.sidebar.number_input("Quick simulation seed", 0, 99999, 42,
                               help="Same seed = same game. Useful for rehearsing.")
names_text = st.sidebar.text_area("Player names (one per line, up to 8)",
                                  "Aarav\nPriya\nRohan\nAnanya\nKabir\nMeera")
names = [n.strip() for n in names_text.splitlines() if n.strip()][:8] or ["Player 1"]


def new_game():
    rng = random.Random(int(seed))
    st.session_state.rng = rng
    st.session_state.cfg = Config(safety_net=safety_net, free_education=free_ed)
    st.session_state.players = create_players(scenario, names, rng)
    st.session_state.stage = 0
    st.session_state.stage_logs = []
    st.session_state.setup = (scenario, safety_net, free_ed)


if st.sidebar.button("Restart quick simulation") or "players" not in st.session_state:
    new_game()

st.sidebar.caption("Setup changes apply when you deal a new game or restart the quick simulation.")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
st.title("Life-Course Inequality Simulator")
st.write("How small differences at birth grow into large gaps by old age.")

tab_play, tab_game, tab_batch, tab_rules = st.tabs(
    ["🎲 Play the game", "Quick simulation", "1,000-life analysis", "How it works"])


# =========================== Turn-based game ===============================
def deal_game(game_seed):
    st.session_state.game = Game(names, scenario, safety_net, free_ed, int(game_seed))


def clear_game():
    st.session_state.pop("game", None)


def option_details(o):
    bits = []
    if o.cost > 0:
        bits.append(f"Costs {o.cost:.0f} points")
    elif o.cost < 0:
        bits.append(f"Earns {-o.cost:.0f} points now")
    if o.roll_bonus:
        bits.append(f"Dice {o.roll_bonus:+d}")
    if o.deferred:
        bits.append(f"{o.deferred:+.0f} points next stage")
    if o.loss_mult < 1:
        bits.append("Softens bad events")
    if o.swing > 1:
        bits.append("Wins and losses doubled")
    return " | ".join(bits) or "No cost"


def stage_track(g):
    parts = []
    for i, s in enumerate(STAGES):
        if g.finished or i < g.stage_idx:
            parts.append(f"✓ {s}")
        elif i == g.stage_idx:
            parts.append(f"**▶ {s}**")
        else:
            parts.append(s)
    return "  →  ".join(parts)


def leaderboard(g):
    rows = sorted(g.players, key=lambda p: -p.score)
    return pd.DataFrame([{
        "Rank": i + 1,
        "Player": ("▶ " if (not g.finished and p is g.player) else "") + p.name,
        "Points": round(p.score),
        "Since birth": f"{p.score - p.start:+.0f}",
    } for i, p in enumerate(rows)])


def render_turn(g):
    p = g.player
    st.markdown(f"### {p.name}'s turn")
    st.caption(f"Born into: {p.background}")
    c1, c2 = st.columns(2)
    done = g.phase == "result"
    c1.metric("Advantage points", f"{p.score:.0f}",
              delta=f"{g.result['change']:+.0f}" if done else None)
    c2.metric("Dice bonus next time" if done else "Dice bonus from advantage",
              f"+{dice_bonus(p.score)}")
    if g.notice:
        st.info(g.notice)

    key = f"{g.stage_idx}_{g.turn_idx}"
    if g.phase == "choose":
        st.markdown(f"#### {g.question()}")
        for o, locked, reason in g.options():
            with st.container(border=True):
                left, right = st.columns([4, 1])
                left.markdown(f"**{o.label}**  \n{o.desc}")
                left.caption(f"🔒 Locked: {reason.lower()}" if locked else option_details(o))
                right.button("Locked" if locked else "Choose", key=f"opt_{key}_{o.key}",
                             disabled=locked, on_click=g.choose, args=(o.key,))

    elif g.phase == "roll":
        parts = g.bonus_parts()
        st.markdown(f"#### You chose: {g.chosen.label}")
        st.write(f"Your dice bonus this turn: **{sum(parts.values()):+d}** "
                 f"(advantage {parts['advantage']:+d}, choice {parts['choice']:+d}, "
                 f"society {parts['society']:+d})")
        st.caption("Roll + bonus of 4 or more is a good event. A 6 is always a lucky break, "
                   "a 1 is always bad luck.")
        st.button("🎲 Roll the dice", key=f"roll_{key}", type="primary",
                  on_click=g.roll)

    else:
        r = g.result
        left, right = st.columns([1, 3])
        left.markdown(f"<div style='font-size:110px;line-height:1'>{r['face']}</div>",
                      unsafe_allow_html=True)
        right.markdown(f"#### Rolled {r['die']} + bonus {r['bonus']} = {r['total']}")
        if r["lucky"]:
            right.markdown("**Lucky break!** Gains are 1.5x.")
        elif r["unlucky"]:
            right.markdown("**Bad luck.** A 1 is bad for everyone, however privileged.")
        msg = f"{p.name} {r['text']}: {r['change']:+.0f} points"
        (st.success if r["good"] else st.error)(msg)
        last_turn = g.turn_idx == len(g.players) - 1
        if not last_turn:
            label = f"Next: {g.players[g.turn_idx + 1].name}'s turn"
        elif g.stage_idx < len(STAGES) - 1:
            label = f"Finish {g.stage} and move to {STAGES[g.stage_idx + 1]}"
        else:
            label = "See how everyone's life turned out"
        st.button(label, key=f"next_{key}", type="primary", on_click=g.next_turn)


def render_end(g):
    if not g.celebrated:
        st.balloons()
        g.celebrated = True
    st.markdown("## Life complete")
    rows = sorted(g.players, key=lambda p: -p.score)
    st.dataframe(pd.DataFrame([{
        "Player": p.name,
        "Background": p.background,
        "Born with": p.start,
        "Old age": round(p.score),
        "Change": f"{p.score - p.start:+.0f}",
        "Options locked": p.locked_count,
        "Outcome": outcome_label(p.score),
    } for p in rows]), hide_index=True)

    by_start = sorted(g.players, key=lambda p: p.start)
    half = len(by_start) // 2 or 1
    bottom, top = by_start[:half], by_start[-half:]
    avg = lambda ps, f: sum(f(p) for p in ps) / len(ps)
    m1, m2, m3 = st.columns(3)
    m1.metric("Inequality (Gini)", f"{g.gini_now():.2f}",
              delta=f"{g.gini_now() - g.gini_start():+.2f} since birth", delta_color="inverse")
    if len({p.start for p in g.players}) > 1:
        m2.metric("Gap: richer-born vs poorer-born half",
                  f"{avg(top, lambda p: p.score) - avg(bottom, lambda p: p.score):.0f}",
                  delta=f"was {avg(top, lambda p: p.start) - avg(bottom, lambda p: p.start):.0f} at birth",
                  delta_color="off")
        m3.metric("Options locked: poorer-born vs richer-born",
                  f"{avg(bottom, lambda p: p.locked_count):.1f} vs {avg(top, lambda p: p.locked_count):.1f}")

    a, b = st.columns(2)
    with a:
        fig = trajectories(g.players)
        st.pyplot(fig)
        plt.close(fig)
    with b:
        fig = live_gini(g.players)
        st.pyplot(fig)
        plt.close(fig)

    st.markdown("#### Questions for the class")
    st.markdown(
        "- Did anyone born poor end near the top? What had to go right for them?\n"
        "- Which choices were locked for some players but not others? Was that their fault?\n"
        "- Did the society events (recession, pandemic) hit everyone equally?\n"
        "- Try again with the policies switched on. What changes?")
    st.button("Play again", type="primary", on_click=clear_game)


with tab_play:
    g = st.session_state.get("game")
    if g is None:
        st.markdown("### Set up a new game")
        st.write("Each player is dealt a family background card at birth. Then, in every "
                 "life stage, each player makes a life choice and rolls the dice. Players "
                 "are set in the sidebar.")
        st.write(f"Players: {', '.join(names)}  \nStarting conditions: {scenario}  \n"
                 f"Policies: {', '.join(p for p, on in (('safety net', safety_net), ('free education', free_ed)) if on) or 'none'}")
        game_seed = st.number_input("Game seed", 0, 99999, 184,
                                    help="Same seed and same choices give the same game.")
        st.button("Deal background cards", type="primary", on_click=deal_game,
                  args=(game_seed,))
    elif g.finished:
        render_end(g)
    else:
        st.progress(g.stage_idx / len(STAGES))
        st.markdown(stage_track(g))
        if g.society:
            name, desc, _ = g.society
            news = f" ({'; '.join(g.stage_news)})" if g.stage_news else ""
            st.warning(f"**Society event: {name}.** {desc}{news}")

        if g.stage_idx == 0 and g.turn_idx == 0 and g.phase == "choose":
            st.markdown("#### Background cards dealt")
            cols = st.columns(len(g.players))
            for col, p in zip(cols, g.players):
                with col.container(border=True):
                    st.markdown(f"**{p.name}**")
                    st.caption(p.background)
                    st.markdown(f"### {p.start:.0f}")
                    st.caption(f"points | dice +{dice_bonus(p.start)}")

        left, right = st.columns([3, 2])
        with left:
            render_turn(g)
        with right:
            st.markdown("#### Leaderboard")
            st.dataframe(leaderboard(g), hide_index=True)
            fig = trajectories(g.players)
            st.pyplot(fig)
            plt.close(fig)

        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.button("Auto-play the rest of this stage", on_click=g.auto_stage)
        c2.button("Auto-play to old age", on_click=g.auto_all)
        c3.button("Restart game", on_click=clear_game)
        st.caption("Auto-play makes the best choice each player can afford.")

# ------------------------- Quick simulation --------------------------------
with tab_game:
    players = st.session_state.players
    stage_i = st.session_state.stage
    cfg = st.session_state.cfg
    sc, sn, fe = st.session_state.setup
    policies = [p for p, on in (("safety net", sn), ("free education", fe)) if on]
    st.caption(f"Scenario: {sc} start"
               + (f" | Policies: {', '.join(policies)}" if policies else " | No policies"))

    done = stage_i >= len(STAGES)
    c1, c2, c3 = st.columns([2, 2, 3])
    if not done:
        if c1.button(f"Play stage: {STAGES[stage_i]}", type="primary"):
            lines = play_stage(players, STAGES[stage_i], cfg, st.session_state.rng)
            st.session_state.stage_logs.append((STAGES[stage_i], lines))
            st.session_state.stage += 1
            st.rerun()
        if c2.button("Play to old age"):
            for s in STAGES[stage_i:]:
                lines = play_stage(players, s, cfg, st.session_state.rng)
                st.session_state.stage_logs.append((s, lines))
            st.session_state.stage = len(STAGES)
            st.rerun()
    else:
        c1.success("Life complete. See final outcomes below.")

    scores = [p.score for p in players]
    current = "Birth" if stage_i == 0 else STAGES[stage_i - 1]
    m1, m2, m3 = st.columns(3)
    m1.metric("Stage completed", current)
    m2.metric("Gini coefficient", f"{gini(scores):.2f}",
              delta=f"{gini(scores) - gini([p.start for p in players]):+.2f} since birth",
              delta_color="inverse")
    m3.metric("Gap: richest vs poorest", f"{max(scores) - min(scores):.0f}",
              delta=f"{(max(scores) - min(scores)) - (max(p.start for p in players) - min(p.start for p in players)):+.0f} since birth",
              delta_color="inverse")

    left, right = st.columns(2)
    with left:
        fig = score_bars(players)
        st.pyplot(fig)
        plt.close(fig)
    with right:
        fig = trajectories(players)
        st.pyplot(fig)
        plt.close(fig)

    if st.session_state.stage_logs:
        last_stage, last_lines = st.session_state.stage_logs[-1]
        st.subheader(f"What happened in {last_stage}")
        for line in last_lines:
            st.write("- " + line)

        fig = live_gini(players)
        st.pyplot(fig)
        plt.close(fig)

        with st.expander("Full life log"):
            for s, lines in st.session_state.stage_logs:
                st.markdown(f"**{s}**")
                for line in lines:
                    st.write("- " + line)

    if done:
        st.subheader("Final outcomes")
        df = pd.DataFrame([{
            "Player": p.name,
            "Background": p.background,
            "Start": p.start,
            "Old age": p.score,
            "Change": round(p.score - p.start, 1),
            "Outcome": outcome_label(p.score),
        } for p in sorted(players, key=lambda p: -p.score)])
        st.dataframe(df, hide_index=True)

# --------------------------- Batch analysis --------------------------------
with tab_batch:
    st.write("Run the same rules for many simulated lives to see the pattern, "
             "not just one lucky or unlucky game.")
    n = st.slider("Number of lives per scenario", 200, 5000, 1000, step=200)
    if st.button("Run analysis", type="primary"):
        hist, stats = {}, {}
        for name, (sc_name, sc_cfg) in SCENARIOS.items():
            hist[name] = run_batch(sc_name, sc_cfg, n=n, seed=int(seed))
            stats[name] = batch_stats(hist[name])
        st.session_state.batch = (hist, stats)

    if "batch" in st.session_state:
        hist, stats = st.session_state.batch
        table = pd.DataFrame([{
            "Scenario": name,
            "Gini at birth": round(s["start_gini"], 2),
            "Gini in old age": round(s["end_gini"], 2),
            "Top vs bottom gap at birth": None if s["start_gap"] is None
                                          else round(s["start_gap"], 1),
            "Top vs bottom gap in old age": None if s["end_gap"] is None
                                            else round(s["end_gap"], 1),
            "% in poverty (old age)": round(s["poverty_pct"], 1),
            "% bottom starters reaching top 20%": None if s["mobility_pct"] is None
                                                   else round(s["mobility_pct"], 1),
        } for name, s in stats.items()])
        st.dataframe(table, hide_index=True)

        a, b = st.columns(2)
        with a:
            fig = gini_comparison(stats)
            st.pyplot(fig)
            plt.close(fig)
        with b:
            fig = top_vs_bottom(stats["Unequal start"], "Unequal start: top vs bottom 20%")
            st.pyplot(fig)
            plt.close(fig)
        a, b = st.columns(2)
        with a:
            fig = top_vs_bottom(stats["Unequal + policies"], "With policies: top vs bottom 20%")
            st.pyplot(fig)
            plt.close(fig)
        with b:
            fig = final_distribution(hist)
            st.pyplot(fig)
            plt.close(fig)

        st.info("Note the equal-start scenario: inequality still rises from zero. "
                "Because early luck changes later odds, random differences compound "
                "into lasting gaps.")

# ----------------------------- Rules ---------------------------------------
with tab_rules:
    st.markdown("""
### The game

Each player is dealt a **family background card** that sets their starting points.
In every life stage, each player:

1. **Makes a choice.** Better options cost points, so some are **locked** for
   poorer players. Loans, investments and savings pay off (or cost) a stage later.
2. **Rolls the dice.** Roll + bonus of 4 or more is a good event. The bonus grows
   with your points (+1 per 35 points, max +3). A 6 is always a lucky break (1.5x gains);
   a 1 is always bad luck.

Half the stages also bring a **society event**: a boom, a recession, a pandemic or a
scholarship drive.

### Quick simulation

**The life course.** Each player passes through six stages: childhood, education,
early career, career, middle age and old age. In each stage they face two random events.

**Three rules create cumulative advantage:**

1. *Better odds.* The higher your score, the more likely your next event is good
   (chance of a good event = 30% + 45% x score/100, capped at 90%).
2. *Bigger gains.* Good events are worth more when your score is high, the way
   wealth earns returns.
3. *Harder falls.* Bad events cost more when your score is low, because there is
   no savings or family buffer to absorb them.

**Policies you can switch on:**

- *Social safety net:* losses are halved for anyone below 50.
- *Free quality education:* everyone gets at least a 55% chance of good events
  in childhood and education, whatever their background.

**Outcome bands in old age:** 100+ comfortable and secure, 60-99 stable,
30-59 struggling, below 30 in poverty.
""")
