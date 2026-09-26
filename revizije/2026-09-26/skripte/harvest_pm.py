# -*- coding: utf-8 -*-
"""Revizija 26.09.2026 — berba `/atp/player/past-matches/{id}` S KVOTAMA (odd1/odd2).

Samo CITANJE s API-ja u lokalni kes (.cache/rev2609/pm/<id>.json). Nista se ne upisuje u bazu.
Nastavlja gdje je stala (preskace igrace koji vec imaju datoteku).
Zasto: tri korisnikove ideje (tablica promasaja po igracu, povijest poraza na turniru,
sekvenca protivnika) traze povijest s CIJENOM za stotine igraca, ne samo nasih ~450 pickova.
"""
import os, sys, json, time, threading
from concurrent.futures import ThreadPoolExecutor

ROOT = r"C:\Users\jovin\Desktop\Tenis Claude"
sys.path.insert(0, ROOT)
from agent import data_fetcher as df

OUT = os.path.join(ROOT, ".cache", "rev2609", "pm")
os.makedirs(OUT, exist_ok=True)
MIN_DATE = "2023-06-01"
MAX_PAGES = 4


def ids():
    am = json.load(open(os.path.join(ROOT, ".cache/rev2609/data/analyzed_matches.json"), encoding="utf-8"))
    s = set()
    for r in am:
        for k in ("player1_id", "player2_id"):
            if r.get(k):
                s.add(str(r[k]))
    pbn = os.path.join(ROOT, ".cache/player_context/pid_by_name.json")
    if os.path.exists(pbn):
        for v in json.load(open(pbn, encoding="utf-8")).values():
            if v:
                s.add(str(v))
    d = json.load(open(os.path.join(ROOT, "draw_stats_harvest.json"), encoding="utf-8"))["matches"]
    for v in d.values():
        if "Challenger" in v["tournament"]:
            continue
        s.add(str(v["p1_id"])); s.add(str(v["p2_id"]))
    return sorted(s)


lock = threading.Lock()
done = [0]


def one(pid):
    path = os.path.join(OUT, f"{pid}.json")
    if os.path.exists(path):
        return
    allg, ok = [], True
    for page in range(1, MAX_PAGES + 1):
        data = df._get(f"/atp/player/past-matches/{pid}", params=({"pageNo": page} if page > 1 else None))
        if data is None:
            ok = False
            break
        raw = data.get("data", data.get("result", data))
        games = raw if isinstance(raw, list) else []
        allg.extend(games)
        if not data.get("hasNextPage") or not games:
            break
        if min(str(g.get("date", ""))[:10] for g in games) < MIN_DATE:
            break
    if ok:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(allg, f, ensure_ascii=False)
    with lock:
        done[0] += 1
        if done[0] % 20 == 0:
            print(f"  {done[0]} igraca", flush=True)


if __name__ == "__main__":
    L = ids()
    print("igraca:", len(L), flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(one, L))
    print(f"gotovo za {time.time()-t0:.0f}s; datoteka: {len(os.listdir(OUT))}", flush=True)
