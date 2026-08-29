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
