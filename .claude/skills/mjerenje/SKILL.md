---
name: mjerenje
description: Postupak za svako mjerenje u projektu (je li varijabla, pravilo ili nalaz stvaran) — prag unaprijed, snaga uzorka, prazna polja, curenje, kontrola cijene, višestruko testiranje, polovice, povijesna predprovjera, skeptik i upis u registar. Koristi prije svake analize kandidata, revizije ili tvrdnje "X predviđa ishod".
argument-hint: "[što mjerimo]"
---

# /mjerenje — postupak kapije

Mjerimo: $ARGUMENTS

Nijedan korak se ne preskače. Na kraju ide izvještaj u formatu ispod.

## 0. Prije gledanja podataka

- Hipoteza jednom rečenicom i SMJER (+ ili −).
- Prag za "prolazi / pada" zapiši UNAPRIJED (u `DECISION_INPUTS.md` sekcija 0a ili u
  `revizije/<datum>/PRAGOVI_*.md`) s vremenom iz `date "+%d.%m.%Y %H:%M"`.
- Izračunaj snagu i napiši je uz prag:
  `python ${CLAUDE_SKILL_DIR}/scripts/snaga.py --n <n>` (koliki edge taj n uopće vidi) ili
  `python ${CLAUDE_SKILL_DIR}/scripts/snaga.py --edge 5` (koliki n treba).
  Uz n=30 interval je ±17pp — takav prag je probir, ne dokaz.

## 1. Podaci prije brojki (tihi null)

- Popunjenost svakog polja (% praznih). Polje prazno u ~100% redaka → PRVO ispiši ključeve
  sirovog odgovora; provjeri i pisca i čitača polja.
- Zadane vrijednosti koje glume podatak: ELO 1500, 0 umjesto None, oznaka "Winner".
- Duplikati (isti meč pod ±3 dana), poravnanje strana (u nekim izvorima je pobjednik uvijek
  prvi; match-stats zna obrnuti igrače).
- Curenje iz budućnosti: varijabla smije koristiti samo mečeve PRIJE ovog meča (H2H je jednom
  brojao isti meč pod drugim datumom i pokazao lažnih +76pp).

## 2. Mjera

- edge = stvarni postotak pobjeda − prosjek devigirane cijene (u pp). Nikad sirovi postotak.
- Skupine se uspoređuju unutar istog pojasa cijene (Simpsonov paradoks: `value` je izgledao
  −21pp, pod kontrolom cijene −1pp).
- Berbe povijesti: simetrično uzorkovanje (oba igrača u uzorku), inače favoriti izgledaju
  bolje nego jesu.
- Uz svaku brojku interval (bootstrap ili sd/√n).

## 3. Je li stvarno

- Koliko je testova napravljeno? Holm ili BH korekcija; napiši koliko lažnih nalaza se očekuje
  slučajno.
- Polovice (vremenski) i ere: isti predznak? To je bolje predviđalo ishod kapije od P-vrijednosti.
- Monotonost po razredima (nemonotono i ponovljeno = nema mehanizma).
- Mehanizam: zašto tržište to ne bi već imalo u kvoti? Na 12.324 meča (povijesni laboratorij,
  27.09.2026) nijedna od 10 predmečnih varijabli o igraču nije pobijedila cijenu.
- Ako se varijabla da izračunati iz povijesti: predprovjera u povijesnom laboratoriju
  (`revizije/2026-09-27/skripte/lab_*.py`, naspram Pinnacle ili prosjeka kladionica).
  Povijest ne može testirati NAŠ izbor pickova — samo je li cijena na tržištu kriva.

## 4. Prije upisa

- Pokreni subagent `skeptik` s kratkim opisom nalaza, brojkama i putem do skripte.
- Upis u `DECISION_INPUTS.md` (novi K broj ili ishod postojećeg) s pragom zapisanim prije
  podataka; ako se mjeri uživo, dodaj ga u `scripts/measure_candidates.py`.
- U model ne ulazi ništa bez korisnikova odobrenja.

## Izvještaj korisniku

- Jedna rečenica: drži / slab / pada.
- Tablica: skupina | n | edge | interval | polovice.
- Najviše tri ograde.
- Što predlažeš i što to znači za tiket — jednostavnim jezikom.
