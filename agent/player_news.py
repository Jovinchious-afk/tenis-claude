# -*- coding: utf-8 -*-
"""Vijesti po igraču s Google News RSS-a — SAMO BILJEŽENJE (27.09.2026 11:52).

ZAŠTO: kanal vijesti (`data_fetcher.get_atp_injury_news`, ESPN/BBC) od 13.09.2026 nije dao
nijednu vijest o igraču kojeg analiziramo (0 od 43 analize) — ti izvori pišu o vrhu tablice.
Google News pretraga po IMENU igrača (besplatno, bez ključa) vratila je 27.09.2026 za Machača
50+ članaka, među njima i vijest o ozljedi stopala s Roland-Garrosa. Bez izvora po imenu K13
(vijesti o ozljedama, DECISION_INPUTS) nema što mjeriti.

ŠTO RADI: za igrača dohvati naslove iz zadnjih 14 dana prije meča i označi one s riječima o
ozljedi ili odustajanju. Rezultat ide SAMO u `context_snapshot` (`p1_gnews` / `p2_gnews`,
`context_version` 23).

MODEL TO NE VIDI — i to je namjerno: ključ u podacima igrača je `gnews`, a prompt čita samo
`news`. Pravilo uz `_NEWS_EXCLUDE` vrijedi i ovdje: čim tekst o kvotama ili "favoritu" uđe u
prompt, model prestaje biti neovisan o tržištu i ruše se i bonus za konsenzus i mjerenja.
U odluku ovo ulazi tek nakon mjerenja K13 i korisnikova odobrenja.

NEUSPJEH NIJE "PRAZNO": ako Google ne odgovori, zapis je {"error": ...} (a ne {"n": 0}), da se
"nema vijesti" i "nismo dobili odgovor" nikad ne pomiješaju. Dnevni run ide dalje u oba slučaja.
"""
import datetime as _dt
import email.utils as _eu
import re
import threading
import urllib.parse
import xml.etree.ElementTree as ET

import requests

_URL = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; tenis-claude/1.0)"}
_TIMEOUT = 8
_DAYS = 14
_MAX_ITEMS = 8

# Riječi o ozljedi / odustajanju, kao CIJELE riječi: "pain" ne smije pogoditi "Spain", "ill"
# ne smije pogoditi "will". Namjerno bez "back", "recover", "setback" — preširoko u teniskim
# naslovima ("comes back", "recovers from a set down").
# IZMJERENO 25.10.2026 11:21 (revizija 25.10., točka 8; samo komentar): na Lyonu/Bruxellesu/
# Almatyju od 15 oznaka stvarne fizičke su samo 3–5. Ostalo su "retir\w*" kao umirovljenje karijere
# (Wawrinka, Monfils), "walkover"/"withdr\w*" tuđeg igrača i tuđa ozljeda u naslovu (Alcaraz).
# Zato je grupa K13 (21 od 40) zagađena. Prijedlog P2 (čeka "provedi"): fizičke riječi + prezime
# igrača u naslovu, bez umirovljenja karijere; pravilo zapisano unaprijed, K13b broji od tog dana.
_INJURY_RE = re.compile(
    r"\b(injur\w*|withdr\w*|pull(?:s|ed|ing)? out|retir\w*|illness|ill|sick\w*|blister\w*|"
    r"strain\w*|sprain\w*|tear|torn|surgery|fitness|doubtful|pain|cramp\w*|medical|"
    r"hamstring|abdominal|ankle|knee|wrist|shoulder|elbow|ruled out|walkover)\b",
    re.IGNORECASE)

# ── STROŽI DETEKTOR OZLJEDA v2 (25.10.2026 11:39, revizija 25.10., P2) ───────────────────────
# Stari `_INJURY_RE` ostaje NETAKNUT (K13 se mjeri točno kako je zapisan 27.09.). Uz njega se od
# danas bilježi i `inj2` / `injury_n2` (oznaka `inj_v: 2`) — pravilo zapisano PRIJE ijednog
# podatka iz njega (DECISION_INPUTS K13b):
#   1. riječ o tijelu/bolesti (_PHYS_RE) mora stajati najviše _NEAR riječi od PREZIMENA igrača u
#      naslovu (s bilo koje strane); riječ o odustajanju (_OUT_RE, retire) samo IZA prezimena
#      ("X withdraws", "X's withdrawal") — "Draperovo povlačenje daje Filsu prvog nositelja" ne
#      broji se Filsu (tuđa ozljeda u istom naslovu se ne broji); "walkover" se ne broji (dobiva ga
#      i protivnik);
#   2. "retire/retirement/retiring" broji se SAMO uz riječ meča (semi, final, match, set, hurt...),
#      a nikad uz umirovljenje karijere (_CAREER_RE: farewell, from tennis, ahead of retirement...);
#   3. kladioničarski naslovi ne broje se (isti `_NEWS_EXCLUDE` kao prompt).
# Primjeri koji su odredili pravilo (Lyon/Bruxelles/Almaty, 19.–25.10.2026): "Alexander Bublik
# retires suddenly as semi-final..." DA; "Corentin Moutet battles through cramps" DA; "Stan Wawrinka
# ... ahead of retirement in Basel" NE; "Carlos Alcaraz reveals how Stan Wawrinka helped him ...
# with a wrist injury" NE (za Wawrinku); "Medvedev into Almaty final after Bublik retirement" NE za
# Medvedeva, DA za Bublika. MODEL OVO NE VIDI (ključ `gnews`).
_PHYS_RE = re.compile(
    r"^(injur\w*|hurt|pain|cramp\w*|blister\w*|strain\w*|sprain\w*|tear|torn|surgery|illness|ill|"
    r"sick\w*|fever|virus|hamstring|abdominal|ankle|knee|wrist|shoulder|elbow|hip|foot|calf|thigh|"
    r"groin|medical|physio\w*)$")   # bez "treatment": "special treatment" (Medvedev, 23.10.) nije ozljeda
_OUT_RE = re.compile(r"^(withdr\w*|pull(?:s|ed|ing)?|ruled)$")
_RETIRE_RE = re.compile(r"^(retire[sd]?|retirement|retiring)$")
_MATCH_CTX_RE = re.compile(r"\b(semi\w*|quarter\w*|final|match|set|hurt|injur\w*|mid-match|opener|"
                           r"tiebreak|game)\b", re.IGNORECASE)
_CAREER_RE = re.compile(r"(from tennis|farewell|final season|last tournament|last event|career|"
                        r"ahead of (?:his )?retirement|announces? (?:his )?retirement|retirement plans|"
                        r"retirement tour|penultimate|swansong|before retiring|retire from)", re.IGNORECASE)
_NEAR = 4


def _fold(text: str) -> str:
    """Mala slova bez dijakritika (Đoković -> djokovic), da se prezime nađe u engleskom naslovu."""
    import unicodedata
    t = (text or "").replace("đ", "dj").replace("Đ", "Dj")
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def _surnames(name: str) -> set:
    """Zadnja riječ imena; uz 4+ riječi i predzadnja (npr. "Jaume Antoni Munar Clar" -> munar, clar)."""
    toks = re.findall(r"[a-z]+", _fold(name))
    out = {toks[-1]} if toks else set()
    if len(toks) >= 4 and len(toks[-2]) >= 4:
        out.add(toks[-2])
    return {t for t in out if len(t) >= 3}


def strict_injury(title: str, name: str) -> list:
    """Detektor v2: riječi o ozljedi/odustajanju BLIZU prezimena igrača (pravilo gore)."""
    sn = _surnames(name)
    if not sn or _CAREER_RE.search(title or ""):
        return []
    toks = re.findall(r"[a-z]+", _fold(title))
    pos = [i for i, t in enumerate(toks) if t in sn]
    if not pos:
        return []
    ctx = bool(_MATCH_CTX_RE.search(title or ""))
    hits = set()
    for i, t in enumerate(toks):
        near = any(abs(i - p) <= _NEAR for p in pos)
        after = any(0 < i - p <= _NEAR for p in pos)   # odustajanje: samo iza prezimena
        if _PHYS_RE.match(t):
            if near:
                hits.add(t)
            continue
        if not after:
            continue
        if _OUT_RE.match(t):
            nxt = toks[i + 1] if i + 1 < len(toks) else ""
            if t.startswith("pull") and nxt != "out":
                continue
            if t == "ruled" and nxt != "out":
                continue
            hits.add(t if t not in ("pull", "pulls", "pulled", "pulling", "ruled") else f"{t} out")
        elif _RETIRE_RE.match(t) and ctx:
            hits.add(t)
    return sorted(hits)


# Prikaz za čovjeka (P1, 25.10.2026 11:39): s Dnevnog listića maknut je ESPN/BBC panel (izmjereno
# 25.10.: 4 od 12 pogodaka o pravom igraču i svježe). Od Google Newsa se prikazuju samo "priče" i
# stvarne ozljede — najave, rezultati i kladionice su 76% naslova i ne nose ništa novo.
_PREVIEW_RE = re.compile(
    r"\bvs\.?\b|\bv\b|preview|prediction|odds|pick|h2h|head[- ]to[- ]head|\blive\b|stats|scores?\b|"
    r"result|\bdraw\b|men'?s singles|round|\br\d{2,3}\b|quarter\w*|semi\w*|\bfinals?\b|\bqfs?\b|"
    r"\bsfs?\b|beats?\b|def\.|defeats|upends|advances|into the|stuns|edges|cruises|through to|"
    r"reach\w*|sees off|gets past|\bdowns?\b|takes out|falls|quells|outlasts|survives|ousts|"
    r"knocks out|eliminat\w*|\bwins?\b|victory|title|champion|hot shot|watch|video|highlights|"
    r"upsets?\b|\w/\w|^tennis, (?:atp|wta)|tennis\.com",   # \w/\w = parovi ("Koepfer/Struff")
    re.IGNORECASE)


def display_items(gnews: dict, match_date=None, days: int = 3, max_items: int = 3) -> list:
    """Naslovi za prikaz čovjeku: ne-kladioničarski, ≤ days dana prije meča, prezime u naslovu, i
    ili stvarna ozljeda (v2) ili "priča" (nije najava/rezultat). [{d, s, t, kind}] — najnoviji prvi."""
    if not isinstance(gnews, dict) or gnews.get("error"):
        return []
    name = str(gnews.get("q") or "").replace('"', "").replace(" tennis", "").strip()
    sn = _surnames(name)
    end = _as_date(match_date) if match_date else _dt.date.today()
    out, seen = [], set()
    for it in gnews.get("items") or []:
        if it.get("bet"):
            continue
        key = _fold(it.get("t") or "")[:70]
        if key in seen:          # isti naslov s dva izvora
            continue
        seen.add(key)
        d = _as_date(it.get("d"))
        if (end - d).days > days or (d - end).days > 1:
            continue
        t = it.get("t") or ""
        if not (sn & set(re.findall(r"[a-z]+", _fold(t)))):
            continue
        inj = it.get("inj2") if "inj2" in it else strict_injury(t, name)
        if inj:
            out.append({"d": it.get("d"), "s": it.get("s"), "t": t, "kind": "ozljeda", "inj": inj})
        elif (not _PREVIEW_RE.search(t)
              and len(t.rsplit(" - ", 1)[0].split()) >= 5):   # "Federico Cina - ATP Tour" = profil
            out.append({"d": it.get("d"), "s": it.get("s"), "t": t, "kind": "priča", "inj": []})
    return out[:max_items]

# Kladioničarski naslovi ("prediction: odds, picks") se označavaju ISTIM popisom koji čuva prompt
# (`data_fetcher._NEWS_EXCLUDE`) — jedna politika na jednom mjestu. Ako ove vijesti ikad uđu u
# prompt, stavke s `bet: True` moraju ostati vani. Uvoz unutar funkcije: modul ostaje lagan za
# testove, a dnevni run `data_fetcher` ionako već ima učitan.
def _bet_words():
    try:
        from agent.data_fetcher import _NEWS_EXCLUDE
        return _NEWS_EXCLUDE
    except Exception:
        return ("odds", "favourite", "favorite", "prediction", "predict", "betting", "bookmaker")


_cache = {}
_lock = threading.Lock()


def _as_date(value):
    if isinstance(value, _dt.date):
        return value
    try:
        return _dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return _dt.date.today()


def parse_feed(xml_bytes, match_date, days: int = _DAYS, max_items: int = _MAX_ITEMS,
               name: str = None) -> dict:
    """RSS -> {"n", "injury_n", "items"}; samo članci iz [datum meča - days, datum meča + 1].
    Uz `name` (od 25.10.2026) i strogi detektor v2: `inj2` po stavci, `injury_n2`, `inj_v: 2`."""
    end = _as_date(match_date)
    start = end - _dt.timedelta(days=days)
    root = ET.fromstring(xml_bytes)
    bet_words = _bet_words()
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        try:
            pub = _eu.parsedate_to_datetime(it.findtext("pubDate") or "").date()
        except (TypeError, ValueError, IndexError):
            continue
        if not (start <= pub <= end + _dt.timedelta(days=1)):
            continue
        src = (it.findtext("source") or "").strip()
        flags = sorted({m.group(0).lower() for m in _INJURY_RE.finditer(title)})
        low = title.lower()
        bet = any(w in low for w in bet_words)
        rec = {"d": pub.isoformat(), "t": title[:160], "s": src[:40], "inj": flags, "bet": bet}
        if name:
            rec["inj2"] = strict_injury(title, name)
        items.append(rec)
    items.sort(key=lambda x: x["d"], reverse=True)
    # injury_n broji samo NE-kladioničarske naslove s riječju o ozljedi — to je mjera za K13.
    out = {"n": len(items), "injury_n": sum(1 for x in items if x["inj"] and not x["bet"]),
           "items": items[:max_items]}
    if name:
        # 25.10.2026 11:39: K13b — strogi detektor v2, broji se preko SVIH naslova u prozoru (kao K13).
        out["injury_n2"] = sum(1 for x in items if x.get("inj2") and not x["bet"])
        out["inj_v"] = 2
    return out


def player_news(name: str, match_date=None) -> dict:
    """Naslovi o igraču iz zadnjih 14 dana. Kešira se po (ime, datum) unutar runa."""
    name = (name or "").strip()
    if not name:
        return {"error": "nema imena"}
    key = (name.lower(), str(match_date)[:10])
    with _lock:
        if key in _cache:
            return _cache[key]
    q = f'"{name}" tennis'
    try:
        resp = requests.get(_URL.format(q=urllib.parse.quote(q)), headers=_HEADERS,
                            timeout=_TIMEOUT)
        if resp.status_code != 200:
            out = {"error": f"http {resp.status_code}", "q": q}
        else:
            out = parse_feed(resp.content, match_date, name=name)   # name: detektor v2 (25.10.2026)
            out["q"] = q
    except Exception as e:  # mreža, parsiranje — nikad ne ruši dnevni run
        out = {"error": f"{type(e).__name__}: {str(e)[:60]}", "q": q}
    with _lock:
        _cache[key] = out
    return out
