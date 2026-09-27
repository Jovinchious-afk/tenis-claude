# -*- coding: utf-8 -*-
"""Povijesni laboratorij — učitavanje i spajanje izvora (27.09.2026 11:40).

Pragovi su zapisani PRIJE ovog koda: revizije/2026-09-27/PRAGOVI_POVIJESNI_LAB.md.
Samo čita lokalne datoteke (.cache/tennis-data, .cache/tml). Ništa ne mijenja.

Izvori:
  tennis-data.co.uk  ATP 2022-2026, kvote pred početak meča (Pinnacle do ~rujna 2025,
                     prosjek kladionica Avg, Bet365). Korisnik ih je skinuo ručno (uvjeti
                     stranice zabranjuju automatsko skidanje).
  TML                ATP glavni ždrijeb 2000-2026 + Challengeri i kvalifikacije 2020-2026,
                     Sackmann format (ID igrača, runda, statistika, državljanstvo). Nema
                     točnog datuma meča, samo ponedjeljak turnira -> datum se procjenjuje po
                     rundi, osim za mečeve spojene s tennis-data (tamo je datum točan).
"""
import glob
import os
import re
import unicodedata
from bisect import bisect_left

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TD_DIR = os.path.join(ROOT, ".cache", "tennis-data")
TML_DIR = os.path.join(ROOT, ".cache", "tml")
LAB_CACHE = os.path.join(ROOT, ".cache", "lab")

ROUND_ORDER = {"Q1": -3, "Q2": -2, "Q3": -1, "RR": 0, "R128": 1, "R64": 2, "R32": 3,
               "R16": 4, "QF": 5, "SF": 6, "BR": 6, "F": 7}

# Procjena dana od ponedjeljka turnira do meča, po vrsti turnira i rundi. Greška ±3 dana
# utječe samo na "dane od zadnjeg meča" (K19) i prozor od 365 dana (CO).
_OFF_GS = {"R128": 1, "R64": 3, "R32": 5, "R16": 7, "QF": 9, "SF": 11, "F": 13}
_OFF_M = {"R128": 2, "R64": 3, "R32": 5, "R16": 7, "QF": 8, "SF": 9, "F": 10}
_OFF_STD = {"R128": 0, "R64": 0, "R32": 1, "R16": 3, "QF": 4, "SF": 5, "F": 6, "RR": 3, "BR": 5}
_OFF_Q = {"Q1": -2, "Q2": -1, "Q3": 0}

# Grad (tennis-data "Location") -> država (IOC) za K2 (domaći igrač).
LOCATION_IOC = {
    "'s-Hertogenbosch": "NED", "Acapulco": "MEX", "Adelaide": "AUS", "Almaty": "KAZ",
    "Antwerp": "BEL", "Athens": "GRE", "Atlanta": "USA", "Auckland": "NZL",
    "Banja Luka": "BIH", "Barcelona": "ESP", "Basel": "SUI", "Bastad": "SWE",
    "Beijing": "CHN", "Belgrade": "SRB", "Brisbane": "AUS", "Brussels": "BEL",
    "Bucharest": "ROU", "Buenos Aires": "ARG", "Chengdu": "CHN", "Cincinnati": "USA",
    "Cordoba": "ARG", "Dallas": "USA", "Delray Beach": "USA", "Doha": "QAT", "Dubai": "UAE",
    "Eastbourne": "GBR", "Estoril": "POR", "Florence": "ITA", "Geneva": "SUI", "Gijon": "ESP",
    "Gstaad": "SUI", "Halle": "GER", "Hamburg": "GER", "Hangzhou": "CHN", "Hong Kong": "HKG",
    "Houston": "USA", "Indian Wells": "USA", "Kitzbuhel": "AUT", "London": "GBR",
    "Los Cabos": "MEX", "Lyon": "FRA", "Madrid": "ESP", "Mallorca": "ESP", "Marrakech": "MAR",
    "Marseille": "FRA", "Melbourne": "AUS", "Metz": "FRA", "Miami": "USA", "Monte Carlo": "MON",
    "Montpellier": "FRA", "Montreal": "CAN", "Munich": "GER", "Napoli": "ITA",
    "New York": "USA", "Newport": "USA", "Nur-Sultan": "KAZ", "Paris": "FRA", "Pune": "IND",
    "Queens Club": "GBR", "Rio de Janeiro": "BRA", "Rome": "ITA", "Rotterdam": "NED",
    "San Diego": "USA", "Santiago": "CHI", "Seoul": "KOR", "Shanghai": "CHN", "Sofia": "BUL",
    "Stockholm": "SWE", "Stuttgart": "GER", "Sydney": "AUS", "Tel Aviv": "ISR", "Tokyo": "JPN",
    "Toronto": "CAN", "Turin": "ITA", "Umag": "CRO", "Vienna": "AUT", "Washington": "USA",
    "Winston-Salem": "USA", "Zhuhai": "CHN",
}


def letters(s) -> str:
    """Samo mala slova a-z (bez dijakritike, razmaka, crtica, apostrofa)."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s.lower())


def td_name_key(name: str):
    """'Bautista Agut R.' -> ('bautistaagut', 'r'); 'Cerundolo J.M.' -> ('cerundolo', 'j')."""
    toks = str(name or "").replace("\xa0", " ").split()
    init = [t for t in toks if t.endswith(".")]
    sur = [t for t in toks if not t.endswith(".")]
    if not sur:
        return letters(name), ""
    return letters(" ".join(sur)), (letters(init[0])[:1] if init else "")


def full_matches_td(full_letters: str, key) -> bool:
    """Puno ime (samo slova) odgovara tennis-data ključu (prezime, prvo slovo imena)?
    Radi za oba redoslijeda (Ime Prezime i Prezime Ime, npr. kineska imena)."""
    sur, ini = key
    if not sur or not full_letters:
        return False
    if full_letters.endswith(sur) and (not ini or full_letters[:1] == ini):
        return True
    if full_letters.startswith(sur) and len(full_letters) > len(sur) and \
            (not ini or full_letters[len(sur)] == ini):
        return True
    return False


def devig(a, b):
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return None
    if not (a > 1.0 and b > 1.0):
        return None
    return (1 / a) / (1 / a + 1 / b)


def load_td() -> pd.DataFrame:
    frames = []
    for f in sorted(glob.glob(os.path.join(TD_DIR, "*.xls*"))):
        frames.append(pd.read_excel(f))
    d = pd.concat(frames, ignore_index=True)
    d["Date"] = pd.to_datetime(d["Date"])
    d["Location"] = d["Location"].astype(str).str.strip()
    d = d[d["Comment"] == "Completed"].copy()
    d["p_ps"] = [devig(a, b) for a, b in zip(d["PSW"], d["PSL"])]
    d["p_avg"] = [devig(a, b) for a, b in zip(d["AvgW"], d["AvgL"])]
    d["p_b365"] = [devig(a, b) for a, b in zip(d["B365W"], d["B365L"])]
    # Poštena cijena pobjednika: Pinnacle gdje postoji, inače prosjek kladionica (PRAGOVI).
    d["p_fair"] = d["p_ps"].where(d["p_ps"].notna(), d["p_avg"])
    d["fair_src"] = ["PS" if pd.notna(x) else ("AVG" if pd.notna(y) else None)
                     for x, y in zip(d["p_ps"], d["p_avg"])]
    d = d[d["p_fair"].notna()].copy()
    d["wkey"] = d["Winner"].map(td_name_key)
    d["lkey"] = d["Loser"].map(td_name_key)
    d["half"] = (d["Date"].dt.year >= 2024).map({False: "P1", True: "P2"})
    d["country"] = d["Location"].map(LOCATION_IOC)
    return d.reset_index(drop=True)


def _approx_offset(level: str, rnd: str, draw: int) -> int:
    if rnd in _OFF_Q:
        return _OFF_Q[rnd]
    if level == "G":
        return _OFF_GS.get(rnd, 7)
    if level == "M" and (draw or 0) >= 56:
        return _OFF_M.get(rnd, 5)
    if level == "D":
        return 1
    return _OFF_STD.get(rnd, 3)


def load_tml() -> pd.DataFrame:
    frames = []
    for y in range(2000, 2027):
        f = os.path.join(TML_DIR, f"{y}.csv")
        if os.path.exists(f):
            t = pd.read_csv(f, low_memory=False)
            t["src"] = "main"
            frames.append(t)
    for y in range(2020, 2027):
        for f, src in ((os.path.join(TML_DIR, f"{y}_challenger.csv"), "ch"),
                       (os.path.join(TML_DIR, "atp_quali", f"{y}_atp_quali.csv"), "q")):
            if os.path.exists(f):
                t = pd.read_csv(f, low_memory=False)
                t["src"] = src
                frames.append(t)
    t = pd.concat(frames, ignore_index=True)
    t["tourney_date"] = pd.to_datetime(t["tourney_date"].astype(str), format="%Y%m%d", errors="coerce")
    t = t[t["tourney_date"].notna()].copy()
    t["round"] = t["round"].astype(str)
    t["rord"] = t["round"].map(ROUND_ORDER).fillna(0)
    t["tourney_level"] = t["tourney_level"].astype(str)
    # ZAMKA NAĐENA 27.09.2026 11:40: u TML-u za 2026. (74% turnira glavnog ždrijeba, 6%
    # kvalifikacija) `tourney_date` NIJE ponedjeljak turnira nego DATUM MEČA (US Open 2026:
    # QF 09.09., SF 11.09., F 13.09.). Ostale godine su čiste. Posljedica bez popravka:
    # polufinale istog Slama brojilo se kao "raniji" GS (Zverev 13 umjesto 12), a procjena
    # datuma dodavala je pomak runde na već točan datum. Zato: početak turnira = najraniji
    # datum u turniru, a gdje turnir ima više datuma, datum retka je točan datum meča.
    grp = t.groupby(["src", "tourney_id"])["tourney_date"]
    t["t_start"] = grp.transform("min")
    t["per_match_date"] = grp.transform("nunique") > 1
    t["approx_date"] = [td if pm else td + pd.Timedelta(days=_approx_offset(lv, r, dz))
                        for td, pm, lv, r, dz in zip(t["tourney_date"], t["per_match_date"],
                                                     t["tourney_level"], t["round"],
                                                     t["draw_size"].fillna(0))]
    t["wl"] = t["winner_name"].map(letters)
    t["ll"] = t["loser_name"].map(letters)
    t["tname"] = t["tourney_name"].map(letters)
    return t.reset_index(drop=True)


def join_td_tml(td: pd.DataFrame, tml: pd.DataFrame) -> pd.DataFrame:
    """Svakom tennis-data meču pridruži redak TML glavnog ždrijeba (isti par, isti
    pobjednik, turnir koji počinje 7 dana prije do 3 dana nakon... tj. datum meča je
    unutar [ponedjeljak turnira - 3, + 17])."""
    main = tml[tml["src"] == "main"]
    by_week = {}
    for idx, tdate in zip(main.index, main["tourney_date"]):
        by_week.setdefault(tdate, []).append(idx)
    weeks = sorted(by_week)
    wl, ll = main["wl"].to_dict(), main["ll"].to_dict()
    adate = main["approx_date"].to_dict()

    def relaxed(full, key):
        # Dugo prezime koje tennis-data skraćuje ili piše drugim imenom ("Mpetshi G." =
        # Giovanni Mpetshi Perricard, "Barrios M." = Tomas Barrios Vera): prezime od 5+ slova
        # sadržano u punom imenu. Samo kad strogo pravilo ne nađe nikoga; par + datum štite.
        return full_matches_td(full, key) or (len(key[0]) >= 5 and key[0] in full)

    out = []
    for date, wk, lk in zip(td["Date"], td["wkey"], td["lkey"]):
        lo = bisect_left(weeks, date - pd.Timedelta(days=17))
        hi = bisect_left(weeks, date + pd.Timedelta(days=4))
        pool = [idx for w in weeks[lo:hi] for idx in by_week[w]]
        cand = [i for i in pool if full_matches_td(wl[i], wk) and full_matches_td(ll[i], lk)]
        if not cand:
            cand = [i for i in pool if relaxed(wl[i], wk) and relaxed(ll[i], lk)]
        if len(cand) > 1:
            # Isti par dva tjedna zaredom (Sydney pa Australian Open): uzmi turnir čiji je
            # procijenjeni datum meča najbliži stvarnom.
            cand.sort(key=lambda i: abs((adate[i] - date).days))
        out.append(cand[0] if cand else None)
    td = td.copy()
    td["tml_idx"] = out
    return td


if __name__ == "__main__":
    os.makedirs(LAB_CACHE, exist_ok=True)
    td = load_td()
    tml = load_tml()
    td = join_td_tml(td, tml)
    n = len(td)
    ok = td["tml_idx"].notna().sum()
    print(f"tennis-data odigranih s poštenom cijenom: {n}  | izvor cijene: {td['fair_src'].value_counts().to_dict()}")
    print(f"spojeno s TML: {ok} ({100*ok/n:.1f}%) | nespojeno: {n-ok}")
    miss = td[td["tml_idx"].isna()]
    print("primjeri nespojenih:")
    print(miss[["Date", "Tournament", "Winner", "Loser"]].head(25).to_string())
    td.to_pickle(os.path.join(LAB_CACHE, "td_joined.pkl"))
    tml.to_pickle(os.path.join(LAB_CACHE, "tml.pkl"))
