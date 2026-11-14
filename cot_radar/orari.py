# -*- coding: utf-8 -*-
"""
orari.py - v7.62 ARCHIVIO ORARIO (candele di 1 ora) per la STAGIONALITA' IN ORA DI ROMA.

COSA FA
  Scarica da EODHD (endpoint intraday) lo storico piu' lungo possibile e lo salva come CANDELE ORARIE IN UTC:
    - fino a ottobre 2020: barre da 1 MINUTO (le uniche cosi' vecchie: forex e crypto dal 2009, USA dal 2004),
      raggruppate qui in candele da 1 ora (apertura = primo minuto, chiusura = ultimo, massimo, minimo, minuti presenti);
    - da ottobre 2020: barre da 1 ORA gia' pronte (una sola richiesta copre fino a 7.200 giorni).
  Si salva in UTC e si converte in ora di Roma SOLO al momento del calcolo (stagionalita_orari.py): cosi' l'ora
  legale e' sempre giusta, anche negli anni passati e quando cambiano le regole (zoneinfo "Europe/Rome").
  Un'ora di Roma e' sempre un'ora intera UTC (+1 o +2): nessuna candela va spezzata.

FASI (in ordine di priorita', scelte con Ya il 13/11/2026)
  1 forex: 28 coppie delle 8 valute principali + oro e argento spot (simboli .FOREX)
  2 crypto: Bitcoin, Ether e le principali (simboli .CC)
  3 USA: ETF su indici, settori, obbligazioni e materie prime (.US), pre-mercato e after-hours inclusi
  4 indici ed estero: solo candele orarie da ottobre 2020 (storia breve, segnalata in pagina)

RIPRESA: lo stato (fin dove e' arrivato ogni simbolo) sta in <cartella>/_stato.json. Ogni giro lavora per un tempo
  massimo (--tempo) e riparte da dove si era fermato; quando lo storico e' completo aggiunge solo i giorni nuovi.
FILE: <cartella>/<SIMBOLO>.csv.gz  righe "ts,o,h,l,c,n" (ts = inizio dell'ora in secondi UTC, n = minuti presenti;
  n = 60 per le barre orarie gia' pronte).
CHIAVE: solo EODHD_API_KEY dai Secrets (eodhd.py non la scrive mai nei log).
USO: python -m cot_radar.orari <cartella> [--tempo 18000] [--fase 1]
"""
import csv
import gzip
import io
import json
import os
import sys
import time
from datetime import datetime, timezone

from . import eodhd
from .log import log

VALUTE = ["EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF", "JPY"]
FOREX = [a + b for i, a in enumerate(VALUTE) for b in VALUTE[i + 1:]]       # 28 coppie, nell'ordine del mercato
METALLI = ["XAUUSD", "XAGUSD"]          # v7.64 via platino e palladio: EODHD non ha candele orarie (0 scaricate)
CRYPTO = ["BTC-USD", "ETH-USD", "XRP-USD", "LTC-USD", "BCH-USD", "ADA-USD", "SOL-USD", "DOGE-USD", "BNB-USD"]
ETF_USA = ["SPY", "QQQ", "DIA", "IWM", "EFA", "EEM", "FXI", "EWJ", "EWG",            # indici
           "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC",   # settori
           "TLT", "IEF", "SHY", "HYG", "LQD",                                        # obbligazioni
           "GLD", "SLV", "USO", "UNG", "DBA", "CPER", "UUP"]                         # materie prime e dollaro
INDICI = ["GSPC.INDX", "NDX.INDX", "DJI.INDX", "GDAXI.INDX", "FCHI.INDX", "STOXX50E.INDX", "FTSE.INDX",
          "N225.INDX", "HSI.INDX", "FTSEMIB.INDX", "VIX.INDX"]

DAL_1M = int(datetime(2004, 1, 1, tzinfo=timezone.utc).timestamp())    # il piu' vecchio dato a 1 minuto (USA)
SOGLIA_1H = int(datetime(2020, 10, 1, tzinfo=timezone.utc).timestamp())  # da qui esistono le barre orarie
PEZZO_1M = 119 * 86400          # limite EODHD per l'intervallo 1m: 120 giorni a richiesta
PEZZO_1H = 7000 * 86400         # limite EODHD per l'intervallo 1h: 7.200 giorni a richiesta
VUOTI_MAX = 3                   # pezzi vuoti di fila prima di saltare avanti di un anno (simbolo nato dopo)


def universo(fase=None):
    """[(simbolo EODHD, fase, usa_1m)] nell'ordine di download. Fase 4: solo barre orarie (niente 1m garantito)."""
    out = [(p + ".FOREX", 1, True) for p in FOREX + METALLI]
    out += [(c + ".CC", 2, True) for c in CRYPTO]
    out += [(e + ".US", 3, True) for e in ETF_USA]
    out += [(i, 4, False) for i in INDICI]
    return [x for x in out if fase is None or x[1] == fase]


# --------------------------------------------------------------------------- candele
def a_ore(barre):
    """Barre EODHD [{timestamp, open, high, low, close}] -> {ora UTC: [o, h, l, c, n]} (n = barre unite)."""
    ore = {}
    for b in sorted(barre, key=lambda x: x.get("timestamp") or 0):
        try:
            ts = int(b["timestamp"])
            o, h, l, c = (float(b[k]) for k in ("open", "high", "low", "close"))
        except (KeyError, TypeError, ValueError):
            continue
        if not (o > 0 and c > 0 and h > 0 and l > 0):
            continue
        k = ts - ts % 3600
        x = ore.get(k)
        if x is None:
            ore[k] = [o, h, l, c, 1]
        else:
            x[1], x[2], x[3], x[4] = max(x[1], h), min(x[2], l), c, x[4] + 1
    return ore


def leggi(f):
    """{ts: [o, h, l, c, n]} dal file salvato ({} se non c'e')."""
    if not os.path.exists(f):
        return {}
    out = {}
    with gzip.open(f, "rt") as fh:
        for r in csv.reader(fh):
            if r and r[0] != "ts":
                out[int(r[0])] = [float(r[1]), float(r[2]), float(r[3]), float(r[4]), int(r[5])]
    return out


def utc_vero(sym, ore):
    """v7.65 CORREZIONE DEL FUSO DEL FOREX A 1 MINUTO. Le barre a 1 minuto di EODHD per i simboli .FOREX (fino a
    settembre 2020) hanno l'orologio di NEW YORK scritto come se fosse UTC: la settimana apre la domenica alle 17:00
    e i dati sul lavoro USA (8:30 di New York) cadono alle 8 tutto l'anno. Le barre orarie (da ottobre 2020), le
    crypto e gli ETF USA sono invece in UTC vero. Trovato da Ya il 14/11/2026 (EUR/GBP "aperto" la domenica alle 18
    di Roma) e verificato su 27 coppie: il profilo orario prima del 2020 era spostato di 4 ore rispetto a dopo.
    Qui le candele vecchie del forex vengono riportate all'UTC vero (+4 ore d'estate, +5 d'inverno, ora legale USA).
    L'archivio sul ramo "orari" resta com'e' (dato grezzo): la correzione si applica ogni volta che lo si legge."""
    if not sym.endswith(".FOREX"):
        return ore
    from zoneinfo import ZoneInfo
    ny, out = ZoneInfo("America/New_York"), {}
    for ts, v in ore.items():
        if ts < SOGLIA_1H:
            ts = int(datetime.fromtimestamp(ts, timezone.utc).replace(tzinfo=ny).timestamp())
        out.setdefault(ts, v)                            # l'ora doppia del cambio d'ora autunnale: resta la prima
    return out


def scrivi(f, ore):
    """Scrive le candele ordinate per ora (file temporaneo + rename: mai un file a meta')."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ts", "o", "h", "l", "c", "n"])
    for ts in sorted(ore):
        o, h, l, c, n = ore[ts]
        w.writerow([ts, f"{o:.6g}", f"{h:.6g}", f"{l:.6g}", f"{c:.6g}", n])
    tmp = f + ".tmp"
    with gzip.open(tmp, "wt") as fh:
        fh.write(buf.getvalue())
    os.replace(tmp, f)


def nome_file(cartella, sym):
    return os.path.join(cartella, sym.replace("/", "_") + ".csv.gz")


# --------------------------------------------------------------------------- download
def pezzo(sym, intervallo, da, a):
    """Barre EODHD di un pezzo di tempo. None se la richiesta fallisce (si riprova al giro dopo), [] se vuoto."""
    js = eodhd.get("intraday/" + sym, {"interval": intervallo, "from": da, "to": a}, timeout=180)
    if js is None:
        return None
    return js if isinstance(js, list) else []


def scarica_simbolo(cartella, sym, usa_1m, st, scadenza, ora=None):
    """Porta avanti un simbolo fino a 'scadenza' (time.time()). Aggiorna st (stato del simbolo). True = completo."""
    ora = ora or int(time.time())
    f = nome_file(cartella, sym)
    ore = leggi(f)
    nuove = 0
    # 1) storico a 1 minuto fino a ottobre 2020 (solo dove esiste)
    if usa_1m and not st.get("fatto_1m"):
        t = st.get("fino_1m", DAL_1M)
        vuoti = st.get("vuoti", 0)
        while t < SOGLIA_1H and time.time() < scadenza:
            b = pezzo(sym, "1m", t, min(t + PEZZO_1M, SOGLIA_1H))
            if b is None:
                break                                   # errore: si riprende da qui al prossimo giro
            if b:
                ore.update(a_ore(b))
                nuove += len(b)
                vuoti = 0
            else:
                vuoti += 1
            t = min(t + PEZZO_1M, SOGLIA_1H)
            if vuoti >= VUOTI_MAX and not ore:          # nessun dato ancora: il simbolo nasce dopo, si salta avanti
                t, vuoti = min(t + 365 * 86400, SOGLIA_1H), 0
            st["fino_1m"], st["vuoti"] = t, vuoti
        if t >= SOGLIA_1H:
            st["fatto_1m"] = True
    # 2) barre orarie da ottobre 2020 (o dall'ultima ora salvata) a oggi
    if (st.get("fatto_1m") or not usa_1m) and time.time() < scadenza:
        t = max(st.get("fino_1h", SOGLIA_1H), SOGLIA_1H)
        t = max(t - 2 * 86400, SOGLIA_1H)               # riprende 2 giorni prima: l'ultima ora era forse incompleta
        while t < ora and time.time() < scadenza:
            b = pezzo(sym, "1h", t, min(t + PEZZO_1H, ora))
            if b is None:
                break
            for k, v in a_ore(b).items():               # una barra oraria gia' pronta = 60 minuti
                ore[k] = v[:4] + [60]
            nuove += len(b)
            t = min(t + PEZZO_1H, ora)
            st["fino_1h"] = t
    if nuove:
        scrivi(f, ore)
    st["candele"] = len(ore)
    if ore:
        st["dal"], st["al"] = min(ore), max(ore)
    st["completo"] = bool(st.get("fatto_1m") or not usa_1m) and st.get("fino_1h", 0) >= ora - 86400
    return st["completo"]


def aggiorna(cartella, tempo=18000, fase=None, ora=None):
    """Un giro di download entro 'tempo' secondi. Restituisce lo stato complessivo."""
    os.makedirs(cartella, exist_ok=True)
    f_st = os.path.join(cartella, "_stato.json")
    stato = json.load(open(f_st)) if os.path.exists(f_st) else {}
    scadenza = time.time() + tempo
    for sym, fs, usa_1m in universo(fase):
        if time.time() >= scadenza:
            break
        st = stato.setdefault(sym, {"fase": fs})
        if st.get("assente"):                           # EODHD non ha il simbolo: non si richiede piu'
            continue
        err0 = eodhd.CHIAMATE["errori"]
        try:
            scarica_simbolo(cartella, sym, usa_1m, st, scadenza, ora)
        except Exception as e:                          # un simbolo rotto non ferma gli altri
            log.warning("orari %s: %s", sym, type(e).__name__)
        if eodhd.CHIAMATE["errori"] > err0 and not st.get("candele"):
            st["errori"] = st.get("errori", 0) + 1      # 3 giri di fila senza un dato = simbolo assente
            st["assente"] = st["errori"] >= 3
        st["agg"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        with open(f_st + ".tmp", "w") as fh:            # stato salvato dopo ogni simbolo: ripresa sicura
            json.dump(stato, fh, indent=0, sort_keys=True)
        os.replace(f_st + ".tmp", f_st)
        log.info("orari %s: %s candele, completo=%s", sym, st.get("candele"), st.get("completo"))
    log.info("orari: chiamate EODHD %d (errori %d)", eodhd.CHIAMATE["n"], eodhd.CHIAMATE["errori"])
    return stato


def main(argv):
    cartella = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else "dati_orari"
    tempo = int(argv[argv.index("--tempo") + 1]) if "--tempo" in argv else 18000
    fase = int(argv[argv.index("--fase") + 1]) if "--fase" in argv else None
    from .log import setup                              # messaggi a schermo (log di GitHub Actions)
    setup()
    if not eodhd.attivo():
        log.error("orari: manca EODHD_API_KEY")
        return 1
    aggiorna(cartella, tempo, fase)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
