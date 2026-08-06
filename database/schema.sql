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
