# -*- coding: utf-8 -*-
"""
paesi.py - PAESI EMERGENTI: chi cresce e chi no (v6.72, riquadro della Dashboard)

FONTE: Fondo Monetario Internazionale, World Economic Outlook (API DataMapper, gratuita e senza chiave).
  - NGDP_RPCH = crescita del PIL reale in % sull'anno prima (dati passati + stime e previsioni FMI)
  - PCPIPCH   = inflazione media dell'anno in %
  Il FMI aggiorna le previsioni due volte l'anno (aprile e ottobre): basta scaricarle a ogni giro del sito,
  la chiamata e' una sola per indicatore (l'API restituisce tutti i paesi insieme).

PAESI: i 24 dell'indice MSCI Emerging Markets, lo stesso seguito dall'ETF EEM e dal COT "MSCI Emergenti"
  (cosi' il riquadro parla degli stessi paesi in cui si investe con quell'indice).

COSA CALCOLA per ogni paese (anno = anno solare in corso):
  pil      crescita del PIL dell'anno in corso (stima FMI finche' l'anno non e' chiuso)
  prec     crescita dell'anno prima
  prox     previsione FMI per l'anno prossimo
  tend     prox - pil: >0 = l'economia ACCELERA, <0 = RALLENTA
  inf      inflazione dell'anno in corso
  stato    "crescita" se pil > 0, "decrescita" se pil <= 0 (PIL che si riduce = recessione)

AGGIORNAMENTO AUTOMATICO: si riscarica a ogni giro del sito (piu' volte al giorno), con 3 tentativi.
SICUREZZA DEI DATI: copia dell'ultimo download in dati/paesi_fmi.json; se il FMI non risponde si usa quella
(con la sua data), se manca anche la copia il riquadro sparisce. Mai bloccante per il resto del sito.
"""
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

from .config import ROOT
from .log import log

API = "https://www.imf.org/external/datamapper/api/v1/{ind}"
COPIA = os.path.join(ROOT, "dati", "paesi_fmi.json")

# (codice ISO3 del FMI, nome in italiano, area) - indice MSCI Emerging Markets
PAESI = [
    ("CHN", "Cina", "Asia"), ("IND", "India", "Asia"), ("TWN", "Taiwan", "Asia"), ("KOR", "Corea del Sud", "Asia"),
    ("IDN", "Indonesia", "Asia"), ("THA", "Thailandia", "Asia"), ("MYS", "Malesia", "Asia"),
    ("PHL", "Filippine", "Asia"),
    ("BRA", "Brasile", "America Latina"), ("MEX", "Messico", "America Latina"), ("CHL", "Cile", "America Latina"),
    ("COL", "Colombia", "America Latina"), ("PER", "Perù", "America Latina"),
    ("SAU", "Arabia Saudita", "Golfo"), ("ARE", "Emirati Arabi", "Golfo"),
    ("QAT", "Qatar", "Golfo"), ("KWT", "Kuwait", "Golfo"),
    ("ZAF", "Sudafrica", "Africa"), ("EGY", "Egitto", "Africa"),
    ("TUR", "Turchia", "Europa"), ("POL", "Polonia", "Europa"), ("HUN", "Ungheria", "Europa"),
    ("CZE", "Rep. Ceca", "Europa"), ("GRC", "Grecia", "Europa"),
]


TENTATIVI = 3                # il FMI a volte risponde lento: 3 prove con attesa crescente (2 s, 6 s) prima della copia


def _scarica(ind, timeout=30):
    """{ISO3: {anno: valore}} di un indicatore FMI. User-Agent dichiarato del progetto. Riprova fino a TENTATIVI."""
    req = urllib.request.Request(API.format(ind=ind), headers={"User-Agent": "cot-radar/paesi"})
    for n in range(TENTATIVI):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)["values"][ind]
        except Exception as e:
            if n == TENTATIVI - 1:
                raise                                  # ultimo tentativo fallito: carica() passa alla copia salvata
            log.info("paesi: FMI %s non risponde (%s), nuovo tentativo %d/%d", ind, type(e).__name__, n + 2, TENTATIVI)
            time.sleep(2 * 3 ** n)


def _leggi_copia():
    try:
        with open(COPIA, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def calcola(pil, inf, anno):
    """Righe del riquadro, dalla crescita piu' alta alla piu' bassa (solo paesi con i tre valori del PIL)."""
    righe = []
    for iso, nome, area in PAESI:
        p, i = pil.get(iso) or {}, inf.get(iso) or {}
        cur, prec, prox = p.get(str(anno)), p.get(str(anno - 1)), p.get(str(anno + 1))
        if cur is None or prox is None:
            continue                                   # paese senza stima FMI: meglio non mostrarlo che inventare
        righe.append({"iso": iso, "nome": nome, "area": area, "pil": round(cur, 1),
                      "prec": None if prec is None else round(prec, 1), "prox": round(prox, 1),
                      "tend": round(prox - cur, 1), "inf": None if i.get(str(anno)) is None else round(i[str(anno)], 1),
                      "stato": "crescita" if cur > 0 else "decrescita"})
    return sorted(righe, key=lambda r: -r["pil"])


def carica(scarica=True, adesso=None):
    """Dati per la pagina: {anno, agg, fonte, copia, paesi:[...]} oppure None. scarica=False (demo/test): solo copia."""
    adesso = adesso or datetime.now(timezone.utc)
    grezzi = None
    if scarica:
        try:
            grezzi = {"pil": _scarica("NGDP_RPCH"), "inf": _scarica("PCPIPCH"),
                      "agg": adesso.strftime("%Y-%m-%d")}
            if sum(1 for iso, _, _ in PAESI if iso in grezzi["pil"]) < 20:
                raise ValueError("risposta FMI incompleta")
            os.makedirs(os.path.dirname(COPIA), exist_ok=True)
            with open(COPIA, "w", encoding="utf-8") as f:
                json.dump(grezzi, f, separators=(",", ":"))
        except Exception as e:                         # rete o FMI giu': si ripiega sulla copia
            log.warning("paesi: FMI non disponibile (%s), uso l'ultima copia", type(e).__name__)
            grezzi = None
    copia = grezzi is None
    if copia:
        grezzi = _leggi_copia()
    if not grezzi:
        return None
    righe = calcola(grezzi["pil"], grezzi["inf"], adesso.year)
    if not righe:
        return None
    return {"anno": adesso.year, "agg": grezzi.get("agg"), "copia": copia, "fonte": "FMI World Economic Outlook",
            "paesi": righe}
