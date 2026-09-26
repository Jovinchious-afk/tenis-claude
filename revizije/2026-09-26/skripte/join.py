# -*- coding: utf-8 -*-
"""Spaja nas korpus (analyzed_matches) s berbom past-matches: rezultat po setovima, predaja,
API kvota, razina/runda/podloga turnira. Po ID-u igraca, a gdje ID fali — po imenu. Datum +-3."""
import re, unicodedata
import numpy as np, pandas as pd
import base, pmbase


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", " ", s).split()


def build_joined(surface=None, include_unresolved=False):
    am = base.build(surface=surface, include_unresolved=include_unresolved)
    pm, names = pmbase.load_matches()
    # indeks po paru ID-eva
    by_ids = {}
    for i, r in enumerate(pm.itertuples()):
        by_ids.setdefault(frozenset([r.p1, r.p2]), []).append(i)
    # imena -> id (zadnja rijec + prva slova)
    name_to_id = {}
    for pid, nm in names.items():
        if nm:
            name_to_id.setdefault(" ".join(_norm(nm)), pid)
    def nid(nm):
        k = " ".join(_norm(nm))
        if k in name_to_id:
            return name_to_id[k]
        toks = _norm(nm)
        cands = [pid for kk, pid in name_to_id.items() if toks and kk.split()[-1:] == toks[-1:]
                 and kk.split()[0][:1] == toks[0][:1]]
        return cands[0] if len(cands) == 1 else None
    out = []
    for r in am.itertuples():
        a = str(r.pick_id) if isinstance(r.pick_id, str) and r.pick_id else nid(r.pick)
        b = str(r.opp_id) if isinstance(r.opp_id, str) and r.opp_id else nid(r.opp)
        rec = {}
        if a and b:
            cands = [pm.iloc[i] for i in by_ids.get(frozenset([a, b]), [])]
            cands = [c for c in cands if abs((c.date - r.date).days) <= 3]
            if cands:
                c = cands[0]
                rec = dict(pm_result=c.result, pm_rtype=c.rtype, pm_level=c.level, pm_court=c.court,
                           pm_round_id=c.round_id, pm_tname=c.tname, pm_winner=c.winner,
                           pm_pick_won=float(c.winner == a),
                           pm_o_pick=(c.o1 if c.p1 == a else c.o2), pm_o_opp=(c.o2 if c.p1 == a else c.o1))
        rec["pick_pid"], rec["opp_pid"] = a, b
        out.append(rec)
    j = pd.concat([am.reset_index(drop=True), pd.DataFrame(out)], axis=1)
    return j, pm, names


def parse_sets(result, pick_won):
    """'6-4 3-6 7-6(5)' iz perspektive POBJEDNIKA (player1 u past-matches je uvijek pobjednik).
    Vraca listu (games_pick, games_opp, tiebreak) po setu iz perspektive naseg picka."""
    sets = []
    for tok in str(result or "").split():
        m = re.match(r"(\d+)-(\d+)(\((\d+)\))?", tok)
        if not m:
            continue
        w, l = int(m.group(1)), int(m.group(2))
        tb = (w == 7 and l == 6) or (w == 6 and l == 7)
        if pick_won:
            sets.append((w, l, tb))
        else:
            sets.append((l, w, tb))
    return sets
