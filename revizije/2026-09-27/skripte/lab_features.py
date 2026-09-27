# -*- coding: utf-8 -*-
"""Povijesni laboratorij — osobine igrača NA DAN MEČA (27.09.2026 11:38).

Za svaki tennis-data meč spojen s TML-om računa, za pobjednika (w) i poraženog (l), samo iz
mečeva odigranih PRIJE tog meča (bez curenja iz budućnosti):
  sw    ATP pobjede u tekućoj sezoni (glavni ždrijeb, razine iz TML glavnih datoteka)   K15
  gssf  broj Grand Slam polufinala prije ovog turnira (TML od 2000.)                    K16
  rest  dani od zadnjeg meča (glavni, Challenger, kvalifikacije)                       K19
  ioc   državljanstvo (za "domaći igrač")                                              K2
  hist  najdalja runda (R16=1 ... naslov=5) na TOM turniru u prethodne 3 sezone        POV
  spw / depth  % osvojenih poena na servisu na ovom turniru prije ovog meča + broj mečeva K12
  co    omjer protiv zajedničkih protivnika (365 dana, tour+Challenger+kval.), pobjednik minus
        poraženi; co_n = broj zajedničkih protivnika                                   CO
Pragovi: revizije/2026-09-27/PRAGOVI_POVIJESNI_LAB.md (zapisani prije ovog koda).
"""
import os
from bisect import bisect_left
from collections import defaultdict

import pandas as pd

from lab_data import LAB_CACHE

MAIN_LEVELS = {"G", "M", "250", "500", "A", "F", "D", "O"}
HIST_VALUE = {"F": 4, "SF": 3, "QF": 2, "R16": 1}


def build_history(tml: pd.DataFrame, exact_date: dict) -> dict:
    """igrač -> popis zapisa (datum, turnir, runda, ...) sortiran po datumu."""
    hist = defaultdict(list)
    cols = ["tourney_id", "t_start", "rord", "round", "tourney_level", "src", "tname",
            "winner_id", "loser_id", "approx_date", "w_svpt", "w_1stWon", "w_2ndWon",
            "l_svpt", "l_1stWon", "l_2ndWon"]
    for idx, r in zip(tml.index, tml[cols].itertuples(index=False)):
        date = exact_date.get(idx, r.approx_date)
        for pid, opp, won, svpt, a, b in ((r.winner_id, r.loser_id, 1, r.w_svpt, r.w_1stWon, r.w_2ndWon),
                                          (r.loser_id, r.winner_id, 0, r.l_svpt, r.l_1stWon, r.l_2ndWon)):
            if pd.isna(pid):
                continue
            try:
                sv = float(svpt)
                spw = float(a) + float(b)
            except (TypeError, ValueError):
                sv, spw = 0.0, 0.0
            if not (sv > 0):
                sv, spw = 0.0, 0.0
            hist[pid].append((date, r.tourney_id, r.rord, r.round, r.tourney_level, r.src,
                              r.tname, r.t_start, opp, won, sv, spw))
    for pid in hist:
        hist[pid].sort(key=lambda x: x[0])
    return hist


def edition_results(hist: dict) -> dict:
    """(igrač, turnir_id) -> vrijednost najdalje runde (naslov 5, finale 4 ... R16 1, ostalo 0)."""
    res = {}
    for pid, recs in hist.items():
        for (date, tid, rord, rnd, lvl, src, tname, tdate, opp, won, sv, spw) in recs:
            if src != "main" or rnd == "RR":
                continue
            v = 5 if (rnd == "F" and won) else (HIST_VALUE.get(rnd, 0) if not won else 0)
            key = (pid, tid)
            if v > res.get(key, (0, tname, tdate))[0]:
                res[key] = (v, tname, tdate)
            elif key not in res:
                res[key] = (0, tname, tdate)
    by_player = defaultdict(list)
    for (pid, tid), (v, tname, tdate) in res.items():
        by_player[pid].append((tname, tdate.year, v))
    return by_player


def features_for_match(pid, other, D, T, R, tname, tyear, tdate, hist, eds, gs_sf):
    recs = hist.get(pid, [])
    dates = [x[0] for x in recs]
    prev = None
    sw = 0
    spw_sum, sv_sum, depth = 0.0, 0.0, 0
    for (date, tid, rord, rnd, lvl, src, tn, td_, opp, won, sv, spw) in recs[:bisect_left(dates, D + pd.Timedelta(days=20))]:
        same = (tid == T)
        before = (rord < R) if same else (date < D)
        if not before:
            continue
        if prev is None or date > prev:
            prev = date
        if src == "main" and lvl in MAIN_LEVELS and won and date.year == D.year:
            sw += 1
        if same and src == "main" and sv > 0:
            spw_sum += spw
            sv_sum += sv
            depth += 1
    rest = None if prev is None else max((D - prev).days, 0)
    h = 0
    for (tn, y, v) in eds.get(pid, []):
        if tn == tname and tyear - 3 <= y <= tyear - 1:
            h = max(h, v)
    gs = bisect_left(gs_sf.get(pid, []), tdate)
    return {"sw": sw, "rest": rest, "hist": h, "gssf": gs,
            "spw": (spw_sum / sv_sum) if sv_sum > 0 else None, "depth": depth}


def co_score(a, b, D, hist):
    lo_d = D - pd.Timedelta(days=365)

    def agg(pid, other):
        recs = hist.get(pid, [])
        dates = [x[0] for x in recs]
        out = defaultdict(lambda: [0, 0])
        for x in recs[bisect_left(dates, lo_d):bisect_left(dates, D)]:
            opp, won = x[8], x[9]
            if opp == other:
                continue
            out[opp][0] += won
            out[opp][1] += 1
        return out

    A, B = agg(a, b), agg(b, a)
    common = set(A) & set(B)
    if len(common) < 3:
        return None, len(common)
    s = sum(A[c][0] / A[c][1] - B[c][0] / B[c][1] for c in common) / len(common)
    return s, len(common)


def main():
    td = pd.read_pickle(os.path.join(LAB_CACHE, "td_joined.pkl"))
    tml = pd.read_pickle(os.path.join(LAB_CACHE, "tml.pkl"))
    td = td[td["tml_idx"].notna()].copy()
    td["tml_idx"] = td["tml_idx"].astype(int)
    td = td.drop_duplicates("tml_idx")
    exact = dict(zip(td["tml_idx"], td["Date"]))
    hist = build_history(tml, exact)
    eds = edition_results(hist)
    gs_sf = defaultdict(set)
    g = tml[(tml["tourney_level"] == "G") & (tml["round"] == "SF")]
    for tdate, w, l in zip(g["t_start"], g["winner_id"], g["loser_id"]):
        gs_sf[w].add(tdate)
        gs_sf[l].add(tdate)
    gs_sf = {k: sorted(v) for k, v in gs_sf.items()}

    rows = []
    t = tml.loc[td["tml_idx"]]
    for (_, m), (_, r) in zip(td.iterrows(), t.iterrows()):
        D, T, R = m["Date"], r["tourney_id"], r["rord"]
        a, b = r["winner_id"], r["loser_id"]
        # t_start = stvarni početak turnira (vidi zamku u lab_data.load_tml, 27.09.2026 11:40)
        fw = features_for_match(a, b, D, T, R, r["tname"], r["t_start"].year, r["t_start"], hist, eds, gs_sf)
        fl = features_for_match(b, a, D, T, R, r["tname"], r["t_start"].year, r["t_start"], hist, eds, gs_sf)
        co, con = co_score(a, b, D, hist)
        row = {"Date": D, "half": m["half"], "Series": m["Series"], "Surface": m["Surface"],
               "Best of": m["Best of"], "Location": m["Location"], "country": m["country"],
               "round": r["round"], "level": r["tourney_level"], "tname": r["tname"],
               "p_fair": m["p_fair"], "p_avg": m["p_avg"], "p_ps": m["p_ps"], "p_b365": m["p_b365"],
               "fair_src": m["fair_src"], "AvgW": m["AvgW"], "AvgL": m["AvgL"],
               "B365W": m["B365W"], "B365L": m["B365L"], "Winner": m["Winner"], "Loser": m["Loser"],
               "ioc_w": r["winner_ioc"], "ioc_l": r["loser_ioc"], "co": co, "co_n": con}
        for k, v in fw.items():
            row[f"{k}_w"] = v
        for k, v in fl.items():
            row[f"{k}_l"] = v
        rows.append(row)
    f = pd.DataFrame(rows)
    f.to_pickle(os.path.join(LAB_CACHE, "features.pkl"))
    print(f"mečeva s osobinama: {len(f)}")
    for c in ("sw_w", "rest_w", "hist_w", "gssf_w", "spw_w", "depth_w", "co"):
        s = f[c]
        print(f"  {c:8s} popunjeno {s.notna().mean()*100:5.1f}%  medijan {s.median() if s.notna().any() else None}")
    print("  primjer:", f[["Date", "Winner", "Loser", "sw_w", "sw_l", "rest_w", "rest_l", "hist_w", "hist_l", "gssf_w", "gssf_l", "co", "co_n"]].tail(5).to_string())


if __name__ == "__main__":
    main()
