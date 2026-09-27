# Pregled prompta analize prema Claudeovim uputama — 27.09.2026 11:57

**Samo izvještaj. Prompt NIJE mijenjan** (era `9696c4ee` ostaje; svaka izmjena teksta otvara
novu eru i reže korpus za K1/K5/K11). Postupak: `/claude-api prompt-audit` (službeni vodič za
pregled promptova, stavke "Group 1–4" i "keep list").

## Pretpostavke

- **Opseg:** prompt analize u `agent/predictor.py` — `_ANALYSIS_SYSTEM_TEMPLATE` (433–688),
  `ANALYSIS_PROMPT_TEMPLATE` (689–844), pravila po podlozi (`_surface_specific_rules`, grass
  u funkciji od 888, `_CLAY_RULES_V1` od 1030, `_HARD_RULES_V1` od 1206) i kod poziva
  (`_call_analysis_model`, 1439). Nisu pregledani: prompt analize gubitka i prijedloga težina
  (`feedback_analyzer.py`), `ticket_writer` i čitanje screenshota — manji utjecaj na odluku.
- **Ciljni model:** `claude-sonnet-4-6` (to kod stvarno zove, `config/model_config.py`
  `CLAUDE_MODELS`). Za eventualni prelazak na Sonnet 5 dodane su napomene na kraju.

## Sažetak

Prompt je većinom **kontekst s izmjerenim razlozima** (tržište kao provjera a ne ulaz, visina
ne predviđa pobjednika, kapice i zašto postoje) — to po vodiču nije višak i ostaje. Stvarni
problemi su četiri vrste:

1. **Dvije upute proturječe mjerenjima samog projekta** (visoka pouzdanost): pravilo o domaćem
   terenu (kazna −3pp kad je protivnik domaći) i uputa da se statistici s turnira na dubini 3+
   vjeruje "nekoliko bodova pouzdanosti".
2. **Zastarjeli prag 63%** na dva mjesta, dok je u kodu 60 od 08.09.2026 (visoka pouzdanost).
3. **Povijest i "pritisak" u tekstu koji model čita** (srednja pouzdanost): datumi izmjena,
   "REPLACES the hard 64% ceiling...", "user's explicit instruction", "THE SINGLE MOST IMPORTANT
   INSTRUCTION", 2× CRITICAL, 7× MUST, 5× NEVER, 2× SELECTION-CRITICAL. Noviji modeli takav
   ton slijede preširoko, a relativne formulacije ("now required for 63%+, not just 66%+")
   opisuju verziju prompta koju model nikad nije vidio.
4. **Kod poziva:** petlja "pokušaj ponovno ako JSON ne valja" je zakrpa za nešto što API
   rješava strukturiranim izlazom; model rezonira u prozi prije JSON-a jer razmišljanje nije
   uključeno. Obje stvari si 27.08. odlučio ne dirati — ovdje su samo zabilježene s mjerenjem.

## Nalazi

| # | gdje | obrazac (vodič) | zašto | pouzdanost | radnja |
|---|---|---|---|---|---|
| 1 | `predictor.py:1006-1014` (grass 11), `1096-1102` (clay 7), `1313-1321` (hard 11) | činjenica koju repozitorij pobija | kazna −3pp kad je protivnik domaći: DI K2 (naši pickovi s protivnikom-domaćim +7,5pp), povijesni laboratorij (domaći igrači −1,4pp naspram cijene, 2.775 mečeva, obje polovice −) | visoka | ukloniti (čeka tvoje odobrenje, K2) |
| 2 | `predictor.py:445-457` | činjenica koju repozitorij pobija | "at 3+ each it is real evidence and may be worth several points of confidence" — povijesno r=+0,004 na 970 mečeva dubine 3+; po vlastitom pragu K12 (r<+0,05) varijabla izlazi | visoka | svesti na opis ili ukloniti (čeka odobrenje, K12) |
| 3 | `predictor.py:1099-1100` (clay 7) i grass 11 `1010` | zastarjela činjenica | "score the pick below 63% so it drops out" — prag je 60 (`model_config.py:201`); ispod 63 pick više NE ispada | visoka | ispraviti ili maknuti "so it drops out" |
| 4 | `predictor.py:1230-1233` (hard 2) | relativna formulacija (1d) + zastarjeli prag | "now required for 63%+, not just 66%+ (REVISED 2026-07-31)" — opisuje staru verziju | srednja | napisati kao trenutno pravilo, bez povijesti |
| 5 | `predictor.py:579-580` | pritisak (1a) + relativna formulacija (1d) | "THE SINGLE MOST IMPORTANT INSTRUCTION HERE (REPLACES the hard 64% ceiling, which was in force 13.08.-17.08.2026)" | srednja | normalan naslov, razlog ostaje |
| 6 | `485, 497, 527, 540, 618, 634, 650, 657, 670, 791, 796, 803` i pravila po podlozi | povijest u tekstu (Group 2 "history narratives") | "(added 2026-08-04)", "(user's explicit instruction)", "(rewritten 2026-09-26)" — datumi i povod pripadaju komentarima i changelogu (ondje već postoje) | srednja | maknuti oznake iz teksta prompta |
| 7 | `485, 913, 972, 979, 1110, 1212, 1215` | pritisak (1a) | CRITICAL / SELECTION-CRITICAL / MUST bez potrebe; pravila vrijede i izgovorena normalnim tonom | srednja | normalan ton, zadržati "zašto" |
| 8 | `796-812` (scouting ±3pp), kazne "subtract 3pp" | aritmetika koju model računa (1b) | pravila s brojevima bodova bolje stoje u kodu (tako već radi `_apply_measured_penalties`) | srednja | samo zabilježeno (promjena arhitekture) |
| 9 | `predictor.py:44-55`, `1402-1500` (`_safe_json_parse`, `_fix_json_strings`, 2 pokušaja) | JSON zakrpa zamijenjena API značajkom (1b) | strukturirani izlaz jamči valjan JSON; izmjereno 27.09.: 21 od 171 analize trebala je drugi puni poziv | srednja | samo zabilježeno — odbijeno 27.08. |
| 10 | `_call_analysis_model`, bez `thinking` | rezoniranje u odgovoru umjesto razmišljanja (Group 4) | model "prvo rezonira u prozi pa tek onda piše JSON" (komentar 27.08.) — uzrok rezanja; `thinking: adaptive` bi to premjestio u blokove razmišljanja | niska–srednja | samo zabilježeno (mijenja ponašanje, nova era) |
| 11 | redoslijed prompta i keš | Group 4 | u redu: fiksni dio u `system` s `cache_control`, podaci o meču u poruci; izmjereno 41 od 51 poziva čita iz keša | — | ništa |
| 12 | brojanje tokena | Group 4 | u redu: `analysis_call` u snapshotu bilježi ulaz, izlaz, keš i pokušaje | — | ništa |

**Ne diram (keep list):** mjerenja s razlozima (Brier, "market price — a check, never an
input", visina/građa, vjetar), JSON primjer izlaza (drži format), popis težina na dnu (tvoja
odluka 26.09. da ostaje, iako ga model ne koristi u računu), zabrana izmišljanja geografskih
tvrdnji (dokumentirana stvarna greška — Slovačka i Hrvatska).

## Predložena izmjena (NIJE primijenjena)

Samo nalazi visoke pouzdanosti (1–3) i dva naslova (4–5). Sve zajedno = jedna nova era; tada
premjeriti duljinu odgovora i napraviti jedan živi poziv (pravilo 6 u `CLAUDE.md`).

```diff
--- a/agent/predictor.py  (_ANALYSIS_SYSTEM_TEMPLATE, oko 445)
-  balls, same court. Use them as the freshest read on how he is actually serving and
-  returning right now, and prefer them over season averages when the two disagree.
-  HOW MUCH TO TRUST IT DEPENDS ON N. Measured on 551 matches across 28 tournaments,
-  ...
-  So the same gap means much more deep in a draw than early. Weight it accordingly:
-  at 2 matches each it is a tiebreaker at most; at 3+ each it is real evidence and may
-  be worth several points of confidence.
+  balls, same court. They describe how he has played this week. Measured on 970 ATP
+  matches (2022-2026) where both players had 3+ matches at the event, the gap between
+  their numbers added nothing to the bookmaker price (r = +0.004), so use them to
+  describe the matchup, not to move your confidence.

--- a/agent/predictor.py  (grass 11, clay 7, hard 11 — isti blok na tri mjesta)
-11. HOME-CROWD RULE (asymmetric — from cross-surface analysis of 31 home-player matches;
-   ...
-   If the OPPONENT of our pick plays in his own country (check Country vs tournament host
-   country): subtract 3pp from confidence. If that home opponent ALSO has in-tournament
-   momentum (2+ wins this week) or the match is otherwise close, score the pick below 63%
-   so it drops out — home underdogs in rhythm repeatedly destroyed marginal favourites
-   (Fery eliminated 5 of our picks at his home events; Huesler beat our pick in Gstaad).
-   If OUR pick is the home player: NO bonus — home picks won at exactly the baseline rate.
+11. HOME PLAYERS: playing at home is already in the bookmaker price (measured on 2,775
+   matches: home players did not beat the price). Do not adjust confidence for it.

--- a/agent/predictor.py  (hard 2, oko 1230)
-2. DOUBLE-CONFIRMATION — now required for 63%+, not just 66%+ (REVISED 2026-07-31):
-   Why revised: 4 of our first 5 hard losses were scored 63-65%, i.e. BELOW the old 66%
-   trigger, so this rule never applied to them. It therefore applies from 63%.
+2. DOUBLE-CONFIRMATION for 63%+:
+   Why: our early hard losses at 63-65% were all driven by a rating gap with no second
+   independent edge.

--- a/agent/predictor.py  (oko 579)
-CONFIDENCE MUST SPREAD — THE SINGLE MOST IMPORTANT INSTRUCTION HERE
-(REPLACES the hard 64% ceiling, which was in force 13.08.-17.08.2026; measured 17.08.2026)
+CONFIDENCE MUST SPREAD ACROSS MATCHES
```

Nalaz 6 (datumi u tekstu prompta) i 7 (ton) predlažem raditi tek zajedno s gornjim, u istoj
eri, kad odlučiš — to su desetci sitnih izmjena i nema smisla trošiti dvije ere.

## Ako jednom prijeđemo na Sonnet 5

- Razmišljanje je uključeno po zadanom; `max_tokens` broji i razmišljanje, a novi tokenizer daje
  ~30% više tokena — `_ANALYSIS_MAX_TOKENS` (4000, 6000) treba povećati.
- `temperature` nije dopušten (kod ga ne šalje — u redu).
- Sonnet 5 uputu čita doslovnije; nalazi 5–7 (pritisak) tada postaju važniji.
- Cijena po tokenu je niža ($2/$10 naspram $3/$15). Sonnet 4.6 nije zastario, pa nema žurbe.
