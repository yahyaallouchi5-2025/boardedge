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
