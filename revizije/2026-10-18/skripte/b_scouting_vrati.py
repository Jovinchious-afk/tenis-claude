# -*- coding: utf-8 -*-
"""Povratak scouting tablice na stanje PRIJE 18.10.2026 (18.10.2026 12:52).

Vraća SVA polja svih redaka iz `revizije/2026-10-18/scouting/player_scouting_prije_2026-10-18.json`
(snimljeno neposredno prije upisa skriptom `b_scouting.py --primijeni`) i stari Excel.
    python revizije/2026-10-18/skripte/b_scouting_vrati.py            # suho: koliko bi se vratilo
    python revizije/2026-10-18/skripte/b_scouting_vrati.py --vrati    # stvarni povratak
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

OUTD = os.path.join(ROOT, "revizije", "2026-10-18", "scouting")
SKIP = {"updated_at"}

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    rows = json.load(open(os.path.join(OUTD, "player_scouting_prije_2026-10-18.json"), encoding="utf-8"))
    chg = json.load(open(os.path.join(OUTD, "promjene_2026-10-18.json"), encoding="utf-8"))["promjene"]
    names = {c["player_name"] for c in chg}
    todo = [r for r in rows if r["player_name"] in names]
    print(f"kopija: {len(rows)} redaka; mijenjanih 18.10.: {len(todo)}")
    if "--vrati" not in sys.argv:
        print("(suho — za povratak: --vrati)")
        sys.exit(0)
    ok = 0
    for r in todo:
        body = {k: v for k, v in r.items() if k not in SKIP and k != "player_name"}
        res = db._update("player_scouting", body, {"player_name": f"eq.{r['player_name']}"})
        ok += 1 if isinstance(res, list) and res else 0
    shutil.copy2(os.path.join(OUTD, "ATP_Player_Scouting_top150_prije_2026-10-18.xlsx"),
                 os.path.join(ROOT, "ATP_Player_Scouting top150.xlsx"))
    print(f"vraćeno u Supabase: {ok}/{len(todo)}; Excel vraćen.")
