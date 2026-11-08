# Sve promjene 08.11.2026 — što smo danas uveli, što zadržali i što gledamo nakon Stockholma

Zapisano 08.11.2026 17:28, na kraju radnog dana. Ovo je jedan pregled cijelog dana. Detalji i brojke
su u izvještaju `REVIZIJA_2026-11-08.md`, tehnički opis za pregled u `IZMJENE_ZA_PREGLED_2026-11-08.md`,
a zapis po satima u `MODEL_CHANGELOG.md` (08.11.2026 12:07, 16:38 i 17:28).

## Ukratko

- **Glavna promjena:** od sutra (Stockholm, 09.11.) **nos ima pravo odluke** pri slaganju tiketa. To je
  tvoja odluka, uvedena bez kapije, ali sa zapisom, usporedbom i prekidačem.
- **Prompt analize i era (`rules_hash`) NISU dirani.** Prag 63, 3–6 nogu i kvota 4–50 ostaju.
- Navečer smo provjerili kazne, prag i bodovanje. **Sve ostaje**, a dva sitna dijela idu na prosinac.

---

## 1. Što je UVEDENO u odluku (mijenja tiket od 09.11.)

| što | čemu služi | gdje u kodu | kako isključiti |
|---|---|---|---|
| **Nos-odluka v1** | svaki pick dobiva ocjenu nosa iz znakova (jak ELO, kvota 1,20–1,35, noć, scouting, profil protivnika, jutro, Noseovo upozorenje, mlađi pick, pauza...); ocjena pomiče pouzdanost ZA TIKET najviše ±6 boda | `agent/nos_odluka.py`, `agent/run_daily.py` | `NOS_ODLUKA_ON = False` u `config/model_config.py` |
| **Nos-autsajder** | najviše JEDNA noga na autsajdera kad Nose vidi vrijednost na protivniku, a model nije uvjeren (kvota 2,00–3,50); recenzent je ne smije maknuti | `agent/ticket_builder.py` (`_nos_autsajder_u_tiket`) | `NOS_AUTSAJDER_ON = False` |
| **Nos uči svako jutro** | GitHub prije runa nauči težine iz svih riješenih pickova zadnjih 120 dana | `scripts/nos_tezine.py`, `.github/workflows/daily_ticket.yml`; rezerva `config/nos_tezine.json` | — |
| **Redoslijed runa** | Nose i nos-ploča računaju se PRIJE tiketa (prije su bili iza) | `agent/run_daily.py` | — |

U bazu i dalje ide **modelova** pouzdanost, pa mjerenje modela nije prekinuto. Nosova pouzdanost ide
samo na noge tiketa i u snimku (`context_snapshot["nos_odluka"]`).

**Zašto baš ovakav nos:** simulacija na pet turnirskih tjedana (27.09.–07.11.) usporedila je 11 inačica.

| | tiketa | dobitnih | ROI | edge nogu |
|---|---|---|---|---|
| odabrani nos (prozor 120 dana) | 26 | 7 | +62% | +14,3pp |
| bez nosa | 17 | 5 | +24% | +5,9pp |

**Ograda:** svi kandidati za autsajdera zajedno pogodili su 7 od 25 (ROI −28%). Razliku drži nekoliko
tiketa, pa pravu presudu daje K27.

## 2. Ostale izmjene danas (ne mijenjaju izbor pickova)

| što | čemu služi | gdje |
|---|---|---|
| detektor ozljeda v3 | ozljeda se više ne pripisuje krivom igraču (Fils–Fritz); spremaju se svi označeni naslovi | `agent/player_news.py` |
| nos-ploča pokazuje naslov uz znak ozljede | da odmah vidiš o kome je vijest | `agent/nos_ploca.py` |
| popis "samo analiza" po pouzdanosti | prije je pokazivao 12 najvećih kvota (Fritz @1,21 uz 70 je nestajao) | `ticket_builder.build_analysis_only_ticket` |
| ispis jučerašnjih nogu | zašto se par s jučerašnjeg tiketa danas (ne) pojavljuje | `agent/run_daily.py` |
| H2H i marža kvota u snimci | H2H koji model vidi sada se sprema; glasno upozorenje za kvote bez marže (6% parova) | `agent/run_daily.py`, snimka v24 |
| Dnevni listić | nos-odluka po paru, tablica težina nosa, autsajderi po rundi | `pages/1_Dnevni_Listic.py` |
| scouting top 150 | 79 rangova osvježeno (56 + 23 iz TML-a), tekst profila bez izmjene | Excel + Supabase `player_scouting` |
| mjerenja | K13c (ozljeda, detektor v3) i K27/K27b (nos-odluka, nos-autsajder) | `scripts/measure_candidates.py` |

## 3. Što smo PROVJERILI i ZADRŽALI (večer, ništa se ne mijenja)

| mjera | brojke | odluka |
|---|---|---|
| kazna Med-Low −4 | pickovi koje je spustila ispod 63 pogodili su 3 od 11 (kvota očekivala 63%) | **ostaje** |
| kazna za pojas 65–68 −5 | −3,7pp (n=48) i −4,4pp (n=100), sve četiri polovice u minusu | **ostaje** |
| kazna za tržišnog autsajdera −5 | danas otprilike nula (+5,4pp n=19; −1,6pp n=44) | ostaje **do prosinca** |
| prag 63 | pickovi 60–62,9 slabiji za −9,0pp (n=105) | **ostaje** |
| bodovanje tiketa | sitni dijelovi mijenjaju 1–2 noge u 41 dan; tržišna cijena umjesto pouzdanosti lošija (+50% naspram +62%) | **ostaje** |
| "maknuto iz modela" kao znak nosa | konsenzus −5,4pp, pobjede u sezoni −7,3pp, tie-break −3,0pp, izjednačen servis −2,7pp; forma i povijest turnira bez učinka | **ne dodaju se** |

Komentari s brojkama stoje uz kod: `agent/predictor.py` (iznad `_SCOUTING_MEDLOW_PENALTY`),
`agent/ticket_builder.py` (prag 63 i `_score_combo`) i `agent/nos_odluka.py` (iznad `PROZOR_DANA`).

## 4. Plan za prosinac (zimska pauza, zajedno s čišćenjem prompta)

1. **Kazna za autsajdera −5 → naučeni znak nosa.** Nos sam uči koliko vrijedi, a fiksni broj nestaje.
   Usput nestaje i dvostruko brojanje (zato je `pick_autsajder` sada izvan nosa).
2. **Value bonus u bodovanju → maknuti ili zamijeniti znakom nosa po pojasu kvote.** Bonus potiče kvote
   oko 1,85–1,90, gdje od 17.08. gubimo (1,65–1,85 −6,0pp; 1,85+ −8,1pp).
3. Za obje točke vrijedi isto: prije uvođenja simulacija hodom naprijed na svim tjednima do tada, i to
   tek uz tvoje odobrenje.
4. Novi kandidat za nos: **točan H2H iz TML-a** (RapidAPI H2H je nepotpun). Ograda: povijesni
   laboratorij nije našao da H2H tuče tržište, pa je ovo pokušaj, a ne obećanje.
5. Ostalo za prosinac stoji i u `BACKLOG.md`: čišćenje prompta (P6 iz 25.10. i stavke iz Šangaja) i
   K25 test B (~700 mečeva).

## 5. Što gledamo nakon Stockholma

1. **Prvi run s nosom (09.11.)** — u GitHub ispisu dnevnog runa pogledati redak "Nos-odluka (...)":
   - jesu li težine učitane (piše datum i broj pickova; "NEMA — nos šuti" znači da učenje nije uspjelo);
   - "preko praga" i "ispod praga" — koliko je pickova nos pomaknuo preko ili ispod 63;
   - "NOS-AUTSAJDER kandidat" — je li predložen autsajder i je li ostao na tiketu.
2. **Tiketi s nosom naspram "bez nosa"** — run svaki dan ispisuje redak "tiket bez nosa imao bi N nogu;
   zajedničkih X, nos dodao Y, nos maknuo Z". Snimka uz svaki pick bilježi bi li bio na tiketu bez nosa.
   Ishode za cijeli Stockholm usporediti po tim bilješkama. To je anegdota, a presuda dolazi tek kod K27.
3. `python scripts/measure_candidates.py --only K27` — prvo stanje (presuda tek na 40 + 40 nogu).
4. `python scripts/measure_candidates.py --only K13c` — ozljeda protivnika, detektor v3 (prvih 30).
5. **Intuicija (K20):** mail sa stanjem stiže sam 15.11.2026, a sljedeća sesija mora javiti stanje.
6. **GPT-astra pregled** — ako je našao grešku u kodu ili logici, prvo to ispraviti.

## 6. Kako vratiti ako nos šteti

- Samo autsajder van: `NOS_AUTSAJDER_ON = False` u `config/model_config.py`, pa commit i push.
- Cijeli nos van (stari izbor tiketa): `NOS_ODLUKA_ON = False`, pa commit i push.
- Sve izmjene dana (krajnja mjera): `git revert bf185c9`, pa push.
- Prijedlog za isključenje daje K27 prema pragu zapisanom unaprijed (dodao − maknuo ≤ −5pp).
