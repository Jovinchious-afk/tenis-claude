# -*- coding: utf-8 -*-
"""Tri igraceve varijable koje je korisnik trazio 26.09.2026 17:04.

    1. OMJER PROTIV LJEVAKA / DESNJAKA — povod: komentator finala US Opena 2026 rekao je
       da je Zverev dominantan protiv ljevaka jer trenira s bratom Mischom, koji je ljevak.
       Korisnik: "kada desni tenisac igra protiv ljevih, treba u analizu uci postotak
       dobivenih i izgubljenih protiv takvih igraca i obrnuto" + da se to zabiljezi za
       SVE nase dosadasnje meceve.
    2. BROJ ATP POBJEDA U TEKUCOJ SEZONI — pokazatelj forme sezone.
    3. BROJ GRAND SLAM POLUFINALA I FINALA — pokazatelj favorita ("Shelton je imao prvo
       GS finale i vidjelo se da je Zverev mirniji").

Sve su CISTE FUNKCIJE nad listom proslih meceva i datumom `as_of`, pa isti kod racuna
vrijednost u dnevnom runu i u backfillu unatrag (`scripts/backfill_player_context.py`).
To je namjerno: mjerenje unatrag vrijedi samo ako je varijabla racunata ISTIM kodom kao
ona koju ce model vidjeti.

ZASTITA OD CURENJA (ista kao `agent/history_features.py`): nas `match_date` i API-jev datum
razilaze se u 23% meceva (±2 dana), pa bi naivni filtar "prije datuma" u backfillu uvukao
SAM MEC koji predvidjamo. Broje se samo mecevi `MIN_DAYS_BEFORE`+ dana prije, a mec protiv
istog protivnika unutar `SAME_PAIR_WINDOW` dana odbacuje se uvijek. U dnevnom runu to
nije nuzno (API vraca samo odigrane meceve), ali se primjenjuje i ondje da vrijednost
bude racunata jednako u oba slucaja.

IZVOR RUKE: `/atp/player/profile/{id}` -> `information.plays` ("Left-Handed, Two-Handed
Backhand"). Ruka se ne mijenja, pa se kesira trajno u `player_hands.json` (puni se
backfill skriptom); nepoznati igraci dohvacaju se uzivo uz strop po runu.
Ranking lista ruku NE nosi (provjereno 26.09.2026), a Sackmannov CSV vise ne postoji (404).
"""
import datetime
import json
import os
import time

from utils.helpers import safe_int

MIN_DAYS_BEFORE = 3
SAME_PAIR_WINDOW = 5
VS_HAND_WINDOW_DAYS = 730          # dvije sezone: dovoljno meceva protiv ljevaka, jos aktualno

# Razine turnira u `past-matches` (tournament.rankId), provjereno 26.09.2026 na 53.642 meca:
#   0 Futures/ITF  1 Challenger  2 ATP 250/500  3 Masters  4 Grand Slam
#   5 Davis Cup / ekipno  7 ATP Finals  9 Olimpijske
# "ATP pobjeda" = razine koje ATP broji u sluzbeni W-L: sve osim Futuresa i Challengera.
TOUR_RANK_IDS = {2, 3, 4, 5, 7, 9}
# `roundId` 1-3 su kvalifikacije, glavni zdrijeb pocinje na 4 (provjereno na US Openu,
# Challengerima i `tournament-record`, koji Zverevu za US Open 2014 daje "Q2" s id 2).
# Provjera cijelog filtra: Zverev 2026 = 55-13, tocno kao sluzbeni `perf-breakdown`.
MAIN_DRAW_MIN_ROUND_ID = 4

GS_KEYS = ("AO", "RG", "WIM", "USO")
# Grand Slam runde po `bestRoundId` iz `tournament-record` — provjereno 26.09.2026 na
# 3.795 izdanja (287 igraca): 1-3 kvalifikacije, 4 prvo kolo, 5, 6, 7, 9 = 1/4,
# 10 = 1/2, 12 = finale. ID je dosljedan u svakom retku.
# OZNAKA `bestRound` NIJE: "Winner" stoji uz ID 1, 4, 5, 6, 7 i 9 u 19 izdanja (npr.
# Gaston, Roland Garros 2025: ID 4, 1-0, "Winner" — dobio prvo kolo pa se povukao; API
# pise "Winner" kad nema poraza). Zato se broji po ID-u, a naslov je ID 12 BEZ poraza.
GS_SF_ROUND_ID = 10
GS_F_ROUND_ID = 12

HANDS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "player_hands.json")


def hand_code(plays_or_hand: str) -> str:
    """'Left-Handed, Two-Handed Backhand' / 'Left-Handed' / 'L' -> 'L'; desnjak 'R'; inace ''."""
    s = str(plays_or_hand or "").strip().lower()
    if s.startswith("left") or s in ("l", "ljevak", "lijeva"):
        return "L"
    if s.startswith("right") or s in ("r", "desnjak", "desna"):
        return "R"
    return ""


def _d(x):
    try:
        return datetime.date.fromisoformat(str(x)[:10])
    except (TypeError, ValueError):
        return None


def safe_matches(matches: list, as_of, opponent_id: str = "") -> list:
    """Mecevi koje je sigurno koristiti za predikciju na `as_of` (vidi docstring modula)."""
    ref = _d(as_of)
    if ref is None:
        raise ValueError("safe_matches trazi `as_of` — bez njega nema zastite od curenja.")
    out = []
    for m in matches or []:
        md = _d(m.get("date"))
        if md is None:
            continue
        gap = (ref - md).days
        if gap < MIN_DAYS_BEFORE:
            continue
        if opponent_id and gap <= SAME_PAIR_WINDOW and opponent_id in (m.get("p1"), m.get("p2")):
            continue
        out.append(m)
    return out


def _won(m: dict, pid: str) -> bool:
    return str(m.get("w") or "") == str(pid)


def _opp(m: dict, pid: str) -> str:
    return m.get("p2") if str(m.get("p1")) == str(pid) else m.get("p1")


def season_record(matches: list, pid: str, as_of, opponent_id: str = "") -> dict:
    """ATP W-L u kalendarskoj godini `as_of`, glavni zdrijeb, razine iz `TOUR_RANK_IDS`.
    Uz to i W-L na SVIM razinama (Challenger/Futures), jer igrac koji zivi od Challengera
    ima malo ATP meceva, sto je samo po sebi podatak."""
    ref = _d(as_of)
    tw = tl = aw = al = 0
    for m in safe_matches(matches, as_of, opponent_id):
        if _d(m.get("date")).year != ref.year:
            continue
        if safe_int(m.get("rid")) < MAIN_DRAW_MIN_ROUND_ID:
            continue
        won = _won(m, pid)
        aw += won
        al += not won
        if m.get("rank") in TOUR_RANK_IDS:
            tw += won
            tl += not won
    return {"year": ref.year, "tour_w": tw, "tour_l": tl, "all_w": aw, "all_l": al}


def vs_hand_record(matches: list, pid: str, hands: dict, as_of, opponent_id: str = "",
                   window_days: int = VS_HAND_WINDOW_DAYS) -> dict:
    """W-L protiv ljevaka i protiv desnjaka u zadnjih `window_days` dana (sve razine,
    kvalifikacije ukljucene — ovdje se mjeri stil protivnika, ne razina turnira).

    `hands` je {player_id: 'L'/'R'/''}. Protivnik nepoznate ruke broji se u `unknown`,
    ne pogadja se. Vraca {"L": {"w","l"}, "R": {"w","l"}, "unknown": n, "window_days": n}.
    """
    ref = _d(as_of)
    out = {"L": {"w": 0, "l": 0}, "R": {"w": 0, "l": 0}, "unknown": 0,
           "window_days": window_days}
    for m in safe_matches(matches, as_of, opponent_id):
        if (ref - _d(m.get("date"))).days > window_days:
            continue
        h = hands.get(str(_opp(m, pid)), "")
        if h not in ("L", "R"):
            out["unknown"] += 1
            continue
        out[h]["w" if _won(m, pid) else "l"] += 1
    return out


def gs_end_date(key: str, year: int, gs_starts: dict = None) -> datetime.date:
    """Datum zavrsetka Grand Slama. Za godine u `gs_starts` ({(kljuc, godina): pocetak})
    tocno (finale je 13. dan od pocetka, +1 rezerve); inace konzervativna procjena
    (kasnije je sigurnije: izdanje se tada broji tek kad je sigurno gotovo)."""
    start = (gs_starts or {}).get((key, year))
    if start:
        return _d(start) + datetime.timedelta(days=14)
    approx = {"AO": (2, 3), "RG": (6, 10), "WIM": (7, 16), "USO": (9, 15)}[key]
    return datetime.date(year, *approx)


def gs_record(records_by_slam: dict, as_of, gs_starts: dict = None) -> dict:
    """Koliko je Grand Slam POLUFINALA / FINALA / NASLOVA igrac imao PRIJE `as_of`.

    `records_by_slam` je {"AO": [...], "RG": [...], "WIM": [...], "USO": [...]} gdje je
    svaki redak iz `/atp/player/tournament-record/{pid}/{tid}` ({year, bestRoundId,
    losses, ...}). Broji se po `bestRoundId`, ne po oznaci — vidi `GS_SF_ROUND_ID`.
    Izdanje koje jos nije zavrsilo NE broji se — inace bi igrac u polufinalu US Opena
    vec imao "jedno GS polufinale vise" upravo zbog meca koji predvidjamo.
    """
    ref = _d(as_of)
    sf = f = titles = played = 0
    last_sf_year = None
    for key in GS_KEYS:
        for r in (records_by_slam or {}).get(key) or []:
            yr = safe_int(r.get("year"))
            if not yr or gs_end_date(key, yr, gs_starts) >= ref:
                continue
            rid = safe_int(r.get("bestRoundId"))
            if rid < MAIN_DRAW_MIN_ROUND_ID:
                continue            # kvalifikacije nisu nastup u glavnom zdrijebu
            played += 1
            if rid >= GS_SF_ROUND_ID:
                sf += 1
                last_sf_year = max(last_sf_year or 0, yr)
            if rid >= GS_F_ROUND_ID:
                f += 1
                if safe_int(r.get("losses")) == 0:
                    titles += 1
    return {"sf": sf, "f": f, "titles": titles, "main_draws": played,
            "last_sf_year": last_sf_year}


# ── dohvat (samo dnevni run; backfill ima vlastite kesirane podatke) ─────────────

_hands_cache: dict = {}
_hands_loaded = False
_live_hand_fetches = 0
HAND_FETCH_CAP = 150               # najvise ovoliko profila uzivo po runu


def load_hands() -> dict:
    global _hands_loaded
    if not _hands_loaded:
        try:
            with open(HANDS_FILE, encoding="utf-8") as fh:
                _hands_cache.update({str(k): v for k, v in json.load(fh).items()})
        except (OSError, ValueError):
            pass
        _hands_loaded = True
    return _hands_cache


def hand_of(pid, fetch_profile=None) -> str:
    """'L'/'R'/'' za igraca. Datoteka -> uzivo (strop `HAND_FETCH_CAP`) -> ''."""
    global _live_hand_fetches
    pid = str(pid or "")
    if not pid:
        return ""
    hands = load_hands()
    if pid in hands:
        return hands[pid]
    if fetch_profile is None or _live_hand_fetches >= HAND_FETCH_CAP:
        return ""
    _live_hand_fetches += 1
    info = fetch_profile(pid) or {}
    code = hand_code(info.get("plays") or info.get("hand"))
    hands[pid] = code
    return code


_history_cache: dict = {}


def past_matches(pid, df, days_back: int = VS_HAND_WINDOW_DAYS + 30, max_pages: int = 3) -> list:
    """Prosli mecevi igraca u obliku koji citaju funkcije gore. Prva stranica dolazi iz
    istog keša kao `get_recent_form` (nula dodatnih poziva); dodatne stranice samo dok ne
    pokriju `days_back`."""
    pid = str(pid or "")
    if not pid:
        return []
    if pid in _history_cache:
        return _history_cache[pid]
    cutoff = (datetime.date.today() - datetime.timedelta(days=days_back)).isoformat()
    out = []
    for page in range(1, max_pages + 1):
        games, has_next = df.get_past_matches_page(pid, page)
        if games is None:
            # Neuspjeli poziv NIJE "nema vise meceva" — inace bi sezona i omjer po ruci
            # tiho bili prebrojani premalo. `build` ovo biljezi kao `error`.
            raise RuntimeError(f"past-matches {pid} str. {page} nije dohvacena")
        for g in games:
            t = g.get("tournament") or {}
            out.append({"date": str(g.get("date", ""))[:10],
                        "p1": str(g.get("player1Id")), "p2": str(g.get("player2Id")),
                        "w": str(g.get("match_winner") or ""), "rank": t.get("rankId"),
                        "rid": g.get("roundId")})
        if not games or not has_next or str(games[-1].get("date", ""))[:10] < cutoff:
            break
    _history_cache[pid] = out
    return out


_gs_meta: dict = {}


def gs_meta(df) -> dict:
    """{kljuc: tid} i {(kljuc, godina): pocetak} za tekucu godinu, iz kalendara (1 poziv po runu)."""
    if _gs_meta:
        return _gs_meta
    year = datetime.date.today().year
    tids, starts = {}, {}
    data = df._get(f"/atp/tournament/calendar/{year}") or {}
    names = {"AO": "australian open", "RG": "french open", "WIM": "wimbledon", "USO": "u.s. open"}
    for row in data.get("data") or []:
        nm = str(row.get("name") or "").lower()
        if "junior" in nm:
            continue
        for key, frag in names.items():
            if nm.startswith(frag) and key not in tids:
                tids[key] = str(row.get("id"))
                starts[(key, year)] = str(row.get("date") or "")[:10]
    if len(tids) < 4:
        # Neuspjeli kalendar se NE pamti — inace bi jedan pad oborio GS podatke za cijeli run.
        return {"tids": tids, "starts": starts}
    _gs_meta.update({"tids": tids, "starts": starts})
    return _gs_meta


_gs_cache: dict = {}


def gs_records(pid, df) -> dict:
    """{"AO": [...], ...} iz `tournament-record` za sva cetiri Slama (4 poziva, kesirano)."""
    pid = str(pid or "")
    if not pid:
        return {}
    if pid in _gs_cache:
        return _gs_cache[pid]
    out = {}
    for key, tid in (gs_meta(df).get("tids") or {}).items():
        data = df._get(f"/atp/player/tournament-record/{pid}/{tid}")
        if data is None:                       # jedan ponovni pokusaj, pa greska
            time.sleep(2)
            data = df._get(f"/atp/player/tournament-record/{pid}/{tid}")
        if data is None:
            # NEUSPJEH != "nikad nije igrao Slam" — isti kvar je 26.09.2026 u backfillu
            # upisao prazne liste za 51 igraca dok nije uhvacen. Ne kesira se.
            raise RuntimeError(f"tournament-record {pid}/{key} nije dohvacen")
        out[key] = data.get("data") or []
    if len(out) < 4:
        raise RuntimeError(f"kalendar nije dao sva cetiri Slama ({sorted(out)})")
    _gs_cache[pid] = out
    return out


def build(pid, opp_id, own_plays, opp_plays, as_of, df) -> dict:
    """Sve tri varijable za jednog igraca u jednom mecu. Nikad ne baca — greska ide u
    polje `error`, jer ovo je dodatak i ne smije srusiti analizu meca."""
    try:
        hist = past_matches(pid, df)
        hands = {}
        for m in hist:
            o = str(_opp(m, pid))
            if o not in hands:
                hands[o] = hand_of(o, fetch_profile=df.get_player_info)
        return {
            "hand": hand_code(own_plays),
            "opp_hand": hand_code(opp_plays),
            "season": season_record(hist, pid, as_of, str(opp_id or "")),
            "vs_hand": vs_hand_record(hist, pid, hands, as_of, str(opp_id or "")),
            "gs": gs_record(gs_records(pid, df), as_of, gs_meta(df).get("starts")),
            "source": "live",
        }
    except Exception as e:           # pragma: no cover — obrambeno
        return {"error": str(e)[:120], "source": "live"}
