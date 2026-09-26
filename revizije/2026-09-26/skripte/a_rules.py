# -*- coding: utf-8 -*-
"""Revizija 26.09.2026 — procjena kandidatskih pravila: koliko gubitaka uklanja, koliko
pobjeda usput ubija, edge i ROI izbacene naspram zadrzane skupine, i drzi li se u obje
polovice korpusa (do 22.08. / od 23.08.) — gruba zamjena za replikaciju."""
import numpy as np, pandas as pd, base

j = pd.read_pickle("classified.pkl")
j = j[j.win.notna() & j.p_dev.notna()].copy()
j["period"] = np.where(j.date < "2026-08-23", "A", "B")

RULES = {
    "R1 kvota 1,35-1,60 (rupa)": lambda d: (d.odds >= 1.35) & (d.odds < 1.60),
    "R1b kvota 1,43-1,60 (postojeca zona)": lambda d: (d.odds >= 1.43) & (d.odds < 1.60),
    "R2 screenshot autsajder (p<0,50)": lambda d: d.p_dev < 0.50,
    "R3 runda R16/QF": lambda d: d["round"].isin(["R16", "QF"]),
    "R4 pouzdanost 65-68 (nakon kazni)": lambda d: (d.conf >= 65) & (d.conf < 68),
    "R5 specijalist podloge": lambda d: (d.d_elo_s > 0) & (d.d_elo_o <= 0),
    "R6 model 8pp+ iznad trzista": lambda d: (d.conf / 100 - d.p_dev) >= 0.08,
    "R7 konsenzus NE podupire (gap<+1)": lambda d: d.cons_gap.notna() & (d.cons_gap < 1),
    "R8 protivnik bolja povijest turnira": lambda d: d.d_tbest < 0,
    "R9 pick stariji 4+ god": lambda d: d.d_age >= 4,
    "R10 K15 manje ATP pobjeda u sezoni (<-10)": lambda d: d.seas_w_d <= -10,
    "R11 Med-Low profil naseg picka": lambda d: d.scout_p == "Med-Low",
    "R12 pick s losijim ELO podloge": lambda d: d.d_elo_s < 0,
}


def grp(d):
    if len(d) == 0:
        return dict(n=0)
    return dict(n=len(d), L=int((d.win == 0).sum()), W=int((d.win == 1).sum()),
                edge=round(100 * (d.win.mean() - d.p_dev.mean()), 1), roi=round(100 * d.roi.mean(), 1))


rows = []
for surf in ["all", "hard"]:
    s = j if surf == "all" else j[j.surface == "hard"]
    for name, f in RULES.items():
        m = f(s).fillna(False).astype(bool)
        a, b = grp(s[m]), grp(s[~m])
        pa, pb = grp(s[m & (s.period == "A")]), grp(s[m & (s.period == "B")])
        ka, kb = grp(s[~m & (s.period == "A")]), grp(s[~m & (s.period == "B")])
        rows.append(dict(podloga=surf, pravilo=name, izbaceno_n=a.get("n"), L_uklonjeno=a.get("L"),
                         W_ubijeno=a.get("W"), edge_izbac=a.get("edge"), roi_izbac=a.get("roi"),
                         edge_zadrz=b.get("edge"), roi_zadrz=b.get("roi"),
                         edge_izbac_A=pa.get("edge"), n_A=pa.get("n"), edge_izbac_B=pb.get("edge"), n_B=pb.get("n"),
                         rel_A=(round(pa["edge"] - ka["edge"], 1) if pa.get("n") and ka.get("n") else None),
                         rel_B=(round(pb["edge"] - kb["edge"], 1) if pb.get("n") and kb.get("n") else None)))
out = pd.DataFrame(rows)
pd.set_option("display.width", 260); pd.set_option("display.max_columns", 30)
print(out.to_string(index=False))
out.to_csv("out_rules.csv", index=False)
print("\nBAZA: sve", grp(j), " hard", grp(j[j.surface == "hard"]))
