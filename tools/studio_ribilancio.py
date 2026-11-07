# -*- coding: utf-8 -*-
"""
studio_ribilancio.py - PUNTO 5: RIBILANCIAMENTO MIGLIORE? (Ya, 07/11/2026). Solo studio: il sito non cambia.

PARTENZA: i profili attuali (cot_radar/portafogli.py, versione 4): controllo il primo giorno di borsa del mese,
filtro di trend a 200 giorni, Treasury e oro sempre presenti, ribilancio lento (si scambia se cambia l'insieme dei
mercati o a inizio trimestre). Misura = quella del sito: IN EURO senza copertura del cambio, liquidita' al tasso BCE,
acquisto PRUDENTE (alla chiusura del giorno di rotazione), 5 azioni scelte contate come l'S&P 500, costi 0,10%.

VARIANTI (una modifica alla volta, poi la combinazione):
  0  Attuale
  1  Pesi in base alla VOLATILITA': dentro la parte rischiosa (azioni, materie prime, Bitcoin, azioni scelte) ogni
     mercato pesa base / volatilita' degli ultimi 3 mesi, riportato alla stessa quota totale della parte rischiosa
     (massimo 2 volte e minimo meta' del peso base). Treasury, oro e liquidita' restano fermi.
  2  ALLARME A META' MESE per mercato: ogni sera, se un mercato rischioso tenuto chiude sotto la sua media a 200
     giorni di oltre il 3% (margine contro i falsi allarmi), si vende alla chiusura del giorno DOPO e la quota va in
     liquidita' fino al controllo del mese successivo (nessun rientro a meta' mese).
  3  ALLARME DI PORTAFOGLIO: se dal giorno di rotazione il portafoglio perde oltre una soglia (conservativo 4%,
     moderato 5%, aggressivo 6%), la meta' della parte rischiosa va in liquidita' (giorno dopo) fino al mese successivo.
  4  Combinazione 1 + 2.

REGOLA DI SCELTA (scritta PRIMA di guardare i numeri): una variante entra solo se FUORI CAMPIONE (dal 2016) migliora
il rapporto rendimento/volatilita' E non peggiora il drawdown massimo di oltre 1 punto, E nello STUDIO (2006-2015)
il rapporto rendimento/volatilita' non scende di oltre 0,05. Si riportano anche gli ordini in piu' all'anno.
USO: python tools/studio_ribilancio.py <cartella storico> <satellite.json>
"""
import json
import math
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cot_radar import portafogli as P          # noqa: E402

DIFESA = ("CASH", "US10Y", "GOLD")
SOGLIA_PORT = {"conservativo": 0.04, "moderato": 0.05, "aggressivo": 0.06}
MARGINE_TREND = 0.03


def piano(prof, g, giorni, pesi_vol=False):
    """Calendario del sito (ribilancio lento) con, se richiesto, i pesi in base alla volatilita'."""
    out, prec = {}, None
    for i in giorni:
        pesi, info, _ = P.scegli(prof, g, i, {})
        if pesi_vol:
            pesi = per_volatilita(pesi, info)
        insieme = frozenset(k for k in pesi if k != "CASH")
        if prec is None or insieme != prec or g.date[i][5:7] in P.TRIMESTRI:
            out[i] = pesi
        prec = insieme
    return out


def per_volatilita(pesi, info):
    """Parte rischiosa ripesata con base/volatilita' (somma della parte rischiosa invariata, limiti 0,5x-2x)."""
    risk = {k: w for k, w in pesi.items() if k not in DIFESA}
    tot = sum(risk.values())
    if not tot or len(risk) < 2:
        return pesi
    grezzi = {k: w / max(0.05, (info.get(k) or {}).get("vol") or 0.2) for k, w in risk.items()}
    s = sum(grezzi.values())
    nuovi = {k: min(2 * risk[k], max(0.5 * risk[k], tot * v / s)) for k, v in grezzi.items()}
    f = tot / sum(nuovi.values())                    # dopo i limiti: si riporta la somma alla quota rischiosa
    out = {k: w for k, w in pesi.items() if k in DIFESA}
    out.update({k: round(v * f, 4) for k, v in nuovi.items()})
    return out


def sma(col, i, n=P.SMA):
    f = [v for v in col[max(0, i - n + 1):i + 1] if v is not None]
    return sum(f) / len(f) if len(f) >= n * 0.9 else None


def simula(g, piani, dal_i, fx, tassi, allarme=None, soglia=None):
    """Come P.simula_prudente (euro, liquidita' al tasso BCE, AZ come S&P 500) + allarmi a meta' mese.
    allarme="mercato" | "portafoglio" | None. Ritorna (curva, numero di vendite d'allarme)."""
    cambio, tasso, uf, ut = [], [], None, 0.0
    for d in g.date:
        uf, ut = fx.get(d, uf), tassi.get(d, ut)
        cambio.append(uf)
        tasso.append(ut)
    tick = lambda k: P._ticker("SPY" if k == "AZ" else k)
    valore, curva, quote, vendite = 100.0, [], {}, 0
    in_attesa, v_rot, fermi = [], None, set()
    for i in range(dal_i, len(g.date)):
        if quote:
            f = cambio[i - 1] / cambio[i] if cambio[i] and cambio[i - 1] else 1.0
            gg = (date.fromisoformat(g.date[i]) - date.fromisoformat(g.date[i - 1])).days
            rc = (1 + tasso[i] / 100) ** (gg / 365) - 1
            quote = {k: v * (1 + rc) if k == "CASH" else v * (1 + g.rend(tick(k), i)) * f for k, v in quote.items()}
            valore = sum(quote.values())
        if i in piani:                               # rotazione: si riparte dai pesi del piano
            valore, quote = P._ribilancia(valore, quote, piani[i])
            in_attesa, v_rot, fermi = [], valore, set()
        elif in_attesa and quote:                    # vendite decise ieri sera: eseguite alla chiusura di oggi
            for k, quota in in_attesa:
                if k in quote:
                    x = quote[k] * quota
                    quote[k] -= x
                    quote["CASH"] = quote.get("CASH", 0) + x * (1 - P.COSTO)
                    vendite += 1
            in_attesa = []
            valore = sum(quote.values())
        if quote and allarme == "mercato":
            for k in list(quote):
                if k in DIFESA or k in fermi or quote[k] <= 0:
                    continue
                col = g.p.get(tick(k))
                m = sma(col, i) if col else None
                if m and col[i] and col[i] < m * (1 - MARGINE_TREND):
                    in_attesa.append((k, 1.0))
                    fermi.add(k)
        elif quote and allarme == "portafoglio" and v_rot and "PORT" not in fermi:
            if valore / v_rot - 1 < -soglia:
                in_attesa += [(k, 0.5) for k in quote if k not in DIFESA]
                fermi.add("PORT")
        curva.append((g.date[i], valore))
    return curva, vendite


def misura(curva):
    st = P.statistiche(P._tagli(curva, al="2015-12-31"))
    oo = P.statistiche(P._tagli(curva, dal=P.OOS_DAL))
    return st, oo


def main():
    cartella, satf = sys.argv[1], sys.argv[2]
    px = P.prezzi(scarica=None, cartella=cartella)
    ss = P.serie_satellite(json.load(open(satf, encoding="utf-8")), [d for d, _ in px["SPY"]])
    if ss:
        px["SAT"] = ss
    fx, te = P.cambio_eur(cartella), P.tassi_eur(cartella)
    g = P.Griglia(px)
    giorni = P.date_ribilancio(g)
    anni = (len(g.date) - giorni[0]) / 252
    print(f"Periodo {g.date[giorni[0]]} - {g.date[-1]} ({anni:.1f} anni). Misura: EURO, acquisto prudente, AZ = S&P 500")
    f = lambda s: f"{s['cagr']:6.1f}{s['vol']:6.1f}{s['maxdd']:7.1f}{(s["cagr"] / s["vol"] if s["vol"] else 0):6.3f}"
    for prof in P.PROFILI:
        print(f"\n=== {prof['nome']} ===")
        print(f"{'':30}{'STUDIO 2006-2015':^25}|{'FUORI CAMPIONE 2016+':^25}| vendite/anno")
        print(f"{'':30}" + ("  CAGR   Vol  MaxDD  R/V|" * 2))
        base = piano(prof, g, giorni)
        vol = piano(prof, g, giorni, pesi_vol=True)
        prove = [("0 attuale", base, None), ("1 pesi per volatilita'", vol, None),
                 ("2 allarme per mercato", base, "mercato"), ("3 allarme di portafoglio", base, "portafoglio"),
                 ("4 combinazione 1+2", vol, "mercato")]
        rif = None
        for nome, pi, al in prove:
            c, vend = simula(g, pi, giorni[0], fx, te, al, SOGLIA_PORT[prof["id"]])
            st, oo = misura(c)
            esito = ""
            if rif is None:
                rif = (st, oo)
            else:
                rv = lambda s: s["cagr"] / s["vol"] if s["vol"] else 0
                ok = rv(oo) > rv(rif[1]) and oo["maxdd"] >= rif[1]["maxdd"] - 1 and rv(st) >= rv(rif[0]) - 0.05
                esito = "  ENTRA" if ok else "  scartata"
            print(f"{nome:30}{f(st)}|{f(oo)}| {vend / anni:5.1f}{esito}")


if __name__ == "__main__":
    main()
