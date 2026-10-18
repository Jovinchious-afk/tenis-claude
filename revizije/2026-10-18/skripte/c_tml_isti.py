# -*- coding: utf-8 -*-
"""Prelazak modela na TML — kriteriji B i C: isti mečevi (naše analize od 01.08.2026) i preslikavanje
pragova po kvantilima (18.10.2026 16:31). Pragovi: PRAGOVI_C_TML_PROMPT_2026-10-18.md (16:25).

TML vrijednosti se računaju ZA DATUM SVAKOG MEČA (samo mečevi prije njega; datumi iz povijesnog
laboratorija: točni gdje je meč spojen s tennis-data, inače procjena po rundi), kao mješavina
12 mj. i karijere (w = servisni poeni 12 mj. / (isti + 1.500)) — varijanta (c), izabrana kriterijem A.
RapidAPI vrijednosti su one iz snapshota (što je model tada vidio).
Ograničenje: LAB TML završava 06.10.2026, pa za Šangaj (07.–17.10.) 12 mj. ne vidi ranije runde
istog turnira (nekoliko mečeva od ~60 — zanemarivo za prosjek).
    python revizije/2026-10-18/skripte/c_tml_isti.py
"""
import json
import math
import os
import sys
from bisect import bisect_left

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from b_lab import (build_history, F_DATE, F_SV, F_1IN, F_1W, F_2W, F_SG, F_BPS, F_BPF, F_ACE,  # noqa: E402
                   F_OSV, F_O1IN, F_O1W, F_O2W, F_OSG, F_OBPS, F_OBPF, F_OK)
from agent.tml_forma import norm  # noqa: E402

K = 1500.0
FIELDS = (F_SV, F_1IN, F_1W, F_2W, F_SG, F_BPS, F_BPF, F_ACE, F_OSV, F_O1IN, F_O1W, F_O2W, F_OSG, F_OBPS, F_OBPF)
IX = {f: i for i, f in enumerate(FIELDS)}


def derive(s):
    g = lambda f: s[IX[f]]
    sv, osv, sg = g(F_SV), g(F_OSV), g(F_SG)
    if sv <= 0 or osv <= 0 or sg <= 0:
        return None
    return {"s": (g(F_1W) + g(F_2W)) / sv, "r": 1 - (g(F_O1W) + g(F_O2W)) / osv,
            "hold": 1 - (g(F_BPF) - g(F_BPS)) / sg, "first_in": g(F_1IN) / sv, "svpt": sv}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    LAB = os.path.join(ROOT, ".cache", "lab")
    td = pd.read_pickle(os.path.join(LAB, "td_joined.pkl"))
    tml = pd.read_pickle(os.path.join(LAB, "tml.pkl"))
    td = td[td["tml_idx"].notna()]
    exact = dict(zip(td["tml_idx"].astype(int), td["Date"]))
    hist = build_history(tml, exact, {})
    # po igraču: zapisi po DATUMU, prefiksni zbrojevi
    dates, pref = {}, {}
    for pid, recs in hist.items():
        rs = sorted(recs, key=lambda x: x[F_DATE])
        dates[pid] = [x[F_DATE] for x in rs]
        acc = np.zeros((len(rs) + 1, len(FIELDS)))
        for i, x in enumerate(rs):
            acc[i + 1] = acc[i] + (np.array([x[f] for f in FIELDS]) if x[F_OK] else 0)
        pref[pid] = acc
    # ime -> id
    name_id = {}
    for col_id, col_nm in (("winner_id", "winner_name"), ("loser_id", "loser_name")):
        for pid, nm in zip(tml[col_id], tml[col_nm]):
            if pd.notna(pid) and isinstance(nm, str):
                name_id[norm(nm)] = pid
    keys = list(name_id)

    def find(nm):
        k = norm(nm)
        if k in name_id:
            return name_id[k]
        toks = set(k.split())
        for test in (lambda kk: set(kk.split()) == toks,
                     lambda kk: len(kk.split()) >= 2 and set(kk.split()) <= toks):
            c = [kk for kk in keys if test(kk)]
            if len(c) == 1:
                return name_id[c[0]]
        return None

    def at(pid, d):
        d = pd.Timestamp(d)
        j = bisect_left(dates[pid], d)                   # strogo prije datuma meča
        lo = bisect_left(dates[pid], d - pd.Timedelta(days=365))
        car = pref[pid][j]
        y = pref[pid][j] - pref[pid][lo]
        dc, dy = derive(car), derive(y)
        if dc is None or dc["svpt"] < 300:
            return None
        w = (dy["svpt"] / (dy["svpt"] + K)) if dy else 0.0
        out = {k: (w * dy[k] + (1 - w) * dc[k]) if dy else dc[k] for k in ("s", "r", "hold", "first_in")}
        out["w"] = w
        return out

    am = json.load(open(os.path.join(ROOT, ".cache", "rev_2026-10-18b", "analyzed_matches.json"), encoding="utf-8"))
    rows = []
    for r in am:
        d = str(r.get("match_date"))[:10]
        if d < "2026-08-01":
            continue
        cs = r.get("context_snapshot") or {}
        rec = {"date": d, "surface": (r.get("surface") or "").lower(), "id": r.get("id")}
        ok = True
        for side, nm in (("p1", r.get("player1")), ("p2", r.get("player2"))):
            sv, rt, hp = cs.get(f"{side}_serve_pts_won"), cs.get(f"{side}_return_won"), cs.get(f"{side}_hold_pct")
            pid = find(nm)
            t = at(pid, d) if pid is not None and pid in dates else None
            if not all(isinstance(x, (int, float)) and x > 0 for x in (sv, rt, hp)) or t is None:
                ok = False
                break
            rec[f"{side}_api"] = (sv, rt, hp)
            rec[f"{side}_tml"] = (100 * t["s"], 100 * t["r"], 100 * t["hold"])
            rec[f"{side}_w"] = t["w"]
            rec[f"{side}_name"] = nm
        if not ok:
            continue
        pw, aw = r.get("predicted_winner"), r.get("actual_winner")
        o1, o2 = r.get("bookmaker_odds_p1"), r.get("bookmaker_odds_p2")
        try:
            p1d = (1 / float(o1)) / (1 / float(o1) + 1 / float(o2))
        except (TypeError, ValueError, ZeroDivisionError):
            p1d = None
        rec["p1_won"] = (1.0 if aw == r.get("player1") else 0.0) if aw in (r.get("player1"), r.get("player2")) else None
        rec["p1_price"] = p1d
        rows.append(rec)
    print(f"analiza od 01.08. s RapidAPI i TML (u trenutku meča) za oba igrača: {len(rows)}")
    print(f"  težina 12 mj. u mješavini: medijan {np.median([x[k] for x in rows for k in ('p1_w', 'p2_w')]):.2f}")

    def gaps(src, i):
        return np.array([x[f"p1_{src}"][i] - x[f"p2_{src}"][i] for x in rows])

    out = {}
    print("\nC. PRESLIKAVANJE PRAGOVA (isti udio okidanja)")
    for name, i, olds in (("servis (poeni)", 0, (2.5, 5.0)), ("povrat (poeni)", 1, (2.0,))):
        ga, gt = np.abs(gaps("api", i)), np.abs(gaps("tml", i))
        for th in olds:
            share = (ga >= th).mean()
            new = float(np.quantile(gt, 1 - share))
            out[f"{name}_{th}"] = round(new, 2)
            print(f"  {name}: razlika ≥ {th}pp okida u {100 * share:.0f}% mečeva -> TML prag {new:.2f}pp")
    ga, gt = np.abs(gaps("api", 2)), np.abs(gaps("tml", 2))
    share = (ga >= 5.0).mean()
    out["hold_gap_5"] = round(float(np.quantile(gt, 1 - share)), 2)
    print(f"  hold razlika ≥ 5pp (izvedeni) okida u {100 * share:.0f}% -> izmjereni TML hold prag {out['hold_gap_5']:.2f}pp")
    # igrači (jedan zapis po igraču, zadnji)
    pl = {}
    for x in rows:
        for side in ("p1", "p2"):
            pl[x[f"{side}_name"]] = (x[f"{side}_api"], x[f"{side}_tml"])
    api_h = np.array([v[0][2] for v in pl.values()])
    tml_h = np.array([v[1][2] for v in pl.values()])
    api_s = np.array([v[0][0] for v in pl.values()])
    tml_s = np.array([v[1][0] for v in pl.values()])
    for th in (88.0, 85.0):
        share = (api_h >= th).mean()
        new = float(np.quantile(tml_h, 1 - share))
        out[f"hold_{th}"] = round(new, 1)
        print(f"  hold ≥ {th:.0f}% (izvedeni): {100 * share:.0f}% igrača -> izmjereni hold {new:.1f}%")
    share = (api_s >= 70.0).mean()
    out["serve_70"] = round(float(np.quantile(tml_s, 1 - share)), 1)
    print(f"  servis ≥ 70%: {100 * share:.0f}% igrača -> TML {out['serve_70']:.1f}%")
    print(f"  r(izmjereni hold, servisni poeni) na TML-u: {np.corrcoef(tml_h, tml_s)[0, 1]:.2f} (n={len(pl)} igrača)")

    # B. isti mečevi: smjer i okidanje
    res = [x for x in rows if x["p1_won"] is not None]
    print(f"\nB. ISTI MEČEVI (riješeni: {len(res)})")
    for src, lab in (("api", "RapidAPI (karijera, što je model vidio)"), ("tml", "TML 12 mj. + karijera (novo)")):
        comp = np.array([(x[f"p1_{src}"][0] + x[f"p1_{src}"][1]) - (x[f"p2_{src}"][0] + x[f"p2_{src}"][1]) for x in res])
        won = np.array([x["p1_won"] for x in res])
        nz = comp != 0
        acc = ((comp[nz] > 0) == (won[nz] == 1)).mean()
        pr = [x for x in res if x["p1_price"] is not None]
        c2 = np.array([(x[f"p1_{src}"][0] + x[f"p1_{src}"][1]) - (x[f"p2_{src}"][0] + x[f"p2_{src}"][1]) for x in pr])
        y2 = np.array([x["p1_won"] - x["p1_price"] for x in pr])
        rr = float(np.corrcoef(np.concatenate([c2, -c2]), np.concatenate([y2, -y2]))[0, 1])
        print(f"  {lab:42s} strana s boljim servis+povrat pobijedi {100 * acc:.1f}% (n={nz.sum()}) | "
              f"r(razlika, ishod − cijena) {rr:+.3f} (n={len(pr)})")
    def cat(g, lo, hi):
        a = abs(g)
        return "nikakva" if a < lo else ("slaba" if a < hi else "puna")
    old = [cat(x["p1_api"][0] - x["p2_api"][0], 2.5, 5.0) for x in rows]
    new = [cat(x["p1_tml"][0] - x["p2_tml"][0], out["servis (poeni)_2.5"], out["servis (poeni)_5.0"]) for x in rows]
    from collections import Counter
    print(f"  servisna potvrda STARO {dict(Counter(old))} | NOVO {dict(Counter(new))} | ista oznaka u "
          f"{100 * np.mean([a == b for a, b in zip(old, new)]):.0f}% mečeva")
    side_old = [np.sign(x["p1_api"][0] - x["p2_api"][0]) for x in rows]
    side_new = [np.sign(x["p1_tml"][0] - x["p2_tml"][0]) for x in rows]
    print(f"  bolji server ista strana u {100 * np.mean([a == b for a, b in zip(side_old, side_new)]):.0f}% mečeva")
    side_old = [np.sign(x["p1_api"][1] - x["p2_api"][1]) for x in rows]
    side_new = [np.sign(x["p1_tml"][1] - x["p2_tml"][1]) for x in rows]
    print(f"  bolji povratnik ista strana u {100 * np.mean([a == b for a, b in zip(side_old, side_new)]):.0f}% mečeva")
    # pomak skale za pričuvu (RapidAPI -> TML mješavina)
    ds = np.mean([v[1][0] - v[0][0] for v in pl.values()])
    dr = np.mean([v[1][1] - v[0][1] for v in pl.values()])
    out["pricuva_servis_pomak"] = round(float(ds), 2)
    out["pricuva_povrat_pomak"] = round(float(dr), 2)
    print(f"\nD. pričuva: prosječni pomak RapidAPI -> TML mješavina: servis {ds:+.2f}pp, povrat {dr:+.2f}pp")
    json.dump(out, open(os.path.join(ROOT, ".cache", "rev_2026-10-18b", "c_tml_pragovi.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
