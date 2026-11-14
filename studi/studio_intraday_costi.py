# NOTA: script di studio (novembre 2026). I percorsi /tmp/... sono cartelle di lavoro locali: per rifarlo vanno
# puntati ai dati dei rami del repository (orari, storico, studio-delistate, studio-buffett). Risultati: studi/risultati_studi_2026_11.txt
# Studio: le fasce orarie "affidabili" (bordo oro) fanno guadagnare AL NETTO DEI COSTI?
# Regole fissate prima di guardare i risultati:
#  - storico diviso a meta'; nella PRIMA meta' si trovano le caselle affidabili con la regola del sito
#    (casi sufficienti, |z| >= 2,58, stesso verso nelle due meta' di quella prima meta');
#  - nella SECONDA meta' si opera ogni candela di quella fascia nel verso trovato: entrata all'apertura dell'ora,
#    uscita alla chiusura dell'ora. Rendimento = verso x (chiusura/apertura - 1) - costo andata e ritorno.
#  - costi ipotizzati (spread + commissioni, andata e ritorno): forex 0,015%, ETF USA 0,02%, crypto 0,06%.
import sys, glob, os, math, statistics as st, collections
from datetime import datetime
sys.path.insert(0, '/tmp/claude-0/fix14/g')
from cot_radar import orari, stagionalita_orari as S
COSTO = {"FOREX": 0.015, "US": 0.02, "CC": 0.06}
ris = collections.defaultdict(list)            # (classe, tipo) -> rendimenti lordi %
per_str = collections.defaultdict(list)
for f in sorted(glob.glob('/tmp/claude-0/studio_oos/*.csv.gz')):
    sym = os.path.basename(f)[:-7]; cl = sym.split('.')[-1]
    if cl not in COSTO: continue
    ore = orari.utc_vero(sym, orari.leggi(f))
    if not ore or (max(ore) - min(ore)) / 31557600 < 10: continue
    ts = sorted(ore); mid = ts[len(ts) // 2]
    a = S.calcola_simbolo({t: ore[t] for t in ts if t < mid})
    tutti = {int(h): (1 if c[6] > 0 else -1) for h, c in a['ora']['tutti'].items() if c and c[7]}
    pergg = {(int(g), int(h)): (1 if c[6] > 0 else -1) for g in a['ora'] if g != 'tutti' for h, c in a['ora'][g].items() if c and c[7]}
    for t in ts:
        if t < mid: continue
        o, h, l, c, n = ore[t]
        if n < S.MIN_MINUTI: continue
        d = datetime.fromtimestamp(t, S.ROMA); r = (c / o - 1) * 100
        if d.hour in tutti: ris[(cl, 'tutti i giorni')].append(tutti[d.hour] * r); per_str[(cl, sym)].append(tutti[d.hour] * r)
        if (d.weekday(), d.hour) in pergg: ris[(cl, 'giorno x ora')].append(pergg[(d.weekday(), d.hour)] * r)
print(f"{'classe':8s}{'tipo':16s}{'operazioni':>11s}{'lordo %':>9s}{'t':>6s}{'vincenti':>9s}{'costo':>7s}{'netto %':>9s}")
for (cl, tipo), x in sorted(ris.items()):
    m = st.mean(x); t = m / (st.stdev(x) / math.sqrt(len(x)))
    print(f"{cl:8s}{tipo:16s}{len(x):11d}{m:+9.4f}{t:+6.1f}{100*sum(v>0 for v in x)/len(x):8.1f}%{COSTO[cl]:7.3f}{m-COSTO[cl]:+9.4f}")
print("\nstrumenti con lordo medio sopra il costo (tutti i giorni, almeno 500 operazioni):")
ok = 0; tot = 0
for (cl, sym), x in sorted(per_str.items(), key=lambda kv: -st.mean(kv[1])):
    if len(x) < 500: continue
    tot += 1
    if st.mean(x) > COSTO[cl]: ok += 1; print(f"  {sym:14s} {len(x):6d} op. lordo {st.mean(x):+.4f}% costo {COSTO[cl]}")
print(f"  -> {ok} su {tot}")
best = sorted(((st.mean(x), s, len(x)) for (c, s), x in per_str.items() if len(x) >= 500), reverse=True)[:5]
print("migliori 5 (lordo):", [(s, round(m, 4), n) for m, s, n in best])
