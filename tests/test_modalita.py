# -*- coding: utf-8 -*-
"""v7.60 modalita' di mercato (cot_radar/modalita.py)."""
import math
import unittest
from datetime import date, timedelta

from cot_radar import modalita as M


def serie(f, n=2600):
    """n giorni feriali dal 2000 con prezzo f(i)."""
    out, d, i = [], date(2000, 1, 3), 0
    while len(out) < n:
        if d.weekday() < 5:
            out.append((d.isoformat(), f(i)))
            i += 1
        d += timedelta(days=1)
    return out


class Modalita(unittest.TestCase):
    def test_storia_corta_none(self):
        self.assertIsNone(M.calcola({"SPY": serie(lambda i: 100, 500)}))

    def test_pessimismo_dopo_un_drawdown(self):
        # salita lenta, poi drawdown del 20% nelle ultime 60 sedute: prezzo sotto la media a 200 giorni
        r = M.calcola({"SPY": serie(lambda i: 100 * math.exp(0.0003 * i) * (0.8 if i > 2540 else 1))})
        self.assertEqual(r["modo"], "PESSIMISMO")
        self.assertLess(r["dist"], 0)

    def test_eccesso_dopo_uno_strappo(self):
        # oscillazioni regolari, poi +25% nelle ultime 30 sedute: distanza dalla media sopra il suo 80o percentile
        r = M.calcola({"SPY": serie(lambda i: 100 * (1 + 0.03 * math.sin(i / 40)) * (1.25 if i > 2570 else 1))})
        self.assertEqual(r["modo"], "ECCESSO")
        self.assertGreater(r["dist"], r["soglia"])

    def test_storico_conta_i_mesi(self):
        r = M.calcola({"SPY": serie(lambda i: 100 * (1 + 0.05 * math.sin(i / 50)) * math.exp(0.0002 * i))})
        self.assertTrue(r["storico"])
        self.assertTrue(all(len(v) == 4 and v[3] > 0 for v in r["storico"].values()))


if __name__ == "__main__":
    unittest.main()
