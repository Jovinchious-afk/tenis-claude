# -*- coding: utf-8 -*-
"""CLV (closing line value) jednog picka — čiste funkcije, bez baze (01.11.2026 16:18).

ZAŠTO ZASEBAN MODUL: revizija 01.11.2026 predložila je CLV kao glavno mjerilo za "nos" (pomak
kvote do početka meča vidi prednost od 1pp na ~11 mečeva, ishod tek na tisućama — vidi zaglavlje
`scripts/clv_report.py`). Isti izračun sada trebaju tri mjesta: večernja analiza gubitka
(`agent/feedback_analyzer.py`, jedan pick), mjerenje K26 (`scripts/measure_candidates.py`) i
izvještaj. Pravilo je PREPISANO iz `scripts/clv_report.py` (22.08.2026), koji ostaje nepromijenjen:
  - isti par igrača (podudaranje po riječima imena), datum početka unutar ±1 dana od datuma meča;
  - samo snimke unutar `max_hours` sati prije početka (zadano 4 h = prozor snimanja od 26.10.2026);
  - zadnja snimka; konsenzus = medijan devigirane vjerojatnosti preko kladionica;
  - CLV = konsenzus na zatvaranju − naša ulazna cijena (devigirana SuperSport kvota), u pp.
CLV > 0: tržište se do početka pomaknulo PREMA našem picku; CLV < 0: OD njega.

OGRADA (zaglavlje `clv_report.py`): ulazimo po SuperSportu, a mjerimo naspram svjetskog
konsenzusa, pa razina nije čista (SuperSport je za naše pickove u prosjeku ~0,27pp iznad
konsenzusa, skeptik 01.11.2026); predznak i usporedba skupina ostaju upotrebljivi. CLV opisuje
CIJENU po kojoj smo ušli — nije uzrok ishoda i nije prediktor (kretanje linije 5× izmjereno kao
nula, DECISION_INPUTS).
"""
import statistics as _st
from collections import defaultdict


def _toks(name):
    return {t for t in (name or "").lower().replace(".", " ").replace("-", " ").split()
            if len(t) > 1 and t not in ("jr", "sr")}


def same_player(a, b) -> bool:
    ta, tb = _toks(a), _toks(b)
    return bool(ta and tb) and len(ta & tb) >= min(2, min(len(ta), len(tb)))


def _f(x):
    try:
        v = float(x)
        return v if v == v and abs(v) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _devig(o1, o2):
    a, b = 1.0 / o1, 1.0 / o2
    return a / (a + b)


def index_lines(lines: list, max_hours: float = 4.0) -> dict:
    """market_lines retci -> {event_id: {"home", "away", "commence", "snaps": {sat: {kuća: (o_home, o_away, h)}}}}."""
    ev = {}
    for r in lines or []:
        o1, o2 = _f(r.get("odds_p1")), _f(r.get("odds_p2"))
        if not (o1 and o2 and o1 > 1 and o2 > 1):
            continue
        h = _f(r.get("hours_to_start"))
        if max_hours and (h is None or h > max_hours):
            continue
        k = r.get("event_id")
        e = ev.setdefault(k, {"home": r.get("player1"), "away": r.get("player2"),
                              "commence": str(r.get("commence_time") or ""), "snaps": defaultdict(dict)})
        e["snaps"][str(r.get("captured_at") or "")[:13]][r.get("bookmaker")] = (o1, o2, h)
    return ev


def for_pick(index: dict, player1: str, player2: str, pick: str, odds_p1, odds_p2, match_date) -> dict:
    """CLV našeg picka ili None (nema snimke blizu početka, nema obje kvote, pick nije igrač meča)."""
    o1, o2 = _f(odds_p1), _f(odds_p2)
    if not (o1 and o2 and o1 > 1 and o2 > 1 and player1 and player2 and pick):
        return None
    is1 = same_player(pick, player1) and not same_player(pick, player2)
    is2 = same_player(pick, player2) and not same_player(pick, player1)
    if not (is1 or is2):
        return None
    d = str(match_date or "")[:10]
    hit = None
    for k, e in index.items():
        cd = e["commence"][:10]
        if not cd or not d or cd[:7] != d[:7] or abs(int(cd[8:10]) - int(d[8:10])) > 1:
            continue
        if same_player(e["home"], player1) and same_player(e["away"], player2):
            hit = (k, False)
            break
        if same_player(e["home"], player2) and same_player(e["away"], player1):
            hit = (k, True)
            break
    if not hit:
        return None
    k, flip = hit
    snaps = index[k]["snaps"]
    if not snaps:
        return None
    last = sorted(snaps)[-1]
    ps, hrs = [], []
    for _b, (oh, oa, h) in snaps[last].items():
        op1, op2 = (oa, oh) if flip else (oh, oa)
        ps.append(_devig(op1, op2) if is1 else _devig(op2, op1))
        if h is not None:
            hrs.append(h)
    if not ps:
        return None
    close = _st.median(ps)
    entry = _devig(o1, o2) if is1 else _devig(o2, o1)
    return {"clv_pp": round(100 * (close - entry), 2), "close_p": round(close, 4),
            "entry_p": round(entry, 4), "hrs": round(_st.median(hrs), 1) if hrs else None,
            "n_books": len(ps)}
