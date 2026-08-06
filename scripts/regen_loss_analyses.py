# -*- coding: utf-8 -*-
"""Jednokratna regeneracija analiza gubitaka koje mogu dobiti statistiku meca (05.08.2026).

POVOD: `_format_match_stats` je od uvodjenja vracala prazan string (dva neslaganja imena
polja — vidi njezin docstring), pa NIJEDNA analiza gubitka nikad nije vidjela statistiku
meca. Sve postojece analize napisane su samo na temelju rezultata po setovima i vlastitog
predmecnog obrazlozenja, pa su opcenite ("servis je popustio") umjesto konkretne
("iskoristio 2 od 9 break lopti").

ZASTO SAMO NEKE: blok sa statistikom moze se sastaviti samo kad postoje I spremljena
`match_stats` I nasi `player1_id`/`player2_id` (potrebni za poravnanje — redoslijed igraca
u statistici NE prati nas, kod 43% meceva je obrnut). Ostale analize regeneracija ne bi
poboljsala ni za sto, pa se namjerno preskacu umjesto da se trosi Claude poziv.

SIGURNOST OKO ID-eva (korisnikova briga): NE radi se nijedan API poziv. Cita se iskljucivo
ono sto je vec u bazi, a spremljena statistika i spremljeni ID zabiljezeni su u ISTOM
trenutku, pa je poravnanje interno konzistentno bez obzira sto API kasnije radi s ID-evima.
(Provjereno usput: 66 igraca kroz 12 dana, nijedan ID nije promijenio igraca — recikliraju
se fixture ID-evi, ne player ID-evi.)

Pokretanje:
    python scripts/regen_loss_analyses.py --dry-run   # samo popis, bez Claude poziva
    python scripts/regen_loss_analyses.py             # stvarna regeneracija
"""
import sys
import os
import io
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

from database import supabase_client as db
from agent.feedback_analyzer import _format_match_stats, _analyze_lost_match


def main(dry_run: bool) -> None:
    rows = db._select("ticket_matches", select="*", limit=1000)
    lost = [r for r in rows if r.get("result") == "lost"]
    print(f"Izgubljenih pickova ukupno: {len(lost)}")

    # Kandidat = onaj kojem se blok sa statistikom stvarno moze sastaviti.
    cands = []
    for r in lost:
        block = _format_match_stats(r.get("player1", ""), r.get("player2", ""),
                                    r.get("match_stats") or {},
                                    r.get("player1_id"), r.get("player2_id"))
        if block:
            cands.append((r, block))
    print(f"Kandidata za regeneraciju (imaju statistiku + ID-eve): {len(cands)}")
    print(f"Preskace se: {len(lost) - len(cands)} (bez statistike ili bez ID-eva — "
          f"regeneracija im ne bi promijenila nista)\n")

    # Isti mec zna biti na dva tiketa (tiket pokriva danas+sutra) — analiza se generira
    # jednom pa kopira, kao i u vecernjem updateu.
    cache = {}
    done = copied = failed = 0
    for r, block in sorted(cands, key=lambda x: x[0].get("match_date") or ""):
        key = ((r.get("player1") or "").lower().strip(),
               (r.get("player2") or "").lower().strip(), r.get("match_date"))
        label = f"{r.get('match_date')} {r.get('player1')} vs {r.get('player2')} (pick {r.get('pick')})"
        if dry_run:
            print(f"  [DRY] {label}")
            print("        " + block.strip().replace("\n", "\n        "))
            continue
        if key in cache:
            db.save_loss_analysis(r["id"], cache[key])
            copied += 1
            print(f"  Kopirano (isti mec, drugi tiket): {label}")
            continue
        analysis = _analyze_lost_match(r, r.get("match_stats") or {})
        if analysis:
            db.save_loss_analysis(r["id"], analysis)
            cache[key] = analysis
            done += 1
            print(f"  OK: {label}")
        else:
            failed += 1
            print(f"  NEUSPJELO: {label}")

    if not dry_run:
        print(f"\nRegenerirano: {done} | kopirano: {copied} | neuspjelo: {failed}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    main(a.dry_run)
