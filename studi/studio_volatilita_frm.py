# -*- coding: utf-8 -*-
"""
studio_volatilita_frm.py - LA VOLATILITA' "CHE SI AGGIORNA" (FRM Quantitative Analysis: EWMA / GARCH, backtest del VaR)
PREVEDE IL RISCHIO DI DOMANI MEGLIO DELLO STORICO FISSO? - Ya, 13/11/2026. Solo studio.

PERCHE' SERVE: chi opera a leva deve sapere OGGI quanto puo' muoversi lo strumento, per mettere stop e target alla
  distanza giusta e scegliere la dimensione. Il sito oggi usa lo storico degli ultimi 3 anni (uguale ogni giorno).
METODI A CONFRONTO (regole fissate prima; ogni giorno si usano solo i dati fino al giorno prima):
  M1 STORICO     5 percentile dei rendimenti degli ultimi 756 giorni (3 anni)
  M2 EWMA        volatilita' con media esponenziale (lambda 0,94, RiskMetrics) x 1,645 (curva normale)
  M3 EWMA+CODE   volatilita' EWMA x 5 percentile dei rendimenti passati DIVISI per la loro volatilita' EWMA
                 (tiene conto delle code vere: "filtered historical simulation")
MISURA (quella del libro): la perdita di un giorno deve superare la soglia nel 5% dei giorni.
  - quota di superamenti e test di Kupiec (p > 0,05 = la soglia e' onesta);
  - RAGGRUPPAMENTO: probabilita' di un superamento il giorno DOPO un superamento (ideale 5%: se e' molto piu' alta
    la soglia non si adatta e i giorni brutti arrivano a grappoli, proprio quando la leva fa piu' male);
  - errore di previsione: perdita "quantile" media (piu' bassa = previsione migliore).
  Un metodo ENTRA se in STUDIO (fino al 2015) e VERIFICA (dal 2016) ha Kupiec onesto sulla maggioranza degli
  strumenti, raggruppamento piu' basso di M1 e perdita quantile piu' bassa di M1.
USO: python studi/studio_volatilita_frm.py <cartella yahoo>
"""
import csv
import math
import os
import sys

ETF = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "GLD", "SLV", "USO", "UNG", "CPER", "BTC-USD"]
LAM, Q, FIN, CAMBIO = 0.94, 0.05, 756, "2016-01-01"


def leggi(f):
    out = []
    for r in csv.reader(open(f)):
        try:
            v = float(r[1])
        except (ValueError, IndexError):
            continue
        if v > 0:
            out.append((r[0], v))
    return out


def kupiec_p(n, x, p=Q):
    if n == 0 or x == 0 or x == n:
        return 0.0
    f = x / n
    lr = -2 * ((n - x) * math.log((1 - p) / (1 - f)) + x * math.log(p / f))
    return math.erfc(math.sqrt(max(lr, 0) / 2))        # chi-quadro con 1 grado di liberta'


def quantile(v, q):
    s = sorted(v)
    return s[max(0, int(len(s) * q) - 1)] if int(len(s) * q) else s[0]


def prova(px):
    d = [x[0] for x in px]
    r = [px[i][1] / px[i - 1][1] - 1 for i in range(1, len(px))]
    d = d[1:]
    var = sum(x * x for x in r[:60]) / 60
    sig = [None] * len(r)                               # volatilita' prevista per il giorno i (dati fino a i-1)
    for i in range(60, len(r)):
        sig[i] = math.sqrt(var)
        var = LAM * var + (1 - LAM) * r[i] ** 2
    out = {"M1": [], "M2": [], "M3": []}
    for i in range(60 + FIN, len(r)):
        fin = r[i - FIN:i]
        z = [r[j] / sig[j] for j in range(i - FIN, i) if sig[j]]
        soglie = {"M1": quantile(fin, Q), "M2": -1.645 * sig[i], "M3": quantile(z, Q) * sig[i]}
        for k, s in soglie.items():
            out[k].append((d[i], r[i], s))
    return out


def misura(righe):
    n = len(righe)
    sup = [x[1] < x[2] for x in righe]
    x = sum(sup)
    dopo = [sup[i] for i in range(1, n) if sup[i - 1]]
    ql = sum((Q - (r < s)) * (r - s) for _, r, s in righe) / n * 1e4   # perdita quantile (punti base)
    return {"n": n, "pct": 100 * x / n, "p": kupiec_p(n, x), "dopo": 100 * sum(dopo) / len(dopo) if dopo else 0,
            "ql": ql, "soglia": -100 * sum(s for _, _, s in righe) / n}


def main():
    cart = sys.argv[1]
    tot = {}
    print(f"{'':9}{'STUDIO -2015':^37}|{'VERIFICA 2016+':^37}|")
    print(f"{'':9}" + (" super.%  Kupiec  dopo%  errore soglia|" * 2))
    for t in ETF:
        f = os.path.join(cart, t + ".csv")
        if not os.path.exists(f):
            continue
        res = prova(leggi(f))
        for k, righe in res.items():
            s = ""
            for nome, sel in (("st", lambda x: x[0] < CAMBIO), ("ve", lambda x: x[0] >= CAMBIO)):
                rr = [x for x in righe if sel(x)]
                if len(rr) < 250:
                    s += f"{'-':^37}|"
                    continue
                m = misura(rr)
                tot.setdefault((k, nome), []).append(m)
                s += f"{m['pct']:7.2f}{m['p']:8.2f}{m['dopo']:7.1f}{m['ql']:8.2f}{m['soglia']:6.2f}%|"
            print(f"{t:6}{k:3}{s}")
    print("\nRIEPILOGO (media sugli strumenti)")
    for nome, tit in (("st", "STUDIO"), ("ve", "VERIFICA")):
        for k in ("M1", "M2", "M3"):
            v = tot.get((k, nome), [])
            if not v:
                continue
            print(f"  {tit:9}{k}: superamenti {sum(m['pct'] for m in v) / len(v):.2f}%  Kupiec onesto su "
                  f"{sum(m['p'] > 0.05 for m in v)}/{len(v)}  superamento dopo un superamento "
                  f"{sum(m['dopo'] for m in v) / len(v):.1f}%  errore {sum(m['ql'] for m in v) / len(v):.2f}")


if __name__ == "__main__":
    main()
