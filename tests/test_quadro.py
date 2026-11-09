# -*- coding: utf-8 -*-
"""v7.20 quadro economico: regola di Sahm, fasi e allarme."""
import unittest
from cot_radar import quadro as Q


def serie(dal, valori):
    """[[data, valore]] mensile a partire da dal ('AAAA-MM')."""
    return [[Q.mm(dal, k) + "-01", v] for k, v in enumerate(valori)]


class QuadroEconomico(unittest.TestCase):
    def test_sahm_e_mese_mancante(self):
        une = Q.mensile(serie("2024-01", [4.0] * 20 + [4.9] * 3))
        self.assertAlmostEqual(Q.sahm(une, "2025-11"), 0.9, places=6)
        del une["2025-10"]                                   # mese senza dato: si salta, niente errore
        self.assertIsNotNone(Q.sahm(une, "2025-11"))

    def test_fasi_e_allarme(self):
        n = 30
        cpi = serie("2024-01", [100 * 1.002 ** k for k in range(n)])                      # inflazione costante
        cpi_su = serie("2024-01", [100 * (1.001 + 0.0002 * k) ** k for k in range(n)])   # inflazione in salita
        ind_su = serie("2024-01", [100 + k for k in range(n)])
        ind_giu = serie("2024-01", [200 - k for k in range(n)])
        une = serie("2024-01", [4.0] * n)
        tassi = serie("2024-01", [4.0] * n)
        f = lambda c, i, u=une: Q.calcola({"CPIAUCSL": c, "INDPRO": i, "UNRATE": u, "DGS10": tassi, "DGS2": tassi})
        self.assertEqual(f(cpi_su, ind_su)["regime"], "Espansione")
        self.assertEqual(f(cpi_su, ind_giu)["regime"], "Stagflazione")
        self.assertFalse(f(cpi_su, ind_su)["allarme"])
        sale = serie("2024-01", [4.0] * (n - 3) + [4.8] * 3)                      # disoccupazione su di 0,8
        q = f(cpi_su, ind_su, sale)
        self.assertTrue(q["allarme"])
        self.assertEqual(q["regime"], "Stagflazione")                             # Sahm >= 0,5: la crescita e' giu'

    def test_stato_inflazione(self):
        cpi = serie("2024-01", [100 * 0.999 ** k for k in range(30)])                     # prezzi in calo
        tassi = serie("2024-01", [4.0] * 30)
        q = Q.calcola({"CPIAUCSL": cpi, "INDPRO": serie("2024-01", [100] * 30), "UNRATE": serie("2024-01", [4.0] * 30),
                       "DGS10": tassi, "DGS2": tassi})
        self.assertEqual(q["tipo_infl"], "Deflazione")

    def test_dati_mancanti(self):
        self.assertIsNone(Q.calcola({}))


if __name__ == "__main__":
    unittest.main()
