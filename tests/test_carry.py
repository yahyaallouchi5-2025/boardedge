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


class Studio(unittest.TestCase):
    def prezzi(self, seme, mesi=300):
        """Cambi casuali (passeggiata geometrica giornaliera) per le 7 valute contro dollaro."""
        import random
        r = random.Random(seme)
        out = {}
        for v in C.G8[1:]:
            x, pts = 1.0, []
            for i in range(mesi * 21):
                a, m = 2000 + (i // 21) // 12, (i // 21) % 12 + 1
                x *= 1 + r.gauss(0, 0.006)
                pts.append((f"{a:04d}-{m:02d}-{i % 21 + 1:02d}", x))
            out[v] = pts
        return out

    def test_coppie_carry_e_confronto_cot(self):
        ult = {"AUD": {"v": 4.35}, "JPY": {"v": 1.0}, "USD": {"v": 3.9}, "EUR": {"v": 3.7}}
        p = [{"base": "AUD", "quote": "JPY", "label": "BUY"}, {"base": "AUD", "quote": "JPY", "label": "STRONG SELL"},
             {"base": "EUR", "quote": "USD", "label": "SELL"}, {"base": "MXN", "quote": "JPY", "label": "BUY"}]
        C.coppie(p, ult)
        self.assertEqual(p[0]["carry"], 3.35)
        self.assertEqual(p[0]["carry_cot"], "si")          # il BUY incassa
        self.assertEqual(p[1]["carry_cot"], "no")          # il SELL paga
        self.assertNotIn("carry_cot", p[2])                # differenza sotto MIN_CARRY: non conta
        self.assertNotIn("carry", p[3])                    # valuta senza tasso

    def test_casuale_senza_differenze_di_tasso_nessun_vantaggio(self):
        # tassi tutti uguali e cambi casuali: nessuna variante puo' risultare "vantaggio dimostrato"
        per_val = {v: {f"{a:04d}-{m:02d}": 2.0 for a in range(1999, 2026) for m in range(1, 13)} for v in C.G8}
        for seme in (1, 2, 3):
            st = C.studio(per_val, self.prezzi(seme))
            self.assertIsNotNone(st)
            for k, x in st["varianti"].items():
                self.assertNotEqual(x["verdetto"], "si", f"seme {seme}, variante {k}")
                self.assertLess(x["cagr"], 0.5)            # al massimo il rumore, meno i costi

    def test_interessi_pagati_a_chi_tiene_il_tasso_alto(self):
        # cambi fermi: il guadagno e' solo la differenza di tasso meno i costi (~ 3 alte al 5%, 3 basse all'1%)
        fermi = {v: [(f"{2000 + i // 12:04d}-{i % 12 + 1:02d}-28", 1.0) for i in range(120)] for v in C.G8[1:]}
        tassi = {"USD": 3, "EUR": 1, "JPY": 1, "GBP": 5, "CHF": 1, "CAD": 3, "AUD": 5, "NZD": 5}
        per_val = {v: {f"{1999 + i // 12:04d}-{i % 12 + 1:02d}": t for i in range(140)} for v, t in tassi.items()}
        st = C.studio(per_val, fermi)
        cl = st["varianti"]["classico"]
        self.assertAlmostEqual(cl["medio_anno"], 4.0 - C.RICARICO, delta=0.1)
        self.assertEqual([x[0] for x in st["paniere"]["compra"]], ["NZD", "AUD", "GBP"])


if __name__ == "__main__":
    unittest.main()
