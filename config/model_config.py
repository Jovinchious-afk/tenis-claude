"""
Model configuration: default weights, tournament hierarchy, constants.
Weights are stored in Supabase (model_weights table) and can be adjusted
automatically by the feedback loop. These are the initial defaults.
"""

DEFAULT_WEIGHTS = {
    "elo_ranking":          22.0,  # ELO (surface-specific weighted higher than ATP ranking) + opponent quality
    "surface_style":        20.0,  # Surface win rate + style matchup + playing hand
    "serve_return":         22.0,  # Hold%, break%, serve points won%, return dominance
    "recent_form":          17.0,  # Form last 5-10 matches (opponent-quality adjusted)
    "fatigue_injuries":     11.0,  # Fatigue, injuries, days rest, age, match load
    "h2h_context":           4.0,  # H2H (min 3 recent matches), tournament context, round, weather
    "tournament_trajectory": 4.0,  # In-tournament W/L momentum, current run quality, hot-hand signal
}

TOURNAMENT_LEVELS = {
    "Grand Slam": 100,
    "ATP Masters 1000": 85,
    "ATP 500": 65,
    "ATP 250": 45,
    "ATP Challenger": 25,
    "ATP Qualifying": 10,
}

SURFACE_MAP = {
    "clay": "Clay",
    "hard": "Hard",
    "grass": "Grass",
    "indoor_hard": "Indoor Hard",
    "carpet": "Carpet",
}

TICKET_CONFIG = {
    "stake": 50.0,
    "min_matches": 4,
    "max_matches": 7,
    "min_combined_odds": 6.5,
    "max_combined_odds": 40.0,
    "min_confidence": 63.0,
    "fallback_confidence": 58.0,
    "last_resort_confidence": 55.0,
}

# Surface-specifični overridi TICKET_CONFIG-a — primjenjuju se kad su SVI kandidati
# tiketa na toj podlozi (clay revizija 2026-07-11, n=32 pickova / 7 tiketa 0/7):
# clay 6.5-30 umjesto 6.5-40 i max 6 parova umjesto 7 — visoke kombinirane kvote
# na clayu su se gradile gomilanjem dead-zone (1.50-1.90) pickova koji pobjeđuju 27%.
SURFACE_TICKET_OVERRIDES = {
    "clay": {"max_combined_odds": 30.0, "max_matches": 6},
}

# Max kandidata po turniru po danu (danas vs sutra)
# Ovo je pre-filter PRIJE kombinatorike — ne limit na tiketu
DAILY_MATCH_LIMITS = {
    "Grand Slam":       {"today": 7, "tomorrow": 6},
    "ATP Masters 1000": {"today": 6, "tomorrow": 5},
    "ATP 500":          {"today": 6, "tomorrow": 5},
    "ATP 250":          {"today": 6, "tomorrow": 5},
    "ATP Challenger":   {"today": 0, "tomorrow": 0},
    "ATP Qualifying":   {"today": 0, "tomorrow": 0},
}

WEIGHT_ADJUSTMENT = {
    "step": 3.0,        # max % per correction (Claude decides 0.5-3 based on pattern strength)
    "max_shift": 8.0,   # max total shift from starting point
    "min_weight": 1.0,  # no factor can drop below 1%
    "max_weight": 35.0, # no factor can exceed 35%
}

CLAUDE_MODELS = {
    "analysis": "claude-haiku-4-5-20251001",
    "ticket_writer": "claude-sonnet-4-6",
    "feedback": "claude-haiku-4-5-20251001",
    "odds_extraction": "claude-sonnet-4-6",
}
