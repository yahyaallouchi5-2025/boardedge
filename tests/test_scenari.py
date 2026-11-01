# -*- coding: utf-8 -*-
"""Test di cot_radar/scenari.py: dato precedente (trasformazioni) e reazione tipica (soglie)."""
import unittest
from datetime import date, timedelta
from unittest import mock

from cot_radar import scenari as S


def mensile(valori, inizio=(2025, 1)):
    a, m = inizio
    out = []
    for v in valori:
        out.append([f"{a:04d}-{m:02d}-01", v])
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


class Scenari(unittest.TestCase):
    def test_precedente(self):
        self.assertEqual(S.precedente(mensile([159000, 159254]), "diff"), ("+254 mila", "febbraio 2025"))
        cpi = mensile([100 + i * 0.25 for i in range(13)])               # +3% in 12 mesi
        self.assertEqual(S.precedente(cpi, "yoy")[0], "+3,0% sull'anno")
        self.assertEqual(S.precedente(mensile([100, 100.6]), "mom")[0], "+0,6% sul mese")
        self.assertEqual(S.precedente([["2026-04-01", 3.8]], "livello"), ("+3,8% annualizzato", "T2 2026"))
        self.assertEqual(S.precedente([["2026-10-30", 4.0]], "fed", [["2026-10-30", 3.75]])[0], "tassi attuali 3,75-4,00%")
        self.assertIsNone(S.precedente(mensile([100]), "yoy"))           # serie troppo corta: niente numero

    def test_reazione(self):
        giorni = [(date(2025, 1, 1) + timedelta(days=i)).isoformat() for i in range(40)]
        z = iter([2.0] * 6 + [0.2] * 4)                                   # 6 su 10 sopra 1 = forte
        with mock.patch("cot_radar.notizie.sorpresa_mercato", side_effect=lambda d, s: (next(z), 1.0)):
            r = S.reazione(giorni[:10], [])
        self.assertEqual((r["livello"], r["quota"], r["n"]), ("forte", 60, 10))
        with mock.patch("cot_radar.notizie.sorpresa_mercato", return_value=(0.3, 1.0)):
            self.assertEqual(S.reazione(giorni[:10], [])["livello"], "debole")
        with mock.patch("cot_radar.notizie.sorpresa_mercato", return_value=None):
            self.assertIsNone(S.reazione(giorni, []))                    # niente misure: niente giudizio

    def test_tutte_le_serie_agenda(self):
        from cot_radar.agenda import SERIE
        self.assertEqual(set(SERIE), set(S.COSA))                         # ogni evento dell'agenda ha la sua lettura
        out = S.calcola({}, scarica=False)
        self.assertTrue(all(v["alto"] and v["basso"] for v in out.values()))


if __name__ == "__main__":
    unittest.main()
