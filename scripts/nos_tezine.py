# -*- coding: utf-8 -*-
"""Nos uči: težine znakova za nos-odluku iz naših riješenih pickova (08.11.2026 12:34).

Korisnikova odluka 08.11.2026: nos (Nose + nos-ploča + scouting) dobiva pravo odluke pri slaganju
tiketa. Ova skripta je "učenje": iz zadnjih `nos_odluka.PROZOR_DANA` dana riješenih analiza računa
koliko je svaki znak dosad pomogao ili odmogao naspram cijene i zapisuje težine. Pravila učenja su u
`agent/nos_odluka.nauci` (skupljanje prema nuli, predznak iz definicije znaka, strop). Samo čita bazu.

    python scripts/nos_tezine.py                     # zapiše config/nos_tezine.json i ispiše tablicu
    python scripts/nos_tezine.py --izlaz=put.json    # drugi izlaz (GitHub Actions: $RUNNER_TEMP)
    python scripts/nos_tezine.py --suho              # samo ispis
"""
import datetime as _dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except ImportError:
    pass

from agent import nos_odluka as no  # noqa: E402
from database import supabase_client as db  # noqa: E402


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    out = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--izlaz=")), no.TEZINE_PATH)
    danas = _dt.date.today().isoformat()
    od = (_dt.date.today() - _dt.timedelta(days=no.PROZOR_DANA + 1)).isoformat()
    rows = db.get_rows_for_nos_odluka(od)
    primjeri = no.primjeri_iz_redaka(rows)
    t = no.nauci(primjeri, danas=danas)
    if not t.get("n_pickova"):
        print("Nos uči: nema riješenih pickova u prozoru — težine NISU zapisane (ostaje zadnja datoteka).")
        sys.exit(1)
    print(f"Nos uči ({no.VERSION}): {t['n_pickova']} riješenih pickova {t['prozor']['od']} – {t['prozor']['do']}; "
          f"K={no.K_SKUPLJANJE:.0f}, strop {no.STROP_ZNAK:.0f}/{no.STROP_UKUPNO:.0f} boda")
    print(f"  {'znak':44s} {'vrsta':8s} {'n':>4s} {'učinak':>8s} {'težina':>7s}")
    for sid, z in sorted(t["znakovi"].items(), key=lambda kv: -abs(kv[1]["tezina_pp"])):
        u = "—" if z["ucinak_pp"] is None else f"{z['ucinak_pp']:+.1f}pp"
        print(f"  {z['oznaka'][:44]:44s} {z['vrsta']:8s} {z['n']:4d} {u:>8s} {z['tezina_pp']:+6.2f}")
    if "--suho" in sys.argv:
        return
    with open(out, "w", encoding="utf-8") as fo:
        json.dump(t, fo, ensure_ascii=False, indent=1)
    print(f"  -> {out}")


if __name__ == "__main__":
    main()
