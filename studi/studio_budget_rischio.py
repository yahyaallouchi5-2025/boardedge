# -*- coding: utf-8 -*-
"""
studio_budget_rischio.py - PESI A "BUDGET DI RISCHIO" (Pearson, "Risk Budgeting", cap. 13 e 20) - Ya, 13/11/2026.
Solo studio: il sito non cambia.

DOMANDA: invece dei pesi fissi in euro, conviene dare a ogni mercato tenuto una quota FISSA DEL RISCHIO?
Differenza con la variante "pesi per volatilita'" gia' scartata il 07/11 (tools/studio_ribilancio.py, variante 1):
li' si ripesava solo la parte rischiosa con un ritocco (0,5x-2x); qui ogni mercato tenuto (anche Treasury e oro)
riceve la stessa quota di rischio, contando anche le CORRELAZIONI (contributo = peso x covarianza con il portafoglio).

VARIANTI (regole fissate PRIMA di guardare i numeri):
  0  Attuale (pesi del profilo, stesso calendario del sito)
  A  RISCHIO UGUALE (equal risk contribution) tra i mercati tenuti quel mese, covarianze degli ultimi 252 giorni;
     la quota in liquidita' resta quella del profilo (stesso livello di rischio "di base").
  B  RISCHIO UGUALE + stessa volatilita' del profilo: la parte investita si ingrandisce o si riduce (mai oltre il 100%,
     niente leva) per avere la stessa volatilita' stimata dei pesi attuali; il resto e' liquidita'.
  C  RISCHIO "BUDGET DEL PROFILO": ogni mercato riceve come quota di rischio il suo peso base (i pesi del profilo
     diventano quote di rischio invece che quote di capitale).
MISURA: quella del sito (euro senza copertura, liquidita' al tasso BCE, acquisto prudente, azioni scelte = S&P 500,
  costi). REGOLA DI SCELTA identica allo studio del 07/11: una variante entra solo se FUORI CAMPIONE (dal 2016)
  migliora rendimento/volatilita' E non peggiora il drawdown massimo di oltre 1 punto, E nello STUDIO (2006-2015)
  il rapporto rendimento/volatilita' non scende di oltre 0,05. In piu' (regola di Ya): rendimento annuo almeno 2,6%.
USO: python studi/studio_budget_rischio.py <cartella storico> <satellite.json>
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from cot_radar import portafogli as P          # noqa: E402
import studio_ribilancio as R                   # noqa: E402

FINESTRA = 252
MIN_RENDIMENTO = 2.6


def covarianze(g, chiavi, i):
    """Matrice di covarianza (annua) dei rendimenti giornalieri degli ultimi FINESTRA giorni fino a i-1."""
    rs = []
    for k in chiavi:
        t = P._ticker("SP500" if k == "AZ" else k)
        rs.append([g.rend(t, j) for j in range(max(1, i - FINESTRA), i)])
    n = len(rs[0])
    m = [sum(r) / n for r in rs]
    return [[sum((rs[a][j] - m[a]) * (rs[b][j] - m[b]) for j in range(n)) / (n - 1) * 252
             for b in range(len(rs))] for a in range(len(rs))]


def erc(C, budget, iterazioni=500):
    """Pesi (somma 1) con contributi al rischio proporzionali a 'budget' (Spinu/Roncalli, semplice punto fisso)."""
    n = len(C)
    w = [1.0 / n] * n
    for _ in range(iterazioni):
        cw = [sum(C[a][b] * w[b] for b in range(n)) for a in range(n)]
        sig = math.sqrt(max(1e-12, sum(w[a] * cw[a] for a in range(n))))
        nuovi = [budget[a] * sig / max(1e-9, cw[a]) for a in range(n)]
        s = sum(nuovi)
        nuovi = [x / s for x in nuovi]
        if max(abs(x - y) for x, y in zip(nuovi, w)) < 1e-7:
            break
        w = [0.5 * x + 0.5 * y for x, y in zip(nuovi, w)]
    return w


def vol_pesi(C, w):
    return math.sqrt(max(0.0, sum(w[a] * C[a][b] * w[b] for a in range(len(w)) for b in range(len(w)))))


def ripesa(g, i, pesi, modo, prof):
    risk = [k for k, w in pesi.items() if k != "CASH" and w > 0]
    if len(risk) < 2:
        return pesi
    try:
        C = covarianze(g, risk, i)
    except Exception:
        return pesi
    investito = sum(pesi[k] for k in risk)
    if modo == "C":
        base = prof["base"]
        b = [max(1e-4, base.get(k, prof.get("az", 0) if k == "AZ" else 0.0)) for k in risk]
        s = sum(b)
        budget = [x / s for x in b]
    else:
        budget = [1.0 / len(risk)] * len(risk)
    w = erc(C, budget)
    quota = investito
    if modo == "B":
        v_att = vol_pesi(C, [pesi[k] for k in risk])
        v_new = vol_pesi(C, w)
        quota = min(1.0, v_att / v_new) if v_new > 0 else investito
    out = {k: round(x * quota, 4) for k, x in zip(risk, w)}
    out["CASH"] = round(1 - sum(out.values()), 4)
    return out


def main():
    cartella, satf = sys.argv[1], sys.argv[2]
    px = P.prezzi(scarica=None, cartella=cartella)
    ss = P.serie_satellite(json.load(open(satf, encoding="utf-8")), [d for d, _ in px["SPY"]])
    if ss:
        px["SAT"] = ss
    fx, te = P.cambio_eur(cartella), P.tassi_eur(cartella)
    g = P.Griglia(px)
    giorni = P.date_ribilancio(g)
    anni = (len(g.date) - giorni[0]) / 252
    print(f"Periodo {g.date[giorni[0]]} - {g.date[-1]} ({anni:.1f} anni). Misura: EURO, acquisto prudente, AZ = S&P 500")
    f = lambda s: f"{s['cagr']:6.1f}{s['vol']:6.1f}{s['maxdd']:7.1f}{(s['cagr'] / s['vol'] if s['vol'] else 0):6.3f}"   # noqa: E731
    rv = lambda s: s["cagr"] / s["vol"] if s["vol"] else 0                                                              # noqa: E731
    for prof in P.PROFILI:
        print(f"\n=== {prof['nome']} ===")
        print(f"{'':34}{'STUDIO 2006-2015':^25}|{'FUORI CAMPIONE 2016+':^25}|")
        print(f"{'':34}" + ("  CAGR   Vol  MaxDD  R/V|" * 2))
        base = R.piano(prof, g, giorni)
        prove = [("0 attuale", base)]
        for modo, nome in (("A", "A rischio uguale"), ("B", "B rischio uguale, stessa vol."),
                           ("C", "C budget = pesi del profilo")):
            prove.append((nome, {i: ripesa(g, i, p, modo, prof) for i, p in base.items()}))
        rif = None
        for nome, pi in prove:
            c, _ = R.simula(g, pi, giorni[0], fx, te, None, R.SOGLIA_PORT[prof["id"]])
            st, oo = R.misura(c)
            esito = ""
            if rif is None:
                rif = (st, oo)
            else:
                ok = (rv(oo) > rv(rif[1]) and oo["maxdd"] >= rif[1]["maxdd"] - 1 and rv(st) >= rv(rif[0]) - 0.05
                      and oo["cagr"] >= MIN_RENDIMENTO and st["cagr"] >= MIN_RENDIMENTO)
                esito = "  ENTRA" if ok else "  scartata"
            print(f"{nome:34}{f(st)}|{f(oo)}|{esito}")
        ultimo = max(base)
        print("  pesi di oggi  attuale:", {k: round(v * 100, 1) for k, v in sorted(base[ultimo].items())})
        print("  pesi di oggi  A      :", {k: round(v * 100, 1) for k, v in sorted(ripesa(g, ultimo, base[ultimo], "A", prof).items())})


if __name__ == "__main__":
    main()
