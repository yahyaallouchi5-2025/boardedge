# -*- coding: utf-8 -*-
"""
studio_oro_motori.py - "COSA MUOVE L'ORO" ("How to Profit in Gold", cap. 2 e appendice A) MESSO ALLA PROVA.
Ya, 13/11/2026. Solo studio: il sito non cambia.

IL LIBRO DICE: l'oro sale quando il DOLLARO scende e quando i TASSI scendono (tenere oro costa meno).
DOMANDA: sapere oggi dove vanno dollaro e tassi aiuta a guadagnare sull'oro NEL MESE DOPO? (se l'effetto e' solo
  contemporaneo non serve a nulla: lo si misura a parte per mostrarlo.)
DATI: GLD (oro), indice ampio del dollaro FRED DTWEXBGS, IEF (Treasury 7-10 anni: prezzo su = tassi giu').
  LIMITE DICHIARATO: i tassi REALI (FRED DFII10) non sono in archivio: si usa il tasso nominale tramite IEF.
REGOLE (fissate PRIMA di vedere i risultati), decisione a fine mese, valida per il mese dopo, costo 0,10% a cambio:
  G1 DOLLARO   dollaro piu' basso di 3 mesi fa  -> oro, altrimenti liquidita' (SHY)
  G2 TASSI     IEF piu' alto di 3 mesi fa (tassi scesi) -> oro, altrimenti liquidita'
  G3 ENTRAMBI  G1 e G2 insieme
  G4 UNO DEI DUE
  G5 TREND     oro sopra la sua media a 10 mesi (confronto: la regola che il sito usa gia' sull'S&P 500)
  ENTRA solo se in ENTRAMBI i periodi (studio fino al 2015, verifica dal 2016) batte "oro sempre" per
  rendimento/volatilita' E rendimento/drawdown, con almeno 2,6% l'anno.
PER CHI OPERA A LEVA (richiesta di Ya): per la regola migliore si misura, nei 21 giorni di borsa dopo ogni segnale,
  l'escursione contraria massima (MAE, per lo stop) e favorevole massima (MFE, per il target), contro tutti i mesi.
USO: python studi/studio_oro_motori.py <cartella yahoo> <cartella FRED>
"""
import csv
import math
import os
import sys

COSTO, CAMBIO, MIN_REND = 0.001, "2016-01", 2.6


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


def fine_mese(px):
    m = {}
    for d, p in px:
        m[d[:7]] = p
    return m


def stat(rs):
    """rs = [(mese, rendimento)]"""
    if len(rs) < 12:
        return None
    v, pk, dd = 1.0, 1.0, 0.0
    for _, r in rs:
        v *= 1 + r
        pk = max(pk, v)
        dd = min(dd, v / pk - 1)
    anni = len(rs) / 12
    cagr = (v ** (1 / anni) - 1) * 100
    m = sum(r for _, r in rs) / len(rs)
    vol = math.sqrt(sum((r - m) ** 2 for _, r in rs) / (len(rs) - 1) * 12) * 100
    return {"cagr": cagr, "vol": vol, "dd": dd * 100, "rv": cagr / vol if vol else 0,
            "calmar": cagr / -dd / 100 if dd < 0 else 0}


def fmt(s):
    return f"{s['cagr']:6.1f}{s['vol']:6.1f}{s['dd']:7.1f}{s['rv']:6.2f}{s['calmar']:6.2f}" if s else f"{'-':^31}"


def corr(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((x - mb) ** 2 for x in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


def main():
    cy, cf = sys.argv[1], sys.argv[2]
    gld_g = leggi(os.path.join(cy, "GLD.csv"))
    gld, ief, shy = fine_mese(gld_g), fine_mese(leggi(os.path.join(cy, "IEF.csv"))), fine_mese(leggi(os.path.join(cy, "SHY.csv")))
    usd = fine_mese(leggi(os.path.join(cf, "DTWEXBGS.csv")))
    mesi = sorted(set(gld) & set(ief) & set(usd) & set(shy))
    r = lambda s, i: s[mesi[i]] / s[mesi[i - 1]] - 1   # noqa: E731
    # 1) effetto contemporaneo e anticipato (correlazioni mensili)
    ro = [r(gld, i) for i in range(1, len(mesi))]
    rd = [r(usd, i) for i in range(1, len(mesi))]
    rt = [r(ief, i) for i in range(1, len(mesi))]
    print(f"mesi {mesi[0]} - {mesi[-1]} ({len(mesi)})")
    print(f"STESSO MESE   oro/dollaro {corr(ro, rd):+.2f}   oro/Treasury {corr(ro, rt):+.2f}")
    print(f"MESE DOPO     dollaro di ieri -> oro di oggi {corr(ro[1:], rd[:-1]):+.2f}   "
          f"Treasury di ieri -> oro di oggi {corr(ro[1:], rt[:-1]):+.2f}   (|0,13| = soglia del caso al 5%)")
    # 2) regole
    regole = {"oro sempre": [], "G1 dollaro giu'": [], "G2 tassi giu'": [], "G3 entrambi": [], "G4 uno dei due": [],
              "G5 trend 10 mesi": []}
    stato = {k: False for k in regole}
    segn = {k: [] for k in regole}
    for i in range(10, len(mesi) - 1):
        d = usd[mesi[i]] < usd[mesi[i - 3]]
        t = ief[mesi[i]] > ief[mesi[i - 3]]
        tr = gld[mesi[i]] > sum(gld[mesi[i - k]] for k in range(10)) / 10
        dec = {"oro sempre": True, "G1 dollaro giu'": d, "G2 tassi giu'": t, "G3 entrambi": d and t,
               "G4 uno dei due": d or t, "G5 trend 10 mesi": tr}
        ro1, rc1 = r(gld, i + 1), r(shy, i + 1)
        for k, on in dec.items():
            x = ro1 if on else rc1
            if on != stato[k] and k != "oro sempre":
                x -= COSTO
            stato[k] = on
            regole[k].append((mesi[i + 1], x))
            if on:
                segn[k].append(mesi[i])
    print(f"\n{'':20}{'STUDIO -2015':^31}|{'VERIFICA 2016+':^31}| mesi in oro")
    print(f"{'':20}" + ("  CAGR   Vol   MaxDD   R/V  Calm|" * 2))
    base = None
    for k, rs in regole.items():
        a, b = stat([x for x in rs if x[0] < CAMBIO]), stat([x for x in rs if x[0] >= CAMBIO])
        e = ""
        if base is None:
            base = (a, b)
        else:
            ok = all(x["rv"] > y["rv"] and x["calmar"] > y["calmar"] and x["cagr"] >= MIN_REND for x, y in zip((a, b), base))
            e = "ENTRA" if ok else "scartata"
        print(f"{k:20}{fmt(a)}|{fmt(b)}| {len(segn[k]):4}  {e}")
    # 3) oro nel mese dopo: segnale acceso contro spento (t di Welch), per periodo
    print("\nRENDIMENTO MEDIO DELL'ORO NEL MESE DOPO: segnale acceso - spento")
    tutti = dict(regole["oro sempre"])
    for k in list(regole)[1:]:
        s = set(segn[k])
        for nome, sel in (("studio", lambda m: m < CAMBIO), ("verifica", lambda m: m >= CAMBIO)):
            on = [tutti[mesi[i + 1]] for i in range(10, len(mesi) - 1) if mesi[i] in s and sel(mesi[i + 1])]
            off = [tutti[mesi[i + 1]] for i in range(10, len(mesi) - 1) if mesi[i] not in s and sel(mesi[i + 1])]
            if len(on) < 5 or len(off) < 5:
                continue
            ma, mb = sum(on) / len(on), sum(off) / len(off)
            va = sum((x - ma) ** 2 for x in on) / (len(on) - 1)
            vb = sum((x - mb) ** 2 for x in off) / (len(off) - 1)
            print(f"  {k:18}{nome:9} acceso {ma * 100:+.2f}% ({len(on)})  spento {mb * 100:+.2f}% ({len(off)})  "
                  f"t = {(ma - mb) / math.sqrt(va / len(on) + vb / len(off)):+.2f}")
    # 4) escursioni a 21 giorni (per stop e target): tutti i mesi contro i mesi con segnale G5
    date = [d for d, _ in gld_g]
    px = [p for _, p in gld_g]
    ultimo = {}
    for i, d in enumerate(date):
        ultimo[d[:7]] = i
    def escursioni(ms):
        mae, mfe, fin = [], [], []
        for m in ms:
            i = ultimo.get(m)
            if i is None or i + 21 >= len(px):
                continue
            f = [px[j] / px[i] - 1 for j in range(i + 1, i + 22)]
            mae.append(min(min(f), 0) * 100)
            mfe.append(max(max(f), 0) * 100)
            fin.append(f[-1] * 100)
        return mae, mfe, fin
    q = lambda v, p: sorted(v)[int(len(v) * p)]   # noqa: E731
    print("\nORO, 21 GIORNI DOPO LA FINE MESE (senza leva): escursione contraria (MAE) e favorevole (MFE)")
    for nome, ms in (("tutti i mesi", mesi[10:-1]), ("G5 trend acceso", segn["G5 trend 10 mesi"]),
                     ("G1 dollaro giu'", segn["G1 dollaro giu'"])):
        mae, mfe, fin = escursioni(ms)
        print(f"  {nome:16} n {len(mae):3}  MAE mediana {q(mae, .5):6.2f}%  MAE peggiore 10% {q(mae, .1):6.2f}%  "
              f"MFE mediana {q(mfe, .5):5.2f}%  MFE migliore 25% {q(mfe, .75):5.2f}%  finale medio {sum(fin) / len(fin):+.2f}%  "
              f"positivi {100 * sum(x > 0 for x in fin) / len(fin):.0f}%")


if __name__ == "__main__":
    main()
