# -*- coding: utf-8 -*-
"""
studio_libri_etf.py - TRE IDEE DAI LIBRI CONDIVISI DA YA (13/11/2026), MESSE ALLA PROVA SUGLI ETF. Solo studio.

A) MEDIE MOBILI (Clif Droke, "Moving Averages Simplified", cap. 3-4, sulla linea di Weinstein):
   A1 settimanale: investito se la chiusura del venerdi' e' sopra la media a 30 settimane E la media sale; se no
      liquidita'. A2 giornaliero: stessa regola con la media a 30 giorni. A3 due medie: 30 giorni sopra 60 = investito.
B) ORO / ARGENTO ("How to Profit in Gold", appendice A): "l'argento esagera i movimenti dell'oro" e il rapporto
   oro/argento si usa per scegliere. B1 a fine mese: rapporto sopra la sua media di 36 mesi di oltre 1 deviazione =
   argento "economico" -> si tiene SLV, sotto di oltre 1 deviazione -> GLD, in mezzo -> GLD (l'oro e' la base del sito).
   In piu' (descrittivo): beta dell'argento sull'oro.
C) SCALE TRADING (Robert Wiest, "You Can't Lose Trading Commodities", cap. IV-VII, X): comprare a scaglioni SENZA
   leva quando il prezzo e' storicamente basso, vendere ogni scaglione con un guadagno fisso, mai stop.
   C1: zona di acquisto = prezzo sotto il 25 percentile dei 5 anni prima; 1 scaglione al primo ingresso, poi uno ogni
       -10% dal precedente acquisto, massimo 10 scaglioni (capitale = 10 scaglioni, mai leva); ogni scaglione si vende
       a +10% dal suo prezzo di acquisto. Liquidita' non investita a rendimento 0 (prudente).
   Sugli ETF di materie prime (con il costo vero del rinnovo dei future, che il libro cita al cap. XVII).
REGOLE comuni fissate PRIMA di vedere i risultati: prezzi rettificati di chiusura; liquidita' = SHY (A) o 0 (C);
  costo 0,10% per ogni acquisto o vendita; STUDIO fino al 2015, VERIFICA dal 2016.
  Una regola ENTRA solo se in ENTRAMBI i periodi batte il "compra e tieni" per rendimento/volatilita' E per
  rendimento/drawdown (Calmar), con almeno 2,6% l'anno (regola di Ya).
USO: python studi/studio_libri_etf.py <cartella prezzi yahoo>
"""
import csv
import math
import os
import sys

COSTO = 0.001
CAMBIO = "2016-01-01"
MIN_REND = 2.6
ETF_A = ["SPY", "QQQ", "IWM", "DIA", "EFA", "EEM", "VNQ", "TLT", "IEF", "GLD", "SLV", "USO", "UNG", "CORN", "SOYB",
         "WEAT", "CPER", "PPLT"]
ETF_C = ["USO", "UNG", "CORN", "SOYB", "WEAT", "CPER", "GLD", "SLV", "PPLT"]


def leggi(cart, t):
    out = []
    with open(os.path.join(cart, t + ".csv")) as fh:
        for r in csv.reader(fh):
            try:
                v = float(r[1])
            except (ValueError, IndexError):
                continue
            if v > 0:
                out.append((r[0], v))
    return out


def stat(curva):
    """curva = [(data, valore)] -> CAGR %, vol % annua, maxDD %, R/V, Calmar."""
    if len(curva) < 60:
        return None
    rs = [curva[i][1] / curva[i - 1][1] - 1 for i in range(1, len(curva))]
    anni = len(rs) / 252
    v = curva[-1][1] / curva[0][1]
    cagr = (v ** (1 / anni) - 1) * 100 if v > 0 else -100.0
    m = sum(rs) / len(rs)
    vol = math.sqrt(sum((r - m) ** 2 for r in rs) / (len(rs) - 1) * 252) * 100
    picco, dd = curva[0][1], 0.0
    for _, x in curva:
        picco = max(picco, x)
        dd = min(dd, x / picco - 1)
    return {"cagr": cagr, "vol": vol, "dd": dd * 100, "rv": cagr / vol if vol else 0,
            "calmar": cagr / -dd / 100 if dd < 0 else 0}


def periodi(curva):
    a = [x for x in curva if x[0] < CAMBIO]
    b = [x for x in curva if x[0] >= CAMBIO]
    if b and a:
        b = [a[-1]] + b
    return stat(a), stat(b)


def esito(reg, bh):
    ok = all(r and h and r["rv"] > h["rv"] and r["calmar"] > h["calmar"] and r["cagr"] >= MIN_REND
             for r, h in zip(reg, bh))
    return "ENTRA" if ok else "scartata"


def fmt(s):
    return f"{s['cagr']:6.1f}{s['vol']:6.1f}{s['dd']:7.1f}{s['rv']:6.2f}{s['calmar']:6.2f}" if s else f"{'-':^31}"


# --------------------------------------------------------------------------- A) medie mobili
def curva_segnale(px, cash, investito):
    """investito[i] = True/False deciso alla chiusura del giorno i (vale dal giorno dopo). Costi a ogni cambio."""
    v, out, stato = 1.0, [(px[0][0], 1.0)], False
    for i in range(1, len(px)):
        r = px[i][1] / px[i - 1][1] - 1 if stato else cash.get(px[i][0], 0.0)
        v *= 1 + r
        nuovo = investito[i]
        if nuovo != stato:
            v *= 1 - COSTO
            stato = nuovo
        out.append((px[i][0], v))
    return out


def rend_cash(shy):
    return {shy[i][0]: shy[i][1] / shy[i - 1][1] - 1 for i in range(1, len(shy))}


def segnali_ma(px):
    c = [p for _, p in px]
    n = len(c)
    pref = [0.0]
    for x in c:
        pref.append(pref[-1] + x)
    sma = lambda i, k: (pref[i + 1] - pref[i + 1 - k]) / k if i + 1 >= k else None   # noqa: E731
    a2 = [False] * n
    a3 = [False] * n
    for i in range(n):
        m30, m30p, m60 = sma(i, 30), sma(i - 1, 30) if i else None, sma(i, 60)
        a2[i] = bool(m30 and m30p and c[i] > m30 and m30 > m30p)
        a3[i] = bool(m30 and m60 and m30 > m60)
    # settimanale: venerdi' (ultimo giorno di borsa della settimana ISO)
    from datetime import date
    sett = {}
    for i, (d, _) in enumerate(px):
        k = date.fromisoformat(d).isocalendar()[:2]
        sett[k] = i                                     # ultimo indice della settimana
    fine = sorted(sett.values())
    a1 = [False] * n
    stato = False
    chiusure = [c[i] for i in fine]
    for j, i in enumerate(fine):
        if j >= 31:
            m = sum(chiusure[j - 29:j + 1]) / 30
            mp = sum(chiusure[j - 30:j]) / 30
            stato = chiusure[j] > m and m > mp
        a1[i] = stato
    for i in range(1, n):                               # tra un venerdi' e l'altro si resta come deciso
        if i not in sett.values():
            a1[i] = a1[i - 1]
    return {"A1 30 settimane": a1, "A2 30 giorni": a2, "A3 30/60 giorni": a3}


def studio_a(cart):
    cash = rend_cash(leggi(cart, "SHY"))
    print("\n=== A) MEDIE MOBILI (Droke)  ")
    print(f"{'':22}{'STUDIO -2015':^31}|{'VERIFICA 2016+':^31}|")
    print(f"{'':22}" + ("  CAGR   Vol   MaxDD   R/V  Calm|" * 2))
    conta = {}
    for t in ETF_A:
        px = leggi(cart, t)
        bh = periodi([(d, p / px[0][1]) for d, p in px])
        print(f"{t:6} compra e tieni     {fmt(bh[0])}|{fmt(bh[1])}|")
        for nome, sig in segnali_ma(px).items():
            reg = periodi(curva_segnale(px, cash, sig))
            e = esito(reg, bh)
            conta.setdefault(nome, []).append(e == "ENTRA")
            print(f"       {nome:15}{fmt(reg[0])}|{fmt(reg[1])}| {e}")
    for nome, v in conta.items():
        print(f"  {nome}: entra su {sum(v)} ETF su {len(v)}")


# --------------------------------------------------------------------------- B) oro / argento
def mensile(px):
    m = {}
    for d, p in px:
        m[d[:7]] = (d, p)
    return [m[k] for k in sorted(m)]


def studio_b(cart):
    g, s = leggi(cart, "GLD"), leggi(cart, "SLV")
    gd, sd = dict(g), dict(s)
    comuni = sorted(set(gd) & set(sd))
    gm = mensile([(d, gd[d]) for d in comuni])
    sm = dict(mensile([(d, sd[d]) for d in comuni]))    # {ultima data del mese: prezzo}
    # beta dell'argento sull'oro (rendimenti mensili)
    rg = [gm[i][1] / gm[i - 1][1] - 1 for i in range(1, len(gm))]
    rs = [sm[gm[i][0]] / sm[gm[i - 1][0]] - 1 for i in range(1, len(gm))]
    mg, ms = sum(rg) / len(rg), sum(rs) / len(rs)
    cov = sum((a - mg) * (b - ms) for a, b in zip(rg, rs)) / (len(rg) - 1)
    var = sum((a - mg) ** 2 for a in rg) / (len(rg) - 1)
    print(f"\n=== B) ORO / ARGENTO   beta argento su oro (mensile): {cov / var:.2f}")
    rap = [gm[i][1] / sm[gm[i][0]] for i in range(len(gm))]
    v, curva, tiene, scelta = 1.0, [(gm[36][0], 1.0)], "GLD", {}
    for i in range(36, len(gm) - 1):
        fin = rap[i - 36:i]
        m = sum(fin) / 36
        sdv = math.sqrt(sum((x - m) ** 2 for x in fin) / 35)
        nuovo = "SLV" if rap[i] > m + sdv else "GLD"
        if nuovo != tiene:
            v *= (1 - COSTO) ** 2
            tiene = nuovo
        scelta[tiene] = scelta.get(tiene, 0) + 1
        d0, d1 = gm[i][0], gm[i + 1][0]
        r = (gd[d1] / gd[d0] - 1) if tiene == "GLD" else (sd[d1] / sd[d0] - 1)
        v *= 1 + r
        curva.append((d1, v))
    bh = [(gm[i][0], gm[i][1] / gm[36][1]) for i in range(36, len(gm))]
    # stat mensile: si riusa stat con 12 osservazioni l'anno
    def st(c):
        a = [x for x in c if x[0] < CAMBIO]
        b = [x for x in c if x[0] >= CAMBIO]
        b = [a[-1]] + b
        out = []
        for z in (a, b):
            rr = [z[i][1] / z[i - 1][1] - 1 for i in range(1, len(z))]
            anni = len(rr) / 12
            cagr = ((z[-1][1] / z[0][1]) ** (1 / anni) - 1) * 100
            mm = sum(rr) / len(rr)
            vol = math.sqrt(sum((x - mm) ** 2 for x in rr) / (len(rr) - 1) * 12) * 100
            pk, dd = z[0][1], 0.0
            for _, x in z:
                pk = max(pk, x)
                dd = min(dd, x / pk - 1)
            out.append({"cagr": cagr, "vol": vol, "dd": dd * 100, "rv": cagr / vol, "calmar": cagr / -dd / 100 if dd else 0})
        return out
    r1, r0 = st(curva), st(bh)
    print(f"{'':22}{'STUDIO -2015':^31}|{'VERIFICA 2016+':^31}|")
    print(f"GLD compra e tieni    {fmt(r0[0])}|{fmt(r0[1])}|")
    print(f"B1 rapporto oro/arg.  {fmt(r1[0])}|{fmt(r1[1])}| {esito(r1, r0)}  (mesi in SLV: {scelta.get('SLV', 0)})")


# --------------------------------------------------------------------------- C) scale trading
def scale(px, passo=0.10, utile=0.10, max_n=10, anni=5, pct=0.25):
    """Curva del capitale (1 = 10 scaglioni) dello scale trading di Wiest."""
    cassa, lotti, ultimo_acq = 1.0, [], None
    q = 1.0 / max_n
    curva, n_op, giorni_pieno = [], 0, 0
    fin = 252 * anni
    for i, (d, p) in enumerate(px):
        # vendite: ogni scaglione a +utile dal suo prezzo
        rest = []
        for pa, quote in lotti:
            if p >= pa * (1 + utile):
                cassa += quote * p * (1 - COSTO)
                n_op += 1
            else:
                rest.append((pa, quote))
        lotti = rest
        if not lotti:
            ultimo_acq = None
        if i >= fin:
            storia = sorted(x for _, x in px[i - fin:i])
            soglia = storia[int(len(storia) * pct)]
            compra = False
            if not lotti and p <= soglia:
                compra = True
            elif lotti and ultimo_acq and p <= ultimo_acq * (1 - passo) and len(lotti) < max_n:
                compra = True
            if compra and cassa >= q * 0.999:
                quote = q * (1 - COSTO) / p
                lotti.append((p, quote))
                cassa -= q
                ultimo_acq = p
                n_op += 1
        if len(lotti) >= max_n:
            giorni_pieno += 1
        curva.append((d, cassa + sum(qq * p for _, qq in lotti)))
    return curva[fin:], n_op, giorni_pieno


def studio_c(cart):
    print("\n=== C) SCALE TRADING (Wiest)  capitale = 10 scaglioni, nessuna leva")
    print(f"{'':22}{'STUDIO -2015':^31}|{'VERIFICA 2016+':^31}|")
    for t in ETF_C:
        px = leggi(cart, t)
        curva, n_op, pieno = scale(px)
        base = curva[0][0]
        sub = [(d, p) for d, p in px if d >= base]
        bh = periodi([(d, p / sub[0][1]) for d, p in sub])
        reg = periodi(curva)
        print(f"{t:6} compra e tieni     {fmt(bh[0])}|{fmt(bh[1])}|")
        print(f"       C1 scaglioni    {fmt(reg[0])}|{fmt(reg[1])}| {esito(reg, bh)}  "
              f"(operazioni {n_op}, giorni con 10 scaglioni pieni {pieno}, valore finale {curva[-1][1]:.2f})")


def main():
    cart = sys.argv[1]
    studio_a(cart)
    studio_b(cart)
    studio_c(cart)


if __name__ == "__main__":
    main()
