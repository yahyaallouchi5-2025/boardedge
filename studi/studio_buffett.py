# -*- coding: utf-8 -*-
"""
studio_buffett.py - RIACQUISTI DI AZIONI E REGOLE DI WARREN BUFFETT, misurati sui bilanci SEC - Ya, 13/11/2026.
Solo studio: il sito non cambia.

DOMANDA: le regole di Buffett (lettere agli azionisti) danno un vantaggio misurabile a un portafoglio di azioni USA?
  - riacquisti: "comprare azioni proprie ha senso solo se l'azienda le paga meno di quanto valgono";
  - owner earnings: utile + ammortamenti - investimenti per mantenere l'attivita' (capex);
  - poco debito e ROE alto senza leva.
DATI (senza bias di sopravvivenza):
  bilanci = archivi SEC dal 2009 (studi/sec_bilanci_storia.py), usati solo DOPO la data di deposito;
  prezzi  = mensili rettificati di 22.609 titoli USA, anche quelli usciti dalla borsa (cartella "delistate").
  Abbinamento azienda SEC -> titolo: nome normalizzato, solo nomi di UNA azienda SEC (con piu' titoli dello stesso
  nome si prende il piu' scambiato); limite dichiarato: le aziende che hanno cambiato nome restano fuori.
  Capitalizzazione = chiusura EODHD corretta solo per i frazionamenti x azioni dichiarate alla SEC x frazionamenti
  avvenuti dopo (studi/eodhd_capitalizzazione.py); anche la variazione delle azioni (B1) e' calcolata cosi'.
REGOLE (fissate PRIMA di guardare i risultati). Ogni fine mese t, universo = le 500 azioni piu' scambiate dei 12 mesi
  prima (come lo studio onesto); dati di bilancio annuali (10-K, ultimi 18 mesi), azioni in circolazione dal deposito
  piu' recente.
  B1 RIACQUISTI   azioni in circolazione -2% o meno in 12 mesi (al massimo -30%: oltre e' un raggruppamento) e
                  riacquisti pagati nell'anno > 0
  B2 OWNER EARN.  rendimento owner earnings (utile + ammortamenti - capex) / capitalizzazione: primo quinto
  B3 QUALITA'     ROE >= 15% (patrimonio positivo), owner earnings > 0, debito a lungo <= 3 anni di owner earnings
  B4 B3 + PREZZO  B3 e rendimento owner earnings nella meta' alta ("azienda splendida a prezzo giusto")
  B5 B1 + B3      riacquisti fatti da aziende di qualita' (il caso in cui Buffett li approva)
  Pesi uguali, ribilancio mensile, costo 0,20% su ogni cambio (come il satellite).
CONFRONTO: tutte le azioni dell'universo CON bilanci abbinati a pesi uguali (stesso campione: misura il segnale) e SPY.
  STUDIO 2010-2017, VERIFICA 2018-oggi. Una regola "entra" solo se in ENTRAMBI i periodi batte il confronto per
  rendimento E per rendimento/volatilita', con almeno 2,6% l'anno (regola di Ya), e se nella verifica il vantaggio
  mensile ha t >= 2.
CONVENZIONE: un titolo senza il prezzo del mese dopo (uscito dalla borsa) rende 0 quel mese (come lo studio onesto).
USO: python studi/studio_buffett.py <cartella delistate> <cartella bilanci SEC> <cartella storico>
"""
import csv
import glob
import gzip
import json
import math
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from cot_radar import satellite as S          # noqa: E402
import studio_onesto as O                      # noqa: E402

COSTO = S.COSTO
DAL, CAMBIO = "2010-01", "2018-01"
MIN_RENDIMENTO = 2.6
PAROLE_VIA = {"INC", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "PLC", "THE", "LLC", "LP", "NV",
              "SA", "AG", "INCORPORATED", "DE", "NEW", "CL", "CLASS", "COM", "SHS"}


# --------------------------------------------------------------------------- abbinamento nomi
def norma(nome):
    s = re.sub(r"/[A-Z]{2,3}/?", " ", (nome or "").upper())        # "/DE/", "/MD" = stato di registrazione
    s = s.replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return " ".join(p for p in s.split() if p not in PAROLE_VIA)


def abbina(elenco, nomi_sec, scambi=None):
    """{ticker: cik} solo per nomi che individuano UNA azienda SEC. Se lo stesso nome ha piu' titoli (classi A/B,
    vecchio ticker) si prende quello con piu' scambi in totale (scambi = {ticker: controvalore totale})."""
    per_nome = {}
    for cik, nn in nomi_sec.items():
        for n in {norma(x) for x in nn}:
            if n:
                per_nome.setdefault(n, set()).add(cik)
    tick_nome = {}
    for t, v in elenco.items():
        tick_nome.setdefault(norma(v.get("n")), []).append(t)
    out = {}
    for n, ciks in per_nome.items():
        tk = tick_nome.get(n, [])
        if len(ciks) != 1 or not tk:
            continue
        if len(tk) > 1:
            if not scambi:
                continue
            tk = [max(tk, key=lambda t: scambi.get(t, 0))]
        out[tk[0]] = next(iter(ciks))
    return out


# --------------------------------------------------------------------------- bilanci
def carica_bilanci(cartella, ciks):
    """{cik: {voce: [(deposito, fine periodo, trimestri, valore)]}} solo per le aziende abbinate."""
    out = {}
    for f in sorted(glob.glob(os.path.join(cartella, "sec_valori_*.csv.gz"))):
        with gzip.open(f, "rt") as fh:
            for r in csv.reader(fh):
                if r[0] in ciks:
                    out.setdefault(r[0], {}).setdefault(r[4], []).append((r[1], r[2], int(r[3]), float(r[5])))
    for v in out.values():
        for k in v:
            v[k].sort()
    return out


def _mesi_fra(a, b):
    """mesi interi fra due date 'AAAA-MM-GG'."""
    return (int(b[:4]) - int(a[:4])) * 12 + int(b[5:7]) - int(a[5:7])


def ultimo(righe, fino, q=None):
    """Ultima riga depositata entro 'fino' (per data di deposito, poi fine periodo)."""
    best = None
    for dep, fp, qq, v in righe:
        if dep > fino:
            break
        if q is not None and qq != q:
            continue
        if best is None or fp >= best[1]:
            best = (dep, fp, qq, v)
    return best


def valore_anno(b, voci, fino, fp=None):
    """Valore annuale (10-K, 4 trimestri) della prima voce disponibile; con fp, solo per quella fine periodo (+-10 g)."""
    for voce in voci:
        r = b.get(voce)
        if not r:
            continue
        if fp is None:
            x = ultimo(r, fino, 4)
            if x:
                return x
        else:
            for dep, f, q, v in reversed(r):
                if dep <= fino and q == 4 and abs((date.fromisoformat(f) - date.fromisoformat(fp)).days) <= 10:
                    return (dep, f, q, v)
    return None


def valore_bil(b, voci, fino, fp):
    """Valore di bilancio (stock) alla fine periodo fp."""
    for voce in voci:
        for dep, f, q, v in reversed(b.get(voce, [])):
            if dep <= fino and q == 0 and abs((date.fromisoformat(f) - date.fromisoformat(fp)).days) <= 10:
                return v
    return None


def azioni(b, fino):
    for voce in ("azioni", "azioni_bil"):
        x = ultimo(b.get(voce, []), fino, 0)
        if x and x[3] > 0:
            return x
    return None


def fattore(fraz, dopo):
    """Prodotto dei frazionamenti avvenuti DOPO la data 'dopo' (porta un numero di azioni alla base di oggi)."""
    f = 1.0
    for d, r in fraz:
        if d > dopo:
            f *= r
    return f


def fondamentali(b, fine_mese, prezzo, cp=None):
    """Dizionario dei numeri noti a fine mese (stringa 'AAAA-MM-GG'). prezzo(ym) = prezzo rettificato del mese.
    cp = {"c": {AAAA-MM: chiusura corretta solo per i frazionamenti}, "s": [[data, rapporto]]} da EODHD."""
    u = valore_anno(b, ("utile", "utile_tot"), fine_mese)
    if not u or _mesi_fra(u[1], fine_mese) > 18:
        return None
    fp = u[1]
    am = valore_anno(b, ("ammort", "ammort2", "ammort3", "ammort4"), fine_mese, fp)
    cx = valore_anno(b, ("capex", "capex2"), fine_mese, fp)
    rq = valore_anno(b, ("riacquisti",), fine_mese, fp)
    out = {"utile": u[3], "riacq": rq[3] if rq else 0.0}
    if am and cx:
        out["oe"] = u[3] + am[3] - cx[3]
    pn = valore_bil(b, ("pn",), fine_mese, fp)
    out["pn"] = pn
    deb = valore_bil(b, ("debito", "debito_lungo"), fine_mese, fp)
    out["debito"] = deb if deb is not None else 0.0          # chi non dichiara debito a lungo non ne ha (regola fissa)
    a1 = azioni(b, fine_mese)
    anno_fa = f"{int(fine_mese[:4]) - 1}{fine_mese[4:]}"
    a0 = azioni(b, anno_fa)
    if a1 and a0 and _mesi_fra(a1[1], fine_mese) <= 6 and 9 <= _mesi_fra(a0[1], a1[1]) <= 15:
        if cp:                                          # azioni portate alla stessa base: i frazionamenti non contano
            out["var_azioni"] = a1[3] * fattore(cp["s"], a1[1]) / (a0[3] * fattore(cp["s"], a0[1])) - 1
        else:
            out["var_azioni"] = a1[3] / a0[3] - 1
    if cp and a1 and _mesi_fra(a1[1], fine_mese) <= 6:
        px = cp["c"].get(fine_mese[:7])
        if px:
            out["cap"] = px * a1[3] * fattore(cp["s"], a1[1])
    return out


# --------------------------------------------------------------------------- regole
def scelte(fd):
    """{codice: fondamentali} dell'universo del mese -> {regola: [codici]}."""
    oey = {c: f["oe"] / f["cap"] for c, f in fd.items() if f.get("oe") is not None and f.get("cap")}
    ord_ = sorted(oey, key=oey.get, reverse=True)
    quinto, meta = set(ord_[:max(1, len(ord_) // 5)]), set(ord_[:len(ord_) // 2])
    b1 = {c for c, f in fd.items() if f.get("var_azioni") is not None and -0.30 <= f["var_azioni"] <= -0.02
          and f["riacq"] > 0}
    b3 = {c for c, f in fd.items() if f.get("pn") and f["pn"] > 0 and f["utile"] / f["pn"] >= 0.15
          and f.get("oe") is not None and f["oe"] > 0 and f["debito"] <= 3 * f["oe"]}
    return {"B1 riacquisti": b1, "B2 owner earnings": quinto, "B3 qualita'": b3,
            "B4 qualita' + prezzo": b3 & meta, "B5 riacquisti + qualita'": b1 & b3}


def fine_mese(ym):
    a, m = int(ym[:4]), int(ym[5:7])
    nxt = date(a + (m == 12), m % 12 + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1).isoformat()


def rendimento(tt, codici, t, prima):
    """Rendimento pesi uguali del mese t -> t+1 meno i costi; restituisce (r, pesi)."""
    n = len(codici)
    pesi = {c: 1 / n for c in codici} if n else {}
    r = 0.0
    for c in codici:
        x = tt[c][0]
        a, b = x.p.get(t), x.p.get(t + 1)
        if a and b:
            q = b / a - 1
            if -0.95 <= q <= 3.0:
                r += q / n
    giro = sum(abs(pesi.get(c, 0) - prima.get(c, 0)) for c in set(pesi) | set(prima))
    return r - COSTO * giro, pesi


def tstat(xs):
    n = len(xs)
    if n < 3:
        return 0.0
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    return m / sd * math.sqrt(n) if sd else 0.0


def main():
    cart, csec, cst = sys.argv[1], sys.argv[2], sys.argv[3]
    el, dati = O.carica(cart)
    tt = O.titoli(dati)
    nomi = json.load(open(os.path.join(csec, "sec_nomi.json")))
    scambi = {c: sum(cv.values()) for c, (_, cv) in tt.items()}
    mappa = {t: c for t, c in abbina(el, nomi, scambi).items() if t in tt}
    print(f"titoli con prezzi: {len(tt)}, abbinati a un bilancio SEC: {len(mappa)} "
          f"(di cui usciti dalla borsa: {sum(1 for t in mappa if el[t]['stato'] == 'delistata')})")
    bil = carica_bilanci(csec, set(mappa.values()))
    fcap = os.path.join(csec, "cap_prezzi.json.gz")
    cap = {}
    if os.path.exists(fcap):
        for t, v in json.load(gzip.open(fcap, "rt")).items():
            cap[t] = {"c": dict((m, p) for m, p in v["c"]), "s": [tuple(x) for x in v["s"]]}
    print(f"prezzi per la capitalizzazione: {len(cap)} titoli" if cap else "SENZA prezzi per la capitalizzazione")
    spy = O.spy_mensile(cst)
    ultimo_m = max(max(x.p) for x, _ in tt.values()) - 1
    t0, tc = S._n(DAL), S._n(CAMBIO)
    serie = {}
    prima = {}
    copertura = []
    for t in range(t0, ultimo_m):
        ym = S._ym(t)
        fm = fine_mese(ym)
        univ = [x.t for x in O.universo_onesto(tt, t)]
        fd = {}
        for c in univ:
            if c in mappa and mappa[c] in bil:
                f = fondamentali(bil[mappa[c]], fm, lambda m, c=c: tt[c][0].p.get(S._n(m)), cap.get(c))
                if f:
                    fd[c] = f
        copertura.append(len(fd))
        sc = scelte(fd)
        sc["Confronto (tutte con bilancio)"] = set(fd)
        for k, cod in sc.items():
            r, prima[k] = rendimento(tt, sorted(cod), t, prima.get(k, {}))
            serie.setdefault(k, []).append((S._ym(t + 1), r, len(cod)))
        a, b = spy.get(t), spy.get(t + 1)
        serie.setdefault("SPY", []).append((S._ym(t + 1), b / a - 1 if a and b else 0.0, 1))
    print(f"periodo {S._ym(t0 + 1)} - {S._ym(ultimo_m)}; aziende con bilancio nell'universo: "
          f"media {sum(copertura) / len(copertura):.0f} su 500 (min {min(copertura)}, max {max(copertura)})")
    rif = "Confronto (tutte con bilancio)"
    print(f"\n{'':32}{'STUDIO 2010-2017':^30}|{'VERIFICA 2018+':^30}|")
    print(f"{'':32}" + ("  CAGR   Vol  MaxDD   R/V  tit|" * 2) + "  t verif.")
    risultati = {}
    for k, rs in serie.items():
        st = [(m, r) for m, r, _ in rs if m < CAMBIO]
        ve = [(m, r) for m, r, _ in rs if m >= CAMBIO]
        n1 = sum(n for m, _, n in rs if m < CAMBIO) / max(1, len(st))
        n2 = sum(n for m, _, n in rs if m >= CAMBIO) / max(1, len(ve))
        risultati[k] = (O.stat(st), O.stat(ve), n1, n2)
    for k, (a, b, n1, n2) in risultati.items():
        ex = [r - q for (m, r, _), (_, q, _) in zip(serie[k], serie[rif]) if m >= CAMBIO]
        tv = tstat(ex)
        esito = ""
        if k.startswith("B"):
            ra, rb = risultati[rif][0], risultati[rif][1]
            ok = (a and b and a["cagr"] > ra["cagr"] and b["cagr"] > rb["cagr"] and (a["rv"] or 0) > ra["rv"] and (b["rv"] or 0) > rb["rv"]
                  and min(a["cagr"], b["cagr"]) >= MIN_RENDIMENTO and tv >= 2)
            esito = "  ENTRA" if ok else "  scartata"
        f = lambda s, n: (f"{s['cagr']:6.1f}{s['vol']:6.1f}{s['maxdd']:7.1f}{(s['rv'] or 0):6.2f}{n:5.0f}|"  # noqa: E731
                          if s else f"{'(vuota)':^30}|")
        print(f"{k:32}{f(a, n1)}{f(b, n2)}{tv:6.2f}{esito}")


if __name__ == "__main__":
    main()
