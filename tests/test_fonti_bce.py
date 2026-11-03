# -*- coding: utf-8 -*-
"""Test del nuovo tentativo verso la BCE (fonti.get_ecb) e dell'avviso "grave" (calendario.sources_status).
Nessuna rete: http() e' sostituito. Lancia: python -m unittest tests.test_fonti_bce -v"""
import io
import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import fonti  # noqa: E402

CSV = "KEY,TIME_PERIOD,OBS_VALUE\nYC.X,2026-10-27,2.1\n"


def errore(codice):
    return urllib.error.HTTPError("https://bce", codice, "Gateway Time-out", {}, io.BytesIO(b""))


class Riprova(unittest.TestCase):
    def setUp(self):
        self.orig, self.chiamate = fonti.http, []
        fonti.ECB_RIPROVA = (0, 0)                    # niente attese nei test (v6.84: due nuovi tentativi)

    def tearDown(self):
        fonti.http = self.orig

    def finto(self, risposte):
        def http(url):
            self.chiamate.append(url)
            r = risposte.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        fonti.http = http

    def test_504_poi_ok_un_solo_nuovo_tentativo(self):
        self.finto([errore(504), CSV])
        self.assertEqual(fonti.get_ecb("YC", "X", "2026-01-01"), {"YC.X": [["2026-10-27", 2.1]]})
        self.assertEqual(len(self.chiamate), 2)

    def test_due_504_poi_ok_al_terzo(self):
        self.finto([errore(504), errore(504), CSV])
        self.assertEqual(fonti.get_ecb("YC", "X", "2026-01-01"), {"YC.X": [["2026-10-27", 2.1]]})
        self.assertEqual(len(self.chiamate), 3)

    def test_tre_errori_si_rinuncia_dopo_il_terzo(self):
        self.finto([errore(504), errore(504), errore(503), CSV])
        with self.assertRaises(urllib.error.HTTPError):
            fonti.get_ecb("YC", "X", "2026-01-01")
        self.assertEqual(len(self.chiamate), 3)

    def test_connessione_rifiutata_si_riprova(self):
        # v6.84: il 03/11/2026 la BCE non rispondeva proprio (nessun codice HTTP)
        self.finto([urllib.error.URLError(ConnectionRefusedError("rifiutata")), CSV])
        self.assertEqual(fonti.get_ecb("YC", "X", "2026-01-01"), {"YC.X": [["2026-10-27", 2.1]]})
        self.assertEqual(len(self.chiamate), 2)

    def test_404_non_si_riprova(self):
        self.finto([errore(404), CSV])
        with self.assertRaises(urllib.error.HTTPError):
            fonti.get_ecb("YC", "X", "2026-01-01")
        self.assertEqual(len(self.chiamate), 1)


class Paracadute(unittest.TestCase):
    def test_parziale_non_critico_cache_si(self):
        from cot_radar import paracadute
        ok, critici = paracadute.valuta({"fonti": {"cot": "online", "fred": "online", "ecb": "parziale"}}, None)
        self.assertEqual((ok, critici), (True, []))
        ok, critici = paracadute.valuta({"fonti": {"cot": "online", "fred": "online", "ecb": "cache"}}, None)
        self.assertTrue(ok)
        self.assertEqual(len(critici), 1)


class CacheRecente(unittest.TestCase):
    # v6.84: dati BCE salvati da poco = non critico; vecchi o illeggibili = critico come prima
    def test_recente(self):
        from datetime import datetime
        ora = datetime(2026, 11, 3, 13, 0)
        self.assertTrue(fonti._recente("2026-11-03T05:31", 4, ora))
        self.assertTrue(fonti._recente("2026-10-31T05:31", 4, ora))       # venerdi' -> martedi': ok
        self.assertFalse(fonti._recente("2026-10-27T05:31", 4, ora))      # una settimana: critico
        self.assertFalse(fonti._recente(None, 4, ora))


if __name__ == "__main__":
    unittest.main()
