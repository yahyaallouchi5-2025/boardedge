# -*- coding: utf-8 -*-
"""Test dei portafogli modello (cot_radar/portafogli.py). Nessuna rete: prezzi finti e COT finto.
Lancia: python -m unittest tests.test_portafogli -v"""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import portafogli as P  # noqa: E402
from cot_radar.config import ASSETS  # noqa: E402

CODICI = {a[0]: a[1] for a in ASSETS}


def cot_finto(chiavi, compra):
    """Righe COT settimanali dal 2003: per le chiavi in 'compra' gli speculatori accumulano sempre piu' long."""
    righe, d = [], date(2003, 1, 7)
    t = 0
    while d < date(2026, 10, 20):
        for k in chiavi:
            netto = (1000 + t * 40) if k in compra else (1000 - (t % 7) * 10)
            righe.append({"cftc_contract_market_code": CODICI[k], "report_date_as_yyyy_mm_dd": d.isoformat(),
                          "open_interest_all": "100000", "noncomm_positions_long_all": str(20000 + netto),
                          "noncomm_positions_short_all": "20000", "comm_positions_long_all": "30000",
                          "comm_positions_short_all": "30000"})
        d += timedelta(days=7)
        t += 1
    return righe


class Portafogli(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.px = P.prezzi_demo("2003-01-02", "2026-10-23")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_pesi_validi_e_tetti(self):
        g = P.Griglia(self.px)
        sc = P.segnali_cot(cot_finto([u[0] for u in P.UNIVERSO], {u[0] for u in P.UNIVERSO}))
        for prof in P.PROFILI:
            for i in P.date_ribilancio(g)[-24:]:
                pesi, _, _ = P.scegli(prof, g, i, sc)
                self.assertLessEqual(sum(pesi.values()), 1.001)                  # niente leva (arrotondamenti a parte)
                for k, w in pesi.items():
                    if k != "CASH":
                        self.assertIn(k, prof["ammessi"])                         # solo mercati del profilo
                        self.assertLessEqual(w, prof["base"][k] + 1e-6)          # mai oltre il peso della base

    def test_trend_negativo_peso_in_liquidita(self):
        px = dict(self.px)
        for t in ("EFA", "IEF"):                                                   # azioni estere E Treasury in discesa
            px[t] = [(d, 100.0 * 0.999 ** n) for n, (d, _) in enumerate(px[t])]
        g = P.Griglia(px)
        sc = P.segnali_cot(cot_finto(["EAFE"], {"EAFE"}))                         # COT da acquisto: non conta
        prof = P.PROFILI[0]
        pesi, _, esclusi = P.scegli(prof, g, P.date_ribilancio(g)[-1], sc)
        self.assertNotIn("EAFE", pesi)                                             # azioni: filtro di trend
        self.assertEqual([e["k"] for e in esclusi if e["k"] == "EAFE"], ["EAFE"])
        self.assertIn("US10Y", pesi)                                               # v3: la difesa resta sempre
        self.assertGreaterEqual(pesi["CASH"], (prof["base"]["CASH"] + prof["base"]["EAFE"]) * (1 - prof["az"]) - 1e-3)

    @mock.patch.object(P, "LIVE_V3_DAL", "2000-01-01")     # nei dati finti la rotazione v3 e' gia' "live"
    def test_calcolo_completo_e_registro_mai_riscritto(self):
        righe = cot_finto([u[0] for u in P.UNIVERSO], {"SP500", "GOLD", "US10Y", "NASDAQ"})
        r = P.calcola(righe, self.px, cartella=self.dir, scrivi=True, oggi=date(2026, 10, 25))
        self.assertEqual([p["id"] for p in r["profili"]], ["conservativo", "moderato", "aggressivo"])
        self.assertEqual(r["prossima"], "2026-11-02")   # 1 novembre 2026 e' domenica: primo giorno feriale
        for p in r["profili"]:
            self.assertIsNotNone(p["stat"]["oos"])
            self.assertAlmostEqual(sum(c["peso"] for c in p["composizione"]), 100, delta=0.6)
        rot = P.leggi_rotazioni(self.dir)
        self.assertEqual(len(rot), 1)
        # stessa data con pesi diversi: la rotazione salvata NON cambia
        P.registra(rot, rot[0]["data"], {"conservativo": {"CASH": 1.0}}, self.dir)
        self.assertEqual(P.leggi_rotazioni(self.dir), rot)
        # al giro dopo c'e' la linea live
        r2 = P.calcola(righe, self.px, cartella=self.dir, scrivi=True, oggi=date(2026, 10, 25))
        self.assertEqual(r2["profili"][0]["live_dal"], rot[0]["data"])

    def test_rischio_del_mese(self):
        # due mercati sintetici: SPY scende del 10% ogni ottobre e risale a novembre, SHY piatto
        giorni, d = [], date(2015, 1, 1)
        while d < date(2020, 12, 31):
            if d.weekday() < 5:
                giorni.append(d.isoformat())
            d += timedelta(days=1)
        spy, v = [], 100.0
        for gg in giorni:
            if gg[5:7] == "10":
                v *= 0.995
            spy.append((gg, v))
        g = P.Griglia({"SPY": spy, "SHY": [(x, 100.0) for x in giorni]})
        m = P.rischio_mese(g, {"SP500": 0.5, "CASH": 0.5}, "10", "2020-10")
        self.assertEqual(m["mese"], "ottobre")
        self.assertEqual([x["a"] for x in m["anni"]], [2015, 2016, 2017, 2018, 2019])   # ottobre 2020 escluso
        self.assertTrue(all(x["r"] < 0 and x["dd"] <= x["r"] for x in m["anni"]))
        self.assertEqual(m["positivi"], 0)
        self.assertEqual(m["mercati"][0]["k"], "SP500")

    def test_download_ritentato_e_validato(self):
        chiamate = []
        def finto(req, timeout=0):
            chiamate.append(1)
            raise OSError("503")
        with mock.patch.object(P.urllib.request, "urlopen", finto):
            self.assertIsNone(P.scarica_yahoo("SPY", attesa=0))
        self.assertEqual(len(chiamate), P.TENTATIVI)                             # riprova prima di arrendersi
        rotta = [((date(2020, 1, 1) + timedelta(days=i)).isoformat(), 10.0) for i in range(40)]
        rotta[20] = (rotta[20][0], 100.0)                                        # salto assurdo: serie scartata
        self.assertIsNone(P._valida(rotta))

    def test_yahoo_giu_si_smette_e_si_usa_la_copia(self):
        lunga = [((date(2020, 1, 1) + timedelta(days=i)).isoformat(), 10.0 + i) for i in range(100)]
        P._scrivi(self.dir, "SPY", lunga)
        chiesti = []
        out = P.prezzi(scarica=lambda t: chiesti.append(t), cartella=self.dir, oggi=date(2026, 1, 2), pausa=0)
        self.assertEqual(len(chiesti), 3)                                         # dopo 3 fallimenti di fila basta
        self.assertEqual(len(out["SPY"]), 100)                                    # la copia resta
        self.assertIn("SPY", P.ESITO["copia"])

    def test_avviso_prezzi_vecchi_e_scheda_di_riserva(self):
        px = {t: [("2026-10-20", 1.0)] for t in P.usati()}
        self.assertIsNone(P.controlla_prezzi(px, date(2026, 10, 23)))
        av = P.controlla_prezzi(px, date(2026, 10, 30))
        self.assertEqual(av["codice"], P.CODICE_ERRORE)
        self.assertEqual(av["dal"], "2026-10-20")
        self.assertIsNone(P.di_riserva(self.dir))                                 # nessuna copia: niente scheda
        P.salva_ultimo({"aggiornato": "2026-10-20", "profili": []}, self.dir)
        self.assertEqual(P.di_riserva(self.dir)["avviso"]["dal"], "2026-10-20")

    def test_statistiche(self):
        curva = [((date(2020, 1, 1) + timedelta(days=i)).isoformat(), 100 + i * 0.1 - (20 if 100 < i < 150 else 0))
                 for i in range(400)]
        s = P.statistiche(curva)
        self.assertLess(s["maxdd"], -15)
        self.assertIsNotNone(s["peggior_mese"])

    def test_copia_yahoo_sostituita_solo_se_completa(self):
        lunga = [((date(2020, 1, 1) + timedelta(days=i)).isoformat(), 10.0 + i) for i in range(100)]
        P._scrivi(self.dir, "SPY", lunga)
        out = P.prezzi(scarica=lambda t: lunga[:50], cartella=self.dir, oggi=date(2026, 1, 2), pausa=0)
        self.assertEqual(len(out["SPY"]), 100)                                    # download corto: si tiene la copia


if __name__ == "__main__":
    unittest.main()


class AvvioV3(unittest.TestCase):
    def test_rotazione_in_attesa_tra_fine_mese_e_primo_giorno_di_borsa(self):
        # v6.62: domenica 1 novembre, prezzi fino a venerdi' 30 ottobre. La rotazione di lunedi' 2 e' gia' decisa
        # (usa solo la chiusura precedente): si mostra subito, ottobre e' chiuso, il conto alla rovescia punta al 2.
        px = P.prezzi_demo("2003-01-02", "2026-10-30")
        righe = cot_finto([u[0] for u in P.UNIVERSO], {"SP500", "GOLD", "US10Y", "NASDAQ"})
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        r = P.calcola(righe, px, cartella=d, scrivi=True, oggi=date(2026, 11, 1))
        self.assertTrue(r["attesa"])
        self.assertEqual((r["rotazione"], r["prossima"], r["decisa_al"]), ("2026-11-02", "2026-11-02", "2026-10-30"))
        p = r["profili"][0]
        self.assertTrue(p["rotazioni"][0].get("attesa"))
        self.assertEqual(p["rotazioni"][0]["data"], "2026-11-02")
        self.assertEqual(p["mesi_chiusi"][0]["mese"], "2026-10")             # ottobre chiuso al 30
        self.assertEqual(p["mesi_chiusi"][0]["al"], "2026-10-30")
        self.assertEqual((p["corrente"]["gg"], p["corrente"]["mese"]), (0, "novembre"))
        self.assertEqual(P.leggi_rotazioni(d), [])                         # il registro live aspetta il prezzo vero
        # stessa composizione che uscira' il giorno dopo, quando arriva il prezzo del 2 novembre
        px2 = {k: v + [("2026-11-02", v[-1][1] * 1.003)] for k, v in px.items()}   # stessi prezzi + lunedi' 2
        r2 = P.calcola(righe, px2, cartella=d, scrivi=False, oggi=date(2026, 11, 2))
        self.assertNotIn("attesa", r2)
        self.assertEqual(r2["prossima"], "2026-12-01")
        self.assertEqual([(c["k"], c["peso"]) for c in r2["profili"][0]["composizione"]],
                         [(c["k"], c["peso"]) for c in p["composizione"]])

    def test_primo_feriale(self):
        self.assertEqual(P.primo_feriale(2026, 11).isoformat(), "2026-11-02")    # 1 novembre domenica
        self.assertEqual(P.primo_feriale(2027, 1).isoformat(), "2027-01-04")     # 1 gennaio chiuso, poi weekend

    def test_nessuna_rotazione_live_prima_del_2_novembre(self):
        d = tempfile.mkdtemp()
        try:
            rot = P.registra([], "2026-10-01", {"moderato": {"CASH": 1.0}}, d)
            self.assertEqual(rot, [])                                              # niente live retroattivo
            rot = P.registra([], "2026-11-02", {"moderato": {"CASH": 1.0}}, d)
            self.assertEqual([r["data"] for r in rot], ["2026-11-02"])
        finally:
            shutil.rmtree(d)


class MeseInCorso(unittest.TestCase):
    def test_rendimento_e_drawdown_dal_giorno_di_ingresso(self):
        # curva da 100: sale a 110, scende a 99, chiude a 105 -> rendimento +5%, drawdown peggiore -10% dal picco
        curva = [("2026-11-02", 100.0), ("2026-11-03", 110.0), ("2026-11-04", 99.0), ("2026-11-05", 105.0)]
        r, dd = P.mese_tratto(curva, 0, 0, 3)
        self.assertAlmostEqual(r, 5.0)
        self.assertAlmostEqual(dd, -10.0)

    def test_ingresso_non_dal_primo_giorno_della_curva(self):
        # v6.69: rotazione al giorno 2 -> il mese parte dalla chiusura del giorno 1 (base 100) e conta il giorno 2
        curva = [("a", 50.0), ("b", 100.0), ("c", 90.0)]
        r, dd = P.mese_tratto(curva, 0, 2, 2)
        self.assertAlmostEqual(r, -10.0)
        self.assertAlmostEqual(dd, -10.0)

    def test_il_giorno_di_rotazione_conta(self):
        # v6.69: SPY +10% proprio il giorno della rotazione: prima spariva, ora va al portafoglio nuovo
        date_ = ["2026-01-02", "2026-01-30", "2026-02-02", "2026-02-27"]
        px = {"SPY": [(d, v) for d, v in zip(date_, [100, 100, 110, 110])], "SHY": [(d, 50) for d in date_]}
        g = P.Griglia(px)
        curva = P.simula(g, {0: {"SP500": 1.0}, 2: {"SP500": 1.0}}, 0)
        self.assertAlmostEqual(curva[-1][1], 100 * (1 - P.COSTO) * 1.10, places=6)

    def test_giorni_feriali(self):
        self.assertEqual(P.giorni_feriali("2026-11"), 21)

    def test_chiusure_non_si_riscrivono_e_solo_dal_live(self):
        d = tempfile.mkdtemp()
        try:
            vecchio = {"mese": "2026-10", "dal": "2026-10-01", "al": "2026-10-30", "profili": {}}
            nov = {"mese": "2026-11", "dal": "2026-11-02", "al": "2026-11-30", "profili": {"moderato": {"r": 1.0, "dd": -1.0}}}
            c = P.registra_chiusure([], [vecchio, nov], d)
            self.assertEqual([x["dal"] for x in c], ["2026-11-02"])           # ottobre e' precedente al live
            nov2 = dict(nov, profili={"moderato": {"r": 9.9, "dd": -9.9}})
            c = P.registra_chiusure(c, [nov2], d)
            self.assertEqual(c[0]["profili"]["moderato"]["r"], 1.0)           # il mese salvato non cambia
            self.assertEqual(P.leggi_chiusure(d)[0]["dal"], "2026-11-02")
        finally:
            shutil.rmtree(d)


class DettaglioMesi(unittest.TestCase):
    def test_pesi_rendimenti_e_contributi(self):
        # due mercati: SPY +10% nel mese, SHY fermo; portafoglio 50/50 -> totale +5%, contributo SPY 5 punti
        date_ = ["2026-01-02", "2026-01-15", "2026-01-30", "2026-02-02", "2026-02-27", "2026-03-02"]
        px = {"SPY": [(d, v) for d, v in zip(date_, [100, 95, 110, 110, 110, 110])],
              "SHY": [(d, 50) for d in date_]}
        g = P.Griglia(px)
        giorni = [0, 3, 5]
        piani = {0: {"SP500": .5, "CASH": .5}, 3: {"SP500": .5, "CASH": .5}}
        curva = P.simula(g, piani, 0)
        mesi = P.dettaglio_mesi(g, piani, giorni, curva)
        gen = [m for m in mesi if m["mese"] == "2026-01"][0]
        spy = [a for a in gen["asset"] if a["k"] == "SP500"][0]
        self.assertEqual(spy["w"], 50.0)
        self.assertEqual(spy["r"], 10.0)
        self.assertEqual(spy["c"], 5.0)
        self.assertEqual(spy["dd"], -5.0)
        self.assertEqual(gen["r"], 4.9)                     # +5% meno lo 0,10% di costo del primo acquisto


class InEuro(unittest.TestCase):
    """v6.57: statistiche in euro senza copertura (valore in dollari / cambio EUR-USD)."""
    def test_curva_in_euro(self):
        from cot_radar import portafogli as PF
        curva = [("2020-01-02", 100.0), ("2020-01-03", 110.0), ("2020-01-06", 110.0)]
        fx = {"2020-01-02": 1.0, "2020-01-03": 1.1}            # il 6 manca: si usa l'ultimo cambio noto
        self.assertEqual([round(v, 4) for _, v in PF.in_euro(curva, fx)], [100.0, 100.0, 100.0])
        self.assertIsNone(PF.stat_eur(curva, fx))                # troppo pochi giorni


class MisuraProdente(unittest.TestCase):
    """v6.87: acquisto alla chiusura del giorno di rotazione, euro, liquidita' BCE, metriche nuove."""

    def griglia(self):
        d0 = date(2024, 1, 1)
        giorni = [(d0 + timedelta(days=i)).isoformat() for i in range(10)]
        # SPY +10% solo il giorno 5 (giorno di rotazione), poi fermo
        spy = [(g, 100.0 if i < 5 else 110.0) for i, g in enumerate(giorni)]
        return P.Griglia({"SPY": spy, "SHY": [(g, 100.0) for g in giorni]}), giorni

    def test_movimento_del_giorno_di_rotazione_resta_al_portafoglio_vecchio(self):
        g, _ = self.griglia()
        piani = {0: {"CASH": 1.0}, 5: {"SPY": 1.0}}
        vecchio = P.simula(g, {k: v for k, v in piani.items()}, 0)
        nuovo = P.simula_prudente(g, piani, 0)
        self.assertGreater(vecchio[-1][1], 109)                  # simula(): compra alla chiusura del giorno prima
        self.assertLess(nuovo[-1][1], 100.01)                     # prudente: il +10% del giorno 5 non si prende

    def test_liquidita_in_euro_al_tasso_bce(self):
        g, giorni = self.griglia()
        fx = {d: 1.0 for d in giorni}
        c = P.simula_prudente(g, {0: {"CASH": 1.0}}, 0, fx=fx, tassi={giorni[0]: 365.0})
        self.assertGreater(c[-1][1], 100)                         # la liquidita' matura il tasso, non il prezzo SHY

    def test_cinque_azioni_prudenti_come_sp500(self):
        g, giorni = self.griglia()
        px = {"SPY": [(d, 100.0 + i) for i, d in enumerate(giorni)], "SHY": [(d, 100.0) for d in giorni],
              "SAT": [(d, 100.0 + 5 * i) for i, d in enumerate(giorni)]}
        g = P.Griglia(px)
        sel = P.simula_prudente(g, {0: {"AZ": 1.0}}, 0)
        pru = P.simula_prudente(g, {0: {"AZ": 1.0}}, 0, sostituisci={"AZ": "SPY"})
        self.assertGreater(sel[-1][1], pru[-1][1])

    def test_calmar_recupero_e_oltre_la_liquidita(self):
        d0 = date(2020, 1, 1)
        curva, v = [], 100.0
        for i in range(800):
            v *= 0.999 if 100 <= i < 200 else 1.001
            curva.append(((d0 + timedelta(days=i)).isoformat(), v))
        liq = [(d, 100 * 1.00001 ** i) for i, (d, _) in enumerate(curva)]
        s = P.statistiche(curva, liq)
        self.assertLess(s["maxdd"], 0)
        self.assertIsNotNone(s["recupero_mesi"])
        self.assertAlmostEqual(s["calmar"], round(s["cagr"] / abs(s["maxdd"]), 2), places=1)
        self.assertAlmostEqual(s["oltre_liq"], s["cagr"] - s["liq_cagr"], places=1)


class Simulatore(unittest.TestCase):
    """v7.0: finestre mobili, leva con costo del prestito, rendita sostenuta (cot_radar/portafogli.py, simulatore)."""

    def curva(self, giorni=3000, r=0.0003):
        from datetime import date as _d, timedelta as _t
        out, d, v = [], _d(2006, 1, 2), 100.0
        while len(out) < giorni:
            if d.weekday() < 5:
                out.append((d.isoformat(), v))
                v *= 1 + r
            d += _t(days=1)
        return out

    def test_crescita_regolare(self):
        s = P.simulatore(self.curva(), {})
        o = s["leve"]["1.0"]["1"]
        self.assertGreater(o["p50"], 1.0)
        self.assertEqual(o["perdita"], 0.0)
        self.assertLessEqual(o["p5"], o["p50"])
        self.assertLessEqual(o["p50"], o["p95"])
        self.assertIn("10", s["leve"]["1.0"])
        self.assertGreater(s["prelievo"]["1.0"]["p50"], 0)

    def test_leva_costa_e_amplifica(self):
        c = self.curva(600, 0.0)                         # mercato piatto: con la leva si paga solo il prestito
        piatto = P.con_leva(c, {c[0][0]: 3.0}, 1.5)
        self.assertLess(piatto[-1][1], 100.0)
        su = P.con_leva(self.curva(600, 0.0005), {}, 1.5)
        self.assertGreater(su[-1][1], self.curva(600, 0.0005)[-1][1])   # mercato in salita: la leva amplifica

    def test_storico_corto(self):
        self.assertIsNone(P.simulatore(self.curva(100), {}))


class AzioniInSP500(unittest.TestCase):
    """v7.1: dalla rotazione di dicembre 2026 la quota delle 5 azioni va all'S&P 500 (stessi pesi totali)."""

    def test_da_dicembre_niente_az(self):
        px = P.prezzi_demo("2003-01-01", "2026-11-06")
        px["SAT"] = list(px["SPY"])
        g = P.Griglia(px)
        g.p["SPY"] = [100.0 * (1.001 ** k) for k in range(len(g.date))]   # S&P 500 in salita: filtri accesi
        prof = [x for x in P.PROFILI if x["id"] == "aggressivo"][0]
        i = len(g.date) - 1
        prima, _, _ = P.scegli(prof, g, i, {}, giorno="2026-11-02")
        dopo, _, _ = P.scegli(prof, g, i, {}, giorno="2026-12-01")
        self.assertIn("AZ", prima)
        self.assertNotIn("AZ", dopo)
        self.assertAlmostEqual(dopo["SP500"], prima["SP500"] + prima["AZ"], places=3)
        self.assertAlmostEqual(sum(dopo.values()), 1.0, places=2)
