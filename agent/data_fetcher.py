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
import unicodedata
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

# Prolazne server-side greške na koje ima smisla ponoviti pokušaj (privremeni blip):
#  405 = "Method Not Allowed" — u praksi kratkotrajni RapidAPI routing blip; endpoint
#        je ispravan i proradi za par sekundi (17.07.2026 jedan takav 405 oborio je
#        cijeli daily run jer je pao na dohvatu mečeva — prvom i kritičnom pozivu).
#  5xx = server preopterećen/pukao/timeout — isto privremeno.
# Trajne greške (401 kriv ključ, 403 kvota, 404 ne postoji) NAMJERNO se ne ponavljaju.
_RETRYABLE_STATUS = {405, 500, 502, 503, 504}
_TRANSIENT_RETRY_WAIT = 3      # sekundi pauze između pokušaja na prolaznu grešku
_MAX_ATTEMPTS = 3


def _get(path: str, params: dict = None, timeout: int = 15) -> Optional[dict]:
    global _last_api_call_time
    for attempt in range(_MAX_ATTEMPTS):
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
            # Prolazna server-side greška (405/5xx): pauza pa ponovni pokušaj.
            if r.status_code in _RETRYABLE_STATUS and attempt < _MAX_ATTEMPTS - 1:
                print(f"API prolazna greška {r.status_code} [{path}] — pokušaj "
                      f"{attempt + 1}/{_MAX_ATTEMPTS}, čekam {_TRANSIENT_RETRY_WAIT}s...")
                time.sleep(_TRANSIENT_RETRY_WAIT)
                continue
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            # Trajne greške (401/403/404 ili zadnji pokušaj na 405/5xx) — ne ponavljamo.
            print(f"API greška [{path}]: {e}")
            return None
        except requests.exceptions.RequestException as e:
            # Mrežni blip / timeout (ConnectionError, Timeout...) — prolazno, pokušaj ponovno.
            if attempt < _MAX_ATTEMPTS - 1:
                print(f"API mrežna greška [{path}]: {e} — pokušaj "
                      f"{attempt + 1}/{_MAX_ATTEMPTS}, čekam {_TRANSIENT_RETRY_WAIT}s...")
                time.sleep(_TRANSIENT_RETRY_WAIT)
                continue
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


_player_id_by_name_cache: dict = {}


def get_player_ids_by_name(limit: int = 500) -> dict:
    """Mapa normalizirano_ime → player_id iz ATP ranking liste (top {limit}).

    Zašto (A1, 26.07.2026): evening update gradi ID-eve iz fixtures feeda zadnjih 8 dana.
    Kad turnir NESTANE iz feeda (Generali Open Kitzbühel, 25.07.2026), igrači nemaju ID pa
    se rezultat nikad ne razriješi — Bublik-Halys je tako ostao neriješen dok su Estoril
    mečevi istog dana prošli. Ranking lista je neovisan izvor koji pokriva sve main-tour
    igrače na koje ikad tipujemo. Cache: jedan dohvat po procesu."""
    if _player_id_by_name_cache:
        return _player_id_by_name_cache
    pages = (limit + 99) // 100
    for page in range(1, pages + 1):
        data = _get("/atp/ranking/singles", params={"pageSize": 100, "pageNo": page})
        entries = (data or {}).get("data") or []
        if not entries:
            break
        for e in entries:
            p = e.get("player", {}) if isinstance(e.get("player"), dict) else {}
            name, pid = p.get("name", ""), p.get("id")
            if name and pid:
                _player_id_by_name_cache[_norm_key(name)] = str(pid)
    return _player_id_by_name_cache


def _norm_key(s: str) -> str:
    """Normalizirani ključ imena (bez dijakritika, lowercase, single-space)."""
    return " ".join(_strip_diacritics(s or "").lower().strip().split())


def find_player_id(name: str) -> str:
    """Player ID po imenu iz ranking mape — egzaktno pa fuzzy (_name_match). '' ako nema."""
    if not name:
        return ""
    ids = get_player_ids_by_name()
    key = _norm_key(name)
    if key in ids:
        return ids[key]
    for k, pid in ids.items():
        if _name_match(name, k):
            return pid
    return ""


def get_tournament_tier(tournament_id: str) -> str:
    """Public wrapper oko _get_tournament_info — vraća samo tier ("ATP 250", "Grand Slam"...),
    cache-irano. Koristi se za bilježenje razine igračevog PRETHODNOG turnira (context_snapshot,
    korisnikov prijedlog 2026-07-18 točka 7 — umor/motivacija nakon velikog turnira)."""
    if not tournament_id:
        return ""
    return _get_tournament_info(tournament_id).get("category", "")


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
    while page <= 25:
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
            "round_id":      int(g.get("roundId") or 0),
            "date":          date_str,
            "time":          str(g.get("timeGame", "") or ""),
            # Puni UTC timestamp početka meča. `timeGame` je UVIJEK null (provjereno
            # 31.07.2026), pa je "time" gore prazan otkad postoji — pravi izvor sata je
            # ovo polje, koje local_match_time pretvara u lokalno vrijeme turnira.
            "start_utc":     str(g.get("date", "") or ""),
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

        # Extract sets played — use direct field or count from score string
        sets_played = safe_int(g.get("sets") or g.get("totalSets") or g.get("setsPlayed"))
        if not sets_played:
            score_str = str(g.get("score") or g.get("result") or g.get("matchScore") or "")
            if score_str:
                # Count sets from score like "6-4 7-5" or "6-4 4-6 7-5"
                sets_played = len([s for s in score_str.split() if "-" in s and len(s) <= 5])
        if not sets_played:
            sets_played = 0

        result_matches.append({
            "date":       str(g.get("date", ""))[:10],
            "won":        won,
            "finished":   bool(winner_id),   # False = live/neodigran (nema pobjednika)
            "opponent":   opp,
            "tournament_id": tid,
            "surface":    "",
            "sets_played": sets_played,
            "score":      str(g.get("score") or g.get("result") or ""),
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


def get_h2h_stats(player1_id: str, player2_id: str) -> dict:
    """
    Endpoint: GET /atp/h2h/stats/{player1_id}/{player2_id}
    Vraća bogate H2H statistike: tiebreak %, deciding set %, BO3/BO5 record.
    Format: {"p1": {tb_won, tb_total, tb_pct, ds_won, ds_total, ds_pct, bo3_won, ...}, "p2": {...}}
    """
    if not player1_id or not player2_id:
        return {}
    data = _get(f"/atp/h2h/stats/{player1_id}/{player2_id}")
    if not data:
        return {}
    raw = data.get("data", {})
    if not raw or raw.get("error"):
        return {}
    p1s = raw.get("player1Stats", {}) or {}
    p2s = raw.get("player2Stats", {}) or {}
    if not p1s and not p2s:
        return {}

    def _s(d, k):
        v = d.get(k)
        return v if v is not None else 0

    return {
        "p1": {
            "tb_won":    _s(p1s, "tiebreakWon"),
            "tb_total":  _s(p1s, "tiebreakCount"),
            "tb_pct":    _s(p1s, "totalTBWinPercentage"),
            "ds_won":    _s(p1s, "decidingSetWin"),
            "ds_total":  _s(p1s, "decidingSetCount"),
            "ds_pct":    _s(p1s, "decidingSetWinPercentage"),
            "bo3_won":   _s(p1s, "bestOfThreeWon"),
            "bo3_total": _s(p1s, "bestOfThreeCount"),
            "bo5_won":   _s(p1s, "bestOfFiveWon"),
            "bo5_total": _s(p1s, "bestOfFiveCount"),
        },
        "p2": {
            "tb_won":    _s(p2s, "tiebreakWon"),
            "tb_total":  _s(p2s, "tiebreakCount"),
            "tb_pct":    _s(p2s, "totalTBWinPercentage"),
            "ds_won":    _s(p2s, "decidingSetWin"),
            "ds_total":  _s(p2s, "decidingSetCount"),
            "ds_pct":    _s(p2s, "decidingSetWinPercentage"),
            "bo3_won":   _s(p2s, "bestOfThreeWon"),
            "bo3_total": _s(p2s, "bestOfThreeCount"),
            "bo5_won":   _s(p2s, "bestOfFiveWon"),
            "bo5_total": _s(p2s, "bestOfFiveCount"),
        },
    }


def _get_age(p: dict) -> int:
    """Extract age from API response. Tries direct age field first,
    then calculates from dateOfBirth if age is missing."""
    age = safe_int(p.get("age") or p.get("playerAge") or p.get("currentAge"))
    if age and 14 <= age <= 45:
        return age
    # Try calculating from date of birth
    dob_raw = (p.get("dateOfBirth") or p.get("dob") or
               p.get("birthDate") or p.get("born") or "")
    if dob_raw:
        try:
            import datetime as _dt
            dob_str = str(dob_raw)[:10]  # take YYYY-MM-DD part
            dob = _dt.date.fromisoformat(dob_str)
            today = _dt.date.today()
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        except Exception:
            pass
    return None


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
        "age":            _get_age(p),
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

    # Total serve points = first serve attempts (fs_of) = all service points played
    total_serve_pts = safe_float(fs_of) or 1
    total_serve_won = (safe_float(w1s) or 0) + (safe_float(w2s) or 0)
    serve_pts_won_pct = round(total_serve_won / total_serve_pts * 100, 1) if total_serve_pts > 1 else None

    # Hold% proxy: derived from service points won % (high correlation)
    # True hold% requires service games won data which API doesn't expose directly
    # Proxy formula: calibrated from ATP tour data (serve pts won 65%→~90% hold)
    hold_pct = None
    if serve_pts_won_pct:
        # Linear approximation: 60%=75hold, 65%=85hold, 70%=93hold, 75%=97hold
        hold_pct = round(min(99, max(50, (serve_pts_won_pct - 50) * 1.9 + 55)), 1)

    # Break% proxy: return points won is best available signal
    # True break% = return games won / return games played (not in API)
    break_pct = ret_pct  # return points won % is the cleanest proxy

    games = total_serve_pts

    return {
        "aces_per_game":           round(ace_tot / games * 100, 2) if ace_tot and games else None,
        "double_faults_per_game":  round(df_tot  / games * 100, 2) if df_tot  and games else None,
        "first_serve_pct":         _pct(fs_in, fs_of),
        "first_serve_points_won":  _pct(w1s, fs_in),
        "second_serve_points_won": _pct(w2s, ss_of),
        "serve_points_won":        serve_pts_won_pct,
        "hold_pct":                hold_pct,
        "break_points_saved":      _pct(bp_saved, bp_faced),
        "break_points_converted":  _pct(bp_conv, bp_opp),
        "return_points_won":       ret_pct,
        "break_pct":               break_pct,
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


def find_match_odds(player1: str, player2: str, all_odds: dict, screenshot_odds: dict = None) -> dict:
    """Screenshot kvote imaju strogi prioritet — provjeravaju se prve.
    Tek ako tamo nema podudaranja, traži se u all_odds (The Odds API)."""
    def _search(odds: dict) -> dict:
        for val in odds.values():
            if _name_match(player1, val["p1"]) and _name_match(player2, val["p2"]):
                return {"p1_odds": val["p1_odds"], "p2_odds": val["p2_odds"]}
            if _name_match(player1, val["p2"]) and _name_match(player2, val["p1"]):
                return {"p1_odds": val["p2_odds"], "p2_odds": val["p1_odds"]}
        return {}

    if screenshot_odds:
        result = _search(screenshot_odds)
        if result:
            return result
    return _search(all_odds)


# Slova koja Unicode NFKD NE rastavlja na osnovu + znak, pa bi ispala krivo ili nestala.
# đ/Đ su presudni: NFKD ih ostavlja kao "đ", a naivno skidanje daje "d" — dok API i
# kladionice pišu "dj" (Medjedovic, Djere). Bez ovoga se par "Međedović vs ..." nikad ne
# poklopi sa screenshotom (dokumentirano 01.08.2026: Cerundolo vs Međedović ostao nespojen).
_SPECIAL_LETTERS = {
    "đ": "dj", "Đ": "Dj", "ð": "d", "Ð": "D",
    "ø": "o", "Ø": "O", "ß": "ss", "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe",
    "ł": "l", "Ł": "L", "þ": "th", "Þ": "Th",
}


def _strip_diacritics(s: str) -> str:
    """Skida dijakritiku; slova koja NFKD ne rastavlja preslikavaju se eksplicitno."""
    for src, dst in _SPECIAL_LETTERS.items():
        if src in s:
            s = s.replace(src, dst)
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _tokens_covered(short_toks: list, long_toks: list) -> bool:
    """Svaki token kraće liste ima JEDINSTVEN kompatibilan par u duljoj listi.
    Kompatibilno = jednako ILI je jedan token inicijal (prefiks) drugog ("m" ~ "manuel").
    Hvata skraćena imena kladionice: podskup ("Merida Daniel" ⊂ "Daniel Merida Aguilar")
    i skraćene komponente ("Cerundolo Juan M." = "Juan Manuel Cerundolo")."""
    remaining = list(long_toks)
    for t in short_toks:
        hit = None
        for u in remaining:
            if t == u or (len(t) == 1 and u.startswith(t)) or (len(u) == 1 and t.startswith(u)):
                hit = u
                break
        if hit is None:
            return False
        remaining.remove(hit)
    return True


def _name_match(a: str, b: str) -> bool:
    """Usporedba imena otporna na dijakritike, različit redoslijed i spojnice.
    RapidAPI zna skratiti složena prezimena: "Diego Dedura" umjesto "Diego Dedura-Palomero" —
    normalizacija spojnica na razmake omogućava da word-set provjera to uhvati."""
    a = _strip_diacritics(a.lower().strip()).replace("-", " ")
    b = _strip_diacritics(b.lower().strip()).replace("-", " ")
    if a == b:
        return True
    # Ukloni točke s inicijala ("m." → "m") pa izbaci prazne tokene
    aw = [t for t in (w.rstrip(".") for w in a.split()) if t]
    bw = [t for t in (w.rstrip(".") for w in b.split()) if t]
    if not aw or not bw:
        return False
    # Isti redoslijed (oba "Ime Prezime" ili oba "Prezime Ime") — zadnja riječ se poklapa
    if aw[-1] == bw[-1]:
        return True
    # Obrnut redoslijed — jedan je "Ime Prezime", drugi "Prezime Ime"
    if aw[-1] == bw[0] and aw[0] == bw[-1]:
        return True
    # Višerječna prezimena u bilo kojem redoslijedu — sve riječi se podudaraju kao skup
    if set(aw) == set(bw):
        return True
    # Pokrivenost s inicijalima — svaki token kraćeg imena ima par u dužem (jednak ili
    # inicijal-prefiks). Hvata podskup (Merida, 17.07.) I skraćene komponente kladionice
    # (API "Juan Manuel Cerundolo" vs screenshot "Cerundolo Juan M.", 18.07.). Prag >=2
    # poravnate riječi sprječava lažno poklapanje na samo zajedničko ime/prezime.
    sa, sb = (aw, bw) if len(aw) <= len(bw) else (bw, aw)
    if len(sa) >= 2 and _tokens_covered(sa, sb):
        return True
    return False


# ── Screenshot Odds (Claude vision ekstrakcija) ───────────────────────────────

_ODDS_EXTRACTION_PROMPT = """Ovo je screenshot kvota kladionice za teniske mečeve (npr. SuperSport).
Izvuci SVAKI par igrača i njihove decimalne kvote (1X2 / pobjednik meča, ne setovi/gemovi).

Vrati ISKLJUČIVO JSON listu, bez ikakvog drugog teksta, u ovom formatu:
[{"player1": "Prezime Ime", "odds1": 1.85, "player2": "Prezime Ime", "odds2": 1.95}, ...]

Pravila:
- Koristi imena igrača točno onako kako su napisana na slici (ne skraćuj, ne prevodi).
- "odds1"/"odds2" su decimalne kvote za pobjedu tog igrača u meču (ne setovi, ne handikep).
- Ako kvota nije čitljiva ili nedostaje, preskoči taj par.
- Ne uključuj kvalifikacijske mečeve ako su posebno označeni (npr. "Kvalifikacije", "Quali", "Q1", "Q2")."""


def extract_odds_from_screenshot(image_bytes: bytes, media_type: str = "image/png") -> dict:
    """
    Šalje screenshot kvota Claude vision API-ju i parsira odgovor u format
    identičan onome koji vraća get_tennis_odds(): {"player1|player2": {p1_odds, p2_odds, p1, p2}}.
    """
    import base64
    import anthropic
    from config.model_config import CLAUDE_MODELS

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    b64 = base64.b64encode(image_bytes).decode("ascii")

    response = client.messages.create(
        model=CLAUDE_MODELS["odds_extraction"],
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": _ODDS_EXTRACTION_PROMPT},
            ],
        }],
    )
    text = "".join(block.text for block in response.content if hasattr(block, "text")).strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        pairs = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        print(f"Greška pri parsiranju odgovora za ekstrakciju kvota: {text[:200]}")
        return {}

    result = {}
    for pair in pairs:
        try:
            p1, p2 = pair["player1"], pair["player2"]
            o1, o2 = safe_float(pair["odds1"]), safe_float(pair["odds2"])
        except (KeyError, TypeError):
            continue
        if not p1 or not p2 or o1 <= 1.0 or o2 <= 1.0:
            continue
        result[f"{p1}|{p2}"] = {"p1_odds": o1, "p2_odds": o2, "p1": p1, "p2": p2}
    return result


def get_screenshot_odds(date_str: str) -> dict:
    """
    Dohvat ručno unesenih kvota (sa screenshotova, uploadanih kroz Streamlit) za dani dan.
    Format identičan get_tennis_odds(): {"player1|player2": {p1_odds, p2_odds, p1, p2}}.
    """
    from database import supabase_client as _db
    odds = _db.get_screenshot_odds(date_str)
    if odds:
        print(f"Screenshot kvote: učitano {len(odds)} parova za {date_str}.")
    return odds


# ── Tennis Abstract ELO ───────────────────────────────────────────────────────

def get_tennis_abstract_elo() -> dict:
    """
    Returns ELO data dict keyed by player name (lowercase).
    Primary: reads from Supabase elo_cache (populated by scripts/update_elo_cache.py).
    Fallback: scrapes Tennis Abstract directly (works from local IP, blocked on GitHub Actions).
    """
    from database import supabase_client as _db
    cached = _db.get_elo_cache()
    if cached:
        print(f"ELO: loaded {len(cached)} players from Supabase cache.")
        return cached
    print("ELO cache empty — attempting direct scrape (may fail on GitHub Actions)...")

    url = "https://www.tennisabstract.com/reports/atp_elo_ratings.html"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.tennisabstract.com/",
            "Connection": "keep-alive",
        }
        r = requests.get(url, timeout=20, headers=headers)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        table = soup.find("table", {"id": "reportable"}) or soup.find("table")
        if not table:
            return {}

        # Pronađi indekse kolumni iz zaglavlja
        # Tennis Abstract headers: ELO Rank | Player | Age | Elo | hElo Rank | hElo | cElo Rank | cElo | gElo Rank | gElo
        header_row = table.find("tr")
        col_indices = {"name": 1, "elo": 3, "hard": 5, "clay": 7, "grass": 9}
        if header_row:
            headers = [th.get_text(strip=True).lower() for th in header_row.find_all(["th", "td"])]
            for i, h in enumerate(headers):
                if "player" in h or "name" in h:
                    col_indices["name"] = i
                elif h == "elo":
                    col_indices["elo"] = i
                elif h == "helo":          # hard ELO value (ne rank)
                    col_indices["hard"] = i
                elif h == "celo":          # clay ELO value
                    col_indices["clay"] = i
                elif h == "gelo":          # grass ELO value
                    col_indices["grass"] = i
                elif "hard" in h and "rank" not in h:
                    col_indices["hard"] = i
                elif "clay" in h and "rank" not in h:
                    col_indices["clay"] = i
                elif "grass" in h and "rank" not in h:
                    col_indices["grass"] = i

        elo_data = {}
        for row in table.find_all("tr")[1:500]:  # 500 umjesto 300 — sigurnosna margina
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
    import unicodedata

    def _normalize(s: str) -> str:
        """Ukloni dijakritike i standardiziraj razmake."""
        s = unicodedata.normalize("NFD", s)
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        return s.lower().strip()

    default = {"elo_overall": 1500, "elo_hard": 1500, "elo_clay": 1500, "elo_grass": 1500}
    if not player_name:
        return default

    # Normalize hyphens to spaces — "Carreno-Busta" → "Carreno Busta"
    name_norm = _normalize(player_name).replace("-", " ").replace("  ", " ")
    _elo_debug = len(elo_data) == 0  # warn if elo_data is empty

    def _norm_key(k):
        return _normalize(k).replace("-", " ").replace("  ", " ")

    # 1. Direktno podudaranje (normalizirano, bez crtica)
    for key in elo_data:
        if _norm_key(key) == name_norm:
            return elo_data[key]

    # 2. Poklapanje po prezimenu (zadnja riječ, bez crtica)
    surname = name_norm.split()[-1]
    matches = [key for key in elo_data if surname in _norm_key(key)]
    if len(matches) == 1:
        return elo_data[matches[0]]

    # 3. Poklapanje prvog i zadnjeg dijela imena
    parts = name_norm.split()
    if len(parts) >= 2:
        first, last = parts[0], parts[-1]
        for key in elo_data:
            k = _norm_key(key)
            if last in k and (first in k or k.startswith(first[0])):
                return elo_data[key]

    # Log missed lookups so we can diagnose ELO matching issues
    surname = name_norm.split()[-1] if name_norm else ""
    surname_matches = [key for key in elo_data if surname in _normalize(key)]
    print(f"  ELO MISS: '{player_name}' (norm='{name_norm}') → "
          f"surname '{surname}' found {len(surname_matches)} candidates: "
          f"{surname_matches[:3] if surname_matches else 'none'}")
    return default


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
            elif court == "Hard":
                key = "hard"
            elif court == "I.hard":
                key = "indoor_hard"
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


_titles_cache: dict = {}


def get_player_titles(player_id: str) -> dict:
    """
    Endpoint: GET /atp/player/titles/{playerId}
    Karijerna finala po razini turnira (C1, 26.07.2026 — korisnikov prijedlog "tko ima više
    iskustva u završnicama"). titlesWon = osvojeni turniri, titlesLost = izgubljena finala,
    pa je (won + lost) = ukupno odigranih finala na toj razini.

    Vraća: {"main_won": int, "main_lost": int, "ch_won": int, "ch_lost": int}
    (main = ATP main tour + Masters zbrojeno; ch = Challenger/ITF >$10K).
    """
    if not player_id:
        return {}
    key = str(player_id)
    if key in _titles_cache:
        return _titles_cache[key]
    data = _get(f"/atp/player/titles/{key}")
    out = {"main_won": 0, "main_lost": 0, "ch_won": 0, "ch_lost": 0}
    for row in (data or {}).get("data", []) or []:
        rank_id = safe_int(row.get("tourRankId"))
        won, lost = safe_int(row.get("titlesWon")), safe_int(row.get("titlesLost"))
        if rank_id in (2, 3):      # Main tour + Masters series
            out["main_won"] += won or 0
            out["main_lost"] += lost or 0
        elif rank_id == 1:          # Challengers / ITF > $10K
            out["ch_won"] += won or 0
            out["ch_lost"] += lost or 0
    _titles_cache[key] = out
    return out


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


_forecast_series_cache: dict = {}


def _entry_to_weather(e: dict) -> dict:
    return {
        "temp_c":    e.get("main", {}).get("temp"),
        "humidity":  e.get("main", {}).get("humidity"),
        "wind_kmh":  round(safe_float(e.get("wind", {}).get("speed", 0)) * 3.6, 1),
        "condition": e.get("weather", [{}])[0].get("main", ""),
    }


def get_forecast_series(city: str) -> list:
    """Cijela 3-satna prognoza za grad, JEDAN API poziv po gradu po procesu.

    Vraca listu {"utc": datetime, "raw": entry}. Cache je nuzan jer se sada bira unos po
    SATU svakog meca, pa bi bez njega isti grad bio dohvacen po nekoliko puta dnevno.
    cnt=40 (bilo 16): 16 unosa je 48h, a od 01.08.2026. dohvacamo i prekosutra — trecem
    danu je popodnevna sesija tada ispadala IZVAN prozora, pa je za njega jedini dostupan
    unos bio rani jutarnji. 40 unosa = 5 dana, s marginom.
    """
    if not WEATHER_KEY or not city:
        return []
    key = city.lower().strip()
    if key in _forecast_series_cache:
        return _forecast_series_cache[key]
    out = []
    try:
        data = _get_external(
            "https://api.openweathermap.org/data/2.5/forecast",
            params={"q": city, "appid": WEATHER_KEY, "units": "metric", "cnt": 40}
        )
        for e in (data or {}).get("list", []):
            try:
                out.append({"utc": datetime.datetime.strptime(e["dt_txt"], "%Y-%m-%d %H:%M:%S"),
                            "raw": e})
            except (KeyError, ValueError):
                continue
    except Exception:
        out = []
    _forecast_series_cache[key] = out
    return out


def weather_at_match_time(city: str, match_date: str, local_hour: int, utc_offset: int) -> dict:
    """Prognoza za SAT KADA SE MEC IGRA, ne za podne.

    BUG KOJI OVO ISPRAVLJA (04.08.2026, korisnik uocio na Berrettiniju): stara implementacija
    je uzimala unos u 12:00 **UTC** bez obzira na sat meca. Montreal je UTC-4, pa je to
    08:00 ujutro po lokalnom. Provjereno na stvarnom odgovoru za 05.08.2026:

        08:00 lokalno (sto je kod uzimao):  vlaga 68%, temp 19.2 C
        14:00 lokalno (kada se mec igra):   vlaga 48%, temp 28.3 C
        17:00 lokalno (kada se mec igra):   vlaga 52%, temp 28.5 C

    Dakle 20pp greske na vlazi i 9 C na temperaturi, uvijek u istom smjeru: jutro je hladno
    i vlazno, popodne vruce i suho. Posljedica je bila sustavna — pravilo 14 ("daytime heat
    speeds the court up") cijelo je ljeto dobivalo jutarnju temperaturu pa je podcjenjivalo
    vrucinu, a pravila o vlazi/vjetru od 04.08. radila su na krivom ocitanju.

    Vazno: usporedjuje se LOKALNO vrijeme, ne UTC datum. Vecernja sesija u Montrealu
    (20:00 lok. = 00:00 UTC iduci dan) inace bi trazila unos pod pogresnim datumom — isti
    cross-day problem koji je vec dokumentiran kod screenshot gatea 27.07.

    Vraca standardni weather dict + `forecast_local_time` i `hours_off` (koliko je izabrani
    unos udaljen od sata meca) da se u snapshotu vidi koliko je procjena pouzdana.
    """
    series = get_forecast_series(city)
    if not series or utc_offset is None or local_hour is None:
        return {}
    try:
        d = datetime.datetime.strptime(str(match_date)[:10], "%Y-%m-%d")
    except ValueError:
        return {}
    target_local = d + datetime.timedelta(hours=int(local_hour))
    best, best_gap = None, None
    for item in series:
        local = item["utc"] + datetime.timedelta(hours=utc_offset)
        gap = abs((local - target_local).total_seconds()) / 3600.0
        if best_gap is None or gap < best_gap:
            best, best_gap = item, gap
    if best is None:
        return {}
    w = _entry_to_weather(best["raw"])
    local = best["utc"] + datetime.timedelta(hours=utc_offset)
    w["forecast_local_time"] = local.strftime("%Y-%m-%d %H:%M")
    w["hours_off"] = round(best_gap, 1)
    return w


def get_weather_for_tournament(city: str, forecast_date: str = None) -> dict:
    """
    Fallback kad sat meca ILI utc offset grada nisu poznati (tada se ne smije pogadjati sat).
    Za mecheve s poznatim vremenom koristi se `weather_at_match_time` — vidi bug opisan ondje.
    - forecast_date=None or today → current weather (/data/2.5/weather)
    - forecast_date=tomorrow     → forecast API, uzima podnevni unos (gruba procjena)
    """
    if not WEATHER_KEY or not city:
        return {}
    import datetime as _dt
    today_str = _dt.date.today().isoformat()
    use_forecast = forecast_date and forecast_date != today_str

    try:
        if use_forecast:
            entries = [i["raw"] for i in get_forecast_series(city)]
            if not entries:
                return {}
            entry = None
            for e in entries:
                if e.get("dt_txt", "").startswith(forecast_date):
                    entry = e
                    if "12:00" in e.get("dt_txt", ""):
                        break
            if not entry:
                return {}
            return _entry_to_weather(entry)
        else:
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
    if any(x in cat for x in ["qual", "quali"]) or any(x in n for x in ["qualif", "quali"]):
        return "ATP Qualifying"
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


# ── Tournament Draw History (F/SF/QF/R16, zadnje 3 sezone) ────────────────────

def get_tournament_seasons(tournament_id: str) -> list:
    """
    Dohvat liste sezona za turnir.
    Endpoint: GET /atp/tournament/seasons/{tournamentId}
    Vraća: [{season_id, year, name}] sortirano od najnovijih.
    """
    data = _get(f"/atp/tournament/seasons/{tournament_id}")
    if not data:
        return []
    raw = data.get("data", [])
    if not isinstance(raw, list):
        return []
    seasons = []
    for s in raw:
        try:
            date_str = s.get("date") or s.get("startDate") or ""
            year = int(date_str[:4]) if len(date_str) >= 4 else 0
            sid = s.get("id")
            if year and sid:
                seasons.append({"season_id": int(sid), "year": year, "name": s.get("name", "")})
        except (ValueError, TypeError):
            continue
    return sorted(seasons, key=lambda x: x["year"], reverse=True)


def _label_draw_rounds(matches: list) -> list:
    """
    Dodjeljuje oznake rundi (F/SF/QF/R16) na temelju pozicije od kraja turnira.
    Pozicija 0 (najviši roundId) = Finale, 1 = Polufinale, 2 = Četvrtfinale, 3 = R16.
    Radi za bilo koju veličinu draw-a (GS 128, ATP 250 32/48 itd.).
    """
    from collections import defaultdict
    by_round: dict = defaultdict(list)
    for m in matches:
        if m.get("result_type") in ("completed", "retired"):
            by_round[m.get("roundId", 0)].append(m)

    sorted_rounds = sorted(by_round.keys(), reverse=True)
    label_map = {0: "F", 1: "SF", 2: "QF", 3: "R16"}

    labeled = []
    for pos, rid in enumerate(sorted_rounds):
        label = label_map.get(pos)
        if label:
            for m in by_round[rid]:
                labeled.append({**m, "round_name": label})
    return labeled


def get_tournament_draw_history(tournament_id: str, tournament_name: str, years: int = 3) -> list:
    """
    Dohvaća F/SF/QF/R16 rezultate za zadnje N završenih sezona turnira.

    Koristi:
      1. GET /atp/tournament/seasons/{tournamentId} → lista sezona s ID-ovima
      2. GET /atp/tournament/results/{seasonId}     → mečevi te sezone

    Vraća: [{tournament_name, season_id, season_year, round_name,
              winner_name, winner_id, loser_name, loser_id, score}]
    """
    current_year = datetime.date.today().year

    seasons = get_tournament_seasons(tournament_id)
    if not seasons:
        print(f"  Nema sezona za {tournament_name} (ID: {tournament_id}) — preskačem.")
        return []

    past_seasons = [s for s in seasons if s["year"] < current_year][:years]
    if not past_seasons:
        return []

    base_name = tournament_name.split(" - ")[0].strip()
    all_results = []

    for season in past_seasons:
        season_id = season["season_id"]
        year = season["year"]

        data = _get(f"/atp/tournament/results/{season_id}")
        if not data:
            print(f"  Nema rezultata za {base_name} {year} (season_id={season_id}).")
            continue

        raw = data.get("data", {})
        matches = raw.get("singles", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
        if not matches:
            continue

        labeled = _label_draw_rounds(matches)

        for m in labeled:
            winner_id_str = str(m.get("match_winner", ""))
            p1 = m.get("player1") or {}
            p2 = m.get("player2") or {}
            p1_id = str(m.get("player1Id", p1.get("id", "")))
            p2_id = str(m.get("player2Id", p2.get("id", "")))

            if p1_id == winner_id_str:
                winner, loser, w_id, l_id = p1, p2, p1_id, p2_id
            else:
                winner, loser, w_id, l_id = p2, p1, p2_id, p1_id

            winner_name = winner.get("name", "")
            loser_name = loser.get("name", "")
            if not winner_name or not loser_name:
                continue

            all_results.append({
                "tournament_name": base_name,
                "season_id": season_id,
                "season_year": year,
                "round_name": m["round_name"],
                "winner_name": winner_name,
                "winner_id": w_id,
                "loser_name": loser_name,
                "loser_id": l_id,
                "score": m.get("result", ""),
            })

        n_this_year = sum(1 for r in all_results if r["season_year"] == year)
        print(f"  {base_name} {year}: {n_this_year} draw rezultata (F/SF/QF/R16)")

    return all_results


_court_pace_cache: dict = {}

# UTC pomak grada domaćina (ljetno vrijeme, srpanj-listopad). Koristi se SAMO za
# pretvorbu vremena početka meča u LOKALNO vrijeme turnira (31.07.2026, korisnikov
# zahtjev): korisnik je u Zagrebu, a meč koji njemu počinje u 4 ujutro se u Washingtonu
# igra u 17h po suncu i vrućini — vremenska prognoza i sesija (dan/noć) moraju se vezati
# na lokalni sat mjesta, ne na naš. Nepoznat grad -> None (nema nagađanja).
_CITY_UTC_OFFSET = {
    "washington": -4, "los cabos": -6, "cincinnati": -4, "new york": -4,
    "toronto": -4, "montreal": -4, "winston-salem": -4, "atlanta": -4,
    "indian wells": -7, "miami": -4, "acapulco": -6, "delray beach": -5,
    "san diego": -7, "dallas": -5, "houston": -5,
    "london": 1, "paris": 2, "madrid": 2, "rome": 2, "monte carlo": 2,
    "barcelona": 2, "hamburg": 2, "munich": 2, "stuttgart": 2, "halle": 2,
    "vienna": 2, "basel": 2, "geneva": 2, "gstaad": 2, "kitzbuhel": 2,
    "umag": 2, "bastad": 2, "estoril": 1, "lisbon": 1, "marrakech": 1,
    "rotterdam": 2, "antwerp": 2, "metz": 2, "marseille": 2, "montpellier": 2,
    "doha": 3, "dubai": 4, "melbourne": 11, "sydney": 11, "adelaide": 10,
    "tokyo": 9, "beijing": 8, "shanghai": 8, "chengdu": 8, "hangzhou": 8,
    "astana": 6, "almaty": 6, "tel aviv": 3, "buenos aires": -3, "rio": -3,
    "santiago": -4, "cordoba": -3, "bucharest": 3, "sofia": 3, "belgrade": 2,
}


def local_match_time(iso_utc: str, city: str) -> dict:
    """Pretvori UTC vrijeme početka meča u LOKALNO vrijeme turnira + sesiju (dan/noć).

    Povod (31.07.2026): polje `timeGame` iz fixtures API-ja je UVIJEK null, pa je
    context_snapshot.match_time bio prazan otkad je uveden (18.07.) — varijabla "sat meča"
    zapravo nikad nije postojala. Puni timestamp ipak stoji u polju `date`
    (npr. "2026-08-01T03:00:00.000Z"), pa ga ovdje pretvaramo u lokalni sat grada domaćina.

    Vraća {"local_time": "HH:MM", "session": "day|night", "utc_offset": int} ili {} ako
    grad nije poznat (nikad ne nagađamo — bolje bez podatka nego s krivim)."""
    if not iso_utc or not city:
        return {}
    offset = _CITY_UTC_OFFSET.get(city.lower().strip())
    if offset is None:
        return {}
    try:
        base = datetime.datetime.fromisoformat(str(iso_utc).replace("Z", "+00:00"))
    except ValueError:
        return {}
    local = base + datetime.timedelta(hours=offset)
    # Sesija: dnevna do 18h lokalno, inače noćna (US hard noćne sesije su hladnije i sporije)
    session = "day" if 6 <= local.hour < 18 else "night"
    return {"local_time": local.strftime("%H:%M"), "session": session, "utc_offset": offset}


def get_court_pace(tournament_id: str, tournament_name: str = "") -> dict:
    """Proxy za brzinu terena: udio setova odigranih u tiebreaku na ovom turniru ove sezone.

    Zašto ovako (31.07.2026): Tennis_Surface_Analysis.docx kaže da je "tretiranje svih hard
    terena jednako najčešća greška u modeliranju te podloge", a pravi Court Pace Index
    (Hawkeye CPI) nije javno dostupan ni na jednom pristupačnom API-ju. Rezultate turnira
    ionako dohvaćamo svaku večer, pa se iz score stringova broj tiebreakova računa BEZ
    IJEDNOG dodatnog API poziva. Izmjereno: Washington (hard) 15.8% setova u tiebreaku vs
    Estoril (clay) 7.5% — signal jasno razlikuje brze od sporih terena.

    Vraća {"tb_pct": float, "sets": int, "label": "fast|medium|slow"} ili {} bez podataka."""
    if not tournament_id:
        return {}
    if tournament_id in _court_pace_cache:
        return _court_pace_cache[tournament_id]
    results = get_current_season_results(tournament_id)
    tb = sets = 0
    for r in results:
        score = str(r.get("score") or "")
        for token in score.split():
            if "-" not in token:
                continue
            sets += 1
            if "(" in token:
                tb += 1
    out = {}
    if sets >= 20:      # ispod ~20 setova uzorak je prešaren da bi značio išta
        pct = round(tb / sets * 100, 1)
        # Pragovi iz izmjerenog raspona: clay ~7%, medium hard ~12%, fast hard ~16%+
        label = "fast" if pct >= 14 else ("slow" if pct < 9 else "medium")
        out = {"tb_pct": pct, "sets": sets, "label": label}
    _court_pace_cache[tournament_id] = out
    return out


def get_current_season_results(tournament_id: str) -> list:
    """Svi odigrani mečevi TEKUĆE sezone turnira: parovi imena + pobjednik.

    Endpointi: GET /atp/tournament/seasons/{tournamentId} → season_id tekuće godine,
               GET /atp/tournament/results/{seasonId}     → mečevi s match_winner.

    Povod (26.07.2026): /atp/fixtures je čisti raspored i NIKAD ne nosi pobjednika
    (provjereno sirovim odgovorom — ključevi su samo id/date/roundId/playerXId/live/...),
    pa je večernji korak razrješavanja analyzed_matches od 18.07. razriješio 0/421
    analiza: kalibracijska tablica prazna, hard-revalidacijski okidač slijep. Ovo je
    jedini izvor pobjednika koji ne traži player_id — 2 API poziva po turniru.
    """
    if not tournament_id:
        return []
    current_year = datetime.date.today().year
    seasons = get_tournament_seasons(tournament_id)
    season = next((s for s in seasons if s.get("year") == current_year), None)
    if not season:
        return []
    data = _get(f"/atp/tournament/results/{season['season_id']}")
    if not data:
        return []
    raw = data.get("data", {})
    matches = raw.get("singles", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
    out = []
    for m in matches:
        w_id = str(m.get("match_winner") or "")
        p1 = m.get("player1") or {}
        p2 = m.get("player2") or {}
        p1_id = str(m.get("player1Id", p1.get("id", "")))
        p2_id = str(m.get("player2Id", p2.get("id", "")))
        p1_name = p1.get("name", "")
        p2_name = p2.get("name", "")
        if not w_id or not p1_name or not p2_name:
            continue
        winner = p1_name if w_id == p1_id else p2_name if w_id == p2_id else ""
        if not winner:
            continue
        out.append({"player1": p1_name, "player2": p2_name,
                    "winner": winner, "score": str(m.get("result") or "")})
    return out
