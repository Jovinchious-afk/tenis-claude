# -*- coding: utf-8 -*-
"""Intuicija — izvještaj: što je naučila, koliko vrijedi, i je li prošla kapiju (27.09.2026 12:29).

SAMO ČITA (Supabase + config/intuicija_prior.json). Ništa ne mijenja.

    python scripts/intuicija_report.py

Tri dijela:
  1. prior iz povijesti (tržišni obrasci) — što je u datoteci;
  2. naš sloj — nauči se kao u dnevnom runu i ispiše što je naučio (ili zašto šuti), pa
     "kako bi prošla da je postojala": za svaki mjesec uči SAMO na ranijim mečevima i
     procjenjuje taj mjesec (nikad ne vidi ishod koji procjenjuje);
  3. u sjeni (od 28.09.2026): prave procjene zapisane PRIJE meča (`context_snapshot.intuicija`)
     naspram ishoda — mjerodavno za kapiju K20 (DECISION_INPUTS).
"""
import os
import sys
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))
from agent import intuicija as it  # noqa: E402
from database import supabase_client as db  # noqa: E402


def r_and_terciles(pred, resid):
    pred, resid = np.array(pred), np.array(resid)
    if len(pred) < 10 or np.std(pred) == 0:
        return None
    r = float(np.corrcoef(pred, resid)[0, 1])
    q1, q2 = np.quantile(pred, [1 / 3, 2 / 3])
    terc = [float(resid[pred <= q1].mean()), float(resid[(pred > q1) & (pred <= q2)].mean()),
            float(resid[pred > q2].mean())]
    se = 1 / np.sqrt(len(pred))
    return {"n": len(pred), "r": r, "r_lo": r - 1.96 * se, "r_hi": r + 1.96 * se, "terc": terc}


def main():
    prior = it.load_prior()
    print("=== 1. PRIOR IZ POVIJESTI ===")
    if not prior:
        print("  nema config/intuicija_prior.json — pokreni scripts/intuicija_prior.py")
    elif prior.get("silent"):
        print(f"  šuti: {prior['silent']}")
    else:
        print(f"  naučen {prior.get('trained_at')} na {prior.get('n_matches')} mečeva; λ={prior.get('lambda')}; "
              f"r na neviđenim mečevima {prior.get('val_r', 0):+.3f}")

    raw = it.fetch_resolved(db)
    rows, dates = it.resolved_training_rows(raw)
    print(f"\n=== 2. NAŠ SLOJ (riješenih analiza: {len(rows)//2}) ===")
    own = it.train(rows, it.OWN_FEATURES, dates, prior=prior) if len(rows) // 2 >= it.MIN_TRAIN_ROWS \
        else {"silent": f"premalo analiza (< {it.MIN_TRAIN_ROWS})"}
    if own.get("silent"):
        print(f"  šuti: {own['silent']}")
    else:
        print(f"  λ={own['lambda']}, dobitak na novijih 30%: {own['val_gain']*1000:.3f} tisućinki log-lossa")
        coefs = sorted(zip(own["features"], own["beta"]), key=lambda x: -abs(x[1]))
        print("  najjači utjecaji (+ = strana prolazi bolje od cijene; po 1 standardnoj devijaciji):")
        for k, b in coefs[:8]:
            print(f"    {k:14s} {b:+.3f} logit  (≈ {100 * 0.2275 * b:+.2f}pp uz cijenu 0,65)")

    # Kako bi prošla da je postojala: mjesec po mjesec, uči samo na ranijem.
    by_month = defaultdict(list)
    for (f, p, won), d in zip(rows, dates):
        by_month[d[:7]].append((f, p, won, d))
    months = sorted(by_month)
    pred, resid, dog_pred, dog_resid = [], [], [], []
    for i, mth in enumerate(months):
        past = [(f, p, w) for m2 in months[:i] for (f, p, w, _d) in by_month[m2]]
        past_d = [d for m2 in months[:i] for (_f, _p, _w, d) in by_month[m2]]
        if len(past) // 2 < it.MIN_TRAIN_ROWS:
            continue
        mdl = it.train(past, it.OWN_FEATURES, past_d, prior=prior)
        cur = by_month[mth]
        for k in range(0, len(cur) - 1, 2):          # retci idu u parovima (obje strane meča)
            (f1, p1, w1, _d1), (f2, p2, w2, _d2) = cur[k], cur[k + 1]
            for (e, p, won) in zip(it.pair_edges(f1, p1, f2, p2, prior, mdl), (p1, p2), (w1, w2)):
                pred.append(e["edge_pp"])
                resid.append(100 * (won - p))
                if p < 0.5:
                    dog_pred.append(e["edge_pp"])
                    dog_resid.append(100 * (won - p))
    print("\n  KAKO BI PROŠLA (uči samo na ranijim mjesecima, procjenjuje sljedeći):")
    s = r_and_terciles(pred, resid)
    if not s:
        print("    premalo podataka za ovu provjeru")
    else:
        print(f"    strana: n={s['n']}  r={s['r']:+.3f} [{s['r_lo']:+.3f}, {s['r_hi']:+.3f}]  "
              f"ostatak po tercilama procjene: niska {s['terc'][0]:+.1f}pp | srednja {s['terc'][1]:+.1f}pp | "
              f"visoka {s['terc'][2]:+.1f}pp")
        sel = [(e, r) for e, r in zip(dog_pred, dog_resid) if e >= 3.0]
        if sel:
            print(f"    autsajderi kojima je dala +3pp ili više: n={len(sel)}, stvarni ostatak "
                  f"{np.mean([r for _e, r in sel]):+.1f}pp")
        else:
            print("    autsajdera s procjenom +3pp ili više: 0 (intuicija ih nije 'nanjušila')")

    print("\n=== 3. U SJENI (prave procjene zapisane prije meča) — kapija K20 ===")
    live = []
    for r in raw:
        cs = r.get("context_snapshot") or {}
        s_ = cs.get("intuicija") or {}
        pk = s_.get("pick") or {}
        w = r.get("actual_winner")
        if not pk or w not in (r.get("player1"), r.get("player2")):
            continue
        won = 1.0 if w == pk.get("player") else 0.0
        live.append((pk.get("edge_pp", 0.0), 100 * (won - pk.get("p", 0.5)), str(r.get("match_date"))[:10]))
    if len(live) < 10:
        print(f"  zapisanih i riješenih procjena: {len(live)} — kapija traži 300 (prvi zapisi od 28.09.2026)")
    else:
        s = r_and_terciles([x[0] for x in live], [x[1] for x in live])
        half = len(live) // 2
        s1 = r_and_terciles([x[0] for x in live[:half]], [x[1] for x in live[:half]])
        s2 = r_and_terciles([x[0] for x in live[half:]], [x[1] for x in live[half:]])
        print(f"  n={s['n']}  r={s['r']:+.3f} [{s['r_lo']:+.3f}, {s['r_hi']:+.3f}]  terciles "
              f"{s['terc'][0]:+.1f} / {s['terc'][1]:+.1f} / {s['terc'][2]:+.1f}pp  polovice r "
              f"{(s1 or {}).get('r', 0):+.3f} / {(s2 or {}).get('r', 0):+.3f}")
        ok = (s["n"] >= 300 and s["r"] >= 0.12 and s["r_lo"] > 0 and s["terc"][2] >= 3.0
              and s["terc"][2] - s["terc"][0] >= 3.0 and s1 and s2 and s1["r"] > 0 and s2["r"] > 0)
        print(f"  K20: {'PROŠLA — prijedlog korisniku' if ok else ('ČEKA (n < 300)' if s['n'] < 300 else 'NIJE PROŠLA — uči dalje u sjeni')}")


if __name__ == "__main__":
    main()
