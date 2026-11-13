# -*- coding: utf-8 -*-
"""Test dell'archivio orario (cot_radar/orari.py) e della stagionalita' in ora di Roma (stagionalita_orari.py).
Nessuna rete: le risposte EODHD sono finte. Lancia: python -m unittest tests.test_orari -v"""
import os
import shutil
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cot_radar import orari as O, stagionalita_orari as S  # noqa: E402


def ts(*a):
    return int(datetime(*a, tzinfo=timezone.utc).timestamp())


class Candele(unittest.TestCase):
    def test_minuti_in_ore(self):
        b = [{"timestamp": ts(2015, 1, 5, 8, m), "open": 1 + m / 100, "high": 1.5, "low": 0.9 - m / 100,
              "close": 1.1 + m / 100} for m in range(60)]
        b.append({"timestamp": ts(2015, 1, 5, 9, 0), "open": 2, "high": 2, "low": 2, "close": 2})
        ore = O.a_ore(b)
        self.assertEqual(sorted(ore), [ts(2015, 1, 5, 8), ts(2015, 1, 5, 9)])
        o, h, l, c, n = ore[ts(2015, 1, 5, 8)]
        self.assertEqual((o, c, n), (1.0, 1.1 + 59 / 100, 60))      # apertura = primo minuto, chiusura = ultimo
        self.assertAlmostEqual(l, 0.9 - 59 / 100)

    def test_file_andata_e_ritorno(self):
        d = tempfile.mkdtemp()
        try:
            f = os.path.join(d, "X.csv.gz")
            O.scrivi(f, {ts(2020, 1, 1, 0): [1.1, 1.2, 1.0, 1.15, 60]})
            self.assertEqual(O.leggi(f), {ts(2020, 1, 1, 0): [1.1, 1.2, 1.0, 1.15, 60]})
        finally:
            shutil.rmtree(d)


class Download(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_1m_fino_al_2020_poi_orarie_e_ripresa(self):
        chieste = []

        def finto(sym, intervallo, da, a):
            chieste.append((intervallo, da, a))
            if intervallo == "1m" and da >= ts(2019, 1, 1):          # dati a 1 minuto solo dal 2019
                return [{"timestamp": da + 60, "open": 1, "high": 1, "low": 1, "close": 1}]
            if intervallo == "1h":
                return [{"timestamp": ts(2021, 3, 1, 10), "open": 2, "high": 2, "low": 2, "close": 2}]
            return []
        st = {}
        with mock.patch.object(O, "pezzo", finto):
            fatto = O.scarica_simbolo(self.dir, "EURUSD.FOREX", True, st, time.time() + 60, ora=ts(2021, 6, 1))
        self.assertTrue(st["fatto_1m"])
        self.assertTrue(fatto)
        self.assertTrue(all(a - da <= O.PEZZO_1M for i, da, a in chieste if i == "1m"))   # mai oltre 120 giorni
        self.assertTrue(all(a <= O.SOGLIA_1H for i, da, a in chieste if i == "1m"))      # 1m solo fino al 2020
        ore = O.leggi(O.nome_file(self.dir, "EURUSD.FOREX"))
        self.assertEqual(ore[ts(2021, 3, 1, 10)][4], 60)                                 # barra oraria = 60 minuti
        # secondo giro: niente piu' richieste a 1 minuto
        chieste.clear()
        with mock.patch.object(O, "pezzo", finto):
            O.scarica_simbolo(self.dir, "EURUSD.FOREX", True, st, time.time() + 60, ora=ts(2021, 6, 2))
        self.assertFalse([c for c in chieste if c[0] == "1m"])

    def test_errore_si_riprende_dallo_stesso_punto(self):
        st = {}
        with mock.patch.object(O, "pezzo", lambda *a: None):
            O.scarica_simbolo(self.dir, "BTC-USD.CC", True, st, time.time() + 60, ora=ts(2021, 1, 1))
        self.assertFalse(st.get("fatto_1m"))
        self.assertEqual(st.get("fino_1m", O.DAL_1M), O.DAL_1M)


class OraDiRoma(unittest.TestCase):
    def test_ora_legale_giusta(self):
        self.assertEqual(S.controlla_ora_legale([2009, 2015, 2026, 2027]), [])

    def test_stessa_ora_utc_diversa_ora_di_roma(self):
        # 07:00 UTC = 08:00 a Roma d'inverno, 09:00 d'estate: la fascia deve seguire Roma, non l'UTC
        ore = {}
        for g in range(1, 29):
            ore[ts(2025, 1, g, 7)] = [1.0, 1.0, 1.0, 1.01, 60]      # gennaio: sale
            ore[ts(2025, 7, g, 7)] = [1.0, 1.0, 1.0, 0.99, 60]      # luglio: scende
        t = S.calcola_simbolo(ore)["ora"]["tutti"]
        self.assertEqual(t["8"][1], 100.0)                          # tutte le 08 di Roma (gennaio) in rialzo
        self.assertEqual(t["9"][1], 0.0)                            # tutte le 09 di Roma (luglio) in ribasso
        self.assertNotIn("7", t)

    def test_cella_affidabile_solo_se_forte_e_stabile(self):
        forte = [0.1, 0.1, 0.1, -0.1] * 100                        # 75% di rialzi, stabile nelle due meta'
        self.assertTrue(S.cella(forte, 0.5, 24, 200)[7])
        pochi = [0.1] * 30 + [-0.1] * 10
        self.assertFalse(S.cella(pochi, 0.5, 24, 200)[7])          # troppo pochi casi
        instabile = [0.1] * 200 + [-0.1] * 200                      # tutto rialzo prima, tutto ribasso dopo
        self.assertFalse(S.cella(instabile, 0.5, 24, 100)[7])


if __name__ == "__main__":
    unittest.main()
