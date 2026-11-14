# NOTA: script di studio (novembre 2026). I percorsi /tmp/... sono cartelle di lavoro locali: per rifarlo vanno
# puntati ai dati dei rami del repository (orari, storico, studio-delistate, studio-buffett). Risultati: studi/risultati_studi_2026_11.txt
# Studio: la stagionalita' "affidabile" del sito (finestra di 4 settimane, cot_radar/stagionalita.finestra) si ripete
# nell'anno che NON ha visto? Camminata in avanti: per ogni anno Y e ogni inizio mese, la finestra e' calcolata con i
# soli anni PRIMA di Y (prima_di=Y); se e' "robusta" si guarda il rendimento vero di Y nelle 4 settimane dopo.
# Dati: Yahoo, scaricati con le date corrette (fuso della borsa). Classi: future continui (materie prime, tassi) ed ETF.
import sys, json, glob, os, math, statistics as st, collections
from datetime import date
sys.path.insert(0, '/tmp/claude-0/fix14/g')
from cot_radar import stagionalita as G
from cot_radar.config import PREZZI_YAHOO
ris = collections.defaultdict(list); per = collections.defaultdict(list); tutte = collections.defaultdict(list)
for f in sorted(glob.glob('/tmp/claude-0/fut/*.json')):
    k = os.path.basename(f)[:-5]; cl = PREZZI_YAHOO[k][1]
    s = G.Serie([tuple(p) for p in json.load(open(f))])
    a0, a1 = int(s.d[0][:4]), int(s.d[-1][:4])
    for y in range(a0 + G.ANNI_MIN + 1, a1 + 1):
        for m in range(1, 13):
            g = date(y, m, 1)
            fin = G.finestra(s, g, prima_di=y, dettagli=False)
            r = G._rend(s, g.isoformat())
            if not fin or r is None: continue
            tutte[cl].append(r * 100)
            if fin["robusto"]:
                v = 1 if fin["score"] > 0 else -1
                ris[cl].append(v * r * 100); per[k].append(v * r * 100)
for cl, x in ris.items():
    m = st.mean(x); t = m / (st.stdev(x) / math.sqrt(len(x)))
    base = tutte[cl]
    print(f"{cl:8s} finestre affidabili {len(x):4d} su {len(base)} | verso giusto {100*sum(v>0 for v in x)/len(x):.1f}% | "
          f"rendimento medio nel verso {m:+.2f}% in 4 settimane (t {t:+.1f}) | movimento medio di tutte le finestre {st.mean(base):+.2f}%")
print("per strumento (almeno 8 finestre):")
for k, x in sorted(per.items(), key=lambda kv: -st.mean(kv[1])):
    if len(x) >= 8: print(f"  {k:10s} {len(x):3d} finestre, giuste {100*sum(v>0 for v in x)/len(x):3.0f}%, media {st.mean(x):+.2f}%")
