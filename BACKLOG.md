# Backlog i dnevnik rada

Čitljiv pregled projekta: **što čeka** (s uvjetom kada se radi) i **što smo napravili** (po
danima, jednostavnim jezikom). Brojke, obrazloženja i tehnički detalji su u
`MODEL_CHANGELOG.md`; popis svega što ulazi u odluku o picku je u `DECISION_INPUTS.md`
(dalje: DI).

**Pravilo:** na kraju svake radne sesije ovdje se dopiše što smo napravili i ažurira se
popis otvorenog. Otvoreno 26.09.2026 19:21, zadnje ažurirano 26.09.2026 20:46.

**Jedna naredba za sve zakazane provjere kandidata:** `python scripts/measure_candidates.py`
(čita bazu, ništa ne mijenja; kaže za svakog kandidata ČEKA / POTVRĐEN / PAO).

---

## ČEKA — zakazane provjere

Pravilo projekta (kapija, od 06.09.2026): nijedan nalaz ne ulazi u odluku dok se ne potvrdi
na mečevima na kojima nije pronađen. Svaka stavka ima prag zapisan UNAPRIJED.

| što | kada / uvjet | ishod | gdje |
|---|---|---|---|
| **K15 — ATP pobjede u sezoni** | 150 riješenih analiza od 27.09.2026 (procjena: druga polovica listopada) | potvrdi → bonus pri izboru tiketa; padne → odbacuje se | DI K15; `python scripts/measure_player_context.py` |
| **K16 — GS iskustvo u završnicama** | 40 mečeva QF/SF/F u kojima samo jedan igrač ima GS polufinale (više mjeseci) | +5pp ili više → razmotriti bonus u završnicama | DI K16 |
| **Omjer protiv ljevaka** | 300 mečeva s ljevakom (danas 120) | ponovno izmjeriti; do tada samo bilježenje | DI "IZMJERENO 26.09.2026" |
| **K1 — prag 60** | sljedeći dovršeni turnir | skupina 60-63 ispod nule uz n≥25 → prag natrag na 63 | DI K1 |
| **K17 — pick s "High" scouting profilom** | 30 takvih pickova od 27.09.2026 | ≤ −5pp → kazna −3pp; iznad nule → odbacuje se | DI K17; `measure_candidates.py` |
| **K18 — hard ATP 250 turniri** | 30 takvih pickova od 27.09.2026 (jesen je puna 250-ica) | ≤ −5pp → najviše jedna takva noga po tiketu; iznad nule → odbacuje se | DI K18 |
| **K19 — povratak nakon pauze od 21+ dan** | 40 mečeva od 27.09.2026 | isti smjer kao na tržištu → ±2pp; obrnuto → odbacuje se | DI K19 |
| **K5, K8, K9, K10, K11** | sljedeći dovršeni turnir (Chengdu/Hangzhou, pa Tokyo/Beijing) | svaki ima svoj prag; **K11 (R16/QF) se od 26.09. prvi put mjeri na ručnim rundama** | DI K5-K11; `measure_candidates.py` |
| **Konsenzus kladionica** | do kraja listopada 2026: 60+ pickova uz razliku ≥1pp — **vjerojatno nedostižno**: Odds API ne pokriva ATP 250, od 13.09. bilo je 0 takvih mečeva | iznad +5pp → tvrdi uvjet; ispod nule → maknuti bonus | `agent/ticket_builder.py`, blok uz `_CONSENSUS_GAP_MIN` |
| **K12 — prosjek statistike s turnira** | dubina 3+ uz kvotu dosegne n≥100 | interval i dalje prelazi nulu → samo bilježenje | DI K12 |
| **K14 — Davis Cup** | 20 riješenih Davis Cup mečeva (finalni turnir u studenom) | unutar 5pp od prosjeka → smije na tiket | DI K14 |
| **K2 — domaći teren** | još 20 mečeva s domaćim igračem | protivnik-domaći ostane iznad +3pp → kazna se briše iz prompta | DI K2 |
| **K3 — Bo5, kvote 1,30-1,50** | Australian Open, siječanj 2027 | n≥50 i ispod -8pp | DI K3 |
| **Clay težine** | prije prve zemlje 2027. (siječanj 2027.) | aktivna v17 nastala je iz auto-feedbacka na analizama gubitaka (ELO spušten na 11%) — vratiti na v13 ili izjednačiti s hardom | Supabase `model_weights`; MODEL_CHANGELOG 26.09.2026 20:46 |

## ČEKA — ideje i popravci bez roka

- **Drugi izvor tržišnog konsenzusa za ATP 250.** The Odds API pokriva samo GS, Masters i
  nekoliko 500-ica; na ostalim turnirima jedini potvrđeni tržišni signal ne postoji. Treba
  odabrati izvor (i možda platiti) — korisnikova odluka.

- **Vijesti po igraču.** ESPN i BBC od 13.09. nisu dali nijednu vijest o igračima koje
  analiziramo (0 od 43 analize) — pišu o vrhu tablice. Treba izvor koji traži po imenu
  igrača. Bez toga se K13 (vijesti o ozljedama) ne može izmjeriti.
- **Winston-Salem: traženje turnira odustaje nakon 5 pokušaja** pri razrješavanju rezultata,
  pa dio analiza ostane nerazriješen. Prijedlog od 31.08.2026, čeka odobrenje.
- **Nesigurnost brojki u promptu** (npr. hold% je procjena ±8pp, a prikazuje se kao
  činjenica). Otvoreno od 08.08.2026; ide uz sljedeću veću izmjenu prompta (DI točka 4).
- **Model može samo spustiti pouzdanost, nikad promijeniti stranu picka.** Otvoreno od
  29.08.2026.
- **Drugi AI model kao neovisni analitičar** (mjeri se predviđa li slaganje dvaju modela
  bolje od jednoga). Niski prioritet.

## Redovito održavanje

- **Ruka novih igrača:** dnevni run nepoznate igrače dohvaća sam (najviše 150 po runu), ali
  ih ne sprema trajno. Povremeno pokrenuti
  `python scripts/backfill_player_context.py --collect --hands` i commitati `player_hands.json`.
- **Provjera K15:** `python scripts/measure_player_context.py` (čita iz baze; gledati samo
  analize od 27.09.2026 za potvrdu).

---

## NAPRAVLJENO — dnevnik

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
