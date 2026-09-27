# Povijesni laboratorij — izvještaj 27.09.2026 11:45

Pragovi su zapisani **prije** računanja (`PRAGOVI_POVIJESNI_LAB.md`, 11:33) i nisu mijenjani.
Ništa iz ovog izvještaja nije ugrađeno u model ni u tiket; sve preporuke čekaju tvoju odluku.

## Sažetak jednostavnim jezikom

1. **Nijedan naš kandidat ne pobjeđuje tržište na 12.324 ATP meča (2022–2026).** Pobjede u
   sezoni, povijest na turniru, zajednički protivnici, GS iskustvo, pauza, domaći teren, runda,
   razina turnira, statistika s turnira: kladionice sve to već ugrade u kvotu. Kad se pogleda
   što tvrdi naš mali uzorak (30–450 mečeva) i što kaže 12.000 mečeva, veliki uzorak svaki put
   kaže "nula ili sitno".
2. **Naša "rupa" na kvotama 1,35–1,60 nije svojstvo tržišta.** Naprotiv: favoriti na
   1,35–1,43 kod kladionica prolaze **bolje** od cijene (+3,7pp). Ako mi ondje gubimo, to je
   naš izbor pickova ili slučajnost — a spuštanje oprezne zone (K5) rezalo bi pojas koji je
   inače dobar.
3. **Grand Slam favoriti na 1,30–1,50 su potcijenjeni (+4,3pp)** — suprotno od naše hipoteze
   K3 (koja je htjela kazniti baš njih).
4. **Konsenzus kladionica radi u pravom smjeru, ali je učinak mali** — otprilike koliko je
   razlika u cijeni (2–3pp), ne +10pp kako je pokazao naš mali uzorak. Da bi oklada bila u plusu,
   razlika mora biti veća od marže.
5. **Naši pickovi u prosjeku gube maržu:** po SuperSport kvoti i zatvornoj tržišnoj cijeni EV je
   **−5,3%** po picku (samo 10% pickova ima pozitivan EV); noge pravih tiketa **−3,1%**. Na tiketu
   od 4 noge to je oko −12% očekivano po tiketu. Naši pickovi su **točni koliko i tržište**
   (+1,5pp, interval od −2,9 do +5,9) — nemamo znanje koje tržište nema.
6. **SuperSport nije lošiji od prosjeka:** marža 5,2% naspram 6,25% prosjeka kladionica na istim
   mečevima; kvota našeg picka jednaka je prosjeku (medijan omjera 1,000). Na ATP 250 marža je
   nešto viša (5,9%).

**Što iz toga slijedi (preporuke, ne odluke):** (a) zatvoriti K15, K16 i K3, ne uvoditi K5 na
temelju malog uzorka; (b) izbaciti pravilo 11 (kazna kad je protivnik domaći) i prosjek
statistike s turnira (K12) iz prompta uz sljedeću izmjenu prompta; (c) najveća poluga za ROI nije
nova varijabla nego **struktura oklade**: manje nogu i samo pickovi s jasnom prednošću u cijeni.
To je tvoja odluka (vidi "ČEKA" u BACKLOG-u).

## Podaci

| izvor | što | količina |
|---|---|---|
| tennis-data.co.uk (ručno skinuto) | ATP 2022 – 13.09.2026, kvote pred početak meča | 12.360 odigranih mečeva s cijenom |
| TML (stats.tennismylife.org) | glavni ždrijeb 2000–2026, Challengeri i kval. 2020–2026 | spojeno 12.327 (99,7%) |
| naša baza | razriješene analize s pickom, noge pravih tiketa | 417 analiza i 211 nogu spojeno |

Poštena cijena: Pinnacle bez marže (10.216 mečeva, do ~rujna 2025), inače prosjek kladionica bez
marže (2.144, uglavnom 2026. — Pinnacle je te godine praktički nestao iz datoteka). Sve presude
iste su i kad se koristi samo prosjek kladionica (robusnost, `lab_tests.py --avg`).

**Zamka nađena usput (11:40):** u TML-u za 2026. polje "datum turnira" nosi datum MEČA (74%
turnira). Popravljeno u učitavanju prije ijednog testa; bez toga bi se GS polufinale istog Slama
brojilo kao "ranije" (Zverev 13 umjesto 12). Provjera spajanja: runda QF/SF/F/RR slaže se u
2.048 od 2.053 meča.

## Pitanje 1 — naši mečevi naspram zatvorne tržišne cijene (dijagnoza)

    marža na istim mečevima          SuperSport 5,21%   prosjek kladionica 6,25%
    EV našeg picka po SS kvoti       −5,3%  [−6,0, −4,6]   n=417   (EV > 0 u 10%)
    edge naspram zatvorne cijene     +1,5pp [−2,9, +5,9]
    edge naspram devig SuperSporta   +1,1pp [−3,3, +5,5]
    ROI po picku (SS kvota)          −3,2%  [−10,3, +3,9]
    noge pravih tiketa               EV −3,1% [−4,3, −1,9]   n=211   (EV > 0 u 22%)

    po razini:  ATP 250 n=95 marža 5,92% EV −5,7% | Masters n=166 EV −5,2% |
                Grand Slam n=144 EV −5,2% | ATP 500 n=12 (premalo)

KONS na zatvornoj cijeni (gap = zatvorna poštena − devig SuperSport za naš pick; ograda: to je
zatvorna, a ne jutarnja cijena, pa je ovo gornja granica):

    gap ≥ +1pp   n=106   gap +2,9pp   edge naspram SS +1,8pp [−7,4, +11,0]   ROI −0,8%
    gap < +1pp   n=311   gap −1,6pp   edge naspram SS +0,8pp [−4,2, +5,8]    ROI −4,0%

Smjer je isti kao živi nalaz (skupina s gapom bolja), ali razlika je ~1pp u edgeu i ~3pp u ROI-u,
ne +12pp. Očekivanje zapisano unaprijed ("edge ≈ veličina gapa") se potvrdilo.

## Pitanje 2 — je li rupa 1,35–1,60 svojstvo tržišta? **NE**

Favoriti po Avg kvoti, edge naspram poštene cijene:

    <1,20      n=2053  +1,9pp [+0,5, +3,2]   obje polovice +
    1,20-1,30  n=1574  +0,3pp
    1,30-1,35  n= 847  +1,0pp
    1,35-1,43  n=1364  +3,7pp [+1,3, +6,1]   obje polovice +   <- naš K5 kaže −7,9pp
    1,43-1,60  n=2917  −0,4pp
    1,60-1,75  n=2244  −1,2pp
    1,75-2,00  n=1315  −2,0pp [−4,7, +0,7]

Tržište nema rupu; kratki favoriti su blago potcijenjeni, a gotovo izjednačeni favoriti blago
precijenjeni (poznata pristranost favorit–autsajder, ovdje slaba). Naš −7,9pp na 1,35–1,43
(n=53, interval ±13pp) je ili slučajnost ili posljedica toga KOJE favorite model bira u tom pojasu.

## Pitanje 3 — kandidati: **svi PADAJU**

Edge igrača s osobinom naspram poštene cijene (P1 = 2022–23, P2 = 2024–26):

| kandidat | n | edge | 95% interval | P1 / P2 | presuda |
|---|---|---|---|---|---|
| K15 više ATP pobjeda u sezoni | 11.139 | +0,0pp | [−0,8, +0,9] | −0,5 / +0,5 | PADA |
| K16 jedini s GS polufinalom (QF/SF/F) | 826 | +1,1pp | [−2,0, +4,1] | +1,0 / +1,2 | PADA |
| K18 favorit na hard ATP 250 | 2.311 | +0,1pp | [−1,7, +2,0] | +0,0 / +0,2 | PADA |
| K19 povratak nakon 21+ dan | 1.018 | −2,5pp | [−5,2, +0,3] | +0,5 / −4,7 | PADA |
| K2 domaći igrač | 2.775 | −1,4pp | [−3,1, +0,2] | −1,2 / −1,6 | PADA (nije +) |
| K3 Bo5 favorit 1,30–1,50 | 563 | **+4,3pp** | [+0,6, +7,9] | +4,7 / +4,0 | PADA (suprotan smjer) |
| K11 favorit u R16/QF | 3.423 | +0,6pp | [−0,9, +2,1] | +0,3 / +0,9 | PADA |
| POV bolja povijest na turniru | 6.198 | +0,2pp | [−0,8, +1,3] | −0,4 / +0,6 | PADA |
| K12 servis na turniru (dubina 3+) | 970 | +0,4pp | [−2,4, +3,2] | −0,4 / +0,9 | PADA |
| CO bolji protiv zajedničkih protivnika | 10.661 | +0,2pp | [−0,7, +1,0] | −0,1 / +0,4 | PADA |

Dodatno: K15 r(veličina razlike, ostatak) = −0,005; K12 r = +0,004 (prag K12 bio je ≥ +0,05).
Usporedbe: favoriti izvan hard ATP 250 +0,4pp; favoriti u ostalim rundama +0,3pp; K19 21–41 dan
−2,7pp (P1 +2,1 / P2 −6,6), 42+ dana −1,9pp.

**Kako čitati:** kandidati koji opisuju OSOBINU igrača (K15, K16, K19, K2, POV, K12, CO) ovim su
testom izravno provjereni — tržište ih plaća. Kandidati koji opisuju NAŠ izbor (K18, K11, K5)
ovdje se ne mogu potvrditi ni oboriti; test samo kaže da tržište ondje nema rupu, pa ako naš
učinak postoji, dolazi od toga koje pickove model bira, ne od pogrešne cijene.

## Pitanje 4 — mehanizam konsenzusa (Bet365 kao "meka kladionica"): **NE drži se kao oklada**

    gap < −1pp     n= 6419  edge naspram Bet365 −1,5pp  ROI po Bet365 −11,7%
    gap −1..+1pp   n=11726  edge  +0,0pp                ROI  −6,2%
    gap +1..+2pp   n= 3807  edge  +0,4pp                ROI  −6,2%
    gap ≥ +2pp     n= 2612  edge  +3,0pp (gap +2,9pp)   ROI  +0,5% [−3,5, +4,5]  P1 −0,5% / P2 +1,7%

Konsenzus je dobro kalibriran (edge ≈ gap), ali tek kad razlika nadmaši maržu kladionice
oklada prestaje gubiti — i tada je oko nule. Za nas: bonus za konsenzus ima smisla kao
"prednost u odabiru", ali da bi pick sam po sebi bio u plusu, gap mora biti veći od ~3pp.

## Preporuke po kandidatu (ništa nije ugrađeno)

| kandidat | preporuka |
|---|---|
| K15, K16 | zatvoriti — tržište to plaća na 11.139 odnosno 826 mečeva |
| K3 | zatvoriti — povijest pokazuje suprotan smjer (+4,3pp); kazna bi rezala dobre pickove |
| K5 | ne uvoditi na n=20 — tržište u tom pojasu daje +3,7pp; ako se mjeri dalje, tražiti n ≥ 100 |
| K2 | podržava brisanje pravila 11 iz prompta (uz sljedeću izmjenu prompta) |
| K12 | po vlastitom pragu (r < +0,05) izlazi iz prompta — povijesni r = +0,004 |
| K18, K11 | mjeriti dalje uživo (samo naš izbor), ali tržišne rupe nema |
| K19 | mjeriti dalje uživo; povijesno slab i nestabilan smjer (−2,5pp, polovice različite) |
| KONS | zadržati bonus; očekivanje spustiti na ≈ veličinu gapa; za "value" tražiti gap ≥ 3pp |
| novo: Bo5 favoriti 1,30–1,50 | promatrati na AO 2027 (povijesno +4,3pp, nakon Holm korekcije P=0,23 — nije dokazano) |

## Ograde

- Povijest mjeri tržište na SVIM mečevima; naš model bira podskup. Predprovjera ubija ideje o
  pogrešnoj cijeni, ali ne može testirati kvalitetu našeg izbora.
- Cijene su zatvorne (pred početak meča); SuperSport screenshot je jutarnji.
- Dani od zadnjeg meča ne vide ITF turnire (rijetko za igrače na ATP razini).
- 12 testova u pitanju 3; Holm-korigirane P-vrijednosti su sve ≥ 0,23.
- Uzorak 2022–2026 (korisnikov izbor); snaga je dovoljna za učinke od ~2–3pp.

## Kako ponoviti

    python revizije/2026-09-27/skripte/lab_data.py       # učitavanje i spajanje (keš u .cache/lab/)
    python revizije/2026-09-27/skripte/lab_features.py   # osobine na dan meča
    python revizije/2026-09-27/skripte/lab_tests.py      # pitanja 2-4 (i --avg za robusnost)
    python revizije/2026-09-27/skripte/lab_q1.py         # pitanje 1 (čita Supabase)

Kad izađe novija datoteka za 2026., prepiši `.cache/tennis-data/2026.xlsx` i ponovi sve četiri.
