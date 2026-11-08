# -*- coding: utf-8 -*-
"""
notizie_az.py - v7.15 ULTIME NOTIZIE DI OGNI TITOLO (scheda Azionario), dall'API notizie di EODHD (inclusa nel piano:
verificata con prova-eodhd il 07/11/2026). Solo titolo, data, fonte, link e TONO stimato da EODHD (sentiment):
nessun testo dell'articolo viene copiato (diritto d'autore), chi vuole legge l'articolo sulla fonte.

FLUSSO (giro USA della sera, dopo i profili; mai bloccante per la scheda):
  per ogni titolo coperto da EODHD (USA, Xetra, Parigi, Amsterdam...) con il file vecchio di oltre 20 ore:
  una richiesta "news?s=<SIMBOLO>&limit=5" -> pubblico/notizie/<TICKER>.json
  {"t", "agg", "n": [{"d": "AAAA-MM-GG", "titolo", "link", "fonte", "tono": -1..+1 o None}]}
  Solo notizie degli ultimi GIORNI_MAX giorni. Tempo massimo TEMPO_MAX: il resto al giro dopo.
Milano e Asia non sono coperti da EODHD: la scheda non mostra il riquadro.
"""
import logging
import os
import time
import urllib.parse
from datetime import date, datetime, timedelta, timezone

from . import azioni as A
from . import eodhd

log = logging.getLogger(__name__)
LIMITE = 5                     # notizie per titolo
GIORNI_MAX = 30                # piu' vecchie di cosi' non interessano
RIFAI_ORE = 20                 # un file piu' recente di cosi' non si richiede di nuovo
TEMPO_MAX = 600                # secondi massimi per giro


def _fonte(link):
    """'https://www.reuters.com/...' -> 'reuters.com' (vuoto se il link non si legge)."""
    try:
        h = urllib.parse.urlparse(link or "").hostname or ""
        return h[4:] if h.startswith("www.") else h
    except ValueError:
        return ""


def pulisci(js, oggi):
    """Risposta EODHD -> lista compatta delle notizie (piu' recenti prima), senza testi degli articoli."""
    limite = (oggi - timedelta(days=GIORNI_MAX)).isoformat()
    out, visti = [], set()
    for x in js if isinstance(js, list) else []:
        titolo = (x.get("title") or "").strip()
        d = (x.get("date") or "")[:10]
        link = x.get("link") or ""
        if not titolo or not d or d < limite or not link.startswith("http") or titolo.lower() in visti:
            continue
        visti.add(titolo.lower())
        pol = (x.get("sentiment") or {}).get("polarity")
        out.append({"d": d, "titolo": titolo[:220], "link": link, "fonte": _fonte(link),
                    "tono": round(float(pol), 2) if isinstance(pol, (int, float)) else None})
    return sorted(out, key=lambda n: n["d"], reverse=True)[:LIMITE]


def aggiorna(cartella, el=None, oggi=None):
    """Aggiorna pubblico/notizie/ per i titoli coperti da EODHD. Restituisce {"aggiornati", "saltati"}."""
    if not eodhd.attivo():
        return {"aggiornati": 0, "saltati": 0}
    oggi = oggi or date.today()
    titoli = [x["t"] for x in (el if el is not None else A.elenco())]
    adesso, inizio, fatti, saltati = datetime.now(timezone.utc), time.time(), 0, 0
    for t in titoli:
        sym = eodhd.simbolo(t)
        if not sym:
            continue
        f = os.path.join(cartella, "pubblico", "notizie", A._nome_file(t) + ".json")
        vecchio = A._leggi(f) or {}
        try:
            fresco = adesso - datetime.fromisoformat(vecchio.get("agg", "")) < timedelta(hours=RIFAI_ORE)
        except ValueError:
            fresco = False
        if fresco:
            saltati += 1
            continue
        if time.time() - inizio > TEMPO_MAX:
            log.warning("notizie: tempo massimo raggiunto, gli altri titoli al prossimo giro")
            break
        js = eodhd.get("news", {"s": sym, "limit": 10, "offset": 0}, timeout=30, tentativi=2)
        if js is None:                         # EODHD non risponde: resta il file di ieri
            continue
        A._scrivi(f, {"t": t, "agg": adesso.isoformat(timespec="minutes"), "n": pulisci(js, oggi)})
        fatti += 1
    log.warning("notizie dei titoli: %d aggiornate, %d gia' fresche", fatti, saltati)
    return {"aggiornati": fatti, "saltati": saltati}
