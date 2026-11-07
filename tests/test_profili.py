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


class RicercaWikipedia(unittest.TestCase):
    """v7.7: se Wikidata non trova l'azienda per nome, si cerca su Wikipedia (stesso controllo: quotata, paese)."""

    def test_fallback_wikipedia(self):
        from unittest import mock
        from cot_radar import profili as PR

        def finto_get(url, timeout=40):
            if "wbsearchentities" in url:
                return {"search": []}                            # Wikidata non la trova
            if "list=search" in url:
                return {"query": {"search": [{"title": "JD.com"}, {"title": "Altro"}]}}
            if "prop=pageprops" in url:
                return {"query": {"pages": {"1": {"title": "JD.com", "pageprops": {"wikibase_item": "Q123"}},
                                            "2": {"title": "Altro", "pageprops": {"wikibase_item": "Q999"}}}}}
            return {}

        def finto_sparql(q):
            return [{"item": {"value": "http://www.wikidata.org/entity/Q123"}, "paese": {"value": "http://www.wikidata.org/entity/Q148"},
                     "nb": {"value": "1"}, "ni": {"value": "0"}},
                    {"item": {"value": "http://www.wikidata.org/entity/Q999"}, "nb": {"value": "0"}, "ni": {"value": "0"}}]
        with mock.patch.object(PR, "_get", finto_get), mock.patch.object(PR, "_sparql", finto_sparql), \
                mock.patch.object(PR, "PAUSA", 0):
            self.assertEqual(PR.per_nome([("9618.HK", "JD.com, Inc.")]), {"9618.HK": "Q123"})
            # paese sbagliato (Cina per un titolo USA) -> scartato
            self.assertEqual(PR.per_nome([("JD", "JD.com, Inc.")]), {})
