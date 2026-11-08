# -*- coding: utf-8 -*-
"""Povratak scouting izmjena od 08.11.2026 (08.11.2026 11:56).

Vraća polja rank/style/strengths/weaknesses iz kopije revizije/2026-11-08/scouting/
player_scouting_prije_2026-11-08.json za igrače iz promjene_2026-11-08.json, i Excel iz kopije.

    python revizije/2026-11-08/skripte/r_scouting_vrati.py            # suho: što bi se vratilo
    python revizije/2026-11-08/skripte/r_scouting_vrati.py --vrati    # upis
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(ROOT, ".env"))
from database import supabase_client as db  # noqa: E402

OUTD = os.path.join(ROOT, "revizije", "2026-11-08", "scouting")
BACKUP = os.path.join(OUTD, "player_scouting_prije_2026-11-08.json")
CHANGES = os.path.join(OUTD, "promjene_2026-11-08.json")
XLSX = os.path.join(ROOT, "ATP_Player_Scouting top150.xlsx")
XLSX_BACKUP = os.path.join(OUTD, "ATP_Player_Scouting_top150_prije_2026-11-08.xlsx")


def main(apply=False):
    old = {r["player_name"]: r for r in json.load(open(BACKUP, encoding="utf-8"))}
    ch = json.load(open(CHANGES, encoding="utf-8"))["promjene"]
    ok = 0
    for c in ch:
        nm = c["player_name"]
        back = {f: old[nm].get(f) for f in c["new"]}
        print(f"{c['display_name']}: {back}")
        if apply:
            res = db._update("player_scouting", back, {"player_name": f"eq.{nm}"})
            ok += 1 if isinstance(res, list) and res else 0
    if apply:
        shutil.copy2(XLSX_BACKUP, XLSX)
        print(f"vraćeno u Supabase: {ok}/{len(ch)}; Excel vraćen iz kopije")
    else:
        print("(suho — za upis: --vrati)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(apply="--vrati" in sys.argv)
