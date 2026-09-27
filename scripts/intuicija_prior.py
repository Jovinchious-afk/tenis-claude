# -*- coding: utf-8 -*-
"""Intuicija — uči tržišni prior iz povijesnog laboratorija (27.09.2026 12:27).

Čita `.cache/lab/features.pkl` (napravi ga `revizije/2026-09-27/skripte/lab_features.py`) —
12.324 ATP meča 2022-2026 s poštenom cijenom (Pinnacle, inače prosjek kladionica). Svaki
meč daje dva retka (obje strane). Uči samo ODSTUPANJE od cijene po osobinama koje postoje
i uživo (pojas kvote, Grand Slam, razina, podloga, pauza 21+ dan) — `agent/intuicija.py`.

Sprema SAMO koeficijente u `config/intuicija_prior.json` (sirovi podaci ostaju lokalno:
uvjeti tennis-data.co.uk ne dopuštaju dijeljenje ni automatsko skidanje).

    python scripts/intuicija_prior.py          # nauči i spremi
    python scripts/intuicija_prior.py --dry    # samo ispiši, ne spremaj

Ponoviti kad korisnik osvježi `.cache/tennis-data/2026.xlsx` (nakon lab_data.py i lab_features.py).
"""
import datetime as _dt
import json
import math
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from agent import intuicija as it  # noqa: E402

LAB = os.path.join(ROOT, ".cache", "lab", "features.pkl")
OUT = os.path.join(ROOT, "config", "intuicija_prior.json")


def rows_from_lab(f: pd.DataFrame):
    rows, dates = [], []
    for r in f.itertuples(index=False):
        pf = r.p_fair
        if pf is None or (isinstance(pf, float) and math.isnan(pf)):
            continue
        try:
            ow, ol = float(r.AvgW), float(r.AvgL)
        except (TypeError, ValueError):
            continue
        if not (ow > 1 and ol > 1):
            continue
        lvl = str(r.Series)
        d = str(r.Date)[:10]
        rw = 0 if (r.rest_w is None or (isinstance(r.rest_w, float) and math.isnan(r.rest_w))) else r.rest_w
        rl = 0 if (r.rest_l is None or (isinstance(r.rest_l, float) and math.isnan(r.rest_l))) else r.rest_l
        rows.append((it.price_features(ow, lvl, r.Surface, rw, rl), float(pf), 1.0))
        rows.append((it.price_features(ol, lvl, r.Surface, rl, rw), 1.0 - float(pf), 0.0))
        dates += [d, d]
    return rows, dates


def main():
    dry = "--dry" in sys.argv
    f = pd.read_pickle(LAB)
    rows, dates = rows_from_lab(f)
    model = it.train(rows, it.PRIOR_FEATURES, dates)
    print(f"redaka (obje strane): {len(rows)}  | mečeva: {len(rows)//2}")
    if model.get("silent"):
        print(f"PRIOR ŠUTI: {model['silent']}")
    else:
        print(f"izabrana jačina kazne λ={model['lambda']}  | dobitak log-lossa na neviđenim mečevima "
              f"(novijih 30%): {model['val_gain']*1000:.3f} tisućinki")
        # Čitljivo: edge za tipičnog igrača s osobinom, uz cijenu 0,65 (favorit) ili 0,35.
        print("\nšto je naučio (edge u pp kad je osobina uključena, ostalo isključeno):")
        for k in it.PRIOR_FEATURES:
            base = {x: 0.0 for x in it.PRIOR_FEATURES}
            on = dict(base, **{k: 1.0})
            p = 0.35 if k in ("b_160_200", "b_ge200") else 0.65
            e_on = it.edge_pp(on, p, model, None)["prior_pp"]
            e_off = it.edge_pp(base, p, model, None)["prior_pp"]
            print(f"  {k:16s} {e_on - e_off:+5.2f}pp  (uz cijenu {p:.2f})")
    # Provjera na neviđenim mečevima: r(procjena, stvarni ostatak) na novijih 30%
    order = np.argsort(np.array(dates, dtype="datetime64[D]"), kind="stable")
    cut = int(len(rows) * (1 - it.VAL_SHARE))
    val = [rows[i] for i in order[cut:]]
    pred = [it.edge_pp(r[0], r[1], model if not model.get("silent") else None, None)["prior_pp"] for r in val]
    resid = [100 * (r[2] - r[1]) for r in val]
    r_val = float(np.corrcoef(pred, resid)[0, 1]) if np.std(pred) > 0 else 0.0
    print(f"\nr(procjena, stvarni ostatak) na neviđenim mečevima: {r_val:+.3f} (n={len(val)} strana)")
    model.update({
        "trained_at": _dt.datetime.now().strftime("%d.%m.%Y %H:%M"),
        "source": "tennis-data.co.uk 2022-2026 + TML, povijesni laboratorij 27.09.2026",
        "n_matches": len(rows) // 2, "val_r": r_val, "version": it.VERSION,
    })
    if dry:
        print("\n--dry: ništa nije spremljeno")
        return
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(model, fh, ensure_ascii=False, indent=1)
    print(f"\nspremljeno: {OUT}")


if __name__ == "__main__":
    main()
