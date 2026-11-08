# -*- coding: utf-8 -*-
"""Revizija 08.11.2026 — dopuna ranga iz TML-a za igrače bez snimke dnevnog runa od 26.10. (08.11.2026 12:11).

Pravilo: PRAGOVI_REVIZIJA_2026-11-08.md, točka J2 (NAKNADNO 08.11.2026 12:10). Igraču koji u prvom upisu
(`r_scouting.py --primijeni`, 11:56) nije dobio rang upisuje se zadnji TML rang (rang u trenutku zadnjeg
meča) ako je taj meč noviji od 18.10.2026. Promjene se DODAJU u promjene_2026-11-08.json (pa ih
`r_scouting_vrati.py` vraća zajedno s ostalima) i u list "Promjene 08.11.2026" u Excelu.

    python revizije/2026-11-08/skripte/r_scouting_rang_tml.py --tml=MAPA               # suho
    python revizije/2026-11-08/skripte/r_scouting_rang_tml.py --tml=MAPA --primijeni
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from r_scouting import OUTD, XLSX, db, norm  # noqa: E402

CHANGES = os.path.join(OUTD, "promjene_2026-11-08.json")
SINCE = "20261018"


def latest_ranks(folder):
    last = {}
    for name in ("2026.csv", "ongoing_tourneys.csv"):
        with open(os.path.join(folder, name), encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                for nm, rk in ((r["winner_name"], r["winner_rank"]), (r["loser_name"], r["loser_rank"])):
                    if not rk:
                        continue
                    k = norm(nm)
                    if k not in last or r["tourney_date"] >= last[k][0]:
                        last[k] = (r["tourney_date"], int(float(rk)), r["tourney_name"])
    return last


def main(apply=False, folder=None):
    data = json.load(open(CHANGES, encoding="utf-8"))
    done = {c["player_name"] for c in data["promjene"] if "rank" in c["new"]}
    # igrač sa snimkom od 26.10. ima rang iz dnevnog runa i kad se nije promijenio — TML ga ne prepisuje
    from r_scouting import recent_ranks
    seen = set(recent_ranks())
    live = db._select("player_scouting", select="player_name,display_name,rank", limit=400)
    last = latest_ranks(folder)
    new, stale = [], []
    for r in live:
        if r["player_name"] in done or norm(r["display_name"]) in seen or norm(r["player_name"]) in seen:
            continue
        t = last.get(norm(r["display_name"])) or last.get(norm(r["player_name"]))
        if t and t[0] > SINCE:
            if t[1] != r.get("rank"):
                new.append({"player_name": r["player_name"], "display_name": r["display_name"], "confidence": None,
                            "old": {"rank": r.get("rank")}, "new": {"rank": t[1]},
                            "reasons": [f"rang {r.get('rank')} -> {t[1]} (TML, zadnji meč {t[0][6:8]}.{t[0][4:6]}.{t[0][:4]}, {t[2]})"]})
        else:
            stale.append((r["display_name"], r.get("rank"), t[0] if t else None))
    print(f"dopuna iz TML-a: {len(new)} rangova; bez meča od 18.10. (rang ostaje star): {len(stale)}")
    for c in new:
        print(f"  {c['display_name']:28s} {c['reasons'][0]}")
    print("  stari rang ostaje:", ", ".join(f"{n} {rk} (zadnji meč {d or '-'})" for n, rk, d in sorted(stale, key=lambda x: x[1] or 999)[:25]))
    if not apply:
        print("(suho — za upis: --primijeni)")
        return
    ok = 0
    for c in new:
        res = db._update("player_scouting", c["new"], {"player_name": f"eq.{c['player_name']}"})
        ok += 1 if isinstance(res, list) and res else 0
    print(f"upisano u Supabase: {ok}/{len(new)}")
    data["promjene"] += new
    data["dopuna_J2"] = {"pravilo": "PRAGOVI J2 (NAKNADNO 08.11.2026 12:10)", "upisano": len(new),
                         "stari_rang": [{"igrac": n, "rang": rk, "zadnji_tml_mec": d} for n, rk, d in stale]}
    json.dump(data, open(CHANGES, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    # Excel: glavni list ponovno iz Supabasea, ostali listovi se čuvaju; nove promjene se dopisuju
    import openpyxl
    from openpyxl.styles import Alignment
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "scripts"))
    keep = openpyxl.load_workbook(XLSX)
    import export_scouting_excel as ex
    ex.main()
    wb = openpyxl.load_workbook(XLSX)
    from r_scouting import _copy_sheet
    for title in keep.sheetnames[1:]:
        _copy_sheet(keep[title], wb, title)
    ws = wb["Promjene 08.11.2026"]
    k = ws.max_row + 1
    for c in new:
        for col, v in enumerate([c["display_name"], "rank", c["old"]["rank"], c["new"]["rank"], c["reasons"][0]], 1):
            ws.cell(row=k, column=col, value=v).alignment = Alignment(vertical="top", wrap_text=True)
        k += 1
    for n, rk, d in stale:
        for col, v in enumerate([n, "rank", rk, rk, f"rang star: nema TML meča od 18.10.2026 (zadnji {d or '-'})"], 1):
            ws.cell(row=k, column=col, value=v).alignment = Alignment(vertical="top", wrap_text=True)
        k += 1
    wb.save(XLSX)
    print(f"Excel osvježen (listovi: {', '.join(wb.sheetnames)})")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    folder = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--tml=")), None)
    if not folder:
        sys.exit("treba --tml=MAPA")
    main(apply="--primijeni" in sys.argv, folder=folder)
