# -*- coding: utf-8 -*-
"""Revizija 01.11.2026 — LAB: korisnikove točke 1, 2, 5, 6, 9 i 7 (obitelji C, N, G, T; opis R,
tablica nacionalnosti, statistika "ubojice diva", postojanost tie-breakova) naspram poštene cijene
(01.11.2026 13:18).

Pragovi i definicije: revizije/2026-11-01/PRAGOVI_REVIZIJA_2026-11-01.md, točka E (13:05).
Holm posebno u obitelji C (11), N (3), G (4), T (3); uz to P × 109 (88 ranijih testova na istom
uzorku + 21 današnjih).

Podaci: povijesni laboratorij (.cache/lab/td_joined.pkl + tml.pkl; tennis-data + TML, ATP
2022 – 06.10.2026, poštena cijena = Pinnacle bez marže, inače prosjek kladionica). ELO prije meča
iz `revizije/2026-10-18/skripte/b_lab.compute_elo` (538-stil, TML 2000–2026, sve razine).

ZAŠTITA OD CURENJA: igračevi zapisi slažu se po (početak turnira, runda); u profil, H2H, zadnja 3
meča, tie-breakove, odmor i prethodni turnir ulaze SAMO zapisi s datumom STROGO prije datuma ovog
meča; H2H ne broji mečeve istog turnira; N3 koristi strogo ranije godine i isključuje samog igrača;
G gleda prethodni meč glavnog ždrijeba istog turnira (prije ovog po definiciji).

Gradovi: prethodni turnir ima grad samo ako je ATP turnir iz tennis-data (2022+) — inače je pomak
vremenske zone prazan (pragovi, točka E-C). Koordinate i vremenske zone gradova, kopnene granice
država domaćina i glavni gradovi zapisani su ovdje PRIJE računanja.

Samo čita. Izlaz: ispis + .cache/rev_2026-11-01/lab_nos_rezultati.json i lab_nos_features.pkl
    python revizije/2026-11-01/skripte/r_lab_nos.py
"""
import json
import math
import os
import re
import sys
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np
import pandas as pd
import pytz

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "revizije", "2026-10-18", "skripte"))
from b_lab import (F_1IN, F_1W, F_2W, F_BPF, F_BPS, F_DATE, F_DF, F_LVL, F_OELO, F_OK, F_OPP,  # noqa: E402
                   F_OSV, F_O1W, F_O2W, F_RORD, F_SG, F_SRC, F_SURF, F_SV, F_TID, F_TML, F_TS, F_WON,
                   agg, compute_elo, match_tpw, surf_of)
from r_lab3 import num, sets_games, stats  # noqa: E402

LAB = os.path.join(ROOT, ".cache", "lab")
OUTD = os.path.join(ROOT, ".cache", "rev_2026-11-01")
N_TOTAL_TESTS = 109

# dodatna polja zapisa (iza polja iz b_lab.py, koja završavaju na F_OELO = 32)
F_MELO, F_ORANK, F_TBW, F_TBL, F_TNAME, F_IOC = range(33, 39)

# ------------------------------------------------------------------ gradovi (zapisano prije računanja)
CITY = {  # tennis-data Location -> (lat, lon, IANA zona)
    "'s-Hertogenbosch": (51.69, 5.30, "Europe/Amsterdam"), "Acapulco": (16.85, -99.82, "America/Mexico_City"),
    "Adelaide": (-34.93, 138.60, "Australia/Adelaide"), "Almaty": (43.24, 76.89, "Asia/Almaty"),
    "Antwerp": (51.22, 4.40, "Europe/Brussels"), "Athens": (37.98, 23.73, "Europe/Athens"),
    "Atlanta": (33.75, -84.39, "America/New_York"), "Auckland": (-36.85, 174.76, "Pacific/Auckland"),
    "Banja Luka": (44.77, 17.19, "Europe/Sarajevo"), "Barcelona": (41.39, 2.17, "Europe/Madrid"),
    "Basel": (47.56, 7.59, "Europe/Zurich"), "Bastad": (56.43, 12.85, "Europe/Stockholm"),
    "Beijing": (39.90, 116.41, "Asia/Shanghai"), "Belgrade": (44.79, 20.45, "Europe/Belgrade"),
    "Brisbane": (-27.47, 153.03, "Australia/Brisbane"), "Brussels": (50.85, 4.35, "Europe/Brussels"),
    "Bucharest": (44.43, 26.10, "Europe/Bucharest"), "Buenos Aires": (-34.60, -58.38, "America/Argentina/Buenos_Aires"),
    "Chengdu": (30.57, 104.07, "Asia/Shanghai"), "Cincinnati": (39.10, -84.51, "America/New_York"),
    "Cordoba": (-31.42, -64.18, "America/Argentina/Cordoba"), "Dallas": (32.78, -96.80, "America/Chicago"),
    "Delray Beach": (26.46, -80.07, "America/New_York"), "Doha": (25.29, 51.53, "Asia/Qatar"),
    "Dubai": (25.20, 55.27, "Asia/Dubai"), "Eastbourne": (50.77, 0.28, "Europe/London"),
    "Estoril": (38.70, -9.40, "Europe/Lisbon"), "Florence": (43.77, 11.26, "Europe/Rome"),
    "Geneva": (46.20, 6.14, "Europe/Zurich"), "Gijon": (43.53, -5.66, "Europe/Madrid"),
    "Gstaad": (46.47, 7.29, "Europe/Zurich"), "Halle": (52.06, 8.36, "Europe/Berlin"),
    "Hamburg": (53.55, 9.99, "Europe/Berlin"), "Hangzhou": (30.27, 120.15, "Asia/Shanghai"),
    "Hong Kong": (22.32, 114.17, "Asia/Hong_Kong"), "Houston": (29.76, -95.37, "America/Chicago"),
    "Indian Wells": (33.72, -116.31, "America/Los_Angeles"), "Kitzbuhel": (47.45, 12.39, "Europe/Vienna"),
    "London": (51.51, -0.13, "Europe/London"), "Los Cabos": (22.89, -109.92, "America/Mazatlan"),
    "Lyon": (45.76, 4.84, "Europe/Paris"), "Madrid": (40.42, -3.70, "Europe/Madrid"),
    "Mallorca": (39.57, 2.65, "Europe/Madrid"), "Marrakech": (31.63, -8.01, "Africa/Casablanca"),
    "Marseille": (43.30, 5.37, "Europe/Paris"), "Melbourne": (-37.81, 144.96, "Australia/Melbourne"),
    "Metz": (49.12, 6.18, "Europe/Paris"), "Miami": (25.76, -80.19, "America/New_York"),
    "Monte Carlo": (43.74, 7.42, "Europe/Monaco"), "Montpellier": (43.61, 3.88, "Europe/Paris"),
    "Montreal": (45.50, -73.57, "America/Toronto"), "Munich": (48.14, 11.58, "Europe/Berlin"),
    "Napoli": (40.85, 14.27, "Europe/Rome"), "New York": (40.71, -74.01, "America/New_York"),
    "Newport": (41.49, -71.31, "America/New_York"), "Nur-Sultan": (51.17, 71.45, "Asia/Almaty"),
    "Paris": (48.86, 2.35, "Europe/Paris"), "Pune": (18.52, 73.86, "Asia/Kolkata"),
    "Queens Club": (51.49, -0.21, "Europe/London"), "Rio de Janeiro": (-22.91, -43.17, "America/Sao_Paulo"),
    "Rome": (41.90, 12.50, "Europe/Rome"), "Rotterdam": (51.92, 4.48, "Europe/Amsterdam"),
    "San Diego": (32.72, -117.16, "America/Los_Angeles"), "Santiago": (-33.45, -70.67, "America/Santiago"),
    "Seoul": (37.57, 126.98, "Asia/Seoul"), "Shanghai": (31.23, 121.47, "Asia/Shanghai"),
    "Sofia": (42.70, 23.32, "Europe/Sofia"), "Stockholm": (59.33, 18.07, "Europe/Stockholm"),
    "Stuttgart": (48.78, 9.18, "Europe/Berlin"), "Sydney": (-33.87, 151.21, "Australia/Sydney"),
    "Tel Aviv": (32.09, 34.78, "Asia/Jerusalem"), "Tokyo": (35.68, 139.69, "Asia/Tokyo"),
    "Toronto": (43.65, -79.38, "America/Toronto"), "Turin": (45.07, 7.69, "Europe/Rome"),
    "Umag": (45.43, 13.52, "Europe/Zagreb"), "Vienna": (48.21, 16.37, "Europe/Vienna"),
    "Washington": (38.91, -77.04, "America/New_York"), "Winston-Salem": (36.10, -80.24, "America/New_York"),
    "Zhuhai": (22.27, 113.58, "Asia/Shanghai"),
}

CAPITAL = {  # IOC -> glavni grad (lat, lon)
    "USA": (38.90, -77.04), "FRA": (48.86, 2.35), "ITA": (41.90, 12.50), "ESP": (40.42, -3.70),
    "ARG": (-34.60, -58.38), "AUS": (-35.28, 149.13), "RUS": (55.76, 37.62), "GER": (52.52, 13.40),
    "SRB": (44.79, 20.45), "GBR": (51.51, -0.13), "CAN": (45.42, -75.70), "CZE": (50.08, 14.44),
    "NED": (52.37, 4.90), "CHI": (-33.45, -70.67), "KAZ": (51.17, 71.45), "JPN": (35.68, 139.69),
    "BEL": (50.85, 4.35), "CHN": (39.90, 116.41), "HUN": (47.50, 19.04), "POL": (52.23, 21.01),
    "CRO": (45.81, 15.98), "GRE": (37.98, 23.73), "POR": (38.72, -9.14), "NOR": (59.91, 10.75),
    "SUI": (46.95, 7.45), "AUT": (48.21, 16.37), "BRA": (-15.79, -47.88), "DEN": (55.68, 12.57),
    "BUL": (42.70, 23.32), "FIN": (60.17, 24.94), "SVK": (48.15, 17.11), "SWE": (59.33, 18.07),
    "PER": (-12.05, -77.04), "COL": (4.71, -74.07), "BIH": (43.86, 18.41), "BLR": (53.90, 27.57),
    "GEO": (41.72, 44.79), "KOR": (37.57, 126.98), "RSA": (-25.75, 28.19), "MON": (43.74, 7.42),
    "BOL": (-16.50, -68.15), "MDA": (47.01, 28.86), "TPE": (25.03, 121.57), "IND": (28.61, 77.21),
    "LTU": (54.69, 25.28), "HKG": (22.32, 114.17), "PAR": (-25.26, -57.58), "MEX": (19.43, -99.13),
    "ECU": (-0.18, -78.47), "UKR": (50.45, 30.52), "JOR": (31.95, 35.93), "SLO": (46.06, 14.51),
    "MAR": (34.02, -6.84), "LBN": (33.89, 35.50), "TUN": (36.81, 10.18), "URU": (-34.90, -56.16),
    "TUR": (39.93, 32.86), "EST": (59.44, 24.75), "ROU": (44.43, 26.10), "NZL": (-41.29, 174.78),
    "ISR": (31.77, 35.21), "UZB": (41.30, 69.24), "DOM": (18.49, -69.93), "BAR": (13.10, -59.62),
    "ZIM": (-17.83, 31.05), "THA": (13.76, 100.50), "LUX": (49.61, 6.13), "QAT": (25.29, 51.53),
    "LAT": (56.95, 24.11), "CYP": (35.19, 33.38), "MNE": (42.44, 19.26), "MKD": (41.99, 21.43),
    "ALB": (41.33, 19.82), "IRL": (53.35, -6.26), "ARM": (40.18, 44.51), "AZE": (40.41, 49.87),
    "EGY": (30.04, 31.24), "KSA": (24.71, 46.68), "UAE": (24.45, 54.38), "VEN": (10.49, -66.88),
    "PHI": (14.60, 120.98), "INA": (-6.21, 106.85), "MAS": (3.14, 101.69), "SGP": (1.35, 103.82),
    "VIE": (21.03, 105.85), "PAK": (33.68, 73.05), "IRI": (35.69, 51.39), "CUB": (23.11, -82.37),
    "PUR": (18.47, -66.11), "ESA": (13.69, -89.19), "GUA": (14.63, -90.51), "CRC": (9.93, -84.08),
    "BAH": (25.04, -77.35), "JAM": (18.02, -76.80), "TRI": (10.66, -61.51), "NGR": (9.08, 7.40),
    "KEN": (-1.29, 36.82), "MLT": (35.90, 14.51), "AND": (42.51, 1.52), "SMR": (43.94, 12.45),
    "LIE": (47.14, 9.52), "ISL": (64.15, -21.94), "KGZ": (42.87, 74.59), "TJK": (38.56, 68.77),
}

BORDERS = {  # država domaćin -> države s kopnenom granicom (IOC)
    "NED": {"BEL", "GER"}, "MEX": {"USA", "GUA", "BIZ"}, "AUS": set(), "NZL": set(), "JPN": set(),
    "KAZ": {"RUS", "CHN", "KGZ", "UZB", "TKM"}, "BEL": {"FRA", "LUX", "GER", "NED"},
    "GRE": {"ALB", "MKD", "BUL", "TUR"}, "USA": {"CAN", "MEX"}, "BIH": {"CRO", "SRB", "MNE"},
    "ESP": {"POR", "FRA", "AND"}, "SUI": {"GER", "FRA", "ITA", "AUT", "LIE"}, "SWE": {"NOR", "FIN"},
    "CHN": {"KAZ", "KGZ", "TJK", "AFG", "PAK", "IND", "NEP", "BHU", "MYA", "LAO", "VIE", "PRK", "MGL", "RUS", "HKG"},
    "SRB": {"HUN", "ROU", "BUL", "MKD", "MNE", "BIH", "CRO"}, "ROU": {"HUN", "SRB", "BUL", "MDA", "UKR"},
    "ARG": {"CHI", "BOL", "PAR", "BRA", "URU"}, "CHI": {"ARG", "PER", "BOL"}, "QAT": {"KSA"},
    "UAE": {"KSA", "OMA"}, "GBR": {"IRL"}, "POR": {"ESP"}, "ITA": {"FRA", "SUI", "AUT", "SLO", "SMR"},
    "GER": {"DEN", "POL", "CZE", "AUT", "SUI", "FRA", "LUX", "BEL", "NED"}, "HKG": {"CHN"},
    "MAR": {"ALG"}, "FRA": {"BEL", "LUX", "GER", "SUI", "ITA", "MON", "ESP", "AND"}, "MON": {"FRA"},
    "CAN": {"USA"}, "IND": {"PAK", "CHN", "NEP", "BHU", "BAN", "MYA"},
    "BRA": {"ARG", "URU", "PAR", "BOL", "PER", "COL", "VEN", "GUY", "SUR"}, "KOR": {"PRK"},
    "BUL": {"ROU", "SRB", "MKD", "GRE", "TUR"}, "ISR": {"LBN", "SYR", "JOR", "EGY"},
    "AUT": {"GER", "CZE", "SVK", "HUN", "SLO", "ITA", "SUI", "LIE"}, "CRO": {"SLO", "HUN", "SRB", "BIH", "MNE"},
}
IOC_FIX = {"PRT": "POR"}
TB_SET = re.compile(r"^(\d+)-(\d+)")


def letters(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s.lower())


def tkey(name):
    """Isti turnir kroz godine: slova imena bez 'masters' (Monte Carlo = Monte Carlo Masters)."""
    k = letters(name).replace("masters", "")
    return {"winstonsalem": "winstonsalem", "astana": "nursultan"}.get(k, k)


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


_TZC = {}


def utc_off(city, d):
    key = (city, d.date())
    if key not in _TZC:
        tz = pytz.timezone(CITY[city][2])
        _TZC[key] = tz.localize(datetime(d.year, d.month, d.day, 12)).utcoffset().total_seconds() / 3600.0
    return _TZC[key]


def tb_counts(score):
    """(TB setovi koje je dobio POBJEDNIK meča, TB setovi koje je dobio PORAŽENI) iz zapisa rezultata."""
    w = l_ = 0
    for tok in str(score or "").split():
        m = TB_SET.match(tok)
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if {a, b} == {6, 7}:
            if a > b:
                w += 1
            else:
                l_ += 1
    return w, l_


# ------------------------------------------------------------------ povijest (proširena)
def build_history_ext(tml, exact, pre):
    hist = defaultdict(list)
    for idx, r in zip(tml.index, tml.itertuples(index=False)):
        d = exact.get(idx, r.approx_date)
        sw, sl, gw, gl = sets_games(r.score)
        tbw, tbl = tb_counts(r.score)
        w = (num(r.w_svpt), num(r.w_ace), num(r.w_df), num(r.w_1stIn), num(r.w_1stWon), num(r.w_2ndWon),
             num(r.w_SvGms), num(r.w_bpSaved), num(r.w_bpFaced))
        l_ = (num(r.l_svpt), num(r.l_ace), num(r.l_df), num(r.l_1stIn), num(r.l_1stWon), num(r.l_2ndWon),
              num(r.l_SvGms), num(r.l_bpSaved), num(r.l_bpFaced))
        ok = (None not in w and None not in l_ and w[0] > 0 and l_[0] > 0 and w[6] > 0 and l_[6] > 0
              and w[3] > 0 and l_[3] > 0)
        mins = num(r.minutes)
        ep = pre.get(idx)
        sf = surf_of(r.surface)
        tn = tkey(r.tourney_name)
        for pid, opp, won, me, ot, s_w, s_l, g_w, g_l, oelo, melo, orank, tw, tl, ioc in (
                (r.winner_id, r.loser_id, 1, w, l_, sw, sl, gw, gl, ep[1] if ep else None, ep[0] if ep else None,
                 num(r.loser_rank), tbw, tbl, r.winner_ioc),
                (r.loser_id, r.winner_id, 0, l_, w, sl, sw, gl, gw, ep[0] if ep else None, ep[1] if ep else None,
                 num(r.winner_rank), tbl, tbw, r.loser_ioc)):
            if pd.isna(pid):
                continue
            rec = [r.t_start, r.rord, r.tourney_id, d, r.src, r.tourney_level, opp, won,
                   *(x if ok else 0.0 for x in me),
                   *(x if ok else 0.0 for x in (ot[0], ot[3], ot[4], ot[5], ot[6], ot[7], ot[8])),
                   s_w, s_l, g_w, g_l, (mins or 0.0), ok, idx, sf, oelo,
                   melo, orank, tw, tl, tn, IOC_FIX.get(str(ioc), str(ioc))]
            hist[pid].append(rec)
    for pid in hist:
        hist[pid].sort(key=lambda x: (x[F_TS], x[F_RORD]))
    return hist


def main():
    td = pd.read_pickle(os.path.join(LAB, "td_joined.pkl"))
    tml = pd.read_pickle(os.path.join(LAB, "tml.pkl"))
    td = td[td["tml_idx"].notna()].copy()
    td["tml_idx"] = td["tml_idx"].astype(int)
    td = td.drop_duplicates("tml_idx").reset_index(drop=True)
    exact = dict(zip(td["tml_idx"], td["Date"]))
    pre = compute_elo(tml, exact)
    hist = build_history_ext(tml, exact, pre)
    ts = {pid: [x[F_TS] for x in recs] for pid, recs in hist.items()}
    pos = {}
    for pid, recs in hist.items():
        for i, x in enumerate(recs):
            pos[(pid, x[F_TML])] = i
    t = tml.loc[td["tml_idx"]].reset_index(drop=True)
    # turnir (tourney_id) -> grad (najčešći tennis-data Location među spojenim mečevima)
    tid_city = (pd.DataFrame({"tid": t["tourney_id"].values, "loc": td["Location"].values})
                .groupby("tid")["loc"].agg(lambda s: s.value_counts().index[0]).to_dict())
    print(f"igrača: {len(hist)} | LAB mečeva: {len(td)} | ELO zapisa: {len(pre)} | turnira s gradom: {len(tid_city)}")

    # ---------- H2H: svi međusobni mečevi (bez walkovera)
    h2h = defaultdict(list)
    for idx, w, l_, sc, sf, tid in zip(tml.index, tml["winner_id"], tml["loser_id"], tml["score"],
                                       tml["surface"], tml["tourney_id"]):
        if pd.isna(w) or pd.isna(l_) or "W/O" in str(sc).upper() or not str(sc).strip():
            continue
        h2h[frozenset((w, l_))].append((idx, w, surf_of(sf), tid))

    def rec_date(idx):
        return exact.get(idx, tml.at[idx, "approx_date"])

    # ---------- N3: nastupi po (turnir, godina) u glavnom ždrijebu ATP razine
    lvl_grp = {"G": "G", "M": "M", "250": "T", "500": "T", "A": "T"}
    entries = defaultdict(dict)   # (tkey, godina) -> {pid: [ioc, došao do QF, razina]}
    mm = tml[(tml["src"] == "main") & tml["tourney_level"].isin(list(lvl_grp))]
    # samo turniri sa ždrijebom koji ima četvrtfinale — ekipna natjecanja (Laver Cup, ATP/United Cup)
    # nemaju QF i lažno bi spuštala "ostale turnire" (ispravljeno 01.11.2026 prije gledanja rezultata testova)
    mm = mm[mm["tourney_id"].isin(set(mm.loc[mm["round"] == "QF", "tourney_id"]))]
    for r in mm.itertuples(index=False):
        k = (tkey(r.tourney_name), r.t_start.year)
        for pid, ioc in ((r.winner_id, r.winner_ioc), (r.loser_id, r.loser_ioc)):
            if pd.isna(pid):
                continue
            e = entries[k].setdefault(pid, [IOC_FIX.get(str(ioc), str(ioc)), False, lvl_grp[r.tourney_level]])
            if r.rord >= 5 and r.round in ("QF", "SF", "F"):
                e[1] = True
    by_year_lvl = defaultdict(list)   # (godina, razina) -> [(tkey, pid, ioc, qf)]
    cnt_t = defaultdict(lambda: [0, 0])     # (godina, razina, država, turnir) -> [nastupi, QF]
    cnt_all = defaultdict(lambda: [0, 0])   # (godina, razina, država) -> [nastupi, QF]
    self_e = defaultdict(list)              # (godina, razina, igrač) -> [(turnir, QF, država)]
    for (tk_, yr), d_ in entries.items():
        for pid, (ioc, qf, lg) in d_.items():
            by_year_lvl[(yr, lg)].append((tk_, pid, ioc, qf))
            cnt_t[(yr, lg, ioc, tk_)][0] += 1
            cnt_t[(yr, lg, ioc, tk_)][1] += qf
            cnt_all[(yr, lg, ioc)][0] += 1
            cnt_all[(yr, lg, ioc)][1] += qf
            self_e[(yr, lg, pid)].append((tk_, qf, ioc))

    def n3_affinity(tk_, yr, lg, ioc, me):
        """Sunarodnjaci BEZ samog igrača: postotak QF na ovom turniru minus na ostalima iste razine,
        prethodnih ≤ 5 godina (strogo ranije)."""
        n_t = q_t = n_e = q_e = 0
        for y in range(yr - 5, yr):
            nt, qt = cnt_t.get((y, lg, ioc, tk_), (0, 0))
            na, qa = cnt_all.get((y, lg, ioc), (0, 0))
            se = [(t2, q2) for (t2, q2, i2) in self_e.get((y, lg, me), []) if i2 == ioc]
            ns_t = sum(1 for t2, _ in se if t2 == tk_)
            qs_t = sum(q2 for t2, q2 in se if t2 == tk_)
            ns_e = len(se) - ns_t
            qs_e = sum(q2 for _, q2 in se) - qs_t
            n_t += nt - ns_t
            q_t += qt - qs_t
            n_e += (na - nt) - ns_e
            q_e += (qa - qt) - qs_e
        if n_t < 5 or n_e < 20:
            return None, n_t
        return q_t / n_t - q_e / n_e, n_t

    # ---------- značajke po meču i strani
    feats = []
    for i in range(len(td)):
        m, r = td.iloc[i], t.iloc[i]
        pf = m["p_fair"]
        if pf is None or pd.isna(pf):
            continue
        tidx = int(m["tml_idx"])
        ep = pre.get(tidx)
        if ep is None:
            continue
        cd0 = m["Date"]
        city = m["Location"]
        country = m["country"]
        row = {"i": i, "pf": float(pf), "half": m["half"], "series": m["Series"], "round": r["round"],
               "court": m["Court"], "surface_td": m["Surface"], "date": cd0, "city": city, "country": country,
               "tname": tkey(r["tourney_name"]), "level": r["tourney_level"],
               "entry_w": r["winner_entry"], "entry_l": r["loser_entry"]}
        ok_sides = 0
        for side, pid, oid, eo, es in (("w", r["winner_id"], r["loser_id"], ep[0], ep[2]),
                                        ("l", r["loser_id"], r["winner_id"], ep[1], ep[3])):
            j = pos.get((pid, tidx))
            if j is None:
                continue
            ok_sides += 1
            recs = hist[pid]
            me = recs[j]
            cd = me[F_DATE]
            lo = bisect_left(ts[pid], me[F_TS] - pd.Timedelta(days=365))
            win = [x for x in recs[lo:j] if x[F_DATE] < cd]
            prof = agg(win)
            row[f"ret_{side}"], row[f"hold_{side}"] = prof["r"], prof["hold"]
            row[f"bps_{side}"], row[f"bpc_{side}"], row[f"tpw_{side}"] = prof["bps"], prof["bpc"], prof["tpw"]
            row[f"w2_{side}"] = prof["w2"]
            okw = [x for x in win if x[F_OK]]
            sv = sum(x[F_SV] for x in okw)
            row[f"df12_{side}"] = (sum(x[F_DF] for x in okw) / sv) if sv >= 300 else None
            prev_all = [x for x in recs[max(0, j - 40):j] if x[F_DATE] < cd]
            ok3 = [x for x in prev_all if x[F_OK] and (cd - x[F_DATE]).days <= 45][-3:]
            sv3 = sum(x[F_SV] for x in ok3)
            row[f"df3_{side}"] = (sum(x[F_DF] for x in ok3) / sv3) if len(ok3) == 3 and sv3 > 0 else None
            tbw = sum(x[-4] for x in win)
            tbl = sum(x[-3] for x in win)
            row[f"tbn_{side}"] = tbw + tbl
            row[f"tb_{side}"] = (tbw / (tbw + tbl)) if (tbw + tbl) else None
            row[f"rest_{side}"] = (cd - prev_all[-1][F_DATE]).days if prev_all else None
            row[f"first_{side}"] = not any(x[F_TID] == me[F_TID] and x[F_SRC] == "main" for x in prev_all)
            # prethodni turnir (drugi tourney_id) i njegov grad
            prev_t = next((x for x in reversed(prev_all) if x[F_TID] != me[F_TID]), None)
            tz = dist = None
            if prev_t is not None and prev_t[F_TID] in tid_city and city in CITY:
                pc = tid_city[prev_t[F_TID]]
                if pc in CITY:
                    tz = abs(utc_off(city, cd) - utc_off(pc, prev_t[F_DATE]))
                    tz = min(tz, 24 - tz)
                    dist = km(CITY[city][:2], CITY[pc][:2])
            row[f"tz_{side}"], row[f"dist_{side}"] = tz, dist
            row[f"elo_{side}"], row[f"elos_{side}"] = eo, es
            ioc = me[F_IOC]
            row[f"ioc_{side}"] = ioc
            home = (ioc == country)
            row[f"home_{side}"] = home
            nb = False
            if not home and isinstance(country, str):
                nb = ioc in BORDERS.get(country, set()) or (
                    ioc in CAPITAL and city in CITY and km(CAPITAL[ioc], CITY[city][:2]) <= 600)
            row[f"nb_{side}"] = nb
            lg = lvl_grp.get(r["tourney_level"])
            aff, n_t = (n3_affinity(row["tname"], cd0.year, lg, ioc, pid) if lg else (None, 0))
            row[f"aff_{side}"], row[f"affn_{side}"] = aff, n_t
            # H2H (strogo prije, bez istog turnira)
            past = []
            for (hidx, hw, hsf, htid) in h2h.get(frozenset((pid, oid)), []):
                if hidx == tidx or htid == me[F_TID]:
                    continue
                hd = rec_date(hidx)
                if hd < cd:
                    past.append((hd, hw == pid, hsf))
            past.sort()
            row[f"h2h_{side}"] = past
            # prethodni meč glavnog ždrijeba ISTOG turnira (za G)
            prev_same = next((x for x in reversed(prev_all) if x[F_TID] == me[F_TID] and x[F_SRC] == "main"), None)
            gk = None
            if prev_same is not None and prev_same[F_WON]:
                orank, oelo, melo = prev_same[F_ORANK], prev_same[F_OELO], prev_same[F_MELO]
                bpf, bps = prev_same[F_BPF], prev_same[F_BPS]
                tpw = match_tpw(prev_same)
                # profil 12 mj. NA TAJ raniji meč (za opis statistike "ubojice")
                jj = pos[(pid, prev_same[F_TML])]
                lo2 = bisect_left(ts[pid], prev_same[F_TS] - pd.Timedelta(days=365))
                w2 = [x for x in recs[lo2:jj] if x[F_DATE] < prev_same[F_DATE]]
                p2 = agg(w2)
                okw2 = [x for x in w2 if x[F_OK]]
                sv2 = sum(x[F_SV] for x in okw2)
                gk = {"orank": orank, "elo_gap": (oelo - melo) if (oelo is not None and melo is not None) else None,
                      "bpf": bpf, "bps": bps, "tpw": tpw, "ok": bool(prev_same[F_OK]),
                      "m_hold": (1 - (bpf - bps) / prev_same[F_SG]) if prev_same[F_OK] and prev_same[F_SG] > 0 else None,
                      "m_w2": (prev_same[F_2W] / (prev_same[F_SV] - prev_same[F_1IN])) if prev_same[F_OK] and (prev_same[F_SV] - prev_same[F_1IN]) > 0 else None,
                      "m_df": (prev_same[F_DF] / prev_same[F_SV]) if prev_same[F_OK] and prev_same[F_SV] > 0 else None,
                      "m_bps": (bps / bpf) if prev_same[F_OK] and bpf > 0 else None,
                      "p_hold": p2["hold"], "p_w2": p2["w2"], "p_bps": p2["bps"],
                      "p_df": (sum(x[F_DF] for x in okw2) / sv2) if sv2 >= 300 else None,
                      "prev_round": prev_same[F_RORD]}
            row[f"gk_{side}"] = gk
            # tie-breakovi na OVOM turniru u prethodnim izdanjima (5 godina)
            y0 = cd0.year
            ev = [x for x in recs[:j] if x[F_TNAME] == row["tname"] and x[F_SRC] == "main"
                  and y0 - 5 <= x[F_TS].year < y0]
            ew, el = sum(x[-4] for x in ev), sum(x[-3] for x in ev)
            row[f"evtbn_{side}"] = ew + el
            row[f"evtb_{side}"] = (ew / (ew + el)) if (ew + el) else None
        if ok_sides == 2:
            feats.append(row)
    f = pd.DataFrame(feats)
    print(f"mečeva s cijenom i obje strane: {len(f)}")

    def col(c, side):
        return pd.to_numeric(f[f"{c}_{side}"], errors="coerce")

    def q(c, qq):
        v = pd.concat([col(c, "w"), col(c, "l")]).dropna()
        return float(v.quantile(qq))

    P = {"ret90": q("ret", 0.90), "ret75": q("ret", 0.75), "ret60": q("ret", 0.60),
         "hold10": q("hold", 0.10), "hold25": q("hold", 0.25), "hold50": q("hold", 0.50),
         "bps80": q("bps", 0.80), "bpc50": q("bpc", 0.50)}
    print("percentili:", {k: round(v, 4) for k, v in P.items()})
    pf_arr, half_arr = f["pf"].values, f["half"].values
    fav = {"w": (f["pf"] >= 0.5).values, "l": (f["pf"] <= 0.5).values}
    dog = {"w": ((f["pf"] >= 0.30) & (f["pf"] < 0.50)).values, "l": ((f["pf"] > 0.50) & (f["pf"] <= 0.70)).values}
    pA = {"w": f["pf"].values, "l": 1 - f["pf"].values}
    ih = ((f["court"] == "Indoor") & (f["surface_td"] == "Hard")).values
    other = {"w": "l", "l": "w"}

    def oriented(mw, ml):
        out = []
        for k, (aw, al) in enumerate(zip(mw, ml)):
            if aw:
                out.append((1, pf_arr[k], half_arr[k], k))
            if al:
                out.append((0, 1 - pf_arr[k], half_arr[k], k))
        return out

    def h2h_last(side, k):
        return f[f"h2h_{side}"].iat[k]

    def mask(fn):
        return np.array([fn("w", k) for k in range(len(f))], bool), np.array([fn("l", k) for k in range(len(f))], bool)

    def v(c, s, k):
        x = f[f"{c}_{s}"].iat[k]
        return None if x is None or (isinstance(x, float) and math.isnan(x)) else x

    # ---------------- obitelj C
    def c1(s, k, rq="ret90", hq="hold10"):
        a, h = v("ret", s, k), v("hold", s, k)
        return bool(ih[k] and a is not None and h is not None and a >= P[rq] and h <= P[hq])

    def c2(s, k):
        tz, rs = v("tz", s, k), v("rest", s, k)
        return bool(fav[s][k] and tz is not None and tz >= 5 and rs is not None and rs <= 5 and f[f"first_{s}"].iat[k])

    def c3(s, k):
        o = other[s]
        tza, rsa, tzb, rsb = v("tz", s, k), v("rest", s, k), v("tz", o, k), v("rest", o, k)
        return bool(dog[s][k] and tza is not None and tza <= 1 and rsa is not None and rsa >= 4
                    and tzb is not None and tzb >= 5 and rsb is not None and rsb <= 5 and f[f"first_{o}"].iat[k])

    def c4(s, k):
        o = other[s]
        d3, d12, h, rb = v("df3", s, k), v("df12", s, k), v("hold", s, k), v("ret", o, k)
        return bool(fav[s][k] and None not in (d3, d12, h, rb) and d12 > 0 and d3 >= 1.5 * d12 and d3 >= 0.04
                    and h <= P["hold50"] and rb >= P["ret60"])

    def c5(s, k):
        past = h2h_last(s, k)
        if not fav[s][k] or len(past) < 2:
            return False
        cd = f["date"].iat[k]
        surf_now = "Hard" if f["surface_td"].iat[k] not in ("Clay", "Grass") else f["surface_td"].iat[k]
        ld, lwon, lsf = past[-1]
        last3 = past[-3:]
        return bool((not lwon) and (cd - ld).days <= 548 and lsf == surf_now and sum(1 for x in last3 if not x[1]) >= 2)

    def c6(s, k):
        o = other[s]
        b, h, c = v("bps", s, k), v("hold", s, k), v("bpc", o, k)
        return bool(fav[s][k] and None not in (b, h, c) and b >= P["bps80"] and h <= P["hold50"] and c >= P["bpc50"])

    def c7(s, k):
        tb, n, tp = v("tb", s, k), v("tbn", s, k), v("tpw", s, k)
        return bool(fav[s][k] and None not in (tb, n, tp) and n >= 6 and tb >= 0.65 and tp <= 0.51)

    def c8(s, k):
        o = other[s]
        tpa, tpb, ea, eb, tb, n = v("tpw", s, k), v("tpw", o, k), v("elo", s, k), v("elo", o, k), v("tb", s, k), v("tbn", s, k)
        return bool(dog[s][k] and None not in (tpa, tpb, ea, eb, tb, n) and tpa >= tpb and ea < eb and n >= 6 and tb <= 0.40)

    def c9(s, k):
        o = other[s]
        tz, d3, d12, ha, hb = v("tz", s, k), v("df3", s, k), v("df12", s, k), v("hold", s, k), v("hold", o, k)
        return bool(fav[s][k] and None not in (tz, d3, d12, ha, hb) and tz >= 3 and d12 > 0 and d3 >= 1.3 * d12 and ha <= hb)

    def c10(s, k):
        o = other[s]
        past = h2h_last(s, k)
        ha, hb = v("hold", s, k), v("hold", o, k)
        if not dog[s][k] or len(past) < 2 or ha is None or hb is None:
            return False
        cd = f["date"].iat[k]
        l2 = past[-2:]
        return bool(all(x[1] for x in l2) and all((cd - x[0]).days <= 730 for x in l2) and ha >= hb)

    fam_c = [
        ("C1 elitni povrat (P90) + hold <= P10, hard dvorana", -1, mask(c1)),
        ("C1r povrat >= P75 + hold <= P25, hard dvorana", -1, mask(lambda s, k: c1(s, k, "ret75", "hold25"))),
        ("C2 jet-lag favorit (tz>=5h, <=5 d, prvi meč)", -1, mask(c2)),
        ("C3 odmoran autsajder protiv putnika", +1, mask(c3)),
        ("C4 klimav servis favorita (DF3 skok, hold<=med, B povrat>=P60)", -1, mask(c4)),
        ("C5 H2H dinamika protiv favorita", -1, mask(c5)),
        ("C6 favorit 'srećom spašeni BP'", -1, mask(c6)),
        ("C7 favorit napuhan tie-breakovima", -1, mask(c7)),
        ("C8 autsajder bolji po poenima, lošiji po rezultatima", +1, mask(c8)),
        ("C9 lanac: favorit putnik (tz>=3h) + DF3 rast + slabiji hold", -1, mask(c9)),
        ("C10 H2H gospodar kao autsajder", +1, mask(c10)),
    ]

    # ---------------- obitelj N
    def n1(s, k):
        return bool(f[f"nb_{s}"].iat[k])

    def n2(s, k):
        return bool(f[f"nb_{s}"].iat[k] and dog[s][k])

    def n3(s, k):
        a = v("aff", s, k)
        return bool(a is not None and a >= 0.10)

    fam_n = [("N1 susjed (granica ili glavni grad <= 600 km)", +1, mask(n1)),
             ("N2 susjed i autsajder", +1, mask(n2)),
             ("N3 'turnir sunarodnjaka' (+10pp QF, bez njega samog)", +1, mask(n3))]
    ref_home = mask(lambda s, k: bool(f[f"home_{s}"].iat[k]))

    # ---------------- obitelj G
    def is_gk(s, k):
        g = f[f"gk_{s}"].iat[k]
        o = other[s]
        ea, eb = v("elo", s, k), v("elo", o, k)
        return bool(isinstance(g, dict) and g["orank"] is not None and g["orank"] <= 15 and g["elo_gap"] is not None
                    and g["elo_gap"] >= 50 and ea is not None and eb is not None and ea > eb)

    def g3(s, k):
        g = f[f"gk_{s}"].iat[k]
        return bool(is_gk(s, k) and g["ok"] and g["bpf"] >= 5 and g["bps"] / g["bpf"] >= 0.70
                    and g["tpw"] is not None and g["tpw"] < 0.505)

    def g4(s, k):
        g = f[f"gk_{s}"].iat[k]
        return bool(is_gk(s, k) and g["ok"] and g["tpw"] is not None and g["tpw"] >= 0.52)

    fam_g = [("G1 ubojica diva, sada ELO-favorit", 0, mask(is_gk)),
             ("G2 G1 i tržišni favorit", 0, mask(lambda s, k: is_gk(s, k) and fav[s][k])),
             ("G3 G1, prošli meč 'srećom' (BP >= 70%, poeni < 50,5%)", -1, mask(g3)),
             ("G4 G1, prošli meč 'zasluženo' (poeni >= 52%)", +1, mask(g4))]

    # ---------------- obitelj T
    def t1(s, k):
        o = other[s]
        a, b, na, nb_ = v("tb", s, k), v("tb", o, k), v("tbn", s, k), v("tbn", o, k)
        return bool(None not in (a, b, na, nb_) and na >= 6 and nb_ >= 6 and a - b >= 0.20)

    def t2(s, k):
        o = other[s]
        ta, tb_ = v("tpw", s, k), v("tpw", o, k)
        return bool(t1(s, k) and 0.40 <= pA[s][k] <= 0.60 and ta is not None and tb_ is not None and abs(ta - tb_) <= 0.01)

    def t3(s, k):
        o = other[s]
        a, na, b, nb_ = v("evtb", s, k), v("evtbn", s, k), v("evtb", o, k), v("evtbn", o, k)
        return bool(na is not None and na >= 4 and a is not None and a >= 0.75
                    and ((nb_ is None or nb_ < 2) or (b is not None and b < 0.50)))

    fam_t = [("T1 bolji TB zapis 12 mj. +20pp (oba >= 6 TB)", 0, mask(t1)),
             ("T2 T1 + 'ostalo slično' (cijena 0,40-0,60, poeni +-1pp)", 0, mask(t2)),
             ("T3 TB zapis na OVOM turniru (>= 4 TB, >= 75%)", 0, mask(t3))]

    # ---------------- računanje, Holm, stabilnost, presude
    lv = f["series"].map(lambda s: "GS+M" if s in ("Grand Slam", "Masters 1000", "Masters Cup") else ("500" if s == "ATP500" else "250")).values
    early = f["round"].isin(["R128", "R64", "R32"]).values

    def bandof(p):
        return "jak fav" if p >= 0.70 else ("fav" if p >= 0.5 else ("autsajder" if p >= 0.30 else "veliki autsajder"))

    def run(tests):
        res, pvals = {}, []
        for name, sign, (mw, ml) in tests:
            rows_ = oriented(mw, ml)
            a = stats(rows_)
            res[name] = {"sign": sign, "all": a,
                         "P1": stats([x for x in rows_ if x[2] == "P1"]), "P2": stats([x for x in rows_ if x[2] == "P2"]),
                         "lvl": {g: stats([x for x in rows_ if lv[x[3]] == g]) for g in ("GS+M", "500", "250")},
                         "rnd": {g: stats([x for x in rows_ if (early[x[3]] if g == "rano" else not early[x[3]])]) for g in ("rano", "kasno")},
                         "band": {g: stats([x for x in rows_ if bandof(x[1]) == g]) for g in ("jak fav", "fav", "autsajder", "veliki autsajder")},
                         "raw_win": float(np.mean([x[0] for x in rows_])) if rows_ else float("nan"),
                         "mean_p": float(np.mean([x[1] for x in rows_])) if rows_ else float("nan")}
            pvals.append(a.get("p", 1.0) if a.get("n") else 1.0)
        order = sorted(range(len(pvals)), key=lambda q_: pvals[q_])
        holm, run_ = [None] * len(pvals), 0.0
        for kk, q_ in enumerate(order):
            run_ = max(run_, min(1.0, (len(pvals) - kk) * pvals[q_]))
            holm[q_] = run_
        for (name, *_), hp, pv in zip(tests, holm, pvals):
            res[name]["holm"] = hp
            res[name]["p_raw"] = pv
            res[name]["p_x_total"] = min(1.0, pv * N_TOTAL_TESTS)
        return res

    def verdict(r):
        a, p1, p2 = r["all"], r["P1"], r["P2"]
        if a.get("n", 0) < 30 or p1.get("n", 0) < 10 or p2.get("n", 0) < 10:
            return "PREMALO"
        sgn = r["sign"] if r["sign"] != 0 else (1 if a["edge"] > 0 else -1)
        same = (a["edge"] > 0) == (sgn > 0)
        ci = (a["lo"] > 0) if sgn > 0 else (a["hi"] < 0)
        halves = (p1["edge"] > 0) == (p2["edge"] > 0) == (a["edge"] > 0)

        def stable(groups, need):
            okg = [g for g in groups.values() if g.get("n", 0) >= 50]
            if not okg:
                return True
            kk = sum(1 for g in okg if (g["edge"] > 0) == (a["edge"] > 0))
            return kk >= min(need, len(okg))
        stab = stable(r["lvl"], 2) and stable(r["rnd"], 2) and stable(r["band"], 3)
        if same and ci and halves and abs(a["edge"]) >= 2 and r["holm"] < 0.05 and stab:
            return "PROLAZI"
        if same and ci and halves:
            return "SLAB" + ("" if stab else " (nestabilno)")
        return "PADA"

    out = {"percentili": P}
    for fam, tests in (("C", fam_c), ("N", fam_n), ("G", fam_g), ("T", fam_t)):
        res = run(tests)
        print("\n" + "=" * 158)
        print(f"OBITELJ {fam}: {'test':62s} smjer   n      edge   [95% interval]    P1 / P2      Holm  (P×109)  pobjeđuje  cijena  presuda")
        for name, sign, _ in tests:
            r_ = res[name]
            r_["verdict"] = verdict(r_)
            a, p1, p2 = r_["all"], r_["P1"], r_["P2"]
            if not a.get("n"):
                print(f"  {name:66s} n=0")
                continue
            print(f"  {name:66s} {'+' if sign > 0 else ('-' if sign < 0 else '±')}  {a['n']:6d}  {a['edge']:+5.1f}pp [{a['lo']:+5.1f}, {a['hi']:+5.1f}]"
                  f"  {p1.get('edge', float('nan')):+5.1f} / {p2.get('edge', float('nan')):+5.1f}   {r_['holm']:5.2f}  ({r_['p_x_total']:4.2f})"
                  f"   {100*r_['raw_win']:5.1f}%  {100*r_['mean_p']:5.1f}%  {r_['verdict']}")
        for name, *_ in tests:
            r_ = res[name]
            if not r_["all"].get("n"):
                continue
            fmt = lambda d: " ".join(f"{kk}:{vv.get('edge', float('nan')):+.1f}(n={vv.get('n', 0)})" for kk, vv in d.items())
            print(f"     {name[:44]:44s} razina {fmt(r_['lvl'])} | runda {fmt(r_['rnd'])}\n{'':50s} pojas {fmt(r_['band'])}")
        out[fam] = res
    # referenca: domaći (K2), isti kod
    rh = stats(oriented(*ref_home))
    rh1 = stats([x for x in oriented(*ref_home) if x[2] == "P1"])
    rh2 = stats([x for x in oriented(*ref_home) if x[2] == "P2"])
    print(f"\nReferenca K2 domaći igrač (isti kod, nije novi test): n={rh['n']} edge {rh['edge']:+.1f}pp "
          f"[{rh['lo']:+.1f}, {rh['hi']:+.1f}]  P1 {rh1['edge']:+.1f} / P2 {rh2['edge']:+.1f}")
    out["ref_home"] = {"all": rh, "P1": rh1, "P2": rh2}

    # popunjenost ključnih varijabli
    print("\nPopunjenost (udio strana s vrijednošću):",
          {c: round(float(pd.concat([col(c, 'w'), col(c, 'l')]).notna().mean()), 3)
           for c in ("ret", "hold", "bps", "bpc", "tpw", "df12", "df3", "tb", "tz", "rest", "elo", "aff", "evtb")})
    tzv = pd.concat([col("tz", "w"), col("tz", "l")]).dropna()
    print(f"pomak vremenske zone: n={len(tzv)}  0 h {100*(tzv < 0.5).mean():.0f}% | 1-2 h {100*((tzv >= 0.5) & (tzv < 2.5)).mean():.0f}% | "
          f"3-4 h {100*((tzv >= 2.5) & (tzv < 4.5)).mean():.0f}% | 5+ h {100*(tzv >= 4.5).mean():.0f}%")

    # ---------------- OPIS G: statistika prošlog meča "ubojice" naspram njegovog profila 12 mj.
    print("\n" + "=" * 100 + "\nOPIS G — 'ubojica diva': prošli meč (pobjeda nad top-15 s ELO +50) naspram vlastitog profila 12 mj.")
    diffs = defaultdict(list)
    trans = defaultdict(list)
    for k in range(len(f)):
        for s in ("w", "l"):
            if not is_gk(s, k):
                continue
            g = f[f"gk_{s}"].iat[k]
            for a_, b_ in (("m_hold", "p_hold"), ("m_w2", "p_w2"), ("m_df", "p_df"), ("m_bps", "p_bps")):
                if g.get(a_) is not None and g.get(b_) is not None:
                    diffs[a_].append(g[a_] - g[b_])
            if g.get("tpw") is not None:
                diffs["tpw_prosli"].append(g["tpw"])
            won = 1 if s == "w" else 0
            trans[f["round"].iat[k]].append((won, pA[s][k], half_arr[k], k))
    for kk, vv in diffs.items():
        vv = np.array(vv, float)
        print(f"  {kk:12s} n={len(vv):4d}  prosjek razlike {100*vv.mean():+6.2f}pp  (medijan {100*np.median(vv):+6.2f}pp)")
    print("  sljedeći meč po rundi (ubojica sada ELO-favorit): ")
    for rd in ("R64", "R32", "R16", "QF", "SF", "F"):
        st_ = stats(trans.get(rd, []))
        if st_.get("n"):
            print(f"     {rd:4s} n={st_['n']:4d}  edge {st_['edge']:+5.1f}pp [{st_['lo']:+5.1f}, {st_['hi']:+5.1f}]")

    # ---------------- OPIS T: postojanost tie-break uspjeha (igrač-godina, sve razine, >= 10 TB)
    print("\n" + "=" * 100 + "\nOPIS T — je li tie-break vještina postojana? (igrač-godina s >= 10 TB obje godine)")
    py = defaultdict(lambda: [0, 0, 0.0, 0.0])   # (pid, godina) -> [TB dobiveno, TB izgubljeno, poeni osvojeni, poeni ukupno]
    for pid, recs in hist.items():
        for x in recs:
            yr = x[F_TS].year
            if yr < 2010:
                continue
            e = py[(pid, yr)]
            e[0] += x[-4]
            e[1] += x[-3]
            if x[F_OK]:
                won_pts = x[F_1W] + x[F_2W] + x[F_OSV] - x[F_O1W] - x[F_O2W]
                e[2] += won_pts
                e[3] += x[F_SV] + x[F_OSV]
    a1, a2, c1_, c2_ = [], [], [], []
    for (pid, yr), e in py.items():
        nx = py.get((pid, yr + 1))
        if nx is None:
            continue
        if e[0] + e[1] >= 10 and nx[0] + nx[1] >= 10 and e[3] >= 500 and nx[3] >= 500:
            a1.append(e[0] / (e[0] + e[1]))
            a2.append(nx[0] / (nx[0] + nx[1]))
            c1_.append(e[2] / e[3])
            c2_.append(nx[2] / nx[3])
    a1, a2, c1_, c2_ = map(lambda z: np.array(z, float), (a1, a2, c1_, c2_))
    r_tb = float(np.corrcoef(a1, a2)[0, 1])
    r_pts = float(np.corrcoef(c1_, c2_)[0, 1])
    # ostatak: TB% minus ono što predviđa udio poena iste godine (linearno), pa korelacija ostataka kroz godine
    X1 = np.vstack([np.ones_like(c1_), c1_]).T
    b1 = np.linalg.lstsq(X1, a1, rcond=None)[0]
    X2 = np.vstack([np.ones_like(c2_), c2_]).T
    b2 = np.linalg.lstsq(X2, a2, rcond=None)[0]
    res1, res2 = a1 - X1 @ b1, a2 - X2 @ b2
    r_res = float(np.corrcoef(res1, res2)[0, 1])
    r_cross = float(np.corrcoef(a1, a2 - X2 @ b2)[0, 1])
    print(f"  igrač-godina parova: {len(a1)}")
    print(f"  r(TB% godina t, TB% godina t+1)                       = {r_tb:+.3f}")
    print(f"  r(udio poena t, udio poena t+1) — za usporedbu        = {r_pts:+.3f}")
    print(f"  r(TB% 'višak' povrh poena t, isti višak t+1)           = {r_res:+.3f}")
    print(f"  r(TB% t, TB% t+1 povrh onoga što kažu poeni t+1)       = {r_cross:+.3f}")
    out["opis_T"] = {"n": int(len(a1)), "r_tb": r_tb, "r_pts": r_pts, "r_res": r_res, "r_cross": r_cross}

    # ---------------- OPIS R: favoriti po rundi × pojasu; profili autsajdera po rundi
    print("\n" + "=" * 100 + "\nOPIS R — favorit po rundi i pojasu (edge favorita naspram poštene cijene)")
    rg = f["round"].map(lambda x: {"R128": "R128/R64", "R64": "R128/R64"}.get(x, x if x in ("R32", "R16", "QF") else ("SF/F" if x in ("SF", "F") else "ostalo")))
    favs = f["pf"] >= 0.5
    for g_ in ("R128/R64", "R32", "R16", "QF", "SF/F"):
        parts = []
        for lo_, hi_, lab in ((0.70, 1.01, "jak fav >=0,70"), (0.60, 0.70, "fav 0,60-0,70"), (0.50, 0.60, "fav 0,50-0,60")):
            rows_ = []
            for k in np.where(rg.values == g_)[0]:
                p_ = f["pf"].iat[k]
                pfav = p_ if favs.iat[k] else 1 - p_
                won = 1 if favs.iat[k] else 0
                if lo_ <= pfav < hi_:
                    rows_.append((won, pfav, half_arr[k], k))
            st_ = stats(rows_)
            parts.append(f"{lab}: {st_.get('edge', float('nan')):+5.1f}pp (n={st_.get('n', 0)})")
        print(f"  {g_:9s} " + " | ".join(parts))
    print("\nOPIS R — autsajder (0,30-0,50) s profilom, po rundi: edge autsajdera")
    profiles = {
        "kvalifikant/LL": lambda s, k: str(f[f"entry_{s}"].iat[k]) in ("Q", "LL"),
        "ubojica iz prošle runde": lambda s, k: (lambda g: isinstance(g, dict) and g["orank"] is not None and g["orank"] <= 15
                                                 and g["elo_gap"] is not None and g["elo_gap"] >= 50)(f[f"gk_{s}"].iat[k]),
        "hold 12 mj. +3pp bolji": lambda s, k: (v("hold", s, k) is not None and v("hold", other[s], k) is not None
                                                and v("hold", s, k) - v("hold", other[s], k) >= 0.03),
        "domaći": lambda s, k: bool(f[f"home_{s}"].iat[k]),
        "susjed": lambda s, k: bool(f[f"nb_{s}"].iat[k]),
    }
    for nm, fn in profiles.items():
        parts = []
        for g_ in ("R128/R64", "R32", "R16", "QF", "SF/F"):
            rows_ = []
            for k in np.where(rg.values == g_)[0]:
                for s in ("w", "l"):
                    if dog[s][k] and fn(s, k):
                        rows_.append((1 if s == "w" else 0, pA[s][k], half_arr[k], k))
            st_ = stats(rows_)
            parts.append(f"{g_}: {st_.get('edge', float('nan')):+5.1f} (n={st_.get('n', 0)})")
        print(f"  {nm:24s} " + " | ".join(parts))

    with open(os.path.join(OUTD, "lab_nos_rezultati.json"), "w", encoding="utf-8") as fo:
        json.dump(out, fo, indent=1, default=float)
    f.drop(columns=[c for c in f.columns if c.startswith(("h2h_", "gk_"))]).to_pickle(os.path.join(OUTD, "lab_nos_features.pkl"))

    # ---------------- TABLICA nacionalnosti (opis, korisnik ju je tražio)
    print("\n" + "=" * 100 + "\nTABLICA — nastupi i četvrtfinala po državljanstvu i turniru (glavni ždrijeb, TML)")
    def table(tk_, ioc, years):
        rows_ = []
        for y in years:
            d_ = entries.get((tk_, y), {})
            ent = [(pid, e) for pid, e in d_.items() if e[0] == ioc]
            if not d_:
                continue
            names = []
            for pid, e in ent:
                if e[1]:
                    nm = next((x for x in (tml.loc[tml.winner_id == pid, "winner_name"].head(1).tolist()
                                           + tml.loc[tml.loser_id == pid, "loser_name"].head(1).tolist())), str(pid))
                    names.append(nm.split()[-1])
            rows_.append((y, len(ent), sum(1 for _, e in ent if e[1]), names))
        return rows_
    examples = [("vienna", "ITA"), ("vienna", "AUT"), ("vienna", "GER"), ("umag", "ITA"), ("umag", "CRO"),
                ("basel", "GER"), ("basel", "SUI"), ("basel", "FRA"), ("barcelona", "POR"), ("madrid", "POR"),
                ("mallorca", "POR"), ("estoril", "ESP"), ("kitzbuhel", "GER"), ("kitzbuhel", "AUT"),
                ("munich", "AUT"), ("gstaad", "GER"), ("geneva", "FRA"), ("paris", "FRA"), ("paris", "BEL"),
                ("montecarlo", "ITA"), ("montecarlo", "FRA")]
    years = list(range(2017, 2027))
    # postotak QF iste države na OSTALIM turnirima iste razine istih godina (opis uz primjere; dodano
    # 01.11.2026 nakon prvog ispisa — samo prikaz, testovi se ne mijenjaju)
    def elsewhere(tk_, ioc):
        n_ = q_ = 0
        lg0 = None
        for (yr, lg), lst in by_year_lvl.items():
            if not (2017 <= yr <= 2026):
                continue
            if any(t2 == tk_ for t2, *_ in lst):
                lg0 = lg
        for (yr, lg), lst in by_year_lvl.items():
            if 2017 <= yr <= 2026 and lg == lg0:
                for t2, pid, i2, qf in lst:
                    if i2 == ioc and t2 != tk_:
                        n_ += 1
                        q_ += qf
        return (100 * q_ / n_ if n_ else float("nan")), n_
    for tk_, ioc in examples:
        rows_ = table(tk_, ioc, years)
        if not rows_:
            continue
        tot_e = sum(x[1] for x in rows_)
        tot_q = sum(x[2] for x in rows_)
        last5 = [x for x in rows_ if x[0] >= 2022]
        pe, ne = elsewhere(tk_, ioc)
        print(f"  {tk_:11s} {ioc}: 2017-26 nastupa {tot_e:3d}, QF {tot_q:2d} = {100*tot_q/tot_e if tot_e else float('nan'):4.1f}% "
              f"(ista država na ostalim turnirima iste razine {pe:4.1f}%, n={ne}) | zadnjih 5 sez.: "
              + "; ".join(f"{y}: {e} nast./{q_} QF{(' (' + ', '.join(nm) + ')') if nm else ''}" for y, e, q_, nm in last5))
    # najveća odstupanja: postotak QF na turniru naspram istih nacionalnosti na ostalim turnirima iste razine (2017-26)
    agg_t = defaultdict(lambda: [0, 0])
    agg_e = defaultdict(lambda: [0, 0])
    for (yr, lg), lst in by_year_lvl.items():
        if not (2017 <= yr <= 2026):
            continue
        tot = defaultdict(lambda: [0, 0])
        for tk_, pid, ioc, qf in lst:
            tot[ioc][0] += 1
            tot[ioc][1] += qf
            agg_t[(tk_, ioc, lg)][0] += 1
            agg_t[(tk_, ioc, lg)][1] += qf
        for tk_, pid, ioc, qf in lst:
            pass
        for ioc, (n_, q_) in tot.items():
            agg_e[(ioc, lg)][0] += n_
            agg_e[(ioc, lg)][1] += q_
    rowsz = []
    for (tk_, ioc, lg), (n_, q_) in agg_t.items():
        # Grand Slamovi izostavljeni iz poretka (01.11.2026, nakon prvog ispisa): ondje je osnovni
        # postotak QF ~0–2% pa z-vrijednost "eksplodira" (z = 63.245 za NED na US Openu) — artefakt
        if n_ < 8 or lg == "G":
            continue
        ne, qe = agg_e[(ioc, lg)]
        ne, qe = ne - n_, qe - q_
        if ne < 30 or qe == 0:
            continue
        p0 = qe / ne
        z = (q_ - n_ * p0) / math.sqrt(max(n_ * p0 * (1 - p0), 1e-9))
        rowsz.append((z, tk_, ioc, n_, q_, 100 * q_ / n_, 100 * p0))
    rowsz.sort(reverse=True)
    print(f"\n  Najveća pozitivna odstupanja (>= 8 nastupa, 2017-26; ukupno parova turnir×država: {len(rowsz)}; "
          f"uz toliko parova ~{int(0.025*len(rowsz))} s z > 1,96 očekuje se slučajno):")
    for z, tk_, ioc, n_, q_, ph, pe in rowsz[:20]:
        print(f"    {tk_:14s} {ioc}  nastupa {n_:3d}  QF {q_:3d} = {ph:5.1f}%  (ista država drugdje {pe:5.1f}%)  z={z:+.2f}")
    print("  Najveća negativna:")
    for z, tk_, ioc, n_, q_, ph, pe in rowsz[-8:]:
        print(f"    {tk_:14s} {ioc}  nastupa {n_:3d}  QF {q_:3d} = {ph:5.1f}%  (ista država drugdje {pe:5.1f}%)  z={z:+.2f}")
    print(f"  Broj parova sa z > 1,96: {sum(1 for x in rowsz if x[0] > 1.96)} | z < -1,96: {sum(1 for x in rowsz if x[0] < -1.96)}")


if __name__ == "__main__":
    main()
