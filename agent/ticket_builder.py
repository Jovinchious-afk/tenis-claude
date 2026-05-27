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
from config.model_config import TICKET_CONFIG, CLAUDE_MODELS, TOURNAMENT_LEVELS
from utils.helpers import combined_odds, potential_win

load_dotenv()

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client


# Razine turnira koje se NE stavljaju na tiket (samo analiziramo radi modela)
_NON_TICKET_LEVELS = {"ATP Challenger", "ATP Qualifying"}


def build_ticket(predictions: list, weights: dict) -> Optional[dict]:
    """
    Ulaz: lista predikcija iz predictor.analyze_match()
    Izlaz: optimalni tiket dict s matches, odds, summary

    Strategija: 3-4 solidna favorita (conf >= 72%) + 1-2 value autsajdera
    (conf >= 60%, bookmaker kvota >= 1.80, fair_odds povoljan).
    Challengeri se ne stavljaju na tiket.
    """
    cfg = TICKET_CONFIG
    min_conf = cfg["min_confidence"]

    def _eligible(p, conf_threshold):
        return (
            not p.get("skip_reason")
            and (p.get("confidence") or 0) >= conf_threshold
            and p.get("match", {}).get("level", "") not in _NON_TICKET_LEVELS
        )

    candidates = [p for p in predictions if _eligible(p, min_conf)]

    if len(candidates) < cfg["min_matches"]:
        min_conf = cfg["fallback_confidence"]
        candidates = [p for p in predictions if _eligible(p, min_conf)]
        if len(candidates) < cfg["min_matches"]:
            print(f"Premalo kandidata ({len(candidates)}) i na fallback thresholdu {min_conf}% (bez Challengera)")
            return None

    # Sortiraj: value pickovi prvo, pa po confidence
    candidates.sort(key=lambda p: (
        _is_value_pick(p),
        (p.get("confidence") or 0),
        TOURNAMENT_LEVELS.get(p.get("match", {}).get("level", "ATP 250"), 45)
    ), reverse=True)

    best_combo = _find_best_combination(candidates, cfg)

    if not best_combo:
        print("Nije moguće pronaći kombinaciju unutar zadanih parametara kvote.")
        return None

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
    max_same_tournament = cfg["max_matches_same_tournament"]

    best = None
    best_score = -1

    for n in range(max_n, min_n - 1, -1):
        if n > len(candidates):
            continue
        for combo in itertools.combinations(candidates, n):
            # Provjeri diversifikaciju turnira
            tournament_counts = {}
            for pred in combo:
                t = pred.get("match", {}).get("tournament", "unknown")
                tournament_counts[t] = tournament_counts.get(t, 0) + 1
            if any(v > max_same_tournament for v in tournament_counts.values()):
                continue

            odds = combined_odds([_pick_odds(p) for p in combo])
            if odds < min_odds or odds > max_odds:
                continue

            avg_conf = sum(p.get("confidence", 0) for p in combo) / len(combo)
            value_count = sum(1 for p in combo if _is_value_pick(p))
            base_count = sum(1 for p in combo if (p.get("confidence") or 0) >= 72)

            # Scoring: visoki confidence + bonus za prave value pickove + bonus za base favourite
            # Value pick s realnom kvotom >= 1.80 donosi +6 bodova svaki
            score = avg_conf + (value_count * 6) + (base_count * 1.5)

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
    """Claude Sonnet piše kratki write-up tiketa na hrvatskom."""
    picks_text = "\n".join([
        f"{i+1}. {m['pick']} pobjeđuje {m['player1']} vs {m['player2']} "
        f"({m['tournament']}, {m['surface']}) — kvota: {m['odds']:.2f}, "
        f"confidence: {m['confidence']:.0f}%, "
        f"{'VALUE ✓' if m.get('value_bet') else ''}\n"
        f"   Rizik: {m.get('risk_notes','')}\n"
        f"   Ključni faktori: {', '.join(m.get('key_factors',[]))}"
        for i, m in enumerate(matches)
    ])

    prompt = f"""Ti si stručni tenis analitičar. Napiši kratki write-up za sljedeći sportski tiket.
Napiši maksimalno 200 riječi, na hrvatskom jeziku, u stilu sportskog komentatora.

TIKET:
{picks_text}

Ukupna kvota: {total_odds:.2f}
Potencijalni dobitak: €{pot_win:.2f} na €50

Napiši:
1. Jednu rečenicu o generalnoj kvaliteti tiketa
2. Za svaki par: jednu rečenicu zašto je to dobar pick (fokus na ključne faktore)
3. Završnu rečenicu o ukupnoj procjeni

Budi konkretan, navedi specifične razloge (podloga, forma, H2H, itd.)."""

    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODELS["ticket_writer"],
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"Greška generiranja write-upa: {e}")
        return f"Tiket s {len(matches)} parova. Ukupna kvota: {total_odds:.2f}, potencijalni dobitak: €{pot_win:.2f}."
