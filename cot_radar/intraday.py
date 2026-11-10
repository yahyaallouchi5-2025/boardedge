# -*- coding: utf-8 -*-
"""
intraday.py - v7.26 GRAFICI INTRADAY della scheda del titolo (Azionario): "Oggi" e "5 giorni".

DUE FONTI, ZERO SPRECHI
  1) "5 giorni" = barre a 5 minuti delle ultime 5 sedute, scaricate UNA volta al giorno dal giro USA della sera
     (aggiorna()): EODHD per i titoli che copre (USA, Toronto, Sydney, Xetra, Parigi, Amsterdam...), Londra da EODHD
     convertita da pence a sterline, Milano da Yahoo (EODHD non la copre). Tokyo, Hong Kong, Cina e India: niente
     intraday nel nostro piano -> nessun file, la scheda non mostra le due linguette.
     File: pubblico/intraday/<TICKER>.json  {"t", "agg", "b": [[timestamp, chiusura], ...]}  (~8 KB a titolo)
  2) "Oggi" = un punto ogni 15 minuti raccolto dal ciclo dei prezzi live (live.py -> serie_oggi()): nessuna chiamata
     in piu'. File piccoli nel ramo "live": oggi/<TICKER>.json  [[timestamp, prezzo], ...]  (~1 KB a titolo).
  La pagina unisce le due: se le barre a 5 minuti non hanno ancora la seduta di oggi, aggiunge i punti live.

DEBUG: python -c "from cot_radar import intraday as I; print(I.simbolo('SHEL.L', 'GBP'))"
"""
import json
import os
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from . import azioni as A
from . import eodhd
from .log import log

GIORNI = 8                      # finestra richiesta (calendario): copre 5 sedute anche con un ponte festivo
SEDUTE = 5
TEMPO_MAX = 900                 # secondi massimi per il giro: il resto al giorno dopo
FINESTRA_OGGI = 14 * 3600       # punti "Oggi" tenuti: entro 14 ore dall'ultimo (una seduta dura al massimo 8,5 ore)


def simbolo(t, valuta=None):
    """(simbolo, fattore, fonte) per le barre intraday, o None se il titolo non ha intraday nel nostro piano.
    Londra: EODHD da' i prezzi in pence -> fattore 1/100 se la valuta del titolo e' GBP (come in azioni.scarica)."""
    if t.endswith(".L"):
        return t[:-2] + ".LSE", (0.01 if valuta == "GBP" else 1.0), "eodhd"
    if t.endswith(".MI"):
        return t, 1.0, "yahoo"
    s = eodhd.simbolo(t)
    if s and not s.endswith(".INDX"):
        return s, 1.0, "eodhd"
    return None


def sedute(barre, n=SEDUTE):
    """Solo le ultime n sedute (giorni UTC distinti: nessuna borsa nostra attraversa la mezzanotte UTC in seduta,
    tranne Sydney che pero' sta tutta tra le 23 e le 6 UTC del giorno dopo -> si usa l'ora +2 per non spezzarla)."""
    giorni = sorted({datetime.fromtimestamp(ts + 2 * 3600, timezone.utc).date() for ts, _ in barre})[-n:]
    tieni = set(giorni)
    return [[ts, v] for ts, v in barre if datetime.fromtimestamp(ts + 2 * 3600, timezone.utc).date() in tieni]


def da_eodhd(sym, fattore, adesso):
    js = eodhd.get("intraday/" + sym, {"interval": "5m", "from": int(adesso - GIORNI * 86400)}, timeout=30, tentativi=2)
    if not isinstance(js, list):
        return None
    out = []
    for x in js:
        ts, c = x.get("timestamp"), x.get("close")
        if isinstance(ts, (int, float)) and isinstance(c, (int, float)) and c > 0:
            out.append([int(ts), round(c * fattore, 4)])
    return out


def da_yahoo(t, adesso):
    q = urllib.parse.urlencode({"range": "5d", "interval": "5m"})
    for h in A.HOST:
        try:
            req = urllib.request.Request(A.YAHOO.format(h=h, t=urllib.parse.quote(t), q=q), headers={"User-Agent": "cot-radar/intraday"})
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.load(r)["chart"]["result"][0]
            c = res["indicators"]["quote"][0]["close"]
            return [[int(ts), round(float(v), 4)] for ts, v in zip(res.get("timestamp") or [], c) if v]
        except Exception:
            time.sleep(1)
    return None


def scarica(t, valuta, adesso):
    """Barre a 5 minuti delle ultime 5 sedute, o None."""
    s = simbolo(t, valuta)
    if not s:
        return None
    sym, fattore, fonte = s
    barre = da_eodhd(sym, fattore, adesso) if fonte == "eodhd" else da_yahoo(sym, adesso)
    return sedute(sorted(barre)) if barre else None


def aggiorna(cartella, el=None, adesso=None):
    """Riscrive pubblico/intraday/ per tutti i titoli con intraday. Mai bloccante. Restituisce {"ok", "vuoti"}."""
    adesso = adesso or time.time()
    inizio = time.time()
    elenco = el if el is not None else A.elenco()
    lavori = []
    for x in elenco:
        rec = A._leggi(os.path.join(cartella, "grezzi", A._nome_file(x["t"]) + ".json")) or {}
        if simbolo(x["t"], rec.get("valuta")):
            lavori.append((x["t"], rec.get("valuta")))
    agg = datetime.fromtimestamp(adesso, timezone.utc).isoformat(timespec="minutes")
    conta = {"ok": 0, "vuoti": 0}

    def uno(lavoro):
        t, valuta = lavoro
        if time.time() - inizio > TEMPO_MAX:
            return False
        b = scarica(t, valuta, adesso)
        if not b:
            return False
        A._scrivi(os.path.join(cartella, "pubblico", "intraday", A._nome_file(t) + ".json"), {"t": t, "agg": agg, "b": b})
        return True

    with ThreadPoolExecutor(max_workers=6) as ex:              # 6 richieste insieme: ~1.300 titoli in pochi minuti
        for fatto in ex.map(uno, lavori):
            conta["ok" if fatto else "vuoti"] += 1
    log.warning("intraday 5 giorni: %d titoli scritti, %d senza dati", conta["ok"], conta["vuoti"])
    return conta


def serie_oggi(prima, prezzi):
    """Aggiorna la serie "Oggi" (un punto per giro del ciclo live). prima = {ticker: [[ts, p], ...]} del giro prima,
    prezzi = {ticker: [p, prev, ts]} appena letti. Tiene solo i punti entro FINESTRA_OGGI dall'ultimo (la seduta in
    corso), senza doppioni di orario."""
    out = {}
    for t, punti in (prima or {}).items():
        out[t] = [list(x) for x in punti if isinstance(x, (list, tuple)) and len(x) == 2]
    for t, v in (prezzi or {}).items():
        if not v or not v[0] or not v[2]:
            continue
        s = out.setdefault(t, [])
        if not s or s[-1][0] != int(v[2]):
            s.append([int(v[2]), v[0]])
    for t in list(out):
        s = sorted({ts: p for ts, p in out[t]}.items())
        if not s:
            del out[t]
            continue
        ultimo = s[-1][0]
        out[t] = [[ts, p] for ts, p in s if ultimo - ts <= FINESTRA_OGGI]
    return out
