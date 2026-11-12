# -*- coding: utf-8 -*-
# STUDIO A: DA DOVE VIENE L'ASIMMETRIA POSITIVA DELL'AGGRESSIVO (+1,33)? Dagli asset no (le azioni sono negative).
#   Varianti (stesso motore del sito: euro, acquisto prudente, costi): base | senza Bitcoin (quota in liquidita') |
#   senza filtro di trend (sempre investito) | senza entrambi. Misure sui rendimenti mensili: asimmetria classica e
#   robusta (quantili), piu' rendimento annuo e drawdown per contesto. Anche: asimmetria togliendo i 3 mesi migliori.
# STUDIO B: SPOSTARE 5 O 10 PUNTI DAI TREASURY ALL'ORO MIGLIORA? (unica classe con asimmetria positiva stabile)
#   Regola fissata prima: si adotta solo se Calmar sale nello sviluppo (2006-2015) E nella verifica (2016+) per TUTTI
#   i profili e il drawdown massimo non peggiora. Nota: "oro al 10%" era gia' stato scartato in uno studio precedente.
import sys, json, math, copy, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cot_radar import portafogli as P, storico as S
STOR = os.environ.get('STORICO', 'storico')
px = P.prezzi(scarica=None, cartella=STOR)
sat = json.load(open(os.environ.get('SATELLITE', 'satellite.json')))
cot = S.leggi_cot(cartella=STOR)
orig_scegli, orig_sim, PROF0 = P.scegli, P.simula_prudente, copy.deepcopy(P.PROFILI)

def q(x, p):
    s = sorted(x); k = p * (len(s) - 1); i = int(k)
    return s[i] + (s[min(i + 1, len(s) - 1)] - s[i]) * (k - i)
def asim(r):
    n = len(r); mu = sum(r) / n; sd = math.sqrt(sum((v - mu) ** 2 for v in r) / (n - 1))
    return sum(((v - mu) / sd) ** 3 for v in r) * n / ((n - 1) * (n - 2))
def robusta(r):
    return (q(r, .9) + q(r, .1) - 2 * q(r, .5)) / (q(r, .9) - q(r, .1))
def mensili(curva):
    fine = {}
    for d, v in curva: fine[d[:7]] = v
    m = sorted(fine)
    return [fine[m[i]] / fine[m[i - 1]] - 1 for i in range(1, len(m))]

def giro(scegli=None, profili=None):
    """{id profilo: (uscita del sito, curva giornaliera in euro)} con la regola di scelta / i profili dati."""
    presi = []
    def spia(g, piani, dal_i, al_i=None, sostituisci=None, fx=None, tassi=None, traccia=None, scambi=None):
        c = orig_sim(g, piani, dal_i, al_i, sostituisci, fx, tassi, traccia, scambi)
        if sostituisci == {"AZ": "SPY"} and scambi is not None and len(piani) > 50: presi.append(c)
        return c
    P.simula_prudente = spia
    P.scegli = scegli or orig_scegli
    P.PROFILI = profili or PROF0
    try:
        out = P.calcola(cot, px, cartella=STOR, scrivi=False, sat=sat)
    finally:
        P.simula_prudente, P.scegli, P.PROFILI = orig_sim, orig_scegli, PROF0
    return {p["id"]: (p, c) for p, c in zip(out["profili"], presi)}

def senza_btc(profilo, g, i, sc, regola=None, giorno=None):
    pesi, info, esc = orig_scegli(profilo, g, i, sc, regola, giorno)
    if "BTC" in pesi: pesi["CASH"] = round(pesi.get("CASH", 0) + pesi.pop("BTC"), 4)
    return pesi, info, esc
sempre = lambda score, trend_ok: True
def senza_trend(profilo, g, i, sc, regola=None, giorno=None):
    return orig_scegli(profilo, g, i, sc, sempre, giorno)        # nota: il filtro di mercato delle 5 azioni resta
def senza_tutti(profilo, g, i, sc, regola=None, giorno=None):
    pesi, info, esc = orig_scegli(profilo, g, i, sc, sempre, giorno)
    if "BTC" in pesi: pesi["CASH"] = round(pesi.get("CASH", 0) + pesi.pop("BTC"), 4)
    return pesi, info, esc

print("=== A. ORIGINE DELL'ASIMMETRIA (rendimenti mensili in euro, dal 2006) ===")
for nome, fn in [("base", None), ("senza Bitcoin", senza_btc), ("senza filtro di trend", senza_trend), ("senza entrambi", senza_tutti)]:
    R = giro(fn)
    for pid in ("conservativo", "moderato", "aggressivo"):
        p, c = R[pid]; r = mensili(c); t = p["stat"]["totale"]
        senza3 = sorted(r)[:-3]
        print(f"{nome:22} {pid:13} asimmetria {asim(r):+.2f} (senza i 3 mesi migliori {asim(senza3):+.2f}) | robusta {robusta(r):+.2f}"
              f" | rend. {t['cagr']:+.1f}% | max drawdown {t['maxdd']:.1f}% | mese migliore {max(r)*100:+.1f}% peggiore {min(r)*100:+.1f}%")
    sys.stdout.flush()

print("\n=== B. PIU' ORO AL POSTO DEI TREASURY ===")
def profili_oro(punti):
    pr = copy.deepcopy(PROF0)
    for p in pr:
        s = min(punti / 100, p["base"].get("US10Y", 0))
        p["base"]["US10Y"] = round(p["base"]["US10Y"] - s, 4); p["base"]["GOLD"] = round(p["base"]["GOLD"] + s, 4)
        if p["base"]["US10Y"] <= 0: del p["base"]["US10Y"]
    return pr
for punti in (0, 5, 10):
    R = giro(None, profili_oro(punti))
    for pid in ("conservativo", "moderato", "aggressivo"):
        p, c = R[pid]; a, b = p["stat"]["storico"], p["stat"]["oos"]
        print(f"oro +{punti:2} punti {pid:13} SVILUPPO rend. {a['cagr']:+.1f}% dd {a['maxdd']:.1f}% Calmar {a['calmar']} | VERIFICA rend. {b['cagr']:+.1f}% dd {b['maxdd']:.1f}% Calmar {b['calmar']} | asimmetria {asim(mensili(c)):+.2f}")
    sys.stdout.flush()
