# -*- coding: utf-8 -*-
"""Jednokratni backfill ishoda u analyzed_matches (26.07.2026).

Povod: /atp/fixtures nikad ne vraća pobjednika (čisti raspored), pa je večernji korak
razrješavanja od 18.07. upisao 0/421 ishoda — kalibracijska tablica na Model Statistike
je ostala prazna, a hard-revalidacijski okidač (30 razriješenih hard pickova) slijep.
Dodatno, fixtures za PROŠLE dane izbacuju već odigrane mečeve, pa se tournament_id ne
može dobiti iz feeda — koristi se zajednički _build_season_winner_lookup iz
feedback_analyzera (tid preko past-matches igrača s ranking liste, pobjednici iz
/atp/tournament/results tekuće sezone).

Pokretanje:  python scripts/backfill_analyzed_results.py [--dry-run]
"""
import sys
import os
import io
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import supabase_client as db
from agent.feedback_analyzer import _build_season_winner_lookup, _names_match


def main(dry_run: bool) -> None:
    unresolved = db._select(
        "analyzed_matches",
        select="id,match_date,player1,player2,tournament,predicted_winner",
        filters={"actual_winner": "is.null"},
        order="match_date.asc", limit=3000)
    print(f"Nerazriješenih analiza ukupno: {len(unresolved)}")
    if not unresolved:
        return

    winner_by_pair = _build_season_winner_lookup(unresolved, pair_to_tid={})

    n_resolved = n_correct = n_wrong = n_nopred = 0
    unmatched_tournaments: dict = {}
    for am in unresolved:
        k = ((am.get("player1") or "").lower().strip(),
             (am.get("player2") or "").lower().strip())
        winner = winner_by_pair.get(k, "")
        if not winner:
            t = (am.get("tournament") or "?").split(" - ")[0]
            unmatched_tournaments[t] = unmatched_tournaments.get(t, 0) + 1
            continue
        predicted = am.get("predicted_winner") or ""
        correct = _names_match(predicted, winner) if predicted else None
        if correct is True:
            n_correct += 1
        elif correct is False:
            n_wrong += 1
        else:
            n_nopred += 1
        if not dry_run:
            db.update_analyzed_match_result(am["id"], winner, correct)
        n_resolved += 1

    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Razriješeno: {n_resolved}/{len(unresolved)} "
          f"(točno {n_correct}, krivo {n_wrong}, bez predikcije {n_nopred})")
    if unmatched_tournaments:
        print("Nerazriješeno po turnirima (par nije nađen u rezultatima sezone — "
              "kvalifikacije, otkazani, drugačija imena...):")
        for t, n in sorted(unmatched_tournaments.items(), key=lambda x: -x[1]):
            print(f"  {t}: {n}")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="samo ispiši, ne upisuj")
    args = ap.parse_args()
    main(args.dry_run)
