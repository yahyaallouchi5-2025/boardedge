# -*- coding: utf-8 -*-
"""Test di cot_radar/paesi.py: ordine, stato crescita/decrescita, tendenza, ripiego sulla copia salvata."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

from cot_radar import paesi as PA


class Paesi(unittest.TestCase):
    PIL = {"IND": {"2025": 7.8, "2026": 7.0, "2027": 7.0}, "SAU": {"2025": 4.6, "2026": -3.3, "2027": 7.9},
           "BRA": {"2025": 2.3, "2026": 2.2, "2027": 1.9}, "CHN": {"2025": 5.0, "2026": 4.5}}   # Cina senza 2027
    INF = {"IND": {"2026": 5.0}, "SAU": {"2026": 1.9}}

    def test_calcolo(self):
        r = PA.calcola(self.PIL, self.INF, 2026)
        self.assertEqual([x["iso"] for x in r], ["IND", "BRA", "SAU"])      # dal PIL piu' alto; Cina esclusa
        sau = r[2]
        self.assertEqual(sau["stato"], "decrescita")
        self.assertAlmostEqual(sau["tend"], 11.2)                            # accelera
        self.assertLess(r[1]["tend"], 0)                                     # Brasile rallenta
        self.assertIsNone(r[1]["inf"])                                       # inflazione mancante = None, non 0

    def test_copia_se_fmi_giu(self):
        d = tempfile.mkdtemp()
        copia = os.path.join(d, "paesi_fmi.json")
        with open(copia, "w") as f:
            json.dump({"pil": self.PIL, "inf": self.INF, "agg": "2026-10-20"}, f)
        with mock.patch.object(PA, "COPIA", copia), mock.patch.object(PA, "_scarica", side_effect=OSError):
            out = PA.carica(adesso=datetime(2026, 11, 1, tzinfo=timezone.utc))
        self.assertTrue(out["copia"])
        self.assertEqual(out["agg"], "2026-10-20")
        self.assertEqual(len(out["paesi"]), 3)
        with mock.patch.object(PA, "COPIA", os.path.join(d, "manca.json")), \
                mock.patch.object(PA, "RISERVA", os.path.join(d, "manca2.json")):
            self.assertIsNone(PA.carica(scarica=False))

    def test_riserva_completa(self):
        # la riserva nel codice copre i 24 paesi anche nel 2027 (serve il 2028 come "anno prossimo")
        with mock.patch.object(PA, "COPIA", "/non/esiste.json"):
            for anno in (2026, 2027):
                out = PA.carica(scarica=False, adesso=datetime(anno, 6, 1, tzinfo=timezone.utc))
                self.assertEqual(len(out["paesi"]), 24)


if __name__ == "__main__":
    unittest.main()


class Borsa(unittest.TestCase):
    """v7.67 numeri di borsa di un paese dall'ETF (rendimenti, tendenza, volatilita' breve e lunga, regime)."""
    def _serie(self, n=1600, passo=0.001):
        from datetime import date, timedelta
        d, v, out = date(2020, 1, 1), 100.0, []
        for i in range(n):
            v *= 1 + passo + (0.01 if i % 2 else -0.01)
            out.append(((d + timedelta(days=i)).isoformat(), v))
        return out, d + timedelta(days=n - 1)

    def test_numeri(self):
        from cot_radar import paesi
        pts, oggi = self._serie()
        b = paesi.borsa(pts, oggi)
        self.assertTrue(b["su"])                                   # serie che sale: sopra la media a 200 sedute
        self.assertGreater(b["a1"], b["m1"])
        self.assertAlmostEqual(b["vb"], b["vl"], delta=1.0)        # stessa oscillazione ogni giorno: breve = lunga
        self.assertIn(b["reg"], ("calma", "normale", "agitata"))

    def test_prezzi_fermi_o_corti(self):
        from datetime import timedelta
        from cot_radar import paesi
        pts, oggi = self._serie()
        self.assertIsNone(paesi.borsa(pts, oggi + timedelta(days=30)))   # prezzi fermi: nessun numero
        self.assertIsNone(paesi.borsa(pts[:100], oggi))

    def test_paese_senza_etf(self):
        from cot_radar import paesi
        pts, oggi = self._serie()
        d = paesi.aggiungi_borse({"paesi": [{"iso": "CHN"}, {"iso": "HUN"}]}, lambda t: pts, oggi)
        self.assertEqual(d["borse"], 1)
        self.assertIn("b", d["paesi"][0])
        self.assertNotIn("b", d["paesi"][1])
