# -*- coding: utf-8 -*-
"""Backfill post-match statistike za razrijesene meceve bez nje (30.08.2026 11:05).

POVOD
Korisnik je 30.08. uocio da Fery-Buse (finale Winston-Salema, 29.08.) nema post-match
statistiku, pa je i analiza gubitka ostala bez brojki. Dijagnoza: `match_stats` se dohvaca
samo kad je poznat `tournament_id`, a taj se citao ISKLJUCIVO iz `/atp/fixtures` feeda —
koji za prosle dane izbacuje odigrane meceve. Feed za 29.08. vratio je NULA meceva, pa je
`get_match_stats` za taj mec pozvan nula puta. Podaci su cijelo vrijeme postojali:
`/atp/h2h/match-stats/21348/79065/79113` vraca punu statistiku.

Uzrok je popravljen u `feedback_analyzer._build_season_winner_lookup` (razrijeseni
`tournament_id` se sada vraca u `pair_to_tid`), pa se ubuduce ne ponavlja. Ova skripta
zatvara RUPU UNATRAG.

STO RADI
  1. nadje razrijesene retke (`actual_winner` postoji) bez `match_stats`
  2. razrijesi `tournament_id` po TURNIRU (jednom, pa se dijeli) preko past-matches rute
  3. razrijesi player ID-eve koji nedostaju (starim retcima) preko `find_player_id`
  4. dohvati statistiku kroz `get_match_stats_aligned` — poravnato i DOKAZANO po ID-u
  5. spremi; ako je ID nedostajao a poravnanje uspjelo, spremi i ID (poravnanje ga dokazuje)

NIKAD NE POGADJA. Ako se poravnanje ne moze dokazati, redak se preskace i broji u
izvjestaju. Bolje prazno polje nego brojke pripisane krivom igracu.

Pokretanje:
    python scripts/backfill_match_stats.py --dry-run          # samo izvjestaj
    python scripts/backfill_match_stats.py --since 2026-07-25 # stvarni upis
    python scripts/backfill_match_stats.py --limit 20         # u malim serijama
"""
import os
import sys
import argparse
import datetime
import collections

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from database import supabase_client as db
from agent.data_fetcher import (get_recent_form, get_match_stats_aligned,
                                align_match_stats, find_player_id)

_form_cache: dict = {}
_pid_cache: dict = {}
_tid_cache: dict = {}


def _form(pid: str) -> list:
    if pid not in _form_cache:
        try:
            _form_cache[pid] = get_recent_form(pid, n=60).get("matches", []) or []
        except Exception:
            _form_cache[pid] = []
    return _form_cache[pid]


def _pid(name: str) -> str:
    key = (name or "").lower().strip()
    if not key:
        return ""
    if key not in _pid_cache:
        try:
            _pid_cache[key] = str(find_player_id(key) or "")
        except Exception:
            _pid_cache[key] = ""
    return _pid_cache[key]


def _surname(name: str) -> str:
    parts = (name or "").lower().strip().split()
    return parts[-1] if parts else ""


def _tid_for(row: dict, p1_id: str, p2_id: str) -> str:
    """tournament_id preko past-matches jednog od igraca.

    Ista pravila kao `_build_season_winner_lookup`: trazi se TOCNO taj par (prezime
    protivnika) unutar +-2 dana. Siri prozor je hvatao susjedni turnir istog igraca.
    """
    d = str(row.get("match_date") or "")[:10]
    if not d:
        return ""
    try:
        d0 = datetime.date.fromisoformat(d)
    except ValueError:
        return ""
    lo, hi = d0 - datetime.timedelta(days=2), d0 + datetime.timedelta(days=2)
    for me, opp_name in ((p1_id, row.get("player2")), (p2_id, row.get("player1"))):
        if not me:
            continue
        opp = _surname(opp_name)
        if not opp:
            continue
        for fm in _form(me):
            if not fm.get("tournament_id"):
                continue
            if opp not in (fm.get("opponent") or "").lower():
                continue
            try:
                fd = datetime.date.fromisoformat(fm.get("date") or "")
            except ValueError:
                continue
            if lo <= fd <= hi:
                return str(fm["tournament_id"])
    return ""


def _needs_stats(rows: list) -> list:
    return [r for r in rows
            if (r.get("actual_winner") or r.get("result") in ("won", "lost"))
            and not r.get("match_stats")]


def run(table: str, since: str, limit: int, dry: bool, resolve_ids: bool) -> dict:
    if table == "analyzed":
        rows = _sel("analyzed_matches")
        save = db.save_analyzed_match_stats
        id_table = "analyzed_matches"
    else:
        rows = _sel("ticket_matches")
        save = lambda rid, st: (db.save_match_stats(rid, st) or True)
        id_table = "ticket_matches"

    todo = [r for r in _needs_stats(rows) if str(r.get("match_date") or "") >= since]
    todo.sort(key=lambda r: r.get("match_date") or "")
    if limit:
        todo = todo[:limit]

    stat = collections.Counter()
    by_t = collections.defaultdict(list)
    for r in todo:
        by_t[(r.get("tournament") or "?").split(" - ")[0].strip().lower()].append(r)

    print(f"\n=== {id_table}: {len(todo)} redaka bez statistike (od {since}), "
          f"{len(by_t)} turnira ===")

    for tname, group in sorted(by_t.items()):
        tid = _tid_cache.get(tname, "")
        for r in group:
            p1_id = str(r.get("player1_id") or "")
            p2_id = str(r.get("player2_id") or "")
            if resolve_ids and (not p1_id or not p2_id):
                p1_id = p1_id or _pid(r.get("player1"))
                p2_id = p2_id or _pid(r.get("player2"))
            if not p1_id or not p2_id:
                stat["bez player ID-eva"] += 1
                continue
            if not tid:
                tid = _tid_for(r, p1_id, p2_id)
                if tid:
                    _tid_cache[tname] = tid
            if not tid:
                stat["bez tournament_id"] += 1
                continue
            try:
                st, why = get_match_stats_aligned(tid, p1_id, p2_id)
            except Exception as e:
                stat["greska API-ja"] += 1
                print(f"   GRESKA {r.get('player1')} vs {r.get('player2')}: {str(e)[:60]}")
                continue
            if not st:
                stat[f"odbijeno: {why}" if "poklap" in (why or "") else
                     "endpoint nema statistiku"] += 1
                continue
            label = (f"{r.get('match_date')} {r.get('player1')} vs {r.get('player2')}"
                     f"  [{'zamijenjen' if st['_align']['swapped'] else 'isti'} redoslijed]")
            if dry:
                stat["spremno za upis"] += 1
                print(f"   [suho] {label}")
                continue
            if save(r["id"], st):
                stat["upisano"] += 1
                print(f"   OK    {label}")
                # ID-eve spremamo SAMO kad je poravnanje uspjelo — ono ih dokazuje
                # (skup ID-eva iz odgovora mora se poklopiti s nasim parom).
                if not r.get("player1_id") or not r.get("player2_id"):
                    try:
                        db._update(id_table, {"player1_id": p1_id, "player2_id": p2_id},
                                   {"id": f"eq.{r['id']}"})
                        stat["dopunjeni player ID-evi"] += 1
                    except Exception:
                        pass
            else:
                stat["upis nije uspio"] += 1
    return stat


def realign(table: str, dry: bool, resolve_ids: bool = False) -> dict:
    """Poravnaj UNATRAG retke spremljene prije 30.08.2026 (sirovi odgovor u bazi).

    ZASTO: do 30.08. se u bazu spremao SIROVI odgovor, a orijentacija se popravljala tek
    pri citanju. Izmjereno 30.08. na 436 takvih redaka: citani po poziciji, pobjednik meca
    ima vise ukupnih poena u samo **47%** slucajeva — dakle bacanje novcica. Kod redaka
    poravnatih pri upisu isti pokazatelj je **94%**, sto odgovara prirodnoj stopi u tenisu
    (mec se moze izgubiti uz vise osvojenih poena, otprilike 5-6% mecheva).

    Nijedan API poziv: statistika i ID-evi su vec u bazi, poravnanje je cisto racunanje.
    Retci kojima poravnanje nije DOKAZIVO ostaju netaknuti.
    """
    rows = _sel("analyzed_matches" if table == "analyzed" else "ticket_matches")
    save = (db.save_analyzed_match_stats if table == "analyzed"
            else (lambda rid, st: (db.save_match_stats(rid, st) or True)))
    stat = collections.Counter()
    for r in rows:
        ms = r.get("match_stats")
        if not isinstance(ms, dict) or (ms.get("_align") or {}).get("verified"):
            continue
        p1_id = str(r.get("player1_id") or "")
        p2_id = str(r.get("player2_id") or "")
        # Stariji retci (prije 26.07.2026) nemaju spremljene player ID-eve, pa se
        # poravnanje ne moze dokazati i njihova se statistika u analizi ionako
        # PRESKACE. ID-evi se traze po imenu iz ranking mape (kesirano, prakticki bez
        # API poziva); ako su krivi, align_match_stats ih odbija jer se skup ID-eva
        # nece poklopiti s odgovorom. Dakle: pogodak ih ozivljava, promasaj ne steti.
        if resolve_ids and (not p1_id or not p2_id):
            p1_id = p1_id or _pid(r.get("player1"))
            p2_id = p2_id or _pid(r.get("player2"))
        out, why = align_match_stats(ms, p1_id, p2_id)
        if not out:
            stat[f"preskoceno: {why[:38]}"] += 1
            continue
        if dry:
            stat["spremno: " + ("ZAMJENA" if out["_align"]["swapped"] else "vec tocno")] += 1
            continue
        # REDOSLIJED JE NAMJERAN: ID-evi PRIJE statistike. Ako upis pukne na pola (30.08.
        # su tri retka tako zavrsila zbog prekida veze prema Supabaseu), zelimo ostati s
        # ID-evima bez statistike — to je bezopasno — a ne sa statistikom bez ID-eva, gdje
        # se poravnanje vise ne moze PROVJERITI iz samog retka.
        if not r.get("player1_id") or not r.get("player2_id"):
            try:
                db._update("analyzed_matches" if table == "analyzed" else "ticket_matches",
                           {"player1_id": p1_id, "player2_id": p2_id},
                           {"id": "eq.%s" % r["id"]})
                stat["dopunjeni player ID-evi"] += 1
            except Exception:
                stat["upis ID-eva nije uspio"] += 1
                continue
        if save(r["id"], out):
            stat["poravnato: " + ("ZAMJENA" if out["_align"]["swapped"] else "vec tocno")] += 1
        else:
            stat["upis nije uspio"] += 1
    return stat


def _sel(table: str) -> list:
    """Citanje cijele tablice kroz postojeci klijent (bez novih ovisnosti)."""
    out, off = [], 0
    while True:
        page = db._select(table, filters={"limit": "1000", "offset": str(off)}) or []
        out += page
        if len(page) < 1000:
            break
        off += 1000
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-07-25",
                    help="samo mecevi od ovog datuma (zadano: era stabilnog kljuca)")
    ap.add_argument("--limit", type=int, default=0, help="max redaka po tablici")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--table", choices=["both", "analyzed", "ticket"], default="both")
    ap.add_argument("--no-resolve-ids", action="store_true",
                    help="preskoci trazenje player ID-eva za stare retke (manje API poziva)")
    ap.add_argument("--realign", action="store_true",
                    help="samo poravnaj postojece retke spremljene prije 30.08. (0 API poziva)")
    a = ap.parse_args()

    tables = ["ticket", "analyzed"] if a.table == "both" else [a.table]
    total = collections.Counter()
    for t in tables:
        if a.realign:
            print("")
            print("=== PORAVNANJE UNATRAG: %s ===" % t)
            total.update(realign(t, a.dry_run, not a.no_resolve_ids))
        else:
            total.update(run(t, a.since, a.limit, a.dry_run, not a.no_resolve_ids))

    print("\n=== SAZETAK ===")
    for k, v in total.most_common():
        print(f"  {k:<40} {v}")
    if a.dry_run:
        print("\n  (suhi hod — nista nije upisano)")


if __name__ == "__main__":
    main()
