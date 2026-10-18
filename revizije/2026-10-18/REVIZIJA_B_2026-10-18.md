# Revizija 18.10.2026, drugi dio — Šangaj post-mortem, Nose u sjeni, provedene izmjene

Zapisano 18.10.2026 12:57. Nastavak jutarnjeg izvještaja (`REVIZIJA_2026-10-18.md`, 09:07–10:14),
koji se ovdje ne ponavlja nego citira. Pragovi za sve nove testove zapisani su PRIJE računanja:
`PRAGOVI_B_2026-10-18.md` (12:20; dva naknadna dodatka, 12:22 i 12:52, jasno označena).
Tvoje odluke: **1a** (Nose u sjeni), **2a** (scouting samo uz snažan razlog), **3a** (bonus za
konsenzus van). Kritičar (skeptik): točka 15.

Skripte (sve samo čitaju, osim `b_scouting.py --primijeni`): `skripte/b_*.py`. Dump baze:
`.cache/rev_2026-10-18b/` (12:13, identičan jutarnjem). Ispisi: `.cache/rev_2026-10-18b/out_b_*.txt`.

---

## 0. Kratko

1. **Šangaj nije pokazao kvar modela, nego tri stvari.** Pickovi su bili na razini tržišta
   (72, −1,4pp; po poenima točno očekivano). Tiketi gube zbog matematike. Skupe su bile noge
   1,65–1,85 kojima se dosezala kvota 4.
2. **Najčešće greške procjene nisu bile u broju, nego u obrazloženju:** isti podatak brojan
   dvaput (ELO i omjer na podlozi kao "dvije neovisne potvrde"; asovi povrh servisa), oslanjanje
   na izmjereno-mrtve signale (forma × kvaliteta, vjetar, stil iz scoutinga, "iskustvo") i
   **zastarjeli ili napuhani ulazi** (Challenger rezultati u omjeru na podlozi, RapidAPI povrat
   +5,7pp, stari scouting).
3. **Težine v18 nisu opravdane, ali ni bilo koje druge.** v18 je nastala iz automatske petlje
   nad 10 poraza i 10 pobjeda, a model težine u tekstu ne koristi. Ostaju (točka 3).
4. **Statistika s aktualnog turnira** ni u tri pristupa ne dodaje ništa povrh cijene.
5. **Kombinacije:** od tvojih 12 testirano je 11 (jedna se ne može: winneri postoje samo za
   Slamove). **Nijedna ne prolazi.** B4b ("ELO prednost potvrđena servisom/povratom") izgledao je
   kao trag (+1,6pp). Kritičar je pokazao da su to gotovo sve favoriti: uz kontrolu pojasa kvote
   ostaje +0,4pp, dakle ništa.
6. **"ATP wins this season gap"** se pojavljivao zbog zastarjelog retka u analizi gubitka.
   **Popravljeno.** Vrijednosti nema (+0,0pp na 11.139 mečeva).
7. **SIGNAL CONFIRMED** je značio samo "vidjelo se prije meča i u istim mečevima ide uz
   poraze". **Zamijenjen s četiri odvojena pojma**, a izmjenu smije predložiti samo jedan od njih.
8. **Nose postoji i radi u sjeni** (4 procjene + NO PICK, prvo vlastita procjena, tek onda
   cijena). Povijest kaže da **zasad ne tuče cijenu**:
   - kad se razilazi s cijenom, u pravu je cijena (−1,5pp i uz kontrolu pojasa);
   - njegov NO PICK na favoritu daje +1,3pp, dakle bez potpore za minu.

   To je mjerilo koje mora prebaciti na budućim mečevima (kapija K24, sada zamrznuta i s
   kontrolom pojasa), ne presuda da nema potencijala.
9. **Prag 63, 3–6 noga, 4–50 i runde: bez promjene.** Matematika kaže da je trojac najmanje
   loš, ali prijedlog po zapisanom kriteriju ne prolazi (točka 9).
10. **Provedeno:**
    - bonus za konsenzus ugašen (povratak = jedna konstanta);
    - analiza gubitka popravljena;
    - Nose u sjeni;
    - sažetak dana bez tiketa kaže pravi razlog;
    - nova mjerenja K22, K24 i L4 (K24 nakon kritičara: zamrznuta presuda, kontrola pojasa);
    - scouting: 1 tekstualna izmjena (Atmane), 66 rangova i listovi s dokazima.
    - **Usput nađeno:** servis/povrat koji model vidi nije sezonski nego **karijerni** (RapidAPI,
      zamrznut), a povrat je napuhan ~4,7pp. Prijedlog je u točki 10, nije proveden.
11. Oba testna paketa prolaze (892 i 271 provjera). Commit je lokalni, bez pusha (točka 14).

---

## 1. Tiketi: 8 naspram 10 — razriješeno iz izvora

Izvor: Supabase `tickets` + `ticket_matches` (dump 12:13).

| skupina | tiketi | datumi |
|---|---|---|
| svi pravi tiketi od 27.09. | **10** (1 dobitan) | 27.09., 29.09., 30.09., 01.10., 02.10., 03.10., 06.10., 09.10., 10.10., 12.10. |
| od toga noge SAMO s Tokija, Pekinga i Šangaja | **8** (svi izgubljeni) | 30.09. – 12.10. |
| od toga s barem jednom nogom iz Šangaja | 4 | 06.10., 09.10., 10.10., 12.10. |
| dani "samo analiza" (bez uloga) | 7 | 04.10., 05.10., 07.10., 11.10., 15.10., 16.10., 17.10. |

- Tvojih 8 su tiketi sastavljeni isključivo od ta tri turnira.
- Tiket od 27.09. (jedini dobitan) bio je cijeli Chengdu/Hangzhou.
- Tiket od 29.09. miješa finale Chengdua s Pekingom.
- U analizi su svih 10, s oznakom podskupa.
- Svaki datum ima jedan tiket.
- Tri meča stoje na dva tiketa (Cobolli–Safiullin, Rublev–Safiullin, Shapovalov–Tabilo): za
  noge se broje jednom, za tikete dvaput.
- **Ograničenje:** dnevni run kod ponovnog pokretanja briše tiket istog dana, pa obrisani tiketi
  ne postoje ni u bazi.

## 2. Šangaj i tiketi — što smo stvarno naučili

**Pickovi (iz jutarnjeg mjerenja, potvrđeno istim dumpom):** Šangaj 72 picka, pogođeno 63,9%
uz cijenu 65,3% → **−1,4pp ±10,7**. Po poenima: 41 zaslužena pobjeda, 4 sretne, 13 poraza u
kojima smo nadigrani, 9 tijesnih (tie-breakovi, odlučujući set). Ostatak poena +0,4pp ±1,2:
igrali smo točno onako kako je cijena očekivala.

| gdje smo bili loši (Šangaj) | n | edge |
|---|---|---|
| kvota 1,43–1,65 | 22 | −3,9pp |
| kvota 1,65–1,85 | 12 | −5,0pp |
| kvota 1,85–2,10 | 6 | −16,8pp |
| R32 | 16 | −12,2pp |
| polufinala | 2 | 0 od 2 (Medvedev, Zverev) |

| gdje smo bili dobri | n | edge |
|---|---|---|
| kvota 1,20–1,35 | 11 | +8,0pp |
| R64 | 17 | +12,0pp |
| dvorana/krov | 10 | +12,3pp |

Svi intervali su ±20–60pp. Za Šangaj pojedinačno ovo je **opis, ne obrazac**.

**Tiketi (svih 10 od 27.09.):**
- 1 dobitan, očekivano 1,9.
- 13 izgubljenih noga (12 mečeva), od toga **10 na kvoti 1,50–1,90**.
- 6 tiketa palo je na jednoj jedinoj nozi.
- Noge su bile pošteno cijenjene: 63,9% naspram 64,2%.

Mehanizam:
- uz prag 63 ponudu čine kratki favoriti;
- do ukupne kvote 4,0 dolazi se jednom ili dvije noge 1,65–1,85 s pouzdanošću točno 63–64;
- to su gotovo novčići (55–58%).

**AI recenzent ("X carries the most risk") na ovih 10 tiketa:**
- označena noga izgubila je 6 od 10, ostale 7 od 26;
- izgleda dobro, ali na svih 49 označenih noga to je novčić (jutros: 25 od 49);
- ideja je nastala gledajući upravo ove tikete;
- prati se od 19.10. (L4).

**Najčešće i najskuplje pogreške:**

| # | pogreška | primjer | koliko | cijena greške |
|---|---|---|---|---|
| 1 | struktura: 3–6 noga uz maržu po nozi | svi tiketi | 66 tiketa: 5 dobitnih, oček. 6,9 | očekivani povrat tiketa −12% (3 noge) do −23% (6 noga) i bez greške modela |
| 2 | noga-novčić za dosezanje kvote 4 | Cobolli 1,80/1,90, Nakashima 1,70, Tien 1,75, Tiafoe 1,75 | 10 od 13 izgubljenih noga | NOVO 1,65–1,85: −7,3pp (n=27) |
| 3 | dvostruko brojanje u obrazloženju | Zverev: ELO + omjer na hardu kao "dvije neovisne kategorije" | 2 od 2 slučaja niže | broj nije bio iznad tržišta (72 naspram 77) |
| 4 | napuhani ili zastarjeli ulaz | Jodarov omjer s Challengerima okinuo pravilo 15; ADF "slab na brzom hardu" | Jodar, ADF, Đoković (RapidAPI) | 0 nogu na tiketu, ali krivo obrazloženje |
| 5 | pouzdanost iznad tržišta "bez informacije koju tržište nema" | Nakashima, Tien, Tiafoe, Merida, Royer… | 8 analiza gubitaka | odmak od cijene ne nosi ništa (r = −0,07) |

**Suprotni primjeri:**
- Medvedev @1,13 (72%) i Lehečka @1,33 (68%) prošli su istom logikom;
- kratki favoriti 1,00–1,35 u NOVO +6,5 do +7,8pp (n=44).

Dakle obrazloženje "ELO + servis" nije krivo samo po sebi. Krivo je kad dvije mjere iste
kvalitete glume dvije potvrde.

## 3. Dva slučaja iz Šangaja (samo podaci zapisani prije meča)

### A. Jodar – Medvedev (SF, 17.10., noć)

**Polazni podaci:**
- Medvedev @1,55, pouzdanost 60, devigirana cijena 64,8%.
- Analiza je samo analiza: pouzdanost 60 je ispod praga, a 17.10. je ionako bio dan bez tiketa.

| signal iz analize | provjera u snapshotu | relevantan? |
|---|---|---|
| ELO na hardu gotovo jednak (1936 : 1920) | točno (−16,4) | da — ali **ukupni ELO je za Jodara (+44,8)**, što analiza ne spominje |
| Jodarovih 71,6% na otvorenom hardu → pravilo 15 (−4pp) | točno prepisano, ali **zbroj uključuje Challengere** (Jodar je prije godinu dana bio 903., osvojio je 3 Challengera) | pravilo 15 je izmjereno kao NEJASNO (n=52, −3,5pp ±12,8); ovdje je okinulo na napuhanom podatku |
| servis 65,5 : 63,7 (ispod praga 2,5pp), povrat 42,7 : 43,8 | točno | da — i kaže "izjednačeno" |
| Medvedevljevi asovi 10,2 : 5,3 na 100 poena | točno | **dvostruko brojanje**: asovi su dio servisnih poena, a servisni jaz je već ocijenjen kao premalen |
| forma 9/10 : 7/10 uz sličnu kvalitetu protivnika | točno | forma × kvaliteta je pala izvan uzorka (r = −0,02) |
| vjetar 19 km/h, "flat hitter" | točno | vrijeme je izmjereno kao nula; opisi stila promašili su na Šangaju |
| 44 finala naspram 2 | iz konteksta | "iskustvo u velikim mečevima" (K16) zatvoreno |

**Je li odluka bila logična?**
- Broj 60 bio je **ispod tržišta** (64,8%), dakle oprezan. Bez pravila 15 bio bi 64.
- Ono što je stvarno nosilo informaciju (ELO i servis/povrat) govorilo je "otprilike 50:50 do
  60:40".
- Ostalo je bila priča bez izmjerene vrijednosti.
- Nose (izračunat danas na istom snapshotu, retrospektivno): vlastita procjena Medvedev 49% →
  **IZBJEGAVAJ (NO PICK)**, −15,7pp od cijene.
- Na povijesti je takvo razilaženje s cijenom bilo krivo (točka 8), pa ni Nose ovdje nije dokaz.
- **Presuda:** broj je bio pošten, obrazloženje djelomično šum. Poraz je unutar očekivanog (35%
  događaj). Novac nije izgubljen.

### B. Zverev – Davidovich Fokina (SF, 17.10., dan)

**Polazni podaci:** Zverev @1,24, pouzdanost 72, cijena 76,8%. Analiza je iz dana bez tiketa
(16.10.).

| signal | provjera | relevantan? |
|---|---|---|
| ELO na hardu +179, rang 2 : 26, omjer na hardu 75,5% : 60,2% | točno | ELO da; **omjer na podlozi je isti podatak** (ELO je nastao iz istih rezultata) |
| servis 66,8 : 61,8 (puna potvrda) | točno | da — ali servis, ELO i omjer mjere istu kvalitetu, a pravilo 2 ("dvije neovisne kategorije → 70+") ih broji kao neovisne |
| na turniru Zverev 76,1% servisa | točno; ali **spašeni BP na turniru 44,4%** (ADF 70,2%) | turnirska statistika ne nosi ništa (0/18 i danas TA2/TA3) |
| "ADF slabiji na brzom/dvoranskom hardu" (scouting, Med) | tekst točno citiran | **zastario na samom turniru**: ADF je u Šangaju dobio 4 meča, među njima i naše pickove. Opis stila nije nosio informaciju |
| ADF realizacija BP na turniru 50,6%, vjetar 17 km/h (upozorenja) | točno | oboje izmjereno kao šum, pa je ispravno što nisu prevagnuli |

**Je li odluka bila logična?**
- Broj 72 bio je **ispod tržišta** (76,8%).
- Prednosti favorita nisu bile precijenjene u broju, nego u priči: tri mjere iste kvalitete
  predstavljene su kao tri potvrde.
- Upozorenja su bila slaba, i to s pravom.
- Nose (retrospektivno): 73%, **UKLJUČI**, u skladu s cijenom. Ni on ne bi ništa označio.
- **Presuda:** dobra odluka, loš ishod (23% događaj). Jedina prava lekcija je zastarjeli scouting.

## 4. Težine v18 — što su i jesu li opravdane

**Kako rade (iz koda):** `predictor.py` u prompt upisuje 7 postotaka (zbroj 100) kao tekst
"MODEL WEIGHTS". Nijedna linija koda ih ne množi ni ne normalizira. To je uputa modelu kako da
odvagne svoju priču. Revizija 26.09. našla je da ih model ne spominje ni u jednoj od 55 analiza.
Mijenjaju dakle samo koliko visoko model stavi pouzdanost, a ona povrh cijene ne nosi ništa.
Stranu picka praktički ne mijenjaju: pick je tržišni favorit u 92,9% (v14) i 90,1% (v18).

**Što je v18 stvarno promijenila** (baza `model_weights`, v14 → v18):

| faktor | v14 (18.07.) | v18 (04.08.) | aplikacija kaže |
|---|---|---|---|
| ELO / rang | 22 | **19 (−3)** | −1 |
| servis / povrat | 22 | 23 (+1) | +1 |
| podloga / stil | 17 | 18 (+1) | +1 |
| forma | 16 | 17 (+1) | — |
| umor / ozljede | 13 | 12 (−1) | −1 |
| put na turniru | 6 | 7 (+1) | +1 |
| H2H / kontekst | 4 | 4 | — |

**Podrijetlo:** "Auto-feedback na 10 analiza" — automatska petlja koja je iz 10 poraza i 10
pobjeda, uz statistiku poslije meča, zaključila da je ELO "precijenjen". Upravo je za taj postupak
26.08. izmjereno da okrivljuje krive faktore: ELO je jedini koji stvarno razdvaja pobjede od
poraza, samo što ga cijena već zna. Isti postupak dao je i clay v17 (ELO 11%), koji čeka popravak.
Petlja je ugašena 05.08. **Podloga nije bila reprezentativna ni neovisna**.

**Je li v18 pomogla?** v18 − v14 uz kontrolu pojasa kvote: **+0,7pp ±18,7** (v14 ima samo 28
analiza). Isti dan su promijenjena i pravila, pa se dvoje ne može razdvojiti. Nema dokaza ni za
ni protiv.

**Dvostruko brojanje:** ELO, rang, omjer na podlozi, forma i kvaliteta protivnika mjere istu
stvar (kvalitetu igrača). Pravilo 2 ("dvije neovisne kategorije → 70%+") to ne zna (slučaj B).

**Odluka:** težine se **ne mijenjaju**. Bilo koji novi skup bio bi jednako nedokazan, a učinak
je samo na pouzdanost.

**Prijedlog za sljedeću eru prompta (nije sada):** blok težina maknuti ili vratiti ELO na 22, i
u pravilu 2 dopisati da ELO, rang i omjer na podlozi nisu neovisne potvrde.

## 5. Statistika s aktualnog turnira — tri pristupa

| pristup | test | n | edge | P1 / P2 | presuda |
|---|---|---|---|---|---|
| 1. prosjek svih ranijih mečeva na turniru (jutros) | 9 statistika × dubina 2 i 3+ | 622–2.782 | −2,0 do +2,4pp | — | 0/18 PADA |
| 2. zadnja 3 meča na turniru (oba ≥ 3) | TA2 | 933 | −0,5pp [−3,3, +2,4] | +0,0 / −0,8 | PADA |
| 3. turnir + 365 dana na istoj podlozi (k = 10, "povratak prema prosjeku") | TA3 | 1.334 | +1,7pp [−0,6, +4,0] | +4,0 / +0,2 | PADA |

- Pristup 2 je gotovo isti redak kao pristup 1 na dubini 3+, kako je unaprijed i zapisano.
- Pristup 3 je u P1 izgledao dobro, a u P2 je nestao.
- **Ne dodaje ništa povrh cijene.** U promptu ostaje samo opis.
- Naši snapshoti nose servis, asove i BP s turnira, ali ne povrat ni udio poena. Winneri i
  neiznuđene greške postoje samo za Slamove.

## 6. Kombinacije varijabli (tvoj popis od 12)

| # | tvoja kombinacija | test | n | edge | presuda |
|---|---|---|---|---|---|
| 1 | hold vs protivnikov povrat | E2 (jutros) | 798 | +1,3pp | PADA |
| 2 | hold vs protivnikov break | E2 / E9 | — | — | PADA |
| 3 | 1. servis vs povrat na 1. servis | **B1** | 4.649 | +0,9pp [−0,4, +2,1] | PADA |
| 4 | 2. servis vs povrat na 2. servis | E1, E9 (jutros) | 1.385 / 198 | +0,7 / −1,6pp | PADA |
| 5 | asovi po gemu vs povrat i podloga (mina) | **B2** | 1.025 | −1,3pp [−4,0, +1,4] | PADA |
| 6 | spašeni BP vs suočeni i realizacija | **B3** | 345 | +2,7pp (obrnuto) | PADA |
| 7 | winneri / neiznuđene greške | — | — | samo Grand Slam | NE MOŽE |
| 8 | forma na turniru + zadnjih 10 + protivnici | E10, E11 (jutros) | 13 / 143 | −14,5 / −3,0pp | PREMALO / PADA |
| 9 | ATP pobjede u sezoni + ELO | E3, E4 (jutros), K15 | 3.388 / 465 | −0,9 / +2,2pp | PADA |
| 10 | ELO NIJE potvrđen servisom/povratom (mina) | **B4a** | 983 | −1,4pp [−4,3, +1,5]; P1 −4,3 / P2 +0,6 | PADA |
| 10 | ELO potvrđen servisom/povratom i protivnicima | **B4b** | 3.424 | +1,6pp [+0,2, +2,9] sirovo; **uz kontrolu pojasa +0,4pp [−0,9, +1,7]** (98% su favoriti) | **PADA** (uz pojas) |
| 11 | forma + umor + trajanje + setovi | E6, E12 (jutros) | 624 / 913 | +0,9 / −0,8pp | PADA |
| 12 | dob + umor + servis/povrat | E6, E7, E8 (jutros) | 464–752 | −2,1 do +0,9pp | PADA |

- Holm na 10 današnjih testova: najmanja korigirana P = 0,01 (N7, ali u obrnutom smjeru), za B4b
  0,19.
- Na istom povijesnom uzorku to je sada **79 testova**.
- **Najperspektivnije: nijedna.** Prvotno sam B4b nazvao tragom u smjeru K22. Kritičar je
  pokazao zašto to ne vrijedi:
  - 98% odabranih strana su favoriti (prosječna cijena 0,76), a slučajni uzorak iste strukture
    cijena daje +1,1pp;
  - uz kontrolu pojasa ostaje +0,4pp [−0,9, +1,7];
  - povijest ne podupire ni K22: r(ELO jaz, ostatak) = +0,00 na 12.320 mečeva, servis+povrat
    +0,02;
  - K22 (+0,19 na 169 pickova) ima rez "od 14.09." odabran naknadno.

  K22 se i dalje mjeri na 150 novih hard pickova, ali bez povijesne podrške.

## 7. "ATP wins this season gap" i oznake SIGNAL

**Gdje se računa:**
- `run_daily` → `p*_ctx.season.tour_w` (ATP pobjede u tekućoj godini, prije meča, RapidAPI profil);
- snapshot ga sprema;
- prompt predikcije ga ne koristi za odluku.

**Zašto se ponavljao:** analiza gubitka dobivala je blok baznih stopa s retkom "ATP wins this
season … 0,042 ← the only one". Ta brojka je iz istih 451 meča (unutar uzorka). Dan kasnije
varijabla je zatvorena (povijest +0,0pp na 11.139; naši novi mečevi r = +0,03). Zato je 11 od 30
analiza spominjalo ATP pobjede, 5 ih je predložilo kao izmjenu, a 2 su ih proglasile CONFIRMED,
ne znajući ni smjer. **Popravljeno:** redak sada kaže ZATVORENO, s brojkama. Povijesni zapisi
nisu dirani.

**Što je CONFIRMED stvarno značio:** "vidjelo se prije meča I bazne stope (isti mečevi) razdvajaju
pobjede od poraza". Dakle povezanost unutar uzorka, ne dokazana prediktivna vrijednost. Od 27.09.
dodijeljena je 6 puta, nijednom potvrđeno:
- 3× R16/QF — opovrgnuto;
- 1× pojas 1,43–1,60 — neodlučeno;
- 2× ATP pobjede — zatvoreno.

**Nova logika** (svaki faktor dobiva četiri odvojene oznake):

| pojam | oznake |
|---|---|
| (a) prisutnost prije meča | VISIBLE BEFORE THE MATCH / POST-MATCH ONLY |
| (b) naš zapis u istom uzorku | SEPARATES / DOES NOT SEPARATE / POINTS THE OTHER WAY / NOT MEASURED |
| (c) prediktivna vrijednost (kapija izvan uzorka) | GATE PASSED / CANDIDATE, UNCONFIRMED / FAILED OR CLOSED / NEVER TESTED |
| (d) ovaj meč | PRESENT / ABSENT IN THIS MATCH |

- Izmjenu modela smije predložiti **samo (c) = GATE PASSED**. Danas ga nema nijedan faktor.
- Analiza smije dodati jedan redak "Worth measuring" za vidljiv, nikad testiran faktor. To je
  kandidat za registar, ne izmjena.
- Na 30 starih analiza nova pravila dala bi 0 prijedloga umjesto 5. To je ocjena po pravilu, bez
  ponovnog poziva modela, jer bi poziv bio plaćen.

## 8. Nose — što je napravljeno i što zasad zna

**Što je (agent/nose.py, `nose-v1`):** za svaki analizirani meč četiri odvojene procjene.

| procjena | sadržaj |
|---|---|
| **Pick Quality** | vlastita vjerojatnost = 0,80 × ELO (pola na podlozi, pola ukupni) + 0,20 × model poena (servis protiv protivnikova povrata → gem → set → meč), uz pouzdanost visoka / srednja / niska |
| **Mine Risk** | M1 ELO prednost nepotvrđena servisom/povratom; M2 protivnikov povrat napada pickov 2. servis; M3 turnir proturječi formi; M4 umor; M5 rezultati bolji od izvedbe |
| **Upset Value** | U1 protivnik vodi u servisu+povratu; U2 protivnik na turniru iznad svoje razine; U3 jači 1. servis na brzom terenu; U4 forma protiv jačih |
| **Ticket Suitability** | UKLJUČI / UZ UPOZORENJE / **IZBJEGAVAJ = NO PICK** (vlastita procjena < 50% ili 2+ mine), s razlogom |

**Neovisnost:**
- Faza A čita samo teniska polja.
- Ulaz s ijednim tržišnim poljem se odbija.
- Rezultat se zamrzne (SHA-256) i tek onda faza B uspoređuje s devigiranom cijenom.
- Test provjerava da promjena kvote, konsenzusa ili Intuicije ne mijenja fazu A.

**U sjeni:**
- računa se nakon slaganja tiketa;
- upisuje se samo u snapshot;
- na Dnevnom listiću stoji uz oznaku "u sjeni, nepotvrđeno" i razinu dokaza uz svaki "miris".

**Što zasad zna — povijest, vremenski odvojeno.** Težina je procijenjena na 2022–23, a
provjera je na 2024–26:

| test | n | edge | polovice | presuda |
|---|---|---|---|---|
| N5 favorit s 2+ mine | 325 | −1,0pp [−6,2, +4,2] | −4,6 / +1,3 | PADA |
| N6 autsajder s 2+ razloga | 295 | −2,6pp [−8,1, +3,0] | +0,8 / −6,2 | PADA |
| N7 strana kojoj Nose daje 5pp+ više od cijene | 6.358 | **−1,9pp [−3,0, −0,8]** | −1,5 / **−2,3** | PADA (obrnuto) |

Dodatno, na 2024–26:
- log-gubitak: Nose 0,609, cijena 0,588;
- isti favorit kao cijena u 87,7% mečeva.

**Naknadno, na kritičarev zahtjev** (`b_lab_naknadno.py`, nije dio zapisane obitelji testova):

| provjera | n | sirovo | uz kontrolu pojasa cijene | P1 / P2 |
|---|---|---|---|---|
| točno pravilo IZBJEGAVAJ na favoritu (vlastita procjena < 50% ili 2+ mine) | 1.824 | +1,1pp [−1,2, +3,3] | **+1,3pp [−1,0, +3,5]** | −1,7 / +3,5 |
| N7 uz kontrolu pojasa | 6.358 | −1,9pp | **−1,5pp [−2,6, −0,4]** | −1,0 / −1,9 |

Nijedan dio Noseovog NO PICK-a nema povijesnu potporu: takvi favoriti prolaze kako cijena kaže
ili malo bolje. N7 ostaje obrnut i uz kontrolu, a 76% strana koje Nose voli više od cijene su
autsajderi. Kritičar je provjerio i ELO strogo po datumu, ELO samo iz glavnog ždrijeba i samo
Pinnacle cijenu: −1,5 do −2,6pp. Pinnacle u podacima staje 13.01.2026, pa je 29% cijena u P2
prosjek kladionica.

**Što to znači:**
- Vlastito čitanje iz ELO-a i sezonskog servisa/povrata razumno je mjerilo snage (88% isti
  favorit), ali je **lošije od tržišta**.
- **Kad se s tržištem ne slaže, tržište je u pravu.**
- To nije dokaz da Nose nema potencijala. To je granica koju mora prebaciti. Da bi je prebacio,
  treba informaciju koju cijena nema, a ELO i sezonski servis to nisu.
- Kandidati za takvu informaciju:
  - vijesti o ozljedi (K13);
  - bolji ulazi (TML umjesto RapidAPI povrata, točka 10);
  - stvarni teret na turniru.

**Na našim analizama** (razvojni uzorak, 428 s procjenom):

| skupina | n | edge |
|---|---|---|
| UKLJUČI | 303 | +0,3pp ±5,1 |
| UZ UPOZORENJE | 75 | +1,5pp ±10,9 |
| IZBJEGAVAJ | 50 | **−8,8pp ±13,5** (STARO −10,6, NOVO −5,2) |

Interval prelazi nulu, pa po zapisanom pravilu to **nije ni "obećavajuće"**. Prvotno sam
napisao "smjer hipoteze". Kritičar je s pravom upozorio da to proturječi povijesti, gdje isto
pravilo daje +1,3pp:
- 44 od 50 su IZBJEGAVAJ zbog vlastite procjene < 50%, samo 6 zbog 2+ mine;
- to su slabiji favoriti (cijena 0,57 naspram 0,66);
- uz kontrolu pojasa razlika prema ostalim pickovima je −6,9pp, bootstrap [−21,9, +8,3].

Naših −8,8pp najvjerojatnije su sastav pojasa i šum.

**Posljedica da je Nose veto (kritičar):** IZBJEGAVAJ bi pogodio 6 od 13 stvarnih tiketa, i to
noge 0,47–0,58 koje dosežu kvotu 4,0. Pojas ≥ 0,70 gotovo je netaknut (4 od 50). Gubila bi se
učestalost tiketa, ne loše noge. Retrospektivno na 43 noge izgleda "savršeno" (UKLJUČI +13pp,
ostalo −18 i −21pp, SE 9–20pp), a upravo to je zamka.

**Kapija K24** (DECISION_INPUTS, od prvog runa s Noseom):

| provjera | probir | odluka | procjena trajanja |
|---|---|---|---|
| G1 mina | n=60: edge ≥ +3pp → gasi se | n=150: ≤ −5pp, interval < 0, obje polovice < 0 | ~6 IZBJEGAVAJ tjedno → probir krajem prosinca, odluka ~proljeće 2027. |
| G2 vrijednost na protivniku | zrcalno | zrcalno | ~5 tjedana do probira |
| G3 vlastita procjena | — | r ≥ +0,10 uz n=300 | ~2 mjeseca (uz prosinačku stanku dulje) |

Uz n=150 vidi se tek učinak ~10pp. **Nijedna definicija se ne mijenja dok mjerenje traje**;
izmjena znači nose-v2 i kapija kreće od nule.

**Kapija popravljena nakon kritičara** (PRAGOVI_B, NAKNADNO 15:05, prije ijednog podatka K24;
definicije Nosea nisu dirane):
1. **Presuda se zamrzava:** probir na prvih 60 označenih redaka po datumu, odluka na prvih 150
   (G3: 300). Ponovno gledanje digne lažnu potvrdu s 2,4% na 7,5%.
2. **Kontrola pojasa cijene:** G1 traži i razliku ≤ −3pp naspram ostalih pickova u istom pojasu.
   G2 zrcalno.
3. G1 i G2 dijele ~76% redaka, pa se zajedno broje kao **jedan** dokaz.

**Iskreno očekivanje:**
- snaga za stvarnih −5pp je ~22%;
- uz povijesna očekivanja šansa prolaza je ~1% po kapiji.

K24 je dakle pošten test koji Nose v1 vjerojatno ne prolazi. Vrijednost mu je u tome da gradi
naš budući uzorak i da se zna zašto je pao, ako padne.

## 9. Prag 63, broj nogu, ukupna kvota, runde

**Kalibracija:** pouzdanost povrh cijene ne nosi ništa (r = −0,07, n=501). Po razredima od
27.09.:

| pouzdanost | n | edge |
|---|---|---|
| 60–63 | 66 | −5,0pp |
| 63–65 | 21 | +3,0pp |
| 68+ | 30 | +9,5pp |

U Šangaju je 68+ bilo −4,0pp (n=14). Predznaci se okreću: to je šum.

**Matematika tiketa** (noge pošteno cijenjene, marža 4,5% po nozi):

| ukupna kvota | 3 noge | 4 noge | 5 noga | 6 noga |
|---|---|---|---|---|
| 4,0 — šansa | 21,9% | 21,0% | 20,1% | 19,2% |
| 5,0 — šansa | 17,5% | 16,8% | 16,0% | 15,4% |
| 8,0 — šansa | 11,0% | 10,5% | 10,0% | 9,6% |
| **očekivani povrat (bilo koja kvota)** | **−12,4%** | −16,1% | −19,8% | −23,2% |

**Što to znači:**
- Očekivani povrat ovisi samo o broju noga.
- Ukupna kvota mijenja samo koliko često tiket prođe.
- Trojac je najmanje loš, ali i on gubi ~12% po tiketu dok nemamo prednost po nozi.

**Simulacija na istim mečevima od 08.09.** (pravi kod odabira, bez AI recenzenta):

| varijanta | dana s tiketom | prosj. nogu | oček. šansa | oček. povrat |
|---|---|---|---|---|
| V0 kako je bilo (prag po datumu: 60 do 04.10., zatim 63; bonus 4) | 9 | 3,8 | 18,0% | −18,4% |
| V1 isto, bez bonusa za konsenzus (provedeno) | 9 | 3,4 | 18,4% | −17,1% |
| prag 60 cijelo vrijeme | 10 | 3,4 | 18,6% | −16,5% |
| prag 63 cijelo vrijeme (današnje pravilo) | 4 | 3,8 | 18,3% | −18,0% |
| prag 66 cijelo vrijeme | 0 | — | — | — |
| samo 3 noge, kvota 4–6 (prag po datumu) | 5 | 3,0 | 19,8% | −14,5% |
| 4–6 noga (prag po datumu) | 9 | 4,0 | 16,6% | −19,2% |
| kvota 5–8 (prag po datumu) | 7 | 3,7 | 14,3% | −18,4% |

**Ograda:**
- V0 reproducira stvarni tiket 4 od 13 puta točno i 5 od 13 djelomično.
- U prvoj verziji bilo je 2 od 13. Kritičar je našao glavni razlog: simulacija je koristila prag
  63, a do 04.10. je vrijedio 60 (18 od 46 nogu pravih tiketa imalo je pouzdanost ispod 63).
- Ostatak su prepisani retci (7 od 46 noga, uvijek naniže) i AI recenzent koji se ne poziva.
- Brojke su okvirne.

**Kriterij za prijedlog** (zapisan unaprijed): +5pp očekivanog povrata bez gubitka više od 30%
dana.
- Prag 60 naspram današnjeg 63: +1,5pp, više dana → ne prolazi.
- Trojac 4–6: +2,6pp naspram V1, ali 44% dana manje → ne prolazi.
- Bez bonusa za konsenzus tiketi su kraći (3,4 naspram 3,8 noge), a očekivani povrat je za
  1,3pp manje loš. To je mehanika, ne dokaz.

**Odluka:** prag 63, 3–6 noga i 4–50 ostaju (tvoja odluka od 08.09./27.09.).

**Činjenica za tvoju odluku:**
- unutar 3–6, kad je moguće, trojac blizu kvote 4 daje najveću šansu (~22%) i najmanji očekivani
  gubitak;
- bodovanje već kažnjava svaku dodatnu nogu s 3 boda.

**Runde:** nema podloge za ikakvo pravilo po rundi (jutros).

## 10. Scouting top 150 (Excel i Supabase)

**Tri sloja, odvojeno:**
1. Statistika: TML 365 dana do 23.09., glavni ždrijeb, ≥ 25 mečeva. Ima je 93 igrača od 150.
2. Rezultati iz našeg uzorka: Tokio, Peking, Šangaj.
3. Procjena stila: postojeći tekst + provjera svake tvrdnje.

Sve je u Excelu, na novim listovima "Dokazi 18.10.2026" i "Promjene 18.10.2026".

**Provjereno 86 tvrdnji:**
- "veliki server": 33 nije opovrgnuto, 10 neprovjerljivo;
- "jak povratnik": 1 opovrgnuta, 1 nije, 3 neprovjerljivo;
- "slab povrat": 5 nije opovrgnuto, 16 neprovjerljivo;
- "slab servis": 3 nije opovrgnuto, 14 neprovjerljivo.

**Izmijenjeno:**

| što | koliko | detalj |
|---|---|---|
| tekst | 1 | **Atmane**: uz "strong return" dodano "[18.10.2026 check: 'strong returner' NOT supported - return points won 31.1% (median 35.6%) ...]". I naš zapis od 06.09. kaže 19. percentil |
| rang | 66 | iz ATP singl liste koju bilježi dnevni run od 05.10. Kod rang iz scoutinga ne čita |
| razine pouzdanosti i datumi profila | 0 | — |

**Povučeno:**
- Đoković "greatest returner" (12:50 upisano, 12:52 vraćeno);
- 0,9pp ispod medijana je unutar jedne standardne pogreške na 28 mečeva i nije prilagođeno
  jačini protivnika;
- RapidAPI kaže suprotno (87. percentil);
- uvjet je zato pooštren na ≥ 2pp (zapisano kao NAKNADNO 12:52).

**Povratak:** `python revizije/2026-10-18/skripte/b_scouting_vrati.py --vrati`. Kopija svih 150
redaka i starog Excela je u `revizije/2026-10-18/scouting/`.

**Usput nađeno (važno):** RapidAPI povrat koji model vidi je **+5,7pp iznad TML-a za zadnjih
365 dana** (87 igrača; 10.–90. percentil +3,5 do +8,0; servis −1,0pp, r = 0,80). Kritičar je
našao uzrok:
- **To nije sezona 2026, nego praktički zamrznuta statistika KARIJERE.** `get_player_stats` ne
  šalje sezonu, vrijednosti se kroz ~54 dana ne miču (medijan promjene 0,1pp na 90 igrača), a
  poklapaju se s TML karijerom (servis r = 0,94, naspram 0,80 za 365 dana).
- Rastav 5,6pp:
  - +2,3pp je naš neponderirani prosjek povrata na 1. i 2. servis (`data_fetcher.py`, poznato od
    07.08.);
  - ~0,9 prozor;
  - ~0,6 razina (Challengeri);
  - ~2,4 neobjašnjeno (servis+povrat u RapidAPI-ju 102,4, u TML-u 100,5).
- Primjer Đoković: ponderirani RapidAPI 41,9 = njegova TML karijera 41,8, a zadnjih 365 dana
  35,6.
- **Posljedica:** model (i Nose uživo) čita karijerni servis/povrat kao da je sadašnji. Za
  igrače u padu (Đoković, Wawrinka, Čilić) i za one u usponu (Jodar) to je kriva slika.
- **Prijedlog (nije proveden, mijenja ulaz u prompt → nova era, tvoja odluka):** servis/povrat
  za prompt i Nose iz TML-a, zadnjih 365 dana. Osvježavam ga ja, besplatno.

**Preporuka za tebe:** Jodar je sada 13., ima 53 meča glavnog ždrijeba i povrat 41,0% (razina
Sinnera). Profil mu je "Insufficient", pa ga model ne vidi. Ručni profil bi pomogao, a razinu
pouzdanosti biraš ti.

## 11. Što je provedeno, što je eksperiment, što je odbačeno

| stavka | status | dokaz | očekivani učinak | rizik | praćenje |
|---|---|---|---|---|---|
| bonus za konsenzus 4 → 0 | **PROVEDENO** (reverzibilno) | n=40, −0,4pp ±13,9 | ~0 (nema konsenzusa na 250-icama) | ako je ipak stvaran, −4 boda za rijetke kombinacije | KONS u `measure_candidates` |
| analiza gubitka: 3 retka + 4 oznake | **PROVEDENO** | kvar potvrđen jutros; 6/6 CONFIRMED bez potvrde | manje lažnih prijedloga izmjena | nula za pickove | nove analize od 19.10. |
| sažetak dana bez tiketa (B4) | **PROVEDENO** | tiket 4 od 10 dana zbog praga | točan razlog u mailu i aplikaciji | nula | — |
| K22, K24, L4 u mjerenjima | **PROVEDENO** | — | kapije se mjere jednom naredbom | nula | `measure_candidates.py` |
| scouting: Atmane + 66 rangova + dokazi | **PROVEDENO** | TML 41 meč, −4,5pp ispod medijana | ~0 | mali | lista "Promjene" |
| Nose (nose-v1) | **EKSPERIMENT U SJENI** | LAB N5–N7 pali; naši IZBJEGAVAJ −8,8 ±13,5 | nema dok ne prođe K24 | čitateljski (ručni izbor po nepotvrđenom upozorenju) | K24 G1–G3 |
| težine (bilo koje) | ODBAČENO sada | v18 − v14 +0,7 ±18,7 | — | — | nova era prompta |
| prag 60/66, 3 noge, 4–6 noga, kvota 5–8 | ODBAČENO (kriterij) | simulacija + matematika | — | — | tvoja odluka |
| statistika s turnira kao bonus | ODBAČENO | 0/18 + TA2 + TA3 | — | — | ne otvarati bez novog izvora |
| B1–B4a, TA2, TA3, N5, N6 | ODBAČENO | LAB, 79 testova ukupno | — | — | — |
| B4b | ODBAČENO (kritičar) | +1,6pp sirovo, +0,4pp uz kontrolu pojasa | — | — | — |
| kapija K24: zamrzavanje + kontrola pojasa | **PROVEDENO** (prije ijednog podatka) | kritičar: lažna potvrda 7,5% uz ponovno gledanje | poštenija kapija | strožih uvjeta: manja snaga | `nose.gate_status` |
| servis/povrat iz TML-a umjesto RapidAPI-ja | PRIJEDLOG (tvoja odluka, nova era) | RapidAPI = karijera, povrat +4,7pp | točnija slika forme | nova era, korpus se reže | — |
| Nose u odabiru | NE (kapija) | N7 obrnut | — | — | K24 |
| Đoković scouting | POVUČENO | izvori proturječni | — | — | — |

## 12. Stara naspram nove logike na istim mečevima

- **Odabir tiketa** (isti bazeni od 08.09., prag po datumu):
  - s bonusom i bez njega isti su dani s tiketom (9/9);
  - kombinacija je drukčija u 3 od 9 dana (29.09., 01.10., 06.10.);
  - očekivana šansa 18,0% naspram 18,4%, očekivani povrat −18,4% naspram −17,1%: praktički jednako.
- **Analiza gubitka** (30 analiza od 27.09., po pravilu, bez ponovnog plaćenog poziva):
  - stara: 6 CONFIRMED (0 potvrđeno), 5 prijedloga s ATP pobjedama;
  - nova: 0 prijedloga, svih 6 dobiva FAILED OR CLOSED ili CANDIDATE, UNCONFIRMED.
- **Nose naspram cijene, odvojeni uzorak** (2024–26, težina s 2022–23): lošiji od cijene, a
  njegova neslaganja prolaze −2,3pp. Na našim mečevima STARO i NOVO isti smjer kod IZBJEGAVAJ,
  bez dokaza.
- **Promjene iz Šangaja nisu nigdje prikazane kao potvrđene na Šangaju.** Šangaj je razvojni
  uzorak. Sve provjere su ili povijest (vremenski odvojena) ili buduće kapije.

## 13. Bruxelles, Lyon, Almaty (ATP 250, dvorana)

1. **Model isti** (prag 63, era bccf4742). Očekuj malo tiketa: od 04.10. tiket je bio u 4 od 10
   dana.
2. **Konsenzusa nema** (Odds API ne pokriva 250-ice), pa bonus ionako ne bi okinuo. Kazna za
   tržišnog autsajdera radi preko screenshot cijene.
3. **Ako se tiket složi:** najveću šansu ima **trojac s ukupnom kvotom blizu 4,0** (~22%), uz
   najmanji očekivani gubitak (−12%). Svaka dodatna noga oduzima ~1 bod šanse i ~4 boda povrata.
4. **Nose čitaj kao bilješku, ne kao pravilo.**
   - "IZBJEGAVAJ" na povijesti nema potporu (+1,3pp).
   - "Nose vidi rizik koji cijena ne vidi" na povijesti je bio krivi smjer.
   - Nijedno pojedinačno upozorenje nema izmjerenu težinu. M2 je izgledao kao trag (−4,8pp), ali
     nije monoton po pragu, pa je šum.
   - Uživo Nose čita karijerni servis/povrat (točka 10), ne zadnjih 12 mjeseci.
5. **Dvorana:** na dvoranskim hard 250-icama favoriti prolaze točno kako kvota kaže (+1,2pp ±3,1,
   n=882). Almaty je na ~850 m, što pomaže servis obojici.
6. **Puni se K18** (hard ATP 250: 14 od 30).
7. **Tvoji koraci:**
   - (a) skinuti `2026.xlsx` s tennis-data.co.uk — bez toga K21 i K23 stoje (točka 14);
   - (b) odlučiti hoćeš li ručni scouting za Jodara;
   - (c) push na GitHub kad želiš da izmjene i jutarnji raspored Odds API snimanja počnu
     djelovati.

## 14. Datoteke, testovi, ograničenja

**Izmijenjene datoteke:**
- `agent/nose.py` (novo) — Nose i kapija K24 (zamrznuta, s kontrolom pojasa);
- `agent/ticket_builder.py` — bonus 0, razlog bez tiketa;
- `agent/run_daily.py` — Nose u sjeni, razlog bez tiketa;
- `agent/feedback_analyzer.py` — bazne stope, četiri oznake;
- `scripts/measure_candidates.py` — K22, K24, L4, KONS;
- `pages/1_Dnevni_Listic.py` — prikaz Nosea, tekst dana bez tiketa;
- `test_cap_and_weather.py` (odjeljak 52, test konsenzusa prepravljen);
- `test_provisional_schedule.py` (rječnik oznaka);
- `MODEL_CHANGELOG.md`, `DECISION_INPUTS.md`, `BACKLOG.md`;
- `ATP_Player_Scouting top150.xlsx`;
- `revizije/2026-10-18/` (ovaj izvještaj, PRAGOVI_B, `skripte/b_*.py` uključujući
  `b_lab_naknadno.py` za kritičareve provjere, `scouting/`).

**Supabase:** `player_scouting` — 67 redaka (1 tekst, 66 rangova). Ništa drugo u bazi nije
mijenjano; povijesni rezultati i stare analize nisu dirani.

**Testovi:**
- `test_cap_and_weather.py`: 892 OK (jutros 861);
- `test_provisional_schedule.py`: 271 OK (jutros 261);
- nijedan test nije uklonjen; dva su prepravljena da čuvaju nove odluke, uz provjeru da je
  stara vrijednost povratna.

**Git:** lokalni commit, **bez pusha** (push = deploy na GitHub Actions i Streamlit).

**Ograničenja:**
1. **K21 i K23 blokirani:** nema `2026.xlsx` nakon 13.09.
2. TML završava 23.09., pa Peking, Tokio i Šangaj još nisu u povijesti.
3. Na našim mečevima nijedna razlika manja od ~8pp ne može se dokazati (n=140).
4. Simulacija tiketa je okvirna (prepisani retci, bez recenzenta).
5. Nose na povijesti koristi naš izračunati ELO i TML statistiku zadnjih 365 dana, a uživo
   tennisabstract ELO i RapidAPI karijernu statistiku (povrat napuhan ~4,7pp). Isti kod, ali ne
   isti ulazi, pa razina dokaza s povijesti za uživo oznake vrijedi samo približno.
6. Pinnacle u povijesnim podacima staje 13.01.2026, pa je 29% cijena u P2 prosjek kladionica.

## 15. Kritičar (subagent `skeptik`, 18.10.2026, odgovor 15:04)

**Opća presuda: SUMNJIVO.** Kritičar je brojke replicirao neovisno.
- **Drže:** zaključci "ništa ne mijenjati", "Nose samo u sjeni" i "težine ne dirati".
- **Ne drže:** tri "traga" (B4b, M2, "smjer" kod IZBJEGAVAJ) i dva objašnjenja (RapidAPI,
  simulacija).

Sve njegove primjedbe provjerene su i ugrađene.

| točka | presuda | što je promijenjeno |
|---|---|---|
| B4b +1,6pp | **PROBLEM** | uz kontrolu pojasa +0,4pp; slučajni uzorak iste strukture cijena +1,1pp; LAB r(ELO jaz) +0,00 → povučeno "trag K22" |
| N7 obrnut | **OK** | strane poravnate, antisimetrija provjerena; −1,5 do −2,6pp u svim varijantama ELO-a i cijene |
| M2 (opis) | **PROBLEM, blag** | nemonotono po pragu, učinak u prstenu 2,0–2,5pp i u 2023.; najbolja od 9 oznaka → u Noseu označen kao šum |
| Nose na našim analizama | **PROBLEM** | "smjer hipoteze" povučen; isto pravilo na povijesti +1,3pp uz pojas (n=1.824) |
| kapija K24 | **PROBLEM** | zamrznuta presuda (prvih 60/150/300), kontrola pojasa, G1+G2 = jedan dokaz (NAKNADNO 15:05) |
| težine v18 | **OK** | — |
| RapidAPI naspram TML | **brojke OK, tumačenje PROBLEM** | nije sezona nego zamrznuta karijera; rastav 2,3 + 0,9 + 0,6 + 2,4 neobjašnjeno |
| scouting | **OK** | Atmane je 3. percentil od 93 (−5,0 SE, uz protivnike −3,05pp); Đoković s pravom povučen (uz protivnike +1,05pp) |
| simulacija tiketa | **zaključak OK, objašnjenje PROBLEM** | glavni razlog loše reprodukcije bio je prag (60 do 04.10.); ispravljeno → 4/13 isto, 5/13 djelomično |

**Tri najveća rizika (kritičar):**
1. G1/G2 su unaprijed gotovo osuđeni (povijest +1,4pp naspram praga −5pp).
2. Tragovi bez neovisne potvrde predstavljeni su preglasno. Ispravljeno u izvještaju i u
   `nose.py`.
3. Uživo ulazi Nosea nisu povijesni ulazi (RapidAPI karijera). Zapisano u aplikaciji i u
   točki 10.

**Najbrža provjera koju je predložio:** točno pravilo IZBJEGAVAJ uz kontrolu pojasa. Napravljena
je (`b_lab_naknadno.py`): +1,3pp, n=1.824.

---

## 16. Dodatak 18.10.2026 15:48 — novi 2026.xlsx, TML 12 mj., push

**Tvoje odluke:**
1. push odobren (prvo točka 2);
2. novi `2026.xlsx`;
3. "može, pratit ćemo i jedno i drugo";
4. Jodar zanemaren.

**Novi `2026.xlsx` (do 06.10.):**
- laboratorij obnovljen (12.472 meča, TML svjež);
- Intuicija prior ponovno naučen (pomak neznatan);
- K21: od 14.09. n = 9 od 150 → ČEKA;
- K23 (S1): n = 4 → ČEKA (2027.);
- dubina 4+: n = 1.

Ništa od toga ne mijenja model.

**TML forma 12 mj.:** provjere prije uključivanja (`b_tml_provjera.py`):

| provjera | rezultat |
|---|---|
| pokrivenost | 99–100% igrača i mečeva od 01.08. |
| usporedivost | servis +1,0pp (r 0,83), povrat −4,5pp (r 0,81) naspram RapidAPI-ja |
| svježina | tablica do 18.10., zadnji meč igrača medijan 7–8 dana; osvježava se prije svakog runa |
| pričuva | bez TML-a za oba igrača → RapidAPI karijera, uz oznaku izvora |

**Što je provedeno:**
- TML se bilježi uz RapidAPI za svaki meč;
- Nose ga koristi kao ulaz (iste brojke kao na povijesti), a karijernu varijantu bilježi
  usporedno;
- prompt ostaje na RapidAPI-ju (pragovi u pravilima su na toj skali; prelazak traži novu eru i
  plaćeni živi poziv).

**Prijedlozi drugog modela (ChatGPT) — što ima smisla za nas:**

| prijedlog | ocjena | što je napravljeno |
|---|---|---|
| prije pusha provjeriti git status i sadržaj commita | da | provjereno; bez slučajnih datoteka (`.cache` i `__pycache__` su ignorirani) |
| testovi neposredno prije pusha | da | oba paketa: 907 i 271 OK |
| potvrditi da je Nose samo u sjeni i bonus ugašen | da | pokriveno testovima (Nose nakon tiketa, tiket ga ne uvozi, konsenzus ne mijenja bodovanje) |
| ne mijenjati izvor servisa/povrata prije provjere pokrivenosti, usporedivosti, svježine, pričuve | da, i to je presudilo | provjere napravljene; prompt namjerno nije prebačen (skala), Nose jest |
| označiti da Nose koristi karijerne podatke | da | opis u aplikaciji kaže koji je izvor (TML ili karijera) |
| odvojeni commitovi | da | tri commita: revizija, osvježeni podaci, TML |
| potvrditi CI i deploy nakon pusha | djelomično | CI ne postoji (nijedan workflow se ne pokreće na push); dnevni run je ručni, pa izmjene djeluju od idućeg runa |
| bez plaćenih poziva | da | nijedan plaćeni poziv; TML je besplatan |
| K21/K23 kao zasebno otvoreno pitanje | već riješeno | `2026.xlsx` je stigao; pokrenuto, međustanje upisano |

## 17. Dodatak 18.10.2026 19:45 — prelazak modela na TML servis/povrat: napravljen, provjeren, NIJE uveden

**Tvoja odluka:** nova era prompta i TML za zadnjih 12 mjeseci, uključujući jedan plaćeni probni
poziv, "ako rezultati i provjere opravdavaju promjenu". Pravila odluke zapisana su prije računanja
(`PRAGOVI_C_TML_PROMPT_2026-10-18.md`, 16:25).

**Što je napravljeno (sve na grani `tml-era-881d89f8`, commit 54590fb):**
- servis/povrat iz TML-a, 12 mj. povučeno prema karijeri, i izmjereni hold;
- pragovi preslikani po kvantilima (isti udio okidanja; zemlja 4,5pp);
- pričuva za igrača bez TML-a (RapidAPI +0,9 / −4,1pp, s oznakom);
- scouting bez starih brojki u zagradama;
- testovi;
- **jedan plaćeni probni poziv** (Zverev – Davidovich Fokina, podaci do 16.10.): valjan JSON iz prvog
  pokušaja, 2.299 / 4.000 tokena, navodi brojke 12 mj. i nijednu staru.

**Što kaže mjerenje:**

| | P1 2022–23 | P2 2024–26 | presuda |
|---|---|---|---|
| (b) čistih 12 mj. naspram karijere | +0,0030 | **−0,0064** (z −2,1) | lošije → po slovu pravila "ne prelazi se" |
| (c) mješavina naspram karijere | +0,0098 | +0,0028 [−0,0015, +0,0068] | u šumu; 2026. −0,005 |
| (c) kad igrač ima > 50% poena iz Challengera/kval. (48,5% mečeva) | −0,005 (2022–24) | −0,020 (2025–26) | lošije |
| (c) ostali mečevi | +0,013 do +0,028 | | bolje |
| isti naši mečevi (437), pogođena strana | | 58,3% → 59,3% | šum (±2,7pp) |

(razlike log-gubitka, pozitivno = TML bolji; skripte `c_tml_lab.py`, `skeptik_tml/`)

**Kritičar (skeptik): PADA.** Implementacija mješavine bila je tumačenje pravila (za nju nije bio
zapisan prag naspram sadašnjeg stanja), a dobitak je u šumu. Njegove brojke ponovljene su istim
skriptama i slažu se.

**Odluka:** model ostaje na RapidAPI karijeri (era bccf4742). U `master` nije ušlo ništa od nove
ere. Nose ostaje na TML 12 mj. (dodatak 16:53 povučen prije prvog podatka).

**Što to znači:** stari ulaz nije bio pokvaren nego zamrznut. Napuhani povrat je gotovo stalan
pomak, pa razlike među igračima ostaju točne. Novi ulaz sa svim razinama pokvario bi procjenu
upravo igrača koji puno igraju Challengere, a takvih je u našim mečevima ~45%.

**Nastavak (K25):** TML samo s glavnog ždrijeba bio je na viđenim podacima bolji svake godine
(+0,013 do +0,019, i 2026.). To je naknadni rez, pa je prag za potvrdu zapisan u 17:34, prije
gledanja:
- test A: godine 2010–2019 (odmah, besplatno);
- test B: budući mečevi (n ≥ 700, ~prosinac).

Tek kad prođu oba, predlaže se nova era. Ni to ne bi tuklo cijenu: log-gubitak cijene je 0,589,
a najbolje varijante ~0,63.
