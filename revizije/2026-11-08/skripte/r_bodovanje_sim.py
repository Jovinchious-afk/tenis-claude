# -*- coding: utf-8 -*-
"""Revizija 08.11.2026 (večer) — simulacija BODOVANJA tiketa i DODATNIH ZNAKOVA nosa (08.11.2026 17:17).

Pragovi: PRAGOVI_REVIZIJA_2026-11-08.md, točke K/BOD3 i M (NAKNADNO 08.11.2026 17:08). Ista metoda kao
`r_nos_varijante.py`: hod naprijed 27.09.–07.11.2026, težine nosa uvijek samo iz dana PRIJE, nos kako je
postavljen (prozor 120, K=60, strop 4/6, nos-autsajder uključen), isti `_select_combo`, bez Claudeova
pregleda. Ništa se ne mijenja u kodu modela — funkcije se zamjenjuju samo unutar ovog procesa.
    python revizije/2026-11-08/skripte/r_bodovanje_sim.py > .cache/rev_2026-11-08/out_bodovanje_sim.txt
"""
import contextlib
import datetime as dt
import io
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from agent import nos_odluka as no  # noqa: E402
from agent import nos_ploca as npl  # noqa: E402
from agent import ticket_builder as tb  # noqa: E402
from config.model_config import TICKET_CONFIG  # noqa: E402
from r_nos_replay import primjer  # noqa: E402
from r_nos_tiket_sim import pred_iz_retka  # noqa: E402
from r_nos_varijante import TJEDNI, noga  # noqa: E402

DUMP = os.path.join(ROOT, ".cache", "rev_2026-11-08", "analyzed_matches.json")
OD, DO = "2026-09-27", "2026-11-07"
ORIG_SCORE = tb._score_combo
ORIG_ZNAKOVI = no.znakovi
ORIG_INFO = dict(no.INFO)
no.PROZOR_DANA, no.K_SKUPLJANJE, no.STROP_ZNAK, no.STROP_UKUPNO, no.AUTS_MIN_PREDNOST_PP = 120, 60.0, 4.0, 6.0, 5.0


# ------------------------------------------------------------------ bodovanje (inačice BOD3)
def napravi_bodovanje(value=True, high=True, weakest=True, extra_mult=1.0, joint_trziste=False):
    def score(combo):
        confs = [max(1, p.get("confidence", 50)) for p in combo]
        if joint_trziste:
            joint = 1.0
            for p in combo:
                m = p["match"]
                o_opp = m["odds_p2"] if tb._pick_odds(p) == float(m.get("odds_p1") or 0) and p["pick"] == m["player1"] else m["odds_p1"]
                pr = npl.devig(tb._pick_odds(p), o_opp) or 0.5
                joint *= pr
        else:
            joint = 1.0
            for c in confs:
                joint *= c / 100.0
        edge_total = 0.0
        if value:
            for p in combo:
                fair, bm = p.get("fair_odds") or 0, tb._pick_odds(p)
                if fair > 0 and bm > 0:
                    ed = 100.0 / fair - 100.0 / bm
                    cap = tb._UNDERDOG_EDGE_CAP if bm >= tb._UNDERDOG_MIN_ODDS else tb._EDGE_CAP
                    if 3.0 <= ed <= cap:
                        edge_total += min(10.0, ed)
        hc = sum(1 for c in confs if c >= 72) if high else 0
        wp = max(0.0, (63 - min(confs)) * 0.6) if weakest else 0.0
        ex = (len(combo) - TICKET_CONFIG["min_matches"]) * 3 * extra_mult
        return joint * 100 + edge_total * 1.5 + hc * 2 - wp - ex
    return score


BODOVANJA = [
    ("B-a", "sadašnje bodovanje", None),
    ("B-b", "bez 'value' bonusa", napravi_bodovanje(value=False)),
    ("B-c", "bez bonusa 72+", napravi_bodovanje(high=False)),
    ("B-d", "bez kazne za najslabiju nogu", napravi_bodovanje(weakest=False)),
    ("B-e", "dvostruka kazna za višak nogu", napravi_bodovanje(extra_mult=2.0)),
    ("B-f", "zajednička vjerojatnost iz TRŽIŠNE cijene", napravi_bodovanje(joint_trziste=True)),
    ("B-g", "samo zajednička vjerojatnost + višak nogu", napravi_bodovanje(value=False, high=False, weakest=False)),
]


# ------------------------------------------------------------------ dodatni znakovi nosa (M)
def _strana(rec, za):
    s = za or rec.get("pick") or ""
    a, o = ("p1", "p2") if s == rec.get("p1") else ("p2", "p1")
    return s, a, o


def _f(v):
    try:
        x = float(v)
        return None if math.isnan(x) else x
    except (TypeError, ValueError):
        return None


ELIM = []        # (turnir, datum, pobjednik) mečeva u kojima je naš pick izgubio


def z_konsenzus(rec, za):
    s, a, o = _strana(rec, za)
    cs = rec["cs"]
    mp = _f(cs.get("market_p"))
    if mp is None:
        return None
    pc = mp if a == "p1" else 1 - mp
    o1, o2 = _f(rec.get("odds_p1")), _f(rec.get("odds_p2"))
    ps = npl.devig(o1 if a == "p1" else o2, o2 if a == "p1" else o1)
    return None if ps is None else (100 * (pc - ps) >= 1.0)


def z_forma_turnira(rec, za):
    s, a, o = _strana(rec, za)
    cs = rec["cs"]
    na, nb = _f(cs.get(f"{a}_tourn_form_matches")), _f(cs.get(f"{o}_tourn_form_matches"))
    va, vb = _f(cs.get(f"{a}_tourn_form_serve_won")), _f(cs.get(f"{o}_tourn_form_serve_won"))
    if None in (na, nb, va, vb) or na < 2 or nb < 2:
        return None
    return (va - vb) >= (0.02 if max(va, vb) < 1.5 else 2.0)


def z_povijest_turnira(rec, za):
    s, a, o = _strana(rec, za)
    ta, tb_ = _f(rec["cs"].get(f"{a}_tourn_best_3y")), _f(rec["cs"].get(f"{o}_tourn_best_3y"))
    return None if ta is None or tb_ is None else ta > tb_


def _tb(d):
    if not isinstance(d, dict):
        return None, 0
    w, l_ = _f(d.get("won")) or 0, _f(d.get("lost")) or 0
    return ((w / (w + l_)) if (w + l_) else None), w + l_


def z_tb_vodstvo(rec, za):
    s, a, o = _strana(rec, za)
    pa, na = _tb(rec["cs"].get(f"{a}_tiebreak_record"))
    pb, nb = _tb(rec["cs"].get(f"{o}_tiebreak_record"))
    if pa is None or pb is None or na < 3 or nb < 3:
        return None
    return (pa - pb) >= 0.10


def z_servis_jednak(rec, za):
    s, a, o = _strana(rec, za)
    va, vb = _f(rec["cs"].get(f"{a}_serve_pts_won")), _f(rec["cs"].get(f"{o}_serve_pts_won"))
    if not va or not vb:
        return None
    return abs(va - vb) < 2.5


def z_sezona(rec, za):
    s, a, o = _strana(rec, za)
    ca, cb = (rec["cs"].get(f"{a}_ctx") or {}), (rec["cs"].get(f"{o}_ctx") or {})
    wa, wb = _f((ca.get("season") or {}).get("tour_w")), _f((cb.get("season") or {}).get("tour_w"))
    return None if wa is None or wb is None else (wa - wb) >= 8


def z_izbacio(rec, za):
    s, a, o = _strana(rec, za)
    opp = rec.get("p2") if a == "p1" else rec.get("p1")
    dd = rec["cs"].get("_datum")
    if not dd:
        return None
    t = rec.get("tournament")
    return any(tt == t and d0 < dd and w == opp for tt, d0, w in ELIM)


ZNAKOVI_M = [
    ("M1", "konsenzus", "prilika", z_konsenzus), ("M3", "forma_turnira", "prilika", z_forma_turnira),
    ("M4", "povijest_turnira", "prilika", z_povijest_turnira), ("M5", "tb_vodstvo", "opis", z_tb_vodstvo),
    ("M6", "servis_jednak", "opis", z_servis_jednak), ("M7", "prot_izbacio", "opis", z_izbacio),
    ("M8", "sezona_pobjede", "prilika", z_sezona),
]


def postavi_znak(sid=None, vrsta=None, fn=None):
    no.INFO.clear()
    no.INFO.update(ORIG_INFO)
    if sid is None:
        no.znakovi = ORIG_ZNAKOVI
        return
    no.INFO[sid] = {"vrsta": vrsta, "cjenovni": False, "oznaka": sid}

    def wrap(rec, za_igraca=None):
        z = ORIG_ZNAKOVI(rec, za_igraca=za_igraca)
        if z.get("error"):
            return z
        v = fn(rec, za_igraca)
        if v is None:
            z["nedostaje"].append(sid)
        elif v:
            z["aktivni"].append(sid)
        return z
    no.znakovi = wrap


# ------------------------------------------------------------------ simulacija
def simuliraj(rows, by_date):
    ex = [e for e in (primjer(r) for r in rows) if e]
    T, N = [], []
    d = dt.date.fromisoformat(OD)
    while d <= dt.date.fromisoformat(DO):
        ds, d1 = d.isoformat(), (d + dt.timedelta(days=1)).isoformat()
        today = by_date.get(ds, [])
        if today:
            igraju = {x for r in today for x in (r["player1"], r["player2"])}
            sutra = [r for r in by_date.get(d1, []) if r["player1"] not in igraju and r["player2"] not in igraju]
            tb.today_zagreb = lambda ds=ds: dt.date.fromisoformat(ds)
            tb.tomorrow_zagreb = lambda d1=d1: dt.date.fromisoformat(d1)
            preds = [pred_iz_retka(r) for r in today + sutra]
            with contextlib.redirect_stdout(io.StringIO()):
                t = no.nauci([dict(e) for e in ex], danas=ds)
                dogs = no.primijeni(preds, t)
                combo, _ = tb._select_combo(preds, dict(TICKET_CONFIG), dogs)
            if combo:
                legs = [noga(p) for p in combo]
                won = not any(w is False for w, _, _ in legs)
                odds = 1.0
                for _, o, _ in legs:
                    odds *= o
                T.append({"d": ds, "won": won, "isplata": 50 * odds if won else 0.0, "n": len(combo)})
                for (w, o, pr), p in zip(legs, combo):
                    if w is not None and pr is not None:
                        N.append({"d": ds, "w": w, "p": pr, "dog": bool(p.get("nos_autsajder"))})
        d += dt.timedelta(days=1)
    return T, N


def sazetak(oz, opis, T, N):
    ul, isp = 50 * len(T), sum(t["isplata"] for t in T)
    nw = sum(1 for x in N if x["w"])
    e = 100 * (nw - sum(x["p"] for x in N)) / len(N) if N else 0.0
    wk = []
    for _, a, b in TJEDNI:
        n_ = [x for x in N if a <= x["d"] <= b]
        wk.append(100 * (sum(1 for x in n_ if x["w"]) - sum(x["p"] for x in n_)) / len(n_) if n_ else float("nan"))
    print(f"{oz:5s} {opis:46s} {len(T):4d} {sum(t['won'] for t in T):4d} {100 * (isp - ul) / ul if ul else 0:+6.0f}% "
          f"| {len(N):4d} {e:+6.1f}pp | tjedni edge " + " ".join(f"{x:+5.1f}" for x in wk))
    return e, wk, (isp - ul) / ul if ul else 0.0


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rows = json.load(open(DUMP, encoding="utf-8"))
    for r in rows:
        cs = r.get("context_snapshot")
        if isinstance(cs, dict):
            cs["_datum"] = str(r.get("match_date"))[:10]
        if r.get("prediction_correct") is False and r.get("actual_winner"):
            ELIM.append((r.get("tournament"), str(r.get("match_date"))[:10], r.get("actual_winner")))
    by_date = {}
    for r in rows:
        if r.get("predicted_winner") and r.get("predicted_confidence"):
            by_date.setdefault(str(r.get("match_date"))[:10], []).append(r)
    print(f"Simulacija {OD} – {DO}, nos kako je postavljen (prozor 120, autsajder uključen), ulog 50")
    print(f"{'oznaka':5s} {'opis':46s} {'tik':>4s} {'dob':>4s} {'ROI':>7s} | {'nogu':>4s} {'edge':>8s} | tjedni edge (5 tjedana)")
    print("--- BOD3: bodovanje tiketa ---")
    ref = None
    for oz, opis, fn in BODOVANJA:
        tb._score_combo = fn or ORIG_SCORE
        postavi_znak()
        res = sazetak(oz, opis, *simuliraj(rows, by_date))
        ref = ref or res
    tb._score_combo = ORIG_SCORE
    print("--- M: nos + jedan dodatni znak (sadašnje bodovanje) ---")
    for oz, sid, vrsta, fn in ZNAKOVI_M:
        postavi_znak(sid, vrsta, fn)
        e, wk, roi = sazetak(oz, f"nos + {sid}", *simuliraj(rows, by_date))
        bolji = sum(1 for a, b in zip(wk, ref[1]) if not (math.isnan(a) or math.isnan(b)) and a >= b)
        print(f"      -> edge {e - ref[0]:+.1f}pp naspram sadašnjeg nosa; tjedana ≥: {bolji}/5; ROI {100 * (roi - ref[2]):+.0f} p.b.")
    postavi_znak()


if __name__ == "__main__":
    main()
