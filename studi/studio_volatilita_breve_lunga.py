# -*- coding: utf-8 -*-
"""STUDIO (novembre 2026): la volatilita' BREVE (21 sedute) confrontata con quella LUNGA (252 sedute) dice qualcosa
sul mese DOPO? E ridurre la posizione quando la breve supera la lunga migliora rendimento/rischio e drawdown?
Dati: archivio del sito (ramo storico, yahoo/*.csv; ETF dal fornitore EODHD, future da Yahoo). Per ogni strumento,
a ogni fine mese: rapporto R = vol 21 / vol 252; poi rendimento, volatilita' e drawdown massimo delle 21 sedute dopo.
Periodo di studio fino al 2015, verifica fuori campione dal 2016.
USO: python studi/studio_volatilita_breve_lunga.py <cartella con i csv>"""
import csv, glob, math, os, sys, statistics as st

def leggi(f):
    return [(r[0], float(r[1])) for r in list(csv.reader(open(f, encoding="utf-8")))[1:] if len(r) == 2 and float(r[1]) > 0]

def dev(x):
    m = sum(x) / len(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))

def tstat(x):
    return (sum(x) / len(x)) / (dev(x) / math.sqrt(len(x))) if len(x) > 2 and dev(x) > 0 else 0.0

def stat(curva):
    """CAGR %, volatilita' %, drawdown massimo % di una curva giornaliera."""
    r = [curva[i] / curva[i - 1] - 1 for i in range(1, len(curva))]
    anni = len(r) / 252
    cagr = (curva[-1] / curva[0]) ** (1 / anni) - 1
    mx, dd = curva[0], 0.0
    for v in curva:
        mx = max(mx, v); dd = min(dd, v / mx - 1)
    vol = dev(r) * math.sqrt(252)
    return cagr * 100, vol * 100, dd * 100

ALTA, BASSA = 1.25, 0.80            # soglie del rapporto (decise prima di guardare i risultati)
casi = {"studio": {"alta": [], "media": [], "bassa": []}, "verifica": {"alta": [], "media": [], "bassa": []}}
freno = {"studio": [], "verifica": []}
for f in sorted(glob.glob(os.path.join(sys.argv[1], "*.csv"))):
    nome = os.path.basename(f)[:-4]
    if nome.startswith("_"):
        continue
    p = leggi(f)
    if len(p) < 252 * 6:
        continue
    r = [0.0] + [math.log(p[i][1] / p[i - 1][1]) for i in range(1, len(p))]
    # --- 1) cosa succede nel mese dopo, per fascia del rapporto
    peso = [1.0] * len(p)             # 2) freno: posizione dimezzata quando R > ALTA (decisa a fine mese, valida il mese dopo)
    for i in range(252, len(p) - 21):
        if p[i][0][:7] == p[i + 1][0][:7]:
            continue                  # solo l'ultima seduta del mese
        v21, v252 = dev(r[i - 20:i + 1]), dev(r[i - 251:i + 1])
        if not v252:
            continue
        R = v21 / v252
        dopo = p[i:i + 22]
        rend = dopo[-1][1] / dopo[0][1] - 1
        mx, dd = dopo[0][1], 0.0
        for _, v in dopo:
            mx = max(mx, v); dd = min(dd, v / mx - 1)
        vdopo = dev(r[i + 1:i + 22]) / v252
        per = "studio" if p[i][0] < "2016" else "verifica"
        casi[per]["alta" if R > ALTA else "bassa" if R < BASSA else "media"].append((rend * 100, dd * 100, vdopo))
        if R > ALTA:
            for j in range(i + 1, min(i + 22, len(p))):
                peso[j] = 0.5
    for per, a, b in (("studio", 252, next((k for k, x in enumerate(p) if x[0] >= "2016"), len(p))),
                      ("verifica", next((k for k, x in enumerate(p) if x[0] >= "2016"), len(p)), len(p))):
        if b - a < 500:
            continue
        c0, c1 = [1.0], [1.0]
        for j in range(a + 1, b):
            g = math.exp(r[j]) - 1
            c0.append(c0[-1] * (1 + g)); c1.append(c1[-1] * (1 + g * peso[j]))
        freno[per].append((nome, stat(c0), stat(c1)))

for per in ("studio", "verifica"):
    print("\n=== %s (%s) - il mese DOPO, per fascia del rapporto vol 21 / vol 252" % (per.upper(), "fino al 2015" if per == "studio" else "dal 2016"))
    print("  fascia        casi   rend.medio%   t    drawdown medio%   vol dopo / vol lunga")
    for k, et in (("bassa", "R < 0,80"), ("media", "0,80-1,25"), ("alta", "R > 1,25")):
        x = casi[per][k]
        print("  %-10s %6d   %8.2f  %5.1f   %10.2f   %12.2f" % (et, len(x), st.mean(v[0] for v in x), tstat([v[0] for v in x]),
                                                              st.mean(v[1] for v in x), st.mean(v[2] for v in x)))
    a, b = [v[0] for v in casi[per]["alta"]], [v[0] for v in casi[per]["bassa"] + casi[per]["media"]]
    d = st.mean(a) - st.mean(b); se = math.sqrt(dev(a) ** 2 / len(a) + dev(b) ** 2 / len(b))
    print("  differenza di rendimento alta - resto: %+.2f%% (t %.1f)" % (d, d / se))
    F = freno[per]
    rv0 = [s0[0] / s0[1] for _, s0, s1 in F]; rv1 = [s1[0] / s1[1] for _, s0, s1 in F]
    print("  FRENO (posizione dimezzata se R > 1,25), %d strumenti:" % len(F))
    print("    rendimento/volatilita' medio: senza %.3f  con %.3f   migliora su %d/%d" % (st.mean(rv0), st.mean(rv1), sum(b > a for a, b in zip(rv0, rv1)), len(F)))
    print("    drawdown massimo medio:       senza %.1f%%  con %.1f%%   CAGR medio: senza %.2f%%  con %.2f%%" % (
        st.mean(s0[2] for _, s0, s1 in F), st.mean(s1[2] for _, s0, s1 in F), st.mean(s0[0] for _, s0, s1 in F), st.mean(s1[0] for _, s0, s1 in F)))
    # confronto onesto: stessa riduzione media di esposizione ma SEMPRE (senza segnale)
