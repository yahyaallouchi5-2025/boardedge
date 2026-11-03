# -*- coding: utf-8 -*-
"""
tattica.py - LETTURA TATTICA dei mercati COT (v6.88): regressione e indicatori tecnici, SOLO INFORMATIVI.

PERCHE' INFORMATIVA: negli studi offline (tools/studio_sistema.py, 02/11/2026) RSI, momentum e pattern NON hanno
aggiunto vantaggio ai segnali COT. Quindi qui si MOSTRA dove si trova il prezzo, ma nulla entra nel punteggio o nei
segnali. Per usarli nei segnali andrebbero prima verificati sul registro live.

DATI: stesse serie di chiusura giornaliera della volatilita' (storico.prezzi_usd: FRED + Yahoo), coppie costruite
come in stagionalita.prezzo_coppia. LIMITE: abbiamo solo la CHIUSURA, quindi niente ADX e ATR "veri" (servono massimo
e minimo del giorno): al loro posto la forza del trend si legge dall'R2 della regressione e la volatilita' dal
movimento medio giornaliero da chiusura a chiusura.

INDICATORI (ultimo giorno disponibile, nessun dato futuro):
  canale  regressione lineare sul LOGARITMO del prezzo delle ultime 100 sedute (~5 mesi):
          pend = pendenza annua in % (252 sedute), r2 = quanto il prezzo segue la retta (0-1, trend "pulito" >= 0,6),
          z = distanza del prezzo dalla retta in deviazioni standard dei residui (canale = +-2), pos = 0-100 nel canale
  rsi     RSI a 14 sedute di Wilder (>= 70 ipercomprato, <= 30 ipervenduto)
  d200    distanza % dalla media mobile a 200 sedute
  mov     movimento medio giornaliero in % (media dei valori assoluti delle ultime 20 variazioni)
Le etichette (txt_*) sono brevi; la spiegazione sta nel fumetto (i) del sito.
DEBUG: python -m unittest tests.test_tattica -v
"""
import math

from .log import log
from .volatilita import strumenti_con_prezzo

FINESTRA_REG = 100        # sedute della regressione (canale)
RSI_N = 14
MEDIA_LUNGA = 200
MOV_N = 20
R2_PULITO = 0.6           # sopra: trend pulito; sotto 0,3: nessun trend


def regressione(valori):
    """Retta sui log-prezzi -> (pendenza annua %, r2, z dell'ultimo prezzo) oppure None."""
    y = [math.log(v) for v in valori if v and v > 0]
    n = len(y)
    if n < 30:
        return None
    mx, my = (n - 1) / 2, sum(y) / n
    sxx = sum((i - mx) ** 2 for i in range(n))
    b = sum((i - mx) * (y[i] - my) for i in range(n)) / sxx
    a = my - b * mx
    res = [y[i] - (a + b * i) for i in range(n)]
    sres = math.sqrt(sum(r * r for r in res) / (n - 2))
    stot = sum((v - my) ** 2 for v in y)
    r2 = 1 - sum(r * r for r in res) / stot if stot > 0 else 0.0
    z = res[-1] / sres if sres > 0 else 0.0
    return (math.exp(b * 252) - 1) * 100, max(0.0, r2), z


def rsi(valori, n=RSI_N):
    """RSI di Wilder sull'ultima seduta (None con meno di n+1 prezzi)."""
    if len(valori) <= n:
        return None
    d = [valori[i] - valori[i - 1] for i in range(1, len(valori))]
    su = sum(max(x, 0) for x in d[:n]) / n
    giu = sum(max(-x, 0) for x in d[:n]) / n
    for x in d[n:]:
        su = (su * (n - 1) + max(x, 0)) / n
        giu = (giu * (n - 1) + max(-x, 0)) / n
    if giu == 0:
        return 100.0
    return 100 - 100 / (1 + su / giu)


def lettura(pts):
    """[(data, prezzo)] -> indicatori dell'ultima seduta o None se lo storico e' troppo corto."""
    v = [p for _, p in pts if p]
    if len(v) < MEDIA_LUNGA + 1:
        return None
    reg = regressione(v[-FINESTRA_REG:])
    r = rsi(v[-300:])
    m200 = sum(v[-MEDIA_LUNGA:]) / MEDIA_LUNGA
    mov = sum(abs(v[i] / v[i - 1] - 1) for i in range(len(v) - MOV_N, len(v))) / MOV_N * 100
    if not reg or r is None:
        return None
    pend, r2, z = reg
    txt_canale = ("parte alta del canale" if z >= 1.5 else "parte bassa del canale" if z <= -1.5
                  else "sopra la retta" if z >= 0.5 else "sotto la retta" if z <= -0.5 else "sulla retta")
    txt_trend = ("nessun trend" if r2 < 0.3 else
                 ("trend rialzista" if pend > 0 else "trend ribassista") + (" pulito" if r2 >= R2_PULITO else " debole"))
    txt_rsi = "ipercomprato" if r >= 70 else "ipervenduto" if r <= 30 else "neutro"
    return {"data": pts[-1][0], "pend": round(pend, 1), "r2": round(r2, 2), "z": round(z, 2),
            "pos": round(min(100.0, max(0.0, (z + 2) / 4 * 100))), "rsi": round(r), "d200": round((v[-1] / m200 - 1) * 100, 1),
            "mov": round(mov, 2), "txt_canale": txt_canale, "txt_trend": txt_trend, "txt_rsi": txt_rsi}


def calcola(pairs, prezzi):
    """{strumento o coppia: lettura}. Isolato: se uno strumento fallisce, gli altri restano."""
    out = {}
    for nome, pts in strumenti_con_prezzo(pairs, prezzi).items():
        try:
            x = lettura(pts)
            if x:
                out[nome] = x
        except Exception as e:                     # noqa: BLE001 - un mercato non deve fermare gli altri
            log.warning("lettura tattica di %s non calcolata: %s", nome, e)
    return out


# --------------------------------------------------------------------------- v6.89 FORZA DELLE VALUTE
# Per il riepilogo del grafico: "EUR forte / USD debole". Ogni valuta principale contro tutte le altre nelle ultime
# 4 settimane (20 sedute comuni): rendimento in dollari meno la media di tutte (il dollaro vale 0 contro se stesso).
# Classifica su 8 valute: le prime 3 = "forte", le ultime 3 = "debole", le 2 in mezzo = "neutra". Solo informativa.
VALUTE = ("EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
FORZA_N = 20


def forza(prezzi, n=FORZA_N):
    """{valuta: {"r": forza %, "rank": 1-8, "stato": forte/neutra/debole}} oppure {} se mancano i prezzi."""
    serie = {v: dict(prezzi[v]) for v in VALUTE if prezzi.get(v)}
    if len(serie) < len(VALUTE):
        return {}
    comuni = sorted(set.intersection(*(set(s) for s in serie.values())))
    if len(comuni) <= n:
        return {}
    d0, d1 = comuni[-n - 1], comuni[-1]
    r = {v: math.log(s[d1] / s[d0]) * 100 for v, s in serie.items()}
    r["USD"] = 0.0
    media = sum(r.values()) / len(r)
    forze = {v: x - media for v, x in r.items()}
    ordine = sorted(forze, key=lambda v: -forze[v])
    return {v: {"r": round(forze[v], 2), "rank": ordine.index(v) + 1,
                "stato": "forte" if ordine.index(v) < 3 else "debole" if ordine.index(v) >= len(ordine) - 3 else "neutra",
                "dal": d0, "al": d1} for v in forze}
