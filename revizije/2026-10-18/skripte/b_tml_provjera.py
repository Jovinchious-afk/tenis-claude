# -*- coding: utf-8 -*-
"""Provjera TML forme 12 mj. prije upotrebe (18.10.2026 15:43): pokrivenost, usporedivost, svježina,
pričuva — četiri uvjeta koja je korisnik prenio (prijedlog drugog modela) prije bilo kakve zamjene izvora.

Igrači: oba igrača svih analiza od 01.08.2026 i posebno od 27.09.2026 (dump .cache/rev_2026-10-18b).
Usporedba s RapidAPI vrijednostima iz snapshota (`p*_serve_pts_won`, `p*_return_won`,
`p*_return_won_weighted`). Tablica TML-a je na dan 18.10. — za STARIJE analize uključuje i mečeve
poslije analize, pa se ovdje mjeri samo pokrivenost i skala, ne prediktivnost.
    python revizije/2026-10-18/skripte/b_tml_provjera.py
"""
import json
import os
import sys
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from agent import tml_forma as T  # noqa: E402


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    table = T.load()
    print(f"TML tablica: {table.get('igraca')} igrača, podaci do {table.get('podaci_do')}, na dan {table.get('na_dan')}")
    am = json.load(open(os.path.join(ROOT, ".cache", "rev_2026-10-18b", "analyzed_matches.json"), encoding="utf-8"))
    for od in ("2026-08-01", "2026-09-27"):
        rows = [r for r in am if str(r.get("match_date"))[:10] >= od]
        players, both, both_ok, levels = {}, 0, 0, Counter()
        for r in rows:
            cs = r.get("context_snapshot") or {}
            ok_side = []
            for side in ("p1", "p2"):
                nm = r.get("player1" if side == "p1" else "player2")
                rec = T.lookup(nm, table)
                players[nm] = (rec, cs.get(f"{side}_serve_pts_won"), cs.get(f"{side}_return_won"),
                               cs.get(f"{side}_return_won_weighted"))
                ok_side.append(T.usable(rec))
            levels[r.get("tournament_level")] += 1
            both += 1
            both_ok += all(ok_side)
        n = len(players)
        found = sum(1 for v in players.values() if v[0])
        usable = sum(1 for v in players.values() if T.usable(v[0]))
        print(f"\n== analize od {od}: {len(rows)} mečeva, {n} igrača")
        print(f"  POKRIVENOST: nađen u TML-u {found}/{n} ({100 * found / n:.0f}%), upotrebljiv (≥300+300 poena) "
              f"{usable}/{n} ({100 * usable / n:.0f}%) | mečevi s OBA upotrebljiva: {both_ok}/{both} ({100 * both_ok / both:.0f}%)")
        miss = [nm for nm, v in players.items() if not v[0]]
        print(f"  nisu nađeni (primjeri): {miss[:12]}")
        # usporedivost
        ds, dr, drw, xs, ys, xr, yr = [], [], [], [], [], [], []
        for nm, (rec, s_api, r_api, rw_api) in players.items():
            if not T.usable(rec):
                continue
            if isinstance(s_api, (int, float)) and s_api > 0:
                ds.append(100 * rec["s"] - s_api)
                xs.append(100 * rec["s"])
                ys.append(s_api)
            if isinstance(r_api, (int, float)) and r_api > 0:
                dr.append(100 * rec["r"] - r_api)
                xr.append(100 * rec["r"])
                yr.append(r_api)
            if isinstance(rw_api, (int, float)) and rw_api > 0:
                drw.append(100 * rec["r"] - rw_api)
        if ds:
            print(f"  USPOREDIVOST (TML 12 mj. − RapidAPI): servis {np.mean(ds):+.1f}pp (r={np.corrcoef(xs, ys)[0, 1]:.2f}, n={len(ds)}) | "
                  f"povrat {np.mean(dr):+.1f}pp (r={np.corrcoef(xr, yr)[0, 1]:.2f}) | povrat naspram ponderiranog "
                  f"RapidAPI {np.mean(drw):+.1f}pp (n={len(drw)})" if drw else "")
            big = sorted(((100 * players[nm][0]["r"] - players[nm][2], nm) for nm in players
                          if T.usable(players[nm][0]) and isinstance(players[nm][2], (int, float)) and players[nm][2] > 0))
            print(f"  najveći padovi povrata (TML 12 mj. niže od RapidAPI karijere): {[(nm, round(d, 1)) for d, nm in big[:6]]}")
            print(f"  najveći rast povrata: {[(nm, round(d, 1)) for d, nm in big[-4:]]}")
        # svježina
        last = [v[0].get("zadnji") for v in players.values() if v[0]]
        import datetime as _dt
        ref = _dt.date.fromisoformat(table.get("na_dan"))
        age = [(ref - _dt.date.fromisoformat(x)).days for x in last if x]
        print(f"  SVJEŽINA: zadnji meč igrača u TML-u — medijan prije {np.median(age):.0f} dana, "
              f"90. pct {np.percentile(age, 90):.0f} dana; podaci tablice do {table.get('podaci_do')}")
        print(f"  PRIČUVA: Nose bi koristio TML za {100 * both_ok / both:.0f}% mečeva, karijeru (RapidAPI) za ostatak; "
              f"razine: {dict(levels)}")


if __name__ == "__main__":
    main()
