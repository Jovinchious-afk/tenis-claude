# Prelazak modela na TML 12 mj. — kriteriji zapisani PRIJE računanja

Zapisano **18.10.2026 16:25**. Korisnik je odobrio novu eru prompta i prelazak modela (Claude
analiza) sa RapidAPI servisa/povrata (praktički zamrznuta karijera) na TML za zadnjih 12 mjeseci,
uključujući jedan plaćeni probni poziv — **ali samo ako rezultati i provjere to opravdavaju**.
Cilj je bolja procjena igrača, a ne samo druge brojke.

**Što je viđeno prije ovog zapisa:** usporedba skala na igračima iz naših analiza (servis TML
+1,0pp r 0,83; povrat −4,5pp r 0,81), pokrivenost 99–100%, popis pravila u promptu koja koriste
servis/povrat. Ništa od prediktivne usporedbe (karijera naspram 12 mj.) nije računato.

## Kandidati (isti kod, različit izvor istih veličina)

- **(a) karijera:** sve TML mečeve igrača prije datuma meča (zamjena za RapidAPI, koji se poklapa s
  TML karijerom, servis r 0,94);
- **(b) 12 mj.:** TML 365 dana prije meča (prijedlog);
- **(c) mješavina:** 12 mj. povučeno prema karijeri, `(svpt12·v12 + 1500·vK) / (svpt12 + 1500)`.
  K = 1.500 servisnih poena (~20 mečeva) je odabran unaprijed, ne na podacima.

## A. Glavni kriterij — bolja procjena igrača (povijest, vremenski odvojeno)

LAB (ATP 2022 – 06.10.2026), samo podaci prije datuma meča. Vjerojatnost iz modela poena
(servis protiv povrata → gem → set → meč, isti kao Nose), BEZ cijene i bez ELO-a, da se vidi samo
vrijednost servisa/povrata. Polovice: **P1 = 2022–2023, P2 = 2024–2026 (provjera)**.

- **(b) PROLAZI** ako je log-gubitak na P2 ≤ (a) i točnost (pogođen pobjednik) na P2 ≥ (a) − 0,5pp.
- **(c)** se bira umjesto (b) SAMO ako je bolji od (b) za ≥ 0,001 log-gubitka na OBJE polovice.
- Ako je (a) bolji od (b) na P2: prelazak se **ne radi** (izvještaj korisniku).
- Opis (ne kriterij): r(razlika servis+povrat, ishod − poštena cijena) za svaki izvor; očekuje se
  ~0 za sve (tržište to zna), pa se neće tvrditi da prelazak "tuče kvotu".

## B. Isti mečevi (naše analize od 01.08.2026), vrijednosti u trenutku meča

TML 12 mj. računa se za datum svakog meča (bez kasnijih mečeva — inače curenje). Uspoređuje se:
- **točnost smjera:** koliko često strana koju servis+povrat favorizira pobijedi — RapidAPI naspram
  TML 12 mj. (opis, n ≈ 500, ±4pp);
- **okidanje pravila:** koliko često stara i nova verzija daju "punu / slabu / nikakvu" servisnu
  potvrdu i potvrdu povrata te koliko se oznaka promijeni.

## C. Pragovi u promptu — preslikavanje po kvantilima (unaprijed određen postupak)

Pravila su 17.08. postavljena kao kvantili ("< 2,5pp = medijan razlike", "≥ 5pp = gornjih ~17%"),
pa se na TML skalu prenose tako da okidaju **jednako često** na istim mečevima (B):

| pravilo | stara skala | preslikavanje |
|---|---|---|
| hard 2(b) razlika servisa: nikakva / slaba / puna | < 2,5 / 2,5–5 / ≥ 5pp | isti udjeli mečeva |
| hard 2(b) razlika povrata "broji se" | ≥ 2pp | isti udio mečeva |
| "elitni" hard igrač: hold | ≥ 88% (izvedeni hold) | isti percentil igrača, na IZMJERENOM holdu |
| "elitni" zemljaš: hold | ≥ 85% | isti percentil |
| zemlja: razlika holda "odlučujuća" | ≥ 5pp | isti udio mečeva |
| trava: "teško ga je breakati" | hold ≥ 85% | isti percentil |
| opis "70%+ servisnih poena" | 70% | isti percentil |

Hold postaje **izmjeren** (iz izgubljenih breakova), a ne izveden. U pravilima ostaje da su servis
i hold uglavnom ista informacija, ako je korelacija ≥ 0,8 (provjera na TML-u).

## D. Pričuva

Ako za igrača nema TML-a 12 mj. (< 300 + 300 poena): prikazuje se RapidAPI karijera **preračunata
na TML skalu** (izmjereni prosječni pomaci: servis +1,0pp, povrat −4,5pp) uz izričitu oznaku
"career estimate — no 12-month data". Udio u našim mečevima ~1%.

## E. Probni živi poziv (jedan, plaćeni)

Jedna stvarna analiza novim promptom (podaci jednog nedavnog meča iz snapshota + TML). **Prolazi**
ako: JSON se ispravno pročita, izlaz < 85% `_ANALYSIS_MAX_TOKENS`, analiza navodi brojke za zadnjih
12 mjeseci i ne miješa ih s karijerom. Ako ne prođe: popravak i ponovna provjera bez novog poziva,
a tek uz korisnika drugi poziv.

## F. Što se NE mijenja

Prag 63, struktura tiketa, težine, ELO, sve ostale ulaze. Stara verzija prompta sprema se u
`revizije/2026-10-18/prompt_prije_TML/` (i git). Nova era (`rules_hash`) reže korpus: K22 i ostala
mjerenja zadržavaju svoje definicije (RapidAPI polja ostaju u snapshotu pod istim imenima).

---

## REZULTATI I ODLUKA (18.10.2026 17:34) — prelazak se NE radi

Skripte: `skripte/c_tml_lab.py` (A), `skripte/c_tml_isti.py` (B, C, D), `skripte/c_tml_zivi_poziv.py`
(E); provjera kritičara `skripte/skeptik_tml/` (upareni test, po godinama, razine).

| A. LAB 12.315 mečeva (log-gubitak / točnost) | P1 2022–23 | P2 2024–26 |
|---|---|---|
| (a) karijera | 0,6554 / 60,3% | 0,6529 / 60,2% |
| (b) 12 mj. | 0,6524 / 60,9% | 0,6593 / 59,7% |
| (c) mješavina K = 1.500 | 0,6456 / 61,4% | 0,6501 / 60,1% |

- **Po slovu kriterija A: (b) PADA, a "ako je (a) bolji od (b) na P2: prelazak se ne radi" je
  okinulo.** Implementacija s (c) napravljena je po tumačenju (za (c) nije bio zapisan prag naspram
  (a)) — to je bila greška u postupku i zato nije uvedena.
- (c) − (a) na P2: +0,0028, interval [−0,0015, +0,0068] (klaster turnir) — u šumu. Po godinama
  +0,009 / +0,011 / +0,008 / +0,005 / **−0,005 (2026.)**.
- Uzrok (kritičar, naknadni rez, preživi Bonferroni): kad bar jedan igrač ima > 50% servisnih
  poena u 12 mj. iz Challengera/kvalifikacija (48,5% mečeva), (c) je lošiji od (a): −0,005
  (2022–24), **−0,020 (2025–26)**; inače bolji +0,013 do +0,028. Postotci protiv slabijih
  protivnika nisu usporedivi s onima s Toura; udio Challengera u TML-u raste (1,9 → 2,5 po meču
  glavnog ždrijeba, 2022. → 2026.).
- B (437 istih mečeva): 58,3% → 59,3% (+1,2 ± 2,7pp, šum); "bolja strana" se mijenja u 32% mečeva.
- C: preslikavanje pragova je ispravno (2,52 / 5,12 / 2,08pp; hold 87,7 / 85,4; zemlja 4,43pp).
- D: pričuva +0,91 / −4,13pp (izmjereno na istim mečevima; unaprijed je pisalo +1,0 / −4,5).
- E: probni poziv PROŠAO (JSON iz 1. pokušaja, 2.299 / 4.000 tokena, brojke 12 mj., nijedna stara).

**Odluka:** model ostaje na RapidAPI-ju (era bccf4742). Cijela implementacija (predložak, pravila,
pričuva, scouting, testovi) sačuvana je na lokalnoj grani `tml-era-881d89f8` (commit 54590fb).
Pouka za buduće kriterije: svaka varijanta treba vlastiti prag NASPRAM SADAŠNJEG STANJA, s
marginom, a ne samo naspram druge varijante.

## K25 — PRAG ZAPISAN PRIJE GLEDANJA (18.10.2026 17:34)

Hipoteza (naknadni nalaz kritičara, smjer +): servis/povrat iz TML-a **samo glavnog ždrijeba**,
12 mj. povučeno prema karijeri glavnog ždrijeba (K = 1.500), bolje procjenjuje igrače od karijere
svih razina (≈ RapidAPI, sadašnje stanje). Na viđenim podacima 2022–26 (isti mečevi, n = 11.087):
+0,013 do +0,019 svake godine, u pojasu favorita 0,50–0,80 +0,009 do +0,012 — ali to je jedan od
~40 rezova, pa ne smije u odluku bez potvrde.

- **Test A (odmah, besplatno, godine koje nitko nije gledao):** TML glavni ždrijeb **2010–2019**,
  ishodi iz TML-a (bez kvota), model poena kao u `c_tml_lab.py`, samo mečevi prije datuma meča.
  Mješavina glavnog ždrijeba naspram karijere glavnog ždrijeba. **PROLAZI:** log-gubitak bolji za
  ≥ 0,005 u obje polovice (2010–14 i 2015–19) i bolji u ≥ 8 od 10 godina. **PADA:** ≤ 0 u bilo
  kojoj polovici. Inače nejasno (izvještaj). Snaga: ~25.000 mečeva → SE ≈ 0,0012.
- **Test B (budući mečevi od 19.10.2026, n ≥ 700 ATP mečeva glavnog ždrijeba, ~prosinac):** cijeli
  postupak — glavni ždrijeb kad oba igrača imaju ≥ 300 + 300 poena u karijeri glavnog ždrijeba,
  inače karijera svih razina — naspram karijere svih razina. **PROLAZI:** bolji za ≥ 0,005, 95%
  interval iznad nule (klaster turnir), isti predznak u obje polovice po datumu. **PADA:** ≤ 0.
  Snaga: n = 700 → SE ≈ 0,007 (vidi ~0,014; ako je stvarno 0,01, treba ~1.500).
- Tek kad prođu A i B: prijedlog korisniku za novu eru (pragovi po kvantilima kao u C, pričuva,
  jedan plaćeni živi poziv). Ništa od ovoga ne tvrdi da model tuče cijenu (cijena 0,5888 na P2).
