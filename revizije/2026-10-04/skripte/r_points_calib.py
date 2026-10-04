# -*- coding: utf-8 -*-
"""Revizija 04.10.2026 — baždarenje "poena" u povijesnom labu (04.10.2026 18:06).

Pitanje: koliki udio poena igrač s danom poštenom cijenom u prosjeku osvoji, i kolika je
vjerojatnost pobjede za dani udio poena? Tako se za svaki naš meč može reći je li pick bio
"dobar" neovisno o sreći u ključnim poenima (zasluženi edge, PRAGOVI točka "Poeni").

Izvor: .cache/lab/td_joined.pkl (tennis-data + indeks TML retka) i .cache/lab/tml.pkl
(povijesni laboratorij 27.09.2026). Samo čitanje.
Izlaz: .cache/rev_2026-10-04/points_calib.json
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LAB = os.path.join(ROOT, ".cache", "lab")
OUT = os.path.join(ROOT, ".cache", "rev_2026-10-04", "points_calib.json")


def logit_fit(x, y, iters=60):
    X = np.column_stack([np.ones(len(x)), x])
    w = np.zeros(2)
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(X @ w)))
        W = p * (1 - p)
        H = X.T @ (X * W[:, None]) + 1e-9 * np.eye(2)
        step = np.linalg.solve(H, X.T @ (y - p))
        w += step
        if np.abs(step).max() < 1e-10:
            break
    return w


def main():
    td = pd.read_pickle(os.path.join(LAB, "td_joined.pkl"))
    tml = pd.read_pickle(os.path.join(LAB, "tml.pkl"))
    td = td[td["tml_idx"].notna()].copy()
    td["tml_idx"] = td["tml_idx"].astype(int)
    td = td.drop_duplicates("tml_idx")
    t = tml.loc[td["tml_idx"]].reset_index(drop=True)
    td = td.reset_index(drop=True)
    num = lambda c: pd.to_numeric(t[c], errors="coerce")
    w_sv, w1, w2 = num("w_svpt"), num("w_1stWon"), num("w_2ndWon")
    l_sv, l1, l2 = num("l_svpt"), num("l_1stWon"), num("l_2ndWon")
    pts_w = w1 + w2 + (l_sv - l1 - l2)
    pts_l = l1 + l2 + (w_sv - w1 - w2)
    share_w = pts_w / (pts_w + pts_l)
    d = pd.DataFrame({"p": td["p_fair"].values, "share": share_w.values,
                      "bo": pd.to_numeric(td["Best of"], errors="coerce").values,
                      "surface": td["Surface"].values, "half": td["half"].values,
                      "tot": (pts_w + pts_l).values})
    d = d[d["share"].notna() & d["p"].notna() & (d["tot"] >= 60) & d["bo"].isin([3, 5])]
    # simetrično: svaki meč iz obje perspektive (pobjednik: win=1; poraženi: win=0)
    a = d.assign(win=1.0)
    b = d.assign(win=0.0, p=1 - d["p"], share=1 - d["share"])
    s = pd.concat([a, b], ignore_index=True)
    print(f"mečeva sa statistikom i cijenom: {len(d)} (Bo3 {int((d.bo == 3).sum())}, Bo5 {int((d.bo == 5).sum())})")

    calib = {}
    edges = [0, .15, .25, .35, .45, .55, .65, .75, .85, 1.0]
    for bo in (3, 5):
        x = s[s.bo == bo]
        # 1) P(pobjeda | udio poena): logit na (udio - 0,5)
        w = logit_fit((x["share"] - 0.5).values * 100, x["win"].values)
        # 2) očekivani udio za cijenu: linearno na logit(p) (provjereno po pojasima ispod)
        lp = np.log(x["p"] / (1 - x["p"])).values
        A = np.column_stack([np.ones(len(lp)), lp])
        coef, *_ = np.linalg.lstsq(A, x["share"].values, rcond=None)
        resid = x["share"].values - A @ coef
        calib[f"bo{bo}"] = {"win_given_share": [float(w[0]), float(w[1])],
                            "share_given_logitp": [float(coef[0]), float(coef[1])],
                            "share_resid_sd": float(resid.std()), "n_sides": int(len(x))}
        print(f"\nBo{bo}: P(pobjeda|udio) = logit({w[0]:+.3f} + {w[1]:.3f}*(udio-50pp)); "
              f"udio = {coef[0]:.4f} + {coef[1]:.4f}*logit(p); sd ostatka udjela {100*resid.std():.2f}pp")
        # provjera po pojasima cijene: očekivani udio i zasluženi edge moraju biti ~0
        x = x.assign(exp_share=A @ coef,
                     dwin=1 / (1 + np.exp(-(w[0] + w[1] * (x["share"] - 0.5) * 100))))
        print("  pojas p      n     udio   očekiv.  W/L edge  zasluženi edge   sd(zasl.-p) sd(win-p)")
        for lo, hi in zip(edges[:-1], edges[1:]):
            g = x[(x.p >= lo) & (x.p < hi)]
            if len(g) < 50:
                continue
            print(f"  {lo:.2f}-{hi:.2f} {len(g):6d}  {100*g.share.mean():6.2f}  {100*g.exp_share.mean():6.2f}"
                  f"   {100*(g.win.mean()-g.p.mean()):+6.2f}     {100*(g.dwin.mean()-g.p.mean()):+6.2f}"
                  f"          {100*(g.dwin-g.p).std():5.1f}      {100*(g.win-g.p).std():5.1f}")
        for half in ("P1", "P2"):
            g = x[x.half == half]
            print(f"  polovica {half}: n={len(g)} zasluženi edge {100*(g.dwin.mean()-g.p.mean()):+.2f}pp")
        for srf in ("Hard", "Clay", "Grass"):
            g = x[x.surface == srf]
            if len(g) > 200:
                print(f"  {srf:5s}: n={len(g)} udio ostatak {100*(g.share-g.exp_share).mean():+.2f}pp  "
                      f"zasluženi edge {100*(g.dwin.mean()-g.p.mean()):+.2f}pp")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(calib, f, indent=1)
    print("\nzapisano:", OUT)


if __name__ == "__main__":
    main()
