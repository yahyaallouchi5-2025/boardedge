# -*- coding: utf-8 -*-
"""
orari_borse.py - v7.25 ORARI E FESTIVITA' DELLE BORSE (EODHD "exchange-details"), una sola fonte per tutto il sito.

PERCHE'
  Prima il sito conosceva solo gli orari: nei giorni festivi (Thanksgiving, Natale, Venerdi' Santo...) il badge diceva
  "aperta", il ciclo dei prezzi live interrogava borse chiuse e la sorveglianza poteva dare falsi allarmi.

COSA FA
  Una volta a settimana (dal giro delle azioni) scarica, per ogni borsa che usiamo, orari, giorni lavorativi e
  festivita' dei prossimi mesi e scrive pubblico/calendario.json (letto dalla pagina, da live.py e da sorveglianza.py):
    {"agg", "borse": {codice: {"nome", "fuso", "apre", "chiude", "giorni": [0..4], "festivi": {"AAAA-MM-GG": nome}}}}
  Milano non e' nel calendario di EODHD: usa gli orari di Borsa Italiana e le festivita' di Xetra (quasi identiche:
  1 gennaio, Venerdi' Santo, Pasquetta, 1 maggio, 24-26 e 31 dicembre).
  Se EODHD non risponde resta il file della volta prima; senza file valgono gli orari fissi di ORARI_BASE.

DEBUG: python -c "from cot_radar import orari_borse as O; print(O.aperta('US'))"
"""
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .log import log

BORSE = ("US", "TO", "XETRA", "LSE", "PA", "AS", "MC", "AU")
GIORNI = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
# orari di riserva (senza file): fuso, apertura, chiusura
ORARI_BASE = {"US": ("America/New_York", "09:30", "16:00"), "TO": ("America/Toronto", "09:30", "16:00"),
              "XETRA": ("Europe/Berlin", "09:00", "17:30"), "LSE": ("Europe/London", "08:00", "16:30"),
              "PA": ("Europe/Paris", "09:00", "17:30"), "AS": ("Europe/Amsterdam", "09:00", "17:30"),
              "MC": ("Europe/Madrid", "09:00", "17:30"), "MI": ("Europe/Rome", "09:00", "17:30"),
              "AU": ("Australia/Sydney", "10:00", "16:00")}
RIFAI_GIORNI = 7
RAW = "https://raw.githubusercontent.com/yahyaallouchi5-2025/cot-radar/azioni/pubblico/calendario.json"


def riassunto(js):
    """Risposta di exchange-details -> {nome, fuso, apre, chiude, giorni, festivi}. None se non valida."""
    if not isinstance(js, dict) or not js.get("Timezone"):
        return None
    th = js.get("TradingHours") or {}
    giorni = [GIORNI[g] for g in (th.get("WorkingDays") or "Mon,Tue,Wed,Thu,Fri").split(",") if g in GIORNI]
    festivi = {}
    for v in (js.get("ExchangeHolidays") or {}).values():
        d = str(v.get("Date") or "")[:10]
        if len(d) == 10:
            festivi[d] = v.get("Holiday") or "Festivo"
    return {"nome": js.get("Name"), "fuso": js["Timezone"], "apre": str(th.get("Open") or "")[:5] or None,
            "chiude": str(th.get("Close") or "")[:5] or None, "giorni": giorni, "festivi": dict(sorted(festivi.items()))}


def costruisci(scarica):
    """{codice: riassunto} per tutte le BORSE; scarica(codice) -> json di EODHD (o None)."""
    out = {}
    for b in BORSE:
        r = riassunto(scarica(b))
        if r:
            out[b] = r
    if "MC" in out:                     # EODHD da' a Madrid il fuso di Roma: si corregge (stesso orario solare)
        out["MC"]["fuso"] = "Europe/Madrid"
    if "XETRA" in out:                  # Milano: orari propri, festivita' di Xetra
        fuso, apre, chiude = ORARI_BASE["MI"]
        out["MI"] = {"nome": "Borsa Italiana", "fuso": fuso, "apre": apre, "chiude": chiude,
                     "giorni": [0, 1, 2, 3, 4], "festivi": dict(out["XETRA"]["festivi"])}
    return out


def aperta(borsa, adesso=None, cal=None):
    """True se la borsa e' aperta adesso: giorno lavorativo, non festivo (data LOCALE della borsa), dentro l'orario.
    cal = contenuto di calendario.json (o None: solo orari fissi, senza festivita')."""
    b = ((cal or {}).get("borse") or {}).get(borsa) or {}
    base = ORARI_BASE.get(borsa, ("Europe/Berlin", "09:00", "17:30"))
    fuso, apre, chiude = b.get("fuso") or base[0], b.get("apre") or base[1], b.get("chiude") or base[2]
    loc = (adesso or datetime.now(timezone.utc)).astimezone(ZoneInfo(fuso))
    if loc.weekday() not in (b.get("giorni") or [0, 1, 2, 3, 4]):
        return False
    if loc.strftime("%Y-%m-%d") in (b.get("festivi") or {}):
        return False
    return apre <= loc.strftime("%H:%M") < chiude


def festivo(borsa, giorno, cal):
    """Nome della festivita' se la borsa e' chiusa per festa in quel giorno (data 'AAAA-MM-GG'), altrimenti None."""
    return (((cal or {}).get("borse") or {}).get(borsa) or {}).get("festivi", {}).get(giorno)


def leggi_remoto(url=RAW, timeout=20):
    """calendario.json pubblicato (ramo "azioni"), per live.py e sorveglianza.py. None se non raggiungibile."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "cot-radar/orari-borse"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except Exception:
        return None


def aggiorna(cartella, adesso=None):
    """Riscarica il calendario se ha piu' di RIFAI_GIORNI giorni. Mai bloccante: in errore resta il file vecchio."""
    from . import eodhd
    f = os.path.join(cartella, "pubblico", "calendario.json")
    adesso = adesso or datetime.now(timezone.utc)
    try:
        with open(f, encoding="utf-8") as fh:
            vecchio = json.load(fh)
        if adesso - datetime.fromisoformat(vecchio["agg"]) < timedelta(days=RIFAI_GIORNI):
            return vecchio
    except (OSError, ValueError, KeyError, TypeError):
        vecchio = None
    if not eodhd.attivo():
        return vecchio
    borse = costruisci(lambda b: eodhd.get("exchange-details/" + b, timeout=30, tentativi=2))
    if len(borse) < len(BORSE) // 2:                           # risposta povera: si tiene il file vecchio
        log.warning("calendario borse: solo %d borse ricevute, resta la copia precedente", len(borse))
        return vecchio
    nuovo = {"agg": adesso.isoformat(timespec="minutes"), "borse": borse}
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f, "w", encoding="utf-8") as fh:
        json.dump(nuovo, fh, ensure_ascii=False, separators=(",", ":"))
    log.warning("calendario borse aggiornato: %d borse", len(borse))
    return nuovo
