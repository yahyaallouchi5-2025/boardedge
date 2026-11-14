# NOTA: script di studio (novembre 2026). I percorsi /tmp/... sono cartelle di lavoro locali: per rifarlo vanno
# puntati ai dati dei rami del repository (orari, storico, studio-delistate, studio-buffett). Risultati: studi/risultati_studi_2026_11.txt
# Studio "The All-Season Investor" (Pring, 1992): le 6 fasi del ciclo dalla posizione di obbligazioni, azioni e
# materie prime rispetto alla media mobile di 12 mesi. Domanda: la FASE aggiunge qualcosa al semplice trend di
# ciascun mercato? Tutto mensile, fine mese. Dati dal ramo "storico" (FRED + Yahoo).
#  azioni = S&P 500 (prezzo; +2%/anno di dividendi stimati), obbligazioni = Treasury 10 anni ricostruito dal
#  rendimento (cedola + durata 7,5 x variazione), materie prime = petrolio WTI (prezzo spot), liquidita' = T-bill 3 mesi.
#  Il libro e' del 1992: dal 1993 in poi e' tutto FUORI CAMPIONE.
import csv, math, statistics as st
D = "/tmp/claude-0/storico/"
def leggi(f):
    out = {}
    for r in csv.DictReader(open(D + f)):
        try: out[r["data"][:7]] = float(r["valore"])        # ultimo valore del mese
        except ValueError: pass
    return out
spx, t10, t3, wti = leggi("yahoo/_GSPC.csv"), leggi("DGS10.csv"), leggi("DTB3.csv"), leggi("DCOILWTICO.csv")
mesi = sorted(m for m in spx if m in t10 and m in t3 and m in wti)
# indice obbligazionario (rendimento totale) dal rendimento a 10 anni
obb = {mesi[0]: 100.0}
for a, b in zip(mesi, mesi[1:]):
    obb[b] = obb[a] * (1 + t10[a] / 1200 - 7.5 * (t10[b] - t10[a]) / 100)
def sopra(serie, i, n=12):
    v = [serie[m] for m in mesi[i - n + 1:i + 1]]
    return serie[mesi[i]] > sum(v) / n
FASE = {(1, 0, 0): "I", (1, 1, 0): "II", (1, 1, 1): "III", (0, 1, 1): "IV", (0, 0, 1): "V", (0, 0, 0): "VI",
        (1, 0, 1): "fuori seq. (O+M)", (0, 1, 0): "fuori seq. (A)"}
righe = []
for i in range(12, len(mesi) - 1):
    m, n = mesi[i], mesi[i + 1]
    k = (int(sopra(obb, i)), int(sopra(spx, i)), int(sopra(wti, i)))
    righe.append({"m": n, "fase": FASE[k], "a_up": k[1], "o_up": k[0],
                  "az": (spx[n] / spx[m] - 1) * 100 + 2 / 12, "ob": (obb[n] / obb[m] - 1) * 100, "cash": t3[m] / 12})
def riassunto(rr, tit):
    print(f"\n== {tit}: {len(rr)} mesi, {rr[0]['m']} - {rr[-1]['m']}")
    print(f"{'fase':18s}{'mesi':>6s}{'azioni %/mese':>15s}{'obblig. %/mese':>16s}{'liquid.':>9s}")
    for f in ["I", "II", "III", "IV", "V", "VI", "fuori seq. (O+M)", "fuori seq. (A)"]:
        x = [r for r in rr if r["fase"] == f]
        if not x: continue
        a = [r["az"] for r in x]; o = [r["ob"] for r in x]
        ta = st.mean(a) / (st.stdev(a) / math.sqrt(len(a))) if len(a) > 2 else 0
        to = st.mean(o) / (st.stdev(o) / math.sqrt(len(o))) if len(o) > 2 else 0
        print(f"{f:18s}{len(x):6d}{st.mean(a):+9.2f} t{ta:+5.1f}{st.mean(o):+10.2f} t{to:+5.1f}{st.mean(r['cash'] for r in x):+9.2f}")
    # la fase aiuta OLTRE il trend delle azioni? tra i mesi con azioni sopra la media: II vs III+IV (fine ciclo)
    pre = [r["az"] for r in rr if r["fase"] == "II"]; tardi = [r["az"] for r in rr if r["fase"] in ("III", "IV")]
    if len(pre) > 2 and len(tardi) > 2:
        d = st.mean(pre) - st.mean(tardi); se = math.sqrt(st.variance(pre) / len(pre) + st.variance(tardi) / len(tardi))
        print(f"azioni sopra la media: fase II {st.mean(pre):+.2f} vs fasi III-IV {st.mean(tardi):+.2f} -> differenza {d:+.2f} (t {d / se:+.1f})")
    # strategie: (A) trend semplice su azioni e obbligazioni, (B) fasi di Pring
    PESI = {"I": (0.3, 0.7), "II": (0.5, 0.5), "III": (0.7, 0.3), "IV": (0.7, 0.0), "V": (0.0, 0.0), "VI": (0.0, 0.3),
            "fuori seq. (O+M)": (0.0, 0.5), "fuori seq. (A)": (0.5, 0.0)}
    def curva(fun):
        v, pk, dd, rs = 1.0, 1.0, 0.0, []
        for r in rr:
            wa, wo = fun(r); g = (wa * r["az"] + wo * r["ob"] + (1 - wa - wo) * r["cash"]) / 100
            v *= 1 + g; pk = max(pk, v); dd = min(dd, v / pk - 1); rs.append(g)
        anni = len(rr) / 12; cagr = v ** (1 / anni) - 1
        sh = (st.mean(rs) - st.mean(r["cash"] / 100 for r in rr)) / st.stdev(rs) * math.sqrt(12)
        return f"rend. annuo {cagr*100:5.1f}%  drawdown max {dd*100:6.1f}%  Sharpe {sh:4.2f}"
    print("60/40 fisso              ", curva(lambda r: (0.6, 0.4)))
    print("trend semplice (12 mesi) ", curva(lambda r: (0.5 * r["a_up"], 0.5 * r["o_up"])))
    print("fasi di Pring            ", curva(lambda r: PESI[r["fase"]]))
riassunto(righe, "TUTTO")
riassunto([r for r in righe if r["m"] >= "1993-01"], "FUORI CAMPIONE (dopo il libro, dal 1993)")

# Secondo strumento del libro: ROC a 24 mesi dell'S&P 500 (sopra +40% = rialzo "maturo", sotto -25% = ribasso maturo).
# Rendimento delle azioni nei 12 mesi SUCCESSIVI, per zona del ROC (mesi sovrapposti: t solo indicativo).
print("\n== ROC 24 mesi S&P 500 -> azioni nei 12 mesi dopo")
zone = {"> +40%": [], "+0..40%": [], "-25..0%": [], "< -25%": []}
for i in range(24, len(mesi) - 12):
    roc = (spx[mesi[i]] / spx[mesi[i - 24]] - 1) * 100
    dopo = (spx[mesi[i + 12]] / spx[mesi[i]] - 1) * 100
    z = "> +40%" if roc > 40 else "+0..40%" if roc >= 0 else "-25..0%" if roc >= -25 else "< -25%"
    zone[z].append((mesi[i], dopo))
for z, v in zone.items():
    if v:
        x = [d for _, d in v]
        print(f"{z:9s} {len(x):4d} mesi  dopo 12 mesi {st.mean(x):+6.1f}%  positivi {100*sum(d>0 for d in x)/len(x):4.0f}%  (episodi dal {v[0][0]})")
