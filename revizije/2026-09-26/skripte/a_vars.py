# -*- coding: utf-8 -*-
"""Revizija 26.09.2026 — ekran predmecnih varijabla: (a) nosi li varijabla informaciju POVRH
devigirane cijene, (b) koliko nas MODEL na nju reagira (odmak nase pouzdanosti od trzista).

Precijenjena varijabla = model se na nju mice, a ona ne nosi nista (ili nosi suprotno).
Podcijenjena = nosi informaciju, a model je ne koristi.
"""
import sys, math
import numpy as np, pandas as pd
import base

surf = sys.argv[1] if len(sys.argv) > 1 else "hard"
df = base.build(surface=None if surf == "all" else surf)
df = df[df.p_dev.notna() & df.win.notna()].copy()
df["model_dev"] = df.conf / 100 - df.p_dev          # koliko se nas broj odmice od trzista
print(f"podloga={surf} n={len(df)}  WR={df.win.mean():.3f} ocek={df.p_dev.mean():.3f}")

VARS = [
    ("d_elo_s", "ELO podloga (pick-opp)"), ("d_elo_o", "ELO ukupni"), ("d_rank", "rang (log omjer)"),
    ("d_serve", "poeni na servisu %"), ("d_fs_pct", "1. servis u polju %"), ("d_fs_won", "poeni na 1. servisu %"),
    ("d_ss_won", "poeni na 2. servisu %"), ("d_ret", "povrat %"), ("d_retw", "povrat ponderirani %"),
    ("d_hold", "hold % (proxy)"), ("d_bps", "BP spasene %"), ("d_bpc", "BP iskoristene %"),
    ("d_aces", "asovi"), ("d_tb", "tie-break %"), ("d_dec", "odlucujuci set %"),
    ("d_f5", "forma 5"), ("d_f10", "forma 10"), ("d_fq", "forma x kvaliteta protivnika"),
    ("d_aoe5", "prosj. ELO zadnjih 5 protivnika"), ("d_aoe", "prosj. ELO zadnjih 10 protivnika"),
    ("aoe5_p", "prosj. ELO 5 protivnika NASEG picka"),
    ("d_m7", "mecevi u 7 dana"), ("d_s7", "setovi u 7 dana"), ("d_rest", "dani odmora"),
    ("d_m39", "mecevi 3-9 dana"), ("d_age", "dob (pick-opp)"), ("age_p", "dob naseg picka"),
    ("d_h", "visina (pick-opp)"), ("d_tbest", "najdalja runda na turniru 3g"),
    ("seas_w_d", "ATP pobjede u sezoni (K15)"), ("d_tf_serve", "servis NA OVOM turniru (K12)"),
    ("cons_gap", "konsenzus minus SuperSport (pp)"),
]
rows = []
for v, lab in VARS:
    if v not in df.columns:
        continue
    x = df[v].astype(float)
    b, se, z, p, n = base.offset_logit(x, df.win, df.logit_p)
    r_res, p_res, n_res = base.corr(x, df.resid)
    r_mod, p_mod, n_mod = base.corr(x, df.model_dev)
    r_raw, _, _ = base.corr(x, df.win)
    rows.append(dict(var=v, opis=lab, n=n, r_raw=r_raw, r_resid=r_res, P_resid=p_res,
                     beta_vs_price=b, z=z, P=p, r_model=r_mod, P_model=p_mod))
out = pd.DataFrame(rows)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
print(out.round(3).to_string(index=False))
out.to_csv(f"out_vars_{surf}.csv", index=False)
