# -*- coding: utf-8 -*-
"""v7.51 rischio_esteso: Sortino, peggiori 12 mesi, asimmetria, capitale scambiato e costo annuo."""
import unittest
from datetime import date, timedelta
from cot_radar import portafogli as P


def curva(rend_giorno, giorni=800):
    d, v, out = date(2015, 1, 1), 100.0, []
    for i in range(giorni):
        v *= 1 + rend_giorno(i)
        out.append(((d + timedelta(days=i)).isoformat(), v))
    return out


class RischioEsteso(unittest.TestCase):
    def test_corta(self):
        self.assertIsNone(P.rischio_esteso(curva(lambda i: 0.0, 100)))

    def test_valori(self):
        c = curva(lambda i: 0.002 if i % 3 else -0.003)          # sale piano, scende ogni 3 giorni
        r = P.rischio_esteso(c, None, [("2015-01-01", None), ("2015-02-01", 0.5), ("2016-02-01", 0.5)])
        self.assertGreater(r["sortino"], 0)
        self.assertIsNotNone(r["peggiori12"])
        # 1 = 100% scambiato in ~2,2 anni -> circa 46% l'anno; costo = scambiato x COSTO
        self.assertAlmostEqual(r["scambiato_anno"], round(1.0 / (799 / 365.25) * 100), delta=1)
        self.assertAlmostEqual(r["costo_anno"], r["scambiato_anno"] * P.COSTO, delta=0.01)

    def test_asimmetria_negativa(self):
        # quasi sempre piccoli guadagni, un crollo raro: asimmetria negativa
        c = curva(lambda i: -0.25 if i == 400 else 0.0008)
        self.assertLess(P.rischio_esteso(c)["asimmetria"], 0)


if __name__ == "__main__":
    unittest.main()


class Code(unittest.TestCase):
    def test_cvar_e_dd(self):
        c = curva(lambda i: -0.06 if i % 100 == 0 else 0.0005, 1500)       # un crollo ogni ~3 mesi
        r = P.rischio_esteso(c)
        self.assertLess(r["cvar_mese"], 0)
        self.assertLess(r["dd_1su10"], 0)
