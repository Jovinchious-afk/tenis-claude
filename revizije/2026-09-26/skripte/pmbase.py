# -*- coding: utf-8 -*-
"""Jedinstvena tablica meceva iz berbe past-matches (s kvotama). Revizija 26.09.2026."""
import json, os, re
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))


def load_matches():
    rows = {}
    names = {}
    for f in os.listdir(os.path.join(HERE, "pm")):
        g = json.load(open(os.path.join(HERE, "pm", f), encoding="utf-8"))
        for x in g:
            p1, p2 = str(x.get("player1Id")), str(x.get("player2Id"))
            d = str(x.get("date", ""))[:10]
            key = (d, tuple(sorted([p1, p2])))
            t = x.get("tournament") or {}
            names[p1] = (x.get("player1") or {}).get("name")
            names[p2] = (x.get("player2") or {}).get("name")
            o1, o2 = x.get("odd1"), x.get("odd2")
            try:
                o1 = float(o1) if o1 not in (None, "") else np.nan
                o2 = float(o2) if o2 not in (None, "") else np.nan
            except ValueError:
                o1 = o2 = np.nan
            r = dict(date=d, p1=p1, p2=p2, winner=str(x.get("match_winner")),
                     o1=o1, o2=o2, result=x.get("result") or "", rtype=x.get("result_type"),
                     tid=str(t.get("id")), tname=t.get("name"), level=t.get("rankId"),
                     court=t.get("courtId"), round_id=x.get("roundId"), tdate=str(t.get("date", ""))[:10])
            prev = rows.get(key)
            if prev is None or (np.isnan(prev["o1"]) and not np.isnan(o1)):
                rows[key] = r
    df = pd.DataFrame(list(rows.values()))
    df["date"] = pd.to_datetime(df["date"])
    return df, names


COURT = {1: "hard", 2: "clay", 3: "indoor", 4: "grass", 5: "carpet"}
