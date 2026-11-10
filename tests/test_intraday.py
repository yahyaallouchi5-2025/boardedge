# -*- coding: utf-8 -*-
"""v7.26 grafici intraday: simboli, ultime 5 sedute, serie "Oggi" del ciclo live."""
import unittest

from cot_radar import intraday as I

GIORNO = 86400


class Simboli(unittest.TestCase):
    def test_borse(self):
        self.assertEqual(I.simbolo("AAPL"), ("AAPL.US", 1.0, "eodhd"))
        self.assertEqual(I.simbolo("SHEL.L", "GBP"), ("SHEL.LSE", 0.01, "eodhd"))   # pence -> sterline
        self.assertEqual(I.simbolo("ENI.MI")[2], "yahoo")
        self.assertIsNone(I.simbolo("7203.T"))                                      # Tokyo: niente intraday
        self.assertIsNone(I.simbolo("^GSPC"))


class Sedute(unittest.TestCase):
    def test_ultime_cinque(self):
        base = 1794300000                                   # una seduta per giorno, 7 giorni
        barre = [[base + d * GIORNO + k * 300, 100 + d] for d in range(7) for k in range(3)]
        s = I.sedute(barre)
        self.assertEqual(len({x[1] for x in s}), 5)
        self.assertEqual(s[0][1], 102)


class Oggi(unittest.TestCase):
    def test_accoda_senza_doppioni_e_scarta_ieri(self):
        t0 = 1794330000
        prima = {"AAPL": [[t0 - 20 * 3600, 99.0], [t0 - 900, 100.0]]}             # un punto di ieri, uno di oggi
        s = I.serie_oggi(prima, {"AAPL": [101.0, 98.0, t0], "MSFT": [500.0, 490.0, t0]})
        self.assertEqual(s["AAPL"], [[t0 - 900, 100.0], [t0, 101.0]])
        self.assertEqual(s["MSFT"], [[t0, 500.0]])
        s2 = I.serie_oggi(s, {"AAPL": [101.0, 98.0, t0]})                         # stesso orario: nessun doppione
        self.assertEqual(len(s2["AAPL"]), 2)


if __name__ == "__main__":
    unittest.main()
