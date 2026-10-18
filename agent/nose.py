# -*- coding: utf-8 -*-
"""Nose (nose-v1) — vlastita procjena meča koja radi U SJENI (18.10.2026 12:23, korisnikova
odluka "1a" iz revizije 18.10.2026, drugi dio).

ŠTO JE: deterministički "nos" (NE Claude, nema plaćenih poziva) koji za svaki analizirani meč
daje četiri ODVOJENE procjene:
  - Pick Quality      — vlastita vjerojatnost da naš pick pobijedi + pouzdanost te procjene;
  - Mine Risk         — broj konkretnih upozorenja da je pick loš izbor (M1–M5);
  - Upset Value       — konkretni razlozi zašto protivnik može više nego što se čini (U1–U4);
  - Ticket Suitability — UKLJUČI / UZ UPOZORENJE / IZBJEGAVAJ (= NO PICK).

REDOSLIJED JE NAČELO, NE DETALJ (korisnikov uvjet): Nose PRVO donosi vlastitu procjenu iz
teniskih podataka (faza A), zapis se ZAMRZNE (SHA-256 sažetak), a TEK ONDA se uspoređuje s
cijenom (faza B). Faza A fizički ne vidi kvotu: `match_features` čita samo popis teniskih polja
(`_SIDE_FIELDS`), a `assess` odbija ulaz koji nosi ijedno tržišno polje (`_MARKET_TOKENS`).
Test u paketu provjerava da promjena kvote, konsenzusa ili Intuicije ne mijenja fazu A.

U SJENI: računa se u dnevnom runu NAKON što je tiket složen (isto mjesto kao Intuicija), upisuje
se samo u `context_snapshot["nose"]` i prikazuje u aplikaciji uz oznaku "u sjeni, nepotvrđeno".
NE MIJENJA nijedan pick ni tiket. U odabir ulazi tek kad prođe kapiju K24 (DECISION_INPUTS,
pragovi u `revizije/2026-10-18/PRAGOVI_B_2026-10-18.md`, 12:20) i uz korisnikovo odobrenje.

RAZINA DOKAZA (uz svaki "miris", korisnikova želja): sve definicije M1–M5 i U1–U4 zapisane su
PRIJE računanja i provjerene samo na povijesti (`revizije/2026-10-18/skripte/b_lab.py`). Ni
jedna nije potvrđena na našim budućim mečevima; to mjeri K24. Definicije se ne mijenjaju dok
mjerenje traje — svaka izmjena je nova verzija (nose-v2) i kapija kreće od nule.
"""
import hashlib
import json
import math
import re
from functools import lru_cache

VERSION = "nose-v1"

# Udio ELO-a u vlastitoj vjerojatnosti (ostatak je model poena iz servisa i povrata).
# Procijenjeno SAMO na LAB P1 (ATP 2022–2023) prema ISHODU (log-gubitak), nikad prema cijeni;
# ista brojka vrijedi na P2 i uživo (18.10.2026 12:31, `b_lab.py`: rešetka 0–1 po 0,05,
# najbolje 0,80, log-gubitak 0,6071; poštena cijena na istim mečevima 0,5861).
# PROVJERA NA P2 (2024–2026, nije korištena za procjenu): Nose 0,6086 naspram cijene 0,5879,
# a strana kojoj Nose daje 5pp+ više od cijene prolazi −2,3pp [−3,8, −0,8] (N7, n=3.620).
# Dakle: kad se vlastita procjena razilazi s cijenom, u povijesti je u pravu bila CIJENA.
W_ELO = 0.80

# Prosjek osvojenih poena na povratu na skali NAŠEG izvora (RapidAPI sezonski podaci).
# Medijan 908 vrijednosti u snapshotima do 18.10.2026 je 41,4%. Izvor precjenjuje povrat za
# ~2,3pp (memorija "serve/return data defects"), ali kako obje strane dolaze s iste skale,
# pomak se u modelu poena poništava. U LAB-u se predaje LAB-ov prosjek.
AVG_RETURN_LIVE = 0.414

# Pragovi — prepisani iz PRAGOVI_B_2026-10-18.md (12:20; U4 ispravljen u 12:22 prije računanja).
ELO_LEAD_M1 = 25.0          # bodova spojenog ELO-a
SR_GAP = 0.02               # servis + povrat (udjeli poena)
RET_GAP_M2 = 0.02
W2_GAP_M2 = 0.02
TOURN_DROP_M3 = 0.03
TOURN_RISE_M3 = 0.01
SETS_GAP_M4 = 2
REST_MAX_M4 = 1
FORM_GAP_M5 = 0.30
TOURN_RISE_U2 = 0.03
W1_GAP_U3 = 0.03
FORMQ_GAP_U4 = 0.50
P_AVOID = 0.50
P_WARN = 0.55
MARKET_DIFF = 0.05          # faza B: 5pp

# Polja koja faza A smije čitati (po strani). Ništa tržišno.
_SIDE_FIELDS = {
    "elo_s": "elo_surface", "elo_o": "elo_overall", "s": "serve_pts_won", "r": "return_won",
    "w1": "first_serve_won", "w2": "second_serve_won", "form10": "form_10",
    "form_q": "form_quality", "tf_n": "tourn_form_matches", "tf_sv": "tourn_form_serve_won",
    "sets7": "sets_7d", "rest": "days_rest",
}
_PCT_FIELDS = {"s", "r", "w1", "w2", "tf_sv"}
_MARKET_TOKENS = ("odds", "market", "price", "devig", "bookmaker", "intuicija", "consensus",
                  "cons_", "p_dev", "fair", "edge", "kvot")

# Razina dokaza po upozorenju (18.10.2026 12:31; M2 i uživo-napomena 18.10.2026 15:06) — LAB 2022 – 13.09.2026 naspram poštene cijene,
# OPIS, ne test (ne ulazi u kapiju); P1 = 2022–23, P2 = 2024–26. Na našim budućim mečevima
# nijedno nije provjereno — to radi K24. Kombinacije (N5 mina, N6 autsajder) su PALE.
EVIDENCE = {
    "M1": "povijest: nula (-0,8pp; P1 -3,4 / P2 +1,0)",
    # 18.10.2026 15:06 (kritičar): M2 nije monoton po pragu (2,5pp +1,0; 3pp -1,6; 4pp +2,1), cijeli učinak
    # je u prstenu 2,0-2,5pp i u 2023.; najbolja od 9 oznaka (24% šanse da neka to postigne slučajno).
    "M2": "povijest: šum (-4,8pp samo uz prag 2pp, nemonotono; najbolja od 9 oznaka)",
    "M3": "povijest: premalo (n=72)",
    "M4": "povijest: nula (+0,2pp, polovice suprotne)",
    "M5": "povijest: slabo (-2,6pp, interval prelazi nulu)",
    "U1": "povijest: nula (0,0pp)",
    "U2": "povijest: nula (-2,1pp, n=140)",
    "U3": "povijest: šum (+3,9pp, polovice suprotne)",
    "U4": "povijest: nula (-1,5pp)",
}
# Faza B: kad Nose i cijena razilaze za 5pp+, u povijesti je u pravu bila CIJENA (N7 obrnut;
# uz kontrolu pojasa -1,5pp [-2,6, -0,4]; 76% tih strana su autsajderi — b_lab_naknadno.py 15:04).
MARKET_DIFF_EVIDENCE = "povijest: kad se Nose razilazi s cijenom, cijena je bila u pravu (-2,3pp, 2024-26)"
# IZBJEGAVAJ na favoritu, točno pravilo, povijest: +1,3pp uz kontrolu pojasa (n=1.824) — dakle bez
# potpore za "minu" (b_lab_naknadno.py, 18.10.2026 15:04).
AVOID_EVIDENCE = "povijest: takvi favoriti prolaze kako cijena kaže (+1,3pp), mina nije potvrđena"
# Uživo ulazi NISU ulazi s povijesti (kritičar 18.10.2026): servis/povrat iz RapidAPI-ja je praktički
# zamrznuta statistika KARIJERE (povrat ~+4,7pp napuhan), a na povijesti je 365 dana iz TML-a.
LIVE_INPUT_NOTE = "uživo: servis/povrat su karijerni podaci (RapidAPI), ne zadnjih 12 mjeseci"

_LABELS = {
    "M1": "ELO prednost nije potvrđena servisom i povratom",
    "M2": "protivnikov povrat napada pickov 2. servis",
    "M3": "turnir proturječi dugoročnoj formi",
    "M4": "umor: više setova u 7 dana uz najviše dan odmora",
    "M5": "rezultati bolji od izvedbe (forma bez prednosti u poenima)",
    "U1": "protivnik vodi u servisu + povratu",
    "U2": "protivnik na ovom turniru servira iznad svoje razine",
    "U3": "protivnik jači 1. servis na brzom terenu",
    "U4": "protivnikova forma zarađena protiv jačih protivnika",
}


# ------------------------------------------------------------------ pomoćne

def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return None if (isinstance(v, float) and math.isnan(v)) else float(v)
    try:
        return float(str(v).strip().rstrip("%"))
    except (TypeError, ValueError):
        return None


def _form(v):
    """'7/10' -> 0,7; 'W W L' -> udio; broj 0–1 ili 0–10 -> udio."""
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v) if v <= 1 else float(v) / 10.0
    s = str(v)
    m = re.match(r"\s*(\d+)\s*/\s*(\d+)", s)
    if m:
        b = int(m.group(2))
        return int(m.group(1)) / b if b else None
    toks = [t for t in re.split(r"[\s,]+", s) if t in ("W", "L")]
    return (sum(t == "W" for t in toks) / len(toks)) if toks else None


def _has_market(d) -> bool:
    if isinstance(d, dict):
        for k, v in d.items():
            if any(t in str(k).lower() for t in _MARKET_TOKENS):
                return True
            if _has_market(v):
                return True
    return False


# ------------------------------------------------------------------ značajke

def side_features(cs: dict, side: str) -> dict:
    """Teniska polja jedne strane iz snapshota (side = 'p1' ili 'p2'). Postoci -> udjeli.
    ELO 1500 = zadana vrijednost za neprepoznatog igrača (tihi null), pa se tretira kao nepoznat."""
    out = {}
    for key, field in _SIDE_FIELDS.items():
        v = cs.get(f"{side}_{field}")
        if key == "form10":
            out[key] = _form(v)
            continue
        x = _num(v)
        if x is not None and key in _PCT_FIELDS:
            x = x / 100.0 if x > 1.0 else x
            if not (0.0 < x < 1.0):
                x = None
        if key in ("elo_s", "elo_o") and x is not None and (x == 1500.0 or x <= 0):
            x = None
        out[key] = x
    return out


def match_features(cs: dict, surface: str = "", level: str = "") -> dict:
    """Ulaz za fazu A iz `context_snapshot` analize. Čita SAMO teniska polja."""
    cs = cs or {}
    p1, p2 = side_features(cs, "p1"), side_features(cs, "p2")
    if cs.get("elo_suspect"):
        # Analiza s dokazano tuđim ELO-om (revizija 04.10.2026) — ELO se ne koristi.
        for d in (p1, p2):
            d["elo_s"] = d["elo_o"] = None
    surf = (surface or "").lower()
    fast = bool(cs.get("venue_shielded") is True or "indoor" in surf
                or (cs.get("court_pace_label") or "") == "fast")
    best_of = 5 if "grand slam" in (level or "").lower() else 3
    return {"p1": p1, "p2": p2, "fast": fast, "best_of": best_of}


# ------------------------------------------------------------------ model poena

def _game(p: float) -> float:
    q = 1.0 - p
    return (p ** 4 * (1 + 4 * q + 10 * q * q)
            + 20 * p ** 3 * q ** 3 * (p * p / (p * p + q * q)))


def _tiebreak(pa: float, pb: float) -> float:
    """A servira prvi poen; zatim po dva. pa/pb = vjerojatnost da server osvoji poen."""
    @lru_cache(maxsize=None)
    def f(a, b):
        if a >= 7 and a - b >= 2:
            return 1.0
        if b >= 7 and b - a >= 2:
            return 0.0
        if a == b and a >= 6:
            w = pa * (1 - pb)
            l_ = (1 - pa) * pb
            return w / (w + l_) if (w + l_) > 0 else 0.5
        k = a + b
        a_serves = (k % 4 == 0) or (k % 4 == 3)
        p = pa if a_serves else 1 - pb
        return p * f(a + 1, b) + (1 - p) * f(a, b + 1)
    return f(0, 0)


def _set(pa: float, pb: float, a_first: bool) -> float:
    ga, gb = _game(pa), _game(pb)
    tb = _tiebreak(pa, pb) if a_first else 1 - _tiebreak(pb, pa)

    @lru_cache(maxsize=None)
    def f(a, b):
        if (a >= 6 and a - b >= 2) or a == 7:
            return 1.0
        if (b >= 6 and b - a >= 2) or b == 7:
            return 0.0
        if a == 6 and b == 6:
            return tb
        a_serves = ((a + b) % 2 == 0) == a_first
        p = ga if a_serves else 1 - gb
        return p * f(a + 1, b) + (1 - p) * f(a, b + 1)
    return f(0, 0)


def point_model_prob(pa: float, pb: float, best_of: int = 3) -> float:
    """Vjerojatnost da A dobije meč ako osvaja pa poena na svom servisu, a B pb na svom."""
    pa = min(max(pa, 0.40), 0.90)
    pb = min(max(pb, 0.40), 0.90)
    s = 0.5 * (_set(pa, pb, True) + _set(pa, pb, False))
    if best_of == 5:
        return s ** 3 * (1 + 3 * (1 - s) + 6 * (1 - s) ** 2)
    return s * s * (3 - 2 * s)


def _blend_elo(x: dict):
    es, eo = x.get("elo_s"), x.get("elo_o")
    if es is not None and eo is not None:
        return 0.5 * es + 0.5 * eo
    return es if es is not None else eo


# ------------------------------------------------------------------ faza A

def own_probability(a: dict, b: dict, best_of: int = 3, avg_r: float = AVG_RETURN_LIVE,
                    w_elo: float = None):
    """Vlastita vjerojatnost da A pobijedi B. Vraća (P_own, P_elo, P_poeni)."""
    w = W_ELO if w_elo is None else w_elo
    ea, eb = _blend_elo(a), _blend_elo(b)
    p_elo = 1.0 / (1.0 + 10 ** (-(ea - eb) / 400.0)) if (ea is not None and eb is not None) else None
    p_pts = None
    if None not in (a.get("s"), a.get("r"), b.get("s"), b.get("r")):
        pa = a["s"] - (b["r"] - avg_r)
        pb = b["s"] - (a["r"] - avg_r)
        p_pts = point_model_prob(pa, pb, best_of)
    if p_elo is not None and p_pts is not None:
        p = w * p_elo + (1 - w) * p_pts
    else:
        p = p_elo if p_elo is not None else p_pts
    return p, p_elo, p_pts


def _gap(a, b, k):
    return (a[k] - b[k]) if (a.get(k) is not None and b.get(k) is not None) else None


def _sr(x):
    return (x["s"] + x["r"]) if (x.get("s") is not None and x.get("r") is not None) else None


def mine_flags(a: dict, b: dict) -> list:
    """Upozorenja za pick A protiv B (definicije iz PRAGOVI_B, 12:20)."""
    out = []
    ea, eb = _blend_elo(a), _blend_elo(b)
    sra, srb = _sr(a), _sr(b)
    if ea is not None and eb is not None and sra is not None and srb is not None:
        if ea - eb >= ELO_LEAD_M1 and sra - srb <= -SR_GAP:
            out.append("M1")
    g_r, g_w2 = _gap(b, a, "r"), _gap(a, b, "w2")
    if g_r is not None and g_w2 is not None and g_r >= RET_GAP_M2 and g_w2 <= -W2_GAP_M2:
        out.append("M2")
    if (a.get("tf_n") or 0) >= 2 and (b.get("tf_n") or 0) >= 2 and None not in (
            a.get("tf_sv"), a.get("s"), b.get("tf_sv"), b.get("s")):
        if a["tf_sv"] - a["s"] <= -TOURN_DROP_M3 and b["tf_sv"] - b["s"] >= TOURN_RISE_M3:
            out.append("M3")
    if None not in (a.get("sets7"), b.get("sets7"), a.get("rest")):
        if a["sets7"] - b["sets7"] >= SETS_GAP_M4 and a["rest"] <= REST_MAX_M4:
            out.append("M4")
    g_f = _gap(a, b, "form10")
    if g_f is not None and sra is not None and srb is not None:
        if g_f >= FORM_GAP_M5 and sra <= srb:
            out.append("M5")
    return out


def upset_flags(a: dict, b: dict, fast: bool) -> list:
    """Razlozi za protivnika B protiv picka A (definicije iz PRAGOVI_B)."""
    out = []
    sra, srb = _sr(a), _sr(b)
    if sra is not None and srb is not None and srb - sra >= SR_GAP:
        out.append("U1")
    if ((b.get("tf_n") or 0) >= 2 and (a.get("tf_n") or 0) >= 2
            and None not in (b.get("tf_sv"), b.get("s"), a.get("tf_sv"), a.get("s"))):
        if b["tf_sv"] - b["s"] >= TOURN_RISE_U2 and a["tf_sv"] - a["s"] <= 0:
            out.append("U2")
    g = _gap(b, a, "w1")
    if fast and g is not None and g >= W1_GAP_U3:
        out.append("U3")
    g = _gap(b, a, "form_q")
    if g is not None and g >= FORMQ_GAP_U4:
        out.append("U4")
    return out


def _reliability(a: dict, b: dict) -> str:
    elo = None not in (_blend_elo(a), _blend_elo(b))
    sr = None not in (_sr(a), _sr(b))
    form = a.get("form10") is not None and b.get("form10") is not None
    if not elo or not sr:
        return "niska"
    return "visoka" if form else "srednja"


def assess(feat: dict, pick_side: int, avg_r: float = AVG_RETURN_LIVE, w_elo: float = None) -> dict:
    """FAZA A — vlastita procjena iz teniskih podataka. `pick_side` 1 ili 2.

    Odbija ulaz s tržišnim poljem: faza A ne smije ni vidjeti kvotu."""
    if _has_market(feat):
        raise ValueError("Nose faza A ne smije primiti trzisno polje")
    a, b = (feat["p1"], feat["p2"]) if pick_side == 1 else (feat["p2"], feat["p1"])
    p, p_elo, p_pts = own_probability(a, b, feat.get("best_of", 3), avg_r, w_elo)
    mines = mine_flags(a, b)
    ups = upset_flags(a, b, bool(feat.get("fast")))
    rel = _reliability(a, b)
    if p is None:
        suit = "NEMA PODATAKA"
    elif p < P_AVOID or len(mines) >= 2:
        suit = "IZBJEGAVAJ"
    elif len(mines) == 1 or p < P_WARN or len(ups) >= 2:
        suit = "UZ UPOZORENJE"
    else:
        suit = "UKLJUČI"
    reasons = []
    if p is not None and p < P_AVOID:
        reasons.append("Nose čita meč za protivnika (%.0f%%)" % (100 * (1 - p)))
    reasons += [_LABELS[m] for m in mines]
    return {
        "version": VERSION,
        "pick_quality": {"p_own": None if p is None else round(p, 4),
                         "p_elo": None if p_elo is None else round(p_elo, 4),
                         "p_points": None if p_pts is None else round(p_pts, 4),
                         "reliability": rel},
        "mine_risk": {"n": len(mines), "level": ("visok" if len(mines) >= 2 else
                                                  "srednji" if mines else "nizak"),
                      "flags": mines},
        "upset_value": {"n": len(ups), "flags": ups,
                        "p_own_opp": None if p is None else round(1 - p, 4)},
        "ticket_suitability": suit,
        "no_pick": suit == "IZBJEGAVAJ",
        "reasons": reasons,
    }


def freeze(stage_a: dict) -> str:
    """SHA-256 sažetak faze A (12 znakova) — dokaz da je zapisana prije usporedbe s cijenom."""
    blob = json.dumps(stage_a, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


# ------------------------------------------------------------------ faza B

def devig(o_pick, o_opp):
    try:
        a, b = float(o_pick), float(o_opp)
    except (TypeError, ValueError):
        return None
    if not (a > 1.0 and b > 1.0):
        return None
    return (1 / a) / (1 / a + 1 / b)


def compare_with_market(stage_a: dict, odds_pick, odds_opp) -> dict:
    """FAZA B — tek nakon zamrznute faze A. Cijena = devigirana kvota (SuperSport)."""
    p_mkt = devig(odds_pick, odds_opp)
    p = (stage_a.get("pick_quality") or {}).get("p_own")
    if p_mkt is None or p is None:
        return {"p_market": None if p_mkt is None else round(p_mkt, 4), "diff_pp": None,
                "label": "nema usporedbe"}
    d = p - p_mkt
    # "Rizik koji cijena ne vidi" (pick precijenjen) i "vrijednost na protivniku" su ISTI
    # događaj gledan s dvije strane (protivnikova razlika = −d). Zato jedna oznaka + zastavica
    # `opp_value`, koju mjeri G2 točno kako je zapisano (protivnikov P_own − cijena ≥ +5pp).
    if d <= -MARKET_DIFF:
        lab = "Nose vidi rizik koji cijena ne vidi (vrijednost na protivniku)"
    elif d >= MARKET_DIFF:
        lab = "Nose daje picku više od cijene"
    else:
        lab = "u skladu s cijenom"
    return {"p_market": round(p_mkt, 4), "diff_pp": round(100 * d, 1), "label": lab,
            "opp_value": d <= -MARKET_DIFF, "pick_is_market_fav": p_mkt > 0.5}


# ------------------------------------------------------------------ dnevni run

def shadow(pred: dict) -> dict:
    """Nose za jednu predikciju dnevnog runa. Poziva se NAKON slaganja tiketa; ne dira pred
    osim što vraća zapis za `context_snapshot["nose"]`. Greška je {"error": ...}, ne ruši run."""
    try:
        m = pred.get("match") or {}
        cs = pred.get("context_snapshot") or {}
        pick = pred.get("pick") or ""
        p1, p2 = m.get("player1") or "", m.get("player2") or ""
        if not pick or pick not in (p1, p2):
            return {"version": VERSION, "error": "nema picka"}
        side = 1 if pick == p1 else 2
        feat = match_features(cs, m.get("surface") or "", m.get("level") or "")
        a = assess(feat, side)
        a["frozen"] = freeze(a)
        o1, o2 = m.get("odds_p1"), m.get("odds_p2")
        a["vs_market"] = compare_with_market(a, o1 if side == 1 else o2, o2 if side == 1 else o1)
        return a
    except Exception as e:  # noqa: BLE001 — sjena nikad ne smije srušiti run
        return {"version": VERSION, "error": str(e)[:120]}


def describe(n: dict) -> str:
    """Kratak opis za aplikaciju (hrvatski)."""
    if not n or n.get("error"):
        return "Nose: nije izračunat" + (f" ({n.get('error')})" if n else "")
    pq = n.get("pick_quality") or {}
    p = pq.get("p_own")
    parts = [f"{n.get('ticket_suitability')}"
             + (f" [{AVOID_EVIDENCE}]" if n.get("ticket_suitability") == "IZBJEGAVAJ" else "")]
    if p is not None:
        parts.append(f"vlastita procjena {100 * p:.0f}% (pouzdanost {pq.get('reliability')})")
    mr = n.get("mine_risk") or {}
    if mr.get("flags"):
        parts.append("mine: " + "; ".join(f"{_LABELS[f]} [{EVIDENCE[f]}]" for f in mr["flags"]))
    uv = n.get("upset_value") or {}
    if uv.get("flags"):
        parts.append("autsajder: " + "; ".join(f"{_LABELS[f]} [{EVIDENCE[f]}]" for f in uv["flags"]))
    vm = n.get("vs_market") or {}
    if vm.get("diff_pp") is not None:
        txt = f"naspram cijene {vm['diff_pp']:+.1f}pp ({vm['label']})"
        if abs(vm["diff_pp"]) >= 100 * MARKET_DIFF:
            txt += f" [{MARKET_DIFF_EVIDENCE}]"
        parts.append(txt)
    return "Nose (u sjeni, nepotvrđeno; " + LIVE_INPUT_NOTE + "): " + " | ".join(parts)


# ------------------------------------------------------------------ kapija K24

_BANDS = (0.55, 0.65, 0.75, 0.85)     # pojasevi cijene za kontrolu (NAKNADNO 15:05)


def _band(p: float) -> int:
    return sum(1 for b in _BANDS if p >= b)


def _corr(xs, ys):
    k = len(xs)
    if k < 3:
        return 0.0
    mx, my = sum(xs) / k, sum(ys) / k
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return (sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)
            if sxx > 0 and syy > 0 else 0.0)


def gate_status(rows: list) -> dict:
    """K24 (PRAGOVI_B 12:20 + NAKNADNO 15:05, prije ijednog podatka). rows: dict s ključevima
    suit, win (0/1), p (devig cijena picka), date, opp_value (bool), diff (P_own − p, udio).

    ZAMRZNUTO (kritičar 18.10.2026): probir se računa na PRVIH 60 označenih redaka po datumu,
    odluka na PRVIH 150 (G3: 300) — kasniji redovi presudu ne mijenjaju, jer bi ponovno gledanje
    lažnu potvrdu podiglo s 2,4% na 7,5%. KONTROLA POJASA: G1/G2 uz to traže razliku naspram
    ostalih pickova u istom pojasu cijene iz istog razdoblja (≤ −3pp za G1, ≥ +3pp za G2).
    G1 i G2 dijele većinu redaka, pa se zajedno broje kao JEDAN dokaz."""
    rows = sorted(rows, key=lambda r: r["date"])

    def _res(r, opp):
        return ((1 - r["win"]) - (1 - r["p"])) if opp else (r["win"] - r["p"])

    def _edge(rs, opp=False):
        if not rs:
            return 0, None, None
        n = len(rs)
        res = [_res(r, opp) for r in rs]
        m = sum(res) / n
        var = sum((x - m) ** 2 for x in res) / max(n - 1, 1)
        se = math.sqrt(var / n) if n > 1 else float("nan")
        return n, 100 * m, 100 * 1.96 * se

    def _band_diff(flag, others, opp=False):
        """Prosjek (ostatak označenog − prosječni ostatak ostalih u istom pojasu), u pp."""
        by = {}
        for r in others:
            pr = (1 - r["p"]) if opp else r["p"]
            by.setdefault(_band(pr), []).append(_res(r, opp))
        d = []
        for r in flag:
            pr = (1 - r["p"]) if opp else r["p"]
            base = by.get(_band(pr))
            if base:
                d.append(_res(r, opp) - sum(base) / len(base))
        return 100 * sum(d) / len(d) if d else None

    def _gate(is_flag, opp, sign):
        flag_all = [r for r in rows if is_flag(r)]
        n_all = len(flag_all)
        if n_all < 60:
            n, e, ci = _edge(flag_all, opp)
            return {"n": n_all, "edge": e, "ci": ci, "band_diff": None, "status": "CEKA"}
        if n_all < 150:
            first = flag_all[:60]
            n, e, ci = _edge(first, opp)
            killed = (e >= 3) if sign < 0 else (e <= -3)
            return {"n": n_all, "edge": e, "ci": ci, "band_diff": None,
                    "status": "PAO (probir, zamrznuto na prvih 60)" if killed else "CEKA (probir prosao)"}
        first = flag_all[:150]
        cut = first[-1]["date"]
        others = [r for r in rows if not is_flag(r) and r["date"] <= cut]
        n, e, ci = _edge(first, opp)
        h1, h2 = _edge(first[:75], opp)[1], _edge(first[75:], opp)[1]
        bd = _band_diff(first, others, opp)
        if sign < 0:
            ok = e <= -5 and e + ci < 0 and h1 < 0 and h2 < 0 and bd is not None and bd <= -3
            bad = e >= 0 or (bd is not None and bd >= 0)
        else:
            ok = e >= 5 and e - ci > 0 and h1 > 0 and h2 > 0 and bd is not None and bd >= 3
            bad = e <= 0 or (bd is not None and bd <= 0)
        st = "POTVRDJEN" if ok else ("PAO" if bad else "NEJASNO")
        return {"n": n_all, "edge": e, "ci": ci, "band_diff": bd,
                "status": st + " (konacno, prvih 150)"}

    out = {"G1": _gate(lambda r: r.get("suit") == "IZBJEGAVAJ", False, -1),
           "G2": _gate(lambda r: bool(r.get("opp_value")), True, +1)}
    g3_all = [r for r in rows if r.get("diff") is not None]
    n = len(g3_all)
    g3 = g3_all[:300]
    r = lo = None
    if len(g3) >= 30:
        r = _corr([x["diff"] for x in g3], [x["win"] - x["p"] for x in g3])
        se = 1 / math.sqrt(max(len(g3) - 3, 1))
        lo = math.tanh(math.atanh(max(min(r, 0.999), -0.999)) - 1.96 * se)
    if n >= 300:
        r1 = _corr([x["diff"] for x in g3[:150]], [x["win"] - x["p"] for x in g3[:150]])
        r2 = _corr([x["diff"] for x in g3[150:]], [x["win"] - x["p"] for x in g3[150:]])
        st = ("POTVRDJEN" if (r >= 0.10 and lo > 0 and r1 > 0 and r2 > 0)
              else "PAO" if r <= 0 else "NEJASNO") + " (konacno, prvih 300)"
    else:
        st = "CEKA"
    out["G3"] = {"n": n, "r": r, "lo": lo, "status": st}
    return out
