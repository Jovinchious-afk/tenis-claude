# Revizija 01.11.2026 — pragovi zapisani PRIJE računanja

Zapisano **01.11.2026 13:05**. Pravilo kapije (06.09.2026): prag se ne mijenja nakon gledanja
rezultata. Ovaj dokument se nakon računanja NE uređuje; izvještaj ga samo citira. Svaki naknadni
dodatak ide na dno, s vlastitim vremenom i oznakom "NAKNADNO".

**Korisnikova uputa (01.11.2026, "nastavi" = kreni):** prije Pariza analiza svih gubitnih i
dobitnih parova od zadnje revizije (Basel i Beč, 26.10.–01.11.); što smo zapisali da pratimo;
devet korisnikovih točaka (kombinacije 3+ varijabli, nacionalnost/susjedi, analiza gubitka bez
tržišnog šablona, pojas kvote na tiketu, "nos" za mine i autsajdere, ubojica diva u sljedećoj
rundi, tko nas ruši po rundama, Lehečka "samo ELO", tie-break zapis). **Ništa ne implementirati
prije zaključka** — samo izvještaj s prijedlozima.

**Što je viđeno prije ovog zapisa (iskreno):**
1. kod: `agent/predictor.py` (tie-break u promptu je "nije argument"; kazna za TB vodstvo
   uklonjena 06.09.2026 jer je pala izvan uzorka; državljanstvo se prikazuje kao "Country"),
   `revizije/2026-10-18/skripte/r_lab3.py`, `b_lab.py` (ELO), `b_tiketi_sim.py`,
   `revizije/2026-10-25/skripte/r_base.py`, `r_lab_d.py`, `r_dump.py`;
2. registar (DI, izmjereno 27.09.–25.10.), BACKLOG "ČEKA", izvještaj revizije 25.10.;
3. LAB: popis stupaca i raspon datuma (tennis-data 03.01.2022 – 06.10.2026, 12.472 meča; TML glavni
   ždrijeb 2000 – 06.10.2026, Challengeri 2007 – 05.10.2026, kvalifikacije 2020 – 18.10.2026).
   **Nijedan od testova ispod nije računan.**
4. iz korisnikove poruke: citat analize Lehečka (pick "near coin-flip", samo 93 boda ELO-a u
   dvorani) i "Vacherot 6-0 u tie-breakovima na ovom turniru (samo opis)".

**Ishodi Basela i Beča nisu gledani** (baza još nije skinuta).

## Uzorci

| oznaka | što | n (približno) | 95% interval edgea |
|---|---|---|---|
| TJEDAN | analize 26.10.–01.11.2026 (Basel, Beč), riješene, obje kvote, bez `elo_suspect`; finala 01.11. ulaze samo ako su riješena | ~60–75 | ±11–12pp |
| NOVO | sve od 27.09.2026 (era bccf4742) | ~290 | ±5,5pp |
| STARO | ranije riješene analize s obje kvote | ~470 | ±4,4pp |
| LAB | 12.436 ATP mečeva 2022 – 06.10.2026, poštena cijena (Pinnacle bez marže, inače prosjek) | 12.436 | ±1–2pp |

Snaga (`snaga.py`): n=30 ±17,1pp (80% snage tek za 21,7pp); n=60 ±12,1; n=100 ±9,3; n=300 ±5,4;
n=1.000 ±3,0; n=3.000 ±1,7. Za edge od 2pp treba ~3.500 slučajeva. **Na TJEDNU se ne može ništa
dokazati**; na LAB-u kombinacija s n < 300 vidi samo razlike od ~7pp naviše.

## Mjere (iste kao 18.10. i 25.10.)

- **edge** = stvarni % pobjeda − prosjek devigirane cijene (SuperSport za naše pickove, poštena
  cijena u LAB-u), uz 95% interval; **ROI** po SuperSport kvoti (ravni ulog).
- **Kontrola cijene:** usporedbe skupina unutar pojasa kvote (1,00–1,35 | 1,35–1,65 | 1,65–2,10 |
  2,10+), ponderirano.
- **LAB simetrično:** svaki meč ulazi sa strane igrača A koji zadovoljava uvjet (ako oba
  zadovoljavaju, ulaze oba retka); polovice P1 = 2022–23, P2 = 2024–26.

## A. Tjedan (opis, bez praga za model)

- **A1** edge i ROI po turniru, pojasu kvote, rundi, sesiji, pouzdanosti, favorit/autsajder.
- **A2 sreća ili čitanje** (definicija 18.10.): zasluženi edge iz udjela poena unutar ±2pp od
  nule → "pretežno sreća"; istog predznaka kao W/L edge, barem pola veličine, interval ispod nule
  → "nadigrani"; inače "nejasno".
- **A3 tiketi tjedna:** svaka noga (kvota, cijena, ishod), odlučujuća noga, P(tiket) = umnožak
  cijena, noga koju je recenzent označio.

## B. Kandidati na redu (pragovi zapisani ranije — sudac `scripts/measure_candidates.py`)

K5, K13b, K18b, K19, K20 (stanje; provjera tek na 300), K22, K24 (G1/G2/G3), L4, KONS (samo
praćenje), noćna sesija (60), omjer protiv ljevaka (300), K14 (Davis Cup). Pragovi doslovno kako
stoje u DI i skripti; ovdje se ništa ne mijenja. Uz to operativno: **Market Close Capture**
(BACKLOG: "prvi zakazani run 27.10.… do kraja Basela i Beča") — broj zapisanih redaka po danu.

## C. Gubitni i dobitni parovi TJEDNA (opis)

- **C1 kartica za svaki gubitni pick** (kao 25.10.) i **kratka kartica za svaki dobitni** (kvota,
  cijena, runda, glavni argument agenta, udio poena).
- **C2 zasluženo ili ne** (udio poena picka): < 47% nadigran · 47–50% tijesno · > 50% izgubio uz više
  poena.
- **C3 analize gubitka (korisnikova točka 3):** za svaku analizu gubitka brojim (a) rečenice o
  tržištu/cijeni/pojasu kvote (ključne riječi: market, price, devig, band, 1.35, 1.43, priced),
  (b) prijedloge "Worth measuring" i koliko ih je već izmjereno (popis ODBAČENO u DI), (c) postoji
  li ijedan konkretan "znak mine" vidljiv prije meča. **Unaprijed:** ako ≥ 50% analiza troši
  barem jednu rečenicu na tržište/pojas bez novog znaka → prijedlog novog oblika analize gubitka
  (proizvod, ne model; `rules_hash` je samo prompt predviđanja).
- **C4 gubitni naspram dobitnih u istom pojasu cijene** (TJEDAN, pa NOVO): varijable kao 25.10.
  + razlika TB zapisa, domaći/susjed, runda. Opis, Holm po obitelji; ništa iz C4 ne može biti više
  od KANDIDATA.

## D. Korisnikove točke na NAŠIM podacima (opis — n je premalen za dokaz)

- **D7 tko nas ruši po rundama (točka 7):** NOVO (runde ručne od 26.09.), po rundi R32/R16/QF/SF+:
  n, edge; profil protivnika u porazima naspram pobjeda iste runde i pojasa (ELO jaz, rang, dob,
  domaći/susjed, kvalifikant, je li u prošloj rundi izbacio bolje rangiranog, udio poena u prošloj
  rundi). Samo opis; uzorak je ±15–20pp po rundi.
- **D4 pojas kvote (točka 4):** edge po pojasu (1,00–1,35 | 1,35–1,45 | 1,45–1,50 | 1,50–1,65 |
  1,65+) na STARO, NOVO, TJEDNU i na nogama tiketa. **Prag za prijedlog ograničenja pojasa
  (unaprijed):** edge pojasa ≤ −5pp u OBJE ere (STARO i NOVO zasebno) i spojeni interval ispod nule
  → prijedlog korisniku; inače se ne predlaže. Uz to simulacija tiketa (postupak `b_tiketi_sim.py`,
  od 08.09.): V0 kako je bilo; bez nogu 1,35–1,45; najviše 1 noga 1,35–1,45; bez nogu 1,50–1,65;
  najviše 1 noga 1,50–1,65; bez nogu ≥ 1,65; najviše 1 noga ≥ 1,65. Mjere: dani s tiketom, očekivana
  šansa (umnožak devigiranih cijena), očekivani povrat, ostvareno. Kriterij iz 18.10. (T): varijanta
  je zanimljiva samo uz ≥ +5pp očekivanog povrata i ≤ 30% manje dana s tiketom.
- **D8 "novčić odlučen samo ELO-om" (točka 8):** pickovi s cijenom < 0,60 (kvota ≈ 1,60+) i pickovi
  čiji tekst analize sam kaže coin-flip / narrow / marginal / only / solely / thin → edge naspram
  ostalih u istom pojasu; STARO, NOVO, TJEDAN. Opis.
- **D9 tie-break zapis na našim pickovima (točka 9):** r(razlika TB postotka, ishod − cijena), oba
  ≥ 5 TB, STARO i NOVO zasebno. Opis; sudac je LAB (E-T).

## E. LAB — nove obitelji testova (ništa od ovoga nije ranije računano)

**Zajedničko:** LAB 12.436 mečeva; poštena cijena; samo zapisi STROGO prije datuma ovog meča
(`b_lab.py` / `r_lab3.py` zaštita); profil 365 dana (sve razine: glavni ždrijeb, Challengeri,
kvalifikacije; ≥ 300 poena / ≥ 30 gemova na servisu, inače prazno); percentili na profilima obje
strane svih LAB mečeva (ista konvencija kao 18.10.); ELO prije meča (ukupni i po podlozi,
`b_lab.compute_elo`).

**Kriterij (isti kao 18.10. i 25.10.):** PROLAZI = |edge| ≥ 2pp, 95% interval ne prelazi 0, isti
predznak u obje polovice, smjer kao u tablici (za "±" bilo koji), Holm P < 0,05 u obitelji, i
stabilnost (isti predznak u ≥ 2 od 3 razine, u ranim i kasnim rundama, u ≥ 3 od 4 pojasa cijene,
gdje n ≥ 50). SLAB = sve osim |edge| ≥ 2pp ili Holma. PADA = ostalo. PREMALO = n < 30 ili polovica
< 10. **Ishod:** PROLAZI → novi kandidat (K26+) s pragom za potvrdu uživo, ništa u model. SLAB/PADA
→ "ODBAČENO (ne otvarati bez novog izvora)".

**Višestruko testiranje:** isti povijesni uzorak već je korišten za 88 testova; ovdje se dodaje 21
(C 11, N 3, G 4, T 3) → ukupno 109. Uz Holm u obitelji ispisuje se i P × 109. Slučajno se uz
P < 0,05 očekuje ~1 "prolaz" od 21.

### E-C — kombinacije 3+ varijabli (točke 1 i 5), Holm na 11

Varijable (sve iz prošlosti): `ret12` povrat, `hold12` hold, `bps12` spašeni BP, `bpc12`
iskorišteni BP, `tpw12` udio svih poena, `df12` dvostruke po poenu na servisu — profil 365 d;
`df3` dvostruke na zadnja 3 meča sa statistikom (unutar 45 dana); `tb12` postotak dobivenih
tie-breakova u 365 d (iz rezultata setova 7-6 / 6-7, sve razine), uz broj TB; `rest` dani od
zadnjeg meča; **`tz` pomak vremenske zone** (sati, UTC u gradu ovog turnira naspram grada
prethodnog turnira na njegov datum; definirano samo kad su oba grada poznata — gradovi iz
tennis-data `Location`, tj. prethodni turnir mora biti ATP turnir 2022+; inače prazno);
**prvi meč na turniru** (nema ranijeg meča glavnog ždrijeba istog turnira); H2H iz svih razina
TML-a (bez walkovera), strogo prije datuma; "favorit" = poštena cijena ≥ 0,50; "autsajder" = 0,30–0,50.

| oznaka | uvjet za igrača A | smjer |
|---|---|---|
| **C1** (točka 1, doslovno) | A `ret12` ≥ 90. percentil I `hold12` ≤ 10. percentil, meč na hardu u dvorani | − |
| C1r (ista ideja, veći n) | A `ret12` ≥ 75. perc. I `hold12` ≤ 25. perc., hard u dvorani | − |
| C2 jet-lag favorit | A favorit, `tz` ≥ 5 h, zadnji meč prije ≤ 5 dana, prvi meč na turniru | − |
| C3 odmoran autsajder protiv putnika | A autsajder; A `tz` ≤ 1 h i `rest` ≥ 4; B `tz` ≥ 5 h, zadnji meč ≤ 5 dana, B-u prvi meč na turniru | + |
| C4 klimav servis favorita | A favorit; A `df3` ≥ 1,5 × `df12` i `df3` ≥ 4%; A `hold12` ≤ medijan; B `ret12` ≥ 60. perc. | − |
| C5 H2H dinamika protiv favorita | A favorit; B dobio zadnji međusobni meč (≤ 18 mj., ista podloga) I B dobio ≥ 2 od zadnja 3 (≥ 2 meča) | − |
| C6 "srećom spašeni BP" favorit | A favorit; A `bps12` ≥ 80. perc.; A `hold12` ≤ medijan; B `bpc12` ≥ medijan | − |
| C7 favorit napuhan tie-breakovima | A favorit; A `tb12` ≥ 65% (≥ 6 TB); A `tpw12` ≤ 51% | − |
| C8 autsajder bolji po poenima nego po rezultatima | A autsajder; A `tpw12` ≥ B `tpw12`; A ELO < B ELO; A `tb12` ≤ 40% (≥ 6 TB) | + |
| C9 lanac iz točke 5 | A favorit; A `tz` ≥ 3 h; A `df3` ≥ 1,3 × `df12`; A `hold12` ≤ B `hold12` | − |
| C10 H2H gospodar kao autsajder | A autsajder; A dobio zadnja 2 međusobna (≤ 24 mj.); A `hold12` ≥ B `hold12` | + |

### E-N — nacionalnost i susjedi (točka 2), Holm na 3

- **"susjed"** = A nije domaći, a država mu ima kopnenu granicu s državom turnira ILI joj je glavni
  grad ≤ 600 km od grada turnira (popis granica i koordinata zapisuje se u skriptu prije računanja).
- **N1** A je susjed → smjer +.
- **N2** A je susjed I autsajder (0,30–0,50) → smjer +.
- **N3 "turnir sunarodnjaka":** u prethodnih ≤ 5 izdanja OVOG turnira (strogo ranije godine, TML
  glavni ždrijeb) sunarodnjaci igrača A **bez njega samog** imaju postotak dolaska do QF barem
  10pp veći nego isti sunarodnjaci na svim ostalim turnirima iste razine istih godina (≥ 5 nastupa
  sunarodnjaka na ovom turniru) → smjer +.
- **Referenca (nije novi test):** domaći igrač (K2, 27.09.: −1,4pp n=2.775) ponovno istim kodom.
- **Tablica (opis, korisnik ju je tražio):** po turniru i državljanstvu, 2022–2026 (i 2017–2026
  za stabilnost): nastupi, QF+, postotak QF na ovom turniru naspram ostalih iste razine. Primjeri
  iz poruke: Talijani u Beču i Umagu, Nijemci u Baselu, Portugalci na španjolskim turnirima,
  plus najveća odstupanja (≥ 8 nastupa). Tablica je OPIS; prediktor je samo N3.

### E-G — "ubojica diva" u sljedećoj rundi (točka 6), Holm na 4

"Ubojica" = A je u PRETHODNOJ rundi ISTOG turnira (glavni ždrijeb) pobijedio igrača ranga ≤ 15
(rang na taj meč, TML) čiji je ELO (ukupni, prije tog meča) bio veći od A-ovog za ≥ 50; u ovom
meču je A-ov ELO veći od B-ovog (A je ELO-favorit).

| oznaka | uvjet | smjer |
|---|---|---|
| G1 | ubojica, sada ELO-favorit | ± (pad ili zalet — korisnik nije dao smjer) |
| G2 | G1 i A je i tržišni favorit | ± |
| G3 | G1, a u prošlom meču A je spasio ≥ 70% BP (≥ 5 suočenih) uz udio poena < 50,5% ("srećom") | − |
| G4 | G1, a u prošlom meču A je imao udio poena ≥ 52% ("zasluženo") | + |

Opis uz G: statistika prošlog meča naspram A-ovog profila 12 mj. (hold, 2. servis, dvostruke,
spašeni BP) i edge po prijelazu runde (R32→R16, R16→QF, QF→SF+).

### E-T — tie-break zapis (točka 9), Holm na 3

| oznaka | uvjet za A | smjer |
|---|---|---|
| T1 | A `tb12` ≥ B `tb12` + 20pp (oba ≥ 6 TB u 365 d) | ± (korisnik +, naši stari podaci −) |
| T2 | T1 i "ostalo slično": cijena 0,40–0,60 I \|A `tpw12` − B `tpw12`\| ≤ 1pp | ± |
| T3 | na OVOM turniru u prethodnim izdanjima (5 god.) A ≥ 4 TB i ≥ 75% dobivenih; B < 50% ili < 2 TB ondje | ± |

Opis uz T: je li tie-break vještina postojana — r(TB% u godini t, TB% u godini t+1) za igrače s
≥ 10 TB obje godine, i isto POVRH onoga što predviđa udio poena na servisu/povratu (ostatak).

### E-R — runde (točka 7, opis)

Edge favorita po rundi × pojasu cijene, i koji profil autsajdera po rundi dobiva više od cijene
(kvalifikant, ubojica iz prošle runde, bolji hold, mlađi, domaći). **Samo opis**; svaki "uzorak"
iz E-R je hipoteza za buduće mečeve, ne nalaz.

## F. Nos — Nose (K24) i Intuicija (K20) na TJEDNU

Kao 25.10. (F1–F4): tablica po ocjeni Nosea, vlastita vjerojatnost naspram cijene, Intuicija;
definicije se ne mijenjaju.

## G. Što ne pratimo (točka 5)

Popis polja koja bi trebala za ono što E pokaže (npr. grad i vremenska zona prethodnog turnira,
TB zapis na ovom turniru) — samo prijedlog bilježenja, model ne vidi.

## Curenje

- LAB: samo mečevi s datumom STROGO prije datuma ovog meča; prethodni turnir = zadnji zapis prije
  datuma; N3 iz strogo ranijih godina i bez samog igrača; G iz prethodne runde istog turnira
  (prije ovog meča po definiciji).
- Naši podaci: snapshot je zapisan prije meča; statistika meča samo za opis (C1, C2).

---

## NAKNADNO 01.11.2026 13:40 — pragovi za ČISTU povijesnu provjeru tragova (prijedlog P3), zapisani PRIJE podataka

**Što je viđeno do ovog zapisa:** svi rezultati LAB obitelji C, N, G, T i opisi R/G/T
(`.cache/rev_2026-11-01/out_lab_nos.txt`) na 2022 – 06.10.2026. Tragovi ispod su nađeni GLEDANJEM
tih rezultata — zato ih ovaj uzorak ne smije potvrditi. **Podaci za provjeru (tennis-data.co.uk
2010–2021) još ne postoje lokalno**; korisnik ih skida ručno (uvjeti stranice zabranjuju
automatsko skidanje). Kod mora biti napisan i zamrznut prije prvog pokretanja na tim godinama.

**Uzorak:** ATP mečevi tennis-data 2010–2021 spojeni s TML-om, poštena cijena (Pinnacle bez marže,
inače prosjek kladionica), iste definicije i zaštita od curenja kao `r_lab_nos.py` (profil 365 d,
ELO prije meča, H2H strogo prije, bez istog turnira). Percentili su ZAMRZNUTI na današnjim
vrijednostima (ne preračunavaju se na novom uzorku): povrat P75 = 0,3924, hold P25 = 0,7752.
Polovice: 2010–2015 / 2016–2021.

| oznaka | uvjet (igrač A) | smjer | PROLAZI ako |
|---|---|---|---|
| H1 (C1r, tvoja točka 1) | A favorit 0,50–0,70, hard u dvorani, povrat 12 mj. ≥ 0,3924 i hold 12 mj. ≤ 0,7752 | − | edge ≤ −3pp i interval ispod 0 |
| H2 (C5 obrnuto) | A favorit; protivnik dobio zadnji H2H (≤ 18 mj., ista podloga) i ≥ 2 od zadnja 3 | + | edge ≥ +2pp i interval iznad 0 |
| H3 (N2 + K2) | A autsajder 0,30–0,50 i domaći ILI susjed (definicija iz točke E-N) | − | edge ≤ −2pp i interval ispod 0 |
| H4 (opis G, finale) | "ubojica diva" (definicija G1) u FINALU | − | edge ≤ −5pp i interval ispod 0 |
| H5 (opis R) | A kvalifikant/LL i autsajder 0,30–0,50 u QF | − | edge ≤ −3pp i interval ispod 0 |

Uz to za svaki: isti predznak u obje polovice i Holm P < 0,05 na ovih 5. PROLAZI → kandidat za
"nos" (praćenje uživo, ništa u model bez korisnikova odobrenja). Inače → ODBAČENO zauvijek.
**Snaga:** H1 i H4 imat će malo slučajeva (procjena H1 ~150–250, H4 ~60–100) — uz n = 100
interval je ±9pp, pa je i ishod "PREMALO" moguć i ne smije se čitati kao potvrda.
**Napomena:** TML kvalifikacije postoje tek od 2020., pa je profil 365 d za 2010–2019 bez njih
(Challengeri postoje od 2007.); to se prihvaća unaprijed kao razlika uzoraka.

---

## NAKNADNO 01.11.2026 14:11 — ispravak plana P3 nakon provjere skeptika (i dalje PRIJE ikakvih podataka 2010–2021)

**Razlog:** skeptik je izračunao snagu za H1–H5 i našao jednu činjeničnu grešku u dodatku od
13:40. Podaci 2010–2021 lokalno još ne postoje, pa ovaj ispravak ne gleda nikakav rezultat.

1. **Ispravak činjenice:** TML Challengeri i kvalifikacije lokalno postoje tek od 2020. (uz ~124
   zalutala retka iz 2007./08.), a ne od 2007. Za 2010–2019 profil 365 d i ELO nastaju samo iz
   glavnog ždrijeba.
2. **H1 POVUČEN:** na profilu samo iz glavnog ždrijeba isti apsolutni pragovi biraju 5,0% strana
   naspram 11,5% danas (preklapanje 39%), pa test ne bi mjerio istu skupinu; najmanji vidljivi
   učinak ~12pp. Korisnikova točka 1 ostaje otvorena — skuplja se uživo kroz registar znakova
   (prijedlog P2), na karijernim brojkama koje model stvarno vidi.
3. **H4 POVUČEN:** n ≈ 55, najmanji vidljivi učinak ~18pp.
4. **Mjera za H2, H3, H5:** edge kao RAZLIKA naspram baze iste godine i istog pojasa cijene (svi
   igrači tog pojasa te godine), jer se tržišna baza mijenja po godinama (autsajderi 0,30–0,50 u
   2022–26: +2,2 / +1,1 / −1,1 / −1,9 / −1,0pp); samo Pinnacle cijena, bez prosjeka kladionica.
5. **Snaga (skeptik):** H3 ~4.700 strana, najmanji vidljivi učinak ~2,0pp → **glavni test**. H2
   ~560 (~5,7pp) i H5 ~170 (~10pp) → sporedni; uz njihove pragove (+2 i −3pp) ishod "PREMALO" je
   najvjerojatniji i ne smije se čitati kao potvrda ni kao pad. C5 (izvor H2) je i krhak.
6. **Postupak prije skidanja:** kod za H2/H3/H5 napisati, zamrznuti (SHA-256 upisati ovdje) i
   pokrenuti "na suho" na 2022–2026 uz ispis n, najmanjeg vidljivog učinka i polovica. Pragovi H2,
   H3 i H5 ostaju kao u 13:40; Holm na preostala 3; polovice 2010–15 / 2016–21 istog predznaka.
