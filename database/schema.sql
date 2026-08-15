-- Tennis Agent Database Schema
-- Pokreni u Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ELO Cache (populated locally via scripts/update_elo_cache.py, read by GitHub Actions)
CREATE TABLE IF NOT EXISTS elo_cache (
    player_name TEXT PRIMARY KEY,
    elo_overall FLOAT NOT NULL DEFAULT 1500,
    elo_hard    FLOAT NOT NULL DEFAULT 1500,
    elo_clay    FLOAT NOT NULL DEFAULT 1500,
    elo_grass   FLOAT NOT NULL DEFAULT 1500,
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Dnevni tiketi
CREATE TABLE IF NOT EXISTS tickets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'won', 'lost', 'void', 'analysis_only')),
    stake DECIMAL(10,2) DEFAULT 50.00,
    total_odds DECIMAL(10,4),
    potential_win DECIMAL(10,2),
    actual_win DECIMAL(10,2),
    matches_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE,
    ticket_summary TEXT,
    reviewer_decision VARCHAR(20),
    reviewer_changes TEXT,
    reviewer_warning TEXT
);

-- Mečevi na tiketu
CREATE TABLE IF NOT EXISTS ticket_matches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID REFERENCES tickets(id) ON DELETE CASCADE,
    external_match_id VARCHAR(200),
    player1 VARCHAR(150) NOT NULL,
    player2 VARCHAR(150) NOT NULL,
    -- API player ID-evi, spremljeni pri kreiranju tiketa (2026-07-26, A1). Bez njih evening
    -- update ovisi o tome da turnir još postoji u fixtures feedu — 25.07.2026 je Generali Open
    -- Kitzbühel nestao iz feeda pa se Bublik-Halys nije mogao razriješiti. Postojeća baza:
    --   ALTER TABLE ticket_matches ADD COLUMN IF NOT EXISTS player1_id VARCHAR(30);
    --   ALTER TABLE ticket_matches ADD COLUMN IF NOT EXISTS player2_id VARCHAR(30);
    player1_id VARCHAR(30),
    player2_id VARCHAR(30),
    -- Tržišni konsenzus U TRENUTKU OKLADE (2026-08-15 10:12). Cijene 20-46 kladionica,
    -- razvigane i spojene medijanom: {p, p_sharp, ev_p1, ev_p2, gap_pp, n_books, overround}.
    -- ZAŠTO OVDJE, a ne samo u analyzed_matches.context_snapshot: ondje se redak istog meča
    -- PREPISUJE kad se par analizira i sutradan (par sa "sutra" screenshota analizira se
    -- dvaput), pa bi se izgubila cijena po kojoj je oklada stvarno odigrana. `ticket_matches`
    -- se nikad ne prepisuje, pa je ovo jedino mjesto gdje bet-time cijena preživi.
    -- Postojeća baza:
    --   ALTER TABLE ticket_matches ADD COLUMN IF NOT EXISTS market_snapshot JSONB;
    -- Kod radi i BEZ ovog stupca (vidi _OPTIONAL_TM_COLS) — tada se samo ne bilježi.
    market_snapshot JSONB,
    pick VARCHAR(150) NOT NULL,
    odds DECIMAL(10,4) NOT NULL,
    match_date DATE NOT NULL,
    match_time VARCHAR(20),
    tournament VARCHAR(250),
    tournament_level VARCHAR(50),
    surface VARCHAR(50),
    round VARCHAR(80),
    confidence DECIMAL(5,2),
    fair_odds DECIMAL(10,4),
    value_bet BOOLEAN DEFAULT FALSE,
    risk_level VARCHAR(20),
    risk_notes TEXT,
    handicap_option TEXT,
    key_factors JSONB,
    result VARCHAR(20) DEFAULT 'pending' CHECK (result IN ('pending', 'won', 'lost', 'void')),
    actual_winner VARCHAR(150),
    actual_score VARCHAR(100),
    match_stats JSONB,
    analysis_done BOOLEAN DEFAULT FALSE,
    loss_analysis TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- Cijene POJEDINAČNIH kladionica (2026-08-15 10:12, korisnikova ideja).
-- Zašto svaka kuća, a ne samo medijan: medijan skriva TKO odstupa, a to je vjerojatno
-- informativnije od toga koliko. Pinnacle koji ode ispod SuperSporta nije isto što i jedna
-- meka kuća koja kasni. Dohvat je ionako plaćen (sve kuće dolaze u istom odgovoru), pa je
-- bilježenje besplatno — a ne može se analizirati ono što se nije zapisalo.
-- Volumen: ~32 meča × ~46 kuća = ~1500 redaka po pokretanju.
--
-- UPOZORENJE ZA ANALIZU: ~46 kuća znači 46 istovremenih testova. Na p<0,05 očekuje se
-- 2-3 lažno "značajne" kuće ČISTO SLUČAJNO. Hipotezu zapisati prije gledanja i tražiti da
-- se drži u obje polovice uzorka.
CREATE TABLE IF NOT EXISTS market_lines (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    captured_at TIMESTAMP WITH TIME ZONE NOT NULL,
    event_id VARCHAR(80) NOT NULL,
    sport_key VARCHAR(80),
    commence_time TIMESTAMP WITH TIME ZONE,
    -- Sati do početka meča. Zamjenjuje oznaku "otvaranje/zatvaranje": isti meč vidimo više
    -- puta (danas kao sutrašnji, sutra kao današnji), pa se pomak cijene mjeri po ovome.
    hours_to_start DECIMAL(8,2),
    player1 VARCHAR(150),
    player2 VARCHAR(150),
    bookmaker VARCHAR(60) NOT NULL,
    odds_p1 DECIMAL(10,4),
    odds_p2 DECIMAL(10,4),
    p1_devig DECIMAL(9,6),          -- poštena vjerojatnost za player1 kod TE kuće
    is_sharp BOOLEAN DEFAULT FALSE, -- Pinnacle / Betfair exchange / Matchbook
    UNIQUE (event_id, bookmaker, captured_at)
);
CREATE INDEX IF NOT EXISTS idx_market_lines_event ON market_lines(event_id);
CREATE INDEX IF NOT EXISTS idx_market_lines_players ON market_lines(player1, player2);
CREATE INDEX IF NOT EXISTS idx_market_lines_captured ON market_lines(captured_at DESC);

-- Širi pool analiziranih mečeva (uključuje i mečeve koji nisu ušli u tiket)
CREATE TABLE IF NOT EXISTS analyzed_matches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_match_id VARCHAR(200) UNIQUE,
    match_date DATE,
    player1 VARCHAR(150),
    player2 VARCHAR(150),
    tournament VARCHAR(250),
    tournament_level VARCHAR(50),
    surface VARCHAR(50),
    round VARCHAR(80),
    predicted_winner VARCHAR(150),
    predicted_confidence DECIMAL(5,2),
    predicted_fair_odds DECIMAL(10,4),
    bookmaker_odds_p1 DECIMAL(10,4),
    bookmaker_odds_p2 DECIMAL(10,4),
    value_detected BOOLEAN,
    actual_winner VARCHAR(150),
    prediction_correct BOOLEAN,
    full_analysis JSONB,
    -- Sirov kontekst (dob, nacionalnost, vrijeme meča, Bo3 decider record, razina prethodnog
    -- turnira) za buduću korelacijsku analizu — korisnikov prijedlog 2026-07-18. Ne utječe na
    -- pick/confidence, samo se bilježi dok se ne skupi dovoljan uzorak. Vidi context_version
    -- unutar JSON-a za oblik sheme.
    context_snapshot JSONB DEFAULT '{}'::jsonb,
    -- API player ID-evi (05.08.2026). Bez njih se post-match statistika (asovi, break lopte,
    -- postotak servisa) ne moze dohvatiti za meceve koji NISU bili na tiketu — a to je veci
    -- dio korpusa. Spremaju se pri generiranju analize, gdje ih ionako vec imamo, pa ne kostaju
    -- nijedan dodatni API poziv. Postojeca instanca treba:
    --   ALTER TABLE analyzed_matches ADD COLUMN IF NOT EXISTS player1_id VARCHAR(30);
    --   ALTER TABLE analyzed_matches ADD COLUMN IF NOT EXISTS player2_id VARCHAR(30);
    player1_id VARCHAR(30),
    player2_id VARCHAR(30),
    -- Post-match statistika (05.08.2026): asovi, dvostruke greske, postotak 1./2. servisa,
    -- break lopte, brzine servisa. Do sada je postojala SAMO u ticket_matches, dakle samo za
    -- pickove koji su dosli na tiket — a to je selektiran uzorak (prosli su prag 63%).
    -- Posljedica: uvjeti prije meca (context_snapshot) i ponasanje u mecu zivjeli su u
    -- razlicitim tablicama i preklapali se samo na tiketnim pickovima, pa se korelacija tipa
    -- "vlaga/tlak -> postotak prvog servisa" nije mogla racunati na punom korpusu.
    -- Mecevi koje smo analizirali ali odbacili najvredniji su za ucenje jer pokrivaju cijeli
    -- raspon, ne samo ono u sto smo bili sigurni.
    --   ALTER TABLE analyzed_matches ADD COLUMN IF NOT EXISTS match_stats JSONB;
    match_stats JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Verzije težina modela
CREATE TABLE IF NOT EXISTS model_weights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version INTEGER NOT NULL,
    weights JSONB NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    update_reason TEXT,
    triggered_by VARCHAR(200),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Dnevni performance log
CREATE TABLE IF NOT EXISTS performance_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    log_date DATE UNIQUE,
    total_tickets INTEGER DEFAULT 0,
    won_tickets INTEGER DEFAULT 0,
    lost_tickets INTEGER DEFAULT 0,
    pending_tickets INTEGER DEFAULT 0,
    total_staked DECIMAL(10,2) DEFAULT 0,
    total_returned DECIMAL(10,2) DEFAULT 0,
    roi_percent DECIMAL(10,4),
    running_balance DECIMAL(10,2),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Scouting profili igrača (korisnikov Excel "ATP_Player_Scouting top150.xlsx", uvoz preko
-- scripts/import_scouting.py). SEKUNDARNI izvor za prompt: kvalitativni stil/matchup kontekst,
-- nikad ne nadjačava mjerene brojke. Low/Insufficient profili se NE ubacuju u prompt
-- (autorova vlastita legenda: "do NOT fill from memory"), a od 04.08.2026 dopušteni utjecaj
-- skalira s pouzdanošću profila: High/Med-High ±3pp, Med ±2pp, Med-Low samo kao sumnja
-- (nikad kao potpora picku — sva tri profila koja su 31.07. opovrgnuta bila su Med-Low).
CREATE TABLE IF NOT EXISTS player_scouting (
    player_name TEXT PRIMARY KEY,          -- normalizirano (lowercase, bez dijakritika)
    display_name TEXT,
    rank INTEGER,
    country VARCHAR(30),
    hand VARCHAR(30),
    style TEXT,
    best_surfaces TEXT,
    strengths TEXT,
    weaknesses TEXT,
    favourable_matchups TEXT,
    tough_matchups TEXT,
    note TEXT,
    confidence VARCHAR(20),
    source_date DATE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Povijest ždrijebova po turniru i sezoni (tko je koga pobijedio u kojoj rundi).
-- Puni je data_fetcher iz API-ja i koristi se kao anti-halucinacijska provjera: model ne
-- smije tvrditi da je igrač "prošlogodišnji finalist" ako to ovdje ne piše.
-- ZAPISANO NAKNADNO 07.08.2026 — tablica je u Supabaseu postojala od ranije (668 redaka),
-- ali je nikad nije bilo u ovoj datoteci, pa bi podizanje baze od nule ostavilo model bez
-- povijesti ždrijebova. Postojeća instanca ne treba ništa.
CREATE TABLE IF NOT EXISTS tournament_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tournament_name TEXT,
    season_id       VARCHAR(30),
    season_year     INTEGER,
    round_name      VARCHAR(40),
    winner_name     TEXT,
    loser_name      TEXT,
    score           VARCHAR(100),
    fetched_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ručno unesene kvote sa screenshotova kladionice (Streamlit upload, Claude vision ekstrakcija)
CREATE TABLE IF NOT EXISTS screenshot_odds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    match_date DATE UNIQUE,
    odds_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert initial model weights
INSERT INTO model_weights (version, weights, is_active, update_reason)
VALUES (
    1,
    '{
        "elo_ranking": 20.0,
        "surface_style": 23.0,
        "serve_return": 18.0,
        "recent_form": 18.0,
        "fatigue_injuries": 12.0,
        "h2h_context": 5.0,
        "odds_movement": 4.0
    }',
    true,
    'Initial default weights - v1'
);

-- Indexes za performanse
CREATE INDEX IF NOT EXISTS idx_tickets_date ON tickets(ticket_date);
CREATE INDEX IF NOT EXISTS idx_ticket_matches_ticket_id ON ticket_matches(ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_matches_match_date ON ticket_matches(match_date);
CREATE INDEX IF NOT EXISTS idx_analyzed_matches_date ON analyzed_matches(match_date);
CREATE INDEX IF NOT EXISTS idx_performance_log_date ON performance_log(log_date);
