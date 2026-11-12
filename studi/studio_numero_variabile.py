# -*- coding: utf-8 -*-
"""
studio_numero_variabile.py - AZIONI SCELTE CON NUMERO VARIABILE (idea di Ya, 12/11/2026): non sempre 5 titoli,
ma quanti ne passano davvero i filtri del motore (1, 2, 3... o nessuno). Seguito di tools/studio_onesto.py.

DATI E REGOLA DI SCELTA: identici a studio_onesto.py, versione ONESTA (ogni mese le 500 azioni USA piu' scambiate in
quel momento, comprese quelle poi fallite o comprate), filtri del motore (satellite.candidati: momento 12 e 3 mesi,
sopra la media a 10 mesi, non oltre il 15% sotto il massimo, stagionalita' del mese), filtro di mercato sull'S&P 500
(sotto la media a 10 mesi -> tutta la quota in liquidita'), costo 0,20% sul peso cambiato.
VARIANTI FISSATE PRIMA DI VEDERE I RISULTATI (tutte a pari peso tra i titoli tenuti):
  OGGI      al massimo 5; posti vuoti in liquidita' (ogni titolo pesa sempre 1/5 della quota)
  DIVISA5   al massimo 5; la quota intera divisa tra quelli che passano (2 titoli = 50% ciascuno)
  TUTTI     tutti quelli che passano i filtri, senza tetto, quota intera divisa tra loro
  TUTTI20   come TUTTI ma al massimo 20 (evita portafogli da 100 titoli impossibili da comprare)
GIUDIZIO: la quota sostituisce l'S&P 500 dei portafogli, quindi una variante ha VANTAGGIO solo se in ENTRAMBI i periodi
  (2005-2015 studio, 2016-oggi verifica) ha rendimento annuo >= S&P 500 con lo stesso filtro E drawdown massimo non
  peggiore. Si riporta anche quanti titoli passano i filtri ogni mese.
USO: python studi/studio_numero_variabile.py <cartella ramo studio-delistate> <cartella storico (yahoo/SPY.csv)>
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from cot_radar import satellite as S          # noqa: E402
import studio_onesto as O                     # noqa: E402

COSTO = S.COSTO
VARIANTI = {"OGGI": (5, False), "DIVISA5": (5, True), "TUTTI": (None, True), "TUTTI20": (20, True)}


def sotto_media(sp, t):
    """True se l'S&P 500 a fine mese t e' sotto la sua media a 10 mesi (filtro di mercato del sito)."""
    return all(t - k in sp for k in range(10)) and sp[t] < sum(sp[t - k] for k in range(10)) / 10


def serie(tt, univ_t, cand, sp, tetto, dividi, dal, al):
    """Rendimenti mensili della quota. cand[t] = candidati del mese t (gia' calcolati). Pesi: 1/5 fissi oppure quota
    divisa tra i tenuti. Costo = COSTO x somma dei pesi cambiati."""
    out, prima, conta = [], {}, []
    for t in range(dal, al):
        if sotto_media(sp, t):
            pesi = {}
        else:
            sc = cand[t][:tetto] if tetto else cand[t]
            k = len(sc)
            pesi = {x["t"]: (1 / k if dividi else 1 / 5) for x in sc} if k else {}
        conta.append(len(pesi))
        r = 0.0
        for c, w in pesi.items():
            ti = tt[c][0]
            a, b = ti.p.get(t), ti.p.get(t + 1)
            if a and b and -0.95 <= b / a - 1 <= 3.0:
                r += w * (b / a - 1)
        cambio = sum(abs(pesi.get(c, 0) - prima.get(c, 0)) for c in set(pesi) | set(prima))
        out.append((S._ym(t + 1), r - COSTO * cambio))
        prima = pesi
    return out, conta


def main():
    cart, cst = sys.argv[1], sys.argv[2]
    el, dati = O.carica(cart)
    tt = O.titoli(dati)
    sp = O.spy_mensile(cst)
    ultimo = max(max(x.p) for x, _ in tt.values()) - 1
    dal = S._n("2005-01")
    print("candidati mese per mese (universo onesto, 500 titoli)...", flush=True)
    cand = {t: O.scegli(O.universo_onesto(tt, t), t, None) for t in range(dal, ultimo)}
    righe = {}
    for nome, (tetto, dividi) in VARIANTI.items():
        rs, conta = serie(tt, None, cand, sp, tetto, dividi, dal, ultimo)
        righe[nome] = rs
        investiti = [c for c in conta if c]
        print(f"{nome:8} titoli tenuti: media {sum(investiti)/max(1,len(investiti)):.1f} quando investita, "
              f"min {min(investiti) if investiti else 0}, max {max(conta)}; mesi in liquidita' {conta.count(0)} su {len(conta)}")
    righe["S&P 500 + filtro"] = [(S._ym(t + 1), 0.0 if sotto_media(sp, t) else sp[t + 1] / sp[t] - 1)
                                 for t in range(dal, ultimo) if t in sp and t + 1 in sp]
    pas = [len(cand[t]) for t in cand]
    print(f"titoli che passano i filtri (prima del filtro di mercato): media {sum(pas)/len(pas):.1f}, "
          f"0 in {pas.count(0)} mesi, 1-4 in {sum(1 for p in pas if 1 <= p <= 4)}, 5+ in {sum(1 for p in pas if p >= 5)}")
    f = lambda s: f"{s['cagr']:6.1f}%{s['vol']:6.1f}%{s['maxdd']:7.1f}%" if s else "   n/d"
    print(f"\n{'':18}{'STUDIO 2005-2015':^22}|{'VERIFICA 2016-oggi':^22}|{'TUTTO':^22}")
    print(f"{'':18}" + ("   CAGR    Vol   MaxDD|" * 3))
    rif = {}
    for nome, rs in righe.items():
        st, vf, tu = (O.stat([x for x in rs if x[0] < "2016-01"]), O.stat([x for x in rs if x[0] >= "2016-01"]), O.stat(rs))
        rif[nome] = (st, vf)
        print(f"{nome:18}{f(st)}|{f(vf)}|{f(tu)}")
    b = rif["S&P 500 + filtro"]
    print()
    for nome in VARIANTI:
        ok = all(rif[nome][i]["cagr"] >= b[i]["cagr"] and rif[nome][i]["maxdd"] >= b[i]["maxdd"] for i in (0, 1))
        print(f"{nome:8} VANTAGGIO sull'S&P 500: {'SI' if ok else 'no'}")


if __name__ == "__main__":
    main()
