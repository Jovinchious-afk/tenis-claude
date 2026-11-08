# -*- coding: utf-8 -*-
"""Nos-odluka (nos-odluka-v1) — NOS DOBIVA PRAVO ODLUKE pri slaganju tiketa (08.11.2026 12:34).

KORISNIKOVA ODLUKA 08.11.2026 (poruka nakon revizije Pariza): "moramo dati nosu tj. intuiciji moć da
donosi odluke pri kreiranju picka ... ne zanima me ako je rezultat slučajan na malom uzorku ... nešto
danas moramo mijenjati". Uvodi se BEZ kapije (CLAUDE.md pravilo 1: ulazak u model uvijek odobrava
korisnik — ovdje ga je izričito naložio). Zato: puna evidencija u `context_snapshot["nos_odluka"]`,
usporedba sa starim izborom (što bi tiket bio bez nosa) i prekidač `NOS_ODLUKA_ON` u
`config/model_config.py`. Revizija i podaci: `revizije/2026-11-08/REVIZIJA_2026-11-08.md`.

ŠTO RADI (deterministički, bez Claudea i bez plaćenih poziva):
  1. ZNAKOVI za stranu meča: 14 znakova nos-ploče (iste definicije, `agent/nos_ploca.compute`) i 8
     novih. Iz ploče su izostavljeni:
       - "pick_autsajder" — već ga kažnjava mjerena kazna −5 u predictoru, pa bi se brojao dvaput;
       - "ozljeda_pick"/"ozljeda_prot" — detektor v2 pripisuje ozljedu krivom igraču (revizija
         08.11., ideja 6), pa ih ovdje zamjenjuju znakovi iz detektora v3.
  2. TEŽINE uči `nauci()` iz naših riješenih pickova zadnjih PROZOR_DANA dana:
       - učinak znaka = razlika pobjeda − cijena naspram ostalih pickova U ISTOM POJASU cijene; za
         znakove koje definira sama cijena (pojasevi kvote) razlika je naspram svih ostalih pickova;
       - skupljanje prema nuli n / (n + K);
       - predznak smije biti samo onaj iz definicije znaka (mina ≤ 0, prilika ≥ 0): nos uči
         KOLIKO, ne i u kojem smjeru. Bez toga bi Nose-ov "IZBJEGAVAJ" (koji je dosad prolazio
         bolje) podizao pouzdanost — besmislen zaključak iz 24 meča;
       - strop STROP_ZNAK boda po znaku.
     `scripts/nos_tezine.py` zapisuje težine u `config/nos_tezine.json`; GitHub ih uči svako jutro prije
     dnevnog runa (nos "uči" iz svakog novog rezultata), a bez toga se čita spremljena datoteka.
  3. ODLUKA po picku: zbroj težina upaljenih znakova (strop STROP_UKUPNO) pomiče POUZDANOST ZA TIKET
     — prag 63, kaskadu, dnevne limite i bodovanje kombinacija. Modelova pouzdanost ostaje u bazi
     (`analyzed_matches.predicted_confidence`), pa mjerenje modela nije prekinuto; noga tiketa nosi
     pouzdanost nakon nosa.
  4. NOS-AUTSAJDER: Nose (vlastita procjena prije cijene) vidi vrijednost na PROTIVNIKU našeg picka, a
     model nije uvjeren → kandidat za NAJVIŠE JEDNU nogu na autsajdera po tiketu (`ticket_builder`).
     Mjereno do 08.11. (opis, ne dokaz): od 05.10. takve oklade 17–35, edge +2,0pp ±12,2, ROI +11,7%
     (n=52); u Parizu 5–8, ROI +44%.
"""
import datetime as _dt
import json
import os

from agent import nos_ploca as _np

VERSION = "nos-odluka-v1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEZINE_PATH = os.path.join(ROOT, "config", "nos_tezine.json")

# ── parametri (08.11.2026 12:31; korisnikova odluka, obrazloženje u docstringu) ─────────────────
# PROZOR 60 -> 120 dana (08.11.2026 16:42, korisnikov zahtjev "isto napravi s prijašnja 3-4 turnira pa
# vidi koja je najbolja kombinacija ... i takav nos postavi"): simulacija hodom naprijed 27.09.–07.11.
# (`revizije/2026-11-08/skripte/r_nos_varijante.py`, 11 inačica zadanih unaprijed, Claudeov pregled
# izostavljen). Prozor 120 imao je najbolji edge nogu (+14,3pp naspram +12,2 uz 60 dana i +5,9 bez nosa)
# i u SVAKOM tjednu edge jednak ili bolji od prozora 60; ROI tiketa +62% (60 dana +63%, bez nosa +24%).
# Ograda: razlike među inačicama su u granici slučajnosti (jedan dobitni tiket mijenja poredak).
# STARE VARIJABLE KAO ZNAK NOSA — PROBANO 08.11.2026 17:27 (revizija 08.11., Dodatak 2): svaka je dodana
# kao jedan znak više i ponovljena je ista simulacija hodom naprijed. Edge nogu tiketa se mijenjao ovako:
# konsenzus kladionica −5,4pp, ATP pobjede u sezoni −7,3pp, vodstvo u tie-breakovima −3,0pp, izjednačen
# servis −2,7pp; forma i povijest na turniru dobile su težinu 0; "protivnik nam je već izbacio picka"
# +0,2pp (jedna noga, šum). -> NIJEDNA NIJE DODANA. Nosu može pomoći samo podatak kojeg nema u kvoti:
# ozljeda iz detektora v3 (K13c, od 09.11.) i točan H2H iz TML-a (prosinac). Također za prosinac: kad se
# makne fiksna kazna −5 za autsajdera u predictoru, `pick_autsajder` se vraća kao naučeni znak (time
# nestaje dvostruko brojanje iz točke 1 docstringa).
PROZOR_DANA = 120         # nos uči na zadnja ~4 mjeseca riješenih pickova
K_SKUPLJANJE = 60.0       # uz n=60 znak dobiva pola svog izmjerenog učinka, uz n=20 četvrtinu
MIN_N = 8                 # znak s manje pickova ima težinu 0
STROP_ZNAK = 4.0          # bodova po znaku
STROP_UKUPNO = 6.0        # bodova ukupno po picku

ELO_JAK = 150.0           # bodova ELO-a na podlozi (gornja trećina naših pickova od 05.10. ≈ 150)
JUTRO_SAT = 13            # lokalni sat početka < 13 h
POJAS_KRATKI = (1.20, 1.35)
NOSE_RAZLIKA = 5.0        # pp, isti prag kao Nose `MARKET_DIFF` (G2)

AUTS_KVOTA = (2.00, 3.50)        # nos-autsajder: kvota protivnika
AUTS_MIN_PREDNOST_PP = 5.0       # Nose: protivnikov P_own − cijena ≥ +5pp (= G2 / `opp_value`)
AUTS_MAX_MODEL_CONF = 64.0       # nos ide protiv modela samo kad model nije uvjeren
AUTS_MIN_OCJENA = 0.0            # zbroj težina ne-cjenovnih znakova za protivnika

# (id, vrsta, cjenovni, oznaka) — vrsta određuje dopušteni predznak naučene težine
ZNAKOVI = [
    ("novcic", "mina", True, "Novčić: kvota 1,65+"),
    ("pojas_135_145", "mina", True, "Pojas 1,35–1,45"),
    ("tanki_elo", "mina", False, "Tanki ELO (< 50)"),
    ("profil_t1_pick", "mina", False, "Pick: elitni povrat + slab servis, dvorana"),
    ("profil_t1_prot", "prilika", False, "Protivnik: elitni povrat + slab servis, dvorana"),
    ("prot_domaci", "prilika", False, "Protivnik je domaći"),
    ("prot_susjed", "prilika", False, "Protivnik je susjed"),
    ("pick_domaci", "mina", False, "Pick je domaći"),
    ("mladi_pick", "mina", False, "Pick 4+ god. mlađi (R128/R64 ili QF+)"),
    ("pauza_pick", "mina", False, "Pick nakon 21+ dan pauze"),
    ("pauza_prot", "prilika", False, "Protivnik nakon 21+ dan pauze"),
    ("nose_izbjegavaj", "mina", False, "Nose: IZBJEGAVAJ"),
    ("nose_upozorenje", "mina", False, "Nose: UZ UPOZORENJE"),
    ("nocna", "opis", False, "Noćna sesija"),
    # novo 08.11.2026
    ("ozljeda_pick_v3", "mina", False, "Pick: vijest o ozljedi (detektor v3)"),
    ("ozljeda_prot_v3", "prilika", False, "Protivnik: vijest o ozljedi (detektor v3)"),
    ("scout_jak", "prilika", False, "Pick: scouting High/Med-High"),
    ("elo_jak", "prilika", False, "ELO na podlozi +150 ili više"),
    ("pojas_120_135", "prilika", True, "Pojas 1,20–1,35"),
    ("jutro", "mina", False, "Jutarnji meč (< 13 h)"),
    ("nose_plus", "prilika", False, "Nose daje strani 5pp+ više od cijene"),
    ("nose_minus", "mina", False, "Nose daje strani 5pp+ manje od cijene"),
]
INFO = {z[0]: {"vrsta": z[1], "cjenovni": z[2], "oznaka": z[3]} for z in ZNAKOVI}
_IZ_PLOCE = [z[0] for z in ZNAKOVI[:14]]


def _num(v):
    return _np._num(v)


def _sat(lt):
    """'HH:MM' -> sat (int) ili None."""
    try:
        return int(str(lt).strip()[:2])
    except (TypeError, ValueError):
        return None


def znakovi(rec: dict, za_igraca: str = None) -> dict:
    """Znakovi za stranu `za_igraca` (zadano: modelov pick `rec["pick"]`).

    rec = zapis nos-ploče ({"pick","p1","p2","odds_p1","odds_p2","surface","tournament","round","cs"}).
    Vraća {"aktivni": [...], "nedostaje": [...], "detalji": {...}} ili {"error": ...}."""
    try:
        model_pick = rec.get("pick") or ""
        strana = za_igraca or model_pick
        p1, p2 = rec.get("p1") or "", rec.get("p2") or ""
        if strana not in (p1, p2):
            return {"error": "strana nije u meču"}
        r = dict(rec)
        r["pick"] = strana
        b = _np.compute(r)
        if b.get("error"):
            return {"error": b["error"]}
        aktivni = [z for z in b.get("znakovi") or [] if z in _IZ_PLOCE]
        nedostaje = [z for z in b.get("nedostaje") or [] if z in _IZ_PLOCE]
        det = {z: d for z, d in (b.get("detalji") or {}).items() if z in _IZ_PLOCE}
        cs = rec.get("cs") or {}
        a, o = ("p1", "p2") if strana == p1 else ("p2", "p1")
        o1, o2 = _num(rec.get("odds_p1")), _num(rec.get("odds_p2"))
        op = o1 if a == "p1" else o2

        def put(sid, cond, d=""):
            if cond is None:
                nedostaje.append(sid)
            elif cond:
                aktivni.append(sid)
                if d:
                    det[sid] = d

        # ozljeda, detektor v3 (bez v3 zapisa = nedostaje; stari v2 se namjerno ne koristi)
        for sid, x in (("ozljeda_pick_v3", a), ("ozljeda_prot_v3", o)):
            g = cs.get(f"{x}_gnews")
            v = _num(g.get("injury_n3")) if isinstance(g, dict) and "injury_n3" in g else None
            put(sid, (v >= 1) if v is not None else None, f"{v:.0f} naslova" if v else "")
        # scouting profil strane (bez profila = nije jak; ne "nedostaje")
        sc = str(cs.get(f"{a}_scouting_confidence") or "").strip()
        put("scout_jak", sc in ("High", "Med-High"), sc)
        # ELO na podlozi (1500 je zadana vrijednost, ne podatak)
        ea, eb = _num(cs.get(f"{a}_elo_surface")), _num(cs.get(f"{o}_elo_surface"))
        ok = ea is not None and eb is not None and 1500.0 not in (ea, eb)
        put("elo_jak", (ea - eb >= ELO_JAK) if ok else None, f"{ea - eb:+.0f}" if ok else "")
        put("pojas_120_135", (POJAS_KRATKI[0] <= op < POJAS_KRATKI[1]) if op else None,
            f"kvota {op:.2f}" if op else "")
        h = _sat(cs.get("local_time"))
        put("jutro", (h < JUTRO_SAT) if h is not None else None, f"{h} h" if h is not None else "")
        # Nose: razlika vlastite procjene i cijene za OVU stranu (u snapshotu je za modelov pick)
        # (`nose_diff_pp` = isti broj iz plosnatog retka baze, vidi `rec_iz_retka`)
        nz = cs.get("nose")
        d = None
        if isinstance(nz, dict) and not nz.get("error"):
            d = _num((nz.get("vs_market") or {}).get("diff_pp"))
        if d is None:
            d = _num(cs.get("nose_diff_pp"))
        if d is not None and strana != model_pick:
            d = -d
        put("nose_plus", (d >= NOSE_RAZLIKA) if d is not None else None, f"{d:+.1f}pp" if d is not None else "")
        put("nose_minus", (d <= -NOSE_RAZLIKA) if d is not None else None)
        return {"aktivni": aktivni, "nedostaje": nedostaje, "detalji": det}
    except Exception as e:  # noqa: BLE001 — nos nikad ne smije srušiti run
        return {"error": str(e)[:120]}


# ------------------------------------------------------------------ učenje težina
def rec_iz_retka(row: dict) -> dict:
    """Plosnat redak iz `supabase_client.get_rows_for_nos_odluka` -> zapis za `znakovi` (učenje)."""
    rec = _np.rec_from_flat(row)
    cs = rec["cs"]
    cs["p1_scouting_confidence"], cs["p2_scouting_confidence"] = row.get("sc1"), row.get("sc2")
    cs["local_time"] = row.get("lt")
    cs["nose_diff_pp"] = row.get("nd")
    for side, k in (("p1", "inj3_1"), ("p2", "inj3_2")):
        if row.get(k) is not None:
            g = dict(cs.get(f"{side}_gnews") or {})
            g["injury_n3"] = row.get(k)
            cs[f"{side}_gnews"] = g
    return rec


def primjeri_iz_redaka(rows: list) -> list:
    """Riješeni pickovi s obje kvote (bez analiza s tuđim ELO-om) -> primjeri za `nauci`."""
    out = []
    for r in rows or []:
        if str(r.get("elos") or "").lower() == "true" or r.get("prediction_correct") is None:
            continue
        pick, p1 = r.get("predicted_winner"), r.get("player1")
        o_p, o_o = ((r.get("bookmaker_odds_p1"), r.get("bookmaker_odds_p2")) if pick == p1
                    else (r.get("bookmaker_odds_p2"), r.get("bookmaker_odds_p1")))
        p = _np.devig(o_p, o_o)
        if p is None:
            continue
        z = znakovi(rec_iz_retka(r))
        if z.get("error"):
            continue
        out.append({"aktivni": z["aktivni"], "nedostaje": z["nedostaje"],
                    "win": 1.0 if r["prediction_correct"] else 0.0, "p": p,
                    "date": str(r.get("match_date") or "")[:10]})
    return out


def nauci(primjeri: list, danas: str = None) -> dict:
    """primjeri: [{"aktivni": [...], "nedostaje": [...], "win": 0/1, "p": devig cijena strane,
    "date": "GGGG-MM-DD"}] -> težine po znaku (pp) za `config/nos_tezine.json`."""
    danas = danas or _dt.date.today().isoformat()
    od = (_dt.date.fromisoformat(danas) - _dt.timedelta(days=PROZOR_DANA)).isoformat()
    rows = [r for r in primjeri if od <= str(r.get("date") or "")[:10] < danas and r.get("p") is not None]
    out = {"version": VERSION, "napravljeno": _dt.datetime.now().strftime("%d.%m.%Y %H:%M"),
           "prozor": {"od": od, "do": danas, "dana": PROZOR_DANA}, "n_pickova": len(rows),
           "parametri": {"K": K_SKUPLJANJE, "min_n": MIN_N, "strop_znak": STROP_ZNAK,
                         "strop_ukupno": STROP_UKUPNO},
           "znakovi": {}}
    if not rows:
        return out
    for r in rows:
        r["_res"] = r["win"] - r["p"]
        r["_band"] = _np._band(r["p"])
    # 1) OPIS: učinak svakog znaka ZASEBNO (u istom pojasu cijene; cjenovni naspram ostalih) — za
    #    čitanje tablice, NE za odluku (znakovi se preklapaju: jak ELO, kratka kvota, scouting i noć
    #    su često isti mečevi zvijezda, pa bi zbroj zasebnih učinaka isto brojao više puta).
    n_by = {}
    for sid, info in INFO.items():
        elig = [r for r in rows if sid not in (r.get("nedostaje") or [])]
        fl = [r for r in elig if sid in (r.get("aktivni") or [])]
        rest = [r for r in elig if sid not in (r.get("aktivni") or [])]
        n = n_by[sid] = len(fl)
        eff = None
        if n and rest:
            if info["cjenovni"]:
                eff = 100 * (sum(r["_res"] for r in fl) / n - sum(r["_res"] for r in rest) / len(rest))
            else:
                by_band = {}
                for r in rest:
                    by_band.setdefault(r["_band"], []).append(r["_res"])
                d = [r["_res"] - sum(by_band[r["_band"]]) / len(by_band[r["_band"]])
                     for r in fl if by_band.get(r["_band"])]
                eff = 100 * sum(d) / len(d) if d else None
        out["znakovi"][sid] = {"n": n, "ucinak_pp": None if eff is None else round(eff, 2),
                               "tezina_pp": 0.0, "vrsta": info["vrsta"], "oznaka": info["oznaka"]}
    # 2) ODLUKA: svi znakovi ZAJEDNO (ridge: ostatak pobjeda − cijena ~ znakovi + slobodni član), kazna
    #    λ = K po znaku (za neovisan znak to je isto skupljanje n / (n + K)); predznak iz definicije
    #    znaka (krivi predznak -> znak ispada i model se ponovno računa), pa strop po znaku.
    tezine = _ridge(rows, [s for s in INFO if n_by.get(s, 0) >= MIN_N])
    out["slobodni_clan_pp"] = round(tezine.pop("_slobodni", 0.0), 2)
    for sid, w in tezine.items():
        out["znakovi"][sid]["tezina_pp"] = round(max(-STROP_ZNAK, min(STROP_ZNAK, w)), 2)
    return out


def _ridge(rows: list, ids: list) -> dict:
    """Ridge sa znakovima `ids` i nekažnjenim slobodnim članom; vraća težine u pp (+ '_slobodni')."""
    import numpy as np
    ids = list(ids)
    y = np.array([r["_res"] for r in rows], float)
    while True:
        X = np.ones((len(rows), len(ids) + 1))
        for j, sid in enumerate(ids, start=1):
            X[:, j] = [1.0 if sid in (r.get("aktivni") or []) else 0.0 for r in rows]
        D = np.eye(len(ids) + 1) * K_SKUPLJANJE
        D[0, 0] = 0.0
        beta = np.linalg.solve(X.T @ X + D, X.T @ y)
        krivi = [sid for j, sid in enumerate(ids, start=1)
                 if (INFO[sid]["vrsta"] == "mina" and beta[j] > 0)
                 or (INFO[sid]["vrsta"] == "prilika" and beta[j] < 0)]
        if not krivi:
            break
        ids = [s for s in ids if s not in krivi]
    out = {sid: 100 * float(beta[j]) for j, sid in enumerate(ids, start=1)}
    out["_slobodni"] = 100 * float(beta[0])
    return out


def ucitaj_tezine(path: str = None) -> dict:
    """Težine iz `NOS_TEZINE_PATH` (GitHub: naučene to jutro) ili `config/nos_tezine.json`; {} ako nema."""
    for p in (path, os.environ.get("NOS_TEZINE_PATH"), TEZINE_PATH):
        if p and os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as fh:
                    t = json.load(fh)
                if isinstance(t, dict) and t.get("version") == VERSION:
                    t["_izvor"] = os.path.basename(p)
                    return t
            except (OSError, ValueError):
                continue
    return {}


def ocjena(aktivni: list, tezine: dict, bez_cjenovnih: bool = False) -> tuple:
    """(zbroj težina upaljenih znakova sa stropom STROP_UKUPNO, [(znak, težina)])."""
    tz = (tezine or {}).get("znakovi") or {}
    dop = []
    for sid in aktivni or []:
        if bez_cjenovnih and INFO.get(sid, {}).get("cjenovni"):
            continue
        w = _num((tz.get(sid) or {}).get("tezina_pp")) or 0.0
        if w:
            dop.append((sid, round(w, 2)))
    s = sum(w for _, w in dop)
    return max(-STROP_UKUPNO, min(STROP_UKUPNO, round(s, 2))), dop


# ------------------------------------------------------------------ odluka u dnevnom runu
def _autsajder(pred: dict, rec: dict, tezine: dict, conf_model: float):
    """Kandidat za nos-autsajdera ili (None, razlog)."""
    m = pred.get("match") or {}
    pick, p1, p2 = pred.get("pick") or "", m.get("player1") or "", m.get("player2") or ""
    opp = p2 if pick == p1 else p1
    o_pick, o_opp = ((m.get("odds_p1"), m.get("odds_p2")) if pick == p1 else (m.get("odds_p2"), m.get("odds_p1")))
    o_opp_n = _num(o_opp)
    nz = (pred.get("context_snapshot") or {}).get("nose") or {}
    if not isinstance(nz, dict) or nz.get("error"):
        return None, "nema Nosea"
    vm = nz.get("vs_market") or {}
    if not vm.get("opp_value"):
        return None, "Nose ne vidi vrijednost na protivniku"
    p_mkt_pick = _num(vm.get("p_market"))
    p_own_opp = _num((nz.get("upset_value") or {}).get("p_own_opp"))
    if p_mkt_pick is None or p_own_opp is None or not o_opp_n:
        return None, "nema procjene ili kvote"
    prednost = 100 * (p_own_opp - (1 - p_mkt_pick))
    if prednost < AUTS_MIN_PREDNOST_PP:
        return None, f"prednost {prednost:.1f}pp < {AUTS_MIN_PREDNOST_PP}"
    if not (AUTS_KVOTA[0] <= o_opp_n <= AUTS_KVOTA[1]):
        return None, f"kvota {o_opp_n:.2f} izvan {AUTS_KVOTA}"
    if conf_model > AUTS_MAX_MODEL_CONF:
        return None, f"model uvjeren ({conf_model:.0f} > {AUTS_MAX_MODEL_CONF:.0f})"
    zo = znakovi(rec, za_igraca=opp)
    if zo.get("error"):
        return None, "znakovi protivnika: " + zo["error"]
    s_opp, dop = ocjena(zo["aktivni"], tezine, bez_cjenovnih=True)
    if s_opp < AUTS_MIN_OCJENA:
        return None, f"znakovi protivnika {s_opp:+.1f} < {AUTS_MIN_OCJENA:+.1f}"
    flip = {k: v for k, v in pred.items()
            if k not in ("confidence", "fair_odds", "pick", "_nos_model", "measured_penalties")}
    flip.update({
        "pick": opp,
        "confidence": round(100 * p_own_opp, 1),
        "fair_odds": round(1 / p_own_opp, 3),
        "value": True,
        "risk_level": "visok",
        "risk_notes": (f"NOS-AUTSAJDER (nos-odluka-v1): Nose daje {opp} {100 * p_own_opp:.0f}%, cijena "
                       f"{100 * (1 - p_mkt_pick):.0f}% (+{prednost:.1f}pp); model je birao {pick} uz {conf_model:.0f}%."),
        "key_factors": [f"NOS-AUTSAJDER: Nose vidi vrijednost na {opp} (+{prednost:.1f}pp naspram cijene)"]
                       + [f"znak {INFO[s]['oznaka']} {w:+.1f}" for s, w in dop],
        "nos_autsajder": True,
        "nos_prednost_pp": round(prednost, 2),
        "nos_model_pick": pick,
    })
    return flip, {"igrac": opp, "kvota": o_opp_n, "p_nose": round(p_own_opp, 4),
                  "p_cijena": round(1 - p_mkt_pick, 4), "prednost_pp": round(prednost, 2),
                  "znakovi": zo["aktivni"], "ocjena": s_opp}


def primijeni(predictions: list, tezine: dict) -> list:
    """Nos odlučuje za svaku valjanu predikciju: pouzdanost ZA TIKET = model + ocjena znakova.

    Mijenja pred["confidence"] i pred["fair_odds"] (to čita `ticket_builder`), a modelove vrijednosti
    čuva u pred["_nos_model"]; `vrati_model()` ih vraća prije upisa u bazu. Upisuje
    context_snapshot["nos_odluka"]. Vraća listu kandidata za nos-autsajdera (nove predikcije)."""
    flips = []
    for pred in predictions:
        cs = pred.get("context_snapshot")
        if pred.get("skip_reason") or not isinstance(cs, dict) or not pred.get("pick"):
            continue
        try:
            conf_m = float(pred.get("confidence") or 0)
            rec = _np.rec_from_pred(pred)
            z = znakovi(rec)
            if z.get("error"):
                cs["nos_odluka"] = {"version": VERSION, "error": z["error"]}
                continue
            s, dop = ocjena(z["aktivni"], tezine)
            conf_n = round(max(0.0, conf_m + s), 1)
            pred["_nos_model"] = {"confidence": pred.get("confidence"), "fair_odds": pred.get("fair_odds")}
            pred["confidence"] = conf_n
            if conf_n > 0:
                pred["fair_odds"] = round(100.0 / conf_n, 3)
            # bez naučenih težina nos ŠUTI u potpunosti — ni pouzdanost (ocjena 0) ni autsajder
            flip, info = _autsajder(pred, rec, tezine, conf_m) if tezine else (None, "nema težina — nos šuti")
            cs["nos_odluka"] = {
                "version": VERSION, "tezine": (tezine or {}).get("napravljeno"),
                "tezine_izvor": (tezine or {}).get("_izvor"),
                "conf_model": conf_m, "ocjena": s, "conf_tiket": conf_n,
                "odluka": "POTVRDI" if s >= 1 else ("OSLABI" if s <= -1 else "NEUTRALNO"),
                "znakovi": z["aktivni"], "doprinosi": dop, "nedostaje": z["nedostaje"],
                "autsajder": info if flip else {"kandidat": False, "razlog": info},
            }
            if flip:
                flips.append(flip)
        except Exception as e:  # noqa: BLE001
            cs["nos_odluka"] = {"version": VERSION, "error": str(e)[:120]}
    return flips


def vrati_model(predictions: list) -> None:
    """Vrati modelovu pouzdanost i fair_odds (za upis u `analyzed_matches`)."""
    for pred in predictions:
        orig = pred.pop("_nos_model", None)
        if orig:
            pred["confidence"] = orig["confidence"]
            pred["fair_odds"] = orig["fair_odds"]


def oznaci_tiket(predictions: list, ticket: dict, legacy_kljucevi: set = None) -> None:
    """Upiše u nos_odluka je li pick (ili nos-autsajder) na tiketu i bi li bio na starom tiketu."""
    def kljuc(p1, p2):
        return frozenset([str(p1 or "").lower(), str(p2 or "").lower()])
    pravi = (ticket or {}).get("status") != "analysis_only"   # popis "samo analiza" nije tiket
    legs = {kljuc(l.get("player1"), l.get("player2")): l.get("pick")
            for l in ((ticket or {}).get("matches") or [] if pravi else [])}
    for pred in predictions:
        cs = pred.get("context_snapshot")
        if not isinstance(cs, dict) or not isinstance(cs.get("nos_odluka"), dict):
            continue
        m = pred.get("match") or {}
        k = kljuc(m.get("player1"), m.get("player2"))
        cs["nos_odluka"]["na_tiketu"] = legs.get(k)
        if legacy_kljucevi is not None:
            cs["nos_odluka"]["bez_nosa_na_tiketu"] = k in legacy_kljucevi
