# -*- coding: utf-8 -*-
"""Revizija 18.10.2026 — F1 (opis): dob i visina naspram statistike meča; dob × umor (18.10.2026 09:25, zadnja izmjena).

Pragovi: PRAGOVI_REVIZIJA_2026-10-18.md točka F (09:07). OPIS, ne prediktor: statistika meča
je ISHOD tog meča, pa ove korelacije kažu "kako takvi igrači igraju", ne "tko će pobijediti".
Prediktivna pitanja (visina/dob naspram cijene, dob × umor) su testovi F2, E6, E7 u r_lab3.py.

TML glavni ždrijeb 2022 – 13.09.2026, mečevi s potpunom statistikom; jedan redak = igrač u meču.
Dob × umor: LAB mečevi (lab3_features.pkl), ostatak = pobjeda − poštena cijena i ostatak udjela
poena (stvarni udio − očekivani za cijenu, baždarenje iz revizije 04.10.).
Samo čita .cache/lab/*.pkl i .cache/rev_2026-10-18/*.
"""
import json
import math
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LAB = os.path.join(ROOT, ".cache", "lab")
OUTD = os.path.join(ROOT, ".cache", "rev_2026-10-18")


def r_ci(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = ~(np.isnan(x) | np.isnan(y))
    x, y = x[m], y[m]
    n = len(x)
    if n < 10:
        return np.nan, n, (np.nan, np.nan)
    r = float(np.corrcoef(x, y)[0, 1])
    z = 0.5 * math.log((1 + r) / (1 - r))
    se = 1 / math.sqrt(n - 3)
    return r, n, (math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se))


def main():
    t = pd.read_pickle(os.path.join(LAB, "tml.pkl"))
    t = t[(t.src == "main") & (t.t_start >= "2022-01-01") & (t.t_start <= "2026-09-13")].copy()
    num = lambda c: pd.to_numeric(t[c], errors="coerce")
    rows = []
    for me, ot in (("w", "l"), ("l", "w")):
        sv, osv = num(f"{me}_svpt"), num(f"{ot}_svpt")
        fi = num(f"{me}_1stIn")
        d = pd.DataFrame({
            "ht": num(f"{'winner' if me == 'w' else 'loser'}_ht"),
            "age": num(f"{'winner' if me == 'w' else 'loser'}_age"),
            "ace": num(f"{me}_ace") / sv,
            "df": num(f"{me}_df") / sv,
            "first_in": fi / sv,
            "first_won": num(f"{me}_1stWon") / fi,
            "second_won": num(f"{me}_2ndWon") / (sv - fi),
            "ret_won": 1 - (num(f"{ot}_1stWon") + num(f"{ot}_2ndWon")) / osv,
            "tpw": (num(f"{me}_1stWon") + num(f"{me}_2ndWon") + osv - num(f"{ot}_1stWon") - num(f"{ot}_2ndWon")) / (sv + osv),
            "hold": 1 - (num(f"{me}_bpFaced") - num(f"{me}_bpSaved")) / num(f"{me}_SvGms").where(num(f"{me}_SvGms") > 0),
            "bp_saved": num(f"{me}_bpSaved") / num(f"{me}_bpFaced").where(num(f"{me}_bpFaced") > 0),
            "minutes": num("minutes"),
            "surface": t["surface"], "won": 1 if me == "w" else 0,
        })
        rows.append(d[(sv > 20) & (osv > 20)])
    d = pd.concat(rows, ignore_index=True)
    print(f"=== F1 (opis) — igrač-meč redaka: {len(d)} (TML glavni ždrijeb 2022-2026, potpuna statistika)")
    stats_ = [("asovi / servisni poen", "ace"), ("dvostruke / servisni poen", "df"), ("1. servis u polju %", "first_in"),
              ("1. servis osvojen %", "first_won"), ("2. servis osvojen %", "second_won"), ("povrat osvojen %", "ret_won"),
              ("udio osvojenih poena", "tpw"), ("hold %", "hold"), ("BP spašeni %", "bp_saved"), ("trajanje meča (min)", "minutes")]
    for who in ("ht", "age"):
        print(f"\n  {'VISINA (cm)' if who == 'ht' else 'DOB (godine)'} naspram statistike meča: r [95% interval]")
        for lab, c in stats_:
            r, n, ci = r_ci(d[who], d[c])
            print(f"    {lab:26s} r={r:+.3f} [{ci[0]:+.3f}, {ci[1]:+.3f}] n={n}")
    # srednje vrijednosti po razredima (lakše za čitanje)
    d["ht_k"] = pd.cut(d.ht, [0, 180, 188, 196, 230], labels=["<180", "180-187", "188-195", "196+"])
    d["age_k"] = pd.cut(d.age, [0, 23, 27, 31, 50], labels=["<23", "23-26", "27-30", "31+"])
    print("\n  prosjek po visini:")
    print(d.groupby("ht_k", observed=True)[["ace", "first_won", "second_won", "ret_won", "hold", "tpw"]].mean().round(3).to_string())
    print("\n  prosjek po dobi:")
    print(d.groupby("age_k", observed=True)[["ace", "first_won", "second_won", "ret_won", "hold", "tpw", "minutes"]].mean().round(3).to_string())

    # ---------------- dob × umor (LAB)
    f = pd.read_pickle(os.path.join(OUTD, "lab3_features.pkl"))
    cal = json.load(open(os.path.join(OUTD, "points_calib.json"), encoding="utf-8"))
    tml_all = pd.read_pickle(os.path.join(LAB, "tml.pkl"))
    td = pd.read_pickle(os.path.join(LAB, "td_joined.pkl"))
    td = td[td["tml_idx"].notna()].copy()
    td["tml_idx"] = td["tml_idx"].astype(int)
    td = td.drop_duplicates("tml_idx").reset_index(drop=True)
    tt = tml_all.loc[td["tml_idx"]].reset_index(drop=True)
    rows = []
    for _, r in f.iterrows():
        m = tt.iloc[int(r["i"])]
        bo = 5 if td.iloc[int(r["i"])]["Best of"] == 5 else 3
        a, b = cal[f"bo{bo}"]["share_given_logitp"]
        for me, ot, won, p in (("w", "l", 1, r.pf), ("l", "w", 0, 1 - r.pf)):
            try:
                sv, osv = float(m[f"{me}_svpt"]), float(m[f"{ot}_svpt"])
                tpw = (float(m[f"{me}_1stWon"]) + float(m[f"{me}_2ndWon"]) + osv - float(m[f"{ot}_1stWon"]) - float(m[f"{ot}_2ndWon"])) / (sv + osv)
            except (TypeError, ValueError, ZeroDivisionError):
                tpw = np.nan
            exp = a + b * math.log(p / (1 - p)) if 0 < p < 1 else np.nan
            rows.append({"age": r[f"age_{me}"], "sets": r.get(f"tsets_played_{me}"), "mins": r.get(f"tmins_{me}"),
                         "rest": r.get(f"rest_{me}"), "won": won, "p": p, "tpw_res": 100 * (tpw - exp) if not np.isnan(tpw) else np.nan})
    g = pd.DataFrame(rows)
    g["age_k"] = pd.cut(g.age, [0, 25, 30, 50], labels=["<25", "25-29", "30+"])
    g["sets_k"] = pd.cut(g.sets, [-1, 2, 5, 40], labels=["0-2 seta", "3-5 setova", "6+ setova"])
    print("\n=== Dob × umor (LAB, igrač-meč): edge = pobjeda − poštena cijena | ostatak udjela poena (pp)")
    for ak in ["<25", "25-29", "30+"]:
        parts = []
        for sk in ["0-2 seta", "3-5 setova", "6+ setova"]:
            x = g[(g.age_k == ak) & (g.sets_k == sk)]
            if len(x) >= 30:
                e = 100 * (x.won.mean() - x.p.mean())
                se = 100 * math.sqrt((x.p * (1 - x.p)).sum()) / len(x)
                parts.append(f"{sk}: {e:+5.1f}pp ±{1.96*se:4.1f} | poeni {x.tpw_res.mean():+5.2f} (n={len(x)})")
        print(f"  dob {ak:6s} " + "   ".join(parts))
    for ak in ["<25", "25-29", "30+"]:
        x = g[(g.age_k == ak) & g.rest.notna()]
        r, n, ci = r_ci(-x.rest.clip(upper=14), x.tpw_res)
        print(f"  dob {ak:6s} r(kraći odmor, ostatak poena) = {r:+.3f} [{ci[0]:+.3f}, {ci[1]:+.3f}] n={n}")


if __name__ == "__main__":
    main()
