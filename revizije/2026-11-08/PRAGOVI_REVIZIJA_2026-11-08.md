# Pragovi — revizija 08.11.2026 (Pariz + 11 korisnikovih ideja)

Zapisano **08.11.2026 11:27, PRIJE računanja ishoda.** Do tog trenutka gledani su samo broj redaka i
popunjenost polja (bez pobjeda i poraza). Snaga (`snaga.py`): n=51 → ±13pp, n=70 → ±11pp,
n=100 → ±9pp, n=150 → ±8pp, n=268 → ±6pp, n=600 → ±4pp, n=3.000 → ±1,7pp; za 5pp treba ~560.

Zajedničko: edge = pobjede − devigirana cijena (naši podaci: SuperSport sa screenshota; LAB:
Pinnacle bez marže, inače prosjek kladionica). "ODBAČENO" samo uz pola širine intervala ≤ 4pp,
inače "nije potvrđeno" (pravilo 01.11.2026). Ništa ne ulazi u model bez korisnikova odobrenja.

LAB presuda (ista funkcija kao 25.10.2026, `r_lab_d.verdict`): **PROLAZI** = smjer kako je zapisan,
interval ne prelazi 0, obje polovice (P1/P2) isti predznak, |edge| ≥ 2pp, Holm < 0,05 unutar
obitelji, stabilno po razini/rundi/pojasu; **SLAB** = smjer + interval + polovice; inače **PADA**.
Na istom povijesnom uzorku dosad 109 testova (88 do 25.10. + 21 na 01.11.); uz Holm se ispisuje i
P × (109 + današnji).

## A. Doba dana (ideja 1)

- **A0 (stavka "Noćna sesija" iz ČEKA):** pickovi od 05.10.2026 sa `session`. Mjera: edge noć −
  edge dan, ponderirano po pojasu cijene. **Prolazi** (→ kandidat, potvrda na sljedećih 60 noćnih)
  samo ako je razlika ≥ +5pp, interval noćnog edgea iznad 0 i STARO (27.07.–04.10.) istog
  predznaka. 0 do +5pp → ostaje opis; ≤ 0 → PADA. Snaga: ~70 noćnih → ±11pp.
- **A1 (opis):** jutro (< 13:00 lokalno), popodne (13:00–17:59), večer (≥ 18:00), od 27.07.2026.
- **A2 (opis):** po igraču, oba igrača svakog analiziranog meča (ne samo pick), igrači s ≥ 4
  meča i danju i noću. Povijesni izvori (TML, tennis-data, berba RapidAPI) nemaju sat početka →
  povijesna predprovjera nije moguća.

## B. Umor (ideja 4) — LAB 2022 – 06.10.2026, strogi datum

"Tjedan igranja" = kalendarski tjedan (pon–ned) s barem jednim mečem (glavni ždrijeb, Challenger
ili kvalifikacije). **Niz** = broj uzastopnih tjedana igranja neposredno prije tjedna u kojem je
počeo aktualni turnir (aktualni turnir se ne broji). Odmor = dana između prethodnog i ovog meča − 1.

| test | definicija (A = strana koja se mjeri) | smjer |
|---|---|---|
| U1 | A niz ≥ 3 (4.+ tjedan zaredom), B niz = 0 | − |
| U2 | A niz = 2 (3. tjedan zaredom), B niz = 0 | − |
| U3 | A ≥ 3 različita turnira u 45 dana prije početka aktualnog, B ≤ 1 | − |
| U4 | A ≥ 10 mečeva u 30 dana prije meča, B ≤ 4 | − |
| U5 | A ≥ 33 god., odmor ≤ 1 dan, B < 30 god. (korisnikova verzija) | − |
| U6 | A ≥ 30 god., odmor ≤ 1 dan, B < 26 god. | − |
| U7 | A ≥ 30 god. i niz ≥ 2, B < 26 god. | − |

Holm unutar obitelji U (7). Napomena unaprijed: srodno je već palo (ritam N1a +0,0pp n=1.394; dob ×
umor E6/E7 +0,9/−2,1; umorniji u QF+ −0,2pp) → očekivanje je nula. Ruud–Jodar: samo opis.

## C. H2H (ideja 5) — LAB, H2H samo iz mečeva prije datuma ovog meča, aktualni turnir isključen

| test | definicija | smjer |
|---|---|---|
| H1 | A vodi, ≥ 3 ranija susreta, A dobio ≥ 75% | + |
| H2 | kao H1, A je autsajder (cijena < 0,5) | + |
| H3 | "ubojica velikana": A autsajder, B je top 5, A ima ≥ 2 pobjede nad top-5 u 730 dana prije | + |

Holm unutar C (3). Već izmjereno: H2H vođa +0,7pp (n=2.897), kao autsajder −0,1pp.

## D. Runda × autsajder (ideja 9)

- **D-LAB:** edge autsajdera (cijena < 0,5) po rundi R128, R64, R32, R16, QF, SF, F (TML oznaka) i
  edge tijesnog autsajdera (0,40–0,50) po istim rundama — 14 testova, smjer + (korisnikova
  hipoteza: autsajderi prolaze češće nego kvota kaže). Holm na 14.
- **D-NAŠI (opis):** od 26.09.2026 (ručne runde): po rundi broj mečeva, stvarne pobjede
  autsajdera, očekivane (zbroj cijena autsajdera), i naši pickovi po rundi. Bez presude.

## E. Tlak zraka (ideja 10) — naši pickovi od 27.07.2026

Trećine po `weather_pressure_hpa` (razina mora = vremenska promjena).
- **E1** (nema mehanizma, provjera): edge u donjoj − gornjoj trećini. Kandidat samo ako
  |razlika| ≥ 8pp, interval ne prelazi 0, polovice isti predznak.
- **E2** (mehanizam: rjeđi zrak = brža loptica = prednost serveru): samo pickovi koji su bolji
  serveri (asovi/100 poena servisa ≥ +2 ili TML servis ≥ +2pp); razlika donja − gornja trećina
  ≥ +8pp, interval > 0, polovice isti predznak → kandidat; inače nije potvrđeno.
- **E3:** kao E2, samo dvorana/krov (`venue_shielded`).
- **E4 (opis):** tlak na tlu (nadmorska visina).
Snaga: ~200 po trećini → razlika ±12pp; E2/E3 manje.

## F. Ponovno mjerenje starih ideja na zadnjih 5 tjedana (korisnikov zahtjev 08.11.2026)

Pickovi **05.10.–07.11.2026** (Šangaj od 05.10., Lyon, Bruxelles, Almaty, Basel, Beč, Pariz;
n ≈ 268; Pariz zasebno kao jedini potpuno neviđen dio). Mjera: razlika rezidua (pobjeda −
cijena) pickova s uvjetom i bez, ponderirano po pojasu kvote (< 1,30 / 1,30–1,50 / 1,50–1,80 /
≥ 1,80). Unaprijed 13 testova:

R1 ritam (pick ≥ 2 meča u 7 d, protivnik odmor ≥ 10 d) · R2 pick ≥ 2 seta više u 7 d · R3 pick
odmor ≤ 1 d, protivnik ≥ 2 d · R4 pick stariji 4+ god. · R5 pick ≥ 30 god. i odmor ≤ 1 d · R6 ELO
jaz na podlozi u gornjoj trećini · R7 forma 10 bolja ≥ 0,2 · R8 omjer na podlozi bolji ≥ 0,10 ·
R9 hold bolji ≥ 5pp · R10 dalje došao na ovom turniru (zadnje 3 god.) · R11 scouting picka
High/Med-High · R12 pick vodi u H2H (berba RapidAPI, samo mečevi prije datuma) · R13 prosječni
ELO zadnjih 5 protivnika picka < 1700.

**KANDIDAT** (potvrda na sljedećih ~150 pickova, siječanj–veljača 2027.) ako interval razlike ne
prelazi 0 I obje polovice razdoblja isti predznak; Holm-P se navodi (uz 13 testova slučajno se
očekuje ~0,65 lažnih "P < 0,05"). Inače "nije potvrđeno". Ništa ne ulazi u model.

## G. Pariz — usporedba "nosova" (ideja 8), opis

Agent, "uvijek favorit", Intuicija (strana s p ≥ 0,5), Nose (vlastita procjena p_own ≥ 0,5;
IZBJEGAVAJ), nos-ploča: pogođeno/promašeno, edge, ROI po kvoti; Pariz i od 05.10. Bez presude —
K20, K24, K26 imaju svoje zamrznute pragove.

## H. Kombinacije iz analiza gubitaka (ideja 7)

Popis prijedloga i njihovi pragovi dopisuju se ovdje kao NAKNADNO, s vremenom, prije računanja.

## I. Podatkovne provjere (ideje 3 i 6) — bez praga

Ideja 3: zašto par s jučerašnjeg tiketa nije na današnjem (pravilo duplikata ukinuto 18.07.2026).
Ideja 6: koje je vijesti strogi detektor ozljeda (v2) označio u Parizu (Fils, Fritz, Alcaraz...).

## J. Scouting (ideja 2; korisnik 08.11.2026: "slobodno diraj i Excel i Supabase")

Pravila kao 18.10.2026 (točka S): statistika TML 365 dana do zadnjeg TML datuma, glavni ždrijeb,
≥ 25 mečeva; "veliki server" opovrgnut ako su asovi po servis-gemu < medijana I hold < medijana;
"jak povratnik" ako je povrat < medijana; "slab povrat" ako je povrat > 75. percentila; "slab
servis" ako je hold > 75. percentila. Rezultati turnira zapisuju se zasebno i sami ne mijenjaju
profil. Razine pouzdanosti se ne mijenjaju. Rang se osvježava. Novo danas: tvrdnja na koju se
analiza gubitka od 19.10. izričito pozvala, a TML je opovrgava → dobiva oznaku i kad nije na popisu
gornjih obrazaca. Original ostaje, uz njega "[08.11.2026 check: ...]"; kopija prije izmjene i
skripta za povratak.

## H — NAKNADNO 08.11.2026 11:48 (prije računanja): nove kombinacije iz analiza gubitaka (ideja 7)

Izvor: 239 jedinstvenih analiza gubitaka (28.05.–06.11.2026). Teme koje se u njima gotovo ne
pojavljuju, a znaju se PRIJE meča i nisu u registru: motivacija na kraju sezone (1,3% analiza),
uspon na ljestvici (2,9%), nedavna predaja / ozljeda iz rezultata, ne iz vijesti (7,5%), revanš.
LAB kao gore (strogi datum, isti presudni kriterij, Holm unutar obitelji Z, 7 testova; oznake Z da se ne miješaju s K brojevima registra):

| test | definicija (A = strana koja se mjeri) | smjer |
|---|---|---|
| Z1 brzi uspon | A-ov rang sada ≤ 0,70 × rang prije 90 dana (zadnji meč 90–150 d ranije), A ≤ 100; B-ov rang u ±10% | + |
| Z2 pad nakon titule | A je osvojio prethodni turnir (finale ≤ 10 dana prije početka ovog), prvi A-ov meč ovdje | − |
| Z3 nedavna predaja | A-ov prethodni meč (≤ 21 d) završio je A-ovom predajom (RET) — ponovna provjera nalaza 26.09. (+3,5 naspram +2,4pp na berbi) | − |
| Z4 revanš u 21 dan | A je pobijedio B u zadnja 21 dana (drugi turnir); sad ponovno igraju | + |
| Z5 kraj sezone × top 5 | turnir počinje u listopadu/studenom (bez ATP Finala), A je top 5 i favorit | − |
| Z6 kraj sezone × niz | listopad/studeni, A niz ≥ 2 tjedna zaredom, B niz 0 | − |
| Z7 kraj sezone × mlađi od 23 i niz ≥ 2 (Jodar) | listopad/studeni, A < 23 god. i niz ≥ 2, B niz 0 | − |

Kandidat za praćenje (nos-ploča / Intuicija, u sjeni) samo ako je PROLAZI ili SLAB uz interval
koji ne prelazi 0; inače "nije potvrđeno" / "odbačeno" po širini intervala.

## J — NAKNADNO 08.11.2026 11:53 (prije računanja): scouting, točna pravila izmjene

Statistika: TML preuzet 08.11.2026 (2025.csv, 2026.csv, turniri u tijeku), 365 dana do zadnjeg
datuma u datoteci, glavni ždrijeb ATP razine (bez Davis Cupa), ≥ 25 mečeva sa statistikom; iste
granice i razmaci kao 18.10. (hold i povrat ±2pp, asovi ±0,05 po gemu).
1. Četiri stara obrasca (veliki server, jak povratnik, slab povrat, slab servis) — kao 18.10.
2. **Peti obrazac (novo, jer su ga analize gubitaka od 19.10. citirale kod Musettija, Darderija,
   Etcheverryja i Ruuda): "slabiji u dvorani / na brzom terenu"** u polju mana. OPOVRGNUT ako u
   dvorani (TML stupac indoor = I) ima ≥ 12 mečeva, udio osvojenih poena u dvorani ≥ udio na otvorenom
   tvrdom I omjer pobjeda u dvorani ≥ 55%. Primjenjuje se na SVE profile s tom tvrdnjom.
3. Stara oznaka "[18.10.2026 check ...]" koju nove brojke više ne podupiru se UKLANJA (zapisuje se
   u list Promjene); ona koju i dalje podupiru ostaje netaknuta.
4. Rang: najnoviji rang iz snimki dnevnog runa od 26.10.2026.
5. Rezultati od 19.10. (naši mečevi i TML) samo opis; razine pouzdanosti se ne mijenjaju.
Prije upisa: kopija Supabase tablice (JSON) i Excela u revizije/2026-11-08/scouting/, skripta za
povratak. Excel: glavni list iz Supabasea, listovi 18.10. se čuvaju, dodaju se listovi 08.11.

## J2 — NAKNADNO 08.11.2026 12:10 (nakon prvog upisa, prije drugog): rang igrača bez snimke od 26.10.

Prvi upis (11:56) osvježio je rang samo igračima iz snimki dnevnog runa od 26.10., pa je nastalo 26
dvostrukih rangova (npr. Zverev i Sinner oba 1). Dopuna: igraču koji danas NIJE dobio rang iz snimke
upisuje se zadnji rang iz TML-a (rang u trenutku zadnjeg meča, 2026.csv + turniri u tijeku) ako je
taj meč noviji od 18.10.2026. Igrač bez TML meča od 18.10. zadržava stari rang (npr. Sinner, zadnji
meč 12.07.) i u listu Promjene dobiva napomenu "rang star". Rang i dalje ne čita ni kod ni model.
