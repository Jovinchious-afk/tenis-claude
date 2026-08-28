"""
Model configuration: default weights, tournament hierarchy, constants.
Weights are stored in Supabase (model_weights table) and can be adjusted
automatically by the feedback loop. These are the initial defaults.
"""

# DVIJE OGRADE ZA REVIZIJU (izmjereno 07.08.2026 na Montrealu — vidi MODEL_CHANGELOG).
# Ovo su samo POCETNE vrijednosti; aktivne tezine po podlozi zive u Supabase `model_weights`
# (hard v18, clay v17, grass v12), pa izmjena ovdje ne mijenja nista dok se ne upise nova
# verzija. Biljezi se ovdje jer je ovo mjesto na koje se prvo gleda.
#
# `serve_return` (najveca tezina): mjeri se proxyjima koji su ili napuhani, ili pristrani,
#   ili do 07.08. nisu ni stizali. `hold_pct` je linearni proxy s mnoziteljem 1,9 (API ne daje
#   gem-ove na servisu); `return_points_won` precjenjuje za +2,33pp; break lopte su zbog krivih
#   naziva API polja UVIJEK bile None u promptu. Prije diranja same tezine treba srediti sto
#   ona uopce mjeri — vidi komentare u data_fetcher.get_player_stats i predictor._BP_TO_PROMPT.
#
# `fatigue_injuries`: u Montrealu nema nikakvog signala. Nas pick na 1. mecu turnira 62,0%
#   (n=50), na 2. mecu 70,0% (n=10); tko je odmorniji — mi svjeziji 58,3%, jednako 63,6%,
#   protivnik svjeziji 60,0%. Istovremeno 7 od 11 analiza gubitaka krivi umor, ali u SUPROTNIM
#   smjerovima (jednom "underweighted", drugi put "over-weighted", treci put "misfired in the
#   wrong direction"). Kad se ista korekcija optuzi u oba smjera, to je sum, a ne losa
#   kalibracija. Kandidat za smanjenje — ali tek kad bude cime izmjeriti.
# =============================================================================================
# MJERENJE 26.08.2026 14:01 — hard, tezine v18, n=178 rijesenih analiza (04.-26.08.2026).
# Referentna vrijednost je DEVIGIRANA SuperSport cijena (obje strane; marza 5,13%).
#
# `serve_return` (22-23%, najveca tezina): sezonske servisne/povratne brojke NE razdvajaju
#   nase pogotke od promasaja. Dohvaceno za svih 105 igraca iz uzorka; drift naspram onoga
#   sto je model tada vidio je 0,02pp, dakle to su tocno te brojke. r(jaz nas-protivnik,
#   pogodak), n=139:
#       ukupni servis +0,006 | 1. servis -0,006 | 2. servis +0,024 | 1. servis IN +0,019
#       asovi +0,010 | dvostruke greske +0,002 | hold +0,006 | povrat -0,059 (pond.)
#       BP spasene +0,009 | BP iskoristene -0,031 | break% -0,052 | hold iz BP +0,020
#   Sve P > 0,49. Srednji jazovi su isti do druge decimale (servis +1,77 u dobitcima naspram
#   +1,74 u gubitcima). Nije rijec o kolinearnosti s cijenom (r=+0,177) ni s ELO-om (+0,181) —
#   brojka je slabo povezana sa svime. KANDIDAT ZA SMANJENJE, ali tek kad se zna cime se
#   oslobodjena tezina popunjava (vidi nalaze 5A i 3 u MODEL_CHANGELOG 26.08.2026).
#
# `fatigue_injuries` (12%): iz `player_match_history` (uz zastitu od curenja) sirovo izgleda
#   OBRNUTO od ocekivanja — nas pick s 2+ meca u zadnjih 3-9 dana 65,3%, odmorniji 47,4%
#   (r=+0,172 P=0,049). Pod kontrolom cijene efekt pada na -0,9 naspram -8,7pp i predznak se
#   okrece u pojasu 62%+. Sam po sebi preslab. ALI kao INTERAKCIJA s rundom je najjaci
#   mehanizam koji smo nasli: u R16/QF, kad je PROTIVNIK odigrao 2+ meca u 3-9 dana,
#   prolazimo 35,0% (n=20) naspram 59,7% ocekivano — -24,7pp, z=-2,30, ROI -47%; ista
#   situacija u ostalim rundama +10,2pp. Nije rijec o tezini nego o pravilu 1 u promptu.
#
# NOVO, JOS NIJE U MODELU (3 signala koja prezivljavaju kontrolu cijene, runde i split-half):
#   1. prosjecni hard-ELO zadnjih 5 protivnika naseg picka < 1700 -> 41,0% (n=39), -19,0pp,
#      z=-2,48, ROI -37,1%; >= 1700 -> +2,5pp. r=+0,252 P=0,0028.
#   2. nas pick stariji od protivnika 4+ godine -> 42,9% (n=42), -15,4pp, z=-2,08, ROI -31,6%;
#      monotono kroz 5 razreda, r=-0,228 P=0,0069. Dob je od 15.08. NAMJERNO izvan prompta.
#   3. runda R16/QF -> -13,3pp (z=-2,31) naspram +3,7pp u ostalim rundama; bootstrap
#      95% [-31,4, -2,5]; drzi se u 3/3 turnira i sva tri pojasa cijene.
# =============================================================================================
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
#
# POTVRĐENO MJERENJEM 08.08.2026 11:35: stvarni pogodak je 60,9% po nozi (198/325), dakle
# NIŽI od 63% na kojem je gornji račun rađen — prag za nulu je time još viši. Ishodi po
# broju parova: 4 para 2W-19L, 5 parova 1W-14L, 6 parova 1W-7L (ukupno 4W-41L, ROI -43%),
# dok su same noge tek 1,7pp od nule. Gubitak dolazi iz množenja, ne iz loših pickova.
#
# KORISNIKOVA UPUTA UZ TO (08.08.2026): granice 4-6 parova i 6-40 kvote OSTAJU nepromijenjene,
# i cilj NIJE uvijek slagati četiri para pri dnu raspona. Naprotiv — pet ili šest parova je
# poželjno kad ih prati odgovarajuća kvota (20, 32), a odluku o riziku i graničnoj korisnosti
# donosi model. Ono što ovaj račun kaže nije "manje parova", nego "ako uzimaš više parova,
# moraš biti plaćen za njih": šesterac na kvoti 6,5 je matematički osuđen, šesterac na 32 nije.
# Zato je kandidat za reviziju SKALIRAJUĆI donji prag, ne pomicanje broja parova.
SURFACE_TICKET_OVERRIDES = {}

# Max kandidata po turniru po danu (danas vs sutra)
# Ovo je pre-filter PRIJE kombinatorike — ne limit na tiketu
# Max kandidata po TURNIRU po DANU koji ulaze u kombinatoriku tiketa (ne u analizu —
# analysis-only ostaje na 12, vidi _ANALYSIS_ONLY_MAX_PICKS). Ograničava izloženost
# jednom turniru. Podignuto na 6 posvuda 01.08.2026 (bilo 5 za "tomorrow"): otkad
# prozor pokriva i prekosutra, jedan turnir zna dati 13+ screenshotanih parova, a
# stari limit od 5 je bespotrebno rezao izbor. Challenger/Qualifying ostaju 0 —
# to je politička isključenost, ne kapacitet.
DAILY_MATCH_LIMITS = {
    "Grand Slam":       {"today": 7, "tomorrow": 6},
    "ATP Masters 1000": {"today": 6, "tomorrow": 6},
    "ATP 500":          {"today": 6, "tomorrow": 6},
    "ATP 250":          {"today": 6, "tomorrow": 6},
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
