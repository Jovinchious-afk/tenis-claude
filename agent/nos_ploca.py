# -*- coding: utf-8 -*-
"""Nos-ploča (nos-ploca-v1) — ZNAKOVI PRIJE MEČA uz svaki analizirani meč, U SJENI
(01.11.2026 16:18, korisnikov "provedi P1, P2 i P2b" nakon revizije 01.11.2026).

ŠTO JE: deterministički popis znakova vidljivih PRIJE meča (bez Claudea, bez plaćenih poziva).
Svaki znak ima vrstu (mina / prilika / opis) i RAZINU DOKAZA — što o njemu danas znamo. Isti
popis računa se za SVAKI pick, dobitni i gubitni, pa učenje iz poraza nije naknadna pamet: znak
se uvijek uspoređuje s pobjedama u istom pojasu cijene.

ZAŠTO (revizija 01.11.2026, `revizije/2026-11-01/REVIZIJA_2026-11-01.md`, točke 3, 5 i 8):
  - naš pick je tržišni favorit u 94–96% mečeva, a "uvijek favorit" dao bi isti broj pobjeda;
  - svaki dosad izmjereni "nos" (pouzdanost, Nose, Intuicija, rečenica agenta "samo ELO") ne zna
    više od cijene;
  - analiza gubitka trošila je riječi na "tržište je isto mislilo" (12 od 12).
  Ploča skuplja znakove na jednom mjestu, a sudac im je CIJENA: CLV (pomak kvote do početka meča,
  `agent/clv.py`) brzo, a edge u istom pojasu cijene sporije (n=150).

U SJENI: računa se u dnevnom runu NAKON slaganja tiketa (odmah iza Nosea), upisuje se samo u
`context_snapshot["nos_ploca"]`; model je ne vidi, tiket je ne koristi. Prikaz: Dnevni listić
(P2b) i večernja analiza gubitka (P1). Kapija: K26 u DECISION_INPUTS (pragovi zapisani prije
prvog podatka). Za stare analize (prije 02.11.2026) ploča se može izračunati iz polja koja su već
u snapshotu — to je OPIS, ne dokaz (te analize su viđene na reviziji).

DEFINICIJE SE NE MIJENJAJU dok mjerenje traje — svaka izmjena je nova verzija (nos-ploca-v2) i
brojanje K26 kreće od nule (isto pravilo kao nose-v1).
"""
import math
import re
import unicodedata

VERSION = "nos-ploca-v1"
START_DATE = "2026-11-02"      # K26 broji samo analize od prvog runa s pločom (Pariz)

ODDS_COIN = 1.65               # novčić
BAND = (1.35, 1.45)            # K5 / revizija 01.11., točka 4
ELO_THIN = 50.0                # bodova ELO-a na podlozi (točka 8)
AGE_GAP = 4.0                  # godina (opis D7, revizija 01.11.)
PAUSE_DAYS = 21                # K19
# Profil iz točke 1 na KARIJERNIM brojkama koje model vidi (RapidAPI `p*_return_won` i
# `p*_serve_pts_won`, u postocima). Percentili na našem korpusu do 01.11.2026 (n=1.186 strana):
# povrat P90 = 44,40, servis P10 = 60,80. J. M. Cerúndolo 26.10. (44,6 / 59,4) ih prelazi.
RET_P90 = 44.40
SERVE_P10 = 60.80
NEIGHBOUR_KM = 600.0           # glavni grad ≤ 600 km od grada turnira (definicija LAB-a, E-N)

# (id, oznaka HR, label EN za prompt analize gubitka, vrsta, razina dokaza, kapija)
ZNAKOVI = [
    ("novcic", "Novčić: kvota picka 1,65+", "Coin-flip: our pick's odds 1.65+", "mina",
     "opis: STARO +3,4pp, NOVO −9,1pp — predznak skače", "K26"),
    ("pojas_135_145", "Pojas 1,35–1,45", "Odds band 1.35-1.45", "mina",
     "kandidat K5: STARO −5,0 / NOVO −7,4pp, naspram tržišta ~−9pp; prag još nije ispunjen", "K5"),
    ("pick_autsajder", "Pick je tržišni autsajder", "Our pick is the market underdog", "mina",
     "opis: kad model odstupi od tržišta, u prosjeku gubi (STARO: 'uvijek favorit' +12 pobjeda)", "K26"),
    ("tanki_elo", "Tanki ELO: razlika na podlozi < 50", "Thin surface-ELO gap (< 50)", "mina",
     "nije mjereno (točka 8: pick odlučen samo ELO-om)", "K26"),
    ("profil_t1_pick", "Pick: elitni povrat + slab servis, dvorana", "Our pick: elite return + weak serve, indoors",
     "mina", "otvoreno (točka 1, Cerúndolo); povijest ga ne može pošteno izmjeriti", "K26"),
    ("profil_t1_prot", "Protivnik: elitni povrat + slab servis, dvorana",
     "Opponent: elite return + weak serve, indoors", "prilika", "otvoreno (zrcalo točke 1)", "K26"),
    ("prot_domaci", "Protivnik je domaći", "Opponent is the home player", "prilika",
     "povijest: domaći su precijenjeni (−1,5pp, n=2.796)", "K26"),
    ("prot_susjed", "Protivnik je susjed (granica ili ≤ 600 km)", "Opponent from a neighbouring country",
     "prilika", "povijest: susjed kao autsajder −2,7pp (nije potvrđeno)", "K26"),
    ("pick_domaci", "Pick je domaći", "Our pick is the home player", "mina",
     "povijest: domaći su precijenjeni (−1,5pp)", "K26"),
    ("mladi_pick", "Pick 4+ god. mlađi (R128/R64 ili QF+)", "Our pick 4+ years younger (R128/R64 or QF+)",
     "mina", "opis: predznak se mijenja kroz ere", "K26"),
    ("ozljeda_pick", "Pick: prava vijest o ozljedi (v2)", "Our pick: real injury news (strict detector)",
     "mina", "opis (rijetko)", "K26"),
    ("ozljeda_prot", "Protivnik: prava vijest o ozljedi (v2)", "Opponent: real injury news (strict detector)",
     "prilika", "kandidat K13b", "K13b"),
    ("pauza_pick", "Pick se vraća nakon 21+ dan", "Our pick returns after 21+ days off", "mina",
     "kandidat K19", "K19"),
    ("pauza_prot", "Protivnik se vraća nakon 21+ dan", "Opponent returns after 21+ days off", "prilika",
     "kandidat K19", "K19"),
    ("nose_izbjegavaj", "Nose: IZBJEGAVAJ", "Nose: AVOID", "mina",
     "kandidat K24 (zasad u krivom smjeru: +3,7pp, n=17)", "K24"),
    ("nose_upozorenje", "Nose: UZ UPOZORENJE", "Nose: WITH WARNING", "mina", "kandidat K24", "K24"),
    ("nocna", "Noćna sesija", "Night session", "opis", "praćenje (od 05.10.: noć +0,1pp, dan −3,0pp)",
     "praćenje"),
]
# Razina dokaza na engleskom — za prompt analize gubitka, koji je na engleskom.
_EV_EN = {
    "novcic": "description: old era +3.4pp, new era -9.1pp - the sign flips",
    "pojas_135_145": "candidate K5: old -5.0 / new -7.4pp, about -9pp vs the market; threshold not met yet",
    "pick_autsajder": "description: when the model departs from the market it loses on average",
    "tanki_elo": "never measured (the user's point 8: a pick decided by ELO alone)",
    "profil_t1_pick": "open (the user's point 1, Cerundolo); history cannot measure it fairly",
    "profil_t1_prot": "open (mirror of the user's point 1)",
    "prot_domaci": "history: home players are overpriced (-1.5pp, n=2,796)",
    "prot_susjed": "history: a neighbour as underdog -2.7pp (not confirmed)",
    "pick_domaci": "history: home players are overpriced (-1.5pp)",
    "mladi_pick": "description: the sign flips between eras",
    "ozljeda_pick": "description (rare)",
    "ozljeda_prot": "candidate K13b",
    "pauza_pick": "candidate K19",
    "pauza_prot": "candidate K19",
    "nose_izbjegavaj": "candidate K24 (so far the wrong way: +3.7pp, n=17)",
    "nose_upozorenje": "candidate K24",
    "nocna": "tracking only",
}
INFO = {z[0]: {"oznaka": z[1], "label_en": z[2], "vrsta": z[3], "dokaz": z[4], "kapija": z[5],
               "ev_en": _EV_EN.get(z[0], "")} for z in ZNAKOVI}
K26_ZNAKOVI = [z[0] for z in ZNAKOVI if z[5] == "K26"]
_IKONA = {"mina": "⚠️", "prilika": "🟢", "opis": "ℹ️"}

# ------------------------------------------------------------------ geografija (kao LAB E-N, 01.11.2026)
# grad turnira (dio naziva iza " - ") -> (država IOC, lat, lon)
_GRADOVI = {
    "'s-Hertogenbosch": ("NED", 51.69, 5.30), "Acapulco": ("MEX", 16.85, -99.82),
    "Adelaide": ("AUS", -34.93, 138.60), "Almaty": ("KAZ", 43.24, 76.89), "Antwerp": ("BEL", 51.22, 4.40),
    "Astana": ("KAZ", 51.17, 71.45), "Athens": ("GRE", 37.98, 23.73), "Atlanta": ("USA", 33.75, -84.39),
    "Auckland": ("NZL", -36.85, 174.76), "Banja Luka": ("BIH", 44.77, 17.19), "Barcelona": ("ESP", 41.39, 2.17),
    "Basel": ("SUI", 47.56, 7.59), "Bastad": ("SWE", 56.43, 12.85), "Beijing": ("CHN", 39.90, 116.41),
    "Belgrade": ("SRB", 44.79, 20.45), "Bologna": ("ITA", 44.49, 11.34), "Brisbane": ("AUS", -27.47, 153.03),
    "Brussels": ("BEL", 50.85, 4.35), "Bucharest": ("ROU", 44.43, 26.10), "Buenos Aires": ("ARG", -34.60, -58.38),
    "Chengdu": ("CHN", 30.57, 104.07), "Cincinnati": ("USA", 39.10, -84.51), "Cordoba": ("ARG", -31.42, -64.18),
    "Dallas": ("USA", 32.78, -96.80), "Delray Beach": ("USA", 26.46, -80.07), "Doha": ("QAT", 25.29, 51.53),
    "Dubai": ("UAE", 25.20, 55.27), "Eastbourne": ("GBR", 50.77, 0.28), "Estoril": ("POR", 38.70, -9.40),
    "Florence": ("ITA", 43.77, 11.26), "Geneva": ("SUI", 46.20, 6.14), "Gijon": ("ESP", 43.53, -5.66),
    "Gstaad": ("SUI", 46.47, 7.29), "Halle": ("GER", 52.06, 8.36), "Hamburg": ("GER", 53.55, 9.99),
    "Hangzhou": ("CHN", 30.27, 120.15), "Hong Kong": ("HKG", 22.32, 114.17), "Houston": ("USA", 29.76, -95.37),
    "Indian Wells": ("USA", 33.72, -116.31), "Jeddah": ("KSA", 21.54, 39.17), "Kitzbuhel": ("AUT", 47.45, 12.39),
    "London": ("GBR", 51.51, -0.13), "Los Cabos": ("MEX", 22.89, -109.92), "Lyon": ("FRA", 45.76, 4.84),
    "Madrid": ("ESP", 40.42, -3.70), "Malaga": ("ESP", 36.72, -4.42), "Mallorca": ("ESP", 39.57, 2.65),
    "Marrakech": ("MAR", 31.63, -8.01), "Marseille": ("FRA", 43.30, 5.37), "Melbourne": ("AUS", -37.81, 144.96),
    "Metz": ("FRA", 49.12, 6.18), "Miami": ("USA", 25.76, -80.19), "Monte Carlo": ("MON", 43.74, 7.42),
    "Montpellier": ("FRA", 43.61, 3.88), "Montreal": ("CAN", 45.50, -73.57), "Munich": ("GER", 48.14, 11.58),
    "Napoli": ("ITA", 40.85, 14.27), "New York": ("USA", 40.71, -74.01), "Newport": ("USA", 41.49, -71.31),
    "Nur-Sultan": ("KAZ", 51.17, 71.45), "Paris": ("FRA", 48.86, 2.35), "Perth": ("AUS", -31.95, 115.86),
    "Pune": ("IND", 18.52, 73.86), "Queens Club": ("GBR", 51.49, -0.21), "Rio de Janeiro": ("BRA", -22.91, -43.17),
    "Rome": ("ITA", 41.90, 12.50), "Rotterdam": ("NED", 51.92, 4.48), "San Diego": ("USA", 32.72, -117.16),
    "Santiago": ("CHI", -33.45, -70.67), "Seoul": ("KOR", 37.57, 126.98), "Shanghai": ("CHN", 31.23, 121.47),
    "Sofia": ("BUL", 42.70, 23.32), "Stockholm": ("SWE", 59.33, 18.07), "Stuttgart": ("GER", 48.78, 9.18),
    "Sydney": ("AUS", -33.87, 151.21), "Tel Aviv": ("ISR", 32.09, 34.78), "Tokyo": ("JPN", 35.68, 139.69),
    "Toronto": ("CAN", 43.65, -79.38), "Turin": ("ITA", 45.07, 7.69), "Umag": ("CRO", 45.43, 13.52),
    "Vienna": ("AUT", 48.21, 16.37), "Washington": ("USA", 38.91, -77.04), "Winston-Salem": ("USA", 36.10, -80.24),
    "Zhuhai": ("CHN", 22.27, 113.58),
}
_CAPITAL = {  # IOC -> glavni grad (lat, lon)
    "USA": (38.90, -77.04), "FRA": (48.86, 2.35), "ITA": (41.90, 12.50), "ESP": (40.42, -3.70),
    "ARG": (-34.60, -58.38), "AUS": (-35.28, 149.13), "RUS": (55.76, 37.62), "GER": (52.52, 13.40),
    "SRB": (44.79, 20.45), "GBR": (51.51, -0.13), "CAN": (45.42, -75.70), "CZE": (50.08, 14.44),
    "NED": (52.37, 4.90), "CHI": (-33.45, -70.67), "KAZ": (51.17, 71.45), "JPN": (35.68, 139.69),
    "BEL": (50.85, 4.35), "CHN": (39.90, 116.41), "HUN": (47.50, 19.04), "POL": (52.23, 21.01),
    "CRO": (45.81, 15.98), "GRE": (37.98, 23.73), "POR": (38.72, -9.14), "NOR": (59.91, 10.75),
    "SUI": (46.95, 7.45), "AUT": (48.21, 16.37), "BRA": (-15.79, -47.88), "DEN": (55.68, 12.57),
    "BUL": (42.70, 23.32), "FIN": (60.17, 24.94), "SVK": (48.15, 17.11), "SWE": (59.33, 18.07),
    "PER": (-12.05, -77.04), "COL": (4.71, -74.07), "BIH": (43.86, 18.41), "BLR": (53.90, 27.57),
    "GEO": (41.72, 44.79), "KOR": (37.57, 126.98), "RSA": (-25.75, 28.19), "MON": (43.74, 7.42),
    "BOL": (-16.50, -68.15), "MDA": (47.01, 28.86), "TPE": (25.03, 121.57), "IND": (28.61, 77.21),
    "LTU": (54.69, 25.28), "HKG": (22.32, 114.17), "PAR": (-25.26, -57.58), "MEX": (19.43, -99.13),
    "ECU": (-0.18, -78.47), "UKR": (50.45, 30.52), "JOR": (31.95, 35.93), "SLO": (46.06, 14.51),
    "MAR": (34.02, -6.84), "LBN": (33.89, 35.50), "TUN": (36.81, 10.18), "URU": (-34.90, -56.16),
    "TUR": (39.93, 32.86), "EST": (59.44, 24.75), "ROU": (44.43, 26.10), "NZL": (-41.29, 174.78),
    "ISR": (31.77, 35.21), "UZB": (41.30, 69.24), "DOM": (18.49, -69.93), "BAR": (13.10, -59.62),
    "ZIM": (-17.83, 31.05), "THA": (13.76, 100.50), "LUX": (49.61, 6.13), "QAT": (25.29, 51.53),
    "LAT": (56.95, 24.11), "CYP": (35.19, 33.38), "MNE": (42.44, 19.26), "MKD": (41.99, 21.43),
    "ALB": (41.33, 19.82), "IRL": (53.35, -6.26), "ARM": (40.18, 44.51), "AZE": (40.41, 49.87),
    "EGY": (30.04, 31.24), "KSA": (24.71, 46.68), "UAE": (24.45, 54.38), "VEN": (10.49, -66.88),
    "PHI": (14.60, 120.98), "INA": (-6.21, 106.85), "MAS": (3.14, 101.69), "SGP": (1.35, 103.82),
    "VIE": (21.03, 105.85), "PAK": (33.68, 73.05), "IRI": (35.69, 51.39), "CUB": (23.11, -82.37),
    "PUR": (18.47, -66.11), "ESA": (13.69, -89.19), "GUA": (14.63, -90.51), "CRC": (9.93, -84.08),
    "BAH": (25.04, -77.35), "JAM": (18.02, -76.80), "TRI": (10.66, -61.51), "NGR": (9.08, 7.40),
    "KEN": (-1.29, 36.82), "MLT": (35.90, 14.51), "AND": (42.51, 1.52), "SMR": (43.94, 12.45),
    "LIE": (47.14, 9.52), "ISL": (64.15, -21.94), "KGZ": (42.87, 74.59), "TJK": (38.56, 68.77),
}
_BORDERS = {  # država domaćin -> države s kopnenom granicom (IOC)
    "NED": {"BEL", "GER"}, "MEX": {"USA", "GUA", "BIZ"}, "AUS": set(), "NZL": set(), "JPN": set(),
    "KAZ": {"RUS", "CHN", "KGZ", "UZB", "TKM"}, "BEL": {"FRA", "LUX", "GER", "NED"},
    "GRE": {"ALB", "MKD", "BUL", "TUR"}, "USA": {"CAN", "MEX"}, "BIH": {"CRO", "SRB", "MNE"},
    "ESP": {"POR", "FRA", "AND"}, "SUI": {"GER", "FRA", "ITA", "AUT", "LIE"}, "SWE": {"NOR", "FIN"},
    "CHN": {"KAZ", "KGZ", "TJK", "AFG", "PAK", "IND", "NEP", "BHU", "MYA", "LAO", "VIE", "PRK", "MGL", "RUS", "HKG"},
    "SRB": {"HUN", "ROU", "BUL", "MKD", "MNE", "BIH", "CRO"}, "ROU": {"HUN", "SRB", "BUL", "MDA", "UKR"},
    "ARG": {"CHI", "BOL", "PAR", "BRA", "URU"}, "CHI": {"ARG", "PER", "BOL"}, "QAT": {"KSA"},
    "UAE": {"KSA", "OMA"}, "GBR": {"IRL"}, "POR": {"ESP"}, "ITA": {"FRA", "SUI", "AUT", "SLO", "SMR"},
    "GER": {"DEN", "POL", "CZE", "AUT", "SUI", "FRA", "LUX", "BEL", "NED"}, "HKG": {"CHN"},
    "MAR": {"ALG"}, "FRA": {"BEL", "LUX", "GER", "SUI", "ITA", "MON", "ESP", "AND"}, "MON": {"FRA"},
    "CAN": {"USA"}, "IND": {"PAK", "CHN", "NEP", "BHU", "BAN", "MYA"},
    "BRA": {"ARG", "URU", "PAR", "BOL", "PER", "COL", "VEN", "GUY", "SUR"}, "KOR": {"PRK"},
    "BUL": {"ROU", "SRB", "MKD", "GRE", "TUR"}, "ISR": {"LBN", "SYR", "JOR", "EGY"},
    "AUT": {"GER", "CZE", "SVK", "HUN", "SLO", "ITA", "SUI", "LIE"}, "CRO": {"SLO", "HUN", "SRB", "BIH", "MNE"},
    "KSA": {"JOR", "IRQ", "KUW", "QAT", "UAE", "OMA", "YEM"},
}
_IOC_FIX = {"PRT": "POR"}


def _letters(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s.lower())


_GRAD_KLJUC = {_letters(k): v for k, v in _GRADOVI.items()}


def host(tournament: str):
    """(država IOC, lat, lon) grada turnira ("Erste Bank Open - Vienna" -> AUT) ili None."""
    t = str(tournament or "")
    if " - " not in t:
        return None
    return _GRAD_KLJUC.get(_letters(t.rsplit(" - ", 1)[1]))


def _km(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def _num(v):
    if isinstance(v, bool) or v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else x


def devig(o_pick, o_opp):
    o1, o2 = _num(o_pick), _num(o_opp)
    if not (o1 and o2 and o1 > 1 and o2 > 1):
        return None
    return (1 / o1) / (1 / o1 + 1 / o2)


def _ioc(v):
    v = str(v or "").strip().upper()
    return _IOC_FIX.get(v, v) or None


def _hr(x: float, d: int = 2) -> str:
    """Broj s decimalnim zarezom za hrvatski prikaz (1,70 a ne 1.70)."""
    return f"{x:.{d}f}".replace(".", ",")


# ------------------------------------------------------------------ ulazi
def rec_from_pred(pred: dict) -> dict:
    """Predikcija dnevnog runa (pred["match"], pred["context_snapshot"])."""
    m = pred.get("match") or {}
    return {"pick": pred.get("pick") or "", "p1": m.get("player1") or "", "p2": m.get("player2") or "",
            "odds_p1": m.get("odds_p1"), "odds_p2": m.get("odds_p2"), "surface": m.get("surface") or "",
            "tournament": m.get("tournament") or "", "round": m.get("round") or "",
            "cs": pred.get("context_snapshot") or {}}


def rec_from_row(row: dict) -> dict:
    """Redak `analyzed_matches` s punim `context_snapshot`."""
    return {"pick": row.get("predicted_winner") or "", "p1": row.get("player1") or "",
            "p2": row.get("player2") or "", "odds_p1": row.get("bookmaker_odds_p1"),
            "odds_p2": row.get("bookmaker_odds_p2"), "surface": row.get("surface") or "",
            "tournament": row.get("tournament") or "", "round": row.get("round") or "",
            "cs": row.get("context_snapshot") or {}}


def rec_from_flat(row: dict) -> dict:
    """Redak iz `supabase_client.get_rows_for_nos_ploca` (samo potrebna polja snapshota)."""
    cs = {"p1_nationality": row.get("n1"), "p2_nationality": row.get("n2"),
          "p1_elo_surface": row.get("es1"), "p2_elo_surface": row.get("es2"),
          "p1_return_won": row.get("r1"), "p2_return_won": row.get("r2"),
          "p1_serve_pts_won": row.get("s1"), "p2_serve_pts_won": row.get("s2"),
          "p1_age": row.get("age1"), "p2_age": row.get("age2"),
          "p1_days_rest": row.get("rest1"), "p2_days_rest": row.get("rest2"),
          "session": row.get("ses"), "nose": row.get("nose")}
    if row.get("inj1") is not None:
        cs["p1_gnews"] = {"injury_n2": row.get("inj1")}
    if row.get("inj2") is not None:
        cs["p2_gnews"] = {"injury_n2": row.get("inj2")}
    rec = rec_from_row({**row, "context_snapshot": cs})
    return rec


# ------------------------------------------------------------------ znakovi
def compute(rec: dict) -> dict:
    """Znakovi za NAŠ pick. {"version", "znakovi": [id], "detalji": {id: tekst}, "nedostaje": [id]}.
    Nikad ne baca — greška je {"version", "error"} (sjena ne smije srušiti run)."""
    try:
        cs = rec.get("cs") or {}
        pick, p1, p2 = rec.get("pick") or "", rec.get("p1") or "", rec.get("p2") or ""
        if not pick or pick not in (p1, p2):
            return {"version": VERSION, "error": "nema picka"}
        a, b = ("p1", "p2") if pick == p1 else ("p2", "p1")
        o1, o2 = _num(rec.get("odds_p1")), _num(rec.get("odds_p2"))
        op, oo = (o1, o2) if a == "p1" else (o2, o1)
        out, det, miss = [], {}, []

        def put(sid, cond, detail=""):
            if cond is None:
                miss.append(sid)
            elif cond:
                out.append(sid)
                det[sid] = detail

        # 1–3 cijena (kvota sa screenshota)
        put("novcic", (op >= ODDS_COIN) if op else None, f"kvota {_hr(op)}" if op else "")
        put("pojas_135_145", (BAND[0] <= op < BAND[1]) if op else None, f"kvota {_hr(op)}" if op else "")
        p_dev = devig(op, oo)
        put("pick_autsajder", (p_dev < 0.5) if p_dev is not None else None,
            f"cijena {100 * p_dev:.0f}%" if p_dev is not None else "")
        # 4 tanki ELO (1500 je zadana vrijednost, ne podatak — tihi null)
        ea, eb = _num(cs.get(f"{a}_elo_surface")), _num(cs.get(f"{b}_elo_surface"))
        ok_elo = ea is not None and eb is not None and 1500.0 not in (ea, eb)
        put("tanki_elo", (abs(ea - eb) < ELO_THIN) if ok_elo else None,
            f"ELO {ea:.0f} naspram {eb:.0f}" if ok_elo else "")
        # 5–6 profil iz točke 1 (samo dvorana)
        indoor = "indoor" in str(rec.get("surface") or "").lower()
        for sid, x in (("profil_t1_pick", a), ("profil_t1_prot", b)):
            r_, s_ = _num(cs.get(f"{x}_return_won")), _num(cs.get(f"{x}_serve_pts_won"))
            if not indoor:
                put(sid, False)
            elif r_ is None or s_ is None or r_ <= 0 or s_ <= 0:
                put(sid, None)
            else:
                put(sid, r_ >= RET_P90 and s_ <= SERVE_P10, f"povrat {_hr(r_, 1)}%, servis {_hr(s_, 1)}%")
        # 7–9 domaći i susjed
        h = host(rec.get("tournament"))
        na, nb = _ioc(cs.get(f"{a}_nationality")), _ioc(cs.get(f"{b}_nationality"))
        if h is None:
            for sid in ("prot_domaci", "prot_susjed", "pick_domaci"):
                put(sid, None)
        else:
            hc = h[0]
            put("prot_domaci", (nb == hc) if nb else None, f"{nb} na turniru u {hc}" if nb else "")
            put("pick_domaci", (na == hc) if na else None, f"{na} na turniru u {hc}" if na else "")
            if nb:
                nbr = nb != hc and (nb in _BORDERS.get(hc, set())
                                    or (nb in _CAPITAL and _km(_CAPITAL[nb], h[1:]) <= NEIGHBOUR_KM))
                put("prot_susjed", nbr, f"{nb} uz {hc}")
            else:
                put("prot_susjed", None)
        # 10 mlađi pick u prvom kolu Mastersa/GS ili od QF
        ga, gb = _num(cs.get(f"{a}_age")), _num(cs.get(f"{b}_age"))
        rnd = str(rec.get("round") or "").strip().upper()
        if ga is None or gb is None or not rnd:
            put("mladi_pick", None)
        else:
            put("mladi_pick", (gb - ga >= AGE_GAP) and rnd in ("R128", "R64", "QF", "SF", "F"),
                f"{ga:.0f} naspram {gb:.0f} god., {rnd}")
        # 11–12 prava ozljeda (strogi detektor v2; bez v2 zapisa = nedostaje)
        for sid, x in (("ozljeda_pick", a), ("ozljeda_prot", b)):
            g = cs.get(f"{x}_gnews")
            v = _num(g.get("injury_n2")) if isinstance(g, dict) and "injury_n2" in g else None
            # 08.11.2026 (revizija, ideja 6): uz broj i SAM naslov, da se oznaka može provjeriti (od danas
            # se spremaju svi označeni naslovi, `inj_items`). Definicija znaka (v2) se NE mijenja.
            naslov = next((it.get("t") for it in (g.get("inj_items") or []) if it.get("inj2")),
                          None) if isinstance(g, dict) else None
            put(sid, (v >= 1) if v is not None else None,
                (f"{v:.0f} naslova" + (f": „{str(naslov)[:90]}“" if naslov else "")) if v else "")
        # 13–14 pauza 21+ dan
        for sid, x in (("pauza_pick", a), ("pauza_prot", b)):
            d = _num(cs.get(f"{x}_days_rest"))
            put(sid, (d >= PAUSE_DAYS) if d is not None else None, f"{d:.0f} dana" if d is not None else "")
        # 15–16 Nose
        nz = cs.get("nose")
        suit = (nz.get("ticket_suitability") if isinstance(nz, dict) and not nz.get("error")
                else (nz if isinstance(nz, str) else None))
        put("nose_izbjegavaj", (suit == "IZBJEGAVAJ") if suit else None)
        put("nose_upozorenje", (suit == "UZ UPOZORENJE") if suit else None)
        # 17 noćna sesija
        ses = cs.get("session")
        put("nocna", (ses == "night") if ses else None)
        return {"version": VERSION, "znakovi": out, "detalji": det, "nedostaje": miss}
    except Exception as e:  # noqa: BLE001 — sjena nikad ne smije srušiti run
        return {"version": VERSION, "error": str(e)[:120]}


def board_for_row(row: dict) -> dict:
    """Spremljena ploča (ako je iz ove verzije) ili izračunata iz snapshota (OPIS za stare analize)."""
    cs = row.get("context_snapshot") or {}
    st = cs.get("nos_ploca") if isinstance(cs, dict) else None
    if isinstance(st, dict) and st.get("version") == VERSION and not st.get("error"):
        return {**st, "spremljeno": True}
    b = compute(rec_from_row(row))
    b["spremljeno"] = False
    return b


def board_for_pick(row: dict, pick: str) -> dict:
    """Ploča za zadani pick (npr. nogu tiketa). Ponovna analiza istog para zna okrenuti stranu
    (Hanfmann -> Struff, revizija 01.11.2026), pa spremljena ploča vrijedi samo za isti pick."""
    if not pick or (row.get("predicted_winner") or "") == pick:
        return board_for_row(row)
    rec = rec_from_row(row)
    rec["pick"] = pick
    b = compute(rec)
    b["spremljeno"] = False
    return b


def rows_with_boards(flat_rows: list) -> list:
    """Retci iz `get_rows_for_nos_ploca` -> [{"znakovi", "win", "p", "date", "created"}] za `tally`
    (riješeni, s obje kvote, bez analiza s tuđim ELO-om)."""
    out = []
    for r in flat_rows or []:
        if str(r.get("elos") or "").lower() == "true" or r.get("prediction_correct") is None:
            continue
        st = r.get("nos")
        b = (st if isinstance(st, dict) and st.get("version") == VERSION and not st.get("error")
             else compute(rec_from_flat(r)))
        if b.get("error"):
            continue
        pick, p1 = r.get("predicted_winner"), r.get("player1")
        o_p, o_o = ((r.get("bookmaker_odds_p1"), r.get("bookmaker_odds_p2")) if pick == p1
                    else (r.get("bookmaker_odds_p2"), r.get("bookmaker_odds_p1")))
        p = devig(o_p, o_o)
        if p is None:
            continue
        out.append({"znakovi": b.get("znakovi") or [], "win": 1.0 if r["prediction_correct"] else 0.0,
                    "p": p, "date": str(r.get("match_date") or "")[:10], "created": str(r.get("created_at") or ""),
                    "spremljeno": isinstance(st, dict) and st.get("version") == VERSION})
    return out


# ------------------------------------------------------------------ bilanca znakova
_BANDS = (0.55, 0.65, 0.75, 0.85)      # pojasevi cijene kao u K24 (nose.gate_status)


def _band(p: float) -> int:
    return sum(1 for x in _BANDS if p >= x)


# Znakovi koji su SAMI definirani cijenom: za njih "u istom pojasu cijene" nema smisla (usporedba bi
# bila s pickovima koji u taj pojas jedva ulaze — skeptik 01.11.2026, D8; novčić je tako izgledao
# +15,5pp). Za njih vrijede edge naspram cijene i CLV.
PRICE_SIGNS = {"novcic", "pojas_135_145", "pick_autsajder"}


def tally(rows: list) -> dict:
    """rows: [{"znakovi": [...], "win": 0/1, "p": devig cijena picka}] -> po znaku: n, pobjede,
    edge (pp) i razlika naspram ostalih pickova u ISTOM pojasu cijene (pp; None za PRICE_SIGNS)."""
    by_band = {}
    for r in rows:
        by_band.setdefault(_band(r["p"]), []).append(r)
    out = {}
    for sid in INFO:
        fl = [r for r in rows if sid in r["znakovi"]]
        if not fl:
            out[sid] = {"n": 0, "w": 0, "edge": None, "band_diff": None}
            continue
        n = len(fl)
        e = 100 * (sum(r["win"] for r in fl) - sum(r["p"] for r in fl)) / n
        d = []
        if sid not in PRICE_SIGNS:
            for r in fl:
                oth = [x for x in by_band.get(_band(r["p"]), []) if sid not in x["znakovi"]]
                if oth:
                    d.append((r["win"] - r["p"]) - sum(x["win"] - x["p"] for x in oth) / len(oth))
        out[sid] = {"n": n, "w": int(sum(r["win"] for r in fl)), "edge": e,
                    "band_diff": (100 * sum(d) / len(d)) if d else None}
    return out


# ------------------------------------------------------------------ prikaz
def opis(board: dict) -> str:
    """Kratak redak za Dnevni listić (hrvatski), s razinom dokaza uz svaki znak."""
    if not board or board.get("error"):
        return "🐽 Nos-ploča: nije izračunata" + (f" ({board.get('error')})" if board else "")
    z = board.get("znakovi") or []
    if not z:
        return "🐽 Nos-ploča (u sjeni — model je ne vidi, tiket je ne koristi): nijedan znak nije upaljen."
    parts = []
    for sid in z:
        i = INFO.get(sid)
        if not i:
            continue
        d = (board.get("detalji") or {}).get(sid)
        parts.append(f"{_IKONA[i['vrsta']]} {i['oznaka']}" + (f" ({d})" if d else "") + f" [{i['dokaz']}]")
    return "🐽 Nos-ploča (u sjeni — model je ne vidi, tiket je ne koristi): " + " · ".join(parts)
