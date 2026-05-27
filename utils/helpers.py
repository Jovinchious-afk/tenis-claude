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
