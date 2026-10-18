# -*- coding: utf-8 -*-
"""Revizija 18.10.2026 — M: kretanje kvota svih kladionica (The Odds API) na NOVIM događajima (18.10.2026 09:24, zadnja izmjena).

Pragovi: PRAGOVI_REVIZIJA_2026-10-18.md točka M (09:07). Ponavljanje mjerenja od 13.09.2026
(tada: 192 događaja 15.08.-11.09.) na događajima koji počinju POSLIJE 11.09.2026.
- M1 neto pomak konsenzusa (medijan devigiranih kladionica) za pick, prva -> zadnja snimka prije
  početka, naspram ostatka nakon PRVE cijene. Smjer +; 13.09.: r = -0,092.
- M2 raspon kladionica (SD devigiranih vjerojatnosti) u zadnjoj snimci, naspram ostatka nakon
  zadnje cijene. Smjer -; 30.08.: r = +0,029.
- M3 sharp (is_sharp) medijan minus konsenzus, za pick, naspram ostatka nakon konsenzusa.
  Smjer +; 30.08.: r = +0,176.
Kriterij: |r| >= 0,15 u zadanom smjeru, 95% interval ne prelazi 0, isti predznak kao ranije.
Uz to (opis): KONS — edge pickova uz gap >= +1pp (konsenzus naspram SuperSporta) po turniru.
Samo čita .cache/rev_2026-10-18/*.
"""
import math
import os
import re
import sys
import unicodedata

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r_base import DUMP, corr, load  # noqa: E402


def key(name):
    s = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z ]", " ", s).split()
    return s[-1] if s else ""


def main():
    ml = pd.DataFrame(load("market_lines"))
    for c in ["odds_p1", "odds_p2", "p1_devig", "hours_to_start"]:
        ml[c] = pd.to_numeric(ml[c], errors="coerce")
    ml["captured_at"] = pd.to_datetime(ml["captured_at"], utc=True)
    ml["commence_time"] = pd.to_datetime(ml["commence_time"], utc=True)
    ml["is_sharp"] = ml["is_sharp"].astype(str).str.lower() == "true"
    new = ml[ml.commence_time >= pd.Timestamp("2026-09-12", tz="UTC")]
    print(f"market_lines: {len(ml)} redaka, {ml.event_id.nunique()} događaja | novih (od 12.09.): {len(new)} redaka, "
          f"{new.event_id.nunique()} događaja, {new.bookmaker.nunique()} kladionica")
    print("  turniri (sport_key) novih:", new.sport_key.value_counts().to_dict())

    df = pd.read_pickle(os.path.join(DUMP, "all_points.pkl"))
    df = df[df.p_dev.notna() & ~df.elo_suspect & (df.date >= "2026-09-12")].copy()
    rows = []
    ev = new.groupby("event_id")
    evinfo = new.groupby("event_id").agg(p1=("player1", "first"), p2=("player2", "first"), ct=("commence_time", "first"))
    evinfo["k1"], evinfo["k2"] = evinfo.p1.map(key), evinfo.p2.map(key)
    for _, r in df.iterrows():
        kp, ko = key(r.pick), key(r.opp)
        d = pd.Timestamp(r.date).tz_localize("UTC") if pd.Timestamp(r.date).tzinfo is None else pd.Timestamp(r.date)
        cand = evinfo[(((evinfo.k1 == kp) & (evinfo.k2 == ko)) | ((evinfo.k1 == ko) & (evinfo.k2 == kp)))
                      & ((evinfo.ct - d).abs() <= pd.Timedelta(days=2))]
        if not len(cand):
            continue
        eid = cand.index[0]
        pick_is_p1 = cand.iloc[0].k1 == kp
        g = ev.get_group(eid)
        g = g[g.captured_at <= g.commence_time]
        if g.empty:
            continue
        snaps = sorted(g.captured_at.unique())
        def cons(sn):
            x = g[g.captured_at == sn]
            p = x.p1_devig if pick_is_p1 else 1 - x.p1_devig
            return float(p.median()), float(p.std()) if len(p) > 2 else np.nan, int(len(p)), x
        p_first, _, n_first, _ = cons(snaps[0])
        p_last, sd_last, n_last, xl = cons(snaps[-1])
        sh = xl[xl.is_sharp]
        p_sharp = float((sh.p1_devig if pick_is_p1 else 1 - sh.p1_devig).median()) if len(sh) else np.nan
        rows.append({"date": r.date, "tour": r.tournament, "pick": r.pick, "win": r.win, "p_ss": r.p_dev, "odds": r.odds,
                     "p_first": p_first, "p_last": p_last, "move": p_last - p_first, "sd": sd_last,
                     "n_books": n_last, "n_snaps": len(snaps), "p_sharp": p_sharp,
                     "hours_span": (snaps[-1] - snaps[0]).total_seconds() / 3600})
    m = pd.DataFrame(rows)
    print(f"\nupareno s našim analizama (od 12.09., riješene, s cijenom): {len(m)} | medijan snimki {m.n_snaps.median():.0f}, "
          f"kladionica {m.n_books.median():.0f}, raspon sati {m.hours_span.median():.1f}")
    if m.empty:
        return
    print(f"  medijan |pomaka| {100*m.move.abs().median():.2f}pp | 90. percentil {100*m.move.abs().quantile(0.9):.2f}pp")
    m["res_first"] = m.win - m.p_first
    m["res_last"] = m.win - m.p_last
    out = []
    for lab, x, y, sgn, old in (("M1 neto pomak konsenzusa -> ostatak nakon prve cijene", m.move, m.res_first, +1, -0.092),
                                ("M2 raspon kladionica (SD) -> ostatak nakon zadnje", m.sd, m.res_last, -1, +0.029),
                                ("M3 sharp − konsenzus -> ostatak nakon konsenzusa", m.p_sharp - m.p_last, m.res_last, +1, +0.176)):
        r, p, n, ci = corr(x, y)
        ok = (abs(r) >= 0.15 and np.sign(r) == sgn and ((ci[0] > 0) if sgn > 0 else (ci[1] < 0)) and np.sign(r) == np.sign(old))
        print(f"  {lab:56s} r={r:+.3f} [{ci[0]:+.2f}, {ci[1]:+.2f}] n={n} P={p:.2f} | ranije {old:+.3f} -> {'KANDIDAT' if ok else 'ostaje ODBAČENO'}")
    # je li zadnja (zatvorna) cijena bolja od prve? Brier
    b1 = ((m.win - m.p_first) ** 2).mean()
    b2 = ((m.win - m.p_last) ** 2).mean()
    b3 = ((m.win - m.p_ss) ** 2).mean()
    print(f"  Brier: prva konsenzusna {b1:.4f} | zadnja konsenzusna {b2:.4f} | SuperSport (screenshot) {b3:.4f}  (manje = bolje)")
    m["gap"] = 100 * (m.p_last - m.p_ss)
    print("\n--- KONS opis: konsenzus (zadnja snimka) naspram SuperSporta za pick")
    for lab, s in (("gap >= +1pp", m[m.gap >= 1]), ("gap < +1pp", m[m.gap < 1]), ("gap <= -1pp", m[m.gap <= -1])):
        if len(s):
            e = 100 * (s.win.mean() - s.p_ss.mean())
            se = 100 * math.sqrt((s.p_ss * (1 - s.p_ss)).sum()) / len(s)
            print(f"  {lab:12s} n={len(s):3d} edge naspram SuperSporta {e:+6.1f}pp [{e-1.96*se:+5.1f}, {e+1.96*se:+5.1f}] | "
                  f"naspram konsenzusa {100*(s.win.mean()-s.p_last.mean()):+6.1f}pp")
    for t, s in m[m.gap >= 1].groupby("tour"):
        print(f"    {str(t)[:34]:34s} n={len(s):3d} edge {100*(s.win.mean()-s.p_ss.mean()):+6.1f}pp")
    m.to_pickle(os.path.join(DUMP, "market_moves.pkl"))


if __name__ == "__main__":
    main()
