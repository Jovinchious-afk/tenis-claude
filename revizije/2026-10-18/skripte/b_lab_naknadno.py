# -*- coding: utf-8 -*-
"""Revizija 18.10.2026, drugi dio — NAKNADNE provjere koje je tražio kritičar (18.10.2026 15:04).

NIJE dio unaprijed zapisane obitelji od 10 testova (PRAGOVI_B 12:20). Ovo su provjere otpornosti:
  K1  točno pravilo Nose IZBJEGAVAJ na favoritu (P_own < 0,50 ILI 2+ mine) — sirovo i uz kontrolu
      pojasa cijene (razlika naspram svih strana u istom pojasu od 5pp);
  K2  B4b uz istu kontrolu pojasa;
  K3  N7 uz istu kontrolu pojasa.
Kontrola pojasa: za svaku odabranu stranu oduzima se prosječni ostatak (pobjeda − cijena) SVIH
strana iz istog pojasa cijene (5pp), izračunat na cijelom LAB-u (obje strane svakog meča).

Čita .cache/rev_2026-10-18b/b_lab_features.pkl (b_lab.py). Samo čita.
    python revizije/2026-10-18/skripte/b_lab_naknadno.py
"""
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from agent import nose as N  # noqa: E402

F = os.path.join(ROOT, ".cache", "rev_2026-10-18b", "b_lab_features.pkl")


def main():
    f = pd.read_pickle(F)
    pf = f["pf"].values
    # sve strane: pobjednik (1, pf) i gubitnik (0, 1 − pf)
    all_p = np.concatenate([pf, 1 - pf])
    all_w = np.concatenate([np.ones(len(f)), np.zeros(len(f))])
    band = lambda p: np.minimum((np.asarray(p) * 20).astype(int), 19)       # pojasevi od 5pp
    bres = pd.Series(all_w - all_p).groupby(band(all_p)).mean()

    def rep(name, won, p, half):
        won, p, half = np.asarray(won, float), np.asarray(p, float), np.asarray(half)
        n = len(won)
        if n == 0:
            print(f"  {name}: n=0")
            return
        res = won - p
        ctrl = res - bres.reindex(band(p)).fillna(0).values
        se = res.std(ddof=1) / math.sqrt(n)
        sec = ctrl.std(ddof=1) / math.sqrt(n)
        h1, h2 = ctrl[half == "P1"].mean() if (half == "P1").any() else float("nan"), \
            ctrl[half == "P2"].mean() if (half == "P2").any() else float("nan")
        print(f"  {name:58s} n={n:5d} sirovo {100 * res.mean():+5.1f}pp [{100 * (res.mean() - 1.96 * se):+5.1f}, "
              f"{100 * (res.mean() + 1.96 * se):+5.1f}] | uz pojas {100 * ctrl.mean():+5.1f}pp "
              f"[{100 * (ctrl.mean() - 1.96 * sec):+5.1f}, {100 * (ctrl.mean() + 1.96 * sec):+5.1f}] "
              f"P1 {100 * h1:+5.1f} / P2 {100 * h2:+5.1f} | prosj. cijena {p.mean():.2f}")

    def feat(k, s):
        g = lambda c: (None if pd.isna(f.at[k, f"{c}_{s}"]) else float(f.at[k, f"{c}_{s}"])) \
            if f"{c}_{s}" in f.columns else None
        return {"elo_s": g("elo_s"), "elo_o": g("elo_o"), "s": g("s"), "r": g("r"), "w1": g("w1"), "w2": g("w2"),
                "form10": g("form10"), "form_q": g("form_q"), "tf_n": g("tn_ok"), "tf_sv": g("tf_sv"),
                "sets7": g("sets7"), "rest": g("rest")}

    # K1: favorit (pf > 0,5 za pobjednika ili pf < 0,5 za gubitnika) uz IZBJEGAVAJ
    won, p, half = [], [], []
    for k in range(len(f)):
        po = f.at[k, "p_own_w"]
        if po is None or pd.isna(po):
            continue
        fw, fl = feat(k, "w"), feat(k, "l")
        if pf[k] > 0.5:       # favorit je pobjednik
            if po < 0.5 or len(N.mine_flags(fw, fl)) >= 2:
                won.append(1)
                p.append(pf[k])
                half.append(f.at[k, "half"])
        elif pf[k] < 0.5:     # favorit je gubitnik
            if (1 - po) < 0.5 or len(N.mine_flags(fl, fw)) >= 2:
                won.append(0)
                p.append(1 - pf[k])
                half.append(f.at[k, "half"])
    print("NAKNADNO (kritičar) — nije dio zapisane obitelji testova")
    rep("K1 Nose IZBJEGAVAJ na favoritu (P_own<0,5 ILI 2+ mine)", won, p, half)

    # K2: B4b (isti uvjet kao u b_lab.py)
    col = lambda c, s: pd.to_numeric(f[f"{c}_{s}"], errors="coerce")
    eb_w = 0.5 * col("elo_s", "w") + 0.5 * col("elo_o", "w")
    eb_l = 0.5 * col("elo_s", "l") + 0.5 * col("elo_o", "l")
    sr_w, sr_l = col("s", "w") + col("r", "w"), col("s", "l") + col("r", "l")
    mw = ((eb_w - eb_l >= 50) & (sr_w - sr_l >= 0.02) & (col("oppelo5", "w") >= col("oppelo5", "l"))).fillna(False).values
    ml = ((eb_l - eb_w >= 50) & (sr_l - sr_w >= 0.02) & (col("oppelo5", "l") >= col("oppelo5", "w"))).fillna(False).values
    won = np.concatenate([np.ones(mw.sum()), np.zeros(ml.sum())])
    p = np.concatenate([pf[mw], 1 - pf[ml]])
    half = np.concatenate([f["half"].values[mw], f["half"].values[ml]])
    rep("K2 B4b ELO +50 potvrđen servisom+povratom i protivnicima", won, p, half)

    # K3: N7
    po = pd.to_numeric(f["p_own_w"], errors="coerce")
    mw = (po - f["pf"] >= 0.05).fillna(False).values
    ml = ((1 - po) - (1 - f["pf"]) >= 0.05).fillna(False).values
    won = np.concatenate([np.ones(mw.sum()), np.zeros(ml.sum())])
    p = np.concatenate([pf[mw], 1 - pf[ml]])
    half = np.concatenate([f["half"].values[mw], f["half"].values[ml]])
    rep("K3 N7 strana kojoj Nose daje 5pp+ više od cijene", won, p, half)
    print(f"     od toga autsajderi po cijeni: {100 * (p < 0.5).mean():.0f}%")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
