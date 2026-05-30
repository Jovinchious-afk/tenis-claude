"""
Ticket Builder: od liste predikcija gradi optimalni tiket.
Kriteriji: 4-7 mečeva, ukupna kvota 8-15, max 2 mača istog turnira.
Claude Sonnet piše finalni write-up.
"""
import os
import json
import itertools
import anthropic
from typing import Optional
from dotenv import load_dotenv
from config.model_config import TICKET_CONFIG, CLAUDE_MODELS, TOURNAMENT_LEVELS, DAILY_MATCH_LIMITS
from utils.helpers import combined_odds, potential_win, today_zagreb, tomorrow_zagreb

load_dotenv()

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client


# Razine turnira koje se NE stavljaju na tiket (samo analiziramo radi modela)
_NON_TICKET_LEVELS = {"ATP Challenger", "ATP Qualifying"}


def build_ticket(predictions: list, weights: dict, min_odds_override: float = None) -> Optional[dict]:
    """
    Ulaz: lista predikcija iz predictor.analyze_match()
    Izlaz: optimalni tiket dict s matches, odds, summary

    Strategija (quality-first):
    - Primarni kriterij: statistička kvaliteta (confidence + value)
    - Sekundarni: combined odds mora biti 6-20 (nije cilj, samo filter)
    - Challengeri se ne stavljaju na tiket
    - Kaskadni fallback — uvijek generiraj tiket, nikad ne odustaj
    """
    cfg = dict(TICKET_CONFIG)
    if min_odds_override is not None:
        cfg["min_combined_odds"] = min_odds_override

    def _eligible(p, conf_threshold, allow_challengers=False):
        level = p.get("match", {}).get("level", "")
        if not allow_challengers and level in _NON_TICKET_LEVELS:
            return False
        return not p.get("skip_reason") and (p.get("confidence") or 0) >= conf_threshold

    # Kaskadni fallback: 63% → 58% → 55% → last resort (best 4 bez obzira)
    thresholds = [
        (cfg["min_confidence"],        False),   # faza 1: 63%, bez Challengera
        (cfg["fallback_confidence"],   False),   # faza 2: 58%, bez Challengera
        (cfg["last_resort_confidence"], False),  # faza 3: 55%, bez Challengera
        (cfg["last_resort_confidence"], True),   # faza 4: 55%, uz Challengere s real odds
    ]

    candidates = []
    for conf_threshold, allow_challengers in thresholds:
        candidates = [p for p in predictions if _eligible(p, conf_threshold, allow_challengers)]
        if len(candidates) >= cfg["min_matches"]:
            if conf_threshold < cfg["min_confidence"]:
                print(f"Fallback: koristim conf >= {conf_threshold}%"
                      f"{' (uključeni Challengeri)' if allow_challengers else ''}")
            break

    # Zadnji resort: uzmi sve valjane predikcije bez obzira na razinu ili conf
    if len(candidates) < cfg["min_matches"]:
        candidates = [p for p in predictions if not p.get("skip_reason")]
        candidates.sort(key=lambda p: (p.get("confidence") or 0), reverse=True)
        candidates = candidates[:cfg["max_matches"]]
        print(f"Last resort: uzimam top {len(candidates)} pickova po confidence-u")

    # Sortiraj quality-first: value pick > visoki confidence > razina turnira
    candidates.sort(key=lambda p: (
        _is_value_pick(p),
        (p.get("confidence") or 0),
        TOURNAMENT_LEVELS.get(p.get("match", {}).get("level", "ATP 250"), 45)
    ), reverse=True)

    candidates = _apply_daily_limits(candidates)
    best_combo = _find_best_combination(candidates, cfg)

    if not best_combo:
        # Kaskadni fallback za odds: smanji min_conf i traži par s višom kvotom
        # koji će gurnuti kombiniranu kvotu u raspon 6-20
        print("Standardni raspon nije dostignut — tražim riskantnije pickove s višom kvotom.")
        all_valid = [p for p in predictions if not p.get("skip_reason")]
        all_valid.sort(key=lambda p: _pick_odds(p), reverse=True)  # najviše kvote prvo
        combined_pool = candidates + [p for p in all_valid if p not in candidates]
        best_combo = _find_best_combination(combined_pool, cfg)
        if best_combo:
            print("Tiket složen s riskantijim pickovima — prihvaćamo veći rizik.")

    total_odds = combined_odds([_pick_odds(p) for p in best_combo])
    pot_win = potential_win(cfg["stake"], total_odds)

    ticket_matches = []
    for pred in best_combo:
        m = pred.get("match", {})
        pick = pred.get("pick", "")
        ticket_matches.append({
            "player1": m.get("player1", ""),
            "player2": m.get("player2", ""),
            "pick": pick,
            "odds": _pick_odds(pred),
            "match_date": m.get("date", ""),
            "match_time": m.get("time", ""),
            "tournament": m.get("tournament", ""),
            "tournament_level": m.get("level", ""),
            "surface": m.get("surface", ""),
            "round": m.get("round", ""),
            "confidence": pred.get("confidence", 0),
            "fair_odds": pred.get("fair_odds"),
            "value_bet": pred.get("value", False),
            "risk_level": pred.get("risk_level", "srednji"),
            "risk_notes": pred.get("risk_notes", ""),
            "handicap_option": pred.get("handicap_option"),
            "key_factors": pred.get("key_factors", []),
            "external_match_id": m.get("external_id", ""),
            "result": "pending",
        })

    summary = _generate_ticket_summary(ticket_matches, total_odds, pot_win, weights)

    return {
        "total_odds": round(total_odds, 4),
        "potential_win": pot_win,
        "stake": cfg["stake"],
        "matches_count": len(ticket_matches),
        "ticket_summary": summary,
        "status": "pending",
        "matches": ticket_matches,
    }


def _find_best_combination(candidates: list, cfg: dict) -> Optional[list]:
    """
    Nova strategija: traži kombinaciju 3-4 solidna favorita (conf>=72%) +
    1-2 value autsajdera (conf>=60%, bookmaker kvota>=1.80, prava vrijednost).
    Fallback: sve kombinacije unutar parametara ako nema dovoljno value pickova.
    """
    min_n = cfg["min_matches"]
    max_n = cfg["max_matches"]
    min_odds = cfg["min_combined_odds"]
    max_odds = cfg["max_combined_odds"]

    best = None
    best_score = -1

    for n in range(max_n, min_n - 1, -1):
        if n > len(candidates):
            continue
        for combo in itertools.combinations(candidates, n):
            # Nikad ne uzimaj pick s kvotom < 1.06
            if any(_pick_odds(p) < 1.06 for p in combo):
                continue

            odds = combined_odds([_pick_odds(p) for p in combo])
            if odds < min_odds or odds > max_odds:
                continue

            avg_conf = sum(p.get("confidence", 0) for p in combo) / len(combo)
            value_count = sum(1 for p in combo if _is_value_pick(p))
            high_conf_count = sum(1 for p in combo if (p.get("confidence") or 0) >= 72)
            gs_masters_count = sum(1 for p in combo
                                   if TOURNAMENT_LEVELS.get(
                                       p.get("match", {}).get("level", ""), 0) >= 85)

            # Quality-first scoring: statistička kvaliteta je primarni kriterij
            # Odds su samo filter (6-20), ne cilj — ne bonusiramo "pogađanje" nekog raspona
            score = (avg_conf * 1.5          # primarno: prosječni confidence
                     + value_count * 6        # bonus za prave value pickove (real odds > fair)
                     + high_conf_count * 2    # bonus za high-conf (72%+) pickove
                     + gs_masters_count * 1)  # mali bonus za GS/Masters kvalitetu podataka

            if score > best_score:
                best_score = score
                best = list(combo)

    return best


def _is_value_pick(pred: dict) -> bool:
    """Pravi value pick: bookmaker kvota >= 1.80, odds su stvarne (ne default), fair_odds povoljan."""
    match = pred.get("match", {})
    if not match.get("odds_available", True):
        return False
    bookmaker_odds = _pick_odds(pred)
    fair_odds = pred.get("fair_odds") or 0
    if bookmaker_odds < 1.80 or fair_odds <= 0:
        return False
    # Value = bookmaker nudi barem 12% više od naše fair vrijednosti
    return bookmaker_odds >= fair_odds * 1.12


def _pick_odds(pred: dict) -> float:
    m = pred.get("match", {})
    pick = pred.get("pick", "")
    p1 = m.get("player1", "")
    # Matchanje picka s igračem
    if pick.lower() in p1.lower() or p1.lower() in pick.lower():
        return float(m.get("odds_p1", 1.5) or 1.5)
    return float(m.get("odds_p2", 1.5) or 1.5)


def _generate_ticket_summary(matches: list, total_odds: float, pot_win: float, weights: dict) -> str:
    """Claude Sonnet writes the ticket write-up in English."""
    picks_text = "\n".join([
        f"{i+1}. {m['pick']} to win — {m['player1']} vs {m['player2']} "
        f"({m['tournament']}, {m['surface']}, {m.get('round','')}) — odds: {m['odds']:.2f}, "
        f"confidence: {m['confidence']:.0f}%"
        f"{', VALUE ✓' if m.get('value_bet') else ''}\n"
        f"   Risk: {m.get('risk_notes','')}\n"
        f"   Key factors: {', '.join(m.get('key_factors',[]))}"
        for i, m in enumerate(matches)
    ])

    prompt = f"""You are an expert tennis analyst. Write a concise ticket write-up in English, in the style of a sports analyst. Maximum 200 words.

TICKET:
{picks_text}

Combined odds: {total_odds:.2f}
Potential return: €{pot_win:.2f} on €50 stake

Write:
1. One sentence on the overall ticket quality
2. For each pick: one sentence explaining why it is a good selection (focus on key factors)
3. One closing sentence with overall assessment

Be specific — mention surface, form, H2H, fatigue where relevant."""

    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODELS["ticket_writer"],
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"Greška generiranja write-upa: {e}")
        return f"Tiket s {len(matches)} parova. Ukupna kvota: {total_odds:.2f}, potencijalni dobitak: €{pot_win:.2f}."


def _apply_daily_limits(candidates: list) -> list:
    """
    Pre-filtrira kandidate: max N po (turniru, datum) prema DAILY_MATCH_LIMITS.
    Unutar svake grupe zadržava top N po confidence-u.
    Ovo se poziva PRIJE kombinatorike tako da motoru uvijek ostaje čist pool.
    """
    today_str = today_zagreb().isoformat()
    tomorrow_str = tomorrow_zagreb().isoformat()

    groups: dict = {}
    for p in candidates:
        m = p.get("match", {})
        tournament = m.get("tournament", "unknown")
        date = (m.get("date", "") or "")[:10]
        groups.setdefault((tournament, date), []).append(p)

    result = []
    for (tournament, date), group in groups.items():
        level = group[0].get("match", {}).get("level", "ATP 250")
        limits = DAILY_MATCH_LIMITS.get(level, {"today": 2, "tomorrow": 2})

        if date == today_str:
            limit = limits["today"]
        else:
            limit = limits["tomorrow"]  # sutra ili dalje — konzervativniji limit

        if limit == 0:
            continue  # Challenger/Qualifying — preskačemo

        group_sorted = sorted(group, key=lambda p: (p.get("confidence") or 0), reverse=True)
        result.extend(group_sorted[:limit])
        if len(group_sorted) > limit:
            print(f"  Daily limit: {tournament} ({date}) — uzeto {limit}/{len(group_sorted)} kandidata")

    return result
