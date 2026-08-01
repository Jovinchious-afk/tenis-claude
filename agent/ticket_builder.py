"""
Ticket Builder: od liste predikcija gradi optimalni tiket.
Kriteriji: 4-6 mečeva, kombinirana kvota 6.0-40 (jedinstveno za sve podloge, 26.07.2026).
Claude Sonnet piše finalni write-up.
"""
import os
import json
import itertools
import anthropic
from typing import Optional
from dotenv import load_dotenv
from config.model_config import TICKET_CONFIG, CLAUDE_MODELS, TOURNAMENT_LEVELS, DAILY_MATCH_LIMITS
from utils.helpers import combined_odds, potential_win, today_zagreb, tomorrow_zagreb

load_dotenv()

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client


# Razine turnira koje se NE stavljaju na tiket (samo analiziramo radi modela)
_NON_TICKET_LEVELS = {"ATP Challenger", "ATP Qualifying"}


def _is_main_tour(p) -> bool:
    """Challengers, ITF, Qualifying se nikad ne stavljaju na tiket niti u analysis-only."""
    m = p.get("match", {})
    level = m.get("level", "")
    low = level.lower()
    if any(kw in low for kw in ["challenger", "qualifying", "itf", "future"]):
        return False
    # Screenshot override (2026-07-16): ako je korisnik ručno unio kvotu za ovaj meč,
    # to je potvrda glavnog ždrijeba (kvalifikacije nikad ne screenshota) → propusti
    # ga bez obzira na API-jev round-tag. Namjerno IZA level-provjere: screenshot ne
    # smije progurati Challenger/ITF (to je policy isključenje, ne API greška),
    # nego samo zaobići round-based qualifying guard ispod. _infer_rounds obično već
    # ispravi Q→prava runda uzvodno; ovo je pojas-i-tregeri za rubne slučajeve.
    if m.get("has_screenshot_odds"):
        return True
    # Qualifying guard (clay revizija 2026-07-11): ATP 250/500 nemaju R128 u main drawu —
    # "R128" na tim razinama su kvalifikacije koje API krivo označi kao main draw.
    # 11.07. su tako 4 kvalifikacijska meča (igrači ranga 150-300) ušla na tiket i 2/4 pala.
    # Fix 2026-07-16: kvalifikacije su "Q1"/"Q2" — raniji startswith("Q") hvatao je i "QF"
    # (četvrtfinale!), pa je QF dan na ATP 250 (Båstad/Gstaad/Umag, četvrtak 16.07.)
    # izbacio SVE mečeve i s tiketa i iz analysis-only prikaza → prazan email.
    rnd = str(m.get("round", "")).upper().strip()
    is_quali_round = rnd.startswith("Q") and rnd != "QF"
    if ("250" in level or "500" in level) and (rnd == "R128" or is_quali_round):
        return False
    return True


def _has_odds(p) -> bool:
    """Meč mora imati stvarnu kvotu (Odds API ili screenshot) — bez nje se nikad ne stavlja na tiket."""
    return bool(p.get("match", {}).get("odds_available"))


def _is_grass(p) -> bool:
    """True ako se par igra na travi."""
    return "grass" in (p.get("match", {}).get("surface", "") or "").lower()


def _is_clay(p) -> bool:
    """True ako se par igra na zemlji."""
    return "clay" in (p.get("match", {}).get("surface", "") or "").lower()


def _is_hard(p) -> bool:
    """True ako se par igra na hardu — uključuje 'Hard' i 'Indoor Hard' (isti model)."""
    return "hard" in (p.get("match", {}).get("surface", "") or "").lower()


def _needs_conf_floor(p) -> bool:
    """Podloge s confidence floorom u selekciji: grass (22.06.) + clay (11.07.) + hard (18.07.).
    Clay dokaz: pickovi ispod 63% nisu ni ulazili u clay korpus, ali zona 66-70% pobjeđivala
    je 38% — floor + poštena kalibracija zajedno tjeraju coinflipove ispod 63.
    Hard (revizija 18.07., prije prvog hard picka): ista disciplina od 1. dana — deklarirani
    conf 63-70 na grass+clay korpusu (n=187) vraćao je 55-60%, optimizam ~+7pp."""
    return _is_grass(p) or _is_clay(p) or _is_hard(p)


# ── Hard selekcijska pravila (v1 18.07., UBLAŽENO 26.07.2026 uz korisnikovo odobrenje) ──
# v1 je 1.43-1.60 potpuno ZABRANIO a 1.61-1.90 ograničio na max 1 — izvedeno iz korpusa
# PRIJE clay revizije 11.07. (1.43-1.60: 53% WR, ROI -19.2%; 1.61-1.90: 48% WR, -16.5%).
# Ponovno mjerenje 26.07. na post-revizijskom clayu pokazalo je da je zona bila problem
# STAROG modela, ne kvote: s v13+ pravilima (conf floor, hot-hand, Fery veto) ista zona
# daje 1.43-1.60: 10W-4L +7.8% i 1.61-1.90: 9W-4L +21.9% (n=14/13, malen uzorak!).
# Zato zabrana ukinuta → jedna OPREZNA zona 1.43-1.90, max 1 hard pick po tiketu
# (isti oblik koji je na clayu isporučio 72% WR). Prompt pravilo 3 (double-confirmation
# za marginalne favorite) ostaje kao kvalitativna kočnica. Revalidirati s prvih ~30
# stvarnih hard pickova (okidač u run_daily).
# GS je podbacivao vs ATP 250 na obje podloge → na hard GS-u (US Open) prag je 65%.
_HARD_CAUTION_ZONE = (1.43, 1.90)   # uključivo — max 1 po tiketu (vidi _find_best_combination)
_HARD_CAUTION_ZONE_MAX = 1
_HARD_GS_MIN_CONF = 65.0

# Grass dead zone (dodano 2026-07-18, kasnije istog dana): ista 1.43-1.60 mrtva zona je
# NAJJAČE dokumentirana baš na grassu (n=33, 52% WR, ROI -20.3% dedupe) — jača evidencija
# nego što je uopće postojala za hard kad je dobio potpunu zabranu. Grass dosad nije imao
# NIKAKVU determinističku zaštitu (samo opći conf floor 63%) unatoč najviše dokaza od sve
# tri podloge — ista zabrana koju već ima hard, prenesena na dosljednost.
_GRASS_DEAD_ZONE = (1.43, 1.60)     # uključivo — nikad na tiket


# NAPOMENA: per-pick zabrana hard mrtve zone (_hard_bands_ok) UKINUTA 26.07.2026 —
# vidi komentar uz _HARD_CAUTION_ZONE. Ograničenje živi na razini KOMBINACIJE
# (_hard_caution_zone_count u _find_best_combination), ne pojedinačnog picka.
# Grass zabrana (_grass_bands_ok) namjerno OSTAJE — grass evidencija (n=33, -20.3%)
# nije ponovno mjerena jer je grass sezona završila; revalidirati prije iduće trave.


def _grass_bands_ok(p) -> bool:
    """Grass pick s kvotom u mrtvoj zoni 1.43-1.60 nikad ne ulazi na tiket (isto pravilo
    kao hard, ali s jačom evidencijom — grass ima najviše dokumentiranih pickova u zoni)."""
    if not _is_grass(p):
        return True
    o = _pick_odds(p)
    return not (_GRASS_DEAD_ZONE[0] <= o <= _GRASS_DEAD_ZONE[1])


def _hard_gs_conf_ok(p) -> bool:
    """Na hard Grand Slamu (US Open, BO5) pick treba >=65% — GS je sezonski podbacivao."""
    if not _is_hard(p):
        return True
    level = p.get("match", {}).get("level", "")
    if "Grand Slam" not in level:
        return True
    return (p.get("confidence") or 0) >= _HARD_GS_MIN_CONF


# Clay GS prag (dodano 2026-07-18, kasnije istog dana): dokaz da GS podbacuje vs ATP 250
# je zapravo NAĐEN na clayu (Roland Garros 54% vs ne-GS 67%, revizija 2026-07-11), ne na
# grassu (Wimbledon 61% == ne-GS 61%, identično — nema efekta). Hard je ovaj prag dobio
# preventivno bez ikakvih hard podataka; ovdje se primjenjuje tamo gdje dokaz stvarno stoji.
_CLAY_GS_MIN_CONF = 65.0


def _clay_gs_conf_ok(p) -> bool:
    """Na clay Grand Slamu (Roland Garros, BO5) pick treba >=65% — GS je dokazano podbacivao."""
    if not _is_clay(p):
        return True
    level = p.get("match", {}).get("level", "")
    if "Grand Slam" not in level:
        return True
    return (p.get("confidence") or 0) >= _CLAY_GS_MIN_CONF


def _opponent_beat_us(p) -> bool:
    """Fery pravilo (deterministički veto, sve podloge): protivnik picka je igrač koji je
    NAMA već srušio pick 2+ PUTA u istom turniru zadnjih 14 dana (zastavice
    p1_beat_us/p2_beat_us postavlja run_daily; prag 2 poraza korekcija je istog dana —
    1 poraz je normalna varijanca, 2 poraza od istog igrača je obrazac). Fery nas je
    srušio 6× u tri tjedna jer je model svaki dan iznova fade-ao istog vrućeg igrača —
    pravila su rizik registrirala u risk_notes, ali ga nisu PROVODILA. Sada je veto."""
    m = p.get("match", {})
    pick = (p.get("pick") or "").lower()
    if not pick:
        return False
    p1 = (m.get("player1") or "").lower()
    # protivnik = igrač kojeg NISMO pickali
    if pick in p1 or p1 in pick:
        return bool(m.get("p2_beat_us"))
    return bool(m.get("p1_beat_us"))


# NAPOMENA: deterministički hot-hand veto po BROJU pobjeda u turniru je UKINUT na
# korisnikov zahtjev 2026-07-18. Razlog (korisnik ispravno uočio): do četvrtfinala SVI
# igrači imaju 2+ pobjede (R32→R16→QF), do finala 4 — prag "2+ pobjede" bi okinuo veto na
# svaki meč završnice i onemogućio tiket. Broj pobjeda mjeri krivu stvar (napredovanje ≠
# iznenađenje). Hot-hand oprez sada živi CILJANO u promptu (HARD RULES v1 pravilo 1: samo
# pravi UPSET nalet niže rangiranog igrača), a deterministički ostaje samo Fery-veto
# (_opponent_beat_us — igrač koji nas je STVARNO srušio, ne puko brojanje pobjeda).


def _both_declining_ok(p) -> bool:
    """BOTH-PLAYERS-DECLINING CAP otvrdnuto u kod (18.07., korisnikova preporuka C).
    Pravilo je postojalo samo u promptu (grass rule 7, clay rule 3: 'cap confidence at 60%
    regardless of ELO, surface record, or other factors') — deterministički backstop je
    stroži i pouzdaniji: ako su OBA igrača izgubila SVA 3 zadnja meča (0/3 — vidi
    run_daily._is_declining za prag-korekciju 20.07.2026), pick se isključuje iz selekcije
    u potpunosti (60% < 63% tiketni prag, pa svejedno ne bi prošao — ovo samo jamči da ne
    prođe zbog eventualno preoptimistične procjene). PRAG NIJE isti kao u promptu — kod
    traži strogo 0/3 (dokazan slučaj, Butvilas-Huesler), prompt i dalje savjetuje oprez i
    kod 1/3-vs-1/3 (Claudeova vlastita procjena, ne tvrdi izbačaj). Univerzalno, sve podloge
    — logika je surface-neutralna (dva neizvjesna igrača = neizvjestan meč, bez obzira na
    podlogu), i hard pravila to već eksplicitno traže ('surface-independent, MUST be enforced
    from day one'), samo tekst pravila dosad nije bio napisan za hard."""
    m = p.get("match", {})
    return not (m.get("p1_declining") and m.get("p2_declining"))


def _clay_fatigue_ok(p) -> bool:
    """Clay REST & FATIGUE DIFFERENTIAL (rule 4) otvrdnuto u kod (18.07., korisnikova
    preporuka C). CLAY-ONLY — obrazloženje pravila je izričito vezano uz clay ('rallies are
    the longest in tennis'), nema dokumentiranog dokaza za grass/hard, pa se NE prenosi
    (za razliku od both-declining pravila gore, koje je surface-neutralno). Ako je NAŠ pick
    odigrao 2+ meča zadnjih 7 dana I ima 2+ manje dana odmora od protivnika
    (p1/p2_fatigue_disadvantage, postavlja run_daily): efektivni confidence pada 4pp (6pp u
    Bo5) — ako tako umanjen confidence padne ispod 63% tiketnog praga, pick se isključuje."""
    if not _is_clay(p):
        return True
    m = p.get("match", {})
    pick = (p.get("pick") or "").lower()
    if not pick:
        return True
    p1 = (m.get("player1") or "").lower()
    is_p1_pick = pick in p1 or p1 in pick
    fatigued = m.get("p1_fatigue_disadvantage") if is_p1_pick else m.get("p2_fatigue_disadvantage")
    if not fatigued:
        return True
    conf = p.get("confidence") or 0
    penalty = 6.0 if "Grand Slam" in (m.get("level") or "") else 4.0
    return (conf - penalty) >= 63.0


def _selection_ok(p) -> bool:
    """Zajednički mandatory filter za sve kandidatske liste tiketa."""
    return (_is_main_tour(p) and _has_odds(p)
            and _grass_bands_ok(p)
            and _hard_gs_conf_ok(p) and _clay_gs_conf_ok(p)
            and not _opponent_beat_us(p)
            and _both_declining_ok(p) and _clay_fatigue_ok(p))


def build_ticket(predictions: list, weights: dict, min_odds_override: float = None) -> Optional[dict]:
    """
    Ulaz: lista predikcija iz predictor.analyze_match()
    Izlaz: optimalni tiket dict s matches, odds, summary

    Strategija (quality-first):
    - Primarni kriterij: statistička kvaliteta (confidence + value)
    - Sekundarni: combined odds mora biti 6-20 (nije cilj, samo filter)
    - Challengeri se ne stavljaju na tiket
    - Kaskadni fallback — uvijek generiraj tiket, nikad ne odustaj
    """
    cfg = dict(TICKET_CONFIG)
    if min_odds_override is not None:
        cfg["min_combined_odds"] = min_odds_override

    # ── Grass + clay selekcijska disciplina + value-override ────────────────
    # Osnovno: grass/clay pick prolazi samo ako je modelov VLASTITI confidence >= 63%.
    # Grass: filtrira coinflipove (n=73, lipanj 2026: grass <63% pobjeđivali ~40%).
    # Clay (revizija 2026-07-11): prošireno s grassa — ista strukturna bolest, gora
    # kalibracija (66-70% zona pobjeđivala 38%, prosjek conf 69% vs stvarnih 53%).
    #
    # IZNIMKA (value-override, dodano 2026-07-05): naša filozofija je VALUE, ne lov na
    # niske kvote. Standout value oklada (model se JAKO ne slaže s tržištem) smije proći
    # i ispod floora: confidence >= 58% I edge >= 12pp, ali najviše 2 takve (top po edge-u).
    # Value = usporedba s tržištem, pa je edge legitimna upotreba kvote — različito od
    # "biranja niske kvote". Ovo omogućuje povremeni opravdani 15-25 listić.
    # Od 11.07. edge se računa iz fair_odds = 100/confidence (predictor normalizacija),
    # pa je override konzistentan: prolaze samo kvote 2.0+ uz pošten confidence 58-62.
    conf_floor = cfg["min_confidence"]            # 63
    VALUE_MIN_CONF = 58.0
    VALUE_MIN_EDGE = 12.0
    VALUE_MAX_PICKS = 2

    floor_below = [p for p in predictions
                   if _needs_conf_floor(p) and (p.get("confidence") or 0) < conf_floor]
    value_candidates = [p for p in floor_below
                        if (p.get("confidence") or 0) >= VALUE_MIN_CONF
                        and _pick_edge(p) >= VALUE_MIN_EDGE
                        and _selection_ok(p)]
    value_candidates.sort(key=lambda p: _pick_edge(p), reverse=True)
    value_keep = {id(p) for p in value_candidates[:VALUE_MAX_PICKS]}

    n_before = len(predictions)
    predictions = [p for p in predictions
                   if not _needs_conf_floor(p)
                   or (p.get("confidence") or 0) >= conf_floor
                   or id(p) in value_keep]
    n_dropped = n_before - len(predictions)
    if n_dropped:
        print(f"  Grass/clay disciplina: izbačeno {n_dropped} pickova ispod {conf_floor}% "
              f"(modelov confidence, ne kvota).")
    for p in value_candidates[:VALUE_MAX_PICKS]:
        surf = "clay" if _is_clay(p) else "grass"
        print(f"  Value-override ({surf}): {p.get('pick','')} conf={p.get('confidence',0):.0f}% "
              f"edge={_pick_edge(p):.1f}pp — zadržan ispod floora zbog izraženog value-a.")

    def _eligible(p, conf_threshold, allow_challengers=False):
        level = p.get("match", {}).get("level", "")
        if not allow_challengers and level in _NON_TICKET_LEVELS:
            return False
        return not p.get("skip_reason") and (p.get("confidence") or 0) >= conf_threshold

    # Kaskadni fallback: 63% → 58% → 55% — Challengeri nikad
    thresholds = [
        cfg["min_confidence"],         # faza 1: 63%
        cfg["fallback_confidence"],    # faza 2: 58%
        cfg["last_resort_confidence"], # faza 3: 55%
    ]

    candidates = []
    for conf_threshold in thresholds:
        candidates = [p for p in predictions
                      if not p.get("skip_reason")
                      and (p.get("confidence") or 0) >= conf_threshold
                      and _selection_ok(p)]
        if len(candidates) >= cfg["min_matches"]:
            if conf_threshold < cfg["min_confidence"]:
                print(f"Fallback: using conf >= {conf_threshold}% (no Challengers)")
            break

    # Zadnji resort: svi main-tour bez obzira na conf, ali NIKAD Challenger
    if len(candidates) < cfg["min_matches"]:
        candidates = [p for p in predictions
                      if not p.get("skip_reason") and _selection_ok(p)]
        candidates.sort(key=lambda p: (p.get("confidence") or 0), reverse=True)
        candidates = candidates[:cfg["max_matches"]]
        print(f"Last resort: top {len(candidates)} main-tour picks by confidence")

    # Edge override: picks with confidence 55-62% but edge >= 8pp enter the pool
    # These are the "intuition/underdog" picks the market is undervaluing
    edge_overrides = []
    for p in predictions:
        if p.get("skip_reason"):
            continue
        conf = p.get("confidence") or 0
        if 55 <= conf < 63:
            fair = p.get("fair_odds") or 0
            bookmaker = _pick_odds(p)
            if fair > 0 and bookmaker > 0:
                edge = (1.0 / fair - 1.0 / bookmaker) * 100
                if edge >= 8.0:
                    if _selection_ok(p):
                        edge_overrides.append(p)
                        print(f"  Edge override: {p.get('pick','')} conf={conf}% edge={edge:.1f}pp")

    # Merge: add overrides not already in candidates
    candidate_ids = {id(p) for p in candidates}
    for p in edge_overrides:
        if id(p) not in candidate_ids:
            candidates.append(p)

    # Sort by score potential: value pick > high confidence > tournament level
    candidates.sort(key=lambda p: (
        _is_value_pick(p),
        (p.get("confidence") or 0),
        TOURNAMENT_LEVELS.get(p.get("match", {}).get("level", "ATP 250"), 45)
    ), reverse=True)

    candidates = _apply_daily_limits(candidates)
    cfg = _apply_surface_overrides(cfg, candidates)
    best_combo = _find_best_combination(candidates, cfg)

    if not best_combo:
        # Kaskadni fallback za odds: smanji min_conf i traži par s višom kvotom
        # koji će gurnuti kombiniranu kvotu u raspon 6-20
        print("Standardni raspon nije dostignut — tražim riskantnije pickove s višom kvotom.")
        all_valid = [p for p in predictions
                     if not p.get("skip_reason") and _selection_ok(p)]
        all_valid.sort(key=lambda p: _pick_odds(p), reverse=True)  # najviše kvote prvo
        combined_pool = candidates + [p for p in all_valid if p not in candidates]
        best_combo = _find_best_combination(combined_pool, cfg)
        if best_combo:
            print("Tiket složen s riskantijim pickovima — prihvaćamo veći rizik.")

    if not best_combo:
        print("Nema dovoljno mečeva sa stvarnim kvotama za valjan tiket.")
        return None

    # Final holistic review by Claude Sonnet before ticket is confirmed
    rejected_candidates = [p for p in candidates if p not in best_combo]
    best_combo = _review_ticket(best_combo, rejected_candidates, cfg)

    total_odds = combined_odds([_pick_odds(p) for p in best_combo])
    pot_win = potential_win(cfg["stake"], total_odds)

    ticket_matches = []
    for pred in best_combo:
        m = pred.get("match", {})
        pick = pred.get("pick", "")
        ticket_matches.append({
            "player1": m.get("player1", ""),
            "player2": m.get("player2", ""),
            "pick": pick,
            "odds": _pick_odds(pred),
            "match_date": m.get("date", ""),
            "match_time": m.get("time", ""),
            "tournament": m.get("tournament", ""),
            "tournament_level": m.get("level", ""),
            "surface": m.get("surface", ""),
            "round": m.get("round", ""),
            "confidence": pred.get("confidence", 0),
            "fair_odds": pred.get("fair_odds"),
            "value_bet": pred.get("value", False),
            "risk_level": pred.get("risk_level", "srednji"),
            "risk_notes": pred.get("risk_notes", ""),
            "handicap_option": pred.get("handicap_option"),
            "key_factors": pred.get("key_factors", []),
            "external_match_id": m.get("external_id", ""),
            # API player ID-evi (A1, 26.07.2026): evening update ih koristi za razrješavanje
            # rezultata i kad turnir nestane iz fixtures feeda (slučaj Bublik-Halys 25.07.).
            "player1_id": str(m.get("player1_id") or "") or None,
            "player2_id": str(m.get("player2_id") or "") or None,
            "result": "pending",
        })

    summary = _generate_ticket_summary(ticket_matches, total_odds, pot_win, weights)

    return {
        "total_odds": round(total_odds, 4),
        "potential_win": pot_win,
        "stake": cfg["stake"],
        "matches_count": len(ticket_matches),
        "ticket_summary": summary,
        "reviewer_decision": _last_reviewer_notes.get("decision", ""),
        "reviewer_changes": _last_reviewer_notes.get("changes", ""),
        "reviewer_warning": _last_reviewer_notes.get("warning", ""),
        "status": "pending",
        "matches": ticket_matches,
    }


def _apply_surface_overrides(cfg: dict, candidates: list) -> dict:
    """Primijeni surface-specifične ticket limite kad su SVI kandidati na istoj podlozi.
    OD 26.07.2026 je SURFACE_TICKET_OVERRIDES prazan (sve podloge dijele istu strukturu:
    4-6 parova, kombinirana 6.0-40), pa ova funkcija efektivno vraća cfg nepromijenjen.
    Zadržana je namjerno kao mehanizam za slučaj da se surface-specifični limiti vrate."""
    from config.model_config import SURFACE_TICKET_OVERRIDES
    if not candidates:
        return cfg
    for surface, overrides in SURFACE_TICKET_OVERRIDES.items():
        if all(surface in (p.get("match", {}).get("surface", "") or "").lower()
               for p in candidates):
            cfg = {**cfg, **overrides}
            print(f"  Surface override ({surface}): kombinirana kvota "
                  f"{cfg['min_combined_odds']}-{cfg['max_combined_odds']}, "
                  f"max {cfg['max_matches']} parova.")
            break
    return cfg


# Mrtva zona kvota na clayu: 1.50-1.90 pobjeđivala 3/11 (27%) u clay korpusu
# (na grassu ista zona 20%). Marginalni favoriti bez informacijskog edga.
# Gornja granica edga koji se boduje. Razdvojena po cijeni picka 02.08.2026 — vidi
# obrazloženje u _score_combo. Favoriti zadržavaju stari, strogi prag.
_EDGE_CAP = 20.0            # pickovi ispod _UNDERDOG_MIN_ODDS (favoriti)
_UNDERDOG_EDGE_CAP = 30.0   # pickovi na _UNDERDOG_MIN_ODDS i više (pravi underdogovi)
# 30, ne 28: na 28 je Cerundolo @2.79 (28.2pp, DOBIO) ispadao za dvije desetinke —
# tocno onaj "za dlaku" problem koji ovim paketom popravljamo u pravilima. Na 30
# prolaze svi povijesni dobitni underdogovi osim Gaubasa @3.10 (30.7pp), a
# Collignon @2.82 uz conf 71 (35.5pp — dokumentirani promasaj) i dalje ispada.
_UNDERDOG_MIN_ODDS = 2.00

_CLAY_DEAD_ZONE = (1.50, 1.90)
_CLAY_DEAD_ZONE_MAX = 1  # max toliko clay pickova iz mrtve zone po tiketu


def _clay_dead_zone_count(combo) -> int:
    return sum(1 for p in combo
               if _is_clay(p) and _CLAY_DEAD_ZONE[0] <= _pick_odds(p) < _CLAY_DEAD_ZONE[1])


def _hard_caution_zone_count(combo) -> int:
    """Hard oprezna zona 1.43-1.90 — max 1 po tiketu (ublaženo 26.07.2026: prije je
    1.43-1.60 bio potpuno zabranjen; vidi komentar uz _HARD_CAUTION_ZONE)."""
    return sum(1 for p in combo
               if _is_hard(p) and _HARD_CAUTION_ZONE[0] <= _pick_odds(p) <= _HARD_CAUTION_ZONE[1])


def _find_best_combination(candidates: list, cfg: dict) -> Optional[list]:
    """
    Quality-first scoring using joint probability as primary metric.
    Formula:
      score = joint_probability × 100
            + edge_bonus × 1.5        (edge >= 3pp, proportional, cap 10/pick)
            + high_conf_count × 2     (confidence >= 72%)
            - weakest_pick_penalty    (max(0, 68 - min_conf) × 1.5)
            - extra_pick_penalty      ((n_picks - 4) × 3)
    Combined odds range is a hard filter, not a target.
    Clay disciplina: max 1 clay pick u mrtvoj zoni kvota 1.50-1.90 po kombinaciji.
    """
    min_n = cfg["min_matches"]
    max_n = cfg["max_matches"]
    min_odds = cfg["min_combined_odds"]
    max_odds = cfg["max_combined_odds"]

    best = None
    best_score = -1

    for n in range(max_n, min_n - 1, -1):
        if n > len(candidates):
            continue
        for combo in itertools.combinations(candidates, n):
            if any(_pick_odds(p) < 1.06 for p in combo):
                continue

            odds = combined_odds([_pick_odds(p) for p in combo])
            if odds < min_odds or odds > max_odds:
                continue

            if _clay_dead_zone_count(combo) > _CLAY_DEAD_ZONE_MAX:
                continue

            if _hard_caution_zone_count(combo) > _HARD_CAUTION_ZONE_MAX:
                continue

            score = _score_combo(combo)
            if score > best_score:
                best_score = score
                best = list(combo)

    return best


def _score_combo(combo: tuple) -> float:
    """Score a combination using joint probability as primary signal."""
    confs = [max(1, p.get("confidence", 50)) for p in combo]

    # Joint probability (primary) — product of all confidences
    joint_prob = 1.0
    for c in confs:
        joint_prob *= c / 100.0

    # Edge bonus: proportional, only if edge >= 3pp, cap 10 per pick.
    # Edge-sanity (clay revizija 2026-07-11): prevelik edge je povijesno bio signal NAŠE
    # greške, ne value-a (Collignon @2.82 uz umišljenih 18pp izgubio), pa iznad gornje
    # granice pick ne dobiva bonus.
    #
    # GRANICA SADA OVISI O CIJENI PICKA (02.08.2026). Ista brojka znači različite tvrdnje:
    #   - favorit @1.50: "ja 70%, tržište 50%" = "ovo je siguran meč"  -> tu smo griješili
    #   - underdog @2.50: "ja 63%, tržište 40%" = "ovo je bliže izjednačenom nego cijena"
    #     -> bitno skromnija i obranjivija tvrdnja
    # Jedinstvenih 20pp je tiho gasilo SVE underdoge: pick @2.50 uz conf 63 ima 23pp edga,
    # pa je dobivao NULA bonusa i optimizator ga nikad nije birao. Izmjereno na sezoni:
    # raspon 2.30-2.60 nam je NAJBOLJI (6W-2L, ROI +79.4%), dok 1.30-1.60 gubi (-10.2%, n=93).
    # Kontrola: Collignon @2.82 uz conf 71 (35.5pp) i dalje ostaje bez bonusa.
    edge_total = 0.0
    for p in combo:
        fair = p.get("fair_odds") or 0
        bookmaker = _pick_odds(p)
        if fair > 0 and bookmaker > 0:
            model_prob = 1.0 / fair * 100
            implied_prob = 1.0 / bookmaker * 100
            edge = model_prob - implied_prob
            edge_cap = _UNDERDOG_EDGE_CAP if bookmaker >= _UNDERDOG_MIN_ODDS else _EDGE_CAP
            if 3.0 <= edge <= edge_cap:
                edge_total += min(10.0, edge)

    # High confidence bonus
    high_conf_count = sum(1 for c in confs if c >= 72)

    # Weakest pick penalty
    weakest = min(confs)
    weakest_penalty = max(0.0, (68 - weakest) * 1.5)

    # Extra pick penalty
    extra_penalty = (len(combo) - 4) * 3

    return (joint_prob * 100
            + edge_total * 1.5
            + high_conf_count * 2
            - weakest_penalty
            - extra_penalty)


def _pick_edge(pred: dict) -> float:
    """Edge u postotnim bodovima (pp): modelova vjerojatnost (iz fair_odds) minus
    tržišna vjerojatnost (iz bookmaker kvote). Pozitivno = value u našu korist."""
    fair = pred.get("fair_odds") or 0
    bookmaker = _pick_odds(pred)
    if fair <= 0 or bookmaker <= 0:
        return 0.0
    return (1.0 / fair - 1.0 / bookmaker) * 100


def _is_value_pick(pred: dict) -> bool:
    """Value pick: edge >= 3pp between our fair probability and bookmaker implied probability."""
    return _pick_edge(pred) >= 3.0


def _pick_odds(pred: dict) -> float:
    m = pred.get("match", {})
    pick = pred.get("pick", "")
    p1 = m.get("player1", "")
    # Matchanje picka s igračem
    if pick.lower() in p1.lower() or p1.lower() in pick.lower():
        return float(m.get("odds_p1", 1.5) or 1.5)
    return float(m.get("odds_p2", 1.5) or 1.5)


_last_reviewer_notes: dict = {}  # module-level cache for reviewer output


def _review_ticket(proposed: list, rejected: list, cfg: dict) -> list:
    """
    Claude Sonnet reviews the mathematically selected ticket holistically.
    Can confirm, modify (max 2 swaps), reduce, or force a valid ticket.
    Falls back to proposed ticket if review fails or produces invalid result.
    """
    def _pick_summary(p: dict) -> str:
        m = p.get("match", {})
        conf = p.get("confidence", 0)
        fair = p.get("fair_odds") or 0
        bm = _pick_odds(p)
        edge = round((1.0/fair - 1.0/bm) * 100, 1) if fair > 0 and bm > 0 else 0
        fmt = "BoF5" if "Grand Slam" in m.get("level", "") else "BoF3"
        return (
            f"  Pick: {p.get('pick','')} | {m.get('player1','')} vs {m.get('player2','')} "
            f"| {m.get('tournament','')} {m.get('round','')} {fmt} | {m.get('surface','')}\n"
            f"  Confidence: {conf}% | Fair odds: {fair:.2f} | Bookmaker: {bm:.2f} | Edge: {edge:+.1f}pp\n"
            f"  Risk: {p.get('risk_level','')} — {p.get('risk_notes','')}\n"
            f"  Key factors: {'; '.join(p.get('key_factors',[]))}\n"
            f"  Analysis: {p.get('analysis','')}"
        )

    proposed_section = "\n\n".join(_pick_summary(p) for p in proposed)
    rejected_section = "\n\n".join(_pick_summary(p) for p in rejected[:5]) if rejected else "None"

    from utils.helpers import combined_odds as _co
    joint_prob = 1.0
    for p in proposed:
        joint_prob *= (p.get("confidence", 50) / 100)
    c_odds = _co([_pick_odds(p) for p in proposed])

    prompt = f"""You are the final holistic reviewer of a tennis betting ticket.

The mathematical optimizer has already applied: joint probability scoring, edge bonuses, weakest-pick penalty, extra-pick penalty, surface ELO, avg opponent ELO, fatigue, H2H reliability, and round context.

PROPOSED TICKET ({len(proposed)} picks | Combined odds: {c_odds:.2f} | Joint probability: {joint_prob*100:.1f}%):
{proposed_section}

REJECTED CANDIDATES (closest to selection):
{rejected_section}

YOUR ROLE:
Review the ticket holistically as an experienced tennis analyst. You may:
A. CONFIRM — keep as-is
B. MODIFY — replace 1-2 picks if tennis reasoning clearly overrules the math
C. REDUCE — remove the weakest link if it makes the ticket fragile (never below 4 picks)
D. FORCE — if ticket is weak, build the best possible ticket from all available (respect the pick-count limits below)

CHECK FOR: hidden fatigue, false recent form (weak opponents), surface/style mismatch, overlapping risk (too many picks with same vulnerability), data gaps (ELO 1500), BoF5 stamina implications, H2H small sample overweighting.

GRASS-SPECIFIC CHECKS (apply when any pick is on Grass surface):
- FLAG and consider removing: any grass pick at confidence ≥65% — this season's data shows systematic overconfidence at that level; confidence 65%+ on grass has lost repeatedly.
- FLAG: grass picks where the player has 4+ matches in 7 days with only 1-2 days rest — fatigue on grass is decisive and cannot be offset by form.
- FLAG: grass picks driven primarily by ELO when opponent has equal or better recent in-tournament results (tournament trajectory). ELO alone on grass has failed in 5+ documented cases.
- FLAG: grass picks where the favoured player entered via bye and opponent has 2+ in-tournament wins this week — the bye is a disadvantage on grass, not neutral.
- If 2+ grass picks share the same vulnerability (both relying on ELO edge, both with fatigued favourites), treat this as overlapping risk and consider REDUCING to 1 grass pick.

CLAY-SPECIFIC CHECKS (apply when any pick is on Clay surface — derived from 15 documented clay losses, 7/7 lost clay tickets):
- FLAG and consider removing: any clay pick whose opponent has 3+ wins in this tournament or 2+ wins over seeded players, unless our pick is an elite clay player (clay ELO ≥1850 or hold ≥85%). Fading in-form players caused 8 of 15 clay losses (Mensik beat 3 of our picks, Arnaldi 2, Fonseca 2). NEVER keep a pick against a player who already eliminated one of our picks earlier in the same tournament.
- FLAG: clay picks where the opponent has BOTH the better clay W-L record AND the better hold% — our pick's ranking/ELO edge lost all such documented matches (Khachanov, FAA, Brancaccio).
- FLAG: clay picks at odds 1.50-1.90 (dead zone: 27% win rate this season) that lack edges in at least two of: clay record, serve-hold, quality-adjusted form.
- FLAG: clay picks where the OPPONENT plays in his own country (home crowd) and is in rhythm — home underdogs destroyed marginal favourites repeatedly (Fery 5x, Huesler in Gstaad).
- FLAG: clay picks where our player has 2+ matches in last 7 days and 2+ fewer rest days than the opponent — clay rallies punish tired legs hardest.
- If 2+ clay picks share the same vulnerability, treat as overlapping risk and consider REDUCING.

HARD CONSTRAINTS:
- Final ticket: {cfg["min_matches"]}-{cfg["max_matches"]} picks, combined odds {cfg["min_combined_odds"]:g}-{cfg["max_combined_odds"]:g}
- Max 2 replacements
- Never remove a strong pick just because odds are low
- Never add a pick just to increase odds
- Prefer stability over excitement

Respond ONLY in this JSON format:
{{
  "decision": "CONFIRM|MODIFY|REDUCE|FORCE",
  "final_picks": ["exact player name as given above", ...],
  "changes": "No changes made. / Removed X, added Y because: ... (1-2 clean sentences, final answer only — no reasoning steps, hesitations, or self-corrections like 'wait, ...')",
  "warning": "One sentence naming the SINGLE pick (by player name) that carries the most risk on the PROPOSED ticket above, and why. Avoid referring to counts of picks (e.g. 'all four picks') since your proposed changes may be reverted and the original ticket shown instead — focus on the specific pick/risk, not the ticket size."
}}"""

    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODELS["ticket_writer"],
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        import re as _re
        raw = response.content[0].text.strip()
        raw = _re.sub(r'```(?:json)?\s*', '', raw).strip().strip('`')
        # Robust JSON parse — handles unterminated strings and literal newlines
        start = raw.find('{')
        end = raw.rfind('}')
        if start != -1 and end > start:
            raw = raw[start:end + 1]
        result = json.loads(raw)

        decision = result.get("decision", "CONFIRM")
        final_names = result.get("final_picks", [])
        changes = result.get("changes", "")
        warning = result.get("warning", "")

        # Store reviewer notes for inclusion in ticket
        _last_reviewer_notes.clear()
        _last_reviewer_notes.update({
            "decision": decision,
            "changes": changes,
            "warning": warning,
        })

        if changes and changes != "No changes made.":
            print(f"  Reviewer [{decision}]: {changes}")
        if warning:
            print(f"  Reviewer warning: {warning}")

        if decision == "CONFIRM" or not final_names:
            return proposed

        # Match returned names back to prediction objects
        all_pool = proposed + rejected
        final_combo = []
        for name in final_names:
            name_lower = name.lower().strip()
            for p in all_pool:
                pick = (p.get("pick") or "").lower().strip()
                if pick == name_lower or pick.split()[-1] == name_lower.split()[-1]:
                    if p not in final_combo:
                        final_combo.append(p)
                        break

        # Validate result — must satisfy cfg pick-count limits and odds range
        if len(final_combo) >= cfg["min_matches"]:
            rev_odds = combined_odds([_pick_odds(p) for p in final_combo])
            if cfg["min_combined_odds"] <= rev_odds <= cfg["max_combined_odds"]:
                return final_combo
            print(f"  Reviewer result invalid odds ({rev_odds:.2f}) — keeping original.")
        else:
            print(f"  Reviewer returned {len(final_combo)} picks — keeping original.")

        # Reviewer's change was rejected by validation — original ticket kept as-is.
        # Update notes so the displayed decision matches reality (avoid showing a
        # "removed X" claim for a pick that is still in the final ticket), and avoid
        # echoing the reviewer's raw "changes" text which can contain messy
        # mid-reasoning artifacts (e.g. "wait, ...").
        if final_combo and len(final_combo) < len(proposed):
            removed_names = [p.get("pick", "") for p in proposed if p not in final_combo]
            detail = f"remove {', '.join(removed_names)}"
        else:
            detail = f"reduce to {len(final_combo)} pick(s)"

        _last_reviewer_notes["decision"] = "CONFIRM"
        _last_reviewer_notes["changes"] = (
            f"Reviewer proposed to {detail}, but this was reverted to keep combined odds "
            f"within the required range ({cfg['min_combined_odds']}-{cfg['max_combined_odds']}). "
            f"Original ticket retained — see warning below for the highest-risk pick."
        )
        return proposed

    except Exception as e:
        print(f"  Reviewer error: {e} — keeping original ticket.")
        return proposed


def _generate_ticket_summary(matches: list, total_odds: float, pot_win: float, weights: dict) -> str:
    """Claude Sonnet writes the ticket write-up in English."""
    picks_text = "\n".join([
        f"{i+1}. {m['pick']} to win — {m['player1']} vs {m['player2']} "
        f"({m['tournament']}, {m['surface']}, {m.get('round','')}) — odds: {m['odds']:.2f}, "
        f"confidence: {m['confidence']:.0f}%"
        f"{', VALUE ✓' if m.get('value_bet') else ''}\n"
        f"   Risk: {m.get('risk_notes','')}\n"
        f"   Key factors: {', '.join(m.get('key_factors',[]))}"
        for i, m in enumerate(matches)
    ])

    prompt = f"""You are an expert tennis analyst. Write a concise ticket write-up in English, in the style of a sports analyst. Maximum 200 words.

TICKET:
{picks_text}

Combined odds: {total_odds:.2f}
Potential return: €{pot_win:.2f} on €50 stake

Write:
1. One sentence on the overall ticket quality
2. For each pick: one sentence explaining why it is a good selection (focus on key factors)
3. One closing sentence with overall assessment

Be specific — mention surface, form, H2H, fatigue where relevant.

Refer to players by name (or surname) only — do not use nationality/demonyms (e.g. "the Croatian", "the Czech") as a stand-in for a player's name, since this is a frequent source of mix-ups when a ticket contains multiple players."""

    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODELS["ticket_writer"],
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"Greška generiranja write-upa: {e}")
        return f"Tiket s {len(matches)} parova. Ukupna kvota: {total_odds:.2f}, potencijalni dobitak: €{pot_win:.2f}."


_ANALYSIS_ONLY_MAX_PICKS = 12     # max mečeva u analysis-only prikazu
_ANALYSIS_ONLY_MIN_ODDS = 1.06    # ispod ove kvote nema smisla pratiti pick


def build_analysis_only_ticket(predictions: list) -> dict:
    """
    Builds an analysis-only entry when there aren't enough matches for a full ticket.
    Max 12 picks, sorted by odds descending (higher-odds matches make the cut),
    picks below 1.06 excluded. Tracks results, never marks won/lost.
    Also computes a HYPOTHETICAL "forced risk" ticket (limits from TICKET_CONFIG) for the
    EMAIL ONLY — what we'd play if we absolutely had to bet today. Not saved to DB.
    """
    valid = [p for p in predictions
             if not p.get("skip_reason") and _is_main_tour(p)
             and _pick_odds(p) >= _ANALYSIS_ONLY_MIN_ODDS]
    # Sortiraj po kvoti silazno pa ograniči na 12 — veće kvote uđu unutar tih 12.
    valid.sort(key=lambda p: _pick_odds(p), reverse=True)
    valid = valid[:_ANALYSIS_ONLY_MAX_PICKS]

    ticket_matches = []
    for pred in valid:
        m = pred.get("match", {})
        ticket_matches.append({
            "player1": m.get("player1", ""),
            "player2": m.get("player2", ""),
            "pick": pred.get("pick", ""),
            "odds": _pick_odds(pred),
            "match_date": m.get("date", ""),
            "match_time": m.get("time", ""),
            "tournament": m.get("tournament", ""),
            "tournament_level": m.get("level", ""),
            "surface": m.get("surface", ""),
            "round": m.get("round", ""),
            "confidence": pred.get("confidence", 0),
            "fair_odds": pred.get("fair_odds"),
            "value_bet": pred.get("value", False),
            "risk_level": pred.get("risk_level", "srednji"),
            "risk_notes": pred.get("risk_notes", ""),
            "handicap_option": pred.get("handicap_option"),
            "key_factors": pred.get("key_factors", []),
            "external_match_id": m.get("external_id", ""),
            # API player ID-evi (A1, 26.07.2026): evening update ih koristi za razrješavanje
            # rezultata i kad turnir nestane iz fixtures feeda (slučaj Bublik-Halys 25.07.).
            "player1_id": str(m.get("player1_id") or "") or None,
            "player2_id": str(m.get("player2_id") or "") or None,
            "result": "pending",
        })

    summary = _generate_analysis_only_summary(ticket_matches)

    # Hipotetski "kad bih baš morao riskirati" tiket: najbolja kombinacija iz gornje liste,
    # bez conf floora (forsirani scenarij). _find_best_combination boduje po KVALITETI, ne
    # po najvišoj kvoti. Samo za email, NE sprema se u bazu (app ostaje čist).
    #
    # B (26.07.2026): hipotetski tiket sada prolazi kroz _selection_ok — isti deterministički
    # filteri kao pravi tiket (Fery-veto, mrtve zone, GS pragovi, both-declining, clay fatigue).
    # Povod: 23.-25.07. su bili analysis-only dana, a Halys nas je u istom turniru srušio TRI
    # puta zaredom jer se ovdje veto nikad nije primjenjivao. Široka lista analiziranih mečeva
    # (gore) namjerno OSTAJE bez tih filtera — ona je informativna; hipotetski tiket je
    # preporuka koju korisnik stvarno čita, pa mora poštovati ista pravila kao pravi tiket.
    hypo_pool = [p for p in valid if _selection_ok(p)]
    n_filtered = len(valid) - len(hypo_pool)
    if n_filtered:
        print(f"  Hipotetski tiket: izbačeno {n_filtered} pickova determinističkim filterima "
              f"(Fery-veto / mrtve zone / GS prag / declining / fatigue).")
    cfg = _apply_surface_overrides(dict(TICKET_CONFIG), hypo_pool or valid)
    hypo_combo = _find_best_combination(hypo_pool, cfg)
    hypothetical_summary = _generate_hypothetical_summary(hypo_combo, cfg)

    return {
        "total_odds": 0.0,
        "potential_win": 0.0,
        "stake": 0,
        "matches_count": len(ticket_matches),
        "ticket_summary": summary,
        "hypothetical_summary": hypothetical_summary,
        "reviewer_decision": "",
        "reviewer_changes": "",
        "reviewer_warning": "",
        "status": "analysis_only",
        "matches": ticket_matches,
    }


def _generate_hypothetical_summary(combo: Optional[list], cfg: dict) -> str:
    """Email-only: par rečenica u glasu 'lovca na rizik' o tiketu koji bismo odigrali KAD
    bismo baš morali (granice iz TICKET_CONFIG). Pošten 'preskočio bih' ako nije moguće."""
    if not combo:
        return (
            "Even forcing it, today's slate can't reach the minimum combined odds of "
            f"{cfg['min_combined_odds']:.0f} with a {cfg['min_matches']}-{cfg['max_matches']} pick "
            "ticket — the confident picks are too short-priced. If I truly had to, I'd sit this one out."
        )

    total_odds = combined_odds([_pick_odds(p) for p in combo])
    pot = potential_win(cfg["stake"], total_odds)
    picks_text = "\n".join(
        f"- {p.get('pick','')} to win ({p.get('match',{}).get('player1','')} vs "
        f"{p.get('match',{}).get('player2','')}, {p.get('match',{}).get('tournament','')}, "
        f"{p.get('match',{}).get('round','')}) — odds {_pick_odds(p):.2f}, conf {p.get('confidence',0):.0f}%"
        for p in combo
    )
    prompt = f"""You are a sharp, opportunistic tennis bettor — a hunter of value and calculated risk.
No real ticket was placed today (discipline says the slate is too thin or too short-priced), but the reader
wants to know: IF you absolutely HAD to play a {cfg['min_matches']}-{cfg['max_matches']} pick accumulator at
combined odds {cfg['min_combined_odds']:.0f}-{cfg['max_combined_odds']:.0f}, what would you risk?

YOUR FORCED TICKET ({len(combo)} picks | combined odds {total_odds:.2f} | €{pot:.0f} return on €{cfg['stake']:.0f} stake):
{picks_text}

Write 2-4 punchy sentences, first person, in the voice of a risk hunter: name the picks you'd back and the
outcomes you predict, and one honest line on the biggest risk. Be concise and specific. Open with something
like "If I had to risk it today...". Refer to players by surname only."""
    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODELS["analysis"],   # Haiku — jeftino
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"Greška hipotetskog write-upa: {e}")
        names = ", ".join(p.get("pick", "") for p in combo)
        return (
            f"If I had to risk it today: {len(combo)} picks at combined odds {total_odds:.2f} "
            f"(€{pot:.0f} on €{cfg['stake']:.0f}) — {names}."
        )


def _generate_analysis_only_summary(matches: list) -> str:
    """Haiku write-up for analysis-only days — late rounds with too few matches for a ticket."""
    if not matches:
        return "No main-tour matches available for analysis today."

    picks_text = "\n".join([
        f"{i+1}. {m['pick']} to win — {m['player1']} vs {m['player2']} "
        f"({m['tournament']}, {m['surface']}, {m.get('round','')}) — "
        f"odds: {m['odds']:.2f}, confidence: {m['confidence']:.0f}%\n"
        f"   Key factors: {', '.join(m.get('key_factors', []))}"
        for i, m in enumerate(matches)
    ])

    prompt = f"""You are an expert tennis analyst. Today there {'is only 1 main-tour match' if len(matches) == 1 else f'are only {len(matches)} main-tour matches'} available — not enough to build a full accumulator ticket.

AVAILABLE MATCHES:
{picks_text}

Write the analysis as:
1. One sentence: why no ticket was formed (too few matches for a valid accumulator)
2. For EACH of the {len(matches)} matches: exactly one concise sentence — your pick and the single strongest reason. Cover ALL {len(matches)} matches, do not stop early.
3. One closing sentence on overall confidence

Keep each sentence short, but you MUST include all {len(matches)} picks. Be direct and specific. Frame it as: "if I had to bet on these matches..." This entry is tracked for model learning."""

    # Token budget skalira s brojem mečeva (1 rečenica po picku). Analysis-only je
    # sada ograničen na max 12 mečeva, pa je strop ~13 mečeva (ranije 18) — dovoljno
    # da ništa ne reže, bez nepotrebnog trošenja tokena.
    max_tok = min(1300, 350 + len(matches) * 75)

    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODELS["analysis"],
            max_tokens=max_tok,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"Greška analysis-only write-upa: {e}")
        picks_str = ", ".join(f"{m['pick']} ({m['confidence']:.0f}%)" for m in matches)
        return (
            f"Analysis only — {len(matches)} match(es) available today, "
            f"insufficient for a full ticket. Predictions: {picks_str}."
        )


def _apply_daily_limits(candidates: list) -> list:
    """
    Pre-filtrira kandidate: max N po (turniru, datum) prema DAILY_MATCH_LIMITS.
    Unutar svake grupe zadržava top N po confidence-u.
    Ovo se poziva PRIJE kombinatorike tako da motoru uvijek ostaje čist pool.
    """
    today_str = today_zagreb().isoformat()
    tomorrow_str = tomorrow_zagreb().isoformat()

    groups: dict = {}
    for p in candidates:
        m = p.get("match", {})
        tournament = m.get("tournament", "unknown")
        date = (m.get("date", "") or "")[:10]
        groups.setdefault((tournament, date), []).append(p)

    result = []
    for (tournament, date), group in groups.items():
        level = group[0].get("match", {}).get("level", "ATP 250")
        limits = DAILY_MATCH_LIMITS.get(level, {"today": 2, "tomorrow": 2})

        if date == today_str:
            limit = limits["today"]
        else:
            limit = limits["tomorrow"]  # sutra ili dalje — konzervativniji limit

        if limit == 0:
            continue  # Challenger/Qualifying — preskačemo

        group_sorted = sorted(group, key=lambda p: (p.get("confidence") or 0), reverse=True)
        result.extend(group_sorted[:limit])
        if len(group_sorted) > limit:
            print(f"  Daily limit: {tournament} ({date}) — uzeto {limit}/{len(group_sorted)} kandidata")

    return result
