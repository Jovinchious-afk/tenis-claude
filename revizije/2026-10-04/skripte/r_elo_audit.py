# -*- coding: utf-8 -*-
"""Revizija 04.10.2026 — provjera ELO podudaranja imena (04.10.2026 18:06).

Povod: "Jaume Antoni Munar Clar" (rang 64) u svim analizama nosi hard ELO 1397,5 / ukupni
1421,2, a u `elo_cache` stoji "jaume munar" 1748 / 1767. Sumnja: `find_player_elo` korak 3
prihvaća podudaranje POČETNOG SLOVA imena ("clar" u "jay clarke", "j" = "j") — isti
mehanizam kao Dali/Darwin Blanch 08.09.2026.

Što radi (samo čita): za svakog igrača iz analyzed_matches ponovi PRODUKCIJSKI lookup
(`agent.data_fetcher.find_player_elo` nad `get_elo_cache()`), zapiše kojim je korakom i na
koji ključ pogodio, i usporedi s "pravim" ključem (sve riječi ključa sadržane u imenu igrača,
ili ime igrača sadržano u ključu). Ispisuje sumnjive parove i pogođene analize.
Uz to: koliko redaka `get_elo_cache()` uopće vrati naspram stvarnog broja u tablici.
"""
import io
import json
import os
import re
import sys
import unicodedata
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(ROOT, ".env"))
from database import supabase_client as db  # noqa: E402
from agent import data_fetcher as dfm  # noqa: E402

DUMP = os.path.join(ROOT, ".cache", "rev_2026-10-04")


def norm(s):
    s = str(s or "").replace("\xa0", " ")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.lower().replace("-", " ").split())


def which_step(name, elo):
    """Koji korak find_player_elo pogađa i koji ključ (preslika logike, samo za dijagnozu)."""
    n = norm(name)
    for k in elo:
        if norm(k) == n:
            return 1, k
    sur = n.split()[-1]
    m = [k for k in elo if sur in norm(k)]
    if len(m) == 1:
        return 2, m[0]
    parts = n.split()
    if len(parts) >= 2:
        first, last = parts[0], parts[-1]
        for k in elo:
            kk = norm(k)
            if last in kk and (first in kk or kk.startswith(first[0])):
                return 3, k
    return 0, None


def proper_key(name, elo_all):
    """'Pravi' ključ: sve riječi ključa su riječi imena (npr. 'jaume munar' za 'Jaume Antoni Munar Clar')."""
    toks = set(norm(name).split())
    best = None
    for k in elo_all:
        kt = norm(k).split()
        if len(kt) >= 2 and set(kt) <= toks:
            if best is None or len(kt) > len(norm(best).split()):
                best = k
    return best


def main():
    # stvarni broj redaka u tablici (stranicama) naspram onoga što produkcija dobije
    allr, off = [], 0
    while True:
        ch = db._rest("GET", "elo_cache", params={"select": "player_name,elo_overall,elo_hard,elo_clay,elo_grass,updated_at",
                                                  "offset": str(off), "limit": "1000"})
        allr += ch
        if len(ch) < 1000:
            break
        off += 1000
    full = {}
    for r in allr:
        full[(r["player_name"] or "").lower().strip()] = r
    prod = db.get_elo_cache()
    missing = sorted(set(full) - set(prod))
    print(f"elo_cache: {len(allr)} redaka u tablici, get_elo_cache() vraća {len(prod)} -> nedostaje {len(missing)}")
    print("  primjeri nedostajućih:", [m.replace('\xa0', '_') for m in missing[:12]])
    print("  nedostajući po datumu:", {d: sum(1 for m in missing if str(full[m]['updated_at']).startswith(d))
                                       for d in ('2026-10-04', '2026-08-29', '2026-09-26', '2026-08-14', '2026-05-31')})

    am = json.load(open(os.path.join(DUMP, "analyzed_matches.json"), encoding="utf-8"))
    names = {}
    for r in am:
        cs = r.get("context_snapshot") or {}
        for a, key in (("p1", "player1"), ("p2", "player2")):
            nm = r.get(key)
            if nm:
                names.setdefault(nm, []).append((r, cs.get(f"{a}_elo_overall"), cs.get(f"{a}_elo_surface")))
    print(f"\nigrača u analizama: {len(names)}")
    bad = []
    steps = {0: 0, 1: 0, 2: 0, 3: 0}
    for nm, recs in names.items():
        st, k = which_step(nm, prod)
        steps[st] += 1
        pk = proper_key(nm, full)
        if st == 1:
            continue
        # sumnjivo: pogođeni ključ nije "pravi" ključ, ili pravi postoji a nije pogođen
        got = norm(k) if k else None
        if (pk and got != norm(pk)) or (k and not set(norm(k).split()) <= set(norm(nm).split())):
            with redirect_stdout(io.StringIO()):
                val = dfm.find_player_elo(nm, prod)
            true_val = full.get(pk) if pk else None
            bad.append((nm, st, k, pk, val, true_val, len(recs)))
    print("koraci produkcijskog lookupa:", {f"korak {k}": v for k, v in steps.items()}, "(0 = promašaj -> ELO 1500)")
    print(f"\nSUMNJIVI PAROVI ({len(bad)}): igrač -> pogođeni ključ (korak) | pravi ključ | ELO u analizi -> pravi ELO | analiza")
    affected = set()
    for nm, st, k, pk, val, tv, n in sorted(bad, key=lambda x: -x[6]):
        tvs = f"{tv['elo_overall']}/{tv['elo_hard']}" if tv else "—"
        print(f"  {nm:32s} -> {str(k).replace(chr(160),'_'):26s} (k{st}) | pravi: {str(pk).replace(chr(160),'_'):24s} | "
              f"{val.get('elo_overall')}/{val.get('elo_hard')} -> {tvs} | {n}")
        affected.add(nm)
    # analize u kojima je bar jedna strana pogođena, s pickom i ishodom
    print("\nANALIZE S POGREŠNIM ELO-om (riješene, s pickom):")
    tot = 0
    for r in am:
        if r.get("prediction_correct") is None or not r.get("predicted_winner"):
            continue
        hit = [x for x in (r.get("player1"), r.get("player2")) if x in affected]
        if hit:
            tot += 1
            pk = r["predicted_winner"]
            side = "PROTIV" if pk not in hit else "ZA"
            print(f"  {str(r['match_date'])[:10]} {str(r['tournament'])[:14]:14s} pick {pk:28s} {side:6s} pogođenog ({', '.join(hit)}) "
                  f"-> {'W' if r['prediction_correct'] else 'L'}")
    print(f"ukupno: {tot}")


if __name__ == "__main__":
    main()
