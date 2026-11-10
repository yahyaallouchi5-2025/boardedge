# -*- coding: utf-8 -*-
"""
azioni.py - SCHEDA AZIONI: ~630 titoli dei listini principali, divisi per settore, con prezzi Yahoo Finance.

LISTINI: S&P 500, Nasdaq-100, FTSE MIB, DAX 40, Euro Stoxx 50 (+ i 5 indici come riferimento).
  L'elenco dei titoli con settore (classificazione GICS, 11 settori) e listini e' in cot_radar/azioni_elenco.csv:
  Yahoo da GitHub Actions non concede il profilo aziendale (settore), quindi l'elenco e' fisso e va aggiornato a
  ogni ribilanciamento trimestrale degli indici. Il NOME del titolo invece arriva da Yahoo a ogni download.

FLUSSO GIORNALIERO (workflow .github/workflows/azioni.yml, dopo la chiusura USA, separato dal sito):
  1. per ogni titolo: ultimi 2 anni giornalieri (prezzi rettificati) -> 1 richiesta;
     una volta a settimana per titolo (giorno scelto dal ticker, cosi' il carico si spalma) anche lo storico
     MENSILE completo per la stagionalita' -> 1 richiesta in piu';
  2. ogni richiesta: fino a 3 tentativi (pausa 2 s, poi 6 s). 5 titoli falliti di fila = Yahoo fermo:
     niente altre richieste in questo giro, restano le copie di ieri;
  3. le copie grezze stanno in <cartella>/grezzi/ (ramo git "azioni", riscritto ogni giorno senza storia:
     non si gonfia mai). Un titolo che non si aggiorna tiene la sua copia: la pagina non salta;
  4. si scrivono i file per il sito in <cartella>/pubblico/: indice.json (tutti i titoli con i numeri della
     tabella, ~200 KB) e titoli/<TICKER>.json (grafico e stagionalita', caricato solo quando si apre il titolo);
  5. ANOMALIA: se Yahoo e' fermo o fallisce oltre il 10% dei titoli -> indice.json riporta {codice, quando}:
     l'utente vede un popup "manutenzione in corso" (una volta per sessione), il workflow fallisce apposta e
     GitHub manda la mail all'admin. I titoli singoli che falliscono (es. appena tolti dal listino) finiscono
     solo nel registro.

USO: python -m cot_radar.azioni <cartella>        (es. dati_azioni; --prova = solo 12 titoli)
"""
import csv
import json
import math
import os
import random
import sys
import time
import urllib.parse
import urllib.request
import zlib
from datetime import date, datetime, timedelta, timezone

from .log import log

QUI = os.path.dirname(os.path.abspath(__file__))
ELENCO = os.path.join(QUI, "azioni_elenco.csv")
YAHOO = "https://{h}.finance.yahoo.com/v8/finance/chart/{t}?{q}"
HOST = ("query1", "query2")    # v6.82: i due server di Yahoo, alternati a ogni tentativo (se uno limita, l'altro spesso no)
TENTATIVI = 3                  # tentativi per richiesta
DI_FILA = 5                    # fallimenti consecutivi oltre i quali Yahoo e' considerato fermo
SOGLIA_ANOMALIA = 0.10         # quota di titoli falliti oltre la quale scatta l'avviso di manutenzione
# v6.86 RITMO UMANO: pausa A CASO tra 1,5 e 3 secondi tra una richiesta e l'altra (prima 0,35 s fissi = raffica che
# Yahoo riconosce e blocca). Un numero fisso (es. 0 nei test) resta valido.
PAUSA = (1.5, 3.0)
# v6.82 - BLOCCO TEMPORANEO: il 03/11/2026 Yahoo ha smesso di rispondere dopo 84 titoli (limite di richieste sull'IP
# del server GitHub) e il giro si e' fermato. Ora, ai 5 fallimenti di fila, si aspetta e si riprende dai titoli falliti:
# prima 2 minuti, poi 5. Solo dopo la seconda ripresa fallita Yahoo e' davvero "fermo".
RIPRESE = (120, 300)
CODICE_ERRORE = "503"
CHIUSURA_UTC = "21:00"         # dopo quest'ora (UTC) i prezzi del giorno sono definitivi anche per Wall Street

# v6.86 TRE GIRI PER AREA (workflow azioni.yml), ognuno dopo la chiusura delle SUE borse, cosi' Yahoo riceve tre gruppi
# piccoli a ore di distanza invece di ~1.000 richieste tutte insieme:
#   asia   ~10:30 UTC  Tokyo, Hong Kong, Shanghai, India (l'India chiude alle 10:00 UTC)
#   europa ~17:15 UTC  Milano, Francoforte, Parigi, Amsterdam, Madrid... (chiusura 16:30 UTC)
#   usa    ~21:35 UTC  Wall Street (chiusura 21:00 UTC; anche fondamentali SEC, profili e 5 azioni scelte)
# CHIUSURA = ora UTC dopo la quale i prezzi del giorno di quell'area sono definitivi (giro ripetuto = niente richieste).
AREE = ("asia", "europa", "usa")
CHIUSURA = {"asia": "10:00", "europa": "16:35", "usa": CHIUSURA_UTC}
# v7.23 Sydney (.AX, chiude alle 06:00 UTC) va col giro asiatico, Londra (.L) con l'europeo, Toronto (.TO) con gli USA
SUFFISSI_ASIA = (".T", ".HK", ".SS", ".SZ", ".NS", ".BO", ".AX")
SUFFISSI_USA = (".TO",)
INDICI_AREA = {"^N225": "asia", "^HSI": "asia", "^NSEI": "asia", "000001.SS": "asia", "^AXJO": "asia",
               "FTSEMIB.MI": "europa", "^GDAXI": "europa", "^STOXX50E": "europa", "^FTSE": "europa"}
# DOWNLOAD INCREMENTALE: ogni giorno solo gli ultimi 5 giorni (risposta leggera) aggiunti alla copia. Lo storico di 2 anni
# si riscarica intero una volta a settimana per titolo (stesso giorno dello storico mensile) o se la copia non torna:
# i prezzi sono RETTIFICATI, quindi un dividendo o uno split cambia anche i giorni passati -> giorni in comune diversi
# oltre lo 0,5% = storico da riscaricare.
DIFF_RETTIFICA = 0.005
GIORNI_STORICO = 745           # ~2 anni di copia (come range=2y)

SETTORI = [  # id, nome, ETF di riferimento USA (SPDR)
    ("tech", "Tecnologia", "XLK"), ("tlc", "Comunicazione", "XLC"), ("cdis", "Beni voluttuari", "XLY"),
    ("cstap", "Beni di prima necessità", "XLP"), ("salute", "Salute", "XLV"), ("fin", "Finanza", "XLF"),
    ("ind", "Industria", "XLI"), ("mat", "Materiali", "XLB"), ("ener", "Energia", "XLE"),
    ("util", "Servizi pubblici", "XLU"), ("imm", "Immobiliare", "XLRE"),
]
LISTINI = {"sp500": "S&P 500", "ndx": "Nasdaq-100", "mib": "FTSE MIB", "dax": "DAX 40", "sx5e": "Euro Stoxx 50",
           "n225": "Nikkei 225", "hsi": "Hang Seng", "sse50": "SSE 50 Cina", "nifty": "Nifty 50 India",
           "ftse100": "FTSE 100", "tsx60": "TSX 60 Canada", "asx50": "ASX 50 Australia"}     # v7.23: 3 nuove borse
INDICI = [("^GSPC", "S&P 500", "sp500"), ("^NDX", "Nasdaq-100", "ndx"), ("FTSEMIB.MI", "FTSE MIB", "mib"),
          ("^GDAXI", "DAX 40", "dax"), ("^STOXX50E", "Euro Stoxx 50", "sx5e"), ("^N225", "Nikkei 225", "n225"),
          ("^HSI", "Hang Seng", "hsi"), ("000001.SS", "Shanghai Composite", "sse50"), ("^NSEI", "Nifty 50", "nifty"),
          ("^FTSE", "FTSE 100", "ftse100"), ("^GSPTSE", "S&P/TSX Composite", "tsx60"), ("^AXJO", "S&P/ASX 200", "asx50")]

# PUNTEGGIO di ogni titolo (0-100), ricalcolato ogni sera: media pesata dei PERCENTILI tra tutti i titoli
# (cosi' valute e mercati diversi sono confrontabili). Forza = momento + trend + stagionalita' del mese in corso.
PESI = {"v1a": 0.30, "v3m": 0.20, "t200": 0.15, "st_media": 0.20, "st_pos": 0.15}
MESI_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
           "novembre", "dicembre"]
# v7.24 ACQUISTABILI: titoli che un privato compra davvero in euro su Scalable Capital (USA ed Europa continentale).
# Gli altri restano nell'Azionario (classifica, ciambelle dei paesi) ma NON entrano nella vetrina della Dashboard ne'
# nelle 5 azioni dei portafogli (satellite.py usa la stessa regola: una sola fonte).
#   India, Cina continentale: chiuse ai privati europei; Tokyo, Hong Kong: di solito assenti su Scalable (v6.90);
#   Toronto, Sydney: liquidita' in euro scarsa o assenti, le grandi canadesi sono gia' a Wall Street;
#   Londra: sui titoli britannici si paga l'imposta di bollo dello 0,5% in acquisto; cosi' lo storico simulato dei
#   portafogli resta sullo stesso universo di prima (cambiano solo le seconde quotazioni, prima ammesse).
NON_ACQUISTABILI = (".NS", ".BO", ".SS", ".SZ", ".T", ".HK", ".AX", ".TO", ".L")
# v7.24 SECONDE QUOTAZIONI della stessa societa' (o altra classe di azioni): restano in tabella con il rimando alla
# principale, ma non entrano in vetrina/portafogli (eviterebbero doppioni). {seconda: principale}
DOPPIE = {"ASML.AS": "ASML", "SHOP.TO": "SHOP", "TRI.TO": "TRI", "0005.HK": "HSBA.L", "RIO.AX": "RIO.L",
          "GOOG": "GOOGL", "FOX": "FOXA", "NWS": "NWSA"}


def acquistabile(t):
    """True se il titolo puo' entrare nella vetrina e nelle 5 azioni dei portafogli (vedi NON_ACQUISTABILI)."""
    return not t.endswith(NON_ACQUISTABILI) and t not in DOPPIE


TOP_N = 5                      # titoli nella vetrina della Dashboard (al massimo 1 per settore)
SCONTO_N = 3                   # v6.66: titoli "in sconto" sotto la vetrina (settori diversi da quelli della vetrina)
MIN_ANNI_STAG = 8              # anni minimi di storico mensile perche' la stagionalita' conti


def ora_italia():
    """Data e ora italiane (per il messaggio d'anomalia), con ripiego su UTC."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Rome"))
    except Exception:
        return datetime.now(timezone.utc)


def elenco(percorso=ELENCO):
    """[{t, nome, s (settore), l [listini]}] dal CSV (le righe che iniziano con # sono commenti)."""
    with open(percorso, encoding="utf-8") as f:
        righe = [r for r in f if r.strip() and not r.startswith("#")]
    return [{"t": r["ticker"], "nome": r["nome"], "s": r["settore"], "l": r["listini"].split(",")}
            for r in csv.DictReader(righe, delimiter=";")]


# --------------------------------------------------------------------------- download
def _valida(pts, min_punti=20):
    """Serie plausibile: abbastanza punti, date crescenti, nessun salto fra -75% e +300% (= dato rotto)."""
    if not pts or len(pts) < min_punti:
        return None
    for (d0, v0), (d1, v1) in zip(pts, pts[1:]):
        if d1 <= d0 or not (0.25 < v1 / v0 < 4):
            return None
    return pts


def min_punti(intervallo, periodo):
    """v6.97 CORREZIONE: punti minimi perche' una risposta sia valida. Il download INCREMENTALE ("5d", v6.86) porta
    al massimo 5 prezzi: prima si chiedevano comunque 20 punti, quindi OGNI aggiornamento incrementale veniva scartato
    come "risposta incompleta" (3 tentativi a vuoto, titolo alla copia, dopo 5 di fila "Yahoo fermo"). Era una delle
    cause dei giri con 0 titoli aggiornati."""
    if intervallo == "1mo":
        return 12
    return 1 if periodo == "5d" else 20


def scarica(ticker, intervallo="1d", periodo="2y", timeout=20, tentativi=TENTATIVI, attesa=2):
    """({meta}, [(data, prezzo rettificato)]) da Yahoo, oppure None dopo `tentativi` prove fallite.
    meta = nome, valuta, borsa (dal grafico: nessun cookie o crumb richiesto)."""
    # ATTENZIONE: con range=max Yahoo "comprime" gli storici lunghi (es. Apple dal 1980) in barre TRIMESTRALI anche se
    # si chiede interval=1mo. Con l'intervallo esplicito period1/period2 rispetta invece la granularita' mensile.
    if periodo == "max":
        q = urllib.parse.urlencode({"period1": 0, "period2": int(time.time()), "interval": intervallo,
                                    "includeAdjustedClose": "true", "events": "div,split"})
    else:
        q = urllib.parse.urlencode({"range": periodo, "interval": intervallo, "includeAdjustedClose": "true",
                                    "events": "div,split"})
    for n in range(tentativi):
        try:
            # tentativo 1 -> query1, 2 -> query2, 3 -> query1 ...
            req = urllib.request.Request(YAHOO.format(h=HOST[n % len(HOST)], t=urllib.parse.quote(ticker), q=q),
                                         headers={"User-Agent": "cot-radar/azioni"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                res = json.load(r)["chart"]["result"][0]
            m = res["meta"]
            off = m.get("gmtoffset", 0)
            ind = res["indicators"]
            valori = (ind.get("adjclose") or [{}])[0].get("adjclose") or ind["quote"][0]["close"]
            out = {}
            for ts, v in zip(res.get("timestamp") or [], valori):
                if v is not None and v > 0:
                    d = datetime.fromtimestamp(ts + off, tz=timezone.utc).date().isoformat()
                    out[d[:7] if intervallo == "1mo" else d] = round(float(v), 4)
            pts = _valida(sorted(out.items()), min_punti(intervallo, periodo))
            if pts and intervallo == "1mo" and not mensile_ok(pts):
                log.warning("Yahoo %s: storico mensile non mensile (granularita' %s)", ticker, m.get("dataGranularity"))
                pts = None
            valuta = m.get("currency")
            if pts and valuta in ("GBp", "GBX"):        # v7.23 Londra quota in pence: si passa a sterline (/100)
                pts, valuta = [(d, round(v / 100, 4)) for d, v in pts], "GBP"
            if pts:
                return {"nome": m.get("longName") or m.get("shortName"), "valuta": valuta,
                        "borsa": m.get("fullExchangeName") or m.get("exchangeName")}, pts
            # Risposta arrivata ma inutilizzabile: per lo storico MENSILE e' sempre la stessa (titolo quotato da poco o con
            # buchi), quindi riprovare e' solo tempo perso -> ci si ferma subito e aggiorna() usa i prezzi giornalieri.
            if intervallo == "1mo":
                log.info("Yahoo %s: storico mensile non utilizzabile, uso i prezzi giornalieri", ticker)
                return None
            log.warning("Yahoo %s (%s): risposta incompleta o anomala (tentativo %d/%d)", ticker, intervallo, n + 1, tentativi)
        except Exception as e:
            log.warning("Yahoo %s (%s): %s (tentativo %d/%d)", ticker, intervallo, getattr(e, "code", type(e).__name__),
                        n + 1, tentativi)
        if n + 1 < tentativi and attesa:
            time.sleep(attesa * (3 ** n))
    return None


def scarica_auto(ticker, intervallo="1d", periodo="2y"):
    """v6.97 FONTE PRINCIPALE EODHD, Yahoo come riserva (stesso formato di scarica()).
    1) se c'e' la chiave e il titolo e' coperto (USA, Xetra, Parigi, Amsterdam..., indici) -> EODHD;
    2) altrimenti, o se EODHD non risponde/ha una serie non valida -> Yahoo come prima (Milano, Asia)."""
    from . import eodhd
    if eodhd.attivo() and eodhd.simbolo(ticker):
        r = eodhd.scarica_azione(ticker, intervallo, periodo)
        if r and _valida(r[1], min_punti(intervallo, periodo)) and (intervallo != "1mo" or mensile_ok(r[1])):
            return r
        log.info("EODHD %s (%s %s) non disponibile: provo Yahoo", ticker, intervallo, periodo)
    return scarica(ticker, intervallo, periodo)


def pausa_per(ticker, pausa):
    """Pausa tra un titolo e l'altro: serve solo con Yahoo (anti-blocco). Con EODHD basta la sua pausa interna."""
    from . import eodhd
    return 0 if (eodhd.attivo() and eodhd.simbolo(ticker)) else pausa


def _mesi(x):
    """'AAAA-MM' -> numero progressivo del mese (per misurare la distanza tra due barre)."""
    return int(x[:4]) * 12 + int(x[5:7])


def mensile_da_giornaliero(d):
    """[(AAAA-MM-GG, prezzo)] -> [(AAAA-MM, ultimo prezzo del mese)]: storico mensile di riserva (copre solo gli anni
    dei prezzi giornalieri, ma basta per i titoli quotati da poco, che uno storico lungo non ce l'hanno comunque)."""
    m = {}
    for g, v in d or []:
        m[g[:7]] = v
    return sorted(m.items())


def mensile_ok(m):
    """True se lo storico [(AAAA-MM, prezzo)] e' davvero MENSILE: almeno il 90% delle barre consecutive dista 1 mese
    (le copie vecchie scaricate con range=max possono essere trimestrali: vanno riscaricate)."""
    if not m or len(m) < 3:
        return False
    salti = [_mesi(b[0]) - _mesi(a[0]) for a, b in zip(m, m[1:])]
    return sum(s == 1 for s in salti) >= 0.9 * len(salti)


def _nome_file(t):
    return t.replace("^", "_").replace("/", "_")


def _leggi(f):
    try:
        with open(f, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _scrivi(f, dati):
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(dati, fh, separators=(",", ":"), ensure_ascii=False)
    os.replace(f + ".tmp", f)


def giorno_mensile(t):
    """Giorno della settimana (0-4) in cui il titolo riscarica lo storico mensile: sparso sui 5 giorni."""
    return zlib.crc32(t.encode()) % 5


def area(t):
    """Area di borsa del ticker Yahoo: 'asia', 'europa' o 'usa' (decide in quale dei tre giri si aggiorna)."""
    if t in INDICI_AREA:
        return INDICI_AREA[t]
    if t.startswith("^") or "." not in t or t.endswith(SUFFISSI_USA):
        return "usa"                                   # indici USA e titoli USA (BRK-B, BF-B: trattino, nessun punto)
    return "asia" if t.endswith(SUFFISSI_ASIA) else "europa"


def _dormi(pausa):
    """Pausa tra le richieste: numero fisso oppure (minimo, massimo) = a caso nell'intervallo."""
    if not pausa:
        return
    time.sleep(random.uniform(*pausa) if isinstance(pausa, tuple) else pausa)


def unisci(vecchi, nuovi, oggi):
    """Copia [(data, prezzo)] + ultimi giorni da Yahoo -> serie unita, oppure None se va riscaricato tutto
    (giorni in comune con prezzo diverso = rettifica per dividendo/split, oppure un buco tra copia e nuovi dati)."""
    if not vecchi or not nuovi:
        return None
    vv = {g: v for g, v in vecchi}
    for g, v in nuovi:
        if g in vv and vv[g] and abs(v / vv[g] - 1) > DIFF_RETTIFICA:
            return None
    ultimo = vecchi[-1][0]
    nuovi_dopo = [(g, v) for g, v in nuovi if g > ultimo]
    if nuovi_dopo and (date.fromisoformat(nuovi_dopo[0][0]) - date.fromisoformat(ultimo)).days > 6:
        return None                                    # mancano giorni in mezzo: la copia e' troppo vecchia
    taglio = (oggi - timedelta(days=GIORNI_STORICO)).isoformat()
    return [list(x) for x in vecchi if x[0] >= taglio] + [list(x) for x in nuovi_dopo]


def data_minima(oggi, ora_utc, chiusura):
    """v6.95 PARACADUTE: data minima che l'ultimo prezzo di un titolo deve avere per essere ancora "fresco".
    Ultima seduta chiusa = oggi se e' feriale e la borsa dell'area ha gia' chiuso (ora_utc >= chiusura, "HH:MM"),
    altrimenti il giorno feriale prima. Tolleranza di UNA seduta (il giro dopo recupera): minimo = feriale precedente.
    Cosi' un giro fallito durante la seduta o con un solo giorno perso NON accende "in manutenzione"."""
    g = oggi if (oggi.weekday() < 5 and ora_utc >= chiusura) else oggi - timedelta(days=1)
    while g.weekday() >= 5:
        g -= timedelta(days=1)
    g -= timedelta(days=1)
    while g.weekday() >= 5:
        g -= timedelta(days=1)
    return g.isoformat()


def freschezza(cartella, titoli, chiusura, oggi=None, ora_utc=None):
    """v6.95 AUTO-GUARIGIONE: rilegge le copie salvate (nessun download) e dice se un'area e' ancora indietro.
    Ritorna l'anomalia {codice, quando} se piu' di SOGLIA_ANOMALIA titoli hanno dati piu' vecchi di data_minima,
    altrimenti None. Usata a OGNI giro per tutte le aree: l'avviso sparisce da solo appena i dati tornano freschi."""
    if not titoli:
        return None
    oggi = oggi or date.today()
    minimo = data_minima(oggi, ora_utc or datetime.now(timezone.utc).strftime("%H:%M"), chiusura)
    vecchi = 0
    for t in titoli:
        d = (_leggi(os.path.join(cartella, "grezzi", _nome_file(t) + ".json")) or {}).get("d") or []
        if not d or d[-1][0] < minimo:
            vecchi += 1
    if vecchi / len(titoli) > SOGLIA_ANOMALIA:
        return {"codice": CODICE_ERRORE, "quando": ora_italia().strftime("%Y-%m-%d %H:%M")}
    return None


def aggiorna(cartella, titoli=None, oggi=None, scarica=scarica_auto, pausa=PAUSA, riprese=None, chiusura=CHIUSURA_UTC,
             ora_utc=None):
    """Aggiorna le copie grezze (cartella/grezzi/<T>.json). Restituisce lo stato del giro:
    {quando, ok, copia [titoli rimasti alla copia], falliti [senza nessun dato], fermo (Yahoo giu'), anomalia}."""
    oggi = oggi or date.today()
    titoli = titoli if titoli is not None else [x["t"] for x in elenco()] + [i[0] for i in INDICI]
    stato = {"quando": ora_italia().strftime("%Y-%m-%d %H:%M"), "ok": 0, "copia": [], "falliti": [], "fermo": False}
    ora_utc = ora_utc or datetime.now(timezone.utc).strftime("%H:%M")
    minimo = data_minima(oggi, ora_utc, chiusura)    # sotto questa data la copia di un titolo e' "vecchia"
    vecchie = set()                                  # titoli rimasti con dati vecchi (o senza dati): solo loro contano
    di_fila = 0
    # riprese dopo un blocco: solo nel giro vero (pausa > 0); nei test (pausa=0) ci si ferma subito come prima
    riprese = list(RIPRESE if pausa else ()) if riprese is None else list(riprese)
    coda, i, ultimi = list(titoli), 0, []          # ultimi = titoli falliti di fila (da rifare dopo la pausa)
    while i < len(coda):
        t = coda[i]
        i += 1
        f = os.path.join(cartella, "grezzi", _nome_file(t) + ".json")
        vecchio = _leggi(f) or {}
        # gia' aggiornato DOPO la chiusura USA di oggi (giro ripetuto): niente nuove richieste.
        # Un aggiornamento fatto durante la seduta (prezzi provvisori) invece si ripete la sera.
        if vecchio.get("agg") == oggi.isoformat() and vecchio.get("agg_ora", "") >= chiusura:
            stato["ok"] += 1
            continue
        nuovo = None
        if di_fila >= DI_FILA and riprese:
            # BLOCCO: pausa, poi si rifanno i titoli falliti di fila (tolti dalla copia) e si prosegue
            sec = riprese.pop(0)
            log.warning("azioni: Yahoo non risponde da %d titoli: pausa di %d s e ripresa", di_fila, sec)
            time.sleep(sec)
            for x in ultimi:
                for lista in (stato["copia"], stato["falliti"]):
                    if x in lista:
                        lista.remove(x)
            coda[i - 1:i - 1] = ultimi             # si rifanno prima del titolo corrente
            t, ultimi, di_fila = coda[i - 1], [], 0
            f = os.path.join(cartella, "grezzi", _nome_file(t) + ".json")
            vecchio = _leggi(f) or {}
        completo = (oggi.weekday() == giorno_mensile(t) and vecchio.get("agg_full", "") < (oggi - timedelta(days=3)).isoformat()) \
            or vecchio.get("agg_full", "") < (oggi - timedelta(days=8)).isoformat() or len(vecchio.get("d") or []) < 200
        d = None
        if di_fila < DI_FILA:
            if not completo:
                # giorno normale: solo gli ultimi 5 giorni, uniti alla copia
                nuovo = scarica(t, "1d", "5d")
                _dormi(pausa_per(t, pausa))
                if nuovo:
                    d = unisci(vecchio.get("d"), nuovo[1], oggi)
                    if d is None:
                        log.info("azioni %s: la copia non torna (dividendo/split o buco): riscarico 2 anni", t)
                        completo = True
            if completo:
                nuovo = scarica(t)
                _dormi(pausa_per(t, pausa))
                d = nuovo[1] if nuovo else None
        if nuovo and d:
            di_fila, ultimi = 0, []
            meta = nuovo[0]
            rec = dict(vecchio, t=t, agg=oggi.isoformat(), agg_ora=datetime.now(timezone.utc).strftime("%H:%M"), d=d,
                       **{k: v for k, v in meta.items() if v})
            if completo:
                rec["agg_full"] = oggi.isoformat()
            # storico mensile: nel giorno del titolo (al massimo una volta a settimana) o se e' vecchio di oltre 10 giorni.
            # Se Yahoo non da' uno storico mensile valido, si ricava dai prezzi giornalieri (ultimo prezzo di ogni mese)
            # e si segna la data lo stesso: cosi' NON si richiede di nuovo ogni sera (prima ~3 tentativi a vuoto al giorno).
            vecchio_m = vecchio.get("agg_m", "")
            if (oggi.weekday() == giorno_mensile(t) and vecchio_m < (oggi - timedelta(days=3)).isoformat()) \
                    or vecchio_m < (oggi - timedelta(days=10)).isoformat():
                mm = scarica(t, "1mo", "max")
                _dormi(pausa_per(t, pausa))
                if mm:
                    rec["m"], rec["agg_m"] = mm[1], oggi.isoformat()
                else:
                    if not mensile_ok(vecchio.get("m")):
                        rec["m"] = mensile_da_giornaliero(d)
                    rec["agg_m"] = oggi.isoformat()
            _scrivi(f, rec)
            stato["ok"] += 1
        else:
            di_fila += 1
            if di_fila <= DI_FILA:
                ultimi.append(t)
            (stato["copia"] if vecchio.get("d") else stato["falliti"]).append(t)
            if not vecchio.get("d") or vecchio["d"][-1][0] < minimo:
                vecchie.add(t)
    stato["fermo"] = di_fila >= DI_FILA
    mancati = len(stato["copia"]) + len(stato["falliti"])
    stato["anomalia"] = None
    # v6.95: l'avviso "in manutenzione" scatta SOLO se i dati sono davvero vecchi (oltre una seduta di ritardo).
    # Yahoo bloccato ma copie fresche = nessun avviso (solo log): il sito mostra dati corretti.
    vecchie &= set(stato["copia"]) | set(stato["falliti"])      # tolti quelli recuperati dopo la pausa
    stato["vecchi"] = len(vecchie)
    if titoli and len(vecchie) / len(titoli) > SOGLIA_ANOMALIA:
        stato["anomalia"] = {"codice": CODICE_ERRORE, "quando": stato["quando"]}
        log.error("azioni: aggiornamento non riuscito (%s): %d titoli non aggiornati su %d%s",
                  stato["quando"], mancati, len(titoli), ", Yahoo fermo" if stato["fermo"] else "")
    elif mancati:
        log.warning("azioni: %d titoli non aggiornati (restano le copie): %s", mancati,
                    ", ".join((stato["copia"] + stato["falliti"])[:30]))
    return stato


# --------------------------------------------------------------------------- calcoli per il sito
def _var(d, giorni):
    """Variazione % dall'ultimo prezzo a quello di `giorni` di calendario prima (o il primo disponibile dopo)."""
    if len(d) < 2:
        return None
    lim = (date.fromisoformat(d[-1][0]) - timedelta(days=giorni)).isoformat()
    base = next((v for x, v in reversed(d) if x <= lim), None)
    return round((d[-1][1] / base - 1) * 100, 1) if base else None


def riassunto(rec):
    """Numeri della tabella per un titolo: prezzo, variazioni, distanza dal massimo a 52 settimane, trend rispetto
    alla media a 200 giorni e mini grafico (1 punto a settimana, scala 0-99)."""
    d = rec.get("d") or []
    if len(d) < 2:
        return None
    ult = d[-1][0]
    inizio_anno = next((v for x, v in reversed(d) if x < ult[:4] + "-01-01"), None)
    anno = [v for x, v in d if x >= (date.fromisoformat(ult) - timedelta(days=365)).isoformat()]
    sma = sum(v for _, v in d[-200:]) / len(d[-200:]) if len(d) >= 200 else None
    sett, ultima = [], None
    for x, v in d:
        if x >= (date.fromisoformat(ult) - timedelta(days=365)).isoformat():
            k = date.fromisoformat(x).isocalendar()[:2]
            if k != ultima:
                sett.append(v)
                ultima = k
            else:
                sett[-1] = v
    lo, hi = min(sett), max(sett)
    return {"p": d[-1][1], "data": ult, "v1g": round((d[-1][1] / d[-2][1] - 1) * 100, 2),
            "v1s": _var(d, 7), "v1m": _var(d, 30), "v3m": _var(d, 91),
            "vytd": round((d[-1][1] / inizio_anno - 1) * 100, 1) if inizio_anno else None, "v1a": _var(d, 365),
            "dmax": round((d[-1][1] / max(anno) - 1) * 100, 1) if anno else None,
            "t200": round((d[-1][1] / sma - 1) * 100, 1) if sma else None,
            # v7.7 icona del trend accanto al nome (stessa regola di tecnica(): prezzo e SMA 50 contro SMA 200)
            "tr": stato_trend(d[-1][1], _sma([v for _, v in d], 50), _sma([v for _, v in d], 200)),
            "sp": [round((v - lo) / (hi - lo) * 99) if hi > lo else 50 for v in sett]}


def _rsi(chiusure, n=14):
    """RSI di Wilder (0-100) sulle chiusure: media mobile esponenziale di Wilder di rialzi e ribassi."""
    if len(chiusure) <= n:
        return None
    su = giu = 0.0
    for i in range(1, n + 1):
        x = chiusure[i] - chiusure[i - 1]
        su, giu = su + max(x, 0), giu + max(-x, 0)
    su, giu = su / n, giu / n
    for i in range(n + 1, len(chiusure)):
        x = chiusure[i] - chiusure[i - 1]
        su = (su * (n - 1) + max(x, 0)) / n
        giu = (giu * (n - 1) + max(-x, 0)) / n
    return 100.0 if giu == 0 else round(100 - 100 / (1 + su / giu), 1)


def _sma(v, n, fine=None):
    """Media semplice degli n valori che finiscono all'indice fine (escluso; default: fino all'ultimo)."""
    fine = len(v) if fine is None else fine
    return sum(v[fine - n:fine]) / n if fine >= n else None


def stato_trend(prezzo, sma50, sma200):
    """1 = rialzista (prezzo e SMA 50 sopra la SMA 200), -1 = ribassista (entrambi sotto), 0 = laterale."""
    if not (sma50 and sma200):
        return None
    if prezzo > sma200 and sma50 > sma200:
        return 1
    if prezzo < sma200 and sma50 < sma200:
        return -1
    return 0


def tecnica(d):
    """v7.7 ANALISI TECNICA del titolo (chiusure giornaliere [(data, prezzo)]), calcolata qui sui prezzi
    dell'archivio (stesse formule dell'API tecnica di EODHD, senza chiamate in piu'):
      - SMA 50 / SMA 200 e TREND (stato_trend) con i giorni di borsa da cui dura;
      - RSI 14 (Wilder): sopra 70 ipercomprato, sotto 30 ipervenduto;
      - ATR 14 % sulle chiusure (abbiamo solo le chiusure): movimento medio di un giorno, media di Wilder delle
        variazioni assolute in %; utile per la distanza di uno stop;
      - posizione nel range di 52 settimane (0 = minimo, 100 = massimo)."""
    c = [v for _, v in d]
    if len(c) < 60:
        return None
    s50, s200 = _sma(c, 50), _sma(c, 200)
    tr = stato_trend(c[-1], s50, s200)
    gg = 0
    if tr is not None:                                  # da quanti giorni di borsa dura lo stato di oggi
        for i in range(len(c) - 1, 199, -1):
            if stato_trend(c[i], _sma(c, 50, i + 1), _sma(c, 200, i + 1)) != tr:
                break
            gg += 1
    var = [abs(c[i] / c[i - 1] - 1) * 100 for i in range(1, len(c)) if c[i - 1]]
    atr = sum(var[:14]) / 14 if len(var) >= 14 else None
    for x in var[14:]:
        atr = (atr * 13 + x) / 14
    ult = d[-1][0]
    anno = [v for x, v in d if x >= (date.fromisoformat(ult) - timedelta(days=365)).isoformat()]
    lo, hi = min(anno), max(anno)
    return {"sma50": round(s50, 4) if s50 else None, "sma200": round(s200, 4) if s200 else None,
            "tr": tr, "tr_gg": gg if tr is not None else None, "rsi": _rsi(c[-300:]),
            "atr": round(atr, 2) if atr is not None else None,
            "min52": lo, "max52": hi, "pos52": round((c[-1] - lo) / (hi - lo) * 100) if hi > lo else 50}


def stagionalita(m):
    """Stagionalita' mensile dallo storico mensile [(AAAA-MM, prezzo)]: per ogni mese di calendario rendimento
    medio, mediano, % di anni positivi e numero di anni. Il mese in corso (incompleto) e' escluso."""
    if not m or len(m) < 13:
        return None
    corrente = ora_italia().strftime("%Y-%m")
    r = {}
    # le barre mensili di Yahoo portano la chiusura di FINE mese: rendimento del mese b = chiusura b / chiusura a
    for (a, va), (b, vb) in zip(m, m[1:]):
        if b >= corrente:            # mese in corso: non ancora chiuso
            break
        if _mesi(b) - _mesi(a) != 1:  # buco o barra trimestrale: non e' il rendimento di UN mese, si salta
            continue
        r.setdefault(int(b[5:]), []).append(vb / va - 1)
    out = []
    for mese in range(1, 13):
        x = sorted(r.get(mese, []))
        if not x:
            out.append(None)
            continue
        med = x[len(x) // 2] if len(x) % 2 else (x[len(x) // 2 - 1] + x[len(x) // 2]) / 2
        out.append({"media": round(sum(x) / len(x) * 100, 2), "mediana": round(med * 100, 2),
                    "pos": round(100 * sum(v > 0 for v in x) / len(x)), "n": len(x)})
    return {"dal": m[0][0][:4], "mesi": out}


def pubblica(cartella, stato=None, titoli=None):
    """Scrive cartella/pubblico/: indice.json (tutti i titoli + indici + settori) e titoli/<T>.json.
    Usa SOLO le copie grezze: se oggi Yahoo non ha risposto, la scheda mostra gli ultimi dati con l'avviso."""
    el = titoli if titoli is not None else elenco()
    righe, dettagli, mensili = [], 0, {}
    for x in el:
        rec = _leggi(os.path.join(cartella, "grezzi", _nome_file(x["t"]) + ".json"))
        r = riassunto(rec) if rec else None
        if not r:
            continue
        stag = stagionalita(rec.get("m"))
        mese = (stag or {}).get("mesi", [None] * 12)[ora_italia().month - 1] if stag else None
        righe.append(dict({"t": x["t"], "n": rec.get("nome") or x["nome"], "s": x["s"], "l": x["l"],
                           "val": rec.get("valuta"), "st_media": mese and mese["media"], "st_pos": mese and mese["pos"],
                           "st_n": mese and mese["n"]}, **r))
        if x["t"] in DOPPIE:                   # v7.24 seconda quotazione: la tabella rimanda alla principale
            righe[-1]["dq"] = DOPPIE[x["t"]]
        try:                                   # v7.22 rendimento da dividendo (ultimi 12 mesi) al prezzo di oggi
            from . import dividendi
            righe[-1]["dy"] = dividendi.rendimento(cartella, x["t"], r.get("p"), rec.get("valuta"))
        except Exception:
            pass
        det = {"t": x["t"], "n": rec.get("nome") or x["nome"], "s": x["s"], "l": x["l"], "val": rec.get("valuta"),
               "borsa": rec.get("borsa"), "d": rec["d"], "m": rec.get("m") or [], "stag": stag,
               "tec": tecnica(rec["d"])}                                   # v7.7 analisi tecnica
        _scrivi(os.path.join(cartella, "pubblico", "titoli", _nome_file(x["t"]) + ".json"), det)
        mensili[x["t"]] = [v for _, v in (rec.get("m") or [])[:-1]]   # SMART DISCOUNT: solo mesi chiusi
        dettagli += 1
    indici = []
    for t, nome, l in INDICI:
        rec = _leggi(os.path.join(cartella, "grezzi", _nome_file(t) + ".json"))
        r = riassunto(rec) if rec else None
        if r:
            indici.append(dict({"t": t, "n": nome, "l": l, "val": rec.get("valuta")}, **r))
    punteggi(righe)
    try:                                       # v6.55 SMART DISCOUNT (sconto.py): mai bloccante per la scheda
        from . import sconto
        log.warning("smart discount: %d titoli valutati", sconto.calcola(mensili, righe))
    except Exception as e:
        log.warning("smart discount non calcolato (%s: %s)", type(e).__name__, e)
    top = vetrina(righe)
    ultimo = max((r["data"] for r in righe), default=None)
    indice = {"aggiornato": ultimo, "generato": ora_italia().strftime("%Y-%m-%d %H:%M"),
              "anomalia": (stato or {}).get("anomalia"),
              "settori": [{"id": i, "nome": n, "etf": e} for i, n, e in SETTORI],
              "listini": [{"id": k, "nome": v} for k, v in LISTINI.items()],
              "indici": indici, "titoli": righe, "top": [r["t"] for r in top]}
    _scrivi(os.path.join(cartella, "pubblico", "indice.json"), indice)
    # file piccolo per la vetrina della Dashboard (si carica all'apertura del terminale, ~3 KB)
    _scrivi(os.path.join(cartella, "pubblico", "top.json"),
            {"aggiornato": ultimo, "mese": ora_italia().month, "anomalia": indice["anomalia"],
             "settori": {i: n for i, n, _ in SETTORI}, "listini": LISTINI, "titoli": top,
             "sconto": in_sconto(righe, top), "ampiezza": ampiezza(righe),
             "economie": economie_borsa(righe, indici)})
    _scrivi(os.path.join(cartella, "stato.json"), dict(stato or {}, pubblicati=len(righe)))
    log.info("azioni: %d titoli pubblicati (%d schede dettaglio), dati al %s", len(righe), dettagli, ultimo)
    return indice


AREE_AMPIEZZA = (("USA", ("",)), ("Europa", ("MI", "DE", "PA", "AS", "MC", "BR", "HE")),
        ("Asia", ("T", "HK", "SS", "SZ", "NS", "BO")))


def ampiezza(righe):
    """v7.9 AMPIEZZA DEL MERCATO per la Dashboard: quanti titoli sono in trend rialzista / laterale / ribassista
    (stessa regola della freccia dell'Azionario: prezzo e SMA 50 contro SMA 200), in totale e per area."""
    def conta(rr):
        tr = [r.get("tr") for r in rr if r.get("tr") is not None]
        return {"su": sum(1 for x in tr if x == 1), "lat": sum(1 for x in tr if x == 0),
                "giu": sum(1 for x in tr if x == -1), "n": len(tr)}
    suff = lambda t: t.rsplit(".", 1)[1] if "." in t else ""
    return {"tot": conta(righe),
            "aree": [dict(conta([r for r in righe if suff(r["t"]) in s]), nome=n) for n, s in AREE_AMPIEZZA]}


# v7.21 BORSA PER ECONOMIA (sezione "Quadro economico" della Dashboard): per USA, Eurozona e Giappone, settore per
# settore, quanti titoli sono in trend rialzista e il punteggio medio, piu' gli indici della stessa economia.
# Regno Unito, Australia e Canada non hanno titoli nell'Azionario: la Dashboard mostra solo i loro dati economici.
ECONOMIE_BORSA = {"usa": (("",), ("^GSPC", "^NDX")),
                  "eur": (("MI", "DE", "PA", "AS", "MC", "BR", "HE"), ("^STOXX50E", "^GDAXI", "FTSEMIB.MI")),
                  "jpn": (("T",), ("^N225",)),
                  "gbr": (("L",), ("^FTSE",)), "can": (("TO",), ("^GSPTSE",)), "aus": (("AX",), ("^AXJO",))}


def economie_borsa(righe, indici):
    """{economia: {"settori": {id: {"n", "su", "pt"}}, "indici": [{"n", "tr", "v3m", "v1a"}]}}.
    su = titoli in trend rialzista (stessa freccia dell'Azionario), pt = punteggio medio 0-100 del settore."""
    suff = lambda t: t.rsplit(".", 1)[1] if "." in t else ""
    per_t = {i["t"]: i for i in indici}
    out = {}
    for eid, (suffissi, idx) in ECONOMIE_BORSA.items():
        settori = {}
        for r in righe:
            if suff(r["t"]) not in suffissi or r.get("tr") is None:
                continue
            s = settori.setdefault(r["s"], {"n": 0, "su": 0, "pt": 0})
            s["n"] += 1
            s["su"] += r["tr"] == 1
            s["pt"] += r.get("pt") or 0
        for s in settori.values():
            s["pt"] = round(s["pt"] / s["n"]) if s["n"] else None
        out[eid] = {"settori": settori,
                    "indici": [{"n": per_t[t]["n"], "tr": per_t[t].get("tr"), "v3m": per_t[t].get("v3m"),
                                "v1a": per_t[t].get("v1a")} for t in idx if t in per_t]}
    return out


def punteggi(righe):
    """Aggiunge a ogni riga 'pt' (0-100) e 'rk' (posizione). Un dato mancante vale il percentile mediano (50)."""
    n = len(righe)
    if not n:
        return righe
    perc = {}
    for k in PESI:
        val = sorted((r[k], i) for i, r in enumerate(righe) if r.get(k) is not None)
        for pos, (_, i) in enumerate(val):
            perc.setdefault(i, {})[k] = 100 * pos / max(1, len(val) - 1)
    for i, r in enumerate(righe):
        p = perc.get(i, {})
        r["pt"] = round(sum(w * p.get(k, 50) for k, w in PESI.items()))
    for pos, r in enumerate(sorted(righe, key=lambda x: -x["pt"])):
        r["rk"] = pos + 1
    return righe


def vetrina(righe, n=TOP_N):
    """I titoli piu' forti di oggi per la Dashboard: punteggio alto E condizioni tutte favorevoli
    (sopra la media a 200 giorni, 3 e 12 mesi positivi, mese in corso storicamente positivo in almeno il 60% degli
    anni con almeno 8 anni di storia, non piu' del 15% sotto il massimo a 52 settimane). Al massimo 1 per settore."""
    ok = [r for r in righe if acquistabile(r["t"]) and (r.get("t200") or -1) > 0 and (r.get("v3m") or -1) > 0 and (r.get("v1a") or -1) > 0
          and (r.get("st_media") or -1) > 0 and (r.get("st_pos") or 0) >= 60 and (r.get("st_n") or 0) >= MIN_ANNI_STAG
          and (r.get("dmax") or -100) > -15]
    out, settori = [], set()
    for r in sorted(ok, key=lambda x: -x["pt"]):
        if r["s"] in settori:
            continue
        settori.add(r["s"])
        out.append({k: r.get(k) for k in ("t", "n", "s", "l", "val", "p", "v1g", "v1m", "v3m", "v1a", "t200", "dmax",
                                          "st_media", "st_pos", "st_n", "pt", "rk", "sp")})
        if len(out) == n:
            break
    return out


def in_sconto(righe, top, n=SCONTO_N):
    """v6.66 TITOLI IN SCONTO per la Dashboard ("da tenere d'occhio", NON una selezione dei portafogli: nello studio
    lo Smart Discount usato come filtro toglieva rendimento). Regole fissate prima:
      - Smart Discount >= 60 (scontato rispetto alla SUA storia) e almeno -10% dal massimo delle ultime 12 chiusure;
      - non un crollo: sconto non oltre -35% (oltre di solito c'e' un problema dell'azienda, non uno sconto);
      - trend di fondo ancora sano: ultimi 12 mesi positivi;
      - in passato comprare a questo sconto e' andato almeno come comprare a caso (qualita' >= 50);
      - settori diversi tra loro e da quelli della vetrina (diversificazione); ordine per punteggio di sconto."""
    usati = {r["s"] for r in top}
    ok = [r for r in righe if acquistabile(r["t"]) and (r.get("sd") or 0) >= 60 and -35 <= (r.get("sdo") or 0) <= -10
          and (r.get("v1a") or -1) > 0 and (r.get("sdq") or 0) >= 50]
    out = []
    for r in sorted(ok, key=lambda x: (-x["sd"], -(x.get("pt") or 0))):
        if r["s"] in usati:
            continue
        usati.add(r["s"])
        out.append({k: r.get(k) for k in ("t", "n", "s", "l", "val", "p", "v1g", "v1a", "pt", "sd", "sdo", "sdr", "sdq",
                                          "sdn", "sdv", "sdb", "sdx", "sp")})
        if len(out) == n:
            break
    return out


# --------------------------------------------------------------------------- copia nel sito
def copia_nel_sito(out, ramo="azioni", cartella_locale=None):
    """Copia pubblico/ del ramo git "azioni" dentro <out>/azioni/ (lo fa il workflow del sito).
    Se il ramo non c'e' (primo giorno, PC senza git) non fa niente: la scheda mostra il suo stato vuoto."""
    import shutil
    import subprocess
    import tarfile
    import io
    dest = os.path.join(out, "azioni")
    if cartella_locale:                                   # prova sul PC: copia da una cartella gia' pronta
        src = os.path.join(cartella_locale, "pubblico")
        if os.path.isdir(src):
            shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(src, dest)
            return True
        return False
    try:
        subprocess.run(["git", "fetch", "-q", "--depth", "1", "origin", ramo], check=True, timeout=120,
                       capture_output=True)
        tar = subprocess.run(["git", "archive", "FETCH_HEAD", "pubblico"], check=True, timeout=120,
                             capture_output=True).stdout
        shutil.rmtree(dest, ignore_errors=True)
        with tarfile.open(fileobj=io.BytesIO(tar)) as tf:
            for m in tf.getmembers():
                if m.isfile() and m.name.startswith("pubblico/") and ".." not in m.name:
                    p = os.path.join(dest, m.name[len("pubblico/"):])
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                    with open(p, "wb") as fh:
                        fh.write(tf.extractfile(m).read())
        log.info("azioni: dati copiati nel sito (%s)", dest)
        return True
    except Exception as e:
        log.warning("azioni: ramo '%s' non disponibile (%s): la scheda Azioni mostra l'ultimo stato pubblicato",
                    ramo, type(e).__name__)
        return False


def main(argv):
    cartella = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else "dati_azioni"
    titoli = None
    if "--prova" in argv:
        titoli = elenco()[:12]
    # v6.86 --area asia|europa|usa: si scaricano solo i titoli di quell'area (gli altri restano alla copia del loro giro).
    # Senza --area (o "tutte", es. avvio a mano) si aggiornano tutti come prima.
    sel = argv[argv.index("--area") + 1] if "--area" in argv and argv.index("--area") + 1 < len(argv) else "tutte"
    sel = sel if sel in AREE else "tutte"
    tutti = [x["t"] for x in (titoli or elenco())] + [i[0] for i in INDICI]
    da_fare = tutti if sel == "tutte" else [t for t in tutti if area(t) == sel]
    try:                                       # v7.25 orari e festivita' delle borse (una volta a settimana)
        from . import orari_borse
        orari_borse.aggiorna(cartella)
    except Exception as e:
        log.warning("calendario borse non aggiornato (%s)", e)
    stato = aggiorna(cartella, da_fare, chiusura=CHIUSURA.get(sel, CHIUSURA_UTC))
    errore_giro = bool(stato.get("anomalia"))
    # STATO PER AREA: un giro riuscito toglie solo l'anomalia della SUA area; il popup/striscia resta finche' un'area
    # e' ancora indietro. stato.json conserva {aree: {asia: {...}, europa: {...}, usa: {...}}}.
    aree = (_leggi(os.path.join(cartella, "stato.json")) or {}).get("aree") or {}
    for a in (AREE if sel == "tutte" else (sel,)):
        aree[a] = {"quando": stato["quando"], "anomalia": stato.get("anomalia"), "ok": stato["ok"],
                   "mancati": len(stato["copia"]) + len(stato["falliti"])}
    # v6.95 AUTO-GUARIGIONE delle ALTRE aree: la loro anomalia si ricalcola dalle copie salvate (senza scaricare).
    # Se nel frattempo i dati sono freschi l'avviso sparisce; se un'area resta ferma troppo a lungo, si accende.
    for a in AREE:
        if a in aree and (sel != "tutte" and a != sel):
            aree[a]["anomalia"] = freschezza(cartella, [t for t in tutti if area(t) == a], CHIUSURA.get(a, CHIUSURA_UTC))
    stato["area"], stato["aree"] = sel, aree
    stato["anomalia"] = next((v["anomalia"] for v in aree.values() if v.get("anomalia")), None)
    if sel in ("usa", "tutte"):
        # v7.22 dividendi di ogni titolo (EODHD, una volta a settimana per titolo): mai bloccante.
        # v7.24 PRIMA di pubblica(): cosi' la colonna "Div." usa i dividendi appena scaricati (prima arrivava un giorno dopo)
        try:
            from . import dividendi
            dividendi.aggiorna(cartella, el=titoli)
        except Exception:
            import traceback
            log.error("dividendi dei titoli non aggiornati:\n%s", traceback.format_exc())
    pubblica(cartella, stato, titoli)
    if sel not in ("usa", "tutte"):
        # giri Asia/Europa: solo prezzi e scheda. 5 azioni scelte, bilanci SEC e profili restano al giro USA della sera
        # (le 5 azioni scelte devono decidere con TUTTI i prezzi del giorno, come prima).
        print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in stato.items()}, ensure_ascii=False))
        return 1 if errore_giro else 0
    # v7.26 grafici intraday "5 giorni" della scheda del titolo (intraday.py): una volta al giorno, mai bloccante
    try:
        from . import intraday
        intraday.aggiorna(cartella, el=titoli)
    except Exception as e:
        log.warning("intraday non aggiornato (%s)", e)
    # quota "Azioni scelte" dei portafogli modello (satellite.py): mai bloccante per la scheda Azionario
    try:
        from . import satellite
        satellite.calcola(cartella, titoli=titoli, anomalia=bool(stato.get("anomalia")))
    except Exception:
        import traceback
        log.error("satellite non calcolato:\n%s", traceback.format_exc())
    # bilanci delle aziende USA dalla SEC (fondamentali.py): una volta a settimana per titolo, mai bloccante
    try:
        from . import fondamentali
        fondamentali.aggiorna(cartella, el=titoli)
    except Exception:
        import traceback
        log.error("bilanci SEC non aggiornati:\n%s", traceback.format_exc())
    # v6.64 storico COMPLETO dei bilanci USA con le date di pubblicazione (per gli studi sulla qualita'): mai bloccante
    try:
        from . import fondamentali
        fondamentali.storia(cartella, el=titoli)
    except Exception:
        import traceback
        log.error("storico bilanci non aggiornato:\n%s", traceback.format_exc())
    # profilo delle aziende da Wikidata/Wikipedia (profili.py): ognuno al massimo una volta al mese, mai bloccante
    try:
        from . import profili
        profili.aggiorna(cartella, el=titoli)
    except Exception:
        import traceback
        log.error("profili aziende non aggiornati:\n%s", traceback.format_exc())
    # v7.15 ultime notizie di ogni titolo (EODHD, solo titoli e link): mai bloccante
    try:
        from . import notizie_az
        notizie_az.aggiorna(cartella, el=titoli)
    except Exception:
        import traceback
        log.error("notizie dei titoli non aggiornate:\n%s", traceback.format_exc())
    print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in stato.items()}, ensure_ascii=False))
    return 1 if errore_giro else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
