# -*- coding: utf-8 -*-
"""v7.25 orari e festivita' delle borse (orari_borse.py): risposta EODHD -> calendario -> aperta/chiusa."""
import unittest
from datetime import datetime, timezone

from cot_radar import live
from cot_radar import orari_borse as O

US = {"Name": "USA Stocks", "Timezone": "America/New_York",
      "TradingHours": {"Open": "09:30:00", "Close": "16:00:00", "WorkingDays": "Mon,Tue,Wed,Thu,Fri"},
      "ExchangeHolidays": {"1": {"Holiday": "Thanksgiving Day", "Date": "2026-11-26", "Type": "official"}}}
XE = {"Name": "XETRA", "Timezone": "Europe/Berlin",
      "TradingHours": {"Open": "09:00:00", "Close": "17:30:00", "WorkingDays": "Mon,Tue,Wed,Thu,Fri"},
      "ExchangeHolidays": {"0": {"Holiday": "Christmas Eve", "Date": "2026-12-24"}}}
CAL = {"agg": "2026-11-10T20:00+00:00", "borse": O.costruisci(lambda b: {"US": US, "XETRA": XE}.get(b))}
U = timezone.utc


class Calendario(unittest.TestCase):
    def test_riassunto_e_milano(self):
        b = CAL["borse"]
        self.assertEqual(b["US"]["apre"], "09:30")
        self.assertEqual(b["US"]["festivi"], {"2026-11-26": "Thanksgiving Day"})
        self.assertEqual(b["MI"]["festivi"], {"2026-12-24": "Christmas Eve"})     # Milano: festivita' di Xetra
        self.assertIsNone(O.riassunto(None))

    def test_thanksgiving_chiusa(self):
        self.assertFalse(O.aperta("US", datetime(2026, 11, 26, 16, 0, tzinfo=U), CAL))
        self.assertTrue(O.aperta("US", datetime(2026, 11, 27, 16, 0, tzinfo=U), CAL))
        self.assertTrue(O.aperta("US", datetime(2026, 11, 26, 16, 0, tzinfo=U), None))   # senza calendario: solo orari

    def test_orari_e_fine_settimana(self):
        self.assertFalse(O.aperta("XETRA", datetime(2026, 11, 10, 7, 30, tzinfo=U), CAL))   # 08:30 a Berlino
        self.assertTrue(O.aperta("XETRA", datetime(2026, 11, 10, 9, 0, tzinfo=U), CAL))
        self.assertFalse(O.aperta("XETRA", datetime(2026, 11, 14, 10, 0, tzinfo=U), CAL))   # sabato
        self.assertFalse(O.aperta("XETRA", datetime(2026, 12, 24, 10, 0, tzinfo=U), CAL))   # vigilia

    def test_ciclo_live_rispetta_le_feste(self):
        self.assertFalse(live.aperta("US", datetime(2026, 11, 26, 16, 0, tzinfo=U), CAL))
        self.assertTrue(live.aperta("US", datetime(2026, 11, 25, 16, 0, tzinfo=U), CAL))


if __name__ == "__main__":
    unittest.main()
