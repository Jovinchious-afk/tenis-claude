# Model Changelog

Kronologija promjena modela za generiranje tiketa (predikcija + selekcija + strategija).
Svrha: da kroz iteracije znamo ŠTO smo mijenjali, ZAŠTO, i s kojim ishodom.
Težinske verzije (brojčane) žive u Supabase `model_weights`; ovdje su prompt-pravila,
selekcijska logika i strateške odluke koje se ne vide iz baze.

Format: `datum — naslov` → što / zašto / ishod (ako je poznat).

---

## 2026-07-27 — Screenshot-isključivost: mečevi izvan screenshota se izbacuju prije analize

**Povod:** korisnik pitao je li moguće da se meč izvan njegovih uploadanih screenshot
kvota ipak provuče na analysis-only ili tiket. Provjera je pokazala da JEST — i to
uživo, ne teoretski: The Odds API je taj dan vratio 28 stvarnih tržišta za Washington/
Los Cabos, uključujući mečeve koje korisnik NIJE screenshotao, s cijenama koje se za
zajedničke mečeve razlikuju od SuperSporta (npr. Arnaldi-Musetti 2.65/1.47 na screenshotu
naspram 2.42/1.69 na Odds API-ju). Dosadašnja "zaštita" počivala je isključivo na sretnoj
okolnosti da The Odds API dotad nije imao tržišta za manje clay ATP 250 turnire —
pretpostavka koja se raspala na prvom većem hard turniru. Dodatno, `build_analysis_only_
ticket` nije ni provjeravao postoji li stvarna kvota (`_pick_odds` tiho vraća 1.50 kad
kvote nema), pa je isti mehanizam prije proizveo šest lažnih Washington kvalifikacijskih
pickova (vidi zapis od 26.07.).

**Pravilo:** ako je korisnik za dan D (danas ILI sutra) uploadao barem jedan screenshot
par, SAMO ti parovi tog dana smiju dalje u obradu — svi ostali mečevi tog dana se
izbacuju PRIJE ELO/kvota/vremena/Claude analize (ne samo prije selekcije na tiket), bez
obzira što o njima kaže The Odds API ili API-jeva round-oznaka. Dan bez ikakvog uploada
ostaje nepromijenjen (Odds API fallback kao dosad).

**Cross-day nijansa (korisnikov uvid):** Washington/Los Cabos večernji mečevi znaju po
satu ispasti u idući Zagreb kalendarski dan (SAD zapadna obala ~9-10h iza), pa API zna
meč koji je korisnik screenshotao pod "danas" označiti sutrašnjim datumom. Zato provjera
imena ide preko SPOJENOG (danas+sutra) skupa, dok je UKLJUČENOST pravila i dalje po
danu — isti par ne igra dvaput unutar ta dva dana (eliminacijski turnir), pa spajanje ne
nosi rizik krivog poklapanja.

**Implementacija:** `agent/run_daily.py` — nova `_gate_by_screenshot()`, pozvana odmah
nakon učitavanja screenshot kvota, prije `_infer_rounds`. `screenshot_today`/
`screenshot_tomorrow` sada odvojeni (prije su se odmah spajali). Testirano na stvarnim
podacima 27.-28.07.: filter je uživo izbacio 5 Los Cabos mečeva koje korisnik nije
screenshotao te sezone, bez utjecaja na 27 mečeva koje jest.

---

## 2026-07-26 (kasna večer) — Hard zona ublažena po ponovnom mjerenju + model_stamp u snapshotu

**Povod:** korisnik pitao stojim li i dalje iza potpune hard zabrane 1.43-1.60 nakon
Kitzbühela/Estorila. Ponovno mjerenje po erama (dedupe, flat ROI):

| Zona | Prije 11.07. (stari model) | Clay 11.-26.07. (novi model) |
|---|---|---|
| 1.43-1.60 | 17W-15L, −19.2% | 10W-4L, **+7.8%** |
| 1.61-1.90 | 22W-24L, −16.5% | 9W-4L, **+21.9%** |

**Zaključak:** mrtva zona je bila problem STAROG modela (bez conf floora, hot-handa,
Fery veta), ne kvote same. Zabrana iz 18.07. počivala je na korpusu stare ere.

**Izmjena (korisnik odobrio):** hard "1.43-1.60 zabranjeno + 1.61-1.90 max 1" →
**jedna oprezna zona 1.43-1.90, max 1 hard pick po tiketu** (isti oblik kao clay pravilo
koje je isporučilo 72% WR). `_hard_bands_ok` uklonjen iz `_selection_ok`;
`_hard_caution_zone_count` u `_find_best_combination`. Prompt pravilo 3 ažurirano (nosi
obje ere brojki + opis novog backstopa). Grass zabrana NAMJERNO ostaje (n=33, −20.3%,
nije ponovno mjerena — grass sezona gotova; revalidirati prije iduće trave). Nuspojava:
hard tiket je sada izvediv s JEDNIM underdogom >1.90 (test: 1.35/1.40/1.55/2.10 → 6.15),
pa rizik svakodnevnog analysis-only praktički nestaje. Revalidacija na ~30 hard pickova
(okidač aktivan). Oprez: novi uzorak zone je malen (n=14/13) i s claya.

**model_stamp (context_snapshot v3):** svaka analiza sada nosi `{weights_version,
rules_hash}` — verzija aktivnih težina + md5 hash surface pravila i templatea (mijenja se
automatski sa svakom izmjenom prompta, bez ručnog održavanja). Svrha: egzaktno rezanje
kalibracijskog korpusa po erama modela umjesto rekonstrukcije iz datuma revizija.

---

## 2026-07-26 (večer) — Kalibracija proradila (bug 0/421), hard pravila 13-14, ocjena v15

**Povod:** korisnik pitao zašto je "Confidence calibration" na Model Statistike prazan, tražio
ocjenu auto-generiranih clay težina v15 i pripremu hard modela za Washington/Los Cabos (27.07.).

**Nalaz 1 — kalibracija prazna zbog stvarnog buga, ne zbog praga:** korak 2b večernjeg
updatea (18.07.) čitao je pobjednika iz `/atp/fixtures`, ali taj endpoint NIKAD ne vraća
pobjednika — čisti je raspored (provjereno sirovim odgovorom: ključevi samo
id/date/roundId/playerXId/live). Rezultat: 0/421 analiza razriješeno, kalibracijska tablica
prazna, hard-revalidacijski okidač (30 hard pickova) slijep, walkover-fallback mrtav.
Dodatni nalaz: fixtures za PROŠLE dane IZBACUJU odigrane mečeve — isti mehanizam zbog kojeg
je Kitzbühel "nestao" iz feeda 25.07.

**Popravak:** novi izvor pobjednika `/atp/tournament/results/{seasonId}` tekuće sezone
(`get_current_season_results` u data_fetcheru; 2 API poziva po turniru). Zajednički helper
`_build_season_winner_lookup` (feedback_analyzer) pronalazi tournament_id kaskadno:
fixtures par-mapa → past-matches igrača s ranking liste (traži se TOČNO meč para: datum ±2
dana I prezime protivnika — širi prozor je hvatao susjedni turnir istog igrača). Lookup puni
postojeći `fixture_winner`, pa su korak 2b i walkover-fallback proradili bez daljnjih izmjena.
Backfill (`scripts/backfill_analyzed_results.py`): razriješeno 261/421 analiza (ostatak su
kvalifikacije kojih nema u results endpointu, challengeri izvan top-500 i Citi Open koji još
nije počeo). Kalibracijski korpus sada: n=223 — bin 63-65% pogađa 64.9% (dobro kalibrirano
nakon revizija), 66-69% → 73.1%, 70%+ → 90%.

**Nalaz 2 — ocjena clay v15 (auto-feedback, 7 analiza):** zadržan bez izmjena. Opravdano:
elo −2 (gubici s gapom 60-77 bodova tretiranim kao presudnim), fatigue +2 (umor zapisan pa
pregažen u 4 gubitka), serve_return +1 (Halys 3×). Dvije dokumentirane zamjerke: trajectory
−1 počiva na tome da hot-hand sada čuva deterministički Fery-veto (a taj je 25.07. zakazao
zbog feed-rupe — sada zakrpano A1 + ovim popravkom); h2h +1 dijelom citira halucinirani
"Van Assche 2023 Estoril win" iz pred-A2 analiza. Kontekst: clay 11.-26.07. = 39W-15L
(72.2%), flat ROI +14.6%; pravi tiketi 1W-8L (akumulator-matematika, korisnikova odluka).

**Nalaz 3 — hard pravila 13 i 14 (prompt, v14 težine NETAKNUTE do prvih hard podataka):**

- Pravilo 13 SERVE-DOMINANT OPPONENT CAP: protivnik hold ≥82% + naš return <40% → cap 60%
  (destilat tri Halys poraza: Navone @1.45, Hanfmann @1.55, Bublik @1.50).
- Pravilo 14 HARD SUB-SPEED: iz Tennis_Surface_Analysis.docx ("treating all hard courts
  identically is the most common modelling error") — brzi/spori hard mijenja vrijednost
  servisa vs returna; arhetip upozorenje za jednodimenzionalne igrače uz SCOUTING PROFILE.

Provjera usklađenosti s Word dokumentom: pravila 4, 5, 6, 7, 9 + v14 balans (elo 22 =
serve_return 22) već pokrivaju "balanced blend / ranking najpouzdaniji na hardu / vrućina /
indoor amplifikacija"; jedina stvarna rupa bila je sub-speed → pokrivena pravilom 14.

**Retro-provjera scoutinga (uveden 25.07. poslijepodne, prvi live run 27.07.):** profili bi
izravno označili 3 najskuplja gubitka — Navone (tough: "Big servers") vs Halysa, Rublev
(tough: "Counter-punchers who absorb pace") vs Van Asschea, Bublik ("Very streaky") vs
Halysa; s capom −3pp sva tri padaju ispod floora 63% i ispadaju iz selekcije.

---

## 2026-07-26 — Revizija po 8 korisnikovih nalaza: A (5 popravaka), B, C, D (struktura tiketa)

**Povod:** korisnik prijavio 8 točaka (neriješen rezultat, dvije sumnjive tvrdnje u analizama,
dvije hipoteze za provjeru, prijedlog nove varijable, promjena strukture tiketa). Sve je
provjereno kroz stvarne podatke prije bilo kakve izmjene; dvije hipoteze su potvrđene, jedna
opovrgnuta, tri tvrdnje o greškama potvrđene.

**Nalazi iz provjere (dokumentirano jer objašnjava SVE izmjene ispod):**

- **Bublik-Halys 25.07. nije razriješen** jer je Generali Open Kitzbühel NESTAO iz fixtures
  feeda (0 mečeva 22.-26.07.). Evening update gradi player ID-eve isključivo iz feeda → bez
  ID-eva odustaje prije nego išta pokuša. Estoril mečevi istog dana prošli normalno.
  Stvarni rezultat (past-matches): Halys 6-4 7-6(6). Upisan + generirana analiza gubitka.
- **Halys nas je srušio 3× u istom turniru** (23./24./25.07.) a Fery-veto nije upalio: ta
  tri dana bila su `analysis_only`, a `build_analysis_only_ticket` NIJE primjenjivao nijedan
  deterministički filter — ni veto, ni mrtve zone, ni conf floor. Vrijedilo je i za
  hipotetski "kad bih morao riskirati" tiket koji korisnik čita.
- **Rublev-Darderi (točka 2): potvrđeno.** Prompt je doslovno sadržavao `Luciano Darderi:
  2025 FW` (protivnik osvojio isti turnir novije) i `2024 R16: Tirante def. Rublev` (naš pick
  ispao rano zadnji put). Model je citirao samo "Rublev won this title in 2023". Nije
  halucinacija nego jednostrano citiranje dokaza koje je imao pred sobom.
- **Van Assche "2023 Estoril win" (točka 5): potvrđeno i gore.** Naša draw baza kaže
  `2023 R16: Davidovich Fokina def. Luca Van Assche` — dakle taj meč je IZGUBIO. Analiza je
  napisala da ga je dobio, a feedback model to eskalirao u "his 2023 Estoril win" (2023.
  Estoril je osvojio Ruud). Feedback prompt dotad nije imao NI draw podatke NI anti-
  halucinacijsko pravilo. Usput: Estoril draw ima samo 2022-2024, pa je
  `has_tournament_history` vraćao False svaki dan → puni re-fetch ~45 zapisa SVAKI run.
- **Shevchenko/Struff (točka 3): potvrđeno.** Tiket 19.07: `risk_notes` = "Shevchenko fresher
  (2 vs 13 rest days)" dok `key_factors` iste analize kaže "Struff's 13 days rest — fatigue
  factor favours Struff". Igrač s 2 dana odmora označen "svježijim". Ponovilo se i 20.07.
- **Točka 4 (oba igrača >120 ATP): hipoteza NIJE potvrđena.** oba ≤120: n=156, WR 63.5%,
  ROI -4.0% | jedan >120: n=44, 61.4%, -2.9% | **oba >120: n=19, 63.2%, +8.5%**. Kontrola
  prag 100 → +2.1%, prag 150 → -0.3%. Isti WR uz više kvote. Ništa nije mijenjano (korisnik
  potvrdio: "E - okej, necemo dirati nista").
- **Točka 6 (završnice): hipoteza POTVRĐENA.** QF/SF/F kvota ≤1.60: n=59, WR 66.1%,
  **ROI -10.2%** | kvota >1.60: n=21, WR 57.1%, **ROI +11.2%**. Finale je najgora runda
  (n=9, 55.6%, -27.4%). Razlika 21pp ROI-a.
- **Točka 7:** pronađen neiskorišten endpoint `/atp/player/titles/{id}` — karijerna finala
  po razini (osvojena + izgubljena), tj. koliko je finala igrao i koliko ih je zatvorio.

**Što je promijenjeno:**

**A1 — razrješavanje rezultata više ne ovisi o fixtures feedu.** `ticket_matches` dobiva
`player1_id`/`player2_id` (upisuju se pri kreiranju tiketa), a evening update koristi kaskadu
tiket → fixtures → **ATP ranking lista** (nova `df.find_player_id`, cache po procesu).
`save_ticket_matches` ima defenzivni fallback: ako stupci ne postoje, upisuje bez njih pa
spremanje tiketa nikad ne padne. Potreban ALTER TABLE (vidi schema.sql).

**A2 — feedback prompt ojačan:** dobiva draw povijest turnira + isto anti-halucinacijsko
pravilo kao analizni prompt, plus eksplicitnu uputu da `risk_notes` iz predikcije NISU
provjerena činjenica i da se proturječje s draw podacima mora prijaviti kao nalaz.

**A3 — pravilo uravnoteženog citiranja:** ako model citira turnirsku povijest u prilog svog
picka, mora prvo provjeriti istu povijest za protivnika i za vlastite nedavne neuspjehe tamo.
Uz konkretan dokumentirani primjer (Rublev/Darderi). Dodano i pravilo da se rezultat mora
čitati u ispravnom smjeru (primjer Van Assche R16).

**A4 — pravilo interne konzistentnosti:** `risk_notes` ne smiju proturječiti `key_factors`;
model mora prije vraćanja ponovno pročitati oba polja i provjeriti da ime, broj i smjer
("fresher", "better") pokazuju isto. Uz dokumentirani Shevchenko primjer.

**A5 — draw re-fetch throttle:** `has_tournament_history` više ne traži strogo prošlu sezonu
(neki turniri je u API-ju nemaju), nego bilo koju unutar 3 godine; ako su podaci stariji od
current_year-1, dopušta re-fetch **jednom tjedno** umjesto svaki dan.
`save_tournament_history` sada osvježava `fetched_at` pri svakom upsertu — bez toga throttle
nikad ne bi resetirao brojač (uhvaćeno testom).

**B — hipotetski tiket prolazi kroz `_selection_ok`.** Široka lista analiziranih mečeva
namjerno OSTAJE bez filtera (informativna), ali "kad bih morao riskirati" prijedlog sada
poštuje ista pravila kao pravi tiket. Ovo bi spriječilo trostruki Halys fade.

**C1 — karijerna finala u prompt** (`df.get_player_titles`, cache): ATP/Masters i Challenger
finala odigrana + postotak zatvaranja, uz uputu da je to podupirući faktor za QF/SF/F, ne
driver u ranim rundama.

**C2 — LATE-ROUND PRICING DISCIPLINE** (univerzalno, dokaz je cross-surface): od QF nadalje
ne napuhavati confidence heavy favoritu na temelju reputacije; dobro potkrijepljen underdog
u završnici je legitiman pick; finale je najveće-varijance runda. Uz izmjerene brojke i
eksplicitnu zaštitu da ovo NIJE poziv na slijepo favoriziranje underdoga.

**D — struktura tiketa ujednačena za sve podloge** (korisnikova odluka): **4-6 parova,
kombinirana kvota 6.0-40**. `SURFACE_TICKET_OVERRIDES` ispražnjen (clay 6.5-30 i hard max 6
ukinuti). Analysis-only ponašanje nepromijenjeno. **Napomena za buduću reviziju zapisana u
kodu:** pri našem stvarnom pogotku (~63%/pick) prag isplativosti je ~6.0 za 4 para, ~9.3 za
5 i ~14.6 za 6 parova — fiksni donji prag 6.0 znači da su tiketi s 5-6 parova pri dnu
raspona matematički nepovoljni (kandidat: min kvota koja skalira s brojem nogu).

**Ishod:** 48 novih testova (D, B, A1-A5, C1, C2) + regresija scouting i smoke suita + puni
dry-run. Jedan pravi bug uhvaćen vlastitim testom tijekom rada: A5 je prvo koristio
nepostojeći stupac `created_at` umjesto `fetched_at`.

---

## 2026-07-25 — Scouting profili (Excel) + surface-fizika destilat (Word) kao sekundarni izvor

**Povod:** korisnik priložio dva dokumenta: "ATP_Player_Scouting top100.xlsx" (100 igrača:
stil, prednosti/mane, matchupovi, uz pošten confidence sustav High→Insufficient i legendu
"analyst inference, NOT fresh research — validate before use") i "Tennis_Surface_Analysis.docx"
(fizika i taktika podloga, 30 navedenih izvora). Zatražio kritičku procjenu pa integraciju
kao SEKUNDARNI izvor istine za izjednačene mečeve.

**Procjena prije implementacije:** Word dokument neovisno POTVRĐUJE ~80% postojećih odluka
(surface ELO, indoor amplifikacija, serve težine po podlozi, tiebreak lutrija, altitude...)
— glavna stvarna rupa: model o stilu igrača zna samo ruku, a stilski matchup može pomaknuti
vjerojatnost za nekoliko pp uz isti rating (Harvard izvor u dokumentu). Excel: ~69/100
igrača upotrebljivo (Med+); 2026 tvrdnje konzistentne s NAŠIM podacima iz prve ruke (Fery
"Wimbledon run" = srušio nas 6×; Cobolli "breakout" = u našem vetu; Merida "clay craftsman"
= osvojio Umag protiv našeg picka). Za slavne igrače vrijednost je SIDRENJE (model čita
dogovorene činjenice umjesto vlastite memorije), za 2026 risere stvarna nova informacija.

**Što:**
- **Nova Supabase tablica `player_scouting`** (ključ: normalizirano ime; sadržaj: rank,
  stil, podloge, prednosti/mane, matchupovi, confidence, source_date). U schema.sql;
  postojeća instanca treba ručni CREATE TABLE (vidi upute korisniku).
- **`scripts/import_scouting.py`**: Excel → Supabase upsert; `--dry-run` mod; legende na
  dnu Excela automatski preskočene; ponovljivo za buduća osvježavanja.
- **`db.get_all_scouting()`**: jedan query po daily runu, graceful {} ako tablice nema.
- **`run_daily._find_scouting()`**: lookup po normaliziranom imenu + fuzzy fallback preko
  postojećeg `_name_match` (isti mehanizam kao screenshot kvote).
- **Prompt: nova sekcija "SCOUTING PROFILES (secondary evidence)"** sa strogim pravilima:
  max ±3pp utjecaja; tie-breaker za izjednačene mečeve; NIKAD ne nadjačava mjerene brojke;
  anti-double-counting (kvalitativni kontekst za interpretaciju brojki, ne dodatni dokaz);
  stilski matchup eksplicitno dozvoljen kao faktor uz trenutnu podlogu; **Low/Insufficient
  profili se NE ubacuju** — umjesto njih "No reliable scouting — do not fill from memory"
  (poštuje autorovu vlastitu legendu, sprječava da model rupu popuni halucinacijom).
- **Clay pravilo 11 (FAST-CLAY CONDITIONS)** — jedini destilat iz Word dokumenta koji nam
  je stvarno nedostajao: visinski/vrući clay (Madrid, Gstaad, Kitzbühel) pomiče ponašanje
  prema hard vrijednostima; veže se na postojeći Altitude kontekst. Ostatak dokumenta
  NAMJERNO nije prepisan u prompt (već pokriveno težinama/pravilima — izbjegnuto dvostruko
  brojanje istih dokaza).
- **context_snapshot v2**: + `p1/p2_scouting_confidence` — za koji mjesec mjerljivo je li
  scouting stvarno pomogao (WR sa scoutingom vs bez), isti standard kao za druge varijable.
- Scouting NEMA deterministic veto-moć (interpretacija, ne mjereni podaci) i NE ulazi u
  feedback petlju težina.

**Ishod:** 27 novih testova (parse 100/100 igrača, confidence gating, prompt pravila,
end-to-end mock s context_snapshot v2, fuzzy lookup) + regresijski smoke test svih
determinističkih filtera i prompt markera (sve prošlo) + end-to-end dry-run bez tablice
(graceful degradacija). **Čeka korisnika:** CREATE TABLE u Supabase + prvi import.

---

## 2026-07-20 — Korekcija praga: both-declining cap zategnut s "1/3 ili lošije" na strogo "0/3"

**Povod:** korisnik, gledajući stvarne ponedjeljkove (20.07.) ATP 250/500 prvokolaške
mečeve (Estoril, Kitzbühel), primijetio da bi mnogi parovi imali oba igrača na 1/3 u
zadnja 3 meča — brinuo se da će both-players-declining pravilo (jučer otvrdnuto u kod)
isključiti previše mečeva i onemogućiti sastavljanje tiketa. Predložio strožu granicu
(samo 0/3, ne "1/3 ili lošije").

**Provjera na stvarnim podacima PRIJE odluke:** od 14 main-tour mečeva 20.07., **6 (43%)**
palo bi na starom pragu — od toga samo 1 (Muller-Navone) stvarni 0/3-vs-0/3 slučaj, ostalih
5 su 1/3-vs-1/3 ili 0/3-vs-1/3 kombinacije. Dodatno: originalni dokumentirani dokaz koji je
uopće pokrenuo ovo pravilo (Butvilas-Huesler, clay rules v1) bio je baš 0/3-vs-0/3 — "1/3 ili
lošije" je bila NEPROVJERENA generalizacija u kodu, ne dokazan prag.

**Što:** `run_daily._is_declining()`: `sum(...) <= 1` → `sum(...) == 0`. Prompt-tekst
(grass rule 7, clay rule 3 — Claudeova vlastita procjena) NAMJERNO ostaje širi ("1/3 ili
lošije") — Claude i dalje smije biti oprezan kod 1/3-vs-1/3 kroz vlastiti confidence, samo
to više nije automatski tvrdi izbačaj iz tiketa. Kod i prompt sada namjerno NISU identični
(kod = dokazan slučaj, prompt = šira preporuka).

**Ishod:** ista provjera na istim 14 mečeva 20.07. nakon izmjene: samo 1/14 (7%) i dalje
pada (Muller-Navone, jedini dokazan tip slučaja) — pad s 43% na 7% isključenih. Novi
regresijski test (test_c_deterministic.py, 3b) direktno kodira ovaj scenarij (Van De
Zandschulp-Faria tip 1/3-vs-1/3 prolazi, Muller-Navone tip 0/3-vs-0/3 i dalje pada).
Regresija hard v1 + universal logging suita prošla.

---

## 2026-07-18 (osmi put) — Preporuke C, F, D iz stručnog komentara: otvrdnuta 2 pravila, kalibracijska tablica, hard okidač

**Povod:** korisnik pročitao stručni komentar + preporuke A-F iz dokumentacije sustava,
odlučio zadržati strukturu tiketa netaknutom (kvota/broj parova po podlozi ostaju kako jesu
— A i A-tipa promjene isključene), i zatražio preporuku što je odmah spremno za implementaciju.
Odabrano: C (otvrdnuti prompt-only pravila), F (kalibracijska tablica), D (hard okidač) —
odobreno "moze c f i d napravi".

**C — Both-players-declining cap i clay rest/fatigue differential otvrdnuti u kod:**
- Provjera koda PRIJE implementacije otkrila da je moja ranija tvrdnja ("sve tri podloge")
  bila netočna za drugo pravilo — ispravljeno prije pisanja koda:
  - **BOTH-PLAYERS-DECLINING CAP** (60% kad su oba igrača 1/3 ili lošija u zadnja 3 meča):
    postojao je u grass (rule 7) i clay (rule 3) promptu, NE u hardu. Logika je surface-
    neutralna (dva neizvjesna igrača = neizvjestan meč, bez obzira na podlogu) — hard
    pravila to i sama traže ("surface-independent, MUST be enforced from day one") — pa je
    `_both_declining_ok()` implementiran univerzalno, sve tri podloge, i tekst pravila
    dodan hardu (rule 12) za dokumentacijsku dosljednost.
  - **REST & FATIGUE DIFFERENTIAL** (−4pp, −6pp u Bo5, kad naš pick ima 2+ meča/7 dana I 2+
    manje dana odmora od protivnika): postojao je SAMO u clayu (rule 4), s obrazloženjem
    izričito vezanim uz clay ("rallies are the longest in tennis") — NIJE preneseno na
    grass/hard (nema dokaza), `_clay_fatigue_ok()` implementiran clay-only.
- `run_daily.py`: nove zastavice `p1/p2_declining` (iz `p1_form.get("matches")[:3]`, treba
  3+ odigrana meča) i `p1/p2_fatigue_disadvantage` (dani odmora preko novog `_rest_days()`
  helpera + `matches_7d`), postavljene po meču uz postojeće Fery-veto zastavice.
- `ticket_builder.py`: `_both_declining_ok()` (isključuje pick ako su oba igrača declining
  — 60% < 63% tiketni prag pa svejedno ne bi prošao, ovo samo jamči da eventualno
  preoptimistična procjena ne proturije) i `_clay_fatigue_ok()` (računa efektivni
  confidence umanjen za penal, zahtijeva da i tako umanjen i dalje bude ≥63%) — oba
  ožičena u `_selection_ok`.

**F — Kalibracijska tablica proširena na puni korpus, podijeljena po podlozi:**
- Otkriveno tijekom implementacije: kalibracijska tablica na "Model Statistike" stranici
  VEĆ je postojala, ali se gradila SAMO iz `ticket_matches` (uzak, selektirani uzorak —
  isti problem koji je evening update riješio za feedback petlju ranije danas, ali ova
  Streamlit tablica nikad nije ažurirana da prati tu promjenu).
- `database/supabase_client.py`: nova `get_resolved_analyzed_matches()` — čita puni
  `analyzed_matches` korpus gdje `prediction_correct` nije null.
- `pages/4_Model_Statistike.py`: kalibracijska sekcija prepisana da koristi taj korpus,
  PODIJELJENA PO PODLOZI (tabovi Sve/Clay/Grass/Hard) — izravan test je li prekalibracija
  (Nalaz 02) stvarno neovisna po podlozi, umjesto jedne kombinirane tablice koja to
  ne bi mogla pokazati. Osvježava se uživo pri svakom otvaranju stranice.

**D — Hard revalidacijski okidač:**
- `run_daily.py`, rano u `main()`: broji riješene hard picke u `analyzed_matches` (preko
  iste `get_resolved_analyzed_matches()`), javlja upozorenje u dnevnom logu čim prag 30
  bude dosegnut — umjesto oslanjanja da netko ručno primijeti.

**Ishod:** novi unit test suite (test_c_deterministic.py, 19 asercija) + F testiran
(uzorak trenutno n=0 jer se šire razrješavanje tek počelo puniti od danas — očekivano) +
regresija sva tri ranija test suita + end-to-end dry-run.

---

## 2026-07-18 (sedmi put) — Feedback model: Haiku → Sonnet, output_config effort=high

**Povod:** korisnik pitao, nakon prelaska "analysis" koraka na Sonnet, vrijedi li isto napraviti
i za večernji feedback job. Objašnjeno prije implementacije: evening posao ima dva Claude
poziva (analiza zašto smo izgubili konkretan meč, i prijedlog korekcije težina), oba tada
na Haiku, oba niskog volumena (max 5 loss-analiza + povremeni prijedlog težina tek nakon 5+
novih analiza) — pa je dodatni trošak trivijalan bez obzira na odluku. Očekivana dobit
procijenjena manjom nego kod "analysis" koraka (slobodno pisanje objašnjenja, ne kalibrirana
brojčana procjena), ali `_maybe_update_weights` izravno mijenja žive težine za sve buduće
predikcije — najveći utjecaj po pozivu u cijelom večernjem jobu. Korisnik odobrio: "moze da".

**Što:**
- `CLAUDE_MODELS["feedback"]`: `claude-haiku-4-5-20251001` → `claude-sonnet-4-6`.
- `feedback_analyzer.py` `_analyze_lost_match()`: `output_config={"effort":"high"}` dodan,
  `max_tokens` 700→1200 (margin).
- `feedback_analyzer.py` `_maybe_update_weights()`: `output_config={"effort":"high"}` dodan,
  `max_tokens` 500→900 (margin).
- `"analysis"`/`"ticket_writer"`/`"odds_extraction"` nisu dirani ovim krugom (već riješeni ili
  nepromijenjeni).

**Ishod:** mock test potvrđuje kwargs (model/effort/max_tokens) na `_analyze_lost_match`.
STVARNI (ne-mock) pozivi za OBA feedback poziva uspjeli — `_analyze_lost_match` vratio
strukturiranu analizu; `_maybe_update_weights` (DB slojevi monkeypatchani sa 6 sintetičkih
gubitaka, `save_new_weights` presretnut kao no-op da NIKAD ne dirne produkcijske težine)
proizveo koherentan, dobro obrazložen prijedlog korekcije (elo_ranking −3.0%, recent_form
+3.0%, s jasnim obrazloženjem po gubitku). Regresija sva tri ranija test suita (hard v1,
universal logging, sonnet analysis — potonji ažuriran jer je stara asercija "feedback ostaje
Haiku" sad zastarjela) prošla bez padova.

---

## 2026-07-18 (šesti put) — Analysis model: Haiku → Sonnet, output_config effort=high

**Povod:** korisnik primijetio da jezgru predikcije (pick/confidence/fair_odds po meču) radi
Haiku dok finalna holistička recenzija tiketa i write-up već koriste Sonnet — pitao je vrijedi
li podići i taj korak. Direktno povezano s nalazom iz istog dana (dokumentacijski pregled
sustava): precjenjivanje pouzdanosti (~7-16pp) otkriveno je NEOVISNO na sve tri podloge, što
sugerira svojstvo modela, ne podloge — jezgra predikcije je ujedno i najvažnija odluka u
cijelom pipelineu (sve nizvodno — filteri, kombinatorika — samo radi s brojkama koje ovaj
poziv već odluči).

**Što:**
- `CLAUDE_MODELS["analysis"]`: `claude-haiku-4-5-20251001` → `claude-sonnet-4-6` (config/model_config.py).
- `predictor.py` `analyze_match()`: dodan `output_config={"effort": "high"}` na Claude poziv,
  `max_tokens` podignut 900→1500 (margin). Korisnik izvorno tražio "high ili extra high" —
  `"xhigh"` je isproban prvo i odbijen od strane API-ja (400: "Supported levels: high, low,
  max, medium" — ovaj model nema xhigh razinu), pa je `"max"` privremeno postavljen kao
  najbliži ekvivalent, ali korisnik je eksplicitno tražio `"high"` umjesto `"max"` — to je
  finalna vrijednost.
- `"feedback"` (analiza gubitaka u feedback_analyzer.py) i `"ticket_writer"`/`"odds_extraction"`
  NISU dirani — ostaju kako jesu (feedback i dalje Haiku, ostala dva već Sonnet).
- Napomena: `CLAUDE_MODELS["analysis"]` dijeli se i s hipotetskim "kad bih baš morao riskirati"
  write-upom u `ticket_builder.py` (_generate_hypothetical_summary) — taj poziv automatski
  dobiva Sonnet kao model (bolji tekst), ali NE dobiva `effort=high` (nije dirano, ostaje
  default effort — ta odluka nije ono na što se korisnikov zahtjev odnosio).

**Ishod:** mock-testovi potvrđuju konfiguraciju i kwargs poziva; regresija starih test suita
(hard v1 + universal logging) prošla bez padova; STVARNI (ne-mock) API poziv s
`output_config={"effort":"high"}` uspio (7.4s, bez greške) — model je ispravno preskočio
namjerno oskudan testni fixture (5/7 kategorija N/A) umjesto da nagađa, dobar znak discipline
na visokom effortu. Puni end-to-end dry-run sa stvarnim podacima dana istog dana.

---

## 2026-07-18 (peti put) — 9 korisnikovih prijedloga: pregled + univerzalni fixevi + context logging

**Povod:** korisnik predložio 9 ideja za poboljšanje modela (doba dana, 3-set decider record,
ranking gap, ista nacionalnost, tiebreak favorit/outsider, brzina servisa, umor/motivacija
nakon velikog turnira, geografska greška "Molcan/Slovačka", turnirska povijest). Prije bilo
kakve implementacije napravljen je pregled po točkama kroz stvarni kod (ne pretpostavke) —
9 vs 9 kod: 1 je već potpuno implementiran (turnirska povijest, `tournament_history`), 1 je
odmah analizabilan iz postojećih podataka (tiebreak), 1 je jeftin prompt-fix (geo-greška),
1 je već testiran sa suprotnim zaključkom (ranking gap na clayu), 4 zahtijevaju novo
prikupljanje podataka prije analize (doba dana, decider record, nacionalnost, prethodni
turnir), 1 nije dostupan u trenutnom API-ju (brzina servisa km/h — nijedan endpoint koji
koristimo to ne vraća, ni live ni post-match).

**Što (korisnik odobrio cijeli paket, "univerzalno za sve podloge"):**
- **Anti-halucinacijski fix (univerzalan, shared prompt template):** nova STRICT
  ANTI-HALLUCINATION bullet zabranjuje izmišljanje geografskih/nacionalnih tvrdnji izvan
  doslovnog Country polja (npr. "susjedna država", "domaći navijači preko granice").
  Root cause NIJE bug u kodu — nema tablice granica nigdje — nego LLM slobodna asocijacija
  (Claude je u analizi tvrdio da Slovačka graniči s Hrvatskom radi "home crowd" narativa;
  ne graniči). Isti princip kao postojeća zabrana izmišljanja "title defence" (linija 131-133).
- **HOME-CROWD pravilo — parity gap otkriven i popravljen:** pravilo je već bilo izvedeno iz
  cross-surface analize (31 meč, sve podloge), ali tekst je postojao SAMO u clay promptu.
  Propagirano identično u grass i hard pravila (ista evidencija, ista formula −3pp/ispod 63%).
- **RANKING-GAP DEFLATION — grass dobiva, hard namjerno NE:** grass dobiva isti princip kao
  clay (ranking odražava SVE podloge, manje pouzdan od surface-specific ELO na specijaliziranim
  podlogama), ali iskreno označeno kao "provisional" — nema grass-specifičnih dokumentiranih
  gubitaka kao kod claya (Darderi/Khachanov/Faria). Hard NAMJERNO ne dobiva ovo pravilo — hard
  već ima suprotan, dokazan zaključak (rule 7 RANKING RELIABILITY: na hardu je ranking/ELO
  gap legitimno pouzdaniji jer je podloga neutralna) — dodavanje deflacije bilo bi
  kontradiktorno vlastitom dokazu.
- **context_snapshot logging (nova JSONB kolona, `analyzed_matches`, univerzalno sve podloge):**
  počinje se bilježiti dob, nacionalnost, vrijeme meča (već se dohvaćaju uživo, sad se i
  spremaju), plus dvije NOVE izvedene varijable — `decider_record` (Bo3 2-1 win/loss tally iz
  zadnjih odigranih mečeva, Bo5 namjerno izostavljen jer se ne može razlikovati od 3-0 sweepa
  bez podatka o formatu) i `previous_tournament_level` (tier igračevog zadnjeg odigranog
  turnira, preko novog `get_tournament_tier()` wrappera, cache-irano). Sve NE ulazi u prompt
  niti utječe na pick/confidence — čisto bilježenje dok se ne skupi uzorak za analizu.
  `context_version: 1` u JSON-u radi budućih izmjena sheme.
- **Analiza #5 (tiebreak favorit/outsider) — odmah izvedena iz postojećih podataka:**
  71 od 229 resolved ticket_matches sadrži tiebreak set. Favoriti (kvota ≤1.70) u tim mečevima:
  60.7% WR (n=61) — gotovo identično njihovom baznom WR (63.1%, n=160), nema odstupanja.
  Outsideri (kvota ≥2.00): 75.0% WR ali n=4 — statistički beznačajno, NE citirati kao nalaz.
  Zaključak: trenutno nema iskoristivog signala; treba čekati veći uzorak, posebno u
  outsider+tiebreak kutu.

**Ishod:** 27 novih unit-testova (anti-halucinacijski tekst, HOME-CROWD/ranking-gap parity,
`get_tournament_tier`, `_decider_record`/`_previous_tournament_level`, `context_snapshot`
end-to-end s mockiranim Claude odgovorom) + regresija starih 18 hard-revizijskih testova
(svi prošli) + end-to-end dry-run. **Korisnička akcija potrebna:** `context_snapshot` kolona
dodana u `schema.sql` za buduće instalacije, ali postojeća Supabase tablica treba ručni
`ALTER TABLE analyzed_matches ADD COLUMN IF NOT EXISTS context_snapshot JSONB DEFAULT '{}'::jsonb;`
u SQL Editoru prije nego se novi podaci počnu stvarno spremati.

---

## 2026-07-18 (četvrti put) — Cross-surface parity: clay hot-hand popravak + grass dead-zone + clay GS

**Povod:** korisnik pitao koja su od hard-revizijskih pravila zapravo univerzalna, ne samo
hard-specifična. Provjera koda + korpusa otkrila je tri nedosljednosti:

1. **Clay hot-hand pravilo je imalo ISTU grešku koju smo tog jutra popravili na hardu** —
   "3+ pobjede u turniru → veto" i dalje živi u clay promptu (rule 2), a to se okida na
   SVAKI meč od SF-a nadalje (3+ pobjede = SF). Za razliku od hardovog builder-level veta,
   ovo je bio samo prompt-savjet (manje opasno, ali ista logička greška), i clay se **igra
   upravo sada** (finala).
2. **Grass nema NIKAKVU zaštitu od mrtve zone kvota 1.43-1.60**, unatoč najjačem dokazu od
   sve tri podloge (n=33, 52% WR, ROI -20.3% dedupe) — jače nego evidencija koja je
   opravdala potpunu zabranu na hardu (koji ima 0 stvarnih pickova).
3. **GS prag 65% je stavljen na hard (bez dokaza)**, ali dokaz da GS podbacuje postoji na
   **clayu** (Roland Garros 54% vs ne-GS 67%), NE na grassu (Wimbledon 61% == ne-GS 61%,
   nema razlike) — pravilo je bilo na krivoj podlozi.

**Što (potvrdio korisnik — implementirati sve tri):**
- **Clay hot-hand pravilo prepisano** (isti pristup kao hard): "3+ pobjede" trigger
  zamijenjen s ciljanim uvjetom — protivnik mora biti (a) niže rangiran/slabiji clay ELO
  od našeg picka, (b) pobijedio SEEDANOG/više rangiranog igrača ovaj tjedan (pravi upset),
  i (c) naš pick je samo marginalni favorit. Dva favorita koja su normalno napredovala do
  SF/F = normalan meč, bez auto-capa.
- **Grass dead-zone ban** (`_grass_bands_ok`, nova): kvota 1.43-1.60 na grassu nikad ne
  ulazi na tiket — identičan mehanizam kao hard (`_hard_bands_ok`), ista granica.
- **Clay GS prag** (`_clay_gs_conf_ok`, nova): na clay Grand Slamu (Roland Garros) pick
  treba >=65% confidence — identičan mehanizam kao hard GS prag, primijenjen tamo gdje
  dokaz stvarno stoji. Grass GS NE dobiva ovaj prag (nema dokaza za razliku GS/ne-GS).
- Sve novo je ožičeno u `_selection_ok` (zajednički filter za sve kandidatske liste tiketa).

**Ishod:** 18 unit-testova (novi: grass dead-zone 6 scenarija, clay GS 5 scenarija, clay
prompt-tekst provjera 4 asercije) + end-to-end dry-run. Fery-veto je provjeren kao već
univerzalan (bez izmjene, `_opponent_beat_us` nema surface-provjeru).

---

## 2026-07-18 (treći put) — Fery-veto: prag 1→2 poraza, prozor 21→14 dana

**Povod:** korisnik primijetio da je Fery-veto možda prestrog — jedan poraz od nekog igrača
u turniru odmah ga trajno vetira, iako naši pickovi i onako pogađaju samo ~60% vremena
(znači i ISPRAVAN pick gubi ~40% vremena zbog normalne varijance). Jedan poraz nije pouzdan
dokaz da je taj igrač "naš problem" — dva poraza od istog igrača u istom turniru jest.

**Što (potvrdio korisnik):**
- `get_recent_lost_matches`: prozor 21→**14 dana** (i dalje pokriva puno trajanje Grand
  Slama; ATP 250/500 turniri traju ~7 dana pa je i 14 s viškom).
- `run_daily` Fery-veto logika: `beaten_us` se sada gradi preko `Counter`-a po
  (pobjednik, turnir) i u veto ulaze samo igrači sa **2+ poraza** u istom turniru
  (prije: bilo koji 1 poraz).
- `_opponent_beat_us` (ticket_builder) komentar ažuriran; sama logika nepromijenjena —
  i dalje čita p1_beat_us/p2_beat_us zastavice, samo su te zastavice sada strože postavljene.

**Ishod (stvarna provjera na Supabase, 18.07.):** stara logika (1 poraz/21 dan) vraćala je
**27 igrača** u vetu; nova logika (2 poraza/14 dana) vraća **3 igrača** (Fery, Cobolli,
Dimitrov — svi doista 2+ poraza na istom Wimbledonu). Pravi ponavljači ostaju uhvaćeni,
igrači koji su nas pobijedili samo jednom (moguća slučajnost) više se ne blokiraju. 11
unit-testova (čista logika brojanja + usporedba starog/novog praga) + end-to-end dry-run.

---

## 2026-07-18 (kasnije) — Korekcija hard revizije: ukinut duplikat + hot-hand win-count veto

**Povod:** korisnik uočio dvije greške u istodnevnoj hard reviziji (dolje):
1. **Duplikat pravilo** izbacivalo dobre mečeve — tiket legitimno pokriva danas+sutra i isti
   dobar meč se SMIJE ponoviti sljedeći dan. Ne želi to.
2. **Hot-hand veto po BROJU pobjeda je logički pogrešan**: do QF-a SVI igrači imaju 2+ pobjede
   (R32→R16→QF), do finala 4 — prag "2+ pobjede" okinuo bi veto na svaki meč završnice i
   onemogućio tiket. Broj pobjeda mjeri napredovanje, ne "vrući nalet". (Čak i motivirajući
   slučaj Merida vs Džumhur bio je FINALE — oba finalista imaju ~4 pobjede, veto ih ne razlikuje.)

**Što (potvrdio korisnik — opcija "ciljano na iznenađenja"):**
- **Duplikat pravilo UKINUTO** (`run_daily`) — vraćeno na staro, isti meč smije na uzastopne tikete.
- **Deterministički hard hot-hand veto UKINUT** (`_hard_hot_hand_ok` obrisan iz ticket_buildera;
  uklonjene i p1/p2_tourn_wins + elo/hold zastavice iz run_daily koje su ga hranile).
- **HARD RULES v1 pravilo 1 prepisano** iz "HOT-HAND VETO (2+ pobjede → skip)" u
  **"HOT-HAND CAUTION"** ciljano na PRAVI upset nalet: oprez/skip SAMO kad je protivnik
  (a) jasno niže rangiran/slabiji ELO od našeg picka, (b) pobijedio SEEDED/više rangiranog
  igrača ovaj tjedan, i (c) naš pick je tek marginalni favorit. Dva legitimna favorita u
  finalu koji su normalno napredovali = normalan meč, ne auto-skip.
- **Fery-veto OSTAJE** (`_opponent_beat_us`) — jedini deterministički hot-hand backstop,
  temeljen na STVARNOM porazu (igrač koji nas je već srušio u istom turniru), ne na brojanju.

**Ishod:** 34 unit-testa (ažurirani: hot-hand win-count veto uklonjen, potvrđeno da finalist
s 4W više ne pada automatski) + end-to-end dry-run. Sve ostale hard promjene (dead-zone ban,
mid-zona, GS 65, težine v14, evening→analyzed_matches, surface-switch) ostaju netaknute.

---

## 2026-07-18 — HARD REVIZIJA: pravila v1 + težine + selekcijska disciplina (PRIJE prvog hard picka)

**Povod:** potpuna revizija grass+clay korpusa po korisnikovoj metodologiji ("Prompt za
poboljšanje modela"), kao priprema za hard sezonu (Washington 27.07. → US Open). Korpus:
**187 unikatnih razriješenih pickova** (grass 84W-54L 61%, clay 29W-20L 59%), **33 prava
tiketa 2W-31L (ROI ≈ -28%)**, single-pick ROI grass -6.4% / clay -9.4%. Hard: **0 pickova
ikad** — v9 težine nikad testirane.

**Glavni nalazi (dedupe, isti meč na 2 tiketa brojan jednom):**
- Model zarađuje SAMO na ekstremima: teški favoriti ≤1.20 (93% grass, +3.1% ROI) i value
  underdozi >2.30 (7W-7L, +28% ROI). Sredina sustavno gubi: **1.43-1.60 najgori band
  (50% WR, ROI -24%)**, 1.91-2.30 41% WR.
- **Hot-hand fade = #1 uzrok gubitaka cross-surface**: Fery nas srušio 6× u 3 tjedna;
  sva 3 clay poraza POSLIJE revizije 11.07. imala su "opponent in run / home" u risk_notes
  — pravila su rizik registrirala ali ga NISU provodila.
- Kalibracija: deklarirani conf 63-70% vraća 55-60% (optimizam ~+7pp).
- Akumulator matematika: uz naše WR-ove **nijedan band nema EV ≥ 1.0 na kombiniranoj 6.5+**
  (najbolji ≤1.20: EV 0.70-0.83). Korisnikova odluka: struktura OSTAJE 6.5-40, hard 4-6 parova.
- GS podbacuje vs ATP 250 (clay 54% vs 67%); 42 duplikata = isti poraz rušio 2 tiketa;
  9/31 tiketa palo na točno 1 promašaju; `analyzed_matches` 419/419 bez ishoda.
- Clay post-revizija 11.07.: **8W-3L (73%), +5.9% ROI** — prvi pozitivan period (n=11, oprez).

**Što (sve implementirano 18.07., aktivno od sljedećeg runa):**
- **HARD RULES v1** u predictor promptu (10 pravila): hot-hand VETO kao mandatory skip
  (elite iznimka hard ELO ≥1900 / hold ≥88%), dvostruka potvrda za 66%+ (a/b/c hard
  kategorije), marginal-favourite reality check (1.43-1.60), TB-lutrija cap 62 (oba hold
  ≥85%), **surface-switch penalty** (clay SF/F u zadnjih 7 dana → -3pp prva 2 hard turnira;
  svježi hard specijalist → plus), heat/retirement guard (retirement zadnjih 14 dana ili
  injury news → skip), ranking-reliability (na hardu ELO/ranking legitiman uz 1 potvrdu),
  US Open prag 65%, indoor amplifikacija servisa, confidence spread honesty.
- **Ticket builder (deterministička PROVEDBA, ne samo prompt):**
  - hard dead-zone **1.43-1.60 = zabranjen na tiketu** (`_hard_bands_ok`);
  - hard mid-zona 1.61-1.90 **max 1 po tiketu** (`_hard_mid_zone_count`);
  - hard GS pick traži **conf ≥65** (`_hard_gs_conf_ok`);
  - conf floor 63 + value-override (58/12pp/max 2) **prošireni na hard**;
  - **FERY VETO (sve podloge)**: pick protiv igrača koji je nama srušio pick u istom
    turniru zadnjih 21 dan = automatski isključen (`_opponent_beat_us`; zastavice
    p1/p2_beat_us postavlja run_daily iz `ticket_matches` gubitaka).
  - **DETERMINISTIČKI HOT-HAND VETO (hard)**: protivnik s 2+ pobjede u OVOM turniru →
    pick isključen iz selekcije, osim elite iznimke (pick hard ELO ≥1900 ili hold ≥88%)
    (`_hard_hot_hand_ok`; p1/p2_tourn_wins + elite podaci iz run_daily). Dokaz potrebe iz
    dry-runa 18.07.: Haiku dao 64% Meridi protiv Džumhura na 4W/0L runu, reviewer pick
    izbacio, ali je kvota-guard (6.5 min) poništio reviewera i vratio original — prompt i
    reviewer registriraju, samo builder-veto garantirano PROVODI.
- **Duplikat pravilo (sve podloge, run_daily):** meč koji je već na jučerašnjem PRAVOM
  tiketu (ne analysis-only) ne ulazi u današnji pool — isti meč nikad na 2 tiketa.
- **Struktura (korisnikova odluka):** hard kombinirana OSTAJE 6.5-40, **4-6 parova**
  (`SURFACE_TICKET_OVERRIDES["hard"]`; "hard" substring hvata i Indoor Hard).
- **Težine hard v14** (Supabase, aktivne): elo 22, serve 22, **surface 20→17** (hard
  najmanje surface-specifičan), form 17→16, **fatigue 11→13** (US vrućina, 9 voidova u
  korpusu), h2h 4, **trajectory 4→6** (hot-hand lekcija). PROVIZORNE — prva kalibracija
  nakon Washington/Montreal tjedana.
- **Evening update sada upisuje ishode u `analyzed_matches`** (zadnjih 8 dana, 0 dodatnih
  API poziva — reuse fixture_winner lookupa): širi korpus za buduće revizije umjesto samo
  selektiranih tiket pickova.
- **Indoor Hard:** potvrđeno — isti hard model/težine (surface match "hard" substring),
  odvojeno praćenje u Loss Analysis ostaje.

**Ograde (protiv overfittinga):** hard n=0 — SVI pragovi (1900/88%, bandovi, 65 GS) su
prijenos s grass/clay i početni; >2.30 value nalaz je n=14 (ne širiti value cap); post-
revizija clay +5.9% je n=11. Prva hard revalidacija: nakon Washington/Los Cabos/Montreal.

**Ishod:** 34 unit-testa + end-to-end dry-run. Prati se.

---

## 2026-07-18 — Poklapanje inicijala kladionice ("Juan M." = "Juan Manuel")

**Povod:** daily tiket 18.07. sve kvote povukao točno OSIM Collignona (1.50 fallback umjesto
1.65). Izmjereno: Collignonovo ime se savršeno poklopilo, ali `find_match_odds` traži da se
poklope OBA igrača, a **protivnik Cerundolo nije** — kladionica je skratila srednje ime:
API "Juan Manuel Cerundolo" (3 riječi) vs screenshot "Cerundolo Juan M." ("Manuel" → "M.").
Zbog toga cijeli par propao → Collignon dobio fallback 1.50.

**Zašto Fix 2 (17.07.) to nije uhvatio:** Fix 2 je hvatao PODSKUP (screenshot ima manje
riječi, sve sadržane). Ovdje "m." ≠ "manuel" — to je INICIJAL, ne podskup.

**Što (`data_fetcher._name_match` + novi `_tokens_covered`):**
- Tokeni se čiste od točaka ("m." → "m").
- Nova pokrivenost s inicijalima: svaki token kraćeg imena mora imati jedinstven par u dužem
  — jednak ILI inicijal-prefiks ("m" ~ "manuel"). Zamjenjuje raniji čisti podskup-rule
  (podskup je sad poseban slučaj s egzaktnim poklapanjem). Prag >=2 poravnate riječi.

**Sigurnost (provjereno testovima):** braća Cerundolo se NE miješaju u stvarnom smjeru
usporedbe (API "Francisco Cerundolo" vs screenshot "Cerundolo Juan M." → False, jer nema
"juan"). Isto-prezime preko postojećeg pravila ostaje kakvo je bilo; find_match_odds ionako
traži poklapanje OBA igrača.

**Ishod:** 14 unit-testova (Cerundolo/FAA inicijali + braća-negativni + regresija Merida/
Burruchaga/Tsitsipas/Dedura) + stvarna provjera: Collignon–Cerundolo sada vraća 1.65.

---

## 2026-07-17 — Otpornost API-ja (retry) + poklapanje skraćenih imena kladionice

**Povod:** jutarnji daily run 17.07. pao je nakon 38s bez emaila. Log: `405 Client Error`
na `/atp/fixtures/2026-07-17` (prvi i kritični poziv) → 0 mečeva → tihi izlaz. Ponovni
(popodnevni) run onda je izbacio čudan analysis-only: odigrani/live mečevi u prikazu i
kvote 1.50 na većini pickova. Sve dijagnosticirano na stvarnim podacima.

**Uzroci (oba postojeća, nevezana uz izmjene od 16.07.):**
1. **Prolazni ispad API-ja rušio je cijeli run.** `_get` je ponavljao pokušaj SAMO na 429
   (rate limit); na 405/5xx je odmah vraćao None. 405 je bio kratkotrajni RapidAPI blip
   (isti endpoint vraća 200 par sekundi kasnije), ali je oborio dohvat mečeva.
2. **Skraćeno ime kladionice se nije poklapalo.** API "Daniel Merida Aguilar" (3 riječi) vs
   screenshot "Merida Daniel" (2 riječi) — `_name_match` je znao obrnut redoslijed i
   višerječna prezimena istog broja riječi, ali ne i podskup → Meridina kvota (1.55) se
   nije našla → fallback 1.50 → meč izgubi odds_available.

**Što (Fix 1 + Fix 2; Fix 3 svjesno odgođen):**
- **Fix 1 — retry na prolazne greške (`data_fetcher._get`):** 405/500/502/503/504 i mrežni
  blipovi (ConnectionError/Timeout) sada se ponavljaju do 3× uz 3s pauzu. Trajne greške
  (401 ključ, 403 kvota, 404 ne postoji) NAMJERNO fail-fast (bez retryja). Da je ovo
  postojalo, jutrošnji run bi preživio 405.
- **Fix 2 — podskup imena (`data_fetcher._name_match`):** ako su sve riječi kraćeg imena
  sadržane u dužem i dijele >=2 riječi → isti igrač. Prag >=2 sprječava lažno poklapanje.
  Postojeće prezime-pravilo (aw[-1]==bw[-1]) nepromijenjeno.

**Napomena — Problem 1 (odigrani/live mečevi u analizi) NIJE riješen ovdje:** uzrok je što
tennis API kasni (odigrane mečeve još vodi `match_winner=None, live=None` → naš filter ih
vidi kao `scheduled`). Grize samo kod popodnevnog re-runa. Korisnikovo rješenje (Fix 3:
"uzmi samo mečeve koji su na kvote-screenshotu") svjesno odgođeno — vidi [[daily-ticket-workflow]].
Fix 1 neizravno gasi korijen: ako jutarnji run preživi, nema potrebe za popodnevnim re-runom.

**Ishod:** 15 unit-testova (retry: 405→200, 5xx→200, 405×3 odustaje, 404/403 fail-fast,
ConnectionError retry; name-match: Merida podskup + negativni) + stvarna provjera da
Burruchaga–Merida sada vraća 1.55.

---

## 2026-07-16 — Screenshot = izvor istine za glavni ždrijeb + Q-tag korekcija runde

**Povod:** nastavak istrage praznog tiketa 16.07. Nakon QF fixa (dolje), Gstaad/Båstad QF
prolaze, ali **Umag i dalje ispada** — iz drugog razloga: API je Umagova četvrtfinala
(16.07.) vratio kao `roundId=9 → Q2` (kvalifikacije), iako je to glavni ždrijeb (potvrđeno
u korisnikovom screenshotu ždrijeba, kolona ČETVRTFINALE). Krivi Q2 tag radio je dvije
štete: (1) quali-guard ga izbacuje sa selekcije, (2) analiza ga dobiva kao "Round: Q2"
(round_id 9 nije u `_round_context` mapi 1–7 → fallback ispiše doslovno "Q2"), pa bi agent
QF analizirao kao kvalifikacije — točno zagađenje round-signala koji inače koristi ispravno.

**Dizajn (potvrdio korisnik — A + B1):** korisnik svaki dan screenshota SVOJE mečeve
(danas + sutra) u "kvote screenshot", a kvalifikacije prije turnira NIKAD ne screenshota,
ne stavlja na Streamlit niti pokreće daily. Zato je prisutnost screenshot kvote pouzdan,
determinístički dokaz da meč **nije** kvalifikacija.

**Što:**
- **A — selekcija (`ticket_builder._is_main_tour`):** ako meč ima screenshot kvotu
  (`has_screenshot_odds`), propušta se bez obzira na API round-tag. Namjerno IZA
  level-provjere: screenshot NE progura Challenger/ITF/Future (to je policy isključenje,
  ne API greška), nego samo zaobiđe round-based qualifying guard (R128/Q na 250/500).
- **B1 — runda (`run_daily._infer_rounds`):** Q1/Q2 grupa se i dalje ne dira OSIM ako bilo
  koji meč u njoj ima screenshot → tada se ne vjeruje Q-oznaci i runda se izvodi iz broja
  mečeva po `(turnir, dan)` (postojeći mehanizam: 4=QF, 2=SF, 1=F). Ispravlja se i `round`
  i `round_id`, pa analiza dobiva točan round-context. RR i prave kvalifikacije (bez
  screenshota) ostaju netaknute — nula regresije na ispravno označene runde.
- **Preraspodjela:** `screenshot_odds` se sada učitavaju PRIJE `_infer_rounds` (bile su
  učitane tek kasnije), i prosljeđuju u brojalicu. Svaki meč dobiva `has_screenshot_odds`
  zastavicu tijekom obrade (poseban lookup samo protiv screenshota).

**Zašto A i B1 zajedno:** B1 ispravlja rundu uzvodno (rješava i krivu analizu i selekciju
u jednom potezu), A je pojas-i-tregeri za selekciju ako Q-oznaka iz bilo kojeg razloga
preživi. Brojalica broji po turniru **i danu** odvojeno (danas QF, sutra SF se ne miješaju).

**Ograničenje:** brojalica broji samo `scheduled` mečeve — jutarnji run (svi scheduled)
daje točnu rundu; popodnevni re-run nakon što dio QF-a završi mogao bi podbrojati. Daily
ide ujutro pa je u praksi bez utjecaja. Za 100% pouzdanost budući korak = live draw endpoint.

**Ishod:** unit-testovi (6 scenarija) + end-to-end dry-run na stvarnom 16.07. — Umag QF
ulazi s ispravnom rundom.

---

## 2026-07-16 — Bugfix: qualifying guard izbacivao četvrtfinala ("QF" počinje s "Q")

**Povod:** 16.07. ujutro (četvrtak, QF dan na Båstad/Gstaad/Umag) Daily tiket vratio prazan
analysis-only email ("No main-tour matches available") iako je 13+3 mečeva prošlo filter
turnira, kvote sa screenshotova bile učitane i Claude analizirao mečeve (potvrđeno u
`analyzed_matches`). Oba jutarnja runa (07:01 i 08:38) "success" — program nije pukao,
nego je selekcija tiho izbacila sve.

**Uzrok:** qualifying guard iz clay revizije 11.07. u `_is_main_tour()` koristio je
`rnd.startswith("Q")` za detekciju kvalifikacija — a **"QF" (četvrtfinale) također počinje
s "Q"**. Na ATP 250/500 su zato SVA četvrtfinala tretirana kao kvalifikacije → nikad na
tiket, a isti filter prazni i analysis-only prikaz. R32/R16 dane (pon-sri) guard ne dira,
pa se bug pokazao tek na prvom QF danu nakon uvođenja.

**Što:** `ticket_builder._is_main_tour()` — kvalifikacija je sada `startswith("Q") and
rnd != "QF"` (Q1/Q2 i dalje blokirani, R128 guard nepromijenjen).

**Ishod:** verificirano lokalnim dry-runom na stvarnim QF mečevima 16.07.

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
