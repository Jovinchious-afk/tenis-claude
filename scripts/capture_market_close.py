"""Drugo hvatanje trzisnih cijena — zatvaranje linije (17.08.2026 11:46).

ZASTO POSTOJI
Dnevni run hvata cijene u trenutku slaganja tiketa (~2h prije prvog meca). To je JEDNA
snimka po dogadjaju, pa se iz nje moze izracunati raspon medju kladionicama, ali NE i
kretanje linije. Revizija 17.08.2026 pokazala je zasto je to bitno:

  Nalaz koji je izgledao najjace u cijeloj analizi bio je "SuperSport nasu stranu cijeni
  krace od ostatka svijeta -> pick prolazi 76,9% umjesto 62,8%". Prezivio je split-half
  (Montreal 76,2% n=21, Cincinnati 77,8% n=18), stratifikaciju po trzisnoj vjerojatnosti
  (+15,2pp), i svih 22 kladionica s upotrebljivim uzorkom islo je u isti smjer.
  ALI: povijesne snimke trzista uzete su ~09:55 UTC, a nas screenshot dolazi ~12:00 UTC.
  Kad se vrijeme poravna, efekt slabi tocno onako kako se zabuna uklanja:

      trzisna cijena 3h starija   +18,3pp  (n=81, P=0,090)
      svjezija cijena             +11,4pp  (n=31, P=0,540)
      istovremeno hvatanje         +4,4pp  (n=29, P=0,793)

  Dakle nismo mjerili misljenje SuperSporta nego TRI SATA KRETANJA LINIJE. To nije los
  nalaz — kretanje linije prema jednoj strani je jedan od rijetkih mehanizama koji u
  kladionicama doista predvidja. Samo ga mjerimo slucajno i lose.

STO OVA SKRIPTA RADI
Hvata drugu snimku blizu pocetka meceva i upisuje je u istu tablicu `market_lines`
(kljuc je `event_id,bookmaker,captured_at`, pa se druga snimka doda pored prve, ne preko).
Time se za svaki mec dobiva par (cijena pri slaganju tiketa, cijena pri zatvaranju), iz
kojeg se kretanje moze izracunati NAMJERNO umjesto slucajno.

STO NE RADI
Ne ulazi ni u jednu odluku. Ne mijenja nijedan pick, ne dira selekciju, ne salje mail.
Iskljucivo zapisuje. Ista disciplina kao break lopte (07.08.), dob (15.08.) i trzisni
konsenzus (15.08.): podatak se PRVO mjeri kroz vrijeme, tek onda eventualno ulazi u odluku.
Prije ~17.09.2026 nema smisla nista zakljucivati — treba par stotina parova snimaka.

=============================================================================================
ZASTO JE PRVI RASPORED BIO POGRESAN (izmjereno 22.08.2026 14:50, ispravljeno 15:20)
=============================================================================================
Prvi cron (17.08.2026) bio je JEDAN termin u 14:30 UTC bez ikakvog filtra. Nakon 5 dana
podataka (8.528 redaka, 62 dogadjaja, 61 s dvije+ snimke) pokazalo se da tako postavljen
posao NE MOZE uhvatiti zatvarajucu cijenu:

    samo 5,1% snimljenih redaka bilo je unutar 2h od pocetka meca
    medijan je bio 9,6h prije pocetka
    medijan razmaka izmedju prve i zadnje snimke: 26 SATI

Uzrok: mecevi Cincinnatija pocinju 15:00 UTC i traju do ~03:00 UTC, a `fetch_odds` vraca i
SUTRASNJE meceve. Jedan fiksni termin zato hvata mjesavinu "za dva sata" i "za dva dana".
Posljedica u brojkama: Brier zavrsne cijene 0,1988 naspram 0,1998 pri slaganju tiketa —
prakticki isto. U efikasnom trzistu zavrsna linija JASNO pobjedjuje raniju; kad ne
pobjedjuje, to obicno znaci da je ne mjerimo. Tako je i bilo.

ISPRAVAK: tri termina dnevno (16:30 / 20:30 / 00:30 UTC), svaki s filtrom `--max-hours 2.5`,
da pokriju dnevni, vecernji i kasni val. Trosak ~27 kredita dnevno (~800/mj od 20.000).

=============================================================================================
ZASTO UOPCE MJERITI CIJENU KOJU NE MOZEMO ODIGRATI — CLV (korisnikovo pitanje 22.08.2026)
=============================================================================================
Korisnik je s pravom primijetio: on screenshota kvote u 14h, pokrene tiket odmah, i vise se
tog dana ne vraca. Cijena uhvacena 1-2h prije meca NE MOZE promijeniti nijedan njegov tiket.
To je tocno. Korist je posve druge vrste.

Pitanje "ima li nas model prednost" pokusavamo odgovoriti preko ISHODA. Racun snage na nasim
podacima (bazna stopa 63,5%, SD CLV-a 1,21pp izmjeren na n=55):

    preko ishoda, prednost 2pp  ->  ~4.500 meceva
    preko ishoda, prednost 3pp  ->  ~2.000 meceva
    preko CIJENE, prednost 0,5pp ->    ~46 meceva
    preko CIJENE, prednost 1,0pp ->    ~11 meceva

Uz ~15 analiza dnevno, 2.000 meceva je oko cetiri mjeseca bez prekida. Zato smo u tri
uzastopne revizije zapinjali na "uzorak je premalen" — i ostali bismo ondje.
Ishod jednog meca je grubo mjerilo kvalitete picka; cijena po kojoj smo usli je puno
preciznije mjerilo iste stvari.

STO JE VEC IZMJERENO (na losem hvatanju, dakle samo kao polazna tocka):
    prosjecni CLV = -0,53pp   (kod 41 od 55 pickova zavrsna cijena bila je ISPOD nase
                               implicirane — trziste se u prosjeku mice OD nasih pickova)
    pickovi s CLV>0: 12/14 = 85,7%      pickovi s CLV<=0: 23/41 = 56,1%

OGRADA KOJU TREBA PAMTITI: nas CLV mijesa dvije kuce — kladimo se po SuperSportu, a mjerimo
naspram svjetskog konsenzusa. Cist CLV trazio bi SuperSportovu ZAVRSNU cijenu, koje nema u
Odds APIju. Mjerenje je zato bucnije nego idealno, ali smjer i predznak ostaju upotrebljivi.

STO OVO NE RJESAVA: ako CLV kaze da nemamo prednost, to je informacija a ne lijek — reci ce
nam brze da nesto ne valja, nece nam reci sto.

TROSAK
Tri termina dnevno x ~9 kredita = ~27 dnevno, oko 800 mjesecno naspram plana od 20.000.
Popis turnira (`/sports`) je besplatan.

POKRETANJE
    python scripts/capture_market_close.py --dry-run       # ispisi sto bi se spremilo
    python scripts/capture_market_close.py                 # prozor 2,5h (zadano)
    python scripts/capture_market_close.py --max-hours 0   # bez filtra (stari nacin)
"""
import os
import sys
import argparse
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

import agent.market as mkt
from database import supabase_client as db


DEFAULT_MAX_HOURS = 2.5


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-hours", type=float, default=DEFAULT_MAX_HOURS,
                    help="spremi SAMO mečeve koji počinju unutar toliko sati (0 = sve)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    started = datetime.datetime.now(datetime.timezone.utc)
    print(f"Hvatanje zatvarajucih cijena — {started.strftime('%d.%m.%Y %H:%M')} UTC "
          f"(prozor: {args.max_hours}h)")

    if not os.getenv("ODDS_API_KEY"):
        print("  ODDS_API_KEY nije postavljen — preskacem (ovo nije greska koja rusi run).")
        return 0

    try:
        keys = mkt.active_tennis_keys("atp")
    except Exception as e:
        print(f"  Popis turnira nije dohvacen ({str(e)[:90]}) — nista nije zapisano.")
        return 0

    if not keys:
        print("  Nema aktivnih ATP turnira — nista za hvatanje.")
        return 0
    print(f"  Aktivni turniri: {', '.join(keys)}")

    events = []
    for sk in keys:
        try:
            for ev in mkt.fetch_odds(sk):
                ev["sport_key"] = sk
                events.append(ev)
        except Exception as e:
            print(f"  {sk}: preskocen ({str(e)[:80]})")

    if not events:
        print("  Nijedan dogadjaj nije vracen — nista zapisano.")
        return 0

    rows = mkt.flatten_lines(events)
    if not rows:
        print("  Dogadjaji nemaju upotrebljive h2h cijene — nista zapisano.")
        return 0

    # FILTAR NA PROZOR PRIJE POCETKA (dodan 22.08.2026 15:20 — vidi "ZASTO JE PRVI
    # RASPORED BIO POGRESAN" u docstringu). Bez njega snimka nije zatvarajuca cijena
    # nego prosjek svega sto se tog trenutka nudi, ukljucujuci sutrasnje meceve.
    before = len(rows)
    if args.max_hours and args.max_hours > 0:
        rows = [r for r in rows
                if r.get("hours_to_start") is not None and 0 <= r["hours_to_start"] <= args.max_hours]
    print(f"  Dogadjaja u prozoru: {len({r['event_id'] for r in rows})} "
          f"({before} -> {len(rows)} redaka nakon filtra)")
    if not rows:
        print("  Nijedan mec ne pocinje u tom prozoru — nista zapisano (ovo je normalno).")
        return 0

    hrs = [r["hours_to_start"] for r in rows if r.get("hours_to_start") is not None]
    if hrs:
        soon = sum(1 for h in hrs if h <= 2.0)
        print(f"  Sati do pocetka: min {min(hrs):.1f} / medijan "
              f"{sorted(hrs)[len(hrs) // 2]:.1f} / max {max(hrs):.1f} "
              f"({soon}/{len(hrs)} redaka unutar 2h)")

    if args.dry_run:
        print("  [DRY RUN] Nista nije spremljeno.")
        return 0

    saved = db.save_market_lines(rows)
    print(f"  Zapisano {saved} redaka, {len({r['event_id'] for r in rows})} meceva, "
          f"{len({r['bookmaker'] for r in rows})} kladionica.")
    print(f"  Kredita preostalo: {mkt.LAST_USAGE.get('remaining')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
