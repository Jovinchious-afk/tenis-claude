# Backlog i dnevnik rada

Čitljiv pregled projekta: **što čeka** (s uvjetom kada se radi) i **što smo napravili** (po
danima, jednostavnim jezikom). Brojke, obrazloženja i tehnički detalji su u
`MODEL_CHANGELOG.md`; popis svega što ulazi u odluku o picku je u `DECISION_INPUTS.md`
(dalje: DI).

**Pravilo:** na kraju svake radne sesije ovdje se dopiše što smo napravili i ažurira se
popis otvorenog. Otvoreno 26.09.2026 19:21, zadnje ažurirano 27.09.2026 12:00.

**Jedna naredba za sve zakazane provjere kandidata:** `python scripts/measure_candidates.py`
(čita bazu, ništa ne mijenja; kaže za svakog kandidata ČEKA / POTVRĐEN / PAO).

---

## ČEKA — TVOJE ODLUKE (iz povijesnog laboratorija, 27.09.2026 12:00)

Na 12.324 ATP meča nijedan naš kandidat nije pobijedio tržišnu cijenu (izvještaj
`revizije/2026-09-27/POVIJESNI_LAB_2026-09-27.md`). Ništa od ovoga nije ugrađeno:

1. **Zatvoriti K15, K16 i K3?** Tržište pobjede u sezoni i GS iskustvo već plaća (+0,0pp na
   11.139 i +1,1pp na 826 mečeva); Bo5 favoriti 1,30–1,50 idu čak +4,3pp, suprotno od K3.
2. **K5 (oprezna zona od 1,35):** na tržištu su favoriti u 1,35–1,43 BOLJI od cijene (+3,7pp).
   Prijedlog: ne uvoditi na n=20; ako se mjeri dalje, tražiti n ≥ 100.
3. **Jedna nova era prompta** (sve odjednom, da se ne troše dvije ere): maknuti pravilo o
   domaćem terenu (K2 — domaći igrači −1,4pp naspram cijene), uputu o statistici s turnira svesti
   na opis (K12 — r=+0,004), ispraviti "63%" na dva mjesta (kod je na 60), maknuti datume i
   CAPS naglaske iz teksta, i uz to stavku "nesigurnost brojki". Gotov prijedlog izmjene:
   `revizije/2026-09-27/PROMPT_AUDIT_2026-09-27.md`.
4. **Struktura oklade — najveća poluga za ROI.** Noge pravih tiketa imaju prosječni EV −3,1%
   po SuperSport kvoti; tiket od 4 noge je zato oko −12% očekivano. Manje nogu, ili samo noge s
   jasnom prednošću u cijeni (konsenzus ≥ +3pp iznad SuperSporta), bilo bi bliže nuli —
   ali daje puno manje tiketa.

## ČEKA — zakazane provjere

Pravilo projekta (kapija, od 06.09.2026): nijedan nalaz ne ulazi u odluku dok se ne potvrdi
na mečevima na kojima nije pronađen. Svaka stavka ima prag zapisan UNAPRIJED.

| što | kada / uvjet | ishod | gdje |
|---|---|---|---|
| **K15 — ATP pobjede u sezoni** | 150 riješenih analiza od 27.09.2026 (procjena: druga polovica listopada) | potvrdi → bonus pri izboru tiketa; padne → odbacuje se. **Povijest 27.09.: +0,0pp na 11.139 mečeva — predlažem zatvoriti** | DI K15; `python scripts/measure_player_context.py` |
| **K16 — GS iskustvo u završnicama** | 40 mečeva QF/SF/F u kojima samo jedan igrač ima GS polufinale (više mjeseci) | +5pp ili više → razmotriti bonus u završnicama. **Povijest 27.09.: +1,1pp, interval prelazi nulu — predlažem zatvoriti** | DI K16 |
| **Omjer protiv ljevaka** | 300 mečeva s ljevakom (danas 120) | ponovno izmjeriti; do tada samo bilježenje | DI "IZMJERENO 26.09.2026" |
| **K1 — prag 60 + kazna 65-68** | prvi dovršeni turnir u eri 9696c4ee (prompt očišćen 26.09. 21:27, raspodjela pouzdanosti će se pomaknuti) | skupina 60-63 ispod nule uz n≥25 → prag natrag na 63 | DI K1 |
| **K17 — pick s "High" scouting profilom** | 30 takvih pickova od 27.09.2026 | ≤ −5pp → kazna −3pp; iznad nule → odbacuje se | DI K17; `measure_candidates.py` |
| **K18 — hard ATP 250 turniri** | 30 takvih pickova od 27.09.2026 (jesen je puna 250-ica) | ≤ −5pp → najviše jedna takva noga po tiketu; iznad nule → odbacuje se. Povijest 27.09.: tržište ondje nema rupu (+0,1pp) — ako postoji, to je naš izbor | DI K18 |
| **K19 — povratak nakon pauze od 21+ dan** | 40 mečeva od 27.09.2026 | isti smjer kao na tržištu → ±2pp; obrnuto → odbacuje se. Povijest 27.09.: −2,5pp, ali polovice različite (slab znak) | DI K19 |
| **K5, K8, K9, K10, K11** | sljedeći dovršeni turnir (Chengdu/Hangzhou, pa Tokyo/Beijing) | svaki ima svoj prag; **K11 (R16/QF) se od 26.09. prvi put mjeri na ručnim rundama**. Povijest 27.09.: tržište u 1,35–1,43 daje +3,7pp (vidi odluku 2 gore), u R16/QF nema rupe | DI K5-K11; `measure_candidates.py` |
| **Konsenzus kladionica** | do kraja listopada 2026: 60+ pickova uz razliku ≥1pp — **vjerojatno nedostižno**: Odds API ne pokriva ATP 250, od 13.09. bilo je 0 takvih mečeva | iznad +5pp → tvrdi uvjet; ispod nule → maknuti bonus. Povijest 27.09.: smjer točan, ali učinak ≈ veličina razlike (2–3pp), ne +10pp | `agent/ticket_builder.py`, blok uz `_CONSENSUS_GAP_MIN` |
| **K12 — prosjek statistike s turnira** | dubina 3+ uz kvotu dosegne n≥100 | interval i dalje prelazi nulu → samo bilježenje. **Povijest 27.09.: r=+0,004 na 970 mečeva dubine 3+ → po vlastitom pragu izlazi iz prompta (odluka 3 gore)** | DI K12 |
| **K14 — Davis Cup** | 20 riješenih Davis Cup mečeva (finalni turnir u studenom) | unutar 5pp od prosjeka → smije na tiket | DI K14 |
| **K2 — domaći teren** | još 20 mečeva s domaćim igračem (26.09.: 9, edge +0,7pp) | protivnik-domaći ostane iznad +3pp → kazna se briše iz prompta. **Povijest 27.09.: domaći igrači −1,4pp naspram cijene → podržava brisanje (odluka 3 gore)** | DI K2 |
| **K3 — Bo5, kvote 1,30-1,50** | Australian Open, siječanj 2027 | n≥50 i ispod -8pp. **Povijest 27.09.: +4,3pp, suprotan smjer — predlažem zatvoriti** | DI K3 |
| **Clay težine** | prije prve zemlje 2027. (siječanj 2027.) | aktivna v17 nastala je iz auto-feedbacka na analizama gubitaka (ELO spušten na 11%) — vratiti na v13 ili izjednačiti s hardom | Supabase `model_weights`; MODEL_CHANGELOG 26.09.2026 20:46 |

## ČEKA — ideje i popravci bez roka

- **Drugi izvor tržišnog konsenzusa za ATP 250.** The Odds API pokriva samo GS, Masters i
  nekoliko 500-ica; na ostalim turnirima jedini potvrđeni tržišni signal ne postoji. Treba
  odabrati izvor (i možda platiti) — korisnikova odluka. *Dopuna 27.09.2026 11:09:* jedan
  javni projekt (`gmalbert/tennis-predictions`) vuče kvote više kladionica za sve teniske
  mečeve iz nedokumentiranih Flashscore adresa, bez ključa. Besplatno, ali može puknuti bilo
  kad i vjerojatno krši uvjete stranice — samo kao opcija za tvoju odluku.

- **Vijesti po igraču.** ESPN i BBC od 13.09. nisu dali nijednu vijest o igračima koje
  analiziramo (0 od 43 analize) — pišu o vrhu tablice. Treba izvor koji traži po imenu
  igrača. Bez toga se K13 (vijesti o ozljedama) ne može izmjeriti.
  *Rješenje nađeno 27.09.2026 11:09:* Google News RSS pretraga po imenu (besplatno, bez
  ključa) — probano na Machaču, vratio je 50+ članaka, među njima i vijest o njegovoj ozljedi
  stopala s Roland-Garrosa. **NAPRAVLJENO 27.09.2026 12:00:** bilježi se uz svaku analizu
  (model ne vidi); K13 se mjeri kad bude 40 pickova protiv igrača s vijesti o ozljedi (DI K13).

- ~~**Povijesni laboratorij**, **radni tijek u Claude Codeu** (CLAUDE.md, `/oblikuj`,
  `/mjerenje`, `/kraj-sesije`, skeptik) i **pregled prompta** (izvještaj)~~ — **NAPRAVLJENO
  27.09.2026 12:00**, vidi dnevnik. Primjena pregleda prompta čeka tvoju odluku 3 na vrhu.
- **Winston-Salem: traženje turnira odustaje nakon 5 pokušaja** pri razrješavanju rezultata,
  pa dio analiza ostane nerazriješen. Prijedlog od 31.08.2026, čeka odobrenje.
- **Nesigurnost brojki u promptu** (npr. hold% je procjena ±8pp, a prikazuje se kao
  činjenica). Otvoreno od 08.08.2026; ide uz sljedeću veću izmjenu prompta (DI točka 4).
- **Model može samo spustiti pouzdanost, nikad promijeniti stranu picka.** Otvoreno od
  29.08.2026.
- **Drugi AI model kao neovisni analitičar** (mjeri se predviđa li slaganje dvaju modela
  bolje od jednoga). Niski prioritet.
- ~~**Čišćenje prompta: odjeljci analize**~~ — **NAPRAVLJENO 26.09.2026 21:27**, vidi dnevnik.
  Stari opis prijedloga:
  Iz prompta maknuti ono što je izmjereno kao krivo, a model to i dalje koristi: blok
  "povijest turnira je najjača varijabla" (pala dvaput izvan uzorka), hard pravila 4/13/16
  (tie-break i "izjednačen servis" — mjereno u krivom smjeru), blok o "kasnim rundama"
  (brojke s krivih oznaka rundi), blok koji potiče autsajdere (proturječi kazni za tržišnog
  autsajdera) i rečenice o "pragu 63%" (u kodu je 60 od 08.09.). Odjeljke 4 i 5 spojiti u
  jedan kratki "Kontekst", servis skratiti na opis. Ništa novo ne dodavati u prompt.
  **Najbolji trenutak: prije sljedećeg dnevnog runa** — era `bce5693b` još nema nijednu
  analizu, pa izmjena ne reže korpus. Posljedica: K1 (prag 60) i kazna za pojas 65-68
  moraju se ponovno izmjeriti nakon jednog turnira. Pravilo 11 (domaći teren) čeka K2.

## ČEKA — na tvoj znak (dogovoreno 27.09.2026 12:00, sada se NE radi)

- **Supabase MCP, samo za čitanje** (`read_only=true`, `project_ref` samo ovog projekta) —
  Claude bi u sesijama izravno čitao bazu umjesto da piše skripte. Treba tvoja jednokratna
  prijava u pregledniku.
- **Playwright MCP + `/run-skill-generator`** — Claude otvori Streamlit aplikaciju, klikne i
  napravi screenshot, da vidi rezultat izmjene na stranicama ("Claude je slijep"). Isplati se
  tek kad budemo mijenjali stranice.
- **rtk** (`winget install rtk-ai.rtk`) — skraćuje ispis naredbi (git, testovi) koji Claude
  čita. Mali dobitak; mjeri se s `rtk gain`, lako se makne.
- **Sonnet 5 umjesto Sonnet 4.6** — jeftiniji po tokenu ($2/$10 naspram $3/$15), ali broji ~30%
  više tokena i razmišljanje mu je uključeno po zadanom (treba veći `_ANALYSIS_MAX_TOKENS`).
  Sonnet 4.6 nije zastario; raditi samo na prijelomu ere, najbolje zajedno s odlukom 3.

## Redovito održavanje

- **Ruka novih igrača:** dnevni run nepoznate igrače dohvaća sam (najviše 150 po runu), ali
  ih ne sprema trajno. Povremeno pokrenuti
  `python scripts/backfill_player_context.py --collect --hands` i commitati `player_hands.json`.
- **Provjera K15:** `python scripts/measure_player_context.py` (čita iz baze; gledati samo
  analize od 27.09.2026 za potvrdu).

---

## NAPRAVLJENO — dnevnik

### 27.09.2026 12:00 — povijesni laboratorij, vijesti po igraču, radni tijek, Handy (tvoje odobrenje)

1. **Povijesni laboratorij.** Tvoje tablice (tennis-data 2022–2026) spojene su s TML-om
   (runde, statistika, povijest igrača) — 12.324 meča, spojeno 99,7%. Pragovi su zapisani prije
   računanja. **Glavno:** nijedan naš kandidat ne pobjeđuje tržište; naša "rupa" na 1,35–1,60
   nije tržišna (favoriti na 1,35–1,43 su čak bolji od cijene); naši pickovi su točni koliko i
   tržište, a po SuperSport kvoti prosječno gube maržu (EV −5,3% po picku, −3,1% po nozi tiketa).
   SuperSport nije lošiji od prosjeka kladionica (marža 5,2% naspram 6,25%).
   *Služi:* znamo što NE uvoditi (K3, K5, K15, K16) i što izbaciti iz prompta (domaći teren,
   statistika s turnira). Odluke su na vrhu, pod "TVOJE ODLUKE". **Ništa u modelu nije mijenjano.**
2. **Vijesti po igraču** s Google Newsa bilježe se uz svaku analizu od sljedećeg runa (naslovi
   iz zadnjih 14 dana, oznaka ozljede). Model ih ne vidi, era se ne mijenja; ako Google ne
   odgovori, run ide dalje. Za oko 20 mečeva run je dulji otprilike 50 sekundi.
3. **Pregled prompta** prema Claudeovim uputama — samo izvještaj s gotovim prijedlogom izmjene.
4. **Radni tijek u Claude Codeu:** `CLAUDE.md` (cilj projekta i pravila), naredbe `/oblikuj`,
   `/mjerenje`, `/kraj-sesije` i pomoćnik `skeptik`. **Pazi:** skeptik postaje dostupan tek u
   novoj sesiji (nova mapa se učitava pri pokretanju); ako se naredbe ne pojave, upiši
   `/reload-skills`.
5. **Handy** (diktiranje, v0.9.7) instaliran iz službenog izdanja, otisak datoteke provjeren.
6. **Usput nađeno:** u TML podacima za 2026. "datum turnira" je zapravo datum meča — popravljeno
   u učitavanju prije ijednog testa.

*Gdje:* izvještaji `revizije/2026-09-27/` (POVIJESNI_LAB, PRAGOVI, PROMPT_AUDIT, skripte
`lab_*.py`); vijesti `agent/player_news.py`, `agent/run_daily.py` (blok "VIJESTI PO IGRACU"),
`agent/predictor.py` (`context_version` 23); radni tijek `CLAUDE.md`, `.claude/skills/`,
`.claude/agents/skeptik.md`. Testovi: oba paketa prolaze, `test_cap_and_weather.py` odjeljak 49.

### 27.09.2026 11:09 — pregled besplatnih alata s tvog popisa (samo istraživanje)

Prošao sam sve linkove, skillove i repozitorije iz tvojih bilježaka (~70 stavki). U kodu i
modelu **ništa nije mijenjano** i ništa nije instalirano. Prijedlozi su gore u "ČEKA — ideje"
(povijesni laboratorij, vijesti po igraču, radni tijek u Claude Codeu, pregled prompta,
Sonnet 5).

Usput izmjereno u bazi (samo čitanje): od 28.08. **nijedna analiza nije pala** na JSON-u
(21 od 171 spašena drugim pokušajem), a keširanje prompta radi (41 od 51 analize od 08.09.).
Zato alati za "sigurni JSON" (Instructor, Outlines) ne trebaju. Analiza je malo (51 u 19
dana), pa API trošak pipelinea iznosi nekoliko dolara mjesečno — alati za štednju tokena
mogu uštedjeti samo na sesijama u Claude Codeu.

Važno iz bilježaka koje ne stoji: Sackmannovi `tennis_atp`/`tennis_wta` su obrisani s GitHuba;
`/voice` ne podržava hrvatski (za diktiranje: besplatni Handy); `/goal` služi za jednu sesiju,
nije cilj projekta; hook ne može prepisati tvoj prompt, samo dodati kontekst.

### 26.09.2026 21:27 — očišćen prompt analize (tvoje odobrenje)

Iz uputa modelu maknuto sve što je izmjereno kao krivo, a model je to i dalje koristio za
svoj broj: "povijest turnira je najjača varijabla", tri pravila o tie-breaku i servisu
(4, 13, 16), blok o kasnim rundama, blok koji je poticao autsajdere i sve rečenice o
"pragu 63%" (u kodu je 60). Analiza sada ima **pet odjeljaka** umjesto šest: Rating,
Serve/return, Forma, **Kontekst** (spojeni matchup i povijest turnira) i Own read.
Ništa novo nije dodano. Težine i pravilo o domaćem terenu nisu dirani.

**Čemu služi:** tekst koji čitaš uz pick više ne tvrdi netočnosti i dosljedan je broju;
manje razloga za odmak iznad tržišta; prompt kraći za četvrtinu. **Ne očekuj** da nas
ovo samo po sebi učini boljima od tržišta. **Pazi:** brojevi pouzdanosti će se malo
pomaknuti, pa prag 60 i kaznu 65-68 treba premjeriti nakon prvog turnira (stavka K1 gore).
Provjereno: oba testna paketa prolaze, jedan živi poziv modela vratio je pet odjeljaka.

Gdje: `agent/predictor.py` (komentar "CISCENJE PROMPTA" iznad predloška); nova era
`9696c4ee`.

### 26.09.2026 21:18 — tri pitanja (samo mjerenje, ništa u modelu nije mijenjano)

1. **Azijski mečevi na screenshotu: "danas" ili "sutra"?** Stavljaj točno kako grupira
   SuperSport. Kod sam pomakne datum po kratici dana uz sat ("ned 07:00" u subotnjoj listi =
   nedjelja 07:00). Provjereno na današnjoj rubrici: 10 od 10 kratica pročitano, a 4 nedjeljna
   meča spremljena pod subotu dobila su ispravan datum 27.09. i prognozu za taj dan.
   Uvjet: kratica dana mora se vidjeti na slici. Ako pokrećeš tiket u 17h, samo jednom na
   dan — drugi run istog dana stvara drugi tiket s istim datumom, a Dnevni listić prikaže
   samo jedan.
2. **Odjeljci analize (rating, servis, forma, matchup, povijest turnira, own read).**
   Pročitano svih 55 analiza od 06.09. do danas. Odjeljci nisu šest neovisnih varijabli:
   model u njima provodi pravila i zbraja kazne. 80% teksta ide na stvari koje ništa ne
   nose povrh cijene. Pravilo 16 poziva se u 65% analiza, povijest turnira kao argument u
   58%, a u 5 analiza s izrekom "najjača varijabla". U 18 analiza model je napisao da pick ne
   ide na tiket (misli da je prag 63%), a 12 ih je prošlo stvarni prag 60 — od 9 nogu na tri
   prava tiketa, 5 je model sam nazvao "coin-flip" ili "ispod praga". Prijedlog čišćenja je
   gore u "ČEKA — ideje".
   Međustanja kandidata: K8 drži smjer i izvan uzorka (odjeljak "povijest turnira" s
   podatkom −8,0pp, bez podatka −1,9pp, n=27); K9 je okrenuo predznak (vjerojatno pada);
   K2: protivnik-domaćin n=9, +0,7pp (prag je n=20).
3. **Težine hard modela (servis 23%, ELO 19%...).** Ostaju. To je samo popis na dnu prompta;
   model ih ni u jednoj od 55 analiza ne koristi u računu, a nijedna statistika igrača ne nosi
   ništa povrh cijene. Pravi pomaci su u kodu i čekaju kapiju (K11, K5/K10, K18, K15).

Gdje: skripte i izvoz baze samo lokalno u `.cache/pitanja2609/` (izvan gita).

### 26.09.2026 navečer — velika revizija + popravci (commit uz ovaj zapis)

1. **Revizija svega** (izvještaj `revizije/2026-09-26/REVIZIJA_2026-09-26.md`, prilog s
   klasifikacijom svakog gubitka i dobitka). Glavno: naši pickovi su jednaki tržištu; tiketi
   gube na marži. Dvije trećine gubitaka su tijesni mečevi ili mečevi u kojima je i tržište
   vjerovalo našem igraču — to nije greška modela.
2. **Kazna za tržišnog autsajdera sada radi i na ATP 250.** Do danas je tiho bila isključena
   na svim turnirima koje The Odds API ne pokriva (od 13.09. na svima). Sada koristi cijenu
   sa screenshota. *Služi:* tiket više ne može slučajno uzeti igrača kojeg kladionica drži
   slabijim (Shimabukuro @2,00 i Sonego @2,10 bili su baš to).
3. **Analize gubitaka više ne izmišljaju činjenice.** Dobivaju stvarnu kvotu, pojas kvote,
   rundu, je li meč bio na pravom tiketu i je li netko predao. 15 od 20 rujanskih analiza bilo
   je netočno upravo u tome. Sve analize gubitaka od 29.08. napisane su ponovno (stare su
   sačuvane u `revizije/2026-09-26/stare_analize_gubitaka.json`).
4. **Hitni popravak: noge tiketa su se gubile.** API je jutros počeo slati puni datum-sat u
   polje za vrijeme, koje prima najviše 20 znakova, pa jutrošnji tiket (Hurkacz, Vacherot,
   Marozsan) nije imao nijednu nogu i ne bi se nikad razriješio. Popravljeno i vraćeno.
   Ako se upis ikad opet pokvari, log to sada viče.
5. **Scouting:** iz modela je maknut tekst "voli igrati protiv / muči se protiv" (izmjereno da
   ne predviđa ništa), ispravljena 4 profila koja su proturječila brojkama (Nakashima, Norrie,
   Giron, Wong). U Excelu je sve ostalo.
6. **Ispravci podataka:** jedan krivo upisan ishod (Båstad 17.07.), asovi i visina u zapisu.
7. **Na Dnevnom listiću, samo za tebe:** uz svaki pick "naš edge na ovoj kvoti" i "naš dosje
   s ovim igračem". Model to ne vidi.
8. **Nova skripta `scripts/measure_candidates.py`** — sve zakazane provjere jednom naredbom.
9. **Izmjereno i odbačeno:** tablica promašaja po igraču, "s kim je gubio na turniru",
   slični povijesni slučajevi (četvrti put), sekvenca protivnika, vrijeme, kretanje kvota,
   276 kombinacija varijabli. Obrnuti Fery veto (4e) zatvoren.

*Gdje u kodu:* autsajder — `agent/predictor.py` (`_apply_measured_penalties`); analiza gubitka —
`agent/feedback_analyzer.py` (`_loss_match_facts`, `_LOSS_BASE_RATES`); noge tiketa —
`agent/ticket_builder.py` (`_leg_time`), `database/supabase_client.py` (`save_ticket_matches`);
pojas i dosje — `utils/helpers.py`; prikaz — `pages/1_Dnevni_Listic.py`; glasni ispis —
`agent/run_daily.py`. Testovi: `test_cap_and_weather.py`, odjeljak 48.

### 26.09.2026 (commit `eb366ce`)

1. **Rundu upisuje korisnik.** Program je rundu pogađao iz podataka i često griješio
   (Chengdu i Hangzhou su prvi dan dobili 12 "polufinala"). Sada se na stranici Kvote sa
   Screenshota runda bira pri uploadu: jednim izbornikom za sve parove, a pojedini par se
   može ispraviti (i naknadno, za već spremljene parove). Bez runde se kvote ne spremaju. Sav
   stari kod za pogađanje runde je obrisan, a 31 stari redak s krivom rundom je očišćen.
   *Služi:* model zna pravu fazu turnira; statistike po rundama su točne.
2. **Grand Slam finala više ne ispadaju.** Model je od 26.07. vidio finala bez Grand Slama,
   ATP Finalsa i Olimpijskih igara (Zverev: 36 umjesto 45). Sada vidi sva, a GS posebno.
3. **Tri nove informacije o svakom igraču se zapisuju:** omjer protiv ljevaka i dešnjaka
   (zadnje 2 godine), ATP pobjede u sezoni, broj GS polufinala i finala. Upisane su i unatrag,
   za svih 664 dotadašnjih analiza, kakve su bile na dan meča.
   *Služi:* možemo mjeriti pomažu li, umjesto nagađati.
4. **Odmah izmjereno** (451 meč, naspram kvote):
   - ljevaci: priča o Zverevu je točna (21-1), ali kladionice to već imaju u kvoti, pa ne
     daje prednost;
   - GS iskustvo: općenito već u kvoti; u završnicama obećava, ali premalo mečeva (K16);
   - ATP pobjede u sezoni: jedini mali plus iznad kvote (K15). **Odluka: čeka potvrdu**, ne
     ulazi u odluku prije toga.
5. **Vijesti:** utvrđeno da zadnja dva tjedna nije stigla nijedna vijest o našim igračima
   (vidi "ideje" gore).
6. **Točno lokalno vrijeme mečeva.** Sat se računa po pravoj vremenskoj zoni za svaki grad i
   datum (ljetno/zimsko vrijeme, Kazahstan, Adelaide). Bruxelles, Lyon, Stockholm, Torino,
   Monte-Carlo i Rio prije nisu imali lokalni sat uopće.
   *Služi:* ispravna oznaka dan/noć i prognoza za pravi sat meča, od listopada nadalje.
7. **Program je brži.** Podaci o igračima skupljaju se istovremeno, ne jedan po jedan:
   skupljanje podataka u probnom runu palo je s ~5 na ~2 minute.
8. **Neuspjeh više nije "prazno".** Kad API poziv ne uspije, to se bilježi kao greška, a ne
   kao "igrač nema mečeva" ili "nikad nije igrao Slam".

*Gdje u kodu:* runda — `utils/helpers.py` (`ROUND_CHOICES`), `pages/5_Kvote_Screenshot.py`,
`agent/run_daily.py` (`_apply_manual_rounds`), `agent/predictor.py` (`_round_context`);
finala — `agent/data_fetcher.py` (`get_player_titles`), `agent/predictor.py`
(`_format_titles`); tri varijable — `agent/player_context.py`,
`scripts/backfill_player_context.py`, `scripts/measure_player_context.py`, `player_hands.json`;
vremenske zone — `agent/data_fetcher.py` (`_CITY_TZ`, `local_match_time`); brzina —
`agent/run_daily.py` (`_prefetch_players`), `agent/data_fetcher.py` (`_wait_turn`, keševi).
Testovi: `test_cap_and_weather.py`, odjeljci 44-47.

### Ranije (samo glavne prekretnice; sve je u `MODEL_CHANGELOG.md`)

- **19.09.2026** — Davis Cup postao zasebna razina (analizira se, ne ide na tiket); popravljen
  pad koji je rušio jutarnji run.
- **13.09.2026** — popravljeni pokvareni ulazi (runde, visina/građa igrača, vijesti);
  prosjek statistike s turnira i vijesti ulaze u odluku; kretanje kvota izmjereno i odbačeno.
- **08.09.2026** — revizija na kraju US Opena: tiket 3-6 parova i ukupna kvota 4-50, prag
  pouzdanosti 60, konsenzus kladionica kao bonus, jeftiniji pozivi modelu (prompt caching).
- **06.09.2026** — uvedena kapija: nalaz ulazi u kod tek nakon potvrde na novim mečevima.
- **30.08.2026** — ukinut Fery veto (mjerenje je pokazalo da reže naše najbolje pickove).
