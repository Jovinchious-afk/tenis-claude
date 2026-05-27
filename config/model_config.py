"""
Model configuration: default weights, tournament hierarchy, constants.
Weights are stored in Supabase (model_weights table) and can be adjusted
automatically by the feedback loop. These are the initial defaults.
"""

DEFAULT_WEIGHTS = {
    "elo_ranking": 20.0,        # ELO + ranking trend + opponent quality
    "surface_style": 23.0,      # Surface + style matchup
    "serve_return": 18.0,       # Serve + return stats (surface-adjusted)
    "recent_form": 18.0,        # Form last 5-10 matches (quality-adjusted)
    "fatigue_injuries": 12.0,   # Fatigue, injuries, travel, schedule
    "h2h_context": 5.0,         # H2H + tournament context + motivation
    "odds_movement": 4.0,       # Odds movement + market signal (filter role)
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
    "min_combined_odds": 8.0,
    "max_combined_odds": 15.0,
    "min_confidence": 63.0,
    "fallback_confidence": 58.0,    # koristi se ako nema dovoljno mečeva
    "max_matches_same_tournament": 2,
}

WEIGHT_ADJUSTMENT = {
    "step": 0.5,        # % po korekciji
    "max_shift": 3.0,   # max ukupna promjena od početka
    "min_weight": 1.0,  # nijedna težina ne može ići ispod 1%
    "max_weight": 35.0, # nijedna težina ne može ići iznad 35%
}

CLAUDE_MODELS = {
    "analysis": "claude-haiku-4-5-20251001",
    "ticket_writer": "claude-sonnet-4-6",
    "feedback": "claude-haiku-4-5-20251001",
}
