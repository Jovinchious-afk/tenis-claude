# -*- coding: utf-8 -*-
"""Revizija 25.10.2026 — A3/A4: tiketi TJEDNA i učestalost tiketa od 05.10. (K1, prva 3 tjedna praga 63)
(25.10.2026 10:31; po uzoru na reviziju 18.10.2026 `r_tiketi.py`).

Pragovi: PRAGOVI_REVIZIJA_2026-10-25.md točke A3 i A4 (10:20).
- P(tiket) = umnožak devigiranih SuperSport cijena nogu (cijena iz analize istog para, ±2 dana;
  ako analize nema, devig iz same kvote noge uz prosječnu maržu 6%).
- "odlučujuća" noga = jedina izgubljena noga na tiketu.
Samo čita .cache/rev_2026-10-25/*.
    python revizije/2026-10-25/skripte/r_tiketi.py
"""
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r_base import DUMP, load  # noqa: E402

MARGIN = 1.06


def leg_rows(df, tm, t):
    legs = tm[tm.ticket_id == t["id"]]
    out = []
    for _, lg in legs.iterrows():
        md = pd.Timestamp(str(lg["match_date"])[:10])
        row = df[(df.pick == lg["pick"]) & ((df.opp == lg["player1"]) | (df.opp == lg["player2"]))
                 & ((df.date - md).abs() <= pd.Timedelta(days=2))]
        o = float(lg["odds"])
        # ISPRAVAK 25.10.2026 11:16 (skeptik): stara rezerva (preuzeta iz revizije 18.10.) davala je
        # p·kvota ≈ 1,02 — veću vjerojatnost od same kvote — za otprilike polovicu noga bez analize, pa je
        # "očekivano dobitnih" bilo napuhano (8,55 umjesto ≈7,5). Sada razmjerni devig uz maržu 6%.
        p = float(row.p_dev.iloc[0]) if len(row) else (min(0.97, (1 / o) / MARGIN) if o > 1 else np.nan)
        r0 = row.iloc[0] if len(row) else None
        out.append({"pick": lg["pick"], "opp": lg["player2"] if lg["pick"] == lg["player1"] else lg["player1"],
                    "odds": o, "p": p, "src": "analiza" if len(row) else "procjena", "result": lg["result"],
                    "leg_conf": lg.get("confidence"), "conf_am": (r0.conf if r0 is not None else np.nan),
                    "round": (r0["round"] if r0 is not None else lg.get("round")),
                    "tour": str(r0["tournament"] if r0 is not None else lg.get("tournament")).split("-")[-1].strip(),
                    "tp": (r0.pm_tp_share if r0 is not None else np.nan),
                    "klasa": (r0.klasa if r0 is not None else None),
                    "nose": (r0.nose_suit if r0 is not None else None),
                    "score": lg.get("actual_score")})
    return out


def main():
    df = pd.read_pickle(os.path.join(DUMP, "all_points.pkl"))
    tk = pd.DataFrame(load("tickets"))
    tm = pd.DataFrame(load("ticket_matches"))

    print("=== A3. Tiketi TJEDNA (19.-25.10.2026)")
    wk = tk[(tk.ticket_date >= "2026-10-19") & tk.status.isin(["won", "lost", "pending"])].sort_values("ticket_date")
    for _, t in wk.iterrows():
        legs = leg_rows(df, tm, t)
        pj = float(np.prod([l_["p"] for l_ in legs]))
        lost = [l_ for l_ in legs if l_["result"] == "lost"]
        warn = str(t.get("reviewer_warning") or "")
        named = re.match(r"\s*([A-ZÀ-Ž][\w'\-]+(?:\s+[A-ZÀ-Ž][\w'\-]+){0,3})\s+carries", warn)
        print(f"\n{t['ticket_date']}  status {t['status']}  kvota {float(t['total_odds']):.2f}  ulog {t.get('stake')}  "
              f"P(tiket) = {pj:.3f} (pošteni koeficijent {1/pj:.2f}; isplata {float(t['total_odds']):.2f} -> EV {100*(pj*float(t['total_odds'])-1):+.1f}%)")
        for l_ in legs:
            mark = {"won": "W", "lost": "L"}.get(l_["result"], "?")
            print(f"   {mark}  {l_['pick']:24s} vs {l_['opp']:24s} @{l_['odds']:.2f}  p={l_['p']:.3f}{'' if l_['src']=='analiza' else '*'}"
                  f"  {l_['tour']:9s} {str(l_['round']):4s} conf noge {l_['leg_conf']}  poeni "
                  f"{('%.1f%%' % (100*l_['tp'])) if not pd.isna(l_['tp']) else '-':6s} {l_['klasa'] or ''}  Nose {l_['nose']}  {l_['score'] or ''}")
        if len(lost) == 1:
            print(f"   ODLUČUJUĆA noga: {lost[0]['pick']} (bez nje bi tiket prošao)")
        elif lost:
            print(f"   izgubljenih noga: {len(lost)}")
        print(f"   recenzent: odluka {t.get('reviewer_decision')}; označio: {named.group(1) if named else '?'}")
        print(f"   upozorenje: {warn[:400]}")

    print("\n=== A4. Učestalost tiketa od 05.10.2026 (K1 — prag 63 od 04.10.2026 19:22)")
    days = pd.date_range("2026-10-05", "2026-10-25")
    tkd = tk.copy()
    tkd["d"] = pd.to_datetime(tkd.ticket_date)
    with_t, without, no_run = 0, 0, 0
    for d in days:
        x = tkd[tkd.d == d]
        if not len(x):
            no_run += 1
            print(f"  {d:%d.%m.}  (nema zapisa — run nije pokrenut?)")
            continue
        s = x.iloc[-1]
        real = s.status in ("won", "lost", "pending")
        with_t += real
        without += (not real)
        summ = str(s.get("ticket_summary") or "").replace("\n", " ")
        print(f"  {d:%d.%m.}  {s.status:13s} kvota {float(s.total_odds or 0):5.2f}  {summ[:170]}")
    print(f"  ukupno {len(days)} dana: s tiketom {with_t}, bez tiketa {without}, bez zapisa {no_run}")

    print("\n=== ROI tiketa")
    for od, lab in (("2026-10-05", "od 05.10. (prag 63)"), ("2026-09-27", "od 27.09. (era bccf4742)"), ("2026-05-27", "svi od 27.05.")):
        x = tk[(tk.ticket_date >= od) & tk.status.isin(["won", "lost"])]
        stake = pd.to_numeric(x.stake, errors="coerce").fillna(0).sum()
        ret = pd.to_numeric(x.actual_win, errors="coerce").fillna(0).where(x.status == "won", 0).sum()
        exp_won = 0.0
        for _, t in x.iterrows():
            legs = leg_rows(df, tm, t)
            if legs:
                exp_won += float(np.prod([l_["p"] for l_ in legs]))
        print(f"  {lab:28s} tiketa {len(x):3d}  dobitnih {int((x.status=='won').sum()):2d} (očekivano {exp_won:.2f})  "
              f"ulog {stake:7.0f}  povrat {ret:7.0f}  ROI {100*(ret-stake)/stake if stake else float('nan'):+6.1f}%")


if __name__ == "__main__":
    main()
