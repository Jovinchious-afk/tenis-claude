# -*- coding: utf-8 -*-
"""Čišćenje zastarjelih duplikata u `elo_cache` (04.10.2026 19:13, korisnik odobrio popravak ELO-a).

Problem: 546 imena postoji dvaput — stari zapis s neprekidnim razmakom (NBSP, upisan prije
popravka 08.09.) i novi s običnim razmakom. Briše se SAMO stari NBSP zapis, i to samo kad
postoji novi zapis istog (normaliziranog) imena. Zapisi bez para ostaju.

Prije brisanja cijela tablica se sprema u .cache/rev_2026-10-04/elo_cache_backup_2026-10-04.json
(vraćanje: upsert tih redaka natrag).

    python r_elo_cleanup.py            # samo ispis (ništa ne mijenja)
    python r_elo_cleanup.py --apply    # sigurnosna kopija + brisanje
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(ROOT, ".env"))
from database import supabase_client as db  # noqa: E402

BACKUP = os.path.join(ROOT, ".cache", "rev_2026-10-04", "elo_cache_backup_2026-10-04.json")


def norm(s):
    return " ".join(str(s or "").replace("\xa0", " ").lower().split())


def fetch_all():
    rows, off = [], 0
    while True:
        ch = db._rest("GET", "elo_cache", params={"select": "*", "order": "player_name.asc",
                                                  "offset": str(off), "limit": "1000"})
        rows += ch
        if len(ch) < 1000:
            break
        off += 1000
    return rows


def main():
    apply = "--apply" in sys.argv
    rows = fetch_all()
    by = {}
    for r in rows:
        by.setdefault(norm(r["player_name"]), []).append(r)
    stale = []
    for k, rs in by.items():
        clean = [r for r in rs if "\xa0" not in r["player_name"]]
        dirty = [r for r in rs if "\xa0" in r["player_name"]]
        if clean and dirty:
            stale.extend(dirty)
    lone_dirty = sum(1 for rs in by.values() if all("\xa0" in r["player_name"] for r in rs))
    print(f"redaka: {len(rows)} | imena: {len(by)} | za brisanje (stari NBSP uz noviji par): {len(stale)} "
          f"| NBSP bez para (ostaju): {lone_dirty}")
    newer = sum(1 for r in stale if str(r.get("updated_at")) < max(str(x.get("updated_at")) for x in by[norm(r["player_name"])]))
    print(f"od zapisa za brisanje STARIJI od para: {newer} od {len(stale)}")
    if not apply:
        print("samo ispis — za brisanje pokreni s --apply")
        return
    with open(BACKUP, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)
    print(f"sigurnosna kopija: {BACKUP} ({len(rows)} redaka)")
    deleted = 0
    for r in stale:
        out = db._rest("DELETE", "elo_cache", params={"player_name": f"eq.{r['player_name']}"},
                       prefer="return=representation")
        deleted += len(out)
    after = fetch_all()
    print(f"obrisano: {deleted} | redaka sada: {len(after)} | NBSP zapisa sada: "
          f"{sum(1 for r in after if chr(160) in r['player_name'])}")


if __name__ == "__main__":
    main()
