# -*- coding: utf-8 -*-
"""Test di cot_radar/profili.py (v6.73): varianti del ticker, nome pulito, scelta dell'ISIN."""
import unittest

from cot_radar import profili as P


class Profili(unittest.TestCase):
    def test_varianti(self):
        self.assertEqual(P.varianti("0300.HK"), ["0300", "300"])           # Hong Kong con e senza zeri
        self.assertEqual(P.varianti("BAJAJ-AUTO.NS"), ["BAJAJ-AUTO"])      # India: il trattino resta
        self.assertIn("BRK.B", P.varianti("BRK-B"))                         # USA: trattino -> punto

    def test_nome(self):
        self.assertEqual(P.pulisci_nome("Bajaj Auto Ltd."), "Bajaj Auto")
        self.assertEqual(P.pulisci_nome("Brunello Cucinelli S.p.A."), "Brunello Cucinelli")
        self.assertEqual(P.pulisci_nome("Baycurrent, Inc."), "Baycurrent")

    def test_isin(self):
        self.assertEqual(P.scegli_isin(["US0000000001", "JP3240400006"], "2801.T"), "JP3240400006")
        self.assertEqual(P.scegli_isin(["KYG875721634"], "0700.HK"), "KYG875721634")
        self.assertIsNone(P.scegli_isin(["corto"], "AAPL"))                # ISIN non valido: niente


if __name__ == "__main__":
    unittest.main()
