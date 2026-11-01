# -*- coding: utf-8 -*-
"""
scenari.py - SCENARI DEGLI EVENTI AD ALTO IMPATTO (v6.73): cosa aspettarsi da ogni notizia della Dashboard.

Per ogni tipo di evento dell'agenda (agenda.SERIE) la pagina mostra, al passaggio del mouse o con un tocco:
  1. LETTURA   cosa misura e come si legge per la valuta interessata:
               dato SOPRA il precedente -> valuta più forte o più debole (e perche'), e viceversa.
               Regole classiche dei mercati valutari, uguali per ogni paese:
                 lavoro/crescita/consumi più alti  -> economia solida, banca centrale meno accomodante -> valuta FORTE
                 inflazione più alta               -> banca centrale più restrittiva (tassi alti)  -> valuta FORTE
                 banca centrale che alza / "falco"  -> valuta FORTE; che taglia / "colomba" -> valuta DEBOLE
  2. PRECEDENTE l'ultimo valore pubblicato, da FRED (solo dati USA e tassi Fed/BCE: per gli altri paesi FRED non ha
               serie aggiornate in tempo). Confronto con il PRECEDENTE, non con le attese degli analisti: il consensus
               non e' disponibile gratis (lo dice anche il fumetto della pagina).
  3. REAZIONE  quanto si muove di solito il mercato: date storiche di uscita del dato (FRED, "release dates") e,
               per ognuna, lo z-score del tasso USA a 2 anni nel giorno dell'uscita (notizie.sorpresa_mercato, la
               stessa misura del motore notizie). quota = uscite con |z| >= 1 (mossa più ampia di una giornata
               normale). Su una giornata qualsiasi |z| >= 1 capita circa 1 volta su 3, quindi:
                 quota >= 50% = reazione FORTE, 30-50% = MEDIA, sotto 30% = DEBOLE (come una giornata normale).
               Solo eventi USA (il tasso 2 anni e lo storico delle date ci sono solo per gli USA).

SICUREZZA: tutto isolato; se FRED non risponde si usa l'ultima copia (dati/scenari.json). La chiave FRED resta
nella variabile d'ambiente FRED_API_KEY (Secret di GitHub): mai scritta nel codice, nei log o nella pagina.
"""
import json
import os
import statistics
import urllib.parse
from datetime import date, timedelta

from .config import ROOT
from .log import log

COPIA = os.path.join(ROOT, "dati", "scenari.json")
DATE_API = "https://api.stlouisfed.org/fred/release/dates"
ULTIME = 24                   # uscite più recenti usate per la reazione tipica (circa 2 anni per i dati mensili)
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
        "novembre", "dicembre"]

# --------------------------------------------------------------------------- 1. lettura per famiglia
# famiglia -> (alto, basso) con {v} = valuta. Testi brevi: stanno in un fumetto.
REGOLE = {
    "lavoro": ("economia solida, la banca centrale taglia meno i tassi", "economia che rallenta, più tagli dei tassi"),
    "inflazione": ("prezzi in salita, la banca centrale tiene i tassi alti", "prezzi in calo, più spazio per tagliare i tassi"),
    "crescita": ("economia più forte, tassi alti più a lungo", "economia più debole, tassi verso il basso"),
    "banca": ("tassi alzati o tono restrittivo (falco)", "tassi tagliati o tono accomodante (colomba)"),
}
# codice agenda -> (cosa misura, famiglia)
COSA = {
    "us-nfp": ("Nuovi posti di lavoro nel mese", "lavoro"),
    "us-cpi": ("Inflazione dei prezzi al consumo", "inflazione"),
    "us-pce": ("Inflazione PCE, la misura preferita dalla Fed", "inflazione"),
    "us-ppi": ("Prezzi alla produzione: anticipano l'inflazione", "inflazione"),
    "us-gdp": ("Crescita dell'economia (PIL)", "crescita"),
    "us-retail-sales": ("Spesa dei consumatori nei negozi", "crescita"),
    "us-ism-manufacturing": ("Fiducia delle imprese industriali (sopra 50 = espansione)", "crescita"),
    "us-ism-services": ("Fiducia delle imprese dei servizi (sopra 50 = espansione)", "crescita"),
    "eu-cpi": ("Inflazione dell'Eurozona (prima stima)", "inflazione"),
    "gb-cpi": ("Inflazione del Regno Unito", "inflazione"),
    "ca-cpi": ("Inflazione del Canada", "inflazione"),
    "au-cpi": ("Inflazione dell'Australia", "inflazione"),
    "fomc": ("Decisione sui tassi della Fed", "banca"), "ecb": ("Decisione sui tassi della BCE", "banca"),
    "boe": ("Decisione sui tassi della Bank of England", "banca"), "boj": ("Decisione sui tassi della Bank of Japan", "banca"),
    "boc": ("Decisione sui tassi della Bank of Canada", "banca"), "rba": ("Decisione sui tassi della RBA", "banca"),
    "rbnz": ("Decisione sui tassi della RBNZ", "banca"), "snb": ("Decisione sui tassi della SNB", "banca"),
}

# --------------------------------------------------------------------------- 2-3. dati FRED (solo USA + tassi)
# codice -> (serie FRED, trasformazione, id della "release" FRED per lo storico delle uscite o None)
#   diff = variazione sul mese prima (migliaia), yoy = % sull'anno prima, mom = % sul mese prima, livello = valore
FRED = {
    "us-nfp": ("PAYEMS", "diff", 50), "us-cpi": ("CPIAUCSL", "yoy", 10), "us-pce": ("PCEPI", "yoy", 54),
    "us-ppi": ("PPIFIS", "yoy", 46), "us-gdp": ("A191RL1Q225SBEA", "livello", 53), "us-retail-sales": ("RSAFS", "mom", 9),
    "fomc": ("DFEDTARU", "fed", 101), "ecb": ("ECBDFR", "tasso", None),
}


def _chiave():
    """Chiave FRED dalla variabile d'ambiente (stessa pulizia di fonti.get_fred). Vuota = niente storico."""
    k = os.environ.get("FRED_API_KEY", "").strip().strip('"').strip("'")
    return k.split("=", 1)[1].strip() if k.upper().startswith("FRED_API_KEY=") else k


def _num(v, cifre=1):
    """Numero all'italiana con segno: 3.04 -> '+3,0'."""
    return f"{v:+.{cifre}f}".replace(".", ",")


def precedente(serie, trasf, extra=None):
    """(testo del valore, periodo) dell'ultimo dato pubblicato, oppure None se la serie e' corta."""
    if not serie:
        return None
    d, v = serie[-1]
    a, m = int(d[:4]), int(d[5:7])
    periodo = f"T{(m - 1) // 3 + 1} {a}" if trasf == "livello" else f"{MESI[m - 1]} {a}"
    if trasf == "diff" and len(serie) >= 2:
        return f"{_num(v - serie[-2][1], 0)} mila", periodo
    if trasf == "yoy" and len(serie) >= 13 and serie[-13][1]:
        return f"{_num((v / serie[-13][1] - 1) * 100)}% sull'anno", periodo
    if trasf == "mom" and len(serie) >= 2 and serie[-2][1]:
        return f"{_num((v / serie[-2][1] - 1) * 100)}% sul mese", periodo
    if trasf == "livello":
        return f"{_num(v)}% annualizzato", periodo
    if trasf == "fed":                                   # forchetta dei Fed Funds: limite basso e alto
        basso = (extra or [[None, None]])[-1][1]
        testo = f"{basso:.2f}-{v:.2f}%" if basso is not None else f"{v:.2f}%"
        return "tassi attuali " + testo.replace(".", ","), None
    if trasf == "tasso":
        return f"tasso attuale {v:.2f}%".replace(".", ","), None
    return None


def reazione(date_uscita, dgs2):
    """Reazione tipica del tasso USA a 2 anni nelle ultime ULTIME uscite: {livello, quota, n, med} o None."""
    from .notizie import sorpresa_mercato
    zz = [s[0] for s in (sorpresa_mercato(d, dgs2) for d in date_uscita) if s]
    zz = zz[-ULTIME:]
    if len(zz) < 8:                                      # troppo poche uscite misurabili: meglio non dire nulla
        return None
    quota = sum(1 for z in zz if abs(z) >= 1) / len(zz)
    return {"livello": "forte" if quota >= 0.5 else "media" if quota >= 0.3 else "debole",
            "quota": round(quota * 100), "n": len(zz), "med": round(statistics.median(abs(z) for z in zz), 2)}


def _date_uscita(rid, chiave, da):
    """Date passate di uscita di una release FRED (solo giorni con dati pubblicati)."""
    from .fonti import http
    q = urllib.parse.urlencode({"release_id": rid, "api_key": chiave, "file_type": "json", "realtime_start": da,
                                "include_release_dates_with_no_data": "false", "sort_order": "asc", "limit": 1000})
    return [x["date"] for x in json.loads(http(DATE_API + "?" + q)).get("release_dates", []) if x.get("date")]


def calcola(fred, scarica=True, oggi=None):
    """{codice: {cosa, fam, alto, basso, prec, periodo, reaz}} per tutti i tipi di evento dell'agenda.
    fred = serie gia' scaricate dal sito (DGS2, ECBDFR); le altre serie USA si scaricano qui."""
    from .fonti import get_fred
    oggi = oggi or date.today()
    copia = _leggi_copia()
    chiave = _chiave() if scarica else ""
    da = (oggi - timedelta(days=4 * 365)).isoformat()
    out = {}
    for cod, (cosa, fam) in COSA.items():
        alto, basso = REGOLE[fam]
        out[cod] = {"cosa": cosa, "fam": fam, "alto": alto, "basso": basso, "prec": None, "periodo": None, "reaz": None}
    for cod, (sid, trasf, rid) in FRED.items():
        vecchio = (copia or {}).get(cod) or {}
        try:
            serie = fred.get(sid) or (get_fred(sid, da) if scarica else None)
            extra = (fred.get("DFEDTARL") or (get_fred("DFEDTARL", da) if scarica else None)) if trasf == "fed" else None
            p = precedente(serie, trasf, extra)
        except Exception as e:                           # FRED giu' su una serie: resta l'ultimo valore salvato
            log.warning("scenari: %s non scaricata (%s)", sid, type(e).__name__)
            p = (vecchio.get("prec"), vecchio.get("periodo")) if vecchio.get("prec") else None
        if p:
            out[cod]["prec"], out[cod]["periodo"] = p
        r = None
        if rid and chiave:
            try:
                r = reazione(_date_uscita(rid, chiave, da), fred.get("DGS2") or [])
            except Exception as e:
                log.warning("scenari: date di uscita FRED %s non scaricate (%s)", rid, type(e).__name__)
        out[cod]["reaz"] = r or vecchio.get("reaz")
    if scarica:
        try:
            os.makedirs(os.path.dirname(COPIA), exist_ok=True)
            with open(COPIA, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        except OSError as e:
            log.warning("scenari: copia non salvata (%s)", e)
    return out


def _leggi_copia():
    try:
        with open(COPIA, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None
