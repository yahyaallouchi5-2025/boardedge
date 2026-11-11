# -*- coding: utf-8 -*-
"""v7.40 ciclo del debito USA: regole, trimestri e storia sui dati reali FRED (tests/fixture/debito_fred.txt)."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from cot_radar import debito as D

QUI = os.path.dirname(__file__)


def serie_reali():
    """Le serie trimestrali dal file di prova, nella forma della cache."""
    with open(os.path.join(QUI, "fixture", "debito_fred.txt"), encoding="utf-8") as fh:
        riga = [x for x in fh if not x.startswith("#")][0]
    S = {k: {} for k in ("CMDEBT", "TBSDODNS", "GDP", "FEDFUNDS", "T10Y2Y", "CPIAUCSL", "BAA10Y", "BAA10Y_max")}
    q = "1986-T1"
    for x in riga.strip().split(";"):
        p = x.split(",")
        if p[0]:
            S["CMDEBT"][q], S["TBSDODNS"][q] = float(p[0]) * 1000, 0.0
        if p[1]:
            S["GDP"][q] = float(p[1])
        for k, i in (("FEDFUNDS", 2), ("T10Y2Y", 3), ("CPIAUCSL", 4), ("BAA10Y", 5), ("BAA10Y_max", 6)):
            S[k][q] = float(p[i])
        q = D.tt(q, 1)
    return S


class Trimestri(unittest.TestCase):
    def test_trim_e_spostamento(self):
        self.assertEqual(D.trim("2026-11-11"), "2026-T4")
        self.assertEqual(D.tt("2026-T1", -1), "2025-T4")
        self.assertEqual(D.tt("2025-T4", 12), "2028-T4")

    def test_riduci(self):
        p = [["2026-01-10", 1.0], ["2026-03-30", 3.0], ["2026-04-01", 5.0]]
        self.assertEqual(D.riduci(p, "ultimo"), {"2026-T1": 3.0, "2026-T2": 5.0})
        self.assertEqual(D.riduci(p, "media")["2026-T1"], 2.0)
        self.assertEqual(D.riduci(p, "max")["2026-T1"], 3.0)


class Regole(unittest.TestCase):
    #                        deb  deb3 deb1 reale curva fed1 spread max  6m
    def test_ordine_delle_regole(self):
        self.assertEqual(D.fase_regole(150, 140, 148, 1.0, -0.2, 0.5, 5.0, 6.0, 3.0)[0], "Crisi")       # stress vince
        self.assertEqual(D.fase_regole(150, 140, 148, 1.0, -0.2, 0.5, 1.7, 1.9, 1.6)[0], "Picco")
        self.assertEqual(D.fase_regole(150, 140, 148, -3.0, -0.2, 2.5, 1.7, 1.9, 1.6)[0], "Picco")      # Fed in rialzo rapido
        self.assertEqual(D.fase_regole(140, 150, 142, 0.4, 0.4, -0.5, 1.5, 1.6, 1.6)[0], "Riduzione del debito")
        self.assertEqual(D.fase_regole(150, 140, 148, -1.0, 1.5, 0.0, 1.7, 1.9, 1.6)[0], "Bolla")
        self.assertEqual(D.fase_regole(150, 148, 149.5, -1.0, 1.5, 0.0, 1.7, 1.9, 1.6)[0], "Espansione")

    def test_stress_per_salto_dello_spread(self):
        self.assertEqual(D.fase_regole(150, 148, 149.5, -1.0, 1.5, 0.0, 2.6, 2.8, 1.9)[0], "Crisi")


class Storia(unittest.TestCase):
    def setUp(self):
        self.S = serie_reali()
        self.st = dict(D.storia(self.S))

    def test_episodi_noti(self):
        # trimestre del debito -> fase nota il trimestre dopo
        self.assertEqual(self.st["2004-T2"], "Bolla")                    # bolla del credito immobiliare
        self.assertEqual(self.st["2006-T3"], "Picco")                    # curva piatta, Fed al 5,25%
        self.assertEqual(self.st["2008-T3"], "Crisi")                    # Lehman
        self.assertEqual(self.st["2011-T2"], "Riduzione del debito")     # il debito privato scende rispetto al PIL
        self.assertEqual(self.st["2020-T1"], "Crisi")                    # pandemia
        self.assertEqual(self.st["2023-T2"], "Picco")                    # curva invertita, tasso reale positivo

    def test_oggi_e_tabella(self):
        x = D.lettura(self.S, "2026-T2", "2026-T4")
        self.assertEqual(x["fase"], "Riduzione del debito")
        self.assertAlmostEqual(x["debito"], 139.3, 1)
        self.assertLess(x["deb3"], 0)
        spx = {q: 100.0 * 1.02 ** i for i, q in enumerate(sorted(self.S["BAA10Y"]))}
        t = D.tabella(D.storia(self.S), spx)
        self.assertEqual(set(t), set(D.FASI))
        self.assertTrue(all(v[2] == 100 for v in t.values()))            # prezzi sempre in salita: 100% positivi


class Cache(unittest.TestCase):
    def test_calcola_dalla_cache_senza_rete(self):
        d = tempfile.mkdtemp()
        S = serie_reali()
        S["TDSP"] = {"2025-T4": 11.3, "2026-T2": 11.1}
        with open(os.path.join(d, D.FILE), "w", encoding="utf-8") as fh:
            json.dump({"agg": "2026-11-11T08:00+00:00", "serie": S}, fh)
        out = D.calcola(d, scarica_ora=True, adesso=datetime(2026, 11, 11, 10, 0, tzinfo=timezone.utc),
                        get=lambda *a: self.fail("la cache e' fresca: non si scarica"))
        self.assertEqual(out["fase"], "Riduzione del debito")
        self.assertEqual(out["trimestre"], "2026-T2")
        self.assertEqual(out["mercato"], "2026-T4")
        self.assertEqual(out["storia"][-1], ["2026-T4", D.FASI.index("Riduzione del debito")])
        self.assertEqual(out["da"], "2025-T1")
        self.assertEqual(out["rata"], 11.1)

    def test_serie_fallita_tiene_la_copia(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, D.FILE), "w", encoding="utf-8") as fh:
            json.dump({"agg": "2020-01-01T00:00+00:00", "serie": serie_reali()}, fh)

        def get(sid, since):
            raise RuntimeError("FRED giu'")
        out = D.calcola(d, adesso=datetime(2026, 11, 11, 10, 0, tzinfo=timezone.utc), get=get)
        self.assertEqual(out["fase"], "Riduzione del debito")

    def test_senza_dati_niente_riga(self):
        self.assertIsNone(D.calcola(None, scarica_ora=False))


if __name__ == "__main__":
    unittest.main()
