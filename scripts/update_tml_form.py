# -*- coding: utf-8 -*-
"""Forma iz TML-a za zadnjih 12 mjeseci: servis, povrat, hold, asovi (18.10.2026 15:39).

ZAŠTO: RapidAPI servis/povrat koji model dobiva je praktički ZAMRZNUTA STATISTIKA KARIJERE (revizija
18.10.2026, kritičar): vrijednosti se ne miču, poklapaju se s TML karijerom, a povrat je napuhan
~4,7pp. Korisnik je odobrio (18.10.2026) da se uz to prati i TML za zadnjih 12 mjeseci — "pratit
ćemo i jedno i drugo". Ova skripta gradi tu tablicu; `agent/tml_forma.py` je čita u dnevnom runu.
Nose (u sjeni) je koristi kao svoj ulaz jer je na istim brojkama provjeren na povijesti; prompt
modela je NE vidi (pravila u promptu imaju pragove podešene na RapidAPI skalu).

Izvor: stats.tennismylife.org (TML, nekomercijalna licenca; za razliku od tennis-data.co.uk smije
se preuzimati automatski). Bez API ključa i bez troška. Uzima glavni ždrijeb, Challengere i
kvalifikacije (isto kao povijesni laboratorij) te turnire u tijeku.

    python scripts/update_tml_form.py                    # iz lokalnog .cache/tml (+ .cache/tml_tijek)
    python scripts/update_tml_form.py --preuzmi          # prvo preuzmi svježe datoteke (GitHub Actions)
    python scripts/update_tml_form.py --izlaz=put.json   # drugi izlaz (zadano config/tml_forma_12m.json)

Zapisuje samo zbrojeve po igraču (bez sirovih mečeva). Korisnik odlučuje o upotrebi u promptu.
"""
import datetime as _dt
import json
import os
import sys
import unicodedata
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TML_DIR = os.path.join(ROOT, ".cache", "tml")
TIJEK_DIR = os.path.join(ROOT, ".cache", "tml_tijek")
OUT = os.path.join(ROOT, "config", "tml_forma_12m.json")
BASE = "https://stats.tennismylife.org/data/"
DAYS = 365
MIN_MATCHES = 3          # u datoteku ulazi igrač s barem 3 meča sa statistikom; prag za upotrebu je u tml_forma.py


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().replace("-", " ").replace("'", " ").replace(".", " ").split())


def _files(year: int) -> list:
    out = []
    for y in (year - 1, year):
        out += [(f"{y}.csv", "main"), (f"{y}_challenger.csv", "ch"), (f"atp_quali/{y}_atp_quali.csv", "q")]
    out += [("ongoing_tourneys.csv", "main"), ("challenger_ongoing_tourneys.csv", "ch")]
    return out


def download(dest: str, year: int) -> list:
    """Preuzmi datoteke u `dest` (nova mapa). Vraća popis (put, razina) za one koje su stigle.
    `requests` (ima vlastite certifikate preko certifi) — `urllib` na Windowsu padne na TLS provjeri."""
    import requests
    got = []
    for name, src in _files(year):
        path = os.path.join(dest, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            resp = requests.get(BASE + name, timeout=60)
            resp.raise_for_status()
            data = resp.content
            if not data.startswith(b"tourney_id"):
                print(f"  {name}: neočekivan sadržaj, preskačem")
                continue
            with open(path, "wb") as fo:
                fo.write(data)
            got.append((path, src))
            print(f"  preuzeto {name} ({len(data) // 1024} KB)")
        except Exception as e:  # noqa: BLE001
            print(f"  {name}: nije preuzeto ({str(e)[:60]})")
    return got


def local(year: int) -> list:
    got = []
    for name, src in _files(year):
        for base in (TML_DIR, TIJEK_DIR):
            path = os.path.join(base, name)
            if os.path.exists(path):
                got.append((path, src))
                break
    return got


def build(paths: list, ref: _dt.date) -> dict:
    import csv
    lo = ref - _dt.timedelta(days=DAYS)
    acc = defaultdict(lambda: defaultdict(float))
    names, last, seen = {}, {}, set()
    data_to = None
    def num(x):
        """Broj ili None; TML ima i pokvarenih vrijednosti (npr. '4y') — takav meč je bez statistike."""
        try:
            return float(x) if x not in (None, "") else None
        except ValueError:
            return None
    for path, src in paths:
        with open(path, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                try:
                    d = _dt.datetime.strptime(str(r.get("tourney_date") or "")[:8], "%Y%m%d").date()
                except ValueError:
                    continue
                if not (lo < d <= ref):
                    continue
                key = (r.get("tourney_id"), r.get("winner_id"), r.get("loser_id"), r.get("round"))
                if key in seen:          # turnir u tijeku kasnije dođe i u godišnju datoteku
                    continue
                seen.add(key)
                data_to = max(data_to, d) if data_to else d
                cols = ("svpt", "1stIn", "1stWon", "2ndWon", "SvGms", "bpSaved", "bpFaced", "ace", "df")
                w = [num(r.get(f"w_{c}")) for c in cols]
                l_ = [num(r.get(f"l_{c}")) for c in cols]
                ok = None not in w and None not in l_ and w[0] > 0 and l_[0] > 0 and w[4] > 0 and l_[4] > 0
                for pid, nm, me, op in ((r.get("winner_id"), r.get("winner_name"), w, l_),
                                        (r.get("loser_id"), r.get("loser_name"), l_, w)):
                    if not pid:
                        continue
                    names[pid] = nm
                    last[pid] = max(last.get(pid, d), d)
                    a = acc[pid]
                    a["n_all"] += 1
                    if not ok:
                        continue
                    a["n"] += 1
                    a[f"n_{src}"] += 1
                    for c, v in zip(cols, me):
                        a[c] += v
                    a["o_svpt"] += op[0]
                    a["o_1stIn"] += op[1]
                    a["o_won"] += op[2] + op[3]
                    a["o_1stWon"] += op[2]
    players = {}
    for pid, a in acc.items():
        if a["n"] < MIN_MATCHES:
            continue
        sv, osv, sg = a["svpt"], a["o_svpt"], a["SvGms"]
        rec = {"name": names[pid], "id": pid, "n": int(a["n"]), "n_main": int(a["n_main"]),
               "n_ch": int(a["n_ch"]), "n_q": int(a["n_q"]), "svpt": int(sv), "o_svpt": int(osv),
               "zadnji": last[pid].isoformat(),
               "s": round((a["1stWon"] + a["2ndWon"]) / sv, 4) if sv else None,
               "r": round(1 - a["o_won"] / osv, 4) if osv else None,
               "w1": round(a["1stWon"] / a["1stIn"], 4) if a["1stIn"] else None,
               "w2": round(a["2ndWon"] / (sv - a["1stIn"]), 4) if (sv - a["1stIn"]) > 0 else None,
               "r1": round(1 - a["o_1stWon"] / a["o_1stIn"], 4) if a["o_1stIn"] else None,
               "hold": round(1 - (a["bpFaced"] - a["bpSaved"]) / sg, 4) if sg else None,
               "ace_sg": round(a["ace"] / sg, 4) if sg else None,
               "bps": round(a["bpSaved"] / a["bpFaced"], 4) if a["bpFaced"] else None}
        k = norm(names[pid])
        if k in players and players[k]["n"] >= rec["n"]:
            continue
        players[k] = rec
    return {"izvor": "TML (stats.tennismylife.org), glavni ždrijeb + Challengeri + kvalifikacije + turniri u tijeku",
            "prozor_dana": DAYS, "na_dan": ref.isoformat(), "podaci_do": data_to.isoformat() if data_to else None,
            "napravljeno": _dt.datetime.now().strftime("%d.%m.%Y %H:%M"), "igraca": len(players), "igraci": players}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    out = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--izlaz=")), OUT)
    today = _dt.date.today()
    if "--preuzmi" in sys.argv:
        import tempfile
        dest = tempfile.mkdtemp(prefix="tml_")
        paths = download(dest, today.year)
    else:
        paths = local(today.year)
    if not paths:
        print("Nema TML datoteka — tablica NIJE osvježena (ostaje zadnja spremljena).")
        sys.exit(1)
    res = build(paths, today)
    with open(out, "w", encoding="utf-8") as fo:
        json.dump(res, fo, ensure_ascii=False, separators=(",", ":"))
    print(f"TML forma 12 mj.: {res['igraca']} igrača, podaci do {res['podaci_do']} -> {out}")


if __name__ == "__main__":
    main()
