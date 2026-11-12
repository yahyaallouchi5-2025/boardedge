# -*- coding: utf-8 -*-
"""
studio_modalita_mercato.py - LE TRE "MODALITA' DI MERCATO" (The Long and Short of It, cap. K3) PREVEDONO I MESI DOPO?

MODALITA' a fine mese, solo con prezzi gia' noti (S&P 500 con dividendi, SPY):
  PESSIMISMO        prezzo sotto la media a 200 giorni
  ECCESSO           prezzo sopra la media di piu' dell'80o percentile della distanza negli ultimi 5 anni
                    (mercato "staccato" dai suoi livelli abituali)
  NORMALE           tutto il resto
REGOLE FISSATE PRIMA DI VEDERE I RISULTATI
  - rendimento dell'S&P 500 nel mese e nei 3 mesi successivi meno la liquidita' (DTB3), drawdown nei 3 mesi;
  - sviluppo 1999-2010, verifica 2011-2026 (i primi 5 anni servono al percentile);
  - VANTAGGIO dell'idea "ridurre in ECCESSO" solo se in ENTRAMBI i periodi il rendimento a 3 mesi in ECCESSO e'
    piu' basso di NORMALE (la regola del sito su PESSIMISMO esiste gia' ed e' stata testata a parte).
USO: STORICO=<cartella con DTB3.csv e yahoo/SPY.csv> python studi/studio_modalita_mercato.py
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from studio_regime_macro import fine_mese, leggi   # noqa: E402

TAGLIO = "2011-01"


def main():
    spy = leggi(os.path.join("yahoo", "SPY.csv"))
    t3m = fine_mese(leggi("DTB3.csv"))
    d = [x[0] for x in spy]
    p = [x[1] for x in spy]
    dist = [None] * len(p)
    for i in range(200, len(p)):
        dist[i] = p[i] / (sum(p[i - 200:i]) / 200) - 1
    fine = {}
    for i, x in enumerate(d):
        fine[x[:7]] = i                                  # ultimo giorno di borsa di ogni mese
    mesi = sorted(fine)
    righe = []
    for k, m in enumerate(mesi[:-3]):
        i = fine[m]
        if dist[i] is None or i < 1460 or m < "1999-01" or m not in t3m:
            continue
        passato = sorted(v for v in dist[i - 1260:i] if v is not None)
        soglia = passato[int(0.8 * len(passato))]
        mod = "PESSIMISMO" if dist[i] < 0 else "ECCESSO" if dist[i] > soglia else "NORMALE"
        i1, i3 = fine[mesi[k + 1]], fine[mesi[k + 3]]
        rf = t3m[m] / 1200
        dd = min(p[j] for j in range(i, i3 + 1)) / p[i] - 1
        righe.append({"m": m, "mod": mod, "r1": p[i1] / p[i] - 1 - rf, "r3": p[i3] / p[i] - 1 - 3 * rf, "dd3": dd})
    out = {}
    for per, ok in (("sviluppo", lambda m: m < TAGLIO), ("verifica", lambda m: m >= TAGLIO)):
        out[per] = {}
        for mod in ("PESSIMISMO", "NORMALE", "ECCESSO"):
            rr = [x for x in righe if x["mod"] == mod and ok(x["m"])]
            if not rr:
                continue
            r3 = [x["r3"] for x in rr]
            mu = sum(r3) / len(r3)
            sd = math.sqrt(sum((v - mu) ** 2 for v in r3) / (len(r3) - 1)) if len(r3) > 1 else 0
            out[per][mod] = {"mesi": len(rr), "eccesso_1m_%": round(sum(x["r1"] for x in rr) / len(rr) * 100, 2),
                             "eccesso_3m_%": round(mu * 100, 2), "dev_std_3m_%": round(sd * 100, 1),
                             "positivi_3m_%": round(100 * sum(v > 0 for v in r3) / len(r3)),
                             "drawdown_3m_medio_%": round(sum(x["dd3"] for x in rr) / len(rr) * 100, 1)}
    s, v = out["sviluppo"], out["verifica"]
    out["VANTAGGIO_ridurre_in_eccesso"] = (s["ECCESSO"]["eccesso_3m_%"] < s["NORMALE"]["eccesso_3m_%"]
                                          and v["ECCESSO"]["eccesso_3m_%"] < v["NORMALE"]["eccesso_3m_%"])
    out["modalita_oggi"] = righe[-1]["mod"] if righe else None
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return out


if __name__ == "__main__":
    main()
