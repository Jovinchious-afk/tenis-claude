"""
Dohvat podataka iz:
 - Tennis API - ATP WTA ITF by Matchstat (RapidAPI)
   Host: tennis-api-atp-wta-itf.p.rapidapi.com
   Base: /tennis/v2/
 - The Odds API (bookmaker kvote)
 - Web scraping (vijesti, ozljede, ELO sa Tennis Abstract)
"""
import os
import json
import time
import datetime
import requests
from bs4 import BeautifulSoup
from typing import Optional
from dotenv import load_dotenv
from utils.helpers import format_date, safe_float, safe_int

load_dotenv()

RAPID_API_KEY = os.environ.get("RAPID_API_KEY", "")
ODDS_API_KEY  = os.environ.get("ODDS_API_KEY", "")
WEATHER_KEY   = os.environ.get("OPENWEATHER_KEY", "")

API_BASE   = "https://tennis-api-atp-wta-itf.p.rapidapi.com/tennis/v2"
ODDS_BASE  = "https://api.the-odds-api.com/v4"

HEADERS = {
    "x-rapidapi-key":  RAPID_API_KEY,
    "x-rapidapi-host": "tennis-api-atp-wta-itf.p.rapidapi.com",
    "Content-Type":    "application/json",
}

# Round ID → name mapping (ATP standard: 1=R128 ... 7=F)
_ROUND_ID_MAP = {
    1: "R128", 2: "R64", 3: "R32", 4: "R16",
    5: "QF",   6: "SF",  7: "F",   8: "RR",
    9: "Q2",  10: "Q1",
}

# In-process cache: str(tournamentId) → {name, surface, category, city}
_tournament_info_cache: dict = {}

# Cache za tournament records: (player_id, tournament_id) → dict
_tournament_record_cache: dict = {}

# Rate limiter: max ~90 req/min (limit is 100/min)
_last_api_call_time: float = 0.0
_MIN_CALL_INTERVAL: float = 0.67


def _get(path: str, params: dict = None, timeout: int = 15) -> Optional[dict]:
    global _last_api_call_time
    for attempt in range(3):
        elapsed = time.time() - _last_api_call_time
        if elapsed < _MIN_CALL_INTERVAL:
            time.sleep(_MIN_CALL_INTERVAL - elapsed)
        _last_api_call_time = time.time()
        try:
            r = requests.get(f"{API_BASE}{path}", params=params, headers=HEADERS, timeout=timeout)
            if r.status_code == 429:
                wait = 62 if attempt == 0 else 120
                print(f"Rate limit [{path}], čekam {wait}s...")
                time.sleep(wait)
                _last_api_call_time = time.time()
                continue
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            print(f"API greška [{path}]: {e}")
            return None
        except Exception as e:
            print(f"API greška [{path}]: {e}")
            return None
    print(f"API greška [{path}]: previše pokušaja, preskačem")
    return None


def _get_external(url: str, params: dict = None, headers: dict = None, timeout: int = 15) -> Optional[dict]:
    try:
        r = requests.get(url, params=params, headers=headers or {}, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"HTTP greška [{url}]: {e}")
        return None


# ── Tournament info cache ─────────────────────────────────────────────────────

def _get_tournament_info(tournament_id: str) -> dict:
    """
    Fetch tournament details by ID; cache in-process.
    Returns {name, surface, category, city}.
    Endpoint: GET /atp/tournament/info/{tournamentId}
    Response: {"data": {id, name, court: {name}, tier, country: {name}, ...}}
    """
    tid = str(tournament_id)
    if tid in _tournament_info_cache:
        return _tournament_info_cache[tid]
    data = _get(f"/atp/tournament/info/{tid}")
    info: dict = {"name": "", "surface": "", "category": "", "city": ""}
    if data:
        raw = data.get("data", data.get("result", data))
        t = raw[0] if isinstance(raw, list) and raw else (raw if isinstance(raw, dict) else {})
        court = t.get("court", {}) if isinstance(t.get("court"), dict) else {}
        country = t.get("country", {}) if isinstance(t.get("country"), dict) else {}
        info = {
            "name":     t.get("name", ""),
            "surface":  court.get("name", ""),   # "Clay", "Hard", "Grass", "I.hard"
            "category": t.get("tier", ""),        # "Grand Slam", "ATP Masters 1000", etc.
            "city":     country.get("name", ""),
        }
    _tournament_info_cache[tid] = info
    return info


def _round_from_id(round_id) -> str:
    if round_id is None:
        return ""
    return _ROUND_ID_MAP.get(int(round_id), f"R{round_id}")


# ── Fixtures / Mečevi ─────────────────────────────────────────────────────────

def get_matches_for_date(date: datetime.date) -> list:
    """
    Vraća sve mečeve za dati datum.
    Endpoint: GET /atp/fixtures/{YYYY-MM-DD}  (paginiran — hasNextPage)
    Response: {"data": [...], "hasNextPage": bool}
    Filtrira samo muške ATP singles.
    """
    date_str = format_date(date)

    # Collect all fixture entries (paginated, deduplicate by match id)
    all_entries = []
    seen_ids: set = set()
    page = 1
    while page <= 5:
        params = {"pageNo": page} if page > 1 else None
        data = _get(f"/atp/fixtures/{date_str}", params=params)
        if not data:
            break
        entries = data.get("data", [])
        if not isinstance(entries, list) or not entries:
            break
        new_count = 0
        for e in entries:
            eid = str(e.get("id", ""))
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                all_entries.append(e)
                new_count += 1
        if not data.get("hasNextPage", False) or new_count == 0:
            break
        page += 1

    # Batch-fetch tournament info for all unique tournament IDs
    unique_tids = {str(g.get("tournamentId", "")) for g in all_entries if g.get("tournamentId")}
    for tid in unique_tids:
        _get_tournament_info(tid)  # populates cache

    matches = []
    for g in all_entries:
        p1 = g.get("player1") or {}
        p2 = g.get("player2") or {}
        player1_name = p1.get("name", "")
        player2_name = p2.get("name", "")
        if not player1_name or not player2_name:
            continue

        # Isključi doubles (player name sadrži "/" npr. "Smith/Jones")
        if "/" in player1_name or "/" in player2_name:
            continue

        tournament_id = str(g.get("tournamentId", ""))
        tourn_info    = _tournament_info_cache.get(tournament_id, {})
        tourn_name    = tourn_info.get("name", "") or f"Tournament {tournament_id}"
        tier          = tourn_info.get("category", "")

        # Isključi WTA, doubles, Futures
        combined = f"{tourn_name} {tier}".upper()
        if any(kw in combined for kw in ["WTA", "DOUBLES", "WOMEN", "GIRLS", "ITF WOMEN", "FUTURE"]):
            continue

        surface = _normalize_surface(tourn_info.get("surface", ""), tourn_name)

        matches.append({
            "external_id":   str(g.get("id", "")),
            "player1":       player1_name,
            "player2":       player2_name,
            "player1_id":    str(g.get("player1Id", p1.get("id", ""))),
            "player2_id":    str(g.get("player2Id", p2.get("id", ""))),
            "tournament":    tourn_name,
            "tournament_id": tournament_id,
            "surface":       surface,
            "round":         _round_from_id(g.get("roundId")),
            "date":          date_str,
            "time":          str(g.get("timeGame", "") or ""),
            "winner_id":     str(g.get("match_winner") or g.get("winnerId") or ""),
            "status":        ("finished" if (g.get("match_winner") or g.get("winnerId")) and not g.get("live")
                              else "live" if g.get("live") else "scheduled"),
            "score":         "",
            "level":         _get_tournament_level(tourn_name, tier),
            "seed1":         str(g.get("seed1", "") or ""),
            "seed2":         str(g.get("seed2", "") or ""),
        })

    return matches


def get_recent_form(player_id: str, n: int = 10) -> dict:
    """
    Endpoint: GET /atp/player/past-matches/{player_id}
    Zadnjih N mečeva igrača.
    """
    if not player_id:
        return {"wins": 0, "losses": 0, "matches": []}
    data = _get(f"/atp/player/past-matches/{player_id}")
    if not data:
        return {"wins": 0, "losses": 0, "matches": []}

    # Response may use "data" key (same as fixtures) or nested formats
    raw = data.get("data", data.get("result", data))
    games = raw if isinstance(raw, list) else []

    wins, losses, result_matches = 0, 0, []
    pid_str = str(player_id)
    for g in games[:n]:
        p1     = g.get("player1") or {}
        p2     = g.get("player2") or {}
        p1_id  = str(g.get("player1Id", p1.get("id", "")))
        p2_id  = str(g.get("player2Id", p2.get("id", "")))
        winner_id = str(g.get("match_winner", g.get("winnerId", g.get("winner_id", ""))) or "")
        is_p1  = p1_id == pid_str
        won    = (is_p1 and winner_id == p1_id) or (not is_p1 and winner_id == p2_id)
        opp    = p2.get("name", "") if is_p1 else p1.get("name", "")
        if won:
            wins += 1
        else:
            losses += 1
        tid = str(g.get("tournamentId", ""))
        result_matches.append({
            "date":       str(g.get("date", ""))[:10],
            "won":        won,
            "opponent":   opp,
            "tournament_id": tid,
            "surface":    "",  # surface fetched separately via tournament calendar
        })
    return {"wins": wins, "losses": losses, "matches": result_matches}


def get_h2h(player1_id: str, player2_id: str) -> dict:
    """
    Endpoint: GET /atp/fixtures/h2h/{player1_id}/{player2_id}
    """
    if not player1_id or not player2_id:
        return {"total": 0, "p1_wins": 0, "p2_wins": 0, "clay": {}, "hard": {}, "grass": {}}
    data = _get(f"/atp/fixtures/h2h/{player1_id}/{player2_id}")
    if not data:
        return {"total": 0, "p1_wins": 0, "p2_wins": 0, "clay": {}, "hard": {}, "grass": {}}

    raw = data.get("data", data.get("result", data))
    games = raw if isinstance(raw, list) else []
    total = len(games)
    p1_wins, p2_wins = 0, 0
    by_surface = {"clay": [0, 0], "hard": [0, 0], "grass": [0, 0]}
    for g in games:
        winner_id = str(g.get("match_winner", g.get("winnerId", g.get("winner_id", ""))) or "")
        tid = str(g.get("tournamentId", ""))
        tourn_info  = _get_tournament_info(tid) if tid else {}
        surface_raw = tourn_info.get("surface", "")
        surface = _normalize_surface(surface_raw, tourn_info.get("name", "")).lower()
        if winner_id == str(player1_id):
            p1_wins += 1
            if surface in by_surface:
                by_surface[surface][0] += 1
        elif winner_id == str(player2_id):
            p2_wins += 1
            if surface in by_surface:
                by_surface[surface][1] += 1

    return {
        "total":   total,
        "p1_wins": p1_wins,
        "p2_wins": p2_wins,
        "clay":  {"p1_wins": by_surface["clay"][0],  "p2_wins": by_surface["clay"][1]},
        "hard":  {"p1_wins": by_surface["hard"][0],  "p2_wins": by_surface["hard"][1]},
        "grass": {"p1_wins": by_surface["grass"][0], "p2_wins": by_surface["grass"][1]},
    }


def get_player_info(player_id: str) -> dict:
    """
    Endpoint: GET /atp/player/profile/{player_id}
    """
    if not player_id:
        return {}
    data = _get(f"/atp/player/profile/{player_id}")
    if not data:
        return {}
    # Response: {"data": {...}} or {"data": [...]}
    raw = data.get("data", data.get("result", data))
    p = raw[0] if isinstance(raw, list) and raw else (raw if isinstance(raw, dict) else {})

    ranking_data = p.get("rankings", {}) if isinstance(p.get("rankings"), dict) else {}
    return {
        "id":             player_id,
        "name":           p.get("name", "") or p.get("player_name", "") or p.get("fullName", ""),
        "nationality":    (p.get("country", {}).get("acronym", "") if isinstance(p.get("country"), dict)
                          else p.get("nationality", "") or p.get("countryAcr", "")),
        "ranking":        safe_int(ranking_data.get("singles_rank") or ranking_data.get("singlesRank")
                                   or p.get("ranking") or p.get("atp_rank") or p.get("currentRank")),
        "ranking_points": safe_int(ranking_data.get("singles_points") or ranking_data.get("singlesPoints")
                                   or p.get("ranking_points") or p.get("rankingPoints")),
        "age":            safe_int(p.get("age")),
        "height":         str(p.get("height", "") or p.get("heightCm", "")),
        "hand":           p.get("hand", "") or p.get("plays", "") or p.get("playingHand", ""),
    }


def get_player_stats(player_id: str) -> dict:
    """
    Endpoint: GET /atp/player/match-stats/{player_id}
    """
    if not player_id:
        return {}
    data = _get(f"/atp/player/match-stats/{player_id}")
    if not data:
        return {}
    # Response: {"data": {"serviceStats":{...}, "rtnStats":{...}, "breakPointsServeStats":{...}, "breakPointsRtnStats":{...}}}
    raw = data.get("data", data.get("result", data))
    s = raw[0] if isinstance(raw, list) and raw else (raw if isinstance(raw, dict) else {})

    svc  = s.get("serviceStats", {}) or {}
    rtn  = s.get("rtnStats", {})     or {}
    bps  = s.get("breakPointsServeStats", {}) or {}
    bpr  = s.get("breakPointsRtnStats", {})   or {}

    def _pct(num, den):
        n, d = safe_float(num), safe_float(den)
        return round(n / d * 100, 1) if d and d > 0 else None

    fs_in   = safe_float(svc.get("firstServeGm"))
    fs_of   = safe_float(svc.get("firstServeOfGm"))
    w1s     = safe_float(svc.get("winningOnFirstServeGm"))
    ss_of   = safe_float(svc.get("winningOnSecondServeOfGm"))
    w2s     = safe_float(svc.get("winningOnSecondServeGm"))
    ace_tot = safe_float(svc.get("acesGm"))
    df_tot  = safe_float(svc.get("doubleFaultsGm"))

    # Return: rtnStats tracks opponent's serve; Sinner return_won = 1 - opp_1st_won%
    opp_fs_in = safe_float(rtn.get("firstServeGm"))
    opp_w1s   = safe_float(rtn.get("winningOnFirstServeGm"))
    opp_ss_of = safe_float(rtn.get("winningOnSecondServeOfGm"))
    opp_w2s   = safe_float(rtn.get("winningOnSecondServeGm"))

    ret_won_1st  = _pct(opp_fs_in - (opp_w1s or 0), opp_fs_in) if opp_fs_in else None
    ret_won_2nd  = _pct(opp_ss_of - (opp_w2s or 0), opp_ss_of) if opp_ss_of else None
    ret_pct = round((((ret_won_1st or 0) + (ret_won_2nd or 0)) / 2), 1) if ret_won_1st else None

    bp_faced  = safe_float(bps.get("breakPointOf"))
    bp_saved  = safe_float(bps.get("breakPointSave"))
    bp_opp    = safe_float(bpr.get("breakPointOf"))
    bp_conv   = safe_float(bpr.get("breakPoint"))

    # Estimate games played from 1st serve totals
    games = safe_float(fs_of) or 1

    return {
        "aces_per_game":           round(ace_tot / games * 100, 2) if ace_tot and games else None,
        "double_faults_per_game":  round(df_tot  / games * 100, 2) if df_tot  and games else None,
        "first_serve_pct":         _pct(fs_in, fs_of),
        "first_serve_points_won":  _pct(w1s, fs_in),
        "second_serve_points_won": _pct(w2s, ss_of),
        "break_points_saved":      _pct(bp_saved, bp_faced),
        "break_points_converted":  _pct(bp_conv, bp_opp),
        "return_points_won":       ret_pct,
    }


def get_atp_rankings(limit: int = 200) -> dict:
    """
    Endpoint: GET /atp/ranking/singles?pageSize={limit}
    """
    pages_needed = (limit + 99) // 100
    rankings = {}
    for page in range(1, pages_needed + 1):
        data = _get("/atp/ranking/singles", params={"pageSize": 100, "pageNo": page})
        if not data:
            break
        raw = data.get("data", data.get("result", data))
        entries = raw if isinstance(raw, list) else []
        if not entries:
            break
        for entry in entries:
            player = entry.get("player", {}) if isinstance(entry.get("player"), dict) else {}
            name = (player.get("name", "") or player.get("player_name", "")
                    or entry.get("player_name", "") or entry.get("name", ""))
            rank = safe_int(entry.get("ranking") or entry.get("rank")
                            or entry.get("position") or entry.get("rankNo"))
            if name:
                rankings[name] = rank
        if len(rankings) >= limit:
            break
    return dict(list(rankings.items())[:limit])


# ── The Odds API ──────────────────────────────────────────────────────────────

def get_tennis_odds(match_names: list) -> dict:
    """Dohvat ATP kvota s The Odds API."""
    if not ODDS_API_KEY:
        return {}
    sports_data = _get_external(f"{ODDS_BASE}/sports", params={"apiKey": ODDS_API_KEY, "all": "true"})
    if not sports_data or not isinstance(sports_data, list):
        return {}
    tennis_sports = [s["key"] for s in sports_data
                     if isinstance(s, dict) and "tennis" in s.get("key", "") and s.get("active", False)]
    all_odds = {}
    for sport_key in tennis_sports[:10]:
        data = _get_external(
            f"{ODDS_BASE}/sports/{sport_key}/odds",
            params={"apiKey": ODDS_API_KEY, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"}
        )
        if not data or not isinstance(data, list):
            continue
        for event in data:
            home, away = event.get("home_team", ""), event.get("away_team", "")
            best_h, best_a = 1.01, 1.01
            for bm in event.get("bookmakers", []):
                for market in bm.get("markets", []):
                    if market.get("key") != "h2h":
                        continue
                    for outcome in market.get("outcomes", []):
                        if outcome["name"] == home:
                            best_h = max(best_h, safe_float(outcome.get("price", 1.01)))
                        elif outcome["name"] == away:
                            best_a = max(best_a, safe_float(outcome.get("price", 1.01)))
            all_odds[f"{home}|{away}"] = {"p1_odds": best_h, "p2_odds": best_a, "p1": home, "p2": away}
    return all_odds


def find_match_odds(player1: str, player2: str, all_odds: dict) -> dict:
    for key, val in all_odds.items():
        if _name_match(player1, val["p1"]) and _name_match(player2, val["p2"]):
            return {"p1_odds": val["p1_odds"], "p2_odds": val["p2_odds"]}
        if _name_match(player1, val["p2"]) and _name_match(player2, val["p1"]):
            return {"p1_odds": val["p2_odds"], "p2_odds": val["p1_odds"]}
    return {}


def _name_match(a: str, b: str) -> bool:
    a, b = a.lower().strip(), b.lower().strip()
    if a == b:
        return True
    ap, bp = a.split(), b.split()
    return bool(ap and bp and ap[-1] == bp[-1])


# ── Tennis Abstract ELO ───────────────────────────────────────────────────────

def get_tennis_abstract_elo() -> dict:
    url = "https://www.tennisabstract.com/reports/atp_elo_ratings.html"
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        table = soup.find("table", {"id": "reportable"}) or soup.find("table")
        if not table:
            return {}

        # Pronađi indekse kolumni iz zaglavlja
        header_row = table.find("tr")
        col_indices = {"name": 1, "elo": 2, "hard": 3, "clay": 4, "grass": 5}
        if header_row:
            headers = [th.get_text(strip=True).lower() for th in header_row.find_all(["th", "td"])]
            for i, h in enumerate(headers):
                if "player" in h or "name" in h:
                    col_indices["name"] = i
                elif h in ("elo", "overall", "total") or (h == "elo" ):
                    col_indices["elo"] = i
                elif "hard" in h:
                    col_indices["hard"] = i
                elif "clay" in h:
                    col_indices["clay"] = i
                elif "grass" in h:
                    col_indices["grass"] = i

        elo_data = {}
        for row in table.find_all("tr")[1:300]:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue
            name = cols[col_indices["name"]].get_text(strip=True) if len(cols) > col_indices["name"] else ""
            if not name:
                continue

            def _elo_val(idx):
                if len(cols) <= idx:
                    return None
                v = safe_float(cols[idx].get_text(strip=True))
                return v if v and v > 500 else None  # ELO mora biti > 500

            elo_overall = _elo_val(col_indices["elo"]) or 1500
            elo_hard    = _elo_val(col_indices["hard"]) or elo_overall
            elo_clay    = _elo_val(col_indices["clay"]) or elo_overall
            elo_grass   = _elo_val(col_indices["grass"]) or elo_overall

            elo_data[name.lower()] = {
                "elo_overall": elo_overall, "elo_hard": elo_hard,
                "elo_clay": elo_clay, "elo_grass": elo_grass,
            }
        return elo_data
    except Exception as e:
        print(f"ELO scraping greška: {e}")
        return {}


def find_player_elo(player_name: str, elo_data: dict) -> dict:
    name_lower = player_name.lower()
    if name_lower in elo_data:
        return elo_data[name_lower]
    surname = name_lower.split()[-1] if name_lower else ""
    for key in elo_data:
        if surname and surname in key:
            return elo_data[key]
    return {"elo_overall": 1500, "elo_hard": 1500, "elo_clay": 1500, "elo_grass": 1500}


# ── ATP News ──────────────────────────────────────────────────────────────────

def get_atp_injury_news() -> str:
    sources = ["https://www.atpworldtour.com/en/news", "https://www.tennisworld.net/"]
    combined = []
    for url in sources:
        try:
            r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(r.text, "lxml")
            for tag in soup.find_all(["h2", "h3", "h4", "a"], limit=50):
                text = tag.get_text(strip=True)
                if any(kw in text.lower() for kw in ["withdraw", "injur", "retire", "out of", "scratch"]):
                    combined.append(text[:150])
        except Exception:
            pass
    return "; ".join(combined[:15]) if combined else "Nema dostupnih vijesti."


def get_match_stats(tournament_id: str, player1_id: str, player2_id: str) -> dict:
    """
    Endpoint: GET /atp/h2h/match-stats/{tournamentId}/{player1Id}/{player2Id}
    Vraća detaljnu statistiku završenog meča (servis, return, break, winners...).
    """
    if not tournament_id or not player1_id or not player2_id:
        return {}
    data = _get(f"/atp/h2h/match-stats/{tournament_id}/{player1_id}/{player2_id}")
    if not data:
        return {}
    return data.get("data", data) or {}


def get_player_surface_summary(player_id: str) -> dict:
    """
    Endpoint: GET /atp/player/surface-summary/{player_id}
    Vraća win% po podlozi, agregirano za zadnje 3 kalendarske godine.
    Format: {"clay": {"wins": 27, "losses": 7, "matches": 34, "win_pct": 79.4}, ...}
    """
    if not player_id:
        return {}
    data = _get(f"/atp/player/surface-summary/{player_id}")
    if not data:
        return {}

    import datetime as _dt
    current_year = _dt.date.today().year
    recent_years = {current_year, current_year - 1, current_year - 2}

    totals: dict = {}
    for year_data in data.get("data", []):
        if year_data.get("year") not in recent_years:
            continue
        for s in year_data.get("surfaces", []):
            court = s.get("court", "")
            wins = s.get("courtWins", 0) or 0
            losses = s.get("courtLosses", 0) or 0
            if court == "Clay":
                key = "clay"
            elif court in ("Hard", "I.hard"):
                key = "hard"
            elif court == "Grass":
                key = "grass"
            else:
                continue
            if key not in totals:
                totals[key] = [0, 0]
            totals[key][0] += wins
            totals[key][1] += losses

    result = {}
    for surface, (wins, losses) in totals.items():
        total = wins + losses
        result[surface] = {
            "wins": wins,
            "losses": losses,
            "matches": total,
            "win_pct": round(wins / total * 100, 1) if total > 0 else None,
        }
    return result


def get_player_tournament_record(player_id: str, tournament_id: str) -> dict:
    """
    Endpoint: GET /atp/player/tournament-record/{playerId}/{tournamentId}
    Vraća povijesni rekord igrača na konkretnom turniru (sve godine).
    """
    if not player_id or not tournament_id:
        return {}
    cache_key = (str(player_id), str(tournament_id))
    if cache_key in _tournament_record_cache:
        return _tournament_record_cache[cache_key]

    data = _get(f"/atp/player/tournament-record/{player_id}/{tournament_id}")
    if not data:
        _tournament_record_cache[cache_key] = {}
        return {}

    records = data.get("data", [])
    if not records:
        _tournament_record_cache[cache_key] = {}
        return {}

    total_wins = sum(r.get("wins", 0) or 0 for r in records)
    total_losses = sum(r.get("losses", 0) or 0 for r in records)

    best = max(records, key=lambda r: r.get("bestRoundId", 0))
    best_round = best.get("bestRound", "N/A")
    best_year = best.get("year", "")

    recent = sorted(records, key=lambda r: r.get("year", 0), reverse=True)[:3]
    recent_str = " / ".join(
        f"{r['year']}: {r.get('bestRound', '?')} ({r.get('wins', 0)}W/{r.get('losses', 0)}L)"
        for r in recent
    )

    result = {
        "total_wins": total_wins,
        "total_losses": total_losses,
        "appearances": len(records),
        "best_round": best_round,
        "best_year": best_year,
        "recent": recent_str,
    }
    _tournament_record_cache[cache_key] = result
    return result


def get_weather_for_tournament(city: str) -> dict:
    if not WEATHER_KEY or not city:
        return {}
    try:
        data = _get_external(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "appid": WEATHER_KEY, "units": "metric"}
        )
        if data:
            return {
                "temp_c":    data.get("main", {}).get("temp"),
                "humidity":  data.get("main", {}).get("humidity"),
                "wind_kmh":  round(safe_float(data.get("wind", {}).get("speed", 0)) * 3.6, 1),
                "condition": data.get("weather", [{}])[0].get("main", ""),
            }
    except Exception:
        pass
    return {}


# ── Parse helpers ─────────────────────────────────────────────────────────────

def _extract_player_name(g: dict, side: str) -> str:
    sides = {"home": ["home", "player1", "first_player", "event_first_player"],
             "away": ["away", "player2", "second_player", "event_second_player"]}
    for key in sides.get(side, []):
        val = g.get(key)
        if isinstance(val, dict):
            return val.get("name", "") or val.get("player_name", "")
        if isinstance(val, str) and val:
            return val
    return ""


def _extract_player_id(g: dict, side: str) -> str:
    sides = {"home": ["home", "player1", "first_player"],
             "away": ["away", "player2", "second_player"]}
    for key in sides.get(side, []):
        val = g.get(key)
        if isinstance(val, dict):
            return str(val.get("id", "") or val.get("player_id", ""))
        # Try explicit id fields
    id_key = "home_id" if side == "home" else "away_id"
    return str(g.get(id_key, "") or g.get(f"player{1 if side=='home' else 2}_id", ""))


def _extract_round(g: dict) -> str:
    r = g.get("round", {})
    if isinstance(r, dict):
        return r.get("name", "") or r.get("slug", "")
    return str(r or "")


def _extract_score(g: dict) -> Optional[str]:
    score = g.get("score", {}) or g.get("result", {})
    if isinstance(score, dict):
        home_s = score.get("home", "") or score.get("current", {}).get("home", "")
        away_s = score.get("away", "") or score.get("current", {}).get("away", "")
        if home_s or away_s:
            return f"{home_s}-{away_s}"
    if isinstance(score, str) and score:
        return score
    return None


def _normalize_surface(surface: str, tournament_name: str) -> str:
    # API returns surface as: "Clay", "Hard", "Grass", "I.hard"
    # Prioritise the surface value from the API; use name only as fallback
    s  = surface.lower().strip()
    tn = tournament_name.lower()
    if s == "clay" or (not s and ("clay" in tn or "roland" in tn or "french" in tn)):
        return "Clay"
    if s == "grass" or (not s and ("grass" in tn or "wimbledon" in tn or "queens" in tn)):
        return "Grass"
    if s == "i.hard" or "indoor" in s:
        return "Indoor Hard"
    if "hard" in s:
        return "Hard"
    # fallback to tournament name only if surface field is empty
    if "clay" in tn or "roland" in tn or "french" in tn:
        return "Clay"
    if "grass" in tn or "wimbledon" in tn:
        return "Grass"
    return "Hard"


def _get_tournament_level(name: str, category: str = "") -> str:
    # category = tier from API: "Grand Slam", "ATP Masters 1000", "ATP 500", "ATP 250",
    #            "Finals", "Challenger 125/100/75/50", "Future"
    cat = category.lower()
    n   = name.lower()
    if "grand slam" in cat or any(x in n for x in ["roland garros", "french open", "wimbledon",
                                                     "us open", "australian open"]):
        return "Grand Slam"
    if "masters 1000" in cat or "1000" in cat:
        return "ATP Masters 1000"
    if "500" in cat or "atp 500" in cat:
        return "ATP 500"
    if "challenger" in cat:
        return "ATP Challenger"
    if "250" in cat or "atp 250" in cat:
        return "ATP 250"
    return "ATP 250"
