# -*- coding: utf-8 -*-
"""
prova_eodhd3.py - v7.25 PROVA MIRATA del piano EODHD (lanciata dal workflow prova-eodhd3.yml, mai dal sito):
calendario festivita' delle borse, grafici intraday a 5 e 1 minuto, Londra/Toronto/Sydney, frazionamenti e dividendi
in blocco, delistati per borsa, sentiment, insider, capitalizzazione storica, screener.
La chiave arriva solo dall'ambiente (EODHD_API_KEY, dai Secrets): mai stampata, mai salvata. Scrive eodhd3.json.
"""
import json, os, time, urllib.error, urllib.request
KEY = os.environ.get("EODHD_API_KEY", "")
if not KEY:
    raise SystemExit("manca il secret EODHD_API_KEY")
BASE = "https://eodhd.com/api/"
def get(path, extra=""):
    """(codice http, json o None, byte). Nessun URL nei log: contiene la chiave."""
    url = f"{BASE}{path}{'&' if '?' in path else '?'}api_token={KEY}&fmt=json{extra}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "cot-radar/prova-eodhd3"})
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            try:
                return r.status, json.loads(raw), len(raw)
            except ValueError:
                return r.status, None, len(raw)
    except urllib.error.HTTPError as e:
        return e.code, None, 0
    except Exception as e:
        return type(e).__name__, None, 0
out = {"quando": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "prove": {}}
def prova(nome, path, extra="", riassunto=lambda js: None):
    c, js, n = get(path, extra)
    try:
        r = riassunto(js) if js is not None else None
    except Exception as e:
        r = "riassunto non riuscito: %s %s" % (type(e).__name__, e)
    out["prove"][nome] = {"http": c, "ok": c == 200 and js not in (None, [], {}), "byte": n, "riassunto": r}
    print(f"{nome:30s} {c} {n}")
    return js
oggi = time.strftime("%Y-%m-%d", time.gmtime())
# 1) CALENDARIO: orari e festivita' di ogni borsa che usiamo
def festivi(j):
    h = j.get("ExchangeHolidays") or {}
    futuri = sorted((v.get("Date"), v.get("Holiday"), v.get("Type")) for v in h.values() if (v.get("Date") or "") >= oggi)
    return {"nome": j.get("Name"), "fuso": j.get("Timezone"), "aperta_ora": j.get("isOpen"),
            "orari": j.get("TradingHours"), "festivi_prossimi": futuri[:8], "n_festivi": len(h),
            "chiavi": sorted(j.keys())}
for ex in ("US", "XETRA", "LSE", "TO", "AU", "PA", "AS", "MC", "MI"):
    prova(f"orari_{ex}", f"exchange-details/{ex}", riassunto=festivi)
# 2) GRAFICI INTRADAY: 5 minuti e 1 minuto, per borsa
def barre(j):
    return {"barre": len(j), "prima": j[0].get("datetime") if j else None, "ultima": j[-1].get("datetime") if j else None,
            "campi": sorted(j[-1].keys()) if j else None, "ultima_riga": j[-1] if j else None}
da = int(time.time()) - 3 * 86400
for sym in ("AAPL.US", "SAP.XETRA", "SHEL.LSE", "RY.TO", "BHP.AU", "ASML.AS"):
    prova(f"5m_{sym}", f"intraday/{sym}", f"&interval=5m&from={da}", riassunto=barre)
prova("1m_AAPL.US", "intraday/AAPL.US", f"&interval=1m&from={int(time.time()) - 86400}", riassunto=barre)
# 3) PREZZI LIVE e chiusure in blocco per le borse nuove (valuta di Londra: pence?)
for sym in ("SHEL.LSE", "RY.TO", "BHP.AU"):
    prova(f"rt_{sym}", f"real-time/{sym}", riassunto=lambda j: {k: j.get(k) for k in ("code", "timestamp", "close", "previousClose", "change_p")})
for ex in ("LSE", "TO", "AU"):
    prova(f"bulk_{ex}", f"eod-bulk-last-day/{ex}",
          riassunto=lambda j: {"titoli": len(j), "date": sorted({x.get("date") for x in j})[-2:],
                               "esempio": {k: j[0].get(k) for k in ("code", "close", "adjusted_close")}})
prova("bulk_US_simboli", "eod-bulk-last-day/US", "&symbols=AAPL,MSFT,EXPD",
      riassunto=lambda j: [{k: x.get(k) for k in ("code", "date", "close", "adjusted_close")} for x in j])
# 4) FRAZIONAMENTI e DIVIDENDI di tutta una borsa nell'ultimo giorno, split futuri, delistati per borsa
prova("bulk_split_US", "eod-bulk-last-day/US", "&type=splits", riassunto=lambda j: {"n": len(j), "esempi": j[:3]})
prova("bulk_div_US", "eod-bulk-last-day/US", "&type=dividends", riassunto=lambda j: {"n": len(j), "esempi": j[:2]})
prova("calendario_split", "calendar/splits", f"&from={oggi}&to=" + time.strftime("%Y-%m-%d", time.gmtime(time.time() + 30 * 86400)),
      riassunto=lambda j: {"n": len(j.get("splits") or []), "esempi": (j.get("splits") or [])[:3]})
for ex in ("LSE", "XETRA", "TO", "AU"):
    prova(f"delistati_{ex}", f"exchange-symbol-list/{ex}", "&delisted=1",
          riassunto=lambda j: {"totale": len(j), "trovati": [x.get("Code") for x in j if x.get("Code") in ("BEZ", "SDR", "SDLF", "PHNX")]})
prova("split_NVDA", "splits/NVDA.US", "&from=2020-01-01", riassunto=lambda j: j)
# 5) DATI QUALITATIVI/QUANTITATIVI extra (se il piano li include)
prova("sentiment", "sentiments", "&s=AAPL.US,SHEL.LSE&from=" + time.strftime("%Y-%m-%d", time.gmtime(time.time() - 7 * 86400)),
      riassunto=lambda j: {k: (v[:2] if isinstance(v, list) else v) for k, v in j.items()})
prova("insider", "insider-transactions", "&code=AAPL.US&limit=3", riassunto=lambda j: j[:2] if isinstance(j, list) else j)
prova("cap_storica", "historical-market-cap/AAPL.US", "&from=2026-10-01", riassunto=lambda j: list(j.values())[-2:] if isinstance(j, dict) else j[-2:])
prova("screener", "screener", "&limit=2", riassunto=lambda j: j)
prova("notizie_tag", "news", "&t=earnings&limit=2", riassunto=lambda j: [x.get("title") for x in j])
prova("piano_dopo", "user", riassunto=lambda j: {k: j.get(k) for k in ("apiRequests", "dailyRateLimit")})
json.dump(out, open("eodhd3.json", "w"), indent=1, ensure_ascii=False)
