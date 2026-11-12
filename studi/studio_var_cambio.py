# -*- coding: utf-8 -*-
# STUDIO (Hull, capitoli su VaR e volatilita'): quale stima della "perdita del mese che si supera 1 volta su 20"
# e' ONESTA sui portafogli del sito? E quanta parte del rischio di chi investe in euro viene dal cambio?
# REGOLE FISSATE PRIMA DI VEDERE I RISULTATI
#  - a ogni rotazione mensile, con i pesi decisi quel giorno, si ricostruiscono i rendimenti giornalieri in EURO
#    che quei pesi avrebbero avuto nei giorni precedenti (come quote_rischio del sito: AZ = S&P 500, liquidita' = 0);
#  - soglia di perdita al 95% per i 21 giorni successivi, tre metodi:
#      M1 normale, deviazione standard semplice 63 giorni x radice(21) x 1,645
#      M2 normale, EWMA lambda 0,94 (RiskMetrics)        x radice(21) x 1,645
#      M3 storico: 5o percentile dei rendimenti a 21 giorni (sovrapposti) degli ultimi 756 giorni
#  - realizzato = rendimento vero del portafoglio (curva del sito, costi inclusi) fino alla rotazione dopo;
#  - giudizio: % di mesi oltre la soglia (giusto = 5%), prova binomiale; sviluppo fino al 2015, verifica dal 2016;
#    si adotta il metodo piu' vicino al 5% in ENTRAMBI i periodi e non respinto (p > 0,05). A parita': soglia piu' stretta.
#  - quota di rischio del cambio = covarianza(parte cambio, portafoglio) / varianza(portafoglio), ultimi 252 giorni.
import sys, json, math
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))
from cot_radar import portafogli as P, storico as S
STOR = __import__('os').environ.get('STORICO', 'storico')          # cartella dello storico prezzi
px = P.prezzi(scarica=None, cartella=STOR)
sat = json.load(open(__import__('os').environ.get('SATELLITE', 'satellite.json')))
cot = S.leggi_cot(cartella=STOR)
presi = []
orig = P.simula_prudente
def spia(g, piani, dal_i, al_i=None, sostituisci=None, fx=None, tassi=None, traccia=None, scambi=None):
    c = orig(g, piani, dal_i, al_i, sostituisci, fx, tassi, traccia, scambi)
    if sostituisci == {"AZ": "SPY"} and scambi is not None and len(piani) > 50:
        presi.append((g, piani, dal_i, fx, c))
    return c
P.simula_prudente = spia
out = P.calcola(cot, px, cartella=STOR, scrivi=False, sat=sat)
P.simula_prudente = orig
nomi = [p["id"] for p in out["profili"]]
print("catturati", len(presi), nomi, "| curva:", type(presi[0][4]), presi[0][4][:2], file=sys.stderr)

def std(x):
    m = sum(x) / len(x); return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))
def binom_p(k, n, p=0.05):
    """p a due code: probabilita' di un numero di sforamenti lontano dall'atteso almeno quanto k."""
    pr = [math.comb(n, j) * p ** j * (1 - p) ** (n - j) for j in range(n + 1)]
    return min(1.0, sum(x for x in pr if x <= pr[k] * (1 + 1e-9)))

for nome, (g, piani, dal_i, fx, curva) in zip(nomi, presi):
    cambio, ult = [], None
    for d in g.date:
        ult = (fx or {}).get(d, ult); cambio.append(ult)
    val = {d: v for d, v in curva} if isinstance(curva[0], (list, tuple)) else None
    def proforma(pesi, i, n):
        """rendimenti giornalieri in euro (tot) e sola parte cambio dei pesi, negli n giorni fino a i (compreso)."""
        tot, parte_fx = [], []
        for j in range(i - n + 1, i + 1):
            f = cambio[j - 1] / cambio[j] - 1 if cambio[j] and cambio[j - 1] else 0.0
            a = b = 0.0
            for k, w in pesi.items():
                if k == "CASH" or w <= 0: continue
                r = g.rend(P._ticker("SP500" if k == "AZ" else k), j)
                a += w * ((1 + r) * (1 + f) - 1); b += w * f
            tot.append(a); parte_fx.append(b)
        return tot, parte_fx
    # CORREZIONE: 'piani' ha una voce solo quando la composizione cambia; le soglie a 21 giorni vanno provate su
    # TUTTI i mesi (date di rotazione del sito), con i pesi in vigore quel giorno.
    cambi = sorted(piani)
    rot = [i for i in P.date_ribilancio(g) if i >= cambi[0] and g.date[i] in val]
    print(nome, "cambi di composizione:", len(cambi), "mesi:", len(rot), file=sys.stderr)
    ris = {}; quote_fx = []
    for n_, i in enumerate(rot[:-1]):
        if i < 800: continue
        pesi = piani[max(c for c in cambi if c <= i)]; j = i - 1                      # decisione con i dati fino al giorno prima
        r, rf = proforma(pesi, j, 756)
        ew = r[0] ** 2
        for x in r[1:]: ew = 0.94 * ew + 0.06 * x * x
        cum = [0.0]
        for x in r: cum.append(cum[-1] + math.log(1 + x))
        r21 = sorted(math.exp(cum[k + 21] - cum[k]) - 1 for k in range(len(r) - 20))
        soglie = {"M1 semplice 63g": -1.645 * std(r[-63:]) * math.sqrt(21), "M2 EWMA": -1.645 * math.sqrt(ew * 21),
                  "M3 storico 3 anni": r21[int(0.05 * len(r21))]}
        i2 = rot[n_ + 1]
        reale = val[g.date[i2]] / val[g.date[i]] - 1
        per = "sviluppo" if g.date[i] < "2016" else "verifica"
        for m, s in soglie.items():
            a = ris.setdefault((per, m), [0, 0, 0.0, 0.0]); a[0] += reale < s; a[1] += 1; a[2] += s
            if reale < s: a[3] += reale - s
        r1, f1 = r[-252:], rf[-252:]
        mp, mf = sum(r1) / 252, sum(f1) / 252
        var = sum((x - mp) ** 2 for x in r1)
        if var > 0: quote_fx.append((g.date[i], sum((y - mf) * (x - mp) for x, y in zip(r1, f1)) / var))
    print(f"\n=== {nome} ===")
    for per in ("sviluppo", "verifica"):
        for (p, m), a in ris.items():
            if p == per:
                print(f"{per:9} {m:18} oltre soglia {a[0]:3}/{a[1]} = {100*a[0]/a[1]:4.1f}% (p={binom_p(a[0], a[1]):.2f})"
                      f" | soglia media {100*a[2]/a[1]:+.2f}% | sforamento medio {100*a[3]/max(a[0],1):+.2f}%")
    q = [x for _, x in quote_fx]
    print(f"quota di rischio dal cambio: media storica {100*sum(q)/len(q):.0f}%, minimo {100*min(q):.0f}%, massimo {100*max(q):.0f}%, oggi {100*q[-1]:.0f}%")
