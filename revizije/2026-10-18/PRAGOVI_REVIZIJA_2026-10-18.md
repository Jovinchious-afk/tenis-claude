# Revizija 18.10.2026 — pragovi zapisani PRIJE računanja

Zapisano **18.10.2026 09:07**. Pravilo kapije (06.09.2026): prag se ne mijenja nakon gledanja
rezultata. Ovaj dokument se nakon računanja NE uređuje; izvještaj ga samo citira. Svaki naknadni
dodatak ide na dno, s vlastitim vremenom i oznakom "NAKNADNO".

**Korisnikova uputa za ovaj ciklus (18.10.2026):** bez iznimke od kapije; primijeniti samo
korekcije za koje su postojeći kriteriji nedvosmisleno ispunjeni; nalaz koji ne zadovolji
kriterij ostaje kandidat; akcija koja traži novu heuristiku ili nove težine se NE provodi nego
bilježi kao kandidat.

**Što je viđeno prije ovog zapisa (iskreno):**
1. ispis `scripts/measure_candidates.py` (K5, K10, K11, K13, K17–K20, KONS) — ti kandidati
   imaju pragove zapisane ranije u DECISION_INPUTS;
2. broj pogođenih po turniru od 27.09. BEZ cijene (Šangaj 46 od 72 riješena, Tokio 15/29,
   Peking 21/28, Chengdu 5/7, Hangzhou 6/7);
3. statusi tiketa od 26.09. (27.09. dobitan, zatim 9 izgubljenih zaredom 29.09.–12.10.) i
   tekstovi sažetaka tiketa od 30.09.;
4. popunjenost polja (bez ishoda);
5. rezultati ranijih revizija (30.08., 13.09., 26.09., 27.09., 04.10.).

Ništa drugo od ishoda novih mečeva nije gledano. LAB je isti kao 04.10. (do 13.09.2026); nove
kombinacije iz točaka D, E, S i F na njemu NISU računane.

## Uzorci

| oznaka | što | n (približno) | 95% interval edgea |
|---|---|---|---|
| ŠANGAJ | analize Šangaja (05.–18.10.2026), riješene, obje kvote, bez `elo_suspect` | ~72 | ±11pp |
| NOVO | sve od 27.09.2026 (hard; era bccf4742 + 8 analiza 9696c4ee), runde ručne | ~140 | ±7,7pp |
| STARO | ranije riješene analize s obje kvote | ~450 | ±4,4pp |
| HARD-v18 | hard analize od 04.08.2026 (od tada aktivne hard težine v18) | ~450 | ±4,4pp |
| LAB | 12.324 ATP meča 2022 – 13.09.2026, poštena cijena (Pinnacle, inače prosjek kladionica) | 12.324 | ±1–2pp, podskupine ±2–5pp |

Snaga (`snaga.py`): n=72 → ±11,0pp (80% snage tek za 14pp); n=146 → ±7,7pp (9,8pp); n=300 →
±5,4pp; n=1.000 → ±3,0pp; n=3.000 → ±1,7pp. Za stvarni edge od 3pp treba ~1.560 pickova.
**Na našim novim mečevima ne može se ništa dokazati.** Svaka tvrdnja o "signalu" mora proći
LAB ili ostaje opis.

## Mjere

- **edge** = stvarni % pobjeda − prosjek devigirane cijene, u pp (SuperSport za naše pickove,
  poštena cijena u LAB-u), uz 95% interval.
- **ROI** po SuperSport kvoti (ravni ulog).
- **Poeni**: isto baždarenje kao 04.10. (`.cache/rev_2026-10-04/points_calib.json`), "zasluženi
  edge".
- **Kontrola cijene**: svaka usporedba skupina radi se i unutar pojasa kvote (1,00–1,35 |
  1,35–1,65 | 1,65–2,10 | 2,10+), ponderirano.

## A. Dijagnoza (opis, bez praga za model)

- **A1** edge i ROI po turniru, razini, pojasu kvote, rundi, sesiji, pouzdanosti (konačnoj i
  sirovoj prije kazni), tržišni favorit/autsajder, izvor cijene.
- **A2 — sreća ili čitanje** (preformulirano po pouci iz 04.10.):
  - zasluženi edge unutar ±2pp od nule → "pretežno sreća/varijanca";
  - zasluženi edge istog predznaka kao W/L edge, barem pola njegove veličine, interval ispod
    nule → "nadigrani";
  - inače "nejasno".
- **A3 — tiketi od 27.09.** (10 tiketa: 1 dobitan, 9 izgubljenih):
  - za svaku nogu: kvota, devigirana cijena, ishod;
  - "odlučujuća" noga = jedina izgubljena noga na tiketu (bez nje bi tiket prošao);
  - P(tiket) = umnožak devigiranih cijena nogu;
  - koliko je vjerojatan niz od 9 izgubljenih zaredom uz te P.
- **A4 — učestalost tiketa od 04.10.** (prag 63): dani s tiketom i bez; razlog za dane bez.

## B. Kandidati na redu (pragovi zapisani ranije, prepisani doslovno)

| kandidat | prag (izvor) |
|---|---|
| K5 | od 07.09., kvota 1,35–1,43: n ≥ 100 i edge ≤ −5pp → zona (1,35, 1,60) (`measure_candidates.py`) |
| K10 | od 14.09., n ≥ 25 po pojasu: 1,35–1,65 < 0 i (1,20–1,35 > 0 ili 1,65–1,85 > 0) → "edge_bonus se zamjenjuje IZRIČITIM bonusom po pojasu cijene"; oblik se raspline → član se vadi bez zamjene (DI K10). **Akcija traži novu heuristiku → po uputi 18.10. ne provodi se u ovom ciklusu; bilježi se kao kandidat.** |
| K13 | protivnik s vijesti o ozljedi: n ≥ 40 i edge ≥ ostali + 5pp → prijedlog; ≤ 0 → samo bilježenje |
| K17 | od 27.09., pick s High profilom: n ≥ 30 i edge ≤ −5pp → kazna −3pp; > 0 → odbaciti |
| K18 | od 27.09., hard ATP 250: n ≥ 30 i edge ≤ −5pp → najviše 1 takva noga; > 0 → odbaciti |
| K19 | od 27.09., pauza ≥ 21 dan: n ≥ 40, predznak kao na tržištu |
| K20 | Intuicija: provjera na 150 procjena |
| KONS | `ticket_builder.py` (08.09.2026 12:07): "ako se do kraja listopada 2026 skupi 60+ pickova uz gap ≥ +1 i skupina ostane iznad +5pp → razmotriti tvrdi uvjet. **Ako padne ispod nule — maknuti bonus.**" `measure_candidates.py` (26.09.): PAO uz n ≥ 30 i edge < 0 |
| K15 | zatvoren 27.09., ali prag potvrde od 27.09. postoji: n ≥ 150 analiza od 27.09.: (a) r(S1, ostatak) ≥ +0,05; (b) ponderirano po pojasu ≥ +3pp; (c) CI spojenog uzorka ne prelazi 0. Ispod n=150 samo stanje |
| noćna sesija | 60 noćnih pickova od 05.10. → tek tada pogledati |
| K21 | ne može se mjeriti dok se ne osvježi `.cache/tennis-data/2026.xlsx` — samo stanje |

## C. Analize gubitaka (opis + provjera točnosti)

- **C1** popis svih analiza gubitaka od 27.09. (posebno od 04.10. i cijeli Šangaj): verdikt
  uz svaki faktor i prijedlog "What should change".
- **C2** za svaki faktor proglašen `[SIGNAL CONFIRMED]`: na NOVO + STARO, uz kontrolu cijene,
  razdvaja li stvarno pobjede od poraza.
  - točno = skupina s tim faktorom ima edge ≤ −3pp i interval ispod nule;
  - inače netočno.
  - Rezultat je stopa točnih oznaka CONFIRMED.
- **C3** "ATP wins this season gap": broj spominjanja u analizama; test = K15 (točka B), LAB
  (već zatvoreno: +0,0pp, n=11.139) i nove kombinacije E3/E4.

## D. Statistika s aktualnog turnira po dubini (korisnikova glavna ideja) — LAB

**Hipoteza H-T:** igrač s boljim prosjekom statistike u dosadašnjim mečevima NA OVOM turniru
pobjeđuje češće nego što cijena kaže, i učinak raste s brojem odigranih mečeva. Smjer +.

Definicije (TML, samo ranije runde istog turnira, glavni ždrijeb; prosjek ponderiran poenima):

| oznaka | statistika |
|---|---|
| **T0** | udio osvojenih poena (servis + povrat) — **PRIMARNI test** |
| T1 | hold % |
| T2 | asovi po servisnom poenu |
| T3 | 1. servis osvojen % |
| T4 | 2. servis osvojen % |
| T5 | povrat: osvojeni poeni na protivnikovom servisu % |
| T6 | break-pointi spašeni % |
| T7 | manje izgubljenih setova na turniru |
| T8 | udio osvojenih gemova |

- **Uvjet:** oba igrača imaju ≥ k mečeva na turniru; testovi na dubini k = 2 i k = 3+, a k = 1
  samo kao opis gradijenta. Bilo koja razlika (> 0); uz to tercile razlike (monotonost).
- **PROLAZI (LAB, isti kriterij kao 27.09./04.10.):**
  - |edge| ≥ 2pp, 95% interval ne prelazi 0, isti predznak u polovicama (2022–23 / 2024–26),
    smjer +;
  - Holm P < 0,05 u cijeloj LAB obitelji (vidi "Višestruko testiranje");
  - stabilnost: isti predznak u ≥ 2 od 3 razine (GS+Masters / 500 / 250, svaka n ≥ 50), u
    ranim (do R32) i kasnim (R16+) rundama gdje n ≥ 50, i u ≥ 3 od 4 pojasa cijene (svaki
    n ≥ 50).
- **SLAB** = sve osim |edge| ≥ 2pp ili Holma. **PADA** = ostalo.
- **Ishod:** PROLAZI → novi kandidat (K22+) s pragom za potvrdu uživo; NE ulazi u model.
  SLAB/PADA → zapisuje se; statistika s turnira ostaje opis u promptu (kao od 27.09.).
- **D2 (naši podaci, samo opis):** `p*_tourn_form_*` na NOVO po dubini; winneri i neiznuđene
  greške iz naših post-match statistika s istog turnira (pokrivenost niska).

## E. Kombinacije (interakcije) — LAB, 13 novih

Sve osobine iz 365 dana PRIJE meča (TML), osim gdje piše "na turniru". A = igrač iz ćelije;
edge = pobjeda A − poštena cijena A. Smjer u zagradi. Percentili se računaju na cijelom LAB-u.

| oznaka | uvjet | smjer |
|---|---|---|
| E1 | povratnik protiv slabog 2. servisa: A-ov povrat ≥ +3pp od B-ovog, B-ov 2. servis u donjoj trećini | + |
| E2 | server protiv slabog povratnika: A-ov 1. servis osvojen ≥ +4pp, B-ov povrat u donjoj trećini | + |
| E3 | ATP pobjede u sezoni × hold: A ≥ 8 pobjeda više u sezoni I bolji hold | + |
| E4 | ATP pobjede u sezoni, a autsajder: A ≥ 8 pobjeda više, A je tržišni autsajder | + |
| E5 | visina × dvorana: A ≥ 8 cm viši, dvoranski hard | + |
| E6 | dob × umor: A ≥ 30 god., ≥ 2 seta više na turniru od B, B < 30 | − |
| E7 | dob × kratki odmor: A ≥ 30, ≤ 1 dan odmora, B ≥ 2 dana | − |
| E8 | stariji u završnici: A ≥ 5 god. stariji, QF/SF/F | − |
| E9 | "mina": A favorit, A-ov 2. servis ≥ 3pp lošiji od B-ovog, a B-ov povrat ≥ 3pp bolji | − |
| E10 | "mina": A favorit, oba ≥ 2 meča na turniru, A-ov udio poena na turniru ≤ 51%, B-ov ≥ 54% | − |
| E11 | kad uzeti autsajdera: A autsajder (cijena 0,30–0,50), oba ≥ 2 meča, A-ov udio poena na turniru ≥ 3pp veći | + |
| E12 | umor u minutama: A favorit, ≥ 60 min više na terenu na ovom turniru od B | − |
| E13 | protivnici sličnog profila: A-ov % pobjeda (365 dana, ≥ 8 mečeva) protiv igrača čiji je hold u istoj trećini kao B-ov, ≥ 15pp iznad A-ovog općeg % | + |

## S. Forma kao niz (sekvenca) — LAB, 3 testa

Profil ranijeg protivnika računa se na datum TOG ranijeg meča (bez curenja).

| oznaka | uvjet | smjer |
|---|---|---|
| S1 | A je dobio zadnja 2 meča (≤ 21 dan prije) protiv protivnika s holdom ≥ 3pp boljim od svog, a B ima hold ≥ 3pp bolji od A-ovog | + |
| S2 | isto za 2. servis osvojen | + |
| S3 | "način pobjede": A je dobio zadnja 2 meča uvjerljivo (udio poena ≥ 55% u oba), a B nije (izgubio barem jedan od zadnja 2 ili prosjek udjela poena < 52%) | + |

## F. Dob i visina

- **F1 (opis, LAB):** korelacije visine i dobi s post-match statistikom na TML glavnom ždrijebu
  2022–2026: asovi/servis, 1. servis osvojen, 2. servis osvojen, povrat osvojen, udio poena,
  hold, BP spašeni, minute. Po meču i igraču, r i interval. Ovo je OPIS (kako igraju), ne
  prediktor.
- **F2 (prediktivno, LAB):**
  - visina: A ≥ 8 cm viši, dvostrano (nema hipoteze o smjeru);
  - dob: A ≥ 5 godina stariji, smjer −.
- **F3 (dob × umor):** E6 i E7.

## W. Vrijeme (naši podaci, otvoreni tereni, STARO + NOVO, n ≈ 450)

- **W0 (opis):** korelacije temperature, vlage, tlaka na tlu i vjetra s post-match statistikom
  (asovi/servis, 1. servis osvojen, 2. servis osvojen, udio poena, BP iskorišteni, hold); po
  meču, oba igrača; Holm.
- **W1** vrućina (≥ 28 °C) × pick je veći server (asovi/100 ≥ +2): smjer +
- **W2** vjetar ≥ 20 km/h × pick je veći server: smjer −
- **W3** visoka vlaga (≥ 70%) × pick stariji 4+ godine: smjer −
- **W4** niski tlak na tlu (≤ 1005 hPa, tanji zrak) × pick je veći server: smjer +
- **Kriterij:** n ≥ 40 u ćeliji; |edge| ≥ 5pp; interval ne prelazi 0; isti predznak u STARO i
  NOVO; Holm u obitelji W (4 testa). Povijest nema vrijeme, pa ishod može biti najviše KANDIDAT.

## M. Kretanje kvota (Odds API) — ponavljanje na NOVIM događajima (poslije 11.09.2026)

- **M1** neto pomak devigirane cijene picka od prve do zadnje snimke prije početka, naspram
  ostatka nakon PRVE cijene: smjer +
- **M2** raspon kladionica (neslaganje), naspram ostatka: smjer −
- **M3** sharp kladionice naspram konsenzusa (razlika za pick), naspram ostatka: smjer +
- **Kriterij za povratak među kandidate:** |r| ≥ 0,15 u zadanom smjeru, 95% interval ne prelazi
  0, isti predznak kao 13.09. Inače ostaje ODBAČENO.

## R. Runde i "pouzdanost po rundi"

- **R1** edge po rundi od 14.09. (ručne/ispravljene runde): R128+R64 | R32 | R16 | QF | SF+F.
- **R2** kalibracija po rundi: prosjek (pouzdanost − stvarni %) i (pouzdanost − cijena).
- **Kriterij za kandidata "prilagodba po rundi":**
  - skupina ima edge ≤ −5pp uz n ≥ 40 od 14.09. i interval ispod 0;
  - I LAB pokazuje da tržište ondje griješi (favoriti te runde |edge| ≥ 2pp, interval ne
    prelazi 0).
  - Inače ne.
- Napomena unaprijed: pouzdanost ne nosi informaciju (r = −0,04, n=466). Zato prilagodba
  pouzdanosti po rundi može promijeniti samo KOLIKO pickova prođe prag, ne edge.

## J. Težine hard modela (v18, aktivne od 04.08.2026)

- **J1 (opis):** kako se težine koriste (prompt) i koliko ih analize spominju.
- **J2:** za svaku kategoriju predstavnik naspram ostatka nakon cijene, na hard pickovima od
  04.08.:

  | kategorija | predstavnik |
  |---|---|
  | elo_ranking | razlika ELO-a na podlozi |
  | serve_return | razlika servisnih poena + povrata |
  | recent_form | forma 10 i forma × kvaliteta |
  | surface_style | omjer na podlozi |
  | fatigue | setovi u 7 dana (manje = bolje) |
  | h2h | H2H |
  | tournament_trajectory | najdalja runda na turniru u 3 godine |

- **Kriterij za promjenu težina:**
  - veća težina: kategorija ima r ≥ +0,10 (interval iznad 0) u OBJE polovice hard razdoblja
    od 04.08. (do 13.09. i od 14.09.), a LAB ne proturječi → kandidat;
  - manja težina: r ≤ −0,10 u obje polovice → kandidat;
  - inače nema podloge za promjenu.
- Svaka promjena težina je izmjena modela → kapija i korisnik.

## K. Scouting top 150 (opis)

- K17 po pragu iz točke B.
- Opis: razina profila picka i protivnika na Šangaju i NOVO.
- Stil iz profila naspram ishoda (opis).
- Tvrdnje tipa "slab na brzom hardu": edge tih igrača kao pick i kao protivnik (opis).

## H. Izostavljene varijable — ponovna provjera na NOVO (opis; vraćanje samo kao kandidat)

**Popis:** domaći teren (K2), statistika s turnira na dubini 3+ (K12), ATP pobjede u sezoni
(K15), GS polufinala u završnicama (K16), vrijeme (temperatura, vlaga, vjetar), umor (setovi u
7 dana), scouting (ima/nema, razina), razlika u dobi 4+, H2H, vodstvo u tie-breakovima, hold
jaz ≥ 7, Med-Low, pauza 21+ (K19).

**Kriterij (zapisan sada):**
- varijabla se predlaže kao ponovni KANDIDAT samo ako na NOVO ima isti predznak kao izvorni
  nalaz, |edge| ≥ 5pp i n ≥ 30, I LAB nije već pokazao da tržište to plaća;
- K2, K12, K15, K16 i povijest na turniru su LAB-om zatvoreni. Za njih je ishod unaprijed
  "ostaje zatvoreno", osim ako NOVO pokaže |edge| ≥ 10pp uz interval koji ne prelazi 0.
- U model ne ulazi ništa.

## L. "Nos" — mine i autsajderi (sinteza)

- **L1** profil poraza naspram pobjeda u istom pojasu cijene (NOVO + STARO hard): za osobine iz
  točaka H i C razlika učestalosti; Holm; opis.
- **L2** autsajderi: svi naši pickovi koji su tržišni autsajderi: edge i ROI.
- **L3** ocjena dokaza za svaki "miris": DOKAZANO (prošlo kapiju) / KANDIDAT / OPIS / ODBAČENO.

## Višestruko testiranje

- **LAB obitelj:** D (T0–T8 × dubina 2 i 3+ = 18) + E (13) + S (3) + F2 (2) = **36 testova**.
  Uz P < 0,05 slučajno se očekuje ~1,8 "prolaza". Holm se računa na cijeloj obitelji od 36.
- **Obitelji na našim podacima:** W (4), M (3), R (5), J (7), H (~14) — opis, Holm po obitelji.
- **Ukupno u sesiji ~70 testova**, pa se uz P < 0,05 očekuju ~3–4 lažna "nalaza". Uz to, LAB je
  već korišten za 27 testova (27.09. i 04.10.), pa je i to dio iste obitelji pokušaja.

## Curenje

- Sve LAB osobine samo iz mečeva prije: isti turnir → ranija runda; inače raniji datum.
- Profil protivnika iz sekvence računa se na datum TOG ranijeg meča.
- Post-match statistika se nikad ne koristi kao prediktor istog meča (samo opis u W0 i F1).
- Naši podaci: snapshot je zapisan prije meča; post-match samo za opis.

---

## NAKNADNO 18.10.2026 09:12 — dodano prije računanja ovih točaka

Povod: pri pregledu tiketa (A3) viđeno je da (1) `reviewer_warning` (AI recenzent tiketa) u
svakom tiketu imenuje nogu koja "carries the most risk", i (2) noga Tiafoe ima u analizi
pouzdanost 56, a na tiketu 63 (analiza je kasnije prepisana ponovnom analizom istog para).
Ishodi tih noga u 10 tiketa od 27.09. su viđeni; na širem uzorku (od 26.07.) nisu.

- **L4 — "nos" AI recenzenta:** noge koje recenzent imenuje kao najrizičnije, naspram ostalih
  noga istih tiketa, svi tiketi s upozorenjem. Prag: edge označenih ≤ −5pp, n ≥ 30, interval
  ispod nule I lošije od ostalih noga → kandidat "upozorenje recenzenta = mina" (prijedlog: ta
  noga se mijenja ili tiket ne igra). Inače opis. Smjer −.
- **A3b — pouzdanost noge:** za tikete se koristi pouzdanost iz `ticket_matches` (u trenutku
  oklade), ne iz `analyzed_matches` (može biti prepisana). Opis: koliko je noga imalo različitu
  pouzdanost u analizi i na tiketu.

## NAKNADNO 18.10.2026 09:31 — dodano prije računanja ove točke

Povod: analize gubitaka Majchrzak (07.10.) i Landaluce (08.10.) spominju "Rule 15" (prompt, hard
pravilo 15 od 31.07.2026: −4pp kad je pickov hard omjer ≤ 50% ili protivnikov ≥ 70%). Pravilo
je nastalo iz dva dokumentirana poraza i nikad nije mjereno naspram cijene.

- **H2 — pravilo 15:** pickovi gdje pravilo vrijedi (pickov omjer na hardu ≤ 50% ILI protivnikov
  ≥ 70%, iz `p*_surface_record`) naspram ostalih, hard od 04.08., uz kontrolu cijene.
  Smjer koji pravilo tvrdi: takvi pickovi prolaze LOŠIJE od cijene. Prag: edge skupine ≤ −5pp
  uz n ≥ 30 → pravilo ima podlogu; edge ≥ 0 uz n ≥ 30 → pravilo je bez podloge (kandidat za
  brisanje uz sljedeću izmjenu prompta); inače nejasno. Samo opis/kandidat — prompt se ne dira.
