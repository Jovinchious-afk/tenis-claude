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


def _is_main_tour(p) -> bool:
    """Challengers, ITF, Qualifying se nikad ne stavljaju na tiket niti u analysis-only."""
    level = p.get("match", {}).get("level", "")
    low = level.lower()
    if any(kw in low for kw in ["challenger", "qualifying", "itf", "future"]):
        return False
    return True


def _has_odds(p) -> bool:
    """Meč mora imati stvarnu kvotu (Odds API ili screenshot) — bez nje se nikad ne stavlja na tiket."""
    return bool(p.get("match", {}).get("odds_available"))


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

    # Kaskadni fallback: 63% → 58% → 55% — Challengeri nikad
    thresholds = [
        cfg["min_confidence"],         # faza 1: 63%
        cfg["fallback_confidence"],    # faza 2: 58%
        cfg["last_resort_confidence"], # faza 3: 55%
    ]

    candidates = []
    for conf_threshold in thresholds:
        candidates = [p for p in predictions
                      if not p.get("skip_reason")
                      and (p.get("confidence") or 0) >= conf_threshold
                      and _is_main_tour(p)
                      and _has_odds(p)]
        if len(candidates) >= cfg["min_matches"]:
            if conf_threshold < cfg["min_confidence"]:
                print(f"Fallback: using conf >= {conf_threshold}% (no Challengers)")
            break

    # Zadnji resort: svi main-tour bez obzira na conf, ali NIKAD Challenger
    if len(candidates) < cfg["min_matches"]:
        candidates = [p for p in predictions
                      if not p.get("skip_reason") and _is_main_tour(p) and _has_odds(p)]
        candidates.sort(key=lambda p: (p.get("confidence") or 0), reverse=True)
        candidates = candidates[:cfg["max_matches"]]
        print(f"Last resort: top {len(candidates)} main-tour picks by confidence")

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
                    if _is_main_tour(p) and _has_odds(p):
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
        all_valid = [p for p in predictions
                     if not p.get("skip_reason") and _is_main_tour(p) and _has_odds(p)]
        all_valid.sort(key=lambda p: _pick_odds(p), reverse=True)  # najviše kvote prvo
        combined_pool = candidates + [p for p in all_valid if p not in candidates]
        best_combo = _find_best_combination(combined_pool, cfg)
        if best_combo:
            print("Tiket složen s riskantijim pickovima — prihvaćamo veći rizik.")

    if not best_combo:
        print("Nema dovoljno mečeva sa stvarnim kvotama za valjan tiket.")
        return None

    # Final holistic review by Claude Sonnet before ticket is confirmed
    rejected_candidates = [p for p in candidates if p not in best_combo]
    best_combo = _review_ticket(best_combo, rejected_candidates, cfg)

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
        "reviewer_decision": _last_reviewer_notes.get("decision", ""),
        "reviewer_changes": _last_reviewer_notes.get("changes", ""),
        "reviewer_warning": _last_reviewer_notes.get("warning", ""),
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


_last_reviewer_notes: dict = {}  # module-level cache for reviewer output


def _review_ticket(proposed: list, rejected: list, cfg: dict) -> list:
    """
    Claude Sonnet reviews the mathematically selected ticket holistically.
    Can confirm, modify (max 2 swaps), reduce, or force a valid ticket.
    Falls back to proposed ticket if review fails or produces invalid result.
    """
    def _pick_summary(p: dict) -> str:
        m = p.get("match", {})
        conf = p.get("confidence", 0)
        fair = p.get("fair_odds") or 0
        bm = _pick_odds(p)
        edge = round((1.0/fair - 1.0/bm) * 100, 1) if fair > 0 and bm > 0 else 0
        fmt = "BoF5" if "Grand Slam" in m.get("level", "") else "BoF3"
        return (
            f"  Pick: {p.get('pick','')} | {m.get('player1','')} vs {m.get('player2','')} "
            f"| {m.get('tournament','')} {m.get('round','')} {fmt} | {m.get('surface','')}\n"
            f"  Confidence: {conf}% | Fair odds: {fair:.2f} | Bookmaker: {bm:.2f} | Edge: {edge:+.1f}pp\n"
            f"  Risk: {p.get('risk_level','')} — {p.get('risk_notes','')}\n"
            f"  Key factors: {'; '.join(p.get('key_factors',[]))}\n"
            f"  Analysis: {p.get('analysis','')}"
        )

    proposed_section = "\n\n".join(_pick_summary(p) for p in proposed)
    rejected_section = "\n\n".join(_pick_summary(p) for p in rejected[:5]) if rejected else "None"

    from utils.helpers import combined_odds as _co
    joint_prob = 1.0
    for p in proposed:
        joint_prob *= (p.get("confidence", 50) / 100)
    c_odds = _co([_pick_odds(p) for p in proposed])

    prompt = f"""You are the final holistic reviewer of a tennis betting ticket.

The mathematical optimizer has already applied: joint probability scoring, edge bonuses, weakest-pick penalty, extra-pick penalty, surface ELO, avg opponent ELO, fatigue, H2H reliability, and round context.

PROPOSED TICKET ({len(proposed)} picks | Combined odds: {c_odds:.2f} | Joint probability: {joint_prob*100:.1f}%):
{proposed_section}

REJECTED CANDIDATES (closest to selection):
{rejected_section}

YOUR ROLE:
Review the ticket holistically as an experienced tennis analyst. You may:
A. CONFIRM — keep as-is
B. MODIFY — replace 1-2 picks if tennis reasoning clearly overrules the math
C. REDUCE — remove the weakest link if it makes the ticket fragile (never below 4 picks)
D. FORCE — if ticket is weak, build the best possible 4-7 pick ticket from all available

CHECK FOR: hidden fatigue, false recent form (weak opponents), surface/style mismatch, overlapping risk (too many picks with same vulnerability), data gaps (ELO 1500), BoF5 stamina implications, H2H small sample overweighting.

GRASS-SPECIFIC CHECKS (apply when any pick is on Grass surface):
- FLAG and consider removing: any grass pick at confidence ≥65% — this season's data shows systematic overconfidence at that level; confidence 65%+ on grass has lost repeatedly.
- FLAG: grass picks where the player has 4+ matches in 7 days with only 1-2 days rest — fatigue on grass is decisive and cannot be offset by form.
- FLAG: grass picks driven primarily by ELO when opponent has equal or better recent in-tournament results (tournament trajectory). ELO alone on grass has failed in 5+ documented cases.
- FLAG: grass picks where the favoured player entered via bye and opponent has 2+ in-tournament wins this week — the bye is a disadvantage on grass, not neutral.
- If 2+ grass picks share the same vulnerability (both relying on ELO edge, both with fatigued favourites), treat this as overlapping risk and consider REDUCING to 1 grass pick.

HARD CONSTRAINTS:
- Final ticket: 4-7 picks, combined odds 9-40 (or 6-40 if only 4 matches available)
- Max 2 replacements
- Never remove a strong pick just because odds are low
- Never add a pick just to increase odds
- Prefer stability over excitement

Respond ONLY in this JSON format:
{{
  "decision": "CONFIRM|MODIFY|REDUCE|FORCE",
  "final_picks": ["exact player name as given above", ...],
  "changes": "No changes made. / Removed X, added Y because: ... (1-2 clean sentences, final answer only — no reasoning steps, hesitations, or self-corrections like 'wait, ...')",
  "warning": "One sentence naming the SINGLE pick (by player name) that carries the most risk on the PROPOSED ticket above, and why. Avoid referring to counts of picks (e.g. 'all four picks') since your proposed changes may be reverted and the original ticket shown instead — focus on the specific pick/risk, not the ticket size."
}}"""

    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODELS["ticket_writer"],
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        import re as _re
        raw = response.content[0].text.strip()
        raw = _re.sub(r'```(?:json)?\s*', '', raw).strip().strip('`')
        # Robust JSON parse — handles unterminated strings and literal newlines
        start = raw.find('{')
        end = raw.rfind('}')
        if start != -1 and end > start:
            raw = raw[start:end + 1]
        result = json.loads(raw)

        decision = result.get("decision", "CONFIRM")
        final_names = result.get("final_picks", [])
        changes = result.get("changes", "")
        warning = result.get("warning", "")

        # Store reviewer notes for inclusion in ticket
        _last_reviewer_notes.clear()
        _last_reviewer_notes.update({
            "decision": decision,
            "changes": changes,
            "warning": warning,
        })

        if changes and changes != "No changes made.":
            print(f"  Reviewer [{decision}]: {changes}")
        if warning:
            print(f"  Reviewer warning: {warning}")

        if decision == "CONFIRM" or not final_names:
            return proposed

        # Match returned names back to prediction objects
        all_pool = proposed + rejected
        final_combo = []
        for name in final_names:
            name_lower = name.lower().strip()
            for p in all_pool:
                pick = (p.get("pick") or "").lower().strip()
                if pick == name_lower or pick.split()[-1] == name_lower.split()[-1]:
                    if p not in final_combo:
                        final_combo.append(p)
                        break

        # Validate result — must be 4-7 picks and odds in range
        if len(final_combo) >= cfg["min_matches"]:
            rev_odds = combined_odds([_pick_odds(p) for p in final_combo])
            if cfg["min_combined_odds"] <= rev_odds <= cfg["max_combined_odds"]:
                return final_combo
            print(f"  Reviewer result invalid odds ({rev_odds:.2f}) — keeping original.")
        else:
            print(f"  Reviewer returned {len(final_combo)} picks — keeping original.")

        # Reviewer's change was rejected by validation — original ticket kept as-is.
        # Update notes so the displayed decision matches reality (avoid showing a
        # "removed X" claim for a pick that is still in the final ticket), and avoid
        # echoing the reviewer's raw "changes" text which can contain messy
        # mid-reasoning artifacts (e.g. "wait, ...").
        if final_combo and len(final_combo) < len(proposed):
            removed_names = [p.get("pick", "") for p in proposed if p not in final_combo]
            detail = f"remove {', '.join(removed_names)}"
        else:
            detail = f"reduce to {len(final_combo)} pick(s)"

        _last_reviewer_notes["decision"] = "CONFIRM"
        _last_reviewer_notes["changes"] = (
            f"Reviewer proposed to {detail}, but this was reverted to keep combined odds "
            f"within the required range ({cfg['min_combined_odds']}-{cfg['max_combined_odds']}). "
            f"Original ticket retained — see warning below for the highest-risk pick."
        )
        return proposed

    except Exception as e:
        print(f"  Reviewer error: {e} — keeping original ticket.")
        return proposed


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

Be specific — mention surface, form, H2H, fatigue where relevant.

Refer to players by name (or surname) only — do not use nationality/demonyms (e.g. "the Croatian", "the Czech") as a stand-in for a player's name, since this is a frequent source of mix-ups when a ticket contains multiple players."""

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


def build_analysis_only_ticket(predictions: list) -> dict:
    """
    Builds an analysis-only entry when there aren't enough matches for a full ticket.
    No minimum match count, no odds constraints. Uses Haiku for write-up.
    Status = 'analysis_only' so the evening job tracks results but never marks ticket won/lost.
    """
    valid = [p for p in predictions if not p.get("skip_reason") and _is_main_tour(p)]
    valid.sort(key=lambda p: (p.get("confidence") or 0), reverse=True)

    ticket_matches = []
    for pred in valid:
        m = pred.get("match", {})
        ticket_matches.append({
            "player1": m.get("player1", ""),
            "player2": m.get("player2", ""),
            "pick": pred.get("pick", ""),
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

    summary = _generate_analysis_only_summary(ticket_matches)

    return {
        "total_odds": 0.0,
        "potential_win": 0.0,
        "stake": 0,
        "matches_count": len(ticket_matches),
        "ticket_summary": summary,
        "reviewer_decision": "",
        "reviewer_changes": "",
        "reviewer_warning": "",
        "status": "analysis_only",
        "matches": ticket_matches,
    }


def _generate_analysis_only_summary(matches: list) -> str:
    """Haiku write-up for analysis-only days — late rounds with too few matches for a ticket."""
    if not matches:
        return "No main-tour matches available for analysis today."

    picks_text = "\n".join([
        f"{i+1}. {m['pick']} to win — {m['player1']} vs {m['player2']} "
        f"({m['tournament']}, {m['surface']}, {m.get('round','')}) — "
        f"odds: {m['odds']:.2f}, confidence: {m['confidence']:.0f}%\n"
        f"   Key factors: {', '.join(m.get('key_factors', []))}"
        for i, m in enumerate(matches)
    ])

    prompt = f"""You are an expert tennis analyst. Today there {'is only 1 main-tour match' if len(matches) == 1 else f'are only {len(matches)} main-tour matches'} available — not enough to build a full accumulator ticket.

AVAILABLE MATCHES:
{picks_text}

Write a brief analysis (max 150 words):
1. One sentence: why no ticket was formed (too few matches for a valid accumulator)
2. For each match: one sentence — your pick and the single strongest reason
3. One closing sentence on overall confidence

Be direct and specific. Frame it as: "if I had to bet on these matches..." This entry is tracked for model learning."""

    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODELS["analysis"],
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"Greška analysis-only write-upa: {e}")
        picks_str = ", ".join(f"{m['pick']} ({m['confidence']:.0f}%)" for m in matches)
        return (
            f"Analysis only — {len(matches)} match(es) available today, "
            f"insufficient for a full ticket. Predictions: {picks_str}."
        )


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
