# Backlog i dnevnik rada

Čitljiv pregled projekta: **što čeka** (s uvjetom kada se radi) i **što smo napravili** (po
danima, jednostavnim jezikom). Brojke, obrazloženja i tehnički detalji su u
`MODEL_CHANGELOG.md`; popis svega što ulazi u odluku o picku je u `DECISION_INPUTS.md`
(dalje: DI).

**Pravilo:** na kraju svake radne sesije ovdje se dopiše što smo napravili i ažurira se
popis otvorenog. Otvoreno 26.09.2026 19:21, zadnje ažurirano 27.09.2026 19:29.

**Jedna naredba za sve zakazane provjere kandidata:** `python scripts/measure_candidates.py`
(čita bazu, ništa ne mijenja; kaže za svakog kandidata ČEKA / POTVRĐEN / PAO).

---

## ČEKA — zakazane provjere

Pravilo projekta (kapija, od 06.09.2026): nijedan nalaz ne ulazi u odluku dok se ne potvrdi
na mečevima na kojima nije pronađen. Svaka stavka ima prag zapisan UNAPRIJED.

| što | kada / uvjet | ishod | gdje |
|---|---|---|---|
| **Omjer protiv ljevaka** | 300 mečeva s ljevakom (danas 120) | ponovno izmjeriti; do tada samo bilježenje | DI "IZMJERENO 26.09.2026" |
| **K1 — prag 60 + kazna 65-68** | prvi dovršeni turnir u eri **bccf4742** (prompt promijenjen 27.09. 12:13, raspodjela pouzdanosti će se pomaknuti) | skupina 60-63 ispod nule uz n≥25 → prag natrag na 63 | DI K1 |
| **K17 — pick s "High" scouting profilom** | 30 takvih pickova od 27.09.2026 | ≤ −5pp → kazna −3pp; iznad nule → odbacuje se | DI K17; `measure_candidates.py` |
| **K18 — hard ATP 250 turniri** | 30 takvih pickova od 27.09.2026 (jesen je puna 250-ica) | ≤ −5pp → najviše jedna takva noga po tiketu; iznad nule → odbacuje se. Povijest 27.09.: tržište ondje nema rupu (+0,1pp) — ako postoji, to je naš izbor | DI K18 |
| **K19 — povratak nakon pauze od 21+ dan** | 40 mečeva od 27.09.2026 | isti smjer kao na tržištu → ±2pp; obrnuto → odbacuje se. Povijest 27.09.: −2,5pp, ali polovice različite (slab znak) | DI K19 |
| **K5, K8, K9, K10, K11** | sljedeći dovršeni turnir (Chengdu/Hangzhou, pa Tokyo/Beijing) | svaki ima svoj prag; **K11 (R16/QF) se od 26.09. prvi put mjeri na ručnim rundama**. **K5 od 27.09. traži n ≥ 100** (tržište u 1,35–1,43 daje +3,7pp); u R16/QF tržište nema rupe | DI K5-K11; `measure_candidates.py` |
| **Konsenzus kladionica** | do kraja listopada 2026: 60+ pickova uz razliku ≥1pp — **vjerojatno nedostižno**: Odds API ne pokriva ATP 250, od 13.09. bilo je 0 takvih mečeva | iznad +5pp → tvrdi uvjet; ispod nule → maknuti bonus. Povijest 27.09.: smjer točan, ali učinak ≈ veličina razlike (2–3pp), ne +10pp | `agent/ticket_builder.py`, blok uz `_CONSENSUS_GAP_MIN` |
| **Odds API → besplatni plan** (tvoja odluka 27.09.2026 19:29) | u listopadu otkazuješ plaćeni plan prije naplate (kupljen 15.08., naplata vjerojatno ~15.10.); plaćeni vrijedi do kraja razdoblja | prva sesija nakon prelaska: besplatnim pozivom `/sports` (0 kredita) provjeriti radi li ključ i piše li limit 500 (`x-requests-remaining`); ako je ključ nov → GitHub Secrets `ODDS_API_KEY` i `.env`. Uz tvoj OK smanjiti večernje snimanje kvota s 3 na 1 dnevno (dan turnira sada troši ~14 kredita, najgori mjesec ~430 od 500; uz 1 snimanje ~240). RapidAPI ostaje Pro | `.github/workflows/market_close.yml`, `agent/market.py` |
| **K20 — Intuicija (naučeni signal u sjeni)** | **dvije provjere:** 150 riješenih procjena (≈ sredina studenog) pa 300 (≈ siječanj), poslije svakih +300. **Mail sa stanjem stiže sam 15.11.2026 i 15.01.2027** | uz 150 treba r ≥ 0,16, uz 300 r ≥ 0,12 (interval iznad nule) i gornja trećina ≥ +3pp → prijedlog bonusa pri izboru tiketa (i za autsajdere); inače uči dalje u sjeni | DI K20; `python scripts/intuicija_report.py` |
| **K14 — Davis Cup** | 20 riješenih Davis Cup mečeva (finalni turnir u studenom) | unutar 5pp od prosjeka → smije na tiket | DI K14 |
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
  27.09.2026 12:00**, vidi dnevnik. Pregled prompta primijenjen 27.09.2026 12:17 (era bccf4742).
- **Winston-Salem: traženje turnira odustaje nakon 5 pokušaja** pri razrješavanju rezultata,
  pa dio analiza ostane nerazriješen. Prijedlog od 31.08.2026, čeka odobrenje.
- **Nesigurnost brojki u promptu** (npr. hold% je procjena ±8pp, a prikazuje se kao
  činjenica). Otvoreno od 08.08.2026; ide uz sljedeću veću izmjenu prompta (DI točka 4).
  *27.09.2026 12:17:* namjerno NIJE ušlo u eru bccf4742 — to bi bio novi tekst u promptu, a ta era je
  samo micala izmjereno krivo. Hold% je u promptu već označen kao procjena i "nije drugi signal".
- **Model može samo spustiti pouzdanost, nikad promijeniti stranu picka.** Otvoreno od
  29.08.2026.
- ~~**"Intuicija" — naučeni signal**~~ — **NAPRAVLJENO 27.09.2026 12:34** (u sjeni), vidi dnevnik i K20 gore.
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
- ~~**Provjera K15**~~ — K15 zatvoren 27.09.2026 (povijesno +0,0pp).
- **Intuicija:** stanje u sjeni `python scripts/intuicija_report.py`. Kad osvježiš
  `.cache/tennis-data/2026.xlsx`, ponovno nauči prior: `lab_data.py` → `lab_features.py` (u
  `revizije/2026-09-27/skripte/`) → `python scripts/intuicija_prior.py`, pa commit.

---

## NAPRAVLJENO — dnevnik

### 27.09.2026 19:29 — Pretplate: Odds API ide na besplatni plan, RapidAPI ostaje Pro

Izmjerili smo koliko stvarno trošimo na dva plaćena izvora podataka (tvoje pitanje može li
se pretplata spustiti):

- **RapidAPI (Pro, 29 $):** od 07.09. potrošeno 12.752 od 75.000 poziva, oko 625 dnevno
  (~19.000 mjesečno, 25%). Besplatni plan daje 50 poziva dnevno, a samo jutarnji run troši
  stotine — zato ostaje Pro. Na slici plana piše 150.000, ali API nama javlja 75.000.
- **The Odds API (20K, 30 $):** u rujnu 187 od 20.000 kredita (1%), u tome 13 dana US Opena.
  Tenis pokriva samo 22 ATP turnira (Grand Slamovi, Mastersi, dio 500-ica), od 13.09.
  nijedan. Besplatni plan (500 kredita) ima oštre kladionice (Pinnacle, Betfair, Matchbook,
  Smarkets); otpadaju povijesne kvote (ne koristimo ih) i 2 američke kuće od ~44 po meču.

**Odluka:** u listopadu prelaziš na besplatni Odds API; RapidAPI ostaje kako jest. Ušteda
~360 $ godišnje. U kodu ništa nije mijenjano.

**Pazi:** dan pokrivenog turnira troši ~14 kredita, od toga 9 tri večernja snimanja kvota
(samo mjerni alat). Najgori mjesec (npr. travanj) procijenjen je na ~430 od 500 — tijesno.
Ako krediti nestanu, ništa ne puca: jutarnji run samo preskoči konsenzus do kraja mjeseca.
Što napraviti nakon prelaska piše u "ČEKA".

Gdje u kodu: `agent/market.py` (konsenzus), `scripts/capture_market_close.py` i
`.github/workflows/market_close.yml` (tri snimanja dnevno), `agent/data_fetcher.py` (RapidAPI).

### 27.09.2026 12:49 — Intuicija: dvije provjere (150 pa 300) i mail u dva zakazana dana

Po tvojoj odluci Intuicija se provjerava **dva puta**: prvi put kad skupi **150** riješenih
procjena (otprilike sredinom studenog), drugi put na **300** (siječanj). Nakon svake provjere
nastavlja učiti. Uz manji uzorak provjera traži jači dokaz, pa rizik da prođe bezvrijedna
intuicija ostaje mali (oko 3–4% preko obje provjere).

**Javljanje:** bez dnevnog maila. GitHub će se sam upaliti **15.11.2026 i 15.01.2027** i poslati
ti jedan mail sa stanjem; ja ću ti to reći i u prvoj sesiji nakon tih datuma (zapisano u memoriju).
Mail se može poslati i ručno: GitHub → Actions → "Intuicija - provjera kapije K20" → Run, uz
kvačicu "force".

*Gdje:* `agent/intuicija.py` (`gate_status`, jedno mjesto za pravilo), `scripts/intuicija_status_email.py`,
`.github/workflows/intuicija_status.yml`, K20 u `scripts/measure_candidates.py` i DI.

### 27.09.2026 12:34 — "Intuicija": naučeni signal koji prati svaki meč (u sjeni)

Napravljen je poseban statistički model — tvoja "intuicijska varijabla". Za **obje strane
svakog meča** procjenjuje koliko igrač prolazi bolje ili lošije od svoje kvote, i diže
zastavicu kad bi uzeo **autsajdera kojeg Claude nije odabrao**.

- **Kako uči:** polazi od kvote i uči samo odstupanja. Temelj su obrasci s 12.322 povijesna
  meča (npr. Grand Slam favoriti 1,30–1,50 +3,2pp, igrač nakon pauze 21+ dana −2,3pp). Na to
  dodaje ono što vidi na našim analizama, i **uči iznova svako jutro** na svemu dotad riješenom,
  dakle raste s podacima.
- **Kad šuti:** ako na mečevima koje nije vidio ne bi bio bolji od kvote, kaže 0 umjesto da
  izmišlja.
- **Iskreno stanje danas:** naučio je ono što znamo (npr. "High" scouting profil −2,9pp), ali
  provjera "kako bi prošao da je postojao" još ne pokazuje vještinu (r = +0,01). Zato je **u
  sjeni**: zapisuje procjenu, a tiket je ne vidi. Kad skupi 300 riješenih procjena, provjera
  (K20) kaže smije li dobiti riječ pri slaganju tiketa, uključujući autsajdere.

*Gdje:* `agent/intuicija.py`, `config/intuicija_prior.json`, `scripts/intuicija_prior.py`,
`scripts/intuicija_report.py`, blok "INTUICIJA U SJENI" u `agent/run_daily.py`, K20 u
`scripts/measure_candidates.py` i DI. Testovi: odjeljak 50 (14 provjera), oba paketa prolaze.

### 27.09.2026 12:17 — tvoje odluke provedene: nova era prompta, K15/K16/K3 zatvoreni, K5 strože

**Tvoja odluka:** tiket ostaje **3–6 parova i ukupna kvota 4–50** (provjereno u kodu da je tako;
nije dirano). Prijedlog o manje nogu je time odbačen i neće se ponovno predlagati.

1. **Pravilo o domaćem terenu je van.** Model više ne oduzima 3 boda kad je protivnik domaći —
   na 2.775 mečeva domaći igrači nisu bili bolji od cijene. Ista provjera maknuta je i iz
   AI-recenzenta tiketa, da ne živi dalje na drugom mjestu.
2. **Statistika s ovog turnira** i dalje se prikazuje, ali model je smije koristiti samo za opis,
   ne za pomicanje pouzdanosti (na 970 mečeva nije dodala ništa cijeni).
3. **Tekst prompta je očišćen** od datuma i vikanja ("THE SINGLE MOST IMPORTANT", "CRITICAL");
   sadržaj ostalih pravila nije diran. Prompt je kraći za četvrtinu stranice.
4. **Zatvoreno:** K15 (pobjede u sezoni), K16 (GS iskustvo), K3 (Bo5 1,30–1,50). **K5** (oprezna
   zona od 1,35) sada traži 100 mečeva umjesto 20 prije ikakve odluke.

**Čemu služi:** model manje griješi na stvarima koje su izmjerene kao krive, a tiket ne kažnjava
dobre pickove. **Ne očekuj** skok ROI-ja samo od ovoga. **Pazi:** nova era (hard `bccf4742`), pa se
K1 (prag 60) premjerava nakon prvog dovršenog turnira. Provjereno: oba testna paketa prolaze,
jedan živi poziv modela vratio je ispravan odgovor s pet odjeljaka (1.026 tokena, strop 4.000).

*Gdje:* `agent/predictor.py` (komentar "IZMJENA PROMPTA (27.09.2026 12:13"), `agent/ticket_builder.py`
(`_review_ticket`), `scripts/measure_candidates.py` (K5), DI (K1, K2, K3, K5, K12, K15, K16).

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
