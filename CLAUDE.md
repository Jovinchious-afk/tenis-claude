# Tenis Claude — upute za Claude Code

Nastalo 27.09.2026 11:48 (korisnikova odluka). Odgovaraj na hrvatskom, jednostavnim jezikom,
kratko i s brojkama. Korisnik nije statističar: formule ne, brojke i "što to znači" da.

## Cilj projekta

**Dugoročno pozitivan ROI i bolji rezultat od tržišta i kladionica** (korisnikove riječi).
Mjeri se **edge naspram devigirane cijene** i **EV po kvoti koju stvarno igramo** (SuperSport),
ne postotak pogodaka. Trenutačno stanje i otvorena pitanja: `BACKLOG.md` ("ČEKA") i zadnji
izvještaj u `revizije/`.

## Kako radimo

- Svaki novi zadatak = nova sesija. Prijenos nose `BACKLOG.md` i memorija.
- Prije rada pročitaj "ČEKA" u `BACKLOG.md`; zakašnjele stavke spomeni korisniku.
- Dug ili neuredan zahtjev → `/oblikuj` (jasan zadatak + potvrda) prije rada.
- Svako mjerenje (je li nešto stvarno) → `/mjerenje`. Nalaz prije upisa u
  `DECISION_INPUTS.md` → subagent `skeptik`.
- Na kraju → `/kraj-sesije` (sat, testovi, changelog, BACKLOG, memorija).

## Pravila

1. **Kapija (od 06.09.2026):** nijedan nalaz ne ulazi u odluku dok se ne potvrdi na mečevima
   na kojima nije nađen, uz prag zapisan UNAPRIJED (`DECISION_INPUTS.md`, sekcija 0a). Ulazak
   u model uvijek odobrava korisnik.
2. **Uvijek kontrola cijene:** edge = stvarno − devigirana cijena; skupine se uspoređuju unutar
   istog pojasa cijene (Simpsonov paradoks). Kod berbi povijesti simetrično uzorkovanje.
3. **Snaga uzorka:** uz n=30 interval edgea je ±17pp, za 5pp treba ~560 pickova. Uz svaki prag
   napiši koliku razliku taj n može vidjeti. Varijable koje se daju izračunati iz povijesti
   prvo provjeri u povijesnom laboratoriju (`revizije/2026-09-27/skripte/lab_*.py`).
4. **Vrijeme:** svaki komentar u kodu, unos u `MODEL_CHANGELOG.md` / `BACKLOG.md` /
   `DECISION_INPUTS.md` i bilješka za reviziju nosi `DD.MM.GGGG HH:MM`, dohvaćeno naredbom
   `date "+%d.%m.%Y %H:%M"` neposredno prije upisa — nikad napamet ni procjenom.
5. **Dokumentacija:** svaka izmjena modela (prompt, pravila, odabir tiketa, težine, strategija,
   `context_snapshot`) → unos u `MODEL_CHANGELOG.md` (što / zašto / ishod) + hrvatski komentar s
   vremenom u kodu. Na kraju svake sesije `BACKLOG.md`: unos pod "NAPRAVLJENO" jednostavnim
   jezikom (što, čemu služi, gdje u kodu) i osvježen "ČEKA".
6. **Prompt analize** (`agent/predictor.py`): svaka izmjena teksta otvara novu eru
   (`rules_hash`) i reže korpus za mjerenja. Nakon izmjene premjeri duljinu odgovora naspram
   `_ANALYSIS_MAX_TOKENS` i napravi jedan živi poziv. Ništa što ide u prompt ne smije spominjati
   kvote ni favorite (model mora ostati neovisan o tržištu).
7. **Tihi null (15 slučajeva do sada):** kad je polje prazno u ~100% redaka, PRVO ispiši
   ključeve sirovog odgovora; provjeri i pisca i čitača polja; pazi na zadane vrijednosti
   (ELO 1500, 0 umjesto None) i duljine stupaca (VARCHAR).
8. **Runda je ručni unos korisnika** (od 26.09.2026) — nikad je ne pogađati automatski.
   Gate ide po PARU sa screenshota, ne po datumu.
9. Ne predlagati ponovno ono što je odbijeno ili izmjereno kao nula bez novih podataka
   (memorija i "ODBAČENO" u `DECISION_INPUTS.md`).

## Naredbe

- Testovi (moraju proći prije commita): `python test_cap_and_weather.py` i
  `python test_provisional_schedule.py`
- Kandidati iz registra: `python scripts/measure_candidates.py` (samo čita bazu)
- Povijesni laboratorij: vidi `revizije/2026-09-27/POVIJESNI_LAB_2026-09-27.md`
- Aplikacija: `streamlit run streamlit_app.py`
- Dnevni run: GitHub Actions `daily_ticket.yml` (ručno, jednom ujutro). Lokalni
  `python agent/run_daily.py --dry-run` troši plaćene pozive (Claude, RapidAPI) — samo uz dogovor.
- Na Windowsu uz Python ispis: `PYTHONIOENCODING=utf-8` (inače pada na č/ć/ž).

## Mapa

| gdje | što |
|---|---|
| `agent/predictor.py` | prompt analize, poziv modela, era (`rules_hash`), mjerene kazne |
| `agent/ticket_builder.py` | odabir nogu i tiketa (`_score_combo`, bonus za konsenzus) |
| `agent/run_daily.py` | jutarnji tijek: screenshot gate, ručne runde, dohvat, snapshot |
| `agent/data_fetcher.py` | RapidAPI, ELO, vrijeme, vijesti |
| `agent/player_news.py` | vijesti po igraču (Google News) — samo bilježenje, model ne vidi |
| `agent/feedback_analyzer.py` | večernji rezultati i analize gubitaka |
| `agent/market.py` | The Odds API konsenzus |
| `agent/player_context.py`, `agent/history_features.py` | varijable igrača, zaštita od curenja |
| `database/supabase_client.py`, `database/schema.sql` | pristup bazi (REST) |
| `pages/` | Streamlit stranice (Dnevni listić, Kvote sa screenshota...) |
| `scripts/` | mjerenja, backfill, izvještaji |
| `revizije/<datum>/` | izvještaji revizija i njihove skripte |
| `.cache/` | lokalni podaci izvan gita (tennis-data, TML, keševi) |

## Veliki dokumenti — ne čitati cijele

- `MODEL_CHANGELOG.md` (~6.000 linija): traži po datumu ili ključnoj riječi.
- `DECISION_INPUTS.md`: registar kandidata je sekcija 0a.
- `BACKLOG.md`: čitljiv pregled; "ČEKA" je na vrhu.
