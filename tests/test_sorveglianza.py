# -*- coding: utf-8 -*-
"""v7.24 sorveglianza: regole che decidono quando avvisare l'admin."""
import unittest
from datetime import datetime, timezone

from cot_radar import sorveglianza as S

MAR = datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc)      # martedi', borsa aperta
OK_STATO = {"creato": "2026-11-10 05:40:00", "esito": "ok"}
OK_IND = {"generato": "2026-11-10 12:00", "anomalia": None}
OK_LIVE = {"quando": MAR.timestamp() - 600}


class Archivio(unittest.TestCase):
    """v7.66 serie ferme: l'S&P 500 d'archivio rimasto al 23/10 va segnalato, i dati normali no."""
    def test_serie_ferme(self):
        arch = {"yahoo/_GSPC.csv": ["2026-10-23", 1], "yahoo/SPY.csv": ["2026-11-09", 1],
                "DEXUSEU.csv": ["2026-10-30", 1], "CPIAUCSL.csv": ["2026-09-01", 30], "COT.csv": ["2026-11-03", 7]}
        self.assertEqual(S.archivio_fermo(MAR, arch), [("yahoo/_GSPC.csv", "2026-10-23")])
        p = S.problemi(MAR, OK_STATO, OK_IND, OK_LIVE, archivio=arch)
        self.assertTrue(any("serie ferme" in x and "_GSPC" in x for x in p))

    def test_orari_fermi(self):
        self.assertEqual(S.problemi(MAR, OK_STATO, OK_IND, OK_LIVE, orari={"agg": "2026-11-10 03:40"}), [])
        p = S.problemi(MAR, OK_STATO, OK_IND, OK_LIVE, orari={"agg": "2026-11-07 03:40"})
        self.assertTrue(any("oraria non ricalcolata" in x for x in p))


class Regole(unittest.TestCase):
    def test_tutto_regolare(self):
        self.assertEqual(S.problemi(MAR, OK_STATO, OK_IND, OK_LIVE, {"Sito": ("success", "u")}), [])

    def test_sito_fermo(self):
        p = S.problemi(MAR, {"creato": "2026-11-09 05:00:00", "esito": "ok"}, OK_IND, OK_LIVE)
        self.assertTrue(any("Sito non aggiornato" in x for x in p))

    def test_fine_settimana_tollerato(self):
        lun = datetime(2026, 11, 16, 7, 0, tzinfo=timezone.utc)        # lunedi' mattina
        p = S.problemi(lun, {"creato": "2026-11-13 22:20:00", "esito": "ok"},
                       {"generato": "2026-11-13 23:00", "anomalia": None}, None)
        self.assertEqual(p, [])                                         # borsa chiusa: live non controllato

    def test_live_fermo_solo_a_borsa_aperta(self):
        vecchio = {"quando": MAR.timestamp() - 3 * 3600}
        self.assertTrue(any("live" in x for x in S.problemi(MAR, OK_STATO, OK_IND, vecchio)))
        sera = datetime(2026, 11, 10, 23, 0, tzinfo=timezone.utc)
        self.assertFalse(any("live" in x for x in S.problemi(sera, OK_STATO, {"generato": "2026-11-10 22:00"}, vecchio)))

    def test_workflow_fallito_e_anomalia(self):
        p = S.problemi(MAR, OK_STATO, dict(OK_IND, anomalia={"codice": "503"}), OK_LIVE,
                       {"Azioni": ("failure", "https://x")})
        self.assertTrue(any("Azioni" in x and "https://x" in x for x in p))
        self.assertTrue(any("anomalia" in x for x in p))

    def test_sito_giu(self):
        self.assertTrue(any("non leggibile" in x for x in S.problemi(MAR, None, OK_IND, OK_LIVE)))


if __name__ == "__main__":
    unittest.main()
