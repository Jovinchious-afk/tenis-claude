# -*- coding: utf-8 -*-
"""Revizija 08.11.2026 — scouting top 150: dokazi i izmjene (08.11.2026 11:55).

Korisnik 08.11.2026: "slobodno diraj i Excel i Supabase kada napraviš update za scouting". Pravila
zapisana prije računa: revizije/2026-11-08/PRAGOVI_REVIZIJA_2026-11-08.md, točka J (11:27) i
NAKNADNO J (08.11.2026 11:53). Postupak je isti kao 18.10.2026 (`revizije/2026-10-18/skripte/b_scouting.py`):
original rečenica OSTAJE, uz nju se doda "[08.11.2026 check: ...]" s brojkama; razine pouzdanosti se
ne mijenjaju; rezultati turnira su samo opis.

Statistika: TML preuzet 08.11.2026 u scratchpad (2025.csv, 2026.csv, ongoing_tourneys.csv) — put se
daje argumentom --tml=MAPA. Čita se samo modulom csv (bez izvršavanja ičega iz preuzetih datoteka).

    python revizije/2026-11-08/skripte/r_scouting.py --tml=MAPA               # suho: samo prijedlog
    python revizije/2026-11-08/skripte/r_scouting.py --tml=MAPA --primijeni   # kopija + upis + Excel
Povratak: python revizije/2026-11-08/skripte/r_scouting_vrati.py
"""
import csv
import datetime as dt
import json
import os
import re
import shutil
import sys
import unicodedata
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(ROOT, ".env"))
from database import supabase_client as db  # noqa: E402

OUTD = os.path.join(ROOT, "revizije", "2026-11-08", "scouting")
XLSX = os.path.join(ROOT, "ATP_Player_Scouting top150.xlsx")
DUMP = os.path.join(ROOT, ".cache", "rev_2026-11-08")
BACKUP = os.path.join(OUTD, "player_scouting_prije_2026-11-08.json")
XLSX_BACKUP = os.path.join(OUTD, "ATP_Player_Scouting_top150_prije_2026-11-08.xlsx")
STAMP = "08.11.2026"
MIN_MATCHES = 25
MARGIN_PP = 0.02
MARGIN_ACE = 0.05
IN_MIN, IN_WIN = 12, 0.55
TOUR_LEVELS = {"G", "M", "A", "F", "O", "500", "250"}
EN = {"veliki server": "big server", "jak povratnik": "strong returner", "slab povrat": "weak return",
      "slab servis": "weak serve", "slab u dvorani": "weaker indoors / on fast courts"}
CLAIMS = {   # isti obrasci kao 18.10.2026 + peti (NAKNADNO J 11:53)
    "veliki server": (("style", "strengths"),
                      r"\bbig[- ]serv|\bhuge serve|\bmonster serve|\bpower server|\bserve[- ]first|\bbig-ace serve|\bstrong serve\b"),
    "jak povratnik": (("style", "strengths"),
                      r"\breturner\b|\belite return|\bstrong return\b|\bexcellent return|\bgreat return"),
    "slab povrat": (("weaknesses",),
                    r"return (is the weaker half|game is the weak link)|\b(weak|modest|poor|limited) return|return weaker"),
    "slab servis": (("weaknesses",),
                    r"serve is a liability|\bweak serve|\bsoft serve|serve not yet a weapon"),
    "slab u dvorani": (("weaknesses",),
                       r"\bindoor|\bfast[- ](hard|court|indoor)|\bquick court|\bflat[- ]court"),
}
OLD_NOTE = re.compile(r"\s*\[18\.10\.2026 check: '([^']+)' NOT supported[^\]]*\]")


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().replace("-", " ").replace("'", " ").strip().split())


def num(x):
    try:
        return float(x) if x not in (None, "") else None
    except ValueError:
        return None


def tml_rows(folder):
    seen, rows = set(), []
    for name in ("2025.csv", "2026.csv", "ongoing_tourneys.csv"):
        p = os.path.join(folder, name)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                key = (r.get("tourney_id"), r.get("winner_id"), r.get("loser_id"), r.get("round"))
                if key in seen:
                    continue
                seen.add(key)
                rows.append(r)
    return rows


def profiles(rows):
    dates = []
    for r in rows:
        try:
            dates.append(dt.datetime.strptime(str(r.get("tourney_date"))[:8], "%Y%m%d").date())
        except ValueError:
            dates.append(None)
    end = max(d for d in dates if d)
    lo = end - dt.timedelta(days=365)
    acc = defaultdict(lambda: defaultdict(float))
    names = {}
    cols = ["svpt", "ace", "1stIn", "1stWon", "2ndWon", "SvGms", "bpSaved", "bpFaced"]
    for r, d in zip(rows, dates):
        if not d or not (lo < d <= end) or r.get("tourney_level") not in TOUR_LEVELS:
            continue
        w = [num(r.get(f"w_{c}")) for c in cols]
        l_ = [num(r.get(f"l_{c}")) for c in cols]
        if None in w or None in l_ or w[0] <= 0 or l_[0] <= 0 or w[5] <= 0 or l_[5] <= 0:
            continue
        indoor = (r.get("indoor") == "I")
        hard = (r.get("surface") == "Hard")
        for pid, nm, me, op, won in ((r["winner_id"], r["winner_name"], w, l_, 1), (r["loser_id"], r["loser_name"], l_, w, 0)):
            names[pid] = nm
            a = acc[pid]
            a["n"] += 1
            for c, v in zip(cols, me):
                a[c] += v
            a["o_svpt"] += op[0]
            a["o_won"] += op[3] + op[4]
            tp_me = (me[3] + me[4]) + (op[0] - op[3] - op[4])      # poeni osvojeni na svom + tuđem servisu
            tp_all = me[0] + op[0]
            if indoor:
                a["n_in"] += 1
                a["w_in"] += won
                a["tp_in"] += tp_me
                a["pt_in"] += tp_all
            elif hard:
                a["n_oh"] += 1
                a["w_oh"] += won
                a["tp_oh"] += tp_me
                a["pt_oh"] += tp_all
    prof = {}
    for pid, a in acc.items():
        if a["n"] < MIN_MATCHES:
            continue
        prof[norm(names[pid])] = {
            "n": int(a["n"]), "name": names[pid],
            "ace_sg": a["ace"] / a["SvGms"], "hold": 1 - (a["bpFaced"] - a["bpSaved"]) / a["SvGms"],
            "ret": 1 - a["o_won"] / a["o_svpt"], "srv": (a["1stWon"] + a["2ndWon"]) / a["svpt"],
            "n_in": int(a["n_in"]), "win_in": a["w_in"] / a["n_in"] if a["n_in"] else None,
            "tpw_in": a["tp_in"] / a["pt_in"] if a["pt_in"] else None, "w_in": int(a["w_in"]),
            "n_oh": int(a["n_oh"]), "win_oh": a["w_oh"] / a["n_oh"] if a["n_oh"] else None,
            "tpw_oh": a["tp_oh"] / a["pt_oh"] if a["pt_oh"] else None, "w_oh": int(a["w_oh"]),
        }
    return prof, end


def pct(prof, k, q):
    vals = sorted(p[k] for p in prof.values())
    i = q * (len(vals) - 1)
    lo_, hi_ = int(i), min(int(i) + 1, len(vals) - 1)
    return vals[lo_] + (vals[hi_] - vals[lo_]) * (i - lo_)


def find(prof, name):
    k = norm(name)
    if k in prof:
        return prof[k]
    parts = k.split()
    cand = [v for kk, v in prof.items() if parts and kk.split()[-1:] == parts[-1:] and kk.split()[0][:1] == parts[0][:1]]
    return cand[0] if len(cand) == 1 else None


def recent_ranks():
    am = json.load(open(os.path.join(DUMP, "analyzed_matches.json"), encoding="utf-8"))
    out = {}
    for r in sorted(am, key=lambda x: str(x.get("match_date"))):
        if str(r.get("match_date"))[:10] < "2026-10-26":
            continue
        cs = r.get("context_snapshot") or {}
        for side in ("p1", "p2"):
            rk = cs.get(f"{side}_ranking")
            if isinstance(rk, (int, float)) and 0 < rk < 999:
                out[norm(r.get("player1" if side == "p1" else "player2"))] = (int(rk), str(r["match_date"])[:10])
    return out


def results_since(rows):
    """Opis: W-L od 19.10.2026 (TML glavni ždrijeb) po igraču."""
    res = defaultdict(lambda: [0, 0, []])
    for r in rows:
        try:
            d = dt.datetime.strptime(str(r.get("tourney_date"))[:8], "%Y%m%d").date()
        except ValueError:
            continue
        if d < dt.date(2026, 10, 12) or r.get("tourney_level") not in TOUR_LEVELS:
            continue
        t = r.get("tourney_name")
        for nm, won in ((r["winner_name"], 1), (r["loser_name"], 0)):
            x = res[norm(nm)]
            x[0 if won else 1] += 1
            if t not in x[2]:
                x[2].append(t)
    return res


def check(claim, p, med, p75):
    if claim == "veliki server":
        bad = p["ace_sg"] <= med["ace_sg"] - MARGIN_ACE and p["hold"] <= med["hold"] - MARGIN_PP
        txt = f"aces/service game {p['ace_sg']:.2f} (median {med['ace_sg']:.2f}), hold {100 * p['hold']:.1f}% (median {100 * med['hold']:.1f}%)"
    elif claim == "jak povratnik":
        bad = p["ret"] <= med["ret"] - MARGIN_PP
        txt = f"return points won {100 * p['ret']:.1f}% (median {100 * med['ret']:.1f}%)"
    elif claim == "slab povrat":
        bad = p["ret"] >= p75["ret"] + MARGIN_PP
        txt = f"return points won {100 * p['ret']:.1f}% (75th pct {100 * p75['ret']:.1f}%)"
    elif claim == "slab servis":
        bad = p["hold"] >= p75["hold"] + MARGIN_PP
        txt = f"hold {100 * p['hold']:.1f}% (75th pct {100 * p75['hold']:.1f}%)"
    else:
        if p["n_in"] < IN_MIN or p["tpw_in"] is None or p["tpw_oh"] is None:
            return None, f"too few indoor matches ({p['n_in']})"
        bad = p["tpw_in"] >= p["tpw_oh"] and p["win_in"] >= IN_WIN
        txt = (f"indoor hard {p['w_in']}-{p['n_in'] - p['w_in']} ({100 * p['win_in']:.0f}%), points won {100 * p['tpw_in']:.1f}% "
               f"vs outdoor hard {100 * p['tpw_oh']:.1f}% ({p['w_oh']}-{p['n_oh'] - p['w_oh']})")
    return bad, txt


def main(apply=False, folder=None):
    live = db._select("player_scouting", select="*", limit=400)
    print(f"profila u Supabaseu: {len(live)}")
    rows_t = tml_rows(folder)
    prof, end = profiles(rows_t)
    med = {k: pct(prof, k, 0.5) for k in ("ace_sg", "hold", "ret")}
    p75 = {k: pct(prof, k, 0.75) for k in ("hold", "ret")}
    print(f"TML 365 d do {end}, glavni ždrijeb, >= {MIN_MATCHES} mečeva: {len(prof)} igrača | medijan asovi/gem {med['ace_sg']:.3f}, "
          f"hold {100 * med['hold']:.1f}%, povrat {100 * med['ret']:.1f}% | 75. pct hold {100 * p75['hold']:.1f}%, povrat {100 * p75['ret']:.1f}%")
    ranks, since = recent_ranks(), results_since(rows_t)
    changes, evidence = [], []
    for r in live:
        nm, disp = r["player_name"], r.get("display_name") or r["player_name"]
        p = find(prof, disp) or find(prof, nm)
        ev = {"player_name": nm, "display_name": disp, "confidence": r.get("confidence"), "rank_old": r.get("rank"),
              "stat": p, "claims": [], "since": since.get(norm(disp)) or since.get(norm(nm))}
        new_fields, reasons = {}, []
        # 3. stare oznake 18.10. koje nove brojke više ne podupiru — uklanjaju se
        for fld in ("style", "strengths", "weaknesses"):
            txt = r.get(fld) or ""
            for mm in OLD_NOTE.finditer(txt):
                claim = {v: k for k, v in EN.items()}.get(mm.group(1))
                if claim and p is not None:
                    bad, numtxt = check(claim, p, med, p75)
                    if bad is False:
                        new_fields[fld] = new_fields.get(fld, txt).replace(mm.group(0), "")
                        reasons.append(f"uklonjena oznaka 18.10. ({claim}, {fld}): nove brojke je više ne podupiru — {numtxt}")
        for claim, (fields, pat) in CLAIMS.items():
            for fld in fields:
                txt = new_fields.get(fld, r.get(fld) or "")
                bare = OLD_NOTE.sub("", txt)
                if not re.search(pat, re.sub(r"\[[^\]]*\]", "", bare), re.I):
                    continue
                if p is None:
                    ev["claims"].append((claim, fld, "neprovjerljivo (manje od 25 mečeva glavnog ždrijeba)"))
                    continue
                bad, numtxt = check(claim, p, med, p75)
                if bad is None:
                    ev["claims"].append((claim, fld, "neprovjerljivo: " + numtxt))
                    continue
                ev["claims"].append((claim, fld, ("OPOVRGNUTO: " if bad else "nije opovrgnuto: ") + numtxt))
                already = (f"'{EN[claim]}' NOT supported" in txt)
                if bad and not already:
                    new_fields[fld] = (txt + f" [{STAMP} check: '{EN[claim]}' NOT supported - {numtxt}; "
                                       f"ATP main draw, {p['n']} matches, 365 d to {end.strftime('%d.%m.%Y')}]")
                    reasons.append(f"{claim} ({fld}): OPOVRGNUTO — {numtxt}")
        rk = ranks.get(norm(disp)) or ranks.get(norm(nm))
        if rk and rk[0] != r.get("rank"):
            new_fields["rank"] = rk[0]
            ev["rank_new"] = rk
            reasons.append(f"rang {r.get('rank')} -> {rk[0]} (snimka dnevnog runa {rk[1]})")
        if new_fields:
            changes.append({"player_name": nm, "display_name": disp, "confidence": r.get("confidence"),
                            "old": {k: r.get(k) for k in new_fields}, "new": new_fields, "reasons": reasons})
        evidence.append(ev)
    n_txt = sum(1 for c in changes if set(c["new"]) - {"rank"})
    n_rank = sum(1 for c in changes if "rank" in c["new"])
    print(f"\nprijedlog: {len(changes)} profila — tekst {n_txt}, rang {n_rank}")
    from collections import Counter
    cnt = Counter((c[0], c[2].split(":")[0]) for e in evidence for c in e["claims"])
    for k, v in sorted(cnt.items()):
        print(f"  {k[0]:15s} {k[1]:45s} {v}")
    for c in changes:
        if set(c["new"]) - {"rank"}:
            print(f"\n  * {c['display_name']} [{c['confidence']}]")
            for x in c["reasons"]:
                print(f"      {x}")
    print("\n  Rangovi:", ", ".join(f"{c['display_name']} {c['old'].get('rank')}→{c['new']['rank']}" for c in changes if "rank" in c["new"]))
    if not apply:
        print("\n(suho — ništa nije upisano; za upis: --primijeni)")
        return changes, evidence
    os.makedirs(OUTD, exist_ok=True)
    if not os.path.exists(BACKUP):
        json.dump(live, open(BACKUP, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
        shutil.copy2(XLSX, XLSX_BACKUP)
        print(f"\nkopija: {BACKUP} ({len(live)} redaka) + Excel")
    ok = 0
    for c in changes:
        res = db._update("player_scouting", c["new"], {"player_name": f"eq.{c['player_name']}"})
        ok += 1 if isinstance(res, list) and res else 0
    print(f"upisano u Supabase: {ok}/{len(changes)}")
    json.dump({"vrijeme": STAMP, "pravila": "PRAGOVI_REVIZIJA_2026-11-08.md, točka J (11:27) i NAKNADNO J (11:53)",
               "tml_do": end.isoformat(), "promjene": changes},
              open(os.path.join(OUTD, "promjene_2026-11-08.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    write_excel(evidence, changes, med, p75, end)
    return changes, evidence


def _copy_sheet(src_ws, dst_wb, title):
    from openpyxl.styles import Alignment, Font
    ws = dst_wb.create_sheet(title)
    for row in src_ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                n = ws.cell(row=cell.row, column=cell.column, value=cell.value)
                n.alignment = Alignment(vertical="top", wrap_text=bool(cell.alignment and cell.alignment.wrap_text))
                if cell.font and cell.font.bold:
                    n.font = Font(bold=True)
    for k, dim in src_ws.column_dimensions.items():
        ws.column_dimensions[k].width = dim.width


def write_excel(evidence, changes, med, p75, end):
    """Glavni list = izvoz iz Supabasea (`scripts/export_scouting_excel.py`); listovi 18.10. se prenose
    iz kopije; dodaju se 'Dokazi 08.11.2026' i 'Promjene 08.11.2026'."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import export_scouting_excel as ex
    import openpyxl
    from openpyxl.styles import Alignment, Font
    ex.main()
    wb = openpyxl.load_workbook(XLSX)
    old = openpyxl.load_workbook(XLSX_BACKUP)
    for title in old.sheetnames[1:]:
        _copy_sheet(old[title], wb, title)
    ws = wb.create_sheet("Dokazi 08.11.2026")
    head = ["Igrač", "Pouzdanost profila", "STATISTIKA (TML 365 d, glavni ždrijeb): mečeva", "asovi / servis-gem", "hold %",
            "povrat %", "servis %", "dvorana: W-L", "dvorana: poeni %", "otvoreni tvrdi: W-L", "otvoreni tvrdi: poeni %",
            "REZULTATI od 12.10. (TML, opis)", "PROCJENA STILA: tvrdnje iz profila i provjera"]
    for c, h in enumerate(head, 1):
        ws.cell(row=1, column=c, value=h).font = Font(bold=True)
    ws.cell(row=2, column=1, value=(f"TML do {end.strftime('%d.%m.%Y')}. Medijan: asovi/gem {med['ace_sg']:.2f}, hold {100 * med['hold']:.1f}%, "
                                    f"povrat {100 * med['ret']:.1f}% | 75. percentil: hold {100 * p75['hold']:.1f}%, povrat {100 * p75['ret']:.1f}%. "
                                    f"Dvorana: tvrdnja 'slabiji u dvorani' pada uz ≥ {IN_MIN} mečeva, poeni u dvorani ≥ otvoreni tvrdi i ≥ 55% pobjeda. "
                                    f"Rezultati su OPIS i sami ne mijenjaju profil."))
    for i, e in enumerate(sorted(evidence, key=lambda x: (x.get("rank_old") or 999)), start=3):
        p = e["stat"] or {}
        s = e["since"]
        vals = [e["display_name"], e["confidence"], p.get("n"),
                round(p["ace_sg"], 2) if p else None, round(100 * p["hold"], 1) if p else None,
                round(100 * p["ret"], 1) if p else None, round(100 * p["srv"], 1) if p else None,
                f"{p['w_in']}-{p['n_in'] - p['w_in']}" if p else None,
                round(100 * p["tpw_in"], 1) if p and p.get("tpw_in") else None,
                f"{p['w_oh']}-{p['n_oh'] - p['w_oh']}" if p else None,
                round(100 * p["tpw_oh"], 1) if p and p.get("tpw_oh") else None,
                (f"{s[0]}-{s[1]} ({', '.join(s[2])})" if s else ""),
                " | ".join(f"{c[0]} ({c[1]}): {c[2]}" for c in e["claims"])]
        for c, v in enumerate(vals, 1):
            ws.cell(row=i, column=c, value=v).alignment = Alignment(vertical="top", wrap_text=(c in (12, 13)))
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["L"].width = 50
    ws.column_dimensions["M"].width = 110
    ws2 = wb.create_sheet("Promjene 08.11.2026")
    for c, h in enumerate(["Igrač", "Polje", "Staro", "Novo", "Razlog"], 1):
        ws2.cell(row=1, column=c, value=h).font = Font(bold=True)
    k = 2
    for ch in changes:
        for fld, new in ch["new"].items():
            for c, v in enumerate([ch["display_name"], fld, ch["old"].get(fld), new, "; ".join(ch["reasons"])], 1):
                ws2.cell(row=k, column=c, value=v).alignment = Alignment(vertical="top", wrap_text=True)
            k += 1
    for col, w in zip("ABCDE", (26, 12, 60, 60, 80)):
        ws2.column_dimensions[col].width = w
    wb.save(XLSX)
    print(f"Excel osvježen: {os.path.basename(XLSX)} (listovi: {', '.join(wb.sheetnames)})")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    folder = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--tml=")), None)
    if not folder:
        sys.exit("treba --tml=MAPA (preuzeti TML)")
    main(apply="--primijeni" in sys.argv, folder=folder)
