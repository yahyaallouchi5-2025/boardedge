# -*- coding: utf-8 -*-
"""
studio_vix.py - IL VIX (volatilita' attesa dal mercato delle opzioni) DICE QUALCOSA DI UTILE PER IL TERMINALE?

IDEA (Hull, capitoli su volatilita' e opzioni): il VIX e' la volatilita' annua che le opzioni sull'S&P 500 prezzano
per i 30 giorni successivi. Tre domande, con dati dal 1993:
  1) PREMIO: il VIX sta in media sopra la volatilita' che poi si realizza? (e' il compenso di chi vende opzioni:
     base dello studio sulle strategie buy-write / put-write)
  2) PREVISIONE: per prevedere la volatilita' dei 21 giorni successivi sbaglia meno il VIX, la EWMA (lambda 0,94)
     o la deviazione standard semplice a 20 giorni?
  3) RENDIMENTI: dopo un VIX alto (sopra l'80o percentile dei 5 anni PRIMA) l'S&P 500 rende di piu' nei 21 giorni
     successivi rispetto a tutti gli altri giorni?
REGOLE FISSATE PRIMA DI VEDERE I RISULTATI
  - una misura ogni 21 sedute (niente finestre sovrapposte); sviluppo fino al 31/12/2015, verifica dal 2016;
  - errore di previsione = |previsto - realizzato| / realizzato, media;
  - domanda 3: differenza delle medie, incertezza su blocchi di 6 misure (circa 6 mesi), z = 2,81;
    VANTAGGIO solo se il limite basso e' sopra zero nello sviluppo E la differenza resta sopra zero nella verifica.
DATI: VIX da FRED (VIXCLS), S&P 500 con dividendi da EODHD (SPY.US). Chiavi solo dai Secrets.
USO: python studi/studio_vix.py
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cot_radar import eodhd, fonti   # noqa: E402

TAGLIO = "2016-01-01"
PASSO = 21
Z = 2.81


def sd(x):
    m = sum(x) / len(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))


def media_ic(x, blocco=6):
    """media e intervallo (z = 2,81) calcolato sulle medie di blocchi consecutivi."""
    if len(x) < blocco * 4:
        return None
    b = [sum(x[i:i + blocco]) / len(x[i:i + blocco]) for i in range(0, len(x), blocco)]
    m = sum(b) / len(b)
    e = Z * sd(b) / math.sqrt(len(b))
    return {"n": len(x), "media": round(m, 2), "ic": [round(m - e, 2), round(m + e, 2)]}


def main():
    spy = eodhd.serie("SPY.US", "1993-01-01") or []
    vix = dict(fonti.get_fred("VIXCLS", "1990-01-01") or [])
    print("SPY", len(spy), "VIX", len(vix), flush=True)
    if len(spy) < 3000 or len(vix) < 3000:
        print("dati insufficienti")
        return 1
    d = [x[0] for x in spy]
    r = [0.0] + [math.log(spy[i][1] / spy[i - 1][1]) for i in range(1, len(spy))]
    ew = [r[1] ** 2] * 2
    for x in r[2:]:
        ew.append(0.94 * ew[-1] + 0.06 * x * x)
    ann = lambda v: v * math.sqrt(252) * 100
    out = {}
    for per, ok in (("sviluppo", lambda g: g < TAGLIO), ("verifica", lambda g: g >= TAGLIO)):
        premio, err, alto, resto = [], {"VIX": [], "EWMA": [], "semplice 20g": []}, [], []
        for i in range(1300, len(spy) - PASSO, PASSO):
            v = vix.get(d[i])
            if v is None or not ok(d[i]):
                continue
            reale = ann(sd(r[i + 1:i + 1 + PASSO]))
            premio.append(v - reale)
            for nome, p in (("VIX", v), ("EWMA", ann(math.sqrt(ew[i]))), ("semplice 20g", ann(sd(r[i - 19:i + 1])))):
                err[nome].append(abs(p - reale) / reale * 100)
            passato = sorted(vix[g] for g in d[i - 1260:i] if g in vix)
            rend = (spy[i + PASSO][1] / spy[i][1] - 1) * 100
            (alto if v > passato[int(0.8 * len(passato))] else resto).append(rend)
        diff = None
        if len(alto) >= 12 and len(resto) >= 24:
            ma, mr = sum(alto) / len(alto), sum(resto) / len(resto)
            e = Z * math.sqrt(sd(alto) ** 2 / len(alto) + sd(resto) ** 2 / len(resto))
            diff = {"n_alto": len(alto), "n_resto": len(resto), "dopo_vix_alto": round(ma, 2), "altri": round(mr, 2),
                    "differenza": round(ma - mr, 2), "ic": [round(ma - mr - e, 2), round(ma - mr + e, 2)]}
        out[per] = {"1_premio_vix_meno_realizzata": media_ic(premio),
                    "1_volte_vix_sopra_%": round(100 * sum(x > 0 for x in premio) / len(premio)),
                    "2_errore_previsione_%": {k: round(sum(v) / len(v), 1) for k, v in err.items()},
                    "3_rendimento_21g_%": diff}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    os.makedirs("studio_out", exist_ok=True)
    with open("studio_out/vix.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
