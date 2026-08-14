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
- **strop pouzdanosti 64%** *(novo 13.08.2026 12:47)* — iznad 64 model mora ispuniti
  `above_64_basis` s dvije mjerene potvrde (s brojkama, iz različitih kategorija) i rečenicom
  što bi ga oborilo; inače kod tvrdo spušta na 64 i bilježi `ceiling_enforced`. Razred 65-67%
  isporučivao je 50,0% uz ROI −34,8% (n=20)
- najviše **1 pick iz zone 1,43-1,60** *(suženo s 1,43-1,90 dana 08.08.2026 11:35)*

**Bira kombinaciju** (`_score_combo`): umnožak pouzdanosti kao glavni kriterij, plus bonus za
value (edge 3-20pp za favorite, 3-28pp za pickove ≥2,00), plus bonus za pouzdanost ≥72, minus
kazna za najslabiji pick ispod 68, minus kazna za svaki par preko četiri.

## 3. Bilježi se, ali NE utječe na odluku — `context_snapshot` v10

Vremenski uvjeti u punom obliku (temperatura, vlaga, vjetar, tlak na razini mora i na tlu,
uvjet, koliko je prognoza udaljena od sata meča); je li teren natkriven; je li meč u prvom
valu; odakle dolazi vrijeme početka i koji je bio raspoređeni sat; dob, nacionalnost, ruka;
zajednički protivnici; razina prethodnog turnira; pouzdanost scouting profila; žig verzije
modela (`rules_hash` + `weights_version`); je li cap okinuo i koje pravilo; ELO i ELO razlika;
koliko je protivnika ušlo u prosjek kvalitete; te **ispravljene verzije** povrata
(`return_won_weighted`) i holda (`hold_pct_from_bp`) usporedno s onima koje model stvarno
koristi.

Svrha: svaka buduća hipoteza mora se moći provjeriti retroaktivno umjesto pogađati.

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
