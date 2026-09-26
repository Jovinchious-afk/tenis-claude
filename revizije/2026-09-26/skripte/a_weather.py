# -*- coding: utf-8 -*-
"""Vrijeme, dob i visina (26.09.2026).
DIO 1 — OPISNO (post-match): kako uvjeti/dob/visina mijenjaju statistiku u mecu, na razini
         IGRACA-NASTUPA (oba igraca svakog meca), uz ogradu da to NIJE predikcija.
DIO 2 — PREDIKTIVNO: interakcije uvjeta sa servisnim profilom naseg picka naspram cijene.
Svaka interakcija se testira i na dvije polovice korpusa; broji se koliko bi ih ispalo
"znacajno" slucajno (ocekivanje pod nul-hipotezom).
"""
import numpy as np, pandas as pd, base

j = pd.read_pickle("classified_idea3.pkl")
j = j[j.win.notna()].copy()

# --------------------------------------------------- DIO 1: post-match, po nastupu
rows = []
for r in j.itertuples():
    for side, pre in (("p", "pm_"), ("o", "pmo_")):
        sw = getattr(r, pre + "serve_won");
        if pd.isna(sw):
            continue
        rows.append(dict(temp=r.temp, hum=r.hum, wind=r.wind, press=r.press, shielded=r.shielded,
                         age=getattr(r, f"age_{side}"), h=getattr(r, f"h_{side}"),
                         serve_season=getattr(r, f"serve_{side}"),
                         serve=sw, first_in=getattr(r, pre + "first_in"), first_won=getattr(r, pre + "first_won"),
                         second_won=getattr(r, pre + "second_won"), ace=getattr(r, pre + "ace_rate"),
                         df=getattr(r, pre + "df_rate"), ret=getattr(r, pre + "ret_won"), tp=getattr(r, pre + "tp_share"),
                         bp_saved=getattr(r, pre + "bp_saved_pct"), bp_conv=getattr(r, pre + "bp_conv_pct"),
                         winners=getattr(r, pre + "winners"), ue=getattr(r, pre + "ue")))
P = pd.DataFrame(rows)
P["serve_vs_season"] = P.serve * 100 - P.serve_season
print(f"nastupa s post-match statistikom: {len(P)}; s vremenom: {P.temp.notna().sum()}")
print("\nr(uvjet ili igrac, statistika u mecu)   [n u zagradi]")
stats = ["serve", "serve_vs_season", "first_in", "first_won", "second_won", "ace", "df", "ret", "tp", "bp_saved", "bp_conv", "winners", "ue"]
tab = []
for x in ["temp", "hum", "wind", "press", "age", "h"]:
    row = {"varijabla": x}
    for s in stats:
        r_, p_, n_ = base.corr(P[x], P[s])
        row[s] = f"{r_:+.2f}{'*' if p_ < 0.01 else ''}" if not np.isnan(r_) else ""
    row["n"] = int(P[[x, "serve"]].dropna().shape[0])
    tab.append(row)
pd.set_option("display.width", 260)
print(pd.DataFrame(tab).to_string(index=False))
print("  (* = P<0,01; testova je 6x13=78, pa ~0,8 zvjezdica ocekujemo slucajno)")

# --------------------------------------------------- DIO 2: prediktivno, pick naspram cijene
jp = j[j.p_dev.notna() & j.temp.notna()].copy()
jp["hot"] = (jp.temp >= 28).astype(float)
jp["humid"] = (jp.hum >= 70).astype(float)
jp["windy"] = (jp.wind >= 15).astype(float)
jp["pick_bigserver"] = (jp.d_serve >= 3).astype(float)
jp["pick_taller"] = (jp.d_h >= 5).astype(float)
jp["pick_older"] = (jp.d_age >= 3).astype(float)
jp["pick_ss_better"] = (jp.d_ss_won >= 3).astype(float)
jp["pick_ret_better"] = (jp.d_ret >= 2).astype(float)
half = jp.date <= jp.date.median()
print(f"\nPREDIKTIVNE INTERAKCIJE (n={len(jp)} pickova s vremenom i cijenom); ostatak = pobjeda - devig cijena")
res = []
for w in ["hot", "humid", "windy"]:
    for s in ["pick_bigserver", "pick_taller", "pick_older", "pick_ss_better", "pick_ret_better"]:
        m = (jp[w] == 1) & (jp[s] == 1)
        mo = (jp[w] == 0) & (jp[s] == 1)
        a = jp[m]; b = jp[mo]
        if len(a) < 8:
            continue
        diff = a.resid.mean() - b.resid.mean()
        h1 = jp[m & half].resid.mean() - jp[mo & half].resid.mean()
        h2 = jp[m & ~half].resid.mean() - jp[mo & ~half].resid.mean()
        # permutacijski P za razliku
        rng = np.random.default_rng(11)
        pool = np.concatenate([a.resid.values, b.resid.values]).copy()
        cnt = 0
        for _ in range(2000):
            rng.shuffle(pool)
            if abs(pool[:len(a)].mean() - pool[len(a):].mean()) >= abs(diff):
                cnt += 1
        res.append(dict(uvjet=w, profil=s, n_uvjet=len(a), n_bez=len(b), razlika_pp=round(100 * diff, 1),
                        polovica1=round(100 * h1, 1) if not np.isnan(h1) else None,
                        polovica2=round(100 * h2, 1) if not np.isnan(h2) else None, P_perm=round(cnt / 2000, 3)))
R = pd.DataFrame(res)
print(R.to_string(index=False))
print(f"testova: {len(R)}; ocekivano 'znacajnih' (P<0,05) slucajno: {0.05*len(R):.1f}; dobiveno: {(R.P_perm<0.05).sum()}")
print("glavni ucinci (ostatak):")
for w in ["temp", "hum", "wind", "press"]:
    r_, p_, n_ = base.corr(jp[w], jp.resid)
    print(f"   {w}: r={r_:+.3f} P={p_:.3f} n={n_}")
