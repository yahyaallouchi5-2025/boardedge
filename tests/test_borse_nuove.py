# -*- coding: utf-8 -*-
"""v7.23 nuove borse dell'Azionario: Londra (FTSE 100), Toronto (S&P/TSX 60), Sydney (S&P/ASX 50)."""
import io
import json
import unittest
from unittest import mock

from cot_radar import azioni as A
from cot_radar import eodhd
from cot_radar import live


class Aree(unittest.TestCase):
    def test_giro_giusto_per_ogni_borsa(self):
        self.assertEqual(A.area("BHP.AX"), "asia")          # Sydney chiude di notte: giro asiatico
        self.assertEqual(A.area("SHEL.L"), "europa")
        self.assertEqual(A.area("RY.TO"), "usa")            # Toronto chiude con Wall Street
        self.assertEqual(A.area("^AXJO"), "asia")
        self.assertEqual(A.area("^FTSE"), "europa")
        self.assertEqual(A.area("^GSPTSE"), "usa")

    def test_elenco_e_listini(self):
        el = A.elenco()
        conta = {l: sum(l in x["l"] for x in el) for l in ("ftse100", "tsx60", "asx50")}
        self.assertTrue(all(n >= 40 for n in conta.values()), conta)
        settori = {s[0] for s in A.SETTORI}
        self.assertTrue(all(x["s"] in settori for x in el))
        self.assertEqual(len({x["t"] for x in el}), len(el))   # nessun ticker doppio


class Simboli(unittest.TestCase):
    def test_eodhd(self):
        self.assertIsNone(eodhd.simbolo("SHEL.L"))          # Londra resta a Yahoo (pence)
        self.assertEqual(eodhd.simbolo("RY.TO"), "RY.TO")
        self.assertEqual(eodhd.simbolo("BHP.AX"), "BHP.AU")
        self.assertEqual(eodhd.VALUTA["AU"], "AUD")


class Pence(unittest.TestCase):
    def test_londra_in_sterline(self):
        ts = [1700000000 + 86400 * k for k in range(30)]
        js = {"chart": {"result": [{"meta": {"currency": "GBp", "shortName": "Shell"}, "timestamp": ts,
                                    "indicators": {"quote": [{"close": [2500.0 + k for k in range(30)]}]}}]}}
        with mock.patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(js).encode())):
            meta, pts = A.scarica("SHEL.L", tentativi=1, attesa=0)
        self.assertEqual(meta["valuta"], "GBP")
        self.assertAlmostEqual(pts[0][1], 25.0)


class EconomieBorsa(unittest.TestCase):
    def test_sei_economie(self):
        righe = [{"t": "SHEL.L", "s": "ener", "tr": 1, "pt": 70}, {"t": "RY.TO", "s": "fin", "tr": -1, "pt": 40},
                 {"t": "BHP.AX", "s": "mat", "tr": 1, "pt": 60}]
        e = A.economie_borsa(righe, [{"t": "^FTSE", "n": "FTSE 100", "tr": 1}])
        self.assertEqual(e["gbr"]["settori"]["ener"], {"n": 1, "su": 1, "pt": 70})
        self.assertEqual(e["can"]["settori"]["fin"]["su"], 0)
        self.assertIn("mat", e["aus"]["settori"])
        self.assertEqual(e["gbr"]["indici"][0]["n"], "FTSE 100")


class OrariLive(unittest.TestCase):
    def test_sydney(self):
        from datetime import datetime, timezone
        self.assertTrue(live.aperta("AU", datetime(2026, 11, 10, 1, 0, tzinfo=timezone.utc)))    # 12:00 a Sydney
        self.assertFalse(live.aperta("AU", datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)))


class CicloLive(unittest.TestCase):
    def test_qualche_borsa_aperta(self):
        from datetime import datetime, timezone
        self.assertTrue(live.qualche_borsa_aperta(datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc)))    # Europa + USA
        self.assertTrue(live.qualche_borsa_aperta(datetime(2026, 11, 11, 1, 0, tzinfo=timezone.utc)))     # Sydney
        self.assertFalse(live.qualche_borsa_aperta(datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)))   # sabato


if __name__ == "__main__":
    unittest.main()
