# -*- coding: utf-8 -*-
"""Trzisni konsenzus s The Odds API — cijene iz desetaka kladionica, razvigane i spojene.

UVEDENO 15.08.2026 10:12 (korisnikova odluka; povukao je vlastito pravilo da kvota ne smije
biti prediktivna varijabla).

ZASTO OVO POSTOJI — jednom recenicom: dvije revizije (13.08. n=84, 15.08. n=126) pokazale su
da **nemamo prednost pred trzistem** (61,1% naspram 62,4% postene trzisne vjerojatnosti,
razlika -1,3pp), pa je gubitak na listicima posljedica marze, ne loseg tenisa. Ako prednosti
nema u procjeni, jedino preostalo mjesto gdje moze biti je **razlika u cijeni medju
kladionicama**: ne moramo biti bolji od trzista, dovoljno je da SuperSport promasi u odnosu
na ostale.

STO OVAJ MODUL RADI, A STO NE:
  - RADI: dohvaca cijene mnogih kladionica, mice marzu i racuna konsenzusnu vjerojatnost.
  - NE RADI: ne bira pickove i ne dira prompt. Konzument odlucuje sto s brojkama.

CIJENA POZIVA (provjereno na stvarnim zaglavljima 15.08.2026):
  - `/sports`                    = 0 kredita (besplatno)
  - `/sports/{key}/odds`         = broj trzista x broj regija  (nama: 1 x len(regions))
  - `/historical/.../odds`       = 10 x broj trzista x broj regija
Zaglavlja `x-requests-remaining` / `x-requests-last` citaju se i zapisuju u `LAST_USAGE`.

TENIS JE JEDAN KLJUC PO TURNIRU (`tennis_atp_cincinnati_open`, ...), ne jedan za cijeli ATP —
zato `active_tennis_keys()` prvo pita besplatni `/sports` koji su turniri aktivni.
"""
import os
import statistics
from typing import Optional

import requests

ODDS_BASE = "https://api.the-odds-api.com/v4"

# Regije odredjuju KOJE kladionice dobivamo, a svaka regija kosta jedan kredit po pozivu.
# "eu,uk,us" je izabrano 15.08.2026 jer je provjereno da tek "us" donosi **Pinnacle**, a
# "uk"/"eu" donose **Betfair exchange** i **Matchbook** — jedine ostre reference u ponudi.
# Bez njih bi konsenzus bio prosjek mekih kladionica, tj. prosjek istih gresaka.
DEFAULT_REGIONS = "eu,uk,us"

# Ostre kladionice/burze, poredane po povjerenju. Pinnacle je industrijski standard za
# tocnu cijenu (zivi od volumena, ne od marze); Betfair/Matchbook su burze — cijena je
# stvarni novac, ne ponuda kuce. Koriste se kao ZASEBNA procjena uz medijan svih.
SHARP_BOOKS = ("pinnacle", "betfair_ex_eu", "betfair_ex_uk", "betfair_ex_au",
               "matchbook", "smarkets")

LAST_USAGE = {"remaining": None, "used": None, "last_cost": None}


def _key() -> str:
    return os.environ.get("ODDS_API_KEY", "")


def _request(url: str, params: dict) -> Optional[object]:
    """Poziv uz citanje zaglavlja o potrosnji. Vraca None umjesto da puca."""
    if not _key():
        print("  [market] ODDS_API_KEY nije postavljen — preskacem.")
        return None
    p = dict(params)
    p["apiKey"] = _key()
    try:
        r = requests.get(url, params=p, timeout=30)
    except Exception as e:
        print(f"  [market] mrezna greska: {str(e)[:90]}")
        return None
    for hdr, slot in (("x-requests-remaining", "remaining"),
                      ("x-requests-used", "used"), ("x-requests-last", "last_cost")):
        v = r.headers.get(hdr)
        if v is not None:
            try:
                LAST_USAGE[slot] = int(float(v))
            except ValueError:
                pass
    if r.status_code != 200:
        print(f"  [market] HTTP {r.status_code}: {r.text[:150]}")
        return None
    try:
        return r.json()
    except ValueError:
        return None


def active_tennis_keys(tour: str = "atp") -> list:
    """Aktivni turnirski kljucevi za zadanu turneju. BESPLATAN poziv (0 kredita)."""
    data = _request(f"{ODDS_BASE}/sports", {"all": "true"})
    if not isinstance(data, list):
        return []
    pref = f"tennis_{tour.lower()}_"
    return [s["key"] for s in data
            if isinstance(s, dict) and s.get("active") and str(s.get("key", "")).startswith(pref)]


def fetch_odds(sport_key: str, regions: str = DEFAULT_REGIONS,
               historical_ts: str = None) -> list:
    """Cijene za jedan turnir. `historical_ts` (ISO UTC) prebacuje na povijesnu snimku.

    Povijesne snimke postoje otprilike svakih 5 minuta; API vraca najblizu i uz nju
    `previous_timestamp`/`next_timestamp`. POZOR: povijesni poziv je 10x skuplji.
    """
    params = {"regions": regions, "markets": "h2h", "oddsFormat": "decimal"}
    if historical_ts:
        params["date"] = historical_ts
        data = _request(f"{ODDS_BASE}/historical/sports/{sport_key}/odds", params)
        if isinstance(data, dict):
            return data.get("data") or []
        return []
    data = _request(f"{ODDS_BASE}/sports/{sport_key}/odds", params)
    return data if isinstance(data, list) else []


def devig(o1: float, o2: float) -> tuple:
    """Dvosmjerne kvote -> poštene vjerojatnosti (multiplikativno micanje marze).

    Multiplikativna metoda (svaka implicirana vjerojatnost podijeljena zbrojem) je
    standard i dovoljna za dvosmjerno trziste. Postoje finije (Shin, potencijska), ali
    se razlikuju tek na ekstremnim kvotama i ne bi promijenile nijednu nasu odluku.
    """
    if not o1 or not o2 or o1 <= 1.0 or o2 <= 1.0:
        return None, None
    i1, i2 = 1.0 / o1, 1.0 / o2
    t = i1 + i2
    return i1 / t, i2 / t


def consensus(event: dict) -> dict:
    """Iz jednog dogadjaja izvlaci konsenzusnu vjerojatnost za `home_team`.

    Vraca:
      p_median   — medijan razviganih vjerojatnosti PREKO SVIH kladionica (robustan na
                   jednu razbaruseneu kucu; medijan namjerno, ne prosjek)
      p_sharp    — ista mjera, ali samo preko ostrih kuca/burzi (Pinnacle, Betfair...)
      p_best     — p_sharp ako postoji, inace p_median. Ovo je preporucena procjena.
      n_books    — koliko je kladionica uslo u medijan
      overround  — prosjecna marza u ponudi (koliko kuce naplacuju)
    """
    home, away = event.get("home_team", ""), event.get("away_team", "")
    all_p, sharp_p, overs = [], [], []
    for bm in event.get("bookmakers", []) or []:
        for mk in bm.get("markets", []) or []:
            if mk.get("key") != "h2h":
                continue
            prices = {}
            for out in mk.get("outcomes", []) or []:
                prices[out.get("name")] = out.get("price")
            o1, o2 = prices.get(home), prices.get(away)
            p1, _ = devig(o1, o2)
            if p1 is None:
                continue
            all_p.append(p1)
            overs.append(1.0 / o1 + 1.0 / o2 - 1.0)
            if bm.get("key") in SHARP_BOOKS:
                sharp_p.append(p1)
    if not all_p:
        return {}
    p_med = statistics.median(all_p)
    p_shp = statistics.median(sharp_p) if sharp_p else None
    return {
        "home": home, "away": away,
        "commence_time": event.get("commence_time"),
        "p_median": round(p_med, 5),
        "p_sharp": round(p_shp, 5) if p_shp is not None else None,
        "p_best": round(p_shp if p_shp is not None else p_med, 5),
        "n_books": len(all_p), "n_sharp": len(sharp_p),
        "overround": round(statistics.median(overs), 5) if overs else None,
        "spread": round(max(all_p) - min(all_p), 5),
    }


def _toks(name: str) -> frozenset:
    """Tokeni imena za uparivanje. SuperSport pise 'Prezime Ime', a The Odds API
    'Ime Prezime' — poredak se zato NE smije koristiti (provjereno 15.08.2026: uparivanje
    po zadnjoj rijeci dalo je 0 od 10 parova). Uparuje se presjekom tokena."""
    from agent.data_fetcher import _strip_diacritics
    s = _strip_diacritics(str(name or "")).lower().replace("-", " ")
    return frozenset(t for t in s.split() if len(t) > 2)


def _same_player(a: str, b: str) -> bool:
    return bool(_toks(a) & _toks(b))


def find_for_pair(index: list, player1: str, player2: str) -> dict:
    """Trazi konsenzus za nas par. Vraca {} ili konsenzus preokrenut tako da se
    `p_best` odnosi na NASEG player1."""
    for c in index or []:
        if _same_player(c.get("home"), player1) and _same_player(c.get("away"), player2):
            return c
        if _same_player(c.get("home"), player2) and _same_player(c.get("away"), player1):
            f = dict(c)
            f["home"], f["away"] = c["away"], c["home"]
            for k in ("p_median", "p_sharp", "p_best"):
                f[k] = (1.0 - c[k]) if c.get(k) is not None else None
            f["flipped"] = True
            return f
    return {}


def consensus_index(tour: str = "atp", regions: str = DEFAULT_REGIONS) -> list:
    """Konsenzus za sve aktivne turnire zadane turneje. Trosak: len(regions) po turniru."""
    out = []
    for key in active_tennis_keys(tour):
        for ev in fetch_odds(key, regions=regions):
            c = consensus(ev)
            if c:
                c["sport_key"] = key
                out.append(c)
    return out


def flatten_lines(events: list, captured_utc: str = None) -> list:
    """Svaka kladionica -> jedan redak, za tablicu `market_lines`.

    ZASTO SE CUVA SVAKA KUCA, A NE SAMO MEDIJAN (korisnikova ideja 15.08.2026):
    medijan skriva TKO odstupa, a to je vjerojatno informativnije od toga KOLIKO se
    odstupa. Pinnacle koji ide ispod SuperSporta nije isto sto i jedna meka kuca koja
    kasni s azuriranjem. Dohvat je ionako vec placen — sve kuce dolaze u istom odgovoru,
    pa je biljezenje besplatno. Ne moze se analizirati ono sto se nije zapisalo.

    UPOZORENJE ZA KASNIJU ANALIZU (zapisano namjerno, prije nego podaci postoje):
    ovdje ce biti ~46 kladionica. Ako se kasnije trazi "koja kuca predvidja pobjednika",
    to je 46 istovremenih testova i **neka ce izgledati znacajno cisto slucajno** — na
    p<0,05 ocekuje se 2-3 laznih. U ovoj sesiji su tri takva nalaza vec pala na provjeri
    izvan uzorka (pojas kvota, prag 63%, favorit-autsajder pristranost). Pravilo prije
    ijednog zakljucka: hipotezu zapisati PRIJE gledanja, podijeliti uzorak na pola i
    traziti da se drzi u obje polovice.
    """
    import datetime
    now = captured_utc or datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for e in events or []:
        home, away = e.get("home_team", ""), e.get("away_team", "")
        start = e.get("commence_time")
        hrs = None
        if start:
            try:
                st = datetime.datetime.fromisoformat(str(start).replace("Z", "+00:00"))
                nw = datetime.datetime.fromisoformat(now.replace("Z", "+00:00"))
                hrs = round((st - nw).total_seconds() / 3600.0, 2)
            except ValueError:
                pass
        for bm in e.get("bookmakers", []) or []:
            for mk_ in bm.get("markets", []) or []:
                if mk_.get("key") != "h2h":
                    continue
                pr = {o.get("name"): o.get("price") for o in mk_.get("outcomes", []) or []}
                o1, o2 = pr.get(home), pr.get(away)
                p1, _ = devig(o1, o2)
                if p1 is None:
                    continue
                rows.append({
                    "captured_at": now,
                    "event_id": e.get("id"),
                    "sport_key": e.get("sport_key") or "",
                    "commence_time": start,
                    # Koliko je sati ostalo do pocetka — zamjenjuje oznaku "open/close".
                    # Isti mec vidimo vise puta (danas kao sutrasnji, sutra kao danasnji),
                    # pa se pomak cijene mjeri po ovome, bez rucnog oznacavanja faze.
                    "hours_to_start": hrs,
                    "player1": home, "player2": away,
                    "bookmaker": bm.get("key"),
                    "odds_p1": o1, "odds_p2": o2,
                    "p1_devig": round(p1, 6),
                    "is_sharp": bm.get("key") in SHARP_BOOKS,
                })
    return rows


def expected_value(p_true: float, odds_offered: float) -> float:
    """Ocekivani prinos po jedinici uloga: p x kvota - 1. Pozitivno = isplativa oklada.

    Ovo je JEDINI broj po kojem se od 15.08.2026 rangira selekcija. Zamjenjuje rangiranje
    po modelovoj pouzdanosti, koje je prestalo razlikovati bilo sto otkad strop od 64%
    gura 58% pickova na istu vrijednost (izmjereno 15.08.: 23 od 40 analiza na tocno 64%).
    """
    if not p_true or not odds_offered or odds_offered <= 1.0:
        return None
    return p_true * odds_offered - 1.0
