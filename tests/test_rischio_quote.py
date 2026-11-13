# -*- coding: utf-8 -*-
"""v7.41 quota di rischio per mercato (portafogli.quote_rischio)."""
import math
import random
import unittest
from datetime import date, timedelta

from cot_radar import portafogli as P


def giorni(n):
    out, d = [], date(2025, 1, 1)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def serie(gg, vol, seme):
    """Prezzi con rendimenti casuali di volatilita' giornaliera `vol` (seme fisso: test ripetibile)."""
    rnd, p, out = random.Random(seme), 100.0, []
    for d in gg:
        p *= 1 + rnd.gauss(0, vol)
        out.append((d, p))
    return out


class QuoteRischio(unittest.TestCase):
    def setUp(self):
        self.gg = giorni(300)
        self.px = {"SPY": serie(self.gg, 0.012, 1), "IEF": serie(self.gg, 0.004, 2), "GLD": serie(self.gg, 0.009, 3),
                   "SHY": [(d, 100.0) for d in self.gg], "SAT": [(d, 100.0) for d in self.gg]}
        self.g = P.Griglia(self.px)

    def test_somma_100_e_liquidita_a_zero(self):
        r = P.quote_rischio(self.g, {"SP500": 0.4, "US10Y": 0.3, "GOLD": 0.1, "CASH": 0.2})
        self.assertAlmostEqual(sum(r["quote"].values()), 100, delta=0.3)
        self.assertNotIn("CASH", r["quote"])
        self.assertEqual(r["giorni"], P.RISCHIO_GIORNI)
        # le azioni (3 volte piu' volatili dei Treasury) portano molto piu' rischio del loro peso
        self.assertGreater(r["quote"]["SP500"], 70)
        self.assertLess(r["quote"]["US10Y"], 15)

    def test_volatilita_di_un_solo_mercato(self):
        r = P.quote_rischio(self.g, {"SP500": 1.0})
        self.assertEqual(r["quote"], {"SP500": 100.0})
        self.assertAlmostEqual(r["vol"], 0.012 * math.sqrt(252) * 100, delta=2.5)

    def test_azioni_scelte_contate_come_sp500(self):
        a = P.quote_rischio(self.g, {"AZ": 0.5, "US10Y": 0.5})
        b = P.quote_rischio(self.g, {"SP500": 0.5, "US10Y": 0.5})
        self.assertEqual(a["quote"]["AZ"], b["quote"]["SP500"])     # il prezzo sintetico (SAT, piatto) non si usa
        self.assertEqual(a["vol"], b["vol"])

    def test_in_euro_il_cambio_aggiunge_rischio(self):
        fx = dict(serie(self.gg, 0.006, 9))                          # dollari per 1 euro, si muove ogni giorno
        fx = {d: v / 100 for d, v in fx.items()}
        usd = P.quote_rischio(self.g, {"US10Y": 1.0})
        eur = P.quote_rischio(self.g, {"US10Y": 1.0}, fx)
        self.assertGreater(eur["vol"], usd["vol"])

    def test_pochi_dati_o_solo_liquidita(self):
        g = P.Griglia({k: v[:40] for k, v in self.px.items()})
        self.assertIsNone(P.quote_rischio(g, {"SP500": 1.0}))
        self.assertIsNone(P.quote_rischio(self.g, {"CASH": 1.0}))


if __name__ == "__main__":
    unittest.main()


class PerditaMeseECambio(unittest.TestCase):
    """v7.57 perdita del mese (1 su 20) e quota di rischio dal cambio."""

    def setUp(self):
        import math
        giorni = [(date(2019, 1, 1) + timedelta(days=i)).isoformat() for i in range(1500)]
        giorni = [d for d in giorni if date.fromisoformat(d).weekday() < 5]
        on = lambda a, per: [(d, 100 * math.exp(0.0002 * i + a * math.sin(i / per))) for i, d in enumerate(giorni)]
        self.g = P.Griglia({"SPY": on(0.10, 9.0), "IEF": on(0.02, 5.0), "GLD": on(0.05, 13.0)})
        self.fx = {d: 1.1 + 0.05 * math.sin(i / 7.0) for i, d in enumerate(giorni)}
        self.fermo = {d: 1.1 for d in giorni}

    def test_perdita_negativa_e_cresce_con_il_rischio(self):
        poco = P.perdita_mese(self.g, {"SP500": 0.2, "CASH": 0.8})
        tanto = P.perdita_mese(self.g, {"SP500": 1.0})
        self.assertLess(tanto, poco)
        self.assertLess(poco, 0)

    def test_sola_liquidita_zero(self):
        self.assertEqual(P.perdita_mese(self.g, {"CASH": 1.0}), 0.0)

    def test_cambio_fermo_quota_zero(self):
        self.assertEqual(P.quota_cambio(self.g, {"SP500": 1.0}, self.fermo), 0)

    def test_cambio_mosso_quota_positiva_e_assente_senza_cambio(self):
        self.assertGreater(P.quota_cambio(self.g, {"US10Y": 1.0}, self.fx), 50)     # mercato calmo: domina il cambio
        self.assertIsNone(P.quota_cambio(self.g, {"SP500": 1.0}, None))


class CodaEVerifica(unittest.TestCase):
    """v7.63: media dei mesi peggiori (Expected Shortfall) e verifica storica della soglia 1 mese su 20."""

    def test_media_peggiori_sotto_la_soglia_e_verifica(self):
        px = P.prezzi_demo("2010-01-01", "2026-11-06")
        g = P.Griglia(px)
        pesi = {"SP500": 0.6, "CASH": 0.4}
        soglia, media = P.coda_mese(g, pesi)
        self.assertIsNotNone(soglia)
        self.assertLessEqual(media, soglia)                     # la media dei mesi peggiori e' sempre piu' bassa
        self.assertEqual(P.perdita_mese(g, pesi), soglia)
        storia = [(g.date[i], pesi) for i in range(800, len(g.date) - 30, 21)]
        v = P.verifica_mese(g, storia)
        self.assertIsNotNone(v)
        self.assertTrue(0 <= v["sup"] <= v["n"])
        self.assertTrue(0 <= v["p"] <= 1)
