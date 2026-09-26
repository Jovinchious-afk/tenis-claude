# -*- coding: utf-8 -*-
"""Backfill triju igracevih varijabli za SVE nase dosadasnje analize (26.09.2026 17:04).

Korisnikov zahtjev: omjer protiv ljevaka/desnjaka, broj ATP pobjeda u sezoni i broj Grand
Slam polufinala/finala moraju postojati za svaki mec koji smo ikad analizirali, "da se
biljezi, jer iz toga mozemo dosta saznati i prediktirati". Vrijednosti racuna ISTI kod
kao dnevni run (`agent/player_context.py`), i to NA DAN MECA — ne danasnje stanje.

KORACI (svaki se moze ponoviti; dohvat nastavlja gdje je stao):
    python scripts/backfill_player_context.py --collect   # API -> .cache/player_context/
    python scripts/backfill_player_context.py --hands     # -> player_hands.json (u repozitorij)
    python scripts/backfill_player_context.py --compute   # vrijednosti po retku + pokrivenost
    python scripts/backfill_player_context.py --apply     # upis u analyzed_matches.context_snapshot

UPIS JE SAMO DODAVANJE: u `context_snapshot` dodaju se `p1_ctx`, `p2_ctx` i
`player_ctx_version`; nijedno postojece polje se ne dira, a redak koji vec ima vrijednost
iz dnevnog runa (`source: "live"`) se preskace.

KES NIJE U TEMP-u: prvi pokusaj 26.09.2026 izgubio je ~500 poziva kad je Windows ocistio
privremeni direktorij usred rada. Zato `.cache/` u projektu (git ga ignorira).
"""
import sys
import os
import io
import json
import argparse
import datetime
import time
import concurrent.futures as cf

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace",
                              line_buffering=True)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from agent import data_fetcher as df          # noqa: E402
from agent import player_context as pc        # noqa: E402
from database import supabase_client as sb    # noqa: E402

CACHE = os.path.join(_ROOT, ".cache", "player_context")
os.makedirs(CACHE, exist_ok=True)
F_ROWS = os.path.join(CACHE, "analyzed_matches.json")
F_HIST = os.path.join(CACHE, "history.json")
F_PROF = os.path.join(CACHE, "profiles.json")
F_GS = os.path.join(CACHE, "gs_records.json")
F_PID = os.path.join(CACHE, "pid_by_name.json")
F_VALUES = os.path.join(CACHE, "values.json")

# Pocetni datumi Grand Slamova 2026 iz `/atp/tournament/calendar/2026` (26.09.2026).
# Za ranije godine vrijedi procjena u `pc.gs_end_date` (sve su ionako prije korpusa).
GS_TIDS_2026 = {"AO": "21305", "RG": "21329", "WIM": "21337", "USO": "21349"}
GS_STARTS = {("AO", 2026): "2026-01-19", ("RG", 2026): "2026-05-25",
             ("WIM", 2026): "2026-06-29", ("USO", 2026): "2026-08-31"}
WORKERS = 6       # API dopusta 3000/min (zaglavlje x-ratelimit-limit); 6 niti je ~15/s
GS_WORKERS = 3    # `tournament-record` pod 6 niti prekida veze (26.09.2026 18:20)


def _load(p, default):
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    return default


def _save(p, d):
    tmp = p + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False)
    os.replace(tmp, p)


def _fetch_rows():
    out, off = [], 0
    while True:
        rows = sb._rest("GET", "analyzed_matches", params={
            "select": "id,match_date,player1,player2,player1_id,player2_id,tournament,"
                      "tournament_level,surface,round,predicted_winner,predicted_confidence,"
                      "bookmaker_odds_p1,bookmaker_odds_p2,actual_winner,prediction_correct,"
                      "context_snapshot",
            "order": "match_date.asc", "offset": str(off), "limit": "1000"})
        out += rows
        if len(rows) < 1000:
            return out
        off += 1000


def _row_pids(rows, pid_by_name):
    """(row_id, 'p1'/'p2') -> player_id. ID iz retka; inace po imenu iz drugih redaka;
    inace iz ATP ranking liste (top 500)."""
    by_name = {}
    for r in rows:
        for s in ("1", "2"):
            if r.get(f"player{s}_id") and r.get(f"player{s}"):
                by_name[df._norm_key(r[f"player{s}"])] = str(r[f"player{s}_id"])
    out = {}
    for r in rows:
        for s in ("1", "2"):
            name = r.get(f"player{s}") or ""
            pid = str(r.get(f"player{s}_id") or "") or by_name.get(df._norm_key(name), "")
            if not pid and name:
                if name not in pid_by_name:
                    pid_by_name[name] = df.find_player_id(name) or ""
                pid = pid_by_name[name]
            out[(r["id"], f"p{s}")] = pid
    return out


def _slim(g):
    t = g.get("tournament") or {}
    return {"date": str(g.get("date", ""))[:10], "p1": str(g.get("player1Id")),
            "p2": str(g.get("player2Id")), "w": str(g.get("match_winner") or ""),
            "rank": t.get("rankId"), "rid": g.get("roundId")}


def collect():
    df._MIN_CALL_INTERVAL = 0.0
    rows = _fetch_rows()
    _save(F_ROWS, rows)
    print(f"analyzed_matches: {len(rows)} redaka")
    pid_by_name = _load(F_PID, {})
    pids = _row_pids(rows, pid_by_name)
    _save(F_PID, pid_by_name)
    earliest = {}
    for (rid, side), pid in pids.items():
        if not pid:
            continue
        d = next(r["match_date"] for r in rows if r["id"] == rid)
        earliest[pid] = min(earliest.get(pid, d), d)
    missing = sorted({next(r[f"player{side[1]}"] for r in rows if r["id"] == rid)
                      for (rid, side), pid in pids.items() if not pid})
    print(f"igraca s ID-em: {len(earliest)} | bez ID-a: {len(missing)} {missing[:12]}")

    # 1) povijest: stranice dok ne pokriju 2 godine + 10 dana prije najranije analize
    hist = _load(F_HIST, {})

    def _hist(pid):
        cutoff = (datetime.date.fromisoformat(earliest[pid])
                  - datetime.timedelta(days=pc.VS_HAND_WINDOW_DAYS + 10)).isoformat()
        out = []
        for page in range(1, 9):
            data = df._get(f"/atp/player/past-matches/{pid}",
                           params=({"pageNo": page} if page > 1 else None))
            games = (data or {}).get("data") or []
            out += [_slim(g) for g in games]
            if not games or not data.get("hasNextPage") or str(games[-1].get("date", ""))[:10] < cutoff:
                break
        return pid, out

    todo = [p for p in earliest if p not in hist]
    print(f"povijest: {len(todo)} igraca")
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for i, (pid, out) in enumerate(ex.map(_hist, todo), 1):
            hist[pid] = out
            if i % 25 == 0:
                _save(F_HIST, hist)
                print(f"  povijest {i}/{len(todo)}")
    _save(F_HIST, hist)

    # 2) profili (ruka): svi nasi igraci + svi protivnici iz njihove povijesti
    prof = _load(F_PROF, {})
    need = set(earliest)
    for pid, ms in hist.items():
        for m in ms:
            need.update((m["p1"], m["p2"]))
    todo = sorted(p for p in need if p and p != "None" and p not in prof)
    print(f"profili: {len(todo)}")

    def _prof(pid):
        info = df.get_player_info(pid)
        return pid, {"name": info.get("name", ""), "plays": info.get("plays", "")}

    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for i, (pid, v) in enumerate(ex.map(_prof, todo), 1):
            prof[pid] = v
            if i % 100 == 0:
                _save(F_PROF, prof)
                print(f"  profili {i}/{len(todo)}")
    _save(F_PROF, prof)

    # 3) Grand Slam zapis po godini (4 poziva po igracu)
    # NEUSPJEH != PRAZNO (26.09.2026 18:20): pod 6 paralelnih niti API je poceo prekidati
    # veze, a `_get` nakon tri pokusaja vraca None — sto je prva verzija spremala kao PRAZNU
    # listu, dakle "igrac nema nijedan nastup na Slamu". Isti obrazac kao tihi null kljucevi.
    # Sada se igrac sprema tek kad SVA cetiri poziva vrate odgovor (`_ok`), a zapisi bez te
    # oznake koji imaju prazan Slam dohvacaju se ponovno.
    gs = _load(F_GS, {})

    def _suspect(rec):
        return not rec.get("_ok") and any(not rec.get(k) for k in GS_TIDS_2026)

    todo = [p for p in earliest if p not in gs or _suspect(gs[p])]
    print(f"GS zapisi: {len(todo)} igraca")

    def _gs(pid):
        rec = {}
        for key, tid in GS_TIDS_2026.items():
            data = None
            for attempt in range(4):
                data = df._get(f"/atp/player/tournament-record/{pid}/{tid}")
                if data is not None:
                    break
                time.sleep(5 * (attempt + 1))
            if data is None:
                return pid, None
            rec[key] = data.get("data") or []
        rec["_ok"] = True
        return pid, rec

    failed = 0
    with cf.ThreadPoolExecutor(GS_WORKERS) as ex:
        for i, (pid, rec) in enumerate(ex.map(_gs, todo), 1):
            if rec is None:
                failed += 1
            else:
                gs[pid] = rec
            if i % 25 == 0:
                _save(F_GS, gs)
                print(f"  GS {i}/{len(todo)} (neuspjelih {failed})")
    _save(F_GS, gs)
    print(f"DOHVAT GOTOV. GS neuspjelih: {failed} (ponovi --collect za njih).")


def write_hands():
    prof = _load(F_PROF, {})
    hands = {pid: pc.hand_code(v.get("plays")) for pid, v in prof.items()
             if v.get("name")}          # bez imena = neuspio dohvat, ne upisuje se
    known = {k: v for k, v in hands.items() if v}
    # Igraci kojima API NE ZNA ruku upisuju se s "" — inace bi ih `pc.hand_of` u svakom
    # dnevnom runu ponovno dohvacao (do stropa od 150 poziva) i ponovno dobio prazno.
    with open(pc.HANDS_FILE, "w", encoding="utf-8") as fh:
        json.dump(dict(sorted(hands.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0)),
                  fh, ensure_ascii=False, indent=0)
    n_l = sum(1 for v in known.values() if v == "L")
    print(f"player_hands.json: {len(hands)} igraca, od toga {len(known)} poznate ruke, "
          f"ljevaka {n_l} ({100 * n_l / max(1, len(known)):.1f}%)")


def compute():
    rows = _load(F_ROWS, [])
    hist = _load(F_HIST, {})
    gs = _load(F_GS, {})
    prof = _load(F_PROF, {})
    hands = {pid: pc.hand_code(v.get("plays")) for pid, v in prof.items()}
    pids = _row_pids(rows, _load(F_PID, {}))
    values, cov = {}, {"rows": 0, "both": 0, "unknown_share": []}
    for r in rows:
        as_of = r["match_date"]
        p = {s: pids.get((r["id"], s), "") for s in ("p1", "p2")}
        rec = {}
        for s, o in (("p1", "p2"), ("p2", "p1")):
            pid, oid = p[s], p[o]
            if not pid or pid not in hist:
                continue
            vs = pc.vs_hand_record(hist[pid], pid, hands, as_of, oid)
            rec[f"{s}_ctx"] = {
                "hand": hands.get(pid, ""),
                "opp_hand": hands.get(oid, "") if oid else "",
                "season": pc.season_record(hist[pid], pid, as_of, oid),
                "vs_hand": vs,
                "gs": pc.gs_record(gs.get(pid) or {}, as_of, GS_STARTS),
                "source": "backfill",
            }
            n = vs["L"]["w"] + vs["L"]["l"] + vs["R"]["w"] + vs["R"]["l"] + vs["unknown"]
            if n:
                cov["unknown_share"].append(vs["unknown"] / n)
        cov["rows"] += 1
        cov["both"] += ("p1_ctx" in rec and "p2_ctx" in rec)
        if rec:
            values[r["id"]] = rec
    _save(F_VALUES, values)
    us = cov["unknown_share"]
    print(f"izracunato: {len(values)} redaka od {cov['rows']} (oba igraca: {cov['both']}); "
          f"prosjecni udio protivnika nepoznate ruke {100 * sum(us) / max(1, len(us)):.1f}%")


def apply():
    values = _load(F_VALUES, {})
    # SVJEZE citanje neposredno prije upisa: `context_snapshot` se upisuje CIJELI, pa bi
    # snimka iz --collect (koja moze biti stara satima) prepisala sve sto se u medjuvremenu
    # promijenilo u retku.
    rows = {r["id"]: r for r in _fetch_rows()}
    done = skipped = 0
    for rid, rec in values.items():
        snap = (rows.get(rid) or {}).get("context_snapshot") or {}
        if (snap.get("p1_ctx") or {}).get("source") == "live":
            skipped += 1
            continue
        new = {**snap, **rec, "player_ctx_version": 1}
        sb._rest("PATCH", "analyzed_matches", params={"id": f"eq.{rid}"},
                 body={"context_snapshot": new}, prefer="return=minimal")
        done += 1
        if done % 100 == 0:
            print(f"  upisano {done}")
    print(f"UPISANO {done} redaka, preskoceno {skipped} (vec imaju vrijednost iz dnevnog runa).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--hands", action="store_true")
    ap.add_argument("--compute", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.collect:
        collect()
    if a.hands:
        write_hands()
    if a.compute:
        compute()
    if a.apply:
        apply()
    if not any(vars(a).values()):
        ap.print_help()
