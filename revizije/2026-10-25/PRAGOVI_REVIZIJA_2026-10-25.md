# Revizija 25.10.2026 — pragovi zapisani PRIJE računanja

Zapisano **25.10.2026 10:20**. Pravilo kapije (06.09.2026): prag se ne mijenja nakon gledanja
rezultata. Ovaj dokument se nakon računanja NE uređuje; izvještaj ga samo citira. Svaki naknadni
dodatak ide na dno, s vlastitim vremenom i oznakom "NAKNADNO".

**Korisnikova uputa (25.10.2026, potvrđeno "kreni"):** analiza svih gubitnih i dobitnih parova od
zadnje revizije (Lyon, Bruxelles, Almaty); svaki gubitni par detaljno (prije meča, nalazi agenta,
statistika meča, analiza gubitka); ideja 1 (dubina na zadnja 3 turnira); ideja 2 (vijesti); sve što
smo 18.10. zapisali da pratimo; Nos; GitHub popis. **Ništa ne implementirati prije zaključka.**

**Što je viđeno prije ovog zapisa (iskreno):**
1. broj pogođenih po turniru BEZ cijene: Bruxelles 15/25, Lyon 13/25, Almaty 13/24 (tri finala
   25.10. neriješena); Šangaj 13.–17.10. ima 14 analiza;
2. statusi tiketa od 09.10. (19.10., 21.10., 22.10. izgubljeni; 20., 23., 24., 25.10. bez tiketa);
3. kod: dijelovi prompta (`TOURNAMENT HISTORY`, `THIS TOURNAMENT so far`), `nose.assess`, oznake
   analize gubitka, panel vijesti na Dnevnom listiću (ESPN/BBC, prezime, bez datuma);
4. registar, BACKLOG i ranije revizije.

Ništa drugo od ishoda (cijene, edge, analize gubitaka, ishodi Nosea i Intuicije) nije gledano. LAB
je isti kao 18.10. (tennis-data do 06.10.2026, TML do 16.10.2026); ideja 1 na njemu NIJE računana.

## Uzorci

| oznaka | što | n (približno) | 95% interval edgea |
|---|---|---|---|
| TJEDAN | analize 19.–25.10.2026 (Lyon, Bruxelles, Almaty), riješene, obje kvote, bez `elo_suspect` | ~74 | ±10,9pp |
| NOVO | sve od 27.09.2026 (era bccf4742), hard | ~290 | ±5,5pp |
| STARO | ranije riješene analize s obje kvote | ~470 | ±4,4pp |
| LAB | 12.472 ATP meča 2022 – 06.10.2026, poštena cijena (Pinnacle bez marže, inače prosjek) | 12.472 | ±1–2pp |

TJEDAN su prvi turniri nakon izmjena 18.10. (bonus za konsenzus ugašen, nova analiza gubitka s
četiri oznake, Nose u sjeni, TML 12 mj. se bilježi). Snaga (`snaga.py`): n=74 → ±10,9pp, 80% snage
tek za 13,8pp; n=33 (gubitni) → ±16,3pp; n=290 → ±5,5pp. **Na TJEDNU se ne može ništa dokazati** —
svaka tvrdnja o "signalu" mora proći LAB ili ostaje opis.

## Mjere (iste kao 18.10.)

- **edge** = stvarni % pobjeda − prosjek devigirane cijene (SuperSport za naše pickove, poštena
  cijena u LAB-u), uz 95% interval; **ROI** po SuperSport kvoti (ravni ulog).
- **Poeni**: baždarenje 04.10. (`.cache/rev_2026-10-04/points_calib.json`), "zasluženi edge".
- **Kontrola cijene**: usporedbe skupina i unutar pojasa kvote (1,00–1,35 | 1,35–1,65 | 1,65–2,10
  | 2,10+), ponderirano.

## A. Dijagnoza tjedna (opis, bez praga za model)

- **A1** edge i ROI po turniru, pojasu kvote, rundi, sesiji, pouzdanosti (konačnoj i sirovoj),
  favorit/autsajder, dvorana.
- **A2 — sreća ili čitanje** (definicija 18.10.): zasluženi edge unutar ±2pp od nule → "pretežno
  sreća"; istog predznaka kao W/L edge, barem pola veličine, interval ispod nule → "nadigrani";
  inače "nejasno".
- **A3 — tiketi 19.10., 21.10., 22.10.**: svaka noga (kvota, cijena, ishod), odlučujuća noga,
  P(tiket) = umnožak cijena, noga koju je recenzent označio.
- **A4 — K1, prva 3 tjedna praga 63** (BACKLOG: "pratiti koliko dana nema tiketa (procjena ~13 od
  17) i ROI tiketa"): dani s tiketom i bez od 05.10.; ROI tiketa. Pravilo iz BACKLOG-a: "prag se više
  ne pomiče po pouzdanosti dok pouzdanost ne pokaže informaciju (r > 0) u dvije ere" → mjeri se
  r(pouzdanost − cijena, ishod − cijena) u eri bccf4742 i u prethodnim; ponovno otvaranje praga
  samo ako je r > 0 s intervalom iznad 0 u OBJE.

## B. Kandidati na redu (pragovi zapisani ranije — sudac je `scripts/measure_candidates.py`)

K5, K10, K13, K18, K19, K20, K22, K24, L4, KONS (samo praćenje), noćna sesija (60 noćnih pickova
od 05.10. → tek tada pogledati), omjer protiv ljevaka (300 mečeva). Pragovi doslovno kako stoje u
`DECISION_INPUTS.md` i u skripti; ovdje se ništa ne mijenja. K20: obveza izvješća čim n ≥ 150
(`python scripts/intuicija_report.py`).

## C. Gubitni parovi TJEDNA (opis + provjera točnosti)

- **C1 kartica za svaki gubitni pick:** kvota i cijena, runda, pouzdanost (sirova/konačna) i
  kazne, ELO/rang/forma/servis-povrat (RapidAPI i TML 12 mj.), statistika s turnira, Nose,
  Intuicija, recenzent (ako je noga tiketa), pet odjeljaka agenta, statistika meča (udio poena,
  servis, povrat, BP, asovi/dvostruke), rezultat; analiza gubitka gdje postoji (samo noge tiketa).
- **C2 zasluženo ili ne, po meču** (udio osvojenih poena našeg picka): < 47% → "nadigran";
  47–50% → "tijesno"; > 50% → "izgubio uz više poena".
- **C3 analize gubitka (nove četiri oznake od 18.10.):** za svaki faktor s oznakom
  `[SEPARATES WINS FROM LOSSES]` provjera na NOVO + STARO uz kontrolu cijene — točno = skupina s
  tim faktorom ima edge ≤ −3pp i interval ispod nule (isti kriterij kao 18.10. C2); broj
  `[GATE PASSED]` (smije biti 0); udio "No model change justified". **Unaprijed:** udio ≥ 80% →
  popravak od 18.10. radi; < 50% → ne radi (opis).
- **C4 gubitni naspram dobitnih u istom pojasu cijene** (TJEDAN, pa NOVO): ELO jaz, rang, forma 10,
  forma × kvaliteta, servis+povrat (RapidAPI i TML), statistika s turnira, odmor, setovi u 7 dana,
  dob, H2H, Nose p_own − cijena, Intuicija edge. Opis, Holm na obitelji; ništa iz C4 ne može biti
  više od KANDIDATA.

## D. Korisnikova ideja 1 — "koliko je daleko došao na zadnja 3 turnira" (LAB)

**Hipoteza H-D:** igrač koji je na zadnja 3 turnira dolazio dalje pobjeđuje češće nego što cijena
kaže. Smjer +. **Unaprijed (iskreno):** forma 10 mečeva (+0,2pp) i najdalja runda na ovom turniru
(+0,2pp) već su bile nula, pa realno očekujem PADA — test je pošten jer ova varijabla nije ista.

**Definicije** (TML; samo mečevi odigrani PRIJE datuma ovog meča; aktualni turnir isključen):
- "turnir" = različiti `tourney_id` glavnog ždrijeba ATP razine (G, M, 500, 250, A, F, O; bez
  Davis Cupa) na kojem je igrač odigrao ≥ 1 meč; početak turnira ≤ 120 dana prije meča;
- dubina = broj pobjeda u glavnom ždrijebu tog turnira; najdalja runda = runda zadnjeg meča
  (osvojen naslov = "W");
- uzimaju se ZADNJA 3 takva turnira; testovi D1, D3, D5, D7 traže da OBA igrača imaju 3.

| oznaka | uvjet za igrača A | smjer |
|---|---|---|
| **D1 (PRIMARNI)** | prosjek pobjeda na zadnja 3 turnira A − B ≥ +1,0 | + |
| D3 "vruć" | A je na barem jednom od zadnja 3 došao do SF ili dalje, B ni na jednom do QF | + |
| D4 "hladan favorit" (mina) | A tržišni favorit, na sva 3 zadnja turnira izgubio prvi meč (0 pobjeda), B prosjek ≥ 1 | − |
| D5 "vruć autsajder" | A autsajder (cijena 0,30–0,50), A − B ≥ +1,0 | + |
| D6 sve razine | kao D1, ali turniri bilo koje razine glavnog ždrijeba (uključujući Challengere), oba po 3 | + |
| D7 povrh forme 10 | kao D1, samo kad je razlika forme zadnjih 10 mečeva mala (|A − B| ≤ 0,10) | + |

- **D2 (opis, izvan obitelji):** tercile razlike prosjeka (mala / srednja / velika) — monotonost.
- **PROLAZI (LAB, isti kriterij kao 18.10.):** |edge| ≥ 2pp, 95% interval ne prelazi 0, isti
  predznak u polovicama (2022–23 / 2024–26), smjer kao u tablici, Holm P < 0,05 u obitelji D
  (6 testova), stabilnost (isti predznak u ≥ 2 od 3 razine, u ranim i kasnim rundama, u ≥ 3 od 4
  pojasa cijene, gdje n ≥ 50). **SLAB** = sve osim |edge| ≥ 2pp ili Holma. **PADA** = ostalo.
- **Ishod:** PROLAZI → novi kandidat (K26) s pragom za potvrdu uživo; NE ulazi u model.
  SLAB/PADA → "ODBAČENO (ne otvarati bez novog izvora)".
- **D0 (opis):** što model sada vidi (put kroz aktualni turnir, `THIS TOURNAMENT so far`, forma
  5/10, razina prethodnog turnira, najdalja runda ovdje u 3 sezone) i popunjenost tih polja na
  TJEDNU.

## E. Korisnikova ideja 2 — vijesti

- **E1 panel na listiću (ESPN + BBC RSS):** dohvat obaju feedova sada; broj naslova, raspon
  datuma; za igrače TJEDNA: koliko ih panel "nađe" po prezimenu, koliko od tih naslova je stvarno
  o tom igraču (ručno čitanje) i koliko je mlađe od 14 dana.
- **E2 Google News (`p*_gnews`, bilježi se od 27.09.):** na TJEDNU udio igrača s ≥ 1 naslovom,
  starost naslova naspram datuma meča, ručna provjera uzorka (~30 naslova: o pravom igraču? o
  tenisu? kladioničarski?), `injury_n`.
- **E3 K13** po pragu iz registra.
- **Kriterij za preporuku (proizvod, ne model):** izvor je koristan ako je ≥ 50% prikazanih
  naslova o pravom igraču I mlađe od 14 dana. Panel ESPN/BBC ispod toga → preporuka maknuti ili
  zamijeniti Google Newsom (ako on prođe isti kriterij). Ulazi modela se ne mijenjaju ni u kojem
  slučaju.

## F. Nos — Nose (K24) i Intuicija (K20)

- **F1** za svaki pick TJEDNA: Nose ocjena (UKLJUČI / UZ UPOZORENJE / IZBJEGAVAJ), zastavice mina
  i autsajdera, vlastita vjerojatnost naspram cijene, ishod; tablica po ocjeni (n, edge, uz
  pojas).
- **F2** Intuicija: edge_pp picka i zastavica autsajdera naspram ishoda.
- **F3** kapije po vlastitim pravilima (`nose.gate_status`, `intuicija.gate_status`).
- **F4** definicije se ne mijenjaju; svaki prijedlog = nose-v2 s novom kapijom od nule.

## G. Težine hard modela i automatika

- **G1** `model_weights`: je li se od 18.10. pojavila nova verzija (automatska petlja)?
- **G2 (kriterij doslovno iz revizije 18.10., točka J):** za svaku kategoriju predstavnik naspram
  ostatka nakon cijene, hard pickovi od 04.08.; veća težina samo ako r ≥ +0,10 (interval iznad 0)
  u OBJE polovice (do 13.09. i od 14.09.) i LAB ne proturječi; manja ako r ≤ −0,10 u obje; inače
  nema podloge. Predstavnici: ELO jaz na podlozi; servis+povrat; forma 10 i forma × kvaliteta;
  omjer na podlozi; setovi u 7 dana (manje = bolje); H2H; najdalja runda na turniru u 3 godine.

## H. Rokovi zapisani u kodu i dokumentima (opis)

Pretraga komentara s datumima i rokovima ("do kraja listopada", "31.10.", "nakon ... turnira")
i popis onoga što je dospjelo.

## I. GitHub popis (opis)

Za svaki repozitorij: KORISNO (zašto, za koji cilj) / MOŽDA (pod kojim uvjetom) / NE (zašto) /
SUMNJIVO (sigurnost, lažni klon, affiliate). Ništa se ne instalira.

## Višestruko testiranje

- **LAB obitelj D:** 6 testova (D1, D3–D7), Holm na 6. Isti povijesni uzorak već je korišten za
  79 testova (27.09., 04.10., 18.10.); uz ukupno 85 pokušaja slučajno se očekuje ~4 "prolaza" uz
  P < 0,05 — zato uz Holm na 6 ide i napomena kako bi test stajao uz Holm na 85.
- **Naši podaci:** C4 (~13 varijabli), G2 (7 × 2 polovice) — opis, Holm po obitelji.
- **Ukupno u sesiji ~30 testova** → ~1–2 lažna "nalaza" uz P < 0,05.

## Curenje

- LAB: samo mečevi s datumom STROGO prije datuma ovog meča; aktualni turnir isključen; prozor od
  120 dana po početku turnira.
- Naši podaci: snapshot je zapisan prije meča; statistika meča samo za opis (C1, C2).

---

## NAKNADNO 25.10.2026 10:32 — dodano nakon čitanja kartica gubitaka (C1), PRIJE računanja ovih točaka

**Viđeno do ovog zapisa:** A1 (TJEDAN −10,8pp; R32 −20,0pp n=31; pouzdanost 60–63 −19,2pp n=32,
68+ +10,3pp n=17), A2 (ostatak poena −0,25pp), A3/A4 (tiketi), ispis `measure_candidates.py` i
`intuicija_report.py`, 16 analiza gubitaka i 33 kartice. Iz kartica je nastala hipoteza N1 —
zato TJEDAN NE SMIJE biti njezin dokaz; sudac je LAB (2022–2026) i budući mečevi.

- **N1 "ritam protiv odmora" (LAB, smjer + za igrača u ritmu):**
  - N1a: A je u 7 dana prije meča odigrao ≥ 2 meča (bilo koja razina, i kvalifikacije), B u 10
    dana prije meča nije odigrao nijedan;
  - N1b: kao N1a, A je kvalifikant OVOG turnira (≥ 1 meč kvalifikacija istog turnira) i ovo mu je
    prvi meč glavnog ždrijeba;
  - N1c: kao N1a, A je tržišni autsajder (cijena 0,30–0,50).
  - Kriterij isti kao D (|edge| ≥ 2pp, interval ne prelazi 0, polovice, smjer, Holm u obitelji N
    od 3 testa, stabilnost). PROLAZI → kandidat K27, ništa u model. Inače ODBAČENO.
  - Povezano i već izmjereno: K19 (pauza 21+ dan, LAB −2,5pp, PADA), "umorniji u QF+" −0,2pp,
    "manje setova na turniru" −0,3pp. N1 nije isti test (ritam iz kvalifikacija i ranijih rundi
    naspram duljeg odmora), ali je iz iste obitelji ideja → realno očekujem PADA.
- **N2 (naši podaci, opis):** N1a iz snapshota (`p*_matches_7d` ≥ 2 za protivnika, `p*_days_rest`
  ≥ 10 za pick) na NOVO i STARO hard, uz kontrolu pojasa.
- **H2 ponovno (prag zapisan 18.10.2026 09:31, prepisan doslovno):** pravilo 15 (pickov omjer na
  hardu ≤ 50% ILI protivnikov ≥ 70%), hard od 04.08., uz kontrolu cijene: edge ≤ −5pp uz n ≥ 30 →
  pravilo ima podlogu; edge ≥ 0 uz n ≥ 30 → bez podloge (kandidat za brisanje uz sljedeću izmjenu
  prompta); inače nejasno.
- **N3 (naši podaci, opis):** "forma × kvaliteta" kao druga potvrda — pickovi s fq_pick − fq_prot
  ≥ 0,30 naspram ostalih, uz pojas, NOVO i STARO hard, polovice. Bez praga za model (ta varijabla je
  već [FAILED OR CLOSED]); provjera koliko je agent još koristi kao potvrdu.
- **R32 / prvo kolo (opis):** edge po rundi na NOVO; ništa se ne predlaže iz same rupe po rundi
  (kriterij R iz revizije 18.10. i dalje vrijedi: treba i LAB rupa na tržištu).
