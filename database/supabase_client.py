"""
Supabase REST API klijent — direktni HTTP pozivi, bez supabase Python paketa.
Koristi samo 'requests' koji je standardno dostupan. Kompatibilan s Python 3.14+.
"""
import os
import json
import datetime
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def _get_config():
    url = os.environ.get("SUPABASE_URL") or _streamlit_secret("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY") or _streamlit_secret("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL i SUPABASE_KEY moraju biti postavljeni u .env ili Streamlit Secrets")
    return url.rstrip("/"), key


def _streamlit_secret(key: str) -> Optional[str]:
    try:
        import streamlit as st
        return st.secrets.get(key)
    except Exception:
        return None


def _headers(key: str, prefer: str = None, content_type: bool = True) -> dict:
    h = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    if content_type:
        h["Content-Type"] = "application/json"
    if prefer:
        h["Prefer"] = prefer
    return h


def _rest(method: str, table: str, params: dict = None, body=None, prefer: str = None) -> list:
    url, key = _get_config()
    endpoint = f"{url}/rest/v1/{table}"
    headers = _headers(key, prefer=prefer)
    try:
        r = requests.request(
            method,
            endpoint,
            headers=headers,
            params=params,
            json=body,
            timeout=15
        )
        r.raise_for_status()
        if r.content:
            return r.json() if isinstance(r.json(), list) else [r.json()] if r.json() else []
        return []
    except requests.HTTPError as e:
        print(f"Supabase HTTP greška [{method} {table}]: {e.response.status_code} — {e.response.text[:200]}")
        return []
    except Exception as e:
        print(f"Supabase greška [{method} {table}]: {e}")
        return []


def _select(table: str, select: str = "*", filters: dict = None, order: str = None,
            limit: int = None) -> list:
    params = {"select": select}
    if order:
        params["order"] = order
    if limit:
        params["limit"] = str(limit)
    if filters:
        params.update(filters)
    return _rest("GET", table, params=params)


def _insert(table: str, data) -> list:
    body = data if isinstance(data, list) else [data]
    return _rest("POST", table, body=body, prefer="return=representation")


def _update(table: str, data: dict, filters: dict) -> list:
    params = {}
    params.update(filters)
    return _rest("PATCH", table, params=params, body=data, prefer="return=representation")


def _upsert(table: str, data: dict, on_conflict: str = None) -> list:
    params = {}
    prefer = "return=representation,resolution=merge-duplicates"
    if on_conflict:
        params["on_conflict"] = on_conflict
    return _rest("POST", table, params=params, body=data, prefer=prefer)


# ── Tickets ───────────────────────────────────────────────────────────────────

def save_ticket(ticket_data: dict) -> dict:
    result = _insert("tickets", ticket_data)
    return result[0] if result else {}


def update_ticket_status(ticket_id: str, status: str, actual_win: float = None) -> None:
    data = {"status": status}
    if actual_win is not None:
        data["actual_win"] = actual_win
    if status in ("won", "lost"):
        data["resolved_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    _update("tickets", data, {"id": f"eq.{ticket_id}"})


def get_tickets(limit: int = 50, status: str = None) -> list:
    filters = {}
    if status:
        filters["status"] = f"eq.{status}"
    tickets = _select("tickets", select="*", filters=filters, order="ticket_date.desc", limit=limit)
    for t in tickets:
        matches = _select("ticket_matches", filters={"ticket_id": f"eq.{t['id']}"})
        t["ticket_matches"] = matches
    return tickets


def get_ticket_by_date(date_str: str) -> Optional[dict]:
    results = _select("tickets", filters={"ticket_date": f"eq.{date_str}"}, limit=1)
    if not results:
        return None
    t = results[0]
    t["ticket_matches"] = _select("ticket_matches", filters={"ticket_id": f"eq.{t['id']}"})
    return t


def delete_ticket(ticket_id: str) -> bool:
    """Briše tiket i sve njegove mečeve iz baze."""
    try:
        _rest("DELETE", "ticket_matches", params={"ticket_id": f"eq.{ticket_id}"})
        _rest("DELETE", "tickets", params={"id": f"eq.{ticket_id}"})
        return True
    except Exception as e:
        print(f"Greška brisanja tiketa {ticket_id}: {e}")
        return False


# ── Ticket Matches ────────────────────────────────────────────────────────────

# Stupci dodani 2026-07-26 (A1) koji možda još ne postoje na starijim instancama baze.
# Ako insert padne zbog njih, ponavljamo bez njih — spremanje tiketa NIKAD ne smije pasti
# zbog opcionalnog polja (vidi ALTER TABLE u database/schema.sql).
_OPTIONAL_TM_COLS = ("player1_id", "player2_id")


def save_ticket_matches(matches: list) -> None:
    if not matches:
        return
    result = _insert("ticket_matches", matches)
    if result:
        return
    # Fallback: možda tablica nema opcionalne stupce — probaj bez njih
    stripped = [{k: v for k, v in m.items() if k not in _OPTIONAL_TM_COLS} for m in matches]
    if stripped != matches:
        print("  Upis tiketa bez player1_id/player2_id (stupci ne postoje — pokreni ALTER TABLE "
              "iz database/schema.sql da razrješavanje rezultata bude otpornije).")
        _insert("ticket_matches", stripped)


def update_match_result(match_id: str, result: str, actual_winner: str,
                        actual_score: str = None) -> None:
    data = {
        "result": result,
        "actual_winner": actual_winner,
        "resolved_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    if actual_score:
        data["actual_score"] = actual_score
    _update("ticket_matches", data, {"id": f"eq.{match_id}"})


def save_match_stats(match_id: str, match_stats: dict) -> None:
    """Best-effort: sprema sirove post-match statistike u match_stats (JSONB).
    Namjerno ODVOJENO od update_match_result — ako stupac match_stats još ne
    postoji u bazi, ovo tiho padne, ali upis rezultata (won/lost) ostaje siguran."""
    if not match_stats:
        return
    _update("ticket_matches", {"match_stats": match_stats}, {"id": f"eq.{match_id}"})


def save_loss_analysis(match_id: str, analysis: str) -> None:
    _update("ticket_matches", {"loss_analysis": analysis, "analysis_done": True}, {"id": f"eq.{match_id}"})


def get_pending_matches() -> list:
    today = datetime.date.today().isoformat()
    return _select("ticket_matches", filters={
        "result": "eq.pending",
        "match_date": f"lte.{today}"
    })


def get_lost_matches_needing_analysis() -> list:
    return _select("ticket_matches", filters={
        "result": "eq.lost",
        "analysis_done": "eq.false"
    })


def reset_loss_analyses() -> int:
    """Resetira sve analize gubitaka da se mogu ponovo generirati s ispravnim podacima."""
    result = _rest("PATCH", "ticket_matches",
                   params={"result": "eq.lost", "analysis_done": "eq.true"},
                   body={"analysis_done": False, "loss_analysis": None},
                   prefer="return=representation")
    count = len(result)
    print(f"Reset {count} loss analyses for re-generation.")
    return count


def get_analyzed_lost_matches(limit: int = 20) -> list:
    return _select("ticket_matches", filters={
        "result": "eq.lost",
        "analysis_done": "eq.true"
    }, order="resolved_at.desc", limit=limit)


def get_won_matches(limit: int = 40) -> list:
    """Razriješeni dobitni parovi — koristi se za učenje iz uspješnih tipova
    (kontrast naspram gubitaka pri korekciji težina)."""
    return _select("ticket_matches", filters={
        "result": "eq.won"
    }, order="resolved_at.desc", limit=limit)


def get_recent_lost_matches(days: int = 14) -> list:
    """Izgubljeni pickovi zadnjih N dana — za Fery veto (hard revizija 2026-07-18,
    korekcija istog dana: 21→14 dana, dovoljno za pokriti trajanje Grand Slama).
    Igrač koji nas je srušio 2+ puta u istom turniru ne smije se više fade-ati u
    njemu. Vraća player1/player2/pick/actual_winner/tournament/match_date."""
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    return _select("ticket_matches",
                   select="player1,player2,pick,actual_winner,tournament,match_date",
                   filters={"result": "eq.lost", "match_date": f"gte.{since}"})


# ── Model Weights ─────────────────────────────────────────────────────────────

def _surface_key(surface: str) -> str:
    """Normalise surface string to 'clay' | 'grass' | 'hard'."""
    s = surface.lower().strip()
    if "clay" in s:       return "clay"
    if "grass" in s:      return "grass"
    return "hard"  # hard, indoor hard, default


def get_active_weights(surface: str = "hard") -> dict:
    """Load active weights for the given surface. Falls back to hard if not found."""
    sk = _surface_key(surface)
    # Try surface-specific record first (surface stored inside weights JSON)
    results = _select("model_weights", filters={"is_active": "eq.true", "weights->>surface": f"eq.{sk}"}, order="version.desc", limit=1)
    if not results:
        # Fallback: any active record without surface key (legacy v1-v3)
        results = _select("model_weights", filters={"is_active": "eq.true"}, order="version.desc", limit=1)
    if results:
        raw = results[0].get("weights", {})
        w = json.loads(raw) if isinstance(raw, str) else dict(raw)
        w.pop("surface", None)  # remove surface tag before returning numeric weights
        return w
    from config.model_config import DEFAULT_WEIGHTS
    return DEFAULT_WEIGHTS


def get_active_weight_version(surface: str = "hard"):
    """Broj verzije aktivnih težina za podlogu (npr. 15) ili None.

    Svrha (26.07.2026): žig u context_snapshot.model_stamp — omogućuje kasnije EGZAKTNO
    rezanje kalibracijskog korpusa po erama modela (dosad se era rekonstruirala iz datuma
    revizija u MODEL_CHANGELOG-u, što radi, ali ručno je)."""
    sk = _surface_key(surface)
    results = _select("model_weights", select="version",
                      filters={"is_active": "eq.true", "weights->>surface": f"eq.{sk}"},
                      order="version.desc", limit=1)
    if not results:
        results = _select("model_weights", select="version",
                          filters={"is_active": "eq.true"}, order="version.desc", limit=1)
    return results[0].get("version") if results else None


def get_active_weight_version_date(surface: str = "hard") -> str:
    """Returns the created_at date of the active weights for a given surface."""
    sk = _surface_key(surface)
    results = _select("model_weights", select="created_at",
                      filters={"is_active": "eq.true", "weights->>surface": f"eq.{sk}"},
                      order="version.desc", limit=1)
    if not results:
        results = _select("model_weights", select="created_at",
                          filters={"is_active": "eq.true"}, order="version.desc", limit=1)
    if results:
        return (results[0].get("created_at") or "")[:10]
    return "2000-01-01"


def save_new_weights(weights: dict, reason: str, triggered_by: str, surface: str = "hard") -> None:
    """Save new surface-specific weights. Deactivates only the previous record for that surface."""
    sk = _surface_key(surface)
    weights_to_save = {"surface": sk, **{k: v for k, v in weights.items() if k != "surface"}}
    # Deactivate only same-surface active weights
    old = _select("model_weights", select="id", filters={"is_active": "eq.true", "weights->>surface": f"eq.{sk}"})
    for row in old:
        _update("model_weights", {"is_active": False}, {"id": f"eq.{row['id']}"})
    current = _select("model_weights", select="version", order="version.desc", limit=1)
    next_version = (current[0]["version"] + 1) if current else 2
    _insert("model_weights", {
        "version": next_version,
        "weights": weights_to_save,
        "is_active": True,
        "update_reason": reason,
        "triggered_by": triggered_by
    })


def get_weight_history() -> list:
    return _select("model_weights", order="version.desc", limit=20)


# ── Performance Log ───────────────────────────────────────────────────────────

def upsert_performance_log(log_data: dict) -> None:
    _upsert("performance_log", log_data, on_conflict="log_date")


def get_performance_history(days: int = 60) -> list:
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    return _select("performance_log", filters={"log_date": f"gte.{since}"}, order="log_date")


# ── Analyzed Matches ──────────────────────────────────────────────────────────

def stable_match_key(match_date, player1: str, player2: str) -> str:
    """Stabilan, nepromjenjiv ključ meča: datum + oba igrača (normalizirano, sortirano).

    KRITIČNO (31.07.2026): dosad se kao ključ upserta koristio API-jev fixture `id`, ali
    on NIJE stabilan — API ga s vremenom PRENAMJENJUJE drugom meču. Dokaz: id=1216 je u
    našoj bazi bio Majchrzak-Paul (28.07.), a u API-ju danas pripada meču Echargui-Lee
    (25.07.). Kad se ID reciklira, upsert prepiše imena i predikciju novim mečem, ali
    actual_winner/prediction_correct ostanu od STAROG meča → 55/78 hard analiza je nosilo
    pobjednika s clay turnira (npr. Majchrzak-Paul -> 'Quentin Halys'). Kalibracijska
    tablica za hard bila je 70% smeće, a auto-feedback je iz toga učio.
    Ovaj ključ ovisi samo o stvarnom identitetu meča i ne može se reciklirati."""
    d = str(match_date or "")[:10]
    a = _norm_player_key(player1)
    b = _norm_player_key(player2)
    lo, hi = sorted([a, b])          # sortirano → otporno na zamjenu p1/p2 između runova
    return f"{d}|{lo}|{hi}"


def _norm_player_key(name: str) -> str:
    """Ime igrača svedeno na ključ: bez dijakritika, mala slova, jedan razmak.

    Koristi istu transliteraciju kao data_fetcher._strip_diacritics (đ→dj itd.) da isti
    igrač NIKAD ne dobije dva različita ključa ovisno o tome piše li izvor "Međedović"
    ili "Medjedovic" — inače bi se stvorila dva zapisa za isti meč."""
    from agent.data_fetcher import _strip_diacritics
    s = _strip_diacritics(str(name or ""))
    return " ".join(s.lower().replace("-", " ").split())


def save_analyzed_match(match_data: dict) -> None:
    """Upsert analize. Ključ je STABILAN (datum+igrači), ne API fixture id — vidi
    stable_match_key za razlog. external_match_id se prepisuje ovdje da pozivatelji
    ne moraju znati za promjenu."""
    data = dict(match_data)
    data["external_match_id"] = stable_match_key(
        data.get("match_date"), data.get("player1"), data.get("player2"))
    _upsert("analyzed_matches", data, on_conflict="external_match_id")


def get_unresolved_analyzed_matches(days: int = 8) -> list:
    """Analize bez ishoda (actual_winner NULL) zadnjih N dana — evening update ih
    razrješava (hard revizija 2026-07-18). Prije toga je 419/419 analiza stajalo bez
    rezultata pa je feedback petlja učila samo na uskom, selektiranom uzorku tiketa."""
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    # tournament je potreban da _build_season_winner_lookup (26.07.2026) može grupirati
    # parove po turniru i otkriti tournament_id kad turnir nestane iz fixtures feeda
    return _select("analyzed_matches",
                   select="id,external_match_id,match_date,player1,player2,"
                          "predicted_winner,tournament",
                   filters={"actual_winner": "is.null", "match_date": f"gte.{since}"})


def update_analyzed_match_result(row_id: str, actual_winner: str, prediction_correct,
                                 player1: str = None, player2: str = None) -> bool:
    """Upis ishoda u analyzed_matches (prediction_correct može biti None za void).

    SANITY GUARD (31.07.2026): ako su proslijeđena imena igrača, pobjednik MORA biti
    jedan od njih. Prije ove provjere 55 hard analiza je tiho dobilo pobjednika iz
    posve drugog meča (posljedica recikliranja fixture id-a — vidi stable_match_key),
    a nitko to nije primijetio jer se ishod nigdje ne uspoređuje s igračima.
    Vraća True ako je zapisano, False ako je odbijeno."""
    if player1 is not None and player2 is not None:
        w = _norm_player_key(actual_winner)
        if w and w not in (_norm_player_key(player1), _norm_player_key(player2)):
            print(f"  ODBIJEN neispravan ishod: '{actual_winner}' nije igrač u meču "
                  f"{player1} vs {player2} — preskačem (mogući nesklad izvora).")
            return False
    _update("analyzed_matches",
            {"actual_winner": actual_winner, "prediction_correct": prediction_correct},
            {"id": f"eq.{row_id}"})
    return True


def get_all_scouting() -> dict:
    """Svi scouting profili (player_scouting tablica, uvoz iz korisnikovog Excela preko
    scripts/import_scouting.py) — dict keyed by normalizirano ime. Jedan poziv po daily runu.
    Vraća {} ako tablica ne postoji ili je prazna (pipeline radi normalno bez scoutinga)."""
    try:
        rows = _select("player_scouting", limit=200)
        return {r["player_name"]: r for r in rows if r.get("player_name")}
    except Exception as e:
        print(f"Scouting profili nedostupni ({e}) — nastavljam bez njih.")
        return {}


def get_resolved_analyzed_matches(limit: int = 2000) -> list:
    """Sve razriješene analize (prediction_correct NIJE null) iz ŠIREG korpusa
    analyzed_matches — NE samo tiket pickovi (preporuka F, 18.07.2026: kalibracijska
    tablica na Model Statistike stranici prije je koristila samo ticket_matches, uzak,
    selektirani uzorak). void ishodi (prediction_correct is.null nakon voida) su već
    isključeni jer void upisuje None, ne True/False."""
    return _select("analyzed_matches",
                   select="predicted_confidence,prediction_correct,surface,match_date",
                   filters={"prediction_correct": "not.is.null"},
                   order="match_date.desc",
                   limit=limit)


# ── ELO Cache ─────────────────────────────────────────────────────────────────

def get_elo_cache() -> dict:
    """Fetch all ELO entries from Supabase cache. Returns dict keyed by player_name.lower()."""
    rows = _select("elo_cache", select="player_name,elo_overall,elo_hard,elo_clay,elo_grass", limit=2000)
    result = {}
    for r in rows:
        name = (r.get("player_name") or "").lower().strip()
        if name:
            result[name] = {
                "elo_overall": r.get("elo_overall") or 1500,
                "elo_hard":    r.get("elo_hard")    or 1500,
                "elo_clay":    r.get("elo_clay")    or 1500,
                "elo_grass":   r.get("elo_grass")   or 1500,
            }
    return result


def upsert_elo_cache(entries: list) -> None:
    """Upsert list of ELO dicts with keys: player_name, elo_overall, elo_hard, elo_clay, elo_grass."""
    if not entries:
        return
    # Batch in chunks of 200
    for i in range(0, len(entries), 200):
        batch = entries[i:i+200]
        _rest("POST", "elo_cache", body=batch,
              prefer="return=minimal,resolution=merge-duplicates",
              params={"on_conflict": "player_name"})


# ── Screenshot Odds (ručno unesene kvote sa screenshotova kladionice) ─────────

def save_screenshot_odds(match_date: str, odds_dict: dict) -> None:
    """
    Sprema/dopunjuje kvote izvučene iz screenshota za dani datum (YYYY-MM-DD).
    Mergira s postojećim zapisom za taj dan (više uploada istog dana se akumuliraju),
    pa upserta preko on_conflict=match_date.
    """
    existing = get_screenshot_odds(match_date)
    merged = {**existing, **odds_dict}
    _upsert("screenshot_odds", {"match_date": match_date, "odds_data": merged}, on_conflict="match_date")


def get_screenshot_odds(match_date: str) -> dict:
    """Dohvat kvota sa screenshota za dani datum (YYYY-MM-DD). Vraća {} ako ne postoji."""
    results = _select("screenshot_odds", filters={"match_date": f"eq.{match_date}"}, limit=1)
    if results:
        return results[0].get("odds_data") or {}
    return {}


def delete_screenshot_odds(match_date: str) -> bool:
    """Briše sve spremljene screenshot kvote za dani datum (YYYY-MM-DD)."""
    try:
        _rest("DELETE", "screenshot_odds", params={"match_date": f"eq.{match_date}"})
        return True
    except Exception as e:
        print(f"Greška brisanja screenshot kvota za {match_date}: {e}")
        return False


def cleanup_old_screenshot_odds(keep_from_date: str) -> int:
    """
    Briše screenshot kvote čiji je match_date prošao (stariji od keep_from_date, YYYY-MM-DD).
    Sprječava nakupljanje zastarjelih uploada — pozvati jednom dnevno (npr. iz run_daily.py).
    """
    try:
        deleted = _rest("DELETE", "screenshot_odds", params={"match_date": f"lt.{keep_from_date}"},
                        prefer="return=representation")
        return len(deleted)
    except Exception as e:
        print(f"Greška čišćenja starih screenshot kvota: {e}")
        return 0


# ── Tournament History (draw results — F/SF/QF/R16, zadnje 3 sezone) ─────────

def save_tournament_history(records: list) -> int:
    """Batch upsert draw rezultata turnira. Vraća broj stvarno upsertanih redaka.

    fetched_at se OSVJEŽAVA pri svakom upsertu (A5, 26.07.2026). Prije se slao samo pri
    prvom insertu, pa je ostajao zamrznut na datumu prvog dohvata — zbog čega tjedni
    throttle u has_tournament_history nikad ne bi resetirao brojač i turnir bez najnovije
    sezone (npr. Estoril, koji u API-ju nema 2025) bi se opet dohvaćao svaki dan."""
    if not records:
        return 0
    _DB_COLS = {"tournament_name", "season_id", "season_year", "round_name",
                "winner_name", "loser_name", "score"}
    _now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    clean = [{**{k: v for k, v in r.items() if k in _DB_COLS}, "fetched_at": _now}
             for r in records]
    saved = 0
    for i in range(0, len(clean), 50):
        batch = clean[i:i + 50]
        result = _rest(
            "POST", "tournament_history", body=batch,
            prefer="return=representation,resolution=merge-duplicates",
            params={"on_conflict": "season_id,winner_name,loser_name,round_name"},
        )
        saved += len(result)
    return saved


def get_tournament_draw(tournament_name: str, min_year: int) -> list:
    """
    Dohvat cachiranih draw rezultata (F/SF/QF/R16) za zadani turnir od min_year.
    Radi case-insensitive match na base imenu (npr. "Wimbledon" matchira "Wimbledon - London").
    Vraća [] ako tablica ne postoji ili nema podataka.
    """
    base_name = tournament_name.split(" - ")[0].strip()
    try:
        return _select(
            "tournament_history",
            filters={
                "tournament_name": f"ilike.%{base_name}%",
                "season_year": f"gte.{min_year}",
            },
            order="season_year.desc",
            limit=120,
        )
    except Exception as e:
        print(f"Greška dohvata tournament_history za {tournament_name}: {e}")
        return []


def has_tournament_history(tournament_name: str) -> bool:
    """Provjeri postoje li upotrebljivi draw podaci — ako ne, treba re-fetch.

    Prije (do 26.07.2026) je tražio STROGO prošlu sezonu (current_year - 1). Problem: neki
    turniri tu sezonu jednostavno nemaju u API-ju (Millennium Estoril Open ima 2022/2023/2024,
    2025. ne postoji), pa je provjera vraćala False svaki dan → puni re-fetch i re-upsert
    istih ~45 zapisa SVAKI daily run, a 2025. se ionako nikad nije pojavila.

    Sada: dovoljno je da postoji BILO KOJA sezona unutar zadnje 3 (A5). Time se gubi
    automatski re-fetch čim nova sezona završi, pa se to rješava zasebno: ako su podaci
    stariji od (current_year - 1), dopuštamo jedan re-fetch pokušaj TJEDNO umjesto dnevno.
    """
    base_name = tournament_name.split(" - ")[0].strip()
    today = datetime.date.today()
    try:
        rows = _select(
            "tournament_history",
            select="id,season_year,fetched_at",
            filters={
                "tournament_name": f"ilike.%{base_name}%",
                "season_year": f"gte.{today.year - 3}",
            },
            order="season_year.desc",
            limit=1,
        )
        if not rows:
            return False  # nema ničega → dohvati
        newest_season = rows[0].get("season_year") or 0
        if newest_season >= today.year - 1:
            return True  # svježe, ništa ne treba
        # Podaci postoje ali su stariji (npr. Estoril bez 2025) — pokušaj re-fetch najviše
        # jednom tjedno umjesto svaki dan, da se ne troše API pozivi uzalud.
        fetched = str(rows[0].get("fetched_at") or "")[:10]
        try:
            age_days = (today - datetime.date.fromisoformat(fetched)).days
        except ValueError:
            return False  # nepoznata starost → dopusti dohvat (kao i prije izmjene)
        return age_days < 7
    except Exception:
        return False
