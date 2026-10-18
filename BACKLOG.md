# Backlog i dnevnik rada

Čitljiv pregled projekta: **što čeka** (s uvjetom kada se radi) i **što smo napravili** (po
danima, jednostavnim jezikom). Brojke, obrazloženja i tehnički detalji su u
`MODEL_CHANGELOG.md`; popis svega što ulazi u odluku o picku je u `DECISION_INPUTS.md`
(dalje: DI).

**Pravilo:** na kraju svake radne sesije ovdje se dopiše što smo napravili i ažurira se
popis otvorenog. Otvoreno 26.09.2026 19:21, zadnje ažurirano 18.10.2026 19:56.

**Jedna naredba za sve zakazane provjere kandidata:** `python scripts/measure_candidates.py`
(čita bazu, ništa ne mijenja; kaže za svakog kandidata ČEKA / POTVRĐEN / PAO).

---

## ČEKA — zakazane provjere

Pravilo projekta (kapija, od 06.09.2026): nijedan nalaz ne ulazi u odluku dok se ne potvrdi
na mečevima na kojima nije pronađen. Svaka stavka ima prag zapisan UNAPRIJED.

| što | kada / uvjet | ishod | gdje |
|---|---|---|---|
| **K25 — servis/povrat iz TML-a SAMO GLAVNOG ŽDRIJEBA** (18.10.2026, nastavak tvog prelaska na TML) | **test A ODGOĐEN** (tvoja odluka 18.10.2026 19:56: "za drugi put"; besplatno, godine 2010–2019 koje nitko nije gledao); **test B** sam se skuplja od 19.10.2026, provjera kad bude ≥ 700 ATP mečeva (~prosinac) | prag zapisan 17:34 prije gledanja: A bolji za ≥ 0,005 log-gubitka u obje polovice i u ≥ 8 od 10 godina; B bolji za ≥ 0,005 uz interval iznad nule naspram sadašnjeg stanja. Tek kad prođu oba → prijedlog nove ere (jedan plaćeni poziv). Na viđenim podacima +0,013 do +0,019 svake godine, ali to je naknadni rez | DI K25; `revizije/2026-10-18/PRAGOVI_C_TML_PROMPT_2026-10-18.md`; osnova koda na grani `tml-era-881d89f8` |
| **Omjer protiv ljevaka** | 300 mečeva s ljevakom (danas 120) | ponovno izmjeriti; do tada samo bilježenje | DI "IZMJERENO 26.09.2026" |
| **K1 — prag VRAĆEN na 63 (04.10.2026 19:22, tvoja odluka)** | prva 3 tjedna (do ~25.10.) | pratiti koliko dana nema tiketa (procjena ~13 od 17) i ROI tiketa; K1 kao nalaz nije se ponovio, pa se prag više ne pomiče po pouzdanosti dok pouzdanost ne pokaže informaciju (r > 0) u dvije ere | `config/model_config.py` TICKET_CONFIG; DI K1 |
| **Noćna sesija (samo bilježenje)** | 60 noćnih pickova od 05.10.2026 | tada pogledati smije li postati kandidat (stari +5,7pp n=83, novi +5,4pp n=12; interval dodiruje nulu, povijest je ne zna) | `context_snapshot.session` |
| **K21 — favorit u QF/SF/F protiv boljeg servera** (tvoja ideja o četvrtfinalima, 04.10.2026) | kad bude ≥ 150 NOVIH ATP mečeva nakon 13.09.2026 (~godinu dana; ~130 godišnje) — nakon što osvježiš `.cache/tennis-data/2026.xlsx` | povijest: −4,1pp (n=617) — skeptik SUMNJIVO (23 testa u sesiji, nema neovisne potvrde). Prolazi: edge ≤ −4pp, interval ispod nule, obje polovice novog razdoblja < 0 → prijedlog kazne pri izboru tiketa (ne u promptu); pada: edge ≥ 0 | DI K21; `python revizije/2026-10-04/skripte/r_lab2.py --od=2026-09-14` · **18.10.2026 15:46: `2026.xlsx` osvježen (do 06.10.), LAB obnovljen — K21 n = 9 od 150, ČEKA** |
| ~~**K17 — pick s "High" scouting profilom**~~ | **PAO i zatvoren 18.10.2026** (n=43, +13,7pp; spojeno −0,3pp) — kazna nikad nije bila u kodu | — | DI K17 |
| ~~**TVOJ "PROVEDI" — revizija 18.10.2026**~~ | **PROVEDENO 18.10.2026 13:02** (tvoj "kreni, 1a 2a 3a") | B1 bazne stope analize gubitka popravljene + četiri nove oznake umjesto SIGNAL CONFIRMED; B2 bonus za konsenzus ugašen; B3 recenzent (L4), K22 i Nose (K24) u `measure_candidates.py`; B4 sažetak dana bez tiketa kaže pravi razlog | `revizije/2026-10-18/REVIZIJA_B_2026-10-18.md` |
| **K22 — ELO jaz i servis/povrat od 14.09.** | 150 hard pickova od 19.10.2026 | r ≥ +0,10 (interval iznad nule, obje polovice) za ELO ili servis+povrat → prijedlog bonusa/težine; oba ≤ 0 → pada. Sada od 14.09.: +0,19 i +0,18 (n=169), prije 0 i obrnuto | DI K22 · od 18.10. mjeri `measure_candidates.py` (K22). **Povijest ga NE podupire** (kritičar 18.10.): LAB r(ELO jaz) +0,00, servis+povrat +0,02 (n=12.320); B4b uz kontrolu pojasa +0,4pp; rez "od 14.09." odabran naknadno |
| **K24 — Nose u sjeni (nose-v1)** (tvoja odluka 1a, 18.10.2026) | od prvog runa s Noseom (~19.10.): G1 mina i G2 vrijednost na protivniku — probir n=60 (G1 ~kraj prosinca, G2 ~5 tjedana), odluka n=150; G3 vlastita procjena n=300 (~2 mjeseca) | presuda ZAMRZNUTA na prvih 60 (probir) / 150 (odluka) / 300 (G3) po datumu; G1: IZBJEGAVAJ ≤ −5pp, interval ispod 0, obje polovice < 0 I ≤ −3pp naspram ostalih pickova u istom pojasu cijene → prijedlog; G2 zrcalno; G3 r ≥ +0,10. Povijest: NO PICK na favoritu +1,3pp, razilaženje s cijenom −1,5pp → realno očekuj PAO (šansa prolaza ~1%, kritičar) | DI K24; `python scripts/measure_candidates.py --only K24` |
| **K23 — "zalet protiv boljih servera" precijenjen (S1 obrnuto)** + **K21** + dubina 4+ | kad osvježiš `.cache/tennis-data/2026.xlsx` (ručno, tennis-data.co.uk) | jednom pokrenuti na ATP mečevima nakon 13.09. s pragovima iz DI (K23: ≤ −3pp, interval ispod nule, obje polovice < 0) | DI K21, K23 · **18.10.2026 15:46: pokrenuto na novim mečevima — S1 n = 4, dubina 4+ n = 1 → ČEKA (2027.)** |
| **K10b — izričit bonus po pojasu kvote** | zasebno testiranje (nije hitno) | prvo simulacija tiketa po varijantama bodovanja, pa prag prije dva turnira; oprez: povijest 1,35–1,43 +3,7pp | DI K10, K10b |
| **Upozorenje AI recenzenta (samo praćenje)** | 30 novih označenih noga od 19.10.2026 | uparena razlika ≤ −5pp i interval ispod nule (spojeno) → tek tada kandidat; sada opis (svih 49: −6,0pp, novčić 25/49) | DI "IZMJERENO 18.10.2026" · od 18.10. mjeri `measure_candidates.py` (L4) |
| **K18 — hard ATP 250 turniri** | 30 takvih pickova od 27.09.2026 (jesen je puna 250-ica) | ≤ −5pp → najviše jedna takva noga po tiketu; iznad nule → odbacuje se. Povijest 27.09.: tržište ondje nema rupu (+0,1pp) — ako postoji, to je naš izbor | DI K18 |
| **K19 — povratak nakon pauze od 21+ dan** | 40 mečeva od 27.09.2026 | isti smjer kao na tržištu → ±2pp; obrnuto → odbacuje se. Povijest 27.09.: −2,5pp, ali polovice različite (slab znak) | DI K19 |
| **K5, K10** (K9 PAO, K11 ZATVOREN 04.10.; K8 se od spajanja odjeljaka 26.09. ne može mjeriti) | K5: n ≥ 100 (04.10.: 16); K10: 25 po pojasu (04.10.: 21/34/20) | svaki svoj prag; K10 oblik zasad kao hipoteza, povijest: tržište u 1,35–1,60 nema rupu | DI K5, K10; `measure_candidates.py` |
| ~~**Konsenzus kladionica**~~ | **BONUS UGAŠEN 18.10.2026 12:37** (tvoja odluka 3a) | nije potvrđen (n=40, −0,4pp ±13,9); stara vrijednost 4.0 čuva se u `_CONSENSUS_GAP_BONUS_DO_18_10`; signal se i dalje bilježi i prati (KONS). Ponovni test samo uz prag zapisan unaprijed | `agent/ticket_builder.py` |
| ~~**Odds API — ključ deaktiviran**~~ | **RIJEŠENO 18.10.2026 11:24** | novi ključ besplatnog plana upisan u GitHub Secrets i `.env`; besplatni `/sports` poziv: status 200, **500/500 kredita**. Večernje snimanje smanjeno na **1× dnevno (17:30 UTC)**. Pratiti potrošnju: `kredita preostalo` u ispisu daily runa; za Australian Open (siječanj) pomaknuti termin | `.github/workflows/market_close.yml` |
| **K20 — Intuicija (naučeni signal u sjeni)** | **dvije provjere:** 150 riješenih procjena (≈ sredina studenog) pa 300 (≈ siječanj), poslije svakih +300. **Mail sa stanjem stiže sam 15.11.2026 i 15.01.2027** | uz 150 treba r ≥ 0,16, uz 300 r ≥ 0,12 (interval iznad nule) i gornja trećina ≥ +3pp → prijedlog bonusa pri izboru tiketa (i za autsajdere); inače uči dalje u sjeni | DI K20; `python scripts/intuicija_report.py` |
| **K14 — Davis Cup** | 20 riješenih Davis Cup mečeva (finalni turnir u studenom) | unutar 5pp od prosjeka → smije na tiket | DI K14 |
| **Clay težine** | prije prve zemlje 2027. (siječanj 2027.) | aktivna v17 nastala je iz auto-feedbacka na analizama gubitaka (ELO spušten na 11%) — vratiti na v13 ili izjednačiti s hardom | Supabase `model_weights`; MODEL_CHANGELOG 26.09.2026 20:46 |

## ČEKA — ideje i popravci bez roka

- ~~**Push na GitHub**~~ — **NAPRAVLJENO 18.10.2026** (tvoje odobrenje; commiti b57c0eb, 416a42f i
  TML commit). Push mijenja kod za idući ručni dnevni run i Streamlit. CI s testovima ne postoji
  (nijedan workflow se ne pokreće na push), pa se testovi vrte lokalno prije pusha. Povratak:
  `git revert <sha>` pa push; scouting `b_scouting_vrati.py --vrati`.
- **Servis/povrat: TML 12 mj. se PRATI uz RapidAPI od 18.10.2026 15:47 (tvoja odluka).** Bilježi se uz svaku analizu, a Nose ga koristi.
  - ~~Prelazak modela na TML~~ — **18.10.2026 19:44 izmjereno i NIJE uveden** (vidi dnevnik):
    TML sa svim razinama (Challengeri, kvalifikacije) procjenjuje igrače jednako ili lošije od
    karijere. Nastavak je K25 (samo glavni ždrijeb) gore u zakazanim provjerama.
  - Tablica: `config/tml_forma_12m.json`, osvježava se prije svakog dnevnog runa.
- **Sljedeća era prompta — dvije stavke iz Šangaja (18.10.2026):**
  - (1) pravilo 2 ("dvije neovisne kategorije → 70%+") neka kaže da ELO, rang i omjer na podlozi
    NISU neovisne potvrde (Zverev–ADF);
  - (2) blok težina maknuti ili ELO vratiti na 22 (v18 je nastala iz automatske petlje nad 10
    poraza i 10 pobjeda, a model težine ne koristi).
  Ništa novo se ne dodaje.

- **Drugi izvor tržišnog konsenzusa za ATP 250.** The Odds API pokriva samo GS, Masters i
  nekoliko 500-ica; na ostalim turnirima jedini potvrđeni tržišni signal ne postoji. Treba
  odabrati izvor (i možda platiti) — korisnikova odluka. *Dopuna 27.09.2026 11:09:* jedan
  javni projekt (`gmalbert/tennis-predictions`) vuče kvote više kladionica za sve teniske
  mečeve iz nedokumentiranih Flashscore adresa, bez ključa. Besplatno, ali može puknuti bilo
  kad i vjerojatno krši uvjete stranice — samo kao opcija za tvoju odluku.

- **Vijesti po igraču.** ESPN i BBC od 13.09. nisu dali nijednu vijest o igračima koje
  analiziramo (0 od 43 analize) — pišu o vrhu tablice. Treba izvor koji traži po imenu
  igrača. Bez toga se K13 (vijesti o ozljedama) ne može izmjeriti.
  *Rješenje nađeno 27.09.2026 11:09:* Google News RSS pretraga po imenu (besplatno, bez
  ključa) — probano na Machaču, vratio je 50+ članaka, među njima i vijest o njegovoj ozljedi
  stopala s Roland-Garrosa. **NAPRAVLJENO 27.09.2026 12:00:** bilježi se uz svaku analizu
  (model ne vidi); K13 se mjeri kad bude 40 pickova protiv igrača s vijesti o ozljedi (DI K13).

- ~~**Povijesni laboratorij**, **radni tijek u Claude Codeu** (CLAUDE.md, `/oblikuj`,
  `/mjerenje`, `/kraj-sesije`, skeptik) i **pregled prompta** (izvještaj)~~ — **NAPRAVLJENO
  27.09.2026 12:00**, vidi dnevnik. Pregled prompta primijenjen 27.09.2026 12:17 (era bccf4742).
- **Winston-Salem: traženje turnira odustaje nakon 5 pokušaja** pri razrješavanju rezultata,
  pa dio analiza ostane nerazriješen. Prijedlog od 31.08.2026, čeka odobrenje.
- **Nesigurnost brojki u promptu** (npr. hold% je procjena ±8pp, a prikazuje se kao
  činjenica). Otvoreno od 08.08.2026; ide uz sljedeću veću izmjenu prompta (DI točka 4).
  *27.09.2026 12:17:* namjerno NIJE ušlo u eru bccf4742 — to bi bio novi tekst u promptu, a ta era je
  samo micala izmjereno krivo. Hold% je u promptu već označen kao procjena i "nije drugi signal".
- **Model može samo spustiti pouzdanost, nikad promijeniti stranu picka.** Otvoreno od
  29.08.2026.
- **Kvaliteta zraka (AQI) uz vrijeme** (04.10.2026 19:38): tvoj komentar o Đokovićevom "teškom
  disanju" u Pekingu — zabilježena vlaga bila je 11% (suh zrak), pa vlaga nije uzrok; vjerojatnije
  smog. OpenWeather ima besplatan Air Pollution API (isti ključ, koordinate već dolaze uz prognozu).
  Prijedlog: samo BILJEŽITI PM2,5/AQI u `context_snapshot` (model ne vidi), pa izmjeriti kad bude
  dovoljno mečeva u Aziji. Čeka tvoj OK.
- **Umor/odmor iz prompta kao "strong filter"** (04.10.2026 18:33): na 12.324 meča ne nosi ništa
  povrh cijene (manje setova na turniru −0,3pp n=7.367; umorniji u QF+ −0,2pp n=1.056), a model ga
  koristi u 60% "Own read" odjeljaka. Ide uz sljedeću izmjenu prompta (nova era): maknuti kao potvrdu,
  ništa novo ne dodavati. Revizija 04.10., točka 13 C.
- ~~**"Intuicija" — naučeni signal**~~ — **NAPRAVLJENO 27.09.2026 12:34** (u sjeni), vidi dnevnik i K20 gore.
- **Drugi AI model kao neovisni analitičar** (mjeri se predviđa li slaganje dvaju modela
  bolje od jednoga). Niski prioritet.
- ~~**Čišćenje prompta: odjeljci analize**~~ — **NAPRAVLJENO 26.09.2026 21:27**, vidi dnevnik.
  Stari opis prijedloga:
  Iz prompta maknuti ono što je izmjereno kao krivo, a model to i dalje koristi: blok
  "povijest turnira je najjača varijabla" (pala dvaput izvan uzorka), hard pravila 4/13/16
  (tie-break i "izjednačen servis" — mjereno u krivom smjeru), blok o "kasnim rundama"
  (brojke s krivih oznaka rundi), blok koji potiče autsajdere (proturječi kazni za tržišnog
  autsajdera) i rečenice o "pragu 63%" (u kodu je 60 od 08.09.). Odjeljke 4 i 5 spojiti u
  jedan kratki "Kontekst", servis skratiti na opis. Ništa novo ne dodavati u prompt.
  **Najbolji trenutak: prije sljedećeg dnevnog runa** — era `bce5693b` još nema nijednu
  analizu, pa izmjena ne reže korpus. Posljedica: K1 (prag 60) i kazna za pojas 65-68
  moraju se ponovno izmjeriti nakon jednog turnira. Pravilo 11 (domaći teren) čeka K2.

## ČEKA — na tvoj znak (dogovoreno 27.09.2026 12:00, sada se NE radi)

- **Supabase MCP, samo za čitanje** (`read_only=true`, `project_ref` samo ovog projekta) —
  Claude bi u sesijama izravno čitao bazu umjesto da piše skripte. Treba tvoja jednokratna
  prijava u pregledniku.
- **Playwright MCP + `/run-skill-generator`** — Claude otvori Streamlit aplikaciju, klikne i
  napravi screenshot, da vidi rezultat izmjene na stranicama ("Claude je slijep"). Isplati se
  tek kad budemo mijenjali stranice.
- **rtk** (`winget install rtk-ai.rtk`) — skraćuje ispis naredbi (git, testovi) koji Claude
  čita. Mali dobitak; mjeri se s `rtk gain`, lako se makne.
- **Sonnet 5 umjesto Sonnet 4.6** — jeftiniji po tokenu ($2/$10 naspram $3/$15), ali broji ~30%
  više tokena i razmišljanje mu je uključeno po zadanom (treba veći `_ANALYSIS_MAX_TOKENS`).
  Sonnet 4.6 nije zastario; raditi samo na prijelomu ere, najbolje zajedno s odlukom 3.

## Redovito održavanje

- **Ruka novih igrača:** dnevni run nepoznate igrače dohvaća sam (najviše 150 po runu), ali
  ih ne sprema trajno. Povremeno pokrenuti
  `python scripts/backfill_player_context.py --collect --hands` i commitati `player_hands.json`.
- ~~**Provjera K15**~~ — K15 zatvoren 27.09.2026 (povijesno +0,0pp).
- **Intuicija:** stanje u sjeni `python scripts/intuicija_report.py`. Kad osvježiš
  `.cache/tennis-data/2026.xlsx`, ponovno nauči prior: `lab_data.py` → `lab_features.py` (u
  `revizije/2026-09-27/skripte/`) → `python scripts/intuicija_prior.py`, pa commit.

---

## NAPRAVLJENO — dnevnik

### 18.10.2026 19:44 — Prelazak modela na TML servis/povrat: napravljen, provjeren i NIJE uveden

Tvoje odobrenje: nova era, TML za zadnjih 12 mjeseci i jedan plaćeni probni poziv, **ako rezultati
to opravdaju**. Pravila za odluku zapisana su prije računanja (PRAGOVI_C, 16:25).

- **Napravljeno je sve:**
  - prompt dobiva TML brojke (12 mj. "povučeno" prema karijeri) i izmjereni hold;
  - pragovi u pravilima preslikani su na novu skalu, s pričuvom za igrača bez TML-a;
  - iz scoutinga su maknute stare brojke;
  - testovi su dopisani;
  - **jedan plaćeni probni poziv je prošao**: ispravan odgovor, 57% stropa, navodi nove brojke.
- **Mjerenje ga ne opravdava**, pa model ostaje kakav je bio (era bccf4742):
  - čistih 12 mjeseci procjenjuje igrače lošije od karijere; po pravilu zapisanom unaprijed to
    znači "ne prelazi se";
  - mješavina 12 mj. + karijera bolja je za samo +0,003 na 2024–26, što je u šumu, a 2026. je lošija;
  - na istim našim mečevima 58,3% → 59,3%, također šum;
  - skeptik: PADA.
- **Zašto:** u gotovo pola mečeva bar jedan igrač ima više od pola poena iz Challengera i
  kvalifikacija. Ti su postotci postignuti protiv slabijih protivnika, pa ga brojke prikazuju
  boljim nego što jest. U tim mečevima nova verzija je lošija od stare.
- **Ništa nije izgubljeno:** cijela implementacija je na lokalnoj grani `tml-era-881d89f8`
  (commit 54590fb).
- **Novi kandidat K25:** TML samo s glavnog ždrijeba izgleda bolje svake godine (+0,013 do
  +0,019), ali je nađen naknadno. Prag za potvrdu zapisan je unaprijed, a test A se može
  napraviti odmah i besplatno.
- **Nose:** ostaje kako je bio (TML 12 mj.). Dodatak da prijeđe na mješavinu povučen je prije
  prvog podatka.

Testovi na `master`: 907 + 271 OK. U modelu, tiketu i Noseu ništa nije promijenjeno.

**Zatvaranje dana (19:56, tvoje odluke):** TML promjena zasad NE ulazi u glavni model; test A za drugi
put; grana `tml-era-881d89f8` ostaje odvojena (samo lokalno, nije na GitHubu). Provjereno prije
zatvaranja:
- `master` = GitHub (7b89250), bez nespremljenih izmjena;
- era hard bccf4742, clay 84792fca, grass b22b1375 (iste kao 04.10.);
- prompt ne koristi TML;
- Nose se računa tek nakon tiketa, a `ticket_builder` ga ne uvozi;
- Daily Ticket se pokreće samo ručno, s `master`a;
- testovi 907 + 271 OK.

**Sutra (19.10.) prvi put u produkciji rade Nose i bilježenje TML-a.** U ispisu runa treba vidjeti
"Nose (sjena, nose-v1): izracunat za N predikcija" i "TML forma 12 mj. (podaci do ...)". Redak s
"!!!" znači da je taj dio pao; tiket time nije pogođen.

Gdje:
- `revizije/2026-10-18/PRAGOVI_C_TML_PROMPT_2026-10-18.md` (pravila, rezultati, K25);
- skripte: `revizije/2026-10-18/skripte/c_tml_*.py` i `skripte/skeptik_tml/`;
- probni poziv: `revizije/2026-10-18/zivi_poziv_TML/`.

### 18.10.2026 15:47 — Novi 2026.xlsx, TML forma 12 mj. uz RapidAPI, Nose na TML-u, push

- **Tvoj novi `2026.xlsx`** (do 06.10.):
  - povijesni laboratorij obnovljen (12.472 meča);
  - TML preuzet svjež;
  - Intuicija prior ponovno naučen, s neznatnim pomakom.
  - K21 i K23 pokrenuti na mečevima nakon 13.09.: premalo slučajeva (9 od 150, odnosno 4). Čekaju
    se do 2027.; to je zapisano unaprijed.
- **TML forma za zadnjih 12 mjeseci** se od danas bilježi uz RapidAPI ("pratit ćemo i jedno i
  drugo").
  - Prije toga provjereno: pokrivenost 99–100%, svježina oko tjedan dana, pričuva definirana.
  - Skala povrata je 4,5pp niža od RapidAPI-ja.
  - Tablica se osvježava prije svakog dnevnog runa (besplatno).
- **Nose** sada uživo koristi TML (iste brojke kao na povijesti), a karijernu varijantu bilježi
  usporedno.
- **Model (prompt) ostaje na RapidAPI-ju.** Pravila u njemu imaju pragove na toj skali, pa
  prelazak ide uz sljedeću eru i jedan plaćeni poziv, na tvoj znak.
- Jodarov scouting maknut s popisa (tvoja odluka).
- Testovi: 907 i 271 OK. Tri commita, pushano.

**Pazi:** Nose i bilježenje TML-a vide se tek od idućeg dnevnog runa.

Gdje:
- `scripts/update_tml_form.py`, `agent/tml_forma.py`, `config/tml_forma_12m.json`;
- `agent/nose.py`, `agent/run_daily.py`, `.github/workflows/daily_ticket.yml`;
- `revizije/2026-10-18/skripte/b_tml_provjera.py`.

### 18.10.2026 15:13 — Revizija Šangaja, drugi dio: Nose u sjeni, bonus za konsenzus van, analiza gubitka popravljena

Tvoj "kreni, 1a 2a 3a". Sve brojke i obrazloženja su u izvještaju; ovdje je kratko što je
napravljeno i gdje.

- **Tiketi 8 naspram 10:** od 10 pravih tiketa od 27.09., 8 ima noge samo s Tokija, Pekinga i
  Šangaja (30.09.–12.10., svi izgubljeni). U analizi su svih 10.
- **Šangaj:** pickovi na razini tržišta (−1,4pp). Greške su bile u obrazloženju, ne u broju:
  - isti podatak brojan dvaput (ELO + omjer na podlozi, asovi povrh servisa);
  - Challengeri u omjeru na podlozi (Jodar);
  - zastarjeli scouting (ADF);
  - Medvedev 60% i Zverev 72% bili su ispod tržišta — dobre odluke, loš ishod.
- **Nose (novo, u sjeni):** četiri procjene po meču, s NO PICK-om.
  - Prvo radi vlastitu procjenu bez kvote, zamrzne je, tek onda uspoređuje s cijenom.
  - Vidi se na Dnevnom listiću uz razinu dokaza.
  - Ne mijenja pick ni tiket.
  - Povijest kaže da zasad ne tuče cijenu, pa se mjeri na budućim mečevima (K24, presuda
    zamrznuta, s kontrolom pojasa kvote).
- **Bonus za konsenzus ugašen** (4 → 0). Povratak je jedna konstanta, a signal se i dalje prati.
- **Analiza gubitka:** popravljena tri zastarjela retka ("ATP wins" više nije "jedina koja
  preživi"). SIGNAL CONFIRMED zamijenjen je s četiri odvojena pojma; izmjenu smije predložiti
  samo "GATE PASSED", a njega danas nema nijedan faktor.
- **Sažetak dana bez tiketa** kaže pravi razlog (prag ili premalo mečeva).
- **Mjerenja:** K22, K24 i L4 u `measure_candidates.py`.
- **Scouting (Supabase + Excel):**
  - promijenjen 1 tekst (Atmane "strong return": povrat 3. percentil);
  - osvježeno 66 rangova;
  - novi listovi "Dokazi" i "Promjene";
  - Đoković povučen (premala razlika, izvori proturječni);
  - sigurnosna kopija i skripta za povratak postoje.
- **Testirano i odbačeno:**
  - 4 preostale kombinacije s tvog popisa;
  - pristupi 2 i 3 za statistiku s turnira;
  - Nose na povijesti;
  - težine (v18 je nastala iz automatske petlje, model je ne koristi);
  - prag, broj nogu i kvota (nijedna varijanta ne prolazi zapisani kriterij).
- **Kritičar:** SUMNJIVO. Tri "traga" ne drže (B4b, M2, smjer IZBJEGAVAJ). Ispravljeno prije
  upisa.

**Pazi:**
- Ništa nije pushano. Dnevni run i aplikacija ne vide izmjene dok ne pushaš.
- Scouting u Supabaseu djeluje odmah.
- Servis/povrat koji model vidi je karijerni, ne sezonski. Prijedlog (TML) čeka tvoju odluku.

Gdje:
- `agent/nose.py` (novo);
- `agent/ticket_builder.py`, `agent/run_daily.py`, `agent/feedback_analyzer.py`;
- `scripts/measure_candidates.py`, `pages/1_Dnevni_Listic.py`;
- testovi: odjeljak 52 i prepravljeni testovi konsenzusa i oznaka;
- `revizije/2026-10-18/REVIZIJA_B_2026-10-18.md`, `PRAGOVI_B_2026-10-18.md`, `skripte/b_*.py`,
  `scouting/`;
- DI K24, K22 i "IZMJERENO 18.10. drugi dio".

### 18.10.2026 11:24 — Odds API: novi besplatni ključ radi, večernje snimanje 1× dnevno

- Novi ključ (besplatni plan) upisao si u GitHub i `.env`. Provjereno besplatnim pozivom: radi,
  **500 od 500 kredita**.
- Večernje snimanje kvota smanjeno je s 3 na **1 termin dnevno (17:30 UTC)**. Jedno snimanje
  troši 3 kredita po aktivnom turniru; uz jutarnji dohvat to je ~180–360 kredita mjesečno.
  Termin 17:30 hvata kasne dnevne i večernje mečeve u Parizu i Torinu (Europa je od 25.10.
  UTC+1). Za Australian Open termin treba pomaknuti.
- Test koji je čuvao stari raspored prepravljen je da čuva novi. Oba paketa prolaze.

**Pazi:** novi raspored djeluje tek nakon commita i pusha na GitHub. Ključ djeluje odmah.

Gdje: `.github/workflows/market_close.yml`, `test_provisional_schedule.py` (odjeljak 13).

### 18.10.2026 10:11 — Revizija Peking/Tokio/Šangaj: zašto gubimo tikete (u modelu ništa nije mijenjano)

Pregledano: 140 novih pickova (27.09.–17.10.), svih 10 tiketa, 30 analiza gubitaka (22 iz
Šangaja), 36 tvojih ideja na 12.324 povijesna meča, kvote 50 kladionica, vrijeme, scouting,
težine, runde i ~2.700 linija starih komentara u kodu. Kritičar (skeptik) je sve pregledao, a
njegovi ispravci su ugrađeni.

- **Pickovi su na razini tržišta:** 66,4% pogođeno, kvote su očekivale 65,7% (+0,7pp; s Munarovim
  krivim ELO-om −0,4pp; Šangaj −1,4pp). Nema dokaza kvara, a ni dokaza da smo bolji od tržišta.
- **Tiketi:** 1 od 10 dobitan, očekivano ~1,9. Svih 66 tiketa od svibnja: 5 dobitnih, očekivano
  ~6,9.
  - Tiket s kvotom ~4 prolazi ~1 od 5 puta i kad noge pogađamo točno kako kvota kaže.
  - 10 od 13 izgubljenih noga bilo je na 1,50–1,90; 6 tiketa palo je na jednoj nozi.
- **Statistika s turnira po rundama** (tvoja ideja): tko na turniru igra bolje, pobjeđuje 56–64%,
  ali favorit po kvoti 68%. 18 testova, 0 prolazi. Kombinacije, sekvence te dob i visina: 0 od 18.
- **"ATP wins this season gap"** agent piše zbog zastarjelog retka u analizi gubitka (K15 je
  zatvoren 27.09.). Od 6 oznaka SIGNAL CONFIRMED nijedna nije potvrđena.
- **Upozorenje AI recenzenta** ("najrizičnija noga") samo je opis: na svih 49 noga −6pp, unutar
  tiketa kao novčić. Prati se.
- **K17 zatvoren** (kazna nikad nije bila u kodu).
- **Konsenzus nije potvrđen.** Kriterij za uklanjanje bonusa nije nedvosmislen, pa odlučuješ ti.
- **K10** je formalno zadovoljen, ali se oblik nije ponovio → K10b.
- **Nove hipoteze:** K22 (ELO i servis od 14.09. nose nešto povrh kvote?) i K23 (precijenjen
  "zalet protiv boljih servera").
- **Odds API ključ je deaktiviran od ~15.10.** Treba novi ključ besplatnog plana.
- Vrijeme, runde, težine, scouting i kretanje kvota nemaju podlogu ni za kakvu promjenu.

**Pazi:**
- U kodu su dodani samo komentari, era `bccf4742` je nepromijenjena. Ništa novo ne djeluje dok ne
  kažeš "provedi".
- Oba testna paketa prolaze. Ništa nije commitano.

Gdje:
- `revizije/2026-10-18/REVIZIJA_2026-10-18.md` (izvještaj) i `PRAGOVI_REVIZIJA_2026-10-18.md`;
- skripte `revizije/2026-10-18/skripte/r_*.py` (samo čitaju);
- DECISION_INPUTS: "IZMJERENO 18.10.2026", K17, K10, K22, K23, K10b;
- komentari u `agent/ticket_builder.py`, `agent/feedback_analyzer.py`, `agent/predictor.py`,
  `agent/run_daily.py` i `config/model_config.py`.

### 04.10.2026 19:32 — Provedeno: ELO popravak, rang iz singl liste, prag natrag na 63, analiza gubitka; tvoja pitanja

Po tvojoj odluci iz revizije (točke 1, 2, 4, 5; točku 3 prepustio si meni):

- **ELO.** Igrač se sada traži po cijelim riječima imena. Munar dobiva svoj ELO (1748), a ne
  Clarkeov. Čita se cijela ELO tablica, ne samo prvih 1.000 redaka. Obrisano je 546 starih
  duplikata (sigurnosna kopija je spremljena). Današnje osvježavanje ELO-a sada stvarno djeluje
  (268 igrača dobilo je svjež ELO). Nova zaštita: ako igrač iz top 100 ima ELO ispod 1.550, meč
  se preskače, jer je takav ELO gotovo sigurno tuđi. 10 analiza s krivim Munarovim ELO-om
  označeno je i ne ulazi u mjerenja.
- **Rang.** Sada dolazi s ATP singl liste (500 igrača). Profil igrača je ostao samo rezerva, jer
  je 24.–28.09. davao tuđe rangove (Royer 548 umjesto 75, Basilashvili 22 umjesto 145).
  Potrošena su 2 RapidAPI poziva za provjeru.
- **Prag tiketa 63** (bio 60). Pravilo zapisano 08.09. je okinulo. Očekuj puno više dana bez
  tiketa (procjena ~4 tiketa u 17 dana).
- **K11 (R16/QF) zatvoren:** nije se potvrdio, a R16/QF su ovaj put bili čak bolji od ostalih
  rundi.
- **Analiza gubitka** više ne zove R16/QF "potvrđenim". Dobiva i razinu turnira i prag koji je
  vrijedio na dan meča.
- **Tvoja pitanja:**
  - "1/16 finala" = R32 je ispravno (broji igrače, ne mečeve);
  - duplikata u Analyzed Matches nema;
  - tablica "top 200 × turniri" ne tuče tržište (+1,4pp, interval preko nule), pa je ne gradimo;
  - vlaga ne nosi ništa (Đoković je u Pekingu igrao uz 11% vlage, dakle suh zrak);
  - **tvoja ideja o četvrtfinalima prošla je predprovjeru** na 12.324 povijesna meča (vidi K21).

**Pazi:** izmjene djeluju u dnevnom runu tek kad se commitaju i pushaju na GitHub.

Gdje u kodu:
- `agent/data_fetcher.py` (`find_player_elo`, `elo_implausible`)
- `database/supabase_client.py` (`get_elo_cache`)
- `agent/run_daily.py` (`_rank_of`, zaštita ELO-a)
- `config/model_config.py` (`TICKET_CONFIG`)
- `agent/feedback_analyzer.py` (`_LOSS_BASE_RATES`, `_loss_match_facts`)
- `scripts/measure_candidates.py`
- testovi: odjeljak 51

### 04.10.2026 18:34 — Revizija azijske turneje: zašto smo pogađali i promašivali (ništa nije mijenjano)

Pregledano 57 novih pickova (28.09.–04.10.: završnice Chengdua i Hangzhoua, Peking, Tokio),
8 analiza gubitaka sa stranice, tvoje varijable na 12.324 povijesna meča i scouting.

- **Rezultat:** 35 od 57, −4,5pp naspram cijene (interval ±12pp, dakle slučajnost). Sav minus je
  Tokio (12 od 26); Peking 18 od 25. Bez 3 meča s krivim ELO-om manjak je −1,9pp.
- **Kvar u podacima:** Munar je u svakoj analizi dobivao ELO Jaya Clarkea (1397 umjesto 1748).
  Model je tri puta u Tokiju išao protiv njega zbog "ogromnog ELO jaza", i tri puta izgubio.
  Uz to današnje osvježavanje ELO-a ne djeluje (stari zapisi s NBSP dolaze prvi) i čita se samo
  1.000 od 1.138 redaka. Popravak čeka tvoj OK.
- **Tvoje varijable** (forma, podloga, hold, break, asovi, DF, H2H, rang, umor) i 9 kombinacija:
  na 12.324 meča **0 od 18** tuče tržište. Ne istraživati ponovno bez novog izvora.
- **"Intuicija" agenta:** pick je tržišni favorit u 96,5% slučajeva, a odmak pouzdanosti od
  cijene ne nosi informaciju. Najčešći argument modela je umor (60% "Own read"), a tržište ga
  plaća.
- **Kandidati:**
  - K1 na pragu povratka na 63 (tvoja odluka, vidi ČEKA);
  - K9 pao;
  - K11 nije potvrđen (prijedlog zatvaranja);
  - K17 se okreće.
- **Analize gubitaka:** činjenice su sada točne (8 od 8). Ali 3 od 8 zovu R16/QF "potvrđenim",
  jer ga njihov prompt prikazuje bez oznake "nepotvrđeno".
- **Scouting Excel:** ne širiti radi predviđanja (pokrivenost 95%, profil ne nosi ništa povrh
  cijene).

Kritičar (skeptik) je oborio jedan moj naslov ("nadigrani, ne nesretni" kršio je vlastito
pravilo zapisano unaprijed); ispravljeno u izvještaju.

**Pazi:** ELO koji model vidi star je od 29.08. dok se ne popravi keš. Tih 10 analiza s
Munarovim krivim ELO-om ulazi u sva buduća mjerenja dok se ne označe.

Gdje: `revizije/2026-10-04/REVIZIJA_2026-10-04.md` (izvještaj), `PRAGOVI_REVIZIJA_2026-10-04.md`,
`Revizija_2026-10-04_prilog.xlsx`, skripte `revizije/2026-10-04/skripte/r_*.py` (samo čitaju),
DECISION_INPUTS "IZMJERENO 04.10.2026 18:32".

### 27.09.2026 19:29 — Pretplate: Odds API ide na besplatni plan, RapidAPI ostaje Pro

Izmjerili smo koliko stvarno trošimo na dva plaćena izvora podataka (tvoje pitanje može li
se pretplata spustiti):

- **RapidAPI (Pro, 29 $):** od 07.09. potrošeno 12.752 od 75.000 poziva, oko 625 dnevno
  (~19.000 mjesečno, 25%). Besplatni plan daje 50 poziva dnevno, a samo jutarnji run troši
  stotine — zato ostaje Pro. Na slici plana piše 150.000, ali API nama javlja 75.000.
- **The Odds API (20K, 30 $):** u rujnu 187 od 20.000 kredita (1%), u tome 13 dana US Opena.
  Tenis pokriva samo 22 ATP turnira (Grand Slamovi, Mastersi, dio 500-ica), od 13.09.
  nijedan. Besplatni plan (500 kredita) ima oštre kladionice (Pinnacle, Betfair, Matchbook,
  Smarkets); otpadaju povijesne kvote (ne koristimo ih) i 2 američke kuće od ~44 po meču.

**Odluka:** u listopadu prelaziš na besplatni Odds API; RapidAPI ostaje kako jest. Ušteda
~360 $ godišnje. U kodu ništa nije mijenjano.

**Pazi:** dan pokrivenog turnira troši ~14 kredita, od toga 9 tri večernja snimanja kvota
(samo mjerni alat). Najgori mjesec (npr. travanj) procijenjen je na ~430 od 500 — tijesno.
Ako krediti nestanu, ništa ne puca: jutarnji run samo preskoči konsenzus do kraja mjeseca.
Što napraviti nakon prelaska piše u "ČEKA".

Gdje u kodu: `agent/market.py` (konsenzus), `scripts/capture_market_close.py` i
`.github/workflows/market_close.yml` (tri snimanja dnevno), `agent/data_fetcher.py` (RapidAPI).

### 27.09.2026 12:49 — Intuicija: dvije provjere (150 pa 300) i mail u dva zakazana dana

Po tvojoj odluci Intuicija se provjerava **dva puta**: prvi put kad skupi **150** riješenih
procjena (otprilike sredinom studenog), drugi put na **300** (siječanj). Nakon svake provjere
nastavlja učiti. Uz manji uzorak provjera traži jači dokaz, pa rizik da prođe bezvrijedna
intuicija ostaje mali (oko 3–4% preko obje provjere).

**Javljanje:** bez dnevnog maila. GitHub će se sam upaliti **15.11.2026 i 15.01.2027** i poslati
ti jedan mail sa stanjem; ja ću ti to reći i u prvoj sesiji nakon tih datuma (zapisano u memoriju).
Mail se može poslati i ručno: GitHub → Actions → "Intuicija - provjera kapije K20" → Run, uz
kvačicu "force".

*Gdje:* `agent/intuicija.py` (`gate_status`, jedno mjesto za pravilo), `scripts/intuicija_status_email.py`,
`.github/workflows/intuicija_status.yml`, K20 u `scripts/measure_candidates.py` i DI.

### 27.09.2026 12:34 — "Intuicija": naučeni signal koji prati svaki meč (u sjeni)

Napravljen je poseban statistički model — tvoja "intuicijska varijabla". Za **obje strane
svakog meča** procjenjuje koliko igrač prolazi bolje ili lošije od svoje kvote, i diže
zastavicu kad bi uzeo **autsajdera kojeg Claude nije odabrao**.

- **Kako uči:** polazi od kvote i uči samo odstupanja. Temelj su obrasci s 12.322 povijesna
  meča (npr. Grand Slam favoriti 1,30–1,50 +3,2pp, igrač nakon pauze 21+ dana −2,3pp). Na to
  dodaje ono što vidi na našim analizama, i **uči iznova svako jutro** na svemu dotad riješenom,
  dakle raste s podacima.
- **Kad šuti:** ako na mečevima koje nije vidio ne bi bio bolji od kvote, kaže 0 umjesto da
  izmišlja.
- **Iskreno stanje danas:** naučio je ono što znamo (npr. "High" scouting profil −2,9pp), ali
  provjera "kako bi prošao da je postojao" još ne pokazuje vještinu (r = +0,01). Zato je **u
  sjeni**: zapisuje procjenu, a tiket je ne vidi. Kad skupi 300 riješenih procjena, provjera
  (K20) kaže smije li dobiti riječ pri slaganju tiketa, uključujući autsajdere.

*Gdje:* `agent/intuicija.py`, `config/intuicija_prior.json`, `scripts/intuicija_prior.py`,
`scripts/intuicija_report.py`, blok "INTUICIJA U SJENI" u `agent/run_daily.py`, K20 u
`scripts/measure_candidates.py` i DI. Testovi: odjeljak 50 (14 provjera), oba paketa prolaze.

### 27.09.2026 12:17 — tvoje odluke provedene: nova era prompta, K15/K16/K3 zatvoreni, K5 strože

**Tvoja odluka:** tiket ostaje **3–6 parova i ukupna kvota 4–50** (provjereno u kodu da je tako;
nije dirano). Prijedlog o manje nogu je time odbačen i neće se ponovno predlagati.

1. **Pravilo o domaćem terenu je van.** Model više ne oduzima 3 boda kad je protivnik domaći —
   na 2.775 mečeva domaći igrači nisu bili bolji od cijene. Ista provjera maknuta je i iz
   AI-recenzenta tiketa, da ne živi dalje na drugom mjestu.
2. **Statistika s ovog turnira** i dalje se prikazuje, ali model je smije koristiti samo za opis,
   ne za pomicanje pouzdanosti (na 970 mečeva nije dodala ništa cijeni).
3. **Tekst prompta je očišćen** od datuma i vikanja ("THE SINGLE MOST IMPORTANT", "CRITICAL");
   sadržaj ostalih pravila nije diran. Prompt je kraći za četvrtinu stranice.
4. **Zatvoreno:** K15 (pobjede u sezoni), K16 (GS iskustvo), K3 (Bo5 1,30–1,50). **K5** (oprezna
   zona od 1,35) sada traži 100 mečeva umjesto 20 prije ikakve odluke.

**Čemu služi:** model manje griješi na stvarima koje su izmjerene kao krive, a tiket ne kažnjava
dobre pickove. **Ne očekuj** skok ROI-ja samo od ovoga. **Pazi:** nova era (hard `bccf4742`), pa se
K1 (prag 60) premjerava nakon prvog dovršenog turnira. Provjereno: oba testna paketa prolaze,
jedan živi poziv modela vratio je ispravan odgovor s pet odjeljaka (1.026 tokena, strop 4.000).

*Gdje:* `agent/predictor.py` (komentar "IZMJENA PROMPTA (27.09.2026 12:13"), `agent/ticket_builder.py`
(`_review_ticket`), `scripts/measure_candidates.py` (K5), DI (K1, K2, K3, K5, K12, K15, K16).

### 27.09.2026 12:00 — povijesni laboratorij, vijesti po igraču, radni tijek, Handy (tvoje odobrenje)

1. **Povijesni laboratorij.** Tvoje tablice (tennis-data 2022–2026) spojene su s TML-om
   (runde, statistika, povijest igrača) — 12.324 meča, spojeno 99,7%. Pragovi su zapisani prije
   računanja. **Glavno:** nijedan naš kandidat ne pobjeđuje tržište; naša "rupa" na 1,35–1,60
   nije tržišna (favoriti na 1,35–1,43 su čak bolji od cijene); naši pickovi su točni koliko i
   tržište, a po SuperSport kvoti prosječno gube maržu (EV −5,3% po picku, −3,1% po nozi tiketa).
   SuperSport nije lošiji od prosjeka kladionica (marža 5,2% naspram 6,25%).
   *Služi:* znamo što NE uvoditi (K3, K5, K15, K16) i što izbaciti iz prompta (domaći teren,
   statistika s turnira). Odluke su na vrhu, pod "TVOJE ODLUKE". **Ništa u modelu nije mijenjano.**
2. **Vijesti po igraču** s Google Newsa bilježe se uz svaku analizu od sljedećeg runa (naslovi
   iz zadnjih 14 dana, oznaka ozljede). Model ih ne vidi, era se ne mijenja; ako Google ne
   odgovori, run ide dalje. Za oko 20 mečeva run je dulji otprilike 50 sekundi.
3. **Pregled prompta** prema Claudeovim uputama — samo izvještaj s gotovim prijedlogom izmjene.
4. **Radni tijek u Claude Codeu:** `CLAUDE.md` (cilj projekta i pravila), naredbe `/oblikuj`,
   `/mjerenje`, `/kraj-sesije` i pomoćnik `skeptik`. **Pazi:** skeptik postaje dostupan tek u
   novoj sesiji (nova mapa se učitava pri pokretanju); ako se naredbe ne pojave, upiši
   `/reload-skills`.
5. **Handy** (diktiranje, v0.9.7) instaliran iz službenog izdanja, otisak datoteke provjeren.
6. **Usput nađeno:** u TML podacima za 2026. "datum turnira" je zapravo datum meča — popravljeno
   u učitavanju prije ijednog testa.

*Gdje:* izvještaji `revizije/2026-09-27/` (POVIJESNI_LAB, PRAGOVI, PROMPT_AUDIT, skripte
`lab_*.py`); vijesti `agent/player_news.py`, `agent/run_daily.py` (blok "VIJESTI PO IGRACU"),
`agent/predictor.py` (`context_version` 23); radni tijek `CLAUDE.md`, `.claude/skills/`,
`.claude/agents/skeptik.md`. Testovi: oba paketa prolaze, `test_cap_and_weather.py` odjeljak 49.

### 27.09.2026 11:09 — pregled besplatnih alata s tvog popisa (samo istraživanje)

Prošao sam sve linkove, skillove i repozitorije iz tvojih bilježaka (~70 stavki). U kodu i
modelu **ništa nije mijenjano** i ništa nije instalirano. Prijedlozi su gore u "ČEKA — ideje"
(povijesni laboratorij, vijesti po igraču, radni tijek u Claude Codeu, pregled prompta,
Sonnet 5).

Usput izmjereno u bazi (samo čitanje): od 28.08. **nijedna analiza nije pala** na JSON-u
(21 od 171 spašena drugim pokušajem), a keširanje prompta radi (41 od 51 analize od 08.09.).
Zato alati za "sigurni JSON" (Instructor, Outlines) ne trebaju. Analiza je malo (51 u 19
dana), pa API trošak pipelinea iznosi nekoliko dolara mjesečno — alati za štednju tokena
mogu uštedjeti samo na sesijama u Claude Codeu.

Važno iz bilježaka koje ne stoji: Sackmannovi `tennis_atp`/`tennis_wta` su obrisani s GitHuba;
`/voice` ne podržava hrvatski (za diktiranje: besplatni Handy); `/goal` služi za jednu sesiju,
nije cilj projekta; hook ne može prepisati tvoj prompt, samo dodati kontekst.

### 26.09.2026 21:27 — očišćen prompt analize (tvoje odobrenje)

Iz uputa modelu maknuto sve što je izmjereno kao krivo, a model je to i dalje koristio za
svoj broj: "povijest turnira je najjača varijabla", tri pravila o tie-breaku i servisu
(4, 13, 16), blok o kasnim rundama, blok koji je poticao autsajdere i sve rečenice o
"pragu 63%" (u kodu je 60). Analiza sada ima **pet odjeljaka** umjesto šest: Rating,
Serve/return, Forma, **Kontekst** (spojeni matchup i povijest turnira) i Own read.
Ništa novo nije dodano. Težine i pravilo o domaćem terenu nisu dirani.

**Čemu služi:** tekst koji čitaš uz pick više ne tvrdi netočnosti i dosljedan je broju;
manje razloga za odmak iznad tržišta; prompt kraći za četvrtinu. **Ne očekuj** da nas
ovo samo po sebi učini boljima od tržišta. **Pazi:** brojevi pouzdanosti će se malo
pomaknuti, pa prag 60 i kaznu 65-68 treba premjeriti nakon prvog turnira (stavka K1 gore).
Provjereno: oba testna paketa prolaze, jedan živi poziv modela vratio je pet odjeljaka.

Gdje: `agent/predictor.py` (komentar "CISCENJE PROMPTA" iznad predloška); nova era
`9696c4ee`.

### 26.09.2026 21:18 — tri pitanja (samo mjerenje, ništa u modelu nije mijenjano)

1. **Azijski mečevi na screenshotu: "danas" ili "sutra"?** Stavljaj točno kako grupira
   SuperSport. Kod sam pomakne datum po kratici dana uz sat ("ned 07:00" u subotnjoj listi =
   nedjelja 07:00). Provjereno na današnjoj rubrici: 10 od 10 kratica pročitano, a 4 nedjeljna
   meča spremljena pod subotu dobila su ispravan datum 27.09. i prognozu za taj dan.
   Uvjet: kratica dana mora se vidjeti na slici. Ako pokrećeš tiket u 17h, samo jednom na
   dan — drugi run istog dana stvara drugi tiket s istim datumom, a Dnevni listić prikaže
   samo jedan.
2. **Odjeljci analize (rating, servis, forma, matchup, povijest turnira, own read).**
   Pročitano svih 55 analiza od 06.09. do danas. Odjeljci nisu šest neovisnih varijabli:
   model u njima provodi pravila i zbraja kazne. 80% teksta ide na stvari koje ništa ne
   nose povrh cijene. Pravilo 16 poziva se u 65% analiza, povijest turnira kao argument u
   58%, a u 5 analiza s izrekom "najjača varijabla". U 18 analiza model je napisao da pick ne
   ide na tiket (misli da je prag 63%), a 12 ih je prošlo stvarni prag 60 — od 9 nogu na tri
   prava tiketa, 5 je model sam nazvao "coin-flip" ili "ispod praga". Prijedlog čišćenja je
   gore u "ČEKA — ideje".
   Međustanja kandidata: K8 drži smjer i izvan uzorka (odjeljak "povijest turnira" s
   podatkom −8,0pp, bez podatka −1,9pp, n=27); K9 je okrenuo predznak (vjerojatno pada);
   K2: protivnik-domaćin n=9, +0,7pp (prag je n=20).
3. **Težine hard modela (servis 23%, ELO 19%...).** Ostaju. To je samo popis na dnu prompta;
   model ih ni u jednoj od 55 analiza ne koristi u računu, a nijedna statistika igrača ne nosi
   ništa povrh cijene. Pravi pomaci su u kodu i čekaju kapiju (K11, K5/K10, K18, K15).

Gdje: skripte i izvoz baze samo lokalno u `.cache/pitanja2609/` (izvan gita).

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
