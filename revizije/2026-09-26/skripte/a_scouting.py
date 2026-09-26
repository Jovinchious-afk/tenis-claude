# -*- coding: utf-8 -*-
"""Revizija scouting tablice (26.09.2026).

1) Rade li tvrdnje o MATCHUPIMA ("muku muci s velikim serverima / returnerima / ljevacima")?
   Za svaku tvrdnju (igrac P, tip protivnika A) usporedi P-ov ostatak naspram cijene protiv
   protivnika tipa A s ostatkom protiv svih ostalih — na berbi past-matches (kvote, 2023-2026).
   Tip protivnika je MJEREN (sezonski servis/povrat iz nasih snapshotova, ruka iz profila),
   ne preuzet iz teksta — inace bi se tvrdnja provjeravala samom sobom.
2) Proturjecja profila i mjerenja (stil "big server" uz servis u donjoj polovici i sl.).
3) Nasi pickovi po razini pouzdanosti profila (azurirano).
"""
import json, re, numpy as np, pandas as pd, base, pmbase

sc = pd.DataFrame(json.load(open("data/player_scouting.json", encoding="utf-8")))
am = json.load(open("data/analyzed_matches.json", encoding="utf-8"))
hands = json.load(open(r"C:\Users\jovin\Desktop\Tenis Claude\player_hands.json", encoding="utf-8"))
pm, names = pmbase.load_matches()

# --- mjereni profil (zadnji snapshot po igracu): servis i povrat
prof = {}
for r in sorted(am, key=lambda r: r.get("match_date") or ""):
    cs = r.get("context_snapshot") or {}
    for side, pid in (("p1", r.get("player1_id")), ("p2", r.get("player2_id"))):
        if not pid:
            continue
        sv, rt = cs.get(f"{side}_serve_pts_won"), cs.get(f"{side}_return_won")
        if sv and rt:
            prof[str(pid)] = (float(sv), float(rt), r.get(side if side != "p1" else "player1") )
P = pd.DataFrame([(k, v[0], v[1]) for k, v in prof.items()], columns=["pid", "serve", "ret"])
q_s = P.serve.quantile(0.75); q_r = P.ret.quantile(0.75)
BIG = set(P[P.serve >= q_s].pid); RET = set(P[P.ret >= q_r].pid)
LEFT = {k for k, v in hands.items() if v == "L"}
print(f"mjereni profili: {len(P)} igraca; veliki server = servis >= {q_s:.1f}% (gornja cetvrt), returner = povrat >= {q_r:.1f}%")

# ime -> id
nid = {}
for pid, nm in names.items():
    if nm:
        nid[nm.lower()] = pid
sc["pid"] = sc.display_name.str.lower().map(nid)

def claims(text):
    t = (text or "").lower()
    out = set()
    if re.search(r"big serv|server|serve-led|first-strike|serving", t): out.add("BIG")
    if re.search(r"returner|counter|mover|grinder|retriever|defen", t): out.add("RET")
    if re.search(r"left|lefty", t): out.add("LEFT")
    return out

pr = pm[pm.o1.notna() & pm.o2.notna() & (pm.o1 > 1) & (pm.o2 > 1) & (pm.level >= 1)].copy()
pr["pw"] = (1 / pr.o1) / (1 / pr.o1 + 1 / pr.o2)
long = pd.concat([pd.DataFrame(dict(pid=pr.p1, opp=pr.p2, won=1.0, p=pr.pw, date=pr.date)),
                  pd.DataFrame(dict(pid=pr.p2, opp=pr.p1, won=0.0, p=1 - pr.pw, date=pr.date))])
long["res"] = long.won - long.p
SETS = {"BIG": BIG, "RET": RET, "LEFT": LEFT}
for field, lab in [("tough_matchups", "MUKU MUCI S (tough)"), ("favourable_matchups", "VOLI (favourable)")]:
    rows = []
    for s in sc.itertuples():
        if not isinstance(s.pid, str):
            continue
        mine = long[long.pid == s.pid]
        for a in claims(getattr(s, field)):
            known = mine[mine.opp.isin(set(P.pid) if a != "LEFT" else set(hands))]
            vs = known[known.opp.isin(SETS[a])]; other = known[~known.opp.isin(SETS[a])]
            if len(vs) >= 5 and len(other) >= 10:
                rows.append(dict(player=s.display_name, conf=s.confidence, claim=a, n_vs=len(vs), res_vs=vs.res.mean(),
                                 n_other=len(other), res_other=other.res.mean()))
    R = pd.DataFrame(rows)
    R["diff"] = R.res_vs - R.res_other
    print(f"\n=== {lab}: {len(R)} provjerljivih tvrdnji")
    for a, g in R.groupby("claim"):
        w = g.n_vs
        md = np.average(g["diff"], weights=w)
        se = np.sqrt(np.average((g["diff"] - md) ** 2, weights=w) / len(g))
        print(f"   tip {a}: tvrdnji {len(g)}, meceva protiv tog tipa {int(g.n_vs.sum())}; "
              f"ponderirana razlika ostatka (protiv tipa - ostali) = {100*md:+.1f}pp  (+-{196*se:.1f}); "
              f"tvrdnja 'tocna' (razlika u ocekivanom smjeru) u {int(((g['diff']<0) if field=='tough_matchups' else (g['diff']>0)).sum())}/{len(g)}")
    R.to_csv(f"out_scouting_{field}.csv", index=False)
    if field == "tough_matchups":
        print(R.sort_values("diff").head(8)[["player", "conf", "claim", "n_vs", "diff"]].round(3).to_string(index=False))

# --- 2) proturjecja stila i mjerenja
sc2 = sc.merge(P, on="pid", how="left")
bigstyle = sc2["style"].str.lower().str.contains("big server|serve-led|huge-serving|big lefty server|energetic big server|tall big server", regex=True)
retstyle = sc2["style"].str.lower().str.contains("returner|counter-puncher|defensive|retriever", regex=True)
pct_s = sc2.serve.rank(pct=True); pct_r = sc2.ret.rank(pct=True)
bad1 = sc2[bigstyle & (pct_s < 0.5)][["display_name", "style", "serve", "confidence"]]
bad2 = sc2[retstyle & (pct_r < 0.5)][["display_name", "style", "ret", "confidence"]]
print("\n=== PROTURJECJA: stil kaze VELIKI SERVER, a servis je u donjoj polovici igraca koje pratimo:")
print(bad1.to_string(index=False) if len(bad1) else "   nema")
print("=== stil kaze RETURNER/COUNTER, a povrat je u donjoj polovici:")
print(bad2.to_string(index=False) if len(bad2) else "   nema")
sc2.to_pickle("scouting_measured.pkl")

# --- 3) nasi pickovi po pouzdanosti profila
j = pd.read_pickle("classified_idea3.pkl")
jp = j[j.win.notna() & j.p_dev.notna()]
print("\n=== NASI PICKOVI po pouzdanosti profila NASEG picka")
for c in ["High", "Med-High", "Med", "Med-Low", "Low", "Insufficient", None]:
    m = (jp.scout_p == c) if c else jp.scout_p.isna()
    print(f"   {str(c):12s}", base.edge_table(jp, m, ""))
