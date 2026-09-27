---
name: oblikuj
description: Pretvori korisnikovu dugu ili neurednu poruku (struju svijesti, bilješke, popis ideja, zalijepljene linkove) u jasan zadatak s ciljem, ograničenjima i kriterijem uspjeha, pa traži potvrdu prije rada. Koristi kad korisnik napiše /oblikuj ili zalijepi dugačke bilješke s više ideja odjednom.
argument-hint: "[bilješke ili zahtjev]"
---

# /oblikuj — od struje svijesti do jasnog zadatka

Korisnik piše brzo, na hrvatskom, često više ideja u jednoj poruci (ponekad i diktirano). Ovdje
posao NIJE odmah raditi, nego razumjeti i provjeriti razumijevanje. Jasan zadatak u prvoj
poruci štedi tokene i daje bolji rezultat nego dogovaranje kroz deset poruka.

Ulaz: $ARGUMENTS (ako je prazno, uzmi zadnju korisnikovu poruku).

## Koraci

1. Pročitaj ulaz do kraja. Izdvoji svaku zasebnu ideju ili zahtjev.
2. Za svaku brzo provjeri u projektu (bez dugog istraživanja):
   - `BACKLOG.md` "ČEKA" — je li već na popisu?
   - `DECISION_INPUTS.md` (registar K i "ODBAČENO") i memorija — je li već izmjereno i
     odbačeno? Ako jest, reci to jednom rečenicom s razlogom; ne predlaži ponovno bez novih
     podataka.
   - Je li to izmjena modela (prompt, odabir tiketa, težine)? Tada vrijedi kapija, nova era i
     korisnikovo odobrenje.
3. Napiši kratki brief (najviše ~15 redaka), ovim redom:
   - **Cilj** — jedna rečenica: što korisnik zapravo želi postići.
   - **Zadaci** — numerirani, konkretni koraci.
   - **Ne diram** — što ostaje netaknuto (npr. model bez odobrenja, ručne runde).
   - **Gotovo je kad** — mjerljivo (testovi prolaze, izvještaj u `revizije/`, brojka).
   - **Već postoji / odbijeno** — ako išta od traženog već postoji ili je izmjereno kao nula.
   - **Pitanja** — najviše 3, samo ona o kojima stvarno ovisi što radiš.
4. Završi s: "Je li to to? Napiši **kreni** ili ispravi."
5. Ne počinji rad dok korisnik ne potvrdi.

## Stil

Jednostavan jezik, bez žargona. Brojke da, formule ne. Ako je ulaz kratak i jasan, reci to u
jednoj rečenici i ponudi da kreneš odmah.
