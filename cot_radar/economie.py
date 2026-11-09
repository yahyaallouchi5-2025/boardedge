# -*- coding: utf-8 -*-
"""
economie.py - v7.21 QUADRO ECONOMICO DI 6 ECONOMIE (Dashboard): USA, Eurozona, Giappone, Regno Unito, Australia,
Canada. Solo CONTESTO, non un segnale operativo (lo studio storico di quadro.py: le fasi non anticipano i mercati).

STESSA REGOLA PER TUTTE (cosi' si confrontano tra loro)
  crescita SU    = indicatore anticipatore OCSE (CLI, "amplitude adjusted") piu' alto di 3 mesi prima
                   (Eurozona: media di Germania, Francia, Italia e Spagna pesata per il PIL)
  inflazione SU  = inflazione annua piu' alta di 6 mesi prima (BIS; USA da FRED)
  -> Ripresa (su, giu'), Espansione (su, su), Stagflazione (giu', su), Recessione (giu', giu')  [quadro.REGIMI]
  ALLARME RECESSIONE = regola di Sahm sulla disoccupazione (OCSE; USA da FRED) >= 0,5 punti;
                       per gli USA anche curva 10-2 invertita + spread high yield in salita (quadro.stato)

FONTI (verificate con il workflow "Prova OCSE" il 09/11/2026; API pubbliche, senza chiave)
  OCSE CLI          sdmx.oecd.org  DSD_STES@DF_CLI       ultimi dati ~1 mese fa
  OCSE disoccupaz.  sdmx.oecd.org  DSD_LFS@DF_IALFS_UNE_M (destagionalizzata, 15 anni e piu')
  BIS inflazione    stats.bis.org  WS_LONG_CPI, 771 = variazione annua %   (l'OCSE non pubblica piu' il Giappone)
CACHE: storico/economie.json (salvata nel ramo "storico" dal workflow del sito). Si riscarica se ha piu' di 20 ore;
  se una fonte non risponde restano i dati della volta prima (le serie sono mensili: un giorno di ritardo non conta).

DEBUG: python -c "from cot_radar import economie; help(economie.calcola)"
"""
import csv
import io
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from . import quadro as Q
from .log import log

FILE = "economie.json"
RIFAI_ORE = 20
UA = "cot-radar/economie (+https://github.com/yahyaallouchi5-2025/cot-radar)"
# id, nome, codice OCSE (CLI e disoccupazione), codice BIS (inflazione), valuta (punteggio COT nella Dashboard)
ECONOMIE = [("usa", "USA", "USA", "US", "DXY"), ("eur", "Eurozona", None, "XM", "EUR"),
            ("jpn", "Giappone", "JPN", "JP", "JPY"), ("gbr", "Regno Unito", "GBR", "GB", "GBP"),
            ("aus", "Australia", "AUS", "AU", "AUD"), ("can", "Canada", "CAN", "CA", "CAD")]
# Eurozona = media dei 4 paesi piu' grandi, pesi = quota di PIL (circa, 2025): Germania, Francia, Italia, Spagna
PESI_EUR = {"DEU": 0.39, "FRA": 0.27, "ITA": 0.20, "ESP": 0.14}
OCSE = "https://sdmx.oecd.org/public/rest/data/"
URL_CLI = OCSE + "OECD.SDD.STES,DSD_STES@DF_CLI,4.1/{paesi}.M.LI...AA...H?startPeriod={dal}&format=csvfile"
URL_UNE = OCSE + "OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M,1.0/all?startPeriod={dal}&format=csvfile"
URL_BIS = "https://stats.bis.org/api/v1/data/WS_LONG_CPI/M.{paesi}.771?startPeriod={dal}&format=csv"


# --------------------------------------------------------------------------- download
def _get(url, timeout=120):
    """Testo della risposta; nuovi tentativi se il server limita le richieste (429) o non risponde."""
    for t in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code != 429 or t == 2:
                raise
        except (urllib.error.URLError, TimeoutError):
            if t == 2:
                raise
        time.sleep(15 * (t + 1))


def _righe(testo):
    return list(csv.DictReader(io.StringIO(testo)))


def scarica_cli(get=_get):
    """{paese OCSE: {'AAAA-MM': valore}} dell'indicatore anticipatore, dal 1960 (serve la storia lunga USA)."""
    paesi = "+".join([e[2] for e in ECONOMIE if e[2]] + list(PESI_EUR))
    out = {}
    for r in _righe(get(URL_CLI.format(paesi=paesi, dal="1960-01"))):
        try:
            out.setdefault(r["REF_AREA"], {})[r["TIME_PERIOD"]] = float(r["OBS_VALUE"])
        except (KeyError, ValueError):
            pass
    return out


def scarica_disoccupazione(get=_get, oggi=None):
    """{paese OCSE: {'AAAA-MM': %}}: tasso destagionalizzato, totale, 15 anni e piu', solo mensile (ultimi 3 anni)."""
    dal = ((oggi or datetime.now(timezone.utc).date()) - timedelta(days=3 * 366)).strftime("%Y-%m")
    voluti, out = {e[2] for e in ECONOMIE if e[2]}, {}
    for r in _righe(get(URL_UNE.format(dal=dal))):
        if (r.get("REF_AREA") in voluti and r.get("MEASURE") == "UNE_LF_M" and r.get("ADJUSTMENT") == "Y"
                and r.get("SEX") == "_T" and r.get("AGE") == "Y_GE15" and len(r.get("TIME_PERIOD", "")) == 7):
            try:
                out.setdefault(r["REF_AREA"], {})[r["TIME_PERIOD"]] = float(r["OBS_VALUE"])
            except ValueError:
                pass
    return out


def scarica_inflazione(get=_get):
    """{paese BIS: {'AAAA-MM': inflazione annua %}} dal 2000."""
    out = {}
    for r in _righe(get(URL_BIS.format(paesi="+".join(e[3] for e in ECONOMIE), dal="2000-01"))):
        try:
            out.setdefault(r["REF_AREA"], {})[r["TIME_PERIOD"]] = float(r["OBS_VALUE"])
        except (KeyError, ValueError):
            pass
    return out


def aggiorna_cache(cartella, scarica=True, adesso=None):
    """Legge storico/economie.json e, se ha piu' di RIFAI_ORE ore, riscarica le fonti (ognuna isolata:
    se una fallisce resta la sua copia precedente). Restituisce il dizionario della cache."""
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
    if scarica and not fresca:
        for chiave, fn in (("cli", scarica_cli), ("une", scarica_disoccupazione), ("cpi", scarica_inflazione)):
            try:
                dati = fn()
                if dati:
                    cache[chiave] = dati
            except Exception as e:                     # una fonte giu' non ferma le altre
                log.warning("economie: %s non scaricato (%s), resta la copia precedente", chiave, e)
        cache["agg"] = adesso.isoformat(timespec="minutes")
        if f:
            try:
                tmp = f + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(cache, fh, separators=(",", ":"))
                os.replace(tmp, f)
            except OSError as e:
                log.warning("economie: cache non salvata (%s)", e)
    return cache


# --------------------------------------------------------------------------- calcolo
def cli_eurozona(cli):
    """Media pesata per PIL dei 4 paesi grandi, solo nei mesi in cui ci sono tutti."""
    serie = [cli.get(p) or {} for p in PESI_EUR]
    mesi = set.intersection(*(set(s) for s in serie)) if all(serie) else set()
    return {m: round(sum(PESI_EUR[p] * cli[p][m] for p in PESI_EUR), 4) for m in mesi}


def fase(cli, cpi, une, oggi_mese=None):
    """Stato di un'economia con le sue serie mensili {'AAAA-MM': v}. None se mancano i dati essenziali."""
    if not cli or not cpi:
        return None
    m_cli = max(cli)
    m_cpi = max(cpi)
    try:
        cresce = cli[m_cli] > cli[Q.mm(m_cli, -3)]
        sale = cpi[m_cpi] > cpi[Q.mm(m_cpi, -6)]
    except KeyError:
        return None
    infl, infl6 = cpi[m_cpi], cpi[Q.mm(m_cpi, -6)]
    tipo = "Deflazione" if infl < 0 else ("Disinflazione" if not sale else ("Reflazione" if infl6 < 2 else "In salita"))
    out = {"regime": Q.REGIMI[(cresce, sale)], "cresce": cresce, "sale": sale, "tipo_infl": tipo,
           "mese": min(m_cli, m_cpi), "mese_cli": m_cli, "mese_cpi": m_cpi,
           "cli": round(cli[m_cli], 2), "cli3": round(cli[Q.mm(m_cli, -3)], 2),
           "infl": round(infl, 1), "infl6": round(infl6, 1)}
    if une:
        u = max(une)
        s = Q.sahm(une, u)
        out.update({"disoc": round(une[u], 1), "mese_disoc": u,
                    "sahm": None if s is None else round(s, 2), "allarme": bool(s is not None and s >= Q.SAHM_SOGLIA)})
    return out


def storico_usa(cli, cartella):
    """Tabella della (i): rendimento medio annualizzato del mese dopo per fase, dal 1990 (oro dal 2004), con la regola
    di oggi (CLI + inflazione). Inflazione USA dal CPI archiviato (FRED), pubblicato con 1 mese di ritardo."""
    cpi_i = Q._csv(cartella, "CPIAUCSL.csv")
    spx, gld = Q._csv(cartella, os.path.join("yahoo", "_GSPC.csv")), Q._csv(cartella, os.path.join("yahoo", "GLD.csv"))
    d10 = Q._csv(cartella, "DGS10.csv")
    if not (cli and cpi_i and spx):
        return None
    yoy = {m: (cpi_i[m] / cpi_i[Q.mm(m, -12)] - 1) * 100 for m in cpi_i if Q.mm(m, -12) in cpi_i}
    tab = {}
    for m in sorted(x for x in spx if x >= Q.STORICO_DAL):
        u, n = Q.mm(m, -1), Q.mm(m, 1)                 # a fine mese m si conosce il dato del mese prima
        if not all(k in cli for k in (u, Q.mm(u, -3))) or not all(k in yoy for k in (u, Q.mm(u, -6))) or n not in spx:
            continue
        reg = Q.REGIMI[(cli[u] > cli[Q.mm(u, -3)], yoy[u] > yoy[Q.mm(u, -6)])]
        r = {"sp": spx[n] / spx[m] - 1 + 0.02 / 12}
        if m in d10 and n in d10:
            r["tr"] = d10[m] / 1200 - 8 * (d10[n] - d10[m]) / 100
        if m in gld and n in gld:
            r["oro"] = gld[n] / gld[m] - 1
        for k, v in r.items():
            tab.setdefault(reg, {}).setdefault(k, []).append(v)
    return {reg: {k: [round(sum(v) / len(v) * 1200, 1), len(v)] for k, v in d.items()} for reg, d in tab.items()}


def calcola(fred, cartella=None, scarica=True):
    """Dati della sezione "Quadro economico": {"economie": [...], "storico": tabella USA}. None se non c'e' nulla.
    USA: inflazione, disoccupazione (Sahm), curva e spread da FRED (quadro.py); crescita dal CLI dell'OCSE."""
    cache = aggiorna_cache(cartella, scarica=scarica)
    cli, une, cpi = cache.get("cli") or {}, cache.get("une") or {}, cache.get("cpi") or {}
    usa_fred = None
    try:
        usa_fred = Q.calcola(fred, None)            # indicatori FRED degli USA (anche la curva 10-2 e l'allarme)
    except Exception as e:
        log.warning("economie: indicatori USA da FRED non calcolati (%s)", e)
    out = []
    for eid, nome, ocse, bis, valuta in ECONOMIE:
        c = cli_eurozona(cli) if eid == "eur" else cli.get(ocse) or {}
        p = cpi.get(bis) or {}
        if eid == "usa" and usa_fred:                # inflazione USA: stessa serie della card USA (FRED, piu' fresca)
            cpi_f = Q.mensile(fred.get("CPIAUCSL"))
            p = {m: (cpi_f[m] / cpi_f[Q.mm(m, -12)] - 1) * 100 for m in cpi_f if Q.mm(m, -12) in cpi_f} or p
        u = Q.mensile(fred.get("UNRATE")) if eid == "usa" else (une.get(ocse) or {})
        st = fase(c, p, u)
        if not st:
            log.warning("economie: %s senza dati sufficienti", nome)
            continue
        st.update({"id": eid, "nome": nome, "valuta": valuta})
        if eid == "usa" and usa_fred:
            st.update({k: usa_fred.get(k) for k in ("curva", "invertita", "hy", "prod")})
            st["allarme"] = bool(st.get("allarme") or usa_fred.get("allarme"))
        out.append(st)
    if not out:
        return None
    res = {"economie": out, "agg": cache.get("agg")}
    if cartella and cli.get("USA"):
        try:
            res["storico"] = storico_usa(cli["USA"], cartella)
        except Exception as e:
            log.warning("economie: storico USA non calcolato (%s)", e)
    return res
