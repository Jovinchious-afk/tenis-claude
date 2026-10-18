# -*- coding: utf-8 -*-
"""Revizija 18.10.2026, drugi dio — LAB: preostale korisnikove kombinacije (B1–B4b), pristupi 2 i 3
statistike s turnira (TA2, TA3) i Nose (N5–N7) naspram poštene cijene (18.10.2026 12:26).

Pragovi i definicije: revizije/2026-10-18/PRAGOVI_B_2026-10-18.md (12:20; U4 ispravljen 12:22
prije ijednog izračuna). Obitelj za Holm = ovih 10 testova.

Podaci: isti LAB kao jutros (.cache/lab/td_joined.pkl + tml.pkl; ATP 2022 – 13.09.2026, poštena
cijena = Pinnacle bez marže, inače prosjek). ELO se računa OVDJE iz TML rezultata 2000–2026
(glavni ždrijeb, Challengeri, kvalifikacije), kronološki, samo iz mečeva PRIJE ovog meča.

ZAŠTITA OD CURENJA: isto kao `r_lab3.py` — igračevi mečevi se slažu po (početak turnira, runda),
a profil uzima samo mečeve odigrane PRIJE datuma ovog meča (strogi datum). ELO prije meča se
zapisuje prije ažuriranja. Statistika s turnira = raniji mečevi glavnog ždrijeba istog turnira.

Nose u LAB-u koristi ISTI kod kao uživo (`agent/nose.py`), s LAB značajkama i LAB-ovim
prosjekom povrata. Težina ELO-a (W_ELO) procjenjuje se samo na P1 prema ishodu.

Samo čita. Izlaz: ispis + .cache/rev_2026-10-18b/b_lab_rezultati.json i b_lab_features.pkl
    python revizije/2026-10-18/skripte/b_lab.py
"""
import json
import math
import os
import sys
from bisect import bisect_left
from collections import defaultdict

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from r_lab3 import num, sets_games, stats  # noqa: E402
from agent import nose as N  # noqa: E402

LAB = os.path.join(ROOT, ".cache", "lab")
OUTD = os.path.join(ROOT, ".cache", "rev_2026-10-18b")
os.makedirs(OUTD, exist_ok=True)

(F_TS, F_RORD, F_TID, F_DATE, F_SRC, F_LVL, F_OPP, F_WON, F_SV, F_ACE, F_DF, F_1IN, F_1W, F_2W, F_SG,
 F_BPS, F_BPF, F_OSV, F_O1IN, F_O1W, F_O2W, F_OSG, F_OBPS, F_OBPF, F_SW, F_SL, F_GW, F_GL, F_MIN,
 F_OK, F_TML, F_SURF, F_OELO) = range(33)
SUM_FIELDS = [F_SV, F_ACE, F_DF, F_1IN, F_1W, F_2W, F_SG, F_BPS, F_BPF, F_OSV, F_O1IN, F_O1W, F_O2W,
              F_OSG, F_OBPS, F_OBPF]


def surf_of(s):
    s = str(s or "")
    return "Hard" if s in ("Hard", "Carpet") else (s if s in ("Clay", "Grass") else "Hard")


# ------------------------------------------------------------------ ELO (prije meča)
def compute_elo(tml, exact):
    """538-stil: K = 250/(n+5)^0,4; ukupni i po podlozi; početno 1500. Walkover se ne broji."""
    srt = tml.sort_values(["t_start", "rord"])
    R, Rs = defaultdict(lambda: 1500.0), defaultdict(lambda: 1500.0)
    n, ns = defaultdict(int), defaultdict(int)
    pre = {}
    for idx, w, l, surface, score in zip(srt.index, srt["winner_id"], srt["loser_id"],
                                         srt["surface"], srt["score"]):
        if pd.isna(w) or pd.isna(l):
            continue
        sf = surf_of(surface)
        pre[idx] = (R[w], R[l], Rs[(w, sf)], Rs[(l, sf)])
        sc = str(score or "")
        if "W/O" in sc.upper() or not sc.strip():
            continue
        for tab, cnt, kw, kl in ((R, n, w, l), (Rs, ns, (w, sf), (l, sf))):
            e = 1.0 / (1.0 + 10 ** ((tab[kl] - tab[kw]) / 400.0))
            kw_ = 250.0 / (cnt[kw] + 5) ** 0.4
            kl_ = 250.0 / (cnt[kl] + 5) ** 0.4
            tab[kw] += kw_ * (1 - e)
            tab[kl] -= kl_ * (1 - e)
            cnt[kw] += 1
            cnt[kl] += 1
    return pre


def build_history(tml, exact, pre):
    hist = defaultdict(list)
    for idx, r in zip(tml.index, tml.itertuples(index=False)):
        d = exact.get(idx, r.approx_date)
        sw, sl, gw, gl = sets_games(r.score)
        w = (num(r.w_svpt), num(r.w_ace), num(r.w_df), num(r.w_1stIn), num(r.w_1stWon), num(r.w_2ndWon),
             num(r.w_SvGms), num(r.w_bpSaved), num(r.w_bpFaced))
        l_ = (num(r.l_svpt), num(r.l_ace), num(r.l_df), num(r.l_1stIn), num(r.l_1stWon), num(r.l_2ndWon),
              num(r.l_SvGms), num(r.l_bpSaved), num(r.l_bpFaced))
        ok = (None not in w and None not in l_ and w[0] > 0 and l_[0] > 0 and w[6] > 0 and l_[6] > 0
              and w[3] > 0 and l_[3] > 0)
        mins = num(r.minutes)
        ep = pre.get(idx)
        sf = surf_of(r.surface)
        for pid, opp, won, me, ot, s_w, s_l, g_w, g_l, oelo in (
                (r.winner_id, r.loser_id, 1, w, l_, sw, sl, gw, gl, ep[1] if ep else None),
                (r.loser_id, r.winner_id, 0, l_, w, sl, sw, gl, gw, ep[0] if ep else None)):
            if pd.isna(pid):
                continue
            rec = [r.t_start, r.rord, r.tourney_id, d, r.src, r.tourney_level, opp, won,
                   *(x if ok else 0.0 for x in me),
                   *(x if ok else 0.0 for x in (ot[0], ot[3], ot[4], ot[5], ot[6], ot[7], ot[8])),
                   s_w, s_l, g_w, g_l, (mins or 0.0), ok, idx, sf, oelo]
            hist[pid].append(rec)
    for pid in hist:
        hist[pid].sort(key=lambda x: (x[F_TS], x[F_RORD]))
    return hist


def agg(recs, min_pts=300, min_g=30):
    s = dict.fromkeys(SUM_FIELDS, 0.0)
    n_ok = 0
    for x in recs:
        if x[F_OK]:
            n_ok += 1
            for f in SUM_FIELDS:
                s[f] += x[f]
    sv, osv, sg, osg = s[F_SV], s[F_OSV], s[F_SG], s[F_OSG]
    o = {"n_ok": n_ok}
    big = sv >= min_pts and osv >= min_pts
    o["s"] = (s[F_1W] + s[F_2W]) / sv if sv >= min_pts else None
    o["r"] = 1 - (s[F_O1W] + s[F_O2W]) / osv if osv >= min_pts else None
    o["w1"] = s[F_1W] / s[F_1IN] if sv >= min_pts and s[F_1IN] > 0 else None
    o["w2"] = s[F_2W] / (sv - s[F_1IN]) if sv >= min_pts and (sv - s[F_1IN]) > 0 else None
    o["r1"] = 1 - s[F_O1W] / s[F_O1IN] if osv >= min_pts and s[F_O1IN] > 0 else None
    o["tpw"] = ((s[F_1W] + s[F_2W] + osv - s[F_O1W] - s[F_O2W]) / (sv + osv)) if big else None
    o["hold"] = 1 - (s[F_BPF] - s[F_BPS]) / sg if sg >= min_g else None
    o["ace_sg"] = s[F_ACE] / sg if sg >= min_g else None
    o["bpf_sg"] = s[F_BPF] / sg if sg >= min_g else None
    o["bps"] = s[F_BPS] / s[F_BPF] if sg >= min_g and s[F_BPF] > 0 else None
    o["bpc"] = (s[F_OBPF] - s[F_OBPS]) / s[F_OBPF] if osg >= min_g and s[F_OBPF] > 0 else None
    return o


def match_tpw(x):
    if not x[F_OK]:
        return None
    sv, osv = x[F_SV], x[F_OSV]
    return (x[F_1W] + x[F_2W] + osv - x[F_O1W] - x[F_O2W]) / (sv + osv)


def match_serve(x):
    if not x[F_OK] or x[F_SV] <= 0:
        return None
    return (x[F_1W] + x[F_2W]) / x[F_SV]


def main():
    td = pd.read_pickle(os.path.join(LAB, "td_joined.pkl"))
    tml = pd.read_pickle(os.path.join(LAB, "tml.pkl"))
    td = td[td["tml_idx"].notna()].copy()
    td["tml_idx"] = td["tml_idx"].astype(int)
    td = td.drop_duplicates("tml_idx").reset_index(drop=True)
    exact = dict(zip(td["tml_idx"], td["Date"]))
    pre = compute_elo(tml, exact)
    hist = build_history(tml, exact, pre)
    ts = {pid: [x[F_TS] for x in recs] for pid, recs in hist.items()}
    pos = {}
    for pid, recs in hist.items():
        for i, x in enumerate(recs):
            pos[(pid, x[F_TML])] = i
    t = tml.loc[td["tml_idx"]].reset_index(drop=True)
    print(f"igrača: {len(hist)} | LAB mečeva: {len(td)} | ELO zapisa: {len(pre)}")

    feats = []
    for i in range(len(td)):
        m, r = td.iloc[i], t.iloc[i]
        pf = m["p_fair"]
        if pf is None or pd.isna(pf):
            continue
        tidx = int(m["tml_idx"])
        ep = pre.get(tidx)
        if ep is None:
            continue
        sf = surf_of(r["surface"])
        row = {"i": i, "pf": float(pf), "half": m["half"], "series": m["Series"], "round": r["round"],
               "surface": r["surface"], "indoor": r["indoor"], "date": m["Date"],
               "best_of": int(m["Best of"]) if not pd.isna(m["Best of"]) else 3}
        for side, pid, eo, es in (("w", r["winner_id"], ep[0], ep[2]), ("l", r["loser_id"], ep[1], ep[3])):
            j = pos.get((pid, tidx))
            if j is None:
                continue
            recs = hist[pid]
            me = recs[j]
            cd = me[F_DATE]
            lo = bisect_left(ts[pid], me[F_TS] - pd.Timedelta(days=365))
            win = [x for x in recs[lo:j] if x[F_DATE] < cd]
            prof = agg(win)
            for k, v in prof.items():
                row[f"{k}_{side}"] = v
            sprof = agg([x for x in win if x[F_SURF] == sf], min_pts=150, min_g=15)
            row[f"stpw_{side}"] = sprof["tpw"] if sprof["n_ok"] >= 5 else None
            row[f"elo_o_{side}"], row[f"elo_s_{side}"] = eo, es
            prev = [x for x in recs[max(0, j - 16):j] if x[F_DATE] < cd]
            l10 = prev[-10:]
            row[f"form10_{side}"] = (sum(x[F_WON] for x in l10) / len(l10)) if len(l10) >= 5 else None
            l5 = prev[-5:]
            oe = [x[F_OELO] for x in l5 if x[F_OELO] is not None]
            row[f"oppelo5_{side}"] = (sum(oe) / len(oe)) if len(oe) >= 3 else None
            row[f"form_q_{side}"] = ((sum(x[F_WON] for x in l5) / len(l5)) * ((sum(oe) / len(oe)) - 1700) / 100
                                     if len(l5) >= 3 and len(oe) >= 3 else None)
            row[f"rest_{side}"] = (cd - prev[-1][F_DATE]).days if prev else None
            row[f"sets7_{side}"] = sum(x[F_SW] + x[F_SL] for x in prev if (cd - x[F_DATE]).days <= 7)
            same = [x for x in recs[max(0, j - 8):j] if x[F_TID] == me[F_TID] and x[F_SRC] == "main" and x[F_DATE] < cd]
            ok_same = [x for x in same if x[F_OK]]
            row[f"tn_ok_{side}"] = len(ok_same)
            tp = [match_tpw(x) for x in ok_same]
            sv_pts = sum(x[F_SV] for x in ok_same)
            row[f"tf_sv_{side}"] = (sum(x[F_1W] + x[F_2W] for x in ok_same) / sv_pts) if sv_pts > 0 else None
            all_pts = sum(x[F_SV] + x[F_OSV] for x in ok_same)
            row[f"ttpw_{side}"] = (sum(x[F_1W] + x[F_2W] + x[F_OSV] - x[F_O1W] - x[F_O2W] for x in ok_same) / all_pts
                                   if all_pts > 0 else None)
            last3 = ok_same[-3:]
            p3 = sum(x[F_SV] + x[F_OSV] for x in last3)
            row[f"ttpw3_{side}"] = (sum(x[F_1W] + x[F_2W] + x[F_OSV] - x[F_O1W] - x[F_O2W] for x in last3) / p3
                                    if len(last3) == 3 and p3 > 0 else None)
            del tp
        feats.append(row)
    f = pd.DataFrame(feats)
    print(f"mečeva s cijenom: {len(f)}")

    def col(c, side):
        return pd.to_numeric(f.get(f"{c}_{side}"), errors="coerce")

    def q(c, qq):
        v = pd.concat([col(c, "w"), col(c, "l")]).dropna()
        return float(v.quantile(qq))

    # ------------------------------------------------------------ Nose značajke (isti kod kao uživo)
    avg_r_lab = float(pd.concat([col("r", "w"), col("r", "l")]).dropna().mean())
    fast = ((f["indoor"] == "I") | (f["surface"] == "Grass")).values

    def nfeat(k, side):
        g = lambda c: (None if pd.isna(f.at[k, f"{c}_{side}"]) else float(f.at[k, f"{c}_{side}"])) \
            if f"{c}_{side}" in f.columns else None
        return {"elo_s": g("elo_s"), "elo_o": g("elo_o"), "s": g("s"), "r": g("r"), "w1": g("w1"), "w2": g("w2"),
                "form10": g("form10"), "form_q": g("form_q"), "tf_n": g("tn_ok"), "tf_sv": g("tf_sv"),
                "sets7": g("sets7"), "rest": g("rest")}

    nose_rows = []
    for k in range(len(f)):
        fw, fl = nfeat(k, "w"), nfeat(k, "l")
        feat = {"p1": fw, "p2": fl, "fast": bool(fast[k]), "best_of": int(f.at[k, "best_of"])}
        _, p_elo, p_pts = N.own_probability(fw, fl, feat["best_of"], avg_r_lab)
        mines_w, mines_l = N.mine_flags(fw, fl), N.mine_flags(fl, fw)
        ups_w, ups_l = N.upset_flags(fl, fw, feat["fast"]), N.upset_flags(fw, fl, feat["fast"])
        nose_rows.append({"p_elo_w": p_elo, "p_pts_w": p_pts, "mines_w": mines_w, "mines_l": mines_l,
                          "ups_w": ups_w, "ups_l": ups_l})
    nz = pd.DataFrame(nose_rows)
    f = pd.concat([f, nz], axis=1)

    # W_ELO na P1 prema ISHODU (pobjednik je uvijek strana "w", pa log-gubitak simetriziramo:
    # svaki meč ulazi dvaput — jednom kao (p, 1), jednom kao (1 − p, 0))
    p1m = (f["half"] == "P1") & f["p_elo_w"].notna() & f["p_pts_w"].notna()
    best_w, best_ll = None, 1e9
    for w_ in np.linspace(0, 1, 21):
        p = (w_ * f.loc[p1m, "p_elo_w"] + (1 - w_) * f.loc[p1m, "p_pts_w"]).clip(1e-4, 1 - 1e-4)
        ll = -float(np.log(p).mean())
        if ll < best_ll:
            best_w, best_ll = float(w_), ll
    print(f"W_ELO (P1, ishod): {best_w:.2f}  log-gubitak {best_ll:.4f}  | prosjek povrata LAB {avg_r_lab:.4f}")
    ll_price = -float(np.log(f.loc[p1m, "pf"].clip(1e-4, 1 - 1e-4)).mean())
    print(f"  za usporedbu: log-gubitak poštene cijene na P1 {ll_price:.4f}")

    def p_own_w(k):
        pe, pp = f.at[k, "p_elo_w"], f.at[k, "p_pts_w"]
        if pe is not None and not pd.isna(pe) and pp is not None and not pd.isna(pp):
            return best_w * pe + (1 - best_w) * pp
        if pe is not None and not pd.isna(pe):
            return pe
        return pp if (pp is not None and not pd.isna(pp)) else None
    f["p_own_w"] = [p_own_w(k) for k in range(len(f))]

    pf_arr, half_arr = f["pf"].values, f["half"].values

    def oriented(mw, ml):
        out = []
        for k, (aw, al) in enumerate(zip(mw, ml)):
            if aw:
                out.append((1, pf_arr[k], half_arr[k], k))
            if al:
                out.append((0, 1 - pf_arr[k], half_arr[k], k))
        return out

    fav_w, fav_l = (f["pf"] > 0.5).values, (f["pf"] < 0.5).values
    slow = ((f["surface"] == "Clay") | ((f["surface"] == "Hard") & (f["indoor"] != "I"))).values
    eb_w = 0.5 * col("elo_s", "w") + 0.5 * col("elo_o", "w")
    eb_l = 0.5 * col("elo_s", "l") + 0.5 * col("elo_o", "l")
    sr_w, sr_l = col("s", "w") + col("r", "w"), col("s", "l") + col("r", "l")
    ace_t, ret_t = q("ace_sg", 2 / 3), q("r", 2 / 3)
    bps_t, bpf_t, bpc_t = q("bps", 2 / 3), q("bpf_sg", 2 / 3), q("bpc", 2 / 3)
    print(f"gornje trećine: asovi/servis-gem {ace_t:.3f} | povrat {ret_t:.3f} | BP spašeni {bps_t:.3f} | "
          f"BP suočeni/gem {bpf_t:.3f} | realizacija BP {bpc_t:.3f}")
    m1w = (col("w1", "w") + col("r1", "w")) - (col("w1", "l") + col("r1", "l"))
    tn_w, tn_l = col("tn_ok", "w"), col("tn_ok", "l")
    k_shr = 10.0

    def blended(side):
        n_ = col("tn_ok", side)
        base = col("stpw", side).fillna(col("tpw", side))
        return (n_ * col("ttpw", side) + k_shr * base) / (n_ + k_shr)
    bl_w, bl_l = blended("w"), blended("l")

    tests = []
    tests.append(("B1 (#3) 1. servis + povrat na 1. servis >= +4pp", +1,
                  ((m1w >= 0.04).fillna(False).values, (m1w <= -0.04).fillna(False).values)))
    tests.append(("B2 (#5) favorit-asovi vs jak povratnik, spora podloga (-)", -1,
                  (((col("ace_sg", "w") >= ace_t) & (col("r", "l") >= ret_t)).fillna(False).values & fav_w & slow,
                   ((col("ace_sg", "l") >= ace_t) & (col("r", "w") >= ret_t)).fillna(False).values & fav_l & slow)))
    tests.append(("B3 (#6) spašava puno BP, suočava puno, vs dobar realizator (-)", -1,
                  (((col("bps", "w") >= bps_t) & (col("bpf_sg", "w") >= bpf_t) & (col("bpc", "l") >= bpc_t)).fillna(False).values,
                   ((col("bps", "l") >= bps_t) & (col("bpf_sg", "l") >= bpf_t) & (col("bpc", "w") >= bpc_t)).fillna(False).values)))
    tests.append(("B4a (#10) ELO +50, servis+povrat -2pp (nepotvrđeno) (-)", -1,
                  (((eb_w - eb_l >= 50) & (sr_w - sr_l <= -0.02)).fillna(False).values,
                   ((eb_l - eb_w >= 50) & (sr_l - sr_w <= -0.02)).fillna(False).values)))
    tests.append(("B4b (#10) ELO +50 potvrđen servisom+povratom i protivnicima", +1,
                  (((eb_w - eb_l >= 50) & (sr_w - sr_l >= 0.02) & (col("oppelo5", "w") >= col("oppelo5", "l"))).fillna(False).values,
                   ((eb_l - eb_w >= 50) & (sr_l - sr_w >= 0.02) & (col("oppelo5", "l") >= col("oppelo5", "w"))).fillna(False).values)))
    c3 = ((tn_w >= 3) & (tn_l >= 3)).fillna(False)
    tests.append(("TA2 zadnja 3 meča na turniru: bolji udio poena", +1,
                  ((c3 & (col("ttpw3", "w") > col("ttpw3", "l"))).fillna(False).values,
                   (c3 & (col("ttpw3", "l") > col("ttpw3", "w"))).fillna(False).values)))
    c2 = ((tn_w >= 2) & (tn_l >= 2)).fillna(False)
    tests.append(("TA3 turnir + 365 dana na podlozi (k=10), A-B >= +1pp", +1,
                  ((c2 & (bl_w - bl_l >= 0.01)).fillna(False).values, (c2 & (bl_l - bl_w >= 0.01)).fillna(False).values)))
    mr_w = f["mines_w"].map(len).values
    mr_l = f["mines_l"].map(len).values
    tests.append(("N5 Nose mina: favorit s Mine Risk >= 2 (-)", -1, ((mr_w >= 2) & fav_w, (mr_l >= 2) & fav_l)))
    uv_w = f["ups_w"].map(len).values   # razlozi ZA pobjednika kao autsajdera
    uv_l = f["ups_l"].map(len).values
    dog_ok_w = ((f["pf"] >= 0.25) & (f["pf"] < 0.5)).values
    dog_ok_l = ((f["pf"] > 0.5) & (f["pf"] <= 0.75)).values
    tests.append(("N6 Nose autsajder: Upset Value >= 2 (cijena 0,25-0,50)", +1,
                  ((uv_w >= 2) & dog_ok_w, (uv_l >= 2) & dog_ok_l)))
    po = pd.to_numeric(f["p_own_w"], errors="coerce")
    tests.append(("N7 Nose vlastita vjerojatnost >= cijena + 5pp", +1,
                  ((po - f["pf"] >= 0.05).fillna(False).values, ((1 - po) - (1 - f["pf"]) >= 0.05).fillna(False).values)))

    lv = f["series"].map(lambda s: "GS+M" if s in ("Grand Slam", "Masters 1000", "Masters Cup") else ("500" if s == "ATP500" else "250")).values
    early = f["round"].isin(["R128", "R64", "R32"]).values
    res, pvals = {}, []
    for name, sign, (mw, ml) in tests:
        rows = oriented(np.asarray(mw, bool), np.asarray(ml, bool))
        a = stats(rows)
        p1 = stats([r for r in rows if r[2] == "P1"])
        p2 = stats([r for r in rows if r[2] == "P2"])
        by_lvl = {g: stats([r for r in rows if lv[r[3]] == g]) for g in ("GS+M", "500", "250")}
        by_rnd = {g: stats([r for r in rows if (early[r[3]] if g == "rano" else not early[r[3]])]) for g in ("rano", "kasno")}

        def bandof(pA):
            return "jak fav" if pA >= 0.70 else ("fav" if pA >= 0.5 else ("autsajder" if pA >= 0.30 else "veliki autsajder"))
        by_band = {g: stats([r for r in rows if bandof(r[1]) == g]) for g in ("jak fav", "fav", "autsajder", "veliki autsajder")}
        res[name] = {"sign": sign, "all": a, "P1": p1, "P2": p2, "lvl": by_lvl, "rnd": by_rnd, "band": by_band}
        pvals.append(a.get("p", 1.0) if a.get("n") else 1.0)
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    holm, run = [None] * len(pvals), 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (len(pvals) - k) * pvals[i]))
        holm[i] = run

    def verdict(r, hp):
        a, p1, p2 = r["all"], r["P1"], r["P2"]
        if a.get("n", 0) < 30 or p1.get("n", 0) < 10 or p2.get("n", 0) < 10:
            return "PREMALO"
        sgn = r["sign"]
        same = (a["edge"] > 0) == (sgn > 0)
        ci = (a["lo"] > 0) if sgn > 0 else (a["hi"] < 0)
        halves = (p1["edge"] > 0) == (p2["edge"] > 0) == (a["edge"] > 0)

        def stable(groups, need):
            ok = [g for g in groups.values() if g.get("n", 0) >= 50]
            if len(ok) < 1:
                return True
            k = sum(1 for g in ok if (g["edge"] > 0) == (a["edge"] > 0))
            return k >= min(need, len(ok))
        stab = stable(r["lvl"], 2) and stable(r["rnd"], 2) and stable(r["band"], 3)
        if same and ci and halves and abs(a["edge"]) >= 2 and hp < 0.05 and stab:
            return "PROLAZI"
        if same and ci and halves:
            return "SLAB" + ("" if stab else " (nestabilno)")
        return "PADA"

    print("\n" + "=" * 150)
    print(f"{'test':62s} smjer   n      edge   [95% interval]    P1 / P2        Holm   presuda")
    for (name, sign, _), hp in zip(tests, holm):
        r = res[name]
        r["holm"] = hp
        r["verdict"] = verdict(r, hp)
        a, p1, p2 = r["all"], r["P1"], r["P2"]
        if not a.get("n"):
            print(f"{name:62s}   n=0")
            continue
        print(f"{name:62s} {'+' if sign > 0 else '-'}  {a['n']:6d}  {a['edge']:+5.1f}pp [{a['lo']:+5.1f}, {a['hi']:+5.1f}]"
              f"  {p1.get('edge', float('nan')):+5.1f} / {p2.get('edge', float('nan')):+5.1f}   {hp:5.2f}  {r['verdict']}")

    # N7 na P2 posebno (zapisani kriterij: P2 edge >= +2pp, interval iznad 0, i P1 > 0)
    n7 = res["N7 Nose vlastita vjerojatnost >= cijena + 5pp"]
    print(f"\nN7 po zapisanom kriteriju: P2 {n7['P2'].get('edge', float('nan')):+.1f}pp "
          f"[{n7['P2'].get('lo', float('nan')):+.1f}, {n7['P2'].get('hi', float('nan')):+.1f}] n={n7['P2'].get('n')} | "
          f"P1 {n7['P1'].get('edge', float('nan')):+.1f}pp n={n7['P1'].get('n')}")
    # r(P_own − cijena, ishod − cijena) po polovici — strana pobjednika i gubitnika simetrično
    for h in ("P1", "P2"):
        mm = (f["half"] == h) & po.notna()
        x = np.concatenate([(po - f["pf"])[mm].values, (-(po - f["pf"]))[mm].values])
        y = np.concatenate([(1 - f["pf"])[mm].values, (0 - (1 - f["pf"]))[mm].values])
        rr = float(np.corrcoef(x, y)[0, 1])
        print(f"  r(P_own − cijena, ishod − cijena) {h}: {rr:+.4f} (n={int(mm.sum())} mečeva)")
    # log-gubitak: Nose sam, cijena sama, na P2
    mm = (f["half"] == "P2") & po.notna()
    print(f"  log-gubitak P2: Nose {-float(np.log(po[mm].clip(1e-4, 1 - 1e-4)).mean()):.4f} | "
          f"cijena {-float(np.log(f.loc[mm, 'pf'].clip(1e-4, 1 - 1e-4)).mean()):.4f}")
    print(f"  Nose i cijena biraju istog favorita: {100 * float(((po[mm] > 0.5) == (f.loc[mm, 'pf'] > 0.5)).mean()):.1f}% (P2)")

    # Opis (NIJE test, ne ulazi u Holm): pojedinačna upozorenja M1–M5 i U1–U4 — za razinu dokaza u aplikaciji
    print("\nOPIS (ne test): pojedinačna Nose upozorenja na LAB-u, edge strane na koju se odnose")
    desc = {}
    for flag in ("M1", "M2", "M3", "M4", "M5"):
        mw = np.array([flag in x for x in f["mines_w"]]) & fav_w
        ml = np.array([flag in x for x in f["mines_l"]]) & fav_l
        s_ = stats(oriented(mw, ml))
        s1 = stats([r for r in oriented(mw, ml) if r[2] == "P1"])
        s2 = stats([r for r in oriented(mw, ml) if r[2] == "P2"])
        desc[flag] = {"all": s_, "P1": s1, "P2": s2}
        print(f"  {flag} favorit: n={s_.get('n', 0):5d} edge {s_.get('edge', float('nan')):+5.1f}pp "
              f"[{s_.get('lo', float('nan')):+5.1f}, {s_.get('hi', float('nan')):+5.1f}]  P1 {s1.get('edge', float('nan')):+5.1f} / P2 {s2.get('edge', float('nan')):+5.1f}")
    for flag in ("U1", "U2", "U3", "U4"):
        mw = np.array([flag in x for x in f["ups_w"]]) & dog_ok_w
        ml = np.array([flag in x for x in f["ups_l"]]) & dog_ok_l
        s_ = stats(oriented(mw, ml))
        s1 = stats([r for r in oriented(mw, ml) if r[2] == "P1"])
        s2 = stats([r for r in oriented(mw, ml) if r[2] == "P2"])
        desc[flag] = {"all": s_, "P1": s1, "P2": s2}
        print(f"  {flag} autsajder: n={s_.get('n', 0):5d} edge {s_.get('edge', float('nan')):+5.1f}pp "
              f"[{s_.get('lo', float('nan')):+5.1f}, {s_.get('hi', float('nan')):+5.1f}]  P1 {s1.get('edge', float('nan')):+5.1f} / P2 {s2.get('edge', float('nan')):+5.1f}")

    with open(os.path.join(OUTD, "b_lab_rezultati.json"), "w", encoding="utf-8") as fo:
        json.dump({"tests": res, "w_elo": best_w, "avg_r_lab": avg_r_lab, "opis": desc}, fo, indent=1, default=float)
    f.drop(columns=["mines_w", "mines_l", "ups_w", "ups_l"]).to_pickle(os.path.join(OUTD, "b_lab_features.pkl"))


if __name__ == "__main__":
    main()
