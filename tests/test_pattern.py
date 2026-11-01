# -*- coding: utf-8 -*-
"""Test del Pattern Detector (cot_radar/pattern.py). Nessuna rete.
Lancia: python -m unittest tests.test_pattern -v"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import pattern as P  # noqa: E402


def cand(ts, o, c):
    return (ts, o, max(o, c) + 0.5, min(o, c) - 0.5, c)


class Pattern(unittest.TestCase):
    def test_buy_con_assorbimento(self):
        # candela 1 SELL 110->100, candele 2 e 3 BUY, la 3 chiude a 112 > apertura della 1 (110)
        c = [cand(0, 110, 100), cand(1, 100, 105), cand(2, 105, 112)]
        self.assertEqual(P.trova(c), [(2, "BUY")])
        # se la candela 3 non supera l'apertura della 1: nessun segnale
        c[2] = cand(2, 105, 109)
        self.assertEqual(P.trova(c), [])

    def test_sell_simmetrico(self):
        c = [cand(0, 100, 110), cand(1, 110, 104), cand(2, 104, 97)]
        self.assertEqual(P.trova(c), [(2, "SELL")])
        c[1] = cand(1, 110, 112)                       # candela 2 rialzista: non e' il pattern
        self.assertEqual(P.trova(c), [])

    def test_h4_scarta_la_candela_aperta(self):
        # v6.70: H4 allineate a New York. 5 gennaio 2026 (ora solare, NY = UTC-5): 17:00 NY = 22:00 UTC.
        t0 = 1767650400                                        # lunedi' 5/1/2026 22:00 UTC = 17:00 New York
        ore = [(t0 + h * 3600, 1, 2, 0.5, 1.5) for h in range(10)]   # 17-21 e 21-01 NY chiuse, 01-05 aperta
        x = P.h4(ore, adesso=t0 + 10 * 3600)
        self.assertEqual([g[0] for g in x], [t0, t0 + 4 * 3600])

    def test_h4_ora_legale_e_weekend(self):
        # ora legale (luglio, NY = UTC-4): le candele partono alle 21 UTC; la domenica sera (apertura forex alle 17 NY)
        # la prima H4 e' intera: nessuna candela di un'ora sola
        dom = 1783890000                                       # domenica 12/7/2026 21:00 UTC = 17:00 New York
        ore = [(dom + h * 3600, 1, 2, 0.5, 1.5) for h in range(8)]
        x = P.h4(ore, adesso=dom + 8 * 3600)
        self.assertEqual([g[0] for g in x], [dom, dom + 4 * 3600])
        # barra oraria del venerdi' dopo le 17 di New York (Yahoo): scartata, il venerdi' finisce con la H4 13-17
        ven = dom - 2 * 86400 - 4 * 3600                       # venerdi' 10/7 13:00 New York
        ore = [(ven + h * 3600, 1, 2, 0.5, 1.5) for h in range(5)]  # 13, 14, 15, 16 e 17 (fuori orario)
        x = P.h4(ore, adesso=dom)
        self.assertEqual([g[0] for g in x], [ven])

    def test_quotidiane_scarta_le_mensili(self):
        # v6.59b: Yahoo con range=max restituisce candele mensili: vanno riconosciute e scartate
        mensili = [(i * 30 * 86400, 1, 2, 0.5, 1.5) for i in range(60)]
        daily = [(i * 86400 + (2 * 86400 if i % 5 == 4 else 0), 1, 2, 0.5, 1.5) for i in range(60)]
        self.assertFalse(P.quotidiane(mensili))
        self.assertTrue(P.quotidiane(daily))

    def test_statistica_e_giro(self):
        c = [cand(0, 110, 100), cand(1, 100, 105), cand(2, 105, 112)] + [cand(3 + i, 112 + i, 113 + i) for i in range(6)]
        a = P.analizza(c, 2)
        self.assertEqual(a["stat"]["n"], 1)
        self.assertEqual(a["stat"]["vinti"], 100)
        self.assertEqual(a["ultimo"]["lato"], "BUY")
        self.assertEqual(a["ultimo"]["livello"], 110)
        d = tempfile.mkdtemp()
        try:
            serie = [(i * 3600, 1.0 + i * 0.001, 1.01 + i * 0.001, 0.99 + i * 0.001, 1.0 + i * 0.001) for i in range(800)]
            out = P.esegui(d, scarica=lambda t, i, p: serie if not t.startswith("XAU") else None,
                           adesso=800 * 3600 + 86400, pausa=0)
            self.assertIsNone(out["anomalia"])
            ids = [x["id"] for x in out["strumenti"]]
            self.assertIn("XAUUSD", ids)                                 # spot assente: si usa il future
            self.assertEqual([x for x in out["strumenti"] if x["id"] == "XAUUSD"][0]["fonte"], "GC=F")
            # Yahoo giu': restano le copie del giro prima e scatta l'anomalia
            out2 = P.esegui(d, scarica=lambda *a: None, pausa=0)
            self.assertIsNotNone(out2["anomalia"])
            self.assertEqual(len(out2["strumenti"]), len(out["strumenti"]))
            self.assertTrue(json.load(open(os.path.join(d, "pattern.json")))["anomalia"])
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()


class StudioStorico(unittest.TestCase):
    """v6.59: su prezzi CASUALI lo studio non deve trovare un vantaggio (niente falsi positivi)."""
    def test_casuale_nessun_vantaggio(self):
        import random
        from cot_radar import pattern as PT
        import math
        random.seed(7)
        serie, m = [], 60
        sg = 0.007 / m ** 0.5
        for k in range(12):                      # prezzi casuali "veri": martingala con 60 passi dentro la candela
            p, c, t = 100.0, [], 946684800
            for i in range(3000):
                p *= math.exp(random.gauss(0, 0.001))
                o = h = l = p
                for _ in range(m):
                    p *= math.exp(random.gauss(0, sg) - sg * sg / 2)
                    h, l = max(h, p), min(l, p)
                c.append((t + i * 86400 + k, o, h, l, p))
            serie.append(("forex", c))
        st = PT.studio(serie)
        self.assertEqual(st["verdetto"], "nessun_vantaggio")
        t1 = st["varianti"]["1R"]["tutti"]
        self.assertGreater(t1["n"], 1000)
        self.assertLess(t1["r_medio"], 0.05)

    def test_stop_prima_del_target(self):
        from cot_radar import pattern as PT
        # BUY: candela 1 giu', 2 e 3 su con chiusura sopra l'apertura della 1; poi una candela che tocca stop e target
        c = [(0, 10, 10.1, 9.5, 9.6), (86400, 9.6, 9.9, 9.55, 9.8), (172800, 9.8, 10.3, 9.7, 10.2),
             (259200, 10.2, 11.5, 9.0, 10.0)]
        ops = PT.operazioni(c, "forex", 1)
        self.assertEqual(len(ops), 1)
        self.assertLess(ops[0][1], -0.99)               # stop (ipotesi prudente) meno i costi
