# Izmjene 08.11.2026 — za pregled (GPT-astra): nos-odluka i provedba revizije

Pisano 08.11.2026 16:44. Ovaj dokument je napisan za drugi AI koji pregledava **kod, rezultat, tok i
logiku**, i za vlasnika projekta. Projekt je tenis-agent: Claude analizira mečeve, a kod slaže
akumulatorski tiket (3–6 nogu, ukupna kvota 4–50, prag pouzdanosti 63). Kontekst revizije je u
`REVIZIJA_2026-11-08.md`, a pravila projekta u `CLAUDE.md`.

---

## 1. Što je naređeno i zašto je važno za pregled

Vlasnik je 08.11.2026 odlučio da "nos" mora dobiti **pravo odluke** pri slaganju tiketa. Pod nosom se
misli na Nose, nos-ploču i scouting. Izričito je rekao da ga ne zanima ako je učinak slučajan na malom
uzorku.

Projektno pravilo 1 ("kapija") inače traži potvrdu svakog nalaza na novim mečevima prije ulaska u
odluku. Ovdje je to svjesno preskočeno odlukom vlasnika. Zato je kod napravljen tako da:

1. **sve bilježi**: `context_snapshot["nos_odluka"]` uz svaku analizu;
2. **računa usporedbu** "što bi tiket bio bez nosa", bez plaćenih poziva;
3. ima **prekidače** `NOS_ODLUKA_ON` / `NOS_AUTSAJDER_ON` u `config/model_config.py`;
4. ima **praćenje s pragom zapisanim prije podataka**: K27/K27b u `DECISION_INPUTS.md` i
   `scripts/measure_candidates.py --only K27`.

**Prompt analize i era (`rules_hash`) nisu dirani.** Test to provjerava.

---

## 2. Tok dnevnog runa (`agent/run_daily.py`), novo stanje

```
dohvat mečeva -> screenshot-kapija -> analize (Claude, predictor.analyze_matches_batch)
  -> [NOVO] h2h + marža kvota u snimku (P3/P6)
  -> TML forma -> Nose -> nos-ploča          (PREMJEŠTENO ispred tiketa; prije je bilo iza)
  -> [NOVO] NOS-ODLUKA:
       ucitaj_tezine()  (NOS_TEZINE_PATH s GitHuba ili config/nos_tezine.json)
       predlozi_bez_pregleda(predictions)  -> skup "bez nosa" (usporedba)
       primijeni(predictions, tezine)      -> pred["confidence"] = model + ocjena (±6), čuva _nos_model
                                           -> lista kandidata za nos-autsajdera (nove predikcije)
  -> build_ticket(..., nos_autsajderi=...)    (_select_combo -> _nos_autsajder_u_tiket -> Claudeov pregled)
  -> [NOVO] oznaci_tiket() + vrati_model()    (u bazu ide MODELOVA pouzdanost)
  -> [NOVO] ispis jučerašnjih nogu (P2)
  -> Intuicija (i dalje IZA tiketa) -> upis u Supabase -> e-mail
```

GitHub (`.github/workflows/daily_ticket.yml`) prije runa pokreće korak "Nose learns". On izvodi
`scripts/nos_tezine.py`, a rezultat ide u `$RUNNER_TEMP/nos_tezine.json` i `NOS_TEZINE_PATH`. Korak ima
`continue-on-error` i samo čita bazu.

---

## 3. Logika nos-odluke (`agent/nos_odluka.py`)

### 3.1 Znakovi (`znakovi(rec, za_igraca=None)`)

- **Iz nos-ploče** (`agent/nos_ploca.compute`) dolazi 14 znakova s istim definicijama. Tri su
  namjerno izostavljena:
  - `pick_autsajder` — u predictoru već postoji mjerena kazna −5, pa bi se brojao dvaput;
  - `ozljeda_pick` / `ozljeda_prot` v2 — detektor v2 pripisuje ozljedu krivom igraču.
- **Novih 8 znakova:**
  - `ozljeda_*_v3`;
  - `scout_jak` (High/Med-High);
  - `elo_jak` (ELO na podlozi ≥ +150, a 1500 se tretira kao zadana vrijednost, ne podatak);
  - `pojas_120_135`;
  - `jutro` (< 13 h lokalno);
  - `nose_plus` / `nose_minus` (Noseova razlika naspram cijene ±5pp za TU stranu; u snimci je
    razlika za modelov pick, pa se za drugu stranu okreće predznak).
- Za stranu protivnika (`za_igraca`) ploča se računa s okrenutim pickom.

### 3.2 Učenje (`nauci`, `_ridge`; poziva ga `scripts/nos_tezine.py`)

- **Podaci:** riješeni pickovi u prozoru [danas − 120 dana, danas). Ostatak = pobjeda − devigirana
  SuperSport cijena picka.
- **Opis:** zaseban učinak svakog znaka, u istom pojasu cijene; za cjenovne znakove naspram ostalih.
  Ovaj broj se samo ispisuje.
- **Odluka:** ridge svih znakova zajedno, uz nekažnjeni slobodni član; λ = `K_SKUPLJANJE` (60) po znaku.
- **Predznak** smije biti samo onaj iz definicije: mina ≤ 0, prilika ≥ 0, a "opis" je slobodan. Znak
  krivog predznaka izbacuje se i model se ponovno računa (aktivni skup).
- **Strop** je ±`STROP_ZNAK` (4) po znaku; za znak treba n ≥ `MIN_N` (8).

### 3.3 Odluka (`primijeni`)

- `ocjena` = zbroj težina upaljenih znakova, sa stropom ±`STROP_UKUPNO` (6).
- `pred["confidence"] = model + ocjena`, a `fair_odds = 100 / conf`. To čitaju prag 63, kaskada,
  dnevni limiti i `_score_combo`.
- Modelove vrijednosti čuvaju se u `pred["_nos_model"]`, a `vrati_model` ih vraća prije upisa u
  `analyzed_matches`.

### 3.4 Nos-autsajder (`_autsajder` -> `ticket_builder._nos_autsajder_u_tiket`)

**Uvjeti** (svi moraju vrijediti):

- Nose `vs_market.opp_value` je istina;
- Noseov p protivnika − cijena protivnika ≥ +5pp;
- kvota protivnika je 2,00–3,50;
- modelova pouzdanost ≤ 64;
- ocjena ne-cjenovnih znakova za protivnika ≥ 0.

**Kandidat** je kopija predikcije s okrenutim pickom: `confidence` = Noseov p×100,
`nos_autsajder = True`, a `risk_notes` počinje s "NOS-AUTSAJDER".

**Na tiketu** je najviše jedan, i to onaj s najvećom Noseovom prednošću:

- isti meč je na tiketu → noga se okreće;
- inače zamjenjuje najslabiju nogu, a ako to ne prolazi, dodaje se;
- tiketa nema → najbolja kombinacija favorita + autsajder;
- sve prolazi kroz `_combo_rules_ok`: 3–6 nogu, kvota 4–50, zone, jedan meč jednom.

**Claudeov recenzent** ne smije maknuti tu nogu. Ako je ipak makne, ostaje predloženi tiket
(`build_ticket`). U recenzentov prompt dodan je jedan redak; to nije prompt analize.

### 3.5 Refaktor

Izbor kombinacije izdvojen je iz `build_ticket` u `_select_combo`. Tijelo je premješteno bez promjene
logike. `predlozi_bez_pregleda` zove `_select_combo` bez ispisa, za usporedbu.

---

## 4. Ostale izmjene (provedba revizije 08.11.)

| oznaka | što | gdje |
|---|---|---|
| P1 | detektor ozljeda v3: naslov s drugim poznatim igračem se ne broji; riječ o tijelu bilo gdje ako je igrač sam; "physiotherapist" nije ozljeda; spremaju se `injury_n3` i svi označeni naslovi (`inj_items`); v2 netaknut | `agent/player_news.py` (`strict_injury_v3`, `_known_surnames`, `parse_feed`) |
| P1 | nos-ploča uz znak ozljede prikazuje naslov (definicija znaka nepromijenjena) | `agent/nos_ploca.py` |
| P2 | popis "samo analiza": prvo pickovi 63+ po pouzdanosti (prije: 12 najvećih kvota) | `ticket_builder.build_analysis_only_ticket` |
| P2 | ispis jučerašnjih nogu i razloga zašto (ne) idu danas | `run_daily.py` |
| P3 | `context_snapshot["h2h"]` (RapidAPI H2H koji model vidi; do sada se nije spremao) | `run_daily.py` |
| P6 | `odds_margin_pct` i glasno upozorenje za kvote bez marže (6% parova) | `run_daily.py` |
| P5 | Dnevni listić: nos-odluka po paru, tablica težina, autsajderi po rundi | `pages/1_Dnevni_Listic.py` |
| — | snimka v24 | `agent/predictor.py` (samo `context_version` i komentar) |
| — | mjerenja K13c (v3) i K27/K27b (nos-odluka) | `scripts/measure_candidates.py` |

---

## 5. Rezultati koji su bili poznati prije uvođenja

Sve je bez plaćenih poziva. Skripte su u `revizije/2026-11-08/skripte/`, ispisi u
`.cache/rev_2026-11-08/`.

**Pariz izvan uzorka** (`r_nos_replay.py`, težine samo do 01.11.):

| skupina | n | ishod | edge |
|---|---|---|---|
| pickovi koje nos podiže | 35 | 24–11 | −1,6pp |
| pickovi koje nos spušta | 11 | 5–6 | −9,0pp |
| nos-autsajderi | 4 | 2 pogođena | ROI +52% |

**Hod naprijed 27.09.–07.11.** (`r_nos_varijante.py`, 5 turnirskih tjedana, 11 inačica zadanih
unaprijed, težine uvijek samo prije dana, bez Claudeova pregleda):

| inačica | tiketa | dobitnih | ROI | edge nogu |
|---|---|---|---|---|
| bez nosa | 17 | 5 | +24% | +5,9pp |
| prozor 60 | 29 | 8 | +63% | +12,2pp |
| **prozor 120 (postavljena)** | 26 | 7 | +62% | **+14,3pp** |
| samo autsajder | 22 | 7 | +73% | +8,9pp |
| samo pouzdanost | 28 | 6 | −10% | +6,7pp |
| samo pouzdanost, prozor 120 | 26 | 5 | −21% | +8,6pp |

**Svi jedinstveni kandidati za nos-autsajdera** (27.09.–07.11.): 7 od 25 pogođeno, ROI −28%. U
simulaciji tiketa prošli su bolje (8 od 14 nogu), zbog dva razloga:

- na tiket ide samo najjači kandidat dana (4 od 9);
- isti meč se zna pojaviti dva dana zaredom.

**Testovi:**

- `test_cap_and_weather.py` (nova sekcija 56: 29 provjera znakova, učenja, stropova, odluke, povrata,
  autsajdera u svim granama (i Davis Cup, i nos bez težina), popisa "samo analiza", detektora v3, ugradnje u run i netaknutog
  `rules_hash`) — SVI PROŠLI;
- `test_provisional_schedule.py` — SVE PROŠLO;
- Dnevni listić iscrtan bez iznimke (Streamlit AppTest).

---

## 6. Poznati rizici i ograde (molim posebnu pažnju)

1. **Prenaučenost.** Težine se uče na našim pickovima (n ≈ 750 u 120 dana). Na 12.436 povijesnih mečeva
   nijedan predmečni znak nije pobijedio cijenu. Velik dio "učinka" je vjerojatno razdoblje, a ne
   vještina. Ridge, predznak i stropovi samo ograničavaju štetu.
2. **Izbor inačice na istom uzorku.** 11 inačica na ~20–29 tiketa; razlike ROI-ja drži nekoliko
   tiketa.
3. **Nos-autsajder** na svim kandidatima ima negativan zapis (7/25). Ostavljen je uključen jer je
   vlasnik izričito tražio rizik na autsajderima. K27b ima prag za isključenje.
4. **Simulacija nije vjerna kopija.** Nema Claudeova pregleda; predikcije su zadnja spremljena analiza
   meča; mečevi D+1 čiji igrači igraju na D su izbačeni (artefakt "isti igrač dvaput").
5. **Više tiketa.** Nos diže više pickova preko 63 nego što ih spušta (Pariz: 13 gore, 0 dolje), pa
   ima više dana s tiketom i više izloženosti akumulatoru.
6. **Kratke kvote.** Jak ELO, pojas 1,20–1,35 i noć su često isti mečevi zvijezda. Ridge to dijeli, ali
   nos će gurati prema kraćim kvotama, a za kvotu 4+ tada treba više nogu.
7. **Pouzdanost je i dalje "mrtva"** (Brier gori od konstante; memorija projekta). Nos zato zapravo
   zamjenjuje njenu ulogu svojom ocjenom, a ne popravlja je.

---

## 7. Kako provjeriti

```bash
PYTHONIOENCODING=utf-8 python test_cap_and_weather.py        # sekcija 56 = nos-odluka
PYTHONIOENCODING=utf-8 python test_provisional_schedule.py
PYTHONIOENCODING=utf-8 python scripts/nos_tezine.py --suho    # težine koje bi danas vrijedile
PYTHONIOENCODING=utf-8 python revizije/2026-11-08/skripte/r_nos_varijante.py   # simulacija inačica
PYTHONIOENCODING=utf-8 python scripts/measure_candidates.py --only K27        # praćenje od 09.11.
```

U ispisu sutrašnjeg runa traži:

- `Nos-odluka (nos-odluka-v1; težine ...)`;
- retke `ime  61 -> 67  znak +x`;
- `NOS-AUTSAJDER kandidat`;
- `tiket bez nosa imao bi N nogu; zajedničkih ...`;
- `Jučerašnji tiket:`;
- `Kvote bez marže`.

**Povratak:**

- `NOS_ODLUKA_ON = False` (stari izbor, bilježenje ostaje);
- `NOS_AUTSAJDER_ON = False`;
- `git revert` commita.

---

## 8. Pitanja za pregled

1. Je li **povrat modelove pouzdanosti** (`vrati_model`) na svakom putu prije upisa u bazu? Uključeni su
   put "samo analiza" i iznimka u nos-bloku.
2. Može li `_nos_autsajder_u_tiket` ikad složiti tiket koji krši pravila iz `_find_best_combination`?
   Usporedi `_combo_rules_ok` sa zonama i rasponom. Može li dva puta uzeti isti meč?
3. Je li **predznak u `znakovi`** za Nose ispravan kad se računa za protivnika (okretanje `diff_pp`)?
4. Je li `nauci` pošten: prozor `[danas − 120, danas)`, nikad isti dan? Je li ridge s aktivnim skupom
   za predznak razuman ili bi trebao NNLS po znaku?
5. Je li `_select_combo` doista izvučen bez promjene ponašanja?
   - Provjereno 08.11.2026 16:46: stari `build_ticket` iz commita `1b3c3d4` (s isključenim Claude
     pozivima) i novi `predlozi_bez_pregleda` izabrali su iste noge na 41 od 41 dana (27.09.–07.11.).
   - Ponovi neovisno.
6. Smije li recenzentu biti zabranjeno micanje nos-autsajdera, ili bi to trebalo samo upozoriti?
7. Detektor v3: bi li popis `_NOT_A_PLAYER` / gradova trebao biti širi? Isti problem može nastati kad je
   prezime ujedno obična riječ.
