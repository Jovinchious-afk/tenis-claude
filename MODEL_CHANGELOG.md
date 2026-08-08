# Model Changelog

Kronologija promjena modela za generiranje tiketa (predikcija + selekcija + strategija).
Svrha: da kroz iteracije znamo ŠTO smo mijenjali, ZAŠTO, i s kojim ishodom.
Težinske verzije (brojčane) žive u Supabase `model_weights`; ovdje su prompt-pravila,
selekcijska logika i strateške odluke koje se ne vide iz baze.

Format: `datum — naslov` → što / zašto / ishod (ako je poznat).

---

## 2026-08-08 11:35 — PUNA HARD REVIZIJA (90 rijesenih analiza)

Ovo je revizija koju je `run_daily` trazio svaki dan od 18.07. (okidac na 30 rijesenih hard
pickova; danas ih je 90). Okidac je premjesten na sljedeci prag (180) da ne postane sum.

**Korpus:** hard od 01.08.2026, **90 analiza / 78 rijeseno / bazna stopa 60,3%**; 42 meca sa
statistikom poravnatom na nas pick preko player ID-a; 16 analiza gubitaka.

### A — UKLJUCENO, ne dira izbor igraca

- **ELO u `context_snapshot` (v9).** `elo_ranking` nosi 19% tezine na hardu, a ELO se nigdje
  nije zapisivao — korelacija "ELO <-> ishod" doslovno se nije mogla izracunati. Biljeze se
  sirove ocjene, ocjena po podlozi i RAZLIKA (ono sto model zapravo koristi).
- **Broj protivnika u `avg_opp_elo`** (`_avg_opponent_elo_n`). Protivnici bez ELO-a se tiho
  ispustaju, a nedostaju sustavno slabiji, pa prosjek ispada previsok. Vrijednost je
  NEPROMIJENJENA; biljezi se samo koliko ih je uslo, da se pristranost moze izmjeriti.
- **`PYTHONUNBUFFERED=1`** u workflow — logovi vise ne kasne u nakupinama.
- **Hard okidac utisan** s 30 na 180; dnevni ispis sada javlja stanje korpusa umjesto da vristi.

### B — UKLJUCENO, mijenja izbor igraca

- **Break lopte idu u prompt** (`_BP_TO_PROMPT` False -> True). Do 07.08. su bile `None` zbog
  krivih naziva API polja; model ih nikad nije vidio. Dokaz (n=42): tko napravi vise breakova
  od protivnika ide **21W-1L**, tko manje **1W-17L**; nas pick u porazima prima **8,6** break
  lopti naspram **5,0** u pobjedama (p=0,002); "primljene BP" je najjaca pojedinacna
  korelacija s ishodom (**r=-0,44, p=0,002**), dok iskoristivost vlastitih prilika NIJE
  znacajna (r=+0,19, p=0,250). Svih **16/16** analiza gubitaka imenuje servis/hold.
  Zakljucak: gubimo jer nasem igracu servis bude napadnut, ne jer propusta prilike.
- **Zona opreza suzena 1.43-1.90 -> 1.43-1.60.** Stara zona spajala je dvije suprotne
  polovice (n=84, nefiltrirano tiketom): 1.43-1.60 ROI **-13,4%**, 1.60-1.90 ROI **+6,5%**
  (jedini pozitivan raspon). Pravilo "max 1 po tiketu" guslo je bas ono sto donosi novac i
  uzrokovalo analysis-only 04.08. Nijansa koja se ne smije procitati krivo: postotak pogotka
  je u zoni i izvan nje PRAKTICKI JEDNAK (60,4% vs 61,1%, Fisher p=1,000) — razlika je u
  CIJENAMA, ne u kvaliteti pickova.

**ZAMKA:** `rules_hash` se ovim NIJE promijenio (0477edbb) jer tekst prompta nije diran.
Eru prije/poslije break lopti rezati po **`context_snapshot.bp_in_prompt`** (False do
08.08. 11:35) ili po `context_version` (8 -> 9), NIKAKO po hashu.

### C — NIJE mijenjano, ceka veci uzorak

- **Prag selekcije 63%.** Kalibracija je iznad 61% monotono OBRNUTA: deklarirano 58-60% ->
  stvarnih 84,6% (n=13); 63-64% -> 57,1% (n=35); 65-67% -> **52,2%** (n=23, ROI -29,9%).
  Nasa pouzdanost korelira s ishodom **negativno** (r=-0,18), a trzisna kvota **pozitivno**
  (r=+0,15) — suprotni predznaci su nalaz. `cap_enforced` pickovi idu **12W-2L (85,7%)**.
  Najveci potencijalni dobitak i najveci rizik; n=78 je premalo za prag na kojem stoji
  cijela selekcija.
- **Ispravci `return_points_won` (+2,33pp) i `hold_pct` (x1,9).** Oba su tocna, ali oba
  guraju model prema VISE opreza — a oprez je vec prejak. Idu tek zajedno s pragom.
- **Tezine.** `serve_return` (23%, najveca) mjeri se kroz pokvarene posrednike; dizanje ili
  spustanje broja prije popravka mjeri krivo ravnalo. `fatigue_injuries` (12%) nema signala
  (1. mec 62,0% n=50, 2. mec 70,0% n=10; svjeziji 58,3% vs protivnik svjeziji 60,0%), ali ga
  10/16 analiza gubitaka krivi u SUPROTNIM smjerovima — to je sum, ne losa kalibracija.
- **Pravila u promptu formulirana kroz kvote** ("late-round picks at odds <= 1.60"). Model
  kvotu NE VIDI (jedino `_odds_alert` pri omjeru >=6:1), pa su mu ta pravila neprovediva —
  u najgorem slucaju ga navode da cijenu pogadja iz vlastite pouzdanosti. Treba ih prepisati
  u jezik koji ima pred sobom; svaka izmjena teksta mijenja pickove pa ide u isti paket.

### D — NIJE mijenjano, i ne planira se

- **`_UNDERDOG_EDGE_CAP = 28` ostaje.** Ne brani veliku kvotu nego preveliko NESLAGANJE s
  trzistem. Dokumentirano: Collignon @2,82 uz conf 71 (35,5pp) izgubio, @2,79 uz conf 64
  (28,2pp) dobio — dva dana razmaka, isti igrac. Problem je bila glasnoca, ne cijena.
- **`_UNDERDOG_MIN_ODDS = 2.00` ostaje.** Na hardu imamo cetiri picka >=2,00 u cijeloj
  sezoni (2W-2L, ROI 0,0%) — nema dokaza ni za popustanje ni za pooostravanje.
- **Vremenske zone** (rok listopad), **tlak** (n=8), **LATE-ROUND pravilo** (krive oznake
  rundi), **rubni slucaj ljestvice rundi**, **mrtva zona na travi** — svi cekaju svoj uvjet.

### Kvaliteta match stats varijabli (odgovor na korisnikovo pitanje)

Od 398 igracevih nastupa: 13 polja popunjeno 100% (asovi, dvostruke greske, servis, sve
cetiri break-lopta velicine). Sedam polja (`winners`, `unforcedErrors`, brzine servisa,
izlasci na mrezu) popunjeno je 32,7% — i to **iskljucivo za Wimbledon (65/65), 0/134 na svim
ATP turnirima**. Nije kvar: slamovi imaju bogatiji feed. Na hard sezoni se nikad nece pojaviti.

Trebaju li nam: na Wimbledon uzorku `winneri - UE` razdvaja jako (+10,9, p<0,001), ali
korelira **r=+0,46** s razlikom u breakovima koju vec imamo za svaki mec, a sve su to
POSTMECNE velicine — za predikciju bi trebao sezonski prosjek po igracu, kojeg API ne nudi
ni u jednom endpointu. **Preporuka: ne traziti vanjski izvor.**
Sporedno: asovi na TRAVI razdvajaju (p=0,005), na hardu ne (p=0,392) — trag za grass reviziju.

### Odbaceni prijedlog (da se ne predlaze ponovno)

"Primljene break lopte na 100 servisnih poena" kao nova predmecna varijabla — izmjereno na
16 igraca, korelacija sa `serve_points_won` je **r=-0,99**. Prakticki linearna preslika, nula
nove informacije. Ne fali nam varijabla; fali postovanje prema sumu (SD unutar meca je 7,9pp,
a pragovi pravila razlucuju na 1,6-2,6pp).

### Zasto usporedba starog i novog modela NIJE moguca

Cetiri ere po `rules_hash`: `023d06d4`/v14 (n=4), `2e455012`/v14 (n=19, 57,9%),
`612a7b17`/v18 (n=39, **66,7%**), `0477edbb`/v18 (n=16, **50,0%**). Stari vs novi: 56,5% vs
61,8%, Fisher **p=0,800**.
**Ali usporedba je zbunjena rundama:** `612a7b17` je 100% R32, a `0477edbb` je QF 8 / R16 4 /
R32 4 — usporedjujemo razlicite runde, ne razlicite modele. Uz to su se tezine v14->v18
promijenile ISTOG DANA kad i pravila (tezine 04.08. 09:05, pravila 13:28), pa se ni to dvoje
ne da razdvojiti. Zakljucak: na ovom uzorku se ne moze utvrditi je li model bolji ili gori.

---

## 2026-08-07 (c) — Natpisi podloge u selekciji + dvije stavke na popis za reviziju

**Povod:** pregled GitHub Actions logova od 27.07. (potpun run) i 02.08. (prekinut run) na
korisnikov zahtjev. Pipeline je ispravan; nista u logici nije mijenjano.

### Popravljeno: dva zaostala natpisa podloge (samo ISPIS, nula utjecaja na pickove)

Confidence floor prosiren je na hard 18.07., ali dva ispisa nose natpise iz doba kad je
vrijedio samo za travu i zemlju:

- skupni ispis je i na hard kartici pisao **"Grass/clay disciplina"** — log od 27.07. tako
  javlja "Grass/clay disciplina: izbaceno 8 pickova" na kartici koja je bila cijela hard;
- value-override je hard pick nazivao **"grass"**, jer je jedini izbor bio
  `"clay" if _is_clay(p) else "grass"`.

Ponasanje je oba puta bilo ispravno (`_needs_conf_floor` pokriva sve tri podloge) — krivo se
samo zvalo, sto zbunjuje pri citanju logova. Uveden `_surface_label()` koji vraca
grass/clay/hard/'?', a skupni ispis sada i razlaze broj po podlozi
("izbaceno 4 ... — clay 1, grass 1, hard 2").

### Sto je log POTVRDIO, a vec je bilo popravljeno

- **Pravilo 12:** 27.07. je izbacilo OSAM meceva, a obrazlozenja modela pokazuju da bi sedam
  od njih po pravilu od 06.08. (strogo 0/3) ostalo u igri — ukljucujuci jedan gdje je model
  napisao *"Brooksby 2/3 borderline"* i svejedno primijenio cap. Samo Norrie/Kovacevic je
  bio stvarno 0/3 na obje strane. To je 23% kartice (`Valjane predikcije: 23/31`).
- **Runde:** `Round fix: Montreal (2026-08-03) — R16 -> R32 (22 matches)` i
  `Washington — R12 -> F` — oba obrasca popravljena 07.08.
- **Vrijeme:** `Montreal (2026-08-03): Humidity 98% (forecast)` — neusklaen sat, popravljeno 04.08.
- **Prekid 02.08.:** `timeout-minutes` 20 -> 35, popravljeno istog dana.

### Dodano na popis za reviziju (zapisano uz kod, NIJE implementirano)

0. **Ljestvica procjene runde moze vratiti istu nemogucu oznaku.** Pragovi (`>= 4`, `>= 8`)
   ukljucuju i maksimum runde ISPOD, a do procjene se dolazi samo kad je n VECI od maksimuma
   trenutne oznake — dakle prava runda je nuzno ranija. Pogodjeni slucajevi: ATP 250/500
   oznaka `QF` uz n=5..7 vrati `QF`; oznaka `R16` uz n=9..15 vrati `R16`; sve razine oznaka
   `SF` uz n=3 vrati `SF`. Steta je ogranicena — ne stvara novu krivu oznaku, samo ne popravi
   staru. Popravak ("inferred mora biti strogo ranija runda od current_round") mijenja rundu
   koja ide u prompt, dakle i pickove. Biljeska stoji uz ljestvice u `_infer_rounds`.

1. **`PYTHONUNBUFFERED=1`** u workflow. Python puferira stdout pa se ispis pojavljuje u
   nakupinama (27.07.: 4,5 minute tisine pa sve odjednom). Kad je run 02.08. prekinut na 20
   minuta, iz loga se NIJE moglo vidjeti gdje je zapeo — timeout je podignut zakljucivanjem,
   ne mjerenjem. Biljeska stoji u `.github/workflows/daily_ticket.yml`.
2. **Broj protivnika u `_avg_opponent_elo`.** Protivnici bez ELO-a se tiho ispustaju, a oni
   koji nedostaju sustavno su SLABIJI (kvalifikanti, challengeri, wildcardi izvan
   `elo_cache`; nekoliko desetaka `ELO MISS` po runu). Prosjek zato ispada PREVISOK, pa igrac
   koji je punio omjer protiv slabe konkurencije izgleda kao da je pobjedjivao jake — a to je
   bas nas "kvalitetom prilagodjen" signal forme. Velicina ucinka je NEPOZNATA jer ne
   biljezimo koliko je protivnika uslo u prosjek. Biljeska stoji uz funkciju.

### Izmjereno usput (n=325 razrijesenih nogu, sve podloge) — NISTA nije mijenjano

Tocnost pickova **60,9%**; za nulu uz prosjecnu kvotu 1,60 treba **62,6%**. Manjak je 1,7pp,
ROI po ravnom ulogu -5,2%. Po razredima kvota nijedna razlika nije znacajna (svi P > 0,13),
ukljucujuci ">1,90 nosi +11,9% ROI" (P=0,558) — smjer se poklapa s nalazom s trave i zemlje,
dokaz nije.

Tiketi: 4 para 2W-19L, 5 parova 1W-14L, 6 parova 1W-7L; ukupno 4W-41L (-43%). Noge su blizu
nule, tiketi gube 43% — razlika je mnozenje blago negativnog ruba kroz 4-6 nogu, dodatno
pogorsano time sto noge dijele turnir i uvjete pa padaju zajedno. Ilustracija iz loga: tiket
od 27.07. imao je **5 od 6 tocnih pogodaka i svejedno propao** (Tommy Paul @1,35).
Ovo je odluka o strategiji (broj parova / minimalna kvota), ne kod — ceka korisnika.

---

## 2026-08-07 (b) — Break lopte nikad nisu stigle do modela + servis/povrat u snapshot

**Povod:** korisnik odobrio biljezenje `hold_pct` / `return_pct` / `serve_points_won` uz
pitanje moze li se to uopce izvuci iz API-ja. Provjera sirovog odgovora otkrila je vecu stvar.

### NALAZ: `break_points_saved` i `break_points_converted` UVIJEK su bili None

`get_player_stats` je citao `breakPointOf` / `breakPointSave` / `breakPoint`, a API vraca
`breakPointFacedGm` / `breakPointSavedGm` / `breakPointChanceGm` / `breakPointWonGm`.
`.get()` na nepostojeci kljuc vraca None bez greske, pa je prompt od prvog dana ispisivao
doslovno **"BP saved: None | BP converted: None"** za oba igraca. Nista to nije javljalo.

Zasto je to skupo: analiza Montreala istog dana pokazala je da break lopte odlucuju mec —
tko napravi vise breakova od protivnika ide **14W-1L**, tko manje **1W-12L**; nas pick u
porazima prima **8,8** break lopti naspram **5,5** u pobjedama (p=0,028), dok razlika u
iskoristenosti vlastitih prilika nije znacajna (p=0,380). Jedina varijabla koja cisto
razdvaja pobjede od poraza bila je jedina koju model nije vidio.

**Nazivi popravljeni, ali prompt NAMJERNO ostaje nepromijenjen** — zastavica
`predictor._BP_TO_PROMPT = False`. Otvaranje tog podatka mijenja pickove, a model je zamrznut
radi cistog pripisivanja do revizije 08.-09.08. Vrijednost se od danas biljezi i mjeri.
Na reviziji je to izmjena jedne linije.

### Dvije pristranosti u postojecim brojkama (utvrdjeno, NIJE mijenjano)

**1. `return_points_won` sustavno precjenjuje za +2,33pp.** Racuna se kao NEPONDERIRANI
prosjek povrata na 1. i 2. servis, a prvi servis nosi ~60% return-poena i povrat je ondje
bitno tezi (~31% naspram ~51%). Izmjereno na 14 igraca: raspon +2,0 do +2,7, uvijek isti smjer.
Pravilo 13 ima pragove na 40%, "unutar 1pp od 42%", 43-45% i 45%+ — koraci od 1pp na velicini
pomaknutoj za 2,3pp. Rulu je 02.08. dodan "sliding threshold" bas jer se *"defused by a hair
in THREE straight losses"*; dokumentirani primjer u samom pravilu je "De Minaur 42.5%", a
njegov stvarni ponderirani povrat je **40,3%**.

**2. `hold_pct` je proxy s mnoziteljem 1,9.** API ne daje broj gem-ova na servisu (provjereno
na sirovom odgovoru), pa se pravi hold% ne moze izracunati — korisnikova pretpostavka bila je
tocna. Posljedica mnozitelja: prompt vidi razliku gotovo dvostruko vecu nego sto jest, pa
pragovi stvarno znace: "hold gap >= 3pp" -> 1,58pp poena na servisu, ">= 5pp odlucujuci" ->
2,63pp, "protivnik drzi >= 82%" -> 64,2% poena na servisu. Izmjereno na 58 nastupa u Montrealu:
prosjek 62,5%, **SD 7,9pp**. Pravila razlucuju na razlikama 3-5x manjima od sluma unutar meca.

Obje vrijednosti ostaju nepromijenjene u promptu jer su pragovi pravila empirijski ugadjani
PROTIV njih; ispravak broja bez ponovnog ugadjanja pragova pomaknuo bi ponasanje u
neizmjerenom smjeru. Ispravljene verzije (`return_points_won_weighted`, `hold_pct_from_bp`)
se od danas biljeze usporedno.

### context_snapshot v8 (samo biljezenje, nula dodatnih API poziva)

Po igracu: `serve_pts_won`, `hold_pct`, `hold_pct_from_bp`, `return_won`,
`return_won_weighted`, `bp_saved`, `bp_converted`, `first_serve_pct`; plus `bp_in_prompt`.
Sve dolazi iz `get_player_stats` koji se ionako vec poziva.

Svrha: bez ovoga se ne moze izmjeriti KOLIKO CESTO pravila 13 i 16 uopce okinu ni kako prolaze
pickovi na koje su okinula — a to je preduvjet za bilo kakvu odluku o pragovima na reviziji.

---

## 2026-08-07 — Duplikati analiza, runde, ELO trag (revizija evidencije, ne modela)

**Povod:** korisnik je u Supabaseu uocio da su neki Montreal mecevi oznaceni QF, a vecina
R32, iako je rijec o istoj rundi. Provjera je otkrila da je pogresna runda simptom, a ne
uzrok.

### 1. Duplikati: 22,6% korpusa bila je ista utakmica upisana dvaput

`stable_match_key` (uveden 31.07. protiv reciklaze API ID-a) sadrzi **datum**, a datum nije
stabilan. Mecevi se dohvacaju za danas+sutra(+prekosutra), pa isti mec prvo vidimo pod
provizornim datumom, a idui dan pod stvarnim — API ga pomakne kad se raspored slegne ili kad
padne kisa. Kljuc se promijeni, upsert promasi postojeci redak, nastane drugi zapis.
Oba zatim budu razrijesena istim pobjednikom jer `_build_season_winner_lookup` trazi po
imenima, bez datuma.

Izmjereno: **45 parova, 90 od 399 redaka**; kod 44 od 45 oba retka razrijesena istim
pobjednikom. Svih 45 unutar 3 dana, nijedan izvan.

**Popravak:** `find_existing_analysis` (±3 dana, korisnikov prag) trazi postojeci zapis prije
upisa; ako ga nade, zadrzi njegov `external_match_id` a osvjezi `match_date` na noviji (to je
datum kad je mec stvarno odigran, a na njega vezemo vrijeme i uvjete). Identitet meca je od
sada trojka (turnir, par igraca, ±3 dana); `external_match_id` je samo ID retka.
Povijest ociscena skriptom `scripts/merge_duplicate_analyses.py` (399 -> 354 retka,
sigurnosna kopija prije brisanja).

**Ishod na brojke:** hard 66W-39L (62,9%) -> **52W-30L (63,4%)**;
Montreal 49W-33L (59,8%) -> **38W-24L (61,3%)**, n 82 -> 62.

**ISPRAVAK NALAZA OD 06.08.:** prva, gruba deduplikacija (zadrzi najraniji redak) pokazala je
da `cap_enforced` pada s 11W-1L na 8W-1L i da P raste s 0,034 na 0,104. **To je bilo krivo.**
Pravilo "zadrzi najraniji" arbitrarno je bacalo bas one retke koji nose `cap_enforced` (raniji
redak je stariji `context_version` i nema to polje). Nakon ispravnog spajanja (zadrzi bogatiji
+ dopuni polja iz blizanca) ostaje **12 razlicitih meceva, 11W-1L, P=0,034** — nalaz od 06.08.
stoji nepromijenjen, kao i "pravilo 12: 6 puta, 6W-0L". Korpusne brojke iznad jesu bile
napuhane; ovaj konkretni nalaz nije.

### 2. Runde: tri neovisna kvara

Prije popravka **170 od 399 redaka (42,6%)** sjedilo je u grupi (turnir, runda) gdje isti
igrac igra vise puta — fizicki nemoguce. Samo "Montreal R32": 97 redaka, 68 ponovljenih
igraca (Hurkacz "R32" 03., 04., 05. i 07.08.). Runda ide ravno u prompt i nosi vlastita
pravila (LATE-ROUND PRICING DISCIPLINE, hot-hand), pa je kriva oznaka mijenjala pickove.

- **(a)** `_infer_rounds` je grupirao po (turnir, datum) i uzimao `group[0]["round"]` kao rundu
  cijelog dana. Dan legitimno nosi dvije runde (Wimbledon 02.07. R64+R32, Bastad 13.07.
  R32+R16, Montreal 06.08. R32+QF), a kad bi ispravak okinuo, prepisao bi **cijelu grupu**
  jednom oznakom i unistio manjinu koja je bila tocna. Sada se grupira po
  **(turnir, datum, runda)**.
- **(b)** Ljestvica za Masters stajala je na `n >= 8 -> R32`, bez precki R64/R128. Masters je
  od 2025. zdrijeb od 96 s 12 dana igre, gdje prve dvije runde imaju po 32 meca — otud dan s
  28 meceva kao "R32". Dodane precke R64/R128 (i R32 za ATP 250/500, R128 za GS).
  Ogranicenje: broj meceva ne razlikuje 1. od 2. runde u zdrijebu od 96, obje imaju 32.
- **(c)** Od uvodenja screenshot-gatea 27.07. brojanje se radilo na **filtriranom** skupu —
  gate je na liniji prije `_infer_rounds`. Ako screenshotas 12 od 16 meceva, procjena runde
  racunala je 12. Sada `_count_by_tournament_day` broji **prije** gatea.
- **(d)** `_warn_impossible_rounds` ispisuje upozorenje kad isti igrac igra vise puta u istoj
  (turnir, runda). Ne ispravlja nista — samo vice. Ovaj obrazac bio je jedini pouzdan trag da
  su oznake krive, a nista ga nije ispisivalo.

**Povijesni redci se NE ispravljaju** — prava runda se ne da pouzdano rekonstruirati (nedostaju
nescreenshotani mecevi, ima slobodnih prolaza). Nakon spajanja duplikata udio nemogucih grupa
pao je s 42,6% na 31,1%; ostatak je stvarna pogresna oznaka.
**Posljedica: nalaz "QF/SF/F kratke kvote gube -10,2% ROI" stoji na tim oznakama i treba ga
ponovno izmjeriti na cistom uzorku.**

### 3. ELO cache: nije se znalo koliko je star

`upsert_elo_cache` nikad nije postavljao `updated_at`, a `DEFAULT NOW()` okida samo pri
INSERT-u — pa je stupac biljezio kad je igrac **prvi put videN**, ne kad je ELO osvjezen.
521 od 567 redaka nosilo je 31.05. Sada se upisuje izrijekom, a dnevni run ispisuje
"ELO cache osvjezen prije N dana" s podsjetnikom preko 7 dana. `elo_ranking` nosi 19% tezine
na hardu, pa je slijepa tocka bila skupa.

### 4. `tournament_history` dodana u schema.sql

Tablica je u Supabaseu postojala (668 redaka) ali je nije bilo u shemi — podizanje baze od
nule ostavilo bi model bez povijesti zdrijebova. Postojeca instanca ne treba nista.

### Namjerno NIJE dirano

- **Prosirenje prozora razrjesavanja (8 dana).** 119 analiza nikad nije dobilo ishod, ali sve
  su iz svibnja/lipnja/srpnja i API ih vise nema; iz kolovoza nijedna nije zaglavljena.
  Promjena bez dobitka.
- **Nista sto mijenja pickove.** Model ostaje zamrznut do revizije; brojke na kojima bi se
  promjena opravdavala bile su napuhane, pa se prvo cisti evidencija, pa mjeri.

---

## 2026-08-06 — Pravilo 12 uskladjeno s kodom (0/3, ne "1/3 ili losije")

**Povod:** puna analiza dobitaka i gubitaka za Montreal na korisnikov zahtjev, prva koja je
koristila novopopravljenu statistiku meca i `context_snapshot` v7.

**Korpus:** Montreal 02.-06.08., **73 razrijesene analize, 44W-29L (60,3%)** — ukljucujuci
meceve koji nikad nisu dosli na tiket, dakle nepristran uzorak.

### NALAZ: nasa vlastita pravila opreza izbacivala su POBJEDNIKE

Kad kod prisilno spusti pouzdanost na cap koji je model sam proglasio (`cap_enforced`), ti
pickovi idu **11W-1L (91,7%)** naspram bazne stope 63,5% na hardu. **P(X>=11 | p=0,635) =
0,034.** Svih 12 clampanih zavrsi ispod 63%, dakle svi ispadnu iz selekcije — nije rijec o
dva nalaza nego o jednom: unutar iste skupine ispod praga, clampani idu 11W-1L, neclampani
2W-1L.

Po pravilima: **12 (oba igraca u padu) 6 puta, 6W-0L**; 13 dvaput (1W-1L); 16 dvaput (2W-0L);
15 i 4 po jednom (2W-0L).

**Mehanizam.** Prompt je trazio "1/3 ili losije", a kod (`_is_declining`) strogo 0/3. Ta
razlika NIJE bila slucajna: korisnik ju je uocio 20.07. kad je siri prag izbacivao 43%
ponedjeljkovih parova, pa je KOD zategnut, a u changelogu je zapisano da je "1/3 ili losije"
**neprovjerena generalizacija**. Prompt je tada namjerno ostavljen siri. Posljedica: model se
sam capira na sirem kriteriju i spusti pick ispod 63, pa ga selekcija odbaci **prije nego kod
uopce dobije priliku primijeniti svoj strozi prag**. Sest puta u tri dana, svih sest pobijedilo.

**Izmjena:** hard pravilo 12 sada trazi **strogo 0/3 za oba igraca**, uz izricitu recenicu da
1/3 NE okida. Clay i grass NAMJERNO ostaju siri — za njih nemamo mjerenje, a izmjena bi im
promijenila `rules_hash` usred hard sezone. Revidirati kad te podloge dodju na red.

### Ostali nalazi — zabiljezeni, NISU implementirani

- **Pouzdanost je na vrhu anti-prediktivna:** ispod 63 -> 86,7% (n=15), 63-64 -> 56,8%
  (n=37), **65+ -> 47,6% (n=21)**. Na punom hard korpusu 65+ ide 14W-13L, P=0,09.
- **Mecheve odlucuju BREAK LOPTE, ne servis** (n=26 sa statistikom): iskoristene BP 47,9%
  (dobitci) vs 31,5% (gubici) = 16,4pp razlike; spasene BP 59,5% vs 47,9% = 11,6pp. Sve
  servis-metrike su ispod 6pp, a dvostruke greske ne razlikuju NISTA (4,6 vs 4,4). Model
  tezi servisu (`serve_return` 22%) a o break loptama zna samo posredno. Nije ugradivo
  izravno (BP je ishod, ne predmecni podatak) — treba bolji predmecni proxy za clutch.
- **Kvote:** 1,60-1,90 -> 65,2%, ROI **+13,5%** (potvrdjuje nalaz od 05.08.); <1,43 -> 68,0%
  ali ROI -13,6%; **>1,90 -> 2W-6L, ROI -52,5%** — sto PROTURJECI sezonskom nalazu da su
  underdogovi profitabilni. Taj je nalaz bio s trave i zemlje (n=36); ovo je prvi pravi hard
  uzorak (n=8) i ide suprotno. Ne dirati nista dok se ne skupi vise.

### Sto se IZRIJEKOM ne tvrdi

**Vremenski nalazi su na ovom uzorku bezvrijedni.** Vlaga >=62% -> 70,8%, hladnije -> 76,5%,
vjetar >=15 km/h -> 76,5%. Zvuci uvjerljivo, ali svih 39 meceva dolazi iz **pet dana** —
dakle pet neovisnih vremenskih situacija, ne 39 — a te su tri varijable i medjusobno vezane
(hladno-vlazno-vjetrovito je jedno stanje). Isti tip konfundiranja koji je 04.08. vec jednom
proizveo prividan signal. Brzina terena je neupotrebljiva: svih 39 meceva oznaceno "fast".

**Ishod:** 8 novih asercija (ukupno 120), ukljucujuci provjeru da se prag u promptu i u kodu
(`_is_declining`) sada stvarno poklapaju, te da clay/grass NISU dirani.

---

## 2026-08-05 (najkasnije) — Analiza gubitka NIKAD nije vidjela statistiku meca (BUG)

**Povod:** korisnik trazio provjeru generira li vecernja analiza gubitka zakljucke na temelju
statistike meca (dvostruke greske, break lopte, postotak drugog servisa) ili samo rezultata.

**Nalaz: nije — i to od uvodjenja.** `_format_match_stats` je vracala PRAZAN STRING za svaki
mec. Dva tiha neslaganja imena:
  - trazila je `stats["player1"]` / `["p1"]`, a podaci dolaze pod `player1Stats`;
  - trazila je snake_case (`double_faults`, `break_points_saved`), a API vraca camelCase
    (`doubleFaults`, `breakPointSavedGm`).
Nijedno polje se nije poklopilo, pa se vracalo "". Provjereno na stvarnom zapisu: izlaz
duljine 0. Statistika se uredno dohvacala i spremala (171 mec u bazi) — samo nikad nije
dosla do Claudea. To objasnjava zasto su analize bile opcenite ("servis je popustio") umjesto
konkretne ("iskoristio 2 od 9 break lopti").

**DRUGI BUG, otkriven pri popravku prvog — statistike su bile pripisane KRIVOM IGRACU.**
Redoslijed igraca u statistici ne prati nas: od 56 meceva koji imaju oba podatka, kod **24
(43%)** se `player1Stats.player1Id` ne poklapa s nasim `player1_id`. Da je popravak samo
preslikao polja po poziciji, analiza bi u gotovo pola slucajeva dobila ZAMIJENJENE brojke i
izvela samouvjereno pogresan zakljucak — mjerljivo gore nego bez statistike. Sada se
poravnava po ID-u; kad se ID-evi ne poklapaju ni u jednom smjeru, ili kad nasih ID-eva nema,
blok se **namjerno izostavlja** umjesto da se pogadja (115 starijih zapisa bez ID-eva).

**Uz to:** racunaju se postoci (API daje "35 od 59", model bolje rezonira s "59,3%"), a
polja koja su kod ovog izvora cesto null (winners, unforced errors, izlasci na mrezu)
izostavljaju se umjesto da se ispisuje "N/A | N/A".

### Zamrznuto automatsko azuriranje tezina (opcija B, korisnikova odluka)

Analize gubitaka hrane `_maybe_update_weights`, koja mijenja ZIVE tezine. Kako su analize od
sada bitno bogatije, prijedlozi tezina bi se mogli promijeniti — a model je istog dana
zamrznut 3-4 dana radi ciste atribucije. Zato je uveden prekidac
`WEIGHTS_AUTO_UPDATE_ENABLED = False`: analize se i dalje generiraju i spremaju u punom
obliku, ali se tezine ne miču. **ODMRZAVANJE: vratiti na True nakon revizije ~08.-09.08.2026.**
To je jedini prekidac — nema drugih mjesta koja diraju tezine.

### player1_id / player2_id u analyzed_matches

Spremaju se pri generiranju analize, gdje ih ionako vec imamo — **nula dodatnih API poziva**.
Bez njih se post-match statistika ne moze dohvatiti za meceve koji NISU bili na tiketu, a to
je veci dio korpusa (384 analize naspram 334 tiketna zapisa), niti se moze provjeriti
poravnanje igraca. Trazi `ALTER TABLE` (vidi schema.sql); `save_analyzed_match` ima
defenzivni fallback pa spremanje ne pada dok se ne pokrene.

**Ishod:** 13 novih asercija (ukupno 108) — ukljucujuci zamijenjen redoslijed koji se
ispravlja po ID-u, odbijanje kad se ID-evi ne poklapaju, i provjeru da je zamrzavanje aktivno.
Popravak provjeren na stvarnim podacima: blok se sada generira za 56/56 meceva koji imaju
ID-eve (prije 0/171).

### Regeneracija starih analiza (isti dan, korisnikov zahtjev)

Sve postojece analize gubitaka napisane su bez statistike, pa su bile opcenite. Regenerirano
je **19 analiza + 2 kopirane** (`scripts/regen_loss_analyses.py`), tocno one kojima se blok
sa statistikom stvarno moze sastaviti; preostalih 105 namjerno preskoceno jer im regeneracija
ne bi promijenila nista (nemaju spremljenu statistiku ili nemaju ID-eve).

**Korisnikova briga oko recikliranja ID-eva — provjerena i rijesena.** Bojazan je legitimna
jer se *fixture* ID-evi dokazano recikliraju (bug 31.07.). Provjera na nasim podacima: 66
igraca kroz 12 dana, **nijedan ID nije promijenio igraca** (66 ID-eva ↔ 66 imena, nula
sudara u oba smjera), a 10 od 10 ID-eva spremljenih prije 11 dana i danas se razrjesava u
istog igraca. Dakle recikliraju se ID-evi MECEVA, ne igraca.
Neovisno o tome, regeneracija ne radi **nijedan API poziv**: cita iskljucivo spremljenu
`match_stats` i spremljeni `player1_id`, a oboje je zabiljezeno u ISTOM trenutku, pa je
poravnanje interno konzistentno bez obzira sto API kasnije radi.

**Usput popravljeno:** vecernji update je statistiku uvijek dohvacao IZNOVA preko
`name_to_id`/`match_to_tournament`, a oboje se gradi iz DANASNJEG rasporeda — za mec od
prije tjedan dana ti igraci i turnir vise nisu u feedu, pa je `stats` ispadao prazan i
analiza je i dalje ostajala bez brojki. Sada spremljena statistika ima prioritet, a dohvat
je fallback.

**Primjer ucinka** (Atmane-Draper, 04.08.): stara analiza je nagadjala ("vjerojatno je
popustio pod opterecenjem"); nova navodi da je Draper iskoristio 2 od 9 break lopti (22,2%)
naspram Atmaneovih 3 od 4 (75%), uz 50,7% prvog servisa — dakle konkretan, provjerljiv uzrok.

### Brzine servisa + statistika za NE-tiketne meceve (korisnikov zahtjev, isti dan)

**Brzine servisa** — revizija svih polja koja API vraca (342 igraceva zapisa iz 171 meca)
pokazala je da je svih 13 polja koja koristimo popunjeno **100%**, a neiskoristene su bile
tocno tri: prosjecna brzina 1. i 2. servisa te najbrzi servis (popunjenost ~38%, samo turniri
s mjeracima). To je **korisnikova ideja br. 6 iz srpnja**, tada odbacena uz biljesku da
"brzina servisa nije dostupna ni na jednom endpointu" — sto je bilo tocno ZA PREDIKCIJU
(prije meca je ne mozemo znati), ali POSLIJE meca postoji i vec se sprema. Sada se cita;
redak se izostavlja kad podatka nema. Nista drugo u odgovoru nije neiskoristeno.

**`match_stats` u `analyzed_matches`** — do sada je post-match statistika postojala SAMO u
`ticket_matches`, dakle samo za pickove koji su prosli prag 63% i dosli na tiket. Posljedica
je bila nesimetrija koja je blokirala upravo ono zbog cega se korpus i gradi:

| | uvjeti prije meca | statistika iz meca |
|---|---|---|
| `analyzed_matches` (384) | DA | **NE** |
| `ticket_matches` (334) | NE | DA (171) |

Vlaga, tlak i vjetar zivjeli su u jednoj tablici, a asovi i break lopte u drugoj, i
preklapali se samo na tiketnim pickovima — dakle na **selektiranom i pristranom** uzorku.
Mecevi koje smo analizirali pa odbacili najvredniji su za ucenje jer pokrivaju cijeli raspon,
ne samo ono u sto smo bili sigurni.

Sada vecernje razrjesavanje upisuje statistiku i u `analyzed_matches`. Cijena: **jedan API
poziv po razrijesenom mecu (~10-18 po veceri), nula Claude poziva** — onih ~20 centi po
vrtnji trosi Claude, a ovo ga ne dira. Trazi `ALTER TABLE` (schema.sql);
`save_analyzed_match_stats` je namjerno ODVOJEN od upisa ishoda pa razrjesavanje prolazi i
dok stupac ne postoji — ishod je vazniji od statistike.

---

## 2026-08-05 (kasno) — Tlak u zapis (context_snapshot v7)

**Povod:** korisnikov prijedlog da se biljezi i atmosferski tlak, radi kasnije korelacije sa
stilom igre i statistikom meca.

**Sto:** `weather_pressure_hpa` (na razini mora) i `weather_pressure_ground_hpa` (prizemni,
gdje ga API daje) ulaze u `context_snapshot`. Na visinskim turnirima (Bogota, Quito, Gstaad)
te se dvije brojke bitno razlikuju, a visina je ono sto vec imamo u `altitude`.
**SAMO SE BILJEZI — ne ulazi u prompt i ne utjece ni na jedan pick**, pa ne krsi zamrzavanje
modela dogovoreno istog dana.

**OGRADA za kasniju analizu:** "prirodni" tlak igraca NEMAMO. Iz API-ja znamo samo
nacionalnost, ne mjesto treniranja ni nadmorsku visinu doma. Mjerljivo je zasad samo tlak na
mecu i njegov odnos prema nadmorskoj visini turnira. Korisnikova hipoteza (razlika izmedju
tlaka na koji je igrac naviknut i tlaka na mecu) trazi podatak koji trenutno nemamo.

**Usput popravljeno:** fallback grana (`get_weather_for_tournament`, trenutno vrijeme) gradila
je svoj dict rucno, pa bi mecevi koji na nju padnu tiho ostali bez tlaka. Sada obje grane
koriste isti `_entry_to_weather`.

---

## 2026-08-05 — Kasnjenje kasnijih valova (+1h) i novo pravilo odabira prognoze

**Povod:** korisnikovo zapazanje da samo PRVI mecevi dana krecu po rasporedu — sve iza njih
ceka da se prethodni mec na tom terenu zavrsi.

**Pravilo (korisnikovo):** najraniji val dana ide tocno kako pise, **svi ostali dobivaju +1h**,
bez obzira koliko meceva ima u kojem terminu. Pomak vrijedi i za odabir prognoze i za oznaku
dan/noc — inace bismo tvrdili da mec igra po danu, a citali prognozu za noc.

**"Najraniji" se odredjuje po (turnir, LOKALNI DAN TURNIRA), iz stvarnog trenutka:**
- **po turniru**, jer se kasnjenje gomila unutar jednog turnira; ako Montreal krece u 17:00
  a Cincinnati u 19:00 (po Zagrebu), Cincinnatijev prvi val ne smije dobiti +1h;
- **po lokalnom danu turnira, ne po zagrebackom datumu.** Korisnik meceve iza ponoci namjerno
  sprema pod "danas" (kladionica ih tako lista, jer se sutra na njih vise ne moze kladiti).
  Za Montreal je "cet 02:10" zapravo srijeda 20:10 lokalno — zadnji mec ISTOG turnirskog dana.
  Provjereno 05.08.: svih 23 para pada u isti montrealski dan;
- **iz stvarnog trenutka, ne iz sata na ekranu** — "cet 00:00" bi kao string bio najraniji, a
  zapravo je pretposljednji. Kratica dana (uvedena 04.08.) to rjesava sama.

**Zasto NE "najranije vrijeme prije ponoci"** (korisnikova prva formulacija): za turnire na
istoku bi puklo. Melbourne je u sijecnju Zagreb +10, pa Australian Open krece u 11:00 po
Melbourneu = **01:00 po Zagrebu** — ondje su SVI mecevi "poslije ponoci", a prvi je bas taj u
01:00. Grupiranje po lokalnom danu turnira radi jednako za Montreal, Dubai i Melbourne, bez
ijedne iznimke u kodu.

**Novo pravilo odabira zapisa prognoze (korisnikovo):** OpenWeather daje zapise svaka 3 sata.
Uzima se **zadnji zapis prije meca**, a ako je mec **1 sat ili vise** nakon njega, pomak na
**sljedeci**. Korisnikov primjer: mec u 15:00 uz zapise 14:00 i 17:00 -> razlika tocno 1h ->
uzima se 17:00, iako je 14:00 "blizi". Obrazlozenje: pristranost prema kasnijem zapisu je
realnija od simetricnog zaokruzivanja kad mecevi ionako kasne. Zamjenjuje dosadasnji
"najblizi zapis". Cache kljuc sada nosi sat I minutu (18:10 i 18:30 mogu pasti na razlicite
zapise). `scheduled_local_time` i `wave_first` idu u `context_snapshot` — da se kasnije moze
izmjeriti je li pretpostavka o +1h bila dobra.

**Pomak se primjenjuje SAMO kad vrijeme dolazi sa screenshota.** Kod API-jevog sata ne znamo
u kojem je mec valu, pa se ne nagadja.

**Verificirano na stvarnim korisnikovim parovima (05.08., Montreal, 23 para):**

| termin | pomak | raspored | efektivno | sesija | zapis | vlaga | temp |
|---|---|---|---|---|---|---|---|
| sri 17:00 | ne (prvi val) | 11:00 | 11:00 | day | 11:00 | 66% | 23,6 |
| sri 18:10 | +1h | 12:10 | 13:10 | day | 14:00 | 49% | 29,9 |
| sri 19:20 | +1h | 13:20 | 14:20 | day | 14:00 | 49% | 29,9 |
| sri 20:50 | +1h | 14:50 | 15:50 | day | 17:00 | 50% | 31,2 |
| cet 00:00 | +1h | 18:00 | 19:00 | **night** | 20:00 | 71% | 24,9 |
| cet 02:10 | +1h | 20:10 | 21:10 | night | 23:00 | 75% | 23,3 |

Raspon temperature kroz dan je 23,6-31,2 C — signal koji pravilo 14 ("daytime heat speeds the
court up") dosad uopce nije vidjelo, jer je cijeli dan dobivao jedno jutarnje ocitanje.

**Ishod:** 8 novih asercija (ukupno 95) — tocno na zapisu, 30/59 min nakon (ostaje), tocno 1h
(pomak, korisnikov primjer), 1h30 i 2h (pomak), te mec prije prvog dostupnog zapisa.

---

## 2026-08-04 (najkasnije) — Screenshot je izvor istine za VRIJEME pocetka

**Povod:** korisnik poslao SuperSport screenshot koji pokazuje pocetak u 17:00 po Zagrebu,
dok je nas API tvrdio 20:00. Provjera je pokazala da je korisnik u pravu.

**Nalaz:** sluzbeni raspored turnira kaze da dnevna sesija u Montrealu pocinje **11:00 ET**
(= 17:00 po Zagrebu, tocno kako pise na screenshotu), a vecernja "not before 19:00 ET".
Nas API **nije imao nijedan mec prije 14:00 ET** — kasni oko 3 sata. Razlika NIJE konstantna
(3h00, 3h05, 3h45, 4h05 na razlicitim mecevima), pa nije rijec o pogresnoj vremenskoj zoni
koju bi se dalo ispraviti konstantom. Montreal je ljeti UTC-4 i to nas kod ima tocno.

**Dvije posljedice, obje mjerljive:**
1. **`session` (dan/noc)** iz 31.07. je bio kriv — Lehecka je po API-ju "night" (18:35 ET),
   a stvarno je dnevni mec (14:30 ET). Pravilo 14 je dobivalo krivu oznaku sesije.
2. **Izbor prognoze po satu meca** (uveden ranije istog dana) precizno je pogadjao KRIVI sat.
   Za Baeza: API 14:00 ET -> 60% vlage / 24 C; stvarno 11:00 ET -> 73% / 20,5 C.

**Izmjena:** vrijeme se sada cita SA SCREENSHOTA i ima prioritet nad API-jem — isti princip
koji vec vrijedi za kvote (18.07.) i za zdrijeb (27.07.).
- `_ODDS_EXTRACTION_PROMPT` trazi i `start_time`; kratica dana ("uto 17:00") se odbacuje,
  a ako sat nije citljiv polje se izostavlja (ne pogadja se).
- `screenshot_start_utc()` pretvara zagrebacki sat u UTC preko **pytz**, ne fiksne konstante —
  inace bi se svaki listopad pojavila tiha jednosatna greska.
- `find_screenshot_time()` trazi par kroz screenshotove SVIH dana; datum je nuzan jer sat sam
  po sebi ne odredjuje dan.
- `local_match_time()` vraca i **`local_date`** — vecernja sesija (19:00 ET) pada u sljedeci
  UTC dan, pa bi prognoza trazena po "datumu meca" pogodila krivi dan. Prognoza i cache kljuc
  sada koriste lokalni datum turnira, ne datum meca.
- `context_snapshot.time_source` ("screenshot" ili "api") — da se kasnije vidi koliko je
  analiza radilo na tocnom, a koliko na pomaknutom vremenu.
- Streamlit stranica prikazuje procitano vrijeme u obje tablice i izricito upozorava kad
  vrijeme nije procitano ni za jedan par.

**KOREKCIJA istog dana — mecevi iza ponoci.** Prvi zivi test ekstrakcije (7/7 vremena
procitano) otkrio je rupu: kladionica pod istim danom prikazuje i meceve koji pocinju iza
ponoci ("sri 00:00" u utorkovom pregledu). Korisnik ih NAMJERNO sprema pod "danas" jer ih
tako grupira i SuperSport — kladiti se na njih moze samo tog dana, sutra su vec odigrani.
**Ta konvencija spremanja se NE dira** (na njoj pociva i screenshot gate). Ali datum
spremanja tada nije datum pocetka: bez korekcije bi takav mec dobio vrijeme **24 sata
prerano**, sto je gore nego nemati vrijeme uopce. Zato ekstrakcija sada vraca i
`start_day` (kratica dana, doslovno), a `screenshot_start_utc` pomice datum naprijed do
tog dana u tjednu (dopusteno +1 ili +2 dana; dalje od toga se NE nagadja, vraca se prazno).
Provjereno na stvarnoj ekstrakciji: "sri 00:00" pod utorkom -> 18:00 ET u utorak navecer,
ispravno oznaceno kao nocna sesija.

**VAZNO za postojece podatke:** kvote spremljene prije ove izmjene nemaju `start_time`
(provjereno: 0 od 23 para za 04.08. i 0 od 9 za 05.08.). Ponovni upload iste snimke ih
nadopisuje — `save_screenshot_odds` mergea po kljucu, nista se ne gubi. Bez ponovnog uploada
pipeline pada na API-jev sat, sto je i dalje ispravno ponasanje (fallback), samo neprecizno.

**Verificirano na stvarnim mecevima** (vremena prepisana s korisnikovog screenshota):
Lehecka 18:35 ET "night" -> 14:30 ET "day" (oznaka sesije se PREOKRENE);
Baez i Hurkacz 14:00 ET / 60% vlage / 24 C -> 11:00 ET / 73% / 20,5 C.

**Ishod:** 17 novih asercija (ukupno 75) — parsiranje sata, ljetni i zimski pomak, prijelaz
preko ponoci (01:00 Zagreb = 19:00 ET PRETHODNOG dana), obrnut redoslijed igraca, odbijanje
pogadjanja kad sat nije citljiv.

---

## 2026-08-04 (kasno) — Prognoza po satu meca (BUG), ruka i common opponents u log

**Povod:** korisnikove biljeske s prijedlozima + sumnja da vlaga nije tocna ("model je za
Berrettinija rekao 99%, a ja sam na Googleu nasao 85-90%").

### A. KRITICNO: prognoza se citala za 12:00 UTC, ne za sat meca

`get_weather_for_tournament` je uzimao unos u **12:00 UTC** bez obzira kad se mec igra.
Montreal je UTC-4, pa je to **08:00 ujutro po lokalnom vremenu**. Provjereno na stvarnom
OpenWeather odgovoru za 05.08.2026:

| termin | vlaga | temperatura |
|---|---|---|
| 08:00 lokalno (sto je kod uzimao) | **68%** | **19,2 °C** |
| 14:00 lokalno (sesija meca) | 48% | 28,3 °C |
| 17:00 lokalno (sesija meca) | 52% | 28,5 °C |

**20pp greske na vlazi i 9 °C na temperaturi, uvijek u istom smjeru** — jutro je hladno i
vlazno, popodne vruce i suho.

**Tri posljedice:**
1. Pravilo 14 ("daytime heat speeds the court up") postoji od 26.07. i cijelo je vrijeme
   dobivalo jutarnju temperaturu, pa je sustavno PODCJENJIVALO vrucinu.
2. Pravila o vlazi i vjetru dodana ranije istog dana radila su na krivom ocitanju.
3. **Prekosutra je bilo najgore:** `cnt=16` je 48h, pa je zadnji dostupni unos za treci dan
   bio 08:00 ujutro — popodnevna sesija fizicki nije bila u prozoru. A treci dan dohvacamo
   tek od 01.08.

**Popravak:** nova `weather_at_match_time(city, date, local_hour, utc_offset)` bira unos
najblizi LOKALNOM satu meca. `get_forecast_series` dohvaca cijelu seriju **jednom po gradu**
(cache po procesu), pa biranje po satu ne kosta dodatne pozive — zapravo ih ima manje nego
prije. `cnt` 16 -> 40 (5 dana). Usporedjuje se LOKALNO vrijeme, ne UTC datum: vecernja
sesija u Montrealu (20:00 lok. = 00:00 UTC iduci dan) inace bi trazila unos pod pogresnim
datumom — isti cross-day problem vec dokumentiran kod screenshot gatea 27.07.
U `run_daily` je redoslijed promijenjen: lokalno vrijeme se sada racuna PRIJE prognoze.
Kad sat ili offset grada nisu poznati, NE pogadja se — vraca se stara gruba procjena.
Weather cache kljuc sada nosi i sat, pa dnevna i vecernja sesija istog turnira vise ne
dijele istu prognozu.

**Verificirano na stvarnim podacima:** mec u 14h dobiva 48% / 28,3 °C (prije 68% / 19,2 °C),
svaki sat pogadja s odstupanjem 0,0 h, a prekosutrasnje popodne je sada pokriveno.

### B. Provjera korisnikovih GitHub prijedloga — nalazi

- **`JeffSackmann/tennis_atp` i `tennis_wta` VISE NE POSTOJE.** Provjereno preko GitHub
  API-ja: Sackmann danas ima tocno jedan javni repo. Klonovi koje sam nasao zadnji put su
  azurirani 2018.
- **`Tennismylife/TML-Database`** postoji (1968-2026, 40+ stupaca), ali README tvrdi
  "updated daily" dok je zadnji commit 27.01.2026., a `2026.csv` ima 28 KB. Nije zivi izvor.
  Nama ionako ne treba — serve/return, forme i H2H vucemo iz API-ja u stvarnom vremenu.
- **Match Charting Project** je ziv (7.566 muskih meceva, 184 u 2026.), ali unakrsna
  provjera sa svih 150 nasih scouting igraca pokazuje da **pokriva bogate, ne siromasne**:
  medijan charted meceva je 196 za High profile, 58 za Med-High, 15 za Med, **9 za Med-Low i
  3 za Low**. Od 70 slabih profila samo 43% ima >=10 meceva. Konkretno za nase gubitke:
  Droguet 1 charted mec, Atmane 1, Kopriva 3, Landaluce 3. Momentum-varijabla je zato
  neizvediva kao dnevni signal. Licenca je CC BY-NC-SA (nekomercijalno) — korisnikova odluka.
- **Alati** (Qdrant, RAGFlow, Ollama, CrewAI, AutoGen, Langflow, Mem0, Instructor...):
  postoje i veliki su, ali nijedan ne rjesava nas problem — RAG nad jednim Wordom i jednim
  Excelom, orkestracija nad pipelineom koji vec radi deterministicki, lokalni modeli koji bi
  bili korak unatrag od Sonneta. Nista nije dodano. Lista "Top 10 AI GitHub Repo"
  (DeepSeek-Reasonix, QwenPaw, OmniRoute, Graphify...) ne odgovara nijednom poznatom repou.

### C. Dvije varijable u log (context_snapshot v6) — bez utjecaja na pickove

- **`p1_hand` / `p2_hand`** — ruka vec ide u prompt, ali se nikad nije spremala, pa se
  korisnikova hipoteza o ljevak-vs-desnak matchupu nije mogla ni provjeriti.
- **`common_opponents`** (korisnikov prijedlog): ako A i B nisu igrali medjusobno ali su oba
  igrala protiv istih protivnika, iz toga se izvodi relativna snaga. Racuna se iz vec
  dohvacenih zadnjih 10 meceva po igracu — **nula dodatnih API poziva**. **NE ide u prompt i
  ne utjece ni na jedan pick.** Isti standard koji je projekt vec dvaput naplatio: 31.07. bi
  auto-analiza uvela "dugi odmor = penal" i kostala nas cetiri dobitnika, a ranije danas je
  prividan signal o vlazi ispao konfundiran jednim kisnim tjednom. Prvo mjerimo, pa onda
  odlucujemo. Prva stvar koju cemo iz loga vidjeti je KOLIKO CESTO metrika uopce okine —
  dubina od 10 meceva znaci rijetko poklapanje, a prosirenje trazi vlastite API pozive i
  bit ce zasebna odluka s vlastitom cijenom.
- Dodano i `weather_forecast_local_time` + `weather_hours_off` — da se vidi za koji je sat
  prognoza vrijedila i koliko je udaljena od pocetka meca (bez toga se bug iz tocke A ne bi
  ni mogao primijetiti u podacima).

**NIJE implementirano:** MCP stilski profili (popravljaju uglavnom profile koji su vec dobri,
uz otvoreno pitanje licence), visina/dob kao izolirane varijable (korisnikova vlastita ograda
da ih model lako precijeni), i svi alati s lista.

**Ishod:** 15 novih asercija (ukupno 58) — ukljucujuci vecernju sesiju koja prelazi u iduci
UTC dan i odbijanje pogadjanja kad sat/offset nisu poznati. Verificirano i na stvarnom
OpenWeather odgovoru. Jedan bug uhvacen vlastitim testom: asercija je koristila
`w["hours_off"] or 99`, sto za tocno 0.0 daje 99 (0 je falsy).

---

## 2026-08-04 — Tvrdi clamp na cap + uvjeti se pocinju biljeziti

**Povod:** korisnik trazio analizu tri uzastopna promasena tiketa (01., 02. i 03.08.).

**Ispravak polazne pretpostavke:** vremena nastanka tiketa u bazi su UTC, a commitovi
lokalni. Preracunato, paket izmjena od 01.08. (prosireni prozor 16:07, klizni pragovi
16:37, underdog cap 16:49) usao je PRIJE sva tri tiketa (01.08. u 17:11, 02.08. u 15:22,
03.08. u 14:44 lokalno). Dakle nije "jedan stari + dva nova" — **sva tri su prvi zivi test
novog modela.** Bilanca: prije 01.08. 24 jedinstvena picka 16W-8L (66,7%), ROI -2,3%;
od 01.08. 7 jedinstvenih 3W-4L (42,9%), ROI -35,6%.

### A. Tiketi nisu bili neovisni (nalaz zabiljezen, popravak ODBIJEN)

13 legova na tri tiketa, ali samo **10 razlicitih meceva**. Tiketi 01.08. i 03.08. dijele
Kopriva-Galarneau (W) i **Berrettini-Navone (L)**; tiketi 02.08. i 03.08. dijele
Draper-Atmane. **Berrettinijev poraz je sam ubio dva tiketa.** Uz to 12 od 13 legova je
Montreal — tri "neovisna" dnevna tiketa bila su jedan ulog na jedan turnir.
Uzrok: prosireni prozor na prekosutra + `ticket_builder` nema nikakvu provjeru je li mec
vec bio na ranijem tiketu. Pojava je starija (Shelton 28.07., De Minaur i Musetti 29.07.,
Fritz 31.07. — 7 meceva na po dva tiketa), ali su svi ti duplikati dobili pa se nije vidjelo.
**Korisnik odbio dedupe:** ponekad namjerno zeli izostaviti dobar mec, pa ne zeli automatiku
koja mu to oduzima. Nalaz ostaje zapisan radi buducih revizija.

### B. Model navede cap pa ga ne primijeni — TVRDI CLAMP (implementirano)

Skeniranje svih 102 hard analize na eksplicitne formulacije odstupanja dalo je 4 slucaja,
**tri u zadnja tri dana**:

| mec | model napisao | emitirao | ishod |
|---|---|---|---|
| Jodar-Musetti 01.08. | *"rule 16's cap of 62% … is technically triggered"* | 64% | W (analysis-only) |
| Van Assche-Droguet 02.08. | *"cap at 60% is nearly triggered but … moderate rather than full penalty"* | 63% | **L** |
| Fucsovics-Moutet 03.08. | *"Cap held at 60% per rule 12 — below 63% threshold"* | 63% | **L** |
| Landaluce-Mejia 04.08. | *"start at 64% (overwhelming rating), +1pp for style"* | 65% | **L** |

Dva su cista prekrsaja: Fucsovics (risk_notes doslovno kaze da je ispod praga za tiket, broj
je tocno na pragu) i Landaluce (pravilo 2 propisuje cap 64%, model ga uzeo kao POLAZISTE i
dodao +1pp scoutinga). Ishod te cetvorke 1W-3L naspram 25W-16L (61%) za ostale hard analize
— **n=4, P≈0,15, statisticki nista**; izmjena se ne oslanja na uzorak nego na to da model
krsi vlastito pravilo, dokumentirano njegovim rijecima.

**Mehanizam — strukturirano polje, NE parsiranje proze.** Prvi pokusaj (regex nad prozom)
dao je 26 "krsenja" od kojih je vecina bila puko SPOMINJANJE capa koji ne veze
("rule 13 cap does not trigger"). Zato model sada popunjava novo JSON polje
**`applied_caps`** (`[{"rule": "16", "cap": 62}]`) s capovima koje sam smatra vezujucima, a
`_enforce_stated_caps()` spusta confidence na najnizi od njih. Proza se i dalje skenira, ali
**samo za biljezenje** (`cap_prose_mismatch`) — nikad ne spusta broj.

**Simulacija na stvarnim tiketima:** Van Assche 63->60 i Fucsovics 63->60 ispadaju, cime
tiket od 02.08. ostaje s 2 noge i **uopce se ne sastavlja** (taj je tiket izgubio 50 EUR).
Jedini dobitak koji bi clamp izbacio (Jodar 64->62) bio je na analysis-only listi — dakle
na stvarnim tiketima **nijedan dobitnik nije kostao**.

**Uz to:** pravilo 2 (hard) i sekcija SCOUTING PROFILES sada izrijekom kazu da je cap STROP,
ne polaziste — nista (scouting, stil, uvjeti, svjezina) ne smije podici capirani pick iznad
njega. Prompt takodjer navodi da "nearly/technically triggered" znaci TRIGGERED.

**Otkriveno tijekom testiranja i popravljeno:** u prvom zivom testu model je pretjerao u
drugom smjeru — deklarirao rule 12 kao vezuci cap dok je u key_factors argumentirao da NE
veze. Prompt je pooštren: ako igdje pises da pravilo "does not trigger/bind/apply", to
pravilo NE SMIJE biti u `applied_caps`, jer pretjerano deklariranje tiho brise pickove koji
nikad nisu bili capirani. Ponovni zivi test potvrdio ispravak.

### C. Vrijeme se pocinje biljeziti + smije samo HLADITI (implementirano)

Dvije nezavisne auto-analize gubitaka (Berrettini i Fucsovics) predlozile su isto pravilo:
vlaga >85% usporava teren i pomaze grinderu protiv servera. **Nije se moglo provjeriti** —
`context_snapshot` nije sadrzavao nijedno weather polje (provjereni kljucevi svih 37 hard
snapshota), iako vrijeme od pocetka ulazi u prompt.

Pokusaj mjerenja iz teksta analiza dao je prividan signal (vrijeme kao argument ZA pick =
10W-14L, 42%, naspram 58% prosjeka na hardu), ali **23 od 24 takva meca su iz jednog kisnog
tjedna u Montrealu** — potpuno konfundirano. Nije izmjereno "vrijeme steti" nego "los tjedan
u Montrealu bio je kisan". Isti tip zamke kao "dugi odmor = penal" od 31.07., koji bi nas
kostao cetiri dobitnika. **Zato NIJE uvedeno nikakvo humidity pravilo.**

Ono sto ne trazi statistiku: ista vlaga (89-92%) u istom tjednu i gradu koristena je kao
argument **ZA** jedan pick (Van Assche — "sporiji, tezi teren odgovara njegovoj igri s
osnovne crte", izgubio) i kao odbaceni **rizik** protiv drugog (Berrettini, izgubio).
Varijabla koja argumentira u oba smjera u istom tjednu je narativ, ne dokaz.

**Izmjena 1 — `context_snapshot` v5:** + `weather_temp_c`, `weather_humidity`,
`weather_wind_kmh`, `weather_condition`, `weather_forecast_for`, `venue_shielded`
(dvorana/zatvoreni krov — prognoza tada ne opisuje uvjete igre, pa se ti mecevi pri mjerenju
moraju izdvojiti), plus `cap_enforced` i `cap_prose_mismatch` iz tocke B.
`run_daily` sada uz formatirani string cuva i sirovi dict (`weather_raw_cache`).
**Zastavica "mec je poceo kasnije od zakazanog" NIJE uvedena:** API-jev `timeGame` je uvijek
null, a `date` nosi ZAKAZANI termin — stvarni pocetak nemamo ni nakon meca. Biljezi se za
koji je termin prognoza vrijedila. (Korisnik: odgode su rijetke, mecevi uglavnom krecu na
vrijeme.)

**Izmjena 2 — asimetrija (korisnik odabrao opciju B):** vrijeme, vlaga, vjetar i kisa smiju
SPUSTITI pouzdanost, ali je nikad ne smiju PODICI, dok se ne skupi mjerljivi dokaz.
Obrazlozenje: cijela povijest projekta pokazuje da PRECJENJUJEMO, pa je asimetrija koja moze
samo hladiti siguran smjer, a lako se ukine kad podaci stignu. **Izuzeti su izmjerena
"court pace this event" i lokalna sesija (dan/noc) iz pravila 14** — to su mjereni, ne
prognozirani podaci, i zadrzavaju dvosmjernu upotrebu.

### D. Provjereno i NAMJERNO nedirano

- **Tezine** — n=7 razrijesenih pickova.
- **Underdog prag 28pp** — razrijesen tocno JEDAN novi underdog pick (Fucsovics @2.00, L),
  Baez @2.00 jos visi. Uz to hard sezona kaze `value_bet=True` 5W-4L ROI **+3,3%** naspram
  `value_bet=False` 14W-8L ROI **-15,1%** — dokaz ide U KORIST underdoga, ne protiv.
- **R32 / Masters pravilo** — R32 je 2W-4L, ali to je istih tih 6 meceva, konfundirano i s
  erom i s jednim jedinim turnirom.
- **Klizni pragovi** — Van Assche sugerira rizik (klizni prag dao modelu prostor za
  "moderate rather than full penalty" umjesto tvrde skale), ali n=1.
- **Kalibracija po confidenceu** (hard, n=45): 63% -> 42,9% (n=14), 64% -> 73,7% (n=19),
  65% -> 45,5% (n=11). Nemonotono, dakle sum na malom n — NIJE osnova za izmjenu. Ono sto
  ostaje je obrazac ponasanja: u zadnja 4 dana **35% svih hard analiza zavrsi na tocno 63%**
  (prag za ulaz na tiket), naspram 20,6% kroz cijelu hard sezonu — model marginalne meceve
  gura NA prag umjesto ISPOD njega. Clamp iz tocke B djeluje upravo na to.

### E. Vjetar dobio pravilo (bio jedina nepokrivena stavka izvornog dokumenta)

**Povod:** korisnik podsjetio da je `Tennis_Surface_Analysis.docx` bitan dokument koji model
mora imati na umu. Dokument je procitan u cijelosti (40.788 znakova, 8 poglavlja) i poglavlja
4 (Hard) i 8 (Konsolidirane preporuke) usporedjena red po red s aktualnim promptom.

**Pokriveno i potvrdjeno:** sub-speed (pravilo 14, uz IZMJERENU brzinu terena), toplina i
nocne sesije (14), tiebreak/decider kao nositelji signala (31.07.), indoor kao zasebno stanje
(9), 1-2 tjedna prilagodbe nakon promjene podloge (5), jednodimenzionalni specijalisti (14),
Bo5 smanjuje varijancu upseta (8), stilski matchupovi (scouting sekcija).

**Nepokriveno — VJETAR.** Podatak je od pocetka isao u prompt (`Wind: X km/h`), ali nijedno
pravilo nije reklo modelu sto znaci; jedini spomen bio je negativan, u pravilu 9 ("indoors
there is no wind"). Posljedica vidljiva u analizi Norrie-UGC (03.08., vjetar 15,7 km/h):
model je napisao samo *"wind adds randomness"*, bez smjera.

Dokument tvrdi smjer: *"wind penalises high-margin spin games and rewards flatter, more
controlled hitting"*, a isti mehanizam potvrdjuje obrnuto u indoor poglavlju — bez vjetra
najvise dobivaju precizni agresori i flat udarci, dok heavy-topspin igraci "who rely on
wind/heat to make the ball jump lose some of that weapon".

**Novo pravilo WIND** (zajednicki template, univerzalno — fizika je cross-surface):
<15 km/h zanemari; 15-25 km/h znacajno, rizik ako je NAS PICK spin/high-margin igrac ili
cisti defanzivac bez prvog udarca; >25 km/h jako, penal jaci + tolerancija na gresku
nadjacava cistu brzinu za OBA igraca. Stil se cita iz SCOUTING PROFILES; ako stil nije
utvrdjen, pravilo se NE primjenjuje umjesto da se nagadja. **Vrijedi ista asimetrija kao za
ostale uvjete: vjetar smije samo HLADITI** — ako je nas pick flat igrac, vjetar naprosto
nije rizik za njega, sto NIJE razlog da mu se broj digne. Pragovi su iz izvornog dokumenta i
opceg teniskog znanja, **ne iz naseg korpusa** — vjetar se od danas biljezi, pa je pravilo
kandidat za reviziju kad se bude moglo testirati.

### F. Scouting: budzet ±3pp sada skalira s pouzdanoscu profila

**Povod:** korisnik podsjetio da se `ATP_Player_Scouting top150` prati u Supabaseu i da ga
model treba koristiti. Provjera stanja: tablica ima **150 redaka** (High 10, Med-High 25,
Med 45, Med-Low 50, Low 16, Insufficient 4), gate izbacuje 20, ostaje 130 upotrebljivih.
Pokrivenost u stvarnim mecevima je dobra — od 69 hard analiza sa snapshotom **54 imaju profil
za OBA igraca**, samo 3 nemaju nijedan. Pipeline dakle radi.

**Otvoreni nalaz od 31.07. koji nikad nije strukturno rijesen:** tri profila koja su se
pokazala pogresnima — Van Assche, Halys, Majchrzak — bila su **sva tri Med-Low**, i sva tri
su sudjelovala u gubicima. Tada su ispravljena ta tri konkretna profila, ali Med-Low je i
dalje prolazio gate s punim ±3pp utjecaja kao i High profil. Med-Low je trecina tablice
(50 od 150), dakle nije rubni slucaj.

**Izmjena:** budzet sada skalira s vlastitom pouzdanoscu profila — High/Med-High puni ±3pp,
Med najvise ±2pp, **Med-Low asimetricno: smije podici SUMNJU u pick, ali se nikad ne smije
citirati kao potpora za njega**. Ako pick pociva samo na Med-Low profilu, taj dokaz ne
postoji. Gate je nediran (Low/Insufficient i dalje ispadaju uz eksplicitnu "no reliable
scouting" poruku) — ovo je gradacija unutar onoga sto prolazi, ne nova zabrana.

**Zivi test oba pravila** (vjetar 28 km/h, nas pick heavy-topspin s Med-Low profilom,
protivnik flat s High profilom): model je prepoznao prag >25 km/h, kaznio spin igraca,
razlikovao High od Med-Low profila i **sam** spustio confidence na 62% — ispod praga 63,
pick ispada. Clamp nije morao intervenirati jer je model dobrovoljno postovao vlastiti cap,
sto je i bio cilj izmjene B.

**Napomena:** korpus ima 45 razrijesenih hard analiza, dakle revalidacijski okidac (prag 30)
je prekoracen — vrijedi provjeriti javlja li se u dnevnom logu.

**Ishod:** novi test suite `test_cap_and_weather.py` (26 asercija: clamp spusta / ne dira
netaknuto / graceful bez polja / besmislene vrijednosti / poredak prema fair_odds / prozna
mreza samo upozorava / prompt markeri) — sve proslo. Prompt se formatira ispravno za sve tri
podloge (nova viticasta zagrada u JSON shemi provjerena). **Dva stvarna (ne-mock) API
poziva:** Landaluce-Mejia — model deklarirao capove, clamp okinuo 64->60, pick ispao;
kontrolni poziv potvrdio da clamp ne okida kad cap ne veze.

---

## 2026-08-02 — Klizni pragovi + underdogovi vraceni u igru

**Povod:** korisnik trazio analizu hard rezultata nakon poraza De Minaura i Sheltona, i
pitao zasto na tiketu nikad nema kvote preko 2.50.

**Stanje hard sezone (n=24):** 16W-8L (66.7%), flat ROI -2.3%. Trziste je iz kvota
ocekivalo 16.7 pobjeda (69.5%), model tvrdio 15.6 (65%), dobili smo 16 — **kalibracija je
odlicna**, ali prosjecna kvota 1.474 trazi 67.8% za nulu. Savrseno kalibriran model na tim
cijenama i dalje gubi: problem nije predikcija nego cijena.

### A. Pragovi su se "za dlaku" iskljucivali (3 od 3 zadnja SF poraza)

De Minaur (return 42.5% naspram praga 42%), Shelton (Tabilov return 41.8% naspram 40%),
Norrie ("jedva presao"). Model je tvrde brojke koristio kao prekidac: 42.5 > 42 znaci rizik
nestao, confidence natrag na 65%. Greska u pravilima napisanima 31.07.

**Popravak:** pragovi u pravilima 2b, 13 i 16 sada su KLIZNI. Presao za <2pp = slaba potvrda
(max +1pp confidence); 3-5pp = djelomicna; >5pp = puna. Pravilo 13 nosi izmjerenu skalu
(42.5% -> cap ostaje 60%, 43-45% -> 63%, >45% -> cap se dize) i primjer De Minaura.

### B. Zasto nikad nema kvote >2.50 — strukturni nalaz

Sezonska raspodjela: najveci segment gubi, najskuplji je najprofitabilniji.

| Kvota | Pickova | Rezultat | ROI |
|---|---|---|---|
| 1.30-1.60 | 101 | 59W-34L | **-10.2%** |
| 2.30-2.60 | 9 | 6W-2L | **+79.4%** |
| 2.60+ | 9 | 3W-5L | +7.4% |

Uzrok: `_score_combo` je bodovao edge samo do 20pp. Pick @2.50 uz conf 63 ima 23pp -> NULA
bonusa -> optimizator ga nikad ne bira. Nije bio zabranjen, samo nikad isplativ. Uz to u
uputama nije postojalo nijedno pravilo koje agentu kaze da SMIJE podrzati underdoga.

**Popravak 1 — granica ovisi o cijeni:** favoriti (<2.00) zadrzavaju 20pp, underdogovi
(>=2.00) dobivaju **28pp**. Ista brojka znaci razlicite tvrdnje: favorit @1.50 uz conf 70
tvrdi "ovo je siguran mec" (tu smo grijesili), underdog @2.50 uz conf 63 tvrdi samo "ovo je
blize izjednacenom nego cijena". Ucinak: 32 underdog picka ulaze u bodovanje (16W-15L,
ROI +15.5%), 4 ostaju izvan (ukljucujuci dokumentirani promasaj Collignon @2.82 uz conf 71).

**KOREKCIJA istog dana (korisnikova primjedba):** prag je prvo bio 30 kako bi prosao
Collignon @2.79 (28.2pp, dobio). Provjera je pokazala da razlika 28 vs 30 dira **tocno dva
picka u cijeloj sezoni** — taj Collignon (W) i Vacherot @2.78 (void). Pomicanje praga zbog
jednog povoljnog slucaja je upravo obrazac koji ovim paketom ispravljamo kod modela; uz to
granica postoji jer smo povijesno PRECJENJIVALI value, pa je popustanje rizican smjer koji
trazi pozitivan dokaz. Vraceno na **28**. Ilustrativno: isti igrac je i promasaj i pogodak —
Collignon @2.82 uz conf 71 izgubio, @2.79 uz conf 64 dobio, dva dana razmaka. Problem nije
bio igrac nego razina uvjerenja. (Ispravak: pick @2.79 je Collignon, ne Cerundolo.)

**OGRADA za prvu hard reviziju:** od 36 pickova >=2.00 u sezoni, **23 su na travi, 12 na
zemlji i samo 1 na hardu** (Tabilo @2.00). Nalaz o profitabilnosti visokih kvota je
grass/clay dokaz — za hard nemamo gotovo nista, a hard sada igramo.

**Popravak 2 — izricito pravilo** ("WHEN A BIG UNDERDOG IS A LEGITIMATE PICK"): velik edge
je dopusten samo uz DVIJE nezavisne mjerene kategorije (servis/return >=3pp, ucinak na
podlozi, forma prilagodjena kvaliteti), uz obavezno imenovanje obiju u 6. tocki key_factors.
Ako je jedini argument rejting ili predosjecaj — ostaje nelegitimno.

### C. Late-round nalaz potvrden na drugoj podlozi, uz korekciju

Rano (R16/R32) 7/9 = 78% naspram trzisnih 73% (nadmasujemo); zavrsnice 9/15 = 60% naspram
67% (zaostajemo) — isto kao 26.07. na clay+grass. ALI na hardu su i underdogovi u
zavrsnicama negativni (2W-2L, -7.5%), dok su na clayu bili +11.2%. Prompt nosi tu korekciju.
Nista deterministicko nije uvedeno: 63% volumena nam je u zavrsnicama.

### D. Provjereno i ODBACENO

- "Veliki server uvijek pobjeduje" — Shelton je imao 90% holda i izgubio od Tabila (78.9%).
- Broj stavki u analizi — nekad je 3 stavke znacilo 50% a 5 stavki 88%, ali otkad je format
  od 31.07. propisan na 6 polja svi pickovi imaju 6, pa signal vise ne razlikuje nista.
- Los Cabos 4W-4L vs Washington 12W-4L — n=8 na slabijem polju, ne gradi se nista na tome.

**Tezine NISU dirane** (n=24, kalibracija vec dobra).

---

## 2026-08-01 — Prosireni prozor na prekosutra + dj-transliteracija + limiti 6

**Povod:** korisnik uploadao 16 parova pod "Sutra", a na listic dosao samo jedan Montreal par.

**Dijagnoza — gate NIJE bio kriv.** 13 od 16 parova zapravo se igra **prekosutra**
(Montreal glavni zdrijeb po API-jevim podacima pocinje 03.08.; ono sto se 01.08. ondje
igralo su kvalifikacije). Pipeline je dohvacao samo danas+sutra pa ti mecevi nikad nisu ni
dohvaceni. Gate je usput dokazao vrijednost unije danas+sutra od 27.07.: korisnikova 3 para
uploadana pod "Danas" API vodi pod SUTRA, i unija ih je uhvatila.
Analysis-only je bio matematicki neizbjezan: 4 meca kroz gate, Fery veto maknuo Fritza
(Nakashima nas srusio 2x u Washingtonu), ostala 3 < min 4, kombinirana kvota 2.98 << 6.0.

**Izmjena 1 — prosireni prozor:** dohvaca se i prekosutra, ali SAMO uz "sutra" screenshot, i
za taj je dan gate UVIJEK aktivan (`always_gated_dates`). Bez tog uvjeta prekosutra bi prosao
nefiltriran (nema vlastiti screenshot slot) i povukao cijeli turnir u analizu. Screenshot se
sada cita PRIJE dohvata meceva jer o njemu ovisi hoce li se treci dan dohvatiti.
Verificirano na stvarnim podacima: kroz gate prolazi **19 umjesto 4** meca — tocno svih 19
parova sa screenshota, nista izvan njega (39 -> 19).

**Izmjena 2 — dj-transliteracija:** `_strip_diacritics` je pretvarao d u "d", a API pise
"dj" (Medjedovic, Djere) — par "Cerundolo vs Medjedovic" se nije poklapao. Dodano
preslikavanje slova koja NFKD ne rastavlja (d->dj, o, ss, ae, oe, l, th). Ista transliteracija
u `_norm_player_key` da isti igrac ne dobije dva kljuca. Provjereno: 0 postojecih redaka s d.

**Izmjena 3 — dnevni limiti po turniru 5 -> 6** (Masters/500/250); GS ostaje 7/6,
Challenger/Qualifying 0; analysis-only ostaje 12.

---

## 2026-07-31 (kasno) — Scouting prosiren na ATP top 150 + ispravci profila

**Audit — tri profila su bila kriva, i sva tri su sudjelovala u gubicima:**

- **Van Assche** (bio Med-Low, "needs a weapon; tough vs big power + servers"): opovrgnuto —
  osvojio Estoril 2026 pobijedivsi Rubleva 3-6 6-3 6-4, Carreno-Bustu, Gastona i Blockxa;
  ranking #78 -> #48.
- **Halys** (bio Med-Low, best "Hard, Grass, Indoor", tough "elite returners/movers"):
  opovrgnuto na brzoj zemlji u Kitzbuhelu — srusio TRI nasa picka u tjedan dana (Navone
  7-5 6-3, a Navone je elitni clay mover; Hanfmann; Bublik) i uzeo naslov. #83 -> #52.
- **Majchrzak**: pobijedio nas pick Tommy Paul 7-5 7-6(4) uz obostrani hold ~81%.

Sistemski nalaz: sva tri su bila **"Med-Low / partial data"**, sto PROLAZI prompt gate —
najslabiji profili su ulazili kao dokaz.

**Prosirenje na top 150:** dodano 50 profila (100 -> 150). Nista se ne izmislja: profili su
IZVEDENI iz mjerenih podataka (3-godisnji surface W-L, hold%, return points won, ace rate,
surface ELO). Kvalitativni opis dodan samo za 8 igraca s provjerenim izvorom (ATP Tour bio,
Wikipedia, LTA); gdje podatka nema, pise "cannot be determined". Stil se klasificira iz
brojki s pragovima kalibriranim na stvarni raspon (hold 67-93%, return 32-47%).
Sukobi se biljeze: Arthur Gea se u ATP bio-u opisuje kao "big serve", a mjereni hold mu je
75.7% uz 44.7% return — profil nosi CONFLICT zapis i uputu da se vjeruje izmjerenom.
Skripte: `scripts/build_scouting_150.py`, `scripts/export_scouting_excel.py`
(Excel `ATP_Player_Scouting top150.xlsx`, krug radi u oba smjera).

---

## 2026-07-31 — Kalibracija spašena od tihe korupcije + 4 nova izvora signala

**Povod:** korisnik tražio analizu Tommy Paul gubitka i obrazaca prvog hard tjedna. Usput
otkriven ozbiljan bug koji je mijenjao tumačenje svega ostalog.

### A. KRITIČNO: `analyzed_matches` je bio 70% korumpiran na hardu

`actual_winner` u 56 redaka nije bio nijedan od dvojice igrača u meču — npr.
"Kamil Majchrzak vs Tommy Paul" → `actual_winner = 'Quentin Halys'` (igrač s clay turnira).

**Uzrok:** API-jev fixture `id` NIJE stabilan — s vremenom se prenamjenjuje drugom meču.
Dokaz: `id=1216` je u našoj bazi Majchrzak-Paul (28.07.), a u API-ju danas pripada meču
Echargui-Lee (25.07.). Kako se koristio kao `on_conflict` ključ pri upsertu, reciklirani ID
je prepisao imena i predikciju NOVIM mečem, dok su `actual_winner`/`prediction_correct`
ostali od STAROG. Posljedica: hard kalibracija 70,5% neispravna (55/78), hard okidač
revalidacije brojao smeće, auto-feedback učio iz izmišljenih ishoda.

**Popravak:**
- `stable_match_key()` — ključ je sada `datum|igrac_a|igrac_b` (normalizirano, sortirano),
  ovisi samo o stvarnom identitetu meča i ne može se reciklirati. Otporan na zamjenu p1/p2.
- Sanity guard u `update_analyzed_match_result()`: pobjednik MORA biti jedan od dvojice
  igrača, inače se zapis odbija uz upozorenje umjesto da tiho iskrivi korpus.
- Migracija `scripts/migrate_analyzed_key.py`: obrisano 56 korumpiranih + 67 duplikata,
  286 ključeva prepisano. Korpus poslije: **140 razriješenih (clay 91 / grass 36 / hard 13)**.
- NAPOMENA: `ticket_matches` NIJE bio pogođen (koristi insert, ne upsert) — W/L i ROI su
  cijelo vrijeme bili točni.

### B. Obrasci prvog hard tjedna (12W-5L, flat ROI +1,9%)

U **svih 5 gubitaka** rejting je bio glavni pokretač, a upozorenje uredno zapisano u
`risk_notes` pa pregaženo. 4 od 5 bila su na 63-65% — ISPOD starog praga od 66% na kojem se
double-confirmation uopće aktivirao. To je bila prava rupa.

Provjerena i **opovrgnuta** lekcija iz auto-analize Lehecka gubitka ("dugi odmor = penal"):
igrači s 23-28 dana odmora išli su **4W-1L**. Da smo je ugradili, izbacili bismo 4 dobitnika.
Zaključak: auto-analize gubitaka pišu se na n=1 i sposobne su predložiti štetne izmjene.

**Zona kvota 1.43-1.90 (max 1/tiket) validirana:** u zoni 3W-3L (50%, ROI −13,3%), izvan
zone 9W-2L (82%, ROI +10,2%). Zadržana bez izmjene.

### C. Nova/izmijenjena pravila (prompt-razina, težine NETAKNUTE)

- **Pravilo 2 prepisano**: double-confirmation sada vrijedi od **63%** (ne 66%), i tri
  kategorije su strogo odvojene — ELO + ranking + surface record su **JEDNA** kategorija
  (model ih je razbijao na više "potvrda"); serve/return se broji tek od **≥3pp hold** ili
  **≥2pp return** (Mensikov 1,2pp return "edge" bio je šum). Jedna kategorija sama prolazi
  samo ako je golema (ELO ≥250 ili record gap ≥15pp), i tada max 64%.
- **Pravilo 15 RATING-vs-REALITY**: −4pp ako naš pick ima hard win-rate ≤50% (Brooksby) ili
  protivnik ≥70% (Gea 76,7%). Odbitak, ne veto.
- **Pravilo 16 CONVERGED SERVE**: kad su hold% unutar 3pp, servis se NEUTRALIZIRA kao
  potvrda i odluku preuzimaju vlastiti tiebreak/decider recordi; cap 62% ako pick ne vodi u
  oba. Namjerno NE capira sam po sebi — Norrie (konvergiran servis, ELO 284 + forma) dobio
  je 6-1 6-0 i mora proći. Dizajn testiran: hvata 4 od 5 gubitaka, gubi 1 od 12 dobitaka.

### D. key_factors standardiziran (5 fiksnih + 1 slobodna)

Uzrok varijacije: JSON predložak je doslovno pisao `["factor1","factor2","factor3"]`.
Izmjereno: analize s 3 stavke išle su **3W-3L (50%)**, s 5+ **9W-2L (82%)**.
Sada su polja 1-5 obavezna (Rating / Serve-return / Form vs opponent quality / Style matchup
/ Fatigue & conditions) uz obavezno "no data" kad podatka nema, a **6. je slobodna** —
korisnikov zahtjev da se ne izgubi agentov vlastiti uvid; izričito potiče i argumente
PROTIV vlastitog picka.

### E. Četiri nova signala u promptu

- **Vlastiti tiebreak record** (`_tiebreak_record`) — parsiran iz score stringova koje već
  imamo, 0 API poziva. Dosad je postojao samo međusobni H2H tiebreak, koji je na n=1 šum.
- **Deciding-set record** — postojao od 18.07. samo u snapshotu, sada ulazi u prompt.
- **Brzina terena** (`get_court_pace`) — udio setova u tiebreaku po turniru, iz rezultata
  sezone koje ionako dohvaćamo. Izmjereno: Washington 15,8% (fast), Los Cabos 10,9%
  (medium), Estoril clay 7,5% (slow). Zamjenjuje dosadašnju procjenu "po reputaciji" u
  pravilu 14.
- **Lokalno vrijeme + sesija** (`local_match_time`) — `timeGame` iz API-ja je UVIJEK null,
  pa je `context_snapshot.match_time` bio prazan otkad postoji (18.07.). Pravi izvor je puni
  UTC timestamp u polju `date`; pretvara se u lokalni sat turnira preko mape gradova.
  Korisnikov nalaz: meč koji nama počinje u 4 ujutro u Washingtonu je popodnevna sesija po
  suncu — vrijeme i sesija moraju se vezati na lokalni sat, ne naš.

`max_tokens` za analizu 1500 → 2600: u dry-runu je 1 od 5 analiza pala na odrezan JSON zbog
duljeg key_factors formata (odrezan odgovor = tiho preskočen meč).
`context_snapshot` v4: + local_time, session, court_pace_label, p1/p2_tiebreak_record.

---

## 2026-07-27 — Screenshot-isključivost: mečevi izvan screenshota se izbacuju prije analize

**Povod:** korisnik pitao je li moguće da se meč izvan njegovih uploadanih screenshot
kvota ipak provuče na analysis-only ili tiket. Provjera je pokazala da JEST — i to
uživo, ne teoretski: The Odds API je taj dan vratio 28 stvarnih tržišta za Washington/
Los Cabos, uključujući mečeve koje korisnik NIJE screenshotao, s cijenama koje se za
zajedničke mečeve razlikuju od SuperSporta (npr. Arnaldi-Musetti 2.65/1.47 na screenshotu
naspram 2.42/1.69 na Odds API-ju). Dosadašnja "zaštita" počivala je isključivo na sretnoj
okolnosti da The Odds API dotad nije imao tržišta za manje clay ATP 250 turnire —
pretpostavka koja se raspala na prvom većem hard turniru. Dodatno, `build_analysis_only_
ticket` nije ni provjeravao postoji li stvarna kvota (`_pick_odds` tiho vraća 1.50 kad
kvote nema), pa je isti mehanizam prije proizveo šest lažnih Washington kvalifikacijskih
pickova (vidi zapis od 26.07.).

**Pravilo:** ako je korisnik za dan D (danas ILI sutra) uploadao barem jedan screenshot
par, SAMO ti parovi tog dana smiju dalje u obradu — svi ostali mečevi tog dana se
izbacuju PRIJE ELO/kvota/vremena/Claude analize (ne samo prije selekcije na tiket), bez
obzira što o njima kaže The Odds API ili API-jeva round-oznaka. Dan bez ikakvog uploada
ostaje nepromijenjen (Odds API fallback kao dosad).

**Cross-day nijansa (korisnikov uvid):** Washington/Los Cabos večernji mečevi znaju po
satu ispasti u idući Zagreb kalendarski dan (SAD zapadna obala ~9-10h iza), pa API zna
meč koji je korisnik screenshotao pod "danas" označiti sutrašnjim datumom. Zato provjera
imena ide preko SPOJENOG (danas+sutra) skupa, dok je UKLJUČENOST pravila i dalje po
danu — isti par ne igra dvaput unutar ta dva dana (eliminacijski turnir), pa spajanje ne
nosi rizik krivog poklapanja.

**Implementacija:** `agent/run_daily.py` — nova `_gate_by_screenshot()`, pozvana odmah
nakon učitavanja screenshot kvota, prije `_infer_rounds`. `screenshot_today`/
`screenshot_tomorrow` sada odvojeni (prije su se odmah spajali). Testirano na stvarnim
podacima 27.-28.07.: filter je uživo izbacio 5 Los Cabos mečeva koje korisnik nije
screenshotao te sezone, bez utjecaja na 27 mečeva koje jest.

---

## 2026-07-26 (kasna večer) — Hard zona ublažena po ponovnom mjerenju + model_stamp u snapshotu

**Povod:** korisnik pitao stojim li i dalje iza potpune hard zabrane 1.43-1.60 nakon
Kitzbühela/Estorila. Ponovno mjerenje po erama (dedupe, flat ROI):

| Zona | Prije 11.07. (stari model) | Clay 11.-26.07. (novi model) |
|---|---|---|
| 1.43-1.60 | 17W-15L, −19.2% | 10W-4L, **+7.8%** |
| 1.61-1.90 | 22W-24L, −16.5% | 9W-4L, **+21.9%** |

**Zaključak:** mrtva zona je bila problem STAROG modela (bez conf floora, hot-handa,
Fery veta), ne kvote same. Zabrana iz 18.07. počivala je na korpusu stare ere.

**Izmjena (korisnik odobrio):** hard "1.43-1.60 zabranjeno + 1.61-1.90 max 1" →
**jedna oprezna zona 1.43-1.90, max 1 hard pick po tiketu** (isti oblik kao clay pravilo
koje je isporučilo 72% WR). `_hard_bands_ok` uklonjen iz `_selection_ok`;
`_hard_caution_zone_count` u `_find_best_combination`. Prompt pravilo 3 ažurirano (nosi
obje ere brojki + opis novog backstopa). Grass zabrana NAMJERNO ostaje (n=33, −20.3%,
nije ponovno mjerena — grass sezona gotova; revalidirati prije iduće trave). Nuspojava:
hard tiket je sada izvediv s JEDNIM underdogom >1.90 (test: 1.35/1.40/1.55/2.10 → 6.15),
pa rizik svakodnevnog analysis-only praktički nestaje. Revalidacija na ~30 hard pickova
(okidač aktivan). Oprez: novi uzorak zone je malen (n=14/13) i s claya.

**model_stamp (context_snapshot v3):** svaka analiza sada nosi `{weights_version,
rules_hash}` — verzija aktivnih težina + md5 hash surface pravila i templatea (mijenja se
automatski sa svakom izmjenom prompta, bez ručnog održavanja). Svrha: egzaktno rezanje
kalibracijskog korpusa po erama modela umjesto rekonstrukcije iz datuma revizija.

---

## 2026-07-26 (večer) — Kalibracija proradila (bug 0/421), hard pravila 13-14, ocjena v15

**Povod:** korisnik pitao zašto je "Confidence calibration" na Model Statistike prazan, tražio
ocjenu auto-generiranih clay težina v15 i pripremu hard modela za Washington/Los Cabos (27.07.).

**Nalaz 1 — kalibracija prazna zbog stvarnog buga, ne zbog praga:** korak 2b večernjeg
updatea (18.07.) čitao je pobjednika iz `/atp/fixtures`, ali taj endpoint NIKAD ne vraća
pobjednika — čisti je raspored (provjereno sirovim odgovorom: ključevi samo
id/date/roundId/playerXId/live). Rezultat: 0/421 analiza razriješeno, kalibracijska tablica
prazna, hard-revalidacijski okidač (30 hard pickova) slijep, walkover-fallback mrtav.
Dodatni nalaz: fixtures za PROŠLE dane IZBACUJU odigrane mečeve — isti mehanizam zbog kojeg
je Kitzbühel "nestao" iz feeda 25.07.

**Popravak:** novi izvor pobjednika `/atp/tournament/results/{seasonId}` tekuće sezone
(`get_current_season_results` u data_fetcheru; 2 API poziva po turniru). Zajednički helper
`_build_season_winner_lookup` (feedback_analyzer) pronalazi tournament_id kaskadno:
fixtures par-mapa → past-matches igrača s ranking liste (traži se TOČNO meč para: datum ±2
dana I prezime protivnika — širi prozor je hvatao susjedni turnir istog igrača). Lookup puni
postojeći `fixture_winner`, pa su korak 2b i walkover-fallback proradili bez daljnjih izmjena.
Backfill (`scripts/backfill_analyzed_results.py`): razriješeno 261/421 analiza (ostatak su
kvalifikacije kojih nema u results endpointu, challengeri izvan top-500 i Citi Open koji još
nije počeo). Kalibracijski korpus sada: n=223 — bin 63-65% pogađa 64.9% (dobro kalibrirano
nakon revizija), 66-69% → 73.1%, 70%+ → 90%.

**Nalaz 2 — ocjena clay v15 (auto-feedback, 7 analiza):** zadržan bez izmjena. Opravdano:
elo −2 (gubici s gapom 60-77 bodova tretiranim kao presudnim), fatigue +2 (umor zapisan pa
pregažen u 4 gubitka), serve_return +1 (Halys 3×). Dvije dokumentirane zamjerke: trajectory
−1 počiva na tome da hot-hand sada čuva deterministički Fery-veto (a taj je 25.07. zakazao
zbog feed-rupe — sada zakrpano A1 + ovim popravkom); h2h +1 dijelom citira halucinirani
"Van Assche 2023 Estoril win" iz pred-A2 analiza. Kontekst: clay 11.-26.07. = 39W-15L
(72.2%), flat ROI +14.6%; pravi tiketi 1W-8L (akumulator-matematika, korisnikova odluka).

**Nalaz 3 — hard pravila 13 i 14 (prompt, v14 težine NETAKNUTE do prvih hard podataka):**

- Pravilo 13 SERVE-DOMINANT OPPONENT CAP: protivnik hold ≥82% + naš return <40% → cap 60%
  (destilat tri Halys poraza: Navone @1.45, Hanfmann @1.55, Bublik @1.50).
- Pravilo 14 HARD SUB-SPEED: iz Tennis_Surface_Analysis.docx ("treating all hard courts
  identically is the most common modelling error") — brzi/spori hard mijenja vrijednost
  servisa vs returna; arhetip upozorenje za jednodimenzionalne igrače uz SCOUTING PROFILE.

Provjera usklađenosti s Word dokumentom: pravila 4, 5, 6, 7, 9 + v14 balans (elo 22 =
serve_return 22) već pokrivaju "balanced blend / ranking najpouzdaniji na hardu / vrućina /
indoor amplifikacija"; jedina stvarna rupa bila je sub-speed → pokrivena pravilom 14.

**Retro-provjera scoutinga (uveden 25.07. poslijepodne, prvi live run 27.07.):** profili bi
izravno označili 3 najskuplja gubitka — Navone (tough: "Big servers") vs Halysa, Rublev
(tough: "Counter-punchers who absorb pace") vs Van Asschea, Bublik ("Very streaky") vs
Halysa; s capom −3pp sva tri padaju ispod floora 63% i ispadaju iz selekcije.

---

## 2026-07-26 — Revizija po 8 korisnikovih nalaza: A (5 popravaka), B, C, D (struktura tiketa)

**Povod:** korisnik prijavio 8 točaka (neriješen rezultat, dvije sumnjive tvrdnje u analizama,
dvije hipoteze za provjeru, prijedlog nove varijable, promjena strukture tiketa). Sve je
provjereno kroz stvarne podatke prije bilo kakve izmjene; dvije hipoteze su potvrđene, jedna
opovrgnuta, tri tvrdnje o greškama potvrđene.

**Nalazi iz provjere (dokumentirano jer objašnjava SVE izmjene ispod):**

- **Bublik-Halys 25.07. nije razriješen** jer je Generali Open Kitzbühel NESTAO iz fixtures
  feeda (0 mečeva 22.-26.07.). Evening update gradi player ID-eve isključivo iz feeda → bez
  ID-eva odustaje prije nego išta pokuša. Estoril mečevi istog dana prošli normalno.
  Stvarni rezultat (past-matches): Halys 6-4 7-6(6). Upisan + generirana analiza gubitka.
- **Halys nas je srušio 3× u istom turniru** (23./24./25.07.) a Fery-veto nije upalio: ta
  tri dana bila su `analysis_only`, a `build_analysis_only_ticket` NIJE primjenjivao nijedan
  deterministički filter — ni veto, ni mrtve zone, ni conf floor. Vrijedilo je i za
  hipotetski "kad bih morao riskirati" tiket koji korisnik čita.
- **Rublev-Darderi (točka 2): potvrđeno.** Prompt je doslovno sadržavao `Luciano Darderi:
  2025 FW` (protivnik osvojio isti turnir novije) i `2024 R16: Tirante def. Rublev` (naš pick
  ispao rano zadnji put). Model je citirao samo "Rublev won this title in 2023". Nije
  halucinacija nego jednostrano citiranje dokaza koje je imao pred sobom.
- **Van Assche "2023 Estoril win" (točka 5): potvrđeno i gore.** Naša draw baza kaže
  `2023 R16: Davidovich Fokina def. Luca Van Assche` — dakle taj meč je IZGUBIO. Analiza je
  napisala da ga je dobio, a feedback model to eskalirao u "his 2023 Estoril win" (2023.
  Estoril je osvojio Ruud). Feedback prompt dotad nije imao NI draw podatke NI anti-
  halucinacijsko pravilo. Usput: Estoril draw ima samo 2022-2024, pa je
  `has_tournament_history` vraćao False svaki dan → puni re-fetch ~45 zapisa SVAKI run.
- **Shevchenko/Struff (točka 3): potvrđeno.** Tiket 19.07: `risk_notes` = "Shevchenko fresher
  (2 vs 13 rest days)" dok `key_factors` iste analize kaže "Struff's 13 days rest — fatigue
  factor favours Struff". Igrač s 2 dana odmora označen "svježijim". Ponovilo se i 20.07.
- **Točka 4 (oba igrača >120 ATP): hipoteza NIJE potvrđena.** oba ≤120: n=156, WR 63.5%,
  ROI -4.0% | jedan >120: n=44, 61.4%, -2.9% | **oba >120: n=19, 63.2%, +8.5%**. Kontrola
  prag 100 → +2.1%, prag 150 → -0.3%. Isti WR uz više kvote. Ništa nije mijenjano (korisnik
  potvrdio: "E - okej, necemo dirati nista").
- **Točka 6 (završnice): hipoteza POTVRĐENA.** QF/SF/F kvota ≤1.60: n=59, WR 66.1%,
  **ROI -10.2%** | kvota >1.60: n=21, WR 57.1%, **ROI +11.2%**. Finale je najgora runda
  (n=9, 55.6%, -27.4%). Razlika 21pp ROI-a.
- **Točka 7:** pronađen neiskorišten endpoint `/atp/player/titles/{id}` — karijerna finala
  po razini (osvojena + izgubljena), tj. koliko je finala igrao i koliko ih je zatvorio.

**Što je promijenjeno:**

**A1 — razrješavanje rezultata više ne ovisi o fixtures feedu.** `ticket_matches` dobiva
`player1_id`/`player2_id` (upisuju se pri kreiranju tiketa), a evening update koristi kaskadu
tiket → fixtures → **ATP ranking lista** (nova `df.find_player_id`, cache po procesu).
`save_ticket_matches` ima defenzivni fallback: ako stupci ne postoje, upisuje bez njih pa
spremanje tiketa nikad ne padne. Potreban ALTER TABLE (vidi schema.sql).

**A2 — feedback prompt ojačan:** dobiva draw povijest turnira + isto anti-halucinacijsko
pravilo kao analizni prompt, plus eksplicitnu uputu da `risk_notes` iz predikcije NISU
provjerena činjenica i da se proturječje s draw podacima mora prijaviti kao nalaz.

**A3 — pravilo uravnoteženog citiranja:** ako model citira turnirsku povijest u prilog svog
picka, mora prvo provjeriti istu povijest za protivnika i za vlastite nedavne neuspjehe tamo.
Uz konkretan dokumentirani primjer (Rublev/Darderi). Dodano i pravilo da se rezultat mora
čitati u ispravnom smjeru (primjer Van Assche R16).

**A4 — pravilo interne konzistentnosti:** `risk_notes` ne smiju proturječiti `key_factors`;
model mora prije vraćanja ponovno pročitati oba polja i provjeriti da ime, broj i smjer
("fresher", "better") pokazuju isto. Uz dokumentirani Shevchenko primjer.

**A5 — draw re-fetch throttle:** `has_tournament_history` više ne traži strogo prošlu sezonu
(neki turniri je u API-ju nemaju), nego bilo koju unutar 3 godine; ako su podaci stariji od
current_year-1, dopušta re-fetch **jednom tjedno** umjesto svaki dan.
`save_tournament_history` sada osvježava `fetched_at` pri svakom upsertu — bez toga throttle
nikad ne bi resetirao brojač (uhvaćeno testom).

**B — hipotetski tiket prolazi kroz `_selection_ok`.** Široka lista analiziranih mečeva
namjerno OSTAJE bez filtera (informativna), ali "kad bih morao riskirati" prijedlog sada
poštuje ista pravila kao pravi tiket. Ovo bi spriječilo trostruki Halys fade.

**C1 — karijerna finala u prompt** (`df.get_player_titles`, cache): ATP/Masters i Challenger
finala odigrana + postotak zatvaranja, uz uputu da je to podupirući faktor za QF/SF/F, ne
driver u ranim rundama.

**C2 — LATE-ROUND PRICING DISCIPLINE** (univerzalno, dokaz je cross-surface): od QF nadalje
ne napuhavati confidence heavy favoritu na temelju reputacije; dobro potkrijepljen underdog
u završnici je legitiman pick; finale je najveće-varijance runda. Uz izmjerene brojke i
eksplicitnu zaštitu da ovo NIJE poziv na slijepo favoriziranje underdoga.

**D — struktura tiketa ujednačena za sve podloge** (korisnikova odluka): **4-6 parova,
kombinirana kvota 6.0-40**. `SURFACE_TICKET_OVERRIDES` ispražnjen (clay 6.5-30 i hard max 6
ukinuti). Analysis-only ponašanje nepromijenjeno. **Napomena za buduću reviziju zapisana u
kodu:** pri našem stvarnom pogotku (~63%/pick) prag isplativosti je ~6.0 za 4 para, ~9.3 za
5 i ~14.6 za 6 parova — fiksni donji prag 6.0 znači da su tiketi s 5-6 parova pri dnu
raspona matematički nepovoljni (kandidat: min kvota koja skalira s brojem nogu).

**Ishod:** 48 novih testova (D, B, A1-A5, C1, C2) + regresija scouting i smoke suita + puni
dry-run. Jedan pravi bug uhvaćen vlastitim testom tijekom rada: A5 je prvo koristio
nepostojeći stupac `created_at` umjesto `fetched_at`.

---

## 2026-07-25 — Scouting profili (Excel) + surface-fizika destilat (Word) kao sekundarni izvor

**Povod:** korisnik priložio dva dokumenta: "ATP_Player_Scouting top100.xlsx" (100 igrača:
stil, prednosti/mane, matchupovi, uz pošten confidence sustav High→Insufficient i legendu
"analyst inference, NOT fresh research — validate before use") i "Tennis_Surface_Analysis.docx"
(fizika i taktika podloga, 30 navedenih izvora). Zatražio kritičku procjenu pa integraciju
kao SEKUNDARNI izvor istine za izjednačene mečeve.

**Procjena prije implementacije:** Word dokument neovisno POTVRĐUJE ~80% postojećih odluka
(surface ELO, indoor amplifikacija, serve težine po podlozi, tiebreak lutrija, altitude...)
— glavna stvarna rupa: model o stilu igrača zna samo ruku, a stilski matchup može pomaknuti
vjerojatnost za nekoliko pp uz isti rating (Harvard izvor u dokumentu). Excel: ~69/100
igrača upotrebljivo (Med+); 2026 tvrdnje konzistentne s NAŠIM podacima iz prve ruke (Fery
"Wimbledon run" = srušio nas 6×; Cobolli "breakout" = u našem vetu; Merida "clay craftsman"
= osvojio Umag protiv našeg picka). Za slavne igrače vrijednost je SIDRENJE (model čita
dogovorene činjenice umjesto vlastite memorije), za 2026 risere stvarna nova informacija.

**Što:**
- **Nova Supabase tablica `player_scouting`** (ključ: normalizirano ime; sadržaj: rank,
  stil, podloge, prednosti/mane, matchupovi, confidence, source_date). U schema.sql;
  postojeća instanca treba ručni CREATE TABLE (vidi upute korisniku).
- **`scripts/import_scouting.py`**: Excel → Supabase upsert; `--dry-run` mod; legende na
  dnu Excela automatski preskočene; ponovljivo za buduća osvježavanja.
- **`db.get_all_scouting()`**: jedan query po daily runu, graceful {} ako tablice nema.
- **`run_daily._find_scouting()`**: lookup po normaliziranom imenu + fuzzy fallback preko
  postojećeg `_name_match` (isti mehanizam kao screenshot kvote).
- **Prompt: nova sekcija "SCOUTING PROFILES (secondary evidence)"** sa strogim pravilima:
  max ±3pp utjecaja; tie-breaker za izjednačene mečeve; NIKAD ne nadjačava mjerene brojke;
  anti-double-counting (kvalitativni kontekst za interpretaciju brojki, ne dodatni dokaz);
  stilski matchup eksplicitno dozvoljen kao faktor uz trenutnu podlogu; **Low/Insufficient
  profili se NE ubacuju** — umjesto njih "No reliable scouting — do not fill from memory"
  (poštuje autorovu vlastitu legendu, sprječava da model rupu popuni halucinacijom).
- **Clay pravilo 11 (FAST-CLAY CONDITIONS)** — jedini destilat iz Word dokumenta koji nam
  je stvarno nedostajao: visinski/vrući clay (Madrid, Gstaad, Kitzbühel) pomiče ponašanje
  prema hard vrijednostima; veže se na postojeći Altitude kontekst. Ostatak dokumenta
  NAMJERNO nije prepisan u prompt (već pokriveno težinama/pravilima — izbjegnuto dvostruko
  brojanje istih dokaza).
- **context_snapshot v2**: + `p1/p2_scouting_confidence` — za koji mjesec mjerljivo je li
  scouting stvarno pomogao (WR sa scoutingom vs bez), isti standard kao za druge varijable.
- Scouting NEMA deterministic veto-moć (interpretacija, ne mjereni podaci) i NE ulazi u
  feedback petlju težina.

**Ishod:** 27 novih testova (parse 100/100 igrača, confidence gating, prompt pravila,
end-to-end mock s context_snapshot v2, fuzzy lookup) + regresijski smoke test svih
determinističkih filtera i prompt markera (sve prošlo) + end-to-end dry-run bez tablice
(graceful degradacija). **Čeka korisnika:** CREATE TABLE u Supabase + prvi import.

---

## 2026-07-20 — Korekcija praga: both-declining cap zategnut s "1/3 ili lošije" na strogo "0/3"

**Povod:** korisnik, gledajući stvarne ponedjeljkove (20.07.) ATP 250/500 prvokolaške
mečeve (Estoril, Kitzbühel), primijetio da bi mnogi parovi imali oba igrača na 1/3 u
zadnja 3 meča — brinuo se da će both-players-declining pravilo (jučer otvrdnuto u kod)
isključiti previše mečeva i onemogućiti sastavljanje tiketa. Predložio strožu granicu
(samo 0/3, ne "1/3 ili lošije").

**Provjera na stvarnim podacima PRIJE odluke:** od 14 main-tour mečeva 20.07., **6 (43%)**
palo bi na starom pragu — od toga samo 1 (Muller-Navone) stvarni 0/3-vs-0/3 slučaj, ostalih
5 su 1/3-vs-1/3 ili 0/3-vs-1/3 kombinacije. Dodatno: originalni dokumentirani dokaz koji je
uopće pokrenuo ovo pravilo (Butvilas-Huesler, clay rules v1) bio je baš 0/3-vs-0/3 — "1/3 ili
lošije" je bila NEPROVJERENA generalizacija u kodu, ne dokazan prag.

**Što:** `run_daily._is_declining()`: `sum(...) <= 1` → `sum(...) == 0`. Prompt-tekst
(grass rule 7, clay rule 3 — Claudeova vlastita procjena) NAMJERNO ostaje širi ("1/3 ili
lošije") — Claude i dalje smije biti oprezan kod 1/3-vs-1/3 kroz vlastiti confidence, samo
to više nije automatski tvrdi izbačaj iz tiketa. Kod i prompt sada namjerno NISU identični
(kod = dokazan slučaj, prompt = šira preporuka).

**Ishod:** ista provjera na istim 14 mečeva 20.07. nakon izmjene: samo 1/14 (7%) i dalje
pada (Muller-Navone, jedini dokazan tip slučaja) — pad s 43% na 7% isključenih. Novi
regresijski test (test_c_deterministic.py, 3b) direktno kodira ovaj scenarij (Van De
Zandschulp-Faria tip 1/3-vs-1/3 prolazi, Muller-Navone tip 0/3-vs-0/3 i dalje pada).
Regresija hard v1 + universal logging suita prošla.

---

## 2026-07-18 (osmi put) — Preporuke C, F, D iz stručnog komentara: otvrdnuta 2 pravila, kalibracijska tablica, hard okidač

**Povod:** korisnik pročitao stručni komentar + preporuke A-F iz dokumentacije sustava,
odlučio zadržati strukturu tiketa netaknutom (kvota/broj parova po podlozi ostaju kako jesu
— A i A-tipa promjene isključene), i zatražio preporuku što je odmah spremno za implementaciju.
Odabrano: C (otvrdnuti prompt-only pravila), F (kalibracijska tablica), D (hard okidač) —
odobreno "moze c f i d napravi".

**C — Both-players-declining cap i clay rest/fatigue differential otvrdnuti u kod:**
- Provjera koda PRIJE implementacije otkrila da je moja ranija tvrdnja ("sve tri podloge")
  bila netočna za drugo pravilo — ispravljeno prije pisanja koda:
  - **BOTH-PLAYERS-DECLINING CAP** (60% kad su oba igrača 1/3 ili lošija u zadnja 3 meča):
    postojao je u grass (rule 7) i clay (rule 3) promptu, NE u hardu. Logika je surface-
    neutralna (dva neizvjesna igrača = neizvjestan meč, bez obzira na podlogu) — hard
    pravila to i sama traže ("surface-independent, MUST be enforced from day one") — pa je
    `_both_declining_ok()` implementiran univerzalno, sve tri podloge, i tekst pravila
    dodan hardu (rule 12) za dokumentacijsku dosljednost.
  - **REST & FATIGUE DIFFERENTIAL** (−4pp, −6pp u Bo5, kad naš pick ima 2+ meča/7 dana I 2+
    manje dana odmora od protivnika): postojao je SAMO u clayu (rule 4), s obrazloženjem
    izričito vezanim uz clay ("rallies are the longest in tennis") — NIJE preneseno na
    grass/hard (nema dokaza), `_clay_fatigue_ok()` implementiran clay-only.
- `run_daily.py`: nove zastavice `p1/p2_declining` (iz `p1_form.get("matches")[:3]`, treba
  3+ odigrana meča) i `p1/p2_fatigue_disadvantage` (dani odmora preko novog `_rest_days()`
  helpera + `matches_7d`), postavljene po meču uz postojeće Fery-veto zastavice.
- `ticket_builder.py`: `_both_declining_ok()` (isključuje pick ako su oba igrača declining
  — 60% < 63% tiketni prag pa svejedno ne bi prošao, ovo samo jamči da eventualno
  preoptimistična procjena ne proturije) i `_clay_fatigue_ok()` (računa efektivni
  confidence umanjen za penal, zahtijeva da i tako umanjen i dalje bude ≥63%) — oba
  ožičena u `_selection_ok`.

**F — Kalibracijska tablica proširena na puni korpus, podijeljena po podlozi:**
- Otkriveno tijekom implementacije: kalibracijska tablica na "Model Statistike" stranici
  VEĆ je postojala, ali se gradila SAMO iz `ticket_matches` (uzak, selektirani uzorak —
  isti problem koji je evening update riješio za feedback petlju ranije danas, ali ova
  Streamlit tablica nikad nije ažurirana da prati tu promjenu).
- `database/supabase_client.py`: nova `get_resolved_analyzed_matches()` — čita puni
  `analyzed_matches` korpus gdje `prediction_correct` nije null.
- `pages/4_Model_Statistike.py`: kalibracijska sekcija prepisana da koristi taj korpus,
  PODIJELJENA PO PODLOZI (tabovi Sve/Clay/Grass/Hard) — izravan test je li prekalibracija
  (Nalaz 02) stvarno neovisna po podlozi, umjesto jedne kombinirane tablice koja to
  ne bi mogla pokazati. Osvježava se uživo pri svakom otvaranju stranice.

**D — Hard revalidacijski okidač:**
- `run_daily.py`, rano u `main()`: broji riješene hard picke u `analyzed_matches` (preko
  iste `get_resolved_analyzed_matches()`), javlja upozorenje u dnevnom logu čim prag 30
  bude dosegnut — umjesto oslanjanja da netko ručno primijeti.

**Ishod:** novi unit test suite (test_c_deterministic.py, 19 asercija) + F testiran
(uzorak trenutno n=0 jer se šire razrješavanje tek počelo puniti od danas — očekivano) +
regresija sva tri ranija test suita + end-to-end dry-run.

---

## 2026-07-18 (sedmi put) — Feedback model: Haiku → Sonnet, output_config effort=high

**Povod:** korisnik pitao, nakon prelaska "analysis" koraka na Sonnet, vrijedi li isto napraviti
i za večernji feedback job. Objašnjeno prije implementacije: evening posao ima dva Claude
poziva (analiza zašto smo izgubili konkretan meč, i prijedlog korekcije težina), oba tada
na Haiku, oba niskog volumena (max 5 loss-analiza + povremeni prijedlog težina tek nakon 5+
novih analiza) — pa je dodatni trošak trivijalan bez obzira na odluku. Očekivana dobit
procijenjena manjom nego kod "analysis" koraka (slobodno pisanje objašnjenja, ne kalibrirana
brojčana procjena), ali `_maybe_update_weights` izravno mijenja žive težine za sve buduće
predikcije — najveći utjecaj po pozivu u cijelom večernjem jobu. Korisnik odobrio: "moze da".

**Što:**
- `CLAUDE_MODELS["feedback"]`: `claude-haiku-4-5-20251001` → `claude-sonnet-4-6`.
- `feedback_analyzer.py` `_analyze_lost_match()`: `output_config={"effort":"high"}` dodan,
  `max_tokens` 700→1200 (margin).
- `feedback_analyzer.py` `_maybe_update_weights()`: `output_config={"effort":"high"}` dodan,
  `max_tokens` 500→900 (margin).
- `"analysis"`/`"ticket_writer"`/`"odds_extraction"` nisu dirani ovim krugom (već riješeni ili
  nepromijenjeni).

**Ishod:** mock test potvrđuje kwargs (model/effort/max_tokens) na `_analyze_lost_match`.
STVARNI (ne-mock) pozivi za OBA feedback poziva uspjeli — `_analyze_lost_match` vratio
strukturiranu analizu; `_maybe_update_weights` (DB slojevi monkeypatchani sa 6 sintetičkih
gubitaka, `save_new_weights` presretnut kao no-op da NIKAD ne dirne produkcijske težine)
proizveo koherentan, dobro obrazložen prijedlog korekcije (elo_ranking −3.0%, recent_form
+3.0%, s jasnim obrazloženjem po gubitku). Regresija sva tri ranija test suita (hard v1,
universal logging, sonnet analysis — potonji ažuriran jer je stara asercija "feedback ostaje
Haiku" sad zastarjela) prošla bez padova.

---

## 2026-07-18 (šesti put) — Analysis model: Haiku → Sonnet, output_config effort=high

**Povod:** korisnik primijetio da jezgru predikcije (pick/confidence/fair_odds po meču) radi
Haiku dok finalna holistička recenzija tiketa i write-up već koriste Sonnet — pitao je vrijedi
li podići i taj korak. Direktno povezano s nalazom iz istog dana (dokumentacijski pregled
sustava): precjenjivanje pouzdanosti (~7-16pp) otkriveno je NEOVISNO na sve tri podloge, što
sugerira svojstvo modela, ne podloge — jezgra predikcije je ujedno i najvažnija odluka u
cijelom pipelineu (sve nizvodno — filteri, kombinatorika — samo radi s brojkama koje ovaj
poziv već odluči).

**Što:**
- `CLAUDE_MODELS["analysis"]`: `claude-haiku-4-5-20251001` → `claude-sonnet-4-6` (config/model_config.py).
- `predictor.py` `analyze_match()`: dodan `output_config={"effort": "high"}` na Claude poziv,
  `max_tokens` podignut 900→1500 (margin). Korisnik izvorno tražio "high ili extra high" —
  `"xhigh"` je isproban prvo i odbijen od strane API-ja (400: "Supported levels: high, low,
  max, medium" — ovaj model nema xhigh razinu), pa je `"max"` privremeno postavljen kao
  najbliži ekvivalent, ali korisnik je eksplicitno tražio `"high"` umjesto `"max"` — to je
  finalna vrijednost.
- `"feedback"` (analiza gubitaka u feedback_analyzer.py) i `"ticket_writer"`/`"odds_extraction"`
  NISU dirani — ostaju kako jesu (feedback i dalje Haiku, ostala dva već Sonnet).
- Napomena: `CLAUDE_MODELS["analysis"]` dijeli se i s hipotetskim "kad bih baš morao riskirati"
  write-upom u `ticket_builder.py` (_generate_hypothetical_summary) — taj poziv automatski
  dobiva Sonnet kao model (bolji tekst), ali NE dobiva `effort=high` (nije dirano, ostaje
  default effort — ta odluka nije ono na što se korisnikov zahtjev odnosio).

**Ishod:** mock-testovi potvrđuju konfiguraciju i kwargs poziva; regresija starih test suita
(hard v1 + universal logging) prošla bez padova; STVARNI (ne-mock) API poziv s
`output_config={"effort":"high"}` uspio (7.4s, bez greške) — model je ispravno preskočio
namjerno oskudan testni fixture (5/7 kategorija N/A) umjesto da nagađa, dobar znak discipline
na visokom effortu. Puni end-to-end dry-run sa stvarnim podacima dana istog dana.

---

## 2026-07-18 (peti put) — 9 korisnikovih prijedloga: pregled + univerzalni fixevi + context logging

**Povod:** korisnik predložio 9 ideja za poboljšanje modela (doba dana, 3-set decider record,
ranking gap, ista nacionalnost, tiebreak favorit/outsider, brzina servisa, umor/motivacija
nakon velikog turnira, geografska greška "Molcan/Slovačka", turnirska povijest). Prije bilo
kakve implementacije napravljen je pregled po točkama kroz stvarni kod (ne pretpostavke) —
9 vs 9 kod: 1 je već potpuno implementiran (turnirska povijest, `tournament_history`), 1 je
odmah analizabilan iz postojećih podataka (tiebreak), 1 je jeftin prompt-fix (geo-greška),
1 je već testiran sa suprotnim zaključkom (ranking gap na clayu), 4 zahtijevaju novo
prikupljanje podataka prije analize (doba dana, decider record, nacionalnost, prethodni
turnir), 1 nije dostupan u trenutnom API-ju (brzina servisa km/h — nijedan endpoint koji
koristimo to ne vraća, ni live ni post-match).

**Što (korisnik odobrio cijeli paket, "univerzalno za sve podloge"):**
- **Anti-halucinacijski fix (univerzalan, shared prompt template):** nova STRICT
  ANTI-HALLUCINATION bullet zabranjuje izmišljanje geografskih/nacionalnih tvrdnji izvan
  doslovnog Country polja (npr. "susjedna država", "domaći navijači preko granice").
  Root cause NIJE bug u kodu — nema tablice granica nigdje — nego LLM slobodna asocijacija
  (Claude je u analizi tvrdio da Slovačka graniči s Hrvatskom radi "home crowd" narativa;
  ne graniči). Isti princip kao postojeća zabrana izmišljanja "title defence" (linija 131-133).
- **HOME-CROWD pravilo — parity gap otkriven i popravljen:** pravilo je već bilo izvedeno iz
  cross-surface analize (31 meč, sve podloge), ali tekst je postojao SAMO u clay promptu.
  Propagirano identično u grass i hard pravila (ista evidencija, ista formula −3pp/ispod 63%).
- **RANKING-GAP DEFLATION — grass dobiva, hard namjerno NE:** grass dobiva isti princip kao
  clay (ranking odražava SVE podloge, manje pouzdan od surface-specific ELO na specijaliziranim
  podlogama), ali iskreno označeno kao "provisional" — nema grass-specifičnih dokumentiranih
  gubitaka kao kod claya (Darderi/Khachanov/Faria). Hard NAMJERNO ne dobiva ovo pravilo — hard
  već ima suprotan, dokazan zaključak (rule 7 RANKING RELIABILITY: na hardu je ranking/ELO
  gap legitimno pouzdaniji jer je podloga neutralna) — dodavanje deflacije bilo bi
  kontradiktorno vlastitom dokazu.
- **context_snapshot logging (nova JSONB kolona, `analyzed_matches`, univerzalno sve podloge):**
  počinje se bilježiti dob, nacionalnost, vrijeme meča (već se dohvaćaju uživo, sad se i
  spremaju), plus dvije NOVE izvedene varijable — `decider_record` (Bo3 2-1 win/loss tally iz
  zadnjih odigranih mečeva, Bo5 namjerno izostavljen jer se ne može razlikovati od 3-0 sweepa
  bez podatka o formatu) i `previous_tournament_level` (tier igračevog zadnjeg odigranog
  turnira, preko novog `get_tournament_tier()` wrappera, cache-irano). Sve NE ulazi u prompt
  niti utječe na pick/confidence — čisto bilježenje dok se ne skupi uzorak za analizu.
  `context_version: 1` u JSON-u radi budućih izmjena sheme.
- **Analiza #5 (tiebreak favorit/outsider) — odmah izvedena iz postojećih podataka:**
  71 od 229 resolved ticket_matches sadrži tiebreak set. Favoriti (kvota ≤1.70) u tim mečevima:
  60.7% WR (n=61) — gotovo identično njihovom baznom WR (63.1%, n=160), nema odstupanja.
  Outsideri (kvota ≥2.00): 75.0% WR ali n=4 — statistički beznačajno, NE citirati kao nalaz.
  Zaključak: trenutno nema iskoristivog signala; treba čekati veći uzorak, posebno u
  outsider+tiebreak kutu.

**Ishod:** 27 novih unit-testova (anti-halucinacijski tekst, HOME-CROWD/ranking-gap parity,
`get_tournament_tier`, `_decider_record`/`_previous_tournament_level`, `context_snapshot`
end-to-end s mockiranim Claude odgovorom) + regresija starih 18 hard-revizijskih testova
(svi prošli) + end-to-end dry-run. **Korisnička akcija potrebna:** `context_snapshot` kolona
dodana u `schema.sql` za buduće instalacije, ali postojeća Supabase tablica treba ručni
`ALTER TABLE analyzed_matches ADD COLUMN IF NOT EXISTS context_snapshot JSONB DEFAULT '{}'::jsonb;`
u SQL Editoru prije nego se novi podaci počnu stvarno spremati.

---

## 2026-07-18 (četvrti put) — Cross-surface parity: clay hot-hand popravak + grass dead-zone + clay GS

**Povod:** korisnik pitao koja su od hard-revizijskih pravila zapravo univerzalna, ne samo
hard-specifična. Provjera koda + korpusa otkrila je tri nedosljednosti:

1. **Clay hot-hand pravilo je imalo ISTU grešku koju smo tog jutra popravili na hardu** —
   "3+ pobjede u turniru → veto" i dalje živi u clay promptu (rule 2), a to se okida na
   SVAKI meč od SF-a nadalje (3+ pobjede = SF). Za razliku od hardovog builder-level veta,
   ovo je bio samo prompt-savjet (manje opasno, ali ista logička greška), i clay se **igra
   upravo sada** (finala).
2. **Grass nema NIKAKVU zaštitu od mrtve zone kvota 1.43-1.60**, unatoč najjačem dokazu od
   sve tri podloge (n=33, 52% WR, ROI -20.3% dedupe) — jače nego evidencija koja je
   opravdala potpunu zabranu na hardu (koji ima 0 stvarnih pickova).
3. **GS prag 65% je stavljen na hard (bez dokaza)**, ali dokaz da GS podbacuje postoji na
   **clayu** (Roland Garros 54% vs ne-GS 67%), NE na grassu (Wimbledon 61% == ne-GS 61%,
   nema razlike) — pravilo je bilo na krivoj podlozi.

**Što (potvrdio korisnik — implementirati sve tri):**
- **Clay hot-hand pravilo prepisano** (isti pristup kao hard): "3+ pobjede" trigger
  zamijenjen s ciljanim uvjetom — protivnik mora biti (a) niže rangiran/slabiji clay ELO
  od našeg picka, (b) pobijedio SEEDANOG/više rangiranog igrača ovaj tjedan (pravi upset),
  i (c) naš pick je samo marginalni favorit. Dva favorita koja su normalno napredovala do
  SF/F = normalan meč, bez auto-capa.
- **Grass dead-zone ban** (`_grass_bands_ok`, nova): kvota 1.43-1.60 na grassu nikad ne
  ulazi na tiket — identičan mehanizam kao hard (`_hard_bands_ok`), ista granica.
- **Clay GS prag** (`_clay_gs_conf_ok`, nova): na clay Grand Slamu (Roland Garros) pick
  treba >=65% confidence — identičan mehanizam kao hard GS prag, primijenjen tamo gdje
  dokaz stvarno stoji. Grass GS NE dobiva ovaj prag (nema dokaza za razliku GS/ne-GS).
- Sve novo je ožičeno u `_selection_ok` (zajednički filter za sve kandidatske liste tiketa).

**Ishod:** 18 unit-testova (novi: grass dead-zone 6 scenarija, clay GS 5 scenarija, clay
prompt-tekst provjera 4 asercije) + end-to-end dry-run. Fery-veto je provjeren kao već
univerzalan (bez izmjene, `_opponent_beat_us` nema surface-provjeru).

---

## 2026-07-18 (treći put) — Fery-veto: prag 1→2 poraza, prozor 21→14 dana

**Povod:** korisnik primijetio da je Fery-veto možda prestrog — jedan poraz od nekog igrača
u turniru odmah ga trajno vetira, iako naši pickovi i onako pogađaju samo ~60% vremena
(znači i ISPRAVAN pick gubi ~40% vremena zbog normalne varijance). Jedan poraz nije pouzdan
dokaz da je taj igrač "naš problem" — dva poraza od istog igrača u istom turniru jest.

**Što (potvrdio korisnik):**
- `get_recent_lost_matches`: prozor 21→**14 dana** (i dalje pokriva puno trajanje Grand
  Slama; ATP 250/500 turniri traju ~7 dana pa je i 14 s viškom).
- `run_daily` Fery-veto logika: `beaten_us` se sada gradi preko `Counter`-a po
  (pobjednik, turnir) i u veto ulaze samo igrači sa **2+ poraza** u istom turniru
  (prije: bilo koji 1 poraz).
- `_opponent_beat_us` (ticket_builder) komentar ažuriran; sama logika nepromijenjena —
  i dalje čita p1_beat_us/p2_beat_us zastavice, samo su te zastavice sada strože postavljene.

**Ishod (stvarna provjera na Supabase, 18.07.):** stara logika (1 poraz/21 dan) vraćala je
**27 igrača** u vetu; nova logika (2 poraza/14 dana) vraća **3 igrača** (Fery, Cobolli,
Dimitrov — svi doista 2+ poraza na istom Wimbledonu). Pravi ponavljači ostaju uhvaćeni,
igrači koji su nas pobijedili samo jednom (moguća slučajnost) više se ne blokiraju. 11
unit-testova (čista logika brojanja + usporedba starog/novog praga) + end-to-end dry-run.

---

## 2026-07-18 (kasnije) — Korekcija hard revizije: ukinut duplikat + hot-hand win-count veto

**Povod:** korisnik uočio dvije greške u istodnevnoj hard reviziji (dolje):
1. **Duplikat pravilo** izbacivalo dobre mečeve — tiket legitimno pokriva danas+sutra i isti
   dobar meč se SMIJE ponoviti sljedeći dan. Ne želi to.
2. **Hot-hand veto po BROJU pobjeda je logički pogrešan**: do QF-a SVI igrači imaju 2+ pobjede
   (R32→R16→QF), do finala 4 — prag "2+ pobjede" okinuo bi veto na svaki meč završnice i
   onemogućio tiket. Broj pobjeda mjeri napredovanje, ne "vrući nalet". (Čak i motivirajući
   slučaj Merida vs Džumhur bio je FINALE — oba finalista imaju ~4 pobjede, veto ih ne razlikuje.)

**Što (potvrdio korisnik — opcija "ciljano na iznenađenja"):**
- **Duplikat pravilo UKINUTO** (`run_daily`) — vraćeno na staro, isti meč smije na uzastopne tikete.
- **Deterministički hard hot-hand veto UKINUT** (`_hard_hot_hand_ok` obrisan iz ticket_buildera;
  uklonjene i p1/p2_tourn_wins + elo/hold zastavice iz run_daily koje su ga hranile).
- **HARD RULES v1 pravilo 1 prepisano** iz "HOT-HAND VETO (2+ pobjede → skip)" u
  **"HOT-HAND CAUTION"** ciljano na PRAVI upset nalet: oprez/skip SAMO kad je protivnik
  (a) jasno niže rangiran/slabiji ELO od našeg picka, (b) pobijedio SEEDED/više rangiranog
  igrača ovaj tjedan, i (c) naš pick je tek marginalni favorit. Dva legitimna favorita u
  finalu koji su normalno napredovali = normalan meč, ne auto-skip.
- **Fery-veto OSTAJE** (`_opponent_beat_us`) — jedini deterministički hot-hand backstop,
  temeljen na STVARNOM porazu (igrač koji nas je već srušio u istom turniru), ne na brojanju.

**Ishod:** 34 unit-testa (ažurirani: hot-hand win-count veto uklonjen, potvrđeno da finalist
s 4W više ne pada automatski) + end-to-end dry-run. Sve ostale hard promjene (dead-zone ban,
mid-zona, GS 65, težine v14, evening→analyzed_matches, surface-switch) ostaju netaknute.

---

## 2026-07-18 — HARD REVIZIJA: pravila v1 + težine + selekcijska disciplina (PRIJE prvog hard picka)

**Povod:** potpuna revizija grass+clay korpusa po korisnikovoj metodologiji ("Prompt za
poboljšanje modela"), kao priprema za hard sezonu (Washington 27.07. → US Open). Korpus:
**187 unikatnih razriješenih pickova** (grass 84W-54L 61%, clay 29W-20L 59%), **33 prava
tiketa 2W-31L (ROI ≈ -28%)**, single-pick ROI grass -6.4% / clay -9.4%. Hard: **0 pickova
ikad** — v9 težine nikad testirane.

**Glavni nalazi (dedupe, isti meč na 2 tiketa brojan jednom):**
- Model zarađuje SAMO na ekstremima: teški favoriti ≤1.20 (93% grass, +3.1% ROI) i value
  underdozi >2.30 (7W-7L, +28% ROI). Sredina sustavno gubi: **1.43-1.60 najgori band
  (50% WR, ROI -24%)**, 1.91-2.30 41% WR.
- **Hot-hand fade = #1 uzrok gubitaka cross-surface**: Fery nas srušio 6× u 3 tjedna;
  sva 3 clay poraza POSLIJE revizije 11.07. imala su "opponent in run / home" u risk_notes
  — pravila su rizik registrirala ali ga NISU provodila.
- Kalibracija: deklarirani conf 63-70% vraća 55-60% (optimizam ~+7pp).
- Akumulator matematika: uz naše WR-ove **nijedan band nema EV ≥ 1.0 na kombiniranoj 6.5+**
  (najbolji ≤1.20: EV 0.70-0.83). Korisnikova odluka: struktura OSTAJE 6.5-40, hard 4-6 parova.
- GS podbacuje vs ATP 250 (clay 54% vs 67%); 42 duplikata = isti poraz rušio 2 tiketa;
  9/31 tiketa palo na točno 1 promašaju; `analyzed_matches` 419/419 bez ishoda.
- Clay post-revizija 11.07.: **8W-3L (73%), +5.9% ROI** — prvi pozitivan period (n=11, oprez).

**Što (sve implementirano 18.07., aktivno od sljedećeg runa):**
- **HARD RULES v1** u predictor promptu (10 pravila): hot-hand VETO kao mandatory skip
  (elite iznimka hard ELO ≥1900 / hold ≥88%), dvostruka potvrda za 66%+ (a/b/c hard
  kategorije), marginal-favourite reality check (1.43-1.60), TB-lutrija cap 62 (oba hold
  ≥85%), **surface-switch penalty** (clay SF/F u zadnjih 7 dana → -3pp prva 2 hard turnira;
  svježi hard specijalist → plus), heat/retirement guard (retirement zadnjih 14 dana ili
  injury news → skip), ranking-reliability (na hardu ELO/ranking legitiman uz 1 potvrdu),
  US Open prag 65%, indoor amplifikacija servisa, confidence spread honesty.
- **Ticket builder (deterministička PROVEDBA, ne samo prompt):**
  - hard dead-zone **1.43-1.60 = zabranjen na tiketu** (`_hard_bands_ok`);
  - hard mid-zona 1.61-1.90 **max 1 po tiketu** (`_hard_mid_zone_count`);
  - hard GS pick traži **conf ≥65** (`_hard_gs_conf_ok`);
  - conf floor 63 + value-override (58/12pp/max 2) **prošireni na hard**;
  - **FERY VETO (sve podloge)**: pick protiv igrača koji je nama srušio pick u istom
    turniru zadnjih 21 dan = automatski isključen (`_opponent_beat_us`; zastavice
    p1/p2_beat_us postavlja run_daily iz `ticket_matches` gubitaka).
  - **DETERMINISTIČKI HOT-HAND VETO (hard)**: protivnik s 2+ pobjede u OVOM turniru →
    pick isključen iz selekcije, osim elite iznimke (pick hard ELO ≥1900 ili hold ≥88%)
    (`_hard_hot_hand_ok`; p1/p2_tourn_wins + elite podaci iz run_daily). Dokaz potrebe iz
    dry-runa 18.07.: Haiku dao 64% Meridi protiv Džumhura na 4W/0L runu, reviewer pick
    izbacio, ali je kvota-guard (6.5 min) poništio reviewera i vratio original — prompt i
    reviewer registriraju, samo builder-veto garantirano PROVODI.
- **Duplikat pravilo (sve podloge, run_daily):** meč koji je već na jučerašnjem PRAVOM
  tiketu (ne analysis-only) ne ulazi u današnji pool — isti meč nikad na 2 tiketa.
- **Struktura (korisnikova odluka):** hard kombinirana OSTAJE 6.5-40, **4-6 parova**
  (`SURFACE_TICKET_OVERRIDES["hard"]`; "hard" substring hvata i Indoor Hard).
- **Težine hard v14** (Supabase, aktivne): elo 22, serve 22, **surface 20→17** (hard
  najmanje surface-specifičan), form 17→16, **fatigue 11→13** (US vrućina, 9 voidova u
  korpusu), h2h 4, **trajectory 4→6** (hot-hand lekcija). PROVIZORNE — prva kalibracija
  nakon Washington/Montreal tjedana.
- **Evening update sada upisuje ishode u `analyzed_matches`** (zadnjih 8 dana, 0 dodatnih
  API poziva — reuse fixture_winner lookupa): širi korpus za buduće revizije umjesto samo
  selektiranih tiket pickova.
- **Indoor Hard:** potvrđeno — isti hard model/težine (surface match "hard" substring),
  odvojeno praćenje u Loss Analysis ostaje.

**Ograde (protiv overfittinga):** hard n=0 — SVI pragovi (1900/88%, bandovi, 65 GS) su
prijenos s grass/clay i početni; >2.30 value nalaz je n=14 (ne širiti value cap); post-
revizija clay +5.9% je n=11. Prva hard revalidacija: nakon Washington/Los Cabos/Montreal.

**Ishod:** 34 unit-testa + end-to-end dry-run. Prati se.

---

## 2026-07-18 — Poklapanje inicijala kladionice ("Juan M." = "Juan Manuel")

**Povod:** daily tiket 18.07. sve kvote povukao točno OSIM Collignona (1.50 fallback umjesto
1.65). Izmjereno: Collignonovo ime se savršeno poklopilo, ali `find_match_odds` traži da se
poklope OBA igrača, a **protivnik Cerundolo nije** — kladionica je skratila srednje ime:
API "Juan Manuel Cerundolo" (3 riječi) vs screenshot "Cerundolo Juan M." ("Manuel" → "M.").
Zbog toga cijeli par propao → Collignon dobio fallback 1.50.

**Zašto Fix 2 (17.07.) to nije uhvatio:** Fix 2 je hvatao PODSKUP (screenshot ima manje
riječi, sve sadržane). Ovdje "m." ≠ "manuel" — to je INICIJAL, ne podskup.

**Što (`data_fetcher._name_match` + novi `_tokens_covered`):**
- Tokeni se čiste od točaka ("m." → "m").
- Nova pokrivenost s inicijalima: svaki token kraćeg imena mora imati jedinstven par u dužem
  — jednak ILI inicijal-prefiks ("m" ~ "manuel"). Zamjenjuje raniji čisti podskup-rule
  (podskup je sad poseban slučaj s egzaktnim poklapanjem). Prag >=2 poravnate riječi.

**Sigurnost (provjereno testovima):** braća Cerundolo se NE miješaju u stvarnom smjeru
usporedbe (API "Francisco Cerundolo" vs screenshot "Cerundolo Juan M." → False, jer nema
"juan"). Isto-prezime preko postojećeg pravila ostaje kakvo je bilo; find_match_odds ionako
traži poklapanje OBA igrača.

**Ishod:** 14 unit-testova (Cerundolo/FAA inicijali + braća-negativni + regresija Merida/
Burruchaga/Tsitsipas/Dedura) + stvarna provjera: Collignon–Cerundolo sada vraća 1.65.

---

## 2026-07-17 — Otpornost API-ja (retry) + poklapanje skraćenih imena kladionice

**Povod:** jutarnji daily run 17.07. pao je nakon 38s bez emaila. Log: `405 Client Error`
na `/atp/fixtures/2026-07-17` (prvi i kritični poziv) → 0 mečeva → tihi izlaz. Ponovni
(popodnevni) run onda je izbacio čudan analysis-only: odigrani/live mečevi u prikazu i
kvote 1.50 na većini pickova. Sve dijagnosticirano na stvarnim podacima.

**Uzroci (oba postojeća, nevezana uz izmjene od 16.07.):**
1. **Prolazni ispad API-ja rušio je cijeli run.** `_get` je ponavljao pokušaj SAMO na 429
   (rate limit); na 405/5xx je odmah vraćao None. 405 je bio kratkotrajni RapidAPI blip
   (isti endpoint vraća 200 par sekundi kasnije), ali je oborio dohvat mečeva.
2. **Skraćeno ime kladionice se nije poklapalo.** API "Daniel Merida Aguilar" (3 riječi) vs
   screenshot "Merida Daniel" (2 riječi) — `_name_match` je znao obrnut redoslijed i
   višerječna prezimena istog broja riječi, ali ne i podskup → Meridina kvota (1.55) se
   nije našla → fallback 1.50 → meč izgubi odds_available.

**Što (Fix 1 + Fix 2; Fix 3 svjesno odgođen):**
- **Fix 1 — retry na prolazne greške (`data_fetcher._get`):** 405/500/502/503/504 i mrežni
  blipovi (ConnectionError/Timeout) sada se ponavljaju do 3× uz 3s pauzu. Trajne greške
  (401 ključ, 403 kvota, 404 ne postoji) NAMJERNO fail-fast (bez retryja). Da je ovo
  postojalo, jutrošnji run bi preživio 405.
- **Fix 2 — podskup imena (`data_fetcher._name_match`):** ako su sve riječi kraćeg imena
  sadržane u dužem i dijele >=2 riječi → isti igrač. Prag >=2 sprječava lažno poklapanje.
  Postojeće prezime-pravilo (aw[-1]==bw[-1]) nepromijenjeno.

**Napomena — Problem 1 (odigrani/live mečevi u analizi) NIJE riješen ovdje:** uzrok je što
tennis API kasni (odigrane mečeve još vodi `match_winner=None, live=None` → naš filter ih
vidi kao `scheduled`). Grize samo kod popodnevnog re-runa. Korisnikovo rješenje (Fix 3:
"uzmi samo mečeve koji su na kvote-screenshotu") svjesno odgođeno — vidi [[daily-ticket-workflow]].
Fix 1 neizravno gasi korijen: ako jutarnji run preživi, nema potrebe za popodnevnim re-runom.

**Ishod:** 15 unit-testova (retry: 405→200, 5xx→200, 405×3 odustaje, 404/403 fail-fast,
ConnectionError retry; name-match: Merida podskup + negativni) + stvarna provjera da
Burruchaga–Merida sada vraća 1.55.

---

## 2026-07-16 — Screenshot = izvor istine za glavni ždrijeb + Q-tag korekcija runde

**Povod:** nastavak istrage praznog tiketa 16.07. Nakon QF fixa (dolje), Gstaad/Båstad QF
prolaze, ali **Umag i dalje ispada** — iz drugog razloga: API je Umagova četvrtfinala
(16.07.) vratio kao `roundId=9 → Q2` (kvalifikacije), iako je to glavni ždrijeb (potvrđeno
u korisnikovom screenshotu ždrijeba, kolona ČETVRTFINALE). Krivi Q2 tag radio je dvije
štete: (1) quali-guard ga izbacuje sa selekcije, (2) analiza ga dobiva kao "Round: Q2"
(round_id 9 nije u `_round_context` mapi 1–7 → fallback ispiše doslovno "Q2"), pa bi agent
QF analizirao kao kvalifikacije — točno zagađenje round-signala koji inače koristi ispravno.

**Dizajn (potvrdio korisnik — A + B1):** korisnik svaki dan screenshota SVOJE mečeve
(danas + sutra) u "kvote screenshot", a kvalifikacije prije turnira NIKAD ne screenshota,
ne stavlja na Streamlit niti pokreće daily. Zato je prisutnost screenshot kvote pouzdan,
determinístički dokaz da meč **nije** kvalifikacija.

**Što:**
- **A — selekcija (`ticket_builder._is_main_tour`):** ako meč ima screenshot kvotu
  (`has_screenshot_odds`), propušta se bez obzira na API round-tag. Namjerno IZA
  level-provjere: screenshot NE progura Challenger/ITF/Future (to je policy isključenje,
  ne API greška), nego samo zaobiđe round-based qualifying guard (R128/Q na 250/500).
- **B1 — runda (`run_daily._infer_rounds`):** Q1/Q2 grupa se i dalje ne dira OSIM ako bilo
  koji meč u njoj ima screenshot → tada se ne vjeruje Q-oznaci i runda se izvodi iz broja
  mečeva po `(turnir, dan)` (postojeći mehanizam: 4=QF, 2=SF, 1=F). Ispravlja se i `round`
  i `round_id`, pa analiza dobiva točan round-context. RR i prave kvalifikacije (bez
  screenshota) ostaju netaknute — nula regresije na ispravno označene runde.
- **Preraspodjela:** `screenshot_odds` se sada učitavaju PRIJE `_infer_rounds` (bile su
  učitane tek kasnije), i prosljeđuju u brojalicu. Svaki meč dobiva `has_screenshot_odds`
  zastavicu tijekom obrade (poseban lookup samo protiv screenshota).

**Zašto A i B1 zajedno:** B1 ispravlja rundu uzvodno (rješava i krivu analizu i selekciju
u jednom potezu), A je pojas-i-tregeri za selekciju ako Q-oznaka iz bilo kojeg razloga
preživi. Brojalica broji po turniru **i danu** odvojeno (danas QF, sutra SF se ne miješaju).

**Ograničenje:** brojalica broji samo `scheduled` mečeve — jutarnji run (svi scheduled)
daje točnu rundu; popodnevni re-run nakon što dio QF-a završi mogao bi podbrojati. Daily
ide ujutro pa je u praksi bez utjecaja. Za 100% pouzdanost budući korak = live draw endpoint.

**Ishod:** unit-testovi (6 scenarija) + end-to-end dry-run na stvarnom 16.07. — Umag QF
ulazi s ispravnom rundom.

---

## 2026-07-16 — Bugfix: qualifying guard izbacivao četvrtfinala ("QF" počinje s "Q")

**Povod:** 16.07. ujutro (četvrtak, QF dan na Båstad/Gstaad/Umag) Daily tiket vratio prazan
analysis-only email ("No main-tour matches available") iako je 13+3 mečeva prošlo filter
turnira, kvote sa screenshotova bile učitane i Claude analizirao mečeve (potvrđeno u
`analyzed_matches`). Oba jutarnja runa (07:01 i 08:38) "success" — program nije pukao,
nego je selekcija tiho izbacila sve.

**Uzrok:** qualifying guard iz clay revizije 11.07. u `_is_main_tour()` koristio je
`rnd.startswith("Q")` za detekciju kvalifikacija — a **"QF" (četvrtfinale) također počinje
s "Q"**. Na ATP 250/500 su zato SVA četvrtfinala tretirana kao kvalifikacije → nikad na
tiket, a isti filter prazni i analysis-only prikaz. R32/R16 dane (pon-sri) guard ne dira,
pa se bug pokazao tek na prvom QF danu nakon uvođenja.

**Što:** `ticket_builder._is_main_tour()` — kvalifikacija je sada `startswith("Q") and
rnd != "QF"` (Q1/Q2 i dalje blokirani, R128 guard nepromijenjen).

**Ishod:** verificirano lokalnim dry-runom na stvarnim QF mečevima 16.07.

---

## 2026-07-11 — Clay revizija: pravila v1 + težine v8 + selekcijska disciplina (prije Gstaad/Umag)

**Povod:** kompletna revizija clay modela na 32 razriješena picka (28 RG BO5 + 4 ATP 250
kvalifikacije): 17W-15L (53%) uz prosječni confidence 69% (prekalibracija −16pp), **svih 7
čistih clay tiketa izgubljeno**. Dominantan uzrok gubitaka: fade igrača s in-tournament
momentumom (8/15 — Menšik 3×, Arnaldi 2×, Fonseca 2×, Svajda). Dead zone kvota 1.50-1.90
na clayu 3/11 (27%), ista strukturna bolest kao grass. Zona confidence 66-70% pobjeđivala 38%.

**Što (potvrdio korisnik):**
- **CLAY-SPECIFIC RULES v1** u predictor promptu (clay dosad NIJE imao nijedno surface
  pravilo): dvostruka potvrda (2 od 3: clay record / hold% / quality-adjusted forma),
  hot-hand veto s elitnom iznimkom (clay ELO ≥1850 ili hold ≥85%), oba-u-padu cap 60%,
  rest differential −4pp (BO5 −6pp), ranking-gap deflacija, underdog disciplina,
  home-crowd pravilo (asimetrično: domaći protivnik −3pp / skip; naš domaći bez bonusa),
  qualifying guard, clay kalibracijski spread, BP-conversion preko aseva.
- **Ticket builder:** confidence floor 63% + value-override (58%/12pp/max 2) prošireni
  s grassa na clay; **clay raspon kombinirane kvote 6.5-30 i max 6 parova** (korisnikova
  odluka; global ostaje 6.5-40/7); max 1 clay pick u dead zoni 1.50-1.90 po tiketu;
  R128/Q na ATP 250/500 = kvalifikacije → nikad na tiket (11.07. su 4 kvalifikacijska
  meča ušla kao "ATP 250 R128", 2/4 pala); edge >20pp ne dobiva score bonus (umišljeni
  edge = naša greška, ne value — Collignon @2.82 lekcija); reviewer dobio clay checkove.
- **fair_odds popravak (sve podloge):** LLM-ov fair_odds gravitirao na ~1.52 neovisno o
  meču (12/15 clay gubitaka fair 1.51-1.54 na kvotama 1.28-2.82) → sada fair_odds =
  100/confidence u postprocessingu, value = edge ≥3pp prema stvarnoj kvoti. Edge/value
  mehanika prvi put stoji na konzistentnoj osnovi.
- **Težine v8 clay** (Supabase): elo 22→18, form 20→18, fatigue 11→12, trajectory 4→9;
  surface 20, serve 19, h2h 4 nepromijenjeni.
- **Podaci:** Country u analysis promptu (za home pravilo — nationality je već bila u
  fetchu); altitude tablica + Gstaad 1050 m i Kitzbühel 762 m, pragovi 1500/800 → 1000/600
  (Gstaad se dosad analizirao kao razina mora).

**Zašto:** vidi analizu u sesiji 11.07. — retroaktivno bi pravila eliminirala/degradirala
9-10 od 15 gubitaka uz gubitak 0-1 od 17 dobitaka. Oprez: korpus je malen (n=32) i 87%
s jednog kaotičnog RG-a — pravila su pisana kao mehanizmi (veto/cap/dvostruka potvrda),
brojčani pragovi (1850, 85%, 5pp) su početni i revidiraju se nakon Gstaad/Umag/Båstad
ciklusa. Strukturni nalazi (dead zone, overconfidence 66-70, hot-hand) neovisno potvrđeni
na grass korpusu (n=177).

**Ishod:** prati se.

---

## 2026-07-05 — Grass value-override (value smije proći ispod floora)

**Što:** Grass floor (≥63% confidence) dobio iznimku za **standout value** oklade: grass pick
ispod 63% prolazi ako je confidence ≥58% I edge ≥12pp, najviše 2 takve po listiću (top po edge-u).

**Zašto:** Osnovna filozofija je VALUE, ne lov na niske kvote. Apsolutni floor od 63% odbacivao je
odlične value oklade (npr. model 61% vs tržište 42%, edge 19pp, kvota 2.35 = +43% EV) samo zbog
niskog apsolutnog confidence-a. Edge = usporedba s tržištem → legitimna upotreba kvote, različito
od "biranja niske kvote". Omogućuje povremeni opravdani 15-25 listić.

**Rizik:** edge ovisi o kalibraciji `fair_odds` (nova od v3). Zato oprezan start: prag 12pp, kap 2,
min conf 58%. Ako se pokaže presuho → spustiti prag. Prati se.

**Ishod:** prati se.

---

## 2026-07-05 — Grass prompt v3 + spuštanje floora na 6.5

**Što:**
- Uklonjen tvrdi cap confidence-a od 64% → uvedeno **širenje** (dominantni favoriti 72-80%,
  coinflipovi <60%). Cilj: vratiti confidence kao koristan signal za rangiranje.
- Kombinirana kvota floor: **9.0 → 6.5** (raspon 6.5-40). Maknut poseban 4-mec override
  (jedinstvena, stabilna granica).
- Grass rule 10 (novo): tiebreak + serve-hold (85%+) kao ODLUČUJUĆI faktor, ne "rizik".
- Grass rule 2 pooštren: hard/clay forma se NE prenosi na travu.

**Zašto:** Post-Wimbledon analiza (n=51). Model odličan na teškim favoritima (kvota ≤1.42 → 78%),
katastrofa u "mrtvoj zoni" (1.43-1.90 → 20%; 1.43-1.60 doslovno 0/7). Confidence spljošten na
62-64% (cap ubio diskriminaciju). 9.0 floor je matematički forsirao dead-zone pickove → 3/3
prava tiketa izgubljena. Vidi memoriju `grass-model-structural-finding`.

**Ishod:** prati se. Commit `865faa6`.

---

## 2026-07-05 — Analysis-only cap 12 + hipotetski "forced risk" u mailu

**Što:** Analysis-only ograničen na max 12 mečeva (sortirano po kvoti), izbačene kvote <1.06.
Dodana email sekcija "🎯 If I had to risk it..." — najbolji 4-7 pick / 9-40 tiket kad bismo baš
morali (Claude Haiku), samo u mailu, ne u bazu.

**Zašto:** 18 mečeva u analysis-only bilo je previše; korisnik želi info "kad bih morao riskirati".

---

## 2026-06-27 — Učenje iz tipova + trajno spremanje rezultata/statistika

**Što:** Evening update sada sprema `actual_score` i `match_stats` (JSONB) za svaki razriješen
meč (pobjeda I poraz, sve podloge). Petlja za korekciju težina uči i iz DOBITAKA, ne samo gubitaka.

**Zašto:** Gradnja korpusa "hipoteza prije meča vs stvarni ishod + brojke" za buduće korekcije.
Agent je prije učio samo iz pola slike (samo gubici).

---

## 2026-06-27 — Grass težine v12

**Što:** elo_ranking 14→16, serve_return 21→23, recent_form 18→15, tournament_trajectory 8→7.
**Zašto:** Umjeren povrat prema serve/ELO (dokazani dobitni signal); "forma-preko-ELO" doktrina
iz v10/v11 sistemski gubila. (Supabase model_weights v12.)

---

## 2026-06-22 — Grass prompt v2 + težine v11 + confidence floor

**Što:**
- Grass floor u ticket builderu: grass pick mora ≥63% confidence PRIJE selekcije; ugašena
  kaskada 58/55 i edge-override ZA TRAVU (koristi modelov confidence, ne kvotu).
- Grass prompt v2: 8→9 pravila (ELO isolation, surface-weighted forma, fatigue zaoštren,
  bye=hendikep, oba 1/3 → cap 60%, conf cap 64%, honesty floor).
- Grass težine v11: elo 17→14, trajectory 4→8, fatigue 12→13, serve 22→21.

**Zašto:** 6 uzastopnih izgubljenih tiketa na travi (16-22.06). Analiza 14 gubitaka.

---

## 2026-06-16 — Grass prompt v1 + težine v10

**Što:** Prva grass-specifična prompt pravila (ELO cap 100pt, rest paradox, fatigue+momentum).
Težine v10: elo 22→17, form→19. **Zašto:** analiza 12 grass gubitaka; ELO precijenjen.

---

## 2026-06-04 — Surface-specifične težine + tournament_trajectory

**Što:** Odvojene težine po podlozi (clay/grass/hard). Dodan 7. faktor `tournament_trajectory`
(in-tournament momentum). Grass v8: serve-heavy (serve 25, surface 22).

---

## Ranije (2026-05-27 → 06-03) — Temelj

Inicijalni model, uklonjen `odds_movement` faktor (model misli neovisno o tržištu),
dodani: surface record, tournament record, quality-adjusted forma, hold%, avg opp ELO,
H2H reliability, round context, draw-history (anti-halucinacija), ELO cache.
