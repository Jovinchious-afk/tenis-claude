"""
Predictor: za svaki meč šalje strukturirane podatke Claude Haiku-u koji
primjenjuje težine modela i vraća procjenu (pick, confidence, fair_odds, value...).
"""
import os
import re
import json
import anthropic
from dotenv import load_dotenv
from config.model_config import CLAUDE_MODELS
from utils.helpers import safe_float

load_dotenv()

_client = None


def _fix_json_strings(s: str) -> str:
    """Escape literal newlines/tabs inside JSON string values (LLM often forgets to)."""
    out = []
    in_string = False
    escape_next = False
    for c in s:
        if escape_next:
            out.append(c)
            escape_next = False
        elif c == '\\' and in_string:
            out.append(c)
            escape_next = True
        elif c == '"':
            in_string = not in_string
            out.append(c)
        elif in_string and c == '\n':
            out.append('\\n')
        elif in_string and c == '\r':
            pass  # skip \r
        elif in_string and c == '\t':
            out.append('\\t')
        else:
            out.append(c)
    return ''.join(out)


def _safe_json_parse(raw: str) -> dict:
    """Parse JSON from LLM output — handles markdown fences, literal newlines in strings."""
    raw = re.sub(r'```(?:json)?\s*', '', raw).strip()
    start = raw.find('{')
    end = raw.rfind('}')
    if start == -1 or end <= start:
        raise ValueError("No JSON object found in LLM response")
    raw = raw[start:end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(_fix_json_strings(raw))


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client


ANALYSIS_PROMPT_TEMPLATE = """You are an expert tennis analyst. Evaluate the following match using only the provided data and model weights.

=== MATCH ===
{player1} vs {player2}
Tournament: {tournament} | Level: {level}
Surface: {surface} | Round: {round}
Date: {date} | Format: {format}
Round context: {round_context}

=== {player1} ===
Age: {p1_age} | Playing hand: {p1_hand}
ATP Ranking: #{p1_ranking} | Ranking trend: {p1_ranking_trend}
ELO (overall): {p1_elo_overall} | ELO ({surface}): {p1_elo_surface}
NOTE: Surface-specific ELO is more predictive than ATP ranking for this match.
{surface} record (last 3 years): {p1_surface_record}
Form (last 5): {p1_form_5} | Form (last 10): {p1_form_10}
Avg opponent ELO (last 10): {p1_avg_opp_elo} — quality-adjusted form signal
{surface} form (6 months): {p1_surface_form}
--- Serve dominance ---
Total serve points won: {p1_serve_pts_won}% | Hold % (est.): {p1_hold_pct}%
1st serve %: {p1_first_serve_pct} | 1st serve pts won: {p1_first_serve_won}
2nd serve pts won: {p1_second_serve_won} | Aces/match: {p1_aces}
BP saved: {p1_bp_saved} | BP converted: {p1_break_conv}
Return pts won: {p1_return_won}% (break proxy)
--- Physical condition ---
Matches last 7 days: {p1_matches_7d} | Sets last 7 days: {p1_sets_7d} | Days rest: {p1_days_rest} | Age: {p1_age}
Current tournament path: {p1_tourn_path}
Form trend: {p1_form_trend}
Known injuries/news: {p1_news}

=== {player2} ===
Age: {p2_age} | Playing hand: {p2_hand}
ATP Ranking: #{p2_ranking} | Ranking trend: {p2_ranking_trend}
ELO (overall): {p2_elo_overall} | ELO ({surface}): {p2_elo_surface}
NOTE: Surface-specific ELO is more predictive than ATP ranking for this match.
{surface} record (last 3 years): {p2_surface_record}
Form (last 5): {p2_form_5} | Form (last 10): {p2_form_10}
Avg opponent ELO (last 10): {p2_avg_opp_elo} — quality-adjusted form signal
{surface} form (6 months): {p2_surface_form}
--- Serve dominance ---
Total serve points won: {p2_serve_pts_won}% | Hold % (est.): {p2_hold_pct}%
1st serve %: {p2_first_serve_pct} | 1st serve pts won: {p2_first_serve_won}
2nd serve pts won: {p2_second_serve_won} | Aces/match: {p2_aces}
BP saved: {p2_bp_saved} | BP converted: {p2_break_conv}
Return pts won: {p2_return_won}% (break proxy)
--- Physical condition ---
Matches last 7 days: {p2_matches_7d} | Sets last 7 days: {p2_sets_7d} | Days rest: {p2_days_rest} | Age: {p2_age}
Current tournament path: {p2_tourn_path}
Form trend: {p2_form_trend}
Known injuries/news: {p2_news}

=== H2H ===
Overall: {h2h_overall}
On {surface}: {h2h_surface}
Last meeting: {h2h_last}
Recent trend (last 3): {h2h_trend}
H2H reliability: {h2h_reliability}

=== CONTEXT ===
Conditions: {weather}
Altitude: {altitude}
Tournament history {player1}: {p1_tournament_history}
Tournament history {player2}: {p2_tournament_history}
{odds_alert}

=== MODEL WEIGHTS ===
ELO + ranking trend + opponent quality: {w_elo_ranking}%
Surface + playing style matchup: {w_surface_style}%
Serve + return stats: {w_serve_return}%
Recent form (last 5-10 matches): {w_recent_form}%
Fatigue + injuries + schedule: {w_fatigue_injuries}%
H2H + tournament context: {w_h2h_context}%
Tournament trajectory (in-tournament W/L run, current momentum, hot-hand): {w_tournament_trajectory}%

=== INSTRUCTIONS ===
Form your prediction based exclusively on statistical factors and model weights — independent of bookmaker odds.
If stats and form favour the underdog, pick the underdog. Since we do not play system bets, the pick must be highly reliable (min 63% confidence).
For handicap option: suggest only if the favourite is clearly dominant AND has no tiebreak profile.
Round context is critical: early rounds allow larger upsets; later rounds (SF/F) favour proven performers. Adjust confidence accordingly.

Key analytical priorities:
- Surface-specific ELO outweighs ATP ranking. A player ranked #15 with clay ELO 1750 is better on clay than a #8 with clay ELO 1680.
- Hold% and serve dominance are the strongest predictors in ATP tennis (especially hard/grass). A player who wins 70%+ of serve points rarely loses service games.
- Average opponent ELO context: if a player has 8/10 form but avg opponent ELO was 1600, that form is less significant than 7/10 against avg ELO 1900.
- H2H: only apply meaningfully if H2H has 3+ recent matches on same/similar surface. Small or old H2H samples are noise — downweight them.
- Tournament trajectory: only meaningful from R3 onwards (2+ wins tracked in this tournament). For R1/R2 or when tournament path shows "N/A", this factor has no data — redistribute its 4% weight mentally to recent_form. Never penalise a player for having no tournament path data.
- Fatigue compounds across rounds: a player who played a 3-hour match yesterday is not the same as one who had 2 days rest, especially in BoF5.

Respond ONLY in the following JSON format (no additional text):
{{
  "pick": "player name who wins",
  "confidence": 67,
  "fair_odds": 1.49,
  "value": true,
  "risk_level": "low|medium|high",
  "risk_notes": "brief explanation of main risks (max 80 chars)",
  "handicap_option": "handicap option description or null",
  "key_factors": ["factor1", "factor2", "factor3"],
  "analysis": "2-3 sentences of key match analysis",
  "skip_reason": null
}}

If the match should be skipped (too much uncertainty, injury, insufficient data), set "skip_reason" to a string with the reason and all other fields to null."""


def analyze_match(match: dict, p1_data: dict, p2_data: dict, h2h: dict, weights: dict, all_news: str = "") -> dict:
    """
    Analizira jedan meč i vraća predikciju.
    p1_data, p2_data: kombinacija player_info + player_stats + form + elo
    """
    p1 = p1_data
    p2 = p2_data
    surface = match.get("surface", "Hard")
    elo_key = f"elo_{surface.lower().replace(' ', '_')}"

    p1_form5 = _format_form(p1.get("form_recent", {}).get("matches", [])[:5])
    p1_form10 = _form_summary(p1.get("form_recent", {}))
    p2_form5 = _format_form(p2.get("form_recent", {}).get("matches", [])[:5])
    p2_form10 = _form_summary(p2.get("form_recent", {}))

    p1_surface_form = _surface_form(p1.get("form_recent", {}).get("matches", []), surface)
    p2_surface_form = _surface_form(p2.get("form_recent", {}).get("matches", []), surface)

    p1_surface_record = _format_surface_record(p1.get("surface_summary", {}), surface)
    p2_surface_record = _format_surface_record(p2.get("surface_summary", {}), surface)

    match_date = match.get("date", "")
    p1_days_rest = _days_since(p1.get("last_match_date", ""), reference_date=match_date)
    p2_days_rest = _days_since(p2.get("last_match_date", ""), reference_date=match_date)

    h2h_surface_key = surface.lower().split()[0]
    h2h_surface_data = h2h.get(h2h_surface_key, {})
    h2h_surface_str = f"{h2h_surface_data.get('p1_wins', 0)}-{h2h_surface_data.get('p2_wins', 0)}" if h2h_surface_data else "N/A"
    h2h_trend = _h2h_trend(h2h)

    odds_p1 = safe_float(match.get("odds_p1", 0))
    odds_p2 = safe_float(match.get("odds_p2", 0))

    prompt = ANALYSIS_PROMPT_TEMPLATE.format(
        player1=match["player1"], player2=match["player2"],
        tournament=match.get("tournament", ""), level=match.get("level", "ATP 250"),
        surface=surface, round=match.get("round", ""), date=match.get("date", ""),
        format="Best of 3" if "Grand Slam" not in match.get("level", "") else "Best of 5",
        round_context=_round_context(match.get("round", ""), match.get("level", ""), match.get("round_id", 0)),

        p1_age=p1.get("age", "N/A"), p1_hand=_format_hand(p1.get("hand", "")),
        p1_ranking=p1.get("ranking", "N/A"), p1_ranking_trend=p1.get("ranking_trend", "N/A"),
        p1_elo_overall=p1.get("elo_overall", 1500), p1_elo_surface=p1.get(elo_key, 1500),
        p1_surface_record=p1_surface_record,
        p1_form_5=p1_form5, p1_form_10=p1_form10, p1_surface_form=p1_surface_form,
        p1_avg_opp_elo=p1.get("avg_opp_elo", "N/A"),
        p1_serve_pts_won=p1.get("serve_points_won", "N/A"),
        p1_hold_pct=p1.get("hold_pct", "N/A"),
        p1_first_serve_pct=p1.get("first_serve_pct", "N/A"),
        p1_aces=p1.get("aces_per_game", "N/A"),
        p1_first_serve_won=p1.get("first_serve_points_won", "N/A"),
        p1_second_serve_won=p1.get("second_serve_points_won", "N/A"),
        p1_bp_saved=p1.get("break_points_saved", "N/A"),
        p1_break_conv=p1.get("break_points_converted", "N/A"),
        p1_return_won=p1.get("return_points_won", "N/A"),
        p1_matches_7d=p1.get("matches_7d", 0),
        p1_sets_7d=p1.get("sets_7d", 0) or "N/A",
        p1_last_match=p1.get("last_match_date", "N/A"),
        p1_days_rest=p1_days_rest,
        p1_tourn_path=p1.get("tournament_path", "N/A"),
        p1_form_trend=p1.get("form_trend", "N/A"),
        p1_news=p1.get("news", "No news") or "No news",

        p2_age=p2.get("age", "N/A"), p2_hand=_format_hand(p2.get("hand", "")),
        p2_ranking=p2.get("ranking", "N/A"), p2_ranking_trend=p2.get("ranking_trend", "N/A"),
        p2_elo_overall=p2.get("elo_overall", 1500), p2_elo_surface=p2.get(elo_key, 1500),
        p2_surface_record=p2_surface_record,
        p2_form_5=p2_form5, p2_form_10=p2_form10, p2_surface_form=p2_surface_form,
        p2_avg_opp_elo=p2.get("avg_opp_elo", "N/A"),
        p2_serve_pts_won=p2.get("serve_points_won", "N/A"),
        p2_hold_pct=p2.get("hold_pct", "N/A"),
        p2_first_serve_pct=p2.get("first_serve_pct", "N/A"),
        p2_aces=p2.get("aces_per_game", "N/A"),
        p2_first_serve_won=p2.get("first_serve_points_won", "N/A"),
        p2_second_serve_won=p2.get("second_serve_points_won", "N/A"),
        p2_bp_saved=p2.get("break_points_saved", "N/A"),
        p2_break_conv=p2.get("break_points_converted", "N/A"),
        p2_return_won=p2.get("return_points_won", "N/A"),
        p2_matches_7d=p2.get("matches_7d", 0),
        p2_sets_7d=p2.get("sets_7d", 0) or "N/A",
        p2_last_match=p2.get("last_match_date", "N/A"),
        p2_days_rest=p2_days_rest,
        p2_tourn_path=p2.get("tournament_path", "N/A"),
        p2_form_trend=p2.get("form_trend", "N/A"),
        p2_news=p2.get("news", "No news") or "No news",

        h2h_overall=f"{h2h.get('p1_wins', 0)}-{h2h.get('p2_wins', 0)} (total {h2h.get('total', 0)})",
        h2h_surface=h2h_surface_str,
        h2h_last=_last_h2h_result(h2h),
        h2h_trend=h2h_trend,
        h2h_reliability=_h2h_reliability(h2h),

        weather=match.get("weather", "N/A"),
        altitude=match.get("altitude", "Normal altitude"),
        p1_tournament_history=_format_tournament_record(p1.get("tournament_record", {})),
        p2_tournament_history=_format_tournament_record(p2.get("tournament_record", {})),
        odds_alert=_odds_alert(odds_p1, odds_p2, match["player1"], match["player2"]),

        w_elo_ranking=weights.get("elo_ranking", 22),
        w_surface_style=weights.get("surface_style", 20),
        w_serve_return=weights.get("serve_return", 22),
        w_recent_form=weights.get("recent_form", 17),
        w_fatigue_injuries=weights.get("fatigue_injuries", 11),
        w_h2h_context=weights.get("h2h_context", 4),
        w_tournament_trajectory=weights.get("tournament_trajectory", 4),
    )

    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODELS["analysis"],
            max_tokens=900,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        result = _safe_json_parse(raw)
        result["match"] = match
        return result
    except Exception as e:
        print(f"Greška analize {match.get('player1')} vs {match.get('player2')}: {e}")
        return {
            "pick": None, "confidence": 0, "fair_odds": None, "value": False,
            "risk_level": "visok", "risk_notes": f"Greška analize: {str(e)[:50]}",
            "handicap_option": None, "key_factors": [], "analysis": "",
            "skip_reason": f"Greška: {str(e)[:100]}", "match": match
        }


def analyze_matches_batch(matches_with_data: list, weights: dict, all_news: str = "") -> list:
    """Analizira listu mečeva sekvencijalno.
    weights may be a flat dict (legacy) or a surface-keyed dict {"clay": {...}, "grass": {...}, "hard": {...}}.
    Per-match weights stored in item["weights"] always take priority.
    """
    is_surface_dict = bool(weights) and any(k in weights for k in ("clay", "grass", "hard"))
    results = []
    for item in matches_with_data:
        if item.get("weights"):
            match_weights = item["weights"]
        elif is_surface_dict:
            from database.supabase_client import _surface_key
            sk = _surface_key(item["match"].get("surface", "hard"))
            match_weights = weights.get(sk) or weights.get("hard") or next(iter(weights.values()))
        else:
            match_weights = weights
        result = analyze_match(
            match=item["match"],
            p1_data=item["p1_data"],
            p2_data=item["p2_data"],
            h2h=item.get("h2h", {}),
            weights=match_weights,
            all_news=all_news
        )
        if result.get("skip_reason"):
            print(f"  Preskačem {item['match']['player1']} vs {item['match']['player2']}: {result['skip_reason']}")
        else:
            conf = result.get("confidence", 0)
            print(f"  {item['match']['player1']} vs {item['match']['player2']}: pick={result.get('pick')}, conf={conf}%")
        results.append(result)
    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_form(matches: list) -> str:
    if not matches:
        return "N/A"
    return " ".join("W" if m.get("won") else "L" for m in matches)


def _form_summary(form: dict) -> str:
    w = form.get("wins", 0)
    l = form.get("losses", 0)
    total = w + l
    return f"{w}/{total}" if total > 0 else "N/A"


def _surface_form(matches: list, surface: str) -> str:
    surface_lower = surface.lower()
    filtered = [m for m in matches if surface_lower in m.get("surface", "").lower()]
    if not filtered:
        return "N/A"
    wins = sum(1 for m in filtered if m.get("won"))
    return f"{wins}/{len(filtered)}"


def _format_surface_record(surface_summary: dict, surface: str) -> str:
    """Formatira career win% na podlozi iz surface_summary dicta."""
    key = surface.lower().split()[0]  # "Clay" → "clay", "Hard" → "hard", "Grass" → "grass"
    if key == "indoor":
        key = "hard"
    data = surface_summary.get(key, {})
    if not data or not data.get("matches"):
        return "N/A"
    return f"{data['wins']}W/{data['losses']}L ({data['win_pct']}%) u {data['matches']} mečeva"


def _round_context(round_str: str, level: str, round_id: int = 0) -> str:
    """Contextual description of the round using numeric round_id (eliminates F ambiguity)."""
    is_gs = "Grand Slam" in level
    fmt = "Best of 5" if is_gs else "Best of 3"

    # Prefer numeric ID — avoids the "F" ambiguity (API uses F for both Final and sometimes other rounds)
    if round_id:
        _ctx = {
            1: f"First round ({fmt}). Large skill gaps possible; qualifiers and lucky losers present. Higher upset potential.",
            2: f"Second round ({fmt}). Qualifiers mostly gone. Some upsets still common.",
            3: f"Third round ({fmt}). Field significantly reduced. Top players usually through.",
            4: f"Round of 16 ({fmt}). Only proven performers remain. Upsets less frequent.",
            5: f"Quarterfinal ({fmt}). Elite level — all 8 players proven over 4-5 matches. Physical fatigue starts to matter.",
            6: f"Semifinal ({fmt}). Top 4 in the draw. Both battle-hardened. Fatigue and mental strength decisive.",
            7: f"Final ({fmt}). Both finalists proven over 6+ matches. Psychological pressure and physical condition critical.",
        }
        if round_id in _ctx:
            return _ctx[round_id]

    # String fallback
    r = round_str.upper().strip()
    if r in ("R128", "R1"):
        return f"First round ({fmt})."
    if r in ("R64", "R2"):
        return f"Second round ({fmt})."
    if r in ("R32", "R3"):
        return f"Third round ({fmt}). Field significantly reduced."
    if r in ("R16", "R4"):
        return f"Round of 16 ({fmt}). Only proven performers remain."
    if r == "QF":
        return f"Quarterfinal ({fmt}). Elite level — physical fatigue starts to matter."
    if r == "SF":
        return f"Semifinal ({fmt}). Both players battle-hardened. Fatigue decisive."
    if r == "F":
        return f"Final ({fmt}). Both finalists proven over 6+ matches."
    return f"Round: {round_str} ({fmt})."


def _odds_alert(odds_p1: float, odds_p2: float, name_p1: str, name_p2: str) -> str:
    """Upozorenje samo ako su kvote ekstremno neuravnotežene — signal ozljede/povlačenja."""
    if not odds_p1 or not odds_p2 or odds_p1 <= 0 or odds_p2 <= 0:
        return ""
    ratio = max(odds_p1, odds_p2) / min(odds_p1, odds_p2)
    if ratio >= 6.0:
        big = name_p1 if odds_p1 > odds_p2 else name_p2
        return f"⚠️ TRŽIŠNI SIGNAL: {big} ima ekstremno visoku kvotu ({max(odds_p1, odds_p2):.2f}) — provjeri ima li vijesti o ozljedi/povlačenju."
    return ""


def _days_since(date_str: str, reference_date: str = None) -> str:
    """Days of rest = match_date - last_match_date.
    Uses actual match date so tomorrow's matches correctly get +1 day of rest."""
    if not date_str or date_str == "N/A":
        return "N/A"
    try:
        import datetime
        last = datetime.date.fromisoformat(str(date_str)[:10])
        ref = (datetime.date.fromisoformat(str(reference_date)[:10])
               if reference_date else datetime.date.today())
        days = (ref - last).days
        return f"{days} days"
    except Exception:
        return "N/A"


def _format_hand(hand: str) -> str:
    if not hand:
        return "N/A"
    h = hand.lower().strip()
    if h in ("left", "l", "ljevica", "left-handed"):
        return "Lijeva (ljevak)"
    if h in ("right", "r", "desnica", "right-handed"):
        return "Desna"
    return hand


def _h2h_reliability(h2h: dict) -> str:
    """Assess if H2H sample is reliable enough to influence prediction."""
    total = h2h.get("total", 0)
    matches = h2h.get("recent_matches", [])
    if total == 0:
        return "No H2H history — ignore H2H factor entirely."
    if total < 3:
        return f"Only {total} meeting(s) — small sample, treat H2H as weak signal only."
    # Check recency — if last match was over 3 years ago, downweight
    if matches:
        last_date = matches[0].get("date", "")[:4] if matches else ""
        try:
            import datetime
            years_ago = datetime.date.today().year - int(last_date)
            if years_ago >= 3:
                return f"{total} meetings but last was {years_ago}y ago — recency low, downweight."
        except Exception:
            pass
    return f"{total} meetings — H2H reliable, apply normally."


def _h2h_trend(h2h: dict) -> str:
    """Trend zadnja 3 H2H meča — tko dominira recentno."""
    matches = h2h.get("recent_matches", [])
    if not matches:
        return "N/A"
    recent = matches[:3]
    winners = [m.get("winner", "") for m in recent if m.get("winner")]
    if not winners:
        return "N/A"
    return " → ".join(winners) if len(winners) > 1 else winners[0]


def _format_tournament_record(record: dict) -> str:
    """Formatira turnirsku historiju za Claude prompt."""
    if not record or not record.get("appearances"):
        return "Nikad nije igrao ovaj turnir"
    total = record["total_wins"] + record["total_losses"]
    win_pct = round(record["total_wins"] / total * 100, 1) if total > 0 else 0
    return (
        f"{record['total_wins']}W/{record['total_losses']}L ({win_pct}%) "
        f"u {record['appearances']} nastupa | "
        f"Najbolje: {record['best_round']} ({record['best_year']}) | "
        f"Zadnje: {record['recent']}"
    )


def _last_h2h_result(h2h: dict) -> str:
    matches = h2h.get("recent_matches", [])
    if not matches:
        return "N/A"
    last = matches[0]
    return f"{last.get('winner', '?')} pobijedio {last.get('date', '')}"
