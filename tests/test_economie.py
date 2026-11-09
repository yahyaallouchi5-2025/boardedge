# -*- coding: utf-8 -*-
"""v7.21 quadro economico di 6 economie: fase dal CLI dell'OCSE e dall'inflazione, Eurozona come media pesata,
cache che sopravvive a una fonte giu'."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from cot_radar import economie as EC
from cot_radar import quadro as Q


def mesi(dal, valori):
    return {Q.mm(dal, k): v for k, v in enumerate(valori)}


class FaseEconomia(unittest.TestCase):
    def test_quattro_fasi(self):
        su, giu = mesi("2025-01", [99 + k * 0.1 for k in range(12)]), mesi("2025-01", [101 - k * 0.1 for k in range(12)])
        sale, scende = mesi("2025-01", [2 + k * 0.1 for k in range(12)]), mesi("2025-01", [3 - k * 0.1 for k in range(12)])
        self.assertEqual(EC.fase(su, scende, None)["regime"], "Ripresa")
        self.assertEqual(EC.fase(su, sale, None)["regime"], "Espansione")
        self.assertEqual(EC.fase(giu, sale, None)["regime"], "Stagflazione")
        self.assertEqual(EC.fase(giu, scende, None)["regime"], "Recessione")
        self.assertIsNone(EC.fase({}, sale, None))

    def test_allarme_sahm(self):
        cli, cpi = mesi("2025-01", [100] * 20), mesi("2025-01", [2] * 20)
        une = mesi("2025-01", [4.0] * 17 + [4.8] * 3)
        st = EC.fase(cli, cpi, une)
        self.assertTrue(st["allarme"])
        self.assertEqual(st["disoc"], 4.8)

    def test_eurozona_media_pesata(self):
        cli = {p: {"2026-01": 100.0} for p in EC.PESI_EUR}
        cli["DEU"]["2026-01"] = 102.0
        self.assertAlmostEqual(EC.cli_eurozona(cli)["2026-01"], 100 + 2 * EC.PESI_EUR["DEU"], places=4)
        del cli["ESP"]
        self.assertEqual(EC.cli_eurozona(cli), {})              # manca un paese: niente media


class Cache(unittest.TestCase):
    def test_fonte_giu_resta_la_copia(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, EC.FILE), "w") as fh:
                json.dump({"agg": "2020-01-01T00:00+00:00", "cli": {"USA": {"2020-01": 100}}}, fh)
            vero = (EC.scarica_cli, EC.scarica_disoccupazione, EC.scarica_inflazione)
            EC.scarica_cli = lambda get=None: (_ for _ in ()).throw(OSError("giu"))
            EC.scarica_disoccupazione = lambda get=None, oggi=None: {}
            EC.scarica_inflazione = lambda get=None: {"US": {"2020-01": 2.0}}
            try:
                c = EC.aggiorna_cache(d, adesso=datetime(2026, 11, 9, tzinfo=timezone.utc))
            finally:
                EC.scarica_cli, EC.scarica_disoccupazione, EC.scarica_inflazione = vero
            self.assertEqual(c["cli"], {"USA": {"2020-01": 100}})   # CLI giu': resta la copia
            self.assertEqual(c["cpi"], {"US": {"2020-01": 2.0}})


if __name__ == "__main__":
    unittest.main()
