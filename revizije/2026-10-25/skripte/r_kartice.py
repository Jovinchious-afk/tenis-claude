# -*- coding: utf-8 -*-
"""Revizija 25.10.2026 — C1: kartica za svaki GUBITNI pick TJEDNA (Lyon, Bruxelles, Almaty)
(25.10.2026 10:31).

Za svaki poraz na jednom mjestu: što je model znao prije meča (snapshot), što je agent napisao
(pet odjeljaka, analiza, rizici), Nose i Intuicija, statistika meča poslije (poravnato po ID-u)
i analiza gubitka ako postoji (samo za mečeve koji su bili na listi tiketa, najviše 5 po večeri).
Statistika meča je OPIS, nikad dokaz da se moglo znati prije (PRAGOVI točka C).

Samo čita .cache/rev_2026-10-25/*. Izlaz: revizije/2026-10-25/KARTICE_GUBITAKA_2026-10-25.md
    python revizije/2026-10-25/skripte/r_kartice.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r_base import DUMP, ROOT, load, post_stats  # noqa: E402

OUT = os.path.join(ROOT, "revizije", "2026-10-25", "KARTICE_GUBITAKA_2026-10-25.md")


def pct(x, d=1):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100*float(x):.{d}f}%"


def num(x, d=0):
    if x is None:
        return "-"
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    return "-" if np.isnan(v) else f"{v:.{d}f}"


def ps(s, k):
    try:
        return float(s.get(k))
    except (TypeError, ValueError, AttributeError):
        return np.nan


def match_line(s, o):
    """Kratki opis statistike meča za igrača s (protiv o)."""
    if not s or not o:
        return None
    w1, w1o, w2, w2o = ps(s, "winningOnFirstServe"), ps(s, "winningOnFirstServeOf"), ps(s, "winningOnSecondServe"), ps(s, "winningOnSecondServeOf")
    ow1, ow1o, ow2, ow2o = ps(o, "winningOnFirstServe"), ps(o, "winningOnFirstServeOf"), ps(o, "winningOnSecondServe"), ps(o, "winningOnSecondServeOf")
    fs, fso = ps(s, "firstServe"), ps(s, "firstServeOf")
    sp, rp = w1o + w2o, ow1o + ow2o
    tp, otp = ps(s, "totalPointsWon"), ps(o, "totalPointsWon")
    return {
        "poeni": f"{num(tp)}–{num(otp)} ({pct(tp/(tp+otp) if tp+otp else np.nan)})",
        "servis": pct((w1 + w2) / sp if sp else np.nan),
        "povrat": pct(((ow1o - ow1) + (ow2o - ow2)) / rp if rp else np.nan),
        "1. servis u": pct(fs / fso if fso else np.nan),
        "1. servis osv.": pct(w1 / w1o if w1o else np.nan),
        "2. servis osv.": pct(w2 / w2o if w2o else np.nan),
        "asovi/DF": f"{num(ps(s, 'aces'))}/{num(ps(s, 'doubleFaults'))}",
        "BP spašeni": f"{num(ps(s, 'breakPointSavedGm'))}/{num(ps(s, 'breakPointFacedGm'))}",
        "BP iskorišteni": f"{num(ps(s, 'breakPointWonGm'))}/{num(ps(s, 'breakPointChanceGm'))}",
    }


def main():
    df = pd.read_pickle(os.path.join(DUMP, "all_points.pkl"))
    am = {r["id"]: r for r in load("analyzed_matches")}
    tm = load("ticket_matches")
    la = {}
    for t in tm:
        if t.get("loss_analysis") and str(t.get("match_date")) >= "2026-10-18":
            la.setdefault(frozenset([t["player1"], t["player2"]]), t["loss_analysis"])
    tj = df[df.tjedan & (df.win == 0)].sort_values(["date", "tournament"])
    lines = [
        "# Kartice gubitnih parova — Lyon, Bruxelles, Almaty (19.–25.10.2026)",
        "",
        "Nastalo 25.10.2026 skriptom `revizije/2026-10-25/skripte/r_kartice.py` (samo čita dump baze od",
        "25.10.2026 10:21). Za svaki poraz: prije meča → agent → Nose/Intuicija → statistika meča →",
        "analiza gubitka. **Statistika meča je opis, nije dokaz da se moglo znati prije meča.**",
        "Cijena = devigirana SuperSport kvota. \"Poeni\" = udio svih osvojenih poena našeg picka.",
        "",
    ]
    for k, (_, r) in enumerate(tj.iterrows(), 1):
        raw = am.get(r["id"]) or {}
        cs = raw.get("context_snapshot") or {}
        fa = raw.get("full_analysis") or {}
        is1 = r.pick == raw.get("player1")
        a, b = ("p1", "p2") if is1 else ("p2", "p1")
        ms = raw.get("match_stats") or {}
        sp_, so_ = post_stats(ms, r.pick_id), post_stats(ms, r.opp_id)
        lines.append(f"## {k}. {r.pick} (pick) – {r.opp} · {str(r.tournament).split('-')[-1].strip()} {r['round']} · {r.date:%d.%m.}")
        lines.append("")
        lines.append(f"- **Kvota / cijena:** {r.odds:.2f} (protivnik {r.odds_opp:.2f}) → cijena picka {pct(r.p_dev)}; "
                     f"pouzdanost {num(r.conf_raw)} → {num(r.conf)}{' (kazne: ' + r.penalties + ')' if r.penalties else ''}; "
                     f"{'**NOGA TIKETA** (na tiketu: kvota ' + num(r.leg_odds, 2) + ', pouzdanost ' + num(r.leg_conf) + ')' if r.on_ticket else 'nije na tiketu'}"
                     f"{'; rezultat ' + str(r.score) if isinstance(r.score, str) and r.score else ''}")
        lines.append(f"- **Klasa po poenima:** {r.klasa}" + (f" (ostatak poena {r.pts_resid:+.1f}pp naspram cijene)" if not pd.isna(r.pts_resid) else ""))
        lines.append("")
        lines.append("| prije meča | pick | protivnik |")
        lines.append("|---|---|---|")
        rows = [
            ("ELO podloga / ukupno", f"{num(r.elo_s_p)} / {num(r.elo_o_p)}", f"{num(r.elo_s_o)} / {num(r.elo_o_o)}"),
            ("rang", num(r.rank_p), num(r.rank_o)),
            ("forma 10 (W/L)", str(cs.get(f"{a}_form_10") or "-"), str(cs.get(f"{b}_form_10") or "-")),
            ("forma × kvaliteta / ELO protivnika (5)", f"{num(r.fq_p, 2)} / {num(r.aoe5_p)}", f"{num(r.fq_o, 2)} / {num(r.aoe5_o)}"),
            # RapidAPI vrijednosti su već u postocima (npr. 61.4), TML u udjelima (0.614)
            ("servis / povrat (RapidAPI, karijera)", f"{num(r.serve_p, 1)}% / {num(r.ret_p, 1)}%", f"{num(r.serve_o, 1)}% / {num(r.ret_o, 1)}%"),
            ("servis / povrat / hold (TML 12 mj.)", f"{pct(r.tml_s_p)} / {pct(r.tml_r_p)} / {pct(r.tml_hold_p)} (glavni ždrijeb {num(r.tml_nmain_p)})",
             f"{pct(r.tml_s_o)} / {pct(r.tml_r_o)} / {pct(r.tml_hold_o)} (glavni ždrijeb {num(r.tml_nmain_o)})"),
            ("omjer na podlozi (n)", f"{pct(r.srf_p)} ({num(r.srf_pn)})", f"{pct(r.srf_o)} ({num(r.srf_on)})"),
            ("na ovom turniru: mečeva / servis", f"{num(r.tf_n_p)} / {pct(r.tf_sv_p)}", f"{num(r.tf_n_o)} / {pct(r.tf_sv_o)}"),
            ("put kroz turnir", str(cs.get(f"{a}_tournament_path") or "-")[:80], str(cs.get(f"{b}_tournament_path") or "-")[:80]),
            ("odmor (dana) / setovi u 7 dana", f"{num(r.rest_p)} / {num(r.s7_p)}", f"{num(r.rest_o)} / {num(r.s7_o)}"),
            ("dob / visina", f"{num(r.age_p)} / {num(r.ht_p)}", f"{num(r.age_o)} / {num(r.ht_o)}"),
            ("najdalje ovdje (3 sez.) / prethodni turnir", f"{num(r.tbest_p)} / {r.prev_lvl_p or '-'}", f"{num(r.tbest_o)} / {r.prev_lvl_o or '-'}"),
            ("scouting pouzdanost", str(r.scout_p or "-"), str(r.scout_o or "-")),
            ("Google News: naslova / o ozljedi", f"{num(r.gn_n_p)} / {num(r.inj_p)}", f"{num(r.gn_n_o)} / {num(r.inj_o)}"),
        ]
        for lab, x, y in rows:
            lines.append(f"| {lab} | {x} | {y} |")
        h2h = cs.get("h2h") or cs.get("h2h_summary")
        if h2h:
            lines.append(f"\nH2H: {str(h2h)[:200]}")
        lines.append("")
        lines.append("**Agent (pet odjeljaka):**")
        for item in (fa.get("key_factors") or []):
            lines.append(f"- {str(item).strip()}")
        if fa.get("analysis"):
            lines.append(f"\n*Sažetak agenta:* {str(fa.get('analysis')).strip()}")
        if fa.get("risk_notes"):
            lines.append(f"\n*Rizici koje je agent naveo:* {str(fa.get('risk_notes')).strip()}")
        lines.append("")
        lines.append(f"**Nose:** {r.nose_suit} · vlastita {pct(r.nose_p_own)} naspram cijene {pct(r.p_dev)} "
                     f"({'' if pd.isna(r.nose_diff) else f'{r.nose_diff:+.1f}pp'}) · mine: {r.nose_mines or '-'} · autsajder: {r.nose_ups or '-'} · ulaz {r.nose_src}"
                     f" · **Intuicija:** prior {num(r.int_prior, 2)}pp, vlastiti sloj {'šuti' if r.int_silent else num(r.int_own, 2)}")
        lines.append("")
        ml_p, ml_o = match_line(sp_, so_), match_line(so_, sp_)
        if ml_p and ml_o:
            lines.append("| statistika meča (opis) | pick | protivnik |")
            lines.append("|---|---|---|")
            for key in ml_p:
                lines.append(f"| {key} | {ml_p[key]} | {ml_o[key]} |")
        else:
            lines.append("*Statistika meča: nema je u bazi.*")
        lines.append("")
        txt = la.get(frozenset([raw.get("player1"), raw.get("player2")]))
        if txt:
            sh = []
            for ln in txt.splitlines():
                l_ = ln.strip()
                if l_.startswith("**Factor") or l_.startswith("Worth measuring") or l_.startswith("**Worth measuring") \
                        or "No model change" in l_:
                    sh.append(l_)
            lines.append("**Analiza gubitka (sažeto — cijeli tekst u `.cache/rev_2026-10-25/loss_analyses_tjedan.txt`):**")
            for l_ in sh[:6]:
                lines.append(f"> {l_[:400]}")
        else:
            lines.append("**Analiza gubitka:** ne postoji (meč nije bio na listi za analizu gubitka ili je preskočen; večer analizira najviše 5).")
        lines.append("")
        lines.append("---")
        lines.append("")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("kartica:", len(tj), "->", OUT)


if __name__ == "__main__":
    main()
