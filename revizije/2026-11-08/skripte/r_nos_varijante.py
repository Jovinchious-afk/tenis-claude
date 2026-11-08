# -*- coding: utf-8 -*-
"""Revizija 08.11.2026 — koja inačica nosa bi najbolje prošla na prijašnjim turnirima (08.11.2026 16:38).

Korisnikov zahtjev 08.11.2026: "isto napravi i s prijašnja 3-4 turnira pa vidi koja je najbolja kombinacija
i model za nos ... i onda takav nos treba i postaviti". Postupak (pošten koliko se dade):
  - HOD NAPRIJED: za svaki dan D težine nosa uče se SAMO na riješenim pickovima PRIJE D (nikad isti dan);
  - predikcije dana D = zadnje spremljene analize mečeva s datumom D, plus mečevi D+1 čiji igrači ne igraju
    na D (inače taj meč ujutro još ne bi bio poznat — artefakt "Đoković dvaput" iz prve simulacije);
  - isti `_select_combo` kao dnevni run (pravila tiketa, prag, kaskada, dnevni limiti s datumom D),
    BEZ Claudeova pregleda i sažetka (plaćeni pozivi) — dakle provjera izbora, ne vjerna kopija tiketa;
  - ishod nogu iz baze; noga bez pobjednika = void (kvota 1); ulog 50 po tiketu.
Inačice su zadane UNAPRIJED (popis ispod) — ne traži se "najbolji broj" po svim parametrima, jer bi to
na ~35 dana i ~20 tiketa bila čista naknadna pamet. Presuda: postojanost po tjednima, ne samo zbroj.
    python revizije/2026-11-08/skripte/r_nos_varijante.py
"""
import contextlib
import datetime as dt
import io
import json
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

DUMP = os.path.join(ROOT, ".cache", "rev_2026-11-08", "analyzed_matches.json")
OD, DO = "2026-09-27", "2026-11-07"
TJEDNI = [("Chengdu/Hangzhou/Peking/Tokio", "2026-09-27", "2026-10-04"), ("Šangaj", "2026-10-05", "2026-10-18"),
          ("Lyon/Bruxelles/Almaty", "2026-10-19", "2026-10-25"), ("Basel/Beč", "2026-10-26", "2026-11-01"),
          ("Pariz", "2026-11-02", "2026-11-08")]
BASE = {"K": 60.0, "SZ": 4.0, "SU": 6.0, "PD": 60, "AP": 5.0}
VARIJANTE = [   # (oznaka, opis, parametri, nos-pouzdanost, nos-autsajder)
    ("V0", "bez nosa (stari izbor)", BASE, False, False),
    ("V1", "nos v1: pouzdanost + autsajder (postavljeno danas)", BASE, True, True),
    ("V2", "samo pouzdanost (bez autsajdera)", BASE, True, False),
    ("V3", "samo autsajder (pouzdanost netaknuta)", BASE, False, True),
    ("V4", "oprezniji: K=120, strop 3/4", {**BASE, "K": 120.0, "SZ": 3.0, "SU": 4.0}, True, True),
    ("V5", "agresivniji: K=30, strop 6/9", {**BASE, "K": 30.0, "SZ": 6.0, "SU": 9.0}, True, True),
    ("V6", "kraće pamćenje: prozor 30 dana", {**BASE, "PD": 30}, True, True),
    ("V7", "dulje pamćenje: prozor 120 dana", {**BASE, "PD": 120}, True, True),
    # drugi krug (08.11.2026, nakon provjere SVIH kandidata za autsajdera: 7 od 25, ROI −28%)
    ("V8", "samo pouzdanost, prozor 120", {**BASE, "PD": 120}, True, False),
    ("V9", "pouzdanost 120 + oprezno K=120 strop 3/4", {**BASE, "PD": 120, "K": 120.0, "SZ": 3.0, "SU": 4.0}, True, False),
    ("V10", "pouzdanost 120 + autsajder samo uz Nose ≥ 10pp", {**BASE, "PD": 120, "AP": 10.0}, True, True),
]


def postavi(par):
    no.K_SKUPLJANJE, no.STROP_ZNAK, no.STROP_UKUPNO, no.PROZOR_DANA = par["K"], par["SZ"], par["SU"], par["PD"]
    no.AUTS_MIN_PREDNOST_PP = par.get("AP", 5.0)


def dani():
    d = dt.date.fromisoformat(OD)
    while d <= dt.date.fromisoformat(DO):
        yield d.isoformat()
        d += dt.timedelta(days=1)


def noga(p):
    """(pogođena?, kvota, cijena) noge; bez pobjednika = void."""
    aw = p.get("_win")
    o = tb._pick_odds(p)
    m = p["match"]
    oo = m["odds_p2"] if p["pick"] == m["player1"] else m["odds_p1"]
    pr = npl.devig(o, oo)
    if not aw:
        return None, 1.0, pr
    return aw == p["pick"], o, pr


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rows = json.load(open(DUMP, encoding="utf-8"))
    ex = [e for e in (primjer(r) for r in rows) if e]
    by_date = {}
    for r in rows:
        if r.get("predicted_winner") and r.get("predicted_confidence"):
            by_date.setdefault(str(r.get("match_date"))[:10], []).append(r)
    rez = {v[0]: {"tiketi": [], "noge": []} for v in VARIJANTE}
    for d in dani():
        d1 = (dt.date.fromisoformat(d) + dt.timedelta(days=1)).isoformat()
        today = by_date.get(d, [])
        if not today:
            continue
        igraju = {x for r in today for x in (r["player1"], r["player2"])}
        sutra = [r for r in by_date.get(d1, []) if r["player1"] not in igraju and r["player2"] not in igraju]
        day_rows = today + sutra
        tb.today_zagreb = lambda d=d: dt.date.fromisoformat(d)
        tb.tomorrow_zagreb = lambda d1=d1: dt.date.fromisoformat(d1)
        for oz, _, par, nos_conf, nos_dog in VARIJANTE:
            postavi(par)
            preds = [pred_iz_retka(r) for r in day_rows]
            with contextlib.redirect_stdout(io.StringIO()):
                if nos_conf or nos_dog:
                    t = no.nauci([dict(e) for e in ex], danas=d)
                    dogs = no.primijeni(preds, t)
                    if not nos_conf:
                        no.vrati_model(preds)
                    combo, _ = tb._select_combo(preds, dict(TICKET_CONFIG), dogs if nos_dog else None)
                else:
                    combo, _ = tb._select_combo(preds, dict(TICKET_CONFIG), None)
            if not combo:
                continue
            legs = [noga(p) for p in combo]
            if any(w is False for w, _, _ in legs):
                won, odds = False, 0.0
            else:
                won = True
                odds = 1.0
                for _, o, _ in legs:
                    odds *= o
            rez[oz]["tiketi"].append({"d": d, "won": won, "odds": tb.combined_odds([o for _, o, _ in legs]),
                                      "isplata": 50 * odds if won else 0.0, "n": len(combo),
                                      "autsajder": any(p.get("nos_autsajder") for p in combo)})
            for (w, o, pr), p in zip(legs, combo):
                if w is not None and pr is not None:
                    rez[oz]["noge"].append({"d": d, "w": w, "o": o, "p": pr, "dog": bool(p.get("nos_autsajder"))})
    postavi(BASE)
    print(f"Simulacija {OD} – {DO}, hod naprijed (težine samo iz dana prije), ulog 50 po tiketu")
    print(f"{'inačica':4s} {'opis':52s} {'tiketa':>6s} {'dobitnih':>8s} {'ulog':>6s} {'isplata':>8s} {'ROI':>7s} | "
          f"{'nogu':>4s} {'pogođeno':>8s} {'edge noge':>9s} | {'aut.':>4s} {'aut. ✓':>6s}")
    for oz, opis, *_ in VARIJANTE:
        T, N = rez[oz]["tiketi"], rez[oz]["noge"]
        ul, isp = 50 * len(T), sum(t["isplata"] for t in T)
        nw = sum(1 for x in N if x["w"])
        e = 100 * (nw - sum(x["p"] for x in N)) / len(N) if N else 0.0
        dg = [x for x in N if x["dog"]]
        fv = [x for x in N if not x["dog"]]
        ef = 100 * (sum(1 for x in fv if x["w"]) - sum(x["p"] for x in fv)) / len(fv) if fv else 0.0
        print(f"{oz:4s} {opis:52s} {len(T):6d} {sum(t['won'] for t in T):8d} {ul:6.0f} {isp:8.1f} "
              f"{100 * (isp - ul) / ul if ul else 0:+6.0f}% | {len(N):4d} {100 * nw / len(N) if N else 0:7.1f}% "
              f"{e:+8.1f}pp | {len(dg):4d} {sum(1 for x in dg if x['w']):6d} | favoriti {ef:+.1f}pp")
    print("\nPo tjednima (tiketi dobitni/ukupno, neto u eurima; edge nogu):")
    print(f"{'inačica':4s} " + " | ".join(f"{t[0][:22]:22s}" for t in TJEDNI))
    for oz, *_ in VARIJANTE:
        parts = []
        for _, a, b in TJEDNI:
            T = [t for t in rez[oz]["tiketi"] if a <= t["d"] <= b]
            N = [x for x in rez[oz]["noge"] if a <= x["d"] <= b]
            net = sum(t["isplata"] for t in T) - 50 * len(T)
            e = 100 * (sum(1 for x in N if x["w"]) - sum(x["p"] for x in N)) / len(N) if N else 0.0
            parts.append(f"{sum(t['won'] for t in T)}/{len(T)} {net:+5.0f}€ {e:+4.0f}pp")
        print(f"{oz:4s} " + " | ".join(f"{p:22s}" for p in parts))
    json.dump(rez, open(os.path.join(ROOT, ".cache", "rev_2026-11-08", "nos_varijante.json"), "w", encoding="utf-8"),
              ensure_ascii=False, default=str)


if __name__ == "__main__":
    main()
