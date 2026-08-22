# -*- coding: utf-8 -*-
"""CLV izvještaj — mjeri kvalitetu CIJENE po kojoj smo ušli, ne ishoda (22.08.2026 15:20).

ČEMU SLUŽI
Pitanje "ima li naš model prednost" dosad smo pokušavali odgovoriti preko ishoda — koliko
smo pickova pogodili. Račun snage na našim podacima (bazna stopa 63,5%, SD CLV-a 1,21pp):

    preko ISHODA,  prednost 2pp   ->  ~4.500 mečeva
    preko ISHODA,  prednost 3pp   ->  ~2.000 mečeva
    preko CIJENE,  prednost 0,5pp ->     ~46 mečeva
    preko CIJENE,  prednost 1,0pp ->     ~11 mečeva

Uz ~15 analiza dnevno, 2.000 mečeva je oko četiri mjeseca bez prekida. Zato smo u tri
uzastopne revizije zapinjali na "uzorak je premalen". Ishod jednog meča je grubo mjerilo
kvalitete picka; cijena po kojoj smo ušli je puno preciznije mjerilo iste stvari.

ŠTO JE CLV
Closing Line Value = razlika između onoga što tržište misli NEPOSREDNO PRIJE POČETKA i
onoga što je naša cijena implicirala u trenutku slaganja tiketa.
    CLV > 0  ->  tržište se pomaknulo PREMA našem picku; ušli smo po boljoj cijeni od
                 konačne, dakle imali smo informaciju koju tržište tek treba pokupiti
    CLV < 0  ->  tržište se pomaknulo OD našeg picka; platili smo skuplje nego što je
                 konačna cijena, dakle vjerojatno smo bili u krivu
Dugoročno CLV predviđa isplativost bolje i BRŽE nego postotak pogotka, jer ne ovisi o tome
je li lopta pala unutra ili vani u jednom meču.

DVIJE OGRADE KOJE TREBA PAMTITI PRI SVAKOM ČITANJU
1. NAŠ CLV MIJEŠA DVIJE KUĆE. Kladimo se po SuperSportovoj kvoti sa screenshota, a mjerimo
   naspram svjetskog konsenzusa. Čist CLV tražio bi SuperSportovu ZAVRŠNU cijenu, koje u
   Odds APIju nema. Mjerenje je zato bučnije nego idealno; smjer i predznak ostaju
   upotrebljivi, apsolutna razina manje.
2. ZAVRŠNA CIJENA JE ZAVRŠNA SAMO AKO JE SNIMLJENA BLIZU POČETKA. Do 22.08.2026 hvatanje je
   bilo jedan termin u 14:30 UTC bez filtra i samo 5,1% redaka bilo je unutar 2h od početka
   (medijan 9,6h). Zato ovaj izvještaj ISPISUJE koliko je snimka bila blizu i dopušta filtar
   `--max-hours`. Podaci prije 22.08.2026 nisu upotrebljivi za CLV i program na to upozorava.

POLAZNA TOČKA (izmjereno 22.08.2026 na n=55, uz loše hvatanje — dakle samo orijentir):
    prosječni CLV = -0,53pp; kod 41 od 55 pickova završna cijena bila je ISPOD naše
    implicirane. Tržište se u prosjeku miče OD naših pickova.
    Pickovi s CLV>0: 12/14 = 85,7%   |   s CLV<=0: 23/41 = 56,1%

NE ULAZI NI U JEDNU ODLUKU. Ovo je mjerni alat, ne dio pipelinea.

POKRETANJE
    python scripts/clv_report.py                    # sve od 22.08.2026
    python scripts/clv_report.py --since 2026-09-01
    python scripts/clv_report.py --max-hours 3      # samo snimke unutar 3h od početka
"""
import os
import sys
import math
import argparse
import statistics as st
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from database import supabase_client as db

# Prije ovog datuma hvatanje nije imalo filtar na prozor prije početka (vidi ograda 2).
GOOD_CAPTURE_FROM = "2026-08-22"


def _page(table, order="id.asc"):
    out, p = [], 0
    while True:
        chunk = db._rest("GET", table, params={"select": "*", "order": order,
                                               "offset": str(p * 1000), "limit": "1000"})
        if not chunk:
            break
        out.extend(chunk)
        p += 1
        if len(chunk) < 1000 or p > 60:
            break
    return out


def _toks(name):
    return {t for t in (name or "").lower().replace(".", " ").replace("-", " ").split()
            if len(t) > 1 and t not in ("jr", "sr")}


def _same(a, b):
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=GOOD_CAPTURE_FROM)
    ap.add_argument("--max-hours", type=float, default=0.0,
                    help="uzmi samo snimke unutar toliko sati od pocetka (0 = sve)")
    args = ap.parse_args()

    ml = _page("market_lines")
    am = _page("analyzed_matches")
    print(f"market_lines: {len(ml)} redaka | analyzed_matches: {len(am)}")

    # event -> {captured_hour: {book: (o_home, o_away, hours_to_start)}}
    ev, meta = defaultdict(lambda: defaultdict(dict)), {}
    for r in ml:
        o1, o2 = _f(r.get("odds_p1")), _f(r.get("odds_p2"))
        if not (o1 and o2 and o1 > 1 and o2 > 1):
            continue
        h = _f(r.get("hours_to_start"))
        if args.max_hours and (h is None or h > args.max_hours):
            continue
        k = r.get("event_id")
        ev[k][(r.get("captured_at") or "")[:13]][r.get("bookmaker")] = (o1, o2, h)
        meta.setdefault(k, {"home": r.get("player1"), "away": r.get("player2"),
                            "commence": r.get("commence_time")})

    def consensus(k, snap, flip, pick_is_p1):
        ps = []
        for _b, (oh, oa, _h) in ev[k].get(snap, {}).items():
            op1, op2 = (oa, oh) if flip else (oh, oa)
            ps.append(_devig(op1, op2) if pick_is_p1 else _devig(op2, op1))
        return st.median(ps) if ps else None

    rows = []
    for r in am:
        d = r.get("match_date") or ""
        if d < args.since or r.get("prediction_correct") is None:
            continue
        p1, p2, pk = r.get("player1"), r.get("player2"), r.get("predicted_winner")
        if not (p1 and p2 and pk):
            continue
        is1 = _same(pk, p1) and not _same(pk, p2)
        is2 = _same(pk, p2) and not _same(pk, p1)
        if not (is1 or is2):
            continue
        o1, o2 = _f(r.get("bookmaker_odds_p1")), _f(r.get("bookmaker_odds_p2"))
        if not (o1 and o2 and o1 > 1 and o2 > 1):
            continue
        hit = None
        for k, m in meta.items():
            cd = (m.get("commence") or "")[:10]
            if not cd or cd[:7] != d[:7] or abs(int(cd[8:10]) - int(d[8:10])) > 1:
                continue
            if _same(m["home"], p1) and _same(m["away"], p2):
                hit = (k, False); break
            if _same(m["home"], p2) and _same(m["away"], p1):
                hit = (k, True); break
        if not hit:
            continue
        k, flip = hit
        snaps = sorted(ev[k])
        if not snaps:
            continue
        ss_pick, ss_opp = (o1, o2) if is1 else (o2, o1)
        ss_p = _devig(ss_pick, ss_opp)
        close = consensus(k, snaps[-1], flip, is1)
        if close is None:
            continue
        hrs = [h for (_o1, _o2, h) in ev[k][snaps[-1]].values() if h is not None]
        rows.append({"date": d, "pick": pk, "correct": bool(r["prediction_correct"]),
                     "ss_pick": ss_pick, "ss_p": ss_p, "close": close,
                     "clv": close - ss_p, "hrs": st.median(hrs) if hrs else None})

    if not rows:
        print(f"\nNema meceva od {args.since} sa snimkom trzista. "
              f"(Ako je datum nedavan, to je normalno.)")
        return 0

    clv = [100 * r["clv"] for r in rows]
    hs = [r["hrs"] for r in rows if r["hrs"] is not None]
    print(f"\n{'='*78}\nCLV IZVJESTAJ — od {args.since}   n={len(rows)}\n{'='*78}")
    if hs:
        near = sum(1 for h in hs if h <= 2)
        print(f"  Zavrsna snimka: medijan {st.median(hs):.1f}h prije pocetka, "
              f"{near}/{len(hs)} unutar 2h")
        if st.median(hs) > 4:
            print("  UPOZORENJE: zavrsna snimka je daleko od pocetka — CLV je nepouzdan.")
    k = sum(1 for r in rows if r["correct"])
    print(f"  Ucinak: {k}/{len(rows)} = {100*k/len(rows):.1f}%")
    print(f"\n  PROSJECNI CLV: {st.mean(clv):+.2f}pp   medijan {st.median(clv):+.2f}pp   "
          f"SD {st.pstdev(clv):.2f}pp")
    pos = sum(1 for x in clv if x > 0)
    print(f"  Pickova s pozitivnim CLV-om: {pos}/{len(clv)} ({100*pos/len(clv):.0f}%)")
    if len(clv) >= 8:
        se = st.pstdev(clv) / math.sqrt(len(clv))
        lo, hi = st.mean(clv) - 1.96 * se, st.mean(clv) + 1.96 * se
        print(f"  95% interval za prosjecni CLV: {lo:+.2f} .. {hi:+.2f}pp")
        if lo > 0:
            print("  -> CLV je POZITIVAN i interval ne prelazi nulu: znak stvarne prednosti.")
        elif hi < 0:
            print("  -> CLV je NEGATIVAN i interval ne prelazi nulu: selekcija gubi na cijeni.")
        else:
            print("  -> interval prelazi nulu: jos nema odgovora, treba vise meceva.")
    a = [r for r in rows if r["clv"] > 0]
    b = [r for r in rows if r["clv"] <= 0]
    if a and b:
        ka = sum(1 for r in a if r["correct"])
        kb = sum(1 for r in b if r["correct"])
        print(f"\n  Ishod po CLV-u:  CLV>0 {ka}/{len(a)} = {100*ka/len(a):.1f}%   "
              f"CLV<=0 {kb}/{len(b)} = {100*kb/len(b):.1f}%")
    br_ss = st.mean([(r["ss_p"] - (1.0 if r["correct"] else 0.0)) ** 2 for r in rows])
    br_cl = st.mean([(r["close"] - (1.0 if r["correct"] else 0.0)) ** 2 for r in rows])
    print(f"\n  Brier nase cijene   {br_ss:.4f}")
    print(f"  Brier zavrsne linije {br_cl:.4f}")
    print("  (ako zavrsna NIJE osjetno bolja, vjerojatno je nismo uhvatili dovoljno blizu)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
