# -*- coding: utf-8 -*-
"""
studio_opzioni.py - VENDERE OPZIONI SULL'S&P 500 BATTE IL SEMPLICE "COMPRA E TIENI"?

IDEA (Hull, strategie con opzioni; studio VIX del 12/11/2026: il VIX sta in media 3,6 punti sopra la volatilita' che
poi si realizza = chi vende opzioni incassa un premio). Il CBOE pubblica da decenni indici che applicano la regola
in modo meccanico, ogni mese, senza scelte:
  BXM  = S&P 500 + vendita di una call a un mese "at the money" (buy-write / covered call)
  PUT  = liquidita' in Treasury + vendita di una put a un mese "at the money" (put-write)
  BXMD = come BXM ma call 30 delta (piu' lontana)   PPUT = S&P 500 + put di protezione 5% fuori dal prezzo
Sono indici a rendimento totale, SENZA costi e tasse: il risultato reale e' un po' piu' basso.

REGOLE FISSATE PRIMA DI VEDERE I RISULTATI
  - confronto con l'S&P 500 a rendimento totale (SPY rettificato) sugli STESSI mesi, rendimenti mensili;
  - sviluppo fino al 31/12/2015, verifica dal 01/01/2016;
  - misure: rendimento annuo, volatilita', drawdown massimo, Calmar, Sortino (soglia zero);
  - VANTAGGIO solo se Calmar E Sortino sono piu' alti dell'S&P 500 in ENTRAMBI i periodi. Si riporta comunque
    quanto rendimento annuo si lascia sul tavolo.
DATI: EODHD (indici .INDX), SPY.US. La chiave arriva solo dai Secrets. Se un indice non e' nel piano viene saltato.
USO: python studi/studio_opzioni.py
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cot_radar import eodhd   # noqa: E402

INDICI = ["BXM", "PUT", "BXMD", "PPUT", "CLL", "BXY"]
TAGLIO = "2016-01"


def mensili(pts):
    """{aaaa-mm: rendimento del mese} dai prezzi di fine mese."""
    fine = {}
    for d, p in pts:
        if p and p > 0:
            fine[d[:7]] = p
    m = sorted(fine)
    return {m[i]: fine[m[i]] / fine[m[i - 1]] - 1 for i in range(1, len(m))}


def misure(r):
    n = len(r)
    if n < 36:
        return None
    v, picco, dd = 1.0, 1.0, 0.0
    for x in r:
        v *= 1 + x
        picco = max(picco, v)
        dd = min(dd, v / picco - 1)
    cagr = v ** (12 / n) - 1
    mu = sum(r) / n
    vol = math.sqrt(sum((x - mu) ** 2 for x in r) / (n - 1) * 12)
    giu = math.sqrt(sum(min(x, 0) ** 2 for x in r) / n * 12)
    return {"mesi": n, "cagr": round(cagr * 100, 1), "vol": round(vol * 100, 1), "maxdd": round(dd * 100, 1),
            "calmar": round(cagr / abs(dd), 2) if dd else None, "sortino": round(mu * 12 / giu, 2) if giu else None}


def main():
    if not eodhd.attivo():
        print("manca EODHD_API_KEY")
        return 1
    spy = mensili(eodhd.serie("SPY.US", "1993-01-01") or [])
    print("SPY mesi", len(spy), flush=True)
    out = {}
    for nome in INDICI:
        pts = eodhd.serie(nome + ".INDX", "1986-01-01") or []
        if len(pts) < 1000:
            print(nome, "non disponibile (", len(pts), "prezzi )", flush=True)
            continue
        m = mensili(pts)
        comuni = sorted(k for k in m if k in spy)
        print(nome, "dal", pts[0][0], "al", pts[-1][0], "mesi in comune", len(comuni), flush=True)
        out[nome] = {}
        for per, ok in (("sviluppo", lambda k: k < TAGLIO), ("verifica", lambda k: k >= TAGLIO)):
            kk = [k for k in comuni if ok(k)]
            a, b = misure([m[k] for k in kk]), misure([spy[k] for k in kk])
            vant = bool(a and b and a["calmar"] and b["calmar"] and a["calmar"] > b["calmar"] and a["sortino"] > b["sortino"])
            out[nome][per] = {"dal": kk[0] if kk else None, "indice": a, "sp500": b, "meglio_su_rischio": vant}
    print(json.dumps(out, indent=1))
    os.makedirs("studio_out", exist_ok=True)
    with open("studio_out/opzioni.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
