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

DOPUNA 26.09.2026 20:28 (revizija, H2): analiza gubitka od danas dobiva CINJENICE O MECU
(kvota, devig cijena, pojas, runda, status tiketa, predaja — `_loss_match_facts`), jer je
15 od 20 rujanskih analiza te cinjenice izmisljalo. Za regeneraciju tih analiza:
    python scripts/regen_loss_analyses.py --since 2026-08-29 --include-no-stats         --backup revizije/2026-09-26/stare_analize_gubitaka.json
  --since             samo noge s match_date >= datum (format analiza s verdiktima je od 29.08.)
  --include-no-stats  i noge BEZ post-match statistike — cinjenice vrijede i bez nje
  --backup            PRIJE prepisivanja spremi stare tekstove (JSON) — prepisivanje je
                      nepovratno, a stare analize su dokaz zasto je popravak bio potreban
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


def main(dry_run: bool, since: str = None, include_no_stats: bool = False,
         backup: str = None) -> None:
    rows = db._select("ticket_matches", select="*", limit=1000)
    lost = [r for r in rows if r.get("result") == "lost"]
    if since:
        lost = [r for r in lost if str(r.get("match_date") or "") >= since]
    print(f"Izgubljenih pickova ukupno: {len(lost)}" + (f" (od {since})" if since else ""))

    # Kandidat = onaj kojem se blok sa statistikom stvarno moze sastaviti — ili, uz
    # --include-no-stats, svaki (cinjenice o mecu vrijede i bez statistike).
    cands = []
    for r in lost:
        block = _format_match_stats(r.get("player1", ""), r.get("player2", ""),
                                    r.get("match_stats") or {},
                                    r.get("player1_id"), r.get("player2_id"))
        if block or include_no_stats:
            cands.append((r, block or "(bez statistike)"))

    if backup and not dry_run:
        import json as _json
        os.makedirs(os.path.dirname(os.path.abspath(backup)), exist_ok=True)
        with open(backup, "w", encoding="utf-8") as f:
            _json.dump([{k: r.get(k) for k in ("id", "match_date", "player1", "player2", "pick",
                                                "odds", "round", "ticket_id", "loss_analysis")}
                        for r, _ in cands], f, ensure_ascii=False, indent=1)
        print(f"Sigurnosna kopija starih analiza: {backup} ({len(cands)} zapisa)")
    print(f"Kandidata za regeneraciju: {len(cands)}" + (" (i oni bez statistike)" if include_no_stats else " (imaju statistiku + ID-eve)"))
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
    ap.add_argument("--since", default=None, help="samo noge s match_date >= YYYY-MM-DD")
    ap.add_argument("--include-no-stats", action="store_true")
    ap.add_argument("--backup", default=None, help="JSON za stare tekstove prije prepisivanja")
    a = ap.parse_args()
    main(a.dry_run, since=a.since, include_no_stats=a.include_no_stats, backup=a.backup)
