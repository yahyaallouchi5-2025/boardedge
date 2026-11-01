# -*- coding: utf-8 -*-
"""
carry.py - CARRY TRADE (v6.61): i tassi d'interesse delle valute, il carry di ogni coppia e lo studio storico.

IDEA FINANZIARIA
  Chi compra una valuta con tasso alto e vende una valuta con tasso basso incassa ogni giorno la differenza
  (lo "swap" del broker). Carry di una coppia BASE/QUOTATA comprata = tasso BASE - tasso QUOTATA (% annuo).
  Positivo = il BUY incassa, negativo = il BUY paga (e il SELL incassa). Il rischio tipico: guadagno lento,
  perdite rapide nei momenti di panico (2008, agosto 2024) quando tutti chiudono insieme.

DATI (FRED, gratuiti, MENSILI)
  Per ogni valuta una lista di serie in ordine di preferenza: tasso interbancario a 3 mesi dell'OECD (IR3TIB01..),
  poi il tasso a brevissimo (IRSTCI01..), per il dollaro anche i T-bill a 3 mesi (TB3MS). Per la storia si usa la
  prima serie e i mesi che le mancano si prendono dalle altre; il valore di OGGI e' l'ultimo mese disponibile.
  I dati OECD arrivano con circa 1-2 mesi di ritardo: per il carry va bene, i tassi cambiano lentamente.

ARCHIVIO: storico/tassi.json (ramo "storico" su GitHub). Un archivio a parte perche' i tassi possono essere
  NEGATIVI (franco, euro e yen tra il 2015 e il 2022) e l'archivio dei prezzi scarta i valori <= 0.
  Si scarica al massimo una volta al giorno; una serie che non arriva tiene i valori gia' salvati.
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from .log import log

CARTELLA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storico")
FILE = "tassi.json"
DAL = "1990-01-01"

# valuta -> serie FRED candidate (la prima e' la preferita). Le valute senza dati mostrano "n/d".
CANDIDATI = {
    "USD": ["IR3TIB01USM156N", "TB3MS"],
    "EUR": ["IR3TIB01EZM156N", "IRSTCI01EZM156N"],
    "JPY": ["IR3TIB01JPM156N", "IRSTCI01JPM156N"],
    "GBP": ["IR3TIB01GBM156N", "IRSTCI01GBM156N"],
    "CHF": ["IR3TIB01CHM156N", "IRSTCI01CHM156N"],
    "CAD": ["IR3TIB01CAM156N", "IRSTCI01CAM156N"],
    "AUD": ["IR3TIB01AUM156N", "IRSTCI01AUM156N"],
    "NZD": ["IR3TIB01NZM156N", "IRSTCI01NZM156N"],
    "MXN": ["IR3TIB01MXM156N", "IRSTCI01MXM156N"],
    "ZAR": ["IR3TIB01ZAM156N", "IRSTCI01ZAM156N"],
    "BRL": ["IRSTCI01BRM156N"],
}
VECCHIO_GIORNI = 150     # ultimo dato piu' vecchio di ~5 mesi: la valuta e' segnata "dato vecchio"


# --------------------------------------------------------------------------- archivio
def leggi(cartella=CARTELLA):
    """Archivio salvato: {"scaricato": data, "serie": {sid: [[data, valore], ...]}, "errori": {sid: testo}}."""
    try:
        with open(os.path.join(cartella, FILE), encoding="utf-8") as f:
            a = json.load(f)
        if isinstance(a.get("serie"), dict):
            return a
    except (OSError, ValueError):
        pass
    return {"scaricato": None, "serie": {}, "errori": {}}


def aggiorna_tassi(scarica, cartella=CARTELLA, oggi=None, forza=False):
    """Scarica (al massimo una volta al giorno) tutte le serie candidate e aggiorna storico/tassi.json.
    scarica(sid, inizio) -> [[data, valore], ...] (fonti.get_fred). Ogni serie e' indipendente: se una non
    arriva, resta la copia salvata. Restituisce l'archivio aggiornato."""
    oggi = (oggi or date.today()).isoformat()
    a = leggi(cartella)
    if a.get("scaricato") == oggi and a["serie"] and not forza:
        return a
    tutte = [sid for lista in CANDIDATI.values() for sid in lista]

    def una(sid):
        try:
            pts = scarica(sid, DAL)
            pts = [[d, round(float(v), 4)] for d, v in pts if v is not None]
            return sid, pts, None
        except Exception as e:                     # serie inesistente, interrotta o rete giu': si va avanti
            return sid, None, (str(e) or type(e).__name__)[:160]

    with ThreadPoolExecutor(max_workers=4) as ex:
        risultati = list(ex.map(una, tutte))
    errori, nuove = {}, 0
    for sid, pts, err in risultati:
        if pts and len(pts) >= 12:
            vecchi = a["serie"].get(sid) or []
            if len(pts) >= 0.9 * len(vecchi):      # un download molto piu' corto del salvato e' sospetto
                a["serie"][sid] = pts
                nuove += 1
            else:
                errori[sid] = f"download sospetto: {len(pts)} punti contro {len(vecchi)} salvati"
        else:
            errori[sid] = err or "troppo pochi dati"
    a["scaricato"], a["errori"] = oggi, errori
    try:
        os.makedirs(cartella, exist_ok=True)
        with open(os.path.join(cartella, FILE + ".tmp"), "w", encoding="utf-8") as f:
            json.dump(a, f, separators=(",", ":"))
        os.replace(os.path.join(cartella, FILE + ".tmp"), os.path.join(cartella, FILE))
    except OSError as e:
        log.warning("carry: archivio dei tassi non salvato (%s)", e)
    log.info("carry: %d serie di tassi aggiornate, %d non disponibili%s", nuove, len(errori),
             (" (" + ", ".join(sorted(errori)) + ")") if errori else "")
    return a


# --------------------------------------------------------------------------- tassi mensili per valuta
def mensili(archivio):
    """{valuta: {"AAAA-MM": tasso %}} unendo le candidate: la preferita vince, le altre riempiono i buchi.
    + {valuta: {"v", "mese", "fonte", "vecchio"}} con l'ultimo valore disponibile."""
    serie, oggi = archivio.get("serie") or {}, date.today()
    per_val, ultimo = {}, {}
    for val, lista in CANDIDATI.items():
        m, fonte_ult, mese_ult = {}, None, ""
        for sid in reversed(lista):                # dalla meno preferita alla preferita: la preferita sovrascrive
            for d, v in serie.get(sid) or []:
                m[d[:7]] = v
        if not m:
            continue
        mese_ult = max(m)
        for sid in lista:                          # fonte del valore piu' recente = prima candidata che ce l'ha
            if any(d[:7] == mese_ult for d, _ in serie.get(sid) or []):
                fonte_ult = sid
                break
        per_val[val] = m
        eta = (oggi - date.fromisoformat(mese_ult + "-15")).days
        ultimo[val] = {"v": round(m[mese_ult], 2), "mese": mese_ult, "fonte": fonte_ult,
                       "vecchio": eta > VECCHIO_GIORNI}
    return per_val, ultimo
