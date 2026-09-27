# -*- coding: utf-8 -*-
"""Intuicija — naučeni signal koji radi U SJENI (27.09.2026 12:27, korisnikova želja).

ŠTO JE: poseban statistički model (NE Claude) koji iz svega što bilježimo uz svaku analizu
uči **kada igrač nadmaši svoju cijenu** — za obje strane meča, pa može "nanjušiti" i
autsajdera kojeg Claude nije odabrao. Korisnik je tražio varijablu koja se kroz vrijeme
razvija i sama prepoznaje dobar rizik (npr. autsajdera).

KAKO UČI: logistička regresija s POMAKOM — polazi od cijene (logit devigirane SuperSport
vjerojatnosti) i uči samo ODSTUPANJE od nje, uz jaku L2 kaznu koja ga vuče natrag na
cijenu. Dva sloja:
  1. prior iz povijesti (`config/intuicija_prior.json`, uči se lokalno na 12.324 ATP meča,
     `scripts/intuicija_prior.py`) — tržišni obrasci: pojas kvote, Grand Slam, razina,
     podloga, duga pauza;
  2. naš sloj — uči se IZNOVA na početku svakog dnevnog runa na svim dotad riješenim
     analizama (dakle raste sa svakim danom), s ELO razlikom, formom, konsenzusom, scouting
     profilom, vijestima o ozljedi i razilaženjem Claudea s cijenom.

KAD ŠUTI: jačina kazne bira se vremenskim rezom (starijih 70% uči, novijih 30% provjerava).
Ako NIJEDNA jačina nije bolja od čiste cijene na tim neviđenim mečevima, sloj je 0 —
"intuicija nema što reći". To je namjerno: bolje šutjeti nego pričati šum (povijesni
laboratorij: 0 od 10 varijabli ne tuče tržište; auto-korekcija težina je jednom već
"naučila" šum — clay težine v17).

U SJENI: procjena se upisuje u `context_snapshot["intuicija"]` NAKON što je tiket složen,
pa fizički ne može utjecati na izbor. U odluku ulazi tek kad prođe kapiju zapisanu unaprijed
(DECISION_INPUTS K20) i uz korisnikovo odobrenje. Neuspjeh je {"error": ...}, ne ruši run.
"""
import math

import numpy as np

VERSION = "int-v1"
MIN_TRAIN_ROWS = 150            # manje od ovoga riješenih analiza -> naš sloj šuti
LAMBDAS = (3.0, 10.0, 30.0, 100.0, 300.0, 1000.0)
VAL_SHARE = 0.30

# Tržišni prior — iste osobine se daju izračunati i u povijesti i uživo.
PRIOR_FEATURES = ("b_lt120", "b_120_135", "b_135_143", "b_143_160", "b_160_200", "b_ge200",
                  "gs", "gs_band130_150", "lvl250", "clay", "grass", "rest21", "rest21_opp")
# Naš sloj — sve što je zabilježeno PRIJE meča.
OWN_FEATURES = PRIOR_FEATURES + ("elo_gap", "form_gap", "cons_gap", "cons_missing",
                                 "conf_minus_p", "is_llm_pick", "scout_high", "scout_medlow",
                                 "inj_self", "inj_opp")


def _sig(x):
    return 1.0 / (1.0 + np.exp(-x))


def _logit(p):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def devig(a, b):
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return None
    if not (a > 1.0 and b > 1.0):
        return None
    return (1 / a) / (1 / a + 1 / b)


def _form(v):
    """'7/10' -> 0,7; broj -> broj; inače None."""
    if isinstance(v, (int, float)):
        return float(v) if v <= 1 else float(v) / 10
    try:
        a, b = str(v).split("/")
        return float(a) / float(b)
    except (ValueError, ZeroDivisionError):
        return None


def price_features(odds: float, level: str, surface: str, rest_self, rest_opp) -> dict:
    """Osobine koje postoje i u povijesti i uživo (tržišni prior)."""
    lvl = (level or "").lower()
    surf = (surface or "").lower()
    gs = 1.0 if "grand slam" in lvl else 0.0
    f = {
        "b_lt120": 1.0 if odds < 1.20 else 0.0,
        "b_120_135": 1.0 if 1.20 <= odds < 1.35 else 0.0,
        "b_135_143": 1.0 if 1.35 <= odds < 1.43 else 0.0,
        "b_143_160": 1.0 if 1.43 <= odds < 1.60 else 0.0,
        "b_160_200": 1.0 if 1.60 <= odds < 2.00 else 0.0,
        "b_ge200": 1.0 if odds >= 2.00 else 0.0,
        "gs": gs,
        "gs_band130_150": gs * (1.0 if 1.30 <= odds < 1.50 else 0.0),
        "lvl250": 1.0 if "250" in lvl else 0.0,
        "clay": 1.0 if "clay" in surf else 0.0,
        "grass": 1.0 if "grass" in surf else 0.0,
        "rest21": 1.0 if (rest_self or 0) >= 21 else 0.0,
        "rest21_opp": 1.0 if (rest_opp or 0) >= 21 else 0.0,
    }
    return f


def side_rows(r: dict) -> list:
    """Jedan zapis analize -> dva retka (strana igrača 1 i strana igrača 2).

    `r` treba imati: player1, player2, predicted_winner, predicted_confidence,
    bookmaker_odds_p1/p2, tournament_level, surface, context_snapshot (+ po želji winner).
    Vraća [(osobine, p_strane, pobijedio_ili_None, ime_strane), ...]. Sve osobine su iz
    perspektive te strane; one koje opisuju razliku mijenjaju predznak između strana.
    """
    cs = r.get("context_snapshot") or {}
    o1, o2 = r.get("bookmaker_odds_p1"), r.get("bookmaker_odds_p2")
    p1 = devig(o1, o2)
    if p1 is None:
        return []
    pick = r.get("predicted_winner") or ""
    conf = r.get("predicted_confidence")
    conf = float(conf) / 100 if isinstance(conf, (int, float)) and conf > 0 else None
    winner = r.get("winner")
    mp = cs.get("market_p")
    out = []
    for side in (1, 2):
        me, opp = ("p1", "p2") if side == 1 else ("p2", "p1")
        name = r.get("player1") if side == 1 else r.get("player2")
        p = p1 if side == 1 else 1 - p1
        odds = float(o1 if side == 1 else o2)
        f = price_features(odds, r.get("tournament_level"), r.get("surface"),
                           cs.get(f"{me}_days_rest"), cs.get(f"{opp}_days_rest"))
        eg = cs.get("elo_gap_surface")
        f["elo_gap"] = ((eg if side == 1 else -eg) / 100.0) if isinstance(eg, (int, float)) else 0.0
        fa, fb = _form(cs.get(f"{me}_form_10")), _form(cs.get(f"{opp}_form_10"))
        f["form_gap"] = (fa - fb) if (fa is not None and fb is not None) else 0.0
        if isinstance(mp, (int, float)):
            m_side = mp if side == 1 else 1 - mp
            f["cons_gap"] = 100.0 * (m_side - p) / 10.0      # u desetinama pp
            f["cons_missing"] = 0.0
        else:
            f["cons_gap"], f["cons_missing"] = 0.0, 1.0
        is_pick = 1.0 if (pick and name == pick) else 0.0
        f["is_llm_pick"] = is_pick
        if conf is not None and pick in (r.get("player1"), r.get("player2")):
            c_side = conf if is_pick else 1 - conf
            f["conf_minus_p"] = (c_side - p) * 10.0          # u desetinama
        else:
            f["conf_minus_p"] = 0.0
        sc = (cs.get(f"{me}_scouting_confidence") or "").strip()
        f["scout_high"] = 1.0 if sc == "High" else 0.0
        f["scout_medlow"] = 1.0 if sc == "Med-Low" else 0.0
        gn_self, gn_opp = cs.get(f"{me}_gnews") or {}, cs.get(f"{opp}_gnews") or {}
        f["inj_self"] = 1.0 if (gn_self.get("injury_n") or 0) >= 1 else 0.0
        f["inj_opp"] = 1.0 if (gn_opp.get("injury_n") or 0) >= 1 else 0.0
        won = None if winner is None else (1.0 if winner == name else 0.0)
        out.append((f, p, won, name))
    return out


# ------------------------------------------------------------------------------------
# Model: logistička regresija s pomakom i L2 kaznom (Newton), bez presjecišta — presjecište
# bi učilo "SuperSport je pristran", a to pokrivaju pojasevi kvote.
# ------------------------------------------------------------------------------------
def fit(X, off, y, lam: float, iters: int = 30):
    n, k = X.shape
    beta = np.zeros(k)
    for _ in range(iters):
        mu = _sig(off + X @ beta)
        w = mu * (1 - mu)
        grad = X.T @ (y - mu) - lam * beta
        H = (X * w[:, None]).T @ X + lam * np.eye(k)
        step = np.linalg.solve(H, grad)
        beta += step
        if np.max(np.abs(step)) < 1e-7:
            break
    return beta


def logloss(X, off, y, beta):
    mu = np.clip(_sig(off + X @ beta), 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(mu) + (1 - y) * np.log(1 - mu)))


def train(rows: list, features: tuple, dates: list, prior: dict = None) -> dict:
    """rows = [(osobine, p, pobijedio)], dates = datum retka (za vremenski rez).

    Vraća model {"beta", "mean", "sd", "features", "lambda", "n", "val_gain"} ili model koji
    šuti ({"silent": razlog}) ako nijedna jačina ne pobijedi čistu cijenu na novijih 30%.
    """
    n = len(rows)
    if n < 2:
        return {"silent": "nema podataka", "n": n, "features": list(features)}
    order = np.argsort(np.array(dates, dtype="datetime64[D]"), kind="stable")
    X = np.array([[r[0].get(k, 0.0) for k in features] for r in rows], dtype=float)[order]
    y = np.array([r[2] for r in rows], dtype=float)[order]
    off = np.array([_logit(r[1]) for r in rows], dtype=float)[order]
    if prior:
        off = off + np.array([prior_score(r[0], prior) for r in rows], dtype=float)[order]
    # Samo skaliranje, BEZ centriranja (27.09.2026 12:31): osobina 0 = "nema odstupanja od
    # cijene". Centriranje bez presjecista tiho pretpostavlja da je PROSJECNI redak na cijeni i
    # dijeli ucinak na pola (test na sintetici: +0,8 logit nauceno kao +0,4). Pojasevi kvote
    # (uvijek tocno jedan = 1) i dalje rade kao presjeciste po pojasu.
    mean = np.zeros(X.shape[1])
    sd = X.std(axis=0)
    sd[sd < 1e-9] = 1.0
    Z = X / sd
    cut = int(n * (1 - VAL_SHARE))
    base = logloss(Z[cut:], off[cut:], y[cut:], np.zeros(Z.shape[1]))
    best = (0.0, None)
    for lam in LAMBDAS:
        b = fit(Z[:cut], off[:cut], y[:cut], lam)
        gain = base - logloss(Z[cut:], off[cut:], y[cut:], b)
        if gain > best[0]:
            best = (gain, lam)
    if best[1] is None:
        return {"silent": "nijedna jačina nije bolja od cijene na neviđenim mečevima",
                "n": n, "features": list(features), "val_gain": 0.0}
    beta = fit(Z, off, y, best[1])
    return {"beta": beta.tolist(), "mean": mean.tolist(), "sd": sd.tolist(),
            "features": list(features), "lambda": best[1], "n": n, "val_gain": best[0]}


def score(f: dict, model: dict) -> float:
    """Doprinos modela u logit jedinicama (0 ako model šuti)."""
    if not model or model.get("silent") or not model.get("beta"):
        return 0.0
    z = [(f.get(k, 0.0) - m) / s for k, m, s in zip(model["features"], model["mean"], model["sd"])]
    return float(np.dot(z, model["beta"]))


def prior_score(f: dict, prior: dict) -> float:
    return score(f, prior) if prior else 0.0


def pair_edges(f1: dict, p1: float, f2: dict, p2: float, prior: dict, own: dict) -> tuple:
    """Procjene za OBJE strane meča, normalizirane da se vjerojatnosti zbrajaju u 1.

    Model uči po strani, a osobine nisu sve zrcalne (pojas kvote, scouting, "Claudeov pick"),
    pa sirove procjene dviju strana ne moraju davati zbroj 1 — a u meču pobjeđuje točno jedan.
    (27.09.2026 12:30: bez ovoga su obje strane meča Safiullin-Bu dobile negativan edge.)"""
    raw = []
    for f, p in ((f1, p1), (f2, p2)):
        base = _logit(p)
        sp = prior_score(f, prior)
        so = score(f, own)
        raw.append((float(_sig(base + sp)), float(_sig(base + sp + so))))
    sp_tot = raw[0][0] + raw[1][0]
    sa_tot = raw[0][1] + raw[1][1]
    out = []
    for (qp, qa), p in zip(raw, (p1, p2)):
        qpn, qan = qp / sp_tot, qa / sa_tot
        out.append({"edge_pp": round(100 * (qan - p), 2), "prior_pp": round(100 * (qpn - p), 2),
                    "own_pp": round(100 * (qan - qpn), 2)})
    return out[0], out[1]


def edge_pp(f: dict, p: float, prior: dict, own: dict) -> dict:
    """Procijenjeni edge naspram cijene u postotnim bodovima, i doprinos svakog sloja."""
    base = _logit(p)
    sp = prior_score(f, prior)
    so = score(f, own)
    q_prior = float(_sig(base + sp))
    q_all = float(_sig(base + sp + so))
    return {"edge_pp": round(100 * (q_all - p), 2), "prior_pp": round(100 * (q_prior - p), 2),
            "own_pp": round(100 * (q_all - q_prior), 2)}


# ------------------------------------------------------------------------------------
# Dnevni run
# ------------------------------------------------------------------------------------
def load_prior(path: str = None) -> dict:
    import json
    import os
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "intuicija_prior.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def resolved_training_rows(raw: list) -> tuple:
    """Riješene analize iz baze -> (retci, datumi). Preskače Davis Cup, neuspjele analize i
    retke bez obje kvote ili s pobjednikom izvan para."""
    rows, dates = [], []
    for r in raw:
        cs = r.get("context_snapshot") or {}
        if cs.get("is_davis_cup") or cs.get("analysis_failed"):
            continue
        w = r.get("actual_winner")
        if w not in (r.get("player1"), r.get("player2")):
            continue
        rr = dict(r)
        rr["winner"] = w
        for f, p, won, _name in side_rows(rr):
            rows.append((f, p, won))
            dates.append(str(r.get("match_date") or "")[:10])
    return rows, dates


def fetch_resolved(db) -> list:
    raw, off = [], 0
    while True:
        chunk = db._rest("GET", "analyzed_matches", params={
            "select": "match_date,player1,player2,predicted_winner,actual_winner,predicted_confidence,"
                      "bookmaker_odds_p1,bookmaker_odds_p2,tournament_level,surface,context_snapshot",
            "actual_winner": "not.is.null", "order": "match_date.asc",
            "offset": str(off), "limit": "1000"})
        raw.extend(chunk)
        if len(chunk) < 1000:
            return raw
        off += 1000


def build_models(db) -> dict:
    """Prior iz datoteke + naš sloj naučen iznova na svim riješenim analizama."""
    prior = load_prior()
    raw = fetch_resolved(db)
    rows, dates = resolved_training_rows(raw)
    matches = len(rows) // 2
    if matches < MIN_TRAIN_ROWS:
        own = {"silent": f"premalo riješenih analiza ({matches} < {MIN_TRAIN_ROWS})", "n": len(rows)}
    else:
        own = train(rows, OWN_FEATURES, dates, prior=prior)
    return {"prior": prior, "own": own, "n_matches": matches}


def shadow_scores(pred: dict, models: dict) -> dict:
    """Procjena za obje strane jedne analize (dnevni run). Ne dira pick ni pouzdanost."""
    m = pred.get("match") or {}
    r = {"player1": m.get("player1"), "player2": m.get("player2"),
         "predicted_winner": pred.get("pick"), "predicted_confidence": pred.get("confidence"),
         "bookmaker_odds_p1": m.get("odds_p1"), "bookmaker_odds_p2": m.get("odds_p2"),
         "tournament_level": m.get("level"), "surface": m.get("surface"),
         "context_snapshot": pred.get("context_snapshot") or {}}
    sides = side_rows(r)
    if not sides:
        return {"error": "nema obje kvote", "version": VERSION}
    out = {"version": VERSION, "n_train_matches": models.get("n_matches"),
           "own_silent": (models.get("own") or {}).get("silent"),
           "prior_silent": (models.get("prior") or {}).get("silent") if models.get("prior") else "nema priora"}
    has_pick = pred.get("pick") in (m.get("player1"), m.get("player2")) and bool(pred.get("pick"))
    (f1, p1, _w1, _n1), (f2, p2, _w2, _n2) = sides
    edges = pair_edges(f1, p1, f2, p2, models.get("prior"), models.get("own"))
    for (f, p, _won, name), e in zip(sides, edges):
        if has_pick:
            key = "pick" if name == pred.get("pick") else "other"
        else:                     # analiza bez picka: obje strane pod svojim brojem
            key = "side1" if name == m.get("player1") else "side2"
        out[key] = {"player": name, "p": round(p, 4), **e}
    other = out.get("other") or {}
    # "Njuškalo za autsajdera": strana koju Claude NIJE odabrao, a Intuicija joj daje +3pp ili više.
    out["underdog_flag"] = bool(other and other.get("p", 1) < 0.5 and other.get("edge_pp", 0) >= 3.0)
    return out

# ------------------------------------------------------------------------------------
# Kapija K20 — JEDNO mjesto za pravilo (27.09.2026 12:45, korisnikova odluka: dvije provjere)
# Koriste je scripts/measure_candidates.py, scripts/intuicija_report.py i
# scripts/intuicija_status_email.py, da se pravilo nikad ne razide na dva mjesta.
# ------------------------------------------------------------------------------------
GATE_CHECKS = (150, 300)        # prva provjera na 150, druga na 300; poslije svakih +300


def _corr(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0 or vy <= 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(vx * vy)


def next_check(n: int) -> int:
    for c in GATE_CHECKS:
        if n < c:
            return c
    last = GATE_CHECKS[-1]
    return last + 300 * ((n - last) // 300 + 1)


def gate_status(pairs: list) -> dict:
    """pairs = [(procjena_pp za naš pick, stvarni ostatak_pp, datum)] -> stanje kapije K20.

    Kriterij (isti na svakoj provjeri, zapisan unaprijed u DECISION_INPUTS K20):
      r(procjena, ostatak) >= max(0,12 ; 1,96/sqrt(n)) — tj. >= +0,12 I interval iznad nule
      (uz n=150 to znači r >= 0,16, uz n=300 r >= 0,12); gornja trećina procjena >= +3pp i
      barem 3pp iznad donje; r > 0 u obje vremenske polovice.
    """
    pairs = sorted(pairs, key=lambda x: str(x[2]))
    n = len(pairs)
    out = {"n": n, "next_check": next_check(n)}
    if n < GATE_CHECKS[0]:
        out["verdict"] = f"ČEKA prvu provjeru ({n}/{GATE_CHECKS[0]})"
        out["passed"] = False
        if n >= 10:
            out["r"] = _corr([p[0] for p in pairs], [p[1] for p in pairs])
        return out
    xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
    r = _corr(xs, ys)
    need = max(0.12, 1.96 / math.sqrt(n))
    srt = sorted(pairs, key=lambda p: p[0])
    k = n // 3
    lo = sum(p[1] for p in srt[:k]) / k
    hi = sum(p[1] for p in srt[-k:]) / k
    h = n // 2
    r1 = _corr(xs[:h], ys[:h])
    r2 = _corr(xs[h:], ys[h:])
    passed = r >= need and hi >= 3.0 and hi - lo >= 3.0 and r1 > 0 and r2 > 0
    done = [c for c in GATE_CHECKS if n >= c]
    stage = f"{len(done)}. provjera (n={n})" if n < GATE_CHECKS[-1] + 300 else f"redovna provjera (n={n})"
    out.update({"r": r, "need_r": need, "r_lo": r - 1.96 / math.sqrt(n), "top": hi, "bottom": lo,
                "halves": (r1, r2), "stage": stage, "passed": passed,
                "verdict": ("PROŠLA — prijedlog korisniku da Intuicija dobije riječ pri izboru tiketa"
                            if passed else "NIJE PROŠLA — uči dalje u sjeni")})
    return out


def live_pairs(raw: list) -> tuple:
    """Prave procjene iz baze: [(procjena za naš pick, ostatak, datum)] i ostaci autsajdera sa zastavicom."""
    live, dogs = [], []
    for r in raw:
        cs = r.get("context_snapshot") or {}
        s_ = cs.get("intuicija") or {}
        pk = s_.get("pick") or {}
        w = r.get("actual_winner")
        if not pk or w not in (r.get("player1"), r.get("player2")):
            continue
        won = 1.0 if w == pk.get("player") else 0.0
        live.append((pk.get("edge_pp", 0.0), 100 * (won - pk.get("p", 0.5)), str(r.get("match_date"))[:10]))
        ot = s_.get("other") or {}
        if s_.get("underdog_flag") and ot:
            dogs.append(100 * ((1.0 - won) - ot.get("p", 0.5)))
    return live, dogs
