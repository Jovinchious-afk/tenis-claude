# -*- coding: utf-8 -*-
"""Usporedba starog i novog ELO podudaranja imena (04.10.2026 19:11).

Za svih igrača iz analyzed_matches usporedi:
  (a) staro podudaranje (find_player_elo iz git HEAD) naspram novog — na ISTOM (novom) kešu;
  (b) stari keš (get_elo_cache iz git HEAD: 1.000 redaka, NBSP duplikati) naspram novog.
Ispisuje svakog igrača kojemu se vraćeni ELO promijenio, da se svaka promjena ručno provjeri.
Samo čita Supabase.
"""
import io
import json
import os
import subprocess
import sys
import types
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(ROOT, ".env"))
from database import supabase_client as db  # noqa: E402
from agent import data_fetcher as dfm  # noqa: E402


def old_module(path, name):
    src = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8").stdout
    mod = types.ModuleType(name)
    mod.__dict__["__file__"] = os.path.join(ROOT, path)
    exec(compile(src, name, "exec"), mod.__dict__)
    return mod


def quiet(fn, *a):
    with redirect_stdout(io.StringIO()):
        return fn(*a)


def main():
    old_df = old_module("agent/data_fetcher.py", "old_df")
    old_db = old_module("database/supabase_client.py", "old_db")
    new_cache = db.get_elo_cache()
    old_cache = old_db.get_elo_cache()
    print(f"keš: stari čitač {len(old_cache)} ključeva | novi čitač {len(new_cache)} ključeva")
    am = json.load(open(os.path.join(ROOT, ".cache", "rev_2026-10-04", "analyzed_matches.json"), encoding="utf-8"))
    names = sorted({r[k] for r in am for k in ("player1", "player2") if r.get(k)})
    print(f"igrača: {len(names)}")
    ch_match, ch_cache = [], []
    miss_old = miss_new = 0
    for nm in names:
        a = quiet(old_df.find_player_elo, nm, new_cache)
        b = quiet(dfm.find_player_elo, nm, new_cache)
        c = quiet(old_df.find_player_elo, nm, old_cache)
        miss_old += a.get("elo_overall") == 1500
        miss_new += b.get("elo_overall") == 1500
        if (a.get("elo_overall"), a.get("elo_hard")) != (b.get("elo_overall"), b.get("elo_hard")):
            ch_match.append((nm, a, b))
        if (c.get("elo_overall"), c.get("elo_hard")) != (b.get("elo_overall"), b.get("elo_hard")):
            ch_cache.append((nm, c, b))
    print(f"promašaji (1500) na novom kešu: staro podudaranje {miss_old} | novo {miss_new}")
    print(f"\n(a) PROMJENA ZBOG PODUDARANJA ({len(ch_match)}): ime -> staro / novo (ukupni, hard)")
    for nm, a, b in ch_match:
        def who(v):
            for k, x in new_cache.items():
                if x is v or (x.get("elo_overall"), x.get("elo_hard")) == (v.get("elo_overall"), v.get("elo_hard")):
                    return k
            return "zadani 1500"
        print(f"  {nm:32s} {a['elo_overall']}/{a['elo_hard']} ({who(a)})  ->  {b['elo_overall']}/{b['elo_hard']} ({who(b)})")
    top = sorted(ch_cache, key=lambda x: -abs(x[1]['elo_overall'] - x[2]['elo_overall']))[:12]
    print("\n  najveći pomaci zbog keša (ukupni / hard):")
    for nm, c, b in top:
        print(f"    {nm:30s} {c['elo_overall']}/{c['elo_hard']}  ->  {b['elo_overall']}/{b['elo_hard']}")
    diffs = sorted(abs(c['elo_overall'] - b['elo_overall']) for _, c, b in ch_cache)
    print(f"\n(b) PROMJENA ZBOG KEŠA (stari čitač + staro podudaranje -> novo): {len(ch_cache)} igrača; "
          f"medijan pomaka {diffs[len(diffs)//2] if diffs else 0:.1f}, najveći {max(diffs) if diffs else 0:.1f}")


if __name__ == "__main__":
    main()
