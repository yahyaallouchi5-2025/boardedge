# -*- coding: utf-8 -*-
"""
backtest_ottimizza.py - STUDIO DELLE OTTIMIZZAZIONI DEI PORTAFOGLI (v6.57, solo studio: non cambia il sito)

Partenza: i profili della versione 3 (cot_radar/portafogli.py: base fissa, filtro di trend a 200 giorni, Treasury e
oro sempre presenti, ribilancio lento). Si prova UNA modifica alla volta, poi le migliori insieme:
  0  Attuale (v3)
  1  Oro con filtro di trend      : l'oro esce (va in liquidita') quando e' sotto la media a 200 giorni
  2  Freno di volatilita'         : se la volatilita' degli ultimi 3 mesi del portafoglio proposto supera il bersaglio
                                    del profilo, la parte rischiosa (azioni, Bitcoin, azioni scelte) si riduce in
                                    proporzione e la differenza va in liquidita'
  3  Materie prime 5%             : 2,5% rame + 2,5% petrolio (con filtro di trend), presi dalla quota S&P 500
  4  Oro al 10%                   : 5 punti di oro passano in liquidita'
  5  Combinazione delle modifiche che migliorano rendimento/rischio fuori campione SENZA peggiorare il drawdown
Ogni variante e' misurata in DOLLARI (come il sito) e in EURO senza copertura (come la vede un investitore italiano:
valore in dollari diviso il cambio EUR/USD della BCE/FRED del giorno).

Regola di scelta (decisa PRIMA di guardare i numeri): una modifica entra solo se, fuori campione (dal 2016),
migliora il rapporto rendimento/volatilita' e non peggiora il drawdown massimo di oltre 1 punto, in dollari E in euro.

USO: python tools/backtest_ottimizza.py <cartella_storico> <satellite.json> <DEXUSEU.csv>
"""
import copy
import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cot_radar import portafogli as P          # noqa: E402

VOL_BERSAGLIO = {"conservativo": 0.06, "moderato": 0.08, "aggressivo": 0.11}   # volatilita' annua massima
DIFESA = ("CASH", "US10Y", "GOLD")             # parte del portafoglio che il freno NON riduce


def cambio(f):
    """{data: EUR/USD} dal CSV FRED DEXUSEU (dollari per 1 euro)."""
    with open(f, encoding="utf-8") as h:
        rd = csv.reader(h)
        next(rd)
        return {r[0]: float(r[1]) for r in rd if len(r) == 2 and r[1]}


def in_euro(curva, fx):
    """Curva in dollari -> curva in euro (senza copertura): valore / EURUSD dell'ultimo giorno disponibile."""
    out, ult = [], None
    for d, v in curva:
        ult = fx.get(d, ult)
        if ult:
            out.append((d, v / ult))
    return out


def freno(prof, g, i, pesi):
    """Freno di volatilita': stima la volatilita' dei pesi proposti sugli ultimi VOL_GIORNI giorni e, se supera il
    bersaglio, riduce in proporzione tutto cio' che non e' difesa. Restituisce (pesi, fattore)."""
    r = []
    for j in range(max(1, i - P.VOL_GIORNI), i):
        r.append(sum(w * g.rend(P._ticker(k), j) for k, w in pesi.items()))
    vol = (P._std(r) or 0) * (252 ** 0.5)
    bersaglio = VOL_BERSAGLIO[prof["id"]]
    if vol <= bersaglio or vol == 0:
        return pesi, 1.0
    rischio = sum(w for k, w in pesi.items() if k not in DIFESA)
    difesa_vol = 0.0                                  # approssimazione: la difesa pesa poco sulla volatilita'
    f = max(0.3, min(1.0, (bersaglio - difesa_vol) / vol))
    nuovi = {k: (w * f if k not in DIFESA else w) for k, w in pesi.items()}
    nuovi["CASH"] = nuovi.get("CASH", 0) + rischio * (1 - f)
    return {k: round(v, 4) for k, v in nuovi.items() if v >= 0.005}, f


def piano(prof, g, giorni, con_freno=False):
    """Stesso calendario della v3: si scambia se cambia l'insieme dei mercati attivi, a inizio trimestre o
    (con il freno) quando il fattore del freno cambia di oltre 0,15."""
    out, prec, prec_f = {}, None, 1.0
    for i in giorni:
        pesi, _, _ = P.scegli(prof, g, i, {})
        f = 1.0
        if con_freno:
            pesi, f = freno(prof, g, i, pesi)
        insieme = frozenset(k for k in pesi if k != "CASH")
        if prec is None or insieme != prec or g.date[i][5:7] in P.TRIMESTRI or abs(f - prec_f) > 0.15:
            out[i] = pesi
            prec_f = f
        prec = insieme
    return out


def variante(prof, oro=None, materie=False):
    p = copy.deepcopy(prof)
    b = p["base"]
    if oro is not None:
        diff = b.get("GOLD", 0) - oro
        b["GOLD"] = oro
        b["CASH"] = b.get("CASH", 0) + diff
    if materie:
        b["SP500"] -= 0.05
        b["COPPER"] = 0.025
        b["WTI"] = 0.025
    p["ammessi"] = [k for k in b if k != "CASH"] + (["AZ"] if p.get("az") else [])
    return p


def misura(curva, fx):
    usd_t, usd_o = P.statistiche(curva), P.statistiche(P._tagli(curva, dal=P.OOS_DAL))
    e = in_euro(curva, fx)
    eur_t, eur_o = P.statistiche(e), P.statistiche(P._tagli(e, dal=P.OOS_DAL))
    return usd_t, usd_o, eur_t, eur_o


def main():
    cartella, satf, fxf = sys.argv[1], sys.argv[2], sys.argv[3]
    px = P.prezzi(scarica=None, cartella=cartella)
    ss = P.serie_satellite(json.load(open(satf, encoding="utf-8")), [d for d, _ in px["SPY"]])
    if ss:
        px["SAT"] = ss
    fx = cambio(fxf)
    g = P.Griglia(px)
    giorni = P.date_ribilancio(g)
    print(f"Periodo {g.date[giorni[0]]} - {g.date[-1]}, {len(giorni)} controlli mensili")
    tutto = {}
    sempre = P.SEMPRE
    for prof in P.PROFILI:
        print(f"\n=== {prof['nome']} ===")
        prove = [("0 attuale", prof, False, sempre), ("1 oro con trend", prof, False, ("US10Y",)),
                 ("2 freno volatilita'", prof, True, sempre), ("3 materie prime 5%", variante(prof, materie=True), False, sempre),
                 ("4 oro al 10%", variante(prof, oro=0.10), False, sempre)]
        righe = []
        for nome, p, fr, sem in prove:
            P.SEMPRE = sem
            c = P.simula(g, piano(p, g, giorni, fr), giorni[0])
            righe.append((nome, misura(c, fx)))
        P.SEMPRE = sempre
        w = {"conservativo": .3, "moderato": .6, "aggressivo": .8}[prof["id"]]
        cb = P.simula(g, {i: {"SPY": w, "IEF": 1 - w} for i in giorni}, giorni[0])
        righe.append((f"bench {round(w*100)}/{round((1-w)*100)}", misura(cb, fx)))
        f = lambda s: f"{s['cagr']:6.1f}{s['vol']:6.1f}{s['maxdd']:7.1f}{(s['cagr']/s['vol'] if s['vol'] else 0):6.2f}{s['peggior_mese'][1]:6.1f}"
        print(f"{'':24}{'USD dal 2016':^31}|{'EUR dal 2016':^31}|{'EUR tutto':^31}")
        print(f"{'':24}" + ("  CAGR   Vol  MaxDD  R/V  Pegg|" * 3))
        for nome, (ut, uo, et, eo) in righe:
            print(f"{nome:24}{f(uo)}|{f(eo)}|{f(et)}")
        tutto[prof["id"]] = righe
    return tutto


if __name__ == "__main__":
    main()
