# -*- coding: utf-8 -*-
"""Bere post-match statistiku CIJELOG zdrijeba svakog turnira iz naseg korpusa.

NASTALO 13.09.2026 12:50.

ZASTO POSTOJI
=============
13.09.2026 12:20 uveden je kandidat **K12** — prosjek stvarne post-match statistike koju
je igrac ostvario NA OVOM turniru (servis, asovi, obranjeni i iskoristeni break-pointi)
ulazi u prompt, u odjeljak forme.

Uveden je unatoc tome sto je istog dana izmjeren kao nula (n=127, serve_won r=+0,008
P=0,924). Razlog je bio korisnikov prigovor mjerenju, i taj je prigovor VALJAN: uzorak je
bio plitak. Od 127 slucajeva njih 58 imalo je samo JEDAN raniji mec, a dubina 3+ imala je
n=23. Korisnikova tvrdnja je da signal zivi tek u cetvrtfinalu i polufinalu, kad iza
igraca stoje 3-4 meca — a mjerenje bas ondje nije imalo snagu.

Prag za odluku o K12 (zapisan PRIJE podataka, vidi DECISION_INPUTS) trazi n >= 40 na
dubini 3+. Iz `analyzed_matches` toliko nikad necemo skupiti, jer ta tablica drzi samo
mecheve koje smo MI analizirali — obicno 2-6 po danu, dakle djelic zdrijeba.

STO OVA SKRIPTA MIJENJA
=======================
`tournament/results` daje SVE odigrane mecheve turnira, bez obzira jesmo li ih gledali.
Berbom cijelog zdrijeba uzorak raste ovako (izmjereno 13.09.2026 12:50 na 28 turnira):

    dubina                      sada    nakon berbe
    2+ meca (nas prag)            69         260
    3+ meca (QF nadalje)          23         114   <- uzorak za odluku o K12
    4+ meca (SF/F)                 -          41

Razlika je dakle izmedju "vidjet cemo za dva-tri turnira" i "znamo danas".

STO SE NE MIJENJA
=================
Ovo je iskljucivo ANALITICKI korpus. Produkcija (`data_fetcher.tournament_form_stats`)
i dalje vuce statistiku UZIVO s API-ja i ne cita ovu datoteku. Nijedan pick se ne mijenja.
Nema nove Supabase tablice — sprema se u lokalni JSON, jer podatak sluzi jednokratnoj
odluci, a ne svakodnevnom radu.

NIKAD NE POGADJA: statistika ide kroz `get_match_stats_aligned`, koji odbija zapis ako se
poravnanje s nasim igracima ne moze dokazati po ID-u (vidi biljesku o 43% obrnutih
redoslijeda od 30.08.2026). Nedokazivi mecevi se preskacu i broje u izvjestaju.

POKRETANJE
==========
    python scripts/harvest_draw_stats.py --dry-run    # samo prebroji, bez poziva
    python scripts/harvest_draw_stats.py              # berba (nastavlja gdje je stala)
    python scripts/harvest_draw_stats.py --limit 200  # u manjim serijama
"""
import sys
import os
import io
import json
import argparse
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

import agent.data_fetcher as df
import database.supabase_client as sb

OUT_PATH = os.path.join(_ROOT, "draw_stats_harvest.json")


def _load() -> dict:
    if os.path.exists(OUT_PATH):
        try:
            return json.load(io.open(OUT_PATH, encoding="utf-8"))
        except Exception:
            print("  (postojeci harvest nije citljiv — krecem iznova)")
    return {"matches": {}, "meta": {}}


def _save(store: dict) -> None:
    with io.open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False)


def _calendar() -> dict:
    """{ime turnira: tournament_id} iz sluzbenog kalendara sezone."""
    out = {}
    for year in (2026, 2025):
        data = df._get(f"/atp/tournament/calendar/{year}")
        rows = (data or {}).get("data", data)
        if not isinstance(rows, list):
            continue
        for t in rows:
            if t.get("name") and t.get("id") and t["name"] not in out:
                out[t["name"]] = t["id"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="samo prebroji posao")
    ap.add_argument("--limit", type=int, default=0, help="najvise N novih poziva")
    args = ap.parse_args()

    rows = sb._select("analyzed_matches", select="tournament", limit=3000)
    tours = sorted({r["tournament"] for r in rows if r.get("tournament")})
    print(f"Turnira u korpusu: {len(tours)}")

    cal = _calendar()
    print(f"Kalendar sezone: {len(cal)} turnira")

    store = _load()
    have = store["matches"]
    print(f"Vec pobrano: {len(have)} meceva")

    todo = []
    for tname in tours:
        tid = cal.get(tname)
        if not tid:
            print(f"  (preskacem, nema u kalendaru) {tname}")
            continue
        raw = df._get(f"/atp/tournament/results/{tid}")
        singles = ((raw or {}).get("data") or {}).get("singles") or []
        # Oznaka runde se NE izvodi (26.09.2026): mapa rundi iz zdrijeba obrisana je iz
        # koda kad je runda postala rucni unos. K12 mjeri DUBINU (broj ranijih meceva na
        # turniru), ne oznaku; sprema se sirovi `roundId` bez tumacenja.
        for m in singles:
            if not m.get("match_winner"):
                continue
            key = f"{tid}|{m.get('player1Id')}|{m.get('player2Id')}"
            if key in have:
                continue
            todo.append((key, tid, tname, m, m.get("roundId")))

    print(f"Za obraditi: {len(todo)} meceva "
          f"(~{len(todo) * 0.67 / 60:.0f} min uz nas rate limit)")
    if args.dry_run:
        print("PRIKAZ SAMO — nijedan poziv nije napravljen.")
        return 0

    if args.limit:
        todo = todo[:args.limit]

    ok = skipped = 0
    for i, (key, tid, tname, m, rnd) in enumerate(todo, 1):
        p1, p2 = m.get("player1Id"), m.get("player2Id")
        try:
            stats, why = df.get_match_stats_aligned(tid, p1, p2)
        except Exception as e:
            stats, why = None, str(e)[:60]
        if not stats:
            skipped += 1
            have[key] = {"skipped": why}
        else:
            ok += 1
            have[key] = {
                "tournament": tname,
                "tournament_id": tid,
                "date": (m.get("date") or "")[:10],
                "round_id_raw": rnd,
                "p1_id": p1, "p2_id": p2,
                "p1_name": (m.get("player1") or {}).get("name", ""),
                "p2_name": (m.get("player2") or {}).get("name", ""),
                "winner_id": m.get("match_winner"),
                "p1_stats": stats.get("player1Stats"),
                "p2_stats": stats.get("player2Stats"),
            }
        if i % 50 == 0:
            _save(store)
            print(f"  {i}/{len(todo)} — pobrano {ok}, preskoceno {skipped}")

    store["meta"]["last_run"] = "13.09.2026 12:50"
    _save(store)
    print()
    print(f"GOTOVO. Pobrano {ok}, preskoceno {skipped} (nedokazivo poravnanje).")
    print(f"Datoteka: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
