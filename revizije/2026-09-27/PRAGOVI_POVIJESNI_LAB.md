# Povijesni laboratorij — pragovi zapisani PRIJE podataka

Zapisano **27.09.2026 11:32**, prije nego što je ijedna brojka iz povijesnih podataka
izračunata. Pravilo kapije (06.09.2026): prag se ne smije mijenjati nakon gledanja rezultata.
Ovaj dokument se nakon računanja NE uređuje; izvještaj ga samo citira.

## Podaci

- **tennis-data.co.uk**, ATP 2022–2026 (datoteke skinuo korisnik ručno 27.09.2026; 2026 ide
  do 13.09.2026). Samo odigrani mečevi (`Comment == Completed`); predaje i w.o. van.
- **Poštena cijena** = kvota bez marže (multiplikativni devig, isto kao `devig_pick_prob`):
  Pinnacle gdje postoji (praktički 2022 – rujan 2025), inače prosjek kladionica (`Avg`).
  2026. gotovo nema Pinnacla (71 od 2.150), pa je tamo poštena cijena prosjek kladionica.
  Provjera robusnosti: isti testovi samo s `Avg` cijenom.
- **TML** (stats.tennismylife.org, skinuto 27.09.2026): ATP glavni ždrijeb 2000–2026,
  Challengeri i kvalifikacije 2020–2026 — za runde, statistiku, državljanstvo i povijest igrača.
- **Naša baza** (`analyzed_matches`, samo čitanje): za pitanje 1.

## Mjera

Za igrača s osobinom: **edge = stvarni postotak pobjeda − prosjek poštene cijene**, u
postotnim bodovima. 95% interval: normalna aproksimacija (sd/√n). Polovice: **P1 =
2022–2023**, **P2 = 2024–2026**.

## Kriteriji (jednaki za sve kandidate iz pitanja 3)

- **PROLAZI**: |edge| ≥ 2pp, 95% interval ne prelazi nulu, isti predznak u obje polovice, i
  smjer isti kao u našem registru (DECISION_INPUTS).
- **SLAB**: isti smjer, interval ne prelazi nulu, ali |edge| < 2pp (tržište to većim dijelom
  već plaća; kao bonus možda, kao samostalna oklada ne — marža SuperSporta je ~2,7pp po strani).
- **PADA**: interval prelazi nulu, ili predznak različit u polovicama, ili suprotan smjer.
- Uz svaki test ide i Holm-korigirana P-vrijednost preko svih testova iz pitanja 3 (samo
  informativno; odluka ide po gornja tri kriterija).
- Prolaz na povijesnim podacima je **predprovjera**: ne mijenja status u registru sam od sebe;
  ulazak u model odlučuje korisnik.

## Pitanje 1 — naši mečevi naspram tržišta (2026, preklop s našom bazom)

Opisno: marža SuperSporta naspram prosjeka kladionica na istim mečevima; za naše pickove
EV na SuperSport kvoti = kvota × poštena cijena − 1; po razini turnira (ATP 250 posebno).
Test: edge naših pickova naspram **zatvorne** poštene cijene (nije isto što i naspram
devigirane SuperSport cijene). Nema praga — ovo je dijagnoza, ne kandidat.
Dodatno (KONS na novom uzorku, s ogradom da je cijena zatvorna, ne jutarnja):
`gap = poštena cijena − devig SuperSport` za naš pick; skupina gap ≥ +1pp mora imati edge
(naspram devig SuperSport) veći od ostalih. Očekivanje zapisano unaprijed: ako je tržište
dobro kalibrirano, edge te skupine ≈ veličina gapa (nekoliko pp), ne +10pp.

## Pitanje 2 — je li "rupa" 1,35–1,60 svojstvo tržišta

Favoriti po `Avg` kvoti, pojasevi: <1,20 | 1,20–1,30 | 1,30–1,35 | **1,35–1,43** |
**1,43–1,60** | 1,60–1,75 | 1,75–2,00. **Rupa je tržišna** ako favoriti u 1,35–1,43 i
1,43–1,60 imaju edge ≤ −1,5pp, interval ispod nule, isti predznak u obje polovice. Inače
naša rupa nije svojstvo tržišta (šum ili naš izbor pickova u tom pojasu).

## Pitanje 3 — kandidati (smjer iz registra u zagradi)

| oznaka | tko je "igrač s osobinom" | očekivani smjer |
|---|---|---|
| K15 | igrač s više ATP pobjeda u tekućoj sezoni (G/M/A/F/D/O, glavni ždrijeb, prije meča) | + |
| K16 | u QF/SF/F: jedini od dvojice s bar jednim GS polufinalom (TML od 2000.) | + |
| K18 | favorit na hard ATP 250 (usporedba: favoriti na ostalim razinama) | − |
| K19 | igrač koji se vraća nakon ≥21 dan bez meča (bilo koja razina u TML), protivnik nije | − |
| K2 | domaći igrač (državljanstvo = država turnira), protivnik nije; pravilo 11 u promptu | + (ako nije +, podržava brisanje pravila 11) |
| K3 | favorit u Bo5 (Grand Slam) uz `Avg` kvotu 1,30–1,50 | − |
| K11 | favorit u R16 ili QF (usporedba: favoriti u ostalim rundama) | − |
| POV | igrač s boljom najdaljom rundom (R16+) na TOM turniru u prethodne 3 sezone | + |
| K12 | u meču gdje oba igrača imaju 3+ ranija meča na turniru: igrač s većim % osvojenih poena na servisu na turniru; dodatno r(razlika, ostatak) ≥ +0,05 | + |
| CO | igrač s boljim omjerom protiv zajedničkih protivnika (zadnjih 365 dana, tour + Challenger, bar 3 zajednička) | + |

## Pitanje 4 — mehanizam konsenzusa (Bet365 kao "meka kladionica")

`gap = poštena cijena − devig Bet365` po strani meča. Pojasevi gapa: < −1 | −1..+1 |
+1..+2 | ≥ +2pp. **Mehanizam drži** ako klađenje po Bet365 kvoti u pojasu gap ≥ +2pp ima
ROI > 0 s intervalom iznad nule i isti predznak u obje polovice. Očekivanje zapisano
unaprijed: edge naspram devig Bet365 ≈ gap (kalibracija konsenzusa), a ROI tek kad gap
nadmaši maržu.
