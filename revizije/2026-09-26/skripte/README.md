# Skripte revizije 26.09.2026

Analitičke skripte iz kojih su izračunate sve brojke u `../REVIZIJA_2026-09-26.md`.
**Ne ulaze u produkciju** i ne mijenjaju bazu — samo čitaju.

Podaci nisu u repozitoriju (veliki su); regeneriraju se u `.cache/rev2609/`:

1. `fetch.py` — tablice iz Supabasea u `.cache/rev2609/data/` (samo čitanje)
2. `harvest_pm.py` — `/atp/player/past-matches` s kvotama za ~315 igrača u `.cache/rev2609/pm/`
   (~1.000 RapidAPI poziva, nastavlja gdje je stala)

Skripte očekuju da se pokreću iz `.cache/rev2609/` (tamo su i `data/` i `pm/`):

| skripta | što mjeri |
|---|---|
| `base.py`, `pmbase.py`, `join.py` | zajednička tablica mečeva, devig cijena, spoj s berbom |
| `a_losses.py` | klasifikacija svakog gubitka i dobitka po unaprijed zadanim pravilima |
| `a_rules.py` | koliko gubitaka i pobjeda bi svako kandidatsko pravilo uklonilo |
| `a_vars.py`, `a_vars2.py` | varijable: informacija povrh cijene naspram osjetljivosti modela |
| `a_idea2.py` | tablica promašaja po igraču (tri testa) |
| `a_idea3.py` | povijest poraza na turniru (jači/slabiji protivnik po kvoti) |
| `a_sequence.py` | sekvenca protivnika na pobranim ždrijebovima |
| `a_weather.py` | vrijeme, dob, visina — opisno i prediktivno |
| `a_interact.py` | 276 interakcija + permutacijska nul-raspodjela |
| `a_hmc.py`, `a_hmc_big*.py` | Historical Match-Up Context: walk-forward, oracle, veliki uzorak |
| `a_scouting.py` | provjera matchup tvrdnji scoutinga i proturječja stila |
| `a_ticketsim.py` | simulacija tiketa kroz stvarni `_find_best_combination` |
| `make_appendix.py` | Excel prilog |

Za redovite provjere kandidata iz registra ne koristiti ove skripte nego
`python scripts/measure_candidates.py` (pragovi zapisani unaprijed).
