# -*- coding: utf-8 -*-
"""Prilog reviziji 26.09.2026 — Excel sa svim gubicima, dobicima, auditom analiza gubitaka,
procjenom pravila, ekranom varijabli, interakcijama i prijedlogom za scouting."""
import os, json, numpy as np, pandas as pd

OUT = r"C:\Users\jovin\Desktop\Tenis Claude\revizije\2026-09-26"
os.makedirs(OUT, exist_ok=True)
j = pd.read_pickle("classified_idea3.pkl")
j = j[j.win.notna()].copy()


def flags_str(z):
    return ", ".join(z) if isinstance(z, list) else ""


def removed_by(r):
    out = []
    if not pd.isna(r.odds) and 1.35 <= r.odds < 1.60: out.append("R1 rupa 1,35-1,60")
    if not pd.isna(r.p_dev) and r.p_dev < 0.5: out.append("R2 autsajder")
    if r["round"] in ("R16", "QF"): out.append("R3 R16/QF")
    if r.level == "ATP 250" and r.surface == "hard": out.append("R4 hard ATP 250")
    if r.scout_p == "High": out.append("K17 High profil")
    return ", ".join(out)


j["uklonio_bi"] = j.apply(removed_by, axis=1)
j["zastavice_s"] = j.zastavice.apply(flags_str)
base_cols = dict(date="datum", tournament="turnir", level="razina", surface="podloga", round="runda", pick="nas_pick",
                 opp="protivnik", odds="kvota", p_dev="trziste_devig", conf="nasa_pouzdanost", uzrok="klasifikacija",
                 zastavice_s="zastavice", pm_tp_share="udio_poena_picka", pm_result="rezultat_(pobjednik_prvi)",
                 pm_rtype="zavrsetak", uklonio_bi="koje_bi_pravilo_ga_izbacilo", risk_notes="rizici_prije_meca",
                 era="era_modela")
L = j[j.win == 0][list(base_cols)].rename(columns=base_cols).sort_values("datum")
W = j[j.win == 1][list(base_cols)].rename(columns=base_cols).sort_values("datum")
for d in (L, W):
    d["datum"] = d["datum"].dt.date
    d["trziste_devig"] = (100 * d["trziste_devig"]).round(1)
    d["udio_poena_picka"] = (100 * d["udio_poena_picka"]).round(1)

audit = pd.DataFrame([
    ("01.09.", "Basavareddy @1,32", "R64 (US Open 2. kolo)", "tvrdi 'cetvrto kolo = R16' i primjenjuje R16/QF rupu", "KRIVA RUNDA", "[CONFIRMED] na krivoj premisi; TB tvrdnja na zastarjeloj baznoj stopi"),
    ("02.09.", "Rublev @1,55/1,60", "R64", "primjenjuje R16/QF -13,3pp", "KRIVA RUNDA", "[CONFIRMED] na krivoj premisi; godina 'US Open 2025' kriva"),
    ("02.09.", "Berrettini @1,50", "R64", "'drugo kolo gdje je ELO najslabiji' (obrnuto od mjerenja)", "KRIVA RUNDA + krivo citanje", "[CONTRADICTED] na krivoj premisi"),
    ("02.09.", "Duckworth @2,20", "R32", "ispravno kaze da R16/QF ne vrijedi; 'nema promjene'", "OK", "jedna od rijetkih bez greske"),
    ("03.09.", "Buse @1,70", "R64", "TB [CONTRADICTED] po zastarjeloj stopi; forma [CONFIRMED]", "DJELOMICNO", "forma x kvaliteta nije prosla na novim podacima (r=+0,02)"),
    ("03.09.", "Auger-Aliassime @1,35", "R64", "izmislja 'R32 granicu na kojoj ELO slabi'", "IZMISLJEN GRADIJENT", "zakljucak 'nema promjene' ipak ispravan"),
    ("05.09.", "Zheng @1,65", "R32 (3. kolo GS)", "'trece kolo spada u R16/QF slabu tocku'", "KRIVA RUNDA", "predlaze tvrdo pravilo na krivoj premisi"),
    ("05.09.", "Lehecka @1,60", "R32", "'R16/QF-tier susret'", "KRIVA RUNDA", ""),
    ("05.09.", "Cobolli @1,90 (x2)", "R32", "ispravno: R16/QF ne vrijedi", "OK", "TB po zastarjeloj stopi"),
    ("05.09.", "Fritz @1,12", "R32", "'QF-equivalent late round'", "KRIVA RUNDA", "predlaze smanjenje ELO u kasnim rundama na krivoj premisi"),
    ("06.09.", "Medvedev @1,60", "R16", "pojas izveden iz POUZDANOSTI ('61-66% -> kvote 1,43-1,65')", "KRIVA KVOTA (rub)", "stvarna kvota 1,60 je na rubu rupe"),
    ("07.09.", "Tien @1,60", "QF", "rupa primijenjena na kvotu PROTIVNIKA", "KRIVA LOGIKA", "[CONFIRMED] + prijedlog -5pp"),
    ("07.09.", "Gea @2,25", "R16", "'implicirana 1,75, trziste 1,44 -> rupa'", "KRIVA KVOTA", "pick @2,25 nije u rupi"),
    ("07.09.", "F. Cerundolo @2,30", "R16", "rupa primijenjena na kvotu protivnika (Blockx)", "KRIVA KVOTA", ""),
    ("08./09.09.", "Alcaraz @1,24 (x2)", "SF", "'72% -> kvota ~1,39 -> rupa 1,35-1,43' / '1,43-1,60'", "KRIVA KVOTA", "stvarna 1,24 = nas NAJBOLJI pojas; runda nazvana QF"),
    ("09.09.", "Blockx @2,35", "SF", "'pick u zoni 1,43-1,60'", "KRIVA KVOTA + propustena PREDAJA", "Blockx predao (3-2 ret.) — ozljeda se ne spominje"),
    ("19.09.", "Tabilo @1,75 (DC)", "DC", "iskreno: 'cijena nije dana, INSUFFICIENT DATA'", "OK", "potvrda da prompt NE dobiva kvotu"),
    ("19.09.", "Tien @1,85 (DC)", "DC", "'~1,43-1,60 zbog izjednacenog trzista -> rupa'", "KRIVA KVOTA", ""),
    ("24.09.", "Shimabukuro @2,00", "(ociscena)", "'pick u rupi 1,43-1,60'", "KRIVA KVOTA", "pick je bio trzisni autsajder — to se ne spominje"),
    ("25.09.", "Sonego @2,10", "(ociscena)", "'kazna za autsajdera se primijenila', 'nije izdan na tiket', 'ispod praga 63'", "TRI NETOCNE TVRDNJE",
     "kazna NIJE okinula (nema konsenzusa za Chengdu), pick JE bio na pravom tiketu 24.09., prag je 60 od 08.09."),
], columns=["datum", "pick", "stvarna_runda", "sto_analiza_tvrdi", "ocjena", "napomena"])

rules = pd.read_csv("out_rules.csv")
vars2 = pd.read_csv("out_vars2_hard.csv")
inter = pd.read_csv("out_interactions.csv").head(40)
sim = pd.read_csv("out_ticketsim.csv")
scp = pd.read_pickle("scouting_proposal.pkl")

path = os.path.join(OUT, "Revizija_2026-09-26_prilog.xlsx")
with pd.ExcelWriter(path, engine="openpyxl") as xw:
    L.to_excel(xw, sheet_name="Gubici", index=False)
    W.to_excel(xw, sheet_name="Dobici", index=False)
    audit.to_excel(xw, sheet_name="Audit_analiza_gubitaka", index=False)
    rules.to_excel(xw, sheet_name="Pravila_procjena", index=False)
    vars2.to_excel(xw, sheet_name="Varijable_hard", index=False)
    inter.to_excel(xw, sheet_name="Interakcije_top40", index=False)
    sim.to_excel(xw, sheet_name="Simulacija_tiketa", index=False)
    scp.to_excel(xw, sheet_name="Scouting_prijedlog", index=False)
# siroka stupcasta sirina radi citljivosti
import openpyxl
wb = openpyxl.load_workbook(path)
for ws in wb.worksheets:
    for col in ws.columns:
        width = min(60, max(10, max(len(str(c.value or "")) for c in col[:60]) + 2))
        ws.column_dimensions[col[0].column_letter].width = width
    ws.freeze_panes = "A2"
wb.save(path)
print("spremljeno:", path, "| gubitaka", len(L), "dobitaka", len(W))
