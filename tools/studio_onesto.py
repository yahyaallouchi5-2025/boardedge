# -*- coding: utf-8 -*-
"""
studio_onesto.py - PUNTO 4: LE 5 AZIONI SCELTE SENZA "BIAS DI SOPRAVVIVENZA" (Ya, 07/11/2026). Solo studio.

PROBLEMA: lo storico simulato delle 5 azioni (satellite.py) usa i titoli che OGGI sono negli indici. Le aziende
fallite, comprate o uscite dagli indici non ci sono: lo storico sembra migliore del vero.

DATI: ramo "studio-delistate" (workflow studio-delistate.yml, EODHD): storico mensile di TUTTE le azioni ordinarie
USA (NYSE, NASDAQ, AMEX) quotate e delistate, con prezzo rettificato e controvalore scambiato del mese.

TRE PROVE, STESSA REGOLA DI SCELTA (satellite.candidati: momento 12 e 3 mesi, sopra la media a 10 mesi, non oltre il
15% sotto il massimo, stagionalita' del mese che entra; poi punteggio) e STESSI COSTI (0,20% per titolo cambiato):
  A  "come oggi":  universo = le azioni USA dell'elenco attuale dell'Azionario (solo sopravvissute) = il metodo vecchio
  B  "onesto":     universo = ogni mese le 500 azioni USA con il controvalore medio degli ultimi 12 mesi piu' alto
                   IN QUEL MOMENTO (comprese quelle poi fallite o comprate). Nessun dato futuro.
  B10 "onesto, 10 titoli": come B ma 10 titoli (meno dipendenza dal singolo nome).
  Senza il limite di 1 titolo per settore (per le delistate il settore non c'e'): A e B sono confrontati alla pari.
TITOLO CHE SPARISCE nel mese dopo la scelta (delistato): rendimento 0 (ipotesi neutra: i fallimenti di solito
crollano PRIMA di sparire e il crollo e' gia' nelle barre mensili; le acquisizioni pagano di solito un premio).
Rendimenti mensili oltre +300% o sotto -95% = dato rotto: il titolo e' escluso quel mese.
PERIODI: 2005-2015 studio, 2016-oggi verifica. Confronto: S&P 500 (SPY) nello stesso periodo.
USO: python tools/studio_onesto.py <cartella ramo studio-delistate> <cartella storico (SPY.csv in yahoo/)>
"""
import csv
import glob
import gzip
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cot_radar import azioni as A, satellite as S          # noqa: E402

TOP = 500
COSTO = S.COSTO


def carica(cart):
    el = json.load(open(os.path.join(cart, "elenco.json"), encoding="utf-8"))
    dati = {}
    for f in glob.glob(os.path.join(cart, "mensile_*.json.gz")):
        dati.update(json.load(gzip.open(f, "rt")))
    return el, dati


def titoli(dati):
    """{codice: (Titolo, {mese intero: controvalore})}. Serie con buchi o prezzi rotti tagliate al primo problema."""
    out = {}
    for code, righe in dati.items():
        p, cv = {}, {}
        for ym, adj, dv in righe:
            k = S._n(ym)
            p[k], cv[k] = adj, dv
        if len(p) >= 14:
            out[code] = (S.Titolo(code, code, None, p), cv)
    return out


def universo_onesto(tt, t):
    """Le TOP azioni per controvalore medio dei 12 mesi fino a t (incluso): solo dati disponibili a t."""
    sc = []
    for code, (x, cv) in tt.items():
        v = [cv.get(t - k) for k in range(12)]
        if None in v or x.p.get(t, 0) < 1:              # serve un anno intero di scambi e prezzo almeno 1 dollaro
            continue
        sc.append((sum(v) / 12, code))
    sc.sort(reverse=True)
    return [tt[c][0] for _, c in sc[:TOP]]


def scegli(univ, t, n):
    return S.candidati(univ, t)[:n]


def serie(tt, fn_univ, n, dal, al, filtro=None):
    """Rendimento mensile della quota (posti vuoti = liquidita' a 0), costi di cambio inclusi.
    filtro = prezzi mensili SPY: se l'S&P 500 e' sotto la sua media a 10 mesi la quota va in liquidita' (come nel sito)."""
    out, prima = [], set()
    for t in range(dal, al):
        if filtro and t in filtro and all(t - k in filtro for k in range(10)) \
                and filtro[t] < sum(filtro[t - k] for k in range(10)) / 10:
            out.append((S._ym(t + 1), -COSTO * len(prima) / n))
            prima = set()
            continue
        sc = scegli(fn_univ(t), t, n)
        r, ora = 0.0, set()
        for x in sc:
            ti = tt[x["t"]][0]
            a, b = ti.p.get(t), ti.p.get(t + 1)
            ora.add(x["t"])
            if a and b:
                q = b / a - 1
                if -0.95 <= q <= 3.0:
                    r += q / n
        r -= COSTO * len(ora ^ prima) / n
        prima = ora
        out.append((S._ym(t + 1), r))
    return out


def stat(rs):
    if not rs:
        return None
    v, picco, dd = 1.0, 1.0, 0.0
    for _, r in rs:
        v *= 1 + r
        picco = max(picco, v)
        dd = min(dd, v / picco - 1)
    anni = len(rs) / 12
    m = sum(r for _, r in rs) / len(rs)
    sd = math.sqrt(sum((r - m) ** 2 for _, r in rs) / (len(rs) - 1)) * math.sqrt(12)
    cagr = (v ** (1 / anni) - 1) * 100
    return {"cagr": round(cagr, 1), "vol": round(sd * 100, 1), "maxdd": round(dd * 100, 1),
            "rv": round(cagr / (sd * 100), 2) if sd else None, "mesi": len(rs)}


def spy_mensile(cart_storico):
    p = {}
    with open(os.path.join(cart_storico, "yahoo", "SPY.csv"), encoding="utf-8") as f:
        for r in csv.reader(f):
            try:
                p[S._n(r[0][:7])] = float(r[1])
            except (ValueError, IndexError):
                continue
    return p


def main():
    cart, cst = sys.argv[1], sys.argv[2]
    el, dati = carica(cart)
    tt = titoli(dati)
    print(f"azioni con storico: {len(tt)} (delistate nell'elenco: {sum(1 for v in el.values() if v['stato'] == 'delistata')})")
    oggi_us = {x["t"] for x in A.elenco() if "." not in x["t"] and not x["t"].startswith("^")}
    univ_a = [tt[c][0] for c in sorted(oggi_us) if c in tt]          # ordine fisso: risultati ripetibili
    print(f"universo A (elenco di oggi): {len(univ_a)} titoli trovati su {len(oggi_us)}")
    ultimo = max(max(x.p) for x, _ in tt.values()) - 1
    dal = S._n("2005-01")
    prove = {"A  come oggi (5)": serie(tt, lambda t: univ_a, 5, dal, ultimo),
             "B  onesto (5)": serie(tt, lambda t: universo_onesto(tt, t), 5, dal, ultimo),
             "B10 onesto (10)": serie(tt, lambda t: universo_onesto(tt, t), 10, dal, ultimo)}
    sp = spy_mensile(cst)
    prove["A  come oggi + filtro"] = serie(tt, lambda t: univ_a, 5, dal, ultimo, sp)
    prove["B  onesto + filtro"] = serie(tt, lambda t: universo_onesto(tt, t), 5, dal, ultimo, sp)
    prove["B10 onesto + filtro"] = serie(tt, lambda t: universo_onesto(tt, t), 10, dal, ultimo, sp)
    prove["SPY + filtro"] = [(S._ym(t + 1), 0.0 if all(t - k in sp for k in range(10)) and sp[t] < sum(sp[t - k] for k in range(10)) / 10
                              else sp[t + 1] / sp[t] - 1) for t in range(dal, ultimo) if t in sp and t + 1 in sp]
    prove["S&P 500 (SPY)"] = [(S._ym(t + 1), sp[t + 1] / sp[t] - 1) for t in range(dal, ultimo) if t in sp and t + 1 in sp]
    f = lambda s: f"{s['cagr']:6.1f}%{s['vol']:6.1f}%{s['maxdd']:7.1f}%{(s['rv'] or 0):6.2f}" if s else "   n/d"
    print(f"\n{'':20}{'STUDIO 2005-2015':^29}|{'VERIFICA 2016-oggi':^29}|{'TUTTO':^29}")
    print(f"{'':20}" + ("   CAGR    Vol   MaxDD   R/V|" * 3))
    for nome, rs in prove.items():
        st = stat([x for x in rs if x[0] < "2016-01"])
        vf = stat([x for x in rs if x[0] >= "2016-01"])
        tu = stat(rs)
        print(f"{nome:22}{f(st)}|{f(vf)}|{f(tu)}")


if __name__ == "__main__":
    main()
