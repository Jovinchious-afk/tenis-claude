# Model Changelog

Kronologija promjena modela za generiranje tiketa (predikcija + selekcija + strategija).
Svrha: da kroz iteracije znamo ŠTO smo mijenjali, ZAŠTO, i s kojim ishodom.
Težinske verzije (brojčane) žive u Supabase `model_weights`; ovdje su prompt-pravila,
selekcijska logika i strateške odluke koje se ne vide iz baze.

Format: `datum — naslov` → što / zašto / ishod (ako je poznat).

---

## 2026-07-11 — Clay revizija: pravila v1 + težine v8 + selekcijska disciplina (prije Gstaad/Umag)

**Povod:** kompletna revizija clay modela na 32 razriješena picka (28 RG BO5 + 4 ATP 250
kvalifikacije): 17W-15L (53%) uz prosječni confidence 69% (prekalibracija −16pp), **svih 7
čistih clay tiketa izgubljeno**. Dominantan uzrok gubitaka: fade igrača s in-tournament
momentumom (8/15 — Menšik 3×, Arnaldi 2×, Fonseca 2×, Svajda). Dead zone kvota 1.50-1.90
na clayu 3/11 (27%), ista strukturna bolest kao grass. Zona confidence 66-70% pobjeđivala 38%.

**Što (potvrdio korisnik):**
- **CLAY-SPECIFIC RULES v1** u predictor promptu (clay dosad NIJE imao nijedno surface
  pravilo): dvostruka potvrda (2 od 3: clay record / hold% / quality-adjusted forma),
  hot-hand veto s elitnom iznimkom (clay ELO ≥1850 ili hold ≥85%), oba-u-padu cap 60%,
  rest differential −4pp (BO5 −6pp), ranking-gap deflacija, underdog disciplina,
  home-crowd pravilo (asimetrično: domaći protivnik −3pp / skip; naš domaći bez bonusa),
  qualifying guard, clay kalibracijski spread, BP-conversion preko aseva.
- **Ticket builder:** confidence floor 63% + value-override (58%/12pp/max 2) prošireni
  s grassa na clay; **clay raspon kombinirane kvote 6.5-30 i max 6 parova** (korisnikova
  odluka; global ostaje 6.5-40/7); max 1 clay pick u dead zoni 1.50-1.90 po tiketu;
  R128/Q na ATP 250/500 = kvalifikacije → nikad na tiket (11.07. su 4 kvalifikacijska
  meča ušla kao "ATP 250 R128", 2/4 pala); edge >20pp ne dobiva score bonus (umišljeni
  edge = naša greška, ne value — Collignon @2.82 lekcija); reviewer dobio clay checkove.
- **fair_odds popravak (sve podloge):** LLM-ov fair_odds gravitirao na ~1.52 neovisno o
  meču (12/15 clay gubitaka fair 1.51-1.54 na kvotama 1.28-2.82) → sada fair_odds =
  100/confidence u postprocessingu, value = edge ≥3pp prema stvarnoj kvoti. Edge/value
  mehanika prvi put stoji na konzistentnoj osnovi.
- **Težine v8 clay** (Supabase): elo 22→18, form 20→18, fatigue 11→12, trajectory 4→9;
  surface 20, serve 19, h2h 4 nepromijenjeni.
- **Podaci:** Country u analysis promptu (za home pravilo — nationality je već bila u
  fetchu); altitude tablica + Gstaad 1050 m i Kitzbühel 762 m, pragovi 1500/800 → 1000/600
  (Gstaad se dosad analizirao kao razina mora).

**Zašto:** vidi analizu u sesiji 11.07. — retroaktivno bi pravila eliminirala/degradirala
9-10 od 15 gubitaka uz gubitak 0-1 od 17 dobitaka. Oprez: korpus je malen (n=32) i 87%
s jednog kaotičnog RG-a — pravila su pisana kao mehanizmi (veto/cap/dvostruka potvrda),
brojčani pragovi (1850, 85%, 5pp) su početni i revidiraju se nakon Gstaad/Umag/Båstad
ciklusa. Strukturni nalazi (dead zone, overconfidence 66-70, hot-hand) neovisno potvrđeni
na grass korpusu (n=177).

**Ishod:** prati se.

---

## 2026-07-05 — Grass value-override (value smije proći ispod floora)

**Što:** Grass floor (≥63% confidence) dobio iznimku za **standout value** oklade: grass pick
ispod 63% prolazi ako je confidence ≥58% I edge ≥12pp, najviše 2 takve po listiću (top po edge-u).

**Zašto:** Osnovna filozofija je VALUE, ne lov na niske kvote. Apsolutni floor od 63% odbacivao je
odlične value oklade (npr. model 61% vs tržište 42%, edge 19pp, kvota 2.35 = +43% EV) samo zbog
niskog apsolutnog confidence-a. Edge = usporedba s tržištem → legitimna upotreba kvote, različito
od "biranja niske kvote". Omogućuje povremeni opravdani 15-25 listić.

**Rizik:** edge ovisi o kalibraciji `fair_odds` (nova od v3). Zato oprezan start: prag 12pp, kap 2,
min conf 58%. Ako se pokaže presuho → spustiti prag. Prati se.

**Ishod:** prati se.

---

## 2026-07-05 — Grass prompt v3 + spuštanje floora na 6.5

**Što:**
- Uklonjen tvrdi cap confidence-a od 64% → uvedeno **širenje** (dominantni favoriti 72-80%,
  coinflipovi <60%). Cilj: vratiti confidence kao koristan signal za rangiranje.
- Kombinirana kvota floor: **9.0 → 6.5** (raspon 6.5-40). Maknut poseban 4-mec override
  (jedinstvena, stabilna granica).
- Grass rule 10 (novo): tiebreak + serve-hold (85%+) kao ODLUČUJUĆI faktor, ne "rizik".
- Grass rule 2 pooštren: hard/clay forma se NE prenosi na travu.

**Zašto:** Post-Wimbledon analiza (n=51). Model odličan na teškim favoritima (kvota ≤1.42 → 78%),
katastrofa u "mrtvoj zoni" (1.43-1.90 → 20%; 1.43-1.60 doslovno 0/7). Confidence spljošten na
62-64% (cap ubio diskriminaciju). 9.0 floor je matematički forsirao dead-zone pickove → 3/3
prava tiketa izgubljena. Vidi memoriju `grass-model-structural-finding`.

**Ishod:** prati se. Commit `865faa6`.

---

## 2026-07-05 — Analysis-only cap 12 + hipotetski "forced risk" u mailu

**Što:** Analysis-only ograničen na max 12 mečeva (sortirano po kvoti), izbačene kvote <1.06.
Dodana email sekcija "🎯 If I had to risk it..." — najbolji 4-7 pick / 9-40 tiket kad bismo baš
morali (Claude Haiku), samo u mailu, ne u bazu.

**Zašto:** 18 mečeva u analysis-only bilo je previše; korisnik želi info "kad bih morao riskirati".

---

## 2026-06-27 — Učenje iz tipova + trajno spremanje rezultata/statistika

**Što:** Evening update sada sprema `actual_score` i `match_stats` (JSONB) za svaki razriješen
meč (pobjeda I poraz, sve podloge). Petlja za korekciju težina uči i iz DOBITAKA, ne samo gubitaka.

**Zašto:** Gradnja korpusa "hipoteza prije meča vs stvarni ishod + brojke" za buduće korekcije.
Agent je prije učio samo iz pola slike (samo gubici).

---

## 2026-06-27 — Grass težine v12

**Što:** elo_ranking 14→16, serve_return 21→23, recent_form 18→15, tournament_trajectory 8→7.
**Zašto:** Umjeren povrat prema serve/ELO (dokazani dobitni signal); "forma-preko-ELO" doktrina
iz v10/v11 sistemski gubila. (Supabase model_weights v12.)

---

## 2026-06-22 — Grass prompt v2 + težine v11 + confidence floor

**Što:**
- Grass floor u ticket builderu: grass pick mora ≥63% confidence PRIJE selekcije; ugašena
  kaskada 58/55 i edge-override ZA TRAVU (koristi modelov confidence, ne kvotu).
- Grass prompt v2: 8→9 pravila (ELO isolation, surface-weighted forma, fatigue zaoštren,
  bye=hendikep, oba 1/3 → cap 60%, conf cap 64%, honesty floor).
- Grass težine v11: elo 17→14, trajectory 4→8, fatigue 12→13, serve 22→21.

**Zašto:** 6 uzastopnih izgubljenih tiketa na travi (16-22.06). Analiza 14 gubitaka.

---

## 2026-06-16 — Grass prompt v1 + težine v10

**Što:** Prva grass-specifična prompt pravila (ELO cap 100pt, rest paradox, fatigue+momentum).
Težine v10: elo 22→17, form→19. **Zašto:** analiza 12 grass gubitaka; ELO precijenjen.

---

## 2026-06-04 — Surface-specifične težine + tournament_trajectory

**Što:** Odvojene težine po podlozi (clay/grass/hard). Dodan 7. faktor `tournament_trajectory`
(in-tournament momentum). Grass v8: serve-heavy (serve 25, surface 22).

---

## Ranije (2026-05-27 → 06-03) — Temelj

Inicijalni model, uklonjen `odds_movement` faktor (model misli neovisno o tržištu),
dodani: surface record, tournament record, quality-adjusted forma, hold%, avg opp ELO,
H2H reliability, round context, draw-history (anti-halucinacija), ELO cache.
