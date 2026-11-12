# -*- coding: utf-8 -*-
"""
dividendi.py - v7.22 DIVIDENDI DI OGNI TITOLO (scheda Azionario), dall'API dividendi di EODHD (inclusa nel piano:
verificata con prova-eodhd il 07/11/2026). Mai bloccante per la scheda.

FLUSSO (giro USA della sera, dopo le notizie):
  per ogni titolo coperto da EODHD (USA, Xetra, Parigi, Amsterdam...) con il file vecchio di oltre 7 giorni:
  una richiesta "div/<SIMBOLO>?from=<11 anni fa>" -> pubblico/dividendi/<TICKER>.json
  {"t", "v", "agg", "valuta", "u12" (somma degli ultimi "freq" stacchi gia' avvenuti), "freq" (pagamenti l'anno, media degli ultimi 2 anni),
   "cagr5" (crescita annua del dividendo in 5 anni, %), "anni" (anni solari consecutivi con dividendo),
   "storia": [[anno, totale]] ultimi 10 anni (l'anno in corso e' parziale), "ultimi": [{"d" stacco, "pag", "v"}]}
  Il rendimento da dividendo (u12 / prezzo) lo calcola azioni.pubblica con il prezzo del giorno (colonna "Div.").
Milano e Asia non sono coperti da EODHD: niente file, la scheda non mostra il riquadro.
Importi "value" di EODHD = rettificati per i frazionamenti (cosi' la storia e' confrontabile).
"""
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone

from . import azioni as A
from . import eodhd

log = logging.getLogger(__name__)
VERSIONE = 3              # v7.53: storia di 31 anni e anni di AUMENTI (rifare tutti i file). v7.22b: u12 senza stacchi futuri
RIFAI_GIORNI = 7               # i dividendi cambiano di rado: una volta a settimana basta
TEMPO_MAX = 600                # secondi massimi per giro: il resto al giro dopo
ANNI = 31                  # v7.53 (prima 11): servono 25+ anni per riconoscere gli "aristocratici" del dividendo


def riassunto(js, oggi):
    """Risposta EODHD -> riassunto compatto (vedi docstring del modulo). None se la risposta non e' una lista."""
    if not isinstance(js, list):
        return None
    pag = []
    for x in js:
        try:
            v = float(x.get("value"))
            d = str(x.get("date") or "")[:10]
            date.fromisoformat(d)
        except (TypeError, ValueError):
            continue
        if v > 0:
            pag.append({"d": d, "pag": (x.get("paymentDate") or "")[:10] or None, "v": round(v, 4), "val": x.get("currency")})
    pag.sort(key=lambda p: p["d"])
    # v7.22b solo stacchi gia' avvenuti (EODHD elenca anche quelli annunciati, con data futura)
    oggi_s = oggi.isoformat()
    fatti = [p for p in pag if p["d"] <= oggi_s]
    due_anni, max_eta = (oggi - timedelta(days=730)).isoformat(), (oggi - timedelta(days=400)).isoformat()
    freq = round(len([p for p in fatti if p["d"] > due_anni]) / 2)   # pagamenti l'anno, media di 2 anni
    # ultimi 12 mesi = gli ultimi "freq" stacchi (non una finestra di giorni: con le date che slittano di qualche
    # giorno una finestra fissa ne conta 3 o 5 invece di 4); scartati quelli di oltre 400 giorni fa
    recenti = [p for p in fatti[-freq:] if p["d"] > max_eta] if freq else []
    per_anno = {}
    for p in pag:
        per_anno[int(p["d"][:4])] = per_anno.get(int(p["d"][:4]), 0) + p["v"]
    a = oggi.year - 1                                     # ultimo anno solare completo
    cagr = None
    if per_anno.get(a) and per_anno.get(a - 5):
        cagr = round(((per_anno[a] / per_anno[a - 5]) ** (1 / 5) - 1) * 100, 1)
    anni = 0
    while per_anno.get(a - anni):
        anni += 1
    # v7.53 ANNI DI AUMENTI CONSECUTIVI (idea: "Dividend Aristocrats", Lichtenfeld): la rata TIPICA dell'anno (mediana
    # dei pagamenti, cosi' un pagamento che slitta a gennaio o un dividendo straordinario non falsano il conto) deve
    # essere piu' alta di quella dell'anno prima. Anno in corso escluso (parziale).
    rate = {}
    for p in pag:
        rate.setdefault(int(p["d"][:4]), []).append(p["v"])
    tipica = {y: sorted(v)[len(v) // 2] if len(v) % 2 else sum(sorted(v)[len(v) // 2 - 1:len(v) // 2 + 1]) / 2
              for y, v in rate.items()}
    aumenti = 0
    while tipica.get(a - aumenti) and tipica.get(a - aumenti - 1) and \
            tipica[a - aumenti] > tipica[a - aumenti - 1] * 1.0005:
        aumenti += 1
    return {"valuta": next((p["val"] for p in reversed(pag) if p["val"]), None),
            "u12": round(sum(p["v"] for p in recenti), 4), "freq": freq, "cagr5": cagr, "anni": anni, "aumenti": aumenti,
            "storia": [[y, round(per_anno.get(y, 0), 4)] for y in range(oggi.year - 9, oggi.year + 1)],
            "ultimi": [{k: p[k] for k in ("d", "pag", "v")} for p in pag[-8:]][::-1]}


def file_titolo(cartella, t):
    return os.path.join(cartella, "pubblico", "dividendi", A._nome_file(t) + ".json")


def rendimento(cartella, t, prezzo, valuta=None):
    """Rendimento da dividendo (%) degli ultimi 12 mesi al prezzo dato; None senza file o con valute diverse."""
    d = A._leggi(file_titolo(cartella, t))
    if not d or not prezzo:
        return None
    if valuta and d.get("valuta") and d["valuta"] != valuta:
        return None
    r = round(d.get("u12", 0) / prezzo * 100, 2)
    return r if r <= 25 else None                     # v7.23 oltre il 25% e' quasi sempre un errore di unita' (pence)


def aggiorna(cartella, el=None, oggi=None):
    """Aggiorna pubblico/dividendi/ per i titoli coperti da EODHD. Restituisce {"aggiornati", "saltati"}."""
    if not eodhd.attivo():
        return {"aggiornati": 0, "saltati": 0}
    oggi = oggi or date.today()
    elenco = el if el is not None else A.elenco()
    adesso, inizio, fatti, saltati = datetime.now(timezone.utc), time.time(), 0, 0
    dal = date(oggi.year - ANNI, 1, 1).isoformat()
    for x in elenco:
        t = x["t"]
        sym = eodhd.simbolo(t)
        if not sym:
            continue
        f = file_titolo(cartella, t)
        vecchio = A._leggi(f) or {}
        try:
            fresco = adesso - datetime.fromisoformat(vecchio.get("agg", "")) < timedelta(days=RIFAI_GIORNI)
        except ValueError:
            fresco = False
        if fresco and vecchio.get("v") == VERSIONE:
            saltati += 1
            continue
        if time.time() - inizio > TEMPO_MAX:
            log.warning("dividendi: tempo massimo raggiunto, gli altri titoli al prossimo giro")
            break
        js = eodhd.get("div/" + sym, {"from": dal}, timeout=30, tentativi=2)
        r = riassunto(js, oggi)
        if r is None:                               # EODHD non risponde: resta il file della volta prima
            continue
        A._scrivi(f, dict({"t": t, "v": VERSIONE, "agg": adesso.isoformat(timespec="minutes")}, **r))
        fatti += 1
    log.warning("dividendi: %d aggiornati, %d gia' freschi", fatti, saltati)
    return {"aggiornati": fatti, "saltati": saltati}
