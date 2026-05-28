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


ANALYSIS_PROMPT_TEMPLATE = """Ti si ekspertni tenis analitičar. Tvoj zadatak je procijeniti sljedeći meč koristeći isključivo pružene podatke i zadane težine.

=== MEČ ===
{player1} vs {player2}
Turnir: {tournament} | Razina: {level}
Podloga: {surface} | Runda: {round}
Datum: {date} | Format: {format}

=== {player1} ===
ATP Ranking: #{p1_ranking} | Ranking trend: {p1_ranking_trend}
ELO (opći): {p1_elo_overall} | ELO ({surface}): {p1_elo_surface}
Rekord na {surface} (zadnje 3 god.): {p1_surface_record}
Forma (zadnjih 5): {p1_form_5} | Forma (zadnjih 10): {p1_form_10}
Forma na {surface} (6 mj): {p1_surface_form}
Servis %: {p1_first_serve_pct} | Asevi/meč: {p1_aces}
Poeni na 1. servis: {p1_first_serve_won} | Poeni na 2. servis: {p1_second_serve_won}
Break lopte spašene: {p1_bp_saved} | Break konverzija: {p1_break_conv}
Return poeni (na 2. servis): {p1_return_won}
Mečevi zadnjih 7 dana: {p1_matches_7d} | Zadnji meč: {p1_last_match}
Poznate ozljede/vijesti: {p1_news}
Win% kao heavy favorit: {p1_fav_winpct}
1. set → meč konverzija: {p1_first_set_conv}

=== {player2} ===
ATP Ranking: #{p2_ranking} | Ranking trend: {p2_ranking_trend}
ELO (opći): {p2_elo_overall} | ELO ({surface}): {p2_elo_surface}
Rekord na {surface} (zadnje 3 god.): {p2_surface_record}
Forma (zadnjih 5): {p2_form_5} | Forma (zadnjih 10): {p2_form_10}
Forma na {surface} (6 mj): {p2_surface_form}
Servis %: {p2_first_serve_pct} | Asevi/meč: {p2_aces}
Poeni na 1. servis: {p2_first_serve_won} | Poeni na 2. servis: {p2_second_serve_won}
Break lopte spašene: {p2_bp_saved} | Break konverzija: {p2_break_conv}
Return poeni (na 2. servis): {p2_return_won}
Mečevi zadnjih 7 dana: {p2_matches_7d} | Zadnji meč: {p2_last_match}
Poznate ozljede/vijesti: {p2_news}
Win% kao heavy favorit: {p2_fav_winpct}
1. set → meč konverzija: {p2_first_set_conv}

=== H2H ===
Ukupno: {h2h_overall}
Na {surface}: {h2h_surface}
Zadnji meč: {h2h_last}

=== KONTEKST ===
Uvjeti: {weather}
Turnirska historia {player1}: {p1_tournament_history}
Turnirska historia {player2}: {p2_tournament_history}
Kretanje kvota: {odds_movement}

=== BOOKMAKER KVOTE ===
{player1}: {odds_p1}
{player2}: {odds_p2}

=== TEŽINE MODELA ===
ELO + ranking trend + kvaliteta protivnika: {w_elo_ranking}%
Podloga + stil igre matchup: {w_surface_style}%
Servis + return statistika: {w_serve_return}%
Forma zadnjih 5-10 mečeva: {w_recent_form}%
Umor + ozljede + raspored: {w_fatigue_injuries}%
H2H + turnirski kontekst: {w_h2h_context}%
Kretanje kvota + market signal: {w_odds_movement}%

=== UPUTA ===
Primijeni navedene težine pri procjeni. Budući da ne igramo sisteme, bitno je da pick bude visoko pouzdan (min 63% confidence).
Uzmi u obzir sve faktore. Za hendikep opciju: predloži samo ako je favorit izrazito dominantan I nema tie-break profila.

Odgovori ISKLJUČIVO u sljedećem JSON formatu (bez ikakvih dodatnih tekstova):
{{
  "pick": "ime igrača koji pobjeđuje",
  "confidence": 67,
  "fair_odds": 1.49,
  "value": true,
  "risk_level": "nizak|srednji|visok",
  "risk_notes": "kratko objašnjenje glavnih rizika (max 80 znakova)",
  "handicap_option": "opis hendikep opcije ili null",
  "key_factors": ["faktor1", "faktor2", "faktor3"],
  "analysis": "2-3 rečenice ključne analize meča",
  "skip_reason": null
}}

Ako meč treba preskočiti (prevelika nesigurnost, ozljeda, nedostupnost podataka), postavi "skip_reason" na string s razlogom, a ostala polja na null."""


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

    h2h_surface_key = surface.lower().split()[0]
    h2h_surface_data = h2h.get(h2h_surface_key, {})
    h2h_surface_str = f"{h2h_surface_data.get('p1_wins', 0)}-{h2h_surface_data.get('p2_wins', 0)}" if h2h_surface_data else "N/A"

    odds_p1 = safe_float(match.get("odds_p1", 0))
    odds_p2 = safe_float(match.get("odds_p2", 0))

    prompt = ANALYSIS_PROMPT_TEMPLATE.format(
        player1=match["player1"], player2=match["player2"],
        tournament=match.get("tournament", ""), level=match.get("level", "ATP 250"),
        surface=surface, round=match.get("round", ""), date=match.get("date", ""),
        format="Best of 3" if "Grand Slam" not in match.get("level", "") else "Best of 5",

        p1_ranking=p1.get("ranking", "N/A"), p1_ranking_trend=p1.get("ranking_trend", "N/A"),
        p1_elo_overall=p1.get("elo_overall", 1500), p1_elo_surface=p1.get(elo_key, 1500),
        p1_surface_record=p1_surface_record,
        p1_form_5=p1_form5, p1_form_10=p1_form10, p1_surface_form=p1_surface_form,
        p1_first_serve_pct=p1.get("first_serve_pct", "N/A"),
        p1_aces=p1.get("aces_per_game", "N/A"),
        p1_first_serve_won=p1.get("first_serve_points_won", "N/A"),
        p1_second_serve_won=p1.get("second_serve_points_won", "N/A"),
        p1_bp_saved=p1.get("break_points_saved", "N/A"),
        p1_break_conv=p1.get("break_points_converted", "N/A"),
        p1_return_won=p1.get("return_points_won", "N/A"),
        p1_matches_7d=p1.get("matches_7d", 0),
        p1_last_match=p1.get("last_match_date", "N/A"),
        p1_news=p1.get("news", "Nema vijesti") or "Nema vijesti",
        p1_fav_winpct=p1.get("fav_win_pct", "N/A"),
        p1_first_set_conv=p1.get("first_set_conv", "N/A"),

        p2_ranking=p2.get("ranking", "N/A"), p2_ranking_trend=p2.get("ranking_trend", "N/A"),
        p2_elo_overall=p2.get("elo_overall", 1500), p2_elo_surface=p2.get(elo_key, 1500),
        p2_surface_record=p2_surface_record,
        p2_form_5=p2_form5, p2_form_10=p2_form10, p2_surface_form=p2_surface_form,
        p2_first_serve_pct=p2.get("first_serve_pct", "N/A"),
        p2_aces=p2.get("aces_per_game", "N/A"),
        p2_first_serve_won=p2.get("first_serve_points_won", "N/A"),
        p2_second_serve_won=p2.get("second_serve_points_won", "N/A"),
        p2_bp_saved=p2.get("break_points_saved", "N/A"),
        p2_break_conv=p2.get("break_points_converted", "N/A"),
        p2_return_won=p2.get("return_points_won", "N/A"),
        p2_matches_7d=p2.get("matches_7d", 0),
        p2_last_match=p2.get("last_match_date", "N/A"),
        p2_news=p2.get("news", "Nema vijesti") or "Nema vijesti",
        p2_fav_winpct=p2.get("fav_win_pct", "N/A"),
        p2_first_set_conv=p2.get("first_set_conv", "N/A"),

        h2h_overall=f"{h2h.get('p1_wins', 0)}-{h2h.get('p2_wins', 0)} (ukupno {h2h.get('total', 0)})",
        h2h_surface=h2h_surface_str,
        h2h_last=_last_h2h_result(h2h),

        weather=match.get("weather", "N/A"),
        p1_tournament_history=p1.get("tournament_history", "N/A"),
        p2_tournament_history=p2.get("tournament_history", "N/A"),
        odds_movement=match.get("odds_movement", "N/A"),

        odds_p1=f"{odds_p1:.2f}" if odds_p1 else "N/A",
        odds_p2=f"{odds_p2:.2f}" if odds_p2 else "N/A",

        w_elo_ranking=weights.get("elo_ranking", 20),
        w_surface_style=weights.get("surface_style", 23),
        w_serve_return=weights.get("serve_return", 18),
        w_recent_form=weights.get("recent_form", 18),
        w_fatigue_injuries=weights.get("fatigue_injuries", 12),
        w_h2h_context=weights.get("h2h_context", 5),
        w_odds_movement=weights.get("odds_movement", 4),
    )

    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODELS["analysis"],
            max_tokens=512,
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
    """Analizira listu mečeva sekvencijalno."""
    results = []
    for item in matches_with_data:
        result = analyze_match(
            match=item["match"],
            p1_data=item["p1_data"],
            p2_data=item["p2_data"],
            h2h=item.get("h2h", {}),
            weights=weights,
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


def _last_h2h_result(h2h: dict) -> str:
    matches = h2h.get("recent_matches", [])
    if not matches:
        return "N/A"
    last = matches[0]
    return f"{last.get('winner', '?')} pobijedio {last.get('date', '')}"
