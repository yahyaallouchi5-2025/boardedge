# -*- coding: utf-8 -*-
"""
studio_opzioni.py - VENDERE OPZIONI SULL'S&P 500 (buy-write, put-write) BATTE IL TENERE L'INDICE?

IDEA (Hull, strategie con opzioni; studio VIX del 12/11/2026: il VIX sta in media 3,6 punti sopra la volatilita'
che poi si realizza, quindi chi vende opzioni incassa un premio). Qui si misura se quel premio si vede davvero nei
risultati, con gli indici ufficiali CBOE che replicano le due strategie meccaniche:
  BXM = S&P 500 + vendita ogni mese di una call alla pari (buy-write, "covered call")
  PUT = liquidita' in titoli di Stato + vendita ogni mese di una put alla pari (put-write)
confrontati con l'S&P 500 con dividendi (SPY, prezzi rettificati EODHD).
REGOLE FISSATE PRIMA DI VEDERE I RISULTATI
  - rendimenti mensili in dollari (fine mese), stesso periodo per tutti; sviluppo fino al 31/12/2015, verifica dal 2016;
  - misure: rendimento annuo, volatilita', drawdown massimo, Calmar, Sortino (soglia 0), asimmetria, mese peggiore;
  - VANTAGGIO solo se Calmar E Sortino sono sopra quelli dell'S&P 500 in ENTRAMBI i periodi;
  - in piu': differenza media mensile contro l'S&P 500 con intervallo (blocchi di 6 mesi, z = 2,81).
LIMITI: gli indici non pagano commissioni, differenze denaro/lettera ne' tasse; un privato europeo li replica solo
  con opzioni vere (multiplo 100) o con ETF a gestione simile: il risultato reale e' piu' basso.
DATI: file pubblici CBOE (cdn.cboe.com), User-Agent onesto. USO: python studi/studio_opzioni.py
"""
import json
import math
import os
import sys
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cot_radar import eodhd   # noqa: E402

URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{}_History.csv"
TAGLIO = "2016-01"
Z = 2.81


def cboe(nome):
    """[(data ISO, valore)] dal file storico CBOE dell'indice. Stampa l'intestazione (per capire il formato)."""
    req = urllib.request.Request(URL.format(nome), headers={"User-Agent": "BoardEdge studio (ricerca, uso personale)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        testo = r.read().decode("utf-8", "replace")
    righe = testo.splitlines()
    print(nome, "righe:", len(righe), "| intestazione:", righe[:2], flush=True)
    out = []
    for riga in righe:
        c = [x.strip().strip('"') for x in riga.split(",")]
        if len(c) < 2:
            continue
        d = None
        for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                d = datetime.strptime(c[0], fmt).date().isoformat()
                break
            except ValueError:
                pass
        try:
            v = float(c[-1])
        except ValueError:
            continue
        if d and v > 0:
            out.append((d, v))
    return sorted(out)


def mensili(pts):
    fine = {}
    for d, v in pts:
        fine[d[:7]] = v
    m = sorted(fine)
    return {m[i]: fine[m[i]] / fine[m[i - 1]] - 1 for i in range(1, len(m))}


def misure(r):
    n = len(r)
    mu = sum(r) / n
    sd = math.sqrt(sum((v - mu) ** 2 for v in r) / (n - 1))
    v, picco, dd = 1.0, 1.0, 0.0
    for x in r:
        v *= 1 + x
        picco = max(picco, v)
        dd = min(dd, v / picco - 1)
    cagr = v ** (12 / n) - 1
    giu = math.sqrt(sum(min(x, 0) ** 2 for x in r) / n) * math.sqrt(12)
    return {"mesi": n, "rend_annuo_%": round(cagr * 100, 1), "volatilita_%": round(sd * math.sqrt(12) * 100, 1),
            "max_drawdown_%": round(dd * 100, 1), "calmar": round(cagr / -dd, 2) if dd else None,
            "sortino": round(mu * 12 / giu, 2) if giu else None,
            "asimmetria": round(sum(((x - mu) / sd) ** 3 for x in r) * n / ((n - 1) * (n - 2)), 2),
            "mese_peggiore_%": round(min(r) * 100, 1)}


def differenza(a, b, blocco=6):
    d = [x - y for x, y in zip(a, b)]
    bl = [sum(d[i:i + blocco]) / len(d[i:i + blocco]) for i in range(0, len(d), blocco)]
    m = sum(bl) / len(bl)
    sd = math.sqrt(sum((x - m) ** 2 for x in bl) / (len(bl) - 1))
    e = Z * sd / math.sqrt(len(bl))
    return {"media_mese_%": round(m * 100, 2), "ic": [round((m - e) * 100, 2), round((m + e) * 100, 2)]}


def main():
    serie = {"S&P 500": mensili(eodhd.serie("SPY.US", "1993-01-01") or [])}
    for nome in ("BXM", "PUT"):
        try:
            serie[nome] = mensili(cboe(nome))
        except Exception as e:
            print(nome, "non scaricato:", getattr(e, "code", type(e).__name__))
    if len(serie) < 2 or not serie["S&P 500"]:
        print("dati insufficienti")
        return 1
    mesi = sorted(set.intersection(*[set(s) for s in serie.values()]))
    print("periodo comune:", mesi[0], "-", mesi[-1], "mesi:", len(mesi), flush=True)
    out = {}
    for per, ok in (("sviluppo", lambda m: m < TAGLIO), ("verifica", lambda m: m >= TAGLIO)):
        mm = [m for m in mesi if ok(m)]
        out[per] = {n: misure([s[m] for m in mm]) for n, s in serie.items()}
        for n in serie:
            if n != "S&P 500":
                out[per][n]["contro_sp500"] = differenza([serie[n][m] for m in mm], [serie["S&P 500"][m] for m in mm])
    print(json.dumps(out, indent=1, ensure_ascii=False))
    os.makedirs("studio_out", exist_ok=True)
    with open("studio_out/opzioni.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
