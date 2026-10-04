# -*- coding: utf-8 -*-
"""Prilog reviziji 04.10.2026 — Excel meč po meč (04.10.2026 18:15).

Listovi: NOVO_mecevi (57 pickova s klasifikacijom iz poena), Analize_gubitaka (8 nogu, provjera),
Lab_varijable (C/D naspram tržišta), Korpus_varijable (F), ELO_kvar (pogođene analize).
Čita .cache/rev_2026-10-04/*.pkl i lab_r.json (rezultate skripti r_*.py).
"""
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r_base import DUMP  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Revizija_2026-10-04_prilog.xlsx")


def main():
    df = pd.read_pickle(os.path.join(DUMP, "all_vars.pkl"))
    nv = df[df["sample"] == "NOVO"].copy()
    cols = {"date": "datum", "tournament": "turnir", "round": "runda", "session": "sesija", "pick": "naš_pick",
            "opp": "protivnik", "odds": "kvota_SS", "p_dev": "tržište_devig_%", "conf": "pouzdanost",
            "conf_raw": "pouzdanost_prije_kazni", "penalties": "kazne", "win": "pogodak",
            "pm_tp_share": "udio_poena_%", "exp_share": "očekivani_udio_%", "pts_resid": "ostatak_poena_pp",
            "klasa": "klasifikacija", "on_ticket": "na_tiketu", "elo_s_p": "ELO_pick", "elo_s_o": "ELO_protivnik",
            "rank_p": "rang_pick", "rank_o": "rang_protivnik", "s7_p": "setovi7d_pick", "s7_o": "setovi7d_protivnik",
            "scout_p": "profil_pick", "scout_o": "profil_protivnik", "own_read": "own_read_modela",
            "risk_notes": "rizici_prije_meča"}
    t = nv[list(cols)].rename(columns=cols).sort_values("datum")
    t["datum"] = t["datum"].dt.date
    t["tržište_devig_%"] = (100 * t["tržište_devig_%"]).round(1)
    t["udio_poena_%"] = (100 * t["udio_poena_%"]).round(1)
    t["očekivani_udio_%"] = (100 * t["očekivani_udio_%"]).round(1)
    t["ostatak_poena_pp"] = t["ostatak_poena_pp"].round(1)
    t["pogodak"] = t["pogodak"].map({1.0: "W", 0.0: "L"})
    t["napomena"] = ""
    t.loc[(t["protivnik"] == "Jaume Antoni Munar Clar") | (t["naš_pick"] == "Jaume Antoni Munar Clar"), "napomena"] = \
        "KRIVI ELO: Munar je dobio ELO Jaya Clarkea (1397 umjesto 1748)"

    audit = pd.DataFrame([
        ("27.09.", "Marozsan @1,80", "QF Hangzhou", "kvota, runda, tiket točni", "OK",
         "R16/QF i pojas cijene ispravno označeni kao NOT CONFIRMED"),
        ("29.09.", "Hurkacz @1,65", "F Chengdu", "kvota, runda, tiket točni", "OK", "dobro vidi da je pick išao protiv vlastitih signala"),
        ("30.09.", "Cobolli @1,80", "R32 Peking", "kvota, runda, tiket točni", "OK", ""),
        ("01.10.", "Cobolli @1,90", "R32 Peking", "BP brojke zamijenjene ('Cobolli 0 od 11'; točno 0 od 5)", "SITNA GREŠKA", "isti meč na dva tiketa"),
        ("01.10.", "Fritz @1,30", "R32 Tokio", "Tokio nazvan 'ATP 250' (Tokio je ATP 500) -> primijenjena kriva bazna stopa", "KRIVA RAZINA",
         "prompt analize gubitka ne dobiva razinu turnira; Munarov ELO bio kriv (to analiza ne zna)"),
        ("03.10.", "Berrettini @1,50", "R16 Tokio", "kvota, runda, tiket točni", "KRIVA OCJENA",
         "pojas 1,43-1,60 i R16 proglašeni [SIGNAL CONFIRMED] — nijedno nije potvrđeno"),
        ("04.10.", "Fils @1,26", "QF Tokio", "datum naslova kriv (02.10.)", "KRIVA OCJENA",
         "R16/QF [SIGNAL CONFIRMED] + prijedlog novog filtra za QF"),
        ("04.10.", "Khachanov @1,65", "QF Peking", "datum kriv (03.10.)", "KRIVA OCJENA",
         "R16/QF [SIGNAL CONFIRMED] + prijedlog praga 65 za R16/QF; K11 je danas -1,5pp (n=31)"),
    ], columns=["datum", "noga", "runda", "činjenice", "ocjena", "napomena"])

    lab = json.load(open(os.path.join(DUMP, "lab_r.json"), encoding="utf-8"))
    lr = []
    for name, r in lab.items():
        a = r["all"]
        lr.append((name, "+" if r["sign"] > 0 else "-", a.get("n"), round(a.get("edge", float("nan")), 2),
                   round(a.get("lo", float("nan")), 2), round(a.get("hi", float("nan")), 2),
                   round(r["P1"].get("edge", float("nan")), 2), round(r["P2"].get("edge", float("nan")), 2),
                   round(r["holm"], 2), r["verdict"]))
    lab_df = pd.DataFrame(lr, columns=["test", "smjer", "n", "edge_pp", "CI_donja", "CI_gornja", "P1_2022-23",
                                       "P2_2024-26", "Holm_P", "presuda"])

    elo = pd.DataFrame([
        ("Jaume Antoni Munar Clar", "jay clarke (korak 2: 'clar' u 'clarke'; od 04.10. korak 3: prvo slovo imena)", "1421 / 1397", "1767 / 1748",
         "10 analiza; svih 7 riješenih pickova PROTIV Munara: 2-5"),
        ("(svi s dvije verzije imena)", "stari zapis s NBSP (29.08.) dolazi prvi", "stara vrijednost", "nova (04.10.)",
         "stari zapis se vraća za 535 od 546 (vrijednost se razlikuje u 448); osvježavanje ne djeluje"),
        ("(tablica elo_cache)", "get_elo_cache() vraća 1.000 od 1.138 redaka", "—", "—",
         "138 najnovijih redaka (04.10.) se ne čita"),
    ], columns=["igrač", "što lookup pogodi", "ELO u analizi (ukupni / hard)", "pravi ELO", "posljedica"])

    with pd.ExcelWriter(OUT, engine="openpyxl") as w:
        t.to_excel(w, sheet_name="NOVO_mecevi", index=False)
        audit.to_excel(w, sheet_name="Analize_gubitaka", index=False)
        lab_df.to_excel(w, sheet_name="Lab_varijable", index=False)
        elo.to_excel(w, sheet_name="ELO_kvar", index=False)
        for ws in w.book.worksheets:
            ws.freeze_panes = "A2"
            for col in ws.columns:
                width = min(60, max(10, max(len(str(c.value or "")) for c in col[:60]) + 2))
                ws.column_dimensions[col[0].column_letter].width = width
    print("zapisano:", OUT)


if __name__ == "__main__":
    main()
