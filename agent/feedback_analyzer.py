"""
Feedback Analyzer: večernji job koji:
1. Dohvaća rezultate završenih mečeva
2. Ažurira statuse tiketa
3. Analizira izgubljene parove (Claude)
4. Predlaže i primjenjuje korekcije težina modela
"""
import os
import json
import datetime
import anthropic
from dotenv import load_dotenv
from config.model_config import CLAUDE_MODELS, WEIGHT_ADJUSTMENT, DEFAULT_WEIGHTS
from database import supabase_client as db
from agent.data_fetcher import get_matches_for_date, get_recent_form, get_match_stats
from utils.helpers import today_zagreb, days_ago, format_date

load_dotenv()

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client


def run_evening_update() -> dict:
    """
    Glavni entry point za večernji job.
    Vraća summary promjena.
    """
    print("=== Evening update ===")
    summary = {"resolved": 0, "won": 0, "lost": 0, "analyzed": 0, "weight_updated": False}

    # One-time migration: reset all old loss analyses so they are re-generated
    # in English with corrected ELO data. Runs once until no analyzed losses remain.
    existing = db.get_analyzed_lost_matches(limit=1)
    if existing:
        analysis_text = existing[0].get("loss_analysis", "") or ""
        # Detect old Croatian-language analyses by common Croatian words
        is_old = any(w in analysis_text for w in ["Analiza", "Faktori", "Pogrešno", "Presudni", "Promjena", "greške", "faktor"])
        if is_old:
            count = db.reset_loss_analyses()
            print(f"  Migrated {count} loss analyses to English (will re-generate this run).")

    # 1. Izgradi lookup player_id, tournament_id i fixture winner po imenu
    name_to_id = {}
    match_to_tournament = {}   # (p1_lower, p2_lower) -> tournament_id
    fixture_winner = {}        # (p1_lower, p2_lower) -> winner_name  (za walkover/predaju)
    for n_days in range(8):
        for m in get_matches_for_date(days_ago(n_days)):
            if m.get("player1_id"):
                name_to_id[m["player1"].lower().strip()] = m["player1_id"]
            if m.get("player2_id"):
                name_to_id[m["player2"].lower().strip()] = m["player2_id"]
            if m.get("tournament_id"):
                key = (m["player1"].lower().strip(), m["player2"].lower().strip())
                match_to_tournament[key] = m["tournament_id"]
                match_to_tournament[(key[1], key[0])] = m["tournament_id"]
            # Fixture winner — pokriva walkover/predaju gdje past-matches nema zapisa
            w_id = str(m.get("winner_id") or "")
            if w_id and w_id != "0":
                winner_name = ""
                if w_id == str(m.get("player1_id", "")):
                    winner_name = m["player1"]
                elif w_id == str(m.get("player2_id", "")):
                    winner_name = m["player2"]
                if winner_name:
                    fkey = (m["player1"].lower().strip(), m["player2"].lower().strip())
                    fixture_winner[fkey] = winner_name
                    fixture_winner[(fkey[1], fkey[0])] = winner_name

    # 2. Za svaki pending par provjeri rezultat via past-matches
    pending = db.get_pending_matches()
    print(f"Pronadeno {len(pending)} pending parova za provjeru...")
    for pm in pending:
        p1_name = pm.get("player1", "")
        p2_name = pm.get("player2", "")
        p1_id = name_to_id.get(p1_name.lower().strip(), "")
        p2_id = name_to_id.get(p2_name.lower().strip(), "")

        if not p1_id and not p2_id:
            print(f"  Nema player_id: {p1_name} vs {p2_name}")
            continue

        # Pokušaj via past-matches (normalno) — probaj s oba igrača
        actual_winner = ""
        if p1_id:
            actual_winner = _check_result_via_form(pm, p1_id)
        if not actual_winner and p2_id:
            pm_alt = {**pm, "player1": p2_name, "player2": p1_name}
            actual_winner = _check_result_via_form(pm_alt, p2_id)

        # Fallback: walkover/predaja — fixture direktno zna pobjednika
        if not actual_winner:
            fkey = (p1_name.lower().strip(), p2_name.lower().strip())
            actual_winner = fixture_winner.get(fkey, "")
            if actual_winner:
                print(f"  Walkover/predaja detektirana via fixture: {actual_winner}")

        if not actual_winner:
            # Auto-void: ako je meč pending već 3+ dana → walkover/odgoda
            match_date_str = pm.get("match_date", "")
            if match_date_str:
                try:
                    days_old = (datetime.date.today() - datetime.date.fromisoformat(match_date_str)).days
                    if days_old >= 3:
                        db.update_match_result(pm["id"], "void", "Walkover / Odgoda / Nerazriješen")
                        summary["resolved"] += 1
                        print(f"  Auto-void: {p1_name} vs {p2_name} ({days_old} dana pending)")
                        continue
                except ValueError:
                    pass
            print(f"  Jos nije gotov: {p1_name} vs {p2_name}")
            continue

        pick = pm.get("pick", "")
        result = "won" if _names_match(pick, actual_winner) else "lost"
        db.update_match_result(pm["id"], result, actual_winner)
        summary["resolved"] += 1
        summary["won" if result == "won" else "lost"] += 1
        print(f"  Azuriran: {p1_name} vs {p2_name} -> {result} ({actual_winner})")

    # 2. Ažuriraj statuseve tiketa
    _update_ticket_statuses()

    # 3. Analiziraj izgubljene parove
    lost_matches = db.get_lost_matches_needing_analysis()

    # Build lookup of already-analyzed matches so duplicates can reuse the analysis
    already_analyzed = db.get_analyzed_lost_matches(limit=100)
    analysis_cache: dict[tuple, str] = {}
    for am in already_analyzed:
        key = (am.get("player1","").lower().strip(), am.get("player2","").lower().strip(), am.get("match_date",""))
        if key not in analysis_cache and am.get("loss_analysis"):
            analysis_cache[key] = am["loss_analysis"]

    for lm in lost_matches[:5]:
        p1_key = lm.get("player1", "").lower().strip()
        p2_key = lm.get("player2", "").lower().strip()
        match_key = (p1_key, p2_key, lm.get("match_date",""))

        # Reuse existing analysis for duplicate tickets (same match, different ticket date)
        if match_key in analysis_cache:
            db.save_loss_analysis(lm["id"], analysis_cache[match_key])
            summary["analyzed"] += 1
            print(f"  Kopirano: {lm.get('player1')} vs {lm.get('player2')} (isti meč, drugi tiket)")
            continue

        p1_id = name_to_id.get(p1_key, "")
        p2_id = name_to_id.get(p2_key, "")
        tournament_id = match_to_tournament.get((p1_key, p2_key), "")
        stats = get_match_stats(tournament_id, p1_id, p2_id) if (p1_id and p2_id and tournament_id) else {}
        analysis = _analyze_lost_match(lm, stats)
        if analysis:
            db.save_loss_analysis(lm["id"], analysis)
            analysis_cache[match_key] = analysis
            summary["analyzed"] += 1

    # 4. Ažuriraj performance log
    _update_performance_log()

    # 5. Provjeri trebamo li prilagoditi težine (tek nakon 10+ izgubljenih analiza)
    weight_updated = _maybe_update_weights(lost_matches)
    summary["weight_updated"] = weight_updated

    print(f"Večernji update završen: {summary}")
    return summary


def _update_ticket_statuses() -> None:
    """Pregledava tikete s pending statusom i ažurira ih kad su svi parovi riješeni.
    Pravila:
    - Jedan 'lost' = tiket odmah lost (ne čekamo ostale)
    - 'void' parovi se izuzimaju iz računice (walkover/odgoda)
    - Svi non-void parovi won = tiket won
    """
    tickets = db.get_tickets(status="pending")
    for ticket in tickets:
        matches = ticket.get("ticket_matches", [])
        if not matches:
            continue
        lost_count   = sum(1 for m in matches if m.get("result") == "lost")
        won_count    = sum(1 for m in matches if m.get("result") == "won")
        void_count   = sum(1 for m in matches if m.get("result") == "void")
        pending_count = sum(1 for m in matches if m.get("result") == "pending")
        total = len(matches)

        if lost_count > 0:
            db.update_ticket_status(ticket["id"], "lost", 0)
            print(f"  Tiket {ticket.get('ticket_date')}: lost ({lost_count}L, {won_count}W, {void_count} void)")
            continue

        if pending_count > 0:
            continue

        # Svi razriješeni, nema lost — won (void ne blokira)
        actual_win = ticket.get("stake", 50) * ticket.get("total_odds", 1)
        db.update_ticket_status(ticket["id"], "won", actual_win)
        print(f"  Tiket {ticket.get('ticket_date')}: won ({won_count}W, {void_count} void, {total} ukupno)")


def _format_match_stats(p1: str, p2: str, stats: dict) -> str:
    """Formatira post-match statistike u čitljiv blok za Claude prompt."""
    if not stats:
        return ""
    lines = ["\nSTATISTIKE MEČA:"]
    p1_stats = stats.get("player1", stats.get("p1", {})) or {}
    p2_stats = stats.get("player2", stats.get("p2", {})) or {}
    stat_keys = [
        ("aces", "Ace"),
        ("double_faults", "Dvostruke greške"),
        ("first_serve_percentage", "1. servis %"),
        ("first_serve_points_won", "Poeni na 1. servisu %"),
        ("second_serve_points_won", "Poeni na 2. servisu %"),
        ("break_points_saved", "Sačuvani BP"),
        ("break_points_faced", "BP protiv"),
        ("break_points_converted", "Iskorišteni BP"),
        ("break_points_on", "BP prilike"),
        ("return_points_won", "Return poeni %"),
        ("total_points_won", "Ukupni poeni"),
        ("winners", "Winneri"),
        ("unforced_errors", "Neforsirane greške"),
    ]
    for key, label in stat_keys:
        v1 = p1_stats.get(key)
        v2 = p2_stats.get(key)
        if v1 is not None or v2 is not None:
            lines.append(f"  {label}: {p1}={v1 if v1 is not None else 'N/A'} | {p2}={v2 if v2 is not None else 'N/A'}")
    return "\n".join(lines) + "\n" if len(lines) > 1 else ""


def _analyze_lost_match(match: dict, stats: dict = None) -> str:
    """Claude analizira zašto smo pogriješili na konkretnom paru."""
    pick = match.get("pick", "")
    actual = match.get("actual_winner", "")
    p1 = match.get("player1", "")
    p2 = match.get("player2", "")
    score = match.get("actual_score", "N/A")
    tournament = match.get("tournament", "")
    surface = match.get("surface", "")
    risk_notes = match.get("risk_notes", "")
    confidence = match.get("confidence", 0)
    key_factors = match.get("key_factors", [])

    stats_block = ""
    if stats:
        stats_block = _format_match_stats(p1, p2, stats)

    prompt = f"""A tennis prediction model made an incorrect prediction. Analyse the error.

MATCH: {p1} vs {p2} | {tournament} ({surface})
OUR PREDICTION: {pick} to win (confidence: {confidence}%)
ACTUAL RESULT: {actual} won | Score: {score}
STATED RISKS: {risk_notes}
KEY FACTORS THAT DROVE THE PICK: {', '.join(key_factors) if key_factors else 'N/A'}
{stats_block}
Write a concise analysis (max 150 words) explaining:
1. Which factor was incorrectly assessed?
2. What actually decided the match?
3. What should change in the prediction algorithm?

Be specific and concrete. Focus on model factors (ELO, surface, form, fatigue, H2H, etc.)"""

    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODELS["feedback"],
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"Greška analize gubitka: {e}")
        return f"Analiza nije dostupna: {str(e)[:100]}"


def _maybe_update_weights(lost_matches: list) -> bool:
    """
    Prilagođava težine modela na temelju uzorka grešaka.
    Koristi SVE analizirane gubitke iz baze (ne samo tekući run).
    Potrebno minimalno 5 analiziranih grešaka ukupno.
    """
    # Only use losses from matches played AFTER the current weights were activated.
    # This ensures we correct the current model, not a previous version.
    weights_active_since = db.get_active_weight_version_date()
    all_analyzed_raw = db.get_analyzed_lost_matches(limit=40)
    all_analyzed_filtered = [m for m in all_analyzed_raw
                              if (m.get("match_date") or "") >= weights_active_since]

    # Deduplicate by (player1, player2, match_date): same match on multiple tickets = 1 loss.
    # If both tickets have an analysis, combine them for a richer learning signal.
    seen: dict[tuple, dict] = {}
    for m in all_analyzed_filtered:
        key = (m.get("player1","").lower().strip(), m.get("player2","").lower().strip(), m.get("match_date",""))
        if key not in seen:
            seen[key] = dict(m)
        else:
            existing = seen[key]
            if m.get("loss_analysis") and existing.get("loss_analysis") and m["loss_analysis"] != existing["loss_analysis"]:
                existing["loss_analysis"] = (
                    existing["loss_analysis"]
                    + f"\n\n[Analysis from ticket {m.get('ticket_date','?')}:]\n"
                    + m["loss_analysis"]
                )
    all_analyzed = list(seen.values())

    if len(all_analyzed) < 5:
        print(f"  Not enough losses under current weights ({len(all_analyzed)}/5, "
              f"weights active since {weights_active_since}).")
        return False

    # Determine dominant surface among recent losses
    from collections import Counter
    surface_counts = Counter(db._surface_key(m.get("surface", "hard")) for m in all_analyzed)
    dominant_surface = surface_counts.most_common(1)[0][0] if surface_counts else "hard"
    # Filter to that surface for a cleaner signal (min 3 losses, else use all)
    surface_losses = [m for m in all_analyzed if db._surface_key(m.get("surface", "hard")) == dominant_surface]
    analysis_pool = surface_losses if len(surface_losses) >= 3 else all_analyzed

    current_weights = db.get_active_weights(dominant_surface)
    matches_with_analysis = [m for m in analysis_pool[:10] if m.get("loss_analysis")]

    if len(matches_with_analysis) < 5:
        return False

    match_blocks = []
    for i, m in enumerate(matches_with_analysis):
        p1 = m.get("player1", "?")
        p2 = m.get("player2", "?")
        pick = m.get("pick", "?")
        actual = m.get("actual_winner", "?")
        conf = m.get("confidence", 0)
        odds = m.get("odds", 0)
        surface = m.get("surface", "?")
        runda = m.get("round", "?")
        tournament = m.get("tournament", "?")
        level = m.get("tournament_level", "")
        fmt = "BoF5" if "Grand Slam" in level else "BoF3"
        risk = m.get("risk_notes", "—")
        factors = m.get("key_factors", [])
        factors_str = "; ".join(factors) if factors else "N/A"
        analysis = m.get("loss_analysis", "")

        block = (
            f"--- LOSS {i+1} ---\n"
            f"Match: {p1} vs {p2} | {tournament} | {surface} | {runda} | {fmt}\n"
            f"Pick: {pick} (confidence: {conf}%, odds: {odds:.2f})\n"
            f"Winner: {actual}\n"
            f"Key factors that drove the pick: {factors_str}\n"
            f"Stated risks beforehand: {risk}\n"
            f"Error analysis: {analysis}"
        )
        match_blocks.append(block)

    matches_section = "\n\n".join(match_blocks)

    prompt = f"""You are an expert in tennis prediction model analysis. Based on {len(matches_with_analysis)} documented incorrect predictions, suggest adjustments to the model weights.

LOSSES WITH FULL CONTEXT:
{matches_section}

CURRENT MODEL WEIGHTS:
{json.dumps(current_weights, indent=2)}

WHAT EACH WEIGHT COVERS:
- elo_ranking: ELO rating, ATP ranking, ranking trend, opponent quality
- surface_style: surface + playing style matchup (clay/hard/grass specialist)
- serve_return: serve%, return%, aces, break points
- recent_form: form over last 5-10 matches (W/L ratio, opponent quality)
- fatigue_injuries: fatigue, injuries, match schedule, travel, days of rest
- h2h_context: H2H record, tournament context, motivation, mental factors

INSTRUCTIONS:
Analyse error patterns across all losses. Look for factors that were CONSISTENTLY underweighted or overweighted.
Pay particular attention to:
- Does the same factor appear as an error in 3+ cases?
- Is there a difference in performance between BoF3 and BoF5 formats?
- Is fatigue/form or ELO/ranking consistently underestimated?

CONSTRAINTS:
- Max change ±{WEIGHT_ADJUSTMENT['step']}% per factor (use 0.5-1% for weak/unclear patterns, 2-3% for very consistent patterns across 5+ losses)
- Total must remain 100%
- Min weight per factor: {WEIGHT_ADJUSTMENT['min_weight']}%
- Max weight per factor: {WEIGHT_ADJUSTMENT['max_weight']}%
- Change ONLY factors with a clear pattern in the data

Respond ONLY in JSON format:
{{
  "new_weights": {{
    "elo_ranking": 20.0,
    "surface_style": 23.0,
    "serve_return": 18.0,
    "recent_form": 20.0,
    "fatigue_injuries": 14.0,
    "h2h_context": 5.0
  }},
  "reason": "specific explanation — which factor, how many cases, why the change",
  "changed_factors": ["list of changed factors"]
}}

If there is no clear pattern requiring change, return the same weights with reason="No consistent pattern requiring change"."""

    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODELS["feedback"],
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        new_weights = result.get("new_weights", {})
        reason = result.get("reason", "Automatska prilagodba")
        changed = result.get("changed_factors", [])

        # Provjeri da su nove težine validne
        if not _validate_weights(new_weights):
            print("Predložene težine nisu validne, odbačeno.")
            return False

        if not changed or reason == "Nema konzistentnog uzorka za promjenu":
            print("Nema potrebe za promjenom težina.")
            return False

        db.save_new_weights(new_weights, reason, f"Auto-feedback na {len(matches_with_analysis)} analiza", surface=dominant_surface)
        print(f"Težine ažurirane: {reason}")
        return True

    except Exception as e:
        print(f"Greška ažuriranja težina: {e}")
        return False


def _update_performance_log() -> None:
    today = format_date(today_zagreb())
    tickets = db.get_tickets(limit=200)

    total = len([t for t in tickets if t.get("status") != "pending"])
    won = len([t for t in tickets if t.get("status") == "won"])
    lost = len([t for t in tickets if t.get("status") == "lost"])
    pending = len([t for t in tickets if t.get("status") == "pending"])

    total_staked = total * 50.0
    total_returned = sum(t.get("actual_win", 0) or 0 for t in tickets if t.get("status") == "won")
    roi = ((total_returned - total_staked) / total_staked * 100) if total_staked > 0 else 0
    running_balance = total_returned - total_staked

    db.upsert_performance_log({
        "log_date": today,
        "total_tickets": total,
        "won_tickets": won,
        "lost_tickets": lost,
        "pending_tickets": pending,
        "total_staked": total_staked,
        "total_returned": total_returned,
        "roi_percent": round(roi, 2),
        "running_balance": round(running_balance, 2),
    })


def _validate_weights(weights: dict) -> bool:
    if not weights:
        return False
    numeric = {k: v for k, v in weights.items() if isinstance(v, (int, float))}
    total = sum(numeric.values())
    if abs(total - 100.0) > 0.5:
        return False
    for k, v in weights.items():
        if not isinstance(v, (int, float)):
            continue  # skip "surface" string key
        if v < WEIGHT_ADJUSTMENT["min_weight"] or v > WEIGHT_ADJUSTMENT["max_weight"]:
            return False
    return True


def _check_result_via_form(pm: dict, player1_id: str) -> str:
    """
    Koristi past-matches endpoint (ima match_winner) za provjeru rezultata.
    Vraća ime pobjednika ako je meč završen, inače ''.
    """
    p1_name = pm.get("player1", "")
    p2_name = pm.get("player2", "")
    cutoff = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    try:
        form = get_recent_form(player1_id, 10)
        for m in form.get("matches", []):
            if m.get("date", "") < cutoff:
                continue
            if not _names_match(m.get("opponent", ""), p2_name):
                continue
            return p1_name if m.get("won") else p2_name
    except Exception as e:
        print(f"  Greska provjere {p1_name} vs {p2_name}: {e}")
    return ""


def _names_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    a, b = a.lower().strip(), b.lower().strip()
    if a == b:
        return True
    a_parts = a.split()
    b_parts = b.split()
    if not a_parts or not b_parts:
        return False
    return a_parts[-1] == b_parts[-1]
