# NOTA: script di studio (novembre 2026). I percorsi /tmp/... sono cartelle di lavoro locali: per rifarlo vanno
# puntati ai dati dei rami del repository (orari, storico, studio-delistate, studio-buffett). Risultati: studi/risultati_studi_2026_11.txt
# Studio: regole del "Warren Buffett Accounting Book" (Brodersen e Pysh) sull'archivio SEC gia' scaricato.
# Riusa studi/studio_buffett.py (stesso universo, stessi costi, stessa regola di ingresso) e aggiunge le regole W.
# REGOLE DEL LIBRO, fissate prima di guardare i risultati:
#   W1 SOLIDITA'   debito a lungo / patrimonio < 0,5 e ROE >= 8% in OGNUNO degli ultimi 5 bilanci annuali
#                  (il libro chiede 10 anni: l'archivio parte dal 2009, con 10 lo studio partirebbe dal 2019)
#   W2 W1 + P/E    W1 e prezzo/utili < 15
#   W3 W1 + P/E + P/B   W1, P/E < 15 e prezzo/patrimonio < 1,5 (le due soglie di prezzo del libro insieme)
#   W4 GRAHAM      W1 e P/E x P/B < 22,5 (la variante che il libro cita per chi supera una delle due soglie)
# NON testabile: liquidita' corrente > 1,5 (attivo e passivo correnti non sono nell'archivio).
import sys
sys.path.insert(0, '/tmp/claude-0/fix14/g'); sys.path.insert(0, '/tmp/claude-0/fix14/g/studi')
import studio_buffett as B
from datetime import date
_fond, _scelte = B.fondamentali, B.scelte
def fondamentali(b, fine_mese, prezzo, cp=None):
    out = _fond(b, fine_mese, prezzo, cp)
    if not out: return out
    # storia del ROE: ultimi 5 bilanci annuali depositati entro fine mese (una riga per fine periodo)
    anni = {}
    for voce in ("utile", "utile_tot"):
        for dep, fp, q, v in b.get(voce, []):
            if dep <= fine_mese and q == 4 and fp not in anni: anni[fp] = v
        if anni: break
    roe = []
    for fp in sorted(anni)[-5:]:
        pn = B.valore_bil(b, ("pn",), fine_mese, fp)
        roe.append(anni[fp] / pn if pn and pn > 0 else None)
    out["roe5"] = roe if len(roe) == 5 and all(x is not None for x in roe) else None
    return out
def scelte(fd):
    sc = _scelte(fd)
    w1 = {c for c, f in fd.items() if f.get("pn") and f["pn"] > 0 and f["debito"] / f["pn"] < 0.5
          and f.get("roe5") and min(f["roe5"]) >= 0.08}
    pe = {c: f["cap"] / f["utile"] for c, f in fd.items() if f.get("cap") and f["utile"] > 0}
    pb = {c: f["cap"] / f["pn"] for c, f in fd.items() if f.get("cap") and f.get("pn") and f["pn"] > 0}
    sc = {k: v for k, v in sc.items() if k.startswith("B5")}        # per confronto si tiene solo la migliore B
    sc["BW1 solidita' (libro)"] = w1
    sc["BW2 solidita' + P/E<15"] = {c for c in w1 if c in pe and pe[c] < 15}
    sc["BW3 + P/E<15 e P/B<1,5"] = {c for c in w1 if c in pe and c in pb and pe[c] < 15 and pb[c] < 1.5}
    sc["BW4 solidita' + Graham"] = {c for c in w1 if c in pe and c in pb and pe[c] * pb[c] < 22.5}
    return sc
B.fondamentali, B.scelte = fondamentali, scelte
sys.argv = ["x", "/tmp/claude-0/d_studio-delistate", "/tmp/claude-0/d_studio-buffett", "/tmp/claude-0/storico"]
B.main()
