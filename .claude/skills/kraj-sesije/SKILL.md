---
name: kraj-sesije
description: Zatvaranje radne sesije — pravi sat, testovi, MODEL_CHANGELOG (ako je dirnut model), DECISION_INPUTS (ako su se mijenjali kandidati), BACKLOG (NAPRAVLJENO + ČEKA), memorija i git. Koristi kad korisnik napiše /kraj-sesije ili kaže da je posao sesije gotov.
disable-model-invocation: true
---

# /kraj-sesije

1. **Sat:** `date "+%d.%m.%Y %H:%M"` — to vrijeme ide u sve upise ispod. Nikad napamet.
2. **Testovi:** `PYTHONIOENCODING=utf-8 python test_cap_and_weather.py` i
   `PYTHONIOENCODING=utf-8 python test_provisional_schedule.py`. Ako išta padne, pokaži
   korisniku ispis i ne commitaj.
3. **Je li dirnut model** (prompt, pravila, odabir tiketa, težine, strategija, `context_snapshot`)?
   - Da → unos u `MODEL_CHANGELOG.md`: naslov s datumom i vremenom; što / zašto / ishod; era
     (`rules_hash`) i verzija snapshota ako su se promijenile. Uz izmjenu u kodu hrvatski
     komentar s vremenom.
   - Prompt dirnut → nova era; premjeri duljinu odgovora naspram `_ANALYSIS_MAX_TOKENS`.
4. **Kandidati (K#)** mijenjani ili izmjereni → `DECISION_INPUTS.md` sekcija 0a (ishod, prag,
   datum i vrijeme).
5. **`BACKLOG.md`:**
   - "zadnje ažurirano" u zaglavlju;
   - novi unos na vrh "NAPRAVLJENO — dnevnik": `### DD.MM.GGGG HH:MM — kratki naslov`, pa
     jednostavnim jezikom što je napravljeno i čemu služi, "Pazi:" ako ima posljedica, i redak
     "Gdje u kodu";
   - osvježi "ČEKA" (nove provjere s pragom; zatvorene stavke prekriži ili makni).
6. **Memorija:** novi trajni nalaz ili korisnikova odluka → zapis u memoriju. Ne duplicirati
   ono što već stoji u kodu, gitu ili `CLAUDE.md`.
7. **Git:** `git status`. Commit samo ako ga je korisnik tražio ili odobrio (poruka na
   hrvatskom, sažeto, s erom ako je nova). Push samo na izričit zahtjev.
8. **Korisniku:** 3-6 rečenica — što je napravljeno, što čeka njega, što je sljedeće.
