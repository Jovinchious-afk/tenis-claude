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


# Puštaju li se break-lopta statistike u prompt.
#
# Do 07.08.2026 su `break_points_saved` i `break_points_converted` bili UVIJEK None jer je
# `get_player_stats` tražio krive nazive polja (`breakPointOf` umjesto `breakPointFacedGm`
# itd.) — `.get()` na nepostojeći ključ ne baca grešku, pa je model od prvog dana čitao
# "BP saved: None | BP converted: None" i to nitko nije primijetio.
#
# UKLJUČENO 08.08.2026 11:35 uz korisnikovo odobrenje (do tada False, dok je model bio
# zamrznut radi čistog pripisivanja). Dokaz iz hard analize 08.08.2026 (n=42 meča sa
# statistikom poravnatom na naš pick):
#   - tko napravi više breakova od protivnika ide 21W-1L, tko manje 1W-17L;
#   - naš pick u PORAZIMA prima 8,6 break lopti naspram 5,0 u pobjedama (p=0,002);
#   - "primljene break lopte" je najjača pojedinačna korelacija s ishodom u cijelom
#     skupu (r=-0,44, p=0,002) — jača od iskoristivosti vlastitih prilika (r=+0,19,
#     p=0,250, dakle neznačajna);
#   - svih 16 analiza gubitaka na hardu imenuje servis/hold kao promašeni faktor.
# Drugim riječima: gubimo jer našem igraču servis bude napadnut, ne jer propušta prilike —
# a to je jedina varijabla koju model do danas nije vidio.
#
# ZAMKA ZA BUDUĆU ANALIZU: `rules_hash` se ovom izmjenom NIJE promijenio (0477edbb), jer se
# tekst prompta nije dirao — mijenja se samo vrijednost koja se u njega upisuje. Era prije
# i poslije break lopti zato se NE razdvaja po rules_hashu, nego po
# `context_snapshot.bp_in_prompt` (False do 08.08.2026 11:35, True poslije) ili po
# `context_version` (8 -> 9). Rezati po hashu ovdje bi spojilo dvije različite ere u jednu.
_BP_TO_PROMPT = True

# DOB U PROMPTU — NAMJERNO ISKLJUCENA (15.08.2026 09:19).
#
# Dohvat dobi je danas popravljen (`_get_age` je trazio kriv naziv kljuca, pa je u promptu
# stajalo "Age: N/A" za svaki meč ikad — vidi data_fetcher). Od sada dob POSTOJI, ali
# NAMJERNO ne ide u prompt, nego samo u `context_snapshot`, iz dva razloga:
#
# 1. IZMJERENO: dob nema prediktivnu vrijednost. Retroaktivno dohvacena dob za 242 meca
#    (sve podloge, svi mecevi a ne samo nasi pickovi): mladji pobjeduje 51,5% (P=0,691);
#    nijedan dobni duel ne prolazi prag (testirano 10 celija, nijedna p<0,05); po velicini
#    razlike u godinama nista (1-2 g. 52,1%, 3-5 g. 48,8%, 6-8 g. 61,8%, 9+ g. 49,2%).
#    Presudno: mladji pobjeduje 50,7% a trziste ocekuje 50,8% — razlika -0,1pp, P=1,000.
#    Trziste dob vec ima u cijeni; nema ostatka za iskoristiti.
# 2. ATRIBUCIJA: 15.08. traje dogovoreno mjerenje ucinka stropa 64% (korisnik: cekamo 4-5
#    dana Cincinnatija prije ijedne izmjene modela). Pustanje nove varijable u prompt usred
#    tog prozora pokvarilo bi upravo ono sto mjerimo.
#
# Isti obrazac kao kod break lopti 07.08.: podatak se PRVO skuplja i mjeri, tek onda
# eventualno ulazi u odluku. Za ukljucivanje je dovoljno postaviti ovo na True.
#
# ZAMKA ZA BUDUCU ANALIZU: `rules_hash` se ovim NE mijenja (predlozak prompta je netaknut),
# pa se era prije/poslije dobi NE smije rezati po hashu nego po `context_version` >= 12.
_AGE_TO_PROMPT = False

# CJELOVIT POPIS ULAZA U ODLUKU: vidi `DECISION_INPUTS.md` (08.08.2026 12:30) — što ulazi u
# prompt, što u deterministički kod, a što se samo bilježi. Ondje je i otvorena zamjerka o
# tome da se nesigurne procjene ovdje prikazuju bez ikakve mjere pouzdanosti (npr.
# `Hold % (est.)` čija je varijacija od meča do meča 7,9pp, a pravila razlučuju na 1,6-2,6pp).
#
# OGRADA NA PRAVILO "LATE-ROUND PRICING DISCIPLINE" (zapisano 07.08.2026).
#
# Namjerno stoji OVDJE, izvan templatea: `rules_hash` u `_model_stamp` je md5 nad
# (surface pravila + ANALYSIS_PROMPT_TEMPLATE), pa bi svaki znak dodan unutar stringa
# promijenio žig ere modela — a i model bi to čitao kao uputu. Python komentar uz template
# ne mijenja ni jedno ni drugo.
#
# Brojke u tom pravilu (−10,2% ROI za kratke kvote u QF/SF/F, +11,2% za duže, n=59/21)
# izmjerene su 26.07.2026 na oznakama rundi za koje je 07.08. utvrđeno da su bile krive na
# 42,6% redaka: `_infer_rounds` je grupirao po danu umjesto po rundi, ljestvica za Masters
# stajala je na R32, a brojanje se od 27.07. radilo NAKON screenshot-gatea. Sve troje je
# popravljeno 07.08., ali POVIJESNE oznake nisu — prava runda se ne da pouzdano
# rekonstruirati (nedostaju nescreenshotani mečevi, ima slobodnih prolaza).
#
# Pravilo je zato ZADRŽANO ali NEPOTVRĐENO: smjer je i dalje uvjerljiv, nije opovrgnuto,
# ali brojke ne treba citirati kao izmjerene. Ponovno izmjeriti tek na uzorku skupljenom
# od 07.08.2026 nadalje, kad oznake rundi budu pouzdane.
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
Tiebreaks (own record): {p1_tb_record} | Deciding sets (Bo3 2-1): {p1_decider_record}
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
Tiebreaks (own record): {p2_tb_record} | Deciding sets (Bo3 2-1): {p2_decider_record}
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
Local start time at the venue: {local_time} ({session} session)
Court pace this event (share of sets going to a tiebreak): {court_pace}
Market check (NOT an input — see MARKET PRICE rule below): {market_line}
Tournament draw history — verified API data, last 3 seasons (F/SF/QF/R16):
{tournament_draw_history}
STRICT ANTI-HALLUCINATION RULE:
- Draw history above is the ONLY authoritative source for past champions, finalists, and semifinalists.
- Tournament records below show ONLY aggregate match win/loss COUNTS — the underlying API endpoint is known to contain round-label errors (e.g. labelling a player "Winner" when they did not win the title). Do NOT use them to make any historical claims about who won or reached which round.
- Do NOT write "title defence", "defending champion", "winner last year", "finalist last year", or ANY historical tournament achievement for either player unless they are explicitly listed in the draw history above (e.g. "F: PlayerName def. ...").
- If draw history shows "Nema podataka" — make ZERO historical tournament claims.
- Do NOT invent geographic, political, or biographical claims beyond the literal Country value given above (e.g. "his home country borders the host nation", "he grew up nearby", "fans from the neighbouring country"). Documented error: the model claimed Slovakia borders Croatia to justify a "home crowd" narrative for a Slovak player at a Croatian tournament — Slovakia does not border Croatia. Use the Country field exactly as given; do not reason about geography, borders, or regional ties beyond it.
- Read the draw history for what it ACTUALLY says about each player, including losses. Documented error: the model wrote "Van Assche won 2023 R16 here" when the draw history for that event explicitly recorded "2023 R16: Davidovich Fokina def. Luca Van Assche" — i.e. he lost that match. Before citing any past result, confirm the player's name is on the WINNING side of that specific line.
- BALANCED CITATION (mandatory): if you cite tournament history as evidence FOR your pick, you must first check the SAME history for the opponent and for your pick's recent failures there, and mention anything comparable or stronger. Documented error: the model cited "Rublev won this title in 2023" to support picking Rublev, while the very same draw history in this prompt showed "Darderi: 2025 FW" (the opponent won the title more recently) and "2024 R16: Tirante def. Rublev" (our pick lost early on his most recent appearance). Citing only the half that supports your pick is a reasoning error even when the individual fact is true. Either present both sides or do not use tournament history as a key factor at all.
Tournament record {player1} (aggregate W/L COUNTS ONLY — do not infer round achievements):
{p1_tournament_history}
Tournament record {player2} (aggregate W/L COUNTS ONLY — do not infer round achievements):
{p2_tournament_history}

=== CAREER FINALS EXPERIENCE (verified API counts) ===
Relevant mainly from the quarterfinal onwards: how often each player has BEEN in a final and
how often he CLOSED it. A player with many finals played and a high conversion rate handles
closing pressure better than one with a poor conversion record; a player with no tour-level
finals is unproven in that specific situation. Treat this as a supporting factor for late
rounds (QF/SF/F), not as a driver in early rounds.
{player1}: {p1_titles}
{player2}: {p2_titles}
{odds_alert}

=== SCOUTING PROFILES (secondary evidence — strict usage rules) ===
Curated analyst scouting notes (qualitative priors, snapshot-dated). Usage rules:
- SECONDARY evidence only: may adjust confidence by AT MOST ±3pp, and may act as the
  tie-breaker when the measured factors above are close to even. It must NEVER override
  the measured statistics (ELO, hold%, form, H2H) when they clearly point one way.
- A CAP IS A CEILING, NOT A STARTING POINT (added 2026-08-04): when any rule caps this
  match, scouting may only move confidence DOWN from that cap — never up through it.
  Documented failure: Landaluce vs Mejia, where rule 2's "one overwhelming category" cap
  of 64% was treated as a base and +1pp of scouting was added on top for a final 65%.
  That pick lost. If a cap applies, the cap is the maximum, full stop.
- THE ±3pp BUDGET SCALES WITH THE PROFILE'S OWN CONFIDENCE (added 2026-08-04). Each block
  states its confidence — honour it instead of treating every profile as equal evidence:
    High / Med-High -> the full ±3pp is available.
    Med             -> at most ±2pp.
    Med-Low         -> ASYMMETRIC: it may raise DOUBT about a pick, but it may never be
                       cited as support FOR one. If the only thing backing your pick is a
                       Med-Low profile, you do not have that evidence at all.
  Reason (measured 2026-07-31): the three scouting profiles that turned out to be plainly
  wrong — Van Assche ("needs a weapon", then beat Rublev and won Estoril), Halys (who then
  beat three of our picks in one week and took the title) and Majchrzak — were ALL Med-Low,
  and all three participated in losses. Med-Low means "partial data", which is exactly the
  profile most likely to be stale on a riser. One third of the table (50 of 150) is
  Med-Low, so this is not a rare edge case.
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

LATE-ROUND PRICING DISCIPLINE (QF/SF/F — measured on our own 2026 corpus, all surfaces):
In quarterfinals, semifinals and finals our SHORT-PRICED picks have systematically
underperformed their price while our higher-priced picks have outperformed theirs:
  - late-round picks at odds <= 1.60: 66.1% win rate but -10.2% ROI (n=59)
  - late-round picks at odds >  1.60: 57.1% win rate but +11.2% ROI (n=21)
  - finals specifically are our worst round overall (55.6% win rate, -27.4% ROI, n=9)
By the quarterfinal the field has narrowed to players who have all proven themselves that
week, so the true gap between them is smaller than ratings and reputation suggest, and the
market's favourite is more likely to be over-priced. Therefore, from the QF onwards:
  - do NOT inflate confidence for a heavy favourite purely on rating/reputation — require
    the same double-confirmation you would demand anywhere else;
  - a well-supported underdog in a late round is a legitimate, historically profitable pick,
    not a gamble to be avoided — if the evidence genuinely favours him, say so and price it;
  - treat a final as the highest-variance round of the tournament, not the safest.
This is a pricing/calibration rule, not an instruction to prefer underdogs blindly.
UPDATE 2026-08-02 — the hard-court corpus confirms the round effect but NOT the underdog
half: on hard, late rounds lose at every price (<=1.60: 64%, -11.5%; >1.60: 50%, -7.5%).
So on hard, treat late rounds as harder across the board rather than as an underdog
opportunity; the underdog finding above still stands for clay and grass.

WHEN A BIG UNDERDOG IS A LEGITIMATE PICK (added 2026-08-02):
You are ALLOWED — and on the evidence, expected — to back a genuine underdog when the
case is real. Measured across our whole 2026 season: picks at odds 2.30-2.60 returned
+79.4% ROI (6W-2L) and picks above 2.60 returned +7.4% (3W-5L), while our largest band
(1.30-1.60, n=93) LOST 10.2%. Short favourites are where we bleed, not long shots.
The distinction that matters is WHERE the disagreement with the market comes from, not
how large it is:
  - LEGITIMATE: at least TWO of the rule-2 categories independently favour the underdog —
    e.g. he holds serve 3pp+ better on a fast court, or his surface win rate is clearly
    higher while the opponent's is at or below 50%, or a Med+ scouting profile describes a
    style matchup that genuinely troubles the favourite. Then a 20-28pp disagreement with
    the market is a defensible claim ("this is closer to even than the price says"), and
    you should state the confidence you actually believe.
  - NOT LEGITIMATE: the only argument is a rating gap, a hunch, or "he is due". A large
    disagreement with no measured backing is our documented failure mode (Collignon @2.82
    scored 71% on an imagined edge, lost).
If you back an underdog on this basis, say so EXPLICITLY in key_factors point 6: name the
two categories that back him and the margin in each. If you cannot name two, do not make
the pick — score it honestly below the floor and move on.
NOTE on the claim you are making: with a favourite, claiming 70% against a market price of
50% asserts "this is a lock" — that is where we have historically been wrong. With an
underdog, claiming 63% against a market price of 40% asserts only "this is nearer even
than priced", which is a far more modest and defensible statement. Calibrate accordingly.

Key analytical priorities:
- Surface-specific ELO outweighs ATP ranking. A player ranked #15 with clay ELO 1750 is better on clay than a #8 with clay ELO 1680.
- Hold% and serve dominance are the strongest predictors in ATP tennis (especially hard/grass). A player who wins 70%+ of serve points rarely loses service games.
- Average opponent ELO context: if a player has 8/10 form but avg opponent ELO was 1600, that form is less significant than 7/10 against avg ELO 1900.
- H2H: only apply meaningfully if H2H has 3+ recent matches on same/similar surface. Small or old H2H samples are noise — downweight them.
- Tournament trajectory: only meaningful from R3 onwards (2+ wins tracked in this tournament). For R1/R2 or when tournament path shows "N/A", this factor has no data — redistribute its 4% weight mentally to recent_form. Never penalise a player for having no tournament path data.
- Fatigue compounds across rounds: a player who played a 3-hour match yesterday is not the same as one who had 2 days rest, especially in BoF5.
- Confidence calibration (CRITICAL): Historical data shows the model is systematically overconfident. Apply these strict rules: only reach 68% when 4+ independent factors clearly favour the same pick. Only exceed 70% when the edge is overwhelming across ALL factor categories. If 1-2 factors favour the pick but others are neutral or mixed — cap at 64%. A well-calibrated 68% pick should genuinely win ~68% of the time; if unsure, go lower.
{surface_specific_rules}

INTERNAL CONSISTENCY (mandatory): "risk_notes" and "key_factors" must not contradict each
other. Documented error: risk_notes said "Shevchenko fresher (2 vs 13 rest days)" while
key_factors in the SAME analysis said "Struff's 13 days rest — fatigue factor favours Struff";
the player with 2 days rest was labelled the fresher one. Before returning, re-read your
risk_notes against your key_factors and the data above: every name, number and direction
("fresher", "better", "more rested") must point the same way in both fields. If a field is
too short to state the comparison correctly, name the player the risk applies TO rather than
compressing it into an ambiguous phrase.

DECLARE YOUR CAPS — AND THEN OBEY THEM (mandatory, added 2026-08-04):
Several rules above impose a confidence CEILING. Our own record shows you reason your way
to the correct ceiling and then emit a higher number anyway. Four documented cases, all on
hard, three of them in a single losing week:
  - "rule 16's cap of 62% ... is technically triggered"          -> you emitted 64
  - "the cap at 60% is nearly triggered but ... I apply a
     moderate rather than full penalty"                          -> you emitted 63  (LOST)
  - "Cap held at 60% per rule 12 - below 63% threshold"          -> you emitted 63  (LOST)
  - "start at 64% (overwhelming rating), +1pp for style"         -> you emitted 65  (LOST)
Therefore: list EVERY ceiling you conclude applies to this match in "applied_caps", as
{{"rule": "<rule number or short name>", "cap": <integer percent>}}. Use [] when none apply.
Rules:
  - List a cap only if you conclude it BINDS this match. A ceiling you considered and
    ruled out does not belong here — say so in key_factors instead. Concretely: if
    anywhere in your answer you write that a rule "does not trigger", "does not bind",
    "does not apply" or "is not met", that rule MUST NOT appear in "applied_caps".
    Observed failure of exactly this kind: rule 12 was listed as a binding 60% cap while
    key_factors argued "rule 12 strictly requires BOTH players at 1/3 or worse; Mejia is
    3/3, so rule 12 does NOT bind". Over-declaring is not the safe side — it silently
    deletes picks that were never capped.
  - "Nearly triggered", "technically triggered" and "triggered but softened" all mean
    TRIGGERED. If you find yourself writing a sentence that concedes the cap and then
    negotiates around it, the cap binds — list it.
  - Your "confidence" MUST NOT exceed the lowest cap you list. This is enforced
    mechanically after you answer: a higher number is silently lowered to that cap, so
    emitting one gains you nothing and only makes your written reasoning inconsistent
    with the stored number.
  - If obeying the cap puts the pick below the 63% floor, that is the correct outcome —
    the pick drops out. That is the rule working, not a failure.

WEATHER AND CONDITIONS MAY ONLY LOWER CONFIDENCE (added 2026-08-04):
Temperature, humidity, wind and rain are real and you should keep reading them — but until
we have measured evidence they may act in ONE direction only: they may flag a risk to your
pick and reduce confidence. They may NEVER be cited as a reason to raise confidence or as
support FOR your pick. Reason: in a single rainy week at one venue the same 89-92% humidity
was used as an argument FOR one pick ("slower, heavier court suits his baseline game" —
Van Assche, lost) and as a dismissed risk against another (Berrettini, lost). A variable
that argues both ways in the same week at the same venue is narrative, not evidence.
We are now logging conditions per match; when the data can settle the question this
restriction will be revisited. Until then: conditions cool a pick, they never warm it.
This does NOT apply to the measured "Court pace this event" figure or the local session
(day/night) in rule 14 — those are measured, not forecast, and keep their two-way use.

WIND (added 2026-08-04, from Tennis_Surface_Analysis.docx — the one condition in that
document that had no rule anywhere in this prompt until now):
Wind is not just noise, it has a DIRECTION: it "penalises high-margin spin games and
rewards flatter, more controlled hitting". The mechanism is confirmed in reverse by the
same document's indoor section — remove wind and precision aggressors and flat hitters
gain the most, while heavy-topspin players "who rely on wind/heat to make the ball jump
lose some of that weapon". Read the Wind figure in Conditions above:
  - below ~15 km/h  -> ignore it, this is normal air.
  - ~15-25 km/h     -> meaningful. If OUR PICK is the heavy-topspin / high-margin /
                       spin-reliant player, or a pure defender without a first strike,
                       treat it as a live risk and shade confidence down.
  - above ~25 km/h  -> strong. The same penalty applies harder, and shot-tolerance and
                       error control outweigh raw pace for BOTH players — widen your
                       uncertainty and be reluctant to sit above the floor at all.
Use the style fields in SCOUTING PROFILES to decide which player is which; if neither
profile establishes a style, you cannot apply this rule — say so rather than guessing.
DIRECTION LIMIT: like all conditions, wind may only LOWER confidence. If our pick is the
flat, controlled hitter, wind is simply not a risk flag for him — that is NOT a reason to
raise his number. These thresholds come from the source document and general tennis
knowledge, NOT from our own measured corpus; wind is logged per match from today, so this
rule is a candidate for revision once we can test it.

Respond ONLY in the following JSON format (no additional text):
{{
  "pick": "player name who wins",
  "confidence": 67,
  "fair_odds": 1.49,
  "value": true,
  "risk_level": "low|medium|high",
  "risk_notes": "brief explanation of main risks (max 80 chars)",
  "handicap_option": "handicap option description or null",
  "applied_caps": [{{"rule": "16", "cap": 62}}],
  "above_64_basis": null,
  "market_check": null,
  "key_factors": ["1. Rating: ...", "2. Serve/return: ...", "3. Form vs opponent quality: ...", "4. Style matchup: ...", "5. Fatigue & conditions: ...", "6. Own read: ..."],
  "analysis": "2-3 sentences of key match analysis",
  "skip_reason": null
}}

CONFIDENCE CEILING AT 64% (added 2026-08-13, measured on the full Montreal hard corpus):
Anything you state above 64% has, on our own record, been worse than useless. Measured on
84 resolved hard analyses:
  - your 63-64% band delivered 62.5% (n=40) — essentially perfect calibration;
  - your 65-67% band delivered 50.0% (n=20) with ROI -34.8%;
  - removing that band alone turns the whole corpus from -6.9% ROI to +1.8%.
The reason is structural, not bad luck: your scale saturates near 67%, so "67%" is not a
statement of strong belief — it is the ceiling being hit, and it gets applied to matches
whose real gap ranges from near-even to overwhelming. In that band your number sat on
average 10.7pp BELOW the market price, meaning you were picking heavy favourites while
rating them lower than the market did, and still calling it high confidence.
THEREFORE: 64% is a hard ceiling unless you can fill "above_64_basis" with BOTH of:
  (a) at least TWO independent MEASURED confirmations, each naming the number
      (e.g. "hard ELO +180", "hold 86.4% vs 78.1%", "3-0 H2H on hard"), from DIFFERENT
      categories — two serve numbers are ONE confirmation, not two; and
  (b) one sentence saying what would have to be true for this pick to lose.
If you cannot supply both, state 64 or lower. Do not treat 64 as a target either — most
matches belong below it. An unjustified number above 64 is clamped to 64 by code, and the
clamp is logged, so writing it anyway gains you nothing.

MARKET PRICE — A CHECK, NEVER AN INPUT (added 2026-08-13, user's explicit instruction):
The bookmaker price for this match is shown in the CONDITIONS block as "Market check".
It is NOT a probability input and must NOT enter your estimate. Form your number from the
statistical factors and weights ALONE, exactly as before. Only AFTER you have your number,
compare it with the price, and fill "market_check":
  - if your probability is within 10pp of the market's, write null;
  - if it differs by more than 10pp in either direction, write ONE sentence naming the
    concrete measured fact that justifies the disagreement.
Why this direction matters, measured on our corpus: picks where we sat MORE THAN 10pp ABOVE
the market went 2W-6L (ROI -52.5%) — when we most disagreed upward, we were most wrong.
Picks within 10pp of the market went 36W-21L (ROI 0.0%). So a large gap is a warning about
US, not a discovery about the market. If you cannot name a concrete measured fact for the
gap, that is itself evidence your number is too extreme — move it toward the market and say
so. You are NOT being asked to copy the price; you are being asked to notice when you have
drifted far from it without a reason you can name.

KEY_FACTORS FORMAT (mandatory structure, added 2026-07-31):
Entries 1-5 are FIXED and must ALWAYS be present, in this exact order, each prefixed with
its number and label. Never omit one: if the data is missing, write "no data" and say what
is missing. Measured reason for this rule: analyses that listed only 3 factors went 3W-3L
(50%) while analyses listing 5+ went 9W-2L (82%) — a short list meant thin evidence, not a
simple match, and every hard loss except one came from a 3-factor analysis.
  1. Rating — hard ELO, ATP ranking and hard W-L record (this is ONE category, see rule 2)
  2. Serve/return — hold%, return points won, break-point saved/converted, tiebreak record
  3. Form vs opponent quality — recent form weighted by average opponent ELO
  4. Style matchup — from the SCOUTING PROFILES section; say "no reliable profile" if absent
  5. Fatigue & conditions — rest days, sets played, weather, local start time, day/night
  6. Own read — FREE-FORM AND ENCOURAGED. Anything the five fixed slots do not capture:
     a specific tactical read, an anomaly in the data, a doubt about your own pick, or a
     reason this match resists the usual framework. You are NOT limited to the categories
     above; if you see something that matters and has no slot, this is where it belongs.
     Include it whenever you have a genuine insight — including arguments AGAINST your own
     pick. Omit only if you truly have nothing to add beyond 1-5.

If the match should be skipped (too much uncertainty, injury, insufficient data), set "skip_reason" to a string with the reason and all other fields to null."""


_model_stamp_cache: dict = {}


def _format_wl_record(rec: dict, label: str) -> str:
    """W-L zapis s postotkom; 'no data' kad uzorka nema (31.07.2026 — key_factors format
    zahtijeva eksplicitno 'no data' umjesto tihog izostanka)."""
    if not rec:
        return "no data"
    w, l = int(rec.get("won") or 0), int(rec.get("lost") or 0)
    if w + l == 0:
        return f"no data (0 {label} in last 10 matches)"
    return f"{w}W-{l}L ({round(w / (w + l) * 100)}%)"


def _model_stamp(surface: str) -> dict:
    """Žig verzije modela za context_snapshot (v3, 26.07.2026): omogućuje kasnije EGZAKTNO
    rezanje kalibracijskog korpusa po erama modela umjesto rekonstrukcije iz datuma
    revizija. rules_hash je md5 nad (surface pravila + univerzalni template) pa se mijenja
    AUTOMATSKI sa svakom izmjenom prompta — nema ručnog održavanja verzije; weights_version
    je broj aktivne verzije iz model_weights. Cache po procesu (1 DB upit po podlozi)."""
    key = (surface or "hard").lower()
    if key in _model_stamp_cache:
        return _model_stamp_cache[key]
    import hashlib
    rules_hash = hashlib.md5(
        (_surface_specific_rules(surface or "") + ANALYSIS_PROMPT_TEMPLATE).encode("utf-8")
    ).hexdigest()[:8]
    version = None
    try:
        from database.supabase_client import get_active_weight_version
        version = get_active_weight_version(surface or "hard")
    except Exception:
        pass
    _model_stamp_cache[key] = {"weights_version": version, "rules_hash": rules_hash}
    return _model_stamp_cache[key]


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
# (Washington/Los Cabos/Montreal). Struktura tiketa (korisnik, 26.07.): 6.0-40, 4-6 parova.
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

2. DOUBLE-CONFIRMATION — now required for 63%+, not just 66%+ (REVISED 2026-07-31):
   Why revised: 4 of our first 5 hard losses were scored 63-65%, i.e. BELOW the old 66%
   trigger, so this rule never applied to them. Since only 63%+ picks reach a ticket, the
   gate must sit at 63%. Documented losses: Paul 65%, Cerundolo 65%, Mensik 64%,
   Brooksby 63% — every one driven by a rating gap with no second independent edge.

   The three categories are STRICTLY SEPARATE — do not split one signal into two:
   (a) RATING: hard ELO, ATP ranking AND hard W-L record are ALL ONE CATEGORY. Quoting
       "ELO gap 104" plus "hard record 68% vs 62%" is ONE confirmation, not two.
   (b) SERVE/RETURN: counts ONLY if hold% differs by >= 3pp OR return-points-won by
       >= 2pp. Smaller gaps are noise — a 1.2pp return edge is NOT a confirmation
       (documented: Mensik vs Nakashima cited exactly that and lost).
       SLIDING, NOT A SWITCH (added 2026-08-02): a value that clears the threshold by
       less than 2pp is a WEAK confirmation, not a full one — it may lift confidence by
       at most 1pp. Only a margin of 5pp or more counts as a full confirmation. Barely
       clearing a floor is not evidence, it is a coin-flip dressed as evidence.
   (c) FORM adjusted for opponent quality (avg opponent ELO must actually differ).

   Scoring:
   - TWO or more categories favour your pick  -> 63-70% is available.
   - ONE category only, but OVERWHELMING (hard ELO gap >= 250, or hard W-L record gap
     >= 15pp) -> cap at 64%. This 64% is a CEILING, not a base to build on: nothing —
     scouting, style, conditions, freshness — may lift a capped pick above it, and the
     cap must be declared in "applied_caps". Documented: Landaluce (ELO gap 203, hard
     record gap 16.7pp) was capped at 64%, given +1pp for style matchup, emitted at 65%
     and lost to Mejia.
   - ONE category only, marginal -> score BELOW 63% and let selection drop it.
   - If the OPPONENT leads two of the three -> below 61% regardless of ranking.
   Career-finals experience, H2H with fewer than 3 matches, and "closing pressure" are
   NOT categories and can never serve as a confirmation.

3. MARGINAL-FAVOURITE REALITY CHECK (caution-zone discipline — RE-MEASURED 2026-07-26):
   Market odds 1.43-1.90 are matches where the bookmaker sees something close to a coin-flip.
   Season history: this region was our worst segment under the OLD model (-19% ROI), but
   after the July rule revisions the same region turned positive on clay (19W-8L). The
   lesson stands in softened form: these picks are fine ONLY when honestly earned — demand
   double-confirmation (rule 2) AND at least one decisive hard-specific edge; otherwise
   score below 63% so selection drops it. (Deterministic backstop: the ticket builder
   allows at most ONE hard pick from the 1.43-1.90 zone per ticket, so only your single
   best marginal favourite can make the ticket anyway — grade them honestly, not
   strategically.)

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

12. BOTH-PLAYERS-DECLINING CAP (threshold TIGHTENED 2026-08-06 — see measurement below):
   When BOTH players have LOST ALL THREE of their last 3 matches (strictly 0/3 each):
   cap confidence at 60% regardless of ELO, surface record, or other factors. Do NOT assess
   one player's 0/3 as "stable" and the other's as "declining" — they are in the same
   uncertainty category.
   ONE-OF-THREE IS NOT ENOUGH: a player at 1/3 does NOT trigger this rule. If either player
   has won at least one of his last three, judge the match on the usual factors.
   Why the threshold moved: the wider wording ("1/3 or worse") was never a measured
   threshold — the single documented case that produced this rule (Butvilas-Huesler) was
   0/3-vs-0/3, and the ticket builder's own check (`_is_declining`) has required a strict
   0/3 since 2026-07-20, when the wider version was found to exclude 43% of a normal
   Monday's card. The prompt was deliberately left wider at the time; that turned out to be
   a mistake. Measured at Montreal (02.-06.08.2026, 73 resolved analyses): this rule fired
   and capped six picks below the 63% selection floor, and ALL SIX WON. More broadly, every
   pick that any cap pushed below the floor went 11W-1L (91.7%) against a 63.5% hard
   baseline (P=0.034) — our caution rules were removing our best picks, not our worst.
   (Deterministic backstop: the ticket builder excludes 0/3-vs-0/3 matches from selection
   entirely, so you need not model that consequence — just score honestly.)

13. SERVE-DOMINANT OPPONENT CAP (added 2026-07-26 — distilled from THREE identical losses
   to Halys in one week at Kitzbühel, where fast conditions made his serve unbreakable):
   If the OPPONENT of your pick holds serve >= 82% on hard AND our pick's return points
   won is below ~40%: the opponent can realistically keep every set within one break or
   tiebreak, which is a coin-flip regardless of ELO/ranking gaps. Cap confidence at 60%
   unless our pick has a clearly documented answer: elite return numbers (42%+), a winning
   H2H with this server, or a clearly superior tiebreak record.
   SLIDING THRESHOLD (added 2026-08-02 — this rule was defused by a hair in THREE straight
   losses): "42%+" is not a switch. Measured margins and what they are worth:
     - return within 1pp of 42% (e.g. 42.5%)  -> the answer is NOT established; keep the
       60% cap. Documented: De Minaur 42.5% vs Nakashima 87.5% hold -> lost 7-6 6-4.
     - return 43-45%                          -> partial answer; cap 63%.
     - return above 45%                       -> genuine answer; the cap is lifted.
   The same logic applies to every numeric floor in these rules: ask HOW FAR the value
   clears it, never merely WHETHER it clears it. On hard this pattern is
   STRONGER than on the fast clay where it cost us three picks (Navone @1.45, Hanfmann
   @1.55, Bublik @1.50 — all beaten by the same big server we kept backing against).
   This complements rule 4 (both players serve-dominant) — rule 13 covers the asymmetric
   case where only the OPPONENT is the unbreakable one.

14. HARD SUB-SPEED (added 2026-07-26 from surface-physics analysis — "treating all hard
   courts identically is the most common modelling error for this surface"):
   "Hard" is a wide band from slow/high-bouncing to near-indoor fast. Re-weight styles by
   the specific court. PRIMARY evidence is the measured "Court pace this event" figure in
   the MATCH block above (share of sets going to a tiebreak at THIS event this season):
   >= 14% = fast, 9-13% = medium, < 9% = slow. Measured reference points: Washington 15.8%
   (fast), Los Cabos 10.9% (medium), Estoril clay 7.5% (slow). Fall back to venue
   reputation only when that figure reads "no data".
   - FAST hard (or hot daytime conditions): serve, ace rate and first-strike quality gain
     value — a big server's effective level rises above his ELO; rule 13 triggers earlier.
   - SLOW hard (or cool/night sessions): return, rally tolerance and movement gain value —
     counter-punchers neutralise big serves; do not pay a premium for serve stats alone.
   - SESSION: use the venue's LOCAL start time given in the MATCH block, never an assumption
     based on your own clock — our tournaments are often 6-9 hours behind us. Night sessions
     play cooler, heavier and slower: shade a fast court one step toward medium at night,
     and treat daytime heat (see Conditions) as speeding the court up.
   - Style note (use SCOUTING PROFILES): hard is the least style-punishing surface — it
     rewards complete all-courters and exposes ONE-DIMENSIONAL specialists. A pure clay
     grinder without a serve, or a pure server without a rally game, should be discounted
     against a complete player even when rankings are close.

15. RATING-vs-REALITY CONTRADICTION (added 2026-07-31, from two documented losses):
   A rating is only as good as the record behind it. Subtract 4pp from confidence when
   EITHER holds:
   - our pick's own hard win rate (3y) is <= 50% — his ELO and his actual results are in
     direct contradiction, so the ELO is not trustworthy (documented: Brooksby, 50% hard
     record, backed at 63% on a 121-point ELO gap, lost 6-1 7-5); OR
   - the OPPONENT's hard win rate (3y) is >= 70% — a genuinely strong surface performer
     regardless of what the rating gap says (documented: Gea, 76.7% hard record, was
     flagged as "a real threat" then dismissed; beat our 65% pick).
   If both hold, subtract 8pp. This is a deduction, not a veto — a pick with several
   genuine edges can absorb it.

16. CONVERGED SERVE -> THE MATCH IS DECIDED IN THE MARGINS (added 2026-07-31):
   When both players' hold% are within 3pp of each other, NEITHER can reliably break, so
   the match will be decided by 1-2 tiebreaks or a deciding set. In that situation:
   - serve is NEUTRALISED: it cannot count as a confirmation under rule 2 (b);
   - the decisive evidence becomes each player's OWN tiebreak record and deciding-set
     record (provided in the data above) — not the rating gap;
   - if your pick does not lead in BOTH tiebreak and deciding-set record, cap at 62%.
   SLIDING THRESHOLD: "within 3pp" is a gradient, not a line. A 2.9pp gap is nearly as
   neutralising as a 0.5pp gap; a 3.5pp gap is barely different from 2.9pp. Treat serve as
   fully live only from a 5pp gap upward, and as fully neutralised below 2pp; between the
   two, count it as half a confirmation under rule 2.
   Documented: Paul (hold ~81%) vs Majchrzak (hold ~81%) — a 140-point ELO gap was
   treated as decisive, the model itself wrote "TB lottery possible" in its risk notes,
   and the match went 7-5 7-6(4) exactly as predicted by the risk it ignored.
   NOTE: converged serve alone does NOT sink a pick — a player with a large rating edge
   AND better quality-adjusted form still qualifies under rule 2 (documented: Norrie,
   hold 80.3% vs 81.6% converged, won 6-1 6-0 on a 284-point ELO gap plus form quality).
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

        p1_age=(p1.get("age") or "N/A") if _AGE_TO_PROMPT else "N/A",
        p1_hand=_format_hand(p1.get("hand", "")),
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
        p1_tb_record=_format_wl_record(p1.get("tiebreak_record"), "tiebreaks"),
        p2_tb_record=_format_wl_record(p2.get("tiebreak_record"), "tiebreaks"),
        p1_decider_record=_format_wl_record(p1.get("decider_record"), "deciding sets"),
        p2_decider_record=_format_wl_record(p2.get("decider_record"), "deciding sets"),
        # NAMJERNO None, IAKO PODATAK OD 07.08.2026 POSTOJI. Do tog dana su ova dva polja
        # bila None zbog krivih naziva kljuceva u `get_player_stats` (vidi ondje) — dakle
        # model je cijelo vrijeme citao "BP saved: None". Naziv je popravljen, ali otvaranje
        # tog podatka prema promptu MIJENJA PICKOVE, a model je zamrznut radi cistog
        # pripisivanja do revizije 08.-09.08. Zato se vrijednost od danas BILJEZI u
        # context_snapshot (v8) i mjeri, a prompt ostaje doslovno isti kao u zamrznutoj eri.
        # NA REVIZIJI: zamijeniti s p1.get("break_points_saved") i p1.get("break_points_converted").
        p1_bp_saved=p1.get("break_points_saved") if _BP_TO_PROMPT else None,
        p1_break_conv=p1.get("break_points_converted") if _BP_TO_PROMPT else None,
        p1_return_won=p1.get("return_points_won", "N/A"),
        p1_matches_7d=p1.get("matches_7d", 0),
        p1_sets_7d=p1.get("sets_7d", 0) or "N/A",
        p1_last_match=p1.get("last_match_date", "N/A"),
        p1_days_rest=p1_days_rest,
        p1_tourn_path=p1.get("tournament_path", "N/A"),
        p1_form_trend=p1.get("form_trend", "N/A"),
        p1_news=p1.get("news", "No news") or "No news",

        p2_age=(p2.get("age") or "N/A") if _AGE_TO_PROMPT else "N/A",
        p2_hand=_format_hand(p2.get("hand", "")),
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
        p2_bp_saved=p2.get("break_points_saved") if _BP_TO_PROMPT else None,
        p2_break_conv=p2.get("break_points_converted") if _BP_TO_PROMPT else None,
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
        p1_titles=_format_titles(p1.get("titles") or {}),
        p2_titles=_format_titles(p2.get("titles") or {}),
        odds_alert=_odds_alert(odds_p1, odds_p2, match["player1"], match["player2"]),
        market_line=_market_line(odds_p1, odds_p2, match["player1"], match["player2"]),

        w_elo_ranking=weights.get("elo_ranking", 22),
        w_surface_style=weights.get("surface_style", 20),
        w_serve_return=weights.get("serve_return", 22),
        w_recent_form=weights.get("recent_form", 17),
        w_fatigue_injuries=weights.get("fatigue_injuries", 11),
        w_h2h_context=weights.get("h2h_context", 4),
        w_tournament_trajectory=weights.get("tournament_trajectory", 4),
        # Neobjavljen raspored za sutra (14.08.2026 11:02): sat je kladionicin placeholder,
        # pa se ne prosljedjuje ni vrijeme ni oznaka dan/noc. Ovo je BITNO jer `session`
        # po pravilu 14 smije dizati pouzdanost (za razliku od uvjeta, koji smiju samo
        # spustati) — laznu oznaku "day" model bi smio iskoristiti kao argument ZA pick.
        local_time=("Unknown — tomorrow's schedule is not final"
                    if match.get("schedule_provisional")
                    else (match.get("local_time") or "unknown")),
        session=match.get("session") or "unknown",
        court_pace=match.get("court_pace_str") or "no data",
        surface_specific_rules=_surface_specific_rules(surface),
    )

    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODELS["analysis"],
            # 2600 od 31.07.2026 (bilo 1500): novi obavezni format key_factors ima 6 polja
            # umjesto 3, pa je odgovor osjetno dulji. U dry-runu 31.07. jedna od 5 analiza
            # je pala na "No JSON object found" jer je odgovor bio odrezan na 1500 tokena —
            # odrezan JSON znači tiho preskočen meč, pa je margina ovdje jeftinija od gubitka
            # analize (naplaćuju se samo stvarno generirani tokeni, ne limit).
            max_tokens=2600,
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
            # v3 (26.07.2026): + model_stamp {weights_version, rules_hash} — egzaktno
            # rezanje kalibracije po erama modela (vidi _model_stamp).
            # v4 (31.07.2026): + local_time/session/court_pace (stvarno izmjereni, ne
            # procijenjeni) i tiebreak/decider recordi — sve ULAZI i u prompt od danas.
            "context_version": 4,
            "model_stamp": _model_stamp(match.get("surface", "")),
            "local_time": match.get("local_time"),
            "session": match.get("session"),
            "court_pace_label": match.get("court_pace_label"),
            "p1_tiebreak_record": p1.get("tiebreak_record"),
            "p2_tiebreak_record": p2.get("tiebreak_record"),
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
        # v5 (04.08.2026) — dvije stvari koje dosad NISU bile mjerljive:
        # (1) uvjeti: vrijeme je od početka išlo u prompt, ali se nigdje nije spremalo, pa
        #     se hipoteza "vlaga >85% usporava teren i pomaže grinderu" (predložile je DVIJE
        #     nezavisne auto-analize gubitaka, Berrettini i Fucsovics) nije mogla ni
        #     potvrditi ni odbaciti. Prvi pokušaj mjerenja iz teksta analiza dao je prividan
        #     signal (vrijeme kao argument ZA pick = 42% WR naspram 58% prosjeka), ali 23 od
        #     24 takva meča bila su iz jednog kišnog tjedna u Montrealu — potpuno konfundirano.
        #     Bez ovog zapisa svaka buduća rasprava o vremenu ostaje nagađanje.
        #     NAPOMENA: zastavica "meč je počeo kasnije od zakazanog" NIJE uključena jer je
        #     API-jev `timeGame` uvijek null, a `date` nosi ZAKAZANI termin — stvarni početak
        #     nemamo ni nakon meča. Bilježi se za koji je termin prognoza vrijedila.
        # (2) cap_enforced: je li kod morao spustiti confidence na cap koji je model sam
        #     proglasio — mjeri koliko često se to stvarno događa i s kojim ishodom.
        # v6 (04.08.2026) — tri dodatka, sva tri SAMO za mjerenje:
        # (a) weather_forecast_local_time / weather_hours_off: od danas se prognoza bira po
        #     SATU MECA, pa se biljezi za koji je tocno sat vrijedila i koliko je taj unos
        #     udaljen od pocetka. Bez toga se ne bi vidjelo da je stara logika citala jutro
        #     (12:00 UTC = 08:00 u Montrealu) — bug nadjen tek kad ga je korisnik primijetio.
        # (b) p1/p2_hand: ruka vec ide u prompt, ali se nikad nije spremala, pa se hipoteza
        #     o ljevak-vs-desnak matchupu nije mogla ni provjeriti.
        # (c) common_opponents: relativna snaga preko zajednickih protivnika. NE ide u prompt
        #     i ne utjece na pickove — prvo mjerimo je li signal stvaran (vidi _common_opponents).
        _wd = match.get("weather_data") or {}
        result["context_snapshot"].update({
            "context_version": 13,
            # v13 (15.08.2026 10:12, korisnikov zahtjev): TRZISNI KONSENZUS.
            # Cijene 20-46 kladionica (The Odds API), razvigane i spojene medijanom.
            # `market_p` je vjerojatnost za NASEG player1 po trzistu; `market_ev_pick` je
            # ocekivani prinos ako se kladi NAS pick po SuperSport kvoti.
            # SVE JE SAMO ZA MJERENJE — ne bira pickove, ne ulazi u prompt.
            # Izmjereno pri uvodjenju: SuperSport marza 5,42% vs trzisna 5,29%; samo 3 od
            # 32 uparena para kroz dva dana imala su pozitivan EV. Zato se selekcija NIJE
            # prebacila na EV — nema od cega sloziti tiket od 4-6 parova.
            "market_p": match.get("market_p"),
            "market_p_sharp": match.get("market_p_sharp"),
            "market_n_books": match.get("market_n_books"),
            "market_overround": match.get("market_overround"),
            "market_spread": match.get("market_spread"),
            "market_gap_pp": match.get("market_gap_pp"),
            "market_ev_pick": (
                match.get("market_ev_p1")
                if (result.get("pick") or "").strip().lower() == (match.get("player1") or "").strip().lower()
                else match.get("market_ev_p2")),
            # v12 (15.08.2026 09:19): dob je od danas STVARNO popunjena (bila None u svih
            # 320 redaka zbog krivog naziva kljuca). `age_in_prompt` biljezi je li u toj
            # analizi dob dosla modelu — vidi `_AGE_TO_PROMPT` za razlog zasto je False.
            "age_in_prompt": bool(_AGE_TO_PROMPT),
            "weather_temp_c": _wd.get("temp_c"),
            "weather_humidity": _wd.get("humidity"),
            "weather_wind_kmh": _wd.get("wind_kmh"),
            "weather_condition": _wd.get("condition"),
            # Tlak (05.08.2026, korisnikov prijedlog) — SAMO ZA BILJEZENJE, ne ide u prompt.
            # Hipoteza: razlika izmedju tlaka na koji je igrac naviknut i tlaka na mecu utjece
            # na kondiciju. Ne moze se provjeriti dok se ne skupi uzorak, pa se prvo skuplja.
            # OGRADA koju treba imati na umu pri kasnijoj analizi: "prirodni" tlak igraca
            # NEMAMO — iz API-ja znamo samo nacionalnost, ne mjesto treniranja ni nadmorsku
            # visinu doma. Mjerljivo je zasad samo "tlak na mecu" i njegov odnos prema
            # nadmorskoj visini turnira (`altitude`, vec postoji).
            "weather_pressure_hpa": _wd.get("pressure_hpa"),
            "weather_pressure_ground_hpa": _wd.get("pressure_ground_hpa"),
            "weather_forecast_for": match.get("date"),
            "weather_forecast_local_time": _wd.get("forecast_local_time"),
            "weather_hours_off": _wd.get("hours_off"),
            # "screenshot" = sat s kladionicinog screenshota (tocan), "api" = API-jev sat
            # (za Montreal kasni ~3h). Biljezi se da se kasnije vidi koliko je analiza radilo
            # na tocnom, a koliko na pomaknutom vremenu.
            "time_source": match.get("time_source"),
            # v11 (14.08.2026 11:02, korisnikov zahtjev): raspored za sutra jos nije bio
            # objavljen — kladionica je cijeli dan listala na jedan placeholder sat, pa su
            # uvjeti i oznaka dan/noc NAMJERNO prazni. Ovo polje postoji da se te mecheve
            # kasnije moze izrezati iz svake analize vremena: bez njega bi izgledali kao
            # obicni mecevi kojima prognoza slucajno nedostaje.
            # NAPOMENA O EROVIMA: `rules_hash` se ovom izmjenom NIJE promijenio (predlozak
            # prompta je netaknut, mijenja se samo vrijednost koja se u njega ubacuje), pa
            # se era NE smije rezati po hashu — rezi po `context_version` >= 11. Ista zamka
            # kao kod `_BP_TO_PROMPT` 08.08.2026.
            "schedule_provisional": bool(match.get("schedule_provisional")),
            "scheduled_start_source_date": match.get("time_screenshot_date"),
            # wave_first = mec je u PRVOM valu svog turnira tog lokalnog dana (krece po
            # rasporedu). Ostali dobivaju +1h jer cekaju prethodni mec na terenu — pa se
            # kasnije moze izmjeriti je li ta pretpostavka bila dobra.
            "wave_first": match.get("wave_first"),
            "scheduled_local_time": match.get("scheduled_local_time"),
            "venue_shielded": bool(match.get("weather_shielded")),
            "p1_hand": p1.get("hand"),
            "p2_hand": p2.get("hand"),
            "common_opponents": match.get("common_opponents") or None,
            "cap_enforced": None,
            "cap_prose_mismatch": None,
            # v8 (07.08.2026, korisnikov zahtjev): servis/povrat/break lopte — SAMO ZA
            # BILJEZENJE. Nijedan pick se ne mijenja; sve dolazi iz `get_player_stats` koji
            # se ionako vec poziva, pa NEMA dodatnih API poziva.
            #
            # Zasto bas ovo: analiza Montreala (07.08., n=62 / n=29 sa statistikom) pokazala je
            # da 10 od 11 analiza gubitaka imenuje servis kao promaseni faktor, a da u mecu
            # razlikuju samo poeni osvojeni na servisu (1. servis +8,8pp p=0,004, 2. servis
            # +10,1pp p=0,008) — dok asovi (p=0,463) i dvostruke greske (p=0,417) ne razlikuju
            # nista. Bez ovih polja u bazi ne moze se izmjeriti KOLIKO CESTO pravila 13 i 16
            # uopce okinu ni kako prolaze pickovi na koje su okinula.
            #
            # Za svaku velicinu biljezi se i ono sto prompt vidi i ispravljena vrijednost, da
            # se razlika moze izmjeriti prije nego se odluci sto mijenjati:
            #   hold_pct           -> linearni proxy (x1,9), ono sto prompt cita
            #   hold_pct_from_bp   -> procjena iz stvarno izgubljenih breakova
            #   return_won         -> neponderirani prosjek, ono sto prompt cita (+2,33pp pristran)
            #   return_won_weighted-> ispravno ponderirano
            #   bp_saved/bp_conv   -> od 07.08. konacno postoje; prompt ih JOS NE VIDI (_BP_TO_PROMPT)
            "p1_serve_pts_won": p1.get("serve_points_won"),
            "p2_serve_pts_won": p2.get("serve_points_won"),
            "p1_hold_pct": p1.get("hold_pct"),
            "p2_hold_pct": p2.get("hold_pct"),
            "p1_hold_pct_from_bp": p1.get("hold_pct_from_bp"),
            "p2_hold_pct_from_bp": p2.get("hold_pct_from_bp"),
            "p1_return_won": p1.get("return_points_won"),
            "p2_return_won": p2.get("return_points_won"),
            "p1_return_won_weighted": p1.get("return_points_won_weighted"),
            "p2_return_won_weighted": p2.get("return_points_won_weighted"),
            "p1_bp_saved": p1.get("break_points_saved"),
            "p2_bp_saved": p2.get("break_points_saved"),
            "p1_bp_converted": p1.get("break_points_converted"),
            "p2_bp_converted": p2.get("break_points_converted"),
            "p1_first_serve_pct": p1.get("first_serve_pct"),
            "p2_first_serve_pct": p2.get("first_serve_pct"),
            "bp_in_prompt": _BP_TO_PROMPT,
            # v9 (08.08.2026 11:35): ELO — SAMO ZA BILJEZENJE, ne mijenja nijedan pick.
            # `elo_ranking` nosi 19% tezine na hardu, a ELO se dosad nigdje nije zapisivao,
            # pa se korelacija "ELO <-> ishod" doslovno nije mogla izracunati — 19% modela
            # bilo je slijepa tocka. Utvrdjeno u hard analizi 08.08.2026.
            # Uz sirove ocjene biljezi se i RAZLIKA, jer je ona ono sto model zapravo koristi.
            "p1_elo_overall": p1.get("elo_overall"),
            "p2_elo_overall": p2.get("elo_overall"),
            "p1_elo_surface": p1.get(elo_key),
            "p2_elo_surface": p2.get(elo_key),
            "elo_gap_overall": (round(safe_float(p1.get("elo_overall")) - safe_float(p2.get("elo_overall")), 1)
                                if p1.get("elo_overall") and p2.get("elo_overall") else None),
            "elo_gap_surface": (round(safe_float(p1.get(elo_key)) - safe_float(p2.get(elo_key)), 1)
                                if p1.get(elo_key) and p2.get(elo_key) else None),
            "elo_surface_key": elo_key,
            # Koliko je protivnika uslo u avg_opp_elo (vidi run_daily._avg_opponent_elo_n).
            "avg_opp_elo_n": match.get("avg_opp_elo_n"),
        })
        # Redoslijed je bitan: strop na 64 ide PRVI (moze spustiti 67 -> 64), pa tek onda
        # capovi koje je model sam proglasio (mogu spustiti i ispod 64). Obrnuto bi strop
        # ponistio niži cap. Oba PRIJE `_normalize_fair_odds`, koji fair_odds izvodi iz
        # confidencea pa mora vidjeti konačan broj.
        _enforce_confidence_ceiling(result)
        _enforce_stated_caps(result)
        result["context_snapshot"]["cap_enforced"] = result.get("cap_enforced")
        result["context_snapshot"]["cap_prose_mismatch"] = result.get("cap_prose_mismatch")
        result["context_snapshot"]["ceiling_enforced"] = result.get("ceiling_enforced")
        result["context_snapshot"]["market_check"] = result.get("market_check")
        result["context_snapshot"]["above_64_basis"] = result.get("above_64_basis")
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

# Fraze kojima model prizna cap pa ga zaobiđe. Koriste se SAMO za upozorenje (nikad za
# spuštanje broja) — hvataju slučaj da cap nije završio u "applied_caps" iako je u tekstu.
_CAP_PROSE_RE = re.compile(
    r"(?:cap(?:s|ped)?\s+(?:confidence\s+)?(?:at|to)|cap\s+of|ceiling\s+of|cap\s+held\s+at)\s+(\d{2})\s*%",
    re.I)
# Negacije: "cap does NOT apply", "avoids the cap", "not triggered" — cap se spominje, ne veže.
_CAP_NEGATION_RE = re.compile(
    r"\b(?:does\s+not|doesn't|not\s+fully|never|avoid\w*|no\s+cap|would\s+(?:apply|trigger)|"
    r"cannot|is\s+not)\b", re.I)


_CONF_CEILING = 64.0
_CEILING_MIN_CONFIRMATIONS = 2


def _enforce_confidence_ceiling(result: dict) -> None:
    """Tvrdi strop na 64% osim ako model ne obrazlozi (13.08.2026 12:47).

    MJERENJE (84 razrijesene hard analize, pun Montreal):
        razred 63-64%  ->  62,5% stvarno (n=40)   kalibracija gotovo savrsena
        razred 65-67%  ->  50,0% stvarno (n=20)   ROI -34,8%
        bez razreda 65+, cijeli korpus ide s -6,9% na +1,8% ROI

    Uzrok je strukturni, ne pehov: modelova ljestvica se zasici oko 67%, pa "67%" nije
    izjava o jakom uvjerenju nego udaranje u strop — i onda se lijepi na meceve cija se
    stvarna razlika krece od gotovo izjednacene do premocne. U tom je razredu nas broj
    prosjecno **10,7pp ISPOD** trzisne cijene (17 od 20 pickova), dakle birali smo teske
    favorite a ocjenjivali ih nize od trzista, i to zvali visokom pouzdanoscu.

    Zato NIJE trazena "dodatna potvrda" nekim mjerenim kriterijem — provjerio sam sve
    podjele tog razreda i nijedna ga ne spasava (unutar 10pp od trzista 3W-5L, vise od 10pp
    ispod 6W-5L). Trazi se DEKLARACIJA: dva neovisna mjerena potvrdjivaca s brojkama i
    jedna recenica o tome sto bi moralo biti istina da pick izgubi. Ista mehanika koja vec
    radi kod `_enforce_stated_caps` (capirani pickovi 12W-3L u Montrealu).

    Clamp se BILJEZI (`ceiling_enforced`) da se za mjesec dana moze izmjeriti je li strop
    pomogao ili je samo maknuo dobre pickove zajedno s losima.
    """
    conf = safe_float(result.get("confidence") or 0)
    if conf <= _CONF_CEILING or not result.get("pick"):
        return
    basis = result.get("above_64_basis")
    items, has_downside = [], False
    if isinstance(basis, dict):
        items = [str(x) for x in (basis.get("confirmations") or []) if str(x).strip()]
        has_downside = bool(str(basis.get("what_would_beat_it") or "").strip())
    elif isinstance(basis, list):
        items = [str(x) for x in basis if str(x).strip()]
    elif isinstance(basis, str) and basis.strip():
        items = [p for p in re.split(r";|\||\n", basis) if p.strip()]
    # Potvrda mora sadrzavati BROJKU — "he serves well" nije mjereni potvrdjivac.
    measured = [x for x in items if re.search(r"\d", x)]
    ok = len(measured) >= _CEILING_MIN_CONFIRMATIONS and (has_downside or not isinstance(basis, dict))
    if not ok:
        result["confidence"] = _CONF_CEILING
        result["ceiling_enforced"] = {"from": conf, "to": _CONF_CEILING,
                                      "measured_confirmations": len(measured),
                                      "had_downside": has_downside}


def _enforce_stated_caps(result: dict) -> None:
    """Spušta confidence na najniži cap koji je model SAM proglasio vezujućim.

    Povod (2026-08-04, revizija nakon tri uzastopna promašena tiketa): model uredno izvede
    ispravnu gornju granicu pa emitira viši broj. Četiri dokumentirana slučaja na hardu,
    tri u istom tjednu — "rule 16's cap of 62% is technically triggered" -> 64;
    "cap held at 60% per rule 12 - below 63% threshold" -> 63 (izgubio);
    "start at 64% (overwhelming rating), +1pp for style" -> 65 (izgubio).
    Simulacija na stvarnim tiketima: Van Assche 63->60 i Fucsovics 63->60 ispadaju, čime
    tiket od 02.08. ostaje s 2 noge i uopće se ne sastavlja (taj je tiket izgubio); jedini
    dobitak koji bi ovo izbacilo (Jodar 64->62) bio je na analysis-only listi, dakle na
    stvarnim tiketima nijedan dobitnik nije koštao.

    Izvor istine je STRUKTURIRANO polje `applied_caps` koje model ispunjava, a ne parsiranje
    proze: raniji regex nad 102 hard analize dao je 26 "kršenja" od kojih je većina bila
    puko SPOMINJANJE capa koji ne veže ("rule 13 cap does not trigger"). Proza se i dalje
    skenira, ali samo da zabilježi neslaganje (`cap_prose_mismatch`) — nikad da spusti broj.
    """
    caps = result.get("applied_caps")
    conf = safe_float(result.get("confidence") or 0)
    if conf <= 0 or not result.get("pick"):
        return

    binding = []
    if isinstance(caps, list):
        for c in caps:
            if isinstance(c, dict):
                v = safe_float(c.get("cap") or 0)
                rule = str(c.get("rule") or "?")
            else:
                v, rule = safe_float(c or 0), "?"
            # Sanity: prihvaćamo samo capove u smislenom rasponu; 0/prazno/besmisleno se
            # ignorira umjesto da tiho sruši pick na nulu.
            if 50 <= v <= 80:
                binding.append((v, rule))

    if binding:
        lowest, rule = min(binding, key=lambda x: x[0])
        if conf > lowest:
            result["confidence"] = lowest
            result["cap_enforced"] = {"from": conf, "to": lowest, "rule": rule}
            print(f"    [CAP] {result.get('pick')}: confidence {conf} -> {lowest} "
                  f"(model sam proglasio cap po pravilu {rule})")

    # Sekundarna mreža — samo bilježenje, bez učinka na broj.
    text = " ".join([str(result.get("analysis") or ""), str(result.get("risk_notes") or "")]
                    + [str(x) for x in (result.get("key_factors") or [])])
    declared = {v for v, _ in binding}
    prose = []
    for sent in re.split(r"(?<=[.!?])\s+", text):
        if _CAP_NEGATION_RE.search(sent):
            continue
        for m in _CAP_PROSE_RE.finditer(sent):
            v = int(m.group(1))
            if 50 <= v <= 80 and v not in declared:
                prose.append(v)
    if prose and min(prose) < safe_float(result.get("confidence") or 0):
        result["cap_prose_mismatch"] = {"prose_caps": sorted(set(prose)),
                                        "confidence": result.get("confidence")}


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


def _market_line(odds_p1: float, odds_p2: float, name_p1: str, name_p2: str) -> str:
    """Trzisna cijena kao PROVJERA, nikad kao ulaz (13.08.2026 12:47, korisnikov zahtjev).

    Korisnikovo pravilo je i dalje da kvota NE ulazi u procjenu vjerojatnosti. Ovo je
    srednji put koji je odobrio: model svoj broj formira kao i dosad, a cijenu vidi tek da
    primijeti KAD SE JAKO RAZISAO s trzistem i da to izrijekom obrazlozi.

    Povod (izmjereno na 84 razrijesene hard analize): pickovi gdje smo bili vise od 10pp
    IZNAD trzista isli su 2W-6L (ROI -52,5%), a oni unutar 10pp 36W-21L (ROI 0,0%). Veliko
    razilazenje prema gore bilo je upozorenje o NAMA, ne otkrice o trzistu. Uz to je trzisna
    cijena jedina velicina u cijelom korpusu koja korelira s ishodom u ISPRAVNOM smjeru
    (r=+0,181), dok nasa pouzdanost korelira negativno (r=-0,147).

    Prikazuje se kao implicirana vjerojatnost, ne kao kvota, da se ne cita kao isplata."""
    o1, o2 = safe_float(odds_p1), safe_float(odds_p2)
    if not o1 or not o2 or o1 <= 0 or o2 <= 0:
        return "N/A"
    return (f"{name_p1} {1/o1*100:.0f}% / {name_p2} {1/o2*100:.0f}% "
            f"(implied by the bookmaker, overround not removed)")


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


def _format_titles(t: dict) -> str:
    """Karijerna finala po razini (C1, 26.07.2026). titlesWon+titlesLost = odigrana finala,
    pa dobivamo i KOLIKO ih je igrao i KOLIKO ih je zatvorio. Relevantno za QF/SF/F."""
    if not t:
        return "N/A"
    mw, ml = t.get("main_won", 0), t.get("main_lost", 0)
    cw, cl = t.get("ch_won", 0), t.get("ch_lost", 0)
    main_tot, ch_tot = mw + ml, cw + cl
    if main_tot == 0 and ch_tot == 0:
        return "No tour-level finals on record"
    parts = []
    if main_tot:
        parts.append(f"ATP/Masters finals: {main_tot} played, {mw} won ({mw/main_tot*100:.0f}% converted)")
    else:
        parts.append("ATP/Masters finals: none")
    if ch_tot:
        parts.append(f"Challenger finals: {ch_tot} played, {cw} won ({cw/ch_tot*100:.0f}% converted)")
    return " | ".join(parts)


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
