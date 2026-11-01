# -*- coding: utf-8 -*-
"""Skeptik 01.11.2026 - G1 ('ubojica diva') neovisno: vlastiti ELO (po datumu) i definicija iz PRAGOVA.
Provjerava n i edge ukupno i po rundi (osobito F, n=24 iz kojeg je nastao H4 u planu C). Samo cita."""
import math
import os
from collections import defaultdict

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jovin\Desktop\Tenis Claude"
td = pd.read_pickle(os.path.join(ROOT, ".cache", "lab", "td_joined.pkl"))
tml = pd.read_pickle(os.path.join(ROOT, ".cache", "lab", "tml.pkl"))
td = td[td["tml_idx"].notna()].copy()
td["tml_idx"] = td["tml_idx"].astype(int)
td = td.drop_duplicates("tml_idx").reset_index(drop=True)
td = td[td["p_fair"].notna()].reset_index(drop=True)
date = tml["approx_date"].copy()
ex = pd.Series(dict(zip(td["tml_idx"], td["Date"])))
date.loc[ex.index] = ex.values
tml = tml.assign(date=date)

# ---- ELO po DATUMU (538-stil, K=250/(n+5)^0.4), pre-match vrijednosti
order = tml.sort_values(["date", "t_start", "rord"]).index
R = defaultdict(lambda: 1500.0)
N = defaultdict(int)
pre = {}
wid, lid, sc = tml["winner_id"], tml["loser_id"], tml["score"]
for idx in order:
    w, l = wid[idx], lid[idx]
    if pd.isna(w) or pd.isna(l):
        continue
    pre[idx] = (R[w], R[l])
    s = str(sc[idx]) if isinstance(sc[idx], str) else ""
    if "W/O" in s.upper() or not s.strip():
        continue
    e = 1.0 / (1.0 + 10 ** ((R[l] - R[w]) / 400.0))
    kw, kl = 250.0 / (N[w] + 5) ** 0.4, 250.0 / (N[l] + 5) ** 0.4
    R[w] += kw * (1 - e)
    R[l] -= kl * (1 - e)
    N[w] += 1
    N[l] += 1

# ---- glavni zdrijeb po igracu
main = tml[tml["src"] == "main"]
by_player = defaultdict(list)
for idx, w, l, tid, dt, rord, rk_w, rk_l in zip(main.index, main["winner_id"], main["loser_id"], main["tourney_id"], main["date"],
                                              main["rord"], main["winner_rank"], main["loser_rank"]):
    by_player[w].append((dt, rord, tid, idx, 1, rk_l))
    by_player[l].append((dt, rord, tid, idx, 0, rk_w))
for k in by_player:
    by_player[k].sort(key=lambda x: (x[0], x[1]))

tm = tml.loc[td["tml_idx"]].reset_index(drop=True)
rows = []
for i in range(len(td)):
    cd = td["Date"].iat[i]
    tid = tm["tourney_id"].iat[i]
    idx = td["tml_idx"].iat[i]
    pw = td["p_fair"].iat[i]
    ew, el = pre[idx]
    for side, pid, e_me, e_opp, won, p in (("w", tm["winner_id"].iat[i], ew, el, 1, pw), ("l", tm["loser_id"].iat[i], el, ew, 0, 1 - pw)):
        lst = by_player.get(pid, [])
        prev = [x for x in lst if x[2] == tid and x[0] < cd]
        if not prev:
            continue
        d_, r_, t_, pidx, pwon, orank = prev[-1]
        if not pwon or pd.isna(orank) or orank > 15:
            continue
        pw_pre, pl_pre = pre[pidx]
        # moj pre-ELO i protivnikov na taj raniji mec
        my_pre, op_pre = (pw_pre, pl_pre)     # pobjednik tog meca je 'pid' (pwon==1)
        if op_pre - my_pre >= 50 and e_me > e_opp:
            rows.append((won, p, td["half"].iat[i], tm["round"].iat[i], i))
print("G1 (neovisno) n =", len(rows))


def st(rs):
    r = np.array([x[0] - x[1] for x in rs])
    if len(r) < 3:
        return None
    m = r.mean(); se = r.std(ddof=1) / math.sqrt(len(r))
    return len(r), 100 * m, 100 * (m - 1.96 * se), 100 * (m + 1.96 * se)


a = st(rows)
print("G1 ukupno: n=%d edge %+.1f [%+.1f, %+.1f]" % a, "| njihovo: n=245 +0.5 [-5.4, +6.4]")
for h in ("P1", "P2"):
    b = st([x for x in rows if x[2] == h])
    print("  ", h, "n=%d edge %+.1f [%+.1f, %+.1f]" % b)
for rd in ("R64", "R32", "R16", "QF", "SF", "F"):
    b = st([x for x in rows if x[3] == rd])
    if b:
        print("   runda %-4s n=%3d edge %+6.1f [%+6.1f, %+6.1f]" % ((rd,) + b))
# koliko je finala gdje su OBA finalista 'ubojice'
fin = [x for x in rows if x[3] == "F"]
ids = [x[4] for x in fin]
print("finalnih redaka:", len(fin), "| razlicitih mecava:", len(set(ids)))
# placebo: 'najgora celija od 6 rundi' pod nulom (permutacija ishoda unutar mecava nije moguca; koristimo parametarski bootstrap)
rng = np.random.default_rng(5)
cells = {}
for rd in ("R64", "R32", "R16", "QF", "SF", "F"):
    cells[rd] = [x for x in rows if x[3] == rd]
mins = []
for _ in range(5000):
    zs = []
    for rd, cl in cells.items():
        if len(cl) < 10:
            continue
        p = np.array([x[1] for x in cl])
        w = (rng.random(len(p)) < p).astype(float)
        r = w - p
        zs.append(r.mean() / (r.std(ddof=1) / math.sqrt(len(r))))
    mins.append(min(zs))
obs = (-20.1 / ((20.1 + 18.5) / 2 / 1.96))  # z ~ -2,0 (po njihovom intervalu [-38.6,-1.7])
print("pod nulom: P(najgora od 6 celija ima z <= -2,0) = %.3f" % (np.array(mins) <= -2.0).mean())
