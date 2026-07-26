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

# Struktura tiketa — UJEDNAČENA za sve podloge (korisnikova odluka, 26.07.2026):
# 4-6 parova, kombinirana kvota 6.0-40.0. Prije: 4-7 parova / 6.5-40 uz surface override
# za clay (6.5-30, max 6) i hard (max 6). Razlog ujednačavanja: manje parova = manja
# izloženost akumulator-matematici, a jedinstvena pravila su lakša za praćenje.
# Kad ima premalo mečeva za 4 para, sustav i dalje ide u analysis-only (nepromijenjeno).
TICKET_CONFIG = {
    "stake": 50.0,
    "min_matches": 4,
    "max_matches": 6,
    "min_combined_odds": 6.0,
    "max_combined_odds": 40.0,
    "min_confidence": 63.0,
    "fallback_confidence": 58.0,
    "last_resort_confidence": 55.0,
}

# Surface-specifični overridi UKINUTI 26.07.2026 (korisnikova odluka): sve podloge sada
# dijele istu strukturu iz TICKET_CONFIG-a. Prazan dict znači "nema override-a" i
# _apply_surface_overrides tiho prolazi bez ikakve izmjene.
# NAPOMENA za buduće revizije: EV pri našem stvarnom pogotku (~63% po picku) traži
# kombiniranu kvotu ~6.0 za 4 para, ~9.3 za 5 i ~14.6 za 6 parova da bi tiket bio na nuli.
# Fiksni donji prag 6.0 znači da su tiketi s 5-6 parova pri dnu raspona matematički
# nepovoljni — kandidat za sljedeću reviziju (min_combined_odds koji skalira s brojem nogu).
SURFACE_TICKET_OVERRIDES = {}

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

# "analysis" (18.07.2026, korisnikova odluka): Haiku -> Sonnet, uz output_config effort="high"
# na samom analyze_match pozivu (vidi predictor.py; "xhigh" NIJE podržan za ovaj model — API
# 400 "Supported levels: high, low, max, medium"). Razlog: jezgra predikcije (pick/confidence/
# fair_odds) je najvažnija odluka u cijelom pipelineu — sve nizvodno (filteri, kombinatorika)
# samo radi s brojkama koje ovaj poziv već odluči. Povod: precjenjivanje pouzdanosti (~7-16pp)
# otkriveno NEOVISNO na sve tri podloge — sumnja da je riječ o svojstvu modela, ne podloge.
#
# "feedback" (18.07.2026, isti dan): Haiku -> Sonnet, isti output_config effort="high" na oba
# poziva u feedback_analyzer.py (analiza gubitka + prijedlog korekcije težina). Drugi od ta dva
# poziva izravno mijenja žive težine za sve buduće predikcije — najveći utjecaj po pozivu u
# cijelom večernjem jobu. Volumen je nizak (max 5 loss-analiza + povremeni weight-prijedlog tek
# nakon 5+ novih analiza), pa je dodatni trošak trivijalan; očekivana dobit manja nego kod
# "analysis" jer je ovo slobodno pisanje objašnjenja, ne kalibrirana brojčana procjena.
CLAUDE_MODELS = {
    "analysis": "claude-sonnet-4-6",
    "ticket_writer": "claude-sonnet-4-6",
    "feedback": "claude-sonnet-4-6",
    "odds_extraction": "claude-sonnet-4-6",
}
