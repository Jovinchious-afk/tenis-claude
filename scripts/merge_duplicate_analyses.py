"""
Jednokratno spajanje DUPLIKATA u analyzed_matches (07.08.2026).

POVOD
-----
`stable_match_key` sadrži datum, a datum nije stabilan: mečeve dohvaćamo za danas+sutra
(+prekosutra), pa isti meč prvo vidimo pod provizornim datumom, a idući dan pod stvarnim —
API ga pomakne kad se raspored slegne ili kad padne kiša. Ključ se promijeni, upsert promaši
postojeći redak i nastane DRUGI zapis za isti meč.

Izmjereno prije popravka: 45 parova, 90 redaka = 22,6% korpusa; kod 44 od 45 su OBA retka
razriješena ISTIM pobjednikom (winner lookup traži po imenima, bez datuma), pa je kalibracija
te mečeve brojala dvaput. Montreal: 82 "razriješena" retka = zapravo 62 meča; cap_enforced
11W-1L (P=0,034) = zapravo 8W-1L (P=0,104).

Ubuduće to sprječava `supabase_client.find_existing_analysis` (±3 dana). Ova skripta čisti
ono što je već upisano.

PRAVILO ZADRŽAVANJA
-------------------
Zadržava se BOGATIJI redak (rezultat > statistika > player ID-evi > viši context_version >
predikcija). Polja koja mu nedostaju prepišu se iz onog drugog, pa se drugi obriše —
dakle spajanje, ne odbacivanje. `match_date` se postavlja na NOVIJI datum jer je to datum
kad je meč stvarno odigran, a na njega vežemo vrijeme i vremenske uvjete.

SIGURNOST
---------
Prije ijednog brisanja svi zahvaćeni redci spremaju se u JSON (--backup putanja).
Bez `--apply` skripta samo ISPISUJE što bi napravila.

Pokretanje:
    python scripts/merge_duplicate_analyses.py                 # suho, samo ispis
    python scripts/merge_duplicate_analyses.py --apply         # stvarno spaja
"""
import sys
import os
import json
import argparse
import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from database import supabase_client as db

WINDOW_DAYS = 3

# Polja koja se pri spajanju smiju prepisati iz "gubitnika" ako ih pobjednik nema.
MERGEABLE = [
    "actual_winner", "prediction_correct", "match_stats", "player1_id", "player2_id",
    "predicted_winner", "predicted_confidence", "predicted_fair_odds",
    "bookmaker_odds_p1", "bookmaker_odds_p2", "value_detected", "full_analysis",
    "context_snapshot", "tournament_level", "surface", "round",
]


def _pairkey(row: dict) -> tuple:
    a = db._norm_player_key(row.get("player1"))
    b = db._norm_player_key(row.get("player2"))
    t = " ".join(str(row.get("tournament") or "").lower().split())
    return (t, *sorted([a, b]))


def _richness(row: dict) -> tuple:
    """Što veće, to bolje. Redoslijed prioriteta je namjeran: ishod je najvrjedniji jer
    bez njega redak ne sudjeluje u kalibraciji."""
    cs = row.get("context_snapshot") or {}
    return (
        1 if row.get("actual_winner") else 0,
        1 if row.get("match_stats") else 0,
        1 if (row.get("player1_id") and row.get("player2_id")) else 0,
        int(cs.get("context_version") or 0),
        1 if row.get("predicted_winner") else 0,
        1 if row.get("full_analysis") else 0,
        str(row.get("created_at") or ""),
    )


def _within_window(rows: list) -> bool:
    ds = []
    for r in rows:
        try:
            ds.append(datetime.date.fromisoformat(str(r.get("match_date"))[:10]))
        except (ValueError, TypeError):
            return False
    return bool(ds) and (max(ds) - min(ds)).days <= WINDOW_DAYS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="stvarno spoji (bez toga samo ispis)")
    ap.add_argument("--backup", default=None, help="putanja JSON sigurnosne kopije")
    args = ap.parse_args()

    rows = db._select("analyzed_matches", select="*", filters={})
    print(f"analyzed_matches: {len(rows)} redaka")

    groups = defaultdict(list)
    for r in rows:
        groups[_pairkey(r)].append(r)
    dups = {k: v for k, v in groups.items() if len(v) > 1}

    todo, skipped = [], []
    for k, v in dups.items():
        (todo if _within_window(v) else skipped).append((k, v))

    print(f"duplikata ukupno: {len(dups)}")
    print(f"  unutar {WINDOW_DAYS} dana (spajam):     {len(todo)}")
    print(f"  izvan prozora (NE diram):          {len(skipped)}")
    for k, v in skipped:
        print(f"    ! {k[0][:40]} {k[1]}/{k[2]} -> {[x.get('match_date') for x in v]}")

    if not todo:
        print("Nema što spojiti.")
        return 0

    backup_path = args.backup or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        f"merge_backup_{datetime.date.today().isoformat()}.json")
    backup_path = os.path.abspath(backup_path)

    plan = []
    for k, v in todo:
        ordered = sorted(v, key=_richness, reverse=True)
        keep, drop = ordered[0], ordered[1:]
        patch = {}
        for f in MERGEABLE:
            if keep.get(f) in (None, "", {}, []):
                for d in drop:
                    if d.get(f) not in (None, "", {}, []):
                        patch[f] = d[f]
                        break
        newest = max(str(x.get("match_date") or "")[:10] for x in v)
        if str(keep.get("match_date") or "")[:10] != newest:
            patch["match_date"] = newest
        plan.append({"keep": keep, "drop": drop, "patch": patch})

    print(f"\nzadrzavam {len(plan)} redaka, brisem {sum(len(p['drop']) for p in plan)}")
    n_patched = sum(1 for p in plan if p["patch"])
    print(f"od zadrzanih, {n_patched} dobiva polja iz obrisanog blizanca")

    print("\nprvih 10:")
    for p in plan[:10]:
        k, d = p["keep"], p["drop"][0]
        print(f"  {k.get('player1')[:20]:20s} vs {k.get('player2')[:20]:20s}")
        print(f"      KEEP  {k.get('match_date')} win={str(k.get('actual_winner'))[:18]:18s} "
              f"stats={'DA' if k.get('match_stats') else '-'} cs="
              f"{(k.get('context_snapshot') or {}).get('context_version')}")
        print(f"      DROP  {d.get('match_date')} win={str(d.get('actual_winner'))[:18]:18s} "
              f"stats={'DA' if d.get('match_stats') else '-'} cs="
              f"{(d.get('context_snapshot') or {}).get('context_version')}")
        if p["patch"]:
            print(f"      PATCH {list(p['patch'].keys())}")

    if not args.apply:
        print("\n--- SUHO POKRETANJE. Za stvarno spajanje dodaj --apply ---")
        return 0

    # Sigurnosna kopija SVIH zahvacenih redaka prije ijedne izmjene.
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump([{"keep": p["keep"], "drop": p["drop"], "patch": p["patch"]} for p in plan],
                  f, ensure_ascii=False, indent=2, default=str)
    print(f"\nSigurnosna kopija: {backup_path}")

    n_upd, n_del, n_err = 0, 0, 0
    for p in plan:
        keep, drop, patch = p["keep"], p["drop"], p["patch"]
        try:
            if patch:
                db._update("analyzed_matches", patch, {"id": f"eq.{keep['id']}"})
                n_upd += 1
            for d in drop:
                db._rest("DELETE", "analyzed_matches", params={"id": f"eq.{d['id']}"})
                n_del += 1
        except Exception as e:
            n_err += 1
            print(f"  GRESKA na {keep.get('player1')} vs {keep.get('player2')}: {str(e)[:120]}")

    print(f"\nGotovo: dopunjeno {n_upd}, obrisano {n_del}, gresaka {n_err}")
    after = db._select("analyzed_matches", select="id", filters={})
    print(f"analyzed_matches sada: {len(after)} redaka (bilo {len(rows)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
