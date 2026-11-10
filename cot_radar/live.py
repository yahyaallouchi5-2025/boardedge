# -*- coding: utf-8 -*-
"""
live.py - v7.1 PREZZI INTRADAY (con il ritardo di borsa, ~15-20 minuti) per i Portafogli. Fonte: EODHD real-time.

FLUSSO
  workflow prezzi-live-continuo.yml (v7.24): 4 partenze al giorno, ognuna un CICLO fino a ~6 ore che ogni 15 minuti,
  se una borsa e' aperta, scarica e pubblica (prima: un giro ogni 15 minuti, ma GitHub ne avviava pochissimi):
    1) simboli in EURO degli strumenti acquistabili (STRUMENTI_UE: ISIN -> Xetra), ricordati da un giro all'altro;
    2) simboli USA usati dal modello (SPY, QQQ, GLD... + Bitcoin) e il cambio EUR/USD;
    3) UNA richiesta real-time per gruppo (fino a 15 simboli), scrive live.json nel ramo "live" (un solo commit).
  La pagina (web/js/33_live.js) legge live.json ogni minuto: prezzi in euro della card "Acquisto diretto" e
  variazione di OGGI del portafoglio nel "mese in corso". Le decisioni del modello restano sulle chiusure (EOD).
CHIAVE: solo EODHD_API_KEY dai Secrets (mai nei file o nei log). Senza chiave non fa nulla.
v7.22 AZIONARIO: nello stesso giro anche i titoli dell'Azionario coperti da EODHD (USA ed Europa) MENTRE LA LORO BORSA
  E' APERTA (+20 minuti per il ritardo), nel file separato live_az.json {"quando", "ritardo_min", "p": {ticker:
  [prezzo, chiusura di ieri, timestamp]}} letto solo dalla scheda Azionario. I titoli di borse chiuse tengono il valore
  del giro prima (stesso giorno). Circa 20.000 chiamate EODHD al giorno (1 per titolo per giro), dentro il piano.
USO: python -m cot_radar.live <cartella di uscita> [live.json del giro prima, per riusare i simboli]
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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


# borse aperte (ora locale) per i titoli dell'Azionario: (fuso, apertura, chiusura + ritardo dei prezzi)
ORARI = {"US": ("America/New_York", "09:30", "16:20"), "EU": ("Europe/Berlin", "09:00", "17:50"),
         "TO": ("America/Toronto", "09:30", "16:20"), "AU": ("Australia/Sydney", "10:00", "16:20")}   # v7.23
RAW_AZ = "https://raw.githubusercontent.com/{repo}/live/live_az.json"


def aperta(borsa, adesso=None):
    """True se la borsa ("US" o "EU") e' aperta adesso (giorni feriali, festivi esclusi solo dal fatto che EODHD non
    da' prezzi nuovi: il valore resta quello del giorno prima)."""
    fuso, da, a = ORARI[borsa]
    loc = (adesso or datetime.now(timezone.utc)).astimezone(ZoneInfo(fuso))
    return loc.weekday() < 5 and da <= loc.strftime("%H:%M") <= a


def azioni_live(prima=None, adesso=None):
    """live_az.json: prezzi dei titoli dell'Azionario delle borse aperte (+ quelli del giro prima dello stesso giorno)."""
    from . import azioni as A
    adesso = adesso or datetime.now(timezone.utc)
    simboli = {}
    for x in A.elenco():
        s = eodhd.simbolo(x["t"])
        if not s or s.endswith(".INDX"):
            continue
        borsa = s.rsplit(".", 1)[1] if s.endswith((".US", ".TO", ".AU")) else "EU"
        if aperta(borsa, adesso):
            simboli[s] = x["t"]
    rt = tempo_reale(list(simboli)) if simboli else {}
    oggi = adesso.date().isoformat()
    p = {t: v for t, v in ((prima or {}).get("p") or {}).items()
         if v and v[2] and datetime.fromtimestamp(v[2], timezone.utc).date().isoformat() == oggi}
    for s, t in simboli.items():
        if s in rt:
            v = rt[s]
            p[t] = [v["p"], v["prev"], v["t"]]
    return {"quando": int(time.time()), "ritardo_min": 15, "p": p}


def _prima_az():
    """live_az.json del giro prima (dal ramo "live"), per tenere i titoli delle borse gia' chiuse."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        return None
    try:
        req = urllib.request.Request(RAW_AZ.format(repo=repo), headers={"User-Agent": "cot-radar/live"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def qualche_borsa_aperta(adesso=None):
    """v7.24 True se almeno una borsa di ORARI e' aperta (il ciclo del workflow scarica solo allora)."""
    return any(aperta(b, adesso) for b in ORARI)


def main(argv):
    if "--aperta" in argv:                         # v7.24 per il ciclo del workflow: codice 0 = almeno una borsa aperta
        return 0 if qualche_borsa_aperta() else 1
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
    try:                                           # v7.22 titoli dell'Azionario: mai bloccante per i Portafogli
        az = azioni_live(_prima_az())
        with open(os.path.join(out, "live_az.json"), "w", encoding="utf-8") as f:
            json.dump(az, f, separators=(",", ":"))
        print("live azioni:", len(az["p"]), "titoli")
    except Exception as e:
        log.warning("live: titoli dell'Azionario non aggiornati (%s)", e)
    print("live:", len(dati["ue"]), "ETF in euro,", len(dati["usa"]), "USA, cambio", bool(dati["eurusd"]),
          "chiamate", eodhd.CHIAMATE["n"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
