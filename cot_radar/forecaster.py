# -*- coding: utf-8 -*-
"""
forecaster.py - FORECASTER: previsioni e varianti dei portafogli registrate PRIMA di ogni mese e verificate DOPO.

PERCHE': ogni idea "se avessimo fatto X..." guardata a mese chiuso sembra sempre migliore (senno di poi). L'unico
giudice onesto e' il FUTURO: si scrive cosa si prevede e come si investirebbe prima che il mese cominci, poi si
misura. Le regole sono fissate qui una volta per tutte (niente ritocchi dopo aver visto i risultati).

COSA SI REGISTRA (una riga per mese nel registro, alla rotazione: decisa sulla chiusura dell'ultimo giorno del mese
prima, eseguita all'apertura del primo giorno di borsa):
  1) PREVISIONI per ogni mercato dei portafogli (direzione del mese: +1 rialzo, -1 ribasso, 0 nessuna):
       - stagionalita': solo i mesi "robusti" per i filtri di stagionalita.mesi() (>= 10 anni, trend tolto,
         stabile nel tempo, test t); dati fino alla decisione
       - COT: etichetta del punteggio COT gia' pubblicato (BUY/SELL e STRONG; NEUTRO = nessuna previsione)
       - modello: regressione lineare con coefficienti RISTRETTI (ridge) addestrata ogni mese solo sui mesi passati
         di tutti i mercati insieme. Ingressi fissati prima: punteggio COT, distanza dalla media a 200 giorni,
         momento 12-1 mesi, stagionalita' del mese. Uscita: rendimento atteso del mese
  2) SFIDANTI: come sarebbero i 3 portafogli con una regola diversa (elenco chiuso, SFIDANTI sotto), confrontati
     con il portafoglio attuale ("campione"). Ogni mese ogni variante tiene i pesi fissati all'inizio (come chi
     investe e non tocca nulla fino alla rotazione dopo); costo 0,10% sul capitale scambiato dal mese prima.

VERIFICA a mese chiuso (riga "esito"): rendimento di ogni mercato e di ogni sfidante.
  - precisione delle previsioni: % di direzioni giuste, confrontata con "sempre rialzo" sugli stessi mercati
    (i mercati salgono piu' spesso di quanto scendano: battere il 50% non basta). Giudizio dopo MIN_PREV previsioni
  - sfidanti: differenza mensile con il campione, intervallo con z = 2,58. Giudizio dopo MIN_MESI mesi

REGISTRO: storico/forecaster/registro.jsonl (ramo "storico", salvato con la cronologia git: ogni riga ha data e ora
verificabili). Righe in CATENA: ogni riga contiene l'impronta (sha256) della precedente, quindi una riga cambiata
dopo si vede subito. Le righe non si riscrivono mai.

DEBUG: python -m unittest tests.test_forecaster -v
"""
import hashlib
import json
import math
import os
from datetime import date, datetime, timedelta, timezone
from statistics import mean, median, pstdev

from .config import ROOT
from .cot import label
from .log import log
from . import portafogli as P
from . import stagionalita as SG

CARTELLA = os.path.join(ROOT, "storico", "forecaster")
FILE = "registro.jsonl"
DAL = "2026-11"                 # primo mese registrato
INCLINA = 0.20                  # sfidanti "inclinati": peso del mercato x 1,20 o x 0,80
ORO_IN_PIU = 0.05               # sfidante "oro": +5 punti di oro
MIN_MESI = 12                   # mesi minimi prima del giudizio sugli sfidanti
MIN_PREV = 60                   # previsioni minime prima del giudizio sulla precisione
Z = 2.58                        # intervallo al 99% (stesso rigore degli altri studi del sito)
ANNI_STAG_MODELLO = 5           # anni minimi per la stagionalita' usata dal modello
APERTURA_UTC = (13, 30)         # apertura di Wall Street (ora UTC, ora legale): oltre = registrazione in ritardo
PROVA = "https://github.com/yahyaallouchi5-2025/cot-radar/commits/storico/forecaster/registro.jsonl"

MERCATI = [u[0] for u in P.UNIVERSO]
SFIDANTI = [
    ("campione", "Portafoglio attuale", "Le regole del sito oggi: il riferimento da battere."),
    ("az10", "Azioni: 10 titoli senza limite per settore",
     "La quota Azioni scelte con 10 titoli invece di 5 e senza il limite di 1 per settore (l'unica alternativa "
     "emersa dallo studio sulle azioni)."),
    ("senza_az", "Senza quota azioni",
     "Nessuna azione singola: la quota va nella base di ETF. Misura quanto contribuiscono davvero le 5 azioni."),
    ("oro", "+5% di oro",
     "Cinque punti in più di oro, presi dalla liquidità (se non basta, dalle altre posizioni in proporzione)."),
    ("stag", "Inclinazione stagionale",
     "Peso x 1,20 sui mercati con stagionalità robusta al rialzo nel mese, x 0,80 al ribasso; la differenza va "
     "o viene dalla liquidità."),
    ("modello", "Inclinazione del modello",
     "Peso x 1,20 sui mercati con previsione del modello sopra la media dei mercati, x 0,80 sotto."),
]


# --------------------------------------------------------------------------- calendario
def _mese_dopo(ym, n=1):
    a, m = int(ym[:4]), int(ym[5:7]) - 1 + n
    return f"{a + m // 12:04d}-{m % 12 + 1:02d}"


def ultimo_feriale(ym):
    """Ultimo giorno feriale del mese (le festivita' di borsa non sono considerate)."""
    d = date.fromisoformat(_mese_dopo(ym) + "-01") - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


def fine_mesi(g):
    """{'AAAA-MM': indice dell'ultimo giorno di borsa del mese nella griglia}."""
    out = {}
    for i, d in enumerate(g.date):
        out[d[:7]] = i
    return out


def mese_da_registrare(g):
    """(mese M da prevedere, indice del giorno di decisione = ultima chiusura del mese prima).
    Se l'ultimo mese dei prezzi e' completo si prevede il mese dopo; altrimenti (prezzi gia' dentro al mese nuovo)
    il mese in corso, sempre con i soli dati fino alla chiusura del mese prima."""
    ult = g.date[-1][:7]
    if g.date[-1] >= ultimo_feriale(ult):
        return _mese_dopo(ult), len(g.date) - 1
    fm = fine_mesi(g)
    prima = _mese_dopo(ult, -1)
    return (ult, fm[prima]) if prima in fm else (None, None)


# --------------------------------------------------------------------------- previsioni
def _prezzi(g, k, fino):
    """[(data, prezzo)] del mercato k fino all'indice 'fino' compreso (solo dati noti alla decisione)."""
    col = g.p.get(P.TUTTI[k][1]) or []
    return [(d, v) for d, v in zip(g.date[:fino + 1], col[:fino + 1]) if v is not None]


def prev_stagionale(g, k, mese, fino):
    """+1/-1 se il mese e' stagionalmente robusto (filtri della scheda Stagionalita'), altrimenti 0."""
    pts = _prezzi(g, k, fino)
    if len(pts) < 500:
        return 0, None
    m, _ = SG.mesi(SG.Serie(pts))
    x = (m or [{}] * 12)[int(mese[5:7]) - 1]
    if x.get("robusto"):
        return (1 if x["med_d"] > 0 else -1), x["med_d"]
    return 0, x.get("med_d")


def prev_cot(sc, k, giorno):
    """+1/-1 dall'etichetta del punteggio COT gia' pubblicato al giorno della rotazione; 0 se NEUTRO o assente."""
    x = P.cot_al(sc.get(k), giorno)
    if not x:
        return 0, None
    lab = label(x[1], single=True)
    return (0 if lab == "NEUTRO" else (1 if x[1] > 0 else -1)), round(x[1], 1)


class Pannello:
    """Dati mensili di tutti i mercati per il modello: ingressi alla fine del mese a, rendimento del mese dopo b."""

    def __init__(self, g, sc, fino):
        self.g, self.sc, self.fino = g, sc, fino
        fm = {m: i for m, i in fine_mesi(g).items() if i <= fino}
        self.mesi = sorted(fm)
        self.fm = fm
        self.chiusure = {}
        for k in MERCATI:
            col = g.p.get(P.TUTTI[k][1])
            if col:
                self.chiusure[k] = {m: col[i] for m, i in fm.items() if col[i] is not None}

    def ingressi(self, k, a, b):
        """[COT/100, distanza dalla media 200 g, momento 12-1, stagionalita' del mese b] alla fine del mese a."""
        ch = self.chiusure.get(k) or {}
        if a not in ch:
            return None
        col = self.g.p[P.TUTTI[k][1]]
        i = self.fm[a]
        fin = [v for v in col[max(0, i - P.SMA + 1):i + 1] if v is not None]
        if len(fin) < P.SMA * 0.9:
            return None
        trend = ch[a] / (sum(fin) / len(fin)) - 1
        m1, m12 = _mese_dopo(a, -1), _mese_dopo(a, -12)
        if m1 not in ch or m12 not in ch:
            return None
        mom = ch[m1] / ch[m12] - 1
        x = P.cot_al(self.sc.get(k), P.primo_feriale(int(b[:4]), int(b[5:7])).isoformat())
        cot = (x[1] / 100) if x else 0.0
        # stagionalita': rendimento medio dello stesso mese negli anni prima, meno il rendimento medio di tutti i mesi
        rend = [(m, math.log(ch[m] / ch[_mese_dopo(m, -1)])) for m in ch if m <= a and _mese_dopo(m, -1) in ch]
        stessi = [r for m, r in rend if m[5:7] == b[5:7]]
        stag = (mean(stessi) - mean(r for _, r in rend)) if len(stessi) >= ANNI_STAG_MODELLO else 0.0
        return [cot, trend, mom, stag]

    def righe(self, mese):
        """Esempi di addestramento: tutte le coppie (a, b) con b prima del mese da prevedere."""
        X, y = [], []
        for k, ch in self.chiusure.items():
            for a in self.mesi:
                b = _mese_dopo(a)
                if b >= mese or b not in ch or a not in ch:
                    continue
                f = self.ingressi(k, a, b)
                if f:
                    X.append(f)
                    y.append(ch[b] / ch[a] - 1)
        return X, y


def ridge(X, y):
    """Regressione con coefficienti ristretti: ingressi standardizzati, penalita' = numero di esempi (circa meta'
    dell'effetto stimato). Restituisce (media, deviazione, coefficienti, intercetta)."""
    n, p = len(X), len(X[0])
    mu = [mean(r[j] for r in X) for j in range(p)]
    sd = [pstdev([r[j] for r in X]) or 1.0 for j in range(p)]
    Z_ = [[(r[j] - mu[j]) / sd[j] for j in range(p)] for r in X]
    ym = mean(y)
    A = [[sum(z[i] * z[j] for z in Z_) + (n if i == j else 0) for j in range(p)] for i in range(p)]
    bv = [sum(z[i] * (yy - ym) for z, yy in zip(Z_, y)) for i in range(p)]
    beta = _risolvi(A, bv)
    return mu, sd, beta, ym


def _risolvi(A, b):
    """Sistema lineare A x = b (eliminazione di Gauss con pivot): matrici 4x4, niente librerie esterne."""
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        r = max(range(c, n), key=lambda i: abs(M[i][c]))
        M[c], M[r] = M[r], M[c]
        if abs(M[c][c]) < 1e-12:
            return [0.0] * n
        for i in range(n):
            if i != c:
                f = M[i][c] / M[c][c]
                M[i] = [a - f * bb for a, bb in zip(M[i], M[c])]
    return [M[i][n] / M[i][i] for i in range(n)]


def prev_modello(pan, mese):
    """{mercato: rendimento atteso del mese in %} con il modello addestrato sui soli mesi passati."""
    X, y = pan.righe(mese)
    if len(X) < 200:
        return {}
    mu, sd, beta, ym = ridge(X, y)
    a = pan.mesi[-1]
    out = {}
    for k in pan.chiusure:
        f = pan.ingressi(k, a, mese)
        if f:
            out[k] = round((ym + sum(b * (v - m) / s for b, v, m, s in zip(beta, f, mu, sd))) * 100, 2)
    return out


