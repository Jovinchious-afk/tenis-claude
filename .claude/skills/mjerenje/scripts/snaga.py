# -*- coding: utf-8 -*-
"""Snaga uzorka za edge naspram devigirane cijene (27.09.2026 11:49).

Nastalo uz povijesni laboratorij: pragovi kapije (n=25-40) nisu mogli razlikovati ±5pp.
Ishod jednog picka je 1/0, a cijena p, pa je raspršenost ostatka ~sqrt(p(1-p)).

    python snaga.py --n 30             interval uz n=30 i najmanji edge koji se vidi
    python snaga.py --edge 5           koliko pickova treba da se vidi edge od 5pp
    python snaga.py --n 30 --prag -5   koliko često BESKORISNA varijabla prođe prag "≤ −5pp"
    dodatno: --p 0.65 (tipična cijena naših pickova; zadano)
"""
import argparse
import math
import sys
from statistics import NormalDist

# Windows konzola je cp1252 i pada na "đ"/"č" — ispis uvijek u UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

Z = NormalDist()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int)
    ap.add_argument("--edge", type=float, help="edge u pp")
    ap.add_argument("--prag", type=float, help="prag u pp (npr. -5)")
    ap.add_argument("--p", type=float, default=0.65)
    a = ap.parse_args()
    sd = math.sqrt(a.p * (1 - a.p))
    k80 = Z.inv_cdf(0.95) + Z.inv_cdf(0.80)   # 80% snage, jednostrano 5%
    if a.n:
        se = sd / math.sqrt(a.n)
        print(f"n={a.n}: 95% interval edgea ±{196 * se:.1f}pp; "
              f"najmanji edge koji se vidi uz 80% snage: {100 * k80 * se:.1f}pp")
        if a.prag is not None:
            pr = Z.cdf(-abs(a.prag) / (100 * se))
            print(f"beskorisna varijabla (pravi edge 0) prođe prag {a.prag:+.1f}pp u {100 * pr:.0f}% slučajeva; "
                  f"prava varijabla s edgeom točno {a.prag:+.1f}pp prođe u 50%")
    if a.edge:
        n = (k80 * sd / (abs(a.edge) / 100)) ** 2
        print(f"edge {a.edge:.1f}pp: potrebno ~{math.ceil(n)} pickova (80% snage, jednostrano 5%)")
    if not a.n and not a.edge:
        ap.print_help()


if __name__ == "__main__":
    main()
