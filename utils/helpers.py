import datetime
import pytz
from typing import Optional


ZAGREB_TZ = pytz.timezone("Europe/Zagreb")


def today_zagreb() -> datetime.date:
    return datetime.datetime.now(ZAGREB_TZ).date()


def tomorrow_zagreb() -> datetime.date:
    return today_zagreb() + datetime.timedelta(days=1)


def days_ago(n: int) -> datetime.date:
    return today_zagreb() - datetime.timedelta(days=n)


def format_date(d: datetime.date) -> str:
    return d.strftime("%Y-%m-%d")


def format_date_hr(d: datetime.date) -> str:
    """Croatian-style date formatting."""
    return d.strftime("%d.%m.%Y")


def odds_to_probability(odds: float) -> float:
    if odds <= 1.0:
        return 0.99
    return round(1.0 / odds, 4)


def probability_to_fair_odds(prob: float) -> float:
    if prob <= 0:
        return 99.0
    return round(1.0 / prob, 2)


def calculate_value(fair_odds: float, bookmaker_odds: float, margin: float = 0.05) -> bool:
    """True ako je bookmaker odds >= fair_odds * (1 + margin)."""
    return bookmaker_odds >= fair_odds * (1 + margin)


def combined_odds(odds_list: list) -> float:
    result = 1.0
    for o in odds_list:
        result *= o
    return round(result, 4)


def potential_win(stake: float, total_odds: float) -> float:
    return round(stake * total_odds, 2)


def form_string(wins: int, losses: int) -> str:
    return f"{wins}W/{losses}L"


def days_since(date_str: str) -> int:
    """Broj dana od datuma (YYYY-MM-DD) do danas."""
    try:
        d = datetime.date.fromisoformat(date_str)
        return (today_zagreb() - d).days
    except Exception:
        return -1


def truncate(text: str, max_len: int = 200) -> str:
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def safe_int(val, default: int = 0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default

# ---------------------------------------------------------------------------
# PRIKAZ PICKA — dvije zastite dodane 29.08.2026 13:05
#
# Obje su posljedica istog dana: write-up je 29.08. za dva meca imenovao PROTIVNIKA
# nasih pickova (vidi MODEL_CHANGELOG 2026-08-29 12:10). Popravak prompta i
# deterministicka provjera rijesili su UZROK; ovo rjesava POSLJEDICU — da korisnik
# nikad ne mora zakljucivati sto je sluzbeni pick iz proze koju je napisao model.
#
# 4) `pick_ledger` — sluzbeni popis pickova crtan IZ BAZE, ne iz teksta. Prikazuje se
#    iznad write-upa u Streamlitu, arhivi i mailu. Cak i da model jednom omakne,
#    oko odmah vidi sto je zapisano.
#
# 5) `MIN_PICK_CONFIDENCE` / `is_no_selection` — pick s pouzdanoscu ispod 50% je
#    logicka kontradikcija: model tvrdi da igrac na kojeg se kladimo VJEROJATNIJE
#    GUBI. Prvi put se dogodilo 29.08.2026 (Yibing Wu, 49%, kvota 1,85 uz fair 2,04).
#
#    Izmjereno na razrijesenoj povijesti (337 analiza s poznatom pouzdanoscu):
#        <50%    n=0     (nikad prije; postalo je moguce tek 17.08.2026, kad su
#                         uvedene oduzimajuce kazne -4pp scouting i -5pp trzisni
#                         autsajder, koje se ZBRAJAJU)
#        50-54%  n=2     0 pogodaka    0,0%
#        55-59%  n=11    7             63,6%
#        60-64%  n=222   137           61,7%
#        65%+    n=102   66            64,7%
#
#    ZASTO SE SMIJE UCI PRED GRAND SLAM: prag za pravi tiket je 63% (65% na Grand
#    Slamu), pa pick ispod 50% NIKAD nije mogao doci na listic. Ovo mijenja samo
#    prikaz i hipotetski tiket — selekcija pravog tiketa ostaje netaknuta.
#
#    STO SE NAMJERNO NE RADI: takvi pickovi OSTAJU u bazi, razrjesavaju se i BROJE
#    SE u statistici modela. Iskljuciti ih iz bodovanja znacilo bi tiho brisati
#    vlastite najgore odluke iz dosjea, a uzorak je i onako premalen (n=2 ispod 55%)
#    da bismo si to smjeli dopustiti. Oznaka govori "ovo ne bismo igrali", ne
#    "ovo se nije dogodilo".
#
#    NIJE RIJESENO OVIME (zaseban, veci problem — vidi MODEL_CHANGELOG, tocka 6):
#    model svoje neslaganje s vlastitim pickom moze izraziti SAMO spustanjem broja,
#    nikad promjenom strane. Sva pravila su odbici i stropovi ("deduction, not a
#    veto", "cap at 62%"), nijedno ne kaze "onda uzmi drugoga". Zato je Wu i zavrsio
#    na 49% umjesto da je pick postao Walton.
# ---------------------------------------------------------------------------

MIN_PICK_CONFIDENCE = 50.0


def is_no_selection(match: dict) -> bool:
    """Pick ispod praga — model efektivno tvrdi da vlastiti pick gubi.

    Izvedeno iz `confidence`, NIJE zaseban stupac u bazi: prag je stvar prikaza i
    politike, pa mora biti promjenjiv bez migracije i primjenjiv unatrag na sve
    postojece retke.
    """
    if not match:
        return False
    conf = match.get("confidence")
    if conf is None:
        return False
    return safe_float(conf, default=MIN_PICK_CONFIDENCE) < MIN_PICK_CONFIDENCE


def pick_ledger(matches: list) -> list:
    """Sluzbeni popis pickova IZ BAZE — izvor istine za svaki prikaz.

    Namjerno ne dira nikakav tekst koji je napisao model. Vraca listu dictova
    ({n, pick, player1, player2, odds, confidence, no_selection}) pa svaki
    prikaz (Streamlit, arhiva, HTML mail) oblikuje po svome.
    """
    out = []
    for i, m in enumerate(matches or []):
        out.append({
            "n": i + 1,
            "pick": m.get("pick") or "",
            "player1": m.get("player1") or "",
            "player2": m.get("player2") or "",
            "odds": safe_float(m.get("odds")),
            "confidence": safe_float(m.get("confidence")),
            "no_selection": is_no_selection(m),
        })
    return out


# ---------------------------------------------------------------------------
# RUNDA SE UNOSI RUCNO — 26.09.2026 17:04 (korisnikova odluka)
#
# Od danas rundu svakog para upisuje korisnik na stranici "Kvote sa Screenshota",
# u trenutku uploada. Svi automatski nacini odredjivanja runde su OBRISANI iz koda:
# fiksna mapa `roundId` -> runda, brojanje meceva po danu (`_infer_rounds`),
# provjera na razini turnira (`_verify_late_rounds`), ljestvica iz zdrijeba
# (`get_tournament_round_map` / `_apply_draw_rounds`) i zastita u tiketu koja je iz
# runde pogadjala kvalifikacije.
#
# ZASTO — tri mjeseca pokusaja, svaki je popravljao prethodni i nijedan nije drzao:
#   07.08.  42,6% redaka u nemogucoj grupi (isti igrac vise puta u "R32")
#   13.08.  Montreal: 10 "polufinala" (turnir smije 2)
#   08.09.  US Open: 69 redaka "R64" (smije 32)
#   13.09.  izmjereno 79,2% krivih oznaka na cijelom korpusu; uveden "zdrijeb"
#   24.09.  Chengdu i Hangzhou PRVI DAN: 12 meceva zapisano kao "SF"; sljedeca dva
#           dana "R64" na ATP 250 turnirima, koji R64 uopce nemaju. Zdrijeb na
#           pocetku turnira jos ne postoji, a te je oznake nitko nije provjeravao
#           jer su nosile `round_source="draw"` ("pouzdano").
# Korisnik vidi rundu na kladionici u istom trenutku kad uploada kvote — to je
# jedini izvor koji nikad nije pogrijesio.
#
# INTERNI KODOVI su namjerno isti kao dosad (R128 ... F), jer ih cita prompt
# (pravila za QF/SF/F), korpus u `analyzed_matches.round` i sva mjerenja po rundi
# (K11). Mijenja se samo tko ih upisuje. Hrvatske oznake su samo za prikaz.
# ---------------------------------------------------------------------------

ROUND_CHOICES = [
    ("R128", "1/64 finala"),
    ("R64", "1/32 finala"),
    ("R32", "1/16 finala"),
    ("R16", "1/8 finala"),
    ("QF", "1/4 finala"),
    ("SF", "1/2 finala"),
    ("F", "Finale"),
    # ATP Finals (Torino, studeni) i ekipna natjecanja nemaju eliminacijsku ljestvicu.
    ("RR", "Grupna faza (ATP Finals)"),
    ("DC", "Davis Cup susret"),
]
ROUND_CODES = [c for c, _ in ROUND_CHOICES]
ROUND_LABEL_HR = dict(ROUND_CHOICES)
ROUND_CODE_BY_LABEL = {label: code for code, label in ROUND_CHOICES}


def round_label_hr(code: str) -> str:
    """'R16' -> '1/8 finala'. Nepoznat ili prazan kod vraca se kakav jest ('' ostaje '')."""
    return ROUND_LABEL_HR.get(str(code or "").upper().strip(), str(code or ""))


def normalize_round_code(code) -> str:
    """Valjan interni kod runde ili '' — nikad ne pogadja iz necega drugoga."""
    c = str(code or "").upper().strip()
    return c if c in ROUND_LABEL_HR else ""


# ---------------------------------------------------------------------------
# POJAS CIJENE I "NAS DOSJE" — jedno mjesto za dvije namjene (26.09.2026 20:28)
#
# Revizija 26.09.2026 (revizije/2026-09-26/REVIZIJA_2026-09-26.md) nasla je da analize
# gubitaka iz rujna u 15 od 20 slucajeva tvrde nesto netocno o samom mecu — najcesce
# "pick je bio u rupi 1,43-1,60" za pick koji je bio @1,24 ili @2,35. Uzrok: prompt
# analize nije dobivao kvotu, pa ju je model izvodio iz NASE POUZDANOSTI. Od danas se
# pojas racuna u kodu, ovdje, i daje modelu kao cinjenica.
#
# Iste granice koristi i Dnevni listic za redak "nas povijesni edge u ovom pojasu" —
# namjerno JEDNA definicija (lekcija "dvije kapije, jedna politika" od 19.09.2026: ista
# politika prepisana na dva mjesta rasprsi se cim se jedno mjesto promijeni).
#
# Izmjereno 26.09.2026 upravo ovom funkcijom (`band_edge_context`) na svim razrijesenim
# analizama s obje kvote, naspram devigirane SuperSport cijene:
#     1,00-1,20  -1,6pp (n=56)    1,60-1,75  +4,8pp (n=72)
#     1,20-1,35  +8,8pp (n=80)    1,75-2,00  -0,5pp (n=56)
#     1,35-1,43  -5,6pp (n=59)    2,00+      -2,1pp (n=39)
#     1,43-1,60  -9,0pp (n=89)
# Rupa 1,35-1,60 ima isti predznak u obje polovice korpusa (K5/K10 u DECISION_INPUTS).
# ---------------------------------------------------------------------------

PRICE_BANDS = [(1.00, 1.20), (1.20, 1.35), (1.35, 1.43), (1.43, 1.60),
               (1.60, 1.75), (1.75, 2.00), (2.00, 99.0)]


def price_band(odds) -> Optional[tuple]:
    """Pojas kvote naseg picka kao (od, do) ili None ako kvote nema."""
    o = safe_float(odds)
    if o <= 1.0:
        return None
    for lo, hi in PRICE_BANDS:
        if lo <= o < hi:
            return (lo, hi)
    return None


def price_band_label(band) -> str:
    if not band:
        return "nepoznat"
    lo, hi = band
    return f"{lo:.2f}+" if hi >= 99 else f"{lo:.2f}-{hi:.2f}"


def devig_pick_prob(pick_odds, opp_odds) -> Optional[float]:
    """Devigirana vjerojatnost NASEG picka iz dvije kvote (multiplikativno micanje marze)."""
    a, b = safe_float(pick_odds), safe_float(opp_odds)
    if a <= 1.0 or b <= 1.0:
        return None
    return (1.0 / a) / (1.0 / a + 1.0 / b)


def _resolved_pick_rows(rows: list) -> list:
    """Iz redaka `analyzed_matches` (razrijesenih) izvuci (pick, protivnik, kvota picka,
    devig cijena, pobjeda, datum). Retke bez obje kvote ili s pobjednikom izvan para
    preskace — isto pravilo integriteta kao u reviziji."""
    out = []
    for r in rows or []:
        pick = r.get("predicted_winner") or ""
        p1, p2 = r.get("player1") or "", r.get("player2") or ""
        if not pick or pick not in (p1, p2) or r.get("prediction_correct") is None:
            continue
        o1, o2 = safe_float(r.get("bookmaker_odds_p1")), safe_float(r.get("bookmaker_odds_p2"))
        po, oo = (o1, o2) if pick == p1 else (o2, o1)
        p = devig_pick_prob(po, oo)
        if p is None:
            continue
        out.append({"pick": pick, "opp": p2 if pick == p1 else p1, "odds": po, "p": p,
                    "win": 1.0 if r.get("prediction_correct") else 0.0,
                    "date": str(r.get("match_date") or "")[:10]})
    return out


def band_edge_context(rows: list, odds) -> Optional[dict]:
    """Nas povijesni edge u pojasu kvote kojem pripada `odds`: {band, n, wr, exp, edge}.
    Edge je stvarni postotak pogodaka minus prosjek devigirane cijene, u postotnim bodovima.
    SAMO ZA PRIKAZ / KONTEKST — ne ulazi u odluku (vidi K5/K10)."""
    band = price_band(odds)
    if not band:
        return None
    rs = [x for x in _resolved_pick_rows(rows) if band[0] <= x["odds"] < band[1]]
    if not rs:
        return {"band": band, "n": 0}
    n = len(rs)
    wr = sum(x["win"] for x in rs) / n
    ex = sum(x["p"] for x in rs) / n
    return {"band": band, "n": n, "wr": 100 * wr, "exp": 100 * ex, "edge": 100 * (wr - ex)}


def player_dossier(rows: list, name: str) -> dict:
    """Nas dosje s igracem (korisnikova ideja 2, 26.09.2026) — SAMO ZA PRIKAZ.

    IZMJERENO ISTI DAN I NE ULAZI U ODLUKU: broj nasih promasaja s igracem ne predvidja
    sljedeci mec — doslovno pravilo (-2pp iznad prosjeka / +2pp ispod) dalo je -1,0pp
    naspram -0,4pp; visak promasaja naspram cijene r=-0,004 (n=417); ni na 11.512 trzisnih
    nastupa igracev ostatak naspram cijene nije postojan (r=+0,06 / +0,14). Rublev, kojeg
    smo 3-4 izgubili na 7 pickova, kao trzisni favorit pobjedjuje 3,8pp CESCE od kvote.
    Prikazuje se jer korisnik zeli vidjeti povijest, ne jer nosi signal."""
    key = " ".join(str(name or "").lower().split())
    rs = _resolved_pick_rows(rows)
    mine = [x for x in rs if " ".join(x["pick"].lower().split()) == key]
    vs = [x for x in rs if " ".join(x["opp"].lower().split()) == key]
    out = {"as_pick_n": len(mine), "as_pick_w": int(sum(x["win"] for x in mine)),
           "as_opp_n": len(vs), "beat_us": int(sum(1 for x in vs if x["win"] == 0.0))}
    if mine:
        out["as_pick_edge"] = 100 * (sum(x["win"] for x in mine) - sum(x["p"] for x in mine)) / len(mine)
    return out
