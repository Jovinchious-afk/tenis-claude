"""
Supabase REST API klijent — direktni HTTP pozivi, bez supabase Python paketa.
Koristi samo 'requests' koji je standardno dostupan. Kompatibilan s Python 3.14+.
"""
import os
import json
import datetime
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def _get_config():
    url = os.environ.get("SUPABASE_URL") or _streamlit_secret("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY") or _streamlit_secret("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL i SUPABASE_KEY moraju biti postavljeni u .env ili Streamlit Secrets")
    return url.rstrip("/"), key


def _streamlit_secret(key: str) -> Optional[str]:
    try:
        import streamlit as st
        return st.secrets.get(key)
    except Exception:
        return None


def _headers(key: str, prefer: str = None, content_type: bool = True) -> dict:
    h = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    if content_type:
        h["Content-Type"] = "application/json"
    if prefer:
        h["Prefer"] = prefer
    return h


def _rest(method: str, table: str, params: dict = None, body=None, prefer: str = None) -> list:
    url, key = _get_config()
    endpoint = f"{url}/rest/v1/{table}"
    headers = _headers(key, prefer=prefer)
    try:
        r = requests.request(
            method,
            endpoint,
            headers=headers,
            params=params,
            json=body,
            timeout=15
        )
        r.raise_for_status()
        if r.content:
            return r.json() if isinstance(r.json(), list) else [r.json()] if r.json() else []
        return []
    except requests.HTTPError as e:
        print(f"Supabase HTTP greška [{method} {table}]: {e.response.status_code} — {e.response.text[:200]}")
        return []
    except Exception as e:
        print(f"Supabase greška [{method} {table}]: {e}")
        return []


def _select(table: str, select: str = "*", filters: dict = None, order: str = None,
            limit: int = None) -> list:
    params = {"select": select}
    if order:
        params["order"] = order
    if limit:
        params["limit"] = str(limit)
    if filters:
        params.update(filters)
    return _rest("GET", table, params=params)


def _insert(table: str, data) -> list:
    body = data if isinstance(data, list) else [data]
    return _rest("POST", table, body=body, prefer="return=representation")


def _update(table: str, data: dict, filters: dict) -> list:
    params = {}
    params.update(filters)
    return _rest("PATCH", table, params=params, body=data, prefer="return=representation")


def _upsert(table: str, data: dict, on_conflict: str = None) -> list:
    params = {}
    prefer = "return=representation,resolution=merge-duplicates"
    if on_conflict:
        params["on_conflict"] = on_conflict
    return _rest("POST", table, params=params, body=data, prefer=prefer)


# ── Tickets ───────────────────────────────────────────────────────────────────

def save_ticket(ticket_data: dict) -> dict:
    result = _insert("tickets", ticket_data)
    return result[0] if result else {}


def update_ticket_status(ticket_id: str, status: str, actual_win: float = None) -> None:
    data = {"status": status}
    if actual_win is not None:
        data["actual_win"] = actual_win
    if status in ("won", "lost"):
        data["resolved_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    _update("tickets", data, {"id": f"eq.{ticket_id}"})


def get_tickets(limit: int = 50, status: str = None) -> list:
    filters = {}
    if status:
        filters["status"] = f"eq.{status}"
    tickets = _select("tickets", select="*", filters=filters, order="ticket_date.desc", limit=limit)
    for t in tickets:
        matches = _select("ticket_matches", filters={"ticket_id": f"eq.{t['id']}"})
        t["ticket_matches"] = matches
    return tickets


def get_ticket_by_date(date_str: str) -> Optional[dict]:
    results = _select("tickets", filters={"ticket_date": f"eq.{date_str}"}, limit=1)
    if not results:
        return None
    t = results[0]
    t["ticket_matches"] = _select("ticket_matches", filters={"ticket_id": f"eq.{t['id']}"})
    return t


def delete_ticket(ticket_id: str) -> bool:
    """Briše tiket i sve njegove mečeve iz baze."""
    try:
        _rest("DELETE", "ticket_matches", params={"ticket_id": f"eq.{ticket_id}"})
        _rest("DELETE", "tickets", params={"id": f"eq.{ticket_id}"})
        return True
    except Exception as e:
        print(f"Greška brisanja tiketa {ticket_id}: {e}")
        return False


# ── Ticket Matches ────────────────────────────────────────────────────────────

def save_ticket_matches(matches: list) -> None:
    if matches:
        _insert("ticket_matches", matches)


def update_match_result(match_id: str, result: str, actual_winner: str, actual_score: str = None) -> None:
    data = {
        "result": result,
        "actual_winner": actual_winner,
        "resolved_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    if actual_score:
        data["actual_score"] = actual_score
    _update("ticket_matches", data, {"id": f"eq.{match_id}"})


def save_loss_analysis(match_id: str, analysis: str) -> None:
    _update("ticket_matches", {"loss_analysis": analysis, "analysis_done": True}, {"id": f"eq.{match_id}"})


def get_pending_matches() -> list:
    today = datetime.date.today().isoformat()
    return _select("ticket_matches", filters={
        "result": "eq.pending",
        "match_date": f"lte.{today}"
    })


def get_lost_matches_needing_analysis() -> list:
    return _select("ticket_matches", filters={
        "result": "eq.lost",
        "analysis_done": "eq.false"
    })


def reset_loss_analyses() -> int:
    """Resetira sve analize gubitaka da se mogu ponovo generirati s ispravnim podacima."""
    result = _rest("PATCH", "ticket_matches",
                   params={"result": "eq.lost", "analysis_done": "eq.true"},
                   body={"analysis_done": False, "loss_analysis": None},
                   prefer="return=representation")
    count = len(result)
    print(f"Reset {count} loss analyses for re-generation.")
    return count


def get_analyzed_lost_matches(limit: int = 20) -> list:
    return _select("ticket_matches", filters={
        "result": "eq.lost",
        "analysis_done": "eq.true"
    }, order="resolved_at.desc", limit=limit)


# ── Model Weights ─────────────────────────────────────────────────────────────

def get_active_weights() -> dict:
    results = _select("model_weights", filters={"is_active": "eq.true"}, order="version.desc", limit=1)
    if results:
        raw = results[0].get("weights", {})
        if isinstance(raw, str):
            return json.loads(raw)
        return raw
    from config.model_config import DEFAULT_WEIGHTS
    return DEFAULT_WEIGHTS


def save_new_weights(weights: dict, reason: str, triggered_by: str) -> None:
    current = _select("model_weights", select="version", order="version.desc", limit=1)
    next_version = (current[0]["version"] + 1) if current else 2
    _update("model_weights", {"is_active": False}, {"is_active": "eq.true"})
    _insert("model_weights", {
        "version": next_version,
        "weights": weights,
        "is_active": True,
        "update_reason": reason,
        "triggered_by": triggered_by
    })


def get_weight_history() -> list:
    return _select("model_weights", order="version.desc", limit=20)


# ── Performance Log ───────────────────────────────────────────────────────────

def upsert_performance_log(log_data: dict) -> None:
    _upsert("performance_log", log_data, on_conflict="log_date")


def get_performance_history(days: int = 60) -> list:
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    return _select("performance_log", filters={"log_date": f"gte.{since}"}, order="log_date")


# ── Analyzed Matches ──────────────────────────────────────────────────────────

def save_analyzed_match(match_data: dict) -> None:
    _upsert("analyzed_matches", match_data, on_conflict="external_match_id")
