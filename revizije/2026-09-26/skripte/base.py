# -*- coding: utf-8 -*-
"""Revizija 26.09.2026 — zajednicka baza za sva mjerenja (samo citanje iz lokalnog kesa).

Jedan redak = jedna razrijesena analiza s pickom. Sve "pick minus protivnik" varijable su
poravnate po strani picka. Cijena = devigirana SuperSport screenshot kvota (obje strane).
"""
import json, os, math, re, datetime, collections
import numpy as np
import pandas as pd

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _load(name):
    with open(os.path.join(D, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


def _f(x):
    try:
        if x is None:
            return np.nan
        return float(x)
    except (TypeError, ValueError):
        return np.nan


def _form_num(s):
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


def _rec(d):
    if not isinstance(d, dict):
        return np.nan, np.nan
    w, l = d.get("won"), d.get("lost")
    if w is None or l is None:
        return np.nan, np.nan
    n = w + l
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


ROUND_ORDER = {"Q1": 0, "Q2": 0, "Q3": 0, "R128": 1, "R64": 2, "R32": 3, "R16": 4,
               "QF": 5, "SF": 6, "F": 7, "RR": 5, "DC": -1}


def _post(ms, our_id):
    """Post-match statistika za igraca s ID-em our_id (poravnato po ID-u, nikad po poziciji)."""
    if not isinstance(ms, dict):
        return None
    for k in ("player1Stats", "player2Stats"):
        s = ms.get(k) or {}
        if s and str(s.get("our_player_id")) == str(our_id):
            return s
    return None


def _post_metrics(s, o):
    """Iz statistike igraca (s) i protivnika (o) izvuci mjere za igraca s."""
    if not s or not o:
        return {}
    g = lambda d, k: _f(d.get(k))
    fs, fso = g(s, "firstServe"), g(s, "firstServeOf")
    w1, w1o = g(s, "winningOnFirstServe"), g(s, "winningOnFirstServeOf")
    w2, w2o = g(s, "winningOnSecondServe"), g(s, "winningOnSecondServeOf")
    ow1, ow1o = g(o, "winningOnFirstServe"), g(o, "winningOnFirstServeOf")
    ow2, ow2o = g(o, "winningOnSecondServe"), g(o, "winningOnSecondServeOf")
    sp = w1o + w2o  # servisni poeni
    rp = ow1o + ow2o  # povratni poeni
    tpw, otpw = g(s, "totalPointsWon"), g(o, "totalPointsWon")
    out = {
        "tp_share": tpw / (tpw + otpw) if (tpw + otpw) > 0 else np.nan,
        "serve_won": (w1 + w2) / sp if sp > 0 else np.nan,
        "ret_won": ((ow1o - ow1) + (ow2o - ow2)) / rp if rp > 0 else np.nan,
        "first_in": fs / fso if fso > 0 else np.nan,
        "first_won": w1 / w1o if w1o > 0 else np.nan,
        "second_won": w2 / w2o if w2o > 0 else np.nan,
        "ace_rate": g(s, "aces") / sp if sp > 0 else np.nan,
        "df_rate": g(s, "doubleFaults") / sp if sp > 0 else np.nan,
        "bp_faced": g(s, "breakPointFacedGm"),
        "bp_saved_pct": g(s, "breakPointSavedGm") / g(s, "breakPointFacedGm") if g(s, "breakPointFacedGm") > 0 else np.nan,
        "bp_chances": g(s, "breakPointChanceGm"),
        "bp_conv_pct": g(s, "breakPointWonGm") / g(s, "breakPointChanceGm") if g(s, "breakPointChanceGm") > 0 else np.nan,
        "breaks_made": g(s, "breakPointWonGm"),
        "breaks_suffered": g(o, "breakPointWonGm"),
        "winners": g(s, "winners"),
        "ue": g(s, "unforcedErrors"),
        "net": g(s, "netApproaches"),
        "first_speed": g(s, "averageFirstServeSpeed"),
        "serve_pts": sp,
    }
    return out


def build(surface=None, include_unresolved=False):
    am = _load("analyzed_matches")
    rows = []
    for r in am:
        pw = r.get("predicted_winner")
        if not pw:
            continue
        p1, p2 = r.get("player1"), r.get("player2")
        if pw not in (p1, p2):
            continue
        res = r.get("prediction_correct")
        aw = r.get("actual_winner")
        if res is None and not include_unresolved:
            continue
        if res is not None and aw not in (p1, p2):
            continue  # integritet (vidi analyzed-matches-key-bug)
        cs = r.get("context_snapshot") or {}
        pick_is_p1 = (pw == p1)
        a, b = ("p1", "p2") if pick_is_p1 else ("p2", "p1")
        o1, o2 = _f(r.get("bookmaker_odds_p1")), _f(r.get("bookmaker_odds_p2"))
        op, oo = (o1, o2) if pick_is_p1 else (o2, o1)
        p_dev = np.nan
        if op > 1 and oo > 1:
            p_dev = (1 / op) / (1 / op + 1 / oo)
        mp = _f(cs.get("market_p"))
        mp_pick = (mp if pick_is_p1 else 1 - mp) if not np.isnan(mp) else np.nan
        ms = r.get("match_stats") or {}
        pid = r.get("player1_id") if pick_is_p1 else r.get("player2_id")
        oid = r.get("player2_id") if pick_is_p1 else r.get("player1_id")
        sp_ = _post(ms, pid)
        so_ = _post(ms, oid)
        post = _post_metrics(sp_, so_)
        posto = _post_metrics(so_, sp_)
        fa = r.get("full_analysis") or {}
        rs = cs.get("model_stamp") or {}
        rd = (r.get("round") or cs.get("round") or "").strip()
        tb_p, tb_pn = _rec(cs.get(f"{a}_tiebreak_record"))
        tb_o, tb_on = _rec(cs.get(f"{b}_tiebreak_record"))
        dc_p, dc_pn = _rec(cs.get(f"{a}_decider_record"))
        dc_o, dc_on = _rec(cs.get(f"{b}_decider_record"))
        ctx_p = cs.get(f"{a}_ctx") or {}
        ctx_o = cs.get(f"{b}_ctx") or {}
        seas_p = (ctx_p.get("season") or {})
        seas_o = (ctx_o.get("season") or {})
        gs_p = (ctx_p.get("gs") or {})
        gs_o = (ctx_o.get("gs") or {})
        row = dict(
            id=r["id"], date=r.get("match_date"), created=r.get("created_at"),
            tournament=r.get("tournament"), level=r.get("tournament_level"),
            surface=surface_group(r.get("surface")), surface_raw=r.get("surface"),
            round=rd, round_n=ROUND_ORDER.get(rd, np.nan),
            round_source=cs.get("round_source"),
            era=rs.get("rules_hash"), wver=rs.get("weights_version"), ctxv=cs.get("context_version"),
            pick=pw, opp=(p2 if pick_is_p1 else p1), pick_is_p1=pick_is_p1,
            pick_id=pid, opp_id=oid,
            conf=_f(r.get("predicted_confidence")),
            odds=op, odds_opp=oo, p_dev=p_dev,
            win=(1.0 if res else 0.0) if res is not None else np.nan,
            value=r.get("value_detected"),
            market_p=mp_pick, market_n=_f(cs.get("market_n_books")),
            cons_gap=(mp_pick - p_dev) * 100 if not (np.isnan(mp_pick) or np.isnan(p_dev)) else np.nan,
            elo_s_p=_f(cs.get(f"{a}_elo_surface")), elo_s_o=_f(cs.get(f"{b}_elo_surface")),
            elo_o_p=_f(cs.get(f"{a}_elo_overall")), elo_o_o=_f(cs.get(f"{b}_elo_overall")),
            rank_p=_f(cs.get(f"{a}_ranking")), rank_o=_f(cs.get(f"{b}_ranking")),
            age_p=_f(cs.get(f"{a}_age")), age_o=_f(cs.get(f"{b}_age")),
            h_p=(_f(cs.get(f"{a}_height_cm")) or np.nan) if (_f(cs.get(f"{a}_height_cm")) or 0) > 100 else np.nan,
            h_o=(_f(cs.get(f"{b}_height_cm")) or np.nan) if (_f(cs.get(f"{b}_height_cm")) or 0) > 100 else np.nan,
            hand_p=(ctx_p.get("hand") or ""), hand_o=(ctx_o.get("hand") or ""),
            serve_p=_f(cs.get(f"{a}_serve_pts_won")), serve_o=_f(cs.get(f"{b}_serve_pts_won")),
            fs_pct_p=_f(cs.get(f"{a}_first_serve_pct")), fs_pct_o=_f(cs.get(f"{b}_first_serve_pct")),
            fs_won_p=_f(cs.get(f"{a}_first_serve_won")), fs_won_o=_f(cs.get(f"{b}_first_serve_won")),
            ss_won_p=_f(cs.get(f"{a}_second_serve_won")), ss_won_o=_f(cs.get(f"{b}_second_serve_won")),
            ret_p=_f(cs.get(f"{a}_return_won")), ret_o=_f(cs.get(f"{b}_return_won")),
            retw_p=_f(cs.get(f"{a}_return_won_weighted")), retw_o=_f(cs.get(f"{b}_return_won_weighted")),
            hold_p=_f(cs.get(f"{a}_hold_pct")), hold_o=_f(cs.get(f"{b}_hold_pct")),
            bps_p=_f(cs.get(f"{a}_bp_saved")), bps_o=_f(cs.get(f"{b}_bp_saved")),
            bpc_p=_f(cs.get(f"{a}_bp_converted")), bpc_o=_f(cs.get(f"{b}_bp_converted")),
            aces_p=_f(cs.get(f"{a}_aces")), aces_o=_f(cs.get(f"{b}_aces")),
            tb_p=tb_p, tb_o=tb_o, tb_pn=tb_pn, tb_on=tb_on,
            dec_p=dc_p, dec_o=dc_o, dec_pn=dc_pn, dec_on=dc_on,
            f5_p=_form_num(cs.get(f"{a}_form_5")), f5_o=_form_num(cs.get(f"{b}_form_5")),
            f10_p=_form_num(cs.get(f"{a}_form_10")), f10_o=_form_num(cs.get(f"{b}_form_10")),
            fq_p=_f(cs.get(f"{a}_form_quality")), fq_o=_f(cs.get(f"{b}_form_quality")),
            aoe5_p=_f(cs.get(f"{a}_avg_opp_elo_5")), aoe5_o=_f(cs.get(f"{b}_avg_opp_elo_5")),
            aoe_p=_f(cs.get(f"{a}_avg_opp_elo")), aoe_o=_f(cs.get(f"{b}_avg_opp_elo")),
            m7_p=_f(cs.get(f"{a}_matches_7d")), m7_o=_f(cs.get(f"{b}_matches_7d")),
            s7_p=_f(cs.get(f"{a}_sets_7d")), s7_o=_f(cs.get(f"{b}_sets_7d")),
            rest_p=_f(cs.get(f"{a}_days_rest")), rest_o=_f(cs.get(f"{b}_days_rest")),
            m39_p=_f(cs.get(f"{a}_matches_3_9d")), m39_o=_f(cs.get(f"{b}_matches_3_9d")),
            tbest_p=_f(cs.get(f"{a}_tourn_best_3y")), tbest_o=_f(cs.get(f"{b}_tourn_best_3y")),
            tf_n_p=_f(cs.get(f"{a}_tourn_form_matches")), tf_n_o=_f(cs.get(f"{b}_tourn_form_matches")),
            tf_serve_p=_f(cs.get(f"{a}_tourn_form_serve_won")), tf_serve_o=_f(cs.get(f"{b}_tourn_form_serve_won")),
            tf_ace_p=_f(cs.get(f"{a}_tourn_form_ace_rate")), tf_ace_o=_f(cs.get(f"{b}_tourn_form_ace_rate")),
            tf_bps_p=_f(cs.get(f"{a}_tourn_form_bp_saved")), tf_bps_o=_f(cs.get(f"{b}_tourn_form_bp_saved")),
            tf_bpc_p=_f(cs.get(f"{a}_tourn_form_bp_conv")), tf_bpc_o=_f(cs.get(f"{b}_tourn_form_bp_conv")),
            scout_p=cs.get(f"{a}_scouting_confidence"), scout_o=cs.get(f"{b}_scouting_confidence"),
            seas_w_p=_f(seas_p.get("tour_w")), seas_l_p=_f(seas_p.get("tour_l")),
            seas_w_o=_f(seas_o.get("tour_w")), seas_l_o=_f(seas_o.get("tour_l")),
            gs_sf_p=_f(gs_p.get("sf")), gs_sf_o=_f(gs_o.get("sf")),
            temp=_f(cs.get("weather_temp_c")), hum=_f(cs.get("weather_humidity")),
            wind=_f(cs.get("weather_wind_kmh")), press=_f(cs.get("weather_pressure_hpa")),
            press_g=_f(cs.get("weather_pressure_ground_hpa")),
            wcond=cs.get("weather_condition"), shielded=cs.get("venue_shielded"),
            session=cs.get("session"), pace=cs.get("court_pace_label"),
            penalties=json.dumps(cs.get("measured_penalties")) if cs.get("measured_penalties") else "",
            cap_enforced=cs.get("cap_enforced"),
            analysis=fa.get("analysis") or "", risk_notes=fa.get("risk_notes") or "",
            key_factors=json.dumps(fa.get("key_factors") or [], ensure_ascii=False),
            market_check=cs.get("market_check") or "",
        )
        for k, v in post.items():
            row[f"pm_{k}"] = v
        for k, v in posto.items():
            row[f"pmo_{k}"] = v
        rows.append(row)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    if surface:
        df = df[df.surface == surface].copy()
    # izvedene razlike (pick - protivnik)
    for k in ["elo_s", "elo_o", "age", "h", "serve", "fs_pct", "fs_won", "ss_won", "ret", "retw",
              "hold", "bps", "bpc", "aces", "tb", "dec", "f5", "f10", "fq", "aoe5", "aoe", "m7",
              "s7", "rest", "m39", "tbest", "tf_serve", "tf_ace", "tf_bps", "tf_bpc"]:
        df[f"d_{k}"] = df[f"{k}_p"] - df[f"{k}_o"]
    df["d_rank"] = np.log(df["rank_o"]) - np.log(df["rank_p"])  # + = nas pick bolje rangiran
    df["seas_w_d"] = df["seas_w_p"] - df["seas_w_o"]
    df["resid"] = df["win"] - df["p_dev"]
    df["roi"] = np.where(df["win"] == 1, df["odds"] - 1, -1.0)
    df["logit_p"] = np.log(df["p_dev"] / (1 - df["p_dev"]))
    return df.sort_values(["date", "created"]).reset_index(drop=True)


def dedupe_same_match(df):
    """Isti mec (turnir + par, +-3 dana) moze imati vise redaka — zadrzi zadnji (najbogatiji)."""
    keep = []
    seen = {}
    for i, r in df.iterrows():
        key = (r.tournament, tuple(sorted([str(r.pick), str(r.opp)])))
        prev = seen.get(key)
        if prev is not None and abs((r.date - df.loc[prev, "date"]).days) <= 3:
            keep.remove(prev)
        seen[key] = i
        keep.append(i)
    return df.loc[sorted(keep)].copy()


# ---------------------------------------------------------------- statistika (bez scipy)
def norm_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2))


def corr(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = ~(np.isnan(x) | np.isnan(y))
    x, y = x[m], y[m]
    n = len(x)
    if n < 5 or x.std() == 0 or y.std() == 0:
        return np.nan, np.nan, n
    r = np.corrcoef(x, y)[0, 1]
    # Fisher z -> P
    z = 0.5 * math.log((1 + r) / (1 - r)) * math.sqrt(max(n - 3, 1)) if abs(r) < 1 else 99
    p = 2 * norm_sf(abs(z))
    return r, p, n


def boot_ci(fn, *arrays, B=4000, seed=7):
    rng = np.random.default_rng(seed)
    n = len(arrays[0])
    out = []
    for _ in range(B):
        idx = rng.integers(0, n, n)
        out.append(fn(*[a[idx] for a in arrays]))
    out = np.array([o for o in out if not np.isnan(o)])
    return np.percentile(out, 2.5), np.percentile(out, 97.5)


def edge_table(df, mask, label=""):
    """Stopa pogodaka, ocekivano po cijeni, edge (pp), ROI, n."""
    s = df[mask & df.p_dev.notna() & df.win.notna()]
    n = len(s)
    if n == 0:
        return dict(label=label, n=0)
    wr = s.win.mean()
    ex = s.p_dev.mean()
    se = math.sqrt(max((s.p_dev * (1 - s.p_dev)).sum(), 1e-9)) / n
    z = (wr - ex) / se if se > 0 else np.nan
    return dict(label=label, n=n, wr=round(100 * wr, 1), exp=round(100 * ex, 1),
                edge=round(100 * (wr - ex), 1), z=round(z, 2) if not np.isnan(z) else np.nan,
                roi=round(100 * s.roi.mean(), 1))


def logit_fit(X, y, l2=1e-6, iters=50):
    """Logisticka regresija (Newton-IRLS). X bez stupca konstante — dodaje se ovdje."""
    X = np.column_stack([np.ones(len(X)), X])
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        z = X @ w
        p = 1 / (1 + np.exp(-z))
        W = p * (1 - p)
        H = X.T @ (X * W[:, None]) + l2 * np.eye(X.shape[1])
        g = X.T @ (y - p) - l2 * w
        step = np.linalg.solve(H, g)
        w += step
        if np.abs(step).max() < 1e-8:
            break
    p = 1 / (1 + np.exp(-(X @ w)))
    cov = np.linalg.inv(X.T @ (X * (p * (1 - p))[:, None]) + l2 * np.eye(X.shape[1]))
    se = np.sqrt(np.diag(cov))
    ll = np.sum(y * np.log(np.clip(p, 1e-12, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-12, 1)))
    return w, se, ll


def offset_logit(x, y, offset, iters=50):
    """Logit s cijenom kao OFFSETOM: koliko varijabla x dodaje POVRH devigirane cijene.
    Vraca (beta, se, z, P, n)."""
    x, y, offset = np.asarray(x, float), np.asarray(y, float), np.asarray(offset, float)
    m = ~(np.isnan(x) | np.isnan(y) | np.isnan(offset))
    x, y, offset = x[m], y[m], offset[m]
    n = len(x)
    if n < 20 or x.std() == 0:
        return np.nan, np.nan, np.nan, np.nan, n
    xs = (x - x.mean()) / x.std()
    X = np.column_stack([np.ones(n), xs])
    w = np.zeros(2)
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(offset + X @ w)))
        W = p * (1 - p)
        H = X.T @ (X * W[:, None]) + 1e-9 * np.eye(2)
        g = X.T @ (y - p)
        step = np.linalg.solve(H, g)
        w += step
        if np.abs(step).max() < 1e-9:
            break
    p = 1 / (1 + np.exp(-(offset + X @ w)))
    cov = np.linalg.inv(X.T @ (X * (p * (1 - p))[:, None]))
    se = math.sqrt(cov[1, 1])
    z = w[1] / se
    return w[1], se, z, 2 * norm_sf(abs(z)), n


def brier(p, y):
    p, y = np.asarray(p, float), np.asarray(y, float)
    m = ~(np.isnan(p) | np.isnan(y))
    return float(np.mean((p[m] - y[m]) ** 2)), int(m.sum())
