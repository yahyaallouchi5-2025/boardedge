# -*- coding: utf-8 -*-
"""v7.27 frazionamenti, titoli tolti dalla borsa e prezzi fermi."""
import json
import os
import tempfile
import unittest
from datetime import date
from unittest import mock

from cot_radar import azioni as A
from cot_radar import eventi_titoli as E
from cot_radar import intraday as I
from cot_radar import sorveglianza as S


class Regole(unittest.TestCase):
    def test_codice(self):
        self.assertEqual(E.codice("AAPL"), ("AAPL", "US"))
        self.assertEqual(E.codice("BEZ.L"), ("BEZ", "LSE"))
        self.assertEqual(E.codice("SAP.DE"), ("SAP", "XETRA"))
        self.assertIsNone(E.codice("ENI.MI"))                  # Milano: solo il controllo dei prezzi fermi
        self.assertIsNone(E.codice("^GSPC"))

    def test_rapporto(self):
        self.assertEqual(E.rapporto("10.000000/1.000000"), ("10:1", 0.1))
        self.assertEqual(E.rapporto("1.000000/30.000000"), ("1:30", 30.0))   # raggruppamento
        self.assertIsNone(E.rapporto("1/1"))
        self.assertIsNone(E.rapporto("rotto"))

    def test_ultime_sedute_salta_il_weekend(self):
        self.assertEqual(E.ultime_sedute(date(2026, 11, 9)), ["2026-11-09", "2026-11-06", "2026-11-05"])

    def test_fermi_contro_la_propria_borsa(self):
        ultimi = {"A.L": "2026-11-09", "B.L": "2026-11-09", "C.L": "2026-11-06", "BEZ.L": "2026-10-20",
                  "X": "2026-11-09", "Y": "2026-11-09", "Z": "2026-11-09",
                  "7203.T": "2026-10-01", "6758.T": "2026-10-01", "9984.T": "2026-10-01"}   # festa: tutti fermi
        self.assertEqual(E.fermi(ultimi), {"BEZ.L": "2026-10-20"})

    def test_delistato_solo_se_assente_tra_gli_attivi(self):
        nostri = {"BEZ.L": ("BEZ", "LSE"), "SHEL.L": ("SHEL", "LSE"), "META": ("META", "US"), "SAP.DE": ("SAP", "XETRA")}
        attivi = {"LSE": {"SHEL": "Shell"}, "US": {"META": "Meta"}}
        tolti = {"LSE": {"BEZ": "Beazley", "SHEL": "Vecchia Shell"}, "US": {"META": "Codice riusato"}}
        self.assertEqual(E.delistati(nostri, attivi, tolti), {"BEZ.L": "Beazley"})   # XETRA senza elenco: saltata


class Giro(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.dir, "grezzi"))
        self.el = [{"t": t, "nome": t, "s": "tech", "l": ["x"]} for t in ("NVDA", "AAPL", "MSFT", "BEZ.L", "SHEL.L",
                                                                          "BP.L", "AZN.L")]
        for x in self.el:
            ultimo = "2026-10-15" if x["t"] == "BEZ.L" else "2026-11-09"
            A._scrivi(os.path.join(self.dir, "grezzi", A._nome_file(x["t"]) + ".json"),
                      {"t": x["t"], "agg_full": "2026-11-05", "d": [["2026-10-01", 10.0], [ultimo, 11.0]]})

    def test_split_forza_lo_storico_e_delistati(self):
        split = lambda b, g: [{"code": "NVDA", "exchange": "US", "date": "2026-11-09", "split": "10.000000/1.000000"}] \
            if (b, g) == ("US", "2026-11-09") else []
        def elenco(b, tolti=False):
            if b == "LSE":
                return {"BEZ": "Beazley"} if tolti else {"SHEL": "Shell", "BP": "BP", "AZN": "AstraZeneca"}
            return {} if tolti else {"NVDA": "", "AAPL": "", "MSFT": ""}
        with mock.patch.object(E.eodhd, "attivo", return_value=True):
            ev = E.aggiorna(self.dir, self.el, oggi=date(2026, 11, 9), scarica_elenco=elenco, scarica_split=split)
        self.assertEqual(ev["split"]["NVDA"]["r"], "10:1")
        self.assertEqual(A._leggi(os.path.join(self.dir, "grezzi", "NVDA.json"))["agg_full"], "")
        self.assertEqual(A._leggi(os.path.join(self.dir, "grezzi", "AAPL.json"))["agg_full"], "2026-11-05")
        self.assertEqual(ev["delistati"]["BEZ.L"], {"nome": "Beazley", "ultimo": "2026-10-15"})
        self.assertIn("BEZ.L", ev["fermi"])
        self.assertNotIn("2026-11-09", ev["visti"]["US"])        # la seduta di oggi si ricontrolla
        self.assertIn("2026-11-06", ev["visti"]["US"])
        self.assertEqual(E.sospesi(ev), {"BEZ.L"})
        # secondo giro: nessun nuovo reset dello storico (gia' rifatto) e nessuna chiamata per le sedute gia' viste
        chiamate = []
        with mock.patch.object(E.eodhd, "attivo", return_value=True):
            E.aggiorna(self.dir, self.el, oggi=date(2026, 11, 9), scarica_elenco=elenco,
                       scarica_split=lambda b, g: chiamate.append(g) or [])
        self.assertTrue(all(g == "2026-11-09" for g in chiamate))

    def test_senza_chiave_solo_prezzi_fermi(self):
        ev = E.aggiorna(self.dir, self.el, oggi=date(2026, 11, 9))
        self.assertEqual(ev["fermi"], {"BEZ.L": "2026-10-15"})
        self.assertEqual(ev["split"], {})

    def test_sospeso_fuori_da_vetrina(self):
        A.SOSPESI.clear()
        A.SOSPESI.add("NVDA")
        try:
            self.assertFalse(A.acquistabile("NVDA"))
            self.assertTrue(A.acquistabile("AAPL"))
        finally:
            A.SOSPESI.clear()


class Intraday(unittest.TestCase):
    def test_barre_rettificate_prima_del_frazionamento(self):
        prima, dopo = 1794499200, 1794585600                     # 2026-11-12 e 2026-11-13 ~ 16:00 UTC
        b = I.rettifica([[prima, 1000.0], [dopo, 101.0]], {"data": "2026-11-13", "f": 0.1})
        self.assertEqual(b, [[prima, 100.0], [dopo, 101.0]])
        self.assertEqual(I.rettifica([[prima, 5.0]], None), [[prima, 5.0]])


class Sorveglianza(unittest.TestCase):
    def test_segnala_i_titoli_da_togliere(self):
        from datetime import datetime, timezone
        adesso = datetime(2026, 11, 10, 3, 0, tzinfo=timezone.utc)
        ev = {"delistati": {"BEZ.L": {"nome": "Beazley", "ultimo": "2026-10-15"}},
              "fermi": {"BEZ.L": "2026-10-15", "XYZ": "2026-10-30"}}
        p = S.problemi(adesso, eventi=ev)
        self.assertTrue(any("BEZ.L (Beazley)" in x for x in p))
        self.assertTrue(any("XYZ dal 2026-10-30" in x and "BEZ" not in x for x in p))


if __name__ == "__main__":
    unittest.main()
