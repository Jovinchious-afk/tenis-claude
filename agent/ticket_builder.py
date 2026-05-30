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

    # Edge override: picks with confidence 55-62% but edge >= 8pp enter the pool
    # These are the "intuition/underdog" picks the market is undervaluing
    edge_overrides = []
    for p in predictions:
        if p.get("skip_reason"):
            continue
        conf = p.get("confidence") or 0
        if 55 <= conf < 63:
            fair = p.get("fair_odds") or 0
            bookmaker = _pick_odds(p)
            if fair > 0 and bookmaker > 0:
                edge = (1.0 / fair - 1.0 / bookmaker) * 100
                if edge >= 8.0:
                    level = p.get("match", {}).get("level", "")
                    if level not in _NON_TICKET_LEVELS:
                        edge_overrides.append(p)
                        print(f"  Edge override: {p.get('pick','')} conf={conf}% edge={edge:.1f}pp")

    # Merge: add overrides not already in candidates
    candidate_ids = {id(p) for p in candidates}
    for p in edge_overrides:
        if id(p) not in candidate_ids:
            candidates.append(p)

    # Sort by score potential: value pick > high confidence > tournament level
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
    Quality-first scoring using joint probability as primary metric.
    Formula:
      score = joint_probability × 100
            + edge_bonus × 1.5        (edge >= 3pp, proportional, cap 10/pick)
            + high_conf_count × 2     (confidence >= 72%)
            - weakest_pick_penalty    (max(0, 68 - min_conf) × 1.5)
            - extra_pick_penalty      ((n_picks - 4) × 3)
    Combined odds 9-40 is a hard filter, not a target.
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
            if any(_pick_odds(p) < 1.06 for p in combo):
                continue

            odds = combined_odds([_pick_odds(p) for p in combo])
            if odds < min_odds or odds > max_odds:
                continue

            score = _score_combo(combo)
            if score > best_score:
                best_score = score
                best = list(combo)

    return best


def _score_combo(combo: tuple) -> float:
    """Score a combination using joint probability as primary signal."""
    confs = [max(1, p.get("confidence", 50)) for p in combo]

    # Joint probability (primary) — product of all confidences
    joint_prob = 1.0
    for c in confs:
        joint_prob *= c / 100.0

    # Edge bonus: proportional, only if edge >= 3pp, cap 10 per pick
    edge_total = 0.0
    for p in combo:
        fair = p.get("fair_odds") or 0
        bookmaker = _pick_odds(p)
        if fair > 0 and bookmaker > 0:
            model_prob = 1.0 / fair * 100
            implied_prob = 1.0 / bookmaker * 100
            edge = model_prob - implied_prob
            if edge >= 3.0:
                edge_total += min(10.0, edge)

    # High confidence bonus
    high_conf_count = sum(1 for c in confs if c >= 72)

    # Weakest pick penalty
    weakest = min(confs)
    weakest_penalty = max(0.0, (68 - weakest) * 1.5)

    # Extra pick penalty
    extra_penalty = (len(combo) - 4) * 3

    return (joint_prob * 100
            + edge_total * 1.5
            + high_conf_count * 2
            - weakest_penalty
            - extra_penalty)


def _is_value_pick(pred: dict) -> bool:
    """Value pick: edge >= 3pp between our fair probability and bookmaker implied probability."""
    fair = pred.get("fair_odds") or 0
    bookmaker = _pick_odds(pred)
    if fair <= 0 or bookmaker <= 0:
        return False
    edge = (1.0 / fair - 1.0 / bookmaker) * 100
    return edge >= 3.0


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
