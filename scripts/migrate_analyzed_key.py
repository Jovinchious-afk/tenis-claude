# -*- coding: utf-8 -*-
"""Jednokratna migracija (31.07.2026): stabilan ključ za analyzed_matches + čišćenje.

POVOD: API-jev fixture `id` NIJE stabilan — s vremenom se prenamjenjuje drugom meču.
Kako se koristio kao on_conflict ključ pri upsertu, reciklirani ID bi prepisao imena
igrača i predikciju NOVIM mečem, dok bi actual_winner/prediction_correct ostali od
STAROG meča. Posljedica: 55/78 hard analiza nosilo je pobjednika s clay turnira
(npr. "Kamil Majchrzak vs Tommy Paul" -> actual_winner "Quentin Halys"), pa je
kalibracijska tablica za hard bila ~70% neispravna, a auto-feedback je iz nje učio.

Skripta radi tri stvari:
  1. BRIŠE retke gdje actual_winner nije nijedan od dvojice igrača (nepopravljivi).
  2. Prepisuje external_match_id u stabilan oblik "datum|igrac_a|igrac_b" (sortirano).
     Kod kolizije (isti meč upisan pod dva stara ID-a) zadržava red s ishodom, ostale briše.
  3. Ispisuje stanje kalibracijskog korpusa prije i poslije.

Pokretanje:  python scripts/migrate_analyzed_key.py [--dry-run]
"""
import sys
import os
import io
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import supabase_client as db
from database.supabase_client import stable_match_key, _norm_player_key


def main(dry_run: bool) -> None:
    rows = db._select("analyzed_matches",
                      select="id,external_match_id,match_date,player1,player2,surface,"
                             "actual_winner,prediction_correct",
                      limit=5000)
    print(f"Ukupno analiza u bazi: {len(rows)}")

    # ── 1. Nepopravljivo korumpirani (pobjednik nije nijedan od igrača) ──────────
    corrupt = []
    for r in rows:
        aw = _norm_player_key(r.get("actual_winner"))
        if not aw:
            continue
        if aw not in (_norm_player_key(r.get("player1")), _norm_player_key(r.get("player2"))):
            corrupt.append(r)
    by_surface = {}
    for r in corrupt:
        s = (r.get("surface") or "?").lower()
        by_surface[s] = by_surface.get(s, 0) + 1
    print(f"\n1) KORUMPIRANIH redaka (pobjednik nije igrač u meču): {len(corrupt)}")
    for s, n in sorted(by_surface.items()):
        print(f"     {s}: {n}")
    for r in corrupt[:5]:
        print(f"     npr. {r['match_date']} {r['player1']} vs {r['player2']} "
              f"-> '{r['actual_winner']}'")
    if not dry_run:
        for r in corrupt:
            db._rest("DELETE", "analyzed_matches", params={"id": f"eq.{r['id']}"},
                     prefer="return=representation")
        print(f"     obrisano: {len(corrupt)}")

    # ── 2. Stabilan ključ + razrješavanje kolizija ──────────────────────────────
    survivors = [r for r in rows if r not in corrupt]
    groups: dict = {}
    for r in survivors:
        key = stable_match_key(r.get("match_date"), r.get("player1"), r.get("player2"))
        groups.setdefault(key, []).append(r)

    dupes = {k: v for k, v in groups.items() if len(v) > 1}
    n_dupe_rows = sum(len(v) - 1 for v in dupes.values())
    print(f"\n2) STABILAN KLJUČ: {len(groups)} jedinstvenih mečeva iz {len(survivors)} redaka")
    print(f"     duplikata za spajanje: {len(dupes)} mečeva ({n_dupe_rows} viška redaka)")

    n_updated = n_deleted = 0
    for key, grp in groups.items():
        # Zadrži red s ishodom; ako ih je više s ishodom, zadrži prvi. Ostale briši.
        grp_sorted = sorted(grp, key=lambda r: (r.get("actual_winner") is None,
                                                str(r.get("id"))))
        keep, drop = grp_sorted[0], grp_sorted[1:]
        if keep.get("external_match_id") != key:
            if not dry_run:
                db._update("analyzed_matches", {"external_match_id": key},
                           {"id": f"eq.{keep['id']}"})
            n_updated += 1
        for r in drop:
            if not dry_run:
                db._rest("DELETE", "analyzed_matches", params={"id": f"eq.{r['id']}"},
                         prefer="return=representation")
            n_deleted += 1
    print(f"     {'[dry-run] ' if dry_run else ''}ključ prepisan: {n_updated} | "
          f"duplikata obrisano: {n_deleted}")

    # ── 3. Stanje korpusa ───────────────────────────────────────────────────────
    if not dry_run:
        after = db.get_resolved_analyzed_matches()
        print(f"\n3) KALIBRACIJSKI KORPUS POSLIJE: {len(after)} razriješenih analiza")
        agg = {}
        for r in after:
            s = (r.get("surface") or "?").lower()
            d = agg.setdefault(s, [0, 0])
            d[0] += 1
            if r.get("prediction_correct"):
                d[1] += 1
        for s, (n, ok) in sorted(agg.items()):
            print(f"     {s}: n={n}, točno {ok} ({ok/n*100:.1f}%)")
    else:
        print("\n3) [dry-run] ništa nije promijenjeno.")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="samo ispiši, ne mijenjaj")
    main(ap.parse_args().dry_run)
