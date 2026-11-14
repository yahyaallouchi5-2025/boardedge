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
# RISERVA nel codice: edizione FMI di ottobre 2026 (24 paesi, PIL 2024-2028 e inflazione 2026-2027), presa dalla
# stessa API. Serve solo se mancano sia il download sia la copia (es. primo giro dopo un blocco del FMI).
RISERVA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paesi_riserva.json")

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


# v7.67 LA BORSA DI OGNI PAESE: ETF quotato a New York (in dollari) che segue l'indice MSCI di quel paese. Serve per
# affiancare all'economia (PIL) l'andamento della borsa e la sua volatilita'. 20 paesi su 24: Ungheria e Rep. Ceca non
# hanno un ETF dedicato, quelli di Egitto e Colombia non sono piu' affidabili (restano senza dato, mai inventato).
# I prezzi arrivano con il giro giornaliero di portafogli.prezzi() (archivio storico/yahoo/, fornitore + riserva).
ETF = {"CHN": "MCHI", "IND": "INDA", "TWN": "EWT", "KOR": "EWY", "IDN": "EIDO", "THA": "THD", "MYS": "EWM",
       "PHL": "EPHE", "BRA": "EWZ", "MEX": "EWW", "CHL": "ECH", "PER": "EPU", "SAU": "KSA", "ARE": "UAE",
       "QAT": "QAT", "KWT": "KWT", "ZAF": "EZA", "TUR": "TUR", "POL": "EPOL", "GRC": "GREK"}
MESE, ANNO_B, MEDIA = 21, 252, 200      # sedute: un mese, un anno, media mobile della tendenza (come nei portafogli)
VECCHIO = 10                            # giorni: oltre, i prezzi sono fermi e la borsa non si mostra


def borsa(pts, oggi=None):
    """Numeri di borsa di un paese da [(data, prezzo)]: {"t": data ultimo prezzo, "m1": rendimento % 1 mese,
    "a1": % 12 mesi, "su": True se il prezzo e' sopra la media a 200 sedute (tendenza al rialzo),
    "vb": volatilita' annua % delle ultime 20 sedute (BREVE), "vl": delle ultime 252 (LUNGA),
    "reg": "calma" | "normale" | "agitata" (volatilita.regime: la breve confrontata con i suoi ultimi 5 anni)}.
    None se la storia e' troppo corta o i prezzi sono fermi. Studio (studi/risultati_volatilita_breve_lunga.txt):
    in regime "agitata" il drawdown tipico del mese dopo e' circa -7%, in "calma" circa -4,5%."""
    from . import volatilita as V
    if not pts or len(pts) < ANNO_B + 2:
        return None
    oggi = oggi or datetime.now().date()
    if (oggi - datetime.strptime(pts[-1][0], "%Y-%m-%d").date()).days > VECCHIO:
        return None
    i = len(pts) - 1
    px = [p[1] for p in pts]
    v20, v252 = V.vol_mobile(pts), V.vol_mobile(pts, ANNO_B)
    reg = V.regime(v20, i)
    return {"t": pts[-1][0], "m1": round((px[i] / px[i - MESE] - 1) * 100, 1), "a1": round((px[i] / px[i - ANNO_B] - 1) * 100, 1),
            "su": px[i] > sum(px[i - MEDIA + 1:i + 1]) / MEDIA,
            "vb": None if v20[i] is None else round(v20[i], 1), "vl": None if v252[i] is None else round(v252[i], 1),
            "reg": reg[0] if reg else None}


def aggiungi_borse(dati, leggi, oggi=None):
    """Aggiunge a ogni riga di dati["paesi"] la chiave "b" (vedi borsa) e "etf" (ticker). leggi(ticker) -> [(data, prezzo)].
    Un paese senza ETF o senza prezzi resta senza "b": la tabella mostra un trattino."""
    if not dati:
        return dati
    n = 0
    for r in dati["paesi"]:
        t = ETF.get(r["iso"])
        if not t:
            continue
        try:
            b = borsa(leggi(t), oggi)
        except Exception as e:
            log.warning("paesi: borsa %s non calcolata (%s)", t, e)
            b = None
        if b:
            r["etf"], r["b"] = t, b
            n += 1
    dati["borse"] = n
    return dati


TENTATIVI = 3                # il FMI a volte risponde lento: 3 prove con attesa crescente (2 s, 6 s) prima della copia


def _scarica(ind, timeout=30):
    """{ISO3: {anno: valore}} di un indicatore FMI. User-Agent dichiarato del progetto. Riprova fino a TENTATIVI."""
    req = urllib.request.Request(API.format(ind=ind), headers={"User-Agent": "cot-radar/paesi",
                                                               "Accept": "application/json"})
    for n in range(TENTATIVI):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)["values"][ind]
        except Exception as e:
            if n == TENTATIVI - 1:
                raise                                  # ultimo tentativo fallito: carica() passa alla copia salvata
            log.info("paesi: FMI %s non risponde (%s %s), nuovo tentativo %d/%d", ind, type(e).__name__,
                     getattr(e, "code", ""), n + 2, TENTATIVI)
            time.sleep(2 * 3 ** n)


def _leggi_copia():
    """Ultima copia scaricata (dati/), altrimenti la riserva nel codice; None se mancano entrambe."""
    for f_ in (COPIA, RISERVA):
        try:
            with open(f_, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            continue
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
            log.warning("paesi: FMI non disponibile (%s %s), uso l'ultima copia", type(e).__name__, getattr(e, "code", ""))
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
