# -*- coding: utf-8 -*-
"""
Uvoz scouting profila iz "ATP_Player_Scouting top100.xlsx" u Supabase tablicu player_scouting.

Pokretanje (iz roota projekta):
    python scripts/import_scouting.py --dry-run     # samo parsiraj i ispiši, bez upisa u bazu
    python scripts/import_scouting.py               # parsiraj + upsert u Supabase

Održavanje (npr. za 3 mjeseca): ažuriraj Excel (isti nazivi stupaca, isti format redaka),
snimi ga pod ISTIM imenom u root projekta, pa pokreni ovu skriptu bez --dry-run.
Upsert po player_name znači: postojeći igrači se ažuriraju, novi dodaju — ništa se ne briše
(igrača koji je ispao iz top 100 možeš ostaviti; njegov zapis samo stari preko source_date).

Legenda/napomene redovi na dnu Excela (bez broja u Rank stupcu) automatski se preskaču.
"""
import sys
import os
import io
import argparse
import datetime
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl

# Od 31.07.2026 tablica pokriva top 150 (prije top 100). Stari top100 file je namjerno
# ostavljen u folderu kao zapis polaznog stanja, ali se vise ne cita — uredjuj top150.
XLSX_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "ATP_Player_Scouting top150.xlsx")
SHEET = "ATP Player Scouting"

# Stupci po indeksu (0-based) — redoslijed iz Excela:
# Rank | Player | Country | Hand/BH | Style | Best surfaces | Strengths | Weaknesses
# | Favourable matchups | Tough matchups | Catchy note | Confidence
_VALID_CONFIDENCE = {"High", "Med-High", "Med", "Med-Low", "Low", "Insufficient"}


def _norm_name(s: str) -> str:
    """Ista normalizacija kao drugdje u projektu: bez dijakritika, lowercase, single-space."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().strip().split())


def parse_excel(path: str = XLSX_PATH) -> list:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[SHEET]
    rows = list(ws.iter_rows(values_only=True))
    players = []
    skipped = 0
    for r in rows[1:]:
        # Igrački red = Rank je cijeli broj; legenda/napomene/prazni redovi se preskaču
        try:
            rank = int(str(r[0]).strip())
        except (ValueError, TypeError, AttributeError):
            skipped += 1
            continue
        name = str(r[1] or "").strip()
        if not name:
            skipped += 1
            continue
        conf = str(r[11] or "").strip()
        if conf not in _VALID_CONFIDENCE:
            print(f"  UPOZORENJE: #{rank} {name} ima neočekivan confidence '{conf}' — spremam kako jest.")
        players.append({
            "player_name": _norm_name(name),
            "display_name": name,
            "rank": rank,
            "country": str(r[2] or "").strip(),
            "hand": str(r[3] or "").strip(),
            "style": str(r[4] or "").strip(),
            "best_surfaces": str(r[5] or "").strip(),
            "strengths": str(r[6] or "").strip(),
            "weaknesses": str(r[7] or "").strip(),
            "favourable_matchups": str(r[8] or "").strip(),
            "tough_matchups": str(r[9] or "").strip(),
            "note": str(r[10] or "").strip(),
            "confidence": conf,
        })
    return players


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="samo parsiraj, bez upisa u Supabase")
    ap.add_argument("--source-date", default=datetime.date.today().isoformat(),
                    help="datum snapshota podataka (YYYY-MM-DD); default danas")
    args = ap.parse_args()

    print(f"Čitam: {XLSX_PATH}")
    players = parse_excel()
    print(f"Parsirano igrača: {len(players)}")

    from collections import Counter
    conf_dist = Counter(p["confidence"] for p in players)
    print("Distribucija pouzdanosti:", dict(conf_dist.most_common()))
    dupes = [k for k, v in Counter(p["player_name"] for p in players).items() if v > 1]
    if dupes:
        print(f"  UPOZORENJE: duplikati imena (zadnji pobjeđuje pri upsertu): {dupes}")

    if args.dry_run:
        print("\n[DRY RUN] Prva 3 zapisa koja bi se upisala:")
        for p in players[:3]:
            print(f"  {p['rank']:>3}. {p['display_name']} ({p['confidence']}) — key='{p['player_name']}'")
        print("[DRY RUN] Ništa nije upisano u bazu.")
        return

    for p in players:
        p["source_date"] = args.source_date
        p["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    from database.supabase_client import _rest
    saved = 0
    for i in range(0, len(players), 50):
        batch = players[i:i + 50]
        result = _rest("POST", "player_scouting", body=batch,
                       prefer="return=representation,resolution=merge-duplicates",
                       params={"on_conflict": "player_name"})
        saved += len(result)
    print(f"Upsertano u Supabase: {saved}/{len(players)} zapisa (source_date={args.source_date}).")
    if saved == 0:
        print("NAPOMENA: 0 upisano — najvjerojatnije tablica player_scouting još ne postoji "
              "u Supabase (pokreni CREATE TABLE iz database/schema.sql u SQL Editoru pa ponovi).")


if __name__ == "__main__":
    # UTF-8 stdout samo pri direktnom pokretanju (ne pri importu — testovi imaju svoj wrapper)
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
