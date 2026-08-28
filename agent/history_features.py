# -*- coding: utf-8 -*-
"""Značajke iz povijesti mečeva — SA ZAŠTITOM OD CURENJA (22.08.2026 17:05).

=============================================================================================
ZAŠTO OVAJ MODUL POSTOJI
=============================================================================================
Pri analizi 22.08.2026 head-to-head je pokazao spektakularan rezultat: pick koji "vodi u
H2H" prolazi 96,3% (n=27), pick koji "gubi" 20,0% (n=15) — razlika +76pp, i preživjela je
stratifikaciju po kvoti u sva četiri pojasa. Prije nego što je to prijavljeno kao nalaz,
pregledan je svaki slučaj ručno i našlo se ovo:

    medijan razmaka do "ranijeg" meča bio je JEDAN DAN

    2026-08-06 | pick=Medvedev  opp=Van De Zandschulp  ishod=L
        "raniji": 2026-08-05 L vs Van De Zandschulp

To nije povijest — to je ISTI MEČ zapisan pod drugim datumom. Naš `match_date` u
`analyzed_matches` i datum koji vraća RapidAPI ne poklapaju se uvijek.

IZMJERENO na 256 uparenih mečeva (22.08.2026):
    naš datum = API datum      196 mečeva  (77%)
    naš je +1 dan kasniji       38 mečeva
    naš je -1 dan raniji        19 mečeva
    ±2 dana                      3 meča
Dakle **23% mečeva ima neusklađen datum**. Svaki od njih, u naivnom filtru
`povijest.datum < predikcija.datum`, ulazi kao "raniji meč" i sa sobom nosi ISHOD koji
tek predviđamo. Uz zaštitu, H2H efekt pada s +66,7pp na **+0,0pp** — bio je čisto curenje.

Uzrok neusklađenosti je poznat i NAMJERAN dio sustava: screenshot pokriva danas i sutra,
API ponekad isti par označi kao prekosutrašnji, a `run_daily` to razrješava kroz
`_gate_by_screenshot`, `time_screenshot_date` i `_detect_provisional_schedule`. Ta logika
je pažljivo naštimana i **ovaj modul je NE dira niti smije dirati**.

=============================================================================================
PRODUKCIJA NIJE BILA POGOĐENA — provjereno
=============================================================================================
`/atp/player/past-matches/{id}` vraća isključivo ODIGRANE mečeve: od 727 harvestiranih
redaka 0 je bez pobjednika, 0 bez rezultata, 0 s datumom u budućnosti. Zato
`get_recent_form` u trenutku analize ne može vidjeti ishod meča koji tek predviđamo —
curenje je postojalo samo u retrospektivnoj analizi, ne u generiranju tiketa.
`data_fetcher.get_recent_form` se zato NAMJERNO ne mijenja: promjena bi mijenjala pickove
bez ijednog dokaza da nešto ne valja.

=============================================================================================
KAKO SE ZAŠTITA KORISTI
=============================================================================================
Dvostruka brava, obje su nužne:
  1. VREMENSKA: povijesni meč se broji tek ako je `MIN_DAYS_BEFORE` (3) ili više dana
     prije datuma predikcije. Tri dana pokrivaju najveće izmjereno odstupanje (±2).
  2. PO PARU: meč između IST A DVA IGRAČA unutar `SAME_PAIR_WINDOW` (5) dana odbacuje se
     bez obzira na sve — to je najizravniji potpis istog meča pod drugim datumom.

Sve funkcije ovdje primaju `as_of` (datum predikcije) i same primjenjuju zaštitu. Nijedna
ne smije biti pozvana bez `as_of`.

=============================================================================================
ŠTO JE OVIM IZMJERENO (22.08.2026, uz zaštitu)
=============================================================================================
    H2H                          +0,0pp   -> bio artefakt, nema ga
    sekvence forme (isti profil) 52,6% naspram 64,6%  -> nema signala, predznak se okrenuo
    dominacija (2 seta)          +8,5pp, P=0,31       -> nema
    umor (mečevi u 2-7 dana)     +7,2pp kontrolirano  -> slabo
    kvaliteta protivnika         +18,0pp kontrolirano, r=+0,203 P=0,0030, monotono
                                 kroz 4 razreda, obje polovice isti smjer -> JEDINI kandidat

NIŠTA OD OVOGA NE ULAZI U PROMPT NI U SELEKCIJU. Modul nije uvezen ni u `run_daily` ni u
`predictor` ni u `ticket_builder` — služi analizi i budućem mjerenju. Prije nego išta od
toga uđe u odluku, mora se potvrditi na turniru koji nije bio u uzorku (Winston-Salem).
"""
import datetime
import re
from collections import defaultdict

# Zaštita od curenja — vidi docstring. Ne smanjivati bez novog mjerenja neusklađenosti datuma.
MIN_DAYS_BEFORE = 3
SAME_PAIR_WINDOW = 5


def _norm(s: str) -> str:
    return " ".join(sorted((s or "").lower().replace(".", " ").split()))


def _toks(s: str) -> set:
    return {t for t in (s or "").lower().replace(".", " ").replace("-", " ").split()
            if len(t) > 1 and t not in ("jr", "sr")}


def same_player(a: str, b: str) -> bool:
    """Isto podudaranje imena kao drugdje u projektu (SuperSport piše 'Prezime Ime')."""
    ta, tb = _toks(a), _toks(b)
    return bool(ta and tb) and len(ta & tb) >= min(2, min(len(ta), len(tb)))


def _days_between(as_of: str, hist_date: str):
    try:
        return (datetime.date.fromisoformat(str(as_of)[:10])
                - datetime.date.fromisoformat(str(hist_date)[:10])).days
    except (TypeError, ValueError):
        return None


def safe_history(matches: list, as_of: str, opponent: str = None) -> list:
    """Povijesni mečevi koje je SIGURNO koristiti za predikciju na datum `as_of`.

    `matches` je lista dictova s barem `date`; ostalo (won, opp, score) se propušta.
    Primjenjuje obje brave iz docstringa. Ovo je JEDINI ulaz u sve ostale funkcije —
    nijedna značajka ne smije čitati sirovu povijest.
    """
    if not as_of:
        raise ValueError("safe_history zahtijeva `as_of` — bez njega nema zaštite od curenja.")
    out = []
    for m in matches or []:
        d = _days_between(as_of, m.get("date"))
        if d is None or d < MIN_DAYS_BEFORE:
            continue
        # druga brava: isti par unutar prozora je gotovo sigurno isti meč
        if opponent and d <= SAME_PAIR_WINDOW and same_player(m.get("opp"), opponent):
            continue
        out.append(m)
    return out


def parse_sets(score: str):
    """'6-4 3-6 7-6(5)' -> [(6,4),(3,6),(7,6)]. Prazno ako se ne da parsirati."""
    return [(int(a), int(b)) for a, b in re.findall(r"(\d+)\s*-\s*(\d+)", score or "")]


def is_retirement(score: str) -> bool:
    """Predaja/walkover — takav meč ne govori ništa o formi ni o izdržljivosti.

    `result_type` iz API-ja se ne sprema (nema stupca), ali sam rezultat nosi oznaku:
    vidjeno u podacima npr. '6-2 2-0 ret.'.
    """
    s = (score or "").lower()
    return any(w in s for w in ("ret", "w/o", "wo", "def", "abn"))


def matches_in_window(matches: list, as_of: str, lo_days: int = MIN_DAYS_BEFORE,
                      hi_days: int = 7) -> int:
    """Broj mečeva u prozoru [lo_days, hi_days] prije `as_of` — mjera opterećenja.

    IZMJERENO 22.08.2026: 0 mečeva u prozoru 2-7 dana -> 67,3% (n=107), 1+ -> 61,8% (n=152);
    kontrolirano po kvoti +7,2pp. Najjače u pojasu kvota 1,80+ (56,0% naspram 29,2%).
    Preslabo da uđe u odluku, dovoljno da se prati.
    """
    n = 0
    for m in safe_history(matches, as_of):
        d = _days_between(as_of, m.get("date"))
        if d is not None and lo_days <= d <= hi_days:
            n += 1
    return n


def comeback_rate(matches: list, as_of: str, min_n: int = 5):
    """Udio pobjeda u kojima je igrač izgubio PRVI set. Vraća None ako nema uzorka.

    UPOZORENJE — OVA MJERA HVATA SUPROTNO OD ONOGA ŠTO IME SUGERIRA (izmjereno 22.08.2026
    na 727 mečeva): visoka stopa povratka NIJE oznaka mentalne čvrstine nego oznaka igrača
    koji redovito zaostaje. `r(stopa povratka, koliko često gubi prvi set) = +0,473`.
    Sirovi efekt na ishod je NEGATIVAN (0-8% -> 71,1%; 22%+ -> 57,1%), a pod kontrolom
    cijene pada s -9,9pp na -3,6pp i mijenja predznak. NE koristiti kao prediktor.
    Ostavljeno jer je korisna dijagnostika stila, ne prognoze.
    """
    hist = [m for m in safe_history(matches, as_of) if not is_retirement(m.get("score"))]
    wins = [m for m in hist if m.get("won")]
    if len(hist) < min_n or not wins:
        return None
    cb = 0
    for m in wins:
        sets = parse_sets(m.get("score"))
        if len(sets) >= 2 and sets[0][0] < sets[0][1]:
            cb += 1
    return cb / len(wins)


def straight_set_share(matches: list, as_of: str, last_n: int = 3, min_wins: int = 2):
    """Udio nedavnih pobjeda ostvarenih u dva seta — 'kako je pobijedio', ne samo 'je li'.

    IZMJERENO 22.08.2026: sve pobjede u 2 seta -> 67,3% (n=49) naspram 58,9% (n=107);
    razlika +8,5pp, P=0,313. Nije dovoljno.
    """
    hist = [m for m in safe_history(matches, as_of) if not is_retirement(m.get("score"))][-last_n:]
    wins = [m for m in hist if m.get("won")]
    if len(wins) < min_wins:
        return None
    return sum(1 for m in wins if len(parse_sets(m.get("score"))) == 2) / len(wins)


def opponent_quality(matches: list, as_of: str, height_lookup, last_n: int = 5,
                     min_n: int = 3):
    """Prosječna visina zadnjih `last_n` protivnika — proxy za kvalitetu/stil protivnika.

    NAJJACI KANDIDAT IZ ANALIZE 22.08.2026 (uz zaštitu od curenja):
        prosjek 0-185 cm  -> 50,0% (n=52)
        prosjek 185-188   -> 54,7% (n=64)
        prosjek 188-191   -> 68,1% (n=69)
        prosjek 191+      -> 80,0% (n=25)
        r = +0,203  P=0,0030  n=210; kontrolirano po kvoti +18,0pp, konzistentno u 4/4
        pojasa; obje polovice uzorka isti smjer.
    Visina je proxy za servisni stil (r=+0,597 sa `serve_pts_won`) i djelomično za rang
    (r=-0,178 s ATP rangom), ali ista ideja mjerena RANGOM protivnika daje samo +9,7pp —
    dakle visina nosi nešto preko ranga.
    MEHANIZAM NIJE DO KRAJA JASAN. Zato se prati, a ne koristi, dok se ne potvrdi na
    turniru izvan uzorka.

    `height_lookup` je funkcija ime -> visina u cm (ili None).

    PROVJERA IZVAN UZORKA, 26.08.2026 14:01 — NALAZ SE POLOVIO, ALI MEHANIZAM JE POTVRĐEN
    I NAĐEN JE BOLJI MJERITELJ.
    Ponovljeno na hard uzorku pod težinama v18 (n=134 od 178), uz devigiranu cijenu kao
    referentnu vrijednost umjesto sirove kvote:
        r = +0,149 (P=0,086), bilo +0,203 (P=0,0030)
        iznad medijana +1,9pp naspram cijene, ispod -6,4pp  ->  raspon 8,3pp, bio +18,0pp
        Winston-Salem (turnir izvan izvornog uzorka): r = +0,147, P=0,503, n=23
            — isti smjer, ali nema snage; ovo NIJE potvrda, samo izostanak opovrgavanja
    Dakle klasična regresija prvog nalaza. Visina ostaje smislen proxy za stil (r=+0,689 s
    asovima, +0,571 sa serve_pts_won, -0,431 s povratom), ali je bučan proxy za KVALITETU.

    ISTA IDEJA MJERENA HARD-ELO-om PROTIVNIKA JE BITNO JAČA (isti uzorak, n=139):
        prosjek zadnjih 5 protivnika < 1600  ->  40,0% (n=10)
                                     1600-1700 -> 41,4% (n=29)
                                     1700-1800 -> 65,8% (n=73)
                                     1800+     -> 66,7% (n=27)
        r = +0,252, P=0,0028
        prag 1700:  ispod  41,0% (n=39) naspram 60,0% očekivano  ->  -19,0pp, z=-2,48, ROI -37,1%
                    iznad  66,0% (n=100) -> +2,5pp
        kontrola cijene:  <60% -21,5pp | 60-72% -20,4pp | 72%+ -2,2pp (n=4)
        kontrola runde:   rane -14,4pp | R16/QF -20,3pp | SF/F -24,8pp
        split-half:       +21,4pp i +27,2pp — obje polovice isti smjer
        relativna verzija (naš minus protivnikov): r = +0,179, P=0,040
    Bilješka od 22.08. ("ista ideja mjerena RANGOM daje samo +9,7pp, dakle visina nosi nešto
    preko ranga") ostaje točna za RANG, ali ne i za ELO — ELO je bolji od oba. Za buduću
    upotrebu koristiti ELO, ne visinu. Mehanizam je time i razjašnjen: nije riječ o stilu
    nego o napuhanom rejtingu iz slabog rasporeda, tj. točno o onome što prompt već traži
    u pravilu 2(c) ("FORM adjusted for opponent quality") a model ne primjenjuje.

    KORISNIKOVA SEKVENCIJALNA HIPOTEZA TESTIRANA I PALA (26.08.2026): "pobijedio je 2-3
    protivnika sličnog profila, sljedeći je isti profil" ne nosi ništa preko glavnog učinka:
        nedavni visoki I sljedeći visok   +4,8pp (n=27)
        nedavni visoki, sljedeći nizak    +6,1pp (n=32)   <- veće od gornjeg
        nedavni niski, sljedeći visok     -4,9pp (n=26)
        nedavni niski, sljedeći nizak    -12,1pp (n=38)
    Poredak ćelija ne prati hipotezu; sve što se vidi je kvaliteta nedavnih protivnika.
    """
    hist = safe_history(matches, as_of)[-last_n:]
    hs = [height_lookup(m.get("opp")) for m in hist]
    hs = [h for h in hs if h]
    if len(hs) < min_n:
        return None
    return sum(hs) / len(hs)


def h2h_record(matches: list, as_of: str, opponent: str):
    """Head-to-head naspram konkretnog protivnika, UZ obje brave.

    IZMJERENO 22.08.2026: bez zaštite izgleda kao +76pp; sa zaštitom ostane ~6 pravih
    slučajeva i efekt je +0,0pp. Zadržano jer je zapis korisniji od brisanja: ako netko
    ubuduće ponovno naiđe na "H2H je super prediktor", ovdje piše zašto nije.
    """
    hist = safe_history(matches, as_of, opponent=opponent)
    m = [x for x in hist if same_player(x.get("opp"), opponent)]
    if not m:
        return None
    return {"n": len(m), "wins": sum(1 for x in m if x.get("won"))}


def build_history_index(rows: list) -> dict:
    """`player_match_history` redci -> {player_id: [ {date, won, opp, score}, ... ]}.

    Redci moraju imati player1_id/player2_id/winner_id/match_date/score i imena.
    Sortirano kronološki. Mečevi bez pobjednika se preskaču.
    """
    idx = defaultdict(list)
    for r in rows or []:
        d = r.get("match_date")
        p1, p2 = str(r.get("player1_id") or ""), str(r.get("player2_id") or "")
        w = str(r.get("winner_id") or "")
        if not (d and p1 and p2) or w not in (p1, p2):
            continue
        idx[p1].append({"date": d, "won": p1 == w, "opp": r.get("player2_name"),
                        "score": r.get("score") or ""})
        idx[p2].append({"date": d, "won": p2 == w, "opp": r.get("player1_name"),
                        "score": r.get("score") or ""})
    for k in idx:
        idx[k].sort(key=lambda x: x["date"])
    return idx
