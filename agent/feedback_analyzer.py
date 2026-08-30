"""
Feedback Analyzer: večernji job koji:
1. Dohvaća rezultate završenih mečeva
2. Ažurira statuse tiketa
3. Analizira izgubljene parove (Claude)
4. Predlaže i primjenjuje korekcije težina modela
"""
import os
import json
import datetime
import anthropic
from dotenv import load_dotenv
from config.model_config import CLAUDE_MODELS, WEIGHT_ADJUSTMENT, DEFAULT_WEIGHTS
from database import supabase_client as db
from agent.data_fetcher import (get_matches_for_date, get_recent_form, get_match_stats,
                               get_match_stats_aligned,
                                find_player_id, get_current_season_results)


def _build_season_winner_lookup(rows: list, pair_to_tid: dict) -> dict:
    """Vrati {(p1_lower, p2_lower): winner_name} za parove iz `rows` (analyzed_matches /
    ticket_matches retci s player1/player2/tournament/match_date).

    Izvor pobjednika je /atp/tournament/results tekuće sezone (get_current_season_results)
    jer /atp/fixtures NIKAD ne nosi pobjednika. tournament_id se traži kaskadno:
      1) pair_to_tid — mapa (par igrača) → tid iz fixtures feeda (radi za današnje mečeve,
         ali fixtures za PROŠLE dane izbacuju već odigrane mečeve — otkriveno 26.07.2026,
         isti mehanizam zbog kojeg je Kitzbühel "nestao" iz feeda 25.07.)
      2) past-matches poznatog igrača iz para (ranking lista → player_id → njegovi
         nedavni mečevi nose tournamentId; meč u danima turnira ⇒ tid turnira).
    """
    from agent.data_fetcher import find_player_id as _fpid

    groups: dict = {}   # tname -> [(p1, p2, iso_date), ...]
    for am in rows:
        tname = (am.get("tournament") or "?").split(" - ")[0].strip().lower()
        d = str(am.get("match_date") or "")[:10]
        p1 = (am.get("player1") or "").lower().strip()
        p2 = (am.get("player2") or "").lower().strip()
        if p1 and p2:
            groups.setdefault(tname, []).append((p1, p2, d))

    tids: dict = {}
    for tname, pairs in groups.items():
        for p1, p2, _d in pairs:
            tid = pair_to_tid.get((p1, p2), "")
            if tid:
                tids[tname] = tid
                break

    for tname, pairs in [(t, p) for t, p in groups.items() if t not in tids]:
        # tid preko past-matches: tražimo TOČNO meč tog para (datum ±2 dana I prezime
        # protivnika) — širi prozor po rasponu turnira je hvatao KRIVI turnir, jer isti
        # igrač u susjednom tjednu već igra sljedeći event (npr. Gstaad pa Kitzbühel)
        tried = 0
        for p1, p2, d in pairs:
            if tname in tids or tried >= 5 or not d:
                break
            try:
                d_lo = datetime.date.fromisoformat(d) - datetime.timedelta(days=2)
                d_hi = datetime.date.fromisoformat(d) + datetime.timedelta(days=2)
            except ValueError:
                continue
            for me, opp in ((p1, p2), (p2, p1)):
                pid = _fpid(me)
                if not pid:
                    continue
                tried += 1
                opp_surname = opp.split()[-1] if opp.split() else ""
                for fm in get_recent_form(pid, n=25).get("matches", []):
                    fd = fm.get("date") or ""
                    fopp = (fm.get("opponent") or "").lower()
                    if not (fm.get("tournament_id") and fd and opp_surname
                            and opp_surname in fopp):
                        continue
                    try:
                        fdate = datetime.date.fromisoformat(fd)
                    except ValueError:
                        continue
                    if d_lo <= fdate <= d_hi:
                        tids[tname] = fm["tournament_id"]
                        break
                if tname in tids or tried >= 5:
                    break

    # POVRATNI UPIS (30.08.2026 11:05) — bez ovoga se razrijeseni `tournament_id` gubio.
    #
    # POVOD: Fery-Buse, finale Winston-Salema 29.08. Vecernji job je pobjednika i rezultat
    # (6-3 6-2) nasao BEZ problema — bas preko rezervne rute nize (past-matches poznatog
    # igraca) — ali `match_stats` je ostao prazan. Uzrok: statistika se dohvaca samo ako je
    # poznat `tournament_id`, a taj se cita iz `match_to_tournament`, koji se gradi
    # ISKLJUCIVO iz `/atp/fixtures` feeda. Izmjereno isti dan: feed za 29.08. vratio je NULA
    # meceva (fixtures za prosle dane izbacuje odigrano), pa je Fery-Buse ondje nedostajao
    # svih 8 dana prozora -> `tournament_id = ""` -> `get_match_stats` se nikad ne pozove.
    #
    # Ova funkcija je tid VEC bila razrijesila (`tids[tname]`) i s njim dohvatila rezultate
    # sezone — ali ga je drzala lokalno i vracala samo mapu pobjednika. Dakle: potraga za
    # pobjednikom je imala DVA izvora, potraga za statistikom samo JEDAN.
    #
    # Sada se razrijeseni tid vraca u `pair_to_tid` za sve parove tog turnira, pa oba
    # potrosaca statistike (korak 2 za ticket_matches i 2b za analyzed_matches) nasljedjuju
    # rezervnu rutu uz NULA dodatnih API poziva — tid je ionako vec izracunat.
    #
    # Provjereno na Fery-Buse: tid=21348, a /atp/h2h/match-stats/21348/79065/79113 vraca
    # punu statistiku (Buse 2 asa, 4/7 BP, 57 poena; Fery 3/7 spasenih BP). Podaci su
    # postojali cijelo vrijeme — samo ih nismo trazili.
    n_backfilled = 0
    for tname, tid in tids.items():
        for p1, p2, _d in groups.get(tname, []):
            if (p1, p2) not in pair_to_tid:
                pair_to_tid[(p1, p2)] = tid
                pair_to_tid[(p2, p1)] = tid
                n_backfilled += 1
    if n_backfilled:
        print(f"  tournament_id dopunjen iz rezultata sezone za {n_backfilled} parova "
              f"(fixtures ih nije imao).")

    lookup: dict = {}
    for tname, tid in sorted(tids.items()):
        results = get_current_season_results(tid)
        for r in results:
            k = (r["player1"].lower().strip(), r["player2"].lower().strip())
            lookup.setdefault(k, r["winner"])
            lookup.setdefault((k[1], k[0]), r["winner"])
        print(f"  Rezultati sezone [{tname}]: {len(results)} odigranih mečeva.")
    missing = [t for t in groups if t not in tids]
    if missing:
        print(f"  Bez tournament_id (ostaju nerazriješeni): {', '.join(sorted(missing))}")
    return lookup
from utils.helpers import today_zagreb, days_ago, format_date

load_dotenv()

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client


def run_evening_update() -> dict:
    """
    Glavni entry point za večernji job.
    Vraća summary promjena.
    """
    print("=== Evening update ===")
    summary = {"resolved": 0, "won": 0, "lost": 0, "analyzed": 0, "weight_updated": False}

    # One-time migration: reset all old loss analyses so they are re-generated
    # in English with corrected ELO data. Runs once until no analyzed losses remain.
    existing = db.get_analyzed_lost_matches(limit=1)
    if existing:
        analysis_text = existing[0].get("loss_analysis", "") or ""
        # Detect old Croatian-language analyses by common Croatian words
        is_old = any(w in analysis_text for w in ["Analiza", "Faktori", "Pogrešno", "Presudni", "Promjena", "greške", "faktor"])
        if is_old:
            count = db.reset_loss_analyses()
            print(f"  Migrated {count} loss analyses to English (will re-generate this run).")

    # 1. Izgradi lookup player_id, tournament_id i fixture winner po imenu
    name_to_id = {}
    match_to_tournament = {}   # (p1_lower, p2_lower) -> tournament_id
    fixture_winner = {}        # (p1_lower, p2_lower) -> winner_name  (za walkover/predaju)
    for n_days in range(8):
        for m in get_matches_for_date(days_ago(n_days)):
            if m.get("player1_id"):
                name_to_id[m["player1"].lower().strip()] = m["player1_id"]
            if m.get("player2_id"):
                name_to_id[m["player2"].lower().strip()] = m["player2_id"]
            if m.get("tournament_id"):
                key = (m["player1"].lower().strip(), m["player2"].lower().strip())
                match_to_tournament[key] = m["tournament_id"]
                match_to_tournament[(key[1], key[0])] = m["tournament_id"]
            # Fixture winner — pokriva walkover/predaju gdje past-matches nema zapisa
            w_id = str(m.get("winner_id") or "")
            if w_id and w_id != "0":
                winner_name = ""
                if w_id == str(m.get("player1_id", "")):
                    winner_name = m["player1"]
                elif w_id == str(m.get("player2_id", "")):
                    winner_name = m["player2"]
                if winner_name:
                    fkey = (m["player1"].lower().strip(), m["player2"].lower().strip())
                    fixture_winner[fkey] = winner_name
                    fixture_winner[(fkey[1], fkey[0])] = winner_name

    # 1b. Pobjednici iz rezultata TEKUĆE sezone turnira (26.07.2026): /atp/fixtures je
    # čisti raspored i NIKAD ne nosi pobjednika (provjereno sirovim odgovorom), pa je
    # fixture_winner lookup iznad uvijek bio PRAZAN — korak 2b je od 18.07. razriješio
    # 0/421 analiza (kalibracija prazna, hard-revalidacijski okidač slijep), a walkover
    # fallback u koraku 2 nikad nije okinuo. Pobjednike sada vadimo iz
    # /atp/tournament/results/{seasonId} (2 API poziva po turniru) i punimo ISTI
    # fixture_winner lookup, pa oba postojeća potrošača prorade bez daljnjih izmjena.
    # Turnire ograničavamo na one s parovima koje stvarno trebamo razriješiti.
    unresolved_analyzed = []
    try:
        unresolved_analyzed = db.get_unresolved_analyzed_matches(days=8)
        _rows_of_interest = list(db.get_pending_matches()) + list(unresolved_analyzed)
        fixture_winner.update(
            _build_season_winner_lookup(_rows_of_interest, match_to_tournament))
        print(f"Rezultati sezone: {len(fixture_winner) // 2} mečeva s poznatim pobjednikom.")
    except Exception as e:
        print(f"Rezultati sezone preskočeni (greška): {e}")

    # 2. Za svaki pending par provjeri rezultat via past-matches
    pending = db.get_pending_matches()
    print(f"Pronadeno {len(pending)} pending parova za provjeru...")
    for pm in pending:
        p1_name = pm.get("player1", "")
        p2_name = pm.get("player2", "")
        # Kaskada izvora player ID-a (A1, 26.07.2026 — prije je postojao SAMO korak 2):
        #   1) ID spremljen na tiketu (najpouzdanije, bez API poziva)
        #   2) fixtures feed zadnjih 8 dana
        #   3) ATP ranking lista (neovisna o fixtures feedu)
        # Povod: 25.07. je Generali Open Kitzbühel nestao iz fixtures feeda pa Bublik-Halys
        # nikad nije razriješen, dok su Estoril mečevi istog dana prošli normalno.
        p1_id = (pm.get("player1_id") or "").strip() or name_to_id.get(p1_name.lower().strip(), "")
        p2_id = (pm.get("player2_id") or "").strip() or name_to_id.get(p2_name.lower().strip(), "")
        if not p1_id:
            p1_id = find_player_id(p1_name)
        if not p2_id:
            p2_id = find_player_id(p2_name)

        if not p1_id and not p2_id:
            print(f"  Nema player_id ni u tiketu, ni u fixturesima, ni na ranking listi: "
                  f"{p1_name} vs {p2_name}")
            continue

        # Pokušaj via past-matches (normalno) — probaj s oba igrača
        actual_winner, actual_score = "", ""
        if p1_id:
            actual_winner, actual_score = _check_result_via_form(pm, p1_id)
        if not actual_winner and p2_id:
            pm_alt = {**pm, "player1": p2_name, "player2": p1_name}
            actual_winner, actual_score = _check_result_via_form(pm_alt, p2_id)

        # Fallback: walkover/predaja — fixture direktno zna pobjednika
        if not actual_winner:
            fkey = (p1_name.lower().strip(), p2_name.lower().strip())
            actual_winner = fixture_winner.get(fkey, "")
            if actual_winner:
                print(f"  Walkover/predaja detektirana via fixture: {actual_winner}")

        if not actual_winner:
            # Auto-void: ako je meč pending već 3+ dana → walkover/odgoda
            match_date_str = pm.get("match_date", "")
            if match_date_str:
                try:
                    days_old = (datetime.date.today() - datetime.date.fromisoformat(match_date_str)).days
                    if days_old >= 3:
                        db.update_match_result(pm["id"], "void", "Walkover / Odgoda / Nerazriješen")
                        summary["resolved"] += 1
                        print(f"  Auto-void: {p1_name} vs {p2_name} ({days_old} dana pending)")
                        continue
                except ValueError:
                    pass
            print(f"  Jos nije gotov: {p1_name} vs {p2_name}")
            continue

        pick = pm.get("pick", "")
        result = "won" if _names_match(pick, actual_winner) else "lost"

        # Dohvati i trajno spremi statistike meča (sve podloge, pobjeda I poraz) —
        # gradi se korpus "hipoteza prije meča vs stvarni ishod + brojke" za buduće učenje.
        tournament_id = match_to_tournament.get((p1_name.lower().strip(), p2_name.lower().strip()), "")
        # PORAVNANJE PRIJE UPISA (30.08.2026): `get_match_stats_aligned` dokazuje preko
        # ID-eva da blokovi pripadaju NASEM player1/player2 i odbija statistiku ako to ne
        # moze dokazati. Radije prazno polje nego brojke pripisane krivom igracu — iz njih
        # se izvode buduce revizije. Vidi `data_fetcher.align_match_stats`.
        match_stats = {}
        if tournament_id and p1_id and p2_id:
            try:
                match_stats, why = get_match_stats_aligned(tournament_id, p1_id, p2_id)
                match_stats = match_stats or {}
                if not match_stats:
                    print(f"  Statistika odbijena {p1_name} vs {p2_name}: {why}")
            except Exception as e:
                print(f"  Greska dohvata statistike {p1_name} vs {p2_name}: {e}")
        elif not tournament_id:
            print(f"  Bez tournament_id -> nema statistike: {p1_name} vs {p2_name}")

        db.update_match_result(pm["id"], result, actual_winner,
                               actual_score=actual_score or None)
        # Statistike zasebno (best-effort) — ne smiju srušiti upis rezultata
        if match_stats:
            db.save_match_stats(pm["id"], match_stats)
        summary["resolved"] += 1
        summary["won" if result == "won" else "lost"] += 1
        score_str = f" {actual_score}" if actual_score else ""
        print(f"  Azuriran: {p1_name} vs {p2_name} -> {result} ({actual_winner}{score_str})")

    # 2b. Razriješi analyzed_matches (hard revizija 2026-07-18): upiši ishode u ŠIRI
    # korpus analiza, ne samo tiket pickove. Prije ovoga je 419/419 analiza stajalo bez
    # rezultata → kalibracija/revizije su se radile samo na selektiranom uzorku tiketa.
    # Koristi već izgrađeni fixture_winner lookup (zadnjih 8 dana) — 0 dodatnih API poziva.
    try:
        # unresolved_analyzed je dohvaćen u koraku 1b (isti upit) — ne dupliraj poziv
        unresolved = unresolved_analyzed or db.get_unresolved_analyzed_matches(days=8)
        n_resolved = 0
        n_stats = 0
        n_stats_rejected = 0
        for am in unresolved:
            fkey = ((am.get("player1") or "").lower().strip(),
                    (am.get("player2") or "").lower().strip())
            winner = fixture_winner.get(fkey, "")
            if not winner:
                continue
            predicted = am.get("predicted_winner") or ""
            correct = _names_match(predicted, winner) if predicted else None
            # Imena se prosljeđuju radi sanity guarda (31.07.2026) — pobjednik mora biti
            # jedan od dvojice igrača; inače se zapis odbija umjesto da tiho iskrivi korpus.
            if db.update_analyzed_match_result(am["id"], winner, correct,
                                               player1=am.get("player1"),
                                               player2=am.get("player2")):
                n_resolved += 1
                # POST-MATCH STATISTIKA I ZA NE-TIKETNE MEČEVE (05.08.2026, korisnikov
                # zahtjev). Dosad je statistika postojala samo u `ticket_matches`, dakle
                # samo za pickove koji su prošli prag 63% i došli na tiket — selektiran, a
                # time i pristran uzorak. Uvjeti prije meča (`context_snapshot`) i ponašanje
                # u meču tako su živjeli u različitim tablicama i preklapali se samo ondje,
                # pa se korelacija "vlaga/tlak -> postotak prvog servisa" nije mogla računati
                # na punom korpusu. Mečevi koje smo analizirali pa odbacili najvredniji su za
                # učenje jer pokrivaju cijeli raspon, ne samo ono u što smo bili sigurni.
                # Cijena: jedan API poziv po razriješenom meču, nula Claude poziva.
                p1_id, p2_id = am.get("player1_id"), am.get("player2_id")
                tid = match_to_tournament.get(fkey, "")
                if p1_id and p2_id and tid:
                    try:
                        st, why = get_match_stats_aligned(tid, p1_id, p2_id)
                        if st and db.save_analyzed_match_stats(am["id"], st):
                            n_stats += 1
                        elif not st:
                            n_stats_rejected += 1
                            if why and "endpoint" not in why:
                                print(f"  Statistika odbijena (analyzed) "
                                      f"{am.get('player1')} vs {am.get('player2')}: {why}")
                    except Exception:
                        pass   # statistika je bonus — nikad ne smije srušiti razrješavanje
        print(f"Analyzed_matches: razriješeno {n_resolved}/{len(unresolved)} analiza (8 dana), "
              f"statistika spremljena za {n_stats}"
              + (f", odbijena za {n_stats_rejected}." if n_stats_rejected else "."))
        summary["analyzed_resolved"] = n_resolved
    except Exception as e:
        print(f"Analyzed_matches razrješavanje preskočeno (greška): {e}")

    # 2. Ažuriraj statuseve tiketa
    _update_ticket_statuses()

    # 3. Analiziraj izgubljene parove
    lost_matches = db.get_lost_matches_needing_analysis()

    # Build lookup of already-analyzed matches so duplicates can reuse the analysis
    already_analyzed = db.get_analyzed_lost_matches(limit=100)
    analysis_cache: dict[tuple, str] = {}
    for am in already_analyzed:
        key = (am.get("player1","").lower().strip(), am.get("player2","").lower().strip(), am.get("match_date",""))
        if key not in analysis_cache and am.get("loss_analysis"):
            analysis_cache[key] = am["loss_analysis"]

    for lm in lost_matches[:5]:
        p1_key = lm.get("player1", "").lower().strip()
        p2_key = lm.get("player2", "").lower().strip()
        match_key = (p1_key, p2_key, lm.get("match_date",""))

        # Reuse existing analysis for duplicate tickets (same match, different ticket date)
        if match_key in analysis_cache:
            db.save_loss_analysis(lm["id"], analysis_cache[match_key])
            summary["analyzed"] += 1
            print(f"  Kopirano: {lm.get('player1')} vs {lm.get('player2')} (isti meč, drugi tiket)")
            continue

        # SPREMLJENA STATISTIKA IMA PRIORITET (05.08.2026). Prije se uvijek dohvaćalo iznova
        # preko `name_to_id` i `match_to_tournament`, a oboje se gradi iz DANAŠNJEG rasporeda —
        # za meč od prije tjedan dana ti igrači i turnir više nisu u feedu, pa je `stats`
        # ispadao prazan i analiza je ostajala bez brojki. Statistika je ionako već spremljena
        # u `ticket_matches.match_stats` u trenutku razrješavanja meča.
        # Usput rješava i korisnikovu brigu oko recikliranja ID-eva: spremljena statistika i
        # spremljeni `player1_id` zabilježeni su u ISTOM trenutku, pa je njihovo poravnanje
        # interno konzistentno bez obzira što API radi s ID-evima kasnije. (Izmjereno na 66
        # igrača kroz 12 dana: nijedan ID nije promijenio igrača — recikliraju se fixture
        # ID-evi, ne player ID-evi. Ali ovako nam to niti ne mora biti točno.)
        stats = lm.get("match_stats") or {}
        if not stats:
            p1_id = name_to_id.get(p1_key, "")
            p2_id = name_to_id.get(p2_key, "")
            tournament_id = match_to_tournament.get((p1_key, p2_key), "")
            # I OVDJE poravnati put (30.08.2026). Ovo je citac, ne pisac, pa bi stara
            # logika u `_format_match_stats` svejedno poravnala po ID-u — ali time bi u
            # kodu ostala DVA razlicita nacina poravnanja, a jedan od njih bi se lako
            # zaboravio pri sljedecoj izmjeni. Jedan put, jedno pravilo.
            stats = {}
            if p1_id and p2_id and tournament_id:
                stats, _why_ls = get_match_stats_aligned(tournament_id, p1_id, p2_id)
                stats = stats or {}
                if not stats:
                    print(f"  Statistika za analizu gubitka odbijena ({p1_key} vs {p2_key}): {_why_ls}")
        analysis = _analyze_lost_match(lm, stats)
        if analysis:
            db.save_loss_analysis(lm["id"], analysis)
            analysis_cache[match_key] = analysis
            summary["analyzed"] += 1

    # 4. Ažuriraj performance log
    _update_performance_log()

    # 5. Provjeri trebamo li prilagoditi težine (tek nakon 10+ izgubljenih analiza)
    weight_updated = _maybe_update_weights(lost_matches)
    summary["weight_updated"] = weight_updated

    print(f"Večernji update završen: {summary}")
    return summary


def _update_ticket_statuses() -> None:
    """Pregledava tikete s pending statusom i ažurira ih kad su svi parovi riješeni.
    Pravila:
    - Jedan 'lost' = tiket odmah lost (ne čekamo ostale)
    - 'void' parovi se izuzimaju iz računice (walkover/odgoda)
    - Svi non-void parovi won = tiket won
    """
    tickets = db.get_tickets(status="pending")
    for ticket in tickets:
        matches = ticket.get("ticket_matches", [])
        if not matches:
            continue
        lost_count   = sum(1 for m in matches if m.get("result") == "lost")
        won_count    = sum(1 for m in matches if m.get("result") == "won")
        void_count   = sum(1 for m in matches if m.get("result") == "void")
        pending_count = sum(1 for m in matches if m.get("result") == "pending")
        total = len(matches)

        if lost_count > 0:
            db.update_ticket_status(ticket["id"], "lost", 0)
            print(f"  Tiket {ticket.get('ticket_date')}: lost ({lost_count}L, {won_count}W, {void_count} void)")
            continue

        if pending_count > 0:
            continue

        # Svi razriješeni, nema lost — won (void ne blokira)
        actual_win = ticket.get("stake", 50) * ticket.get("total_odds", 1)
        db.update_ticket_status(ticket["id"], "won", actual_win)
        print(f"  Tiket {ticket.get('ticket_date')}: won ({won_count}W, {void_count} void, {total} ukupno)")


def _ratio(won, total) -> str:
    """'35/59 (59.3%)' — API daje sirove brojeve, a model bolje rezonira s postotkom."""
    if won is None or not total:
        return None
    try:
        return f"{won}/{total} ({won / total * 100:.1f}%)"
    except (TypeError, ZeroDivisionError):
        return None


def _format_match_stats(p1: str, p2: str, stats: dict, p1_id=None, p2_id=None) -> str:
    """Formatira post-match statistike u čitljiv blok za Claude prompt.

    POPRAVLJEN BUG (05.08.2026, korisnik tražio provjeru): ova funkcija je od uvođenja
    vraćala PRAZAN STRING za svaki meč, pa analiza gubitka NIKAD nije vidjela statistiku —
    samo rezultat po setovima i vlastito predmečno obrazloženje. Zato su dosadašnje analize
    bile općenite ("vjerojatno je servis popustio") umjesto konkretne ("spasio 3 od 4 break
    lopte, a naš pick 1 od 6").

    Uzrok su bila dva neslaganja imena, oba tiha:
      - tražila je `stats["player1"]` / `["p1"]`, a podaci dolaze pod `player1Stats`;
      - tražila je snake_case (`double_faults`, `break_points_saved`), a API vraća camelCase
        (`doubleFaults`, `breakPointSavedGm`).
    Nijedno polje se nije poklopilo, `lines` je ostao duljine 1 i vraćao se "".
    Provjereno na stvarnom spremljenom meču: izlaz je bio duljine 0.

    Stari nazivi ključeva namjerno se ZADRŽAVAJU kao fallback — ako izvor ikad počne slati
    normalizirani oblik, i dalje radi.
    """
    if not stats:
        return ""
    p1_stats = stats.get("player1Stats") or stats.get("player1") or stats.get("p1") or {}
    p2_stats = stats.get("player2Stats") or stats.get("player2") or stats.get("p2") or {}
    if not p1_stats and not p2_stats:
        return ""

    # PORAVNANJE PO ID-u (05.08.2026) — NIJE kozmetika. Redoslijed igrača u statistici NE
    # prati naš: provjereno na 56 mečeva koji imaju oba podatka, kod 24 (43%) se
    # `player1Stats.player1Id` ne poklapa s našim `player1_id`. Da se statistika pripisuje
    # po poziciji, analiza gubitka bi u gotovo pola slučajeva dobila ZAMIJENJENE brojke i
    # izvela samouvjereno pogrešan zaključak — mjerljivo gore nego da statistike nema.
    # OD 30.08.2026 statistika se poravnava PRI UPISU (`data_fetcher.align_match_stats`) i
    # nosi dokaz u `_align`. Kad taj dokaz postoji I odgovara nasim ID-evima, blokovi su vec
    # u nasem redoslijedu pa se preskace sva logika nize. Ako `_align` postoji ali je za
    # DRUGI par, blok se odbija — ne pogadja se. Stara logika ostaje za retke spremljene
    # prije 30.08.; nista se ne prepisuje unatrag.
    _al = stats.get("_align") or {}
    _trusted = bool(
        _al.get("verified") and p1_id and p2_id
        and str(_al.get("our_p1_id")) == str(p1_id)
        and str(_al.get("our_p2_id")) == str(p2_id)
    )
    if _al.get("verified") and not _trusted:
        return ""

    sid1 = str((p1_stats.get("player1Id") or "")).strip()
    sid2 = str((p2_stats.get("player2Id") or "")).strip()
    if _trusted:
        pass
    elif p1_id and p2_id and sid1 and sid2:
        if sid1 == str(p2_id) and sid2 == str(p1_id):
            p1_stats, p2_stats = p2_stats, p1_stats
        elif sid1 != str(p1_id):
            # ID-evi postoje ali se ne poklapaju ni u jednom smjeru — ne pogađamo.
            return ""
    elif sid1 or sid2:
        # Statistika nosi ID-eve, a mi svoje nemamo (stariji zapisi prije ALTER TABLE-a):
        # orijentacija se ne može provjeriti, pa se blok izostavlja umjesto da se riskira
        # zamjena. Novi zapisi uvijek imaju ID-eve, pa ovo s vremenom nestaje.
        return ""

    def g(s, *keys):
        for k in keys:
            v = s.get(k)
            if v is not None:
                return v
        return None

    def row(label, fn):
        v1, v2 = fn(p1_stats), fn(p2_stats)
        if v1 is None and v2 is None:
            return None
        return f"  {label}: {p1}={v1 if v1 is not None else 'N/A'} | {p2}={v2 if v2 is not None else 'N/A'}"

    rows = [
        row("Ace", lambda s: g(s, "aces")),
        row("Dvostruke greške", lambda s: g(s, "doubleFaults", "double_faults")),
        row("1. servis", lambda s: _ratio(g(s, "firstServe"), g(s, "firstServeOf"))),
        row("Poeni na 1. servisu", lambda s: _ratio(g(s, "winningOnFirstServe"),
                                                    g(s, "winningOnFirstServeOf"))),
        row("Poeni na 2. servisu", lambda s: _ratio(g(s, "winningOnSecondServe"),
                                                    g(s, "winningOnSecondServeOf"))),
        row("Iskorišteni BP", lambda s: _ratio(g(s, "breakPointWonGm"), g(s, "breakPointChanceGm"))),
        row("Sačuvani BP", lambda s: _ratio(g(s, "breakPointSavedGm"), g(s, "breakPointFacedGm"))),
        row("Ukupni poeni", lambda s: g(s, "totalPointsWon", "total_points_won")),
        row("Winneri", lambda s: g(s, "winners")),
        row("Neforsirane greške", lambda s: g(s, "unforcedErrors", "unforced_errors")),
        row("Izlasci na mrežu", lambda s: _ratio(g(s, "netApproaches"), g(s, "netApproachesOf"))),
        # BRZINE SERVISA (05.08.2026): korisnikova ideja br. 6 iz srpnja. Tada je zapisano da
        # brzina servisa "nije dostupna ni na jednom endpointu" — to je bilo tocno ZA
        # PREDIKCIJU (prije meca je ne mozemo znati), ali POSLIJE meca postoji i mi je vec
        # spremamo, samo je nismo citali. Popunjena je u ~38% meceva (veci turniri imaju
        # mjerace), pa se redak izostavlja kad je nema.
        row("Prosj. brzina 1. servisa", lambda s: g(s, "averageFirstServeSpeed")),
        row("Prosj. brzina 2. servisa", lambda s: g(s, "averageSecondServeSpeed")),
        row("Najbrži servis", lambda s: g(s, "fastestServe")),
    ]
    rows = [r for r in rows if r]
    if not rows:
        return ""
    # NAPOMENA: winners/unforcedErrors/netApproaches su kod ovog izvora često null — zato se
    # redak izostavlja kad ga nema, umjesto da se ispisuje "N/A | N/A" i troši prostor prompta.
    return "\nSTATISTIKE MEČA:\n" + "\n".join(rows) + "\n"


# =============================================================================================
# BAZNE STOPE ZA ANALIZU GUBITKA (uvedeno 26.08.2026 15:20)
#
# Izmjereno na hard uzorku pod tezinama v18 (04.-26.08.2026): 178 rijesenih analiza, od toga
# 138 s post-match statistikom (81 dobitak / 57 gubitaka), 139 sa sezonskim statistikama oba
# igraca. Referentna vrijednost je DEVIGIRANA SuperSport cijena (obje strane, marza 5,13%).
#
# ZASTO OVO ULAZI U PROMPT: bez baznih stopa analiza gubitka moze samo pogoditi koja je
# post-match brojka u tom mecu najekstremnija i proglasiti je uzrokom. Od 20 analiza iz
# razdoblja 16.-26.08.2026 tocno JEDNA preporuka je prezivjela provjeru na podacima.
#
# PREMJERITI: nakon US Opena (n bi trebao narasti na ~250-280). Ako se brojke pomaknu za
# vise od nekoliko postotnih bodova, azurirati OVDJE i zabiljeziti u MODEL_CHANGELOG.
#
# OGRADA NA REDAK O R16/QF (28.08.2026 19:58) — NAMJERNO NIJE UPISANA U SAM PROMPT, da
# se tekst koji model cita ne mijenja: oznake rundi jos plutaju. Isti mec je isti dan
# dobio SF pa QF kad je run pokrenut dvaput (`run_daily._verify_late_rounds` dvostruko
# broji danasnje meceve jer im vlastiti jutarnji redak dodje natrag kao "povijest").
# Nalaz nije pao, ali brojku -13,3pp treba premjeriti kad oznake budu stabilne.
_LOSS_BASE_RATES = """
=== MEASURED BASE RATES FROM OUR OWN CORPUS (hard, weights v18, 04.-26.08.2026) ===
Read these BEFORE naming any cause. They tell you what a NORMAL match looks like, so you can
tell a real signal apart from a number that merely looks extreme in this one match.

OUR PICK'S POST-MATCH NUMBERS - average in matches we WON vs matches we LOST (n=138):
  double faults              won 2.93  |  lost 4.60   (opponent's DF: 3.36 vs 3.35 - flat)
  1st-serve points won, gap  won +10.5 |  lost -8.0
  2nd-serve points won, gap  won +10.7 |  lost -9.1   <- SAME size as 1st serve, not "hidden"
  total serve points, gap    won +11.0 |  lost -8.8
  break points converted,gap won +18.0 |  lost -9.7
  total points won, gap      won +13.4 |  lost -9.9
  aces (our pick)            won 7.05  |  lost 7.07   <- no separation at all
Nearly every post-match number separates wins from losses, because the winner wins more
points. That is a DESCRIPTION of the result, not a cause, and never on its own a model fix.

PRE-MATCH SEASON STATS - correlation with whether our pick won (n=139). ALL ARE ZERO:
  serve points won +0.006 | 1st serve won -0.006 | 2nd serve won +0.024 | 1st-serve-in +0.019
  aces/match +0.010 | double faults +0.002 | hold% +0.006 | return points won -0.059
  BP saved +0.009 | BP converted -0.031 | break% -0.052    (every P-value above 0.49)
So: if you want to blame a serve or return statistic, the season numbers do NOT support it.

OTHER MEASURED FACTS:
  - double faults are NOT a stable player trait in our corpus: split-half by player r=+0.131
    (P=0.396), and variation WITHIN a player (SD 1.64) exceeds variation BETWEEN players (1.43)
  - tiebreak record points the OPPOSITE way: r(our TB-rate edge, our pick winning) = -0.186
    (P=0.014, n=174). Picks whose TB record was BETTER went 54.4%; picks whose opponent led
    by 20pp+ went 73.8%. Deciding-set record: r=-0.045, nothing.
  - ELO gap works, but only outside the middle rounds: r=+0.249 in R64/R32, r=-0.033 in R16/QF
  - round R16/QF is our weak spot: -13.3pp vs the devigged market price, vs +3.7pp elsewhere
  - quality of the pick's recent opposition IS predictive: form matters only when it was
    earned against strong opponents (r=+0.284) and not at all against weak ones (r=-0.017)
  - weather main effects are zero (temp -0.092, humidity +0.101, wind +0.076, pressure -0.077)
  - our pick being 4+ years older than the opponent: 42.9%, -15.4pp vs price

INPUTS THE PREDICTION MODEL ALREADY RECEIVES - do NOT recommend adding any of these:
  ELO (overall + surface), ATP ranking and trend, 3-year surface record, form last 5 and 10,
  average opponent ELO, surface form, total serve points won, hold%, 1st-serve %,
  1st-serve points won, 2ND-SERVE POINTS WON, aces per match, BREAK POINTS SAVED,
  BREAK POINTS CONVERTED, return points won, own tiebreak record, deciding-set record,
  matches and sets in last 7 days, days rest, age, height/weight/hand, best round at this
  tournament in 3 seasons, current tournament path, H2H, weather, altitude, venue type,
  local start time and session, court pace, scouting profile, injury news.
A recommendation to "add" something from this list is a factual error, not a finding.
=== END BASE RATES ==="""


def _analyze_lost_match(match: dict, stats: dict = None) -> str:
    """Claude analizira zašto smo pogriješili na konkretnom paru.

    STRUKTURNA MANA — IZMJERENA 26.08.2026 14:01, NIJE POPRAVLJENA (model zamrznut).
    Ovaj prompt vidi isključivo JEDAN GUBITAK: rezultat, post-match statistiku i vlastite
    predmečne bilješke. Nema baznu stopu, ne vidi nijedan DOBITAK, ne zna raspodjelu
    veličine koju optužuje. Takav prompt matematički mora pronaći onu post-match brojku
    koja je u tom meču najekstremnija i proglasiti je uzrokom. To i radi.

    Provjereno na 20 jedinstvenih analiza gubitaka (16.-26.08.2026, sve hard) naspram
    138 mečeva s post-match statistikom (81 dobitak / 57 gubitaka):

      - 10 od 20 analiza traži "drugi servis kao zaseban ulaz, agregat ga maskira".
        Jaz na 1. servisu razdvaja dobitke od gubitaka za 18,5pp, na 2. servisu za 19,8pp,
        agregat za 19,8pp. Drugi servis je ekstremniji od prvog u 54% gubitaka i 56%
        dobitaka — dakle nema nikakve tendencije. Ništa nije skriveno.
        Usput: `2nd serve pts won` je u promptu od početka (predictor.py, redak 333/357),
        pa je preporuka i činjenično netočna.
      - 9 od 20 traži dvostruke greške kao ulaz. Naš pick: 2,93 u dobitcima, 4,60 u
        gubitcima — ali split-half po igraču daje r=+0,131 (P=0,396), a SD unutar igrača
        (1,64) je VEĆI od SD između igrača (1,43). DF je posljedica lošeg dana, ne osobina.
      - 5 traži jače kažnjavanje slabijeg tiebreak rekorda, 3 traže slabije. Podaci:
        r(jaz u TB postotku, pogodak) = -0,186 (P=0,014, n=174) — signal ide u SUPROTNOM
        smjeru od onoga što traži većina.
      - 5 tvrdi "dug odmor = hrđa", 3 tvrde "umor podcijenjen" — u istom tjednu, o istoj
        varijabli, u suprotnim smjerovima. To je potpis šuma, ne kalibracije.
      - Test na tekstu predmečnih bilježaka: nijedna ključna riječ (umor, forma, ELO,
        tiebreak, hrđa, break lopte, hot hand) ne razdvaja dobitke od gubitaka na P<0,05.

    ŠTO SE JEST POTVRDILO: preporuka iz analize Rottgering-Machac (26.08.) da je izuzeće u
    hot-hand pravilu prestrogo. U R16/QF, kad je protivnik odigrao 2+ meča u zadnjih 3-9
    dana, prolazimo 35,0% (n=20) naspram 59,7% očekivano — z=-2,30. Jedna od dvadeset.

    POPRAVAK KOJI SE PREDLAŽE (nije izveden): u prompt dodati bazne stope za veličinu koja
    se optužuje i tražiti izričitu provjeru "je li isto bilo prisutno i u dobitcima".
    Bez toga svaka nova analiza gubitka proizvodi uvjerljivu naknadnu pamet, a mi na
    temelju nje mijenjamo pravila (pravila 4, 13 i 16 su tako i nastala — sva tri mjerena
    26.08. i sva tri idu u krivom smjeru). Vidi MODEL_CHANGELOG 26.08.2026 14:01, točka 1.
    """
    pick = match.get("pick", "")
    actual = match.get("actual_winner", "")
    p1 = match.get("player1", "")
    p2 = match.get("player2", "")
    score = match.get("actual_score", "N/A")
    tournament = match.get("tournament", "")
    surface = match.get("surface", "")
    risk_notes = match.get("risk_notes", "")
    confidence = match.get("confidence", 0)
    key_factors = match.get("key_factors", [])

    stats_block = ""
    if stats:
        # ID-evi su nužni za poravnanje statistike s našim redoslijedom igrača — vidi
        # `_format_match_stats`. Bez njih se blok namjerno izostavlja.
        stats_block = _format_match_stats(p1, p2, stats,
                                          match.get("player1_id"), match.get("player2_id"))

    # Draw povijest + anti-halucinacijsko pravilo (A2, 26.07.2026). Povod: analiza gubitka
    # Van Assche-Carreno-Busta (23.07.) tvrdila je "his 2023 Estoril win", a naša draw baza
    # kaže "2023 R16: Davidovich Fokina def. Van Assche" — dakle taj meč je IZGUBIO, i nikad
    # nije osvojio Estoril (2023. je uzeo Ruud). Feedback prompt dotad nije imao NI draw
    # podatke NI zabranu izmišljanja povijesti, pa je pogrešku iz risk_notes samo pojačao.
    draw_block = "Nema podataka."
    try:
        from agent.predictor import _format_draw_history
        import datetime as _dt
        _rows = db.get_tournament_draw(tournament, _dt.date.today().year - 3)
        if _rows:
            draw_block = _format_draw_history(_rows, p1, p2)
    except Exception as e:
        print(f"  Draw povijest za analizu gubitka nedostupna: {e}")

    base_rates = _LOSS_BASE_RATES

    prompt = f"""A tennis prediction model made an incorrect prediction. Analyse the error.

MATCH: {p1} vs {p2} | {tournament} ({surface})
OUR PREDICTION: {pick} to win (confidence: {confidence}%)
ACTUAL RESULT: {actual} won | Score: {score}
STATED RISKS: {risk_notes}
KEY FACTORS THAT DROVE THE PICK: {', '.join(key_factors) if key_factors else 'N/A'}
{stats_block}
TOURNAMENT DRAW HISTORY (verified API data, last 3 seasons — the ONLY authoritative source
for past results at this event):
{draw_block}

STRICT ANTI-HALLUCINATION RULES:
- Make NO claim about past titles, finals, or results at this tournament unless it appears
  in the draw history above. If the draw history says a player LOST a round, do not describe
  it as a win. If it shows "Nema podataka", make ZERO historical claims.
- The STATED RISKS above were written before the match and may themselves contain errors.
  Do NOT treat them as verified fact and do NOT amplify them — if a stated risk contradicts
  the draw history, say so explicitly; that contradiction is itself a finding worth reporting.
- Do not invent geographic, political, or biographical claims about either player.

{base_rates}

EVIDENCE DISCIPLINE (mandatory - this section overrides your instinct to find a cause):
- You are looking at ONE LOST MATCH. You cannot see the matches we WON. The base rates above
  are the only thing standing between you and a confident wrong answer.
- Post-match statistics explain HOW the match went. They are NOT evidence that the model
  should have known beforehand. Before blaming any number, ask: was this knowable pre-match,
  and does the base-rate block show it separating wins from losses?
- The word "cause" is BANNED unless the factor was visible pre-match AND the base rates
  support it. Otherwise say "post-match description".
- Do not recommend adding an input the model already receives (see the list above).

Write a concise but COMPLETE analysis (~250 words, never leave a sentence unfinished):

1. WHAT WE GOT WRONG - name at most two pre-match factors. For EACH one, end with exactly
   one of these verdicts, and justify it with a number:
     [SIGNAL CONFIRMED]      visible pre-match AND the base rates separate wins from losses
     [SIGNAL NOT CONFIRMED]  the factor is roughly as common in our wins as in our losses
     [SIGNAL CONTRADICTED]   the base rates point the OPPOSITE way to your reading
     [INSUFFICIENT DATA]     not measurable from what we record
     [POST-MATCH ONLY]       real in this match, but not knowable before it

2. HOW THE MATCH WENT - the post-match story, explicitly labelled as description. It is fine
   and useful to say "his second serve collapsed"; it is wrong to call that a model failure.

3. WHAT SHOULD CHANGE - at most ONE proposal, and only if you reached [SIGNAL CONFIRMED] in
   part 1. If you did not, write exactly: "No model change justified by this match." That is
   a complete and correct answer, and it is the RIGHT answer most of the time - the single
   most common error in these analyses has been proposing a fix that the data does not carry.
   If you do propose something, state what it would cost when it fires on a match we would
   have won."""

    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODELS["feedback"],
            # 1600, bilo 1200 (26.08.2026 15:20): izlaz je od danas strukturiran
            # (verdikt po faktoru + obavezno obrazlozenje brojkom), pa treba nesto vise mjesta.
            max_tokens=1600,  # margin za Sonnet high effort (bilo 700 na Haiku)
            output_config={"effort": "high"},  # 18.07.2026
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"Greška analize gubitka: {e}")
        return f"Analiza nije dostupna: {str(e)[:100]}"


# ZAMRZNUTO AUTOMATSKO AŽURIRANJE TEŽINA (05.08.2026, dogovor s korisnikom — opcija B).
#
# Povod: istog dana je popravljen bug zbog kojeg `_format_match_stats` NIKAD nije isporučio
# statistiku meča u prompt (vidi njezin docstring). Analize gubitaka od sada su bitno
# bogatije — a one hrane upravo `_maybe_update_weights`, koja mijenja ŽIVE težine za sve
# buduće predikcije. Model je istog dana zamrznut 3-4 dana radi čiste atribucije (u 48h je
# promijenjeno šest stvari), pa bi tiha promjena težina pokvarila upravo to mjerenje.
#
# Dakle: analize se i dalje generiraju i spremaju u punom obliku (to je ono što korisnik
# želi čitati), ali se prijedlog težina NE primjenjuje automatski. Prijedlog se i dalje
# ISPISUJE u dnevni log, pa se može pregledati prije nego mu se vrati moć.
#
# ODMRZAVANJE: postaviti natrag na True nakon revizije ~08.-09.08.2026. Ovo je jedini
# prekidač — nema drugih mjesta koja diraju težine.
WEIGHTS_AUTO_UPDATE_ENABLED = False


def _maybe_update_weights(lost_matches: list) -> bool:
    """
    Prilagođava težine modela na temelju uzorka grešaka.
    Koristi SVE analizirane gubitke iz baze (ne samo tekući run).
    Potrebno minimalno 5 analiziranih grešaka ukupno.

    Dok je `WEIGHTS_AUTO_UPDATE_ENABLED` False, izračun se preskače u cijelosti — ne troši
    se ni Claude poziv, jer bi prijedlog ionako bio odbačen.
    """
    if not WEIGHTS_AUTO_UPDATE_ENABLED:
        print("  Automatsko ažuriranje težina je ZAMRZNUTO (WEIGHTS_AUTO_UPDATE_ENABLED=False, "
              "05.08.2026) — analize gubitaka se i dalje generiraju i spremaju.")
        return False
    # Only use losses from matches played AFTER the current weights were activated.
    # This ensures we correct the current model, not a previous version.
    weights_active_since = db.get_active_weight_version_date()
    all_analyzed_raw = db.get_analyzed_lost_matches(limit=40)
    all_analyzed_filtered = [m for m in all_analyzed_raw
                              if (m.get("match_date") or "") >= weights_active_since]

    # Deduplicate by (player1, player2, match_date): same match on multiple tickets = 1 loss.
    # If both tickets have an analysis, combine them for a richer learning signal.
    seen: dict[tuple, dict] = {}
    for m in all_analyzed_filtered:
        key = (m.get("player1","").lower().strip(), m.get("player2","").lower().strip(), m.get("match_date",""))
        if key not in seen:
            seen[key] = dict(m)
        else:
            existing = seen[key]
            if m.get("loss_analysis") and existing.get("loss_analysis") and m["loss_analysis"] != existing["loss_analysis"]:
                existing["loss_analysis"] = (
                    existing["loss_analysis"]
                    + f"\n\n[Analysis from ticket {m.get('ticket_date','?')}:]\n"
                    + m["loss_analysis"]
                )
    all_analyzed = list(seen.values())

    if len(all_analyzed) < 5:
        print(f"  Not enough losses under current weights ({len(all_analyzed)}/5, "
              f"weights active since {weights_active_since}).")
        return False

    # Determine dominant surface among recent losses
    from collections import Counter
    surface_counts = Counter(db._surface_key(m.get("surface", "hard")) for m in all_analyzed)
    dominant_surface = surface_counts.most_common(1)[0][0] if surface_counts else "hard"
    # Filter to that surface for a cleaner signal (min 3 losses, else use all)
    surface_losses = [m for m in all_analyzed if db._surface_key(m.get("surface", "hard")) == dominant_surface]
    analysis_pool = surface_losses if len(surface_losses) >= 3 else all_analyzed

    current_weights = db.get_active_weights(dominant_surface)
    matches_with_analysis = [m for m in analysis_pool[:10] if m.get("loss_analysis")]

    if len(matches_with_analysis) < 5:
        return False

    match_blocks = []
    for i, m in enumerate(matches_with_analysis):
        p1 = m.get("player1", "?")
        p2 = m.get("player2", "?")
        pick = m.get("pick", "?")
        actual = m.get("actual_winner", "?")
        conf = m.get("confidence", 0)
        odds = m.get("odds", 0)
        surface = m.get("surface", "?")
        runda = m.get("round", "?")
        tournament = m.get("tournament", "?")
        level = m.get("tournament_level", "")
        fmt = "BoF5" if "Grand Slam" in level else "BoF3"
        risk = m.get("risk_notes", "—")
        factors = m.get("key_factors", [])
        factors_str = "; ".join(factors) if factors else "N/A"
        analysis = m.get("loss_analysis", "")

        block = (
            f"--- LOSS {i+1} ---\n"
            f"Match: {p1} vs {p2} | {tournament} | {surface} | {runda} | {fmt}\n"
            f"Pick: {pick} (confidence: {conf}%, odds: {odds:.2f})\n"
            f"Winner: {actual}\n"
            f"Key factors that drove the pick: {factors_str}\n"
            f"Stated risks beforehand: {risk}\n"
            f"Error analysis: {analysis}"
        )
        match_blocks.append(block)

    matches_section = "\n\n".join(match_blocks)

    # ── Učenje iz DOBITAKA (isti period, ista podloga) ──────────────────────────
    # Daje modelu kontrast: koji su faktorski obrasci proizveli TOČNE tipove, a koji
    # pogrešne. Bez ovoga petlja uči samo iz pogrešaka i vidi pola slike.
    won_raw = db.get_won_matches(limit=60)
    won_filtered = [m for m in won_raw
                    if (m.get("match_date") or "") >= weights_active_since
                    and db._surface_key(m.get("surface", "hard")) == dominant_surface]
    won_seen: dict = {}
    for m in won_filtered:
        k = (m.get("player1", "").lower().strip(), m.get("player2", "").lower().strip(), m.get("match_date", ""))
        if k not in won_seen:
            won_seen[k] = m
    winning_sample = list(won_seen.values())[:10]

    win_blocks = []
    for i, m in enumerate(winning_sample):
        p1 = m.get("player1", "?")
        p2 = m.get("player2", "?")
        pick = m.get("pick", "?")
        conf = m.get("confidence", 0)
        odds = m.get("odds", 0) or 0
        surface = m.get("surface", "?")
        runda = m.get("round", "?")
        tournament = m.get("tournament", "?")
        level = m.get("tournament_level", "")
        fmt = "BoF5" if "Grand Slam" in level else "BoF3"
        score = m.get("actual_score", "") or "N/A"
        factors = m.get("key_factors", [])
        factors_str = "; ".join(factors) if factors else "N/A"
        win_blocks.append(
            f"--- WIN {i+1} ---\n"
            f"Match: {p1} vs {p2} | {tournament} | {surface} | {runda} | {fmt}\n"
            f"Pick: {pick} (confidence: {conf}%, odds: {odds:.2f}) — CORRECT | Score: {score}\n"
            f"Key factors that drove the pick: {factors_str}"
        )
    wins_section = "\n\n".join(win_blocks) if win_blocks else "No resolved wins on this surface under current weights yet."

    prompt = f"""You are an expert in tennis prediction model analysis. Based on {len(matches_with_analysis)} incorrect predictions AND {len(winning_sample)} correct predictions on {dominant_surface}, suggest adjustments to the model weights. Learn from BOTH: identify which factor patterns separate the winning picks from the losing ones.

LOSSES WITH FULL CONTEXT:
{matches_section}

WINNING PREDICTIONS (same surface, same period — what worked):
{wins_section}

CURRENT MODEL WEIGHTS:
{json.dumps(current_weights, indent=2)}

WHAT EACH WEIGHT COVERS:
- elo_ranking: ELO rating, ATP ranking, ranking trend, opponent quality
- surface_style: surface + playing style matchup (clay/hard/grass specialist)
- serve_return: serve%, return%, aces, break points
- recent_form: form over last 5-10 matches across the season (W/L ratio, opponent quality)
- fatigue_injuries: fatigue, injuries, match schedule, travel, days of rest
- h2h_context: H2H record, tournament context, motivation, mental factors
- tournament_trajectory: in-tournament W/L momentum (current run in THIS tournament), hot-hand signal, quality of opponents beaten this week

INSTRUCTIONS:
Compare the LOSSES against the WINNING PREDICTIONS. Look for factors that CONSISTENTLY separate correct picks from incorrect ones — not just what failed in losses, but what was present in wins.
Pay particular attention to:
- Does the same factor appear as an error in 3+ losses while being sound in the wins?
- Is there a factor pattern common to the wins that the losses lacked (or vice versa)?
- Is there a difference in performance between BoF3 and BoF5 formats?
- Is fatigue/form or ELO/ranking consistently mis-weighted?
- Do NOT overfit: if the wins and losses show the same factor pattern, that factor is NOT the differentiator — leave it unchanged.

CONSTRAINTS:
- Max change ±{WEIGHT_ADJUSTMENT['step']}% per factor (use 0.5-1% for weak/unclear patterns, 2-3% for very consistent patterns across 5+ losses)
- Total must remain 100%
- Min weight per factor: {WEIGHT_ADJUSTMENT['min_weight']}%
- Max weight per factor: {WEIGHT_ADJUSTMENT['max_weight']}%
- Change ONLY factors with a clear pattern in the data

Respond ONLY in JSON format:
{{
  "new_weights": {{
    "elo_ranking": 20.0,
    "surface_style": 23.0,
    "serve_return": 18.0,
    "recent_form": 20.0,
    "fatigue_injuries": 14.0,
    "h2h_context": 5.0
  }},
  "reason": "specific explanation — which factor, how many cases, why the change",
  "changed_factors": ["list of changed factors"]
}}

If there is no clear pattern requiring change, return the same weights with reason="No consistent pattern requiring change"."""

    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODELS["feedback"],
            max_tokens=900,  # margin za Sonnet high effort (bilo 500 na Haiku)
            output_config={"effort": "high"},  # 18.07.2026 — mijenja žive težine, najviši utjecaj
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        new_weights = result.get("new_weights", {})
        reason = result.get("reason", "Automatska prilagodba")
        changed = result.get("changed_factors", [])

        # Provjeri da su nove težine validne
        if not _validate_weights(new_weights):
            print("Predložene težine nisu validne, odbačeno.")
            return False

        if not changed or reason == "Nema konzistentnog uzorka za promjenu":
            print("Nema potrebe za promjenom težina.")
            return False

        db.save_new_weights(new_weights, reason, f"Auto-feedback na {len(matches_with_analysis)} analiza", surface=dominant_surface)
        print(f"Težine ažurirane: {reason}")
        return True

    except Exception as e:
        print(f"Greška ažuriranja težina: {e}")
        return False


def _update_performance_log() -> None:
    today = format_date(today_zagreb())
    tickets = db.get_tickets(limit=200)

    total = len([t for t in tickets if t.get("status") != "pending"])
    won = len([t for t in tickets if t.get("status") == "won"])
    lost = len([t for t in tickets if t.get("status") == "lost"])
    pending = len([t for t in tickets if t.get("status") == "pending"])

    total_staked = total * 50.0
    total_returned = sum(t.get("actual_win", 0) or 0 for t in tickets if t.get("status") == "won")
    roi = ((total_returned - total_staked) / total_staked * 100) if total_staked > 0 else 0
    running_balance = total_returned - total_staked

    db.upsert_performance_log({
        "log_date": today,
        "total_tickets": total,
        "won_tickets": won,
        "lost_tickets": lost,
        "pending_tickets": pending,
        "total_staked": total_staked,
        "total_returned": total_returned,
        "roi_percent": round(roi, 2),
        "running_balance": round(running_balance, 2),
    })


def _validate_weights(weights: dict) -> bool:
    if not weights:
        return False
    numeric = {k: v for k, v in weights.items() if isinstance(v, (int, float))}
    total = sum(numeric.values())
    if abs(total - 100.0) > 0.5:
        return False
    for k, v in weights.items():
        if not isinstance(v, (int, float)):
            continue  # skip "surface" string key
        if v < WEIGHT_ADJUSTMENT["min_weight"] or v > WEIGHT_ADJUSTMENT["max_weight"]:
            return False
    return True


def _check_result_via_form(pm: dict, player1_id: str) -> tuple:
    """
    Koristi past-matches endpoint za provjeru rezultata.
    Vraća (ime_pobjednika, rezultat_u_setovima) ako je meč ZAVRŠEN, inače ('', '').

    Rezultat se prihvaća SAMO ako je nađen završen meč protiv tog protivnika na
    DATUM tog tipa (ili +1 dan za kasni/odgođeni završetak). Time se izbjegavaju
    dvije greške:
      1) LIVE meč se ne smije označiti kao gotov — mora imati pobjednika (finished).
      2) Kad isti par igra dvaput u kratkom roku (npr. finale prije 2 dana pa opet
         na Grand Slamu), ne smije se uhvatiti RANIJI susret — datum mora odgovarati.
    """
    p1_name = pm.get("player1", "")
    p2_name = pm.get("player2", "")
    try:
        md = datetime.date.fromisoformat((pm.get("match_date", "") or "")[:10])
    except Exception:
        md = None
    try:
        form = get_recent_form(player1_id, 10)
        for m in form.get("matches", []):
            if not m.get("finished"):
                continue  # live/neodigran meč — nije rezultat
            if not _names_match(m.get("opponent", ""), p2_name):
                continue
            if md is not None:
                try:
                    m_date = datetime.date.fromisoformat((m.get("date", "") or "")[:10])
                except Exception:
                    continue
                # Prihvati samo meč na dan tipa (ili +1 dan za kasni/odgođeni završetak)
                if not (md <= m_date <= md + datetime.timedelta(days=1)):
                    continue
            winner = p1_name if m.get("won") else p2_name
            return winner, (m.get("score", "") or "")
    except Exception as e:
        print(f"  Greska provjere {p1_name} vs {p2_name}: {e}")
    return "", ""


def _names_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    a, b = a.lower().strip(), b.lower().strip()
    if a == b:
        return True
    a_parts = a.split()
    b_parts = b.split()
    if not a_parts or not b_parts:
        return False
    return a_parts[-1] == b_parts[-1]
