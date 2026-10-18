# -*- coding: utf-8 -*-
"""Revizija 18.10.2026 — zajednička baza (18.10.2026 09:09; kopija revizije 04.10.2026 18:06).

Jedan redak = jedna riješena analiza s pickom; sve "pick minus protivnik" varijable poravnate
po strani picka. Cijena = devigirana SuperSport kvota (obje strane sa screenshota).
Prilagođeno iz revizije 04.10. — dodano 18.10.2026: uzorci ŠANGAJ / NOVO (od 27.09.) / STARO,
vlaga i tlak, visina, 1. i 2. servis, prosjek statistike s turnira (`p*_tourn_form_*`),
ATP pobjede u sezoni i GS polufinala (`p*_ctx`), raspon i sharp cijena kladionica, verzija
težina, oznaka `elo_suspect`, winneri/neiznuđene greške iz post-match statistike.

Čita samo lokalni dump (.cache/rev_2026-10-18/*.json, napravljen iz Supabasea 18.10.2026
skriptom r_dump.py). Pragovi: revizije/2026-10-18/PRAGOVI_REVIZIJA_2026-10-18.md (09:07).
"""
import json
import math
import os
import re

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DUMP = os.path.join(ROOT, ".cache", "rev_2026-10-18")
NOVO_OD = "2026-09-27"   # match_date od početka ere bccf4742 (27.09.2026 12:17) -> NOVO

ROUND_ORDER = {"Q1": 0, "Q2": 0, "Q3": 0, "R128": 1, "R64": 2, "R32": 3, "R16": 4,
               "QF": 5, "SF": 6, "F": 7, "RR": 5, "DC": -1}


def load(name):
    with open(os.path.join(DUMP, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


def f_(x):
    try:
        return np.nan if x is None else float(x)
    except (TypeError, ValueError):
        return np.nan


def form_num(s):
    """'W W L W W' ili '7/10' -> udio pobjeda."""
    if s is None:
        return np.nan
    s = str(s)
    m = re.match(r"\s*(\d+)\s*/\s*(\d+)", s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return a / b if b else np.nan
    toks = [t for t in re.split(r"[\s,]+", s) if t in ("W", "L")]
    return (sum(t == "W" for t in toks) / len(toks)) if toks else np.nan


def rec(d):
    if not isinstance(d, dict):
        return np.nan, np.nan
    w, l = d.get("won"), d.get("lost")
    if w is None or l is None:
        return np.nan, np.nan
    n = w + l
    return (w / n if n else np.nan), n


def surface_rec(s, indoor=None):
    """'Outdoor 66W/26L (71.7%) — 92 matches | Indoor 30W/15L ...' -> (udio, n) za uvjete meča;
    bez oznake uvjeta uzima zbroj svih dijelova."""
    if not s:
        return np.nan, np.nan
    parts = re.findall(r"(Outdoor|Indoor)?\s*(\d+)W/(\d+)L", str(s))
    if not parts:
        return np.nan, np.nan
    want = None if indoor is None else ("Indoor" if indoor else "Outdoor")
    sel = [(int(w), int(l)) for lab, w, l in parts if want is None or lab == want or not lab]
    if not sel:
        sel = [(int(w), int(l)) for _, w, l in parts]
    w = sum(a for a, _ in sel)
    n = sum(a + b for a, b in sel)
    return (w / n if n else np.nan), n


def surface_group(s):
    s = (s or "").lower()
    if "clay" in s:
        return "clay"
    if "grass" in s:
        return "grass"
    if "hard" in s:
        return "hard"
    return "other"


def post_stats(ms, our_id):
    """Post-match statistika igrača s ID-em our_id (poravnato po ID-u, nikad po poziciji)."""
    if not isinstance(ms, dict):
        return None
    for k in ("player1Stats", "player2Stats"):
        s = ms.get(k) or {}
        if s and str(s.get("our_player_id")) == str(our_id):
            return s
    return None


def post_metrics(s, o):
    if not s or not o:
        return {}
    g = lambda d, k: f_(d.get(k))
    w1, w1o = g(s, "winningOnFirstServe"), g(s, "winningOnFirstServeOf")
    w2, w2o = g(s, "winningOnSecondServe"), g(s, "winningOnSecondServeOf")
    ow1, ow1o = g(o, "winningOnFirstServe"), g(o, "winningOnFirstServeOf")
    ow2, ow2o = g(o, "winningOnSecondServe"), g(o, "winningOnSecondServeOf")
    sp, rp = w1o + w2o, ow1o + ow2o
    tpw, otpw = g(s, "totalPointsWon"), g(o, "totalPointsWon")
    fs, fso = g(s, "firstServe"), g(s, "firstServeOf")
    return {
        "tp_share": tpw / (tpw + otpw) if (tpw + otpw) > 0 else np.nan,
        "tp_total": tpw + otpw,
        "serve_won": (w1 + w2) / sp if sp > 0 else np.nan,
        "ret_won": ((ow1o - ow1) + (ow2o - ow2)) / rp if rp > 0 else np.nan,
        "first_in": fs / fso if fso > 0 else np.nan,
        "ace_rate": g(s, "aces") / sp if sp > 0 else np.nan,
        "df_rate": g(s, "doubleFaults") / sp if sp > 0 else np.nan,
        "aces": g(s, "aces"), "dfs": g(s, "doubleFaults"),
        "bp_faced": g(s, "breakPointFacedGm"), "bp_saved": g(s, "breakPointSavedGm"),
        "bp_chances": g(s, "breakPointChanceGm"), "bp_won": g(s, "breakPointWonGm"),
        # 18.10.2026 09:09: 1. i 2. servis zasebno, winneri i neiznuđene greške (opis, W0/D2)
        "first_won": w1 / w1o if w1o > 0 else np.nan,
        "second_won": w2 / w2o if w2o > 0 else np.nan,
        "winners": g(s, "winners"), "ue": g(s, "unforcedErrors"),
    }


def key_sections(kf):
    """Odjeljci analize (era bccf4742: 1 Rating, 2 Serve/return, 3 Form, 4 Context, 5 Own read)."""
    out = {}
    for item in kf or []:
        m = re.match(r"\s*(\d)\.\s*([^:]+):\s*(.*)", str(item), re.S)
        if m:
            out[int(m.group(1))] = (m.group(2).strip(), m.group(3).strip())
    return out


def build():
    am = load("analyzed_matches")
    tm = load("ticket_matches")
    tk = {t["id"]: t for t in load("tickets")}
    # Noge tiketa: `external_match_id` u ticket_matches je API id (reciklira se) a u
    # analyzed_matches "datum|igrač|igrač", pa se spaja po PARU igrača uz ±2 dana
    # (datum noge i datum analize znaju se razlikovati za dan zbog vremenske zone).
    legs = {}
    for t in tm:
        key = frozenset([str(t.get("player1") or ""), str(t.get("player2") or "")])
        legs.setdefault(key, []).append(t)
    rows = []
    for r in am:
        pw = r.get("predicted_winner")
        p1, p2 = r.get("player1"), r.get("player2")
        res = r.get("prediction_correct")
        aw = r.get("actual_winner")
        if not pw or pw not in (p1, p2) or res is None or aw not in (p1, p2):
            continue
        cs = r.get("context_snapshot") or {}
        is1 = pw == p1
        a, b = ("p1", "p2") if is1 else ("p2", "p1")
        o1, o2 = f_(r.get("bookmaker_odds_p1")), f_(r.get("bookmaker_odds_p2"))
        op, oo = (o1, o2) if is1 else (o2, o1)
        p_dev = (1 / op) / (1 / op + 1 / oo) if (op > 1 and oo > 1) else np.nan
        mp = f_(cs.get("market_p"))
        mp_pick = (mp if is1 else 1 - mp) if not np.isnan(mp) else np.nan
        pid = r.get("player1_id") if is1 else r.get("player2_id")
        oid = r.get("player2_id") if is1 else r.get("player1_id")
        ms = r.get("match_stats") or {}
        sp_, so_ = post_stats(ms, pid), post_stats(ms, oid)
        post, posto = post_metrics(sp_, so_), post_metrics(so_, sp_)
        fa = r.get("full_analysis") or {}
        stamp = cs.get("model_stamp") or {}
        rd = (r.get("round") or "").strip().upper()
        ctx_p, ctx_o = cs.get(f"{a}_ctx") or {}, cs.get(f"{b}_ctx") or {}
        seas_p, seas_o = ctx_p.get("season") or {}, ctx_o.get("season") or {}
        indoor = None
        sr = str(r.get("surface") or "").lower()
        if "indoor" in sr:
            indoor = True
        elif sr:
            indoor = False
        srf_p, srf_pn = surface_rec(cs.get(f"{a}_surface_record"), indoor)
        srf_o, srf_on = surface_rec(cs.get(f"{b}_surface_record"), indoor)
        tb_p, tb_pn = rec(cs.get(f"{a}_tiebreak_record"))
        tb_o, tb_on = rec(cs.get(f"{b}_tiebreak_record"))
        intu = cs.get("intuicija") or {}
        gn_p, gn_o = cs.get(f"{a}_gnews") or {}, cs.get(f"{b}_gnews") or {}
        secs = key_sections(fa.get("key_factors"))
        own = secs.get(5, ("", ""))
        md = pd.Timestamp(str(r.get("match_date"))[:10])
        leg = [t for t in legs.get(frozenset([str(p1), str(p2)]), [])
               if str(t.get("pick")) == str(pw)
               and abs((pd.Timestamp(str(t.get("match_date"))[:10]) - md).days) <= 2]
        pen = cs.get("measured_penalties") or {}
        row = dict(
            id=r["id"], ext_id=r.get("external_match_id"), date=r.get("match_date"),
            created=r.get("created_at"),
            sample="NOVO" if str(r.get("match_date"))[:10] >= NOVO_OD else "STARO",
            shanghai="shanghai" in str(r.get("tournament") or "").lower(),
            elo_suspect=bool(cs.get("elo_suspect")),
            weights_version=stamp.get("weights_version"),
            tournament=r.get("tournament"), level=r.get("tournament_level"),
            surface=surface_group(r.get("surface")), surface_raw=r.get("surface"), indoor=indoor,
            round=rd, round_n=ROUND_ORDER.get(rd, np.nan), round_source=cs.get("round_source"),
            era=stamp.get("rules_hash"), ctxv=cs.get("context_version"),
            pick=pw, opp=(p2 if is1 else p1), pick_id=pid, opp_id=oid,
            conf=f_(r.get("predicted_confidence")),
            conf_raw=f_(pen.get("from")) if pen else f_(r.get("predicted_confidence")),
            penalties=",".join(x.get("rule", "") for x in (pen.get("applied") or [])) if pen else "",
            odds=op, odds_opp=oo, p_dev=p_dev, win=1.0 if res else 0.0,
            value=r.get("value_detected"),
            market_p=mp_pick, market_src=cs.get("market_source"), market_n=f_(cs.get("market_n_books")),
            cons_gap=(mp_pick - p_dev) * 100 if not (np.isnan(mp_pick) or np.isnan(p_dev)) else np.nan,
            market_check=cs.get("market_check") or "",
            session=cs.get("session"), local_time=cs.get("local_time"), pace=cs.get("court_pace_label"),
            temp=f_(cs.get("weather_temp_c")), wind=f_(cs.get("weather_wind_kmh")),
            # 18.10.2026 09:09: puno vrijeme (W0-W4), zaklon (krov/dvorana), raspon i sharp cijena
            humidity=f_(cs.get("weather_humidity")), press=f_(cs.get("weather_pressure_hpa")),
            press_ground=f_(cs.get("weather_pressure_ground_hpa")),
            weather_cond=cs.get("weather_condition"), shielded=cs.get("venue_shielded"),
            market_spread=f_(cs.get("market_spread")),
            market_sharp=((f_(cs.get("market_p_sharp")) if is1 else 1 - f_(cs.get("market_p_sharp")))
                          if cs.get("market_p_sharp") is not None else np.nan),
            ht_p=f_(cs.get(f"{a}_height_cm")), ht_o=f_(cs.get(f"{b}_height_cm")),
            w1_p=f_(cs.get(f"{a}_first_serve_won")), w1_o=f_(cs.get(f"{b}_first_serve_won")),
            w2_p=f_(cs.get(f"{a}_second_serve_won")), w2_o=f_(cs.get(f"{b}_second_serve_won")),
            tf_n_p=f_(cs.get(f"{a}_tourn_form_matches")), tf_n_o=f_(cs.get(f"{b}_tourn_form_matches")),
            tf_sv_p=f_(cs.get(f"{a}_tourn_form_serve_won")), tf_sv_o=f_(cs.get(f"{b}_tourn_form_serve_won")),
            tf_ace_p=f_(cs.get(f"{a}_tourn_form_ace_rate")), tf_ace_o=f_(cs.get(f"{b}_tourn_form_ace_rate")),
            tf_bps_p=f_(cs.get(f"{a}_tourn_form_bp_saved")), tf_bps_o=f_(cs.get(f"{b}_tourn_form_bp_saved")),
            tf_bpc_p=f_(cs.get(f"{a}_tourn_form_bp_conv")), tf_bpc_o=f_(cs.get(f"{b}_tourn_form_bp_conv")),
            path_p=cs.get(f"{a}_tournament_path"), path_o=cs.get(f"{b}_tournament_path"),
            gs_sf_p=f_((ctx_p.get("gs") or {}).get("sf")), gs_sf_o=f_((ctx_o.get("gs") or {}).get("sf")),
            aoe5_p=f_(cs.get(f"{a}_avg_opp_elo_5")), aoe5_o=f_(cs.get(f"{b}_avg_opp_elo_5")),
            h2h=cs.get("h2h") or cs.get("h2h_summary"),
            elo_s_p=f_(cs.get(f"{a}_elo_surface")), elo_s_o=f_(cs.get(f"{b}_elo_surface")),
            elo_o_p=f_(cs.get(f"{a}_elo_overall")), elo_o_o=f_(cs.get(f"{b}_elo_overall")),
            rank_p=f_(cs.get(f"{a}_ranking")), rank_o=f_(cs.get(f"{b}_ranking")),
            age_p=f_(cs.get(f"{a}_age")), age_o=f_(cs.get(f"{b}_age")),
            hold_p=f_(cs.get(f"{a}_hold_pct")), hold_o=f_(cs.get(f"{b}_hold_pct")),
            ret_p=f_(cs.get(f"{a}_return_won")), ret_o=f_(cs.get(f"{b}_return_won")),
            serve_p=f_(cs.get(f"{a}_serve_pts_won")), serve_o=f_(cs.get(f"{b}_serve_pts_won")),
            fs_pct_p=f_(cs.get(f"{a}_first_serve_pct")), fs_pct_o=f_(cs.get(f"{b}_first_serve_pct")),
            bps_p=f_(cs.get(f"{a}_bp_saved")), bps_o=f_(cs.get(f"{b}_bp_saved")),
            bpc_p=f_(cs.get(f"{a}_bp_converted")), bpc_o=f_(cs.get(f"{b}_bp_converted")),
            ace100_p=f_(cs.get(f"{a}_aces_per100")), ace100_o=f_(cs.get(f"{b}_aces_per100")),
            f5_p=form_num(cs.get(f"{a}_form_5")), f5_o=form_num(cs.get(f"{b}_form_5")),
            f10_p=form_num(cs.get(f"{a}_form_10")), f10_o=form_num(cs.get(f"{b}_form_10")),
            fq_p=f_(cs.get(f"{a}_form_quality")), fq_o=f_(cs.get(f"{b}_form_quality")),
            srf_p=srf_p, srf_o=srf_o, srf_pn=srf_pn, srf_on=srf_on,
            tb_p=tb_p, tb_o=tb_o, tb_pn=tb_pn, tb_on=tb_on,
            m7_p=f_(cs.get(f"{a}_matches_7d")), m7_o=f_(cs.get(f"{b}_matches_7d")),
            s7_p=f_(cs.get(f"{a}_sets_7d")), s7_o=f_(cs.get(f"{b}_sets_7d")),
            rest_p=f_(cs.get(f"{a}_days_rest")), rest_o=f_(cs.get(f"{b}_days_rest")),
            tbest_p=f_(cs.get(f"{a}_tourn_best_3y")), tbest_o=f_(cs.get(f"{b}_tourn_best_3y")),
            scout_p=cs.get(f"{a}_scouting_confidence"), scout_o=cs.get(f"{b}_scouting_confidence"),
            hand_p=ctx_p.get("hand") or "", hand_o=ctx_o.get("hand") or "",
            seas_w_p=f_(seas_p.get("tour_w")), seas_w_o=f_(seas_o.get("tour_w")),
            nat_p=cs.get(f"{a}_nationality"), nat_o=cs.get(f"{b}_nationality"),
            int_edge=f_((intu.get("pick") or {}).get("edge_pp")),
            int_dog=bool(intu.get("underdog_flag")) if intu else None,
            inj_p=f_(gn_p.get("injury_n")), inj_o=f_(gn_o.get("injury_n")),
            analysis=fa.get("analysis") or "", risk_notes=fa.get("risk_notes") or "",
            sec1=secs.get(1, ("", ""))[1], sec2=secs.get(2, ("", ""))[1], sec3=secs.get(3, ("", ""))[1],
            sec4=secs.get(4, ("", ""))[1], own_read=own[1], own_title=own[0],
            n_secs=len(secs),
            on_ticket=bool(leg), leg_result=(leg[0].get("result") if leg else None),
            leg_score=(leg[0].get("actual_score") if leg else None),
            ticket_ids=",".join(sorted({str(t.get("ticket_id")) for t in leg})) if leg else "",
            loss_analysis=(next((t.get("loss_analysis") for t in leg if t.get("loss_analysis")), None) if leg else None),
        )
        for k, v in post.items():
            row[f"pm_{k}"] = v
        for k, v in posto.items():
            row[f"pmo_{k}"] = v
        rows.append(row)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    for k in ["elo_s", "elo_o", "age", "hold", "ret", "serve", "fs_pct", "bps", "bpc", "ace100",
              "f5", "f10", "fq", "srf", "tb", "m7", "s7", "rest", "tbest", "seas_w",
              "ht", "w1", "w2", "tf_n", "tf_sv", "tf_ace", "tf_bps", "tf_bpc", "gs_sf", "aoe5"]:
        df[f"d_{k}"] = df[f"{k}_p"] - df[f"{k}_o"]
    df["d_rank"] = np.log(df["rank_o"]) - np.log(df["rank_p"])  # + = naš pick bolje rangiran
    df["resid"] = df["win"] - df["p_dev"]
    df["roi"] = np.where(df["win"] == 1, df["odds"] - 1, -1.0)
    df["d_conf"] = df["conf"] - 100 * df["p_dev"]   # odmak modela od cijene (pp)
    return df.sort_values(["date", "created"]).reset_index(drop=True)


def dedupe_same_match(df):
    """Isti meč (turnir + par, ±3 dana) može imati više redaka — zadrži zadnji (najbogatiji)."""
    keep, seen = [], {}
    for i, r in df.iterrows():
        key = (r.tournament, tuple(sorted([str(r.pick), str(r.opp)])))
        prev = seen.get(key)
        if prev is not None and abs((r.date - df.loc[prev, "date"]).days) <= 3:
            keep.remove(prev)
        seen[key] = i
        keep.append(i)
    return df.loc[sorted(keep)].copy()


# ------------------------------------------------------------------ statistika (bez scipy)
def norm_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2))


def corr(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = ~(np.isnan(x) | np.isnan(y))
    x, y = x[m], y[m]
    n = len(x)
    if n < 5 or x.std() == 0 or y.std() == 0:
        return np.nan, np.nan, n, (np.nan, np.nan)
    r = float(np.corrcoef(x, y)[0, 1])
    zf = 0.5 * math.log((1 + r) / (1 - r)) if abs(r) < 1 else 9.9
    se = 1 / math.sqrt(max(n - 3, 1))
    p = 2 * norm_sf(abs(zf) / se)
    ci = (math.tanh(zf - 1.96 * se), math.tanh(zf + 1.96 * se))
    return r, p, n, ci


def edge(s, col_p="p_dev", col_w="win"):
    """(n, edge pp, pola širine 95% intervala pp, ROI %)."""
    s = s[s[col_p].notna() & s[col_w].notna()]
    n = len(s)
    if n == 0:
        return 0, np.nan, np.nan, np.nan
    e = 100 * (s[col_w].mean() - s[col_p].mean())
    se = 100 * math.sqrt(max((s[col_p] * (1 - s[col_p])).sum(), 1e-9)) / n
    roi = 100 * s["roi"].mean() if "roi" in s else np.nan
    return n, e, 1.96 * se, roi


def holm(pvals):
    """Holm-korigirane P vrijednosti (isti redoslijed kao ulaz)."""
    idx = sorted(range(len(pvals)), key=lambda i: pvals[i])
    m = len(pvals)
    out = [None] * m
    run = 0.0
    for k, i in enumerate(idx):
        run = max(run, min(1.0, (m - k) * pvals[i]))
        out[i] = run
    return out


if __name__ == "__main__":
    d = build()
    print("redaka:", len(d), "| po uzorku:", d["sample"].value_counts().to_dict())
    dd = dedupe_same_match(d)
    print("nakon spajanja istog meča:", len(dd), "| po uzorku:", dd["sample"].value_counts().to_dict())
    print("s cijenom:", dd.p_dev.notna().sum(), "| s udjelom poena:", dd.pm_tp_share.notna().sum(),
          "| elo_suspect:", int(dd.elo_suspect.sum()))
    nv = dd[dd["sample"] == "NOVO"]
    print("NOVO: era", nv.era.value_counts().to_dict(), "| Šangaj", int(nv.shanghai.sum()),
          "| na tiketu", int(nv.on_ticket.sum()), "| odjeljaka 5:", int((nv.n_secs == 5).sum()))
    dd.to_pickle(os.path.join(DUMP, "base.pkl"))
