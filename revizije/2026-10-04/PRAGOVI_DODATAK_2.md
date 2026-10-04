# Revizija 04.10.2026 — dodatak 2: korisnikovi novi prijedlozi (pragovi PRIJE računanja)

Zapisano **04.10.2026 19:07**, prije ijedne brojke za ove testove. Isti kriterij kao C/D u
`PRAGOVI_REVIZIJA_2026-10-04.md`:
- **PROLAZI:** |edge| ≥ 2pp, 95% interval ne prelazi nulu, isti predznak u obje polovice
  (2022–23 / 2024–26), smjer kao ovdje.
- **SLAB:** isto uz |edge| < 2pp.
- **PADA:** sve ostalo.

Povijest: 12.324 ATP meča (tennis-data + TML, do 13.09.2026), poštena cijena; sve samo iz
mečeva PRIJE meča. Prolaz je predprovjera, ne odluka: u model ništa ne ulazi bez potvrde
uživo i korisnikova odobrenja.

| oznaka | ćelija (igrač iz ćelije) | smjer |
|---|---|---|
| TWL1 | bolji omjer pobjeda na OVOM turniru u prethodne 3 sezone (glavni ždrijeb + kvalifikacije, oba ≥ 3 meča ondje) | + |
| TWL2 | veći "višak na turniru" = omjer na ovom turniru − njegov opći omjer u istim godinama (oba ≥ 3 meča ondje) | + |
| TWL3 | TWL2 uz razliku viška ≥ 15pp i igrač je tržišni autsajder | + |
| QF1 | favorit po cijeni u QF/SF/F čiji protivnik ima ≥ 3pp bolji hold % (365 dana) | − |
| QF2 | favorit po cijeni u QF/SF/F čiji protivnik ima ≥ 2 asa na 100 servisnih poena više | − |
| QF0 (kontrola, bez praga) | isto kao QF1 i QF2, ali u ranim rundama (R128–R32) | — |

Holm preko 5 testova s pragom (TWL1–3, QF1–2).

**Vlažnost** (korisnikov komentar o Đokovićevom disanju; prije izmjereno r=+0,09, n=315 —
nula): na našem korpusu r(vlaga, ishod − cijena), tercile, i vlaga × dob (pick stariji 4+ god.
u gornjoj trećini vlage). **"Zanimljivo"** = |r| ≥ 0,10 s intervalom koji ne prelazi nulu i
isti predznak u STARO i NOVO. Povijest nema vremenske podatke, pa je ovo samo probir.
