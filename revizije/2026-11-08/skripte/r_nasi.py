# -*- coding: utf-8 -*-
"""Revizija 08.11.2026 — mjerenja na NAŠIM pickovima (08.11.2026 11:31).

Pragovi: revizije/2026-11-08/PRAGOVI_REVIZIJA_2026-11-08.md (08.11.2026 11:27), točke A, D-NAŠI, E, F, G.
Čita samo lokalni dump (.cache/rev_2026-11-08/base.pkl iz r_base.py + sirovi analyzed_matches.json
za polja Nosea/Intuicije koja baza nema). Izlaz: ispis (preusmjeriti u .cache/rev_2026-11-08/out_nasi.txt).
    python revizije/2026-11-08/skripte/r_nasi.py > .cache/rev_2026-11-08/out_nasi.txt
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from r_base import DUMP, ROOT, edge, holm, load  # noqa: E402

RNG = np.random.default_rng(20261108)
B = 2000


def band(o):
    return 0 if o < 1.30 else (1 if o < 1.50 else (2 if o < 1.80 else 3))


def diff_bw(df, mask):
    """Razlika rezidua (pobjeda − cijena) s uvjetom i bez, ponderirano po pojasu kvote (pp)."""
    m = np.asarray(mask, bool)
    num = den = 0.0
    for b in range(4):
        inb = (df["band"].values == b)
        a, c = df["resid"].values[inb & m], df["resid"].values[inb & ~m]
        if len(a) >= 3 and len(c) >= 3:
            num += len(a) * (a.mean() - c.mean())
            den += len(a)
    return 100 * num / den if den else np.nan


def boot(df, mask, reps=B):
    m = np.asarray(mask, bool)
    n = len(df)
    vals = []
    for _ in range(reps):
        ix = RNG.integers(0, n, n)
        v = diff_bw(df.iloc[ix], m[ix])
        if not np.isnan(v):
            vals.append(v)
    vals = np.array(vals)
    if len(vals) < 50:
        return np.nan, np.nan, np.nan
    lo, hi = np.percentile(vals, [2.5, 97.5])
    p = 2 * min((vals <= 0).mean(), (vals >= 0).mean())
    return lo, hi, max(p, 1 / reps)


def halves(df, mask):
    m = np.asarray(mask, bool)
    med = df["date"].sort_values().iloc[len(df) // 2]
    first = (df["date"] < med).values
    return diff_bw(df[first], m[first]), diff_bw(df[~first], m[~first])


def fmt_edge(s):
    n, e, ci, roi = edge(s)
    if not n:
        return "n=   0"
    return (f"n={n:4d}  {s['win'].mean()*100:5.1f}% pogođeno  cijena {s['p_dev'].mean()*100:5.1f}%  "
            f"edge {e:+5.1f}pp ±{ci:4.1f}  ROI {roi:+6.1f}%")


def main():
    d = pd.read_pickle(os.path.join(DUMP, "base.pkl"))
    d = d[d.p_dev.notna() & d.odds.notna()].copy()
    d["band"] = d["odds"].map(band)
    raw = {r["id"]: (r.get("context_snapshot") or {}) for r in load("analyzed_matches")}

    # ------------------------------------------------------------------ A0 noć/dan
    print("=" * 110)
    print("A0 NOĆNA SESIJA (stavka iz ČEKA) — prag: razlika noć−dan ≥ +5pp, interval noćnog edgea > 0, STARO isti predznak")
    for lab, sub in (("NOVO od 05.10.", d[(d.date >= "2026-10-05")]),
                     ("STARO 27.07.–04.10.", d[(d.date >= "2026-07-27") & (d.date < "2026-10-05")])):
        s = sub[sub.session.isin(["day", "night"])]
        nt, dy = s[s.session == "night"], s[s.session == "day"]
        m = (s.session == "night").values
        lo, hi, p = boot(s, m)
        h1, h2 = halves(s, m)
        print(f"  {lab:22s} NOĆ  {fmt_edge(nt)}")
        print(f"  {'':22s} DAN  {fmt_edge(dy)}")
        print(f"  {'':22s} razlika noć−dan (isti pojas cijene) {diff_bw(s, m):+5.1f}pp [{lo:+.1f}, {hi:+.1f}] P={p:.2f}"
              f" | polovice {h1:+.1f}/{h2:+.1f}")

    # ------------------------------------------------------------------ A1 doba dana
    print("\nA1 DOBA DANA (opis, od 27.07.2026, lokalni sat početka)")
    s = d[(d.date >= "2026-07-27") & d.local_time.notna()].copy()
    hh = pd.to_numeric(s.local_time.astype(str).str[:2], errors="coerce")
    s["doba"] = np.where(hh < 13, "jutro <13h", np.where(hh < 18, "popodne 13–18h", "večer ≥18h"))
    grupe = ["jutro <13h", "popodne 13–18h", "večer ≥18h"]
    for g in grupe:
        x = s[s.doba == g]
        m = (s.doba == g).values
        lo, hi, p = boot(s, m, reps=1000)
        print(f"  {g:16s} {fmt_edge(x)} | naspram ostalih {diff_bw(s, m):+5.1f}pp [{lo:+.1f}, {hi:+.1f}]")
    for lab, sub in (("NOVO od 05.10.", s[s.date >= "2026-10-05"]), ("STARO", s[s.date < "2026-10-05"])):
        print(f"   {lab}: " + " | ".join(f"{g} {edge(sub[sub.doba == g])[1]:+.1f}pp (n={len(sub[sub.doba == g])})"
                                         for g in grupe))

    # ------------------------------------------------------------------ A2 po igraču
    print("\nA2 PO IGRAČU (opis) — oba igrača svakog meča od 27.07.; igrači s ≥ 4 meča i danju i noću")
    rows = []
    for r in s.itertuples():
        if r.session not in ("day", "night"):
            continue
        rows.append((r.pick, r.session, r.win, r.p_dev))
        rows.append((r.opp, r.session, 1 - r.win, 1 - r.p_dev))
    pl = pd.DataFrame(rows, columns=["igrac", "ses", "w", "p"])
    out = []
    for name, g in pl.groupby("igrac"):
        dy, nt = g[g.ses == "day"], g[g.ses == "night"]
        if len(dy) >= 4 and len(nt) >= 4:
            out.append((name, len(dy), int(dy.w.sum()), 100 * (dy.w.mean() - dy.p.mean()),
                        len(nt), int(nt.w.sum()), 100 * (nt.w.mean() - nt.p.mean())))
    out.sort(key=lambda x: x[6] - x[3])
    print(f"  igrača s dovoljno mečeva: {len(out)} (od {pl.igrac.nunique()})")
    for o in out:
        print(f"  {o[0]:28s} dan {o[2]:2d}/{o[1]:2d} edge {o[3]:+6.1f}pp | noć {o[5]:2d}/{o[4]:2d} edge {o[6]:+6.1f}pp"
              f" | razlika {o[6]-o[3]:+6.1f}")
    nmax = pl.groupby("igrac").size().sort_values(ascending=False).head(8)
    print("  najviše mečeva po igraču (sve sesije):", ", ".join(f"{k} {v}" for k, v in nmax.items()))

    # ------------------------------------------------------------------ D-NAŠI runde
    print("\n" + "=" * 110)
    print("D-NAŠI RUNDA × AUTSAJDER (opis, od 26.09.2026, ručne runde) — svi analizirani mečevi s cijenom")
    s = d[(d.date >= "2026-09-26") & d["round"].isin(["R128", "R64", "R32", "R16", "QF", "SF", "F"])].copy()
    s = s[(s.p_dev - 0.5).abs() > 1e-9]
    s["p_dog"] = np.minimum(s.p_dev, 1 - s.p_dev)
    s["dog_won"] = np.where(s.p_dev < 0.5, s.win, 1 - s.win)
    s["pick_dog"] = s.p_dev < 0.5
    order = ["R128", "R64", "R32", "R16", "QF", "SF", "F"]
    print("  runda  mečeva | autsajder dobio | očekivano po kvoti | edge autsajdera | tijesni 0,40–0,50 dobio/očekivano"
          " | naši pickovi: pogođeno, edge, od toga autsajder")
    for rd in order:
        x = s[s["round"] == rd]
        if not len(x):
            continue
        n = len(x)
        e = 100 * (x.dog_won.mean() - x.p_dog.mean())
        ci = 196 * math.sqrt((x.p_dog * (1 - x.p_dog)).sum()) / n
        t = x[x.p_dog >= 0.40]
        _, ee, _, _ = edge(x)
        print(f"  {rd:6s} {n:5d} | {int(x.dog_won.sum()):4d} ({100*x.dog_won.mean():4.1f}%) | {x.p_dog.sum():6.1f} ({100*x.p_dog.mean():4.1f}%)"
              f" | {e:+6.1f}pp ±{ci:4.1f} | {int(t.dog_won.sum()):3d}/{t.p_dog.sum():5.1f} (n={len(t)})"
              f" | {int(x.win.sum())}/{n}, {ee:+5.1f}pp, autsajder {int(x.pick_dog.sum())}")
    tot = s
    print(f"  UKUPNO {len(tot):5d} | {int(tot.dog_won.sum()):4d} ({100*tot.dog_won.mean():4.1f}%) | {tot.p_dog.sum():6.1f}"
          f" ({100*tot.p_dog.mean():4.1f}%) | {100*(tot.dog_won.mean()-tot.p_dog.mean()):+6.1f}pp")
    print("\n  Po turniru (autsajder dobio / očekivano), runde R32, R16, QF, SF:")
    for tn, g in s.groupby("tournament"):
        parts = []
        for rd in ["R32", "R16", "QF", "SF"]:
            x = g[g["round"] == rd]
            if len(x):
                parts.append(f"{rd} {int(x.dog_won.sum())}/{x.p_dog.sum():.1f} (od {len(x)})")
        print(f"   {tn[:38]:38s} " + " | ".join(parts))
    print("\n  Strategija (opis): igrati autsajdera po SuperSport kvoti, ravni ulog 1")
    for lab, x in (("svi autsajderi", s), ("tijesni 0,40–0,50", s[s.p_dog >= 0.40]),
                   ("autsajderi R16+", s[s["round"].isin(["R16", "QF", "SF", "F"])])):
        dog_odds = np.where(x.p_dev < 0.5, x.odds, x.odds_opp)
        roi = 100 * np.mean(np.where(x.dog_won == 1, dog_odds - 1, -1.0))
        print(f"   {lab:22s} n={len(x):4d} pogođeno {100*x.dog_won.mean():5.1f}% (kvota očekuje {100*x.p_dog.mean():5.1f}%)  ROI {roi:+6.1f}%")

    # ------------------------------------------------------------------ E tlak
    print("\n" + "=" * 110)
    print("E TLAK ZRAKA (od 27.07.2026) — trećine tlaka na razini mora")
    s = d[(d.date >= "2026-07-27") & d.press.notna()].copy()
    q1, q2 = s.press.quantile([1 / 3, 2 / 3])
    s["ter"] = np.where(s.press <= q1, "nizak", np.where(s.press >= q2, "visok", "srednji"))
    print(f"  granice trećina: ≤ {q1:.0f} hPa nizak, ≥ {q2:.0f} hPa visok; n={len(s)}")
    for g in ["nizak", "srednji", "visok"]:
        print(f"   {g:8s} {fmt_edge(s[s.ter == g])}")
    better_srv = ((s.d_ace100 >= 2) | (s.d_tml_s >= 0.02)).fillna(False).values
    better_srv_any = (s.d_serve >= 2).fillna(False).values
    shielded = (s.shielded == True).values  # noqa: E712
    for lab, sub in (("E1 svi pickovi", s),
                     ("E2 pick bolji server (asovi +2/100 ili TML servis +2pp)", s[better_srv]),
                     ("E3 kao E2, dvorana/krov", s[better_srv & shielded]),
                     ("(opis) pick bolji server po karijernom servisu +2pp", s[better_srv_any])):
        lh = sub[sub.ter.isin(["nizak", "visok"])]
        if len(lh) < 10:
            print(f"  {lab}: premalo (n={len(lh)})")
            continue
        m = (lh.ter == "nizak").values
        lo, hi, p = boot(lh, m, reps=1000)
        h1, h2 = halves(lh, m)
        print(f"  {lab:58s} nizak−visok {diff_bw(lh, m):+6.1f}pp [{lo:+.1f}, {hi:+.1f}] P={p:.2f} | polovice {h1:+.1f}/{h2:+.1f}"
              f" | n nizak {int(m.sum())}, visok {int((~m).sum())}")
    print("  E4 (opis) tlak na tlu (nadmorska visina):")
    g1, g2 = s.press_ground.quantile([1 / 3, 2 / 3])
    for lab, x in (("nizak (visina)", s[s.press_ground <= g1]),
                   ("srednji", s[(s.press_ground > g1) & (s.press_ground < g2)]),
                   ("visok", s[s.press_ground >= g2])):
        tt = ", ".join(t.split(" - ")[-1] for t in x.tournament.value_counts().head(4).index)
        print(f"   {lab:15s} {fmt_edge(x)} | turniri: {tt}")

    # ------------------------------------------------------------------ F ponovno mjerenje
    print("\n" + "=" * 110)
    print("F PONOVNO MJERENJE STARIH IDEJA — pickovi 05.10.–07.11.2026 (zadnjih 5 tjedana); Pariz zasebno")
    s = d[(d.date >= "2026-10-05") & (d.date <= "2026-11-07")].copy()
    hist = json.load(open(os.path.join(ROOT, ".cache", "player_context", "history.json"), encoding="utf-8"))

    def h2h_lead(r):
        a, b = str(r.pick_id), str(r.opp_id)
        recs = hist.get(a) or []
        lim = (r.date - pd.Timedelta(days=3)).strftime("%Y-%m-%d")
        wa = wb = 0
        for x in recs:
            if {str(x.get("p1")), str(x.get("p2"))} == {a, b} and str(x.get("date")) < lim:
                if str(x.get("w")) == a:
                    wa += 1
                elif str(x.get("w")) == b:
                    wb += 1
        return wa, wb
    hh = [h2h_lead(r) for r in s.itertuples()]
    s["h2h_a"], s["h2h_b"] = [x[0] for x in hh], [x[1] for x in hh]
    print(f"  H2H iz berbe: pickova s barem jednim ranijim susretom {int(((s.h2h_a + s.h2h_b) > 0).sum())} od {len(s)}")
    t_hi = s.d_elo_s.quantile(2 / 3)
    tests = [
        ("R1 ritam: pick ≥2 meča u 7 d, protivnik odmor ≥10 d", (s.m7_p >= 2) & (s.rest_o >= 10)),
        ("R2 pick ≥2 seta više u 7 d (umor)", (s.s7_p - s.s7_o) >= 2),
        ("R3 pick odmor ≤1 d, protivnik ≥2 d", (s.rest_p <= 1) & (s.rest_o >= 2)),
        ("R4 pick stariji 4+ god.", (s.age_p - s.age_o) >= 4),
        ("R5 pick ≥30 god. i odmor ≤1 d", (s.age_p >= 30) & (s.rest_p <= 1)),
        ("R6 ELO jaz podloga gornja trećina", s.d_elo_s >= t_hi),
        ("R7 forma 10 bolja ≥0,2", s.d_f10 >= 0.2),
        ("R8 omjer na podlozi bolji ≥0,10", s.d_srf >= 0.10),
        ("R9 hold bolji ≥5pp", s.d_hold >= 5),
        ("R10 dalje došao na ovom turniru (3 god.)", s.d_tbest > 0),
        ("R11 scouting picka High/Med-High", s.scout_p.isin(["High", "Med-High"])),
        ("R12 pick vodi u H2H", s.h2h_a > s.h2h_b),
        ("R13 prosj. ELO zadnjih 5 protivnika picka <1700", s.aoe5_p < 1700),
    ]
    res = []
    for name, m in tests:
        m = m.fillna(False).values.astype(bool)
        dv = diff_bw(s, m)
        lo, hi, p = boot(s, m)
        h1, h2 = halves(s, m)
        par = s[s.tjedan]
        dp = diff_bw(par, m[s.tjedan.values])
        res.append((name, int(m.sum()), edge(s[m])[1], edge(s[~m])[1], dv, lo, hi, p, h1, h2, dp))
    hp = holm([r[7] for r in res])
    print(f"  n = {len(s)} pickova; Pariz {int(s.tjedan.sum())}")
    print("  test                                                 n s uvj. edge s  edge bez | razlika (isti pojas) [95%]  P    Holm | polovice | Pariz | presuda")
    for r, h in zip(res, hp):
        cand = (not np.isnan(r[5])) and ((r[5] > 0) or (r[6] < 0)) and (np.sign(r[8]) == np.sign(r[9]) == np.sign(r[4]))
        print(f"  {r[0]:52s} {r[1]:6d} {r[2]:+6.1f} {r[3]:+7.1f} | {r[4]:+6.1f} [{r[5]:+5.1f}, {r[6]:+5.1f}] {r[7]:5.2f} {h:5.2f}"
              f" | {r[8]:+5.1f}/{r[9]:+5.1f} | {r[10]:+6.1f} | {'KANDIDAT' if cand else 'nije potvrđeno'}")

    # ------------------------------------------------------------------ G nosovi
    print("\n" + "=" * 110)
    print("G USPOREDBA 'NOSOVA' — tko bi koliko pogodio (ravni ulog 1 po SuperSport kvoti)")
    for lab, sub in (("PARIZ", d[d.tjedan]), ("od 05.10.2026", d[d.date >= "2026-10-05"])):
        sub = sub.copy()
        sub["opp_value"] = [bool((((raw.get(i) or {}).get("nose") or {}).get("vs_market") or {}).get("opp_value")) for i in sub["id"]]
        sub["udflag"] = [bool(((raw.get(i) or {}).get("intuicija") or {}).get("underdog_flag")) for i in sub["id"]]
        print(f"\n  {lab}: {len(sub)} riješenih pickova; pick = tržišni favorit u {int((sub.p_dev > 0.5).sum())}"
              f" ({100*(sub.p_dev > 0.5).mean():.0f}%)")

        def strat(name, choose_pick, mask=None):
            if mask is None:
                mask = np.ones(len(sub), bool)
            mask = np.asarray(mask, bool)
            x = sub[mask]
            cp = np.asarray(choose_pick, bool)[mask]
            if not len(x):
                print(f"   {name:50s} n=0")
                return
            won = np.where(cp, x.win, 1 - x.win)
            p = np.where(cp, x.p_dev, 1 - x.p_dev)
            o = np.where(cp, x.odds, x.odds_opp)
            roi = 100 * np.mean(np.where(won == 1, o - 1, -1.0))
            n = len(x)
            ci = 196 * math.sqrt((p * (1 - p)).sum()) / n
            print(f"   {name:50s} n={n:3d}  {int(won.sum()):3d}–{n-int(won.sum()):3d}  ({100*won.mean():5.1f}%; cijena {100*p.mean():5.1f}%)"
                  f"  edge {100*(won.mean()-p.mean()):+5.1f}pp ±{ci:4.1f}  ROI {roi:+6.1f}%  | autsajdera biralo: {int((p < 0.5).sum())}")
        ones = np.ones(len(sub), bool)
        strat("Agent (naš pick)", ones)
        strat("Uvijek tržišni favorit", (sub.p_dev > 0.5).values)
        strat("Uvijek tržišni autsajder", (sub.p_dev < 0.5).values)
        ip = sub.int_p.values
        okI = ~np.isnan(ip)
        strat("Intuicija (strana s p ≥ 0,5)", np.where(okI, ip >= 0.5, True), okI)
        npw = sub.nose_p_own.values
        okN = ~np.isnan(npw)
        strat("Nose (vlastita procjena prije cijene)", np.where(okN, npw >= 0.5, True), okN)
        strat("Nose kaže 'vrijednost na protivniku' → protivnik", np.zeros(len(sub), bool), sub.opp_value.values)
        strat("Pickovi koje Nose kaže IZBJEGAVAJ", ones, (sub.nose_suit == "IZBJEGAVAJ").values)
        strat("Pickovi koje Nose kaže UKLJUČI", ones, (sub.nose_suit == "UKLJUČI").values)
        dis_n = okN & (npw < 0.5)
        print(f"   Nose bira drugu stranu: {int(dis_n.sum())}; Intuicija bira drugu stranu: {int((okI & (ip < 0.5)).sum())};"
              f" Intuicija 'underdog_flag': {int(sub.udflag.sum())}; Intuicija tiha (vlastiti sloj ništa ne zna): "
              f"{int(sub.int_silent.notna().sum())}/{len(sub)}")
        if dis_n.any():
            x = sub[dis_n]
            print(f"     kad Nose bira drugu stranu: agent pogodio {int(x.win.sum())} od {len(x)}; Nose {len(x)-int(x.win.sum())}")
            if lab == "PARIZ":
                for r in x.itertuples():
                    print(f"       {str(r.date)[:10]} {r.pick} (pick, kvota {r.odds:.2f}) – {r.opp}: Nose p_own {r.nose_p_own:.2f}"
                          f" → {'agent ✓' if r.win else 'Nose ✓'}")
        mi = np.abs(sub.int_p.values - sub.p_dev.values) * 100
        print(f"   Intuicija naspram cijene: prosječno odstupanje {np.nanmean(mi):.1f}pp, najveće {np.nanmax(mi):.1f}pp")
        signs = {}
        for r in sub.itertuples():
            for z in [z for z in str(r.ploca or "").split(",") if z]:
                signs.setdefault(z, []).append((r.win, r.p_dev))
        if signs:
            print("   nos-ploča (znak → pickovi s tim znakom):")
            for z, v in sorted(signs.items(), key=lambda kv: -len(kv[1])):
                w = np.array([a for a, _ in v])
                p = np.array([b for _, b in v])
                print(f"     {z:18s} n={len(v):3d}  {int(w.sum())}–{len(v)-int(w.sum())}  edge {100*(w.mean()-p.mean()):+6.1f}pp")


if __name__ == "__main__":
    main()
