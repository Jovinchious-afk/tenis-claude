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
_INJURY_RE = re.compile(
    r"\b(injur\w*|withdr\w*|pull(?:s|ed|ing)? out|retir\w*|illness|ill|sick\w*|blister\w*|"
    r"strain\w*|sprain\w*|tear|torn|surgery|fitness|doubtful|pain|cramp\w*|medical|"
    r"hamstring|abdominal|ankle|knee|wrist|shoulder|elbow|ruled out|walkover)\b",
    re.IGNORECASE)

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


def parse_feed(xml_bytes, match_date, days: int = _DAYS, max_items: int = _MAX_ITEMS) -> dict:
    """RSS -> {"n", "injury_n", "items"}; samo članci iz [datum meča - days, datum meča + 1]."""
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
        items.append({"d": pub.isoformat(), "t": title[:160], "s": src[:40], "inj": flags,
                      "bet": bet})
    items.sort(key=lambda x: x["d"], reverse=True)
    # injury_n broji samo NE-kladioničarske naslove s riječju o ozljedi — to je mjera za K13.
    return {"n": len(items), "injury_n": sum(1 for x in items if x["inj"] and not x["bet"]),
            "items": items[:max_items]}


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
            out = parse_feed(resp.content, match_date)
            out["q"] = q
    except Exception as e:  # mreža, parsiranje — nikad ne ruši dnevni run
        out = {"error": f"{type(e).__name__}: {str(e)[:60]}", "q": q}
    with _lock:
        _cache[key] = out
    return out
