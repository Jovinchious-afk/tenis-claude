# -*- coding: utf-8 -*-
"""Korisnikova ideja 2 (26.09.2026): "tablica promasaja po igracu" — koliko nas je puta
igrac srusio kad smo na njega tipovali; iznad prosjeka -2pp, ispod/nije na listi +2pp.

TRI TESTA:
 A) DOSLOVNA verzija na nasem korpusu, walk-forward (za svaki pick broji samo ranije,
    razrijesene pickove, s razmakom od 3 dana zbog neuskladjenih datuma).
 B) Ista ideja, ali VIŠAK promasaja naspram cijene (stvarno - ocekivano po devigiranoj
    kvoti), jer igrac kojeg cesto biramo kao favorita skupi vise poraza i kad je posve normalan.
 C) TRZISNA verzija na ~29.000 mečeva s kvotama: je li igracev ostatak naspram cijene
    POSTOJAN kroz vrijeme (prva polovica predvidja drugu)? Ako nije postojan ni na tisucama
    meceva, ne moze raditi ni na nasih ~450.
"""
import numpy as np, pandas as pd, base, pmbase

j = pd.read_pickle("classified.pkl")
j = j[j.win.notna()].sort_values("date").reset_index(drop=True)

# ---------------- A + B: walk-forward na nasem korpusu (sve podloge kumulativno)
recs = []
for i, r in j.iterrows():
    past = j[(j.date <= r.date - pd.Timedelta(days=3))]
    # sve podloge; broj NASIH pickova na tog igraca i koliko ih je izgubio
    mine = past[past.pick == r.pick]
    n_pick = len(mine)
    l_pick = int((mine.win == 0).sum())
    exp_l = float((1 - mine.p_dev).sum()) if mine.p_dev.notna().all() else np.nan
    # prosjek promasaja po igracu medju svima koje smo pickali (za 'iznad prosjeka')
    by = past.groupby("pick").win.apply(lambda s: (s == 0).sum())
    avg_l = by.mean() if len(by) else 0.0
    # protivnikova strana: koliko nas je puta ON srusio (kad smo pickali protiv njega)
    vs = past[past.opp == r.opp]
    l_vs = int((vs.win == 0).sum())
    recs.append(dict(i=i, n_pick=n_pick, l_pick=l_pick, avg_l=avg_l,
                     excess=(l_pick - exp_l) if not np.isnan(exp_l) else np.nan, l_vs=l_vs))
w = pd.DataFrame(recs).set_index("i")
j = j.join(w)
jp = j[j.p_dev.notna()].copy()

print("=== A) DOSLOVNO (korisnikova formulacija): pick iznad prosjeka promasaja -> -2pp; inace +2pp")
m_pen = jp.l_pick > jp.avg_l
for lab, m in [("kaznio bi (iznad prosjeka)", m_pen), ("nagradio bi (ispod/nije na listi)", ~m_pen)]:
    print("  ", base.edge_table(jp, m, lab))
print("   od toga 'nije na listi' (0 ranijih promasaja):", base.edge_table(jp, jp.l_pick == 0, ""))
for k in [1, 2, 3]:
    print(f"   pick nas je vec srusio >= {k}x:", base.edge_table(jp, jp.l_pick >= k, ""))

print("\n=== B) VIŠAK promasaja naspram cijene (pick izgubio vise nego sto je trziste ocekivalo)")
for lab, m in [("visak > +0,5", jp.excess > 0.5), ("oko nule", jp.excess.between(-0.5, 0.5)), ("manjak < -0,5", jp.excess < -0.5), ("bez povijesti", jp.excess.isna())]:
    print("  ", base.edge_table(jp, m, lab))
r, p, n = base.corr(jp.excess, jp.resid)
print(f"   r(visak promasaja, ostatak naspram cijene) = {r:+.3f} P={p:.3f} n={n}")

print("\n=== Obrnuta strana (protivnik nas je vec rusio) — referenca: 06.09. raslo monotono")
for k in [0, 1, 2, 3]:
    m = (jp.l_vs == k) if k < 3 else (jp.l_vs >= 3)
    print(f"   protivnik nas srusio {k}{'+' if k==3 else ''}x:", base.edge_table(jp, m, ""))

# ---------------- C: postojanost igracevog ostatka na trzistu (tisuce meceva)
pm, names = pmbase.load_matches()
p = pm[pm.o1.notna() & pm.o2.notna() & (pm.o1 > 1) & (pm.o2 > 1) & (pm.level.isin([2, 3, 4, 7]))].copy()
p["pw"] = (1 / p.o1) / (1 / p.o1 + 1 / p.o2)
long = pd.concat([
    pd.DataFrame(dict(pid=p.p1, date=p.date, won=1.0, pr=p.pw)),
    pd.DataFrame(dict(pid=p.p2, date=p.date, won=0.0, pr=1 - p.pw)),
])
long["res"] = long.won - long.pr
ours = set(pd.concat([j.pick_pid.dropna(), j.opp_pid.dropna()]).astype(str))
long = long[long.pid.isin(ours)]
print(f"\n=== C) TRZISNA POSTOJANOST: {long.pid.nunique()} igraca, {len(long)} nastupa (ATP/Masters/GS), kvote iz past-matches")
for lab, cut in [("do 30.06.2025 -> od 01.07.2025", "2025-07-01"), ("do 31.12.2025 -> 2026", "2026-01-01")]:
    a = long[long.date < cut].groupby("pid").res.agg(["mean", "size"])
    b = long[long.date >= cut].groupby("pid").res.agg(["mean", "size"])
    ab = a.join(b, lsuffix="_a", rsuffix="_b").dropna()
    ab = ab[(ab.size_a >= 20) & (ab.size_b >= 15)]
    r, pv, n = base.corr(ab.mean_a, ab.mean_b)
    print(f"   {lab}: igraca={n}  r(ostatak prije, ostatak poslije) = {r:+.3f} P={pv:.3f}")
    # samo kao favorit (Rublev hipoteza: 'nepouzdan favorit')
    fa = long[(long.pr >= 0.6)]
    a = fa[fa.date < cut].groupby("pid").res.agg(["mean", "size"])
    b = fa[fa.date >= cut].groupby("pid").res.agg(["mean", "size"])
    ab = a.join(b, lsuffix="_a", rsuffix="_b").dropna()
    ab = ab[(ab.size_a >= 15) & (ab.size_b >= 10)]
    r, pv, n = base.corr(ab.mean_a, ab.mean_b)
    print(f"      samo kad je FAVORIT (p>=0,60): igraca={n}  r = {r:+.3f} P={pv:.3f}")

# pojedinci koje je korisnik spomenuo
for nm in ["Rublev", "Buse"]:
    ids = [pid for pid, x in names.items() if x and nm.lower() in x.lower()]
    for pid in ids:
        s = long[long.pid == pid]
        f = s[s.pr >= 0.6]
        print(f"   {names[pid]}: svi {len(s)} meceva, ostatak {100*s.res.mean():+.1f}pp | kao favorit n={len(f)}: {100*f.won.mean():.1f}% naspram {100*f.pr.mean():.1f}% ({100*f.res.mean():+.1f}pp)")
        mine = j[j.pick == names[pid]]
        if len(mine):
            mp = mine[mine.p_dev.notna()]
            print(f"      kao NAS pick: {int(mine.win.sum())}W-{int((mine.win==0).sum())}L; naspram cijene {100*(mp.win.mean()-mp.p_dev.mean()):+.1f}pp (n={len(mp)})")
j.to_pickle("classified_idea2.pkl")
