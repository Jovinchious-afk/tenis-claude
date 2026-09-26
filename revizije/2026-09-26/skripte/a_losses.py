# -*- coding: utf-8 -*-
"""Revizija 26.09.2026 — klasifikacija SVAKOG gubitka i dobitka po unaprijed zadanim pravilima.

Pravila su zapisana PRIJE gledanja raspodjele (ovdje u kodu), da klasifikacija ne bi bila
naknadna pamet. Primarni uzrok ide po prioritetu; uz njega se biljeze i zastavice.

PRIMARNI UZROK GUBITKA (prvi koji vrijedi):
  1 OZLJEDA/PREDAJA     nas pick je predao (rtype=retired, pick izgubio)
  2 TIJESNO (varijanca) nas pick osvojio >=48% poena; bez statistike: izgubio u 3. setu
                        uz tie-break ili 7-5 u odlucujucem
  3 AUTSAJDER SVJESNO   nas pick je bio autsajder po devigiranoj kvoti (p<0,50): poraz je
                        bio vjerojatniji ishod od pobjede
  4 PREOKRET            nas pick dobio 1. set pa izgubio (i nije bilo tijesno)
  5 NADIGRAN, TRZISTE SE SLAGALO   pick osvojio <48% poena, a mi NISMO bili 8pp+ iznad trzista
  6 NADIGRAN, MODEL IZNAD TRZISTA  isto, ali nasa pouzdanost 8pp+ iznad devigirane cijene
ZASTAVICE (nisu uzrok, nego kontekst):
  pojas 1,35-1,60 (rupa) | runda R16/QF | vrucina >=30C ili vjetar >=20 km/h |
  specijalist podloge (ELO podloge za nas, ukupni protiv) | ljevak protiv naseg desnjaka |
  protivnik servirao 8pp+ iznad sezonskog prosjeka (post-match) | konsenzus protiv nas (<-1pp)
"""
import sys
import numpy as np, pandas as pd
import join, base

j = pd.read_pickle("joined.pkl")
j = j[j.win.notna()].copy()


def cls(r):
    sets = join.parse_sets(r.pm_result, r.pm_pick_won == 1.0) if isinstance(r.pm_result, str) else []
    first_won = sets[0][0] > sets[0][1] if sets else None
    last = sets[-1] if sets else None
    decider = len(sets) >= 3
    tight_decider = bool(decider and last and (last[2] or abs(last[0] - last[1]) <= 2))
    tp = r.pm_tp_share if not pd.isna(r.pm_tp_share) else np.nan
    flags = []
    if not pd.isna(r.odds) and 1.35 <= r.odds < 1.60:
        flags.append("rupa_1.35-1.60")
    if r["round"] in ("R16", "QF"):
        flags.append("R16/QF")
    if (not pd.isna(r.temp) and r.temp >= 30) or (not pd.isna(r.wind) and r.wind >= 20):
        flags.append("vrucina/vjetar")
    if not pd.isna(r.d_elo_s) and not pd.isna(r.d_elo_o) and r.d_elo_s > 0 and r.d_elo_o <= 0:
        flags.append("specijalist_podloge")
    if r.hand_o == "L" and r.hand_p == "R":
        flags.append("ljevak_protiv")
    if not pd.isna(r.pmo_serve_won) and not pd.isna(r.serve_o) and r.pmo_serve_won * 100 >= r.serve_o + 8:
        flags.append("protivnik_servis_+8pp")
    if not pd.isna(r.cons_gap) and r.cons_gap <= -1:
        flags.append("konsenzus_protiv")
    edge_model = (r.conf / 100 - r.p_dev) * 100 if not pd.isna(r.p_dev) else np.nan
    if r.win == 1:
        if not pd.isna(tp) and tp < 0.52:
            prim = "D_tijesna_pobjeda"
        elif not pd.isna(r.p_dev) and r.p_dev < 0.5:
            prim = "D_autsajder_prosao"
        else:
            prim = "D_jasna_pobjeda"
        return prim, flags, edge_model, first_won
    if r.pm_rtype == "retired":
        prim = "1_ozljeda_predaja"
    elif (not pd.isna(tp) and tp >= 0.48) or (pd.isna(tp) and tight_decider):
        prim = "2_tijesno_varijanca"
    elif not pd.isna(r.p_dev) and r.p_dev < 0.5:
        prim = "3_autsajder_svjesno"
    elif first_won:
        prim = "4_preokret"
    elif not pd.isna(edge_model) and edge_model >= 8:
        prim = "6_nadigran_model_iznad_trzista"
    else:
        prim = "5_nadigran_trziste_se_slagalo"
    return prim, flags, edge_model, first_won


res = j.apply(lambda r: pd.Series(cls(r), index=["uzrok", "zastavice", "model_minus_trziste", "dobio_1set"]), axis=1)
j = pd.concat([j, res], axis=1)
j.to_pickle("classified.pkl")

for surf in ["all", "hard", "clay", "grass"]:
    s = j if surf == "all" else j[j.surface == surf]
    L = s[s.win == 0]
    W = s[s.win == 1]
    print(f"\n===== {surf}: gubitaka {len(L)}, dobitaka {len(W)}")
    print(L.uzrok.value_counts().to_string())
    print("-- dobici:")
    print(W.uzrok.value_counts().to_string())
    # zastavice u gubicima naspram dobitaka (kontrolna skupina!)
    fl = {}
    for f in ["rupa_1.35-1.60", "R16/QF", "vrucina/vjetar", "specijalist_podloge", "ljevak_protiv",
              "protivnik_servis_+8pp", "konsenzus_protiv"]:
        inL = L.zastavice.apply(lambda z: f in z).mean() * 100
        inW = W.zastavice.apply(lambda z: f in z).mean() * 100
        fl[f] = (round(inL, 1), round(inW, 1))
    print("-- zastavice % u gubicima / % u dobicima:", fl)
