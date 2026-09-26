# -*- coding: utf-8 -*-
"""Sustavna pretraga interakcija (26.09.2026) — uz kontrolu laznih otkrica.

Za svaki par (X, Z): logit(pobjeda) = cijena (offset) + b1*X + b2*Z + b3*X*Z. Testira se b3.
(1) korisnikove izricito navedene kombinacije — zasebno, jer su zadane UNAPRIJED;
(2) svi parovi — uz Benjamini-Hochberg i PERMUTACIJSKU nul-raspodjelu najjaceg rezultata:
    ishodi se promijesaju unutar cijene (sparivanje ostataka), pretraga se ponovi 200 puta, i
    gleda se koliko cesto CISTI SUM proizvede jednako jak "najbolji nalaz".
"""
import itertools, math
import numpy as np, pandas as pd, base

j = pd.read_pickle("classified_idea3.pkl")
j = j[j.win.notna() & j.p_dev.notna()].copy().reset_index(drop=True)
j["is_r16qf"] = j["round"].isin(["R16", "QF"]).astype(float)
j["is_gs"] = j.level.fillna("").str.contains("Grand").astype(float)
j["lefty_opp"] = ((j.hand_o == "L") & (j.hand_p == "R")).astype(float)
j.loc[(j.hand_o == "") | (j.hand_p == ""), "lefty_opp"] = np.nan
j["hot"] = j.temp
j["d_m7x"] = j.d_m7
X = ["d_elo_s", "d_rank", "d_serve", "d_ss_won", "d_ret", "d_bps", "d_bpc", "d_tb", "d_f10", "d_fq", "d_aoe5",
     "aoe5_p", "d_m7", "d_rest", "d_age", "d_h", "d_tbest", "seas_w_d", "is_r16qf", "is_gs", "lefty_opp", "hot", "wind", "hum"]


def inter_test(df, x, z):
    d = df[[x, z, "win", "logit_p"]].dropna()
    if len(d) < 60 or d[x].std() == 0 or d[z].std() == 0:
        return np.nan, np.nan, len(d)
    xs = (d[x] - d[x].mean()) / d[x].std(); zs = (d[z] - d[z].mean()) / d[z].std()
    A = np.column_stack([np.ones(len(d)), xs, zs, xs * zs])
    y = d.win.values; off = d.logit_p.values
    w = np.zeros(4)
    for _ in range(60):
        p = 1 / (1 + np.exp(-(off + A @ w)))
        W = p * (1 - p)
        H = A.T @ (A * W[:, None]) + 1e-6 * np.eye(4)
        step = np.linalg.solve(H, A.T @ (y - p) - 1e-6 * w)
        w += step
        if np.abs(step).max() < 1e-8:
            break
    p = 1 / (1 + np.exp(-(off + A @ w)))
    cov = np.linalg.inv(A.T @ (A * (p * (1 - p))[:, None]) + 1e-6 * np.eye(4))
    z_ = w[3] / math.sqrt(cov[3, 3])
    return z_, 2 * base.norm_sf(abs(z_)), len(d)


print("=== (1) KORISNIKOVE KOMBINACIJE (zadane unaprijed) ===")
user = [("d_elo_s", "aoe5_p", "ELO jaz x prosj. ELO zadnjih 5 protivnika picka"),
        ("d_elo_s", "d_aoe5", "ELO jaz x razlika u kvaliteti zadnjih 5 protivnika"),
        ("d_age", "d_m7", "razlika u dobi x opterecenje (mecevi 7 dana)"),
        ("lefty_opp", "d_serve", "ljevak protiv x servisni profil"),
        ("lefty_opp", "d_ret", "ljevak protiv x povratni profil"),
        ("is_r16qf", "d_m7", "runda R16/QF x ritam (mecevi 7 dana)"),
        ("is_r16qf", "d_elo_s", "runda R16/QF x ELO jaz"),
        ("d_f10", "d_aoe5", "forma x kvaliteta protivnika"),
        ("d_serve", "d_ret", "servis x povrat protivnika (matchup)"),
        ("d_age", "d_h", "dob x visina"),
        ("d_serve", "hot", "servis x temperatura"),
        ("d_ss_won", "hum", "2. servis x vlaga"),
        ("d_serve", "wind", "servis x vjetar")]
half = j.date <= j.date.median()
for x, z, lab in user:
    z_, p_, n_ = inter_test(j, x, z)
    z1, _, n1 = inter_test(j[half], x, z)
    z2, _, n2 = inter_test(j[~half], x, z)
    print(f"  {lab:50s} n={n_:3d} z={z_:+.2f} P={p_:.3f} | polovice z={z1:+.2f} / {z2:+.2f}")

print("\n=== (2) SVI PAROVI ===")
pairs = list(itertools.combinations(X, 2))
res = []
for x, z in pairs:
    z_, p_, n_ = inter_test(j, x, z)
    if not np.isnan(z_):
        res.append((x, z, z_, p_, n_))
R = pd.DataFrame(res, columns=["x", "z", "z", "P", "n"]).sort_values("P")
m = len(R)
R["BH_q"] = (R.P * m / (np.arange(1, m + 1))).cummin().clip(upper=1)  # priblizno (sortirano)
R["BH_q"] = R.P.rank(method="first").pipe(lambda rk: R.P * m / rk)
R["BH_q"] = R.sort_values("P", ascending=False).BH_q.cummin()
print(f"testova: {m}; P<0,05: {(R.P<0.05).sum()} (slucajno ocekivano {0.05*m:.1f}); P<0,01: {(R.P<0.01).sum()} (ocek. {0.01*m:.1f})")
print(f"prezivi Benjamini-Hochberg q<0,10: {(R.BH_q<0.10).sum()}")
print(R.head(10).round(4).to_string(index=False))
# split-half za top 10
print("\n  top 10 po polovicama (z u prvoj / drugoj polovici):")
for r in R.head(10).itertuples():
    z1, _, n1 = inter_test(j[half], r.x, r.z); z2, _, n2 = inter_test(j[~half], r.x, r.z)
    print(f"   {r.x} x {r.z}: {z1:+.2f} (n={n1}) / {z2:+.2f} (n={n2})")

# permutacijska nul-raspodjela NAJMANJEG P
rng = np.random.default_rng(5)
mins = []
for it in range(120):
    jj = j.copy()
    # promijesaj ishode UNUTAR decila cijene (cuva vezu ishod-cijena, rusi sve ostalo)
    jj["dec"] = pd.qcut(jj.p_dev, 10, labels=False, duplicates="drop")
    jj["win"] = jj.groupby("dec").win.transform(lambda s: rng.permutation(s.values))
    best = 1.0
    for x, z in pairs:
        z_, p_, n_ = inter_test(jj, x, z)
        if not np.isnan(p_) and p_ < best:
            best = p_
    mins.append(best)
mins = np.array(mins)
print(f"\nPERMUTACIJSKI TEST: najmanji P u stvarnim podacima = {R.P.min():.4f}; "
      f"u {np.mean(mins <= R.P.min())*100:.0f}% promijesanih (cisti sum) svjetova najbolji je jednako jak ili jaci "
      f"(medijan najmanjeg P u sumu = {np.median(mins):.4f})")
R.to_csv("out_interactions.csv", index=False)
