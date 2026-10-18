# -*- coding: utf-8 -*-
"""TML forma za zadnjih 12 mjeseci — čitanje u dnevnom runu (18.10.2026 15:41).

Tablicu gradi `scripts/update_tml_form.py` (TML: glavni ždrijeb + Challengeri + kvalifikacije +
turniri u tijeku, 365 dana). U GitHub Actions se osvježava prije svakog dnevnog runa (put u
varijabli TML_FORMA_PATH); ako preuzimanje ne uspije, koristi se spremljena `config/tml_forma_12m.json`.

ŠTO JE ZA ŠTO (korisnikova odluka 18.10.2026: "pratit ćemo i jedno i drugo"):
  - bilježi se uz svaku analizu (`context_snapshot["p1_tml12"]`, `["p2_tml12"]`) USPOREDO s
    RapidAPI vrijednostima, koje su praktički zamrznuta statistika karijere;
  - Nose (u sjeni) je koristi kao svoj ulaz kad postoji za OBA igrača — iste brojke na kojima je
    provjeren u povijesnom laboratoriju;
  - prompt modela je NE vidi: pravila u promptu imaju apsolutne pragove podešene na RapidAPI skalu,
    pa bi zamjena brojki bez ponovnog podešavanja promijenila ponašanje neizmjereno (i tražila bi
    plaćeni živi poziv). To je zasebna odluka.

Pragovi za upotrebu (isti kao `b_lab.py`): ≥ 300 servisnih i ≥ 300 povratnih poena u 12 mjeseci.
"""
import json
import os
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(ROOT, "config", "tml_forma_12m.json")
MIN_POINTS = 300

_cache = {}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").replace("\xa0", " "))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().replace("-", " ").replace("'", " ").replace(".", " ").split())


def load(path: str = None) -> dict:
    """Tablica (keš po procesu). Redoslijed: argument, TML_FORMA_PATH, config datoteka. Nikad ne baca."""
    path = path or os.environ.get("TML_FORMA_PATH") or DEFAULT_PATH
    if path in _cache:
        return _cache[path]
    data = {}
    for p in (path, DEFAULT_PATH):
        try:
            with open(p, encoding="utf-8") as fh:
                data = json.load(fh)
            break
        except (OSError, ValueError):
            continue
    _cache[path] = data
    return data


def lookup(name: str, table: dict = None) -> dict:
    """Zapis igrača ili {}. Redom, uvijek samo jednoznačno:
    1. cijelo ime;
    2. iste riječi drugim redom ("Bu Yunchaokete" = "Yunchaokete Bu");
    3. sve riječi TML imena sadržane u našem, najmanje dvije ("Jaume Antoni Munar Clar" ⊇
       "Jaume Munar", "Daniel Merida Aguilar" ⊇ "Daniel Merida") — provjera 18.10.2026: bez ovoga
       3 od 161 igrača nisu nađena;
    4. prezime + prvo slovo imena."""
    table = table if table is not None else load()
    players = table.get("igraci") or {}
    k = norm(name)
    if not k:
        return {}
    if k in players:
        return players[k]
    parts = k.split()
    if len(parts) < 2:
        return {}
    toks = set(parts)
    for test in (lambda kk: set(kk.split()) == toks,
                 lambda kk: len(kk.split()) >= 2 and set(kk.split()) <= toks,
                 lambda kk: kk.split()[-1] == parts[-1] and kk.split()[0][:1] == parts[0][:1]):
        cand = [v for kk, v in players.items() if test(kk)]
        if len(cand) == 1:
            return cand[0]
        if len(cand) > 1:
            return {}
    return {}


def usable(rec: dict) -> bool:
    return bool(rec) and (rec.get("svpt") or 0) >= MIN_POINTS and (rec.get("o_svpt") or 0) >= MIN_POINTS \
        and rec.get("s") is not None and rec.get("r") is not None


def snapshot_entry(name: str, table: dict = None) -> dict:
    """Sažetak za `context_snapshot` (bilježi se uvijek, i kad je ispod praga)."""
    table = table if table is not None else load()
    rec = lookup(name, table)
    if not rec:
        return {"nadjen": False, "podaci_do": table.get("podaci_do")}
    keep = ("n", "n_main", "n_ch", "n_q", "svpt", "o_svpt", "s", "r", "w1", "w2", "r1", "hold",
            "ace_sg", "bps", "zadnji")
    out = {k: rec.get(k) for k in keep}
    out.update({"nadjen": True, "upotrebljiv": usable(rec), "podaci_do": table.get("podaci_do")})
    return out
