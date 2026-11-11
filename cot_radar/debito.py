# -*- coding: utf-8 -*-
"""
debito.py - v7.40 CICLO DEL DEBITO USA (riga dentro il "Quadro economico"). NON e' un segnale operativo.

IDEA (dal modello di Ray Dalio, "Big Debt Crises": il ciclo del debito ha fasi riconoscibili dai dati)
  Il debito privato cresce piu' del reddito (bolla), la banca centrale stringe (picco), il credito si rompe (crisi),
  poi il debito scende rispetto al reddito (riduzione del debito) e si riparte (espansione).
  Qui le fasi si leggono da 5 dati pubblici, con regole fisse. Serve a dare CONTESTO: lo studio storico (tabella
  nella (i), calcolata a ogni giro) mostra quanto ha reso l'S&P 500 dopo ogni fase; non guida i portafogli.

DATI (FRED; il debito esce ogni 3 mesi con circa 10 settimane di ritardo)
  CMDEBT + TBSDODNS  debito di famiglie e aziende non finanziarie (milioni $)   } debito privato in % del PIL
  GDP                PIL nominale annualizzato (miliardi $)                      }
  TDSP               rata dei debiti delle famiglie in % del reddito disponibile (dal 2005)
  FEDFUNDS, CPIAUCSL tasso della Fed e prezzi al consumo -> tasso REALE = tasso Fed - inflazione annua
  T10Y2Y             curva dei tassi: 10 anni meno 2 anni
  BAA10Y             spread delle obbligazioni aziendali Baa sul Treasury a 10 anni (stress del credito)

REGOLE (in quest'ordine: vince la prima vera). Il debito e' dell'ultimo trimestre pubblicato, i dati di mercato
        del trimestre DOPO (sono gia' noti quando il dato sul debito esce: cosi' la fase non usa mai dati futuri).
  1) CRISI                spread Baa sopra 3,5 punti nel trimestre, oppure salito di oltre 0,6 punti in 6 mesi
  2) PICCO                curva sotto 0,25 punti  E  (tasso reale sopra zero  oppure  Fed salita di oltre 1,5 punti in un anno)
  3) RIDUZIONE DEL DEBITO debito/PIL piu' basso di un anno prima
  4) BOLLA                debito/PIL salito di oltre 5 punti in 3 anni  E  di oltre 1 punto nell'ultimo anno
  5) ESPANSIONE           tutti gli altri casi

STORICO: per ogni trimestre dal 1988 la fase "nota" a fine trimestre e il rendimento dell'S&P 500 nel trimestre dopo
  (indice + 2% l'anno di dividendi stimati, come quadro.py). Prezzi dall'archivio (ramo "storico").

FILE: storico/debito.json = cache delle serie gia' ridotte a trimestri (si riscarica ogni RIFAI_ORE ore; se FRED non
  risponde resta la copia precedente). Mai bloccante: senza dati la riga non compare.

DEBUG: python -c "from cot_radar import debito as D; print(D.fase_regole(140, 150, 142, 0.5, 0.4, 0.0, 1.7, 1.9, 1.6))"
"""
import json
import os
from datetime import datetime, timedelta, timezone

from .log import log

FILE = "debito.json"
RIFAI_ORE = 20
DAL = "1984-01-01"
# soglie delle regole (vedi sopra)
STRESS_LIVELLO, STRESS_SALTO = 3.5, 0.6
CURVA_PIATTA, STRETTA_RIALZO = 0.25, 1.5
BOLLA_3A, BOLLA_1A = 5.0, 1.0
# serie -> come si riduce a un valore per trimestre
SERIE = {"CMDEBT": "ultimo", "TBSDODNS": "ultimo", "GDP": "ultimo", "TDSP": "ultimo", "CPIAUCSL": "ultimo",
         "FEDFUNDS": "media", "T10Y2Y": "media", "BAA10Y": "media"}
FASI = ("Espansione", "Bolla", "Picco", "Crisi", "Riduzione del debito")


# --------------------------------------------------------------------------- trimestri
def trim(data):
    """'AAAA-MM-GG' -> 'AAAA-Tn'."""
    return "%s-T%d" % (data[:4], (int(data[5:7]) - 1) // 3 + 1)


def tt(q, k):
    """Trimestre 'AAAA-Tn' spostato di k trimestri (k negativo = indietro)."""
    n = int(q[:4]) * 4 + int(q[6]) - 1 + k
    return "%d-T%d" % (n // 4, n % 4 + 1)


def riduci(punti, modo):
    """[[data, valore], ...] -> {trimestre: ultimo valore | media | massimo}."""
    g = {}
    for d, v in sorted(punti or []):
        g.setdefault(trim(d), []).append(v)
    f = {"ultimo": lambda v: v[-1], "media": lambda v: sum(v) / len(v), "max": max}[modo]
    return {q: round(f(v), 4) for q, v in g.items()}


# --------------------------------------------------------------------------- regole
def fase_regole(deb, deb3, deb1, reale, curva, fed1, spread, spread_max, spread_6m):
    """La fase, dai numeri gia' pronti. deb/deb3/deb1 = debito/PIL ora, 3 anni e 1 anno prima; reale = tasso reale;
    fed1 = variazione del tasso Fed in un anno; spread = media del trimestre, spread_max = massimo,
    spread_6m = media di due trimestri prima. -> (fase, stress, stretta)"""
    stress = spread_max > STRESS_LIVELLO or spread - spread_6m > STRESS_SALTO
    stretta = curva < CURVA_PIATTA and (reale > 0 or fed1 > STRETTA_RIALZO)
    if stress:
        f = "Crisi"
    elif stretta:
        f = "Picco"
    elif deb < deb1:
        f = "Riduzione del debito"
    elif deb - deb3 > BOLLA_3A and deb - deb1 > BOLLA_1A:
        f = "Bolla"
    else:
        f = "Espansione"
    return f, stress, stretta


def debito_pil(S):
    """{trimestre: debito privato in % del PIL}."""
    return {q: (S["CMDEBT"][q] + S["TBSDODNS"][q]) / 1000.0 / S["GDP"][q] * 100
            for q in S["CMDEBT"] if q in S["TBSDODNS"] and S["GDP"].get(q)}


def lettura(S, q_deb, q_mer=None):
    """Indicatori e fase con il debito del trimestre q_deb e i dati di mercato di q_mer (di norma il trimestre dopo).
    None se manca qualcosa."""
    q_mer = q_mer or tt(q_deb, 1)
    L = debito_pil(S)
    try:
        deb, deb3, deb1 = L[q_deb], L[tt(q_deb, -12)], L[tt(q_deb, -4)]
        cpi = S["CPIAUCSL"]
        q_cpi = q_mer if q_mer in cpi else tt(q_mer, -1)          # trimestre appena iniziato: inflazione del precedente
        infl = (cpi[q_cpi] / cpi[tt(q_cpi, -4)] - 1) * 100
        fed, fed_prima = S["FEDFUNDS"][q_mer], S["FEDFUNDS"][tt(q_mer, -4)]
        curva, spread, spread_6m = S["T10Y2Y"][q_mer], S["BAA10Y"][q_mer], S["BAA10Y"][tt(q_mer, -2)]
    except (KeyError, ZeroDivisionError):
        return None
    spread_max = (S.get("BAA10Y_max") or {}).get(q_mer, spread)
    reale = fed - infl
    f, stress, stretta = fase_regole(deb, deb3, deb1, reale, curva, fed - fed_prima, spread, spread_max, spread_6m)
    return {"fase": f, "trimestre": q_deb, "mercato": q_mer, "debito": round(deb, 1), "deb3": round(deb - deb3, 1),
            "deb1": round(deb - deb1, 1), "reale": round(reale, 1), "fed": round(fed, 2), "infl": round(infl, 1),
            "curva": round(curva, 2), "spread": round(spread, 2), "stress": stress, "stretta": stretta}


def storia(S):
    """[(trimestre del debito, fase)] per tutti i trimestri calcolabili, dal piu' vecchio."""
    out = []
    for q in sorted(debito_pil(S)):
        x = lettura(S, q)
        if x:
            out.append((q, x["fase"]))
    return out


def tabella(st, spx):
    """st = storia(); spx = {trimestre: ultimo prezzo dell'S&P 500}.
    La fase del trimestre q si conosce a fine q+1 -> rendimento del trimestre q+2.
    -> {fase: [media annualizzata %, trimestri, % di trimestri positivi, peggior trimestre %]}"""
    g = {}
    for q, f in st:
        a, b = spx.get(tt(q, 1)), spx.get(tt(q, 2))
        if a and b:
            g.setdefault(f, []).append(b / a - 1 + 0.02 / 4)
    return {f: [round(sum(v) / len(v) * 400, 1), len(v), round(100.0 * sum(1 for x in v if x > 0) / len(v)),
                round(min(v) * 100, 1)] for f, v in g.items()}


# --------------------------------------------------------------------------- dati
def scarica(get=None):
    """Scarica le serie e le riduce a trimestri: {codice: {trimestre: valore}} (+ BAA10Y_max). Una serie che fallisce
    non ferma le altre: il chiamante tiene la copia precedente."""
    if get is None:
        from .fonti import get_fred as get
    out = {}
    for sid, modo in SERIE.items():
        try:
            punti = get(sid, "2004-01-01" if sid == "TDSP" else DAL)
            out[sid] = riduci(punti, modo)
            if sid == "BAA10Y":
                out["BAA10Y_max"] = riduci(punti, "max")
        except Exception as e:
            log.warning("ciclo del debito: %s non scaricato (%s)", sid, e)
    return out


def aggiorna_cache(cartella, scarica_ora=True, adesso=None, get=None):
    """Legge storico/debito.json e, se ha piu' di RIFAI_ORE ore, riscarica le serie (resta la copia di quelle fallite)."""
    f = os.path.join(cartella, FILE) if cartella else None
    cache = {}
    if f and os.path.exists(f):
        try:
            with open(f, encoding="utf-8") as fh:
                cache = json.load(fh)
        except (OSError, ValueError):
            cache = {}
    adesso = adesso or datetime.now(timezone.utc)
    try:
        fresca = adesso - datetime.fromisoformat(cache.get("agg", "")) < timedelta(hours=RIFAI_ORE)
    except ValueError:
        fresca = False
    if scarica_ora and not fresca:
        cache.setdefault("serie", {}).update(scarica(get))
        cache["agg"] = adesso.isoformat(timespec="minutes")
        if f:
            try:
                with open(f + ".tmp", "w", encoding="utf-8") as fh:
                    json.dump(cache, fh, separators=(",", ":"))
                os.replace(f + ".tmp", f)
            except OSError as e:
                log.warning("ciclo del debito: cache non salvata (%s)", e)
    return cache


def _spx(cartella):
    """{trimestre: ultimo prezzo dell'S&P 500} dall'archivio. {} se manca."""
    f = os.path.join(cartella, "yahoo", "_GSPC.csv")
    out = {}
    if os.path.exists(f):
        with open(f, encoding="utf-8") as fh:
            for riga in fh:
                p = riga.strip().split(",")
                try:
                    out[trim(p[0])] = float(p[1])
                except (ValueError, IndexError):
                    pass
    return out


# --------------------------------------------------------------------------- ingresso
def calcola(cartella=None, scarica_ora=True, adesso=None, get=None):
    """Dati della riga "Ciclo del debito" (USA). None se mancano i dati essenziali."""
    cache = aggiorna_cache(cartella, scarica_ora, adesso, get)
    S = cache.get("serie") or {}
    if not all(S.get(k) for k in ("CMDEBT", "TBSDODNS", "GDP", "CPIAUCSL", "FEDFUNDS", "T10Y2Y", "BAA10Y")):
        return None
    L = debito_pil(S)
    if not L:
        return None
    q_deb = max(L)
    q_mer = max(q for q in S["BAA10Y"] if q in S["T10Y2Y"] and q in S["FEDFUNDS"])     # trimestre in corso (parziale)
    out = lettura(S, q_deb, q_mer)
    if not out:
        return None
    st = storia(S)
    # in pagina i trimestri sono quelli dei dati di mercato (quando la fase era "nota"): trimestre del debito + 1
    vista = [[tt(q, 1), FASI.index(f)] for q, f in st]
    if not vista or vista[-1][0] < q_mer:
        vista.append([q_mer, FASI.index(out["fase"])])
    da = vista[-1][0]                                                   # da quando dura la fase di oggi
    for q, i in reversed(vista):
        if i != FASI.index(out["fase"]):
            break
        da = q
    out["da"] = da
    out["storia"] = vista[-60:]                                        # 15 anni, per la striscia
    tdsp = S.get("TDSP") or {}
    if tdsp:
        out["rata"] = round(tdsp[max(tdsp)], 1)
        out["rata_media"] = round(sum(tdsp.values()) / len(tdsp), 1)
        out["rata_dal"] = min(tdsp)[:4]
    if cartella:
        try:
            spx = _spx(cartella)
            if spx and st:
                out["storico"] = tabella(st, spx)
                out["storico_dal"] = st[0][0][:4]
        except Exception as e:
            log.warning("ciclo del debito: storico non calcolato (%s)", e)
    out["agg"] = cache.get("agg")
    return out
