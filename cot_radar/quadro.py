# -*- coding: utf-8 -*-
"""
quadro.py - v7.20 QUADRO ECONOMICO USA (card informativa della Dashboard). NON e' un segnale operativo.

IDEA (deciso con Ya il 09/11/2026)
  Capire in che fase e' l'economia: crescita e inflazione salgono o scendono? C'e' un allarme recessione?
  Lo studio storico (1962-2026) ha mostrato che i regimi NON anticipano i mercati in modo affidabile (i prezzi si
  muovono prima dei dati): per questo la card e' solo CONTESTO e non entra nei portafogli (li guida il filtro di trend).

DATI (FRED, mensili, escono con circa un mese di ritardo -> si usa l'ultimo mese pubblicato)
  CPIAUCSL prezzi al consumo, UNRATE disoccupazione, INDPRO produzione industriale, DGS10/DGS2 tassi a 10 e 2 anni,
  BAMLH0A0HYM2 spread high yield (quanto pagano in piu' le aziende piu' indebitate).

REGOLE
  crescita SU    = produzione industriale sopra di 12 mesi prima  e  regola di Sahm sotto 0,5
  inflazione SU  = inflazione annua piu' alta di 6 mesi prima
  -> Ripresa (crescita su, inflazione giu'), Espansione (su, su), Stagflazione (giu', su), Recessione (giu', giu')
  STATO DELL'INFLAZIONE (sotto il riquadro Inflazione): Deflazione (sotto zero), Disinflazione (in calo),
  Reflazione (in salita partendo da sotto il 2%), In salita (in salita partendo da sopra il 2%)
  regola di Sahm = media 3 mesi della disoccupazione meno il minimo delle medie 3 mesi dei 12 mesi prima
                   (>= 0,5 punti: storicamente ha segnato l'inizio di ogni recessione USA dal 1970)
  ALLARME RECESSIONE = Sahm >= 0,5  oppure  (curva 10-2 anni invertita negli ultimi 12 mesi e spread high yield
                       salito di oltre 1 punto in 6 mesi)

STORICO (tabella nella (i)): rendimento medio ANNUALIZZATO del mese dopo, per regime, dal 1990 (oro dal 2004), dalle
  serie archiviate nel ramo "storico". S&P 500 = indice + 2% l'anno di dividendi stimati; Treasury 10 anni stimato
  dal rendimento (cedola + duration 8 x variazione del tasso). Se l'archivio manca la tabella non compare.

DEBUG: python -c "from cot_radar import quadro; help(quadro.calcola)"
"""
import csv
import os

from .log import log

# v7.20 nomi scelti da Ya (ciclo economico). Equivalenti nell'"Investment Clock" usato dagli analisti:
#   Ripresa = Recovery, Espansione = Overheat, Stagflazione = Stagflation, Recessione = Reflation
REGIMI = {(True, False): "Ripresa", (True, True): "Espansione",
          (False, True): "Stagflazione", (False, False): "Recessione"}
SAHM_SOGLIA = 0.5
STORICO_DAL = "1990-01"


# --------------------------------------------------------------------------- mesi
def mm(ym, k):
    """Mese 'AAAA-MM' spostato di k mesi (k negativo = indietro)."""
    a, b = int(ym[:4]), int(ym[5:7]) - 1 + k
    return "%d-%02d" % (a + b // 12, b % 12 + 1)


def mensile(punti):
    """[[data, valore], ...] (giornaliero o mensile) -> {'AAAA-MM': ultimo valore del mese}."""
    out = {}
    for d, v in sorted(punti or []):
        out[d[:7]] = v
    return out


# --------------------------------------------------------------------------- indicatori
def sahm(une, ym):
    """Regola di Sahm al mese ym. I mesi senza dato (es. ottobre 2025, chiusura del governo USA) si saltano."""
    def m3(x):
        v = [une[mm(x, -k)] for k in range(3) if mm(x, -k) in une]
        return sum(v) / len(v) if v else None
    ora = m3(ym)
    prima = [v for v in (m3(mm(ym, -k)) for k in range(1, 13)) if v is not None]
    return ora - min(prima) if ora is not None and prima else None


def stato(cpi, une, ind, d10, d2, hy, u):
    """Indicatori e regime con l'ultimo mese pubblicato u ('AAAA-MM'). None se mancano dati."""
    try:
        infl = (cpi[u] / cpi[mm(u, -12)] - 1) * 100
        infl6 = (cpi[mm(u, -6)] / cpi[mm(u, -18)] - 1) * 100
        prod = (ind[u] / ind[mm(u, -12)] - 1) * 100
    except (KeyError, ZeroDivisionError):
        return None
    s = sahm(une, u)
    if s is None:
        return None
    cresce = prod > 0 and s < SAHM_SOGLIA
    sale = infl > infl6
    # curva e spread: ultimi valori disponibili fino al mese DOPO u (sono dati di mercato, quotidiani)
    fine = mm(u, 1)
    curve = [d10[m] - d2[m] for m in (mm(fine, -k) for k in range(12)) if m in d10 and m in d2]
    curva = curve[0] if curve else None
    invertita = any(c < 0 for c in curve)
    hy_ora, hy_prima = hy.get(fine) or hy.get(u), hy.get(mm(fine, -6))
    spread_su = hy_ora is not None and hy_prima is not None and hy_ora - hy_prima > 1.0
    allarme = s >= SAHM_SOGLIA or (invertita and spread_su)
    # stato dell'inflazione: il 2% e' l'obiettivo della Fed
    tipo = "Deflazione" if infl < 0 else ("Disinflazione" if not sale else ("Reflazione" if infl6 < 2 else "In salita"))
    return {"mese": u, "regime": REGIMI[(cresce, sale)], "tipo_infl": tipo, "cresce": cresce, "sale": sale,
            "infl": round(infl, 1), "infl6": round(infl6, 1), "prod": round(prod, 1),
            "disoc": une.get(u), "sahm": round(s, 2), "curva": None if curva is None else round(curva, 2),
            "invertita": invertita, "hy": None if hy_ora is None else round(hy_ora, 2), "allarme": bool(allarme)}


# --------------------------------------------------------------------------- storico per regime
def _csv(cartella, nome):
    f = os.path.join(cartella, nome)
    if not os.path.exists(f):
        return {}
    out = []
    with open(f, encoding="utf-8") as fh:
        for r in csv.reader(fh):
            try:
                out.append([r[0], float(r[1])])
            except (ValueError, IndexError):
                pass
    return mensile(out)


def storico(cartella):
    """Rendimento medio annualizzato (%) del mese dopo per regime dal 1990: {regime: {mercato: [media, mesi]}}."""
    s = {k: _csv(cartella, k + ".csv") for k in ("CPIAUCSL", "UNRATE", "INDPRO", "DGS10", "DGS2", "BAMLH0A0HYM2")}
    spx, gld = _csv(cartella, os.path.join("yahoo", "_GSPC.csv")), _csv(cartella, os.path.join("yahoo", "GLD.csv"))
    if not (s["CPIAUCSL"] and s["UNRATE"] and s["INDPRO"] and spx and s["DGS10"]):
        return None
    tab = {}
    for m in sorted(x for x in spx if x >= STORICO_DAL):
        st = stato(s["CPIAUCSL"], s["UNRATE"], s["INDPRO"], s["DGS10"], s["DGS2"], s["BAMLH0A0HYM2"], mm(m, -1))
        n = mm(m, 1)
        if not st or n not in spx:
            continue
        r = {"sp": spx[n] / spx[m] - 1 + 0.02 / 12}
        if m in s["DGS10"] and n in s["DGS10"]:
            r["tr"] = s["DGS10"][m] / 1200 - 8 * (s["DGS10"][n] - s["DGS10"][m]) / 100
        if m in gld and n in gld:
            r["oro"] = gld[n] / gld[m] - 1
        for k, v in r.items():
            tab.setdefault(st["regime"], {}).setdefault(k, []).append(v)
    return {reg: {k: [round(sum(v) / len(v) * 1200, 1), len(v)] for k, v in d.items()} for reg, d in tab.items()}


# --------------------------------------------------------------------------- ingresso
def calcola(fred, cartella=None):
    """Dati della card. fred = {codice: [[data, valore]]} (download della Dashboard, circa 3 anni);
    cartella = archivio storico (per la tabella). None se mancano i dati."""
    g = {k: mensile(fred.get(k)) for k in ("CPIAUCSL", "UNRATE", "INDPRO", "DGS10", "DGS2", "BAMLH0A0HYM2")}
    if not (g["CPIAUCSL"] and g["UNRATE"] and g["INDPRO"]):
        return None
    u = min(max(g["CPIAUCSL"]), max(g["INDPRO"]), max(g["UNRATE"]))      # ultimo mese con tutti e tre i dati
    out = stato(g["CPIAUCSL"], g["UNRATE"], g["INDPRO"], g["DGS10"], g["DGS2"], g["BAMLH0A0HYM2"], u)
    if not out:
        return None
    # mese prima, per le frecce di tendenza di disoccupazione e crescita
    prima = stato(g["CPIAUCSL"], g["UNRATE"], g["INDPRO"], g["DGS10"], g["DGS2"], g["BAMLH0A0HYM2"], mm(u, -3))
    if prima:
        out["prima"] = {k: prima[k] for k in ("infl", "prod", "disoc", "curva", "regime")}
    if cartella:
        try:
            out["storico"] = storico(cartella)
        except Exception as e:                      # la tabella e' un di piu': senza, la card resta
            log.warning("quadro economico: storico non calcolato (%s)", e)
    return out
