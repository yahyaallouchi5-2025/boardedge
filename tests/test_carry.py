# -*- coding: utf-8 -*-
"""Test del carry trade (cot_radar/carry.py): archivio dei tassi e unione delle serie candidate."""
import os
import shutil
import tempfile
import unittest
from datetime import date

from cot_radar import carry as C


def mesi(dal, n, v):
    """n punti mensili dal mese 'dal' (AAAA-MM) con valore v (numero o funzione dell'indice)."""
    a, m = int(dal[:4]), int(dal[5:7])
    out = []
    for i in range(n):
        out.append([f"{a:04d}-{m:02d}-01", v(i) if callable(v) else v])
        m += 1
        if m == 13:
            a, m = a + 1, 1
    return out


class Tassi(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d)

    def test_archivio_tiene_le_serie_che_non_arrivano(self):
        def scarica(sid, inizio):
            if sid == "IR3TIB01JPM156N":
                raise RuntimeError("serie interrotta")
            return mesi("2020-01", 24, -0.5 if "CH" in sid else 2.0)
        a = C.aggiorna_tassi(scarica, cartella=self.d, oggi=date(2026, 1, 10))
        self.assertIn("IR3TIB01JPM156N", a["errori"])
        self.assertEqual(a["serie"]["IR3TIB01CHM156N"][0][1], -0.5)          # i tassi negativi restano
        # il giorno dopo la serie torna: si aggiorna; quelle salvate non spariscono se un download fallisce
        a2 = C.aggiorna_tassi(lambda s, i: (_ for _ in ()).throw(RuntimeError("giu'")), cartella=self.d,
                              oggi=date(2026, 1, 11))
        self.assertEqual(len(a2["serie"]), len(a["serie"]))
        # stesso giorno: nessun nuovo download
        chiamate = []
        C.aggiorna_tassi(lambda s, i: chiamate.append(s) or [], cartella=self.d, oggi=date(2026, 1, 11))
        self.assertEqual(chiamate, [])

    def test_mensili_preferita_vince_e_buchi_riempiti(self):
        arch = {"serie": {"IR3TIB01JPM156N": mesi("2020-01", 12, 0.1),        # interbancario: fino a dic 2020
                          "IRSTCI01JPM156N": mesi("2020-06", 30, -0.1)}}     # brevissimo: fino a nov 2022
        per_val, ult = C.mensili(arch)
        self.assertEqual(per_val["JPY"]["2020-06"], 0.1)                      # la preferita vince
        self.assertEqual(per_val["JPY"]["2022-11"], -0.1)                     # il buco e' riempito dall'altra
        self.assertEqual(ult["JPY"]["mese"], "2022-11")
        self.assertEqual(ult["JPY"]["fonte"], "IRSTCI01JPM156N")
        self.assertTrue(ult["JPY"]["vecchio"])


if __name__ == "__main__":
    unittest.main()
