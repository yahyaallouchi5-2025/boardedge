# NOTA: script di studio (novembre 2026). I percorsi /tmp/... sono cartelle di lavoro locali: per rifarlo vanno
# puntati ai dati dei rami del repository (orari, storico, studio-delistate, studio-buffett). Risultati: studi/risultati_studi_2026_11.txt
# Studio fuori campione: una tendenza stagionale trovata nella PRIMA meta' dello storico si ripete nella SECONDA?
# Per ogni strumento e tabella (ora, giorno della settimana, giorno del mese, settimana, mese) si confronta il verso
# dello scarto dal normale (z) nelle due meta'. Se le tendenze fossero solo rumore, il verso si ripeterebbe il 50% delle volte.
import sys,glob,os,collections
sys.path.insert(0,'/tmp/claude-0/fix14/g')
from cot_radar import orari, stagionalita_orari as S
ris=collections.defaultdict(lambda: collections.defaultdict(lambda:[0,0,0.0]))  # tab -> soglia -> [casi, stesso verso, somma z2 orientato]
for f in sorted(glob.glob('/tmp/claude-0/studio_oos/*.csv.gz')):
    ore=orari.utc_vero(os.path.basename(f)[:-7],orari.leggi(f))
    if len(ore)<24*400: continue
    ts=sorted(ore); mid=ts[len(ts)//2]
    a=S.calcola_simbolo({t:ore[t] for t in ts if t<mid}); b=S.calcola_simbolo({t:ore[t] for t in ts if t>=mid})
    tabs=[('ora',a['ora'][k],b['ora'].get(k,{})) for k in a['ora'] if k!='tutti']+[(k,a[k],b[k]) for k in ('gsett','gmese','sett','mese')]
    for nome,ta,tb in tabs:
        for c,ca in ta.items():
            cb=tb.get(c)
            if not ca or not cb: continue
            z1,z2=ca[6],cb[6]
            if z1==0: continue
            for soglia in (0,1.645,1.96,2.58):
                if abs(z1)>=soglia:
                    r=ris[nome][soglia]; r[0]+=1; r[1]+= (z1>0)==(z2>0); r[2]+= z2*(1 if z1>0 else -1)
for nome in ('ora','gsett','gmese','sett','mese'):
    print(nome, '  '.join(f"|z|>={s}: {r[0]} casi, stesso verso {100*r[1]/max(1,r[0]):.1f}%, z medio dopo {r[2]/max(1,r[0]):+.2f}" for s,r in sorted(ris[nome].items())))
