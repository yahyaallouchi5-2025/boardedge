# -*- coding: utf-8 -*-
# STUDIO: l'asimmetria dei rendimenti di un asset e' una proprieta' STABILE (quindi utilizzabile) o cambia a caso?
# REGOLE FISSATE PRIMA DI VEDERE I RISULTATI
#  - asset: solo strumenti comprabili (ETF) con storia dal 2007: niente future continui (salti da rollover);
#  - rendimenti MENSILI (fine mese), in dollari (proprieta' dell'asset, senza il cambio);
#  - due meta' uguali per tutti: A = 05/2007-12/2016, B = 01/2017-10/2026;
#  - misure per asset: asimmetria classica (momento terzo), asimmetria robusta sui quantili
#    (Q90+Q10-2*Q50)/(Q90-Q10), media del 5% dei mesi peggiori (in volatilita'), rapporto guadagno medio / perdita media;
#    volatilita' come TERMINE DI PARAGONE (si sa che e' stabile);
#  - stabilita' = correlazione di rango (Spearman) tra A e B sugli asset; prova a permutazioni (20.000),
#    "stabile" solo se p < 0,005 (z ~ 2,81) e correlazione positiva;
#  - controlli secondari (solo descrittivi): rendimenti giornalieri; 4 blocchi di 5 anni consecutivi.
import sys, math, random
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))
from cot_radar import portafogli as P
px = P.prezzi(scarica=None, cartella=__import__('os').environ.get('STORICO', 'storico'))
ASSET = "SPY DIA QQQ IWM EFA EEM XLK XLY XLF XLI XLE XLB XLV XLP XLU SHY IEF TLT GLD SLV USO UNG UUP".split()
random.seed(7)

def mensili(t):
    """{aaaa-mm: rendimento} dai prezzi di fine mese."""
    fine = {}
    for d, p in px[t]:
        fine[d[:7]] = p
    m = sorted(fine)
    return {m[i]: fine[m[i]] / fine[m[i - 1]] - 1 for i in range(1, len(m))}

def giornalieri(t):
    v = px[t]
    return {v[i][0]: v[i][1] / v[i - 1][1] - 1 for i in range(1, len(v))}

def q(x, p):
    s = sorted(x); k = p * (len(s) - 1); i = int(k)
    return s[i] + (s[min(i + 1, len(s) - 1)] - s[i]) * (k - i)

def misure(r):
    n = len(r); mu = sum(r) / n; sd = math.sqrt(sum((v - mu) ** 2 for v in r) / (n - 1))
    asim = sum(((v - mu) / sd) ** 3 for v in r) * n / ((n - 1) * (n - 2))
    rob = (q(r, .9) + q(r, .1) - 2 * q(r, .5)) / (q(r, .9) - q(r, .1))
    k = max(1, round(n * .05)); coda = sum(sorted(r)[:k]) / k / sd
    su = [v for v in r if v > 0]; giu = [-v for v in r if v < 0]
    return {"asimmetria": asim, "asim. robusta": rob, "coda peggiore/vol": coda,
            "guadagno/perdita": (sum(su) / len(su)) / (sum(giu) / len(giu)), "volatilita'": sd}

def ranghi(x):
    o = sorted(range(len(x)), key=lambda i: x[i]); r = [0] * len(x)
    for k, i in enumerate(o): r[i] = k
    return r

def spearman(a, b):
    ra, rb = ranghi(a), ranghi(b); n = len(a); m = (n - 1) / 2
    return sum((x - m) * (y - m) for x, y in zip(ra, rb)) / sum((x - m) ** 2 for x in ra)

def prova(a, b, giri=20000):
    rho = spearman(a, b); bb = b[:]; piu = 0
    for _ in range(giri):
        random.shuffle(bb)
        if spearman(a, bb) >= rho: piu += 1
    return rho, (piu + 1) / (giri + 1)

def studio(serie, tagli, nome):
    print(f"\n=== {nome} ===")
    per = []
    for da, a in tagli:
        per.append({t: misure([v for d, v in sorted(serie[t].items()) if da <= d < a]) for t in ASSET})
    for m in ("volatilita'", "asimmetria", "asim. robusta", "coda peggiore/vol", "guadagno/perdita"):
        rr = []
        for i in range(len(per) - 1):
            rho, p = prova([per[i][t][m] for t in ASSET], [per[i + 1][t][m] for t in ASSET])
            rr.append(f"{rho:+.2f} (p={p:.3f})")
        print(f"{m:20} " + "  ".join(rr))
    return per

M = {t: mensili(t) for t in ASSET}
G = {t: giornalieri(t) for t in ASSET}
per = studio(M, [("2007-05", "2017-01"), ("2017-01", "2026-11")], "MENSILI, due meta' (prova principale)")
print("\nasset      asim A  asim B | robusta A  B | coda A   B | guad/perd A  B")
for t in sorted(ASSET, key=lambda t: -per[0][t]["asimmetria"]):
    a, b = per[0][t], per[1][t]
    print(f"{t:6} {a['asimmetria']:+8.2f} {b['asimmetria']:+7.2f} | {a['asim. robusta']:+6.2f} {b['asim. robusta']:+6.2f} |"
          f" {a['coda peggiore/vol']:+5.2f} {b['coda peggiore/vol']:+5.2f} | {a['guadagno/perdita']:5.2f} {b['guadagno/perdita']:5.2f}")
studio(G, [("2007-05", "2017-01"), ("2017-01", "2026-11")], "GIORNALIERI, due meta' (secondario)")
studio(M, [("2007-01", "2012-01"), ("2012-01", "2017-01"), ("2017-01", "2022-01"), ("2022-01", "2026-11")], "MENSILI, blocchi di 5 anni consecutivi (secondario)")

# CONTROLLO AGGIUNTO DOPO (dichiarato): gli ETF azionari si muovono insieme, quindi 23 asset non sono 23 prove.
# 1) la classifica regge DENTRO le azioni? 2) regge tra CLASSI (media per classe)?
CLASSI = {"azioni": "SPY DIA QQQ IWM EFA EEM XLK XLY XLF XLI XLE XLB XLV XLP XLU".split(), "obbligazioni": ["SHY", "IEF", "TLT"],
          "metalli": ["GLD", "SLV"], "energia": ["USO", "UNG"], "dollaro": ["UUP"]}
print("\n=== dentro le sole azioni (15 ETF) ===")
for m in ("asimmetria", "asim. robusta"):
    az = CLASSI["azioni"]
    print(m, "%+.2f (p=%.3f)" % prova([per[0][t][m] for t in az], [per[1][t][m] for t in az]))
print("\n=== media per classe: A -> B ===")
for c, tt in CLASSI.items():
    f = lambda i, m: sum(per[i][t][m] for t in tt) / len(tt)
    print(f"{c:13} asimmetria {f(0,'asimmetria'):+.2f} -> {f(1,'asimmetria'):+.2f} | robusta {f(0,'asim. robusta'):+.2f} -> {f(1,'asim. robusta'):+.2f}")
