# -*- coding: utf-8 -*-
"""Revizija 18.10.2026 — LAB: D (statistika s aktualnog turnira po dubini), E (13 kombinacija),
S (forma kao niz), F2 (visina, dob) naspram poštene cijene (18.10.2026 09:19; strogi datum i E13 popravljeni 18.10.2026 10:01).

Pragovi i definicije: revizije/2026-10-18/PRAGOVI_REVIZIJA_2026-10-18.md (09:07), točke D, E,
S, F i "Višestruko testiranje" (Holm na cijeloj obitelji od 36 testova).

Podaci: povijesni laboratorij (.cache/lab/td_joined.pkl + tml.pkl; tennis-data + TML, ATP
2022 – 13.09.2026, poštena cijena = Pinnacle bez marže, inače prosjek kladionica).

ZAŠTITA OD CURENJA: igračevi mečevi se slažu po (početak turnira, runda) — sve što je u tom
poretku PRIJE ovog meča je prošlost. Prozor 365 dana broji se po početku turnira. Profil
ranijeg protivnika (sekvenca, slični protivnici) računa se na TAJ raniji meč, istim pravilom.
Statistika s turnira = samo raniji mečevi glavnog ždrijeba ISTOG turnira.

Samo čita. Izlaz: ispis + .cache/rev_2026-10-18/lab3_rezultati.json i lab3_features.pkl
    python r_lab3.py            # poštena cijena (Pinnacle, inače prosjek)
    python r_lab3.py --avg      # provjera otpornosti: samo prosjek kladionica
"""
import json
import math
import os
import re
import sys
from bisect import bisect_left
from collections import defaultdict

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LAB = os.path.join(ROOT, ".cache", "lab")
OUTD = os.path.join(ROOT, ".cache", "rev_2026-10-18")
USE_AVG = "--avg" in sys.argv
SET_RE = re.compile(r"(\d+)-(\d+)")
MAIN_LEVELS = {"G", "M", "250", "500", "A", "F", "D", "O"}

# indeksi polja u zapisu povijesti
(F_TS, F_RORD, F_TID, F_DATE, F_SRC, F_LVL, F_OPP, F_WON, F_SV, F_ACE, F_DF, F_1IN, F_1W, F_2W, F_SG,
 F_BPS, F_BPF, F_OSV, F_O1W, F_O2W, F_OSG, F_OBPS, F_OBPF, F_SW, F_SL, F_GW, F_GL, F_MIN, F_OK, F_TML) = range(30)


def num(x):
    try:
        v = float(x)
        return v if not math.isnan(v) else None
    except (TypeError, ValueError):
        return None


def sets_games(score):
    """(setovi pobjednika, setovi poraženog, gemovi pobjednika, gemovi poraženog) iz zapisa rezultata."""
    sw = sl = gw = gl = 0
    for a, b in SET_RE.findall(str(score or "")):
        a, b = int(a), int(b)
        if a > 7 or b > 7:      # super tie-break 10-8 i sl. -> broji se kao set, gemovi 1:0
            if a > b:
                sw += 1
                gw += 1
            else:
                sl += 1
                gl += 1
            continue
        gw += a
        gl += b
        if a > b:
            sw += 1
        elif b > a:
            sl += 1
    return sw, sl, gw, gl


def build_history(tml, exact):
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
        for pid, opp, won, me, ot, s_w, s_l, g_w, g_l in (
                (r.winner_id, r.loser_id, 1, w, l_, sw, sl, gw, gl),
                (r.loser_id, r.winner_id, 0, l_, w, sl, sw, gl, gw)):
            if pd.isna(pid):
                continue
            rec = [r.t_start, r.rord, r.tourney_id, d, r.src, r.tourney_level, opp, won,
                   *(x if ok else 0.0 for x in me),
                   *(x if ok else 0.0 for x in (ot[0], ot[4], ot[5], ot[6], ot[7], ot[8])),
                   s_w, s_l, g_w, g_l, (mins or 0.0), ok, idx]
            hist[pid].append(rec)
    for pid in hist:
        hist[pid].sort(key=lambda x: (x[F_TS], x[F_RORD]))
    return hist


SUM_FIELDS = [F_SV, F_ACE, F_DF, F_1IN, F_1W, F_2W, F_SG, F_BPS, F_BPF, F_OSV, F_O1W, F_O2W, F_OSG, F_OBPS, F_OBPF]


def agg(recs):
    """Zbroj statistike preko zapisa s potpunom statistikom -> profil."""
    s = dict.fromkeys(SUM_FIELDS, 0.0)
    n_ok = 0
    for x in recs:
        if x[F_OK]:
            n_ok += 1
            for f in SUM_FIELDS:
                s[f] += x[f]
    sv, osv = s[F_SV], s[F_OSV]
    out = {"n_ok": n_ok}
    out["hold"] = 1 - (s[F_BPF] - s[F_BPS]) / s[F_SG] if s[F_SG] >= 30 else None
    out["brk"] = (s[F_OBPF] - s[F_OBPS]) / s[F_OSG] if s[F_OSG] >= 30 else None
    out["ace"] = s[F_ACE] / sv if sv >= 300 else None
    out["w1"] = s[F_1W] / s[F_1IN] if sv >= 300 and s[F_1IN] > 0 else None
    out["w2"] = s[F_2W] / (sv - s[F_1IN]) if sv >= 300 and (sv - s[F_1IN]) > 0 else None
    out["ret"] = 1 - (s[F_O1W] + s[F_O2W]) / osv if osv >= 300 else None
    return out


def tourn_agg(recs):
    """Prosjek na turniru (raniji mečevi glavnog ždrijeba): ponderirano poenima."""
    s = dict.fromkeys(SUM_FIELDS, 0.0)
    n, n_ok, sl, gw, gl, mins, sp = 0, 0, 0, 0, 0, 0.0, 0
    for x in recs:
        n += 1
        sl += x[F_SL]
        sp += x[F_SW] + x[F_SL]
        gw += x[F_GW]
        gl += x[F_GL]
        mins += x[F_MIN]
        if x[F_OK]:
            n_ok += 1
            for f in SUM_FIELDS:
                s[f] += x[f]
    out = {"n": n, "n_ok": n_ok, "sets_lost": sl, "sets_played": sp, "mins": mins,
           "games": gw / (gw + gl) if (gw + gl) > 0 else None}
    if n_ok and s[F_SV] > 0 and s[F_OSV] > 0:
        sv, osv = s[F_SV], s[F_OSV]
        won = s[F_1W] + s[F_2W] + (osv - s[F_O1W] - s[F_O2W])
        out.update({
            "tpw": won / (sv + osv),
            "hold": 1 - (s[F_BPF] - s[F_BPS]) / s[F_SG] if s[F_SG] > 0 else None,
            "ace": s[F_ACE] / sv,
            "w1": s[F_1W] / s[F_1IN] if s[F_1IN] > 0 else None,
            "w2": s[F_2W] / (sv - s[F_1IN]) if (sv - s[F_1IN]) > 0 else None,
            "ret": 1 - (s[F_O1W] + s[F_O2W]) / osv,
            "bps": s[F_BPS] / s[F_BPF] if s[F_BPF] > 0 else None,
        })
    return out


def match_tpw(x):
    if not x[F_OK]:
        return None
    sv, osv = x[F_SV], x[F_OSV]
    return (x[F_1W] + x[F_2W] + osv - x[F_O1W] - x[F_O2W]) / (sv + osv)


class Profiles:
    """Profil igrača (365 dana) prije zadanog zapisa, s pamćenjem."""

    def __init__(self, hist):
        self.hist = hist
        self.ts = {pid: [x[F_TS] for x in recs] for pid, recs in hist.items()}
        self.pos = {}
        for pid, recs in hist.items():
            for i, x in enumerate(recs):
                self.pos[(pid, x[F_TML])] = i
        self.cache = {}

    def window(self, pid, i):
        recs = self.hist[pid]
        lo = bisect_left(self.ts[pid], recs[i][F_TS] - pd.Timedelta(days=365))
        # strogo po datumu (skeptik 18.10.2026): poredak (t_start, rord) nije strogo vremenski za ~2,8%
        # igrač-mečeva (Challengeri istog tjedna, RR, Rim 2026 s t_start 13.04.), pa se izbacuje sve što
        # nije odigrano PRIJE datuma ovog meča
        cd = recs[i][F_DATE]
        return [x for x in recs[lo:i] if x[F_DATE] < cd]

    def at(self, pid, i):
        key = (pid, i)
        if key not in self.cache:
            self.cache[key] = agg(self.window(pid, i))
        return self.cache[key]

    def at_tml(self, pid, tml_idx):
        i = self.pos.get((pid, tml_idx))
        return None if i is None else self.at(pid, i)


def stats(rows):
    if not rows:
        return {"n": 0}
    won = np.array([r[0] for r in rows], float)
    p = np.array([r[1] for r in rows], float)
    res = won - p
    n = len(res)
    m = res.mean()
    se = res.std(ddof=1) / math.sqrt(n) if n > 1 else float("nan")
    z = m / se if se and se > 0 else 0.0
    return {"n": n, "edge": 100 * m, "lo": 100 * (m - 1.96 * se), "hi": 100 * (m + 1.96 * se),
            "p": math.erfc(abs(z) / math.sqrt(2))}


def main():
    td = pd.read_pickle(os.path.join(LAB, "td_joined.pkl"))
    tml = pd.read_pickle(os.path.join(LAB, "tml.pkl"))
    td = td[td["tml_idx"].notna()].copy()
    td["tml_idx"] = td["tml_idx"].astype(int)
    td = td.drop_duplicates("tml_idx").reset_index(drop=True)
    exact = dict(zip(td["tml_idx"], td["Date"]))
    hist = build_history(tml, exact)
    P = Profiles(hist)
    t = tml.loc[td["tml_idx"]].reset_index(drop=True)
    print(f"igrača u povijesti: {len(hist)} | LAB mečeva: {len(td)}")

    # tercile holda (za E13) i donje trećine 2. servisa / povrata (E1, E2) — na profilima LAB mečeva
    feats = []
    for i in range(len(td)):
        m, r = td.iloc[i], t.iloc[i]
        pf = m["p_avg"] if USE_AVG else m["p_fair"]
        if pf is None or pd.isna(pf):
            continue
        row = {"i": i, "pf": float(pf), "half": m["half"], "series": m["Series"], "round": r["round"],
               "surface": r["surface"], "indoor": r["indoor"], "date": m["Date"]}
        for side, pid, opp, ht, age in (("w", r["winner_id"], r["loser_id"], r["winner_ht"], r["winner_age"]),
                                        ("l", r["loser_id"], r["winner_id"], r["loser_ht"], r["loser_age"])):
            j = P.pos.get((pid, int(td.iloc[i]["tml_idx"])))
            if j is None:
                continue
            recs = hist[pid]
            me = recs[j]
            prof = P.at(pid, j)
            for k, v in prof.items():
                row[f"{k}_{side}"] = v
            row[f"ht_{side}"] = num(ht)
            row[f"age_{side}"] = num(age)
            # ATP pobjede u sezoni (glavni ždrijeb, ista godina, prije ovog meča)
            yr = me[F_TS].year
            row[f"sw_{side}"] = sum(1 for x in recs[:j] if x[F_SRC] == "main" and x[F_LVL] in MAIN_LEVELS
                                    and x[F_WON] and x[F_TS].year == yr and x[F_DATE] < me[F_DATE])
            # odmor: dani od zadnjeg meča (stvarni datum ako je poznat)
            prev = [x for x in recs[max(0, j - 8):j] if x[F_DATE] < me[F_DATE]][-3:]
            row[f"rest_{side}"] = (me[F_DATE] - prev[-1][F_DATE]).days if prev else None
            # forma 10 (svi izvori)
            l10 = [x for x in recs[max(0, j - 16):j] if x[F_DATE] < me[F_DATE]][-10:]
            row[f"form10_{side}"] = (sum(x[F_WON] for x in l10) / len(l10)) if len(l10) >= 5 else None
            # statistika s turnira: raniji mečevi glavnog ždrijeba istog turnira
            same = [x for x in recs[max(0, j - 8):j] if x[F_TID] == me[F_TID] and x[F_SRC] == "main" and x[F_DATE] < me[F_DATE]]
            ta = tourn_agg(same)
            for k, v in ta.items():
                row[f"t{k}_{side}"] = v
            # sekvenca: zadnja 2 meča (ne dalje od 21 dan), protivnikov profil NA TAJ meč
            last2 = [x for x in recs[max(0, j - 8):j] if x[F_DATE] < me[F_DATE]][-2:]
            seq = None
            if len(last2) == 2 and (me[F_DATE] - last2[0][F_DATE]).days <= 21:
                op = [P.at_tml(x[F_OPP], x[F_TML]) for x in last2]
                seq = {"won2": all(x[F_WON] for x in last2),
                       "opp_hold": [o.get("hold") if o else None for o in op],
                       "opp_w2": [o.get("w2") if o else None for o in op],
                       "tpw": [match_tpw(x) for x in last2]}
            row[f"seq_{side}"] = seq
            # slični protivnici (E13): A-ovi mečevi u prozoru s protivnikovim holdom na taj meč
            win = P.window(pid, j)
            row[f"wopp_{side}"] = [(P.at_tml(x[F_OPP], x[F_TML]) or {}).get("hold") for x in win]
            row[f"wwon_{side}"] = [x[F_WON] for x in win]
        feats.append(row)
    f = pd.DataFrame(feats)
    print(f"mečeva s cijenom i obje strane: {len(f)}")

    # percentili na profilima obje strane
    def q(col, qq):
        v = pd.concat([f[col + "_w"], f[col + "_l"]]).dropna()
        return float(v.quantile(qq))

    hold_t1, hold_t2 = q("hold", 1 / 3), q("hold", 2 / 3)
    w2_low, ret_low = q("w2", 1 / 3), q("ret", 1 / 3)
    print(f"tercile holda {hold_t1:.3f}/{hold_t2:.3f} | 2. servis donja trećina ≤ {w2_low:.3f} | povrat donja trećina ≤ {ret_low:.3f}")

    def terc(h):
        if h is None or (isinstance(h, float) and math.isnan(h)):
            return None
        return 0 if h <= hold_t1 else (1 if h <= hold_t2 else 2)

    # E13: omjer protiv protivnika iz iste trećine holda kao današnji protivnik, minus opći omjer
    for a, b in (("w", "l"), ("l", "w")):
        vals = []
        for opps, wons, hb in zip(f[f"wopp_{a}"], f[f"wwon_{a}"], f[f"hold_{b}"]):
            tb = terc(hb)
            if tb is None or not isinstance(opps, list) or len(wons) < 8:
                vals.append(None)
                continue
            sel = [w for o, w in zip(opps, wons) if terc(o) == tb]
            vals.append((sum(sel) / len(sel) - sum(wons) / len(wons)) if len(sel) >= 8 else None)
        f[f"simexc_{a}"] = vals

    pf_arr, half_arr = f["pf"].values, f["half"].values

    def oriented(mw, ml):
        # POPRAVAK (skeptik 18.10.2026): kad uvjet zadovolje OBA igrača (moguće samo u E13), prije je
        # ulazio samo pobjednik (`elif`), što je davalo lažnu prednost. Sada ulaze oba retka.
        out = []
        for k, (aw, al) in enumerate(zip(mw, ml)):
            if aw:
                out.append((1, pf_arr[k], half_arr[k], k))
            if al:
                out.append((0, 1 - pf_arr[k], half_arr[k], k))
        return out

    def col(c, side):
        return pd.to_numeric(f[f"{c}_{side}"], errors="coerce")

    def better(c, gap=0.0, lower=False, need=None):
        w, l = col(c, "w"), col(c, "l")
        ok = w.notna() & l.notna()
        if need is not None:
            ok &= need
        g = (l - w) if lower else (w - l)
        return (ok & (g > gap)).values, (ok & (g < -gap)).values

    dog_w, dog_l = (f["pf"] < 0.5).values, (f["pf"] > 0.5).values
    fav_w, fav_l = dog_l, dog_w
    late = f["round"].isin(["QF", "SF", "F"]).values
    indoor_hard = ((f["surface"] == "Hard") & (f["indoor"] == "I")).values

    tests = []   # (oznaka, smjer, (maska_w, maska_l))
    # ---------- D: statistika s turnira po dubini (T0 primarni)
    tn_w, tn_l = col("tn", "w"), col("tn", "l")
    tok_w, tok_l = col("tn_ok", "w"), col("tn_ok", "l")
    for depth_lab, cond in (("2", (tok_w >= 2) & (tok_l >= 2) & (tok_w < 3) | (tok_w >= 2) & (tok_l >= 2) & (tok_l < 3)),
                            ("3+", (tok_w >= 3) & (tok_l >= 3))):
        cond = cond.fillna(False)
        for code, c, lower in (("T0 udio poena", "ttpw", False), ("T1 hold", "thold", False), ("T2 asovi", "tace", False),
                               ("T3 1. servis", "tw1", False), ("T4 2. servis", "tw2", False), ("T5 povrat", "tret", False),
                               ("T6 BP spašeni", "tbps", False), ("T7 manje izgubljenih setova", "tsets_lost", True),
                               ("T8 udio gemova", "tgames", False)):
            if code.startswith("T7") or code.startswith("T8"):
                need = ((tn_w >= (2 if depth_lab == "2" else 3)) & (tn_l >= (2 if depth_lab == "2" else 3))).fillna(False)
                if depth_lab == "2":
                    need &= ((tn_w < 3) | (tn_l < 3)).fillna(False)
            else:
                need = cond
            mw, ml = better(c, 0.0, lower, need)
            tests.append((f"D {code} | dubina {depth_lab}", +1, (mw, ml)))
    # ---------- E: kombinacije
    ret_w, ret_l, w2_w, w2_l = col("ret", "w"), col("ret", "l"), col("w2", "w"), col("w2", "l")
    w1_w, w1_l, hold_w, hold_l = col("w1", "w"), col("w1", "l"), col("hold", "w"), col("hold", "l")
    sw_w, sw_l = col("sw", "w"), col("sw", "l")
    ht_w, ht_l, age_w, age_l = col("ht", "w"), col("ht", "l"), col("age", "w"), col("age", "l")
    tsl_w, tsl_l = col("tsets_lost", "w"), col("tsets_lost", "l")
    rest_w, rest_l = col("rest", "w"), col("rest", "l")
    ttp_w, ttp_l = col("ttpw", "w"), col("ttpw", "l")
    tm_w, tm_l = col("tmins", "w"), col("tmins", "l")
    tsp_w, tsp_l = col("tsets_played", "w"), col("tsets_played", "l")   # setovi odigrani na turniru (E6)
    E = {
        "E1 povratnik vs slab 2. servis": (+1, ((ret_w - ret_l >= 0.03) & (w2_l <= w2_low)).values,
                                            ((ret_l - ret_w >= 0.03) & (w2_w <= w2_low)).values),
        "E2 server vs slab povratnik": (+1, ((w1_w - w1_l >= 0.04) & (ret_l <= ret_low)).values,
                                         ((w1_l - w1_w >= 0.04) & (ret_w <= ret_low)).values),
        "E3 +8 ATP pobjeda u sezoni i bolji hold": (+1, ((sw_w - sw_l >= 8) & (hold_w > hold_l)).values,
                                                     ((sw_l - sw_w >= 8) & (hold_l > hold_w)).values),
        "E4 +8 ATP pobjeda u sezoni, autsajder": (+1, ((sw_w - sw_l >= 8).values & dog_w),
                                                   ((sw_l - sw_w >= 8).values & dog_l)),
        "E5 8+ cm viši u dvorani (hard)": (+1, ((ht_w - ht_l >= 8).values & indoor_hard),
                                            ((ht_l - ht_w >= 8).values & indoor_hard)),
        "E6 30+ god. i 2+ seta više na turniru (prot. <30)": (-1, ((age_w >= 30) & (age_l < 30) & (tsp_w - tsp_l >= 2)).values,
                                                              ((age_l >= 30) & (age_w < 30) & (tsp_l - tsp_w >= 2)).values),
        "E7 30+ god. uz <=1 dan odmora (prot. 2+)": (-1, ((age_w >= 30) & (rest_w <= 1) & (rest_l >= 2)).values,
                                                      ((age_l >= 30) & (rest_l <= 1) & (rest_w >= 2)).values),
        "E8 5+ god. stariji u QF/SF/F": (-1, ((age_w - age_l >= 5).values & late), ((age_l - age_w >= 5).values & late)),
        "E9 mina: favorit slabijeg 2. servisa vs dobar povratnik": (-1, ((w2_l - w2_w >= 0.03) & (ret_l - ret_w >= 0.03)).values & fav_w,
                                                                     ((w2_w - w2_l >= 0.03) & (ret_w - ret_l >= 0.03)).values & fav_l),
        "E10 mina: favorit koji je na turniru jedva prolazio": (-1, ((tok_w >= 2) & (tok_l >= 2) & (ttp_w <= 0.51) & (ttp_l >= 0.54)).fillna(False).values & fav_w,
                                                                ((tok_w >= 2) & (tok_l >= 2) & (ttp_l <= 0.51) & (ttp_w >= 0.54)).fillna(False).values & fav_l),
        "E11 autsajder dominantniji na turniru (+3pp poena)": (+1, ((tok_w >= 2) & (tok_l >= 2) & (ttp_w - ttp_l >= 0.03)).fillna(False).values & (f["pf"] >= 0.30).values & dog_w,
                                                               ((tok_w >= 2) & (tok_l >= 2) & (ttp_l - ttp_w >= 0.03)).fillna(False).values & (f["pf"] <= 0.70).values & dog_l),
        "E12 favorit s 60+ min više na turniru": (-1, ((tm_w - tm_l >= 60).values & fav_w), ((tm_l - tm_w >= 60).values & fav_l)),
        "E13 slični protivnici: +15pp iznad općeg omjera": (+1, (pd.to_numeric(f["simexc_w"], errors="coerce") >= 0.15).values,
                                                            (pd.to_numeric(f["simexc_l"], errors="coerce") >= 0.15).values),
    }
    for k, (sgn, mw, ml) in E.items():
        tests.append((k, sgn, (np.asarray(mw, bool), np.asarray(ml, bool))))

    # ---------- S: sekvenca
    def seq_mask(side, other, kind):
        out = []
        for s, hb, w2b, hme, w2me in zip(f[f"seq_{side}"], col("hold", other), col("w2", other), col("hold", side), col("w2", side)):
            if not isinstance(s, dict) or not s["won2"]:
                out.append(False)
                continue
            if kind == "hold":
                oh = s["opp_hold"]
                ok = (None not in oh and not pd.isna(hme) and not pd.isna(hb)
                      and all(o - hme >= 0.03 for o in oh) and hb - hme >= 0.03)
            elif kind == "w2":
                oh = s["opp_w2"]
                ok = (None not in oh and not pd.isna(w2me) and not pd.isna(w2b)
                      and all(o - w2me >= 0.03 for o in oh) and w2b - w2me >= 0.03)
            else:
                ok = None not in s["tpw"] and all(x >= 0.55 for x in s["tpw"])
            out.append(bool(ok))
        return np.array(out, bool)

    def not_convincing(side):
        out = []
        for s in f[f"seq_{side}"]:
            if not isinstance(s, dict):
                out.append(False)
                continue
            tp = [x for x in s["tpw"] if x is not None]
            out.append((not s["won2"]) or (len(tp) == 2 and sum(tp) / 2 < 0.52))
        return np.array(out, bool)

    tests.append(("S1 dobio 2 zaredom vs bolje servere, sada opet bolji server", +1,
                  (seq_mask("w", "l", "hold"), seq_mask("l", "w", "hold"))))
    tests.append(("S2 dobio 2 zaredom vs bolji 2. servis, sada opet", +1,
                  (seq_mask("w", "l", "w2"), seq_mask("l", "w", "w2"))))
    tests.append(("S3 uvjerljivo 2 zaredom (55%+ poena), protivnik nije", +1,
                  (seq_mask("w", "l", "tpw") & not_convincing("l"), seq_mask("l", "w", "tpw") & not_convincing("w"))))
    # ---------- F2: visina i dob
    tests.append(("F2a 8+ cm viši (dvostrano)", 0, (((ht_w - ht_l) >= 8).values, ((ht_l - ht_w) >= 8).values)))
    tests.append(("F2b 5+ god. stariji", -1, (((age_w - age_l) >= 5).values, ((age_l - age_w) >= 5).values)))

    # ---------- računanje + stabilnost
    lv = f["series"].map(lambda s: "GS+M" if s in ("Grand Slam", "Masters 1000", "Masters Cup") else ("500" if s == "ATP500" else "250")).values
    early = f["round"].isin(["R128", "R64", "R32"]).values
    res, pvals = {}, []
    for name, sign, (mw, ml) in tests:
        rows = oriented(mw, ml)
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
        sgn = r["sign"] if r["sign"] != 0 else (1 if a["edge"] > 0 else -1)
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

    print("\n" + "=" * 140)
    print(f"{'test':58s} smjer   n      edge   [95% interval]    P1 / P2        Holm   presuda")
    for (name, sign, _), hp in zip(tests, holm):
        r = res[name]
        r["holm"] = hp
        r["verdict"] = verdict(r, hp)
        a, p1, p2 = r["all"], r["P1"], r["P2"]
        if not a.get("n"):
            print(f"{name:58s}   n=0")
            continue
        print(f"{name:58s} {'+' if sign > 0 else ('-' if sign < 0 else '±')}  {a['n']:6d}  {a['edge']:+5.1f}pp [{a['lo']:+5.1f}, {a['hi']:+5.1f}]"
              f"  {p1.get('edge', float('nan')):+5.1f} / {p2.get('edge', float('nan')):+5.1f}   {hp:5.2f}  {r['verdict']}")
    print("\nStabilnost (edge po razini | po rundi | po pojasu cijene) za testove s P<0,10:")
    for (name, sign, _), pv in zip(tests, pvals):
        if pv < 0.10:
            r = res[name]
            fmt = lambda d: " ".join(f"{k}:{v.get('edge', float('nan')):+.1f}(n={v.get('n', 0)})" for k, v in d.items())
            print(f"  {name}\n     razina {fmt(r['lvl'])}\n     runda  {fmt(r['rnd'])}\n     pojas  {fmt(r['band'])}")

    # gradijent po dubini za T0 (opis): dubina 1, 2, 3, 4+
    print("\nT0 udio poena na turniru — gradijent po dubini (oba igrača ≥ k mečeva sa statistikom; opis):")
    for k_ in (1, 2, 3, 4):
        cond = ((tok_w >= k_) & (tok_l >= k_)).fillna(False)
        if k_ < 4:
            cond &= ((tok_w == k_) | (tok_l == k_)).fillna(False)
        mw, ml = better("ttpw", 0.0, False, cond)
        s_ = stats(oriented(mw, ml))
        rr = []
        for kk in range(len(f)):
            if cond.iat[kk] and not pd.isna(ttp_w.iat[kk]) and not pd.isna(ttp_l.iat[kk]):
                rr.append(((ttp_w.iat[kk] - ttp_l.iat[kk]), 1 - f["pf"].iat[kk]))
        # sirova točnost: koliko često pobijedi onaj s boljim T0 (bez cijene) i koliko često favorit
        raw = np.mean([1.0 if d > 0 else 0.0 for d, _ in rr if d != 0]) if rr else float("nan")
        # rr: (razlika T0 pobjednik − poraženi, cijena PORAŽENOG) -> favorit je pobijedio kad je cijena poraženog < 0,5
        fav = np.mean([1.0 if q_ < 0.5 else 0.0 for _, q_ in rr]) if rr else float("nan")
        print(f"  dubina {k_}{'+' if k_ == 4 else ' '}: n={s_.get('n', 0):5d}  bolji T0 pobjeđuje {100*raw:5.1f}% (tržišni favorit pobjeđuje {100*fav:5.1f}%)"
              f"  edge naspram cijene {s_.get('edge', float('nan')):+5.1f}pp [{s_.get('lo', float('nan')):+5.1f}, {s_.get('hi', float('nan')):+5.1f}]")
    # tercile razlike T0 na dubini 2+
    cond = ((tok_w >= 2) & (tok_l >= 2)).fillna(False)
    g = (ttp_w - ttp_l)[cond]
    a_ = g[g != 0].abs()
    if len(a_) > 30:
        q1, q2 = a_.quantile([1 / 3, 2 / 3])
        parts = []
        for lo_, hi_ in [(0, q1), (q1, q2), (q2, 9)]:
            sel = cond & ((ttp_w - ttp_l).abs() > lo_) & ((ttp_w - ttp_l).abs() <= hi_)
            mw, ml = (sel & (ttp_w > ttp_l)).values, (sel & (ttp_l > ttp_w)).values
            st_ = stats(oriented(mw, ml))
            parts.append(f"{st_['edge']:+5.1f} (n={st_['n']}, razlika do {100*hi_:.1f}pp)" if hi_ < 9 else f"{st_['edge']:+5.1f} (n={st_['n']})")
        print("  T0 dubina 2+, tercile razlike (mala / srednja / velika): " + " | ".join(parts))

    with open(os.path.join(OUTD, "lab3_rezultati" + ("_avg" if USE_AVG else "") + ".json"), "w", encoding="utf-8") as fo:
        json.dump(res, fo, indent=1, default=float)
    if not USE_AVG:
        f.drop(columns=[c for c in f.columns if c.startswith(("wopp_", "wwon_", "seq_"))]).to_pickle(os.path.join(OUTD, "lab3_features.pkl"))


if __name__ == "__main__":
    main()
