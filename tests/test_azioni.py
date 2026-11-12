# -*- coding: utf-8 -*-
"""Test della scheda Azioni (cot_radar/azioni.py). Nessuna rete: Yahoo e' sostituito da funzioni finte.
Lancia: python -m unittest tests.test_azioni -v"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import azioni as A  # noqa: E402


def finto(t, intervallo="1d", periodo="2y"):
    """Serie regolare: +0,1% al giorno (o +1% al mese) dal 2024."""
    meta = {"nome": "Nome " + t, "valuta": "USD", "borsa": "Prova"}
    if intervallo == "1mo":
        return meta, [(f"{a}-{m:02d}", 100 * 1.01 ** ((a - 2000) * 12 + m)) for a in range(2000, 2026) for m in range(1, 13)]
    d, v, out = date(2024, 10, 1), 100.0, []
    while d <= date(2026, 10, 23):
        if d.weekday() < 5:
            v *= 1.001
            out.append((d.isoformat(), round(v, 4)))
        d += timedelta(days=1)
    return meta, out


class Azioni(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_elenco_completo_e_settori_validi(self):
        el = A.elenco()
        self.assertGreater(len(el), 600)
        ids = {s[0] for s in A.SETTORI}
        self.assertTrue(all(x["s"] in ids for x in el))
        self.assertTrue(all(set(x["l"]) <= set(A.LISTINI) for x in el))
        self.assertEqual(len({x["t"] for x in el}), len(el))                     # nessun doppione

    def test_giro_completo_e_file_pubblici(self):
        tit = [{"t": "AAA", "nome": "A", "s": "tech", "l": ["sp500"]}, {"t": "BBB.MI", "nome": "B", "s": "fin", "l": ["mib"]}]
        st = A.aggiorna(self.dir, ["AAA", "BBB.MI"], oggi=date(2026, 10, 26), scarica=finto, pausa=0)
        self.assertEqual(st["ok"], 2)
        self.assertIsNone(st["anomalia"])
        ix = A.pubblica(self.dir, st, tit)
        self.assertEqual(len(ix["titoli"]), 2)
        r = ix["titoli"][0]
        self.assertEqual(r["n"], "Nome AAA")                                     # nome da Yahoo
        self.assertGreater(r["v1a"], 0)
        self.assertTrue(0 <= min(r["sp"]) and max(r["sp"]) <= 99)
        det = json.load(open(os.path.join(self.dir, "pubblico", "titoli", "BBB.MI.json")))
        self.assertEqual(len(det["stag"]["mesi"]), 12)
        self.assertAlmostEqual(det["stag"]["mesi"][0]["media"], 1.0, places=1)    # +1% al mese

    def test_punteggio_e_vetrina(self):
        base = {"s": "tech", "l": ["sp500"], "t200": 5, "v3m": 4, "v1a": 20, "st_media": 1.0, "st_pos": 70, "st_n": 20,
                "dmax": -3}
        righe = [dict(base, t="A%d" % i, v1a=i, s="tech" if i % 2 else "fin") for i in range(10)]
        righe.append(dict(base, t="DEBOLE", v1a=-30, t200=-10))
        A.punteggi(righe)
        self.assertEqual(sorted(r["rk"] for r in righe), list(range(1, 12)))
        top = A.vetrina(righe)
        self.assertLessEqual(len(top), A.TOP_N)
        self.assertNotIn("DEBOLE", [r["t"] for r in top])                     # sotto la media a 200 giorni: escluso
        self.assertEqual(len({r["s"] for r in top}), len(top))                 # al massimo un titolo per settore
        self.assertEqual(top[0]["t"], "A9")                                     # il piu' forte del suo settore

    def test_in_sconto(self):
        # v6.66: scontati ma sani, settori diversi da quelli della vetrina e tra loro
        b = {"sd": 80, "sdo": -20, "v1a": 10, "sdq": 60, "pt": 50}
        righe = [dict(b, t="T1", s="tech"),                  # settore gia' in vetrina: escluso
                 dict(b, t="F1", s="fin", sd=90), dict(b, t="F2", s="fin", sd=85),   # un solo finanziario (il piu' scontato)
                 dict(b, t="CROLLO", s="ener", sdo=-60),     # oltre -35%: escluso
                 dict(b, t="GIU", s="mat", v1a=-5),          # 12 mesi negativi: escluso
                 dict(b, t="CASO", s="util", sdq=40),        # storicamente peggio del caso: escluso
                 dict(b, t="POCO", s="imm", sdo=-5),         # meno del 10% dal massimo: non e' sconto
                 dict(b, t="U1", s="salute", sd=70), dict(b, t="U2", s="ind", sd=65), dict(b, t="U3", s="cdis", sd=61)]
        out = [r["t"] for r in A.in_sconto(righe, [{"s": "tech"}])]
        self.assertEqual(out, ["F1", "U1", "U2"])

    def test_blocco_temporaneo_pausa_e_ripresa(self):
        # v6.82: Yahoo blocca per un po' (6 richieste a vuoto) e poi riprende: dopo la pausa si rifanno i titoli falliti
        chiesti, giu = [], [6]
        def a_tratti(t, *a, **k):
            chiesti.append(t)
            if giu[0] > 0:
                giu[0] -= 1
                return None
            return finto(t)
        titoli = [f"X{i}" for i in range(40)]
        with mock.patch.object(A.time, "sleep"):
            st = A.aggiorna(self.dir, titoli, oggi=date(2026, 11, 3), scarica=a_tratti, pausa=0, riprese=[0, 0])
        self.assertFalse(st["fermo"])
        self.assertIsNone(st["anomalia"])
        self.assertEqual(st["ok"], 39)                                            # rifatti X1..X4 dopo la pausa
        self.assertEqual(st["copia"] + st["falliti"], ["X0"])                     # solo il 6o fallimento resta
        # ordine delle richieste (senza i doppioni dello storico mensile): X0..X4, pausa, X0..X4 di nuovo, poi X5
        seq = [t for n, t in enumerate(chiesti) if n == 0 or t != chiesti[n - 1]]
        self.assertEqual(seq[:11], [f"X{i}" for i in range(5)] * 2 + ["X5"])

    def test_blocco_che_non_passa_resta_fermo(self):
        chiesti = []
        def giu(t, *a, **k):
            chiesti.append(t)
            return None
        titoli = [f"X{i}" for i in range(20)]
        st = A.aggiorna(self.dir, titoli, oggi=date(2026, 11, 3), scarica=giu, pausa=0, riprese=[0, 0])
        self.assertEqual(len(chiesti), 3 * A.DI_FILA)                             # 5 + 5 + 5 richieste, poi stop
        self.assertTrue(st["fermo"])
        self.assertEqual(sorted(st["falliti"]), sorted(titoli))                   # nessun titolo perso o doppio

    def test_yahoo_fermo_copia_e_anomalia(self):
        A.aggiorna(self.dir, ["AAA"], oggi=date(2026, 10, 23), scarica=finto, pausa=0)
        chiesti = []
        def giu(t, *a, **k):
            chiesti.append(t)
            return None
        titoli = ["AAA"] + [f"X{i}" for i in range(9)]
        st = A.aggiorna(self.dir, titoli, oggi=date(2026, 10, 26), scarica=giu, pausa=0)
        self.assertEqual(len(chiesti), A.DI_FILA)                                 # dopo 5 fallimenti di fila basta
        self.assertTrue(st["fermo"])
        self.assertEqual(st["copia"], ["AAA"])                                    # resta la copia di venerdi'
        self.assertEqual(st["anomalia"]["codice"], A.CODICE_ERRORE)
        self.assertRegex(st["anomalia"]["quando"], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")  # giorno e ora dell'anomalia
        ix = A.pubblica(self.dir, st, [{"t": "AAA", "nome": "A", "s": "tech", "l": ["sp500"]}])
        self.assertEqual(len(ix["titoli"]), 1)                                    # la scheda resta piena
        self.assertIsNotNone(ix["anomalia"])

    def test_tentativi_e_dati_rotti(self):
        n = []
        def rotto(req, timeout=0):
            n.append(1)
            raise OSError("429")
        with mock.patch.object(A.urllib.request, "urlopen", rotto):
            self.assertIsNone(A.scarica("AAA", attesa=0))
        self.assertEqual(len(n), A.TENTATIVI)
        serie = [((date(2026, 1, 1) + timedelta(days=i)).isoformat(), 10.0) for i in range(30)]
        serie[10] = (serie[10][0], 1.0)                                           # crollo del 90% in un giorno: dato rotto
        self.assertIsNone(A._valida(serie))

    def test_ramo_assente_non_blocca(self):
        with mock.patch("subprocess.run", side_effect=OSError("niente git")):
            self.assertFalse(A.copia_nel_sito(self.dir))


if __name__ == "__main__":
    unittest.main()


class TestMensile(unittest.TestCase):
    """Storico mensile: le copie TRIMESTRALI (range=max di Yahoo sugli storici lunghi) vanno riconosciute e la
    stagionalita' non deve mai usare rendimenti su piu' mesi."""

    def test_riconosce_trimestrale(self):
        mensile = [("2020-%02d" % m, 100 + m) for m in range(1, 13)]
        trimestrale = [("2020-%02d" % m, 100 + m) for m in (3, 6, 9, 12)]
        self.assertTrue(A.mensile_ok(mensile))
        self.assertFalse(A.mensile_ok(trimestrale))
        self.assertFalse(A.mensile_ok(None))

    def test_stagionalita_salta_i_buchi(self):
        # 2010-01..2012-12 mensile, poi un buco di 3 mesi: quel rendimento non deve finire su un mese
        m = [("%d-%02d" % (a, x), 100.0 * (1.01 ** i)) for i, (a, x) in
             enumerate((a, x) for a in (2010, 2011, 2012) for x in range(1, 13))]
        m.append(("2013-03", m[-1][1] * 2))           # +100% in 3 mesi: va ignorato
        st = A.stagionalita(m)
        self.assertEqual(st["mesi"][2]["n"], 3)        # marzo: 2010, 2011, 2012 (NON il salto dic 2012 -> mar 2013)
        self.assertLess(st["mesi"][2]["media"], 2)


class TestMensileRiserva(unittest.TestCase):
    """Titoli senza storico mensile valido su Yahoo (quotati da poco, buchi): niente tentativi a vuoto ogni sera,
    lo storico mensile si ricava dai prezzi giornalieri."""

    def test_da_giornaliero(self):
        d = [("2026-01-30", 10.0), ("2026-02-02", 11.0), ("2026-02-27", 12.0), ("2026-03-02", 13.0)]
        self.assertEqual(A.mensile_da_giornaliero(d), [("2026-01", 10.0), ("2026-02", 12.0), ("2026-03", 13.0)])

    def test_niente_tentativi_ripetuti(self):
        chiamate = []

        def yahoo(t, intervallo="1d", periodo="2y"):
            chiamate.append(intervallo)
            return finto(t)[0], finto(t)[1] if intervallo == "1d" else None
        sca = lambda t, intervallo="1d", periodo="2y": None if intervallo == "1mo" else yahoo(t, intervallo, periodo)
        cart = tempfile.mkdtemp()
        try:
            oggi = date(2026, 10, 26)
            A.aggiorna(cart, titoli=["NUOVO"], oggi=oggi, scarica=sca, pausa=0)
            rec = json.load(open(os.path.join(cart, "grezzi", "NUOVO.json")))
            self.assertTrue(A.mensile_ok(rec["m"]))           # mensile ricavato dai giornalieri
            self.assertEqual(rec["agg_m"], oggi.isoformat())   # segnato: domani NON si richiede di nuovo
            n = len(chiamate)
            A.aggiorna(cart, titoli=["NUOVO"], oggi=oggi + timedelta(days=1), scarica=lambda *a, **k: (
                chiamate.append(k.get("intervallo", a[1] if len(a) > 1 else "1d")) or finto(a[0])), pausa=0)
            self.assertNotIn("1mo", chiamate[n:])
        finally:
            shutil.rmtree(cart)

    def test_scarica_mensile_anomalo_un_solo_tentativo(self):
        class R:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps({"chart": {"result": [{"meta": {}, "timestamp": [], "indicators": {"quote": [{"close": []}]}}]}}).encode()
        with mock.patch("urllib.request.urlopen", return_value=R()) as u, mock.patch("time.sleep") as s:
            self.assertIsNone(A.scarica("X", "1mo", "max", attesa=2))
            self.assertEqual(u.call_count, 1)
            s.assert_not_called()


class TestTreGiri(unittest.TestCase):
    """v6.86: tre giri per area, download incrementale degli ultimi 5 giorni, stato per area."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_area_dei_ticker(self):
        casi = {"AAPL": "usa", "BRK-B": "usa", "^GSPC": "usa", "ENI.MI": "europa", "MC.PA": "europa",
                "NDA-FI.HE": "europa", "7203.T": "asia", "0005.HK": "asia", "600519.SS": "asia",
                "RELIANCE.NS": "asia", "^N225": "asia", "FTSEMIB.MI": "europa", "000001.SS": "asia"}
        for t, a in casi.items():
            self.assertEqual(A.area(t), a, t)

    def test_unisci_aggiunge_solo_i_giorni_nuovi(self):
        vecchi = [["2026-10-28", 100.0], ["2026-10-29", 101.0], ["2026-10-30", 102.0]]
        nuovi = [("2026-10-29", 101.0), ("2026-10-30", 102.0), ("2026-11-02", 103.0)]
        out = A.unisci(vecchi, nuovi, date(2026, 11, 3))
        self.assertEqual(out[-1], ["2026-11-02", 103.0])
        self.assertEqual(len(out), 4)

    def test_unisci_rettifica_dividendo_riscarica(self):
        vecchi = [["2026-10-29", 101.0], ["2026-10-30", 102.0]]
        nuovi = [("2026-10-29", 99.0), ("2026-10-30", 100.0), ("2026-11-02", 101.0)]   # passato cambiato del 2%
        self.assertIsNone(A.unisci(vecchi, nuovi, date(2026, 11, 3)))

    def test_unisci_buco_riscarica(self):
        vecchi = [["2026-10-01", 100.0]]
        self.assertIsNone(A.unisci(vecchi, [("2026-11-02", 101.0)], date(2026, 11, 3)))

    def test_giorno_normale_chiede_solo_5_giorni(self):
        oggi = date(2026, 10, 26)
        A.aggiorna(self.dir, ["AAA"], oggi=oggi, scarica=finto, pausa=0)            # primo giro: storico intero
        richieste = []

        def sca(t, intervallo="1d", periodo="2y"):
            richieste.append((intervallo, periodo))
            return finto(t, intervallo, periodo)
        # giorno dopo, non il giorno settimanale del titolo
        dopo = oggi + timedelta(days=1)
        while dopo.weekday() == A.giorno_mensile("AAA") or dopo.weekday() > 4:
            dopo += timedelta(days=1)
        st = A.aggiorna(self.dir, ["AAA"], oggi=dopo, scarica=sca, pausa=0)
        self.assertEqual(st["ok"], 1)
        self.assertEqual(richieste, [("1d", "5d")])

    def test_main_area_aggiorna_solo_la_sua_area_e_tiene_lo_stato_delle_altre(self):
        el = [{"t": "AAA", "nome": "A", "s": "tech", "l": ["sp500"]},
              {"t": "BBB.MI", "nome": "B", "s": "fin", "l": ["mib"]},
              {"t": "CCC.T", "nome": "C", "s": "ind", "l": ["n225"]}]
        chiesti = []

        def sca(t, *a, **k):
            chiesti.append(t)
            return finto(t, *a, **k)
        with mock.patch.object(A, "elenco", return_value=el), mock.patch.object(A, "INDICI", []), \
                mock.patch.object(A, "scarica", sca), mock.patch.object(A, "PAUSA", 0), \
                mock.patch("cot_radar.azioni.aggiorna.__defaults__",
                           (None, None, sca, 0, None, A.CHIUSURA_UTC, None)):
            A.main(["x", self.dir, "--area", "europa"])
            self.assertEqual(set(chiesti), {"BBB.MI"})
            st = json.load(open(os.path.join(self.dir, "stato.json")))
            self.assertEqual(st["area"], "europa")
            self.assertIn("europa", st["aree"])
            self.assertIsNone(st["anomalia"])

    def test_v761_area_indietro_recuperata_nello_stesso_giro(self):
        """Giro Asia saltato da GitHub: il giro Europa scarica anche i titoli asiatici rimasti indietro."""
        el = [{"t": "BBB.MI", "nome": "B", "s": "fin", "l": ["mib"]},
              {"t": "CCC.T", "nome": "C", "s": "ind", "l": ["n225"]}]
        with open(os.path.join(self.dir, "stato.json"), "w") as f:      # l'Asia c'era, ma senza dati freschi
            json.dump({"aree": {"asia": {"quando": "2026-11-01 11:00", "anomalia": None, "ok": 1, "mancati": 0}}}, f)
        chiesti = []

        def sca(t, *a, **k):
            chiesti.append(t)
            return finto(t, *a, **k)
        with mock.patch.object(A, "elenco", return_value=el), mock.patch.object(A, "INDICI", []), \
                mock.patch.object(A, "scarica", sca), mock.patch.object(A, "PAUSA", 0), \
                mock.patch("cot_radar.azioni.aggiorna.__defaults__",
                           (None, None, sca, 0, None, A.CHIUSURA_UTC, None)):
            A.main(["x", self.dir, "--area", "europa"])
            self.assertEqual(set(chiesti), {"BBB.MI", "CCC.T"})
            st = json.load(open(os.path.join(self.dir, "stato.json")))
            self.assertTrue(st["aree"]["asia"].get("recupero"))
            self.assertIsNone(st["anomalia"])


class TestParacadute(unittest.TestCase):
    """v6.95: "in manutenzione" solo se i dati sono davvero vecchi (oltre una seduta), non per un giro fallito."""

    def test_data_minima(self):
        from datetime import date
        mer = date(2026, 11, 4)
        self.assertEqual(A.data_minima(mer, "17:17", "21:00"), "2026-11-02")   # seduta USA aperta: ultima = mar 3
        self.assertEqual(A.data_minima(mer, "21:30", "21:00"), "2026-11-03")   # dopo la chiusura: ultima = mer 4
        self.assertEqual(A.data_minima(date(2026, 11, 9), "08:00", "21:00"), "2026-11-05")  # lunedi': ven 6 -> gio 5

    def test_yahoo_fermo_ma_copie_fresche_niente_avviso(self):
        import tempfile, shutil
        from datetime import date
        d = tempfile.mkdtemp()
        try:
            for t in ("AAA", "BBB"):
                A._scrivi(os.path.join(d, "grezzi", t + ".json"),
                          {"t": t, "d": [["2026-11-02", 10.0], ["2026-11-03", 10.5]], "agg_full": "2026-11-03"})
            giu = lambda *a, **k: None                                        # Yahoo non risponde
            st = A.aggiorna(d, ["AAA", "BBB"], oggi=date(2026, 11, 4), scarica=giu, pausa=0, ora_utc="17:17")
            self.assertEqual(st["ok"], 0)
            self.assertIsNone(st["anomalia"])                                 # dati al 3/11: ancora freschi
            st = A.aggiorna(d, ["AAA", "BBB"], oggi=date(2026, 11, 6), scarica=giu, pausa=0, ora_utc="22:00")
            self.assertIsNotNone(st["anomalia"])                              # 2 sedute perse: avviso giusto
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestAutoGuarigione(unittest.TestCase):
    def test_freschezza(self):
        import tempfile, shutil
        from datetime import date
        d = tempfile.mkdtemp()
        try:
            A._scrivi(os.path.join(d, "grezzi", "AAA.json"), {"t": "AAA", "d": [["2026-11-03", 10.0]]})
            self.assertIsNone(A.freschezza(d, ["AAA"], "21:00", oggi=date(2026, 11, 4), ora_utc="22:00"))
            self.assertIsNotNone(A.freschezza(d, ["AAA"], "21:00", oggi=date(2026, 11, 6), ora_utc="22:00"))
            self.assertIsNotNone(A.freschezza(d, ["ZZZ"], "21:00", oggi=date(2026, 11, 4), ora_utc="22:00"))
            self.assertIsNone(A.freschezza(d, [], "21:00"))
        finally:
            shutil.rmtree(d, ignore_errors=True)


class AnalisiTecnica(unittest.TestCase):
    """v7.7: SMA 50/200, trend, RSI 14 (Wilder), ATR 14 sulle chiusure, range 52 settimane."""

    def test_trend_e_rsi(self):
        from datetime import date, timedelta
        from cot_radar import azioni as A
        d0 = date(2024, 1, 1)
        su = [((d0 + timedelta(days=i)).isoformat(), 100 * 1.002 ** i) for i in range(400)]
        t = A.tecnica(su)
        self.assertEqual(t["tr"], 1)
        self.assertEqual(t["rsi"], 100.0)                  # solo rialzi
        self.assertEqual(t["pos52"], 100)
        giu = [(x, 1e4 / v) for x, v in su]
        t = A.tecnica(giu)
        self.assertEqual(t["tr"], -1)
        self.assertLess(t["rsi"], 1)
        self.assertAlmostEqual(t["atr"], 0.2, places=1)    # 0,2% al giorno
        self.assertIsNone(A.tecnica(su[:30]))


class Ampiezza(unittest.TestCase):
    def test_conteggi_per_area(self):
        from cot_radar import azioni as A
        r = [{"t": "AAPL", "tr": 1}, {"t": "ENI.MI", "tr": -1}, {"t": "7203.T", "tr": 0}, {"t": "X", "tr": None}]
        a = A.ampiezza(r)
        self.assertEqual(a["tot"], {"su": 1, "lat": 1, "giu": 1, "n": 3})
        self.assertEqual([x["nome"] for x in a["aree"]], ["USA", "Europa", "Asia"])
        self.assertEqual(a["aree"][1]["giu"], 1)
