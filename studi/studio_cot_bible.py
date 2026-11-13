# -*- coding: utf-8 -*-
"""
studio_cot_bible.py - IL METODO DEL LIBRO "THE COMMITMENTS OF TRADERS BIBLE" (Stephen Briese, 2008), MESSO ALLA PROVA
(richiesta di Ya, 13/11/2026). Solo offline: nessun download, dati gia' archiviati dal sito (ramo "storico").

REGOLE FISSATE PRIMA DI GUARDARE I RISULTATI (prese dal libro, capitoli 6, 7 e 9):
  COT Index (cap. 6)      = 100 x (netto attuale - minimo) / (massimo - minimo) del netto del gruppo nelle ultime
                            156 settimane (3 anni, il periodo "standard" del libro). Netto = long - short (appendice A, es. 1).
  Movement Index (cap. 7) = COT Index di oggi - COT Index di 6 settimane fa (il libro usa 6).
  S1 ESTREMI COMMERCIAL   compra quando il COT Index dei commercial entra sopra 90, vendi quando entra sotto 5.
  S2 SURGE COMMERCIAL     compra quando il Movement Index dei commercial arriva a +40, vendi a -40.
  S3 ESTREMI + TREND      come S1, ma in rialzo (prezzo sopra la media a 200 giorni) solo acquisti, in ribasso solo
                          vendite: "in un trend rialzista i segnali di vendita COT sono prematuri" (cap. 6).
  S4 SURGE + TREND        come S2 con lo stesso filtro: le regole dei 40 punti valgono "nel verso del trend" (cap. 7).
  S5 FONDI MEDIE MOBILI   (cap. 9) due medie mobili (in giorni di borsa) del COT Index dei grandi speculatori:
                          media veloce sopra la lenta = lungo, sotto = corto, sempre a mercato. Il libro sceglie la coppia
                          migliore mercato per mercato SULLO STESSO PERIODO che misura (tabella 9.1, senza costi): qui la
                          coppia si sceglie solo sul periodo di studio e si misura sulla verifica (walk-forward onesto).
  Un segnale S1-S4 nasce solo all'INGRESSO nella zona (la settimana dopo, se resta nella zona, non e' un segnale nuovo).
  Tenuta: 1, 2, 4 e 8 settimane (Wang, citato al cap. 8: rendimenti fino a 8 settimane). Principale = 4 settimane.

TEMPI (ora di Roma): il COT fotografa il martedi' e la CFTC lo pubblica il venerdi' alle 15:30 di New York
  (21:30 a Roma, 20:30 nelle settimane in cui l'ora legale USA ed europea non coincidono). Se c'e' una festivita'
  federale USA tra il lunedi' della settimana del dato e il venerdi', la pubblicazione slitta al lunedi' dopo.
  Ingresso = APERTURA della prima candela giornaliera DOPO la pubblicazione (forex: candela del lunedi', che apre
  all'01:00 di Roma, 02:00 con l'ora legale). Dove esiste solo la chiusura (future di cereali, soft, bestiame, tassi,
  ETF), ingresso = CHIUSURA della prima seduta dopo la pubblicazione (un giorno in piu' di ritardo: piu' prudente).
  Uscita: stessa misura (apertura o chiusura) della prima seduta a 7 x H giorni dall'ingresso.
  Settimane con pubblicazione fuori calendario (chiusure del governo USA 2013, 2018-19, 2025): ESCLUSE (date di uscita
  reali non note -> rischio di usare dati prima che fossero pubblici).
COSTI: stessi del sito (motore.py: forex 0,02%, peso messicano 0,15%, indici ed ETF 0,05%, energia 0,08%, gas 0,20%,
  materie prime e tassi 0,10%, crypto 0,20%) andata e ritorno, per operazione.
PERIODI: studio fino al 31/12/2014, verifica dal 2015 (mai usata per scegliere nulla).
CONFRONTO CON IL CASO: stessi ingressi e stesse durate con verso casuale (1.000 estrazioni): quante volte il caso fa
  meglio = "p" (sotto 0,05 = probabilmente non e' fortuna).
STRESS TEST: costi doppi, ingresso un giorno dopo, finestra 26 e 52 settimane, soglie 80/20, periodi di 5 anni,
  per classe di mercato, senza il mercato migliore.
LIMITI DICHIARATI: i future continui di Yahoo (=F) NON sono "back-adjusted": al cambio di contratto il prezzo salta e
  quel salto non e' un guadagno vero (il libro usa serie aggiustate). Per questo i risultati sono dati anche
  separatamente per i mercati con salti di roll e con lo stress "salti tagliati". I prezzi forex sono quelli di Yahoo.
USO: python studi/studio_cot_bible.py <cartella dati>   (COT.csv, yahoo/*.csv, DEXMXUS.csv, pat/*.json.gz)
"""
import csv
import gzip
import json
import math
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone

# --------------------------------------------------------------------------- mercati
# chiave: (codice CFTC, fonte prezzi, segno, classe, costo %, ha_apertura)
#   fonte "pat:XXX" = candele giornaliere OHLC salvate; "y:XXX" = chiusure Yahoo; "fred:XXX" = chiusure FRED
#   segno -1 = il future e' sulla valuta contro il dollaro ma la coppia quotata e' USD/valuta (es. USDJPY)
M = {
    "EUR": ("099741", "pat:EURUSD", 1, "valute", 0.02), "GBP": ("096742", "pat:GBPUSD", 1, "valute", 0.02),
    "JPY": ("097741", "pat:USDJPY", -1, "valute", 0.02), "CHF": ("092741", "pat:USDCHF", -1, "valute", 0.02),
    "CAD": ("090741", "pat:USDCAD", -1, "valute", 0.02), "AUD": ("232741", "pat:AUDUSD", 1, "valute", 0.02),
    "NZD": ("112741", "pat:NZDUSD", 1, "valute", 0.02), "MXN": ("095741", "fred:DEXMXUS", -1, "valute", 0.15),
    "DXY": ("098662", "y:UUP", 1, "valute", 0.05),
    "SP500": ("13874A", "y:_GSPC", 1, "indici", 0.05), "NASDAQ": ("209742", "y:QQQ", 1, "indici", 0.05),
    "DOW": ("124603", "y:DIA", 1, "indici", 0.05), "RUSSELL": ("239742", "y:IWM", 1, "indici", 0.05),
    "EAFE": ("244041", "y:EFA", 1, "indici", 0.05), "EM": ("244042", "y:EEM", 1, "indici", 0.05),
    "US2Y": ("042601", "y:ZT=F", 1, "tassi", 0.10), "US5Y": ("044601", "y:ZF=F", 1, "tassi", 0.10),
    "US10Y": ("043602", "y:ZN=F", 1, "tassi", 0.10), "USBOND": ("020601", "y:ZB=F", 1, "tassi", 0.10),
    "WTI": ("067651", "pat:WTI", 1, "energia", 0.08), "BRENT": ("06765T", "pat:BRENT", 1, "energia", 0.08),
    "NATGAS": ("023651", "pat:NATGAS", 1, "energia", 0.20), "HEATOIL": ("022651", "y:HO=F", 1, "energia", 0.08),
    "GASOLINE": ("111659", "y:RB=F", 1, "energia", 0.08),
    "GOLD": ("088691", "pat:XAUUSD", 1, "metalli", 0.10), "SILVER": ("084691", "pat:XAGUSD", 1, "metalli", 0.10),
    "COPPER": ("085692", "pat:COPPER", 1, "metalli", 0.10), "PLATINUM": ("076651", "pat:PLATINUM", 1, "metalli", 0.10),
    "PALLADIUM": ("075651", "y:PA=F", 1, "metalli", 0.10),
    "CORN": ("002602", "y:ZC=F", 1, "agricoli", 0.10), "SOY": ("005602", "y:ZS=F", 1, "agricoli", 0.10),
    "SOYOIL": ("007601", "y:ZL=F", 1, "agricoli", 0.10), "SOYMEAL": ("026603", "y:ZM=F", 1, "agricoli", 0.10),
    "WHEAT": ("001602", "y:ZW=F", 1, "agricoli", 0.10), "KCWHEAT": ("001612", "y:KE=F", 1, "agricoli", 0.10),
    "SUGAR": ("080732", "y:SB=F", 1, "agricoli", 0.10), "COFFEE": ("083731", "y:KC=F", 1, "agricoli", 0.10),
    "COCOA": ("073732", "y:CC=F", 1, "agricoli", 0.10), "COTTON": ("033661", "y:CT=F", 1, "agricoli", 0.10),
    "OJ": ("040701", "y:OJ=F", 1, "agricoli", 0.10),
    "CATTLE": ("057642", "y:LE=F", 1, "bestiame", 0.10), "FEEDER": ("061641", "y:GF=F", 1, "bestiame", 0.10),
    "HOGS": ("054642", "y:HE=F", 1, "bestiame", 0.10),
    "BTC": ("133741", "y:BTC-USD", 1, "crypto", 0.20),
}
FINE_STUDIO = date(2014, 12, 31)
ORIZZ = (1, 2, 4, 8)
PRINC = 4
# chiusure del governo USA: pubblicazioni COT arretrate con date d'uscita non note -> settimane escluse
ESCLUSE = [(date(2013, 9, 30), date(2013, 11, 22)), (date(2018, 12, 17), date(2019, 3, 8)),
           (date(2025, 9, 29), date(2026, 1, 30))]


# --------------------------------------------------------------------------- festivita' federali USA (calendario CFTC)
def _nesimo(anno, mese, giorno_sett, n):
    """n-esimo giorno della settimana del mese (lun=0); n=-1 = ultimo."""
    if n > 0:
        d = date(anno, mese, 1)
        d += timedelta(days=(giorno_sett - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    d = date(anno + (mese == 12), mese % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - giorno_sett) % 7)


def _osservato(d):
    """Festa che cade di sabato -> venerdi'; di domenica -> lunedi'."""
    return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d


def festivita(anno):
    f = {_osservato(date(anno, 1, 1)), _nesimo(anno, 1, 0, 3), _nesimo(anno, 2, 0, 3), _nesimo(anno, 5, 0, -1),
         _osservato(date(anno, 7, 4)), _nesimo(anno, 9, 0, 1), _nesimo(anno, 10, 0, 2), _osservato(date(anno, 11, 11)),
         _nesimo(anno, 11, 3, 4), _osservato(date(anno, 12, 25))}
    if anno >= 2021:
        f.add(_osservato(date(anno, 6, 19)))
    return f


FEST = set()
for _a in range(1985, 2028):
    FEST |= festivita(_a)


def pubblicazione(rap):
    """Data (New York) in cui il COT del martedi' `rap` e' uscito: venerdi', o lunedi' dopo se c'e' una festa federale
    tra il lunedi' della settimana del dato e il venerdi'. None nelle settimane escluse."""
    if any(a <= rap <= b for a, b in ESCLUSE):
        return None
    ven = rap + timedelta(days=(4 - rap.weekday()) % 7)
    lun = rap - timedelta(days=rap.weekday())
    if any(lun + timedelta(days=k) in FEST for k in range(5)):
        return ven + timedelta(days=3)
    return ven


# --------------------------------------------------------------------------- dati
def leggi_cot(f):
    """{codice: [(data rapporto, netto commercial, netto grandi speculatori, open interest)]} in ordine di data."""
    per = {}
    for r in csv.DictReader(open(f)):
        try:
            per.setdefault(r["cftc_contract_market_code"].strip(), {})[date.fromisoformat(r["report_date_as_yyyy_mm_dd"][:10])] = (
                float(r["comm_positions_long_all"]) - float(r["comm_positions_short_all"]),
                float(r["noncomm_positions_long_all"]) - float(r["noncomm_positions_short_all"]),
                float(r["open_interest_all"]))
        except (KeyError, ValueError):
            continue
    return {c: [(d,) + v[d] for d in sorted(v)] for c, v in per.items()}


def leggi_prezzi(cart, fonte):
    """[(data, apertura o None, chiusura)] in ordine. Le candele salvate hanno l'ora 00:00 UTC del giorno."""
    tipo, nome = fonte.split(":", 1)
    out = []
    if tipo == "pat":
        x = json.load(gzip.open(os.path.join(cart, "pat", nome + ".json.gz"), "rt"))
        for ts, o, h, l, c in x["d"]:
            if o and c:
                out.append((datetime.fromtimestamp(ts, tz=timezone.utc).date(), float(o), float(c)))
    else:
        f = os.path.join(cart, "yahoo", nome + ".csv") if tipo == "y" else os.path.join(cart, nome + ".csv")
        for r in csv.DictReader(open(f)):
            try:
                v = float(r.get("valore") or r.get(nome) or "")
            except ValueError:
                continue
            if v > 0:
                out.append((date.fromisoformat(r["data"]), None, v))
    out.sort()
    # una sola riga per giorno
    pul = []
    for x in out:
        if pul and pul[-1][0] == x[0]:
            pul[-1] = x
        else:
            pul.append(x)
    return pul


def taglia_salti(px, k=5.0):
    """Stress "salti tagliati": un giorno con movimento oltre k volte la mediana dei movimenti degli ultimi 60 giorni
    (tipico salto di roll dei future Yahoo non aggiustati) viene annullato spostando tutta la serie successiva."""
    out, fatt, mv = [], 1.0, []
    for i, (d, o, c) in enumerate(px):
        if i:
            r = c / px[i - 1][2] - 1
            med = sorted(mv[-60:])[len(mv[-60:]) // 2] if len(mv) >= 20 else None
            if med and abs(r) > k * med:
                fatt *= px[i - 1][2] / c                # elimina il salto: la chiusura resta quella di ieri
            mv.append(abs(r))
        out.append((d, o * fatt if o else None, c * fatt))
    return out


# --------------------------------------------------------------------------- indicatori del libro
def cot_index(v, t, n):
    w = v[max(0, t - n + 1): t + 1]
    lo, hi = min(w), max(w)
    return 50.0 if hi == lo else 100 * (v[t] - lo) / (hi - lo)


def sma(v, n):
    out, s = [], 0.0
    for i, x in enumerate(v):
        s += x
        if i >= n:
            s -= v[i - n]
        out.append(s / n if i >= n - 1 else None)
    return out


def sma_vuoti(v, n):
    """Media mobile che ignora i giorni iniziali senza dato (None): None finche' la finestra non e' piena di dati."""
    out, w = [], []
    for x in v:
        if x is None:
            w = []
            out.append(None)
            continue
        w.append(x)
        if len(w) > n:
            w.pop(0)
        out.append(sum(w) / n if len(w) == n else None)
    return out


