# -*- coding: utf-8 -*-
"""v7.22 dividendi: riassunto della risposta EODHD e rendimento al prezzo del giorno."""
import unittest
from datetime import date

from cot_radar import dividendi as DV


class Riassunto(unittest.TestCase):
    def test_trimestrale(self):
        js = [{"date": f"{a}-{m:02d}-07", "value": 0.25 if a < 2026 else 0.27, "currency": "USD"}
              for a in range(2020, 2027) for m in (2, 5, 8, 11) if (a, m) <= (2026, 8)]
        r = DV.riassunto(js, date(2026, 11, 9))
        self.assertEqual(r["freq"], 4)
        self.assertAlmostEqual(r["u12"], 0.25 + 3 * 0.27, places=4)     # novembre 2025 dentro la finestra
        self.assertEqual(r["valuta"], "USD")
        self.assertEqual(r["anni"], 6)                                  # 2020-2025 tutti con dividendo
        self.assertEqual(r["cagr5"], 0.0)
        self.assertEqual(r["ultimi"][0]["d"], "2026-08-07")
        self.assertEqual(len(r["storia"]), 10)

    def test_nessun_dividendo_e_risposta_vuota(self):
        r = DV.riassunto([], date(2026, 11, 9))
        self.assertEqual((r["u12"], r["freq"], r["anni"]), (0, 0, 0))
        self.assertIsNone(DV.riassunto(None, date(2026, 11, 9)))


if __name__ == "__main__":
    unittest.main()
