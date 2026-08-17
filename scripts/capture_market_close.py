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

TROSAK
Jedan poziv po turniru, `regions` x `markets` kredita (3 uz zadane postavke). Uz 2-3
aktivna turnira to je ~9 kredita po pokretanju, dakle ~270 mjesecno naspram plana od
20.000. Popis turnira (`/sports`) je besplatan.
"""
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

import agent.market as mkt
from database import supabase_client as db


def main() -> int:
    started = datetime.datetime.now(datetime.timezone.utc)
    print(f"Hvatanje zatvarajucih cijena — {started.strftime('%d.%m.%Y %H:%M')} UTC")

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

    # Koliko je blizu pocetka snimljeno — to je jedini pokazatelj je li ovo doista
    # "zatvarajuca" cijena ili je run okinuo prerano.
    hrs = [r["hours_to_start"] for r in rows if r.get("hours_to_start") is not None]
    if hrs:
        soon = sum(1 for h in hrs if h is not None and h <= 2.0)
        print(f"  Sati do pocetka: min {min(hrs):.1f} / medijan "
              f"{sorted(hrs)[len(hrs) // 2]:.1f} / max {max(hrs):.1f} "
              f"({soon} redaka unutar 2h od pocetka)")

    saved = db.save_market_lines(rows)
    print(f"  Zapisano {saved} redaka, {len({r['event_id'] for r in rows})} meceva, "
          f"{len({r['bookmaker'] for r in rows})} kladionica.")
    print(f"  Kredita preostalo: {mkt.LAST_USAGE.get('remaining')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
