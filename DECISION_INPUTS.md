# Što ulazi u odluku o picku — referentni popis

**Stanje na dan 13.08.2026 12:47.** Popisano na korisnikov zahtjev jer se dosad nigdje nije
vidjelo na jednom mjestu — ulazi su razasuti po promptu (`agent/predictor.py`),
determinističkom kodu (`agent/ticket_builder.py`) i zapisu (`context_snapshot`).

Ovo je **referenca, ne changelog.** Kad se nešto od navedenog promijeni, ažurirati ovdje i
zabilježiti izmjenu u `MODEL_CHANGELOG.md`.

---

## 1. Ulazi u ODLUKU — analiza (prompt, ~13.800 tokena, od 08.09.2026 u DVA dijela)

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
| **Trajektorija 7%** | karijerni omjer na tom turniru, odigrana finala i naslovi |
| **H2H 4%** | ukupno, na podlozi, zadnji susret, trend zadnja 3, pouzdanost uzorka |

**Izvan težina, ali utječe na pick:**

- **Runda i kontekst runde** — rane runde dopuštaju iznenađenja, završnice favoriziraju dokazane
- **Vremenski uvjeti** — smiju **samo SPUŠTATI** pouzdanost, nikad je dizati (asimetrija namjerna)
- **Lokalno vrijeme početka i sesija** (dan/noć) — za razliku od uvjeta, sesija po pravilu 14
  smije djelovati **u oba smjera**
- **Oboje otpada kad raspored za sutra nije objavljen** *(novo 14.08.2026 11:02)*. Kad 4+
  mečeva jednog turnira dijeli najraniji termin **sutrašnje** liste, kladionica je cijeli dan
  nabila na jedan placeholder sat: prognoza se tada ne dohvaća uopće, a `local_time`/`session`
  ostaju prazni umjesto približni. Rubrici „danas" se vjeruje uvijek. Meč i dalje ide u analizu
  i smije na tiket. Zapis: `context_snapshot.schedule_provisional` (v11)
- **Povijest ždrijeba turnira** — anti-halucinacijska provjera tvrdnji o prošlim rezultatima
- **Scouting profili** (`player_scouting`, 150 igrača iz korisnikova Excela) — SEKUNDARNI
  izvor koji nikad ne nadjačava mjerene brojke. Dopušteni utjecaj skalira s pouzdanošću
  profila: High/Med-High ±3pp, Med ±2pp, **Med-Low samo kao sumnja** (nikad kao potpora
  picku), Low i Insufficient se uopće ne prikazuju
- **`odds_alert`** — upozorenje na moguću ozljedu/povlačenje pri omjeru kvota ≥6:1
- **`market_check`** *(novo 13.08.2026 12:47)* — tržišna cijena kao **PROVJERA, ne ulaz**.
  Model svoj broj i dalje formira bez nje; tek nakon toga uspoređuje i, ako se razilazi za
  više od 10pp, mora imenovati mjerenu činjenicu koja to opravdava. Povod: pickovi >10pp
  IZNAD tržišta išli su 2W-6L (ROI −52,5%). **Kvota i dalje NE ulazi u procjenu
  vjerojatnosti** — to je korisnikovo stalno pravilo.
- **24 pravila**: 16 hard-specifičnih + 8 univerzalnih

## 2. Ulazi u ODLUKU — deterministički kod, nakon analize

**Izbacuje pick** (`_selection_ok` + conf floor):

- pouzdanost < **60%** *(spušteno s 63 dana 08.09.2026 12:07 — kandidat K1 potvrđen na US Openu: pojas 58-63 dao +9,3pp uz n=49, dok je >=63 dao −3,0pp)* — iznimka je value-override: conf ≥58 uz edge ≥12pp, najviše 2 po tiketu
- nije glavni tour, ili nema kvotu
- **oba igrača 0/3** u zadnja 3 meča
- Grand Slam traži **65%** (hard i clay)
- grass mrtva zona 1,43-1,60 (na travi nikad na tiket)
- najviše **6 kandidata po turniru po danu**
- **NIJE na screenshotu** — od 11.08.2026 18:44 meč prolazi samo ako je njegov par na
  screenshotu (danas ∪ sutra), bez obzira na datum koji mu API dodijeli; bez ijednog
  screenshota run staje odmah. Vidi `_gate_by_screenshot`.
- **runde na razini TURNIRA** *(novo 13.08.2026 12:47)* — turnir smije imati najviše 1 F,
  2 SF i 4 QF kroz SVE dane; višak se spušta za rundu. Dnevna provjera je propuštala deset
  "polufinala" jer je svaki dan imao točno dva. Vidi `_verify_late_rounds`.
  **Prošireno 08.09.2026 12:07:** na Grand Slamu se provjeravaju i rane runde (8 R16,
  16 R32, 32 R64), jer je ondje ždrijeb uvijek 128 pa su brojevi nedvosmisleni. Time se
  ispravlja prvo kolo koje je API zvao "R64", a zapravo je R128 — na US Openu 2026 bilo
  je 69 redaka pod "R64" (smije 32). Ostale razine se u ranim rundama i dalje NE diraju.
  Isti dan popravljeno i dvostruko brojanje pri ponovnom pokretanju runa (isti meč se
  brojao kao živi zapis i kao vlastita "povijest" od prije par sati).
- **R128 izvan Grand Slama** — Masters ima ždrijeb od 96, ATP 250/500 od 28-32; R128 ondje ne
  postoji pa je oznaka kvalifikacijska (Cincinnati 11.08.). Screenshot poništava tu provjeru.

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

**Bira kombinaciju** (`_score_combo`): umnožak pouzdanosti kao glavni kriterij, plus bonus za
value (edge 3-20pp za favorite, 3-28pp za pickove ≥2,00), plus bonus za pouzdanost ≥72,
minus kazna za najslabiji pick, minus kazna za svaki par preko minimalnog broja nogu.

**NOVO 08.09.2026 12:07 — tržišni konsenzus ulazi u izbor kombinacije.**
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

## 3. Bilježi se, ali NE utječe na odluku — `context_snapshot` v17

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

---

## 4e. HIPOTEZA, NE ulazi u odluku — obrnuti Fery veto (30.08.2026 12:37)

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

### K1 — pickovi ispod praga 63% tuku tržište — **POTVRĐEN 08.09.2026 12:07, UŠAO U KOD**

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

### K2 — pravilo 11 (domaći teren) ide u krivom smjeru

    protivnik domaći (danas -3pp)   n= 30 | 70,0% | edge +7,5pp
    naš pick domaći  (danas  0pp)   n= 35 | 77,1% | edge +7,4pp
    nitko domaći                    n=271 | 62,4% | edge -1,9pp

Split-half drži u oba smjera, isto i samo na hardu. **PRAG:** još 20 mečeva s domaćim
igračem; ako protivnik-domaći ostane iznad +3pp, penal se briše iz prompta (mijenja
`rules_hash`, ide u paket s preslagivanjem prompta poslije US Opena).

### K3 — Bo5 pojas kvota 1,30-1,50

    Bo5 1,30-1,50  n=26 | 57,7% | tržište 69,9% | edge -12,2pp

Ista rupa marginalnog favorita koju znamo s harda, izraženija u Bo5. **PRAG:** n>=50 i
edge ispod -8pp na sljedećem Grand Slamu.

### K4 — omjer winneri/greške kao PRE-match varijabla

Post-match je najjača veza u projektu (r=+0,705). Sezonski ekvivalent ne postoji ni na
jednom endpointu koji koristimo. **PRAG:** ako se nađe izvor sezonskog winners/UE po igraču,
testirati kao pre-match ulaz; do tada isključivo za objašnjenje u analizi gubitaka.

### K5 — oprezna zona počinje prenisko: rupa je od 1,35, a kod pokriva od 1,43

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
