# -*- coding: utf-8 -*-
"""
live.py - v7.1 PREZZI INTRADAY (con il ritardo di borsa, ~15-20 minuti) per i Portafogli. Fonte: EODHD real-time.

FLUSSO
  workflow prezzi-live.yml, ogni 15 minuti nei giorni feriali in orario di borsa (Europa + USA):
    1) simboli in EURO degli strumenti acquistabili (STRUMENTI_UE: ISIN -> Xetra), ricordati da un giro all'altro;
    2) simboli USA usati dal modello (SPY, QQQ, GLD... + Bitcoin) e il cambio EUR/USD;
    3) UNA richiesta real-time per gruppo (fino a 15 simboli), scrive live.json nel ramo "live" (un solo commit).
  La pagina (web/js/33_live.js) legge live.json ogni minuto: prezzi in euro della card "Acquisto diretto" e
  variazione di OGGI del portafoglio nel "mese in corso". Le decisioni del modello restano sulle chiusure (EOD).
CHIAVE: solo EODHD_API_KEY dai Secrets (mai nei file o nei log). Senza chiave non fa nulla.
USO: python -m cot_radar.live <cartella di uscita> [live.json del giro prima, per riusare i simboli]
"""
import json
import os
import sys
import time

from . import eodhd
from . import portafogli as P
from .log import log

GRUPPO = 15                    # simboli per richiesta real-time


def tempo_reale(simboli):
    """{simbolo: {"p", "prev", "t"}} dai simboli EODHD (es. SXR8.XETRA, SPY.US). Un'assenza non ferma gli altri."""
    out = {}
    for i in range(0, len(simboli), GRUPPO):
        gr = simboli[i:i + GRUPPO]
        js = eodhd.get("real-time/" + gr[0], {"s": ",".join(gr[1:])} if len(gr) > 1 else None)
        for x in (js if isinstance(js, list) else [js] if isinstance(js, dict) else []):
            c, p, prev, t = x.get("code"), x.get("close"), x.get("previousClose"), x.get("timestamp")
            if c and isinstance(p, (int, float)) and p > 0:
                out[c] = {"p": round(float(p), 4), "prev": round(float(prev), 4) if isinstance(prev, (int, float)) else None,
                          "t": int(t) if isinstance(t, (int, float)) else None}
    return out


def calcola(prima=None):
    """live.json: {"quando", "ue": {chiave: {...}}, "usa": {ticker: {...}}, "eurusd": {...}, "simboli_ue": {...}}"""
    simboli_ue = dict((prima or {}).get("simboli_ue") or {})
    for k, (_, isin, _) in P.STRUMENTI_UE.items():
        if k == "CASH":
            continue                                   # la liquidita' resta sul conto: nessun prezzo serve
        if not simboli_ue.get(k):
            s = eodhd.cerca_eur(isin)
            if s:
                simboli_ue[k] = s
    usa = sorted({P._ticker(u[0]) for u in P.UNIVERSO} | {P.LIQUIDITA[1]})
    mappa_usa = {eodhd.simbolo(t): t for t in usa if eodhd.simbolo(t)}
    tutti = list(simboli_ue.values()) + list(mappa_usa) + ["EURUSD.FOREX"]
    rt = tempo_reale(tutti)
    return {"quando": int(time.time()), "ritardo_min": 15,
            "ue": {k: rt[s] for k, s in simboli_ue.items() if s in rt},
            "usa": {t: rt[s] for s, t in mappa_usa.items() if s in rt},
            "eurusd": rt.get("EURUSD.FOREX"), "simboli_ue": simboli_ue}


def main(argv):
    if not eodhd.attivo():
        log.warning("live: manca EODHD_API_KEY, niente prezzi intraday")
        return 0
    out = argv[1] if len(argv) > 1 else "."
    prima = None
    if len(argv) > 2 and os.path.exists(argv[2]):
        try:
            prima = json.load(open(argv[2], encoding="utf-8"))
        except (OSError, ValueError):
            prima = None
    dati = calcola(prima)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "live.json"), "w", encoding="utf-8") as f:
        json.dump(dati, f, separators=(",", ":"))
    print("live:", len(dati["ue"]), "ETF in euro,", len(dati["usa"]), "USA, cambio", bool(dati["eurusd"]),
          "chiamate", eodhd.CHIAMATE["n"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
