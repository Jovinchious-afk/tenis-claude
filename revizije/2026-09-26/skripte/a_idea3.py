# -*- coding: utf-8 -*-
"""Korisnikova ideja 3 (26.09.2026): protiv kojeg protivnika (jaceg ili slabijeg) je igrac
gubio na OVOM turniru u zadnje 3 godine — ima li to prediktivnu moc?

"Jaci/slabiji" se mjeri KVOTOM tog starog meca (je li nas igrac tada bio favorit), jer je
to jedina mjera snage koju imamo za svaki povijesni mec bez curenja.
Izvor: berba past-matches (315 igraca, ~58.000 meceva, ~29.000 s kvotama).
Zastita od curenja: broje se samo mecevi >= 30 dana prije datuma naseg meca (dakle
PROSLA izdanja turnira), nikad tekuce izdanje.
"""
import numpy as np, pandas as pd, base, pmbase

j = pd.read_pickle("classified_idea2.pkl")
j = j[j.win.notna()].sort_values("date").reset_index(drop=True)
pm, names = pmbase.load_matches()
pm["city"] = pm.tname.fillna("").str.split(" - ").str[-1].str.strip().str.lower()
pm["pw"] = np.where(pm.o1.notna() & pm.o2.notna() & (pm.o1 > 1) & (pm.o2 > 1),
                    (1 / pm.o1) / (1 / pm.o1 + 1 / pm.o2), np.nan)
long = pd.concat([
    pd.DataFrame(dict(pid=pm.p1, date=pm.date, city=pm.city, won=1.0, pr=pm.pw, rid=pm.round_id)),
    pd.DataFrame(dict(pid=pm.p2, date=pm.date, city=pm.city, won=0.0, pr=1 - pm.pw, rid=pm.round_id)),
])
g = {k: v for k, v in long.groupby(["pid", "city"])}


def hist(pid, city, date):
    s = g.get((str(pid), city))
    if s is None:
        return dict(n=0, w=0, l=0, l_fav=0, l_dog=0, w_dog=0, res=np.nan, npr=0)
    s = s[(s.date <= date - pd.Timedelta(days=30)) & (s.date >= date - pd.Timedelta(days=3 * 365 + 30))]
    pr = s[s.pr.notna()]
    return dict(n=len(s), w=int(s.won.sum()), l=int((s.won == 0).sum()),
                l_fav=int(((pr.won == 0) & (pr.pr >= 0.55)).sum()),   # izgubio kao favorit = od SLABIJEG
                l_dog=int(((pr.won == 0) & (pr.pr <= 0.45)).sum()),   # izgubio kao autsajder = od JACEG
                w_dog=int(((pr.won == 1) & (pr.pr <= 0.45)).sum()),   # pobijedio kao autsajder
                res=float((pr.won - pr.pr).sum()) if len(pr) else np.nan, npr=len(pr))


rows = []
for r in j.itertuples():
    city = str(r.tournament or "").split(" - ")[-1].strip().lower()
    a = hist(r.pick_pid, city, r.date) if r.pick_pid else None
    b = hist(r.opp_pid, city, r.date) if r.opp_pid else None
    if a is None or b is None:
        rows.append({})
        continue
    rows.append({f"hp_{k}": v for k, v in a.items()} | {f"ho_{k}": v for k, v in b.items()})
h = pd.DataFrame(rows)
j = pd.concat([j, h], axis=1)
jp = j[j.p_dev.notna() & j.hp_n.notna()].copy()
print(f"n={len(jp)}; pick ima povijest ovdje: {(jp.hp_n>0).sum()}, protivnik: {(jp.ho_n>0).sum()}")

print("\n--- pick je ovdje ranije gubio KAO FAVORIT (od slabijeg) ---")
for lab, m in [("0 takvih poraza", jp.hp_l_fav == 0), ("1+", jp.hp_l_fav >= 1), ("2+", jp.hp_l_fav >= 2)]:
    print("  ", lab, base.edge_table(jp, m, ""))
print("   ... i DANAS je opet favorit (p>=0,55):")
for lab, m in [("0", (jp.hp_l_fav == 0) & (jp.p_dev >= .55)), ("1+", (jp.hp_l_fav >= 1) & (jp.p_dev >= .55))]:
    print("  ", lab, base.edge_table(jp, m, ""))
print("\n--- pick je ovdje ranije gubio KAO AUTSAJDER (od jaceg) ---")
for lab, m in [("0", jp.hp_l_dog == 0), ("1+", jp.hp_l_dog >= 1)]:
    print("  ", lab, base.edge_table(jp, m, ""))
print("\n--- PROTIVNIK je ovdje ranije gubio kao favorit (upset-sklon ovdje) ---")
for lab, m in [("0", jp.ho_l_fav == 0), ("1+", jp.ho_l_fav >= 1)]:
    print("  ", lab, base.edge_table(jp, m, ""))
print("\n--- ostatak naspram cijene NA OVOM TURNIRU (pick minus protivnik), kontinuirano ---")
jp["d_tres"] = jp.hp_res.fillna(0) - jp.ho_res.fillna(0)
for v in ["d_tres", "hp_res", "ho_res"]:
    r, p, n = base.corr(jp[v], jp.resid)
    b, se, z, pp, nn = base.offset_logit(jp[v], jp.win, jp.logit_p)
    print(f"   {v}: r(ostatak)={r:+.3f} P={p:.3f} n={n} | offset-logit z={z:+.2f} P={pp:.3f}")
jp["d_wr_here"] = (jp.hp_w / jp.hp_n.replace(0, np.nan)).fillna(0.5) - (jp.ho_w / jp.ho_n.replace(0, np.nan)).fillna(0.5)
r, p, n = base.corr(jp.d_wr_here, jp.resid)
print(f"   razlika u postotku pobjeda OVDJE: r(ostatak)={r:+.3f} P={p:.3f} n={n}")
for per, m0 in [("do 22.08", jp.date < "2026-08-23"), ("od 23.08", jp.date >= "2026-08-23")]:
    r, p, n = base.corr(jp.d_tres[m0], jp.resid[m0])
    print(f"      {per}: r={r:+.3f} n={n}")
j.to_pickle("classified_idea3.pkl")
