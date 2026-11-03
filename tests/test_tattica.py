# -*- coding: utf-8 -*-
"""Test della lettura tattica (cot_radar/tattica.py). Lancia: python -m unittest tests.test_tattica -v"""
import math
import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import tattica as T  # noqa: E402


def serie(f, n=400):
    d0 = date(2025, 1, 1)
    return [((d0 + timedelta(days=i)).isoformat(), f(i)) for i in range(n)]


class Tattica(unittest.TestCase):
    def test_trend_pulito_al_rialzo(self):
        x = T.lettura(serie(lambda i: 100 * math.exp(0.001 * i) * (1 + 0.002 * math.sin(i))))
        self.assertGreater(x["pend"], 20)                       # ~+29% annuo
        self.assertGreater(x["r2"], 0.9)
        self.assertEqual(x["txt_trend"], "trend rialzista pulito")
        self.assertGreater(x["rsi"], 50)
        self.assertGreater(x["d200"], 0)

    def test_rsi_estremi(self):
        self.assertEqual(T.rsi([float(i) for i in range(1, 40)]), 100.0)
        self.assertLess(T.rsi([float(100 - i) for i in range(40)]), 1)

    def test_parte_alta_del_canale(self):
        # serie laterale con un balzo finale: prezzo molto sopra la retta
        x = T.lettura(serie(lambda i: 100 + (0.5 if i % 2 else -0.5) + (6 if i == 399 else 0)))
        self.assertGreaterEqual(x["z"], 1.5)
        self.assertEqual(x["txt_canale"], "parte alta del canale")
        self.assertEqual(x["pos"], 100)

    def test_storico_corto_niente_lettura(self):
        self.assertIsNone(T.lettura(serie(lambda i: 100.0 + i, n=150)))


if __name__ == "__main__":
    unittest.main()
