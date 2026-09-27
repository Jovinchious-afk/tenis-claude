# -*- coding: utf-8 -*-
"""Intuicija — jedan mail sa stanjem kapije K20 u dva zakazana dana (27.09.2026 12:46).

Korisnikova želja (27.09.2026): bez dnevnog maila; samo sredinom studenog i sredinom siječnja
neka se provjera sama upali na GitHubu i javi mailom. Pokreće je
`.github/workflows/intuicija_status.yml` (15.11. i 15.01.); izvan zakazanih dana ne šalje ništa.
Pravilo kapije živi u `agent.intuicija.gate_status` (isto koristi measure_candidates.py).

    python scripts/intuicija_status_email.py            # šalje samo na zakazani dan
    python scripts/intuicija_status_email.py --dry      # samo ispiše mail
    python scripts/intuicija_status_email.py --force    # pošalje i izvan zakazanih dana
"""
import datetime as _dt
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Zakazani dani (korisnikova odluka 27.09.2026). Novi datum = dodati ovdje i u workflowu.
SCHEDULED = ("2026-11-15", "2027-01-15")


def is_scheduled(day: _dt.date) -> bool:
    """Zakazani dan ili dan poslije (GitHub zna zakasniti s pokretanjem)."""
    for s in SCHEDULED:
        d = _dt.date.fromisoformat(s)
        if d <= day <= d + _dt.timedelta(days=1):
            return True
    return False


def build_html(g: dict, dogs: list, n_train: int) -> tuple:
    subject = f"Tenis — Intuicija: {g['verdict'].split(' — ')[0]} ({g['n']} procjena)"
    rows = [f"<p><b>{g['verdict']}</b></p>",
            f"<p>Riješenih procjena zapisanih prije meča: <b>{g['n']}</b>. "
            f"Sljedeća provjera kod {g['next_check']}.</p>"]
    if g.get("stage"):
        rows.append(
            f"<p>{g['stage']}: povezanost procjene i stvarnog ishoda r = {g['r']:+.3f} "
            f"(treba barem {g['need_r']:.2f}). Najbolja trećina procjena: {g['top']:+.1f} bodova "
            f"iznad cijene, najslabija: {g['bottom']:+.1f}.</p>")
    elif "r" in g:
        rows.append(f"<p>Zasad (bez presude): r = {g['r']:+.3f}.</p>")
    if dogs:
        rows.append(f"<p>Autsajderi koje bi Intuicija uzela: {len(dogs)} riješenih, "
                    f"prosječno {sum(dogs) / len(dogs):+.1f} bodova naspram cijene "
                    f"(o njima se razgovara tek uz 40 slučajeva i barem +3).</p>")
    rows.append(f"<p>Intuicija uči na {n_train} riješenih analiza i i dalje radi u sjeni — "
                "tiket ne vidi njezine procjene dok ti to ne odobriš.</p>")
    rows.append("<p>Za detalje otvori Claude Code i napiši: <i>kako stoji intuicija</i>.</p>")
    return subject, "\n".join(rows)


def main():
    dry, force = "--dry" in sys.argv, "--force" in sys.argv
    today = _dt.datetime.now(_dt.timezone.utc).date()
    if not (force or dry or is_scheduled(today)):
        print(f"{today}: nije zakazani dan ({', '.join(SCHEDULED)}) — ništa se ne šalje.")
        return
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
    from agent import intuicija as it
    from database import supabase_client as db
    raw = it.fetch_resolved(db)
    live, dogs = it.live_pairs(raw)
    g = it.gate_status(live)
    n_train = len(it.resolved_training_rows(raw)[0]) // 2
    subject, html = build_html(g, dogs, n_train)
    print(subject)
    print(html)
    if dry:
        print("\n--dry: mail nije poslan")
        return
    from utils.email_sender import _send_email
    ok = _send_email(subject, html)
    print("mail poslan" if ok else "!!! mail NIJE poslan")


if __name__ == "__main__":
    main()
