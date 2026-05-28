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
from agent.data_fetcher import get_matches_for_date, get_recent_form
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
    print("=== Večernji update ===")
    summary = {"resolved": 0, "won": 0, "lost": 0, "analyzed": 0, "weight_updated": False}

    # 1. Izgradi lookup player_id po imenu (external_match_id se mijenja između dana)
    name_to_id = {}
    for n_days in range(8):
        for m in get_matches_for_date(days_ago(n_days)):
            if m.get("player1_id"):
                name_to_id[m["player1"].lower().strip()] = m["player1_id"]
            if m.get("player2_id"):
                name_to_id[m["player2"].lower().strip()] = m["player2_id"]

    # 2. Za svaki pending par provjeri rezultat via past-matches
    pending = db.get_pending_matches()
    print(f"Pronadeno {len(pending)} pending parova za provjeru...")
    for pm in pending:
        p1_id = name_to_id.get(pm.get("player1", "").lower().strip(), "")
        if not p1_id:
            print(f"  Nema player_id: {pm.get('player1')} vs {pm.get('player2')}")
            continue
        actual_winner = _check_result_via_form(pm, p1_id)
        if not actual_winner:
            print(f"  Jos nije gotov: {pm.get('player1')} vs {pm.get('player2')}")
            continue
        pick = pm.get("pick", "")
        result = "won" if _names_match(pick, actual_winner) else "lost"
        db.update_match_result(pm["id"], result, actual_winner)
        summary["resolved"] += 1
        summary["won" if result == "won" else "lost"] += 1
        print(f"  Azuriran: {pm['player1']} vs {pm['player2']} -> {result} ({actual_winner})")

    # 2. Ažuriraj statuseve tiketa
    _update_ticket_statuses()

    # 3. Analiziraj izgubljene parove
    lost_matches = db.get_lost_matches_needing_analysis()
    for lm in lost_matches[:5]:
        analysis = _analyze_lost_match(lm)
        if analysis:
            db.save_loss_analysis(lm["id"], analysis)
            summary["analyzed"] += 1

    # 4. Ažuriraj performance log
    _update_performance_log()

    # 5. Provjeri trebamo li prilagoditi težine (tek nakon 10+ izgubljenih analiza)
    weight_updated = _maybe_update_weights(lost_matches)
    summary["weight_updated"] = weight_updated

    print(f"Večernji update završen: {summary}")
    return summary


def _update_ticket_statuses() -> None:
    """Pregledava tikete s pending statusom i ažurira ih kad su svi parovi riješeni."""
    tickets = db.get_tickets(status="pending")
    for ticket in tickets:
        matches = ticket.get("ticket_matches", [])
        if not matches:
            continue
        pending_count = sum(1 for m in matches if m.get("result") == "pending")
        if pending_count > 0:
            continue
        won_count = sum(1 for m in matches if m.get("result") == "won")
        total = len(matches)
        status = "won" if won_count == total else "lost"
        actual_win = ticket.get("stake", 50) * ticket.get("total_odds", 1) if status == "won" else 0
        db.update_ticket_status(ticket["id"], status, actual_win)
        print(f"  Tiket {ticket.get('ticket_date')}: {status} ({won_count}/{total})")


def _analyze_lost_match(match: dict) -> str:
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

    prompt = f"""Analitičar teniskih tiketa je izgubio predikciju. Analiziraj grešku.

PAR: {p1} vs {p2} | {tournament} ({surface})
NAŠA PREDIKCIJA: {pick} pobjeđuje (confidence: {confidence}%)
STVARNI REZULTAT: {actual} pobijedio | Score: {score}
NAVEDENI RIZICI: {risk_notes}
KLJUČNI FAKTORI KOJI SU ODREDILI PICK: {', '.join(key_factors) if key_factors else 'N/A'}

Napiši kratku analizu (max 150 riječi) koja objašnjava:
1. Koji je faktor bio pogrešno procijenjen?
2. Što je zapravo bilo presudno u meču?
3. Što treba promijeniti u algoritmu procjene?

Budi specifičan i konkretan. Fokusiraj se na faktore iz modela (ELO, podloga, forma, umor, H2H, itd.)"""

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
    Potrebno minimalno 5 novih analiza da bi se pokrenulo ažuriranje.
    """
    if len(lost_matches) < 5:
        return False

    current_weights = db.get_active_weights()
    analysis_texts = [lm.get("loss_analysis", "") for lm in lost_matches[:10] if lm.get("loss_analysis")]

    if len(analysis_texts) < 5:
        return False

    prompt = f"""Na temelju analize {len(analysis_texts)} izgubljenih tenis predikcija, predloži prilagodbu težina modela.

ANALIZE GREŠAKA:
{chr(10).join(f'{i+1}. {a}' for i, a in enumerate(analysis_texts))}

TRENUTNE TEŽINE:
{json.dumps(current_weights, indent=2)}

OGRANIČENJA:
- Svaka promjena max ±{WEIGHT_ADJUSTMENT['step']}% po faktoru
- Ukupna suma mora ostati 100%
- Min težina po faktoru: {WEIGHT_ADJUSTMENT['min_weight']}%
- Max težina po faktoru: {WEIGHT_ADJUSTMENT['max_weight']}%
- Mijenjaj samo faktore koji su KONZISTENTNO pogrešni u analizama

Odgovori ISKLJUČIVO u JSON formatu:
{{
  "new_weights": {{
    "elo_ranking": 20.0,
    "surface_style": 23.0,
    "serve_return": 18.0,
    "recent_form": 18.0,
    "fatigue_injuries": 12.0,
    "h2h_context": 5.0,
    "odds_movement": 4.0
  }},
  "reason": "kratko objašnjenje što i zašto je promijenjeno",
  "changed_factors": ["lista faktora koji su promijenjeni"]
}}

Ako nema jasnog uzorka koji zahtijeva promjenu, vrati iste težine s reason="Nema konzistentnog uzorka za promjenu"."""

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

        db.save_new_weights(new_weights, reason, f"Auto-feedback na {len(analysis_texts)} analiza")
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
    total = sum(weights.values())
    if abs(total - 100.0) > 0.5:
        return False
    for v in weights.values():
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
