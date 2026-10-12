# Life-Course Inequality Simulator (Group 12, Track 6)

## Setup
    pip install -r requirements.txt

## Live demo (for the class playtest)
    streamlit run app.py
Opens in your browser. Set players, scenario and policies in the sidebar.

- "Play the game" tab: turn-based game. Each player makes a life choice
  (better options cost points and can be locked), then rolls the dice.
  Society events (boom, recession, pandemic, scholarships) hit some stages.
- "Quick simulation" tab: one click per life stage, no choices.
- "1,000-life analysis" tab: the statistics for the writeup.

## Charts for the writeup
    python generate_charts.py
Saves 4 PNG charts and results.txt into charts/.

## Files
- simulation.py: rules, event tables, Gini, batch runs (all tunable numbers are in Config)
- plots.py: all charts
- game.py: turn-based game (choices, dice, society events)
- app.py: Streamlit interface
- generate_charts.py: report charts and numbers
