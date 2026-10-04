# Revizija 04.10.2026 — pragovi zapisani PRIJE računanja

Zapisano **04.10.2026 17:54**. Pravilo kapije (06.09.2026): prag se ne mijenja nakon gledanja
rezultata. Ovaj dokument se nakon računanja NE uređuje; izvještaj ga samo citira.

**Što je viđeno prije ovog zapisa (iskreno):** (1) zbirni broj novog uzorka: 35 od 57,
edge −4,5pp, ravni ROI −14,5%; (2) ispis `scripts/measure_candidates.py` (K5, K10, K11, K13,
K17–K20, KONS) — ti kandidati ionako imaju pragove zapisane ranije u DECISION_INPUTS;
(3) popunjenost polja (bez ishoda). Ništa drugo od ishoda nije gledano.

## Uzorci

| oznaka | što | n |
|---|---|---|
| NOVO | analize nastale nakon revizije 26.09.2026 20:08, riješene, s obje SuperSport kvote; sve u eri `bccf4742`, runde ručne | 57 |
| STARO | sve ranije riješene analize s obje kvote | ~466 |
| LAB | povijesni laboratorij: tennis-data + TML, ATP 2022 – 13.09.2026, poštena cijena (Pinnacle, inače prosjek kladionica) | ~12.300 |

Snaga (`snaga.py`): n=57 → interval ±12,4pp; n=28 → ±17,7pp; n=14 → ±25pp; n≈520 → ±4,3pp.
**Na samom NOVOM uzorku ne može se ništa dokazati** — služi kao provjera smjera (isti
predznak) i za opis pojedinačnih mečeva.

## Mjere

- **edge** = stvarni postotak pobjeda − prosjek devigirane cijene (SuperSport za naše
  pickove, poštena cijena u LAB-u), u pp, uz 95% interval (sd/√n).
- **ROI** po SuperSport kvoti (ravni ulog).
- **Poeni (novo):** udio osvojenih poena našeg picka (`totalPointsWon`, poravnato po ID-u).
  - *Očekivani udio za danu cijenu* baždari se u LAB-u: Bo3/Bo5 odvojeno, po pojasu
    poštene cijene.
  - *Ostatak poena* = stvarni udio − očekivani.
  - *Zasluženi edge* = prosjek P(pobjeda | udio poena) − cijena, gdje se P(pobjeda | udio)
    također baždari u LAB-u. Mjeri je li pick "bio dobar" neovisno o sreći u ključnim
    poenima.
  - Provjera baždarenja (mora vrijediti prije upotrebe): u LAB-u prosjek zasluženog edgea po
    pojasu cijene unutar ±1pp od nule.
- **Klasifikacija meča:**
  - poraz s ostatkom poena ≥ 0 ili osvojenih ≥ 48% poena = "tijesno / nesreća";
  - poraz inače = "nadigran";
  - pobjeda s ostatkom < 0 i < 52% poena = "sretna";
  - predaja = zasebno.

## A. Dijagnoza NOVOG uzorka (opis, bez praga)

Edge i ROI po turniru, razini, pojasu kvote, rundi, sesiji (dan/noć), pouzdanosti, i je li pick
tržišni favorit. Tiketi: očekivana vjerojatnost (umnožak devigiranih cijena nogu) naspram
ishoda; vjerojatnost da 0 od N padne slučajno.

**A2 — sreća ili čitanje (zapisano unaprijed):** ako interval zasluženog edgea NOVOG uzorka
sadrži nulu, a W/L edge je negativan → "manjak je pretežno varijanca". Ako je cijeli interval
ispod nule → "nadigrani smo, ne samo nesretni".

## B. Kandidati koji su na redu (pragovi iz DECISION_INPUTS, prepisani doslovno)

| kandidat | prag |
|---|---|
| K1 | skupina pouzdanosti 60–63 u eri `bccf4742`: edge < 0 uz n ≥ 25 → prag natrag na 63 |
| K1b | pojas 65–68 (kazna −5pp): opis po pouzdanosti PRIJE i POSLIJE kazne (prag nije zapisan — samo opis) |
| K9 | duljina "Own read" (pobjede − porazi) negativna uz n ≥ 60 i razlika ≥ 40 znakova; obavezno i uz kontrolu cijene |
| K10 | od 14.09., n ≥ 25 po pojasu: 1,35–1,65 < 0 i (1,20–1,35 > 0 ili 1,65–1,85 > 0) → potvrda; 1,35–1,65 ≥ 0 uz n ≥ 25 → PAO |
| K11 | od 14.09., runda poznata: R16+QF ostatak ≤ −5pp uz n ≥ 20 I razlika naspram ostalih negativna → potvrda; predznak se okrene → odbaciti i zatvoriti |
| K5, K13, K17, K18, K19, K20, KONS | samo stanje (pragovi u `measure_candidates.py`) |

## C. Varijable s korisnikova popisa — LAB naspram tržišta

Sve iz mečeva PRIJE ovog meča (TML), prozor 365 dana. Za svaki meč igrač s boljom
vrijednošću; edge = pobjeda − poštena cijena tog igrača. Uz to tercile razlike i r(razlika, ostatak).

| oznaka | varijabla | uvjet | smjer |
|---|---|---|---|
| C1 | forma: % pobjeda u zadnjih 10 mečeva (sve razine) | oba ≥ 5 mečeva | + |
| C2 | podloga: % pobjeda na podlozi meča, 365 dana | oba ≥ 5 na podlozi | + |
| C3 | hold %: osvojeni servis-gemovi | oba ≥ 30 servis-gemova | + |
| C4 | break %: osvojeni gemovi na returnu | oba ≥ 30 return-gemova | + |
| C5 | asovi po servisnom poenu | oba ≥ 300 servisnih poena | + |
| C6 | dvostruke greške po servisnom poenu (manje = bolje) | oba ≥ 300 servisnih poena | + |
| C7 | H2H: više pobjeda u ranijim međusobnim mečevima | ≥ 2 meča, razlika ≠ 0 | + |
| C8 | rang bolji, a igrač je tržišni autsajder | rang oba poznat | + |
| C9 | umor: manje setova odigranih ranije na ISTOM turniru | razlika ≥ 1 set | + |

## D. Kombinacije — LAB naspram tržišta (unaprijed odabrane, svaka s mehanizmom)

| oznaka | ćelija (igrač iz ćelije) | smjer |
|---|---|---|
| D1 | "vruć autsajder": forma ≥ 20pp bolja (2+ pobjede od 10), tržišni autsajder | + |
| D2 | server na brzom: hold ≥ 5pp bolji, trava ili dvorana (hard indoor) | + |
| D3 | returner na zemlji: break ≥ 5pp bolji, zemlja | + |
| D4 | H2H vođa kao autsajder: ≥ 3 meča, razlika pobjeda ≥ 2, tržišni autsajder | + |
| D5 | umoran u završnici: QF/SF/F, ≥ 2 seta više ranije na turniru | − |
| D6 | "kvalitetne pobjede" kao autsajder: više pobjeda nad top-20 u 365 dana, tržišni autsajder | + |
| D8 | specijalist podloge kao autsajder: (podloga − ukupno) ≥ +10pp, protivnik < +10pp, autsajder | + |
| D9 | asovi u dvorani: ≥ 3 asa na 100 servisnih poena više, dvorana | + |

**Kriteriji za C i D (isti kao povijesni lab 27.09.):**
- **PROLAZI:** |edge| ≥ 2pp, 95% interval ne prelazi nulu, isti predznak u obje polovice
  (P1 = 2022–23, P2 = 2024–26), smjer kao gore.
- **SLAB:** isto, ali |edge| < 2pp.
- **PADA:** sve ostalo.

Holm korekcija preko 17 testova (informativno). Prolaz u LAB-u je predprovjera, ne odluka.

## E. "Intuicija" agenta — naš korpus (STARO + NOVO)

- **E1:** odmak od tržišta d = pouzdanost − 100·cijena.
  - "Intuicija nosi informaciju" ako r(d, ostatak) ≥ +0,10 s intervalom iznad nule na STARO
    I isti predznak na NOVO.
  - Inače "ne nosi". Isto i s ostatkom poena (E2).
- **E3:** razlozi u "Own read" i analizi NOVIH mečeva (umor, rejting, forma, servis, povijest
  turnira, uvjeti/teren, stil, tržište). Samo opis i hipoteze, bez praga (n premalen).
- **E4:** `market_check` popunjen (model se odmaknuo 10pp+ i obrazložio) naspram ne. Opis.

## F. Ista lista na našem korpusu (uz kontrolu cijene)

r(razlika pick − protivnik, ostatak) i edge gornje/donje trećine za: sesiju, hold, return,
asove, 1. servis, BP spašene/iskorištene, formu 10, formu × kvalitetu, podlogu, rang, ELO,
scouting (ima profil / razina), H2H (iz TML-a), dane odmora, setove u 7 dana i dob.

**"Zanimljivo"** = |r| ≥ 0,10, interval ne prelazi nulu na STARO+NOVO, i isti predznak na
STARO i NOVO; Holm preko svih F testova. Bez novih kombinacija na korpusu: revizija 26.09.
testirala je 276 parova (0 preživjelo). Ponavljanje s +57 mečeva (+12%) ne može promijeniti
taj zaključak.

## G. Analize gubitaka (stranica)

Noge tiketa izgubljene nakon popravka 26.09.2026 20:28. Provjera činjenica (kvota, runda,
status tiketa) i usporedba okrivljenog uzroka s klasifikacijom iz poena.

**"Popravak radi"** ako ≥ 80% analiza nema činjeničnu grešku (prije: 5 od 20 bez greške).

## H. Scouting (Excel top 150 i tablica)

Pokrivenost igrača NOVOG uzorka, starost profila, edge s profilom i bez (uz kontrolu cijene),
po razini profila, stanje K17.

**Preporuka za dopunu samo ako:**
- mečevi bez profila idu ≥ 5pp lošije uz interval koji ne prelazi nulu, ILI
- neka razina profila nosi informaciju povrh cijene i ponavlja se u obje polovice.

Inače se Excel ne širi radi predviđanja.

## Dodatak 04.10.2026 18:07 — jedna hipoteza nastala NAKON čitanja poraza (ne prije)

Čitanjem 22 poraza NOVOG uzorka uočeno je da su u Tokiju tri igrača koji su već dobivali na
turniru (Vacherot, Munar, Jacquet) srušila naše favorite 8 puta. Model je u više tih analiza
umor protivnika navodio kao prednost svog picka. Hipoteza je dakle **iz podataka**, pa se ne smije
potvrditi na njima; testira se samo na LAB-u (12.300 mečeva do 13.09.2026, Tokio 2026 nije
unutra), s istim kriterijem kao C/D. Holm sada preko 18 testova.

| oznaka | ćelija (igrač iz ćelije) | smjer |
|---|---|---|
| D10 | "zalet na turniru": tržišni autsajder koji je na OVOM turniru (glavni ždrijeb + kvalifikacije) već dobio barem 2 meča više od favorita | + |

Usput (opis, bez praga): ELO podudaranje imena — "Jaume Antoni Munar Clar" dobiva ELO
igrača "Jay Clarke" (1397 umjesto 1748). To je kvar podataka, ne nalaz; ide u izvještaj kao
popravak na odobrenje.
