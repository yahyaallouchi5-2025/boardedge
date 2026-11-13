# -*- coding: utf-8 -*-
"""
studio_volatilita_frm2.py - SEGUITO di studio_volatilita_frm.py (Ya, 13/11/2026): il metodo "EWMA + code" regge anche
  (a) sulle coppie forex e sui metalli spot, (b) su 5 e 21 giorni (l'orizzonte di chi tiene una posizione a leva)?
METODI (stesse regole del primo studio, fissate prima):
  M1 STORICO   5 percentile dei rendimenti a H giorni degli ultimi 756 giorni
  M3 EWMA+CODE volatilita' EWMA di oggi (lambda 0,94) x radice(H) x 5 percentile dei rendimenti passati a H giorni
               divisi per (volatilita' EWMA di allora x radice(H))
MISURA: finestre NON sovrapposte (una ogni H giorni: cosi' i test sono validi). Superamenti (ideale 5%), Kupiec,
  errore quantile. ENTRA su un orizzonte se in studio (fino al 2015) e verifica (dal 2016) l'errore medio e' piu'
  basso di M1 e Kupiec e' onesto almeno quanto M1.
USO: python studi/studio_volatilita_frm2.py <cartella yahoo> <cartella pat>
"""
import glob
import gzip
import json
import math
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from studio_volatilita_frm import ETF, LAM, Q, FIN, CAMBIO, leggi, kupiec_p, quantile   # noqa: E402


def serie_pat(f):
    d = json.load(gzip.open(f, "rt"))
    return d["id"], [(datetime.fromtimestamp(x[0], timezone.utc).date().isoformat(), x[4]) for x in d["d"] if x[4] and x[4] > 0]


def prova(px, H):
    d = [x[0] for x in px]
    lp = [math.log(x[1]) for x in px]
    r = [lp[i] - lp[i - 1] for i in range(1, len(lp))]
    var = sum(x * x for x in r[:60]) / 60
    sig = [None] * (len(r) + 1)                         # sig[i] = volatilita' nota alla chiusura del giorno i
    for i in range(60, len(r)):
        var = LAM * var + (1 - LAM) * r[i] ** 2
        sig[i + 1] = math.sqrt(var)
    rh = lambda i: lp[i + H] - lp[i]                    # noqa: E731  rendimento da chiusura i a i+H
    out = {"M1": [], "M3": []}
    for i in range(61 + FIN + H, len(lp) - H, H):
        passati = [j for j in range(i - FIN - H, i - H + 1) if sig[j]]
        ret = [rh(j) for j in passati]
        z = [rh(j) / (sig[j] * math.sqrt(H)) for j in passati]
        out["M1"].append((d[i], rh(i), quantile(ret, Q)))
        out["M3"].append((d[i], rh(i), quantile(z, Q) * sig[i] * math.sqrt(H)))
    return out


def misura(righe):
    n = len(righe)
    x = sum(r < s for _, r, s in righe)
    return {"pct": 100 * x / n, "p": kupiec_p(n, x), "ql": sum((Q - (r < s)) * (r - s) for _, r, s in righe) / n * 1e4}


def main():
    cy, cp = sys.argv[1], sys.argv[2]
    serie = [(t, leggi(os.path.join(cy, t + ".csv"))) for t in ETF if os.path.exists(os.path.join(cy, t + ".csv"))]
    serie += [serie_pat(f) for f in sorted(glob.glob(os.path.join(cp, "*.json.gz")))]
    print("strumenti:", len(serie))
    for H in (1, 5, 21):
        tot = {}
        for nome, px in serie:
            if len(px) < FIN + 600:
                continue
            for k, righe in prova(px, H).items():
                for per, sel in (("studio", lambda x: x[0] < CAMBIO), ("verifica", lambda x: x[0] >= CAMBIO)):
                    rr = [x for x in righe if sel(x)]
                    if len(rr) >= 40:
                        tot.setdefault((per, k), {})[nome] = misura(rr)
        print(f"\n=== ORIZZONTE {H} GIORNI")
        for per in ("studio", "verifica"):
            a, b = tot.get((per, "M1"), {}), tot.get((per, "M3"), {})
            com = sorted(set(a) & set(b))
            if not com:
                continue
            for k, v in (("M1 storico", a), ("M3 EWMA+code", b)):
                print(f"  {per:9}{k:14} superamenti {sum(v[n]['pct'] for n in com) / len(com):5.2f}%  Kupiec onesto "
                      f"{sum(v[n]['p'] > 0.05 for n in com):2}/{len(com)}  errore {sum(v[n]['ql'] for n in com) / len(com):7.2f}")
            print(f"  {per:9}M3 ha errore piu' basso su {sum(b[n]['ql'] < a[n]['ql'] for n in com)}/{len(com)} strumenti "
                  f"(riduzione media {100 * (1 - sum(b[n]['ql'] for n in com) / sum(a[n]['ql'] for n in com)):.1f}%)")


if __name__ == "__main__":
    main()
