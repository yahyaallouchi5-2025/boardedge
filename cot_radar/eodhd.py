# -*- coding: utf-8 -*-
"""
eodhd.py - v6.97 FONTE PRINCIPALE DEI PREZZI: EODHD (abbonamento "EOD + Intraday", 100.000 chiamate al giorno).

PERCHE': Yahoo blocca spesso i server di GitHub (giri con 0 titoli aggiornati, avviso "in manutenzione").
EODHD e' un servizio a pagamento con chiave: niente blocchi, storico lungo, titoli delistati, ETF in euro su Xetra.

FLUSSO (sempre con paracadute):
  1) EODHD per tutto quello che copre: USA, Xetra, Parigi, Amsterdam, Madrid, Bruxelles, Helsinki..., indici, ETF.
  2) YAHOO solo per quello che EODHD non ha (Borsa di Milano, Asia, future "=F") o se EODHD non risponde.
  3) Se falliscono entrambi restano le copie salvate (azioni.py / portafogli.py), con l'avviso solo se i dati
     diventano davvero vecchi (paracadute v6.95).
CHIAVE: solo nella variabile d'ambiente EODHD_API_KEY (Secrets di GitHub). Mai nei log, nei file o negli errori:
  per questo gli errori riportano solo il codice HTTP o il tipo di eccezione, mai l'indirizzo chiamato.
Senza chiave (test, prove in locale) attivo() e' False e tutto continua con Yahoo come prima.
"""
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

log = logging.getLogger(__name__)

BASE = "https://eodhd.com/api/"
PAUSA = 0.07                   # ~850 richieste al minuto al massimo (limite EODHD: 1.000 al minuto)
TENTATIVI = 3

# Suffisso del ticker Yahoo -> codice borsa EODHD. Quello che non e' qui (Milano .MI, Tokyo .T, Hong Kong .HK,
# Shanghai .SS, Shenzhen .SZ, India .NS/.BO) resta a Yahoo: EODHD non lo copre nel nostro piano.
BORSE = {".DE": "XETRA", ".F": "F", ".PA": "PA", ".AS": "AS", ".BR": "BR", ".MC": "MC", ".LS": "LS",
         ".HE": "HE", ".VI": "VI", ".IR": "IR", ".L": "LSE", ".SW": "SW", ".CO": "CO", ".ST": "ST",
         ".OL": "OL", ".TO": "TO"}
VALUTA = {"US": "USD", "XETRA": "EUR", "F": "EUR", "PA": "EUR", "AS": "EUR", "BR": "EUR", "MC": "EUR",
          "LS": "EUR", "HE": "EUR", "VI": "EUR", "IR": "EUR"}
# Indici: nome Yahoo -> nome EODHD (borsa INDX). Se uno non risponde, si usa Yahoo (paracadute).
INDICI = {"^GSPC": "GSPC.INDX", "^NDX": "NDX.INDX", "^GDAXI": "GDAXI.INDX", "^STOXX50E": "STOXX50E.INDX",
          "^N225": "N225.INDX", "^HSI": "HSI.INDX", "^NSEI": "NSEI.INDX", "FTSEMIB.MI": "FTSEMIB.INDX"}

CHIAMATE = {"n": 0, "errori": 0}   # contatore del giro (per il registro: quante chiamate e quanti errori)


def chiave():
    return os.environ.get("EODHD_API_KEY", "").strip()


def attivo():
    """True se c'e' la chiave: EODHD e' la fonte principale. False = si continua solo con Yahoo."""
    return bool(chiave())


def simbolo(t):
    """Ticker Yahoo -> simbolo EODHD, oppure None se EODHD non lo copre (allora resta Yahoo)."""
    if t in INDICI:
        return INDICI[t]
    if t.startswith("^") or "=" in t:              # altri indici e future: Yahoo
        return None
    if t.endswith("-USD"):                         # cripto: BTC-USD -> BTC-USD.CC
        return t + ".CC"
    if "." not in t:                               # titoli ed ETF USA (BRK-B, BF-B con il trattino come su EODHD)
        return t + ".US"
    for suf, borsa in BORSE.items():
        if t.endswith(suf):
            return t[: -len(suf)] + "." + borsa
    return None


def get(percorso, parametri=None, timeout=60, tentativi=TENTATIVI):
    """JSON della richiesta, None se fallisce. 404 = il simbolo non esiste: niente altri tentativi."""
    if not attivo():
        return None
    q = dict(parametri or {}, api_token=chiave(), fmt="json")
    url = BASE + percorso + "?" + urllib.parse.urlencode(q)
    for n in range(tentativi):
        try:
            CHIAMATE["n"] += 1
            req = urllib.request.Request(url, headers={"User-Agent": "cot-radar/eodhd"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                js = json.load(r)
            time.sleep(PAUSA)
            return js
        except urllib.error.HTTPError as e:
            CHIAMATE["errori"] += 1
            if e.code in (401, 402, 403, 404):         # chiave/piano/simbolo: riprovare non serve
                log.info("EODHD %s: HTTP %s", percorso.split("?")[0], e.code)
                return None
            log.warning("EODHD %s: HTTP %s (tentativo %d/%d)", percorso, e.code, n + 1, tentativi)
        except Exception as e:                         # rete, risposta non JSON...
            CHIAMATE["errori"] += 1
            log.warning("EODHD %s: %s (tentativo %d/%d)", percorso, type(e).__name__, n + 1, tentativi)
        if n + 1 < tentativi:
            time.sleep(2 * (3 ** n))
    return None


def serie(sym, dal, periodo="d"):
    """[(data, prezzo RETTIFICATO per dividendi e frazionamenti)] dal giorno `dal`; periodo "d" o "m" (mensile)."""
    js = get("eod/" + sym, {"from": dal, "period": periodo})
    if not isinstance(js, list):
        return None
    out = {}
    for x in js:
        v = x.get("adjusted_close") or x.get("close")
        if x.get("date") and v and v > 0:
            out[x["date"][:7] if periodo == "m" else x["date"]] = round(float(v), 6)
    return sorted(out.items()) or None


def scarica_azione(t, intervallo="1d", periodo="2y"):
    """Stesso formato di azioni.scarica (Yahoo): ({meta}, [(data, prezzo)]) oppure None.
    intervallo "1d" (periodo "5d" o "2y") oppure "1mo" (periodo "max" = tutto lo storico mensile)."""
    sym = simbolo(t)
    if not sym:
        return None
    if intervallo == "1mo":
        pts = serie(sym, "1970-01-01", "m")
    else:
        giorni = 10 if periodo == "5d" else 740           # 5 giorni di borsa ~ 10 di calendario; 2 anni ~ 740
        pts = serie(sym, (date.today() - timedelta(days=giorni)).isoformat())
    if not pts:
        return None
    borsa = sym.rsplit(".", 1)[1]
    meta = {"valuta": VALUTA.get(borsa), "fonte": "eodhd"}   # nome e borsa restano quelli gia' salvati
    return meta, pts


def scarica_etf(t):
    """Per portafogli.prezzi(): tutto lo storico giornaliero rettificato [(data, prezzo)], None se non coperto."""
    sym = simbolo(t)
    return serie(sym, "1990-01-01") if sym else None


def cerca_eur(isin):
    """ISIN -> simbolo EODHD quotato in EURO (Xetra per primo, poi Francoforte, Parigi, Amsterdam), None se non c'e'."""
    js = get("search/" + isin)
    ordine = ("XETRA", "F", "PA", "AS", "BR", "MC")
    cand = [x for x in js or [] if x.get("Currency") == "EUR" and x.get("Exchange") in ordine]
    cand.sort(key=lambda x: ordine.index(x["Exchange"]))
    return f"{cand[0]['Code']}.{cand[0]['Exchange']}" if cand else None


def ultimo_eur(sym):
    """(data, prezzo di chiusura) dell'ultima seduta del simbolo in euro, None se non disponibile."""
    js = get("eod/" + sym, {"from": (date.today() - timedelta(days=12)).isoformat()})
    if isinstance(js, list) and js and js[-1].get("close"):
        return js[-1]["date"], float(js[-1]["close"])
    return None
