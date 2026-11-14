# NOTA: script di studio (novembre 2026). I percorsi /tmp/... sono cartelle di lavoro locali: per rifarlo vanno
# puntati ai dati dei rami del repository (orari, storico, studio-delistate, studio-buffett). Risultati: studi/risultati_studi_2026_11.txt
# Da quali ore di Roma arriva il guadagno lordo del forex? (stesse regole di studio_intraday.py, solo "giorno x ora")
import sys, glob, os, statistics as st, collections
from datetime import datetime
sys.path.insert(0, '/tmp/claude-0/fix14/g')
from cot_radar import orari, stagionalita_orari as S
per = collections.defaultdict(list)
for f in sorted(glob.glob('/tmp/claude-0/studio_oos/*.FOREX.csv.gz')):
    sym = os.path.basename(f)[:-7]
    ore = orari.utc_vero(sym, orari.leggi(f))
    if (max(ore) - min(ore)) / 31557600 < 10: continue
    ts = sorted(ore); mid = ts[len(ts) // 2]
    a = S.calcola_simbolo({t: ore[t] for t in ts if t < mid})
    pg = {(int(g), int(h)): (1 if c[6] > 0 else -1) for g in a['ora'] if g != 'tutti' for h, c in a['ora'][g].items() if c and c[7]}
    for t in ts:
        if t < mid: continue
        o, h, l, c, n = ore[t]
        if n < S.MIN_MINUTI: continue
        d = datetime.fromtimestamp(t, S.ROMA)
        if (d.weekday(), d.hour) in pg: per[d.hour].append(pg[(d.weekday(), d.hour)] * (c / o - 1) * 100)
tot = sum(len(v) for v in per.values())
for h in sorted(per): print(f"ore {h:02d}: {len(per[h]):6d} op. ({100*len(per[h])/tot:4.1f}%)  lordo {st.mean(per[h]):+.4f}%")
resto = [x for h, v in per.items() if h not in (22, 23, 0) for x in v]
print("senza le ore 22-00 (chiusura di New York):", len(resto), "op., lordo", round(st.mean(resto), 4))
