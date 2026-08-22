# -*- coding: utf-8 -*-
"""Harvest povijesti mečeva po igraču — za mjerenje MENTALNE IZDRŽLJIVOSTI (22.08.2026 09:24).

ZAŠTO POSTOJI
Korisnik je 22.08.2026 opisao varijablu koju smatra bitnom: "kada netko gubi u setovima i u
drugom setu isto gubi, pa na kraju dobije". To je povratak iz zaostatka — mjerljiva stvar,
ali samo ako imamo REZULTATE PO SETOVIMA za dovoljno mečeva svakog igrača.

Analiza od 22.08. pokušala je to izmjeriti iz našeg vlastitog korpusa i nije uspjela:
    pick s poviješću povrataka >=34%  ->  75,0% (n=20)
    pick bez ijednog povratka        ->  68,6% (n=51)
    rekord u odlučujućim setovima    ->  -2,9pp, P=0,881 (ništa)
Smjer je obećavajuć, ali SAMO 78 pickova ima barem 2 prethodna meča u našem korpusu — a
naš korpus bilježi rezultat po setovima tek od kad se `actual_score` sprema. To je premalo
za bilo kakav zaključak; efekt te veličine treba nekoliko stotina mečeva po populaciji.

ŠTO OVA SKRIPTA RADI
Dohvaća `/atp/player/past-matches/{id}` za svakog igrača kojeg smo ikad analizirali i sprema
SIROVE zapise (uključujući rezultat po setovima) u `player_match_history`. Iz toga se onda
mogu izračunati, po igraču i PRIJE meča koji predviđamo:
  - stopa povratka nakon izgubljenog prvog seta
  - učinak u odlučujućem setu
  - učinak u tie-breakovima
  - udio pobjeda u 2 seta (dominacija) naspram tijesnih
  - kvaliteta protivnika kroz koje je došao

NE ULAZI NI U JEDNU ODLUKU. Samo puni bazu, kao što su to prvo radile break lopte (07.08.),
dob (15.08.), tržišne cijene (15.08.) i cijene po kladionici (15.08.).

=============================================================================================
REZULTAT MJERENJA — 22.08.2026 12:10, nakon prvog harvesta (727 mečeva, 723 iskoristiva,
115 igrača s >=5 mečeva, 259 naših pickova s poviješću naspram 78 prije harvesta)
=============================================================================================
HIPOTEZA JE MJERENA I **NIJE PROŠLA**. Štoviše, sirovi efekt ide u SUPROTNOM smjeru:

    pick se vraća iz zaostatka   0- 8% mečeva  ->  71,1% (n=90)
                                 8-15%          ->  64,0% (n=50)
                                15-22%          ->  60,0% (n=70)
                                22%+            ->  57,1% (n=49)
    r(stopa povratka, pobjeda) = -0,105 (P=0,092); iznad medijana 59,1% vs ispod 68,9%

Monotono OPADANJE kroz četiri razreda, i drži se u obje polovice uzorka.

ZAŠTO — mehanizam je jasan kad se vidi:
    r(stopa povratka, koliko često igrač GUBI PRVI SET) = **+0,473 (P<0,0001)**
    r(stopa povratka, pobjednički postotak igrača)      = +0,340 (P=0,0002)
Visoka stopa povratka NIJE oznaka mentalne čvrstine nego oznaka igrača koji **redovito
zaostaje**. Da bi se vratio iz zaostatka, prvo mora izgubiti set. Konzistentni igrači
pobjeđuju u dva seta i nikad ne uđu u statistiku povratka.

A ONDA I TO NESTANE POD KONTROLOM CIJENE:
    stratificirano po kvoti, efekt pada s -9,9pp na **-3,6pp**, i mijenja predznak unutar
    pojasa (1,55-1,80: visoka stopa 70,6% vs niska 52,2% — obrnuto od ukupnog nalaza).
Dakle sirovi efekt je uglavnom bio kvaliteta igrača, koju kvota ionako već nosi.

ISTO VRIJEDI ZA TIEBREAK REKORD iz prave povijesti: sirovo TB>=55% 67,3% (n=110) naspram
TB<45% 61,1% (n=90), ali kontrolirano po kvoti ostaje **+2,7pp** i praktički je ravno u
svakom pojasu (86,2 vs 83,3 | 59,4 vs 56,7 | 68,8 vs 63,6 | 40,0 vs 40,0).

USPOREDBA KOJA POKAZUJE DA KONTROLA NIJE PREOŠTRA: ista stratifikacija po kvoti primijenjena
na razliku u povijesti na turniru daje **+17,5pp** i signal preživi. Kontrola ne ubija sve
redom — ubija ono što je bilo prerušena kvaliteta igrača.

ZAKLJUČAK: korisnikova intuicija da mentalna izdržljivost postoji vjerojatno nije pogrešna,
ali OVA MJERA je hvata naopako. Ako se bude tražilo dalje, kandidati su: postotak osvojenih
poena pri 30-30/deuce, postotak spašenih break lopti pri 4-5 zaostatka, ili razlika između
očekivanog i stvarnog ishoda u tijesnim setovima — ništa od toga nije u dostupnim podacima.
NE trošiti više vremena na "povratak iz zaostatka" bez novog izvora podataka.
=============================================================================================

POKRETANJE
    python scripts/harvest_player_history.py --dry-run    # samo ispiši što bi se spremilo
    python scripts/harvest_player_history.py              # spremi u Supabase
    python scripts/harvest_player_history.py --limit 30   # samo prvih 30 igrača

PRIJE PRVOG POKRETANJA treba u Supabaseu napraviti tablicu — SQL je u `database/schema.sql`
(tablica `player_match_history`).
"""
import os
import sys
import argparse
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from agent import data_fetcher as df
from database import supabase_client as db


def known_player_ids() -> dict:
    """Svi player_id-evi koje smo ikad vidjeli u analizama -> ime."""
    out = {}
    try:
        rows = db._select("analyzed_matches",
                          select="player1,player2,player1_id,player2_id", limit=5000)
    except Exception as e:
        print(f"  Ne mogu dohvatiti analyzed_matches: {str(e)[:90]}")
        return out
    for r in rows:
        for idk, namek in (("player1_id", "player1"), ("player2_id", "player2")):
            pid = r.get(idk)
            if pid:
                out.setdefault(str(pid), r.get(namek) or "")
    return out


def harvest_one(pid: str, name: str) -> list:
    """Sirovi past-matches za jednog igraca -> redci za bazu."""
    raw = df._get(f"/atp/player/past-matches/{pid}")
    if not raw:
        return []
    games = raw.get("data", raw.get("result", raw))
    if not isinstance(games, list):
        return []
    rows = []
    for g in games:
        p1 = g.get("player1") or {}
        p2 = g.get("player2") or {}
        p1_id = str(g.get("player1Id", p1.get("id", "")) or "")
        p2_id = str(g.get("player2Id", p2.get("id", "")) or "")
        winner = str(g.get("match_winner", g.get("winnerId", g.get("winner_id", ""))) or "")
        score = (g.get("score") or g.get("result") or g.get("scores") or "")
        if isinstance(score, (list, dict)):
            score = str(score)
        date = str(g.get("date") or g.get("startDate") or g.get("matchDate") or "")[:10]
        if not (p1_id and p2_id):
            continue
        rows.append({
            # Kljuc mora biti stabilan i neovisan o tome preko kojeg smo igraca dosli do meca.
            "match_key": f"{date}|{min(p1_id, p2_id)}|{max(p1_id, p2_id)}",
            "match_date": date or None,
            "player1_id": p1_id,
            "player2_id": p2_id,
            "player1_name": p1.get("name") or "",
            "player2_name": p2.get("name") or "",
            "winner_id": winner or None,
            "score": str(score)[:120],
            "tournament": (g.get("tournament") or {}).get("name") if isinstance(g.get("tournament"), dict) else (g.get("tournament") or ""),
            "surface": g.get("surface") or "",
            "round_name": g.get("round") or g.get("roundName") or "",
            "source_player_id": pid,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="obradi samo prvih N igraca")
    args = ap.parse_args()

    ids = known_player_ids()
    if args.limit:
        ids = dict(list(ids.items())[:args.limit])
    print(f"Igraca za harvest: {len(ids)}")

    all_rows, seen = [], set()
    for n, (pid, name) in enumerate(ids.items(), 1):
        try:
            rows = harvest_one(pid, name)
        except Exception as e:
            print(f"  {name}: greska {str(e)[:70]}")
            continue
        for r in rows:
            if r["match_key"] in seen:
                continue
            seen.add(r["match_key"])
            all_rows.append(r)
        if n % 20 == 0:
            print(f"  {n}/{len(ids)} igraca, {len(all_rows)} jedinstvenih meceva")

    with_score = sum(1 for r in all_rows if r["score"] and "-" in r["score"])
    print(f"\nUkupno jedinstvenih meceva: {len(all_rows)}")
    print(f"...s upotrebljivim rezultatom po setovima: {with_score}")
    if all_rows:
        print("Primjer:", {k: all_rows[0][k] for k in ("match_date", "player1_name", "player2_name", "score")})

    if args.dry_run:
        print("[DRY RUN] Nista nije spremljeno.")
        return 0
    if not all_rows:
        print("Nema sto spremiti.")
        return 0

    saved = 0
    for i in range(0, len(all_rows), 500):
        chunk = all_rows[i:i + 500]
        try:
            db._upsert("player_match_history", chunk, on_conflict="match_key")
            saved += len(chunk)
        except Exception as e:
            print(f"  Chunk {i // 500} nije spremljen: {str(e)[:140]}")
    print(f"Spremljeno: {saved}/{len(all_rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
