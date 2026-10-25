# -*- coding: utf-8 -*-
"""Revizija 25.10.2026 — E: vijesti (korisnikova ideja 2) (25.10.2026 10:39).

E1 — panel na Dnevnom listiću (`pages/1_Dnevni_Listic.py`, blok "VIJESTI O IGRACIMA"): isti dohvat
     ESPN + BBC RSS i isto pravilo podudaranja (prezime ≥ 4 slova u naslovu ili opisu, bez datuma),
     primijenjeno na igrače TJEDNA i današnjih finala. Ispisuje svaki "pogodak" s datumom članka,
     da se ručno vidi je li o pravom igraču i koliko je star.
E2 — Google News po igraču (`p*_gnews`, bilježi se od 27.09.2026, model ne vidi): pokrivenost,
     starost naslova naspram datuma meča, vrste naslova (pregled meča / rezultat / kladionica /
     ozljeda / ostalo) i uzorak naslova za ručnu provjeru.
Pragovi: PRAGOVI_REVIZIJA_2026-10-25.md točka E (10:20). Samo čita (RSS je javan, bez ključa).
    python revizije/2026-10-25/skripte/r_vijesti.py
"""
import collections
import datetime as dt
import email.utils
import json
import os
import random
import re
import sys

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r_base import load  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TODAY = dt.date(2026, 10, 25)
PREVIEW = re.compile(r"\bvs\.?\b|\bv\b|preview|prediction|odds|pick|h2h|head to head|live|stats|scores?|result", re.I)


def feeds():
    out = []
    for name, url in (("ESPN", "https://www.espn.com/espn/rss/tennis/news"),
                      ("BBC", "https://feeds.bbci.co.uk/sport/tennis/rss.xml")):
        try:
            r = requests.get(url, timeout=15, headers=UA)
            soup = BeautifulSoup(r.text, "xml")
            for it in soup.find_all("item"):
                t, d, p = it.find("title"), it.find("description"), it.find("pubDate")
                pub = None
                if p is not None:
                    try:
                        pub = email.utils.parsedate_to_datetime(p.get_text(strip=True)).date()
                    except (TypeError, ValueError):
                        pub = None
                out.append((name, t.get_text(strip=True) if t else "", d.get_text(strip=True) if d else "", pub))
        except Exception as e:  # noqa: BLE001
            out.append((name, f"(izvor nedostupan: {str(e)[:60]})", "", None))
    return out


def main():
    am = load("analyzed_matches")
    wk = [r for r in am if "2026-10-19" <= str(r.get("match_date"))[:10] <= "2026-10-25"]
    names = sorted({r[k] for r in wk for k in ("player1", "player2") if r.get(k)})
    print(f"=== E1. Panel ESPN + BBC (dohvat {TODAY}), igrača TJEDNA: {len(names)}")
    heads = feeds()
    by_src = collections.Counter(h[0] for h in heads)
    pubs = sorted(h[3] for h in heads if h[3])
    print(f"  naslova: {dict(by_src)}; datumi od {pubs[0] if pubs else '-'} do {pubs[-1] if pubs else '-'}")
    if pubs:
        ages = [(TODAY - p).days for p in pubs]
        print(f"  starost naslova (dana): medijan {sorted(ages)[len(ages)//2]}, najstariji {max(ages)}, "
              f"mlađih od 14 dana {sum(a <= 14 for a in ages)} od {len(ages)}")
    hits = 0
    for nm in names:
        sn = nm.split()[-1].lower() if nm.split() else ""
        if len(sn) < 4:
            continue
        rel = [h for h in heads if sn in (h[1] + " " + h[2]).lower()]
        for src, ti, de, pub in rel:
            hits += 1
            age = (TODAY - pub).days if pub else None
            print(f"  [{nm}] ({src}, {pub}, {age} d) {ti[:110]}")
    print(f"  ukupno pogodaka panela za igrače TJEDNA: {hits}")

    print("\n=== E2. Google News po igraču (snapshot p*_gnews), TJEDAN")
    n_players, with_items, items_all = 0, 0, []
    for r in wk:
        cs = r.get("context_snapshot") or {}
        md = dt.date.fromisoformat(str(r["match_date"])[:10])
        for k, pk in (("p1_gnews", "player1"), ("p2_gnews", "player2")):
            g = cs.get(k)
            if g is None:
                continue
            n_players += 1
            its = g.get("items") or []
            if its:
                with_items += 1
            for it in its:
                try:
                    d = dt.date.fromisoformat(str(it.get("d"))[:10])
                except ValueError:
                    d = None
                items_all.append({"player": r[pk], "age": (md - d).days if d else None, "t": it.get("t") or "",
                                  "s": it.get("s"), "bet": it.get("bet"), "inj": it.get("inj") or []})
    print(f"  igrač-analiza: {n_players}; s barem jednim naslovom: {with_items}; naslova ukupno: {len(items_all)}")
    ages = [x["age"] for x in items_all if x["age"] is not None]
    if ages:
        print(f"  starost naslova naspram datuma meča: medijan {sorted(ages)[len(ages)//2]} d, "
              f"0-2 d {sum(a <= 2 for a in ages)}, 3-7 d {sum(3 <= a <= 7 for a in ages)}, 8-14 d {sum(8 <= a <= 14 for a in ages)}")
    kinds = collections.Counter()
    for x in items_all:
        surname = x["player"].split()[-1].lower()
        if x["inj"]:
            kinds["ozljeda/odustajanje"] += 1
        elif x["bet"]:
            kinds["kladionica/prognoza"] += 1
        elif surname not in x["t"].lower():
            kinds["ne spominje prezime u naslovu"] += 1
        elif PREVIEW.search(x["t"]):
            kinds["najava/rezultat/statistika meča"] += 1
        else:
            kinds["ostalo (priča, intervju, vijest)"] += 1
    print("  vrste naslova:", dict(kinds))
    print("  --- ozljede (svi naslovi s oznakom)")
    for x in items_all:
        if x["inj"]:
            print(f"    [{x['player']}] {x['age']} d: {x['t'][:120]} | {x['inj']}")
    random.seed(25)
    print("  --- slučajni uzorak 30 naslova 'ostalo' i 'ne spominje prezime' za ručnu provjeru")
    pool = [x for x in items_all if not x["inj"] and not x["bet"] and
            (x["player"].split()[-1].lower() not in x["t"].lower() or not PREVIEW.search(x["t"]))]
    for x in random.sample(pool, min(30, len(pool))):
        print(f"    [{x['player']}] {x['age']} d ({x['s']}): {x['t'][:130]}")


if __name__ == "__main__":
    main()
