# -*- coding: utf-8 -*-
"""Sekvencijalna forma (26.09.2026, korisnikova hipoteza): ako je igrac u prethodnim mecevima
OVOG turnira pobijedio protivnike slicnog (ili jaceg) profila kao sljedeci protivnik —
vise asova, bolji 2. servis, bolji servis — ima li to prediktivnu vrijednost POVRH cijene?

Uzorak: cijeli pobrani zdrijebovi 28 turnira (draw_stats_harvest.json, 1.255 meceva s
post-match statistikom), cijena iz berbe past-matches (kvote), spojeno po ID-evima +-2 dana.
Profil igraca = prosjek njegove statistike u SVIM pobranim mecevima PRIJE pocetka ovog
turnira (dakle bez curenja iz tekuceg turnira i bez buducnosti). Trazi se >=2 takva meca.
"""
import json, os, numpy as np, pandas as pd, base, pmbase

ROOT = r"C:\Users\jovin\Desktop\Tenis Claude"
d = json.load(open(os.path.join(ROOT, "draw_stats_harvest.json"), encoding="utf-8"))["matches"]
ORDER = {"R128": 1, "R64": 2, "R32": 3, "R16": 4, "QF": 5, "SF": 6, "F": 7}


def met(s, o):
    g = lambda x, k: float(x.get(k) or 0)
    sp = g(s, "winningOnFirstServeOf") + g(s, "winningOnSecondServeOf")
    rp = g(o, "winningOnFirstServeOf") + g(o, "winningOnSecondServeOf")
    if sp < 20 or rp < 20:
        return None
    tp = g(s, "totalPointsWon"); otp = g(o, "totalPointsWon")
    return dict(serve=(g(s, "winningOnFirstServe") + g(s, "winningOnSecondServe")) / sp,
                ace=g(s, "aces") / sp,
                ss=g(s, "winningOnSecondServe") / g(s, "winningOnSecondServeOf") if g(s, "winningOnSecondServeOf") else np.nan,
                ret=((g(o, "winningOnFirstServeOf") - g(o, "winningOnFirstServe")) + (g(o, "winningOnSecondServeOf") - g(o, "winningOnSecondServe"))) / rp,
                tp=tp / (tp + otp) if tp + otp else np.nan)


rows = []
for k, v in d.items():
    a = met(v["p1_stats"], v["p2_stats"]); b = met(v["p2_stats"], v["p1_stats"])
    if not a or not b:
        continue
    for pid, oid, m, won in [(v["p1_id"], v["p2_id"], a, v["winner_id"] == v["p1_id"]),
                             (v["p2_id"], v["p1_id"], b, v["winner_id"] == v["p2_id"])]:
        rows.append(dict(tid=v["tournament_id"], tname=v["tournament"], date=v["date"], rnd=ORDER.get(v["round"], 0),
                         pid=str(pid), oid=str(oid), won=float(won), **m))
L = pd.DataFrame(rows)
L["date"] = pd.to_datetime(L.date)
tstart = L.groupby("tid").date.min()
L["tstart"] = L.tid.map(tstart)

# profil prije pocetka turnira
def profile(pid, before):
    s = L[(L.pid == pid) & (L.date < before)]
    if len(s) < 2:
        return None
    return s[["serve", "ace", "ss", "ret"]].mean()

prof_cache = {}
def P(pid, before):
    key = (pid, before)
    if key not in prof_cache:
        prof_cache[key] = profile(pid, before)
    return prof_cache[key]

# cijena iz past-matches
pm, names = pmbase.load_matches()
pm = pm[pm.o1.notna() & pm.o2.notna() & (pm.o1 > 1) & (pm.o2 > 1)]
price = {}
for r in pm.itertuples():
    pw = (1 / r.o1) / (1 / r.o1 + 1 / r.o2)
    price[(r.p1, r.p2, r.date)] = pw          # p1 = pobjednik
def get_price(x, y, date):
    for dd in range(-2, 3):
        dt = date + pd.Timedelta(days=dd)
        if (x, y, dt) in price:
            return price[(x, y, dt)]           # x je pobijedio, vjerojatnost za x
        if (y, x, dt) in price:
            return 1 - price[(y, x, dt)]
    return np.nan

out = []
for r in L.itertuples():
    if r.rnd <= 1 and r.tname and "Open" not in str(r.tname):
        pass
    prev = L[(L.tid == r.tid) & (L.pid == r.pid) & (L.date < r.date)]
    if len(prev) == 0:
        continue
    py = P(r.oid, r.tstart)
    if py is None:
        continue
    # profili prethodnih protivnika
    pprof = [P(o, r.tstart) for o in prev.oid]
    pprof = [(p_, row) for p_, row in zip(pprof, prev.itertuples()) if p_ is not None]
    if not pprof:
        continue
    feats = {}
    for dim in ["ace", "serve", "ss", "ret"]:
        # je li pobijedio protivnika s JEDNAKIM ili JACIM atributom od sljedeceg protivnika
        feats[f"beat_ge_{dim}"] = float(any(p_[dim] >= py[dim] - (0.01 if dim == "ace" else 0.015) for p_, _ in pprof))
        # 'uvjerljivo' (>=53% poena) protiv takvog
        feats[f"beat_ge_{dim}_conv"] = float(any((p_[dim] >= py[dim] - (0.01 if dim == "ace" else 0.015)) and row.tp >= 0.53 for p_, row in pprof))
    feats["prev_tp"] = prev.tp.mean()           # kako je pobjedjivao (udio poena)
    feats["prev_n"] = len(prev)
    pr = get_price(r.pid, r.oid, r.date)
    out.append(dict(pid=r.pid, oid=r.oid, date=r.date, tname=r.tname, rnd=r.rnd, won=r.won, p=pr, **feats))
S = pd.DataFrame(out)
S = S[S.p.notna()].copy()
# svaki mec se pojavljuje dvaput (iz perspektive oba igraca) — zadrzi jednu stranu nasumicno
rng = np.random.default_rng(3)
S["key"] = S.apply(lambda r: tuple(sorted([r.pid, r.oid])) + (str(r.date.date()),), axis=1)
S = S.groupby("key", group_keys=False).apply(lambda g: g.sample(1, random_state=int(rng.integers(1e9))))
S["resid"] = S.won - S.p
S["logit_p"] = np.log(S.p / (1 - S.p))
print(f"meceva s cijenom i profilom: {len(S)} (turnira {S.tname.nunique()})")
for dim in ["ace", "serve", "ss", "ret"]:
    for suf in ["", "_conv"]:
        v = f"beat_ge_{dim}{suf}"
        a = S[S[v] == 1]; b = S[S[v] == 0]
        b_, se, z, pp, n = base.offset_logit(S[v], S.won, S.logit_p)
        print(f"  {v:22s} DA n={len(a):4d} ostatak {100*a.resid.mean():+5.1f}pp | NE n={len(b):4d} {100*b.resid.mean():+5.1f}pp | offset z={z:+.2f} P={pp:.3f}")
b_, se, z, pp, n = base.offset_logit(S.prev_tp, S.won, S.logit_p)
print(f"  prosjecni udio poena u prethodnim mecevima turnira (KAKO je pobjedjivao): offset z={z:+.2f} P={pp:.3f} n={n}")
for dep in [1, 2, 3]:
    s = S[S.prev_n >= dep]
    b_, se, z, pp, n = base.offset_logit(s.prev_tp, s.won, s.logit_p)
    print(f"     dubina >= {dep}: z={z:+.2f} P={pp:.3f} n={n}")
S.to_pickle("sequence.pkl")
