# -*- coding: utf-8 -*-
"""Test di cot_radar/notizie_az.py (v7.15): notizie dei titoli da EODHD, senza rete.
Lancia: python -m unittest tests.test_notizie_az -v"""
import os
import sys
import tempfile
import unittest
from datetime import date
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import eodhd as E, notizie_az as N  # noqa: E402


class Notizie(unittest.TestCase):
    def test_pulisci(self):
        js = [{"date": "2026-11-06T10:00:00+00:00", "title": "Apple sale", "link": "https://www.reuters.com/a",
               "content": "TESTO LUNGO", "sentiment": {"polarity": 0.81}},
              {"date": "2026-11-05T10:00:00+00:00", "title": "apple SALE", "link": "https://x.com/b"},     # doppione
              {"date": "2026-09-01T10:00:00+00:00", "title": "Vecchia", "link": "https://x.com/c"},        # > 30 giorni
              {"date": "2026-11-04T10:00:00+00:00", "title": "Senza link", "link": ""}]
        out = N.pulisci(js, date(2026, 11, 8))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0], {"d": "2026-11-06", "titolo": "Apple sale", "link": "https://www.reuters.com/a",
                                  "fonte": "reuters.com", "tono": 0.81})
        self.assertNotIn("content", out[0])               # mai il testo dell'articolo

    def test_aggiorna_solo_titoli_eodhd(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"EODHD_API_KEY": "finta"}), \
                mock.patch.object(E, "get", return_value=[]) as g:
            r = N.aggiorna(d, el=[{"t": "AAPL"}, {"t": "ENI.MI"}], oggi=date(2026, 11, 8))
        self.assertEqual(r["aggiornati"], 1)                # Milano non e' su EODHD
        g.assert_called_once()


class TrimestriConcettoRecente(unittest.TestCase):
    """v7.15: tra i concetti SEC dei ricavi vince quello con i dati piu' recenti (non il primo della lista)."""

    def test_concetto_piu_recente(self):
        from cot_radar import fondamentali as F
        r = lambda ini, fine, v: {"start": ini, "end": fine, "val": v, "form": "10-Q", "filed": fine}
        fatti = {"facts": {"us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [r("2019-01-01", "2019-03-31", 1)]}},
            "Revenues": {"units": {"USD": [r("2026-04-01", "2026-06-30", 9)]}}}}}
        self.assertEqual(F._periodi(fatti, F.RICAVI), {("2026-04-01", "2026-06-30"): 9})
