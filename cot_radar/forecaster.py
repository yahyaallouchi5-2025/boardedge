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
PROVA = "https://github.com/" + (os.environ.get("GITHUB_REPOSITORY") or "yahyaallouchi5-2025/cot-radar") + "/commits/storico/forecaster/registro.jsonl"

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


# --------------------------------------------------------------------------- sfidanti
def _inclina(pesi, verso):
    """Pesi x (1 +/- INCLINA) secondo verso {k: +1/-1}; la differenza da/verso la liquidita'. Se la liquidita' non
    basta per gli aumenti, gli aumenti si riducono in proporzione (mai leva, mai liquidita' negativa)."""
    out = dict(pesi)
    su = {k: w * INCLINA for k, w in pesi.items() if verso.get(k, 0) > 0 and k not in ("CASH", "AZ")}
    giu = {k: w * INCLINA for k, w in pesi.items() if verso.get(k, 0) < 0 and k not in ("CASH", "AZ")}
    disp = pesi.get("CASH", 0) + sum(giu.values())
    f = min(1.0, disp / sum(su.values())) if su else 1.0
    for k, v in giu.items():
        out[k] -= v
    for k, v in su.items():
        out[k] += v * f
    out["CASH"] = round(disp - sum(su.values()) * f, 6)
    return _pulisci(out)


def _oro(pesi):
    out = dict(pesi)
    da_cash = min(ORO_IN_PIU, out.get("CASH", 0))
    out["CASH"] = out.get("CASH", 0) - da_cash
    resto = ORO_IN_PIU - da_cash
    altri = {k: w for k, w in out.items() if k not in ("CASH", "GOLD") and w > 0}
    tot = sum(altri.values())
    for k, w in altri.items():
        out[k] = w - resto * w / tot if tot else w
    out["GOLD"] = out.get("GOLD", 0) + ORO_IN_PIU
    return _pulisci(out)


def _pulisci(p):
    return {k: round(v, 4) for k, v in p.items() if v >= 0.0005}


def sfidanti(g, sc, i_rot, giorno, prev, sat_az10):
    """{sfidante: {profilo: {mercato: peso}}} per il mese che parte al giorno di rotazione i_rot."""
    out = {s[0]: {} for s in SFIDANTI}
    mod = {k: v["mod"] for k, v in prev.items() if v.get("mod") is not None}
    media_mod = mean(mod.values()) if mod else 0.0
    for prof in P.PROFILI:
        pid = prof["id"]
        campione, _, _ = P.scegli(prof, g, i_rot, sc, giorno=giorno)
        out["campione"][pid] = campione
        if sat_az10 and "AZ" in campione:
            out["az10"][pid] = {("AZ10" if k == "AZ" else k): w for k, w in campione.items()}
        elif "AZ" not in campione:
            out["az10"][pid] = dict(campione)          # quota azioni in pausa: identico al campione
        senza, _, _ = P.scegli(dict(prof, az=0), g, i_rot, sc, giorno=giorno)
        out["senza_az"][pid] = senza
        out["oro"][pid] = _oro(campione)
        out["stag"][pid] = _inclina(campione, {k: v["stag"] for k, v in prev.items()})
        out["modello"][pid] = _inclina(campione, {k: (1 if mod[k] > media_mod else -1) for k in mod})
    return {k: v for k, v in out.items() if v}


# --------------------------------------------------------------------------- rendimenti
def rend_mercati(g, i0, i1, sat_r=None):
    """{chiave: rendimento} dalla chiusura i0 alla chiusura i1 per mercati, liquidita', AZ (e AZ10 se dato)."""
    out = {}
    for k in MERCATI + ["CASH", "AZ"]:
        col = g.p.get(P.TUTTI[k][1])
        if col and col[i0] and col[i1]:
            out[k] = col[i1] / col[i0] - 1
    if sat_r is not None:
        out["AZ10"] = sat_r
    return out


def rend_portafoglio(pesi, r):
    """Pesi fissati all'inizio del mese e lasciati liberi (buy and hold): rendimento = somma pesi x rendimenti.
    None se manca il rendimento di un mercato con peso (non si inventano dati)."""
    if any(k not in r for k, w in pesi.items() if w > 0):
        return None
    return sum(w * r[k] for k, w in pesi.items())


def costo(nuovi, vecchi):
    return P.COSTO * sum(abs(nuovi.get(k, 0) - vecchi.get(k, 0)) for k in set(nuovi) | set(vecchi)) if vecchi else 0.0


# --------------------------------------------------------------------------- registro in catena
def _impronta(prec, corpo):
    testo = json.dumps(corpo, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prec + testo).encode("utf-8")).hexdigest()


def leggi(cartella=CARTELLA):
    f = os.path.join(cartella, FILE)
    if not os.path.exists(f):
        return []
    with open(f, encoding="utf-8") as fh:
        return [json.loads(r) for r in fh if r.strip()]


def catena_ok(righe):
    prec = ""
    for r in righe:
        corpo = {k: v for k, v in r.items() if k not in ("hash", "prec")}
        if r.get("prec") != prec or r.get("hash") != _impronta(prec, corpo):
            return False
        prec = r["hash"]
    return True


def aggiungi(righe, corpo, cartella=CARTELLA, scrivi=True):
    """Aggiunge una riga in coda (mai riscritte), con l'impronta della precedente."""
    prec = righe[-1]["hash"] if righe else ""
    riga = dict(corpo, prec=prec, hash=_impronta(prec, corpo))
    righe.append(riga)
    if scrivi:
        os.makedirs(cartella, exist_ok=True)
        with open(os.path.join(cartella, FILE), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(riga, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    return riga


# --------------------------------------------------------------------------- giudizi
def giudizio_prev(lista):
    """lista = [(direzione prevista, rendimento)]: precisione, base "sempre rialzo" e giudizio (differenza appaiata)."""
    v = [(d, r) for d, r in lista if d]
    if not v:
        return {"n": 0}
    hit = [1 if d * r > 0 else 0 for d, r in v]
    base = [1 if r > 0 else 0 for _, r in v]
    diff = [h - b for h, b in zip(hit, base)]
    out = {"n": len(v), "hit": round(100 * mean(hit)), "base": round(100 * mean(base)),
           "medio": round(100 * mean(d * r for d, r in v), 2)}
    if len(v) >= MIN_PREV:
        m, s = mean(diff), pstdev(diff) / math.sqrt(len(diff))
        out["ic"] = [round(100 * (m - Z * s)), round(100 * (m + Z * s))]
        out["verdetto"] = "meglio" if m - Z * s > 0 else ("peggio" if m + Z * s < 0 else "uguale")
    else:
        out["verdetto"] = "raccolta"
    return out


def giudizio_sfidante(mesi_s, mesi_c):
    """mesi_* = {mese: rendimento}: totale, drawdown mensile, differenza media con il campione e giudizio."""
    comuni = sorted(m for m in mesi_s if m in mesi_c and mesi_s[m] is not None and mesi_c[m] is not None)
    if not comuni:
        return {"mesi": 0, "verdetto": "osservazione"}
    v, pk, dd = 1.0, 1.0, 0.0
    for m in comuni:
        v *= 1 + mesi_s[m]
        pk = max(pk, v)
        dd = min(dd, v / pk - 1)
    diff = [mesi_s[m] - mesi_c[m] for m in comuni]
    out = {"mesi": len(comuni), "tot": round((v - 1) * 100, 2), "dd": round(dd * 100, 2),
           "diff": round(mean(diff) * 100, 2)}
    if len(comuni) >= MIN_MESI:
        s = pstdev(diff) / math.sqrt(len(diff))
        m = mean(diff)
        out["ic"] = [round((m - Z * s) * 100, 2), round((m + Z * s) * 100, 2)]
        out["verdetto"] = "meglio" if m - Z * s > 0 else ("peggio" if m + Z * s < 0 else "uguale")
    else:
        out["verdetto"] = "osservazione"
    return out


# --------------------------------------------------------------------------- giro completo
def calcola(righe_cot, px, sat=None, cartella=CARTELLA, scrivi=True, adesso=None):
    """Aggiorna il registro (previsione del mese nuovo, esito del mese chiuso) e restituisce i dati della scheda.
    px = prezzi dei portafogli; sat = satellite.json (quota azioni e sfidante a 10 titoli). None se mancano i prezzi."""
    if "SPY" not in px or P.LIQUIDITA[1] not in px:
        return None
    adesso = adesso or datetime.now(timezone.utc)
    px_tutti = dict(px)
    ss = P.serie_satellite(sat, [d for d, _ in px["SPY"]])
    if ss:
        px_tutti["SAT"] = ss
    g = P.Griglia(px_tutti)
    sc = P.segnali_cot(righe_cot)
    righe = leggi(cartella)
    if righe and not catena_ok(righe):
        log.error("forecaster: catena del registro NON integra: nessuna nuova riga finche' l'admin non controlla")
        scrivi = False
    prev_r = {r["mese"]: r for r in righe if r["tipo"] == "previsione"}
    esiti = {r["mese"]: r for r in righe if r["tipo"] == "esito"}
    az10 = (sat or {}).get("sfidante10") or {}
    fm = fine_mesi(g)

    # 1) ESITI dei mesi registrati e ormai chiusi (in ordine: i costi guardano il mese prima)
    for mese in sorted(prev_r):
        if mese in esiti or mese not in fm or g.date[-1] < ultimo_feriale(mese):
            continue
        p = prev_r[mese]
        i0, i1 = g.pos.get(p["decisa_al"]), fm[mese]
        if i0 is None:
            continue
        r10 = (az10.get("mesi") or {}).get(mese)
        serve10 = any("AZ10" in w for w in (p["sfidanti"].get("az10") or {}).values())
        if serve10 and r10 is None and adesso.date() < date.fromisoformat(ultimo_feriale(mese)) + timedelta(days=7):
            continue                                  # aspetta qualche giorno il rendimento del 10 titoli
        r = rend_mercati(g, i0, i1, r10)
        prima = prev_r.get(_mese_dopo(mese, -1))
        sf = {}
        for sid, prof in p["sfidanti"].items():
            sf[sid] = {}
            for pid, pesi in prof.items():
                rp = rend_portafoglio(pesi, r)
                vecchi = ((prima or {}).get("sfidanti", {}).get(sid) or {}).get(pid)
                sf[sid][pid] = None if rp is None else round((rp - costo(pesi, vecchi)) * 100, 3)
        esiti[mese] = aggiungi(righe, {"tipo": "esito", "mese": mese, "al": g.date[i1],
                                       "creato": adesso.strftime("%Y-%m-%dT%H:%MZ"),
                                       "mercati": {k: round(v * 100, 3) for k, v in r.items()}, "sfidanti": sf},
                               cartella, scrivi)
        log.info("forecaster: esito di %s registrato", mese)

    # 2) PREVISIONE del mese nuovo (una sola volta, mai riscritta)
    mese, i_dec = mese_da_registrare(g)
    if mese and mese >= DAL and mese not in prev_r:
        giorno = P.primo_feriale(int(mese[:4]), int(mese[5:7]))
        pan = Pannello(g, sc, i_dec)
        mod = prev_modello(pan, mese)
        prev = {}
        for k in MERCATI:
            if P.TUTTI[k][1] not in g.p:
                continue
            ds, vs = prev_stagionale(g, k, mese, i_dec)
            dc, vc = prev_cot(sc, k, giorno.isoformat())
            prev[k] = {"stag": ds, "stag_v": vs, "cot": dc, "cot_v": vc, "mod": mod.get(k)}
        reg10 = ((az10.get("registro") or {}).get(mese) or {}).get("titoli")
        sf = sfidanti(g, sc, i_dec + 1, giorno.isoformat(), prev, bool(reg10))
        apre = datetime(giorno.year, giorno.month, giorno.day, *APERTURA_UTC, tzinfo=timezone.utc)
        corpo = {"tipo": "previsione", "mese": mese, "decisa_al": g.date[i_dec], "creato": adesso.strftime("%Y-%m-%dT%H:%MZ"),
                 "in_ritardo": adesso > apre, "mercati": prev, "sfidanti": sf,
                 "az10": [x["t"] for x in reg10] if reg10 else None}
        prev_r[mese] = aggiungi(righe, corpo, cartella, scrivi)
        log.info("forecaster: previsione di %s registrata (decisa sulla chiusura del %s)", mese, g.date[i_dec])

    return pagina(g, righe, prev_r, esiti, az10)


def pagina(g, righe, prev_r, esiti, az10):
    """Dati per la scheda: mese in corso (previsioni e andamento), precisione, sfidanti, archivio."""
    out = {"dal": DAL, "prova": PROVA, "catena": catena_ok(righe), "mesi": len(esiti), "ultimo_hash": righe[-1]["hash"] if righe else None,
           "min_mesi": MIN_MESI, "min_prev": MIN_PREV,
           "sfidanti_def": [{"id": a, "nome": b, "descr": c} for a, b, c in SFIDANTI],
           "profili": [{"id": p["id"], "nome": p["nome"]} for p in P.PROFILI],
           "nomi": {k: P.TUTTI[k][2] for k in MERCATI + ["CASH", "AZ"]}}
    # mese in corso = ultima previsione registrata
    if prev_r:
        p = prev_r[max(prev_r)]
        i0 = g.pos.get(p["decisa_al"])
        avviato = i0 is not None and len(g.date) - 1 > i0
        r = rend_mercati(g, i0, len(g.date) - 1, ((az10.get("corrente") or {}).get("r") if (az10.get("corrente") or {}).get("mese") == p["mese"] else None)) if avviato else {}
        out["corrente"] = {
            "mese": p["mese"], "decisa_al": p["decisa_al"], "creato": p["creato"], "in_ritardo": p.get("in_ritardo"),
            "al": g.date[-1] if avviato else None, "chiuso": p["mese"] in esiti, "az10": p.get("az10"),
            "mercati": [dict(v, k=k, r=round(r[k] * 100, 2) if k in r else None) for k, v in p["mercati"].items()],
            "sfidanti": {sid: {pid: (round(rend_portafoglio(w, r) * 100, 2) if avviato and rend_portafoglio(w, r) is not None else None)
                               for pid, w in prof.items()} for sid, prof in p["sfidanti"].items()},
            "pesi": p["sfidanti"]}
    # precisione delle previsioni sui mesi chiusi
    liste = {"stag": [], "cot": [], "mod": []}
    for mese, e in esiti.items():
        p = prev_r.get(mese)
        if not p:
            continue
        mod = {k: v["mod"] for k, v in p["mercati"].items() if v.get("mod") is not None}
        for k, v in p["mercati"].items():
            if k not in e["mercati"]:
                continue
            r = e["mercati"][k]
            liste["stag"].append((v["stag"], r))
            liste["cot"].append((v["cot"], r))
            if k in mod:
                liste["mod"].append((1 if mod[k] > 0 else -1, r))
    out["precisione"] = {k: giudizio_prev(v) for k, v in liste.items()}
    # sfidanti: serie dei mesi chiusi per profilo
    serie = {}
    for mese, e in esiti.items():
        for sid, prof in e["sfidanti"].items():
            for pid, v in prof.items():
                serie.setdefault(sid, {}).setdefault(pid, {})[mese] = None if v is None else v / 100
    out["sfidanti"] = {sid: {pid: giudizio_sfidante(m, serie.get("campione", {}).get(pid, {})) for pid, m in prof.items()}
                       for sid, prof in serie.items()}
    out["archivio"] = [{"mese": m, "creato": p["creato"], "in_ritardo": p.get("in_ritardo"),
                        "decisa_al": p["decisa_al"], "esito": m in esiti,
                        "campione": (esiti.get(m) or {}).get("sfidanti", {}).get("campione")}
                       for m, p in sorted(prev_r.items(), reverse=True)]
    return out
