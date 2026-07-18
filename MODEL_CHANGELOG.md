# Model Changelog

Kronologija promjena modela za generiranje tiketa (predikcija + selekcija + strategija).
Svrha: da kroz iteracije znamo ŠTO smo mijenjali, ZAŠTO, i s kojim ishodom.
Težinske verzije (brojčane) žive u Supabase `model_weights`; ovdje su prompt-pravila,
selekcijska logika i strateške odluke koje se ne vide iz baze.

Format: `datum — naslov` → što / zašto / ishod (ako je poznat).

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
