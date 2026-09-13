# -*- coding: utf-8 -*-
"""Ispravlja povijesne oznake rundi u `analyzed_matches` iz stvarnog zdrijeba.

NASTALO 13.09.2026 10:44.

ZASTO POSTOJI
=============
`_ROUND_ID_MAP` u `data_fetcher` pretpostavljao je da je `roundId` globalna konstanta
(1=R128 ... 7=F). Nije — relativan je po turniru:

    U.S. Open (zdrijeb 128)   4=R128(64)  5=R64(32)  6=R32(16)  7=R16(8)  9=QF(4)  10=SF(2)
    Cassis Challenger (32)    4=R32(16)   5=R16(8)                        9=QF(4)  10=SF(2)  12=F(1)

Isti `roundId=4` znaci R128 na jednom turniru i R32 na drugom. Posljedica izmjerena na
zadnjih 40 analiza US Opena: **16 krivih oznaka (40%)**, i to sustavno — prvi dan svake
runde tocan, drugi dan napuhan za jednu do dvije runde.

Zivi put je popravljen istog dana (`data_fetcher.get_tournament_round_map` +
`run_daily._apply_draw_rounds`). Ova skripta popravlja ono sto je vec u bazi.

ZASTO JE TO VAZNIJE NEGO STO ZVUCI
==================================
Runda ne ulazi samo u prompt. Ulazi u SVAKU retrospektivnu analizu. Nalaz "rupa u
R16/QF" (revizija 26.08.2026, -13,3pp z=-2,31) mjeren je na 40% krivim oznakama i bez
ovog ispravka se ne moze ni potvrditi ni odbaciti. Isto vrijedi za svaki buduci nalaz
koji reze korpus po rundi.

KAKO RADI
=========
Za svaki turnir iz `analyzed_matches` dohvaca stvarni zdrijeb i upisuje ispravnu rundu
tamo gdje se mec moze jednoznacno prepoznati po PAROVIMA PREZIMENA. Prezimena, jer se
puni oblik imena razlikuje izmedju API-ja i vec upisanih redaka ("Botic Van De
Zandschulp" naspram "B. van de Zandschulp").

Mecevi koji se ne mogu prepoznati NE DIRAJU SE. Bolje ostaviti staru oznaku nego upisati
pogodjenu — cijela poanta ovog popravka je prestati pogadjati.

POKRETANJE
==========
    python scripts/backfill_rounds_from_draw.py            # samo prikaz, nista ne mijenja
    python scripts/backfill_rounds_from_draw.py --apply    # stvarno upisuje
"""
import sys
import os
import io
import argparse
from collections import defaultdict, Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import agent.data_fetcher as df
import database.supabase_client as sb


def _surname(x: str) -> str:
    parts = str(x or "").lower().replace("-", " ").split()
    return parts[-1] if parts else ""


def _pair(a: str, b: str) -> frozenset:
    return frozenset([_surname(a), _surname(b)])


def _tournament_ids() -> dict:
    """{ime turnira: tournament_id} iz sluzbenog kalendara sezone.

    `analyzed_matches` ne nosi `tournament_id`, pa se mora rekonstruirati. Prvi pokusaj
    (13.09.2026) skenirao je fixtures unatrag 120 dana i uparivao SAMO 14 od 28 turnira —
    fixtures ne sezu daleko u proslost. `/atp/tournament/calendar/{godina}` vraca cijelu
    sezonu (792 zapisa za 2026) u JEDNOM pozivu i pokriva sve.
    """
    out = {}
    for year in (2026, 2025):
        data = df._get(f"/atp/tournament/calendar/{year}")
        rows = (data or {}).get("data", data)
        if not isinstance(rows, list):
            continue
        for t in rows:
            name, tid = t.get("name"), t.get("id")
            if name and tid and name not in out:
                out[name] = tid
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="stvarno upisi promjene (bez toga je samo prikaz)")
    args = ap.parse_args()

    rows = sb._select("analyzed_matches", select="*", limit=3000)
    print(f"Redaka u analyzed_matches: {len(rows)}")

    by_tour = defaultdict(list)
    for r in rows:
        if r.get("tournament"):
            by_tour[r["tournament"]].append(r)
    print(f"Razlicitih turnira: {len(by_tour)}")

    print("Trazim tournament_id-eve iz kalendara sezone...")
    tids = _tournament_ids()
    print(f"  upareno {len(tids)} imena turnira s ID-em")

    total_ok = total_bad = total_unknown = 0
    changes = []
    per_tour = {}

    for tname, group in sorted(by_tour.items()):
        tid = tids.get(tname)
        if not tid:
            total_unknown += len(group)
            per_tour[tname] = ("nema tournament_id", len(group), 0)
            continue

        rmap = df.get_tournament_round_map(tid)
        if not rmap:
            total_unknown += len(group)
            per_tour[tname] = ("zdrijeb nedostupan", len(group), 0)
            continue

        raw = df._get(f"/atp/tournament/results/{tid}")
        singles = ((raw or {}).get("data") or {}).get("singles") or []
        truth = {}
        for m in singles:
            lbl = rmap.get(m.get("roundId"))
            if not lbl:
                continue
            a = (m.get("player1") or {}).get("name") or ""
            b = (m.get("player2") or {}).get("name") or ""
            truth[_pair(a, b)] = lbl

        ok = bad = unknown = 0
        for r in group:
            t = truth.get(_pair(r.get("player1"), r.get("player2")))
            if t is None:
                unknown += 1
                continue
            if (r.get("round") or "") == t:
                ok += 1
            else:
                bad += 1
                changes.append((r["id"], tname, (r.get("match_date") or "")[:10],
                                r.get("player1"), r.get("player2"),
                                r.get("round"), t))
        total_ok += ok
        total_bad += bad
        total_unknown += unknown
        per_tour[tname] = ("ok", len(group), bad)

    print()
    print("=" * 78)
    print("PO TURNIRU")
    print("=" * 78)
    for tname, (status, n, bad) in sorted(per_tour.items(), key=lambda x: -x[1][2]):
        flag = f"{bad} krivih" if status == "ok" else status
        print(f"  {tname[:46]:<46} n={n:<5} {flag}")

    print()
    print("=" * 78)
    print(f"TOCNIH {total_ok}   KRIVIH {total_bad}   NEPROVJERIVIH {total_unknown}")
    if total_ok + total_bad:
        print(f"udio krivih medju provjerivima: {100.0 * total_bad / (total_ok + total_bad):.1f}%")
    print("=" * 78)

    if changes:
        print()
        print("PROMJENE (prvih 40):")
        for _id, tn, d, p1, p2, old, new in changes[:40]:
            print(f"  {d}  {str(p1)[:22]:<22} vs {str(p2)[:22]:<22}  {old or '-':<5} -> {new}")
        print()
        print("smjer promjena:", dict(Counter(f"{o or '-'}->{n}" for _, _, _, _, _, o, n in changes)))

    if not args.apply:
        print()
        print("PRIKAZ SAMO — nista nije upisano. Pokreni s --apply za stvarni upis.")
        return 0

    print()
    print(f"Upisujem {len(changes)} ispravaka...")
    done = fail = 0
    for _id, tn, d, p1, p2, old, new in changes:
        try:
            sb._update("analyzed_matches", {"round": new}, {"id": f"eq.{_id}"})
            done += 1
        except Exception as e:
            fail += 1
            print(f"  GRESKA na {_id}: {str(e)[:70]}")
    print(f"Upisano {done}, neuspjelih {fail}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
