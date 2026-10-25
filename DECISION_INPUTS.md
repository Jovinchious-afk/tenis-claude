# Što ulazi u odluku o picku — referentni popis

**Stanje na dan 13.08.2026 12:47.** Popisano na korisnikov zahtjev jer se dosad nigdje nije
vidjelo na jednom mjestu — ulazi su razasuti po promptu (`agent/predictor.py`),
determinističkom kodu (`agent/ticket_builder.py`) i zapisu (`context_snapshot`).

Ovo je **referenca, ne changelog.** Kad se nešto od navedenog promijeni, ažurirati ovdje i
zabilježiti izmjenu u `MODEL_CHANGELOG.md`.

---

## 1. Ulazi u ODLUKU — analiza (prompt, ~13.800 tokena, od 08.09.2026 u DVA dijela)

**Od 27.09.2026 12:16 (era bccf4742):** fiksni dio 8.207 tokena (izmjereno živim pozivom). Pravilo o domaćem terenu svedeno je na "već je u cijeni", a statistika s ovog turnira služi samo za opis (K2, K12).

**Od 08.09.2026 12:07 prompt je podijeljen** radi kesiranja (`rules_hash` `61999517`):
`_ANALYSIS_SYSTEM_TEMPLATE` nosi fiksne upute i pravila podloge (~10.974 tokena, šalje se
kao `system` s `cache_control: ephemeral`), a `ANALYSIS_PROMPT_TEMPLATE` samo podatke o
meču (~2.805 tokena, 97 placeholdera). Sadržaj je isti kao prije uz pet namjeravanih
izmjena; upute sada dolaze PRIJE podataka. `ranking_trend` je uklonjen — nikad nije imao
vrijednost. Detalji: MODEL_CHANGELOG 08.09.2026 12:07 (druga izmjena).

Model za oba igrača dobiva sve navedeno, uz izričito navedene težine po kategoriji.
Težine su hard v18; žive u Supabase `model_weights`, ne u kodu.

| težina | što model vidi |
|---|---|
| **Servis + povrat 23%** | poeni na servisu, hold % *(procjena)*, % prvog servisa, poeni na 1. i 2. servisu, asovi, **break lopte spašene/iskorištene** *(od 08.08.2026 11:35)*, povrat, tie-break zapis, odlučujući set |
| **ELO + rang 19%** | ATP rang + trend, ELO ukupni, ELO po podlozi, prosječni ELO zadnjih 10 protivnika |
| **Podloga + stil 18%** | omjer na podlozi (3 g.), forma na podlozi (6 mj.), ruka, brzina terena, nadmorska visina, dvorana/otvoreno |
| **Forma 17%** | zadnjih 5 i 10 mečeva, trend forme, put kroz aktualni turnir |
| **Umor + ozljede 12%** | mečevi i setovi u 7 dana, dani odmora, dob, vijesti o ozljedama |
| **Trajektorija 7%** | karijerni omjer na tom turniru, odigrana finala i naslovi *(od 26.09.2026 ukljucuju i Grand Slam, ATP Finals i OI finala, koja su do tada tiho ispadala; GS finala navedena zasebno)* |
| **H2H 4%** | ukupno, na podlozi, zadnji susret, trend zadnja 3, pouzdanost uzorka |

**Izvan težina, ali utječe na pick:**

- **Runda i kontekst runde** — rane runde dopuštaju iznenađenja, završnice favoriziraju dokazane.
  **Od 26.09.2026 17:04 rundu RUČNO upisuje korisnik** uz svaki par na stranici "Kvote sa
  Screenshota" (izbornik za sve parove + ispravak po paru). Kod je više ne pogađa ni na koji
  način; par bez upisane runde ide u analizu s porukom "Round NOT ENTERED". Opis runde u
  promptu ide po broju preostalih igrača, ne po rednom broju kola (stari opis je prvo kolo
  ATP 250 zvao "Third round").
- **Vremenski uvjeti** — smiju **samo SPUŠTATI** pouzdanost, nikad je dizati (asimetrija namjerna)
- **Lokalno vrijeme početka i sesija** (dan/noć) — za razliku od uvjeta, sesija po pravilu 14
  smije djelovati **u oba smjera**. *Od 26.09.2026 pomak se računa po pravoj vremenskoj zoni
  za trenutak meča (ljetno/zimsko, Kazahstan +5, Adelaide +10,5); Bruxelles, Lyon,
  Stockholm, Torino, Monte-Carlo i Rio prije nisu dobivali lokalni sat uopće.*
- **Oboje otpada kad raspored za sutra nije objavljen** *(novo 14.08.2026 11:02)*. Kad 4+
  mečeva jednog turnira dijeli najraniji termin **sutrašnje** liste, kladionica je cijeli dan
  nabila na jedan placeholder sat: prognoza se tada ne dohvaća uopće, a `local_time`/`session`
  ostaju prazni umjesto približni. Rubrici „danas" se vjeruje uvijek. Meč i dalje ide u analizu
  i smije na tiket. Zapis: `context_snapshot.schedule_provisional` (v11)
- **Povijest ždrijeba turnira** — anti-halucinacijska provjera tvrdnji o prošlim rezultatima
- **Scouting profili** (`player_scouting`, 150 igrača iz korisnikova Excela) — SEKUNDARNI
  izvor koji nikad ne nadjačava mjerene brojke. Dopušteni utjecaj skalira s pouzdanošću
  profila: High/Med-High ±3pp, Med ±2pp, **Med-Low samo kao sumnja** (nikad kao potpora
  picku), Low i Insufficient se uopće ne prikazuju. **Od 26.09.2026 20:46 bez polja
  "favours / struggles against"** — izmjereno na 101 tvrdnji (1.783 meča s kvotom) da ne nose
  ništa povrh cijene; ostaju u Excelu i Supabaseu samo za čitanje. Era `bce5693b`.
- **Asovi** se u promptu zovu "Aces per 100 serve pts" (od 26.09.2026; prije "Aces/match" za
  istu brojku — vrijednost je oduvijek bila asovi na 100 servisnih poena)
- **`odds_alert`** — upozorenje na moguću ozljedu/povlačenje pri omjeru kvota ≥6:1
- **`market_check`** *(novo 13.08.2026 12:47)* — tržišna cijena kao **PROVJERA, ne ulaz**.
  Model svoj broj i dalje formira bez nje; tek nakon toga uspoređuje i, ako se razilazi za
  više od 10pp, mora imenovati mjerenu činjenicu koja to opravdava. Povod: pickovi >10pp
  IZNAD tržišta išli su 2W-6L (ROI −52,5%). **Kvota i dalje NE ulazi u procjenu
  vjerojatnosti** — to je korisnikovo stalno pravilo.
- **24 pravila**: 16 hard-specifičnih + 8 univerzalnih

## 2. Ulazi u ODLUKU — deterministički kod, nakon analize

**Izbacuje pick** (`_selection_ok` + conf floor):

- pouzdanost < **63%** *(04.10.2026 19:22 VRAĆENO na 63, korisnikova odluka — K1 okidač: Peking+Tokio 60-63 −17,9pp n=26, ≥63 +12,2pp n=17; od 08.09.2026 12:07 do 04.10. prag je bio 60)* — iznimka je value-override: conf ≥58 uz edge ≥12pp, najviše 2 po tiketu
- **ELO nemoguć za rang** (04.10.2026 19:13): rang ≤ 100 a ukupni ELO < 1.550 → meč se preskače kao da ELO-a nema (`data_fetcher.elo_implausible`, `run_daily`). Rang od 04.10. dolazi s ATP singl liste (`run_daily._rank_of`), profil je rezerva.
- nije glavni tour, ili nema kvotu
- **oba igrača 0/3** u zadnja 3 meča
- Grand Slam traži **65%** (hard i clay)
- grass mrtva zona 1,43-1,60 (na travi nikad na tiket)
- najviše **6 kandidata po turniru po danu**
- **NIJE na screenshotu** — od 11.08.2026 18:44 meč prolazi samo ako je njegov par na
  screenshotu (danas ∪ sutra), bez obzira na datum koji mu API dodijeli; bez ijednog
  screenshota run staje odmah. Vidi `_gate_by_screenshot`.
- ~~runde na razini TURNIRA~~ i ~~R128 izvan Grand Slama~~ — **OBRISANO 26.09.2026 17:04**.
  Obje provjere su pogađale rundu (prva brojanjem oznaka kroz turnir, druga je iz oznake
  "R128"/"Q1"/"Q2" zaključivala da je meč kvalifikacija). Runda je od tada ručni unos, a
  kvalifikacije drži vani screenshot-gate (korisnik ih nikad ne screenshota) i razina
  turnira. Povijest: MODEL_CHANGELOG 13.08., 08.09., 13.09. i 26.09.2026.

**Ograničava listić:**

- **3-6 parova**, ukupna kvota **4-50** *(korisnikova odluka 08.09.2026 12:07; prije 4-6 / 6-40)*. Mjereno kroz stvarni `_find_best_combination` na 36 dana: staro −100,0% (9 dana), novo −34,6% (20 dana, od toga 14 trojaca), jedan par −6,9%. Novi raspon je bitno bolji i bodovanje doista bira manje nogu, ali **nijedna struktura tiketa nije pozitivna** — jedina pozitivna skupina je tržišni konsenzus (niže).
- **strop pouzdanosti 70%** *(podignut s 64 dana 17.08.2026 11:46)* — iznad 70 model mora
  ispuniti `above_64_basis` (ime polja je povijesno) s dvije mjerene potvrde s brojkama iz
  različitih kategorija i rečenicom što bi ga oborilo; inače kod spušta na 70 i bilježi
  `ceiling_enforced`. **Zašto je podignut:** strop 64 nikad nije stisnuo nijedan broj
  (`ceiling_enforced` 0/59) — model se sam cenzurirao, pa je 61% analiza sjelo na točno 64 i
  pouzdanost je prestala nositi informaciju (Brier 0,2308 naspram 0,2305 za konstantu 0,64).
- najviše **1 pick iz zone 1,43-1,60** *(suženo s 1,43-1,90 dana 08.08.2026 11:35)*

**Mjerene kazne — oduzimaju od pouzdanosti** *(novo 17.08.2026 11:46,
`_apply_measured_penalties`)*. Oduzimanje, a ne capiranje, jer cap stvara hrpu na jednoj
vrijednosti i time ubija razlučivanje — to je glavna lekcija revizije od 17.08.:

- scouting profil **NAŠEG picka = `Med-Low`** → **−4pp** (26,7% n=15 naspram 65,8% n=114,
  P=0,0035; Low/Insufficient prolaze bolje jer su izbačeni iz prompta pa se na njih ne oslanja)
- **naš pick je tržišni autsajder** (de-vig konsenzus 40+ kladionica ≤50%) → **−5pp**
  (25,0% n=12 naspram 70,0% n=100, razlika 45pp, P=0,002). **Nije pravilo protiv velikih
  kvota:** kažnjava se neslaganje s cijelim tržištem, ne veličina kvote — pick s kvotom 2,40
  kojemu tržište daje 55% nije pogođen.
  **POPRAVAK 26.09.2026 20:46:** kad konsenzusa NEMA (Odds API ne pokriva ATP 250 — od 13.09.
  to je bilo 100% mečeva), kazna koristi **devigiranu screenshot cijenu** (strogo < 50%; jednake
  kvote nisu autsajder). Do tada je na svim ATP 250 turnirima tiho bila isključena. Izvor se
  bilježi (`measured_penalties.applied[].source`, `market_source`). Izmjereno: autsajderi bez
  konsenzusa −4,0pp (n=28), s konsenzusom −10,7pp (n=20).

**Bira kombinaciju** (`_score_combo`): umnožak pouzdanosti kao glavni kriterij, plus bonus za
value (edge 3-20pp za favorite, 3-28pp za pickove ≥2,00), plus bonus za pouzdanost ≥72,
minus kazna za najslabiji pick, minus kazna za svaki par preko minimalnog broja nogu.

**NOVO 08.09.2026 12:07 — tržišni konsenzus ulazi u izbor kombinacije.**
> **UGAŠEN 18.10.2026 12:37 (korisnikova odluka 3a; zapis 14:44):** `_CONSENSUS_GAP_BONUS` 4.0 →
> 0.0, stara vrijednost u `_CONSENSUS_GAP_BONUS_DO_18_10`. Konsenzus više NE ulazi u izbor; i
> dalje se dohvaća, bilježi i mjeri (KONS u `measure_candidates.py`) i služi kazni za tržišnog
> autsajdera. Ponovni test samo uz prag zapisan unaprijed. MODEL_CHANGELOG 18.10.2026 12:55.
>
> **STANJE 18.10.2026 10:09:** na novim podacima (od 08.09.) n=40, −0,4pp ±13,9 — **NIJE
> POTVRĐEN** (ni oboren). Kriterij za uklanjanje nije nedvosmislen (skripta: n ≥ 30; komentar u
> kodu: 31.10. i n ≥ 60), pa je bonus i dalje u kodu do korisnikove odluke. Odds API ključ je od
> ~15.10. deaktiviran, pa bonus trenutno ionako ne okida. Vidi "IZMJERENO 18.10.2026".

Bonus **+4 boda po picku** kojemu konsenzus ~47 kladionica daje **1pp ili više** više nego
devigirana SuperSport cijena (`_consensus_gap_pp`). Prvi signal u projektu koji je prošao
dvostupanjsku kapiju — nađen na Cincinnatiju, potvrđen na US Openu:

    gap >= +1pp   n=61 | 83,6% | edge +10,5pp | ROI +11,3%
    gap <  +1pp   n=108 | 62,0% | edge  −2,0pp | ROI  −9,2%
    bootstrap 95% CI za edge: [+0,93pp, +19,20pp] — ne prelazi nulu; P=0,036
    uz kontrolu cijene (po pojasevima kvote): zbirno +21,6pp
    US Open +11,8% (n=47) | Cincinnati +9,5% (n=14) | pokrivenost 100% od 30.08.

**Namjerno BONUS, ne tvrdi filtar** — tri ograde: monotonost nije čista (pojas ≤−1pp ide
+6,8pp), n=61 je malo uz prag odabran gledajući podatke, i na TIKETU još nije dokazan (uvjet
`gap>=+1` ostavlja samo 3-4 dana s dovoljno kandidata, što je premalo za zaključak u bilo
kojem smjeru). Puno obrazloženje i prag za sljedeću odluku: `agent/ticket_builder.py`, blok
iznad `_CONSENSUS_GAP_MIN`.

**Dvije stvari u bodovanju ispravljene isti dan** jer su radile protiv mjerenja:
kazna za najslabiji pick išla je s faktorom 1,5 i sidrom 68 (gurala je izbor prema pojasu
65-68, koji ide −35,4%) — sada faktor 0,6 i sidro 63; kazna za dodatne parove bila je
usidrena na fiksnu četvorku pa bi trojac dobio skriveni bonus od +3 boda.

## 3. Bilježi se, ali NE utječe na odluku — `context_snapshot` v21 (v23 od 27.09.2026)

**Od 26.10.2026 (kod 25.10.2026 11:46, u istom zapisu v23):** unutar `p1_gnews` / `p2_gnews` uz stari `inj` / `injury_n` i strogi detektor ozljeda v2 — `inj2` po naslovu, `injury_n2` i oznaka `inj_v: 2` (K13b; `agent/player_news.strict_injury`). Model ih ne vidi; Dnevni listić od istog dana prikazuje samo "priče" i stvarne ozljede iz tih naslova (`player_news.display_items`).

**Od 27.09.2026 12:34 u istom zapisu (v23):** `intuicija` — procjena naučenog signala za obje strane meča (K20), upisana nakon slaganja tiketa; model i tiket je ne vide.

**Od 18.10.2026 15:47 u istom zapisu (v23):** `p1_tml12` / `p2_tml12` — TML forma za zadnjih 12 mjeseci (servis, povrat, 1./2. servis, povrat na 1. servis, hold, asovi po gemu, spašeni BP, broj mečeva po razini, zadnji meč, upotrebljivost), uz postojeće RapidAPI vrijednosti (`p*_serve_pts_won`, `p*_return_won`), koje su praktički zamrznuta statistika karijere. Upisuje se nakon slaganja tiketa iz `agent/tml_forma.py`; tablicu prije runa osvježava `scripts/update_tml_form.py` (korak u `daily_ticket.yml`, pričuva `config/tml_forma_12m.json`). **Prompt je NE vidi:** pravila u promptu imaju pragove na RapidAPI skali, a prelazak bi tražio novo podešavanje i živi (plaćeni) poziv — zasebna odluka. Uz to `nose_karijera` (usporedna varijanta Nosea).

**Od 18.10.2026 12:41 u istom zapisu (v23, oznaka `nose-v1`; zapis 14:44):** `nose` — Nose u sjeni (K24, `agent/nose.py`): Pick Quality (vlastita vjerojatnost, pouzdanost), Mine Risk (M1–M5), Upset Value (U1–U4), Ticket Suitability (IZBJEGAVAJ = NO PICK), `frozen` (SHA-256 faze A) i `vs_market` (faza B). Računa se nakon slaganja tiketa iz teniskih polja snapshota bez ijednog tržišnog polja; model i tiket ga ne vide. Prikazuje se na Dnevnom listiću uz oznaku "u sjeni, nepotvrđeno".

**v23 (27.09.2026 11:58):** vijesti po igraču s Google Newsa (`p1_gnews` / `p2_gnews`, naslovi
iz zadnjih 14 dana, `injury_n`, oznaka `bet` za kladioničarske naslove) — samo za mjerenje K13;
model ih ne vidi.

Vremenski uvjeti u punom obliku (temperatura, vlaga, vjetar, tlak na razini mora i na tlu,
uvjet, koliko je prognoza udaljena od sata meča); je li teren natkriven; je li meč u prvom
valu; odakle dolazi vrijeme početka i koji je bio raspoređeni sat; dob, nacionalnost, ruka;
zajednički protivnici; razina prethodnog turnira; pouzdanost scouting profila; žig verzije
modela (`rules_hash` + `weights_version`); je li cap okinuo i koje pravilo; ELO i ELO razlika;
koliko je protivnika ušlo u prosjek kvalitete; te **ispravljene verzije** povrata
(`return_won_weighted`) i holda (`hold_pct_from_bp`) usporedno s onima koje model stvarno
koristi.

Od **15.08.2026**: tržišni konsenzus 40+ kladionica (`market_p`, `market_p_sharp`,
`market_n_books`, `market_overround`, `market_spread`, `market_gap_pp`, `market_ev_pick`),
cijena **svake kladionice zasebno** u tablici `market_lines`, i cijena u trenutku oklade u
`ticket_matches.market_snapshot`.
Od **30.08.2026 12:37**: `p1_beat_us` / `p2_beat_us` (Fery zastavice) — računaju se i
ispisuju, ali VIŠE NE ULAZE u selekciju. Veto je ukinut jer je mjerenje pokazalo da je
blokirao našu najbolju skupinu: pickovi protiv igrača koji nas je 2+ puta srušio prošli
su 93,3% (n=15, +23,1pp), a pickovi protiv onih koji su nas srušili točno jednom — koje
veto nikad nije dirao — 56,8% (n=44, -10,1pp). Vidi MODEL_CHANGELOG 30.08.2026 12:37.

Od **17.08.2026**: `serve_gap_raw_pp` (sirovi jaz u poenima na servisu, bez množitelja 1,9)
i `measured_penalties` (koja je kazna okinula i koliko je oduzela). Od istog dana radi i
**drugo hvatanje cijena** pred početak mečeva (`scripts/capture_market_close.py`, cron 14:30
UTC) — dopisuje se u `market_lines` pored prve snimke, pa se kretanje linije može mjeriti
namjerno umjesto slučajno.

Od **26.08.2026 15:20** (`context_snapshot` v16) — tri kandidata iz dubinske hard revizije,
svi **isključivo za mjerenje**, nijedan ne ulazi u prompt i nijedan ne mijenja pick:

| polje | što je | zašto se bilježi |
|---|---|---|
| `p1/p2_avg_opp_elo_5` | prosječni surface-ELO zadnjih 5 protivnika | 25 od 25 testiranih definicija ide u isti smjer; ispod ~1700 pick prolazi 41,0% naspram 60,0% koje traži cijena |
| `avg_opp_elo_5_n` | `used` / `total` / `defaulted` po igraču | bez toga se ne zna je li prosjek nizak zato što su protivnici slabi ili zato što ih ne prepoznajemo |
| `p1/p2_form_quality` | forma zadnjih 5 × (prosječni ELO tih protivnika − 1700)/100 | `r = +0,290, P=0,0005` — najjača pojedinačna brojka u cijeloj reviziji, i bez ijednog proizvoljnog praga |
| `age_gap` | dob igrača 1 minus dob igrača 2 | naš pick stariji 4+ godine: 42,9%, −15,4pp naspram cijene; 6 od 6 definicija isti smjer |
| `p1/p2_matches_3_9d` | mečevi u prozoru 3–9 dana prije meča | nalaz o opterećenju protivnika **pao** na provjeri robusnosti (6/12 definicija) — bilježi se samo da se može premjeriti |

Prozor počinje na 3 dana, ne na 0: naš `match_date` i datum iz API-ja razilaze se u 23%
slučajeva (±2 dana), pa bi prozor od danas u dio redaka uvukao sam meč koji predviđamo.

Od **27.08.2026 18:55** (`context_snapshot` v17) — dijagnostika samog poziva modela:

| polje | što je |
|---|---|
| `analysis_call` | `{attempts, stop_reason, max_tokens, output_tokens, raw_chars, error}` — bilježi se **uvijek**, i kad poziv prođe iz prvog pokušaja |
| `analysis_failed` | `True` samo kad model nije vratio JSON; razlikuje grešku od `skip_reason` (svjesna odluka modela da preskoči meč) |

**Važnija promjena od samih polja:** do v17 je meč kod kojeg poziv padne završavao u bazi
**bez ijednog predmečnog podatka** — bez ELO-a, forme, kvote, vremena, `form_quality`,
`age_gap`. Post-match statistiku je takav redak i dalje dobivao, pa smo imali *kako* je meč
završio bez ičega o tome *kakvi su bili uvjeti prije njega*. Od v17 se cijeli snapshot
sprema i na grani greške. Tko broji analize po erama mora znati da se time promijenio
sastav korpusa, ne samo skup polja.

Od **26.09.2026 17:04** (`context_snapshot` v21) — na korisnikov zahtjev, i unatrag za
svih 664 dosadašnjih analiza (`scripts/backfill_player_context.py`, vrijednosti na dan meča):

| polje | što je |
|---|---|
| `p*_ctx.hand` / `opp_hand` | ruka igrača i današnjeg protivnika (`L`/`R`/prazno) |
| `p*_ctx.vs_hand` | W-L protiv ljevaka i protiv desnjaka, zadnje 2 godine (+ broj protivnika nepoznate ruke) |
| `p*_ctx.season` | ATP W-L u kalendarskoj godini (glavni ždrijeb, tour razine) + W-L na svim razinama |
| `p*_ctx.gs` | broj GS polufinala, finala, naslova i nastupa u glavnom ždrijebu do dana meča |
| `p*_titles` | karijerna finala po razini — u promptu od 26.07.2026, prvi put se bilježe |
| `round_source` | `manual` (korisnik upisao) / `missing` (nije) |

Mjerenje: K15, K16 i zapis o ruci u registru niže. Nijedno od toga još NE ulazi u odluku.

Od **26.09.2026 20:46** (`context_snapshot` v22):

| polje | što je |
|---|---|
| `market_source` | odakle je cijena za provjeru autsajdera: `consensus` / `screenshot` / `none` |
| `p*_aces_per100` | asovi na 100 servisnih poena — zamjenjuje `p*_aces`, koji je bio **0 u 410/410** redaka (krivi ključ) |
| `p*_height_cm`, `p*_weight_kg` | sada **None** kad je nepoznato (prije 0 u 50/410 redaka — "signal visine" bio je artefakt tih nula) |

Za **K19** (pauza) koristi se postojeći `p*_days_rest` — ne treba novo polje.

Svrha: svaka buduća hipoteza mora se moći provjeriti retroaktivno umjesto pogađati.

---

## 4a. PREDLOŽENO, još NE ulazi u odluku — "Historical Match-Up Context"

*(zapisano 28.08.2026 20:21; korisnikov rok: do kraja 2026.)*

Sedma točka uz Rating / Serve / Form / Matchup / Tournament history: agent bi prije konačne
preporuke pretražio ranije analizirane mečeve, našao 5–15 povijesno najsličnijih situacija i
prikazao kako su **agregatno** prošle naspram devigirane cijene — npr. *"12 sličnih slučajeva:
41,7% stvarno vs 58,9% devig očekivano = −17,2pp"*. Nikad kao samostalan razlog za pick, i
nikad kao pojedinačna anegdota.

**Backtestirano 28.08.2026 i ODGOĐENO.** Walk-forward k-NN daje `r = −0,020` (n=276);
"oracle" verzija koja smije gledati budućnost daje `r = −0,101` — dakle strukture nema ni kad
se vara. Jednodimenzionalna verzija na najjačem poznatom signalu (runda) u realnom vremenu je
za R16/QF tvrdila **+1,9pp** dok se ostvarivalo **−6,6pp**. Puni zapis s brojkama, uvjetima za
ponovno otvaranje i predloženom arhitekturom: MODEL_CHANGELOG 28.08.2026 20:21.

**Preduvjet za ponovno otvaranje:** ~900 riješenih analiza, `age_gap` / `avg_opp_elo_5` /
`form_quality` riješeni na većini njih (bilježe se tek od 26.08.), pool unutar jedne `rules_hash` ere.

**ČETVRTI BACKTEST 26.09.2026 20:46 — po korisnikovoj točnoj specifikaciji, ODBAČENO kao ulaz.**
Walk-forward (samo analize ≥3 dana starije), tvrdi uvjet isti pojas tržišne vjerojatnosti ±5pp,
sličnost po ELO jazu, ELO zadnjih 5 protivnika oba igrača, rangu, dobi, opterećenju, ruci,
servisu, povratu, formi, visini i rundi (n=451):

    k=5  r=-0,074 | k=10 r=-0,042 | k=15 r=+0,054 | k=30 r=-0,025 | oracle k=10/30 r=-0,064/-0,009

"Negativan signal" (≤−10pp) je za k=10 stvarno išao **+12,1pp**. Na 5.143 ATP meča s kvotama
(berba 26.09.) kNN daje r=+0,13-0,15, ali **sam pojas cijene bez ikakve sličnosti daje +0,16**;
prirast sličnosti povrh pojasa r=+0,04. Snaga: za učinak od 10pp treba ~180 sličnih slučajeva;
"12 slučajeva: −17,2pp" ima 95% interval od −44 do +10pp. Jedini iskreni ostatak ideje je
redak "naš edge u ovom pojasu kvote" — prikazuje se korisniku na Dnevnom listiću
(`utils.helpers.band_edge_context`), ne modelu.

---

## 4e. ZATVORENO 26.09.2026 20:46 — obrnuti Fery veto (30.08.2026 12:37)

**ISHOD:** izvan uzorka (mečevi od 31.08.) "srušio nas točno jednom" daje **−1,9 / +3,2 /
−8,7 / −0,2pp** u četiri definicije (n=23-40) — predznak nedosljedan, prag (−8pp uz n≥80)
nije ni blizu. Druga strana ("2+ poraza") i dalje ide za nas (+18,2pp, n=26). Zatvoreno.
Mjerenje: `revizije/2026-09-26/`.

*(izvorni zapis ispod ostaje radi traga)*

Mjerenje koje je ukinulo Fery veto pokazalo je i suprotan signal: pickovi protiv igrača koji
nas je srušio **točno jednom** prolaze ispod tržišta u sve četiri testirane definicije
pravila — `-10,1pp` (n=44, isti turnir 14 dana), `-10,9pp` (n=54, bilo gdje 14 dana),
`-7,9pp` (n=56, 30 dana), `-5,5pp` (n=59, cijela sezona). Split-half: `-3,8pp` pa `-16,3pp`.

Mehanizam bi bio smislen: igrača koji nas je jednom srušio sustavno podcjenjujemo i nastavimo
ga fade-ati po cijeni na kojoj smo krivi. **NIJE u kodu** jer je P=0,10-0,16 i rezalo bi 18%
kandidata — to je prevelik zahvat na dokazu ove snage. Premjeriti nakon US Opena; ako edge
ostane ispod -8pp na n=80+, pretvoriti u kaznu (ne veto).

---

## 0. PRAVILO PROJEKTA — dvostupanjska kapija za svaku izmjenu modela

*(uvedeno 06.09.2026 10:27, korisnikova odluka; vrijedi od danas za sve podloge)*

**Povod.** Tri pravila uvedena 30.08.2026 imala su P = 0,008 / 0,026 / 0,001 — sva ispod
0,05 — i sva tri su pala na prvom nezavisnom uzorku (US Open, 104 meča). Stopa replikacije
naših implementiranih nalaza je time **0 od 3**. Prag značajnosti očito nije bio usko grlo.

**Kapija ima dva stupnja i ona su namjerno različito stroga.**

### 1. stupanj — OTKRIVANJE (labavo, ne košta ništa)
Gleda se sve što ima smisleni mehanizam, **prag smije biti i labaviji od P<0,10**. Nalaz se
NE implementira. Upisuje se u registar niže, obavezno s **unaprijed zapisanim pragom za
potvrdu** (koji uzorak, koliki učinak, koji smjer). Prag se zapisuje PRIJE nego što podaci
za potvrdu postoje — inače je to naknadna pamet.

### 2. stupanj — POTVRDA (strogo, odlučuje o novcu)
Nalaz ulazi u kod tek kad preživi **turnir na kojem NIJE nađen**, u smjeru i veličini koji
su unaprijed zapisani. Ako promijeni predznak — pada, bez rasprave.

### Zašto je ovo labavije, a ne strože, nego dosad
Danas se nalaz s P<0,05 mogao implementirati odmah. Sada se **bilo koji** nalaz smije
istraživati, ali nijedan ne ulazi u kod bez nezavisne potvrde. Kroz vrijeme daje VIŠE
upotrebljivih nalaza, jer razdvaja "našli smo 6 stvari, 4 su šum, ne znamo koje" od
"imamo 15 kandidata i za mjesec dana znamo koja su tri stvarna".

### Poredak kod praga "prvih N" (25.10.2026 11:46, revizija 25.10., P5)
Kad prag kaže "sljedećih/prvih N" (pickova, mečeva, procjena), u pragu se uvijek piše i POREDAK:
**stabilno po (datum meča, vrijeme upisa analize)**, a presuda se zamrzava na tih N. Bez toga
presuda "treperi" s danom: K18 je 20.10. bio POTVRĐEN (−5,6), 21.–23.10. ČEKA, 24.10. opet
POTVRĐEN, a revizijska skripta s nestabilnim sortom dala je −2,0 umjesto −5,3pp. Vrijedi za sve
nove kandidate; postojeći se ne prepravljaju unatrag.

### Nova metrika zdravlja modela: STOPA REPLIKACIJE
Uz postotak pogodaka pratimo i koliko naših nalaza preživi idući turnir.
**Stanje 06.09.2026: 0 od 3.**

---


**AŽURIRANO 08.09.2026 12:07 — prvi pravi krug kapije, na US Openu:**

| kandidat | prag zapisan prije podataka | ishod |
|---|---|---|
| K1 — pojas 58-63 tuče tržište | edge >= +3pp uz n>=25 | **POTVRĐEN** (+9,3pp, n=49) |
| K6 — široko neslaganje kladionica | >= +8pp uz n>=25 I monotonost | **PAO** (+6,1pp, nemonoton) |
| K7 — sharp naspram konsenzusa | n>=40 u repu, razlika >=10pp | **PAO** (rep prazan) |

**Stopa replikacije: 1 od 6** (prije: 0 od 3). Prvi nalaz koji je prošao. Vrijedi zapamtiti
što ga je razlikovalo: K1 je imao ISTI PREDZNAK u dvije odvojene ere modela još prije
provjere, dok su K6 i K7 bili najjače pojedinačne brojke jednog uzorka. Jačina P-vrijednosti
nije razlikovala potvrđeno od palog — ponovljivost predznaka jest.

## 0a. REGISTAR KANDIDATA — nalazi koji čekaju potvrdu

Ništa odavde NIJE u kodu. Svaki red ima unaprijed zapisan prag.

### K1 — pickovi ispod praga 63% tuku tržište — **POTVRĐEN 08.09.2026 12:07, UŠAO U KOD** — *04.10.2026 19:22: PRAG VRAĆEN NA 63 (korisnikova odluka); K1 se kao nalaz više NE tretira potvrđenim — nije se ponovio (vidi IZMJERENO 04.10.2026)*

*(27.09.2026 12:16) Prompt je promijenjen (era 9696c4ee -> bccf4742): prag 60 i kaznu za pojas 65-68 premjeriti nakon prvog dovršenog turnira u eri bccf4742.*

    sve podloge   <63: n=121  67,8%  edge  +6,7pp  |  >=63: n=293  63,5%  edge  -2,7pp
    hard          <63: n=113  68,1%  edge  +7,1pp  |  >=63: n=209  62,7%  edge  -4,2pp
    staro         <63: n= 64  60,9%  edge  +2,5pp  |  >=63: n=246  61,8%  edge  -2,6pp
    US Open       <63: n= 57  75,4%  edge +11,4pp  |  >=63: n= 47  72,3%  edge  -3,3pp

**Isti predznak u obje ere** — jedini nalaz koji nam se dosad replicirao. Mehanizam je
poznat: pouzdanost modela ima Brier lošiji od konstante 0,64, pa u pojasu 58-63 nosi
negativnu informaciju. Pojas 60-63 je naša najbolja skupina s ozbiljnim uzorkom
(n=82 na hardu, +6,4pp).

**PRAG ZA POTVRDU (zapisano 06.09.2026, prije podataka):** na sljedećem dovršenom turniru
skupina s conf 58-63 mora dati **edge +3pp ili više uz n>=25**. Ako da, uvodi se oprezno:
najviše JEDAN pick iz pojasa 58-63 po tiketu, uz zadržan opći prag za ostale.
Ako edge padne ispod nule — kandidat se odbacuje.

**ZAŠTO SE NIJE UVEO ODMAH (06.09.):** kapija je uvedena isti dan; zaobići je na prvom
nalazu značilo bi da je nemamo. Nalaz je jak i vjerojatno stvaran, ali je čekao svoj red.

---

#### ISHOD PROVJERE NA US OPENU (08.09.2026 12:07) — **POTVRĐENO**

US Open je bio dovršen turnir na kojem nalaz NIJE nađen, dakle valjan drugi stupanj.
Mjereno točno po pragu zapisanom 06.09. prije podataka:

    conf 58-63          n=49 | 75,5% | tržište 66,2% | edge  +9,3pp   <- traženo >= +3pp uz n>=25
    conf 60-63 (uže)    n=40 | 77,5% | tržište 68,6% | edge  +8,9pp
    conf >= 63 (kontrola) n=51 | 72,5% | tržište 75,6% | edge  -3,0pp

Prag je bio **+3pp uz n>=25**. Dobiveno **+9,3pp uz n=49** — potvrđeno s velikom rezervom
iznad praga, a kontrolna skupina je istovremeno negativna.

**ŠTO JE UČINJENO:** opći prag u `TICKET_CONFIG` spušten sa 63 na **60** (ne na 58).

**ODSTUPANJE OD ZAPISANOG LIJEKA — namjerno i evo zašto.** Registrirani lijek glasio je
"najviše JEDAN pick iz pojasa 58-63 po tiketu, uz zadržan opći prag za ostale". Taj je
oprez bio kalibriran na neizvjesnost je li nalaz stvaran. Neizvjesnost je sada testirana i
uklonjena, a sam lijek bi u novom svjetlu bio naopak: ograničio bi BOLJU skupinu (60-63,
+8,9pp) dok bi LOŠIJU (>=63, -3,0pp) puštao neograničeno.

Izmjena je ipak uža od potvrđenog nalaza: potvrđen je pojas 58-63, a u kod je ušao samo
njegov jači i brojniji dio 60-63. Pojas 58-60 ostaje vani jer mu split-half okreće predznak
(-5 / +11).

**ŠTO PRATITI:** ako skupina conf 60-63 na sljedećem dovršenom turniru padne ispod nule uz
n>=25, prag se vraća na 63. Zapisano prije podataka.

### K2 — pravilo 11 (domaći teren) ide u krivom smjeru — **PROVEDENO 27.09.2026 12:16**

**Ishod:** korisnik odobrio nakon povijesnog laboratorija (domaći igrači −1,4pp naspram cijene na 2.775 meča, obje polovice −). Pravilo o domaćem terenu (grass 11, clay 7, hard 11) svedeno je na "već je u cijeni, ne prilagođavaj", a ista provjera maknuta je i iz AI-recenzenta tiketa (`ticket_builder._review_ticket`). Era bccf4742.

    protivnik domaći (danas -3pp)   n= 30 | 70,0% | edge +7,5pp
    naš pick domaći  (danas  0pp)   n= 35 | 77,1% | edge +7,4pp
    nitko domaći                    n=271 | 62,4% | edge -1,9pp

Split-half drži u oba smjera, isto i samo na hardu. **PRAG:** još 20 mečeva s domaćim
igračem; ako protivnik-domaći ostane iznad +3pp, penal se briše iz prompta (mijenja
`rules_hash`, ide u paket s preslagivanjem prompta poslije US Opena).

### K3 — Bo5 pojas kvota 1,30-1,50 — **ZATVOREN 27.09.2026 12:16**

**Ishod:** povijesno suprotan smjer — Grand Slam favoriti 1,30-1,50 idu **+4,3pp** naspram cijene (n=563, obje polovice +). Kazna bi rezala dobre pickove. Korisnik odobrio zatvaranje.

    Bo5 1,30-1,50  n=26 | 57,7% | tržište 69,9% | edge -12,2pp

Ista rupa marginalnog favorita koju znamo s harda, izraženija u Bo5. **PRAG:** n>=50 i
edge ispod -8pp na sljedećem Grand Slamu.

### K4 — omjer winneri/greške kao PRE-match varijabla

Post-match je najjača veza u projektu (r=+0,705). Sezonski ekvivalent ne postoji ni na
jednom endpointu koji koristimo. **PRAG:** ako se nađe izvor sezonskog winners/UE po igraču,
testirati kao pre-match ulaz; do tada isključivo za objašnjenje u analizi gubitaka.

### K5 — oprezna zona počinje prenisko: rupa je od 1,35, a kod pokriva od 1,43 — **PRAG PODIGNUT 27.09.2026 12:16**

**Novi prag (korisnik odobrio):** n ≥ 100 umjesto n ≥ 20, uz isti uvjet (−5pp ili gore). Razlog: na tržištu favoriti u 1,35-1,43 prolaze BOLJE od cijene (+3,7pp, n=1.364), pa je naš −7,9pp (n=53, interval ±13pp) vjerojatnije šum ili naš izbor nego rupa; uz n=20 interval je ±21pp. Stari prag ispod ostaje zapisan radi povijesti; `measure_candidates.py` mjeri novi.

    pojas kvote      staro (do 29.08.)   US Open      cijeli korpus
    1,20-1,30            +6,0pp           +23,2pp        +8,8pp
    1,35-1,43            -6,1pp           -17,8pp        -7,9pp   <- NIJE pokriveno
    1,43-1,60           -12,1pp           +16,4pp        -9,4pp   <- oprezna zona u kodu

Pojas **1,35-1,43** nosi n=53 i **isti predznak u obje ere**. Provjere za širi pojas
1,35-1,50 (n=76): hard −10,9pp, Grand Slam −21,2pp, split-half −4,0pp pa −14,8pp.
Bootstrap 95% CI [−20,0, +2,1] prelazi nulu, pa nije dokazano — ali smjer je dosljedan
u svakom rezu.

**PRAG ZA POTVRDU (zapisano 06.09.2026 10:55, prije podataka):** na sljedećem dovršenom
turniru pojas 1,35-1,43 mora dati **−5pp ili gore uz n>=20**. Ako da, `_HARD_CAUTION_ZONE`
se spušta s (1,43, 1,60) na (1,35, 1,60). Ako edge bude iznad nule — kandidat pada.

### K6 — široko neslaganje kladionica uz kvotu 1,40+

    raspon među kladionicama, gornja trećina   n=55 | 83,6% | tržište 68,7% | +15,0pp | P=0,017
       split-half:  +13,1pp / +16,8pp   (isti smjer)
       bootstrap 95% CI: [+3,5, +25,0]  (ne prelazi nulu)
       nije zamjena za kvotu: prosječna kvota 1,45 naspram 1,49 kod uskog tržišta
    široko tržište + kvota >= 1,40             n=27 | 85,2% | tržište 56,2% | +29,0pp | P=0,002

Najjača pojedinačna brojka izmjerena 06.09. **ALI: nije monotona** — usko +3,8pp, srednje
−10,2pp, široko +15,0pp. Da mehanizam postoji, učinak bi rastao postupno. Uz to je ovo bio
jedan od dvadesetak testova na istom skupu podataka, pa je P=0,002 manje impresivan nego
što izgleda.

**PRAG ZA POTVRDU:** na sljedećem turniru gornja trećina po rasponu mora dati **+8pp ili
više uz n>=25**, I srednja trećina ne smije biti najgora (traži se monotonost). Bez
monotonosti se ne uvodi ni pri jakom P.

#### ISHOD PROVJERE NA US OPENU (08.09.2026 12:07) — **PAO**

    usko (donja trećina)      n=38 | 71,1% | edge  +9,3pp
    srednje                   n=37 | 64,9% | edge  -5,2pp   <- opet najgore
    široko (gornja trećina)   n=37 | 81,1% | edge  +6,1pp   <- traženo >= +8pp

Oba uvjeta pala: gornja trećina daje +6,1pp (ispod praga +8pp), a monotonost je pala po
DRUGI put i to na isti način — srednja trećina je najgora skupina. Nemonotonost koja se
ponovi na neovisnom uzorku nije šum nego znak da mehanizma nema.

Podskupina "široko + kvota >= 1,40" daje +23,3pp, ali n=12 i to je upravo rezanje koje je
kandidat i stvorilo. **ODBAČENO.** Ne otvarati bez novog mehanizma, ne novog rezanja.

### K7 — sharp kladionice naspram konsenzusa

    sharp dao našem picku VIŠE   n=90 | +6,2pp
    sharp se slaže s konsenzusom n=60 | +0,4pp
    sharp dao MANJE              n=17 | -6,4pp

Smjer je smislen i **monoton**, ali r=+0,028 (P=0,72) i rep ima samo 17 mečeva.
**PRAG:** n>=40 u repu i razlika krajnjih skupina >=10pp.

#### ISHOD PROVJERE NA US OPENU (08.09.2026 12:07) — **PAO, i to iz poučnog razloga**

    sharp dao našem picku VIŠE     n=  0
    sharp se slaže s konsenzusom   n=112
    sharp dao MANJE (rep)          n=  0

Na svih 112 US Open analiza `market_p_sharp` je **identičan** `market_p`. Brier im je isti
do četvrte decimale (0,1899 naspram 0,1899). Dakle nema dvije skupine za usporediti —
"sharp" cijena kakvu bilježimo nije zaseban izvor informacije nego ista brojka.

To poništava i uzorak od 06.09. (n=90/60/17): te su razlike vjerojatno dolazile iz mečeva
gdje je sharp podskup imao drukčiji sastav kladionica, a ne iz drukčije procjene.
**ODBAČENO.** Prije ponovnog otvaranja treba provjeriti PIŠE li `market_p_sharp` uopće
išta različito — isti obrazac kao "tihi null ključevi" iz memorije.

### K8 — slotovi 4 i 5 u `key_factors` prazni su četvrtinu vremena, a tada prolazimo BOLJE

Mjereno 08.09.2026 12:07 na 441 riješenoj tiket-nozi s potpunim `key_factors`.

    slot 4 "Matchup & conditions"    'no data' u 112 od 470 (23,8%)
    slot 5 "Tournament history"      'no data' u 118 od 441 (26,8%)

Kad slot kaže "no data", naš pick prolazi **bolje**, i to preživljava kontrolu cijene:

    pojas kvote      slot 4          slot 5
    1,30-1,50        +5,7pp          +7,3pp
    1,50-2,00        +5,7pp          +6,7pp
    2,00+            +5,3pp         +12,6pp
    1,00-1,30        -5,6pp (n=6)    +0,8pp

Provjeren i konfaund runde: "no data" nije samo oznaka ranog kola (R64 39%/46%, ali R16
26%/34% i SF 25%/4,5% — nema čistog gradijenta).

**Čitanje koje se nameće:** kad model IMA podatke o stilu, uvjetima i povijesti turnira, on
ih upotrijebi — a upotreba pogoršava ishod. Isti obrazac kao ranije nađeni "narativni
override": dodatni kontekst se troši na obrazloženje picka, ne na njegovu provjeru.

**PRAG ZA POTVRDU (zapisano prije podataka):** na sljedeća DVA dovršena turnira razlika
"no data" naspram "s podatkom" mora ostati **+4pp ili više uz n≥40**, i to u **barem dva**
pojasa kvote. Ako da → razmotriti spajanje slotova 4 i 5 u jedan i oslobađanje prostora
(prompt caching to čini jeftinim). Ako padne ispod nule → odbaciti.

**ZAŠTO SE NE DIRA ODMAH:** nađeno na jednom korpusu, a stopa replikacije nam je 1 od 6.
Uz to bi izmjena dirala prompt, dakle `rules_hash` — a upravo smo ga mijenjali dvaput danas.

### K9 — duljina slota "Own read" obrnuto je povezana s uspjehom — **PAO 04.10.2026 18:32** (predznak suprotan drugi put)

Isti uzorak. "Own read" je jedini neobavezan slot (prisutan u 297 od 529, 57%) i jedini
s pozitivnim signalom u razini (64,3% naspram 62,6% ukupno). Ali:

    prosječna duljina slota 6 u POBJEDAMA     956 znakova
    prosječna duljina slota 6 u PORAZIMA     1024 znakova

Jedini je od šest slotova gdje je **dulje = gore** (svi ostali imaju +7 do +29 znakova u
pobjedama). Čitanje: dug "vlastiti nalaz" nije uvid nego racionalizacija.

**PRAG ZA POTVRDU:** na sljedeća dva turnira razlika duljine (pobjede minus porazi) mora
ostati **negativna uz n≥60**, i razlika mora biti barem 40 znakova. Ako da → u prompt ide
tvrda granica duljine za slot 6 (npr. 400 znakova) uz uputu da se piše samo ono što se ne
uklapa u 1-5. Ako predznak okrene → odbaciti.

**OGRADA:** duljina može biti proxy za težinu meča (težak meč → dulje objašnjenje → i češći
poraz). To nije kontrolirano. Prije uvođenja bilo kakvog pravila **obavezno** izmjeriti
duljinu uz kontrolu cijene, kao što je učinjeno za K8.

#### MEĐUSTANJE K8 i K9 (26.09.2026 21:27) i što je napravljeno

Izvan uzorka (analize od 08.09. 12:07, n=27 riješenih s cijenom):

    K8  odjeljak povijesti S podatkom  n=18  edge -8,0pp  | bez podatka n=9  -1,9pp
        (prije 08.09. na jedinstvenim analizama: -7,3pp n=62  | +4,7pp n=88)
    K9  own read u pobjedama DULJI za 144 znaka; r(duljina, ishod - cijena) = +0,36

K8 drži smjer u oba uzorka, ali n je ispod praga. K9 je okrenuo predznak — ograničenje
duljine se NE uvodi. Odjeljci 4 i 5 ipak su spojeni u "4. Context" u sklopu čišćenja
prompta (korisnik odobrio), jer je povijest turnira — glavni sadržaj odjeljka 5 — kao
varijabla pala dvaput izvan uzorka. To nije provedba K8 nego posljedica pada te
varijable; K8 se od ere d7e45052 više ne može mjeriti u izvornom obliku. Vidi
MODEL_CHANGELOG 2026-09-26 21:27.

### K10 — `edge_bonus` je prerušena sklonost duljoj kvoti; treba li nam IZRIČITA? — *25.10.2026 11:24: okinut drugi put, oblik se nije ponovio; odluka korisnika, preporuka ne provoditi*

Izmjereno 13.09.2026 10:44 na 427 razriješenih analiza s kvotom i ishodom.

`edge = confidence − 100/kvota`. Uz confidence koji je praktički konstanta (medijan 63,
SD 3,72, n=469), to je **monotona funkcija kvote i ništa drugo**. Zastavica `value`
(edge ≥ 3) reproducira se pukim pragom **`kvota ≥ 1,66` s 84,6% točnosti**.

To je najveći član u `_score_combo`: do +10 po picku, dakle do +30 za trojac, dok
`joint_prob × 100` daje oko 25.

**Nosi li išta?** Ne, kad se kontrolira cijena:

    sirovo          value=TRUE 58,0% (n=162)   value=FALSE 68,6% (n=293)   −10,6pp
    samo US Open    value=TRUE 55,0% (n=20)    value=FALSE 76,3% (n=97)    −21,3pp
    stratificirano  −1,2pp, 95% CI [−16,9 , +13,0]

Sirova razlika je **Simpsonov paradoks** — medijan kvote 1,80 kod TRUE, 1,40 kod FALSE.

**Zašto član ipak ostaje:** po ROI-ju je "lošija" strana zapravo bolja (−1,1% naspram
−7,0%), jer sjedi u pojasu 1,65-1,85, a to je naš najbolji pojas.

    pojas         ROI value=TRUE      ROI value=FALSE
    1,20-1,35       −5,6% (n=8)        +6,3% (n=68)
    1,35-1,50      −11,4% (n=8)       −17,4% (n=70)
    1,50-1,65      −21,6% (n=8)       −19,4% (n=70)
    1,65-1,85      +17,4% (n=57)      +14,2% (n=25)

**PRAG ZA POTVRDU (zapisano prije podataka):** na sljedeća DVA dovršena turnira profil po
pojasima mora zadržati isti oblik — pojas 1,35-1,65 negativan, a **barem jedan** od
1,20-1,35 i 1,65-1,85 pozitivan, uz n≥25 po pojasu. Ako da → `edge_bonus` se zamjenjuje
IZRIČITIM bonusom po pojasu cijene i prestaje se pretvarati da mjeri neslaganje s
tržištem. Ako se oblik raspline → član se vadi bez zamjene.

**Veza:** ovo je isti nalaz kao [K5](#k5), gledan s druge strane. K5 kaže da oprezna zona
u kodu počinje na 1,43 a rupa je od 1,35; K10 kaže da je jedini mehanizam koji na tu rupu
uopće reagira prerušen u nešto drugo. Riješiti ih zajedno.

**NE PONAVLJATI** sirovu usporedbu value=TRUE/FALSE bez kontrole cijene. Tri je puta
izgledala kao dramatičan nalaz i tri je puta bila cijena.

**ISHOD 18.10.2026 10:09 — FORMALNO ZADOVOLJEN, OBLIK SE NIJE PONOVIO (NE PROVODI SE):** od
14.09. 1,20–1,35 +10,4pp (n=33) | 1,35–1,65 −3,3pp (67) | 1,65–1,85 −6,9pp (33). Uvjet prolazi
samo granom "ILI" (1,20–1,35 > 0). Pojas 1,65–1,85, koji `edge_bonus` nagrađuje, bio je +12,3pp
prije 14.09. (n=81), a sada je −6,9pp (razlika vanjskih pojaseva z=1,5); fini pojasevi daju
liniju koja pada s kvotom (+12,6 @1,30–1,40 … −23,0 @1,85–2,10), ne dolinu. Akcija iz praga
("izričiti bonus po pojasu") je nova heuristika → po korisnikovoj uputi 18.10. NE uvodi se u ovom
ciklusu; bilježi se kao **K10b** (niže). Skeptik: SUMNJIVO — pisati "formalno, ne potvrđeno".

### K11 — rupa u R16/QF PREŽIVJELA je ispravak oznaka rundi — **ZATVOREN 04.10.2026 19:27** (nije potvrđen u zadanom roku: −1,5pp n=31, bolji od ostalih rundi; bez analiza s krivim ELO-om +1,2pp n=29; tržište u R16/QF nema rupu)

Premjereno 13.09.2026 11:30, **prvi put na točnim oznakama** (prije ispravka je 79,2%
oznaka bilo krivo, pa se nalaz iz revizije 26.08.2026 nije mogao ni potvrditi ni odbaciti).

    runda    n     WR      ROI      očekivani WR   reziduum
    R128   119   68,1%   +0,4%        65,0%        +3,1pp
    R64    104   64,4%   −7,9%        67,0%        −2,6pp
    R32    113   65,5%   −3,6%        63,4%        +2,1pp
    R16     44   52,3%  −24,2%        64,4%       −12,1pp
    QF      27   55,6%  −18,4%        64,0%        −8,4pp
    SF      15   86,7%  +41,8%        61,8%       +24,8pp

Objedinjeno:

    R16+QF       n=71   WR 53,5%   ROI −22,0%   reziduum −10,7pp
    sve ostalo   n=356  WR 66,9%   ROI  −1,7%   reziduum  +2,0pp
    razlika −12,7pp   P(permutacija)=0,036   bootstrap 95% CI [−24,8 , −0,9]

CI **ne prelazi nulu**, i nalaz replicira u obje polovice korpusa:

    US Open          R16+QF n=11  −12,2pp   ostalo +5,2pp   razlika −17,4pp
    ostali turniri   R16+QF n=60  −10,4pp   ostalo +0,6pp   razlika −11,0pp

Stara brojka (26.08.2026, na pokvarenim oznakama) bila je **−13,3pp** — praktički ista.
To je jedini nalaz u projektu koji je prežio i zamjenu podloge pod sobom.

**Zašto BAŠ R16/QF:** hipoteza je da ELO i forma prestaju razlikovati igrače kad su svi
preostali dobri, a `tournament_trajectory` (7% težine) tek tada postaje smislen — ali
model ga ne koristi jer je do R16 uglavnom "N/A". SF ide u SUPROTNOM smjeru (+24,8pp),
što je konzistentno s tim čitanjem: u SF razlike su opet velike i vidljive.
**OGRADA:** SF ima n=15, to je jedan loš tjedan od preokreta.

**PRAG ZA POTVRDU (zapisano prije podataka):** na sljedeća DVA dovršena turnira reziduum
za R16+QF mora ostati **negativan uz najmanje −5pp i n≥20**, i razlika naspram ostatka
mora ostati negativna. Ako da → u `ticket_builder` ide kazna za R16/QF noge (nije filtar,
nego bod u `_score_combo`, kao konsenzus). Ako predznak okrene → odbaciti i zatvoriti
pitanje zauvijek, jer je onda i stara verzija bila artefakt.

**NE DIRATI PROMPT.** Model ne smije doznati da je R16 "opasan" — to je ista zamka kao s
konsenzusom: procjena bi postala odjek pravila i mehanizam bi se udvostručio.

### K12 — prosjek statistike s turnira: UVEDEN unatoc nuli, mjeri se po DUBINI — **IZAŠAO IZ ODLUČIVANJA 27.09.2026 12:16**

**Ishod:** po vlastitom pragu (ispod: r < +0,05 -> izlazi) — na 970 ATP meča gdje oba igrača imaju 3+ meča na turniru razlika ne dodaje ništa cijeni (r = +0,004). Uputa u promptu svedena je na opis ("use them to describe the matchup, not to move your confidence"); podaci se i dalje prikazuju i bilježe (`p*_tourn_form_*`). Korisnik odobrio. Era bccf4742.

Uveden 13.09.2026 12:20 na korisnikov izricit zahtjev, nakon sto je isti dan izmjeren kao
nula. Ovo je prvi put da nesto ulazi u kod BEZ prolaska kroz kapiju, pa je vrijedno
zapisati tocno zasto i pod kojim uvjetom izlazi.

**Sto je mjerenje reklo (n=127, 13.09.2026 10:44):** razlika u prosjecima ne predvidja
ishod — serve_won r=+0,008 P=0,924; ace_rate −0,097 P=0,283; bp_saved −0,004 P=0,966.
Naspram devigane cijene sve tri idu u krivu stranu.

**Zasto to nije kraj price:** dubina uzorka bila je 1 raniji mec u 58 od 127 slucajeva,
a dubina 3+ imala je n=23. Korisnikova tvrdnja je da signal zivi bas u QF/SF, gdje iza
igraca stoje 3-4 meca. **Mjerenje tu tvrdnju nije testiralo, jer ondje nije imalo snagu.**

**Sto je ugradjeno kao zastita:** prag od 2 meca; prompt izricito kaze da je varijabla
izmjerena kao slaba i da vrijedi najvise par postotnih bodova; razlika se ignorira ako
nije velika (servis <4pp, asovi/100 <3); popis protivnika se cuva i prompt trazi da se
procita prije nego se prosjeku vjeruje.

**PRAG ZA ODLUKU (zapisano prije podataka):** nakon 2-3 dovrsena turnira, na mecevima gdje
OBA igraca imaju **3+ meca** na turniru (dakle QF nadalje), razlika u `serve_won` mora
korelirati s ostatkom nakon devigane cijene uz **r >= +0,15 i n >= 40**. Ako da → varijabla
ostaje i razmatra se pojacanje. Ako r ostane ispod +0,05 ili predznak bude negativan →
**varijabla izlazi iz prompta**, jer je onda i korisnikova hipoteza o dubini izmjerena i
pala.

Polja u snapshotu v19: `p*_tourn_form_matches` (dubina), `p*_tourn_form_serve_won`,
`_ace_rate`, `_bp_saved`, `_bp_conv`.

### K12 — ISHOD PROVJERE 13.09.2026 13:40: korisnikova hipoteza o DUBINI POTVRĐENA

Test proveden isti dan, na **pobranom cijelom ždrijebu** (1.255 mečeva, 28 turnira, 0
preskočenih). Uzorak narastao s 23 na 115 mečeva na dubini 3+.

**Sirovo, naspram pobjede — čist monoton gradijent, sve CI izvan nule:**

    oba igrača 1 meč    n=551   r=+0,099   95% CI [+0,014 , +0,183]
    oba igrača 2 meča   n=262   r=+0,121   95% CI [+0,002 , +0,239]
    oba igrača 3 meča   n=115   r=+0,273   95% CI [+0,095 , +0,437]
    oba igrača 4 meča   n=41    r=+0,443   95% CI [+0,190 , +0,639]

Replicira u obje polovice: veliki turniri (7 rundi) r=+0,362 n=43, manji r=+0,219 n=72.

**Koliko velika razlika treba biti** (dubina 3+, po kvartilima razlike u serve_won):

    najlošiji kvartil   −6,3pp   pobjeda 39%
    2. kvartil          −1,5pp   pobjeda 29%
    3. kvartil          +2,7pp   pobjeda 39%
    najbolji kvartil    +8,1pp   pobjeda 64%

**Nakon kontrole cijene (pre-registrirani test):**

    dubina 3+   n=51   r=+0,160   95% CI [−0,088 , +0,394]
    dubina 4+   n=23   r=+0,172   95% CI [−0,206 , +0,491]

**ODLUKA: K12 OSTAJE.** Prag je glasio "r ≥ +0,15 i n ≥ 40 na dubini 3+" — ispunjen je
(r=+0,160, n=51).

**ALI MORAM PRIZNATI MANU U VLASTITOM PRAGU:** zapisao sam ga bez zahtjeva za intervalom
pouzdanosti, a CI prelazi nulu. Prag je dakle ispunjen po slovu, ali priraštaj naspram
tržišne cijene **nije dokazan** na ovom uzorku. Ne pomičem stativu ni u jednom smjeru:
pravilo je bilo zapisano prije podataka i poštujem ga, a manu bilježim da se ne ponovi —
**svaki budući prag mora tražiti i CI koji ne prelazi nulu, ne samo r i n.**

**Što je promijenjeno u promptu (13.09.2026 13:40, era `b2139075` → `adb358d0`):**
pravilo više ne nosi paušalnu ogradu "izmjereno kao slabo" nego **stvarni gradijent po
dubini**, uputu da je na 2 meča najviše tiebreaker a na 3+ pravi dokaz, mjereni prag
veličine (+8pp = 64%), izričitu napomenu da tržište to uglavnom već ukalkulira
(r pada na +0,16 uz CI koji prelazi nulu), i upozorenje da `bp_saved` duboko u ždrijebu
pokazuje u KRIVU stranu (−0,259 na dubini 3+, −0,585 na 4+).

Izmjena je bila besplatna: era `b2139075` imala je **0 analiza**.

**SLJEDEĆA PROVJERA:** kad dubina 3+ s cijenom dosegne n≥100, ponoviti test. Ako CI tada
i dalje prelazi nulu, varijabla se svodi na bilježenje.

**KVAR U PRVOJ VERZIJI TESTA, ZA POUKU:** `tournament/results` ima `player1Id` koji je
**uvijek pobjednik** (1.255 od 1.255). Prva verzija testa nije to znala, pa je ishod bio
konstanta i sirova korelacija izašla točno `r=+0,000 P=1,000` na sva četiri retka.
Nemoguć rezultat je i bio jedini znak. Verzija naspram cijene nije bila prazna nego
**gore** — mjerila je nešto sasvim drugo, a izgledala uvjerljivo (r=−0,332 P=0,019).
Pravilo: prije zaključka provjeri ima li ishodna varijabla uopće varijancu.

### K13 — vijesti o ozljedama kao ulaz u odluku — *25.10.2026 11:24: 21/40, detektor ~70–80% lažnih oznaka; prijedlog K13b s novim detektorom (vidi IZMJERENO 25.10.2026)*

Uveden isti dan. Kanal je do 13.09.2026 10:44 bio mrtav (deveti tihi null), pa varijabla
nikad nije ni postojala u praksi — nema sto mjeriti unatrag.

**Ocekivana ucestalost je mala:** od 66 stavki oba feeda samo 2% je ozljeda. Varijabla ce
biti prazna u velikoj vecini mecheva. To je u redu — cilj je da kad se pojavi, znaci nesto.

**PRAG ZA ODLUKU (zapisano prije podataka):** nakon 2-3 turnira usporediti mecheve s
nepraznim `p*_news` naspram onih bez, **uz kontrolu cijene**. Ako pickovi protiv igraca s
vijescu o ozljedi prolaze bolje uz n>=15 → varijabla ostaje. Ako nema razlike ili je
obrnuta → prompt-pravilo se skracuje na puko biljezenje.

**OGRADA KOJA SE NE SMIJE ZABORAVITI:** `_NEWS_EXCLUDE` mora ostati. Cim jedna vijest s
rijecju "favorite" ili "odds" prodje u prompt, model prestaje biti neovisan o trzistu i
ruse se i konsenzusni bonus i ovo mjerenje. Vidi mjerenje od 08.09.2026 (+11,3% → −2,2%
→ −7,7%).

#### K13 — NOVI IZVOR OD 27.09.2026 11:58: Google News po imenu igrača (samo bilježenje)

Stari kanal (ESPN/BBC) od 13.09. nije dao nijednu vijest o našem igraču (0 od 43 analize).
Od `context_version` 23 svaka analiza bilježi `p1_gnews` / `p2_gnews` (`agent/player_news.py`):
naslovi iz zadnjih 14 dana, `injury_n` = broj naslova s riječju o ozljedi/odustajanju (cijele
riječi; kladioničarski naslovi označeni `bet` istim `_NEWS_EXCLUDE` popisom i ne broje se).
**Model ih ne vidi** (ključ `gnews`, prompt čita samo `news`), pa se era ne mijenja.

**PRAG (zapisan 27.09.2026 11:58, prije ijednog podatka iz novog izvora):** kad se skupi
**40 razriješenih analiza** (v >= 23) u kojima protivnik našeg picka ima `injury_n >= 1`:
edge tih pickova naspram devig cijene mora biti **≥ +5pp veći** od ostalih pickova istog
razdoblja. Ako da → prijedlog korisniku da vijest uđe u odluku (kao kod, ne kao prompt). Ako
razlika ≤ 0 → ostaje samo bilježenje. Snaga: uz n=40 interval je ±15pp, pa je ovo probir, ne
dokaz (`.claude/skills/mjerenje/scripts/snaga.py`). Stari prag (n≥15, kanal u promptu) vrijedi
i dalje za `p*_news`, ali taj kanal je praktički prazan.

### K14 — Davis Cup: analizira se, ne igra se (19.09.2026 11:50)

Uveden kao vlastita razina na korisnikov zahtjev. **Nije kandidat za signal nego za
MJERENJE cijele klase mecheva o kojoj nemamo nijedan redak.**

Sto mu nedostaje, sve odjednom:

    povijest na turniru   nas najjaci prediktor (r=+0,167 P=0,0036)  -> 0 od 799 redaka
    konsenzus kladionica  jedini nalaz koji je prosao kapiju         -> Odds API ga nema
    prosjek s turnira     K12                                        -> <=2 singla, N/A
    korpus                                                           -> 0 od 627

Ostaje ELO (28/28 pokriveno), sezonske serve/return brojke, forma, H2H, gradja, podloga.

**PRAG ZA UKLJUCIVANJE NA TIKET (zapisano prije podataka):** kad skupimo **n>=20**
razrijesenih Davis Cup redaka, usporediti stopu pogodaka s nasom baznom (64,8% na n=455).
Ako je unutar 5pp od bazne i CI ne prelazi nulu prema dolje -> `DAVIS_CUP_ON_TICKETS=True`.
Ako je 10pp+ ispod -> ostaje trajno izvan tiketa i zapisuje se kao zatvoreno.

Mrtve rubbere mjeriti ZASEBNO (`dc_tie_decided` u snapshotu v20): to je jedina situacija
u kojoj ELO i forma po teoriji ne vrijede, pa ako se i to ne vidi u brojkama, znaci da je
uzorak premali za bilo kakav zakljucak.

**OGRADA:** ovo NIJE test "je li nas model dobar na Davis Cupu" nego "koliko kostaju tri
odsutna ulaza". Ne brkati to dvoje pri citanju rezultata.

**STANJE K13 26.09.2026 17:04:** od 13.09. analizirane su 43 utakmice i **nijedna nije
dobila nijednu vijest** (`p1_news`/`p2_news` prazni u 43 od 43). Kanal radi (ESPN + BBC
vracaju stavke), ali ti izvori pisu o vrhu tablice, a ne o igracima ATP 250 turnira koje
analiziramo. Prag od n>=15 ovim izvorom nece se dosegnuti nikad — za K13 treba izvor po
IGRACU, ne opci feed.

### K15 — ATP pobjede u sezoni (26.09.2026 17:04) — **ZATVOREN 27.09.2026 12:16**

**Ishod:** povijesno +0,0pp na 11.139 meča (r veličine razlike = −0,005) — tržište to plaća. Korisnik odobrio zatvaranje. Varijabla se i dalje bilježi (`p*_ctx`), ne ulazi u odluku.

Korisnikov prijedlog ("broj ATP pobjeda u tekucoj sezoni je pokazatelj forme sezone").
Mjereno na 451 razrijesenoj analizi, vrijednosti izracunate NA DAN MECA
(`scripts/measure_player_context.py`, varijabla S1 = pick minus protivnik):

    S1 razlika u broju ATP pobjeda   r(ostatak naspram cijene) = +0,093  P=0,049
                                     bootstrap 95% CI [-0,00, +0,18]  (na samoj granici nule)
                                     polovice korpusa +0,06 / +0,13  (isti predznak)
    po pojasu kvote, gornja naspram donje polovice S1:
        1,00-1,35 +6,1pp | 1,35-1,60 +5,8pp | 1,60-2,00 +4,7pp | 2,00+ +10,8pp  -> +6,0pp
    uz kontrolu ELO razlike (n=275): djelomicni r = +0,17  (sam ELO naspram cijene: +0,025)
    po mjesecima: srpanj -0,09 (n=78) | kolovoz +0,14 (n=250) | rujan +0,08 (n=103)
    postotak pobjeda (S2) slabiji: +0,061, CI prelazi nulu; razredi ipak monotoni
        -9,1 / -7,4 / -1,1 / -0,8 / +2,7pp

Dakle BROJ pobjeda (korisnikova formulacija) nosi vise od POSTOTKA — vjerojatno aktivnost i
razina na kojoj igrac igra, sto trziste djelomicno podcjenjuje. **Ograde:** jedan od sedam
testova istog dana; srpanj ide suprotno; CI dodiruje nulu.

**ODLUKA KORISNIKA 26.09.2026:** čeka se potvrda — K15 danas NE ulazi u odluku.

**PRAG ZA POTVRDU (zapisano 26.09.2026 prije podataka):** na analizama s `match_date` od
**27.09.2026** nadalje (nijedna nije bila u otkrivanju), kad ih se skupi **n>=150**
razrijesenih: (a) r(S1, ostatak) >= +0,05 (isti predznak), (b) ponderirana razlika po
pojasevima kvote >= +3pp, (c) na SPOJENOM uzorku (otkrivanje + potvrda) bootstrap CI ne
prelazi nulu. Sve tri -> S1 ulazi kao BONUS u `_score_combo` (kao konsenzus), NE u prompt.
Ako (a) padne ispod nule -> odbacuje se. Mjeriti istom skriptom, bez izmjene definicije.

### K16 — GS iskustvo u zavrsnicama (26.09.2026 17:04) — **ZATVOREN 27.09.2026 12:16**

**Ishod:** povijesno +1,1pp u QF/SF/F (n=826, interval −2,0 do +4,1) — daleko od praga +5pp. Korisnik odobrio zatvaranje. Varijabla se i dalje bilježi.

Korisnikov primjer: finale US Opena 2026, Zverev (12 GS polufinala, 5 finala) protiv
Sheltona (2 / 0) — "vidjelo se da je Zverev mirniji". Na CIJELOM korpusu hipoteza NE
prolazi: razlika u broju GS polufinala r = -0,050 (obje polovice negativne), a asimetrija
"samo jedan ima GS polufinale" daje +0,9 / -1,2 / +0,3pp — trziste GS pedigre vec placa.
Ali korisnik govori o ZAVRSNICAMA, i ondje:

    QF/SF/F, samo NAS pick ima GS polufinale   n=16   +8,1pp naspram cijene
    QF/SF/F, samo protivnik ima                n=2    (ne moze se procijeniti)
    (bez 31 retka Chengdu/Hangzhou s krivom rundom; s njima n=18, +10,7pp)

**PRAG (zapisano prije podataka):** kad QF/SF/F s asimetrijom iskustva dosegne n>=40 na
novim mecevima (od 27.09.2026), rub strane s iskustvom mora biti >= +5pp. Tada se razmatra
bonus u zavrsnicama. Uzorak raste ~4-5 meceva mjesecno, pa je ovo pitanje od nekoliko
mjeseci — NE ubrzavati spustanjem praga.

### STANJE KANDIDATA 26.09.2026 20:46 — mjeri ih `scripts/measure_candidates.py`

Svi pragovi ostaju kakvi su zapisani; skripta ih drži na jednom mjestu. Stanje danas:

    K5   kvota 1,35-1,43 od 07.09.     n=6   +14,7pp   CEKA (treba n>=20)
    K10  pojas 1,35-1,65 od 14.09.     n=10  -24,1pp   CEKA (treba n>=25 po pojasu)
    K11  R16+QF od 14.09.              n=0             CEKA — od 26.09. runde su RUCNE, pa se
                                                       K11 prvi put mjeri bez sumnje u oznake
    KONS konsenzus >=+1 od 08.09.      n=2             CEKA — Odds API ne pokriva ATP 250;
                                                       prag "60 do 31.10." vjerojatno nedostizan

### K17 — High scouting profil našeg picka (26.09.2026 20:46) — **PAO 18.10.2026 10:09, ZATVOREN**

**Ishod (prag ispod, zapisan 26.09.):** od 27.09. n=43, edge **+13,7pp** (> 0 → odbaciti). Kazna
−3pp se ne uvodi (nikad nije bila u kodu — `_apply_measured_penalties` ima samo Med-Low,
autsajdera i pojas 65–68). Spojeno STARO+NOVO −0,3pp (n=96); +13,7 nose Peking (+24,5, n=16) i
Hangzhou (+28,8, n=5). Svih 5 razina scoutinga okreće predznak između uzoraka → profil ne nosi
informaciju; i postojeća kazna Med-Low je ista nestabilna obitelj (NOVO n=6). Revizija 18.10.

    High      n= 52 | 63,5% | tržište 75,9% | edge -12,4pp | ROI -22,3%
    razdoblja: do 26.08. -14,0pp (n=28) | poslije -10,6pp (n=24)   <- isti predznak
    naspram konsenzusa (ne SuperSporta) i dalje -8,6pp -> nije "SuperSport skraćuje imena"
    usporedba: Med-High +6,5pp (n=101) | Med +2,4pp (n=116) | bez profila -0,3pp (n=101)

Medvedev 3-4, De Minaur 3-4, Rublev 2-3. Mehanizam neutvrđen (plaćamo ime?).
**PRAG (zapisan prije podataka):** sljedećih 30 pickova s High profilom (od 27.09.2026):
edge ≤ −5pp → kazna −3pp u `_apply_measured_penalties`; edge > 0 → odbaciti.

### K18 — hard ATP 250 (26.09.2026 20:46) — KANDIDAT, jedno razdoblje — *25.10.2026 11:24: OKINUT po slovu (prvih 30 −5,3pp), sav signal iz jednog tjedna; odluka korisnika, preporuka ne uvoditi (vidi IZMJERENO 25.10.2026)*

    hard ATP 250 + Davis Cup   n=63 | 50,8% | tržište 62,0% | edge -11,2pp | ROI -23,6%
    isto bez R16/QF            n=53 | edge -11,3pp       <- nije samo rupa u R16/QF
    clay ATP 250               n=56 | edge  +3,7pp
    GS/1000/500 na hardu       n=294 | edge +1,2pp
    po turnirima: Winston-Salem -12,7 (35) | Hangzhou -11,3 (10) | Chengdu -8,8 (9)

Ograda: sve u drugom razdoblju (hard 250-ice su od kraja kolovoza); ATP 250 je i tamo gdje
Odds API ne pokriva, pa je dio učinka možda nedostatak tržišne kočnice (popravljen danas).
**PRAG:** sljedećih 30 hard ATP 250 pickova (od 27.09.2026): edge ≤ −5pp → najviše jedna
takva noga po tiketu; edge > 0 → odbaciti.

### K19 — povratak nakon pauze (26.09.2026 20:46) — KANDIDAT s tržišnim dokazom

Na berbi s kvotama (19.168 nastupa, simetrično uzorkovanje — oba igrača u berbi):

    pauza <= 7 dana   +0,2pp | 8-20  -0,2pp | 21-41  -1,9pp (n=656) | >= 42  -3,3pp (n=473)
    >= 42 dana po godinama: -2,4 / -0,9 / -9,6 / -2,9pp   <- negativno sve 4 godine

Tržište povratak nakon pauze sustavno blago precjenjuje. Nedavna PREDAJA to ne radi
(+3,5 naspram +2,4pp — tržište ozljede već cijeni).
**PRAG:** 40 naših mečeva (od 27.09.2026) u kojima pick ILI protivnik ima `days_rest` ≥ 21:
pick s pauzom < 0 i protivnik s pauzom > 0 → ±2pp; obrnuto → odbaciti.

### K20 — "Intuicija": naučeni signal u sjeni (27.09.2026 12:34) — KANDIDAT, samo bilježenje — *25.10.2026 11:24: 1. provjera (n=209) r = −0,035 → NIJE PROŠLA, uči dalje*

Korisnikova želja: varijabla koja se kroz vrijeme razvija i sama prepoznaje dobar rizik, npr.
autsajdera. Kod: `agent/intuicija.py` (model), `scripts/intuicija_prior.py` (prior iz povijesti
-> `config/intuicija_prior.json`), `scripts/intuicija_report.py` (izvještaj). U dnevnom runu se
računa TEK nakon što je tiket složen i upisuje u `context_snapshot["intuicija"]` — ne može
utjecati na izbor.

> **PRIOR OSVJEŽEN 18.10.2026 15:46** (zapisani postupak nakon novog `2026.xlsx`): 12.434 meča
> umjesto 12.322, ista jačina kazne (λ = 1000), r na neviđenim +0,034 (bilo +0,036); koeficijenti
> pomaknuti neznatno. Stari prior: `.cache/prije_osvjezavanja_2026-10-18/intuicija_prior.json` i git.
> Kapija K20 se ne mijenja (procjene su zapisane u trenutku analize).

**Kako radi:** logistička regresija s pomakom (polazi od devigirane SuperSport cijene i uči
samo odstupanje), jaka L2 kazna, jačina izabrana vremenskim rezom; ako nijedna jačina nije
bolja od čiste cijene na novijih 30% mečeva, sloj ŠUTI (0). Dva sloja: tržišni prior naučen
na 12.322 povijesna meča (pojas kvote, Grand Slam, razina, podloga, pauza 21+) i naš sloj
naučen iznova u svakom runu na svim riješenim analizama (+ ELO razlika, forma, konsenzus,
scouting, vijesti o ozljedi, Claudeovo razilaženje s cijenom). Ocjenjuje obje strane meča
(normalizirano da je zbroj 1) i diže zastavicu kad strana koju Claude NIJE odabrao, a
autsajder je, dobije +3pp ili više.

**Stanje pri uvođenju (27.09.2026 12:34):** prior r = +0,036 na 7.394 neviđene strane (mali, ali pozitivan
— kratki favoriti i favoriti 1,35-1,43 oko +2,9pp, Grand Slam 1,30-1,50 +3,2pp, pauza 21+ −2,3pp).
Naš sloj (480 analiza) aktivan, najjače: "High" scouting −2,9pp, razlika u formi −1,8pp,
konsenzus +1,3pp. "Kako bi prošla da je postojala" (uči samo na ranijim mjesecima): r = +0,013
[−0,125, +0,151], n=202 strane — **vještina NIJE dokazana**; autsajderi s +3pp: n=12, stvarno −4,7pp.

**PRAG (zapisan 27.09.2026 12:34, prije ijedne zapisane procjene):** kad bude **300 riješenih pickova s
procjenom** zapisanom prije meča: (a) r(procjena za naš pick, stvarni ostatak naspram devig
cijene) ≥ **+0,12** s intervalom iznad nule; (b) gornja trećina procjena ima edge ≥ **+3pp** i
barem 3pp više od donje trećine; (c) r > 0 u obje vremenske polovice. Sve tri → prijedlog
korisniku: bonus u `_score_combo` razmjeran procjeni (tada i za autsajdere). Inače uči dalje u
sjeni i ponovno se mjeri svakih +300. Posebno za autsajdere: kad zastavica ima **40 riješenih
slučajeva**, stvarni edge tih autsajdera mora biti ≥ +3pp da bi se o njima uopće razgovaralo.
Snaga: uz n=300 interval za r je ±0,11. Mjeri: `python scripts/measure_candidates.py --only K20`
i `python scripts/intuicija_report.py`.

**IZMJENA PRAGA 27.09.2026 12:49 (korisnikova odluka, PRIJE ijedne zapisane procjene): DVIJE PROVJERE.**
Prva kod **150** riješenih procjena, druga kod **300**, poslije svakih +300; nakon svake provjere
Intuicija nastavlja učiti. Isti kriterij na svakoj, samo uz manji uzorak traži jači dokaz:
r ≥ max(0,12 ; 1,96/√n) — uz 150 to je **r ≥ 0,16**, uz 300 **r ≥ 0,12** — plus (b) i (c) gore.
Izračunato: bezvrijedna intuicija prođe ~2% po provjeri (~3-4% preko obje); dobra (r=0,15) prođe
uz 150 u 45%, uz 300 u 70% slučajeva. Pravilo živi na JEDNOM mjestu: `agent.intuicija.gate_status`
(koriste ga measure_candidates, intuicija_report i intuicija_status_email). Mail sa stanjem stiže
sam 15.11.2026 i 15.01.2027 (`.github/workflows/intuicija_status.yml`).

### K21 — favorit u QF/SF/F protiv boljeg servera (04.10.2026 19:37) — KANDIDAT, skeptik SUMNJIVO

**Korisnikova ideja** (04.10.2026): igrač koji u četvrtfinalu naiđe na protivnika slabijeg po
ELO-u, ali jačeg po holdu ili asovima, češće pada. Igrač-specifična verzija nije mjerljiva
(medijan 4 četvrtfinala po igraču u 2023–26, samo 62 igrača s 10+), pa je testirana opća
verzija u povijesnom labu (`revizije/2026-10-04/skripte/r_lab2.py`, pragovi
`PRAGOVI_DODATAK_2.md` 19:07).

    favorit po cijeni u QF/SF/F, protivnik ...           n     edge naspram poštene cijene
    ≥3pp bolji hold % (365 dana prije meča)   QF1       296   −5,8pp [−11,5, −0,1]  2022-23 −4,5 / 2024-26 −7,1
    ≥2 asa na 100 servisnih poena više        QF2       554   −5,0pp [ −9,0, −1,0]  −4,8 / −5,2
    SPOJENO (hold ILI asovi) = K21                      617   −4,1pp [ −7,8, −0,3]  −3,8 / −4,3
    kontrole: isti uvjet u RANIM rundama +2,0 / +2,6pp; samo R16 +2,9 / +2,1pp; svi favoriti u QF+ +0,1pp
    po podlozi: hard −10,2 / −5,0 | zemlja +2,5 / −3,8 | trava −12,6 / −7,5 (malo n)

**Skeptik (04.10.2026): SUMNJIVO.**
- Holm preko svih 23 testa sesije: QF1 P = 0,99, QF2 P = 0,34.
- QF1 i QF2 su gotovo isti signal (78,7% preklapanja, r = 0,73 između margina).
- Nema neovisne potvrde: polovice su iz istog izvora.
- Moguće preklapanje s "vrućim servisom ovaj tjedan" (prozor uključuje ranije runde turnira).
Curenje provjereno: OK.

**PRAG ZA POTVRDU (zapisan 04.10.2026 19:37, prije ijednog novog podatka):** samo SPOJENO pravilo,
samo na NEOVISNIM ATP mečevima nakon 13.09.2026 (tržišni podaci, ne samo naši pickovi), kad
ih bude ≥ 150. Naredba: `python revizije/2026-10-04/skripte/r_lab2.py --od=2026-09-14` nakon
osvježavanja `.cache/tennis-data/2026.xlsx` (i 2027) te `lab_data.py` / `r_lab.py`.
- **PROLAZI:** edge ≤ −4pp, 95% interval ispod nule i obje polovice NOVOG razdoblja negativne →
  prijedlog korisniku: kazna za takvu nogu pri izboru tiketa (`_score_combo`), NIKAD u promptu.
- **PADA:** edge ≥ 0.
- Inače čeka sljedeći blok od +150.

Snaga: uz n=150 interval je ±7,6pp, pa se vidi samo učinak ≥ 9–10pp; za pouzdanih −5pp treba
~400–560 mečeva. Takvih mečeva ima ~130 godišnje, pa je prva provjera realno **za ~godinu dana**.
Do tada u model ne ulazi ništa.

> **MEĐUSTANJE 18.10.2026 15:46** (korisnik je osvježio `2026.xlsx`, podaci do 06.10.2026; LAB
> obnovljen, TML do 14.10.): od 14.09. ima 112 novih mečeva s cijenom (Pinnacle nakon 13.09. nema →
> prosjek kladionica). K21 spojeno pravilo: **n = 9** od potrebnih 150, edge −0,0pp [−32, +32] →
> **ČEKA**. Ispis: `.cache/rev_2026-10-18b/out_k21_od_2026-09-14.txt`.

### K22 — ELO jaz i servis/povrat nose nešto povrh cijene OD 14.09.? (18.10.2026 10:09) — KANDIDAT

Iz testa težina J2 (revizija 18.10., `r_nasi.py`): na hard pickovima od 04.08. predstavnik
kategorije naspram ostatka nakon cijene. Kriterij za promjenu težina (obje polovice) NIJE
ispunjen, ali polovice se jako razlikuju (skeptik: "nešto se promijenilo 14.09."):

    ELO jaz na podlozi       do 13.09. r=-0,014 (n=249) | od 14.09. r=+0,190 [+0,04, +0,33] (n=169)  z razlike 2,0
    servis + povrat          do 13.09. r=-0,108 (n=257) | od 14.09. r=+0,182 [+0,03, +0,32] (n=169)  z razlike 2,9
    od 14.09. po trećinama   ELO -8,8 | -8,2 | +13,5pp ; servis+povrat -4,0 | -12,3 | +12,3pp
    pick vodi i u ELO-u i u servisu+povratu  od 14.09. +1,9pp (n=119) | ostali -8,6pp (n=50)

Moguća objašnjenja: popravljeni ulazi (13.09. četiri kvara; 04.10. ELO duplikati i tuđi ELO)
pa model sada vidi točnije brojke — ILI šum (takvo okretanje je u projektu dosad bilo šum: K1,
K17). Holm u obitelji J (7 kategorija × 2 polovice) ≈ 0,2. Povijest ELO nema (rang +0,007 na
12.302 → tržište rang plaća).

**PRAG ZA POTVRDU (zapisan 18.10.2026 10:09, prije ijednog novog podatka):** na sljedećih **150
hard pickova od 19.10.2026** (bez `elo_suspect`), uz kontrolu cijene:
- **PROLAZI:** r(ELO jaz, ostatak) ≥ +0,10 ILI r(servis+povrat jaz, ostatak) ≥ +0,10, uz 95%
  interval iznad nule, I isti predznak u obje polovice tih 150 → prijedlog korisniku: bonus pri
  izboru tiketa (`_score_combo`) ili veća težina — odluka korisnika.
- **PADA:** oba r ≤ 0.
- Inače čeka +150. Snaga: uz n=150 interval r je ±0,16, pa je ovo probir.

> **DOPUNA 18.10.2026 15:11 (revizija, drugi dio; kritičar):** povijest K22 NE podupire —
> r(ELO jaz, ishod − cijena) = +0,00 [−0,02, +0,02], servis+povrat +0,02 (LAB, n=12.320). LAB test
> B4b (ELO +50 potvrđen servisom/povratom i protivnicima) izgledao je +1,6pp, ali 98% su favoriti;
> uz kontrolu pojasa +0,4pp [−0,9, +1,7]. Rez "od 14.09." odabran je naknadno. Mjerenje ostaje
> (`measure_candidates.py`, K22 od 19.10.), prag se ne mijenja.

### K23 — "zalet protiv boljih servera" se precjenjuje (S1, obrnuti smjer) (18.10.2026 10:09) — HIPOTEZA

LAB (`revizije/2026-10-18/skripte/r_lab3.py`, test S1, strogi datum): igrač A dobio je zadnja 2
meča (≤ 21 dan) protiv protivnika s holdom ≥ 3pp boljim od svog, a današnji protivnik B također
ima hold ≥ 3pp bolji. Hipoteza je bila "+", izmjereno suprotno:

    n=550  edge A -5,1pp [-8,7, -1,5]  2022-23 -3,7 / 2024-26 -6,1  Holm (36 testova) 0,21
    s prosjekom kladionica -5,5pp (Holm 0,11); bez strogog datuma -5,3pp (Holm 0,11)
    ostatak iste skupine -0,4pp (n=2.287); glavni učinci: niz +0,5, hold +0,2 -> učinak samo u konjunkciji

Po pravilu PADA (smjer suprotan hipotezi). Skeptik: "ni nula ni nalaz"; ne citirati kao potvrdu
K21 (isti LAB). Kao NOVA hipoteza obrnutog smjera: bolji server protiv igrača u takvom zaletu
prolazi bolje od kvote.

**PRAG ZA POTVRDU (zapisan 18.10.2026 10:09):** na ATP mečevima nakon 13.09.2026, kad se osvježi
`.cache/tennis-data/2026.xlsx` (korisnik skida ručno; isti postupak kao K21): edge A ≤ −3pp, 95%
interval ispod nule, obje polovice novog razdoblja negativne → prijedlog: ne kažnjavati
"giant-killer" priču kad je naš pick bolji server (izbor, ne prompt). PADA: edge ≥ 0. Snaga:
~600 novih mečeva daje ~25–30 takvih slučajeva godišnje — realno provjerljivo tek 2027.

> **MEĐUSTANJE 18.10.2026 15:46** (isti osvježeni LAB; `r_lab3.py --od=2026-09-14`, nova opcija):
> S1 na novim mečevima **n = 4** (−35,8pp, PREMALO); dubina 4+ n = 1. → **ČEKA** (2027).

### K10b — izričita sklonost pojasu kvote umjesto `edge_bonus` (18.10.2026 10:09) — ZA ZASEBNO TESTIRANJE

Akcija koju traži K10 (vidi ISHOD 18.10. uz K10). Ne uvodi se bez korisnika. Oprez prije testa:
oblik se nije ponovio (pojas 1,65–1,85 +12,3pp → −6,9pp), a povijest kaže da favoriti u
1,35–1,43 prolaze BOLJE od kvote (+3,7pp [+1,3, +6,1]) — izričit bonus mogao bi rezati pojas koji
tržište ne kažnjava. **Plan:** (1) simulacija `_find_best_combination` s varijantama bodovanja
(bez `edge_bonus`; s bonusom samo za 1,20–1,35) na danima od 14.09. — samo opis; (2) prag za
potvrdu zapisati PRIJE sljedeća dva dovršena turnira; (3) odluka korisnika.

### K24 — Nose (nose-v1) u sjeni: vlastita procjena, mine i autsajderi (18.10.2026 12:41; zapis 15:11) — EKSPERIMENT

Korisnikova odluka "1a". Kod: `agent/nose.py`; u dnevnom runu nakon slaganja tiketa →
`context_snapshot["nose"]`; prikaz na Dnevnom listiću. **Ne ulazi u odabir pickova ni tiketa.**
Definicije (zapisane PRIJE računanja, `revizije/2026-10-18/PRAGOVI_B_2026-10-18.md` 12:20, U4 skala
12:22):
- **Pick Quality:** vlastita vjerojatnost = 0,80·ELO + 0,20·model poena (W_ELO procijenjen na LAB
  P1 2022–23 prema ishodu), pouzdanost;
- **Mine Risk:** M1–M5;
- **Upset Value:** U1–U4;
- **Ticket Suitability:** IZBJEGAVAJ = NO PICK ako je vlastita < 50% ili 2+ mine.

Faza A bez ijednog tržišnog polja, zamrznuta SHA-256 prije faze B (usporedba s devigiranom cijenom).

**Povijest prije starta** (LAB, vremenski odvojeno; 18.10.2026):
- N7 strana kojoj Nose daje 5pp+ više od cijene: −1,9pp (P2 −2,3), uz kontrolu pojasa −1,5pp
  [−2,6, −0,4];
- N5 mine −1,0pp, N6 autsajderi −2,6pp (oba PALA);
- točno pravilo IZBJEGAVAJ na favoritu: +1,3pp uz pojas (n=1.824).

Na našim analizama (razvojni uzorak): IZBJEGAVAJ −8,8pp ±13,5 (n=50), uz pojas −6,9pp [−21,9,
+8,3] — nije dokaz.

**PRAG (12:20; postupak ispravljen NAKNADNO 15:05 po kritičaru, PRIJE ijednog podatka):** svi
riješeni zapisi `nose-v1` od prvog runa, naspram devigirane SuperSport cijene, bez `elo_suspect`.
- **G1 mina** (pickovi IZBJEGAVAJ):
  - probir na PRVIH 60 (edge ≥ +3pp → PAO);
  - odluka na PRVIH 150 po datumu: POTVRĐEN ako je edge ≤ −5pp, interval ispod 0, obje
    polovice < 0 I razlika naspram ostalih pickova u istom pojasu cijene ≤ −3pp;
  - PAO ako je edge ≥ 0 ili je razlika ≥ 0; inače NEJASNO.
- **G2 vrijednost na protivniku:** zrcalno (+5pp, +3pp).
- **G3:** r(vlastita − cijena, ishod − cijena) ≥ +0,10 na PRVIH 300, interval iznad 0, obje
  polovice > 0.
- Presuda je ZAMRZNUTA; nova provjera samo uz nose-v2 (kapija od nule). G1 i G2 dijele ~76%
  redaka i broje se kao jedan dokaz.
- Snaga: uz n=150 ±7,6pp; za stvarnih −5pp snaga ~22%; uz povijesna očekivanja šansa prolaza
  ~1% po kapiji (kritičar).
- POTVRĐEN znači samo "smije se predložiti"; ulazak u odabir uvijek odobrava korisnik.

Mjeri: `python scripts/measure_candidates.py --only K24` (pravilo u `nose.gate_status`).

> **ULAZI UŽIVO (18.10.2026 15:47, PRIJE ijednog podatka; PRAGOVI_B NAKNADNO 15:47):** servis,
> povrat i 1./2. servis iz **TML-a za zadnjih 12 mjeseci** kad ga imaju oba igrača (≥ 300 + 300
> poena), inače oba na RapidAPI karijeri. Izvor je u `nose.inputs.servis_povrat`. Usporedna
> varijanta samo na karijeri bilježi se kao `nose_karijera` i ne ulazi u K24. Provjera prije
> uključivanja: pokrivenost 99–100% igrača i mečeva; skala povrata 4,5pp niža od RapidAPI-ja.
>
> **NAPOMENA 18.10.2026 19:43 (kritičar, PRAGOVI_C):** čisti TML 12 mj. (sve razine) na povijesti
> procjenjuje igrače LOŠIJE od karijere (2024–26 −0,0064 log-gubitka, 2026. −0,017), osobito kod
> igrača s puno Challengera. Definicije i pragovi K24 se NE mijenjaju (Nose je provjeren na tim
> ulazima); uz presudu se opisno uspoređuje i `nose_karijera`. Dodatak 16:53 (Nose na mješavini)
> povučen je prije ijednog podatka.

### K18 i K10 — ODLUKA 25.10.2026 11:46: okinuti, NE uvode se
Korisnik je 25.10.2026 odluku prepustio preporuci ("provedi sve što smatraš korisnim"). Preporuka iz
revizije 25.10. (točka 6), sa skeptikovim razlozima:
- **K18:** okinut po slovu (prvih 30 po datumu i vremenu analize −5,3pp), ali 74 od 88 pickova su
  Lyon/Bruxelles/Almaty (bez njih +14,5pp, n=14). Razlika prema 500/1000 je samo u kvotama ≥ 1,65,
  tržište na hard 250 nema rupu (+0,1pp, n=2.311), a pravilo bi od 27.09. blokiralo 4 od 13
  tiketa (i jedini dobitni). → **ne uvodi se**; nova serija je K18b.
- **K10:** formalno ispunjen 18.10. i 25.10., ali oblik se nije ponovio (dulje kvote lošije, ne
  bolje), a tržišni pojasevi su ravni (±2pp). → ne provodi se; izričit bonus po pojasu ostaje
  zasebni kandidat K10b.

### K18b — hard ATP 250, NOVA serija (25.10.2026 11:46) — KANDIDAT, prag prije podataka
Ista hipoteza kao K18 (naši pickovi na hard 250-icama prolaze lošije od cijene), ali na mečevima
koji nisu ni u K18 ni u tjednu na kojem je okinut. **PRAG:** prvih 30 hard ATP 250 pickova od
26.10.2026, poredak (datum, vrijeme analize): edge ≤ −5pp → prijedlog korisniku "najviše jedna
takva noga po tiketu"; edge > 0 → K18 se zatvara; između → nejasno. Snaga: n=30 → ±17pp (probir,
ne dokaz). Realno: 250-ice na hardu sljedeće su tek u siječnju 2027. Mjeri `measure_candidates.py`
(K18b).

### K13b — vijest o OZLJEDI protivnika, strogi detektor v2 (25.10.2026 11:46) — KANDIDAT, prag prije podataka
K13 (27.09.) broji naslove s riječju o ozljedi bilo gdje u naslovu; revizija 25.10. našla je da su
od 15 takvih oznaka stvarne samo 3–5 (umirovljenje karijere, walkover, tuđa ozljeda). K13 se NE
preoznačava (21 viđeni slučaj ostaje kako je zapisan). Od 26.10.2026 dnevni run uz stari bilježi i
**strogi detektor v2** (`agent/player_news.strict_injury`, `p*_gnews.injury_n2`, `inj_v: 2`):
riječ o tijelu/bolesti najviše 4 riječi od prezimena igrača; riječ o odustajanju samo iza prezimena;
"retire" samo uz riječ meča i nikad uz umirovljenje karijere; kladioničarski naslovi se ne broje.
Pravilo je određeno na naslovima 19.–25.10. (24 primjera u testu), PRIJE ijednog podatka za K13b.
**PRAG:** prvih 30 riješenih pickova od 26.10.2026 u kojima protivnik ima `injury_n2 ≥ 1`, poredak
(datum, vrijeme analize): edge te skupine ≥ edge ostalih pickova istog razdoblja + 5pp → prijedlog
korisniku (kao kod u odabiru, nikad u prompt); razlika ≤ 0 → samo bilježenje; između → nejasno.
Snaga: n=30 → ±17pp — probir. Učestalost: ~3% igrača ima stvarnu vijest, pa 30 slučajeva treba
~1.000 analiza (realno proljeće 2027.). Model vijesti NE vidi (ključ `gnews`).

### K25 — TML servis/povrat SAMO GLAVNOG ŽDRIJEBA bolje procjenjuje igrače od karijere svih razina (18.10.2026 17:34) — HIPOTEZA

Naknadni nalaz kritičara pri provjeri prelaska na TML (PRAGOVI_C, "REZULTATI I ODLUKA"): kad se iz
12-mjesečnog prozora i karijere izbace Challengeri i kvalifikacije, mješavina 12 mj. + karijera
(K = 1.500) bolja je od karijere na istim mečevima svake godine 2022–26 (+0,013 do +0,019
log-gubitka, i 2026.), u pojasu favorita 0,50–0,80 +0,009 do +0,012 (n = 11.087;
`revizije/2026-10-18/skripte/skeptik_tml/main_only3.py`). Mehanizam: postotci osvojeni protiv
slabijih protivnika nisu usporedivi s onima s Toura. Ograda: jedan od ~40 rezova, na viđenim
podacima — zato ne smije u odluku bez potvrde. Ni ovo ne tvrdi da model tuče cijenu.

**PRAG ZA POTVRDU (zapisan 18.10.2026 17:34, prije gledanja; puni tekst u PRAGOVI_C):**
- **Test A (odmah, besplatno):** TML glavni ždrijeb 2010–2019 (godine koje nitko nije gledao),
  mješavina glavnog ždrijeba naspram karijere glavnog ždrijeba, model poena kao u `c_tml_lab.py`.
  PROLAZI: bolja za ≥ 0,005 u obje polovice (2010–14, 2015–19) i u ≥ 8 od 10 godina; PADA: ≤ 0 u
  bilo kojoj polovici. Snaga: ~25.000 mečeva, SE ≈ 0,0012.
- **Test B (budući mečevi od 19.10.2026, n ≥ 700, ~prosinac):** cijeli postupak (glavni ždrijeb kad
  oba igrača imaju ≥ 300 + 300 poena u karijeri glavnog ždrijeba, inače karijera svih razina)
  naspram karijere svih razina (≈ RapidAPI). PROLAZI: bolji za ≥ 0,005, 95% interval iznad nule
  (klaster turnir), isti predznak u obje polovice; PADA: ≤ 0. Snaga: n = 700 → SE ≈ 0,007.
- Tek kad prođu A i B → prijedlog nove ere (pragovi po kvantilima, pričuva, jedan plaćeni poziv).
  Osnova za implementaciju postoji na grani `tml-era-881d89f8`.

### IZMJERENO 25.10.2026 11:24 — revizija Lyon/Bruxelles/Almaty (A1–A4, C1–C4, D, N, H2, G2, E, F)

Izvještaj: `revizije/2026-10-25/REVIZIJA_2026-10-25.md`; kartice 33 poraza:
`revizije/2026-10-25/KARTICE_GUBITAKA_2026-10-25.md`. Pragovi zapisani prije računanja:
`revizije/2026-10-25/PRAGOVI_REVIZIJA_2026-10-25.md` (10:20; NAKNADNO 10:32). Kritičar (skeptik):
**SUMNJIVO** — "nema kvara, nule drže" drži; dvije greške u revizijskim skriptama (očekivani broj
dobitnih tiketa, nestabilan poredak za K18) i tri preglasne tvrdnje (pravilo 15 "podloga",
"tijesni porazi", "analize gubitka rade") ispravljene prije upisa. **U modelu ništa nije
mijenjano** (korisnikova uputa: prvo zaključak).

    TJEDAN (19.–25.10., hard dvorana)  n=74  41W  edge -10,8pp ±10,4  ROI -24,1%  ostatak poena -0,25pp ±1,15
      kvota >= 1,65 ("novčići")        n=15   2W  edge -36,2pp (oček. 7,4 pobjede; P=0,4%, uz 8 pojaseva 2,5%)
      kvota <  1,65                    n=59  39W  edge  -4,4pp
    NOVO (od 27.09., era bccf4742)     n=214      edge  -3,3pp ±6,2
    tiketi 19./21./22.10.: 3 izgubljena, svaki na jednoj nozi; od 05.10. 0 od 7 (oček. 1,34);
    od 27.05. 5 od 69 (oček. 7,5, P(<=5) ≈ 23%)

**Ishodi (pravila zapisana ranije):**
- **K1** (prva 3 tjedna praga 63): 21 dan → 7 s tiketom, 10 bez (od toga je prag odlučio 3 dana:
  20., 23., 24.10.), 4 bez runa. r(pouzdanost − cijena, ostatak) −0,03 STARO / −0,09 bccf4742 /
  −0,13 TJEDAN → prag se ne pomiče; praćenje zatvoreno. Ponovna analiza istog para dala je nižu
  pouzdanost u 8 od 8 slučajeva (prosjek −4,1).
- **H2 pravilo 15** (prag 18.10.2026 09:31): n=72, −8,1pp [−18,9, +2,7], u istom pojasu −6,2pp →
  po slovu "podloga", ALI svih 20 novih je iz TJEDNA (bez njega −3,5pp, n=52), polovica "pick ≤ 50%"
  okrenula se s +1,8 na −30,3pp (n=12) → **NEJASNO**. Pravilo ostaje kakvo jest (nije kandidat za
  brisanje ni za pojačanje).
- **K18 OKINUT po slovu** (prvih 30 po datumu i vremenu analize −5,3pp; drugi poreci −5,9 / −8,4;
  svih 88 −6,8pp) → **odluka korisnika**. Preporuka NE uvoditi: 74 od 88 su TJEDAN (bez njega +14,5pp,
  n=14); razlika prema 500/1000 samo u kvotama ≥ 1,65; LAB +0,1pp (n=2.311); pravilo bi od 27.09.
  blokiralo 4 od 13 tiketa, među njima jedini dobitni. Revizijska skripta je prvo dala −2,0pp zbog
  nestabilnog poretka (ispravljeno); `measure_candidates.py` se naknadno NE mijenja.
- **K10 okinut** (formalno već 18.10., opet sada) → odluka korisnika; oblik se nije ponovio (dulje
  kvote lošije), LAB pojasevi ravni (±2pp) → preporuka ne provoditi, K10b ostaje.
- **K20** 1. provjera (n=209): r = −0,035 (treba ≥ 0,14) → **NIJE PROŠLA**, uči dalje (sljedeća 300).
- K5 35/100, K13 21/40 (grupa zagađena lažnim oznakama ozljede), K19 22/40, K22 74/150, K24 G1 10/60,
  L4 3/30, noćna 35/60, ljevaci 162/300 — ČEKA.

**IZMJERENO I ODBAČENO (ne otvarati bez novog izvora) — LAB 12.436 mečeva, poštena cijena, strogi
datum, aktualni turnir isključen (`revizije/2026-10-25/skripte/r_lab_d.py`; skeptik neovisno
provjerio 6.000/6.000):**

    D1 prosjek pobjeda na zadnja 3 turnira ATP razine (120 d), +1 više   n=4.137  +0,0pp [-1,3, +1,3]  +0,1 / -0,0  PADA
    D3 "vruć" (SF+ na nekom od 3, protivnik bez QF)                        n=2.473  -0,1pp                            PADA
    D4 "hladan favorit" (0 pobjeda na sva 3) — smjer obrnut                n=  116  +7,9pp [-0,8, +16,6] Holm 0,44   PADA
    D5 "vruć autsajder"                                                    n=  523  +0,8pp                            PADA
    D6 sve razine (i Challengeri)                                          n=5.762  -0,2pp                            PADA
    D7 kao D1 uz sličnu formu 10                                           n=1.240  +0,7pp                            PADA
    N1a ritam (2+ meča u 7 d) protiv odmora (0 u 10 d)                     n=1.394  +0,0pp [-2,3, +2,3]               PADA
    N1b kvalifikant u ritmu, prvi meč glavnog ždrijeba                     n=  560  -0,6pp                            PADA
    N1c ritam protiv odmora, autsajder                                     n=  501  -2,0pp                            PADA

Korisnikova ideja "koliko je daleko došao na zadnja 3 turnira": dublji pobjeđuje 67,9%, ali je
favorit u 86% → tržište to plaća (r povrh cijene +0,001, n=8.821). Na istom povijesnom uzorku
ukupno 88 testova.

**Opis (naši podaci, ne kandidati):** forma × kvaliteta ≥ 0,30 za pick NOVO −9,0pp u istom pojasu
(n=116), STARO hard −4,2pp; ritam protiv odmora na našima oba smjera negativna (šum); dob NOVO
r=+0,21 naspram STARO −0,05 i LAB −0,02 → okretanje predznaka, ne kandidat; G2 težine (kriterij J
18.10.): 0 od 8 kategorija → težine v18 ostaju (automatska petlja zamrznuta, nova verzija nije
nastala); prvo kolo 250/500 NOVO −9,9pp u pojasu (n=83), LAB favoriti u prvom kolu +3,8pp → opis.

**Analize gubitaka (C3):** 17/17 "No model change", 0 dodijeljenih [GATE PASSED] — ali prompt
analize sam traži taj ishod, pa to nije neovisna provjera kvalitete. ~13–14 od 17 "Worth
measuring" već izmjereno; statička tablica pojaseva u `_LOSS_BASE_RATES` (26.09.) proturječi
živim brojkama (1,60–1,75 +4,8 naspram −0,5pp; ATP 250 +14,5 naspram −6,8pp).

**Vijesti (E):** panel ESPN/BBC: 12 pogodaka za 80 igrača (6 pokrivenih), 4 o pravom igraču i
≤ 14 dana (33% < 50%) → **pada** (prezime "Fils" pogađa "Monfils"; bez provjere datuma). Google News
(`p*_gnews`): 154/154 pokriveno, medijan 1 dan, 76% najave/rezultati/kladionice; od 15 oznaka
ozljede stvarne 3–5 (umirovljenje karijere, walkover, tuđa ozljeda). **K13b smije samo s
detektorom zapisanim unaprijed i brojanjem od dana uvođenja**; 21 viđeni slučaj K13 se ne
preoznačava.

### IZMJERENO 18.10.2026 19:43 — prelazak modela na TML servis/povrat 12 mj. (PRAGOVI_C): NE UVODI SE

Kriteriji zapisani 16:25, rezultat 16:27 (`skripte/c_tml_lab.py`, 12.315 ATP mečeva, model poena bez
cijene i ELO-a). Kritičar (skeptik, odgovor primljen prije 17:32): **PADA** kao tvrdnja da rezultati opravdavaju prelazak;
brojke ponovljene njegovim skriptama (`skripte/skeptik_tml/`).

| izvor (log-gubitak / točnost) | P1 2022–23 | P2 2024–26 |
|---|---|---|
| (a) karijera (≈ RapidAPI, r 0,98 / 0,96) | 0,6554 / 60,3% | 0,6529 / 60,2% |
| (b) TML 12 mj., sve razine | 0,6524 / 60,9% | 0,6593 / 59,7% |
| (c) 12 mj. povučeno prema karijeri, K = 1.500 | 0,6456 / 61,4% | 0,6501 / 60,1% |

- po slovu kriterija (b) PADA i "prelazak se ne radi" je okinulo; (c) − (a) na P2 +0,0028
  [−0,0015, +0,0068] — šum; 2026. −0,005;
- miješanje razina: kad bar jedan igrač ima > 50% poena u 12 mj. iz Challengera/kvalifikacija
  (48,5% mečeva) (c) je lošiji od (a), −0,020 u 2025–26; inače bolji +0,013 do +0,028;
- isti mečevi (437): 58,3% → 59,3% (+1,2 ± 2,7pp) — šum;
- probni plaćeni poziv prošao (oblik), ali to ne govori ništa o točnosti.

**Ishod:** model ostaje na RapidAPI karijeri (era bccf4742). Implementacija sačuvana na grani
`tml-era-881d89f8` (54590fb). Nastavak: K25 (samo glavni ždrijeb).

**ODBAČENO (ne otvarati bez novih podataka):** TML 12 mj. ili mješavina 12 mj. + karijera **svih
razina** kao ulaz u prompt.

### IZMJERENO 18.10.2026 15:11 — revizija Šangaja, drugi dio (B1–B4b, TA2/TA3, N5–N7, Nose, težine v18, scouting, RapidAPI)

Izvještaj: `revizije/2026-10-18/REVIZIJA_B_2026-10-18.md`. Pragovi zapisani prije računanja:
`PRAGOVI_B_2026-10-18.md` (12:20; NAKNADNO 12:22, 12:52, 15:05). Kritičar (skeptik, 15:04):
**SUMNJIVO** — zaključci "ništa ne mijenjati / Nose u sjeni / težine ne dirati" drže, tragovi
B4b, M2 i "smjer" IZBJEGAVAJ ne drže (ispravljeno prije upisa).

**LAB (12.320 mečeva, poštena cijena, strogi datum, Holm na 10):**

| test | edge | presuda |
|---|---|---|
| B1 1. servis + povrat na 1. servis (#3) | +0,9pp | PADA |
| B2 favorit-asovi vs jak povratnik, spora podloga (#5) | −1,3pp | PADA |
| B3 spašeni BP vs realizator (#6) | +2,7pp (obrnuto) | PADA |
| B4a ELO nepotvrđen (#10) | −1,4pp | PADA |
| B4b ELO potvrđen | +1,6pp sirovo, **+0,4pp uz kontrolu pojasa** | PADA |
| TA2 zadnja 3 meča na turniru | −0,5pp | PADA |
| TA3 turnir + 365 d na podlozi | +1,7pp (P1 +4,0 / P2 +0,2) | PADA |
| N5 Nose mine | −1,0pp | PADA |
| N6 Nose autsajderi | −2,6pp | PADA |
| N7 vlastita vjerojatnost | −1,9pp, uz pojas −1,5pp | PADA, obrnuto (cijena u pravu) |

Na istom povijesnom uzorku ukupno 79 testova.

**Opis:** M2 −4,8pp nemonotono po pragu → šum.

**Naši podaci:**
- težine v18 nastale su iz automatske petlje nad 10 poraza i 10 pobjeda; v18 − v14 uz pojas
  +0,7pp ±18,7 → bez podloge, ne mijenjaju se;
- simulacija tiketa (prag po datumu) → nijedna strukturna varijanta ne prolazi kriterij +5pp
  uz ≤ 30% manje dana.

**Ulazi:** RapidAPI servis/povrat je praktički zamrznuta statistika KARIJERE (ne sezona). Povrat
je +5,7pp iznad TML-a za 365 dana:
- +2,3 je naš neponderirani prosjek;
- ~0,9 prozor, ~0,6 razina;
- ~2,4 neobjašnjeno.

Prijedlog TML 365 d — korisnikova odluka (nova era). **18.10.2026 19:43: izmjereno i NE uvodi se**
(sve razine su lošije ili u šumu; vidi "IZMJERENO 18.10.2026 19:43" i K25 gore). Napuhani povrat je
gotovo stalan pomak (kritičar: +3,4pp, SD 0,64), pa razlike među igračima ne kvari.

**Scouting (2a):** 1 tekstualna izmjena (Atmane, povrat 3. percentil), 66 rangova; Đoković
povučen; razine nisu mijenjane.

**ODBAČENO (ne otvarati bez novog izvora):**
- statistika s turnira i u pristupima 2 i 3;
- kombinacije B1–B4b;
- Nose kao veto ili bonus prije K24.

### IZMJERENO 18.10.2026 10:09 — revizija Peking/Tokio/Šangaj (KONS, K10, K17, K15; LAB D/E/S/F; L4)

Izvještaj: `revizije/2026-10-18/REVIZIJA_2026-10-18.md`. Pragovi zapisani prije računanja:
`revizije/2026-10-18/PRAGOVI_REVIZIJA_2026-10-18.md` (09:07; NAKNADNO 09:12 i 09:31). Kritičar
(skeptik): SUMNJIVO — "nule" drže, tri stvari su bile prejako predstavljene i ispravljene (točka
18 izvještaja). **U modelu ništa nije mijenjano** (korisnikova uputa: prvo izvještaj).

    NOVO (od 27.09., hard)   n=140  93W  edge +0,7pp ±7,6 (s 3 Munarova meča -0,4pp)  ROI -4,8%
    ŠANGAJ                   n= 72        edge -1,4pp ±10,7
    tiketi od 27.09.: 10, dobitan 1, očekivano 1,93 (P(<=1) >= 39,5%); svih 66 od 27.05.: 5 dobitnih,
    očekivano 6,9, P(<=5)=30%; EV tiketa ≈ -21% i bez greške modela; noge 63,9% vs 64,2%

**Ishodi kandidata (pravila zapisana ranije):**
- **K17 — PAO, ZATVOREN** (n=43, +13,7pp; spojeno −0,3pp).
- **KONS — NIJE POTVRĐEN, ni oboren** (od 08.09. n=40, −0,4pp ±13,9). `measure_candidates` kaže
  PAO (n ≥ 30 i < 0), komentar u `ticket_builder.py` (08.09.) veže odluku uz 31.10. i n ≥ 60 →
  kriterij nije nedvosmislen; bonus NIJE maknut; odluka korisnika (maknuti odmah ili 31.10.).
- **K10 — formalno zadovoljen, oblik se nije ponovio** → K10b.
- **K15** (zatvoren 27.09.): NOVO r = +0,03 (n=140) — ostaje zatvoren.
- K5 25/100, K13 15/40, K18 14/30, K19 4+11/40, K20 132/150 — ČEKA.

**IZMJERENO I ODBAČENO (ne otvarati bez novog izvora) — LAB 12.324 meča naspram poštene cijene,
strogi datum, Holm na 36 testova (najmanja korigirana P = 0,21):**
- prosjek statistike s aktualnog turnira (udio poena, hold, asovi, 1./2. servis, povrat, BP,
  setovi, gemovi) na dubini 2 i 3+: 18 od 18 PADA (−2,0 do +2,4pp). Bolji na turniru pobjeđuje
  56–64%, favorit 68%. Robusno na kontinuiranu verziju i prilagodbu protivnicima; ne isključuje
  1–2pp. Dubina 3+ = runde R16–F. "Dubina 4+" (+4,1pp, n=312) nemjerljiva — nije trag.
- kombinacije E1–E13 (povratnik vs slab 2. servis +0,7; server vs slab povratnik +1,3; +8 ATP
  pobjeda i bolji hold −0,9; +8 ATP pobjeda kao autsajder +2,2 uz razilaženje polovica; viši u
  dvorani +2,1; dob × umor +0,9 / −2,1; stariji u QF+ +0,6; "mina" favorit slabijeg 2. servisa −1,6;
  autsajder dominantniji na turniru −3,0; favorit s 60+ min više −0,8; slični protivnici −0,2 nakon
  popravka greške) — sve PADA; S2, S3 PADA; F2a visina +0,2 PADA; F2b dob 5+ −1,2 SLAB. S1 → K23.
- na našim podacima: vrijeme W1–W4 premalo (n=4–14), glavni učinci okreću predznak; W0 (vrijeme ×
  prvi servis) bila je razlika između turnira (unutar turnira r ≈ ±0,07) — povučeno; runde —
  nijedna ne zadovoljava kriterij; težine v18 — kriterij nije ispunjen (vidi K22); razine
  scoutinga okreću predznak; kretanje kvota M1–M3 (peti put) |r| ≤ 0,07 ("nije otkriveno",
  interval ±0,18); pravilo 15 u promptu −3,5pp (n=52) nejasno.
- **upozorenje AI recenzenta (L4)** — prag NIJE ispunjen → OPIS, ne kandidat: 25 noga s
  dvostranom cijenom −13,8pp [−32, +5]; svih 49 (približna cijena) −6,0pp [−19, +7]; unutar tiketa
  označena lošija u 25 od 49 (novčić); post hoc. **Praćenje:** kad se skupi 30 novih označenih noga
  (od 19.10.) — ako je uparena razlika ≤ −5pp i interval ispod nule na spojenom uzorku, tek tada
  kandidat. Tekst upozorenja ne mijenjati dok traje praćenje.

**OPIS (nije prediktor):** visina ↔ asovi r = +0,42, hold +0,20 (27.022 igrač-meča); dob sve
|r| ≤ 0,04. Winneri/neiznuđene greške postoje samo za Grand Slam (ograničenje izvora).

**KVAR (popravak čeka korisnika):** `_LOSS_BASE_RATES` (analiza gubitka) ima 3 zastarjela retka (ATP
pobjede "jedina koja preživi cijenu", konsenzus "potvrđen", hard ATP 250 −11,2pp); od 6 oznaka
[SIGNAL CONFIRMED] od 27.09. nijedna nije potvrđena (3 opovrgnute, 3 neodlučene).
> **POPRAVLJENO 18.10.2026 12:40** (korisnikov "kreni"; zapis 14:44): sva tri retka ispravljena
> (ne obrisana), a oznaka SIGNAL zamijenjena s četiri odvojena pojma — vidljivo prije meča / naš
> zapis u istom uzorku / prediktivna vrijednost (kapija) / ovaj meč; izmjenu smije predložiti samo
> "GATE PASSED", koji danas nema nijedan faktor. MODEL_CHANGELOG 18.10.2026 12:55, točka 2.

**OPERATIVNO:** Odds API ključ deaktiviran (401 DEACTIVATED_KEY), zadnja snimka 15.10.2026 05 h.

**Višestruko testiranje:** u sesiji ≈118 testova → ~6 nominalnih P < 0,05 očekuje se slučajno.
LAB je kroz tri revizije korišten za 69 testova — jedna obitelj pokušaja.

### IZMJERENO 04.10.2026 18:32 — revizija azijske turneje (K1, K9, K10, K11, K17; lab C/D)

Izvještaj: `revizije/2026-10-04/REVIZIJA_2026-10-04.md`. Pragovi zapisani prije računanja:
`revizije/2026-10-04/PRAGOVI_REVIZIJA_2026-10-04.md` (17:54; dodatak D10 u 18:07 označen kao
naknadni). Kritičar (skeptik) proveo je provjeru; presude su u točki 15 izvještaja. **U modelu
ništa nije mijenjano.**

    NOVO (28.09.-04.10., era bccf4742)  n=57  35W  edge -4,5pp ±12,0   (bez 3 meča s krivim
                                                                         Munarovim ELO-om: -1,9pp, n=54)
    STARO                               n=466        edge -0,6pp ± 4,2

- **K1 (prag 60) — NA PRAGU, odluka korisnika.** Novi uzorak 60-63: -13,8pp (n=30); samo
  Peking+Tokio (prvi turniri cijeli u eri bccf4742): -17,9pp (n=26), >=63 +12,2pp (n=17).
  Formalni uvjet ("sljedeći dovršeni turnir") ispunjava se kad Peking i Tokio odigraju finala;
  preostali mečevi ne mogu vratiti predznak. Skeptik: SUMNJIVO — ista skupina bila je +3,1pp
  (30.08.) i +9,3pp (US Open), pa je okretanje obrazac šuma; pouzdanost ne nosi informaciju
  (r(odmak od cijene, ostatak) = -0,044, n=466). Uz strukturu tiketa 3-6/4-50 prag 63 daje tiket
  u 4 od 17 dana od 08.09. (prag 60: 11 od 17). **Od 08.09. kazna 65-68 ne izbacuje s tiketa**
  (spuštene na 60-63 prag 60 pušta; od 08.09. n=25, -8,3pp, 7 na tiketu).
- **K9 — PAO.** Pobjede imaju DULJI "Own read" za 52 znaka; r(duljina, ishod - cijena) = +0,20
  (n=57). Predznak suprotan hipotezi drugi put zaredom (26.09.: +144 znaka, r=+0,36). Po pravilu
  ("ako predznak okrene -> odbaciti") zatvoren.
- **K10 — ČEKA:** 1,20-1,35 +7,2pp (n=22) | 1,35-1,65 -5,6pp (n=34) | 1,65-1,85 -10,7pp (n=20);
  n<25 u dva pojasa.
- **K11 — NIJE POTVRĐEN u zadanom roku** (dva dovršena turnira od 13.09., runde ručne):
  R16+QF -1,5pp (n=31), ostale runde -3,5pp; R16/QF su BOLJI od ostalih. Skripta kaže ČEKA
  (ostatak nije iznad nule). Povijest: tržište u R16/QF nema rupu (+0,6pp, n=3.423). Prijedlog
  zatvaranja čeka korisnika. Analize gubitaka ga i dalje zovu "[SIGNAL CONFIRMED]" (3 od 8),
  jer ga prompt analize gubitka prikazuje bez oznake "nepotvrđeno".
- **K17 — ČEKA, okreće se:** High od 27.09. +13,2pp (n=23), prije -11,7pp (n=53).
- K5 (n=16), K13 (n=3), K18 (n=14, +14,5pp), K19 (4/9), K20 (57/150), KONS (n=14, -3,6pp) — ČEKA.

**IZMJERENO I ODBAČENO (ne otvarati bez novog izvora podataka) — povijest, 12.324 meča, naspram
poštene cijene, sve iz mečeva prije meča:** forma 10 (+0,2pp), podloga 365 dana (-0,2),
hold % (-0,6), break % (+0,8, SLAB), asovi (-0,4), dvostruke (-0,2), H2H vođa (+0,7, n=2.897),
bolji rang kao autsajder (-0,4), manje setova na turniru (-0,3, n=7.367), te kombinacije: vruć
autsajder (0,0), server na brzom (+1,7), returner na zemlji (+1,8), H2H vođa kao autsajder
(-0,1), umorniji u QF+ (-0,2), top-20 pobjede kao autsajder (-0,3), specijalist kao autsajder
(-0,5), asovi u dvorani (+2,2), zalet na turniru kao autsajder (0,0, naknadno). **0 od 18
prolazi**; s prosjekom kladionica iste presude. Rang povrh cijene r=+0,007 (n=12.302).
Na našim pickovima 24 varijable, 0 preživi Holm. "Intuicija" (odmak pouzdanosti od cijene)
ne nosi informaciju: r=-0,044 [-0,13, +0,05], n=466; pick = tržišni favorit 96,5% (novo).
Scouting: profil ni razina ne nose ništa povrh cijene (s profilom -1,2pp, bez -0,4pp; razine
okreću predznak između polovica) -> Excel se ne širi radi predviđanja.

**KVAR PODATAKA (popravak, ne nalaz; čeka odobrenje):** `find_player_elo` daje "Jaume Antoni
Munar Clar" ELO igrača "jay clarke" (1421/1397 umjesto 1767/1748). Korak 2 hvata prezime kao dio
riječi ("clar" u "clarke"), a korak 3 prihvaća prvo slovo imena. 10 analiza; 7 riješenih
pickova, svi protiv Munara, 2-5. `elo_cache` ima 546 imena dvaput (NBSP 29.08. + novi 04.10.);
lookup vraća stari zapis za 535 (vrijednost se razlikuje u 448), a `get_elo_cache` čita 1.000 od
1.138 redaka. Tih 10 analiza treba označiti prije budućih mjerenja.

### IZMJERENO 04.10.2026 19:30 — korisnikovi novi prijedlozi (pragovi `revizije/2026-10-04/PRAGOVI_DODATAK_2.md`, 19:07)

**ODBAČENO (ne otvarati bez novog izvora) — "tablica top 200 × turniri, pobjede i omjer na
svakom turniru u 3 sezone"** (korisnikov prijedlog: "kako se igrač osjeća na tom turniru,
gradu, ambijentu"). Povijest, 12.324 meča, naspram poštene cijene:

    TWL1 bolji omjer pobjeda na OVOM turniru (3 sez., oba >=3 meča)  n=3.231  +1,4pp [-0,1, +2,9]  P1 +2,2 / P2 +1,0  PADA
    TWL2 veći "višak" (omjer ondje − opći omjer istih godina)        n=3.533  +0,9pp [-0,5, +2,4]  P1 +2,1 / P2 +0,3  PADA
    TWL3 višak +15pp, tržišni autsajder                              n=  809  +2,3pp [-0,9, +5,5]  P1 +6,7 / P2 -0,2  PADA
    tercile TWL1 (mala/srednja/velika razlika): +1,6 / +2,4 / +0,2pp — nemonotono

Smjer je dobar, ali tržište to već plaća (≤ 1,4pp, interval preko nule). Isto kao "najdalja
runda na turniru" (POV, lab 27.09.: +0,2pp n=6.198). Tablica se NE gradi kao prediktor.

**Vlažnost (korisnikov komentar o Đokovićevom disanju): nula.** Naš korpus, otvoreni tereni,
n=366: r(vlaga, ishod − cijena) = +0,054 [−0,05, +0,16]; STARO +0,091, NOVO −0,136 (predznak se
okreće); tercile −3,4 / −2,3 / +2,8pp; pick stariji 4+ godine pri visokoj vlazi +1,3pp (n=12).
Đokovićev meč s Borgesom (Peking 30.09.) imao je zabilježenu vlagu **11%** — suh zrak; "teško
disanje" u Pekingu vjerojatnije je kvaliteta zraka (smog), koju ne bilježimo. Vlaga se i dalje
bilježi (`weather_humidity`).

**K21 — favorit u QF/SF/F protiv igrača s boljim servisom (korisnikova ideja o četvrtfinalima)
— predprovjera prošla, skeptik SUMNJIVO; upisan kao kandidat** (zaseban unos K21 u registru,
iza K20). Povijest: protivnik ≥3pp bolji hold −5,8pp (n=296), ≥2 asa/100 više −5,0pp (n=554),
obje polovice negativne; u ranim rundama i u R16 suprotan smjer.

### POVIJESNA PREDPROVJERA 27.09.2026 11:58 — 12.324 ATP meča naspram tržišne cijene

Izvještaj: `revizije/2026-09-27/POVIJESNI_LAB_2026-09-27.md`; pragovi zapisani prije računanja
u `revizije/2026-09-27/PRAGOVI_POVIJESNI_LAB.md` (11:33). Podaci: tennis-data.co.uk 2022 –
13.09.2026 (Pinnacle bez marže, inače prosjek kladionica) + TML (runde, statistika, povijest).
Kriterij PROLAZI = |edge| ≥ 2pp, interval ne prelazi nulu, isti predznak u obje polovice
(2022–23 / 2024–26) i isti smjer kao u registru. **Nijedan kandidat nije prošao.**

    kandidat                               n       edge    95% interval    P1 / P2      presuda
    K15 više ATP pobjeda u sezoni        11.139   +0,0pp  [−0,8, +0,9]   −0,5 / +0,5   PADA
    K16 jedini s GS SF (QF/SF/F)            826   +1,1pp  [−2,0, +4,1]   +1,0 / +1,2   PADA
    K18 favorit na hard ATP 250           2.311   +0,1pp  [−1,7, +2,0]   +0,0 / +0,2   PADA
    K19 povratak nakon 21+ dan            1.018   −2,5pp  [−5,2, +0,3]   +0,5 / −4,7   PADA
    K2  domaći igrač                      2.775   −1,4pp  [−3,1, +0,2]   −1,2 / −1,6   PADA (nije +)
    K3  Bo5 favorit 1,30–1,50               563   +4,3pp  [+0,6, +7,9]   +4,7 / +4,0   PADA (suprotan smjer)
    K11 favorit u R16/QF                  3.423   +0,6pp  [−0,9, +2,1]   +0,3 / +0,9   PADA
    povijest na turniru (bolja)           6.198   +0,2pp  [−0,8, +1,3]   −0,4 / +0,6   PADA
    K12 servis na turniru, dubina 3+        970   +0,4pp  [−2,4, +3,2]   −0,4 / +0,9   PADA  (r = +0,004)
    zajednički protivnik (CO)            10.661   +0,2pp  [−0,7, +1,0]   −0,1 / +0,4   PADA

Pojasevi favorita (K5/K10): 1,35–1,43 **+3,7pp** [+1,3, +6,1] (obje polovice +) — tržište u
tom pojasu NEMA rupu, favoriti ondje prolaze bolje od cijene; <1,20 +1,9pp; 1,43–1,60 −0,4pp.
Konsenzus (Bet365 naspram poštene cijene): edge ≈ gap; ROI po Bet365 tek u gap ≥ +2pp oko nule
(+0,5% [−3,5, +4,5]). Naši pickovi naspram zatvorne cijene (n=417): edge +1,5pp [−2,9, +5,9],
EV po SuperSport kvoti −5,3%, noge pravih tiketa EV −3,1% (n=211).

**Kako čitati:** kandidati o OSOBINI igrača (K15, K16, K19, K2, povijest, K12, CO) ovime su
izravno provjereni — tržište ih plaća. Kandidati o NAŠEM izboru (K5, K11, K18) ovdje se ne mogu
potvrditi ni oboriti; test samo kaže da tržište ondje nema rupu.

**Preporuke korisniku (NIŠTA nije ugrađeno, statusi gore u registru NISU mijenjani):**
zatvoriti K15, K16, K3; K5 ne uvoditi na n=20 (tražiti n ≥ 100 ako se mjeri dalje); pravilo 11
(domaći) i prosjek statistike s turnira (K12) maknuti iz prompta uz sljedeću izmjenu prompta
(`revizije/2026-09-27/PROMPT_AUDIT_2026-09-27.md`); K11, K18, K19 mjeriti dalje uživo;
konsenzus zadržati, očekivanje spustiti na ≈ veličinu gapa.

**ODLUKE KORISNIKA (27.09.2026 12:16):** preporuke 1-3 prihvaćene i provedene (K15, K16, K3 zatvoreni; K5 prag n ≥ 100; pravilo 11 i K12 van odlučivanja, era bccf4742). Preporuku 4 (manje nogu) korisnik je ODBIO: tiket ostaje **3-6 parova i ukupna kvota 4-50**.

**Novo za promatranje (nije kandidat, nađeno naknadno):** Grand Slam favoriti 1,30–1,50
+4,3pp (Holm P=0,23 — nije dokazano). Provjeriti na AO 2027; do tada ništa ne mijenjati.

### IZMJERENO I ODBAČENO 26.09.2026 20:46 — tri korisnikove ideje i sekvenca

- **Tablica promašaja po igraču** (ideja 2): doslovno pravilo (−2pp iznad prosjeka promašaja,
  +2pp ispod) → kažnjeni −1,0pp (n=155), nagrađeni −0,4pp (n=296); višak promašaja naspram
  cijene r=−0,004 (n=417); ostatak igrača na tržištu nije postojan (r=+0,06 / +0,14 na
  11.512 nastupa). Rublev kao tržišni favorit +3,8pp (n=113). Prikazuje se samo korisniku.
- **Protiv koga je gubio na ovom turniru** (ideja 3): ostatak na turniru r=+0,04 (P=0,40);
  "izgubio ovdje kao favorit 1+" −2,8pp, ako je danas opet favorit −0,6pp. Ćelija "2+" −18,7pp
  ima n=20 — ne koristi se.
- **Sekvenca protivnika** (211 mečeva s cijenom iz pobranih ždrijebova): 1 od 8 varijanti
  P=0,022 ("uvjerljivo pobijedio protivnika s jednako jakim 2. servisom") — unutar slučajnosti.
- **Ocjenjivačka tablica od 26.08.** (n=148 izvan uzorka): forma×kvaliteta +3,2pp (tražilo se
  ≤−8), ELO protivnika <1700 +2,6pp, dob 4+ −0,7pp — sve tri PALE; R16/QF −17,5pp (n=15) drži.
- **Stopa replikacije sada 3 od 12** (K1, konsenzus, R16/QF).

### IZMJERENO 26.09.2026 17:04 — omjer protiv ljevaka/desnjaka NE predvidja

Korisnikov prijedlog, povod komentar s finala US Opena: Zverev je dominantan protiv ljevaka
jer trenira s bratom ljevakom. **Anegdota je tocna** — Zverev u 2 godine prije finala:
protiv ljevaka **21-1**, protiv desnjaka 100-41. Ali kao prediktor naspram cijene nije
prosao (mecevi s bar jednim ljevakom, n=120, "rub po ruci" pick minus protivnik):

    r(ostatak) = -0,103, CI [-0,28, +0,07]; polovice -0,37 / +0,15  (predznak se okrece)
    razredi: protivnik bolji +5,1pp | podjednako -8,0pp | pick bolji -4,9pp  (naopako)
    kontrola desnjak-desnjak (n=331): -0,008

Medijan broja meceva protiv te ruke je 15 po igracu — omjer je sum oko igraceve opce
razine, a gdje je stvaran (Zverev), trziste ga vec zna. **Ostaje se biljeziti** (korisnikov
zahtjev: `p*_ctx.vs_hand` u svakoj analizi i unatrag u svih 664 redaka) i premjerava se kad
meceva s ljevakom bude n>=300. Ljevaka je u nasim podacima 12,7% (220 od 1.727 poznatih).

### IZMJERENO I ZATVORENO 13.09.2026 10:44 — tri hipoteze, sve tri nula

Sve tri su bile korisnikovi prijedlozi ili moji, sve tri su izmjerene **prije** nego što
je išta ušlo u kod. Zapisane su da se ne mjere po četvrti put.

**(a) Prosjek post-match statistike NA TOM TURNIRU ne predviđa sljedeći meč.**
Ideja: tko kroz turnir servira i brani break bolje, ima prednost u sljedećem kolu.
Građeni tekući prosjeci po (turnir, igrač), samo iz mečeva **strogo ranijih**. n=127
mečeva gdje oba igrača imaju bar jedan raniji meč na tom turniru.

    serve_won  r=+0,008 P=0,924      bp_saved  r=−0,004 P=0,966
    ace_rate   r=−0,097 P=0,283      bp_conv   r=−0,073 P=0,423
    first_in   r=+0,079 P=0,372      first_won r=−0,044 P=0,630
    second_won r=+0,011 P=0,893      df_rate   r=+0,008 P=0,920

Naspram devigane tržišne cijene sve tri glavne mjere idu u **krivu** stranu
(serve_won −0,047 P=0,60; ace_rate −0,099 P=0,27; bp_saved −0,060 P=0,50).
Kvartili pri većoj dubini izgledaju velikodušno ali **nisu monotoni**
(bp_saved: 29% → 80% → 33% → 47%) i stoje na 5-6 mečeva po kvartilu.

Ilustracija na finalu US Opena 13.09.2026: Zverev 70,5% servis / 12,7 asova na 100 /
70% BP spašenih naspram Sheltonovih 70,6% / 12,1 / 64%. Mjera ih ne razdvaja.

*Ograda:* uzorak je plitak (58 od 127 ima samo jedan raniji meč) jer korpus drži samo
mečeve koje smo analizirali. Jači test traži pobrane statistike cijelog ždrijeba
(`scripts/backfill_match_stats.py`). Ali prior nije ohrabrujuć — sezonske serve/return
statistike već su izmjerene kao čisti šum (svi |r|<0,06, revizija 26.08.2026).
`winners` i `unforcedErrors` su u ovom feedu **uvijek null**, pa omjer winneri/greške
(kandidat K4) iz ovog izvora nije izvediv.

**(b) Kretanje linije ne predviđa ništa — ni kad snimka doista dosegne zatvaranje.**
Hipoteza: ako je ozljeda poznata tržištu, cijena se pomakne, pa je pomak mjerljiva
zamjena za vijesti. Podaci postoje i zdravi su — **30.350 redaka, 189 od 192 događaja
ima dvije ili više snimaka**. Sparen 149 događaja s poznatim ishodom.

    podskup                        n     r(pomak, ostatak)    P      Brier početna → završna
    svi                          149          +0,036        0,691      0,1915 → 0,1917
    zadnja snimka <2,5h prije     67          +0,000        1,000      0,2021 → 0,2044
    zadnja snimka <6h prije      126          +0,015        0,873      0,1984 → 0,1995

Medijan pomaka je 1,29pp, 90. percentil 4,11pp — dakle pomaka **ima**, samo ne nosi
informaciju. Ključno: **završna cijena nije bolja od početne** ni na podskupu gdje je
snimka doista blizu početka. U efikasnom tržištu završna linija jasno pobjeđuje raniju;
kad ne pobjeđuje na n=67 s pravim tajmingom, hipoteza je izmjerena, a ne neizmjerena.

Posljedica: kretanje linije **ne** ulazi ni u prompt ni u bodovanje. Skripta
`capture_market_close.py` ostaje jer podaci koštaju malo, a jedini ozbiljan preostali
razlog je CLV mjerenje.

**(c) Drugi AI model (Kimi) kao recenzent — odbijeno za ovu namjenu, otvoreno za jednu drugu.**
Korisnikovo pitanje: može li besplatan drugi model revidirati analize. Ne za provjeru
mjerenja — ona su provjerljiva ponovnim pokretanjem koda, pa mišljenje drugog modela
nije dokaz. Sva četiri kvara nađena 13.09.2026 (visina, runde, vijesti, `edge_bonus`)
nađena su upitima nad podacima; drugi bi model gledao isti prazan `p2_build` i isto ne
bi znao da API ima podatak.

Jedina mjerljiva uloga koja ostaje otvorena: **drugi model kao neovisni analitičar na
istom promptu, pa se mjeri predviđa li SLAGANJE dvaju modela bolje od jednog.** To bi
bila zamjena za pouzdanost, koja je kod nas mrtva varijabla. Ograda: oba modela vide
iste ulaze pa će jako korelirati. Prioritet nizak dok se ne potroše K5/K8/K9/K10.

**(d) NAČIN kretanja kvote ne nosi ništa — iskopano do kraja 13.09.2026 12:50.**
Na korisnikov zahtjev provjereni su svi obrasci, ne samo neto pomak. Podaci: 30.350 redaka,
50 kladionica, 192 događaja, 6.028 serija po (događaj, kladionica) s 3+ snimke, od kojih se
90% barem jednom pomakne — nalaz dakle nije posljedica manjka podataka.

    naspram ostatka nakon početne cijene (n=108):
    neto pomak       r=-0,092 P=0,371      najveći izlet   r=-0,101 P=0,321
    broj pomaka      r=-0,029 P=0,757      udio preokreta  r=+0,169 P=0,081
    kolebljivost     r=-0,051 P=0,625

Po kladionici, min 25 mečeva: **48 kladionica, nijedna s P<0,05** — a slučajno bi se
očekivalo 2,4. Dobili smo *manje* naizgled značajnih rezultata nego što bi čisti šum dao.
Sharp kladionice nisu iznimka (najbolji smarkets r=+0,127 P=0,230).

Po pojasu naše kvote: šest testova, jedan ispao P=0,03 (naša strana 68%+, r=-0,382, n=33).
Nije nalaz — uz šest testova jedan ispod 0,05 očekivan je u ~26% slučajeva, a predznak je
naopak (tvrdio bi da prolazimo lošije kad se cijena pomakne prema nama).

Zajedno s ranijim nalazom istog dana (završna cijena nije bolja od početne ni na n=67 s
pravim tajmingom, Brier 0,2021 -> 0,2044) ovo zatvara temu. **Iz tržišta koristimo i radi
samo jednokratni konsenzus.** Ne ponavljati bez novog razloga — treći je put da se tržište
kopa i treći put da ostane samo konsenzus.

**(e) Drugi izvor kvota — ODGOĐENO 13.09.2026 korisnikovom odlukom.** Predložen radi
otpornosti (konsenzusni bonus visi o jednom izvoru), ne radi novog signala. Nakon nalaza
(d) argument je još slabiji: ako 50 kladionica kroz mjesec dana ne nosi ništa osim
jednokratnog konsenzusa, pedeset prva neće ni ona. Otvoriti samo ako Odds API zaigra
(pad pokrivenosti, kvota, ili gašenje) — tada je to hitan popravak, ne poboljšanje.

### ODBAČENO 06.09.2026 iz analize kvota (izmjereno, ne otvarati bez novog razloga)

- **kretanje kvote kroz dan**: `r(pomak, EDGE naspram cijene) = +0,007, P=0,927` na 167
  mečeva. Kad se uzme u obzir završna cijena, pomak ne dodaje **ništa**. Sirova korelacija
  s pobjedom (+0,077) postoji samo zato što pomak korelira s cijenom. Skupine nisu monotone
  (mirno tržište je najbolje: +10,7pp). Medijan pomaka je +0,22pp — tržište se kroz dan
  jedva miče, pa ni nema što mjeriti.
- **broj snimaka po meču** (koliko je dugo bio na tržištu): 2 snimke −1,3pp, 3 → +1,6,
  4 → +6,0, 5 → −6,9, 6+ → +20,7pp (P=0,040). Nemonotono; "6+" je vjerojatno zamjena za
  važnost meča, ne signal.
- **kratke kvote kao problem**: pickovi na <=1,20 idu 83,0% naspram očekivanih 85,3%
  (n=53, −2,3pp), split-half +0,1pp / −4,6pp. Pet gubitaka na US Openu ispod 1,20
  (Musetti 1,04, Jodar 1,06, Fritz 1,12, Đoković 1,15, Fils 1,18) je **varijanca**,
  ne obrazac.
- **R16/QF kao uzrok** (jedini obrazac koji se ponavlja u analizama gubitaka od 30.08.):
  −4,8pp, n=72, P=0,398, a oznake rundi su nam ~43% krive. Prezlabo za bilo kakav zahvat.

### ODBAČENO 06.09.2026 (ne otvarati bez novih podataka)

- **tablica promašaja po igraču** (-2pp iznad prosjeka): izmjereno u oba čitanja; skupina
  koju bi pravilo kaznilo ide +2,1pp, koju bi nagradilo -0,3pp. Smjer suprotan predloženom.
- **P<0,10 kao prag značajnosti**: na 84 testa daje 3 dodatna nalaza (dva su "razlika u
  visini", već oborena) uz dvostruko više očekivanih lažnih pozitiva.
- **prozor 2 godine za mlađe igrače**: r = +0,118 / -0,143 / +0,085 po dobnim skupinama.
- **Historical Match-Up Context, treći put**: medijan 1 sličan slučaj po meču.

---

## 4. Otvorena zamjerka: brojke se prikazuju s više autoriteta nego što ga imaju

*(zabilježeno 08.08.2026 12:30 — NIJE implementirano, ide u paket sa servisom/pragom)*

Model čita `Hold % (est.): 82,4%` kao činjenicu. To je procjena čija je varijacija **od meča
do meča 7,9 postotnih bodova** (izmjereno na 58 igračevih nastupa u Montrealu) — a pravila
koja se na nju oslanjaju razlučuju na razlikama od 1,6 do 2,6 boda. Isto vrijedi za
`Avg opponent ELO`: model ne zna je li izračunat iz deset protivnika ili iz četiri, iako se
protivnici bez ELO ocjene tiho ispuštaju i to su sustavno slabiji igrači.

**Hipoteza:** ovo je isti korijen kao obrnuta kalibracija iznad 61% (deklarirano 65-67% ->
stvarnih 52,2%, n=23). Model je siguran zato što mu ništa ne govori koliko bi trebao biti
nesiguran — svaki broj mu dolazi bez mjere pouzdanosti.

**Prijedlog (čeka odluku):** uz nesigurne veličine prikazati i njihovu pouzdanost — npr.
"Avg opponent ELO: 1712 (iz 6 od 10 protivnika)" i označiti hold kao procjenu s poznatim
rasponom. Ide u isti paket kao ispravci servisa/povrata i prag 63%, jer bi zasebno opet
pomiješalo uzroke.

**Srodna zamjerka iz istog pregleda:** 24 pravila u promptu počinju se preklapati. Vidjeli
smo model kako pravilo 12 primjenjuje na igrača s omjerom 2/3 i sam ga naziva "borderline"
(log 27.07.). Kad ih je toliko, teško je utvrditi koje je zapravo odlučilo — kandidat za
konsolidaciju pri sljedećoj velikoj reviziji.

---

## 4b. NE ULAZI U ODLUKU — "Analysis write-up" (zapisano 29.08.2026 12:10)

Tekst pod naslovom **"Analysis write-up"** (Streamlit `pages/1_Dnevni_Listic.py`, arhiva i
dnevni mail) nastaje ZASEBNIM pozivom modela nad vec donesenim odlukama
(`ticket_builder._generate_analysis_only_summary` / `_generate_ticket_summary`).

**On ne odlucuje nista.** Ne upisuje se kao pick, ne sudjeluje u razrjesavanju rezultata,
ne ulazi u `analyzed_matches`, ne ulazi u statistiku modela i ne utjece na tezine.
Mjerodavno je i uvijek je bilo polje `pick` u `ticket_matches` / `analyzed_matches`.

**Povod za ovaj zapis:** 29.08.2026 write-up je za dva meca imenovao PROTIVNIKA nasih
pickova (Sakamoto umjesto Vukica, Walton umjesto Wua) jer ga je stari prompt stavljao u
nacin odlucivanja umjesto izvjestavanja. Popravljeno isti dan u tri sloja; puna analiza,
mjerenje na 88 tiketa i popis odgodjenog u `MODEL_CHANGELOG.md` (2026-08-29 12:10).

**Za citanje STARIH tiketa:** `ticket_summary` od 29.06. i 22.08.2026 nosi krivo imenovan
pobjednik i NIJE retroaktivno prepisan. Vjerovati polju `pick`.

**Od 29.08.2026 13:40** iznad svakog write-upa (Streamlit, arhiva, oba maila) stoji
`Picks as recorded (source: database, not the text below)` — popis crtan iz
`ticket_matches` preko `utils.helpers.pick_ledger`, bez ijedne rijeci koju je napisao
model. To je sluzbeni izvor za sve tikete, i stare i nove.

## 4c. ULAZI U PRIKAZ (ne u predikciju) — prag `MIN_PICK_CONFIDENCE = 50.0`

`utils.helpers.is_no_selection(match)` -> `confidence < 50`. Pick ispod praga se prikazuje
kao **NO SELECTION**, gubi oznaku VALUE, u write-upu nosi `[NOT BACKED]` i ne ulazi u
**hipotetski** tiket (`_conf_floor_ok` u `_selection_ok`). Pravi tiket je netaknut — ondje
prag ionako iznosi 63% (65% na Grand Slamu).

**Predikcija se i dalje bilježi, razrješava i BRoji u statistici.** Izvedeno iz
`confidence`, nije stupac u bazi. Mjerenja i obrazlozenje: `utils/helpers.py`, blok iznad
`MIN_PICK_CONFIDENCE`, i `MODEL_CHANGELOG.md` (2026-08-29 13:40).

## 4d. ULAZI U ODLUKU — tri nove determinističke provjere (30.08.2026 12:40)

Sve tri žive u kodu, ne u promptu; `rules_hash` je netaknut (`a0424315`).

| provjera | gdje | učinak |
|---|---|---|
| pouzdanost u pojasu 65-68 | `predictor._apply_measured_penalties` | −5pp (spušta ispod praga 63) |
| naš pick vodi u tie-break zapisu 10pp+ (uz 3+ TB kod oba) | isto | −4pp |
| Med-Low scouting profil na našem picku | `ticket_builder._scouting_ok` | **veto** za tiket |

Pojas 65-68 računa se na broju **nakon** ostalih kazni, jer je izmjeren na
`predicted_confidence` kakav završi u bazi. Mjerenja i obrazloženja:
`MODEL_CHANGELOG.md` (2026-08-30 12:40) i komentari uz same funkcije.
