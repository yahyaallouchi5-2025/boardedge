# -*- coding: utf-8 -*-
"""Test del FORECASTER (cot_radar/forecaster.py): niente dati dal futuro, registro in catena, sfidanti coerenti."""
import random
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

from cot_radar import forecaster as F
from cot_radar import portafogli as P


def taglia(px, fino):
    """Prezzi fino alla data 'fino' compresa (come se oggi fosse quel giorno)."""
    return {t: [x for x in pts if x[0] <= fino] for t, pts in px.items()}


class Forecaster(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.px = P.prezzi_demo("2004-01-02", "2026-12-31")

    def tearDown(self):
        shutil.rmtree(self.d)

    def test_somme_dei_pesi(self):
        pesi = {"SP500": 0.5, "GOLD": 0.2, "US10Y": 0.2, "CASH": 0.1}
        for p in (F._inclina(pesi, {"SP500": 1, "GOLD": 1, "US10Y": -1}), F._oro(pesi), F._oro({"SP500": 0.8, "GOLD": 0.2})):
            self.assertAlmostEqual(sum(p.values()), 1.0, places=3)
            self.assertTrue(all(v >= 0 for v in p.values()))
        # liquidita' insufficiente: gli aumenti si riducono, niente leva
        p = F._inclina({"SP500": 0.9, "CASH": 0.1, "GOLD": 0.0}, {"SP500": 1})
        self.assertAlmostEqual(p["SP500"], 1.0, places=3)
        self.assertNotIn("CASH", p)

    def test_ridge_trova_il_verso(self):
        rnd = random.Random(1)
        X = [[rnd.gauss(0, 1) for _ in range(4)] for _ in range(3000)]
        y = [0.01 * x[0] - 0.02 * x[2] + rnd.gauss(0, 0.05) for x in X]
        _, _, beta, _ = F.ridge(X, y)
        self.assertGreater(beta[0], 0)
        self.assertLess(beta[2], 0)
        self.assertLess(abs(beta[1]), abs(beta[2]))

    def test_registro_previsione_poi_esito(self):
        oggi = datetime(2026, 11, 1, 18, tzinfo=timezone.utc)
        out = F.calcola([], taglia(self.px, "2026-10-31"), None, cartella=self.d, adesso=oggi)
        self.assertEqual(out["corrente"]["mese"], "2026-11")
        self.assertFalse(out["corrente"]["in_ritardo"])
        self.assertEqual(out["mesi"], 0)
        # un mese dopo: esito di novembre e previsione di dicembre, catena integra
        out = F.calcola([], taglia(self.px, "2026-11-30"), None, cartella=self.d,
                        adesso=datetime(2026, 12, 1, 7, tzinfo=timezone.utc))
        righe = F.leggi(self.d)
        self.assertEqual([r["tipo"] for r in righe], ["previsione", "esito", "previsione"])
        self.assertTrue(F.catena_ok(righe))
        self.assertEqual(out["mesi"], 1)
        self.assertEqual(out["corrente"]["mese"], "2026-12")
        # il primo mese parte senza costi: il campione rende esattamente la somma pesi x rendimenti
        e, p = righe[1], righe[0]
        r = {k: v / 100 for k, v in e["mercati"].items()}
        for pid, pesi in p["sfidanti"]["campione"].items():
            self.assertAlmostEqual(e["sfidanti"]["campione"][pid] / 100, F.rend_portafoglio(pesi, r), places=4)
        # stesso giro ripetuto: nessuna riga nuova (mai riscritte, mai doppie)
        F.calcola([], taglia(self.px, "2026-11-30"), None, cartella=self.d, adesso=datetime(2026, 12, 1, 9, tzinfo=timezone.utc))
        self.assertEqual(len(F.leggi(self.d)), 3)

    def test_niente_dati_dal_futuro(self):
        # registrazione IN RITARDO (prezzi gia' dentro novembre): previsioni e pesi identici a quelli calcolati
        # con i soli prezzi fino al 30 ottobre
        a = F.calcola([], taglia(self.px, "2026-10-31"), None, cartella=self.d, scrivi=False,
                      adesso=datetime(2026, 11, 1, tzinfo=timezone.utc))["corrente"]
        d2 = tempfile.mkdtemp()
        try:
            b = F.calcola([], taglia(self.px, "2026-11-12"), None, cartella=d2,
                          adesso=datetime(2026, 11, 12, 22, tzinfo=timezone.utc))["corrente"]
        finally:
            shutil.rmtree(d2)
        self.assertEqual(a["mese"], b["mese"])
        self.assertTrue(b["in_ritardo"])
        self.assertEqual(a["pesi"], b["pesi"])
        self.assertEqual([(m["k"], m["stag"], m["mod"]) for m in a["mercati"]],
                         [(m["k"], m["stag"], m["mod"]) for m in b["mercati"]])

    def test_catena_vede_le_modifiche(self):
        F.calcola([], taglia(self.px, "2026-10-31"), None, cartella=self.d, adesso=datetime(2026, 11, 1, tzinfo=timezone.utc))
        righe = F.leggi(self.d)
        self.assertTrue(F.catena_ok(righe))
        righe[0]["mercati"]["SP500"]["stag"] = 1 - righe[0]["mercati"]["SP500"]["stag"]
        self.assertFalse(F.catena_ok(righe))

    def test_giudizi(self):
        self.assertEqual(F.giudizio_sfidante({"2026-11": 0.01}, {"2026-11": 0.0})["verdetto"], "osservazione")
        rnd = random.Random(3)
        c = {f"m{i:02d}": rnd.gauss(0.005, 0.02) for i in range(24)}
        s = {m: v + 0.01 for m, v in c.items()}            # sempre +1% al mese: meglio dimostrato
        self.assertEqual(F.giudizio_sfidante(s, c)["verdetto"], "meglio")
        g = F.giudizio_prev([(1, 0.01)] * 30 + [(-1, -0.02)] * 40)
        self.assertEqual(g["verdetto"], "meglio")            # giusto anche sui ribassi: batte "sempre rialzo"
        g = F.giudizio_prev([(1, 0.01)] * 70)
        self.assertEqual(g["verdetto"], "uguale")            # solo rialzi: identico a "sempre rialzo"


if __name__ == "__main__":
    unittest.main()
