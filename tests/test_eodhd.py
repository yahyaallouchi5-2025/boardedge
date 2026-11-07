# -*- coding: utf-8 -*-
"""Test di cot_radar/eodhd.py (v6.97): EODHD fonte principale, Yahoo di riserva. Nessuna rete: risposte finte.
Lancia: python -m unittest tests.test_eodhd -v"""
import os
import sys
import unittest
from datetime import date, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import azioni as A, eodhd as E, portafogli as P  # noqa: E402


def barre(n, dal=date(2026, 1, 1)):
    """n giorni feriali di risposta EODHD finta (prezzo che sale piano)."""
    out, d, v = [], dal, 100.0
    while len(out) < n:
        if d.weekday() < 5:
            v *= 1.001
            out.append({"date": d.isoformat(), "close": round(v, 4), "adjusted_close": round(v, 4)})
        d += timedelta(days=1)
    return out


class Simboli(unittest.TestCase):
    def test_mappa_yahoo_eodhd(self):
        self.assertEqual(E.simbolo("AAPL"), "AAPL.US")
        self.assertEqual(E.simbolo("BRK-B"), "BRK-B.US")
        self.assertEqual(E.simbolo("SAP.DE"), "SAP.XETRA")
        self.assertEqual(E.simbolo("MC.PA"), "MC.PA")
        self.assertEqual(E.simbolo("BTC-USD"), "BTC-USD.CC")
        self.assertEqual(E.simbolo("^GSPC"), "GSPC.INDX")
        for t in ("ENI.MI", "7203.T", "0005.HK", "600519.SS", "RELIANCE.NS", "HG=F", "^VIX"):
            self.assertIsNone(E.simbolo(t), t)               # non coperti: restano a Yahoo

    def test_senza_chiave_niente_eodhd(self):
        with mock.patch.dict(os.environ, {"EODHD_API_KEY": ""}):
            self.assertFalse(E.attivo())
            self.assertIsNone(E.get("eod/AAPL.US"))


class FontePrincipale(unittest.TestCase):
    def test_min_punti_incrementale(self):
        self.assertEqual(A.min_punti("1d", "5d"), 1)          # il download incrementale porta pochi prezzi
        self.assertEqual(A.min_punti("1d", "2y"), 20)
        self.assertEqual(A.min_punti("1mo", "max"), 12)

    def test_eodhd_prima_yahoo_riserva(self):
        yahoo = mock.Mock(return_value=({"valuta": "USD"}, [("2026-11-06", 1.0)]))
        with mock.patch.dict(os.environ, {"EODHD_API_KEY": "finta"}), mock.patch.object(A, "scarica", yahoo), \
                mock.patch.object(E, "get", return_value=barre(5)):
            meta, pts = A.scarica_auto("AAPL", "1d", "5d")
            self.assertEqual(meta["fonte"], "eodhd")
            self.assertEqual(len(pts), 5)
            yahoo.assert_not_called()
            A.scarica_auto("ENI.MI", "1d", "5d")              # Milano: EODHD non lo copre -> Yahoo
            yahoo.assert_called_once()
        with mock.patch.dict(os.environ, {"EODHD_API_KEY": "finta"}), mock.patch.object(A, "scarica", yahoo), \
                mock.patch.object(E, "get", return_value=None):
            A.scarica_auto("AAPL", "1d", "5d")                # EODHD non risponde -> Yahoo
            self.assertEqual(yahoo.call_count, 2)

    def test_pausa_solo_con_yahoo(self):
        with mock.patch.dict(os.environ, {"EODHD_API_KEY": "finta"}):
            self.assertEqual(A.pausa_per("AAPL", (1.5, 3.0)), 0)
            self.assertEqual(A.pausa_per("7203.T", (1.5, 3.0)), (1.5, 3.0))

    def test_etf_portafoglio(self):
        with mock.patch.dict(os.environ, {"EODHD_API_KEY": "finta"}), \
                mock.patch.object(E, "get", return_value=barre(300)), \
                mock.patch.object(P, "scarica_yahoo") as yahoo:
            self.assertEqual(len(P.scarica_auto("SPY")), 300)
            yahoo.assert_not_called()
            P.scarica_auto("HG=F")                            # future: Yahoo
            yahoo.assert_called_once_with("HG=F")

    def test_cerca_eur_preferisce_xetra(self):
        risp = [{"Code": "CSPX", "Exchange": "LSE", "Currency": "USD"}, {"Code": "SXR8", "Exchange": "F", "Currency": "EUR"},
                {"Code": "SXR8", "Exchange": "XETRA", "Currency": "EUR"}]
        with mock.patch.dict(os.environ, {"EODHD_API_KEY": "finta"}), mock.patch.object(E, "get", return_value=risp):
            self.assertEqual(E.cerca_eur("IE00B5BMR087"), "SXR8.XETRA")


if __name__ == "__main__":
    unittest.main()
