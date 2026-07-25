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
Age: {p1_age} | Playing hand: {p1_hand} | Country: {p1_country}
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
Age: {p2_age} | Playing hand: {p2_hand} | Country: {p2_country}
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
{h2h_detailed_stats}

=== CONTEXT ===
Conditions: {weather}
Altitude: {altitude}
Venue type: {venue_type}
Tournament draw history — verified API data, last 3 seasons (F/SF/QF/R16):
{tournament_draw_history}
STRICT ANTI-HALLUCINATION RULE:
- Draw history above is the ONLY authoritative source for past champions, finalists, and semifinalists.
- Tournament records below show ONLY aggregate match win/loss COUNTS — the underlying API endpoint is known to contain round-label errors (e.g. labelling a player "Winner" when they did not win the title). Do NOT use them to make any historical claims about who won or reached which round.
- Do NOT write "title defence", "defending champion", "winner last year", "finalist last year", or ANY historical tournament achievement for either player unless they are explicitly listed in the draw history above (e.g. "F: PlayerName def. ...").
- If draw history shows "Nema podataka" — make ZERO historical tournament claims.
- Do NOT invent geographic, political, or biographical claims beyond the literal Country value given above (e.g. "his home country borders the host nation", "he grew up nearby", "fans from the neighbouring country"). Documented error: the model claimed Slovakia borders Croatia to justify a "home crowd" narrative for a Slovak player at a Croatian tournament — Slovakia does not border Croatia. Use the Country field exactly as given; do not reason about geography, borders, or regional ties beyond it.
Tournament record {player1} (aggregate W/L COUNTS ONLY — do not infer round achievements):
{p1_tournament_history}
Tournament record {player2} (aggregate W/L COUNTS ONLY — do not infer round achievements):
{p2_tournament_history}
{odds_alert}

=== SCOUTING PROFILES (secondary evidence — strict usage rules) ===
Curated analyst scouting notes (qualitative priors, snapshot-dated). Usage rules:
- SECONDARY evidence only: may adjust confidence by AT MOST ±3pp, and may act as the
  tie-breaker when the measured factors above are close to even. It must NEVER override
  the measured statistics (ELO, hold%, form, H2H) when they clearly point one way.
- Do NOT double-count: scouting is qualitative context for INTERPRETING the numbers above
  (e.g. "big server" explains a high hold%, it is not a second, independent piece of
  evidence on top of that hold%).
- Style-vs-style matchups ARE a legitimate factor (research shows style matchups can swing
  win probability by several points at equal rating, and the surface amplifies this):
  e.g. big server vs counter-puncher tilts server on grass/indoor, counter-puncher on clay.
  Use the styles + favourable/tough matchup fields together with the CURRENT surface.
- Where a profile says "No reliable scouting profile", do NOT substitute your own memory
  of the player — treat scouting as absent and rely purely on the measured data above.
- Profiles are a snapshot (see date) — recent form/results above always outrank them.
Scouting {player1}: {p1_scouting_block}
Scouting {player2}: {p2_scouting_block}

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
- Confidence calibration (CRITICAL): Historical data shows the model is systematically overconfident. Apply these strict rules: only reach 68% when 4+ independent factors clearly favour the same pick. Only exceed 70% when the edge is overwhelming across ALL factor categories. If 1-2 factors favour the pick but others are neutral or mixed — cap at 64%. A well-calibrated 68% pick should genuinely win ~68% of the time; if unsure, go lower.
{surface_specific_rules}

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


def _surface_specific_rules(surface: str) -> str:
    """Returns surface-specific calibration rules for the analysis prompt.
    Grass rules derived from post-analysis of documented losses (June-July 2026 season).
    Version 3: after Wimbledon post-analysis — un-flatten confidence (remove hard 64% cap),
    strengthen surface-weighted form, add tiebreak/serve-hold as decision drivers.
    Clay rules v1 (2026-07-11): derived from full clay revision — 32 resolved picks
    (28 Roland Garros BO5 + 4 ATP 250 qualifying), 7/7 pure clay tickets lost.
    Dominant loss cause: fading opponents with in-tournament momentum (8/15 losses).
    Hard rules v1 (2026-07-18): written BEFORE any hard match was ever picked (0 hard
    picks in corpus) — rules are cross-surface lessons from 187 unique resolved
    grass+clay picks, marked provisional until validated on real hard data."""
    s = surface.lower()
    if "clay" in s:
        return _CLAY_RULES_V1
    if "hard" in s:      # pokriva "Hard" i "Indoor Hard" — isti model po dogovoru
        return _HARD_RULES_V1
    if "grass" not in s:
        return ""
    return """
=== GRASS-SPECIFIC CALIBRATION RULES v3 (apply these STRICTLY over the general rules above) ===
These rules are derived from documented grass prediction errors this season (June-July 2026).
Every rule below was broken in at least one loss — treat them as hard constraints, not guidelines.

1. ELO gap cap + ELO isolation rule:
   Cap effective ELO advantage at 100 pts regardless of the actual gap.
   CRITICAL: If ELO is the PRIMARY or ONLY differentiating factor (form, serve, fatigue
   are comparable or the opponent has 2/3+ recent form), cap confidence at 61%.
   ELO alone has driven picks at 65-68% that lost. A 200pt ELO gap on grass is NOT a
   reliable predictor without corroborating evidence from form and serve.

2. Surface-weighted form (STRENGTHENED v3 — this rule keeps failing, enforce it hard):
   Recent form MUST be surface-weighted. Hard-court or clay wins do NOT transfer to grass.
   A 5/5 streak built OFF grass counts as ~2-3/5 effective grass form and must NOT be a
   primary confidence driver. Documented losses came exactly from this error:
   Cerundolo (5/5 on hard) lost to Munar; hot-streak picks repeatedly lost on grass.
   Before using ANY hot streak as a driver, verify the SURFACE of those wins. If they are not
   on grass, downgrade the form signal to "moderate at best" and do NOT let it push confidence
   above 63% on its own. A grass specialist with 2/3 grass form beats a 5/5 hard-court streak.

3. Grass specialist threshold (REVISED):
   Under 20 career grass matches: informational only, not a primary confidence driver.
   20-24 matches: moderate signal only.
   25+ matches AND 70%+ win rate: PROVEN SPECIALIST — surface record is a PRIMARY signal.
   Do not classify 30+ matches at 80%+ as a "small sample" — that is the strongest
   grass-specific evidence available. A genuine specialist overrides general form momentum.

4. Rest paradox on grass (unchanged):
   >7 days rest = neutral or slightly negative (rhythm and feel for the surface lost).
   Optimal rest is 1-3 days. Do NOT reward a player with 10+ days layoff.
   A player coming from a recent match (1-2 days rest) may be sharper than one rested 2 weeks.

5. Fatigue rule — TIGHTENED (v2 change):
   The previous rule halved fatigue penalty for players with positive recent form.
   This has been removed for extreme load cases.
   Apply fatigue penalty IN FULL when: 4+ matches in 7 days AND 1-2 days rest.
   Improving form does NOT offset severe physical fatigue on grass — grass demands
   explosive lateral movement and recover, which degrades under sustained load.
   Only halve the fatigue penalty when the player has BOTH: 3 or fewer matches in 7 days
   AND 2+ days rest AND 2/3 or better recent form. All three conditions must hold.

6. In-tournament match sharpness vs. rest/bye (NEW):
   On grass, active tournament wins carry more weight than raw rest days or ATP ranking.
   A player who has won 2-3 matches this week has rhythm, timing, and ball feel.
   A player entering via bye/walkover lacks grass match rhythm — this is a disadvantage,
   NOT a neutral factor. When tournament_trajectory shows "N/A" or the player has a bye:
   flag this as a risk. When opponent has 3/3 in-tournament wins this week, weight
   tournament_trajectory as a PRIMARY signal for the current match, not a minor add-on.

7. Both-players-in-declining-form rule (NEW):
   When BOTH players show 1/3 or worse in their last 3 matches:
   Cap confidence at 60% regardless of ELO, surface record, or other factors.
   Do NOT assess one player's 1/3 as "stable" and the other's as "declining" — they are
   in the same uncertainty category. Apply the same assessment to both sides.

8. Confidence CALIBRATION — spread honestly (v3, REPLACES the old flat 64% cap):
   The previous hard 64% cap flattened every pick to 62-64% and destroyed the model's ability
   to rank locks vs coin-flips (it rated a 1.01 near-certainty and a 1.50 coin-flip both at 63%).
   That cap is REMOVED. Confidence must now SPREAD to reflect the true win probability, anchored
   to this season's grass outcomes:
   - Dominant pick — clear edge in serve/hold AND surface ELO AND grass-relevant form AND a
     proven grass record, with few or no live risks → 72-80%.
   - Solid favourite — edge in most factors, one minor risk → 66-71%.
   - Slight favourite — edge in a couple of factors, others neutral/mixed → 60-65%.
   - Coin-flip / conflicting signals / thin samples → below 60% (excluded by the selection floor).
   CALIBRATION HONESTY (critical): a 75% pick MUST genuinely win ~75% of the time — do NOT
   inflate. But equally, do NOT hedge a genuine dominant favourite down to 63%: commit to it.
   Season data: dominant favourites (all factors aligned) win ~80%; marginal favourites (only
   1-2 factors, others level) win ~35%. Grade accordingly — reserve 70%+ for genuine locks and
   push marginal-favourite matches into the 55-62% band where they belong. A WIDE, honest spread
   is the goal, NOT everything clustered near 63%.

9. Confidence floor honesty (SELECTION-CRITICAL):
   Our tickets only ever use picks at 63%+ confidence — anything below is excluded.
   Therefore be HONEST, not optimistic: if this match is a genuine coin-flip, score it
   BELOW 63% (e.g. 60%) so it is correctly dropped. Do NOT inflate a marginal pick to
   63-64% just to make it ticket-eligible. A falsely-confident 63% is worse than an
   honest 60%, because it puts a coin-flip onto a real-money accumulator.
   Score the pick BELOW 63% whenever ANY of these holds:
   - both players have fewer than 15 career grass matches (thin-sample / qualifying);
   - both players are in 1/3-or-worse recent form;
   - your pick rests mainly on a SINGLE factor (ELO alone, or form alone) while the
     other factors are neutral or mixed;
   - you cannot list at least 3 concrete, grass-specific advantages for your pick.
   Only score 63%+ when you can genuinely name 3+ independent grass advantages.

10. Tiebreaks & serve-hold under pressure — DECISION DRIVERS on grass (NEW v3):
   Grass matches are decided by service holds and tiebreaks far more than any other surface.
   Multiple losses (Paul lost to Hurkacz in a tiebreak; Nakashima lost to Struff 3/4 tiebreaks)
   were decided in tiebreaks the model flagged only as a "risk". Treat these as DECISION drivers,
   not side-notes:
   - Hold% (service games held), NOT raw serve-points-won%, is the key serve metric on grass.
     A player holding 85%+ is very hard to break — weight this heavily toward that player.
   - If the opponent has a strong tiebreak record (from H2H tiebreak stats or a high hold%),
     the match will likely hinge on 1-2 tiebreaks — that is effectively a coin-flip, so LOWER
     confidence rather than backing your pick strongly.
   - Do NOT make a confident pick whose main edge is "better return" while the opponent has
     dominant hold%. On grass, HOLDING beats returning — serve-hold wins tight matches.

11. HOME-CROWD RULE (asymmetric — from cross-surface analysis of 31 home-player matches;
   same rule as clay, added here for parity 2026-07-18 — the underlying evidence was already
   cross-surface, only the rule text had not been propagated to grass):
   If the OPPONENT of our pick plays in his own country (check Country vs tournament host
   country): subtract 3pp from confidence. If that home opponent ALSO has in-tournament
   momentum (2+ wins this week) or the match is otherwise close, score the pick below 63%
   so it drops out — home underdogs in rhythm repeatedly destroyed marginal favourites
   (Fery eliminated 5 of our picks at his home events; Huesler beat our pick in Gstaad).
   If OUR pick is the home player: NO bonus — home picks won at exactly the baseline rate.

12. RANKING-GAP DEFLATION (principle transfer from clay — NO grass-specific incidents
   documented yet, treat as provisional until grass evidence accumulates):
   ATP ranking gaps are NOT a primary grass argument — ranking reflects all surfaces, and
   grass is the most specialised surface on tour. Surface-specific evidence (grass ELO,
   grass W-L record, hold% on grass) outranks raw ranking gap. A grass ELO gap under 30
   points is NOISE — treat such matches as even on that factor and look at the other
   categories instead of leaning on the ranking number.
=== END GRASS-SPECIFIC RULES v3 ==="""


# Clay pravila v1 — izvedena iz clay revizije 2026-07-11 (prije Gstaad/Umag):
# 32 razriješena picka, 17W-15L (53%) uz prosječni confidence 69% (prekalibracija -16pp);
# dead zone kvota 1.50-1.90 pobjeđivala 3/11 (27%); svih 7 čistih clay tiketa izgubljeno.
# Svako pravilo dolje slomljeno je u barem jednom dokumentiranom gubitku.
_CLAY_RULES_V1 = """
=== CLAY-SPECIFIC CALIBRATION RULES v1 (apply these STRICTLY over the general rules above) ===
These rules are derived from documented clay prediction errors this season (Roland Garros +
ATP 250 clay, May-July 2026). Every rule was broken in at least one documented loss —
treat them as hard constraints, not guidelines.

1. DOUBLE-CONFIRMATION RULE (the core clay rule):
   A pick may only reach 66%+ confidence with a clear edge in AT LEAST TWO of these three
   categories: (a) clay ELO / clay W-L record (3y), (b) serve-hold% on clay, (c) recent form
   adjusted for opponent quality (avg opponent ELO).
   If the OPPONENT leads in two of the three categories, score the pick BELOW 61% regardless
   of ATP ranking or overall ELO. Documented losses (Khachanov-De Jong, FAA-Cobolli,
   Brancaccio-Gomez): our pick had a ranking/ELO edge while the opponent had BOTH the better
   clay record AND the better hold% — the opponent won all three matches.
   Every winning pick in the corpus with edges in 2+ categories won.

2. HOT-HAND CAUTION — target genuine UPSET runs, NOT normal advancement (the #1 documented
   loss cause — 8 of 15 clay losses). CORRECTED 2026-07-18: raw win-count is NOT the trigger —
   by the quarterfinal every player already has 2-3 tournament wins (R32→R16→QF), by the final
   4-5, so "3+ wins → veto" would fire on every deep-round match and is not a useful signal.
   Reaching the QF/SF/F normally is NOT a hot hand. Apply a strong caution (cap confidence at
   61%, or skip a marginal favourite) ONLY when ALL of these hold:
   - the opponent of your pick is clearly LOWER-ranked / worse clay ELO than your pick, AND
   - he has beaten a SEEDED or higher-ranked player this week (a real upset, not just wins
     over peers), AND
   - your pick is only a MARGINAL favourite (no double-confirmation edge from rule 1).
   In that exact profile, the pick against him is only allowed if our player is a genuinely
   ELITE clay player: clay ELO >= 1850, or hold% >= 85% combined with the better clay record.
   Two proven favourites who both advanced normally to the SF/F are a normal match — judge
   them on the usual factors, do NOT auto-skip just because both have tournament wins.
   Documented: Mensik eliminated 3 of our picks in a row, Arnaldi 2, Fonseca 2, Svajda 1 —
   the model saw them as "weaker on paper" EVERY following day and kept losing (all were
   genuine upset runs, not just normal advancement). The elite exemption is proven: Zverev
   (clay ELO 2021) beat in-form Jodar and Mensik; Berrettini (hold 90.5%) beat a 5/5 J.M.
   Cerundolo. (Deterministic backstop: a player who already ELIMINATED one of our picks
   twice in this same tournament is auto-vetoed by the ticket builder — you need not model
   that specific case.)
   NEVER fade the same in-form player two days in a row after he already beat one of our picks.

3. BOTH-PLAYERS-DECLINING CAP (same as grass rule — proven on clay too):
   When BOTH players are 1/3 or worse in their last 3 matches: cap confidence at 60%.
   Do not use rest-days or minor stats to "differentiate" two out-of-form players
   (documented: Butvilas-Huesler, both 0/3, we still gave 66% — lost).

4. REST & FATIGUE DIFFERENTIAL (strong filter):
   If our pick played 2+ matches in the last 7 days AND has 2+ fewer rest days than the
   opponent: subtract 4pp from confidence (6pp in Best-of-5). Clay rallies are the longest
   in tennis — freshness converts directly to legs in sets 3-5.
   Symmetrically, a genuine rest edge for our pick (2+ more rest days, no over-rest beyond
   10+ days) is a legitimate PLUS signal (documented wins: Tabilo 4v2 days, Hemery 7v2).

5. RANKING-GAP DEFLATION:
   ATP ranking gaps (even 40+ positions) are NOT a primary clay argument — ranking reflects
   all surfaces. Clay-specific evidence outranks it. A surface ELO gap under 30 points is
   NOISE — treat such matches as even on that factor and look at the other categories.
   Documented losses driven by ranking-gap seduction: Darderi #17 vs #102, Khachanov #15
   vs #106, Faria — all lost to the "worse-ranked" player.

6. UNDERDOG PICK DISCIPLINE (picks against market favourites):
   Backing an underdog is allowed ONLY when supported by clay-specific evidence:
   better clay W-L record over 40+ matches AND better return/break-point numbers AND the
   opponent is NOT in an active tournament run. Small samples (e.g. a 77% Grand Slam win
   rate over 9 matches) must be regressed hard, never cited as a primary driver.
   Documented: value underdogs WITH clay evidence went 4/6 (Tiafoe 2.3, Collignon 2.79 with
   a 79% clay record); underdogs built on small samples or against in-form opponents lost.

7. HOME-CROWD RULE (asymmetric — from cross-surface analysis of 31 home-player matches):
   If the OPPONENT of our pick plays in his own country (check Country vs tournament host
   country): subtract 3pp from confidence. If that home opponent ALSO has in-tournament
   momentum (2+ wins this week) or the match is otherwise close, score the pick below 63%
   so it drops out — home underdogs in rhythm repeatedly destroyed marginal favourites
   (Fery eliminated 5 of our picks at his home events; Huesler beat our pick in Gstaad).
   If OUR pick is the home player: NO bonus — home picks won at exactly the baseline rate.

8. QUALIFYING / THIN-DATA GUARD:
   "R128" at an ATP 250/500 event means QUALIFYING (250 draws have no R128) — players ranked
   150-300, thin data, high variance. Never score qualifying-level matches above 62%.
   If both players have fewer than 30 career clay matches, treat all surface stats as
   weak signals and stay below 63%.

9. CONFIDENCE CALIBRATION — clay reality check (SELECTION-CRITICAL):
   This season's clay outcomes by stated confidence: 63-66% → 75% actual; 66-70% → 38%
   actual (!); 70-75% → 67% actual. The 66-70% band is where overconfident "solid favourite"
   picks go to die. Before scoring 66-70%, ask: does this pick genuinely deserve 70%+?
   If not, it almost certainly belongs BELOW 63% — commit one way or the other.
   Best-of-3 at ATP 250 level carries MORE upset variance than Grand Slam BO5:
   cap confidence 2-3pp lower than you would for the same edge at a Slam.
   Only picks at 63%+ enter tickets — be honest, not optimistic: a falsely-confident 63%
   puts a coin-flip onto a real-money accumulator.

10. CLAY DECIDERS — break-point conversion over aces:
   On clay, return quality and break-point CONVERSION decide matches; aces and raw
   serve-points-won matter less than on any other surface. When serve stats conflict with
   return/BP stats, weight the return side. EXCEPTION: a hold% gap of 5pp+ is decisive on
   any surface (documented: Gomez 77.8% vs Brancaccio 72.3% decided the match) — never back
   the clearly weaker server just because of a surface ELO edge.

11. FAST-CLAY CONDITIONS (from surface-physics analysis, 2026-07-25): not all clay plays
   slow. High altitude (see Altitude context above — e.g. Madrid ~650 m, Gstaad, Kitzbühel)
   and hot/dry weather make the ball fly faster and bounce higher, shifting the surface
   partway toward hard-court behaviour: serve and first-strike quality regain value, and
   the pure-grinder edge shrinks. When Altitude/Conditions above indicate fast clay, soften
   rules 5 and 10 accordingly (a big server is less disadvantaged than on slow, heavy clay).
   Conversely cold/damp "heavy" conditions amplify the standard clay logic.
=== END CLAY-SPECIFIC RULES v1 ==="""


# Hard pravila v1 — pisana 2026-07-18 PRIJE prvog hard picka (korpus: 0 hard mečeva).
# Izvor: revizija 187 unikatnih grass+clay pickova (33 tiketa, 2W-31L) + poznate
# razlike podloga. Svi pragovi su POČETNI i revidiraju se nakon prvih hard tjedana
# (Washington/Los Cabos/Montreal). Struktura tiketa (korisnikova odluka): 6.5-40, 4-6 parova.
_HARD_RULES_V1 = """
=== HARD-SPECIFIC CALIBRATION RULES v1 (apply these STRICTLY over the general rules above) ===
These rules are transferred from a full audit of 187 resolved grass+clay picks (our model has
ZERO hard-court history — be humble). Hard is the most neutral, most predictable surface:
overall ELO/ranking is MORE reliable here than on clay or grass, but our documented failure
modes (hot-hand fades, dead-zone marginal favourites, +7pp overconfidence) are surface-independent
and MUST be enforced from day one.

1. HOT-HAND CAUTION — target genuine UPSET runs, NOT normal advancement (#1 loss cause):
   IMPORTANT: reaching the QF/SF/F normally is NOT a hot hand — by the quarterfinal every
   player already has 2+ tournament wins, so raw win-count means nothing. Do NOT penalise a
   player just for being deep in the draw. The real danger is a LOWER-RANKED / unseeded player
   on a genuine upset run. Apply a strong caution (lower confidence toward 60, or skip a
   marginal favourite) ONLY when ALL of these hold:
   - the opponent of your pick is clearly LOWER-ranked / worse-ELO than your pick (the "weaker
     on paper" player), AND
   - he has beaten a SEEDED or higher-ranked player this week (a real upset, not just wins over
     peers), AND
   - your pick is only a MARGINAL favourite (no double-confirmation edge).
   In that exact profile, do not fade him unless your pick is genuinely ELITE on hard
   (hard ELO >= 1900, or hold% >= 88% with the better hard record). Documented: Fery (low-ranked)
   eliminated SIX of our higher-ranked picks in three weeks. Two proven favourites at the SF/F
   who both advanced normally are a normal match — judge them on the usual factors, do NOT auto-skip.
   (Deterministic backstop: a player who already ELIMINATED one of our picks in this same
   tournament is auto-vetoed by the ticket builder, so you need not model that case.)

2. DOUBLE-CONFIRMATION for 66%+ (calibration deflator):
   Season data: our stated confidence ran ~7pp above reality (63-70% picks won 55-60%).
   A pick may only reach 66%+ confidence with a clear edge in AT LEAST TWO of:
   (a) hard ELO / hard W-L record (3y), (b) serve quality on hard (hold% + tiebreak record),
   (c) recent form adjusted for opponent quality. If the OPPONENT leads two of the three,
   score BELOW 61% regardless of ATP ranking. Be honest: a marginal favourite belongs at
   58-62%, not 64%.

3. MARGINAL-FAVOURITE REALITY CHECK (dead-zone discipline):
   Market odds 1.43-1.60 was our WORST segment all season (50% win rate, -24% ROI) — these are
   matches where the bookmaker sees a coin-flip that our model dressed up as a favourite.
   When your pick's market odds are in that region, demand double-confirmation (rule 2) AND
   at least one decisive hard-specific edge; otherwise score below 63% so selection drops it.

4. TIEBREAK LOTTERY RULE (transferred from grass — hard has the 2nd-highest TB rate):
   If BOTH players hold >= 85% on hard, the match will likely hinge on 1-2 tiebreaks — that is
   a coin-flip. Cap confidence at 62% unless your pick has a clearly superior H2H/tiebreak
   record (use the tiebreak stats provided). First-strike quality (1st-serve points won,
   return-points-won gap) outranks break-point conversion on hard — the serve+1 pattern
   decides points before rallies develop.

5. SURFACE-SWITCH PENALTY (US summer swing — NEW, no precedent in our data):
   In the first two hard tournaments after the clay block (Washington, Los Cabos, Montreal):
   a player who played a clay SF/F within the last 7 days arrives tired and unadapted —
   subtract 3pp and flag it; do not treat his clay wins as transferable form (surface-weighted
   form rule applies — clay wins count ~half toward hard form). Conversely a hard-court
   specialist who SKIPPED the clay block arrives fresh and adapted — small legitimate plus.

6. HEAT / RETIREMENT GUARD (US summer hard is physically brutal):
   Washington and Cincinnati are played in extreme heat/humidity — retirements spike.
   If a player retired or gave a walkover in the last 14 days, or injury news mentions him:
   SKIP the match (set skip_reason) or cap at 60% if evidence is weak. 5% of our season picks
   voided on retirements; expect MORE on summer hard. Fatigue differential matters doubly here.

7. RANKING RELIABILITY (hard-specific — the one place ranking IS trustworthy):
   Unlike clay/grass, overall ELO and ATP ranking are legitimately predictive on hard —
   the surface is neutral and rewards all-court quality. A 150+ overall ELO gap with
   corroborating serve numbers is a real edge. But it still needs ONE corroborating
   hard-specific signal — never rank alone.

8. GRAND SLAM (US Open, BO5) — STRICTER BAR:
   Our Grand Slam picks underperformed ATP 250s on BOTH surfaces (clay GS 54% vs non-GS 67%).
   At the US Open every ticket-eligible pick needs 65%+ honest confidence. BO5 protects true
   favourites but punishes marginal ones — grade the marginal ones below 63 and move on.

9. INDOOR HARD (same model, amplified serve):
   Indoors there is no wind/sun and conditions are faster and uniform — serve dominance is
   AMPLIFIED and upsets are rarer. Favour strong servers and proven indoor performers;
   heavy favourites are slightly MORE reliable indoors, and return-based upset picks less so.

10. CONFIDENCE SPREAD HONESTY (same discipline as grass/clay):
   Only 63%+ enters tickets. Dominant pick (edge in ELO + serve + form, no live risks) → 70-80%.
   Solid favourite with one risk → 64-69%. Marginal/conflicting/thin data → below 63%, commit
   to dropping it. A falsely-confident 64% puts a coin-flip onto a real-money accumulator —
   that error, repeated, is exactly why 31 of our 33 tickets lost.

11. HOME-CROWD RULE (asymmetric — from cross-surface analysis of 31 home-player matches;
   same rule as clay, added here for parity 2026-07-18 — the underlying evidence was already
   cross-surface, only the rule text had not been propagated to hard):
   If the OPPONENT of our pick plays in his own country (check Country vs tournament host
   country): subtract 3pp from confidence. If that home opponent ALSO has in-tournament
   momentum (2+ wins this week) or the match is otherwise close, score the pick below 63%
   so it drops out — home underdogs in rhythm repeatedly destroyed marginal favourites
   (Fery eliminated 5 of our picks at his home events; Huesler beat our pick in Gstaad).
   If OUR pick is the home player: NO bonus — home picks won at exactly the baseline rate.
   NOTE: unlike clay/grass, rule 7 above (RANKING RELIABILITY) means hard does NOT get a
   ranking-gap-deflation rule — on hard, ranking/ELO gaps are legitimately more predictive,
   so deflating them here would contradict our own documented hard-specific evidence.

12. BOTH-PLAYERS-DECLINING CAP (same as grass/clay — added here for parity 2026-07-18):
   When BOTH players show 1/3 or worse in their last 3 matches: cap confidence at 60%
   regardless of ELO, surface record, or other factors. Do NOT assess one player's 1/3 as
   "stable" and the other's as "declining" — they are in the same uncertainty category.
   (Deterministic backstop: the ticket builder excludes such matches from selection
   entirely, so you need not model that consequence — just score honestly.)
=== END HARD-SPECIFIC RULES v1 ==="""


def analyze_match(match: dict, p1_data: dict, p2_data: dict, h2h: dict, weights: dict, all_news: str = "") -> dict:
    """
    Analizira jedan meč i vraća predikciju.
    p1_data, p2_data: kombinacija player_info + player_stats + form + elo
    """
    p1 = p1_data
    p2 = p2_data
    surface = match.get("surface", "Hard")
    _surf_lower = surface.lower()
    if "hard" in _surf_lower:
        elo_key = "elo_hard"
    elif "clay" in _surf_lower:
        elo_key = "elo_clay"
    elif "grass" in _surf_lower:
        elo_key = "elo_grass"
    else:
        elo_key = "elo_hard"

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
        p1_country=p1.get("nationality") or "N/A",
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
        p2_country=p2.get("nationality") or "N/A",
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
        h2h_detailed_stats=_format_h2h_stats(h2h, match["player1"], match["player2"]),

        weather=match.get("weather", "N/A"),
        altitude=match.get("altitude", "Normal altitude"),
        venue_type=(
            "Indoor hard court" if "indoor" in surface.lower()
            else "Outdoor hard court" if surface.lower() == "hard"
            else "N/A"
        ),
        tournament_draw_history=_format_draw_history(
            match.get("draw_history", []), match["player1"], match["player2"]
        ),
        p1_tournament_history=_format_tournament_record(p1.get("tournament_record", {})),
        p2_tournament_history=_format_tournament_record(p2.get("tournament_record", {})),
        p1_scouting_block=_format_scouting(p1.get("scouting") or {}),
        p2_scouting_block=_format_scouting(p2.get("scouting") or {}),
        odds_alert=_odds_alert(odds_p1, odds_p2, match["player1"], match["player2"]),

        w_elo_ranking=weights.get("elo_ranking", 22),
        w_surface_style=weights.get("surface_style", 20),
        w_serve_return=weights.get("serve_return", 22),
        w_recent_form=weights.get("recent_form", 17),
        w_fatigue_injuries=weights.get("fatigue_injuries", 11),
        w_h2h_context=weights.get("h2h_context", 4),
        w_tournament_trajectory=weights.get("tournament_trajectory", 4),
        surface_specific_rules=_surface_specific_rules(surface),
    )

    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODELS["analysis"],
            max_tokens=1500,  # margin za Sonnet high effort (bilo 900 na Haiku)
            # 18.07.2026: najvažnija odluka u pipelineu. Korisnik tražio "high ili extra high";
            # "xhigh" NIJE podržan za ovaj model (API 400: "Supported levels: high, low, max,
            # medium") — korisnik odabrao "high" (ne "max").
            output_config={"effort": "high"},
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        result = _safe_json_parse(raw)
        result["match"] = match
        # Sirovi kontekst za buduću analizu (korisnikov prijedlog 2026-07-18) — namjerno NE
        # ulazi u prompt niti utječe na pick/confidence, samo se sprema u analyzed_matches.
        # context_snapshot.context_version bilježi verziju oblika radi budućih izmjena sheme.
        result["context_snapshot"] = {
            # v2 (25.07.2026): + p1/p2_scouting_confidence — omogućuje kasniju usporedbu
            # WR mečeva sa scoutingom vs bez (je li scouting stvarno pomogao, mjerljivo).
            "context_version": 2,
            "p1_age": p1.get("age"), "p2_age": p2.get("age"),
            "p1_nationality": p1.get("nationality"), "p2_nationality": p2.get("nationality"),
            "match_time": match.get("time", ""),
            "p1_decider_record": p1.get("decider_record"),
            "p2_decider_record": p2.get("decider_record"),
            "p1_previous_tournament_level": p1.get("previous_tournament_level"),
            "p2_previous_tournament_level": p2.get("previous_tournament_level"),
            "p1_scouting_confidence": (p1.get("scouting") or {}).get("confidence"),
            "p2_scouting_confidence": (p2.get("scouting") or {}).get("confidence"),
        }
        _normalize_fair_odds(result, match)
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

def _normalize_fair_odds(result: dict, match: dict) -> None:
    """Veže fair_odds uz confidence i value uz stvarnu kvotu (clay revizija 2026-07-11).

    LLM je fair_odds generirao kao nezavisnu brojku koja je gravitirala na ~1.52 bez
    obzira na kvotu picka (12/15 clay gubitaka imalo fair 1.51-1.54 na kvotama 1.28-2.82),
    pa je edge/value mehanika bila besmislena: value=True nije razlikovao dobitke od
    gubitaka (15W-14L). Sada: fair_odds = 100/confidence (jedna izvorna procjena, ne
    dvije nepovezane), a value = edge >= 3pp prema stvarnoj tržišnoj kvoti picka.
    LLM kvote ionako ne vidi (model misli neovisno o tržištu), pa njegov value flag
    nije imao informacijsku osnovu."""
    conf = safe_float(result.get("confidence") or 0)
    if conf <= 0 or not result.get("pick"):
        return
    result["fair_odds"] = round(100.0 / conf, 2)

    pick = str(result.get("pick", "")).lower()
    p1 = str(match.get("player1", "")).lower()
    if pick and p1 and (pick in p1 or p1 in pick):
        book = safe_float(match.get("odds_p1", 0))
    else:
        book = safe_float(match.get("odds_p2", 0))
    if book and book > 1.0:
        edge_pp = conf - (100.0 / book)
        result["value"] = edge_pp >= 3.0
    else:
        result["value"] = False


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
    """Formatira career win% na podlozi. Za hard prikazuje outdoor i indoor odvojeno."""
    key = surface.lower().split()[0]
    if key == "indoor":
        key = "indoor_hard"

    if key == "hard":
        outdoor = surface_summary.get("hard", {})
        indoor = surface_summary.get("indoor_hard", {})
        parts = []
        if outdoor and outdoor.get("matches"):
            parts.append(f"Outdoor {outdoor['wins']}W/{outdoor['losses']}L ({outdoor['win_pct']}%) — {outdoor['matches']} matches")
        if indoor and indoor.get("matches"):
            parts.append(f"Indoor {indoor['wins']}W/{indoor['losses']}L ({indoor['win_pct']}%) — {indoor['matches']} matches")
        return " | ".join(parts) if parts else "N/A"

    data = surface_summary.get(key, {})
    if not data or not data.get("matches"):
        return "N/A"
    return f"{data['wins']}W/{data['losses']}L ({data['win_pct']}%) — {data['matches']} matches"


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


def _format_h2h_stats(h2h: dict, player1: str, player2: str) -> str:
    """Format bogatih H2H statistika: tiebreak %, deciding set %, BO3/BO5 split."""
    stats = h2h.get("stats", {})
    if not stats:
        return "N/A"
    p1s = stats.get("p1", {})
    p2s = stats.get("p2", {})

    lines = []

    tb_total = p1s.get("tb_total", 0)
    if tb_total:
        p1_pct = p1s.get("tb_pct") or (round(p1s["tb_won"] / tb_total * 100) if tb_total else 0)
        p2_pct = p2s.get("tb_pct") or (round(p2s["tb_won"] / tb_total * 100) if tb_total else 0)
        lines.append(f"Tiebreaks ({tb_total} played): {player1} {p1_pct}% | {player2} {p2_pct}%")

    ds_total = p1s.get("ds_total", 0)
    if ds_total:
        lines.append(
            f"Deciding sets ({ds_total} played): "
            f"{player1} {p1s.get('ds_pct', 0)}% | {player2} {p2s.get('ds_pct', 0)}%"
        )

    bo3 = p1s.get("bo3_total", 0)
    bo5 = p1s.get("bo5_total", 0)
    if bo3 or bo5:
        parts = []
        if bo3:
            parts.append(f"BO3: {p1s['bo3_won']}-{p2s['bo3_won']}")
        if bo5:
            parts.append(f"BO5: {p1s['bo5_won']}-{p2s['bo5_won']}")
        lines.append("Format split: " + " | ".join(parts))

    return "\n".join(lines) if lines else "N/A"


# Scouting profili ispod ovih razina pouzdanosti se NE ubacuju u prompt — autorova vlastita
# legenda u Excelu kaže za njih "do NOT trust or fill from memory". Umjesto profila ide
# eksplicitna "no reliable scouting" poruka koja modelu brani da rupu popuni iz vlastite memorije.
_SCOUTING_MIN_CONFIDENCE = {"High", "Med-High", "Med", "Med-Low"}


def _format_scouting(s: dict) -> str:
    """Format scouting profila za prompt (SEKUNDARNI dokaz — pravila korištenja su u templateu).
    Low/Insufficient/nepostojeći profil → eksplicitna 'absent' poruka, nikad tihi izostanak."""
    if not s or (s.get("confidence") or "") not in _SCOUTING_MIN_CONFIDENCE:
        return ("No reliable scouting profile — do not fill this gap from memory; "
                "rely on the measured data only.")
    parts = [
        f"[confidence: {s.get('confidence')}, snapshot: {s.get('source_date', 'N/A')}]",
        f"Style: {s.get('style') or 'N/A'}",
        f"Best surfaces: {s.get('best_surfaces') or 'N/A'}",
        f"Strengths: {s.get('strengths') or 'N/A'}",
        f"Weaknesses: {s.get('weaknesses') or 'N/A'}",
        f"Favours playing against: {s.get('favourable_matchups') or 'N/A'}",
        f"Struggles against: {s.get('tough_matchups') or 'N/A'}",
    ]
    return " | ".join(parts)


def _format_tournament_record(record: dict) -> str:
    """Formatira turnirsku historiju — SAMO agregatni W/L brojevi.
    best_round i recent su namjerno izostavljeni: taj API endpoint vraća pogrešne
    round labele (npr. Winner za igrača koji nije pobijedio turnir), što uzrokuje
    halucinacije. Za točne podatke o prošlim pobjednicima koristi draw_history."""
    if not record or not record.get("appearances"):
        return "Nikad nije igrao ovaj turnir"
    total = record["total_wins"] + record["total_losses"]
    win_pct = round(record["total_wins"] / total * 100, 1) if total > 0 else 0
    return (
        f"{record['total_wins']}W/{record['total_losses']}L ({win_pct}%) "
        f"across {record['appearances']} edition(s)"
    )


def _norm_name(s: str) -> str:
    """Normalizacija imena: bez dijakritika, lowercase, spojnice → razmaci."""
    import unicodedata
    s = unicodedata.normalize("NFKD", s.lower().strip())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("-", " ")


def _format_draw_history(draw_rows: list, player1: str, player2: str) -> str:
    """
    Formatira stvarne draw podatke zadnjih 3 sezone za Claude prompt.
    Prikazuje tko je pobijedio turnir, tko je igrao final, SF, QF.
    Sprječava halucinacije jer Claude vidi STVARNA imena pobjednika.
    """
    if not draw_rows:
        return "Nema podataka (API greška ili turnir nije prethodno igran)."

    from collections import defaultdict
    by_year: dict = defaultdict(lambda: defaultdict(list))
    for row in draw_rows:
        yr = row.get("season_year", 0)
        rn = row.get("round_name", "")
        w = row.get("winner_name", "")
        l = row.get("loser_name", "")
        if w and l and yr and rn:
            by_year[yr][rn].append(f"{w} def. {l}")

    lines = []
    for yr in sorted(by_year.keys(), reverse=True):
        rounds = by_year[yr]
        parts = []
        for rn in ["F", "SF", "QF", "R16"]:
            if rn in rounds:
                parts.append(f"{rn}: {' | '.join(rounds[rn])}")
        if parts:
            lines.append(f"  {yr}: " + "  /  ".join(parts))

    p1_norm = _norm_name(player1)
    p2_norm = _norm_name(player2)

    for pnorm, pname in [(p1_norm, player1), (p2_norm, player2)]:
        appearances = []
        for row in sorted(draw_rows, key=lambda r: r.get("season_year", 0), reverse=True):
            wnorm = _norm_name(row.get("winner_name", ""))
            lnorm = _norm_name(row.get("loser_name", ""))
            rn = row.get("round_name", "")
            yr = row.get("season_year", "")
            if pnorm in wnorm or wnorm in pnorm:
                appearances.append(f"{yr} {rn}W")
            elif pnorm in lnorm or lnorm in pnorm:
                appearances.append(f"{yr} {rn}L")
        if appearances:
            lines.append(f"  {pname}: {', '.join(appearances[:6])}")

    return "\n".join(lines) if lines else "Nema podataka."


def _last_h2h_result(h2h: dict) -> str:
    matches = h2h.get("recent_matches", [])
    if not matches:
        return "N/A"
    last = matches[0]
    return f"{last.get('winner', '?')} pobijedio {last.get('date', '')}"
