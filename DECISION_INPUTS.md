# Što ulazi u odluku o picku — referentni popis

**Stanje na dan 13.08.2026 12:47.** Popisano na korisnikov zahtjev jer se dosad nigdje nije
vidjelo na jednom mjestu — ulazi su razasuti po promptu (`agent/predictor.py`),
determinističkom kodu (`agent/ticket_builder.py`) i zapisu (`context_snapshot`).

Ovo je **referenca, ne changelog.** Kad se nešto od navedenog promijeni, ažurirati ovdje i
zabilježiti izmjenu u `MODEL_CHANGELOG.md`.

---

## 1. Ulazi u ODLUKU — analiza (prompt, ~9.700 tokena)

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

- pouzdanost < **63%** — iznimka je value-override: conf ≥58 uz edge ≥12pp, najviše 2 po tiketu
- nije glavni tour, ili nema kvotu
- **Fery veto** — protivnik nas srušio 2+ puta u istom turniru unutar 14 dana
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
- **R128 izvan Grand Slama** — Masters ima ždrijeb od 96, ATP 250/500 od 28-32; R128 ondje ne
  postoji pa je oznaka kvalifikacijska (Cincinnati 11.08.). Screenshot poništava tu provjeru.

**Ograničava listić:**

- **4-6 parova**, ukupna kvota **6-40** (korisnikove fiksne granice)
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
value (edge 3-20pp za favorite, 3-28pp za pickove ≥2,00), plus bonus za pouzdanost ≥72, minus
kazna za najslabiji pick ispod 68, minus kazna za svaki par preko četiri.

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
