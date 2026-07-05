# Model Changelog

Kronologija promjena modela za generiranje tiketa (predikcija + selekcija + strategija).
Svrha: da kroz iteracije znamo ŠTO smo mijenjali, ZAŠTO, i s kojim ishodom.
Težinske verzije (brojčane) žive u Supabase `model_weights`; ovdje su prompt-pravila,
selekcijska logika i strateške odluke koje se ne vide iz baze.

Format: `datum — naslov` → što / zašto / ishod (ako je poznat).

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
