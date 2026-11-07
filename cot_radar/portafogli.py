# -*- coding: utf-8 -*-
"""
portafogli.py - TRE PORTAFOGLI MODELLO A ROTAZIONE MENSILE (solo acquisto, strumenti spot tipo ETF/ETC)

IDEA
  L'investitore sceglie un profilo (conservativo, moderato, aggressivo) e ogni mese riceve la lista di cosa
  tenere e con che peso. Il profilo decide QUALI mercati sono ammessi e QUANTO rischio si accetta
  (volatilita' obiettivo -> drawdown storico atteso). Ogni ~30 giorni (primo giorno di borsa del mese) il
  portafoglio ruota: restano i mercati ancora favorevoli, escono gli altri, entrano i nuovi.

REGOLE, VERSIONE 3 (dal 28/10/2026; la base e' la versione 2, scelta guardando SOLO lo storico 2006-2015)
  Cambi della v3: quota azioni scelte 5/10/15%, difesa con piu' liquidita' e oro, Treasury e oro SEMPRE presenti
  (niente filtro di trend), ribilancio lento (scambi solo se cambia un mercato o a inizio trimestre).
  ATTENZIONE, onesta': la v3 e' stata decisa guardando TUTTO lo storico 2006-2026, quindi per la v3 il periodo
  "fuori campione" dal 2016 non e' piu' cieco. L'unica verifica davvero pulita e' la linea LIVE (dal 2/11/2026).
  1. Ogni profilo ha una BASE fissa di mercati e pesi (indici azionari, Treasury, oro; Nasdaq, emergenti e
     Bitcoin nell'aggressivo), comprabili a pronti con ETF/ETC. Prezzi rettificati (dividendi inclusi) Yahoo.
  2. FILTRO DI TREND a ogni rotazione mensile: se il prezzo di un mercato e' sotto la sua media a 200 giorni,
     il suo peso va "in pausa" in liquidita' (Treasury 1-3 anni) fino a quando torna sopra. Solo acquisti.
     Dalla v3 il filtro vale per azioni e Bitcoin; Treasury e oro (SEMPRE) restano sempre in portafoglio.
  3. Il punteggio COT di ogni mercato e' mostrato accanto come informazione, ma NON decide i pesi: nello
     storico 2006-2015 il filtro COT (da solo, come conferma o come veto) peggiorava il rendimento a parita'
     di rischio, mentre il filtro di trend dimezzava le cadute (vedi README, "Portafogli modello").
  4. Costi: 0,10% sul capitale che cambia a ogni ribilanciamento.
  VERSIONE 1 (ritirata): ingresso solo con COT da BUY + trend e pesi a volatilita' obiettivo. Fuori campione
  rendeva 1-2% l'anno contro l'8% del 60/40, quasi sempre in liquidita'. Le sue rotazioni restano in
  storico/portafogli/rotazioni.json; la versione 2 in rotazioni_v2.json; la versione 3 registra in rotazioni_v3.json.

VERIFICA ONESTA
  - STORICO: dal primo anno con dati sufficienti fino al 31/12/2015;
  - FUORI CAMPIONE (OOS): dal 2016 a oggi, con le STESSE regole (mai ritoccate guardando questo periodo);
  - LIVE: dalla prima rotazione pubblicata sul sito. Ogni rotazione viene salvata nell'archivio
    (storico/portafogli/rotazioni_v2.json) e non viene mai riscritta: la linea live non si puo' "aggiustare".

DATI: storico/yahoo/<TICKER>.csv (copia dei prezzi Yahoo, aggiornata al massimo una volta al giorno).
  Se Yahoo non risponde si usa la copia salvata; senza copia il portafoglio non viene mostrato.
  ATTENZIONE: i termini d'uso di Yahoo riguardano l'uso personale; per un servizio commerciale conviene
  passare a un fornitore con licenza (basta cambiare scarica_yahoo()).

DEBUG: python -c "from cot_radar import portafogli; help(portafogli.calcola)"
"""
import csv
import json
import math
import os
import time
import urllib.parse
import urllib.request
from bisect import bisect_left
from datetime import date, datetime, timedelta, timezone

from .backtest import punteggi
from .config import ASSETS, NORMAL, PREZZI_YAHOO, ROOT
from .cot import cot_series
from .log import log

CARTELLA = os.path.join(ROOT, "storico")
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{t}?{q}"

# (chiave COT, ticker Yahoo per lo storico, nome, strumento da comprare, classe)
UNIVERSO = [
    ("SP500", "SPY", "S&P 500", "ETF S&P 500", "azioni"),
    ("NASDAQ", "QQQ", "Nasdaq-100", "ETF Nasdaq-100", "azioni"),
    ("DOW", "DIA", "Dow Jones", "ETF Dow Jones", "azioni"),
    ("RUSSELL", "IWM", "Russell 2000", "ETF Russell 2000 (piccole aziende USA)", "azioni"),
    ("EAFE", "EFA", "Azioni Europa e Asia", "ETF MSCI EAFE (Paesi sviluppati esclusi USA)", "azioni"),
    ("EM", "EEM", "Azioni emergenti", "ETF MSCI Emerging Markets", "azioni"),
    ("US10Y", "IEF", "Treasury 10 anni", "ETF Treasury USA 7-10 anni", "obbligazioni"),
    ("USBOND", "TLT", "Treasury 30 anni", "ETF Treasury USA 20+ anni", "obbligazioni"),
    ("GOLD", "GLD", "Oro", "ETC oro fisico", "metalli"),
    ("SILVER", "SLV", "Argento", "ETC argento fisico", "metalli"),
    ("PLATINUM", "PPLT", "Platino", "ETC platino fisico", "metalli"),
    ("COPPER", "CPER", "Rame", "ETC rame", "materie prime"),
    ("WTI", "USO", "Petrolio WTI", "ETC petrolio WTI", "materie prime"),
    ("NATGAS", "UNG", "Gas naturale", "ETC gas naturale", "materie prime"),
    ("CORN", "CORN", "Mais", "ETC mais", "materie prime"),
    ("WHEAT", "WEAT", "Grano", "ETC grano", "materie prime"),
    ("SOY", "SOYB", "Soia", "ETC soia", "materie prime"),
    ("BTC", "BTC-USD", "Bitcoin", "ETP Bitcoin (o Bitcoin a pronti)", "crypto"),
    ("ETH", "ETH-USD", "Ether", "ETP Ether (o Ether a pronti)", "crypto"),
]
LIQUIDITA = ("CASH", "SHY", "Liquidità", "ETF Treasury USA 1-3 anni (parcheggio)", "liquidita")
# Quota "Azioni scelte": 5 titoli dell'Azionario a pari peso, scelti ogni mese da satellite.py (workflow delle azioni).
# Nei calcoli e' un mercato sintetico "SAT": prezzo costruito dai rendimenti mensili dello storico simulato e, dal
# live, dai prezzi giornalieri dei titoli registrati (vedi serie_satellite()).
AZIONI_SCELTE = ("AZ", "SAT", "Azioni scelte", "5 azioni dell'Azionario a pari peso (1 per settore)", "azioni singole")
# Prezzi in piu' che NON entrano nei portafogli: servono alla scheda Correlazioni (correlazioni.py) -> settori USA
# (ETF SPDR) e dollaro (UUP). Scaricati e salvati insieme agli altri, una volta al giorno.
EXTRA = ["XLK", "XLC", "XLY", "XLF", "XLI", "XLE", "XLB", "XLV", "XLP", "XLU", "XLRE", "UUP"]
BENCH = (("SPY", 0.6), ("IEF", 0.4))          # confronto: classico 60% azioni USA + 40% Treasury, ribilanciato
TUTTI = {u[0]: u for u in UNIVERSO + [LIQUIDITA, AZIONI_SCELTE]}
# STRUMENTI DA COMPRARE IN EUROPA: gli ETF USA usati per i calcoli (SPY, QQQ, ...) non si possono comprare da un
# conto europeo (manca il documento KID), quindi per ogni mercato si indica un equivalente UCITS / ETC / ETP con ISIN
# (da cercare nell'app del broker). Verificati il 27/10/2026. Classe di accumulo (Acc) dove esiste.
# chiave -> (nome del prodotto, ISIN, nota facoltativa)
STRUMENTI_UE = {
    "SP500": ("iShares Core S&P 500 UCITS ETF (Acc)", "IE00B5BMR087", None),
    "NASDAQ": ("iShares Nasdaq 100 UCITS ETF (Acc)", "IE00B53SZB19", None),
    "EAFE": ("Xtrackers MSCI World ex USA UCITS ETF 1C", "IE0006WW1TQ4",
             "include anche il Canada: è l'equivalente UCITS più vicino all'MSCI EAFE"),
    "EM": ("iShares Core MSCI EM IMI UCITS ETF (Acc)", "IE00BKM4GZ66", None),
    "US10Y": ("iShares $ Treasury Bond 7-10yr UCITS ETF (Acc)", "IE00B3VWN518", None),
    "GOLD": ("iShares Physical Gold ETC", "IE00B4ND3602", None),
    "BTC": ("iShares Bitcoin ETP", "XS2940466316", None),
    "COPPER": ("WisdomTree Copper (ETC)", "GB00B15KXQ89", "segue i future sul rame: il prezzo include il costo del rinnovo dei contratti"),
    "WTI": ("WisdomTree WTI Crude Oil (ETC)", "GB00B15KXV33", "segue i future sul petrolio WTI: il prezzo include il costo del rinnovo dei contratti"),
    "CASH": ("Xtrackers II EUR Overnight Rate Swap UCITS ETF 1C", "LU0290358497",
             "liquidità in euro al tasso BCE (il modello usa i Treasury USA 1-3 anni in dollari)"),
}

# I tre profili: stesso motore, rischio diverso. BASE fissa di ETF (chiave -> peso relativo, somma 1) e quota di
# AZIONI SCELTE ("az"): i pesi reali sono base x (1 - az) + az nelle 5 azioni. dd = caduta di riferimento del profilo.
# VERSIONE 3 (28/10/2026, studio tools/backtest_varianti.py, variante "E"):
#   - azioni scelte ridotte a 5/10/15% (prima 10/20/40%): meno rischio sul singolo titolo; lo storico simulato della
#     quota azioni sottostima la sua volatilita', quindi pesi alti davano numeri troppo belli per essere veri;
#   - difesa: meta' dei Treasury 7-10 anni in liquidita' e +5 punti di oro (meno legata ai tassi, dopo il 2022);
#   - Treasury e oro SEMPRE in portafoglio (niente filtro di trend: vedi SEMPRE) e ribilancio LENTO (vedi TRIMESTRI):
#     il turnover scende molto (conservativo da circa 150% a 56% l'anno) = meno costi e meno tasse.
#   Rendimento/rischio 2006-2026 (dollari, senza tasse): conservativo 5,7%/5,0% caduta max -13,7%; moderato 7,4%/6,3%
#   -16,9%; aggressivo 11,8%/9,0% -19,8%. La versione 2 (az 10/20/40%) resta nel registro rotazioni_v2.json.
# VERSIONE 4 (31/10/2026, prima della prima rotazione live; studio tools/backtest_ottimizza.py):
#   - +5% materie prime (2,5% rame + 2,5% petrolio WTI, con il filtro di trend) presi dall'S&P 500: dal 2016 migliora
#     rendimento/volatilita' e drawdown in tutti e tre i profili, in dollari e in euro (peggior mese del moderato da
#     -7,1% a -5,4%). Onesta': nel 2006-2015 il rapporto rendimento/volatilita' era un po' piu' basso (drawdown
#     comunque migliore): e' un'assicurazione contro l'inflazione (2022), non un motore di rendimento.
#   - SCARTATE nello stesso studio: filtro di trend sull'oro, oro al 10%, freno di volatilita' (riducevano il
#     rapporto rendimento/volatilita' fuori campione).
#   - statistiche anche IN EURO senza copertura del cambio (stat_eur), come le vede un investitore italiano.
PROFILI = [
    {"id": "conservativo", "nome": "Conservativo", "rischio": "Basso", "dd": 14, "az": .05,
     "base": {"SP500": .15, "EAFE": .10, "COPPER": .025, "WTI": .025, "US10Y": .225, "GOLD": .15, "CASH": .325},
     "descr": "Protezione del capitale prima di tutto: liquidità, Treasury e oro come cuscinetto sempre presente, "
              "azioni globali, un 5% di rame e petrolio contro l'inflazione e una piccola quota di 5 azioni scelte."},
    {"id": "moderato", "nome": "Moderato", "rischio": "Medio", "dd": 17, "az": .10,
     "base": {"SP500": .30, "EAFE": .10, "EM": .05, "COPPER": .025, "WTI": .025, "US10Y": .15, "GOLD": .15, "CASH": .20},
     "descr": "Equilibrio tra crescita e difesa: azioni USA, Europa/Asia ed emergenti bilanciate da Treasury, oro, "
              "liquidità e un 5% di rame e petrolio, più un 10% in 5 azioni scelte ogni mese."},
    {"id": "aggressivo", "nome": "Aggressivo", "rischio": "Alto", "dd": 20, "az": .15,
     "base": {"SP500": .35, "NASDAQ": .15, "EAFE": .10, "EM": .10, "COPPER": .025, "WTI": .025, "US10Y": .05, "GOLD": .15, "BTC": .05},
     "descr": "Massima crescita: indici azionari con tecnologia, emergenti, un 5% di rame e petrolio e una piccola quota "
              "di Bitcoin, più il 15% in 5 azioni scelte. Drawdown più ampi, ripagati da un rendimento più alto."},
]
# Mercati SENZA filtro di trend: la difesa resta sempre in portafoglio (il filtro li faceva entrare e uscire di
# continuo: tanti scambi, tasse e costi per un beneficio che nello studio non c'era).
SEMPRE = ("US10Y", "GOLD")
# RIBILANCIO LENTO: ogni primo giorno di borsa del mese si CONTROLLA, ma si scambia solo se un mercato entra o esce
# (cambia un trend) oppure a inizio trimestre (gennaio, aprile, luglio, ottobre) per riportare i pesi al loro valore.
TRIMESTRI = ("01", "04", "07", "10")
LIVE_V3_DAL = "2026-11-01"     # la linea live della versione 3 parte dalla prima rotazione con le nuove regole
# v7.1 (Ya, 07/11/2026): dalla rotazione di DICEMBRE 2026 la quota delle "5 azioni scelte" passa all'S&P 500 (ETF).
# Studio tools/studio_onesto.py con lo storico EODHD di 22.609 azioni USA (16.684 delistate): misurate senza bias di
# sopravvivenza, le 5 azioni hanno reso come l'S&P 500 (8,4% l'anno con lo stesso filtro di mercato) ma con il doppio
# della volatilita' (22,7% contro 10,4%) e drawdown -37% contro -23%: nessun vantaggio. I numeri della pagina
# contavano gia' la quota come S&P 500 (misura prudente), quindi le statistiche non cambiano. Lo storico resta com'era.
AZ_FINO = "2026-12-01"
for _p in PROFILI:                                   # mercati ammessi = quelli della base (per la pagina)
    _p["ammessi"] = [k for k in _p["base"] if k != "CASH"] + (["AZ"] if _p.get("az") else [])
INIZIO = "2006-01-01"          # primo ribilanciamento (prima i dati degli ETF sono troppo pochi)
OOS_DAL = "2016-01-01"         # da qui in poi: fuori campione
COSTO = 0.001                  # 0,10% del capitale scambiato
SMA = 200                      # media mobile del filtro di trend (giorni di borsa)
VOL_GIORNI = 63                # finestra della volatilita' (circa 3 mesi)
MIN_STORIA = 260               # giorni di prezzo minimi perche' un mercato sia ammesso


# --------------------------------------------------------------------------- dati Yahoo (con copia locale)
TENTATIVI = 3                  # tentativi di download per ogni ticker, con pausa crescente (2 s, 6 s)
VECCHI_GIORNI = 4              # oltre questi giorni di calendario senza prezzi nuovi la scheda avvisa l'utente
CODICE_ERRORE = "503"          # codice generico mostrato all'utente (i dettagli restano nel registro admin)
ESITO = {}                     # ultimo giro di prezzi(): {"falliti": [ticker], "copia": [ticker]} (per l'avviso)


def _valida(pts):
    """Controllo di qualita' di una serie scaricata: almeno 30 prezzi, date crescenti e senza buchi assurdi
    (salto giornaliero oltre +/-70%: dato rotto). Restituisce la serie o None."""
    if not pts or len(pts) < 30:
        return None
    for (d0, v0), (d1, v1) in zip(pts, pts[1:]):
        if d1 <= d0 or not (0.3 < v1 / v0 < 1.7):
            return None
    return pts


def scarica_yahoo(ticker, timeout=20, tentativi=TENTATIVI, attesa=2):
    """Prezzi giornalieri RETTIFICATI (dividendi e frazionamenti inclusi): [(data, prezzo)], None se fallisce.
    Riprova fino a `tentativi` volte (pausa 2 s, poi 6 s): Yahoo a volte risponde 429/5xx per pochi secondi.
    Una risposta incompleta o con prezzi assurdi conta come fallita: in quel caso resta la copia salvata."""
    q = urllib.parse.urlencode({"period1": 0, "period2": int(time.time()), "interval": "1d",
                                "events": "div,split", "includeAdjustedClose": "true"})
    for n in range(tentativi):
        try:
            req = urllib.request.Request(YAHOO.format(t=urllib.parse.quote(ticker), q=q),
                                         headers={"User-Agent": "cot-radar/portafogli"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                js = json.load(r)
            res = js["chart"]["result"][0]
            off = res["meta"].get("gmtoffset", 0)
            adj = res["indicators"]["adjclose"][0]["adjclose"]
            out = {}
            for ts, v in zip(res["timestamp"], adj):
                if v is not None and v > 0:
                    out[datetime.fromtimestamp(ts + off, tz=timezone.utc).date().isoformat()] = round(float(v), 6)
            pts = _valida(sorted(out.items()))
            if pts:
                return pts
            log.warning("Yahoo %s: risposta incompleta o anomala (tentativo %d/%d)", ticker, n + 1, tentativi)
        except Exception as e:                   # rete, limite di richieste, formato cambiato...
            log.warning("Yahoo %s non disponibile: %s (tentativo %d/%d)", ticker, type(e).__name__, n + 1, tentativi)
        if n + 1 < tentativi and attesa:
            time.sleep(attesa * (3 ** n))
    return None


# --------------------------------------------------------------------------- v6.91 PREZZI IN EURO degli strumenti UCITS
# Per l'ACQUISTO DIRETTO a quote intere (Scalable e gli altri broker vendono solo quote intere con l'ordine normale):
# per ogni ISIN si cerca su Yahoo la quotazione in EURO su Xetra (.DE), poi Borsa Italiana (.MI), poi Francoforte (.F),
# e si prende l'ultimo prezzo. Il simbolo trovato si ricorda (storico/yahoo/_ue.json): la ricerca si fa una volta sola.
# Prezzo INDICATIVO (chiusura dell'ultimo giorno): sul broker durante la giornata cambia di poco.
YAHOO_CERCA = "https://query2.finance.yahoo.com/v1/finance/search?{q}"
BORSE_EUR = (".DE", ".MI", ".F")


def _json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "cot-radar/portafogli"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def prezzi_ue(cartella=CARTELLA, oggi=None, cerca=None, ultimo=None):
    """{chiave strumento: {"sym", "p" (euro), "d" (data)}} per gli strumenti di STRUMENTI_UE. Un download al giorno;
    se Yahoo non risponde restano gli ultimi prezzi salvati. cerca/ultimo: funzioni sostituibili nei test."""
    oggi = (oggi or date.today()).isoformat()
    f = os.path.join(cartella, "yahoo", "_ue.json")
    try:
        with open(f, encoding="utf-8") as fh:
            cache = json.load(fh)
    except (OSError, ValueError):
        cache = {}
    simboli, prezzi = cache.get("simboli", {}), cache.get("prezzi", {})
    simboli_e = cache.get("simboli_eodhd", {})                # v6.97: simboli EODHD (formato "SXR8.XETRA")
    giri = cache.get("giri", 0) if cache.get("giorno") == oggi else 0
    if cache.get("giorno") == oggi and (all(k in prezzi for k in STRUMENTI_UE) or giri >= 3):
        return prezzi                            # gia' fatto oggi: completo, oppure gia' 3 tentativi per i mancanti

    def _cerca(isin):                            # simbolo in euro per l'ISIN (None se non c'e')
        js = _json(YAHOO_CERCA.format(q=urllib.parse.urlencode({"q": isin, "quotesCount": 15, "newsCount": 0})))
        sim = [x.get("symbol", "") for x in js.get("quotes") or []]
        for suf in BORSE_EUR:
            for x in sim:
                if x.endswith(suf):
                    return x
        return None

    def _ultimo(sym):                            # (data, prezzo) in euro dell'ultima seduta, None se non e' in euro
        q = urllib.parse.urlencode({"range": "5d", "interval": "1d"})
        res = _json(YAHOO.format(t=urllib.parse.quote(sym), q=q))["chart"]["result"][0]
        if (res["meta"].get("currency") or "").upper() != "EUR":
            return None
        pts = [(datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat(), c)
               for t, c in zip(res.get("timestamp") or [], res["indicators"]["quote"][0]["close"]) if c]
        return pts[-1] if pts else None

    from . import eodhd
    usa_eodhd = eodhd.attivo() and cerca is None and ultimo is None   # nei test (cerca/ultimo finti) solo quelli
    cerca, ultimo = cerca or _cerca, ultimo or _ultimo
    for k, (_, isin, _) in STRUMENTI_UE.items():
        if k in prezzi and prezzi[k].get("d") and cache.get("giorno") == oggi:
            continue                             # questo l'abbiamo gia' oggi: si cercano solo i mancanti
        if usa_eodhd:                            # 1) EODHD: quotazione in euro su Xetra (poi Francoforte, Parigi...)
            try:
                se = simboli_e.get(isin) or eodhd.cerca_eur(isin)
                x = eodhd.ultimo_eur(se) if se else None
                if x:
                    simboli_e[isin] = se
                    prezzi[k] = {"sym": se, "p": round(float(x[1]), 4), "d": x[0], "fonte": "eodhd"}
                    continue
            except Exception as e:
                log.warning("EODHD: prezzo in euro di %s non disponibile (%s): provo Yahoo", k, type(e).__name__)
        try:                                     # 2) Yahoo come riserva (es. Treasury 7-10 anni)
            sym = simboli.get(isin) or cerca(isin)
            if not sym:
                continue
            simboli[isin] = sym
            x = ultimo(sym)
            if x:
                prezzi[k] = {"sym": sym, "p": round(float(x[1]), 4), "d": x[0]}
            time.sleep(0.5)
        except Exception as e:                   # un ETF senza prezzo non deve fermare gli altri
            log.warning("prezzo in euro di %s (%s) non disponibile: %s", k, isin, type(e).__name__)
    try:
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "w", encoding="utf-8") as fh:
            json.dump({"giorno": oggi, "giri": giri + 1, "simboli": simboli, "simboli_eodhd": simboli_e, "prezzi": prezzi}, fh,
                      indent=1, sort_keys=True)
    except OSError:
        pass
    return prezzi


def _in_euro(pr, fx):
    """{"p", "val"} -> prezzo in euro (USD diviso il cambio dollari-per-euro piu' recente), None se non convertibile."""
    if not pr or not pr.get("p"):
        return None
    if (pr.get("val") or "").upper() == "EUR":
        return round(pr["p"], 2)
    if (pr.get("val") or "").upper() == "USD" and fx:
        return round(pr["p"] / fx[max(fx)], 2)
    return None


def _file(cartella, ticker):
    return os.path.join(cartella, "yahoo", ticker.replace("^", "_") + ".csv")


def _leggi(cartella, ticker):
    try:
        with open(_file(cartella, ticker), encoding="utf-8") as f:
            rd = csv.reader(f)
            next(rd, None)
            return [(r[0], float(r[1])) for r in rd if len(r) == 2]
    except (OSError, ValueError):
        return []


def _scrivi(cartella, ticker, pts):
    f = _file(cartella, ticker)
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f + ".tmp", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["data", "valore"])
        w.writerows(pts)
    os.replace(f + ".tmp", f)


def scarica_auto(ticker):
    """v6.97 EODHD come fonte principale degli ETF USA (SPY, QQQ, GLD...) e del Bitcoin; Yahoo per i future (=F)
    e come riserva se EODHD non risponde. Stesso formato di scarica_yahoo: [(data, prezzo rettificato)] o None."""
    from . import eodhd
    if eodhd.attivo() and eodhd.simbolo(ticker):
        pts = _valida(eodhd.scarica_etf(ticker))
        if pts:
            return pts
        log.info("EODHD %s non disponibile: provo Yahoo", ticker)
    return scarica_yahoo(ticker)


def prezzi(scarica=scarica_auto, cartella=CARTELLA, oggi=None, pausa=0.8):
    """{ticker: [(data, prezzo)]} per tutto l'universo + liquidita'. Scarica al massimo una volta al giorno;
    un download nuovo sostituisce la copia solo se e' completo (non piu' corto e non piu' vecchio).
    I prezzi rettificati di Yahoo cambiano all'indietro a ogni dividendo: per questo la copia si sostituisce
    intera invece di aggiungere solo i giorni nuovi."""
    oggi = (oggi or date.today()).isoformat()
    meta_f = os.path.join(cartella, "yahoo", "_meta.json")
    try:
        with open(meta_f, encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError):
        meta = {}
    out, cambiato = {}, False
    ESITO.clear()
    ESITO.update({"falliti": [], "copia": []})
    di_fila = 0                                        # fallimenti consecutivi: a 3 Yahoo e' giu', si smette
    # v6.59: in coda anche i prezzi dei mercati COT che FRED non copre (storico.prezzi_usd li legge da qui)
    gia = set(u[1] for u in UNIVERSO) | {LIQUIDITA[1]} | set(EXTRA)
    for t in [u[1] for u in UNIVERSO] + [LIQUIDITA[1]] + EXTRA + sorted({v[0] for v in PREZZI_YAHOO.values()} - gia):
        vecchi = _leggi(cartella, t)
        if meta.get(t) != oggi and scarica:
            # Yahoo fermo: niente altri tentativi in questo giro (il workflow non resta appeso per mezz'ora),
            # si usano le copie e si riprova al giro successivo
            nuovi = scarica(t) if di_fila < 3 else None
            di_fila = 0 if nuovi else di_fila + 1
            if pausa:
                time.sleep(pausa)
            if nuovi and len(nuovi) >= 0.95 * len(vecchi) and (not vecchi or nuovi[-1][0] >= vecchi[-1][0]):
                _scrivi(cartella, t, nuovi)
                vecchi, meta[t], cambiato = nuovi, oggi, True
            else:                                      # download fallito o peggiore della copia: si tiene la copia
                ESITO["falliti"].append(t)
                if vecchi:
                    ESITO["copia"].append(t)
        if vecchi:
            out[t] = vecchi
    if cambiato:
        os.makedirs(os.path.dirname(meta_f), exist_ok=True)
        with open(meta_f, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=1, sort_keys=True)
    return out


def prezzi_demo(inizio="2000-01-03", fine=None):
    """Prezzi FINTI (passeggiata casuale, sempre uguale) per la modalita' --demo: servono solo a vedere la scheda."""
    import random
    rnd = random.Random(7)
    fine = fine or date.today().isoformat()
    giorni, d = [], date.fromisoformat(inizio)
    while d.isoformat() <= fine:
        if d.weekday() < 5:
            giorni.append(d.isoformat())
        d += timedelta(days=1)
    out = {}
    # v6.59: in coda anche i prezzi dei mercati COT che FRED non copre (storico.prezzi_usd li legge da qui)
    gia = set(u[1] for u in UNIVERSO) | {LIQUIDITA[1]} | set(EXTRA)
    for t in [u[1] for u in UNIVERSO] + [LIQUIDITA[1]] + EXTRA + sorted({v[0] for v in PREZZI_YAHOO.values()} - gia):
        v, pts = 100.0, []
        mu, sg = (0.0001, 0.001) if t == LIQUIDITA[1] else (0.0003, 0.011)
        for g in giorni:
            v *= math.exp(rnd.gauss(mu, sg))
            pts.append((g, round(v, 4)))
        out[t] = pts
    return out


# --------------------------------------------------------------------------- strumenti di calcolo
class Griglia:
    """Prezzi di tutti i mercati sulle stesse date (calendario di borsa USA, quello dello SPY).
    I giorni mancanti di un mercato ripetono l'ultimo prezzo noto; prima del primo prezzo: None."""

    def __init__(self, px, base="SPY"):
        self.date = [d for d, _ in px[base]]
        self.pos = {d: i for i, d in enumerate(self.date)}
        self.p = {}
        for t, pts in px.items():
            dd = dict(pts)
            col, ultimo, n = [], None, 0
            for d in self.date:
                if d in dd:
                    ultimo, n = dd[d], n + 1
                col.append(ultimo)
            self.p[t] = col
        self.n = {t: [0] * len(self.date) for t in px}            # quanti giorni di storia ha ogni mercato
        for t, col in self.p.items():
            c = 0
            for i, v in enumerate(col):
                c += v is not None
                self.n[t][i] = c

    def rend(self, t, i):
        """Rendimento del giorno i (prezzo i / prezzo i-1 - 1); 0 se manca."""
        c = self.p.get(t)
        if not c or i == 0 or c[i] is None or c[i - 1] is None:
            return 0.0
        return c[i] / c[i - 1] - 1


def _std(x):
    if len(x) < 2:
        return None
    m = sum(x) / len(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))


def segnali_cot(righe_cot):
    """{chiave: [(martedi', punteggio)]} point-in-time per i mercati dell'universo (stessa formula del sito)."""
    serie = cot_series(righe_cot)
    codici = {a[0]: a[1] for a in ASSETS}
    out = {}
    for k, *_ in UNIVERSO:
        s = serie.get(codici.get(k))
        if s:
            out[k] = sorted((d, v[0]) for d, v in punteggi(s).items())
    return out


def cot_al(sc, giorno):
    """Ultimo punteggio COT GIA' PUBBLICATO al giorno dato (report del martedi', pubblico il venerdi')."""
    if not sc:
        return None
    limite = (date.fromisoformat(giorno) - timedelta(days=4)).isoformat()   # martedi' + 3 = venerdi' < giorno
    i = bisect_left(sc, (limite, float("inf"))) - 1
    return sc[i] if i >= 0 else None


def primo_feriale(anno, mese):
    """Primo giorno feriale del mese (salta sabato, domenica e il 1 gennaio, chiuso in tutte le borse)."""
    d = date(anno, mese, 1)
    while d.weekday() >= 5 or (d.month == 1 and d.day == 1):
        d += timedelta(days=1)
    return d


def date_ribilancio(g, dal=INIZIO):
    """Primo giorno di borsa di ogni mese, da 'dal' in poi."""
    out, mese = [], None
    for i, d in enumerate(g.date):
        if d >= dal and d[:7] != mese:
            out.append(i)
            mese = d[:7]
    return out


def regola_base(score, trend_ok):
    """Regola della versione 2: conta solo il trend (prezzo sopra la media a 200 giorni). score e' ignorato."""
    return trend_ok


def scegli(profilo, g, i, sc, regola=None, giorno=None):
    """Composizione del profilo al giorno i: ({chiave: peso}, dettagli dei mercati tenuti, mercati in pausa).
    Ogni mercato della base tiene il suo peso se regola(score COT, trend) e' vera, altrimenti il peso va in
    liquidita'. I mercati non ancora quotati abbastanza a lungo (es. Bitcoin prima del 2015) sono liquidita'."""
    regola = regola or regola_base
    # v6.62: giorno puo' essere passato da fuori quando i = len(g.date), cioe' la rotazione del primo giorno di borsa
    # del mese NON ancora nei prezzi: la scelta usa comunque solo i dati fino a i-1 (la chiusura precedente).
    giorno = giorno or g.date[i]
    pesi, info, esclusi = {}, {}, []
    az0 = profilo.get("az", 0)                                  # quota originale (scala la base)
    az = az0 if giorno < AZ_FINO else 0                         # v7.1: da dicembre 2026 la quota va all'S&P 500
    if az:
        # QUOTA AZIONI SCELTE: accesa solo se l'S&P 500 e' sopra la sua media a 200 giorni (filtro di MERCATO:
        # nel 2008 senza filtro la quota perdeva il 55%), altrimenti va in liquidita' come gli ETF in pausa.
        spy = g.p.get("SPY") or []
        fin = [v for v in spy[max(0, i - SMA):i] if v is not None]
        sma = sum(fin) / len(fin) if len(fin) >= SMA * 0.9 else None
        trend = round((spy[i - 1] / sma - 1) * 100, 1) if sma and spy[i - 1] else None
        if "SAT" not in g.p or g.p["SAT"][i - 1 if i else 0] is None:
            pesi["CASH"] = az                                   # dati delle azioni assenti: quota in liquidita'
            esclusi.append({"k": "AZ", "score": None, "trend": None, "base": round(az * 100, 1),
                            "motivo": "dati dell'Azionario non disponibili in questo aggiornamento: quota in liquidità"})
        elif sma and spy[i - 1] > sma:
            vol = _std([g.rend("SAT", j) for j in range(max(1, i - VOL_GIORNI), i)])
            pesi["AZ"] = az
            info["AZ"] = {"k": "AZ", "vol": (vol or 0) * math.sqrt(252), "score": None, "trend": trend, "base": az}
        else:
            pesi["CASH"] = az
            esclusi.append({"k": "AZ", "score": None, "trend": trend, "base": round(az * 100, 1),
                            "motivo": "S&P 500 sotto la media a 200 giorni: le 5 azioni scelte sono in pausa nella liquidità"})
    for k, w in profilo["base"].items():
        w = w * (1 - az0)                                       # la base occupa cio' che resta dopo la quota azioni
        if k == "SP500" and az0 and not az:
            w += az0                                            # v7.1: quota delle 5 azioni -> S&P 500 (stesso filtro)
        if k == "CASH":
            pesi["CASH"] = pesi.get("CASH", 0) + w
            continue
        t = TUTTI[k][1]
        if t not in g.p or g.n[t][i - 1 if i else 0] < MIN_STORIA:
            pesi["CASH"] = pesi.get("CASH", 0) + w            # mercato non ancora disponibile
            continue
        col = g.p[t]
        finestra = [v for v in col[max(0, i - SMA):i] if v is not None]
        sma = sum(finestra) / len(finestra) if len(finestra) >= SMA * 0.9 else None
        x = cot_al(sc.get(k), giorno)
        score = x[1] if x else None
        trend = round((col[i - 1] / sma - 1) * 100, 1) if sma else None
        if k in SEMPRE or (sma and regola(score if score is not None else 0, col[i - 1] > sma)):
            vol = _std([g.rend(t, j) for j in range(max(1, i - VOL_GIORNI), i)])
            pesi[k] = pesi.get(k, 0) + w
            info[k] = {"k": k, "vol": (vol or 0) * math.sqrt(252), "score": score, "trend": trend, "base": w}
        else:
            pesi["CASH"] = pesi.get("CASH", 0) + w
            esclusi.append({"k": k, "score": score, "trend": trend, "base": round(w * 100, 1),
                            "motivo": "prezzo sotto la media a 200 giorni: peso in pausa nella liquidità"})
    pesi = {k: round(v, 4) for k, v in pesi.items() if v >= 0.005}
    return pesi, info, esclusi


def _ticker(k):
    """Chiave del portafoglio -> ticker dei prezzi (le chiavi del benchmark sono gia' ticker)."""
    return TUTTI[k][1] if k in TUTTI else k


def _ribilancia(valore, quote, nuovi):
    """Nuove quote dopo il ribilanciamento (costo sul capitale scambiato). -> (valore, quote)."""
    tot = sum(quote.values()) or 1.0
    vecchi = {k: v / tot for k, v in quote.items()}
    scambio = sum(abs(nuovi.get(k, 0) - vecchi.get(k, 0)) for k in set(nuovi) | set(vecchi))
    valore *= (1 - COSTO * scambio)
    return valore, {k: valore * w for k, w in nuovi.items()}


def simula_prudente(g, pianificati, dal_i, al_i=None, sostituisci=None, fx=None, tassi=None, traccia=None):
    """v6.87 - IL NUMERO ONESTO DEL PORTAFOGLIO (in pagina, PDF, confronti):
      - ACQUISTO PRUDENTE: decisione sulla chiusura del giorno prima, acquisto alla CHIUSURA del giorno di rotazione
        (abbiamo solo prezzi di chiusura). Il movimento del giorno di rotazione resta al portafoglio VECCHIO: e' un
        po' peggio dell'acquisto reale alle 09:00, quindi il numero non e' mai gonfiato;
      - IN EURO (fx = {data: dollari per 1 euro}): ogni mercato rende in dollari x variazione del cambio, senza copertura;
        la LIQUIDITA' matura il tasso BCE sui depositi (tassi, come l'ETF overnight XEON). Senza fx: in dollari;
      - sostituisci = {"AZ": "SPY"}: versione PRUDENTE delle 5 azioni (rendono come l'S&P 500, nessun merito di
        selezione): toglie il possibile vantaggio del bias di sopravvivenza (lo storico usa i titoli di OGGI).
    Stessi pesi, stesse date e stessi costi di simula()."""
    al_i = len(g.date) - 1 if al_i is None else al_i
    sost = sostituisci or {}
    cambio, tasso, ult_fx, ult_t = [], [], None, 0.0
    for d in g.date:
        ult_fx = (fx or {}).get(d, ult_fx)
        ult_t = (tassi or {}).get(d, ult_t)
        cambio.append(ult_fx)
        tasso.append(ult_t)
    valore, curva, quote = 100.0, [], {}
    for i in range(dal_i, al_i + 1):
        if quote:
            f = cambio[i - 1] / cambio[i] if fx and cambio[i] and cambio[i - 1] else 1.0
            if fx:
                gg = (date.fromisoformat(g.date[i]) - date.fromisoformat(g.date[i - 1])).days
                r_cash = (1 + tasso_liquidita(tasso[i]) / 100) ** (gg / 365) - 1
            nuove = {k: v * (1 + r_cash) if (fx and k == "CASH") else
                     v * (1 + g.rend(_ticker(sost.get(k, k)), i)) * f for k, v in quote.items()}
            # v7.4 traccia = [[i0, i1, {chiave: guadagno}]]: guadagno (in valuta del portafoglio) di ogni componente
            # nelle finestre delle crisi storiche, per dire CHI ha difeso il portafoglio (vedi crisi())
            for i0, i1, acc in traccia or ():
                if i0 < i <= i1:
                    for k in nuove:
                        acc[k] = acc.get(k, 0.0) + nuove[k] - quote[k]
            quote = nuove
            valore = sum(quote.values())
        if i in pianificati:                       # acquisto alla chiusura del giorno di rotazione
            valore, quote = _ribilancia(valore, quote, pianificati[i])
        curva.append((g.date[i], valore))
    return curva


# --------------------------------------------------------------------------- v7.4 CRISI STORICHE (stress test)
# Come si e' comportato ogni profilo nelle grandi crisi da quando esiste il modello (2006). Le finestre sono FISSE e
# decise prima di guardare i risultati: dal massimo dell'S&P 500 prima della crisi al suo minimo (chiusure). Nessuna
# previsione: serve a vedere se la diversificazione (Treasury, oro, materie prime, liquidita' del filtro di trend)
# ha fatto il suo lavoro, e quale ingrediente ha difeso in quale tipo di crisi.
# (id, nome, motore della crisi, massimo S&P 500, minimo S&P 500)
CRISI = [
    ("2008", "Crisi finanziaria", "crescita", "2007-10-09", "2009-03-09"),
    ("2011", "Debito europeo", "crescita", "2011-04-29", "2011-10-03"),
    ("2015", "Cina e petrolio", "crescita", "2015-05-21", "2016-02-11"),
    ("2018", "Fed e dazi", "tassi in rialzo", "2018-09-20", "2018-12-24"),
    ("2020", "Pandemia", "liquidità", "2020-02-19", "2020-03-23"),
    ("2022", "Inflazione e guerra", "inflazione", "2022-01-03", "2022-10-12"),
    ("2025", "Dazi USA", "dazi", "2025-02-19", "2025-04-08"),
]
# componenti del portafoglio raggruppati per il "chi ha difeso"
GRUPPI = {"SP500": "Azioni", "NASDAQ": "Azioni", "DOW": "Azioni", "RUSSELL": "Azioni", "EAFE": "Azioni", "EM": "Azioni",
          "AZ": "Azioni", "US10Y": "Treasury", "USBOND": "Treasury", "GOLD": "Oro", "SILVER": "Oro",
          "COPPER": "Materie prime", "WTI": "Materie prime", "NATGAS": "Materie prime", "BTC": "Bitcoin",
          "ETH": "Bitcoin", "CASH": "Liquidità"}
# mappa dei mercati in ogni crisi (in euro): settori USA (ETF SPDR) e le difese
MAPPA_CRISI = [("XLK", "Tecnologia"), ("XLC", "Comunicazione"), ("XLY", "Beni voluttuari"), ("XLP", "Beni di prima necessità"),
               ("XLV", "Salute"), ("XLF", "Finanza"), ("XLI", "Industria"), ("XLE", "Energia"), ("XLB", "Materiali"),
               ("XLU", "Servizi pubblici"), ("XLRE", "Immobiliare"), ("IEF", "Treasury 10 anni"), ("GLD", "Oro"),
               ("USO", "Petrolio WTI")]


def _indice_data(g, d):
    """Indice dell'ultimo giorno di borsa <= d (None se d e' prima dei dati)."""
    i = None
    for j, x in enumerate(g.date):
        if x > d:
            break
        i = j
    return i


def _in_eur_i(g, fx, t, i0, i1):
    """Rendimento % di un mercato tra i giorni i0 e i1, in euro senza copertura (in dollari se manca il cambio)."""
    c = g.p.get(t) or []
    if i1 >= len(c) or c[i0] is None or c[i1] is None:
        return None
    r = c[i1] / c[i0]
    if fx:
        f0 = f1 = None
        for j in range(i0, -1, -1):
            f0 = fx.get(g.date[j])
            if f0:
                break
        for j in range(i1, -1, -1):
            f1 = fx.get(g.date[j])
            if f1:
                break
        if f0 and f1:
            r *= f0 / f1
    return round((r - 1) * 100, 1)


def _recupero(curva, i0, i_min):
    """Mesi (di calendario, arrotondati) dal massimo pre-crisi al ritorno sopra quel valore; None = non ancora."""
    v0 = curva[i0][1]
    for d, v in curva[i_min:]:
        if v >= v0:
            return round((date.fromisoformat(d) - date.fromisoformat(curva[i0][0])).days / 30.44)
    return None


def finestre_crisi(g, dal_i):
    """[(crisi, i0, i1)] delle crisi che cadono dentro lo storico del modello."""
    out = []
    for c in CRISI:
        i0, i1 = _indice_data(g, c[3]), _indice_data(g, c[4])
        if i0 is not None and i1 is not None and i0 >= dal_i and i1 > i0:
            out.append((c, i0, i1))
    return out


def crisi_profilo(g, piani, dal_i, fx=None, tassi=None):
    """Per ogni crisi: rendimento nella finestra, drawdown massimo dentro la finestra, mesi per tornare al valore
    pre-crisi e contributo di ogni gruppo (in punti % del valore all'inizio della crisi). Stessa curva onesta della
    pagina (euro, acquisto prudente, 5 azioni = S&P 500, costi)."""
    fin = finestre_crisi(g, dal_i)
    tr = [[i0 - dal_i, i1 - dal_i, {}] for _, i0, i1 in fin]       # la curva parte da dal_i
    tr_abs = [[i0, i1, acc] for (_, i0, i1), (_, _, acc) in zip(fin, tr)]
    curva = simula_prudente(g, piani, dal_i, sostituisci={"AZ": "SPY"}, fx=fx, tassi=tassi, traccia=tr_abs)
    out = []
    for (c, i0, i1), (a, b, acc) in zip(fin, tr):
        v0 = curva[a][1]
        tratto = [v for _, v in curva[a:b + 1]]
        mx, dd = v0, 0.0
        for v in tratto:
            mx = max(mx, v)
            dd = min(dd, v / mx - 1)
        gr = {}
        for k, x in acc.items():
            gr[GRUPPI.get(k, "Azioni")] = gr.get(GRUPPI.get(k, "Azioni"), 0.0) + x
        out.append({"id": c[0], "r": round((curva[b][1] / v0 - 1) * 100, 1), "dd": round(dd * 100, 1),
                    "rec": _recupero(curva, a, b),
                    "contrib": {k: round(v / v0 * 100, 1) for k, v in sorted(gr.items(), key=lambda x: x[1])}})
    return out


def crisi_mercati(g, dal_i, fx=None):
    """Elenco delle crisi con l'S&P 500 (in euro, comprato e tenuto: rendimento, drawdown, recupero) e la mappa dei
    mercati (settori USA e difese) nella stessa finestra."""
    out = []
    spy = [(d, v) for d, v in zip(g.date, g.p["SPY"]) if v is not None]
    eur = dict(in_euro(spy, fx)) if fx else dict(spy)               # S&P 500 in euro (cambio del giorno o l'ultimo)
    for c, i0, i1 in finestre_crisi(g, dal_i):
        sp = [(d, eur[d]) for d in g.date[i0:] if d in eur]
        mx, dd = sp[0][1], 0.0
        for _, v in sp[:i1 - i0 + 1]:
            mx = max(mx, v)
            dd = min(dd, v / mx - 1)
        mappa = [{"t": t, "n": n, "r": _in_eur_i(g, fx, t, i0, i1)} for t, n in MAPPA_CRISI
                 if (g.n.get(t) or [0] * len(g.date))[i0] > 0]
        out.append({"id": c[0], "nome": c[1], "motore": c[2], "dal": g.date[i0], "al": g.date[i1],
                    "giorni": i1 - i0, "sp": {"r": _in_eur_i(g, fx, "SPY", i0, i1), "dd": round(dd * 100, 1),
                                              "rec": _recupero(sp, 0, i1 - i0)},
                    "mappa": sorted([m for m in mappa if m["r"] is not None], key=lambda m: -m["r"])})
    return out


# --------------------------------------------------------------------------- v6.100 SIMULATORE (punto 6)
# Cosa sarebbe successo a un capitale investito in QUALSIASI mese dello storico (finestre mobili, partenza ogni mese)
# per 1, 3, 5 e 10 anni, sulla stessa curva onesta del sito (euro, acquisto prudente, 5 azioni = S&P 500, costi).
# LEVA MODERATA: rendimento giornaliero x leva, meno il costo del prestito sulla parte presa a prestito
# (tasso BCE + SPREAD_LEVA, ipotesi prudente: il costo reale dipende dal broker). Leva ribilanciata ogni giorno.
# PRELIEVO: per le finestre di 10 anni, il prelievo annuo massimo (in % del capitale iniziale, preso ogni mese) che
# lascia il capitale finale almeno pari a quello iniziale: e' la "rendita" che lo storico avrebbe sostenuto.
ORIZZONTI = (1, 3, 5, 10)
LEVE = (1.0, 1.3, 1.5)
SPREAD_LEVA = 2.0              # punti % sopra il tasso BCE (ipotesi; con leva 1.0 nessun costo)


def _pct(x, q):
    x = sorted(x)
    if not x:
        return None
    k = (len(x) - 1) * q
    a, b = int(math.floor(k)), int(math.ceil(k))
    return x[a] + (x[b] - x[a]) * (k - a)


def con_leva(curva, tassi, leva):
    """Curva giornaliera con leva costante (ribilanciata ogni giorno) e costo del prestito."""
    if leva == 1.0:
        return list(curva)
    out, v, ut = [curva[0]], 100.0, 0.0
    for (d0, a), (d1, b) in zip(curva, curva[1:]):
        ut = tassi.get(d1, ut)
        gg = (date.fromisoformat(d1) - date.fromisoformat(d0)).days
        costo = (leva - 1) * ((ut + SPREAD_LEVA) / 100) * gg / 365
        v *= max(0.0, 1 + leva * (b / a - 1) - costo)
        out.append((d1, v))
    return out


def _mensile(curva):
    """Ultimo valore di ogni mese: [(AAAA-MM, valore)]."""
    m = {}
    for d, v in curva:
        m[d[:7]] = v
    return sorted(m.items())


def _prelievo(rend, lo=0.0, hi=0.4):
    """Prelievo annuo massimo (frazione del capitale iniziale, 1/12 ogni mese) con capitale finale >= iniziale."""
    def finale(w):
        v = 1.0
        for r in rend:
            v = v * (1 + r) - w / 12
            if v <= 0:
                return 0.0
        return v
    if finale(lo) < 1:
        return 0.0
    for _ in range(30):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if finale(mid) >= 1 else (lo, mid)
    return lo


def simulatore(curva, tassi):
    """{"dal", "spread", "leve": {leva: {orizzonte: {p5,p25,p50,p75,p95 (multipli del capitale), perdita (% finestre
    in perdita), dd (drawdown peggiore mediano, %), n}}}, "prelievo": {leva: {p10, p50}} (% annuo, 10 anni)}"""
    if not curva or len(curva) < 300:
        return None
    out = {"dal": curva[0][0], "spread": SPREAD_LEVA, "leve": {}, "prelievo": {}}
    for L in LEVE:
        cl = con_leva(curva, tassi or {}, L)
        gv = [v for _, v in cl]                        # valori GIORNALIERI (per il drawdown vero, anche a meta' mese)
        fine = {}
        for j, (d, _) in enumerate(cl):
            fine[d[:7]] = j                            # indice dell'ultimo giorno di ogni mese
        idx = [fine[m] for m in sorted(fine)]
        val = [gv[j] for j in idx]
        rend = [val[i] / val[i - 1] - 1 for i in range(1, len(val))]
        per_o = {}
        for anni in ORIZZONTI:
            n = anni * 12
            mult, dd = [], []
            for i in range(0, len(val) - n):
                mult.append(val[i + n] / val[i])
                picco, peg = gv[idx[i]], 0.0
                for x in gv[idx[i]:idx[i + n] + 1]:
                    picco = max(picco, x)
                    peg = min(peg, x / picco - 1)
                dd.append(peg)
            if len(mult) < 12:
                continue
            per_o[str(anni)] = {**{f"p{q}": round(_pct(mult, q / 100), 4) for q in (5, 25, 50, 75, 95)},
                                "perdita": round(100 * sum(1 for m in mult if m < 1) / len(mult), 1),
                                "dd": round(100 * _pct(dd, 0.5), 1), "dd_peggiore": round(100 * min(dd), 1),
                                "n": len(mult)}
        out["leve"][str(L)] = per_o
        w = [_prelievo(rend[i:i + 120]) for i in range(0, len(rend) - 120 + 1)]
        if len(w) >= 12:
            out["prelievo"][str(L)] = {"p10": round(100 * _pct(w, 0.10), 1), "p50": round(100 * _pct(w, 0.5), 1)}
    return out


def indice_liquidita(g, tassi, dal_i):
    """Valore di 100 euro tenuti in liquidita' al tasso BCE sui depositi (per "oltre la liquidita'")."""
    v, out, ult = 100.0, [], 0.0
    for i in range(dal_i, len(g.date)):
        ult = tassi.get(g.date[i], ult)
        if i > dal_i:
            gg = (date.fromisoformat(g.date[i]) - date.fromisoformat(g.date[i - 1])).days
            v *= (1 + tasso_liquidita(ult) / 100) ** (gg / 365)
        out.append((g.date[i], v))
    return out


def simula(g, pianificati, dal_i, al_i=None):
    """Valore del portafoglio giorno per giorno. pianificati = {indice giorno: {chiave: peso}}.
    I pesi derivano liberamente tra un ribilanciamento e l'altro (come in un conto reale)."""
    # v6.69 GIORNO DI ROTAZIONE: la composizione e' decisa sulla chiusura del giorno prima (i-1) ed eseguita
    # all'apertura del giorno i, quindi il movimento del giorno i appartiene al portafoglio NUOVO. Prima di v6.69 il
    # rendimento di quel giorno non veniva contato a nessuno (spariva un giorno di borsa a ogni ribilanciamento).
    al_i = len(g.date) - 1 if al_i is None else al_i
    valore, curva, quote = 100.0, [], {}
    for i in range(dal_i, al_i + 1):
        if i in pianificati:
            nuovi = pianificati[i]
            tot = sum(quote.values()) or 1.0
            vecchi = {k: v / tot for k, v in quote.items()}
            scambio = sum(abs(nuovi.get(k, 0) - vecchi.get(k, 0)) for k in set(nuovi) | set(vecchi))
            valore *= (1 - COSTO * scambio)
            quote = {k: valore * w for k, w in nuovi.items()}
        if quote:
            quote = {k: v * (1 + g.rend(_ticker(k), i)) for k, v in quote.items()}
            valore = sum(quote.values())
        curva.append((g.date[i], valore))
    return curva


def statistiche(curva, liq=None):
    """CAGR, volatilita', drawdown massimo, peggior mese, % di mesi positivi (niente statistiche per anno solare:
    il portafoglio ruota ogni mese, il rischio si legge mese per mese).
    v6.87: anche CALMAR (rendimento annuo / drawdown massimo), RECUPERO (mesi dal picco prima del drawdown peggiore
    al ritorno sopra quel picco; None = non ancora recuperato) e, con liq = curva della liquidita' in euro,
    OLTRE LA LIQUIDITA' (rendimento annuo meno quello della liquidita' nello stesso periodo)."""
    if len(curva) < 40:
        return None
    v = [x[1] for x in curva]
    anni = (date.fromisoformat(curva[-1][0]) - date.fromisoformat(curva[0][0])).days / 365.25
    r = [v[i] / v[i - 1] - 1 for i in range(1, len(v))]
    picco, dd, dd_data, picco_data, dd_picco = v[0], 0.0, curva[0][0], curva[0][0], curva[0][0]
    for d, x in curva:
        if x > picco:
            picco, picco_data = x, d
        if x / picco - 1 < dd:
            dd, dd_data, dd_picco = x / picco - 1, d, picco_data
    # recupero: dal picco prima del drawdown peggiore al primo giorno di nuovo sopra quel picco
    recupero = None
    if dd < 0:
        livello = dict(curva)[dd_picco]
        dopo = [d for d, x in curva if d > dd_data and x >= livello]
        if dopo:
            a, b = date.fromisoformat(dd_picco), date.fromisoformat(dopo[0])
            recupero = round((b - a).days / 30.44)
    fine_mese = {}
    for d, x in curva:
        fine_mese[d[:7]] = x
    mesi = list(fine_mese.items())
    rm = [(mesi[i][0], mesi[i][1] / mesi[i - 1][1] - 1) for i in range(1, len(mesi))]
    pm = min(rm, key=lambda x: x[1]) if rm else None
    cagr = round(((v[-1] / v[0]) ** (1 / anni) - 1) * 100, 1) if anni > 0.5 else None
    oltre = liq_cagr = None
    if liq and cagr is not None:
        lq = [x for d, x in liq if curva[0][0] <= d <= curva[-1][0]]
        if len(lq) > 1:
            liq_cagr = round(((lq[-1] / lq[0]) ** (1 / anni) - 1) * 100, 1)
            oltre = round(cagr - liq_cagr, 1)
    return {
        "calmar": round(cagr / abs(dd * 100), 2) if cagr is not None and dd < 0 else None,
        "recupero_mesi": recupero, "recupero_da": dd_picco if dd < 0 else None,
        "liq_cagr": liq_cagr, "oltre_liq": oltre,
        "dal": curva[0][0], "al": curva[-1][0],
        "cagr": cagr,
        "totale": round((v[-1] / v[0] - 1) * 100, 1),
        "vol": round((_std(r) or 0) * math.sqrt(252) * 100, 1),
        "maxdd": round(dd * 100, 1), "maxdd_data": dd_data,
        "peggior_mese": [pm[0], round(pm[1] * 100, 1)] if pm else None,
        "mesi_pos": round(100 * sum(1 for _, x in rm if x > 0) / len(rm)) if rm else None,
    }


def cambio_eur(cartella=CARTELLA):
    """{data: dollari per 1 euro} dall'archivio FRED (storico/DEXUSEU.csv). Vuoto se manca: niente statistiche in euro."""
    try:
        with open(os.path.join(cartella, "DEXUSEU.csv"), encoding="utf-8") as f:
            rd = csv.reader(f)
            next(rd, None)
            return {r[0]: float(r[1]) for r in rd if len(r) == 2 and r[1]}
    except (OSError, ValueError):
        return {}


def in_euro(curva, fx):
    """Curva in dollari -> in euro SENZA copertura: valore / cambio EUR/USD del giorno (o dell'ultimo disponibile)."""
    out, ult = [], None
    for d, v in curva or []:
        ult = fx.get(d, ult)
        if ult:
            out.append((d, v / ult))
    return out


def tasso_liquidita(t):
    """v7.5 REGOLA DELLA LIQUIDITA' (studio 07/11/2026, Ya): con il tasso BCE sui depositi SOTTO ZERO (2014-2022) l'ETF
    overnight (XEON) perde un po' ogni giorno: la liquidita' resta ferma sul conto a 0%. Con il tasso positivo matura
    il tasso BCE (XEON o interessi del conto). Studio 2006-2015 / verifica 2016+: +0,1-0,3% l'anno sulla liquidita',
    nessun drawdown della liquidita' (prima -2,9%). Scartato nello stesso studio: spostare la liquidita' in Treasury
    USA 1-3 anni quando il dollaro e' in trend (EUR/USD sotto la media a 200 giorni): +0,2% l'anno sul Conservativo
    ma drawdown da -7,1% a -9,4% e -10% nel 2008 (la liquidita' diventa una scommessa sul cambio)."""
    return t if t > 0 else 0.0


def tassi_eur(cartella=CARTELLA):
    """{data: tasso BCE sui depositi in %} dall'archivio FRED (storico/ECBDFR.csv, v6.59). Vuoto se manca."""
    try:
        with open(os.path.join(cartella, "ECBDFR.csv"), encoding="utf-8") as f:
            rd = csv.reader(f)
            next(rd, None)
            return {r[0]: float(r[1]) for r in rd if len(r) == 2 and r[1]}
    except (OSError, ValueError):
        return {}


def simula_eur(g, piani, dal_i, fx, tassi):
    """v6.59: il portafoglio COME LO TIENE UN INVESTITORE EUROPEO. Ogni mercato rende (1 + rendimento in dollari) x
    (variazione del cambio EUR/USD); la LIQUIDITA' invece e' in euro (ETF overnight indicato nella scheda) e matura il
    tasso BCE sui depositi del giorno. Stessi ribilanciamenti e costi di simula()."""
    valore, curva, quote, ult_fx, ult_t = 100.0, [], {}, None, 0.0
    cambio, tasso = [], []
    for d in g.date:
        ult_fx = fx.get(d, ult_fx)
        ult_t = tassi.get(d, ult_t)
        cambio.append(ult_fx)
        tasso.append(ult_t)
    for i in range(dal_i, len(g.date)):
        if i in piani:
            nuovi = piani[i]
            tot = sum(quote.values()) or 1.0
            vecchi = {k: v / tot for k, v in quote.items()}
            scambio = sum(abs(nuovi.get(k, 0) - vecchi.get(k, 0)) for k in set(nuovi) | set(vecchi))
            valore *= (1 - COSTO * scambio)
            quote = {k: valore * w for k, w in nuovi.items()}
        if quote and cambio[i] and cambio[i - 1]:          # v6.69: anche il giorno di rotazione (vedi simula)
            f = cambio[i - 1] / cambio[i]                       # se l'euro sale, i dollari valgono meno euro
            gg = (date.fromisoformat(g.date[i]) - date.fromisoformat(g.date[i - 1])).days
            r_eur = (1 + tasso_liquidita(tasso[i]) / 100) ** (gg / 365) - 1
            quote = {k: v * (1 + r_eur) if k == "CASH" else v * (1 + g.rend(_ticker(k), i)) * f
                     for k, v in quote.items()}
            valore = sum(quote.values())
        curva.append((g.date[i], valore))
    return curva


def stat_eur(curva, fx):
    """Statistiche in euro (tutto il periodo e dal 2016) oppure None se il cambio non c'e'."""
    e = in_euro(curva, fx)
    if len(e) < 250:
        return None
    return {"totale": statistiche(e), "oos": statistiche(_tagli(e, dal=OOS_DAL))}


def _settimanale(curva):
    """Un punto per settimana (l'ultimo giorno di ogni settimana): basta per il grafico e pesa poco."""
    out, sett = [], None
    for d, x in curva:
        s = date.fromisoformat(d).isocalendar()[:2]
        if s != sett:
            out.append([d, round(x, 2)])
            sett = s
        else:
            out[-1] = [d, round(x, 2)]
    return out


def _tagli(curva, dal=None, al=None):
    """Parte della curva tra due date, ribasata a 100."""
    c = [(d, x) for d, x in curva if (dal is None or d >= dal) and (al is None or d <= al)]
    return [(d, x * 100 / c[0][1]) for d, x in c] if c else []


MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
        "ottobre", "novembre", "dicembre"]


def rischio_mese(g, pesi, mese, fino_a):
    """IL MESE DI CALENDARIO della rotazione (es. ottobre) in TUTTI gli anni dello storico, tenendo la composizione
    di oggi: per ogni anno rendimento del mese (dalla chiusura dell'ultimo giorno del mese prima a quella dell'ultimo
    giorno del mese, v6.69) e drawdown massimo
    DENTRO il mese (dal punto piu' alto al piu' basso). Un mercato non ancora quotato quell'anno conta come
    liquidita' (o 0 se manca anche quella). fino_a = 'AAAA-MM' della rotazione attuale (esclusa: non e' finita).
    Restituisce {mese, anni: [{a, r, dd}], peggiore, media, positivi, n, dd_max, mercati: [{k, media, pos, n}]}."""
    inizi = {}
    for i, d in enumerate(g.date):
        inizi.setdefault(d[:7], i)
    chiavi = sorted(inizi)
    anni = []
    for j, ym in enumerate(chiavi[:-1]):
        if ym[5:] != mese or ym >= fino_a:
            continue
        # v6.69: dalla chiusura dell'ultimo giorno del mese prima alla chiusura dell'ultimo giorno del mese
        i0, i1 = max(inizi[ym] - 1, 0), inizi[chiavi[j + 1]] - 1
        quote = []                                           # (peso, colonna prezzi) con prezzo noto al via
        for k, w in pesi.items():
            col = g.p.get(_ticker(k))
            if not col or col[i0] is None:
                col = g.p.get(LIQUIDITA[1])
            quote.append((w, col if col and col[i0] is not None else None))
        picco, dd, v = 1.0, 0.0, 1.0
        for i in range(i0, i1 + 1):
            v = sum(w * (c[i] / c[i0] if c else 1.0) for w, c in quote) / (sum(pesi.values()) or 1)
            picco = max(picco, v)
            dd = min(dd, v / picco - 1)
        anni.append({"a": int(ym[:4]), "r": round((v - 1) * 100, 1), "dd": round(dd * 100, 1)})
    if not anni:
        return None
    # stagionalita' di ogni mercato tenuto nello stesso mese (informativa)
    mercati = []
    for k in pesi:
        if k == "CASH":
            continue
        col = g.p.get(_ticker(k))
        rr = [col[inizi[chiavi[j + 1]] - 1] / col[inizi[ym] - 1] - 1 for j, ym in enumerate(chiavi[:-1])
              if ym[5:] == mese and ym < fino_a and inizi[ym] > 0 and col and col[inizi[ym] - 1] is not None
              and g.n[_ticker(k)][inizi[ym] - 1] > 20]
        if len(rr) >= 3:
            mercati.append({"k": k, "media": round(sum(rr) / len(rr) * 100, 1),
                            "pos": round(100 * sum(x > 0 for x in rr) / len(rr)), "n": len(rr)})
    r = [x["r"] for x in anni]
    peg = min(anni, key=lambda x: x["r"])
    return {"mese": MESI[int(mese) - 1], "anni": anni, "n": len(anni),
            "peggiore": [peg["a"], peg["r"]], "media": round(sum(r) / len(r), 1),
            "positivi": sum(x > 0 for x in r), "dd_max": min(x["dd"] for x in anni), "mercati": mercati}


def dettaglio_mesi(g, piani, giorni, curva, sat=None, n=12):
    """ULTIMI n MESI CHIUSI di un profilo (v6.52), per la sezione "Ultime rotazioni":
    per ogni mese (da una rotazione all'ultimo giorno di borsa prima della successiva) il risultato netto e il
    drawdown del portafoglio e, per ogni mercato tenuto: peso a inizio mese, rendimento, contributo al totale
    (peso x rendimento, in punti %) e drawdown dentro il mese. Per la quota "Azioni scelte" anche i singoli titoli.
    I pesi sono quelli REALI a inizio mese (le quote derivano tra un ribilanciamento e l'altro, come in simula)."""
    tutti_g, quote, pesi = set(giorni), {}, {}
    for i in range(giorni[0], len(g.date)):
        if i in piani:
            quote = dict(piani[i])
        if i in tutti_g:                     # pesi a inizio mese: alla chiusura del giorno prima (v6.69)
            tot = sum(quote.values()) or 1.0
            pesi[i] = {k: v / tot for k, v in quote.items()}
        if quote:
            quote = {k: v * (1 + g.rend(_ticker(k), i)) for k, v in quote.items()}
    st = {m[0]: m for m in (sat or {}).get("storico") or []}
    # mesi in cui la quota "Azioni scelte" ha DATI VERI (storico mensile o indice live): negli altri il prezzo
    # sintetico resta fermo e mostrerebbe un falso 0%, quindi il dettaglio dice "dati in arrivo"
    mesi_sat = set(st) | {d[:7] for d, _ in (sat or {}).get("live") or []}
    nomi = (sat or {}).get("nomi") or {}
    reg = (sat or {}).get("registro") or {}
    out = []
    for a, b in list(zip(giorni[:-1], giorni[1:]))[-n:]:
        r_t, dd_t = mese_tratto(curva, giorni[0], a, b - 1)
        voci = []
        for k, w in sorted(pesi.get(a, {}).items(), key=lambda x: -x[1]):
            col = g.p.get(_ticker(k))
            a0 = max(a - 1, 0)                   # v6.69: il mese parte dalla chiusura del giorno prima della rotazione
            if not col or col[a0] is None or col[b - 1] is None or w < 0.001:
                continue
            picco, dd = col[a0], 0.0
            for j in range(a, b):
                if col[j] is not None:
                    picco = max(picco, col[j])
                    dd = min(dd, col[j] / picco - 1)
            r = col[b - 1] / col[a0] - 1
            v = {"k": k, "nome": TUTTI[k][2] if k in TUTTI else k, "w": round(w * 100, 1), "r": round(r * 100, 1),
                 "c": round(w * r * 100, 2), "dd": round(dd * 100, 1)}
            if k == "AZ" and sat is not None and g.date[a][:7] not in mesi_sat:
                v.update({"r": None, "c": None, "dd": None, "attesa": True})
            if k == "AZ":
                m = g.date[a][:7]
                if m in st and len(st[m]) > 3:              # storico simulato: rendimento di ogni titolo
                    v["titoli"] = [{"t": t, "n": nomi.get(t, t), "r": round(x * 100, 1)} for t, x in st[m][3].items()]
                elif m in reg:                               # live: i titoli registrati (rendimento non ancora disponibile)
                    v["titoli"] = [{"t": x["t"], "n": x.get("n", x["t"]), "r": None} for x in reg[m].get("titoli", [])]
            voci.append(v)
        out.append({"mese": g.date[a][:7], "dal": g.date[a], "al": g.date[b - 1], "r": round(r_t, 1),
                    "dd": round(dd_t, 1), "asset": voci})
    return list(reversed(out))


# --------------------------------------------------------------------------- MESE IN CORSO e chiusure mensili
def mese_tratto(curva, off, i0, i1):
    """Rendimento % e drawdown peggiore % del portafoglio dalla chiusura del giorno prima di i0 (decisione) alla
    chiusura del giorno i1 compreso. curva = simula() (parte dal giorno 'off'). Il drawdown e' misurato dal punto piu' alto raggiunto nel mese."""
    # v6.69: base = chiusura del giorno PRIMA della rotazione (il primo giorno del mese conta nel mese)
    base = curva[i0 - 1 - off][1] if i0 - 1 >= off else 100.0
    picco, dd = base, 0.0
    for j in range(i0 - off, i1 - off + 1):
        v = curva[j][1]
        picco = max(picco, v)
        dd = min(dd, v / picco - 1)
    return (curva[i1 - off][1] / base - 1) * 100, dd * 100


def giorni_feriali(ym):
    """Numero di giorni feriali (lun-ven) del mese 'AAAA-MM': stima dei giorni di borsa (le festivita' non contano)."""
    a, m = int(ym[:4]), int(ym[5:])
    d, n = date(a, m, 1), 0
    while d.month == m:
        n += d.weekday() < 5
        d += timedelta(days=1)
    return n


def _file_chiusure(cartella):
    return os.path.join(cartella, "portafogli", "chiusure_v3.json")


def leggi_chiusure(cartella=CARTELLA):
    try:
        with open(_file_chiusure(cartella), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def registra_chiusure(chiusure, nuove, cartella=CARTELLA, scrivi=True):
    """Aggiunge i mesi CHIUSI dal live (rendimento e drawdown finali di ogni profilo). Come il registro delle rotazioni:
    un mese gia' salvato non si tocca piu'. Solo mesi dal LIVE_V3_DAL in poi."""
    out = list(chiusure)
    for n in nuove:
        if n["dal"] >= LIVE_V3_DAL and not any(c["dal"] == n["dal"] for c in out):
            out.append(n)
    if scrivi and len(out) != len(chiusure):
        f = _file_chiusure(cartella)
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        os.replace(f + ".tmp", f)
    return out


# --------------------------------------------------------------------------- registro delle rotazioni live
def _registro(cartella):
    return os.path.join(cartella, "portafogli", "rotazioni_v3.json")


def leggi_rotazioni(cartella=CARTELLA):
    try:
        with open(_registro(cartella), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def registra(rotazioni, data, composizioni, cartella=CARTELLA, scrivi=True):
    """Aggiunge la rotazione del mese se non c'e' ancora. Le rotazioni gia' salvate non si toccano mai."""
    if any(r["data"] == data for r in rotazioni) or data < LIVE_V3_DAL:
        return rotazioni                     # gia' salvata, oppure precedente all'avvio delle regole attuali
    rot = rotazioni + [{"data": data, "profili": {p: sorted(c.items()) for p, c in composizioni.items()}}]
    if scrivi:
        f = _registro(cartella)
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(rot, fh, indent=1)
        os.replace(f + ".tmp", f)
    return rot


# --------------------------------------------------------------------------- controllo di freschezza + ultima copia buona
def usati():
    """Ticker che servono davvero alla scheda: mercati delle basi, liquidita' e benchmark."""
    return sorted({TUTTI[k][1] for p in PROFILI for k in p["base"]} | {t for t, _ in BENCH})


def controlla_prezzi(px, oggi=None):
    """Avviso per l'utente se i prezzi non sono aggiornati: None se tutto ok, altrimenti
    {"codice", "dal": ultimo giorno aggiornato, "mercati": ticker in ritardo o mancanti}.
    In ritardo = ultimo prezzo piu' vecchio di VECCHI_GIORNI giorni di calendario (copre weekend e festivi USA)."""
    oggi = oggi or date.today()
    limite = (oggi - timedelta(days=VECCHI_GIORNI)).isoformat()
    vecchi = [t for t in usati() if not px.get(t) or px[t][-1][0] < limite]
    if not vecchi:
        return None
    ultimi = [px[t][-1][0] for t in vecchi if px.get(t)]
    return {"codice": CODICE_ERRORE, "dal": min(ultimi) if ultimi else None, "mercati": vecchi, "quando": _adesso()}


def _adesso():
    """Data e ora italiane dell'anomalia ('AAAA-MM-GG HH:MM'), mostrate all'utente nel popup."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Rome")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def _ultimo_file(cartella):
    return os.path.join(cartella, "portafogli", "ultimo.json")


def salva_ultimo(dati, cartella=CARTELLA):
    """Copia dell'ultima scheda calcolata: se un giro successivo fallisce si mostra questa (con l'avviso)."""
    f = _ultimo_file(cartella)
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(dati, fh, separators=(",", ":"))
    os.replace(f + ".tmp", f)


def leggi_ultimo(cartella=CARTELLA):
    try:
        with open(_ultimo_file(cartella), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def di_riserva(cartella=CARTELLA, oggi=None):
    """Se il calcolo di oggi non e' riuscito: l'ultima scheda buona con l'avviso di manutenzione (o None)."""
    d = leggi_ultimo(cartella)
    if d:
        d["avviso"] = {"codice": CODICE_ERRORE, "dal": d.get("aggiornato"), "mercati": [], "quando": _adesso()}
    return d


# --------------------------------------------------------------------------- calcolo completo per la pagina
def serie_satellite(sat, date_borsa):
    """Prezzo giornaliero sintetico della quota "Azioni scelte" (ticker SAT) sulle date di borsa dello SPY.
    - storico simulato (rendimenti MENSILI di satellite.py): dentro ogni mese il rendimento e' distribuito in modo
      geometrico sui giorni di borsa (le oscillazioni dentro il mese di questa parte non si vedono: limite noto);
    - live: indice GIORNALIERO dei titoli registrati, attaccato all'ultimo valore dello storico.
    Restituisce [(data, prezzo)] o [] se i dati mancano."""
    if not sat or not sat.get("storico"):
        return []
    per_mese = {}
    for d in date_borsa:
        per_mese.setdefault(d[:7], []).append(d)
    rend = {m: r for m, r, *_ in sat["storico"]}
    mesi = sorted(rend)
    prima = [d for d in date_borsa if d[:7] < mesi[0]]
    if not prima:
        return []
    out, v = [(prima[-1], 100.0)], 100.0                    # base 100 all'ultimo giorno del mese prima
    for m in mesi:
        giorni = per_mese.get(m, [])
        for k, d in enumerate(giorni, 1):
            out.append((d, round(v * (1 + rend[m]) ** (k / len(giorni)), 5)))
        v *= 1 + rend[m]
    lv = sat.get("live") or []
    if lv:
        base, v0 = out[-1][1], lv[0][1] or 1.0
        out += [(d, round(base * x / v0, 5)) for d, x in lv if d > out[-1][0]]
    return out


def calcola(righe_cot, px, cartella=CARTELLA, scrivi=True, oggi=None, sat=None, pue=None):
    """righe_cot = archivio COT; px = prezzi() (ticker -> punti); sat = satellite.json delle azioni scelte (o None:
    la quota va in liquidita'). Restituisce i dati della scheda "Portafogli" oppure None se mancano i prezzi di base
    (SPY e liquidita')."""
    if "SPY" not in px or LIQUIDITA[1] not in px:
        return None
    px_tutti = dict(px)
    ss = serie_satellite(sat, [d for d, _ in px["SPY"]])
    if ss:
        px_tutti["SAT"] = ss
    g = Griglia(px_tutti)
    sc = segnali_cot(righe_cot)
    giorni = date_ribilancio(g)
    if not giorni:
        return None
    ultimo_rib = giorni[-1]
    oggi = oggi or date.today()
    # v6.62 ROTAZIONE IN ATTESA: e' iniziato un mese nuovo ma i prezzi arrivano solo fino all'ultima chiusura del mese
    # prima (es. domenica 1 novembre: ultimo prezzo venerdi' 30 ottobre). La rotazione del primo giorno di borsa usa
    # SOLO i dati fino alla chiusura precedente, quindi e' gia' decisa: la mostriamo subito (si esegue all'apertura),
    # chiudiamo il mese passato e il conto alla rovescia punta all'apertura di quel giorno, non al mese dopo.
    attesa = None
    if oggi.strftime("%Y-%m") > g.date[-1][:7]:
        attesa = primo_feriale(oggi.year, oggi.month).isoformat()
    rif = date.fromisoformat(attesa or g.date[ultimo_rib])          # rotazione in vigore (o in partenza)
    prossima = attesa or primo_feriale(rif.year + (rif.month == 12), rif.month % 12 + 1).isoformat()
    VIRT = len(g.date)                     # indice "virtuale" del giorno di rotazione in attesa (non ancora nei prezzi)
    giorni_c = giorni + [VIRT] if attesa else giorni               # per chiudere anche l'ultimo mese
    # il mese appena finito va nel registro PERMANENTE delle chiusure solo se i prezzi arrivano all'ultimo giorno
    # feriale del mese (es. venerdi' 30 ottobre): con un ritardo dei dati si vede in pagina ma non si salva, e si
    # salvera' con la rotazione vera (le chiusure salvate non si riscrivono mai).
    fine_mese = date.fromisoformat(g.date[-1][:8] + "28")
    while (fine_mese + timedelta(days=1)).month == fine_mese.month:
        fine_mese += timedelta(days=1)
    while fine_mese.weekday() >= 5:
        fine_mese -= timedelta(days=1)
    chiusura_completa = g.date[-1] >= fine_mese.isoformat()

    # benchmark 60/40 ribilanciato ogni mese
    bench = simula(g, {i: dict(BENCH) for i in giorni}, giorni[0]) if "IEF" in px else None

    fx = cambio_eur(cartella)                       # v4: per le statistiche in euro
    te = tassi_eur(cartella)                       # v6.59: tasso BCE per la liquidita' in euro
    # v6.87 NUMERO PRINCIPALE = in EURO (liquidita' al tasso BCE) con ACQUISTO PRUDENTE; senza cambio/tassi in archivio
    # si ripiega sui dollari (stesso acquisto prudente). liq = 100 euro in liquidita', per "oltre la liquidita'".
    eur_ok = bool(fx and te)
    fxp, tep = (fx, te) if eur_ok else (None, None)
    liq = indice_liquidita(g, te, giorni[0]) if eur_ok else None
    bench_p = simula_prudente(g, {i: dict(BENCH) for i in giorni}, giorni[0], fx=fxp, tassi=tep) if "IEF" in px else None
    rotazioni = leggi_rotazioni(cartella)
    out_prof, composizioni, comp_reg = [], {}, {}
    corrente, chiusi = [], {}
    # i 5 titoli del mese della rotazione (registrati dal vivo da satellite.py; prima del live: ultima scelta simulata)
    mese_rot = (attesa or g.date[ultimo_rib])[:7]
    satellite_n = (sat or {}).get("n") or 5
    reg = ((sat or {}).get("registro") or {}).get(mese_rot)
    ante = (sat or {}).get("anteprima") or None       # anteprima dei titoli del mese prossimo (provvisoria)
    if reg:
        titoli_az = [{"t": x["t"], "n": x["n"], "s": x["s"], **({"sost": x["sost"], "sost_n": x.get("sost_n")} if x.get("sost") else {})}
                     for x in reg["titoli"]]                # v6.90: "sost" = al posto di un titolo non acquistabile
    else:
        ult = [x for x in (sat or {}).get("storico") or [] if x[0] == mese_rot]
        titoli_az = [{"t": t, "n": t, "s": None} for t in (ult[0][2] if ult and len(ult[0]) > 2 else [])]
    for prof in PROFILI:
        piani, storia, prec = {}, [], None
        for i in giorni:
            pesi, info, esclusi = scegli(prof, g, i, sc)
            insieme = frozenset(k for k in pesi if k != "CASH")
            # RIBILANCIO LENTO: si scambia solo se cambia l'insieme dei mercati o a inizio trimestre
            if prec is None or insieme != prec or g.date[i][5:7] in TRIMESTRI:
                piani[i] = pesi
            prec = insieme
            storia.append((g.date[i], pesi))
        curva = simula(g, piani, giorni[0])          # serie "tecnica" in dollari: mese in corso e mesi chiusi (come prima)
        # v6.87 serie per i NUMERI in pagina: euro + acquisto prudente; principale con le 5 azioni = S&P 500 (prudente),
        # "sel" con la selezione vera dei 5 titoli, "usd" = principale ma in dollari (per chi investe in dollari)
        cp = simula_prudente(g, piani, giorni[0], sostituisci={"AZ": "SPY"}, fx=fxp, tassi=tep)
        c_sel = simula_prudente(g, piani, giorni[0], fx=fxp, tassi=tep)
        c_usd = simula_prudente(g, piani, giorni[0], sostituisci={"AZ": "SPY"})
        pesi, info, esclusi = scegli(prof, g, ultimo_rib, sc)
        comp_reg[prof["id"]] = pesi                # registro live: solo rotazioni gia' nei prezzi (data vera)
        if attesa:                                 # composizione del mese nuovo, decisa sulla chiusura precedente
            pesi, info, esclusi = scegli(prof, g, VIRT, sc, giorno=attesa)
            storia.append((attesa, pesi))
        composizioni[prof["id"]] = pesi
        # linea LIVE: pesi delle rotazioni salvate (mai ricalcolati)
        live = None
        if rotazioni:
            pl = {g.pos[r["data"]]: dict(r["profili"].get(prof["id"], [])) for r in rotazioni if r["data"] in g.pos}
            if pl:
                live = simula_prudente(g, pl, min(pl), fx=fxp, tassi=tep)      # live: titoli veri, in euro
        # MESE IN CORSO: dal giorno di rotazione (ingresso alla chiusura) a oggi, con i prezzi a fine giornata (EOD).
        # In attesa il mese nuovo non e' ancora iniziato: zero giorni, nessun risultato.
        r_m, dd_m = (0.0, 0.0) if attesa else mese_tratto(curva, giorni[0], ultimo_rib, len(g.date) - 1)
        corrente.append((prof["id"], {"r": round(r_m, 1), "dd": round(dd_m, 1),
                                      "rr": round(r_m / abs(dd_m), 1) if dd_m <= -0.3 else None}))
        # mesi CHIUSI: da una rotazione all'ultimo giorno di borsa prima della successiva
        for a, b in zip(giorni_c[:-1], giorni_c[1:]):
            if g.date[a] >= LIVE_V3_DAL:
                r_c, dd_c = mese_tratto(curva, giorni[0], a, b - 1)
                chiusi.setdefault(g.date[a], {"mese": g.date[a][:7], "dal": g.date[a], "al": g.date[b - 1],
                                              "profili": {}})["profili"][prof["id"]] = {"r": round(r_c, 1), "dd": round(dd_c, 1)}
        comp = [{"k": k, "nome": TUTTI[k][2], "strumento": TUTTI[k][3], "classe": TUTTI[k][4],
                 "peso": round(w * 100, 1), "score": info.get(k, {}).get("score"),
                 "trend": info.get(k, {}).get("trend"), "vol": round(info[k]["vol"] * 100, 1) if k in info else None}
                for k, w in sorted(pesi.items(), key=lambda x: (x[0] == "CASH", -x[1]))]
        for c in comp:
            u = STRUMENTI_UE.get(c["k"])
            if u:
                c["ue"] = {"nome": u[0], "isin": u[1], "nota": u[2]}
                if (pue or {}).get(c["k"]):                 # v6.91: prezzo di 1 quota in euro (Xetra), indicativo
                    c["ue"].update({"prezzo": pue[c["k"]]["p"], "sym": pue[c["k"]]["sym"], "pd": pue[c["k"]]["d"]})
            if c["k"] == "AZ":
                c["titoli"] = titoli_az
                # v6.91 ACQUISTO DIRETTO: prezzo di 1 azione in euro (USD convertiti col cambio BCE/FRED dell'ultimo
                # giorno) e riserve in ordine di punteggio, per sostituire le azioni che costano piu' della quota
                acq = (sat or {}).get("acquisto") or {}
                if acq.get("mese") == mese_rot:
                    for x in c["titoli"]:
                        x["eur"] = _in_euro((acq.get("prezzi") or {}).get(x["t"]), fx)
                    c["riserve"] = [{"t": r["t"], "n": r["n"], "s": r["s"], "pt": r["pt"], "eur": _in_euro(r, fx)}
                                    for r in acq.get("riserve") or [] if _in_euro(r, fx)]
                c["peso_titolo"] = round(c["peso"] / satellite_n, 1)
                if ante and ante.get("titoli"):
                    c["anteprima"] = ante
        cambi = []
        for (d0, p0), (d1, p1) in zip(storia[-13:-1], storia[-12:]):
            a = set(k for k in p1 if k != "CASH")
            b = set(k for k in p0 if k != "CASH")
            cambi.append({"data": d1, "entrati": sorted(a - b), "usciti": sorted(b - a), "tenuti": sorted(a & b),
                          "liquidita": round(p1.get("CASH", 0) * 100), **({"attesa": True} if d1 == attesa else {})})
        out_prof.append({
            "id": prof["id"], "nome": prof["nome"], "descr": prof["descr"], "dd_rif": prof["dd"],
            "rischio": prof.get("rischio"),
            "az": 0 if (attesa or g.date[ultimo_rib]) >= AZ_FINO else round(prof.get("az", 0) * 100),
            "base": [{"k": k, "nome": TUTTI[k][2], "peso": round(w * (1 - prof.get("az", 0)) * 100)}
                     for k, w in prof["base"].items()] + ([{"k": "AZ", "nome": TUTTI["AZ"][2], "peso": round(prof["az"] * 100)}]
                                                          if prof.get("az") else []),
            "ammessi": [{"k": k, "nome": TUTTI[k][2]} for k in prof["ammessi"]],
            "composizione": comp, "esclusi": esclusi,
            "mese": rischio_mese(g, pesi, mese_rot[5:7], mese_rot),
            "corrente": {"mese": MESI[int(mese_rot[5:7]) - 1], "dal": attesa or g.date[ultimo_rib], "al": g.date[-1],
                         "gg": 0 if attesa else len(g.date) - ultimo_rib, "tot": giorni_feriali(mese_rot),
                         "live": (attesa or g.date[ultimo_rib]) >= LIVE_V3_DAL, **({"attesa": True} if attesa else {}),
                         **dict(corrente)[prof["id"]]},
            # v6.87: "stat" e' IN EURO (se c'e' il cambio), acquisto prudente, 5 azioni prudenti (= S&P 500)
            "valuta": "EUR" if eur_ok else "USD",
            "stat": {"storico": statistiche(_tagli(cp, al=OOS_DAL), liq),
                     "oos": statistiche(_tagli(cp, dal=OOS_DAL), liq),
                     "totale": statistiche(cp, liq),
                     "live": statistiche(live, liq) if live else None},
            "stat_eur": {"totale": statistiche(cp, liq), "oos": statistiche(_tagli(cp, dal=OOS_DAL), liq)}
                        if eur_ok else None,
            "stat_sel": {"totale": statistiche(c_sel, liq), "oos": statistiche(_tagli(c_sel, dal=OOS_DAL), liq)},
            "stat_usd": {"totale": statistiche(c_usd), "oos": statistiche(_tagli(c_usd, dal=OOS_DAL))},
            "curva": _settimanale(cp), "live_dal": live[0][0] if live else None,
            "sim": simulatore(cp, tep if eur_ok else {}),       # v6.100: simulatore (finestre mobili, leva, prelievo)
            "crisi": crisi_profilo(g, piani, giorni[0], fxp, tep),   # v7.4: stress test sulle crisi storiche
            "rotazioni": list(reversed(cambi)),
            "mesi_chiusi": dettaglio_mesi(g, piani, giorni_c, curva, sat),
        })
    registra(rotazioni, g.date[ultimo_rib], comp_reg, cartella, scrivi=scrivi)
    da_salvare = [c for c in chiusi.values() if not (attesa and c["al"] == g.date[-1] and not chiusura_completa)]
    chiusure = registra_chiusure(leggi_chiusure(cartella), da_salvare, cartella, scrivi=scrivi)
    if attesa and not chiusura_completa:          # in pagina il mese chiuso si vede lo stesso (provvisorio)
        chiusure = chiusure + [c for c in chiusi.values() if c["al"] == g.date[-1] and
                               not any(x["dal"] == c["dal"] for x in chiusure)]
    avviso = controlla_prezzi(px, oggi)
    if avviso:          # ERRORE nel registro: l'admin riceve la mail (job "avviso-admin"), l'utente vede l'avviso
        log.error("portafogli: prezzi Yahoo non aggiornati dal %s (%s); falliti in questo giro: %s",
                  avviso["dal"], ", ".join(avviso["mercati"]), ", ".join(ESITO.get("falliti", [])) or "nessuno")
    out = {
        "aggiornato": g.date[-1], "rotazione": attesa or g.date[ultimo_rib], "prossima": prossima,
        **({"attesa": True, "decisa_al": g.date[-1]} if attesa else {}),
        "dal": g.date[giorni[0]], "oos_dal": OOS_DAL, "fonte": "Yahoo Finance (prezzi rettificati)",
        "profili": out_prof, "chiusure": chiusure,
        # v6.87: benchmark misurato come i portafogli (euro, acquisto prudente)
        "bench": {"nome": "60/40 (S&P 500 + Treasury 10 anni)", "curva": _settimanale(bench_p),
                  "stat": {"storico": statistiche(_tagli(bench_p, al=OOS_DAL), liq),
                           "oos": statistiche(_tagli(bench_p, dal=OOS_DAL), liq), "totale": statistiche(bench_p, liq)},
                  "stat_eur": {"totale": statistiche(bench_p, liq)} if eur_ok else None} if bench_p else None,
        "valuta": "EUR" if eur_ok else "USD",
        "crisi": crisi_mercati(g, giorni[0], fxp),          # v7.4: crisi storiche (S&P 500 e mappa dei mercati)
        # v7.5: tasso BCE sui depositi in vigore (la scheda dice se la liquidita' va in XEON o resta sul conto)
        "tasso_bce": te[max(te)] if te else None,
        "avviso": avviso,
        "azioni": {"live_dal": (sat or {}).get("live_dal"), "nota": (sat or {}).get("nota"),
                   "disponibili": bool(ss)},
    }
    if scrivi:
        salva_ultimo(out, cartella)
    return out
