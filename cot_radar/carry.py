# -*- coding: utf-8 -*-
"""
carry.py - CARRY TRADE (v6.61): i tassi d'interesse delle valute, il carry di ogni coppia e lo studio storico.

IDEA FINANZIARIA
  Chi compra una valuta con tasso alto e vende una valuta con tasso basso incassa ogni giorno la differenza
  (lo "swap" del broker). Carry di una coppia BASE/QUOTATA comprata = tasso BASE - tasso QUOTATA (% annuo).
  Positivo = il BUY incassa, negativo = il BUY paga (e il SELL incassa). Il rischio tipico: guadagno lento,
  perdite rapide nei momenti di panico (2008, agosto 2024) quando tutti chiudono insieme.

DATI (FRED, gratuiti, MENSILI)
  Per ogni valuta una lista di serie in ordine di preferenza: tasso interbancario a 3 mesi dell'OECD (IR3TIB01..),
  poi il tasso a brevissimo (IRSTCI01..), per il dollaro anche i T-bill a 3 mesi (TB3MS). Per la storia si usa la
  prima serie e i mesi che le mancano si prendono dalle altre; il valore di OGGI e' l'ultimo mese disponibile.
  I dati OECD arrivano con circa 1-2 mesi di ritardo: per il carry va bene, i tassi cambiano lentamente.

ARCHIVIO: storico/tassi.json (ramo "storico" su GitHub). Un archivio a parte perche' i tassi possono essere
  NEGATIVI (franco, euro e yen tra il 2015 e il 2022) e l'archivio dei prezzi scarta i valori <= 0.
  Si scarica al massimo una volta al giorno; una serie che non arriva tiene i valori gia' salvati.
"""
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from .log import log

CARTELLA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storico")
FILE = "tassi.json"
DAL = "1990-01-01"

# valuta -> serie FRED candidate (la prima e' la preferita). Le valute senza dati mostrano "n/d".
CANDIDATI = {
    "USD": ["IR3TIB01USM156N", "TB3MS"],
    "EUR": ["IR3TIB01EZM156N", "IRSTCI01EZM156N", "ECBDFR"],   # ECBDFR (tasso BCE, giornaliero): mesi recenti
    "JPY": ["IR3TIB01JPM156N", "IRSTCI01JPM156N"],
    "GBP": ["IR3TIB01GBM156N", "IRSTCI01GBM156N"],
    "CHF": ["IR3TIB01CHM156N", "IRSTCI01CHM156N"],
    "CAD": ["IR3TIB01CAM156N", "IRSTCI01CAM156N"],
    "AUD": ["IR3TIB01AUM156N", "IRSTCI01AUM156N"],
    "NZD": ["IR3TIB01NZM156N", "IRSTCI01NZM156N"],
    "MXN": ["IR3TIB01MXM156N", "IRSTCI01MXM156N"],
    "ZAR": ["IR3TIB01ZAM156N", "IRSTCI01ZAM156N"],
    "BRL": ["IRSTCI01BRM156N"],
}
VECCHIO_GIORNI = 150     # ultimo dato piu' vecchio di ~5 mesi: la valuta e' segnata "dato vecchio"


# --------------------------------------------------------------------------- archivio
def leggi(cartella=CARTELLA):
    """Archivio salvato: {"scaricato": data, "serie": {sid: [[data, valore], ...]}, "errori": {sid: testo}}."""
    try:
        with open(os.path.join(cartella, FILE), encoding="utf-8") as f:
            a = json.load(f)
        if isinstance(a.get("serie"), dict):
            return a
    except (OSError, ValueError):
        pass
    return {"scaricato": None, "serie": {}, "errori": {}}


def aggiorna_tassi(scarica, cartella=CARTELLA, oggi=None, forza=False):
    """Scarica (al massimo una volta al giorno) tutte le serie candidate e aggiorna storico/tassi.json.
    scarica(sid, inizio) -> [[data, valore], ...] (fonti.get_fred). Ogni serie e' indipendente: se una non
    arriva, resta la copia salvata. Restituisce l'archivio aggiornato."""
    oggi = (oggi or date.today()).isoformat()
    a = leggi(cartella)
    tutte = [sid for lista in CANDIDATI.values() for sid in lista]
    nuove_serie = [sid for sid in tutte if sid not in a["serie"] and sid not in (a.get("errori") or {})]
    if a.get("scaricato") == oggi and a["serie"] and not forza and not nuove_serie:   # serie aggiunte: subito
        return a

    def una(sid):
        try:
            pts = scarica(sid, DAL)
            pts = [[d, round(float(v), 4)] for d, v in pts if v is not None]
            return sid, pts, None
        except Exception as e:                     # serie inesistente, interrotta o rete giu': si va avanti
            return sid, None, (str(e) or type(e).__name__)[:160]

    with ThreadPoolExecutor(max_workers=4) as ex:
        risultati = list(ex.map(una, tutte))
    errori, nuove = {}, 0
    for sid, pts, err in risultati:
        if pts and len(pts) >= 12:
            vecchi = a["serie"].get(sid) or []
            if len(pts) >= 0.9 * len(vecchi):      # un download molto piu' corto del salvato e' sospetto
                a["serie"][sid] = pts
                nuove += 1
            else:
                errori[sid] = f"download sospetto: {len(pts)} punti contro {len(vecchi)} salvati"
        else:
            errori[sid] = err or "troppo pochi dati"
    a["scaricato"], a["errori"] = oggi, errori
    try:
        os.makedirs(cartella, exist_ok=True)
        with open(os.path.join(cartella, FILE + ".tmp"), "w", encoding="utf-8") as f:
            json.dump(a, f, separators=(",", ":"))
        os.replace(os.path.join(cartella, FILE + ".tmp"), os.path.join(cartella, FILE))
    except OSError as e:
        log.warning("carry: archivio dei tassi non salvato (%s)", e)
    log.info("carry: %d serie di tassi aggiornate, %d non disponibili%s", nuove, len(errori),
             (" (" + ", ".join(sorted(errori)) + ")") if errori else "")
    return a


# --------------------------------------------------------------------------- tassi mensili per valuta
def mensili(archivio):
    """{valuta: {"AAAA-MM": tasso %}} unendo le candidate: la preferita vince, le altre riempiono i buchi.
    + {valuta: {"v", "mese", "fonte", "vecchio"}} con l'ultimo valore disponibile."""
    serie, oggi = archivio.get("serie") or {}, date.today()
    per_val, ultimo = {}, {}
    for val, lista in CANDIDATI.items():
        m, fonte_ult, mese_ult = {}, None, ""
        for sid in reversed(lista):                # dalla meno preferita alla preferita: la preferita sovrascrive
            for d, v in serie.get(sid) or []:
                m[d[:7]] = v
        if not m:
            continue
        mese_ult = max(m)
        for sid in lista:                          # fonte del valore piu' recente = prima candidata che ce l'ha
            if any(d[:7] == mese_ult for d, _ in serie.get(sid) or []):
                fonte_ult = sid
                break
        per_val[val] = m
        eta = (oggi - date.fromisoformat(mese_ult + "-15")).days
        ultimo[val] = {"v": round(m[mese_ult], 2), "mese": mese_ult, "fonte": fonte_ult,
                       "vecchio": eta > VECCHIO_GIORNI}
    return per_val, ultimo


# --------------------------------------------------------------------------- carry delle coppie (live)
def coppie(pairs, ultimo):
    """Aggiunge a ogni coppia: carry (% annuo per chi COMPRA = tasso base - tasso quotata) e il confronto con il
    COT: "si" = il lato che incassa e' lo stesso del segnale COT, "no" = opposto, assente = segnale NEUTRO o carry
    troppo piccolo (sotto MIN_CARRY non conta). Le valute senza tasso lasciano la coppia senza carry."""
    for p in pairs:
        b, q = ultimo.get(p.get("base")), ultimo.get(p.get("quote"))
        if not b or not q:
            continue
        c = round(b["v"] - q["v"], 2)
        p["carry"] = c
        lab = p.get("label") or ""
        verso = 1 if "BUY" in lab else -1 if "SELL" in lab else 0
        if verso and abs(c) >= MIN_CARRY:
            p["carry_cot"] = "si" if verso * c > 0 else "no"


# --------------------------------------------------------------------------- studio storico
# Regole decise PRIMA di guardare i risultati (quelle classiche degli studi accademici sul carry):
#  - 8 valute: USD EUR JPY GBP CHF CAD AUD NZD (le uniche con prezzi giornalieri FRED e tassi dal 1999).
#  - A fine mese si ordinano per tasso del MESE PRIMA (i dati OECD arrivano in ritardo: niente sbirciate al futuro).
#  - Si comprano le 3 con tasso piu' alto e si vendono le 3 con tasso piu' basso, pesi uguali, per un mese.
#  - Rendimento di una valuta = variazione del cambio contro dollaro + interessi del mese (tasso / 12).
#  - Costi: COSTO_CAMBIO a ogni valuta che entra o esce + ricarico del broker sugli swap (RICARICO annuo).
#  Varianti (stesse regole + un filtro): "trend" tiene una valuta solo se negli ultimi 3 mesi si e' mossa nel verso
#  giusto rispetto alle altre; "cot" toglie una valuta quando il COT e' chiaramente contro (|punteggio| >= 25).
G8 = ("USD", "EUR", "JPY", "GBP", "CHF", "CAD", "AUD", "NZD")
N_LATO = 3
MIN_CARRY = 0.5           # % annuo: sotto questa differenza il carry non conta per il confronto con il COT
COSTO_CAMBIO = 0.03       # % per ogni valuta che entra o esce dal paniere (spread delle valute principali)
RICARICO = 0.5            # % annuo: quanto il broker trattiene sugli swap rispetto ai tassi interbancari
Z_CARRY = 2.39            # intervallo al 95% corretto per 3 varianti (Bonferroni)
COT_CONTRO = 25           # punteggio COT oltre il quale (in verso opposto) la valuta viene tolta
STRESS = [("Crisi 2008", "2008-08", "2008-12"), ("Covid 2020", "2020-02", "2020-03"),
          ("Uscita dallo yen 2024", "2024-07", "2024-08")]
VARIANTI = (("classico", "Carry classico"), ("trend", "Carry + trend"), ("cot", "Carry + COT"))


def _mese_succ(m):
    a, n = int(m[:4]), int(m[5:7]) + 1
    return f"{a + (n > 12):04d}-{(n - 1) % 12 + 1:02d}"


def _mese_prec(m):
    a, n = int(m[:4]), int(m[5:7]) - 1
    return f"{a - (n < 1):04d}-{(n - 1) % 12 + 1:02d}"


def chiusure_mensili(prezzi):
    """{valuta: {"AAAA-MM": ultimo prezzo del mese in dollari}} per le valute G8 (USD = 1)."""
    out = {}
    for v in G8:
        if v == "USD":
            continue
        m = {}
        for d, x in prezzi.get(v) or []:
            m[d[:7]] = x
        if m:
            out[v] = m
    return out


def cot_mensile(cot_righe):
    """{valuta: {"AAAA-MM": punteggio COT noto a fine mese}} (USD = indice del dollaro). Solo i report gia'
    pubblicati: il report del martedi' esce il venerdi', quindi conta se martedi' + 3 giorni cade nel mese."""
    from .backtest import punteggi
    from .config import ASSETS
    from .cot import cot_series
    from datetime import timedelta
    serie = cot_series(cot_righe or [])
    codici = {a[0]: a[1] for a in ASSETS}
    out = {}
    for v in G8:
        cod = codici.get("DXY" if v == "USD" else v)
        if not cod or cod not in serie:
            continue
        m = {}
        for d, (sc, _) in sorted(punteggi(serie[cod]).items()):
            m[(date.fromisoformat(d) + timedelta(days=3)).isoformat()[:7]] = sc   # l'ultimo del mese vince
        out[v] = m
    return out


def _stat(rend, mesi):
    """Statistiche di una serie di rendimenti mensili (in %)."""
    n = len(rend)
    if n < 24:
        return None
    m = sum(rend) / n
    sd = (sum((x - m) ** 2 for x in rend) / (n - 1)) ** 0.5
    eq, picco, dd, curva = 1.0, 1.0, 0.0, []
    for x, me in zip(rend, mesi):
        eq *= 1 + x / 100
        picco = max(picco, eq)
        dd = min(dd, eq / picco - 1)
        curva.append([me, round(eq, 4)])
    err = Z_CARRY * sd / n ** 0.5
    peg = min(range(n), key=lambda i: rend[i])
    return {"n": n, "cagr": round((eq ** (12 / n) - 1) * 100, 2), "vol": round(sd * 12 ** 0.5, 2),
            "rr": round(m * 12 / (sd * 12 ** 0.5), 2) if sd else None, "maxdd": round(dd * 100, 1),
            "positivi": round(100 * sum(1 for x in rend if x > 0) / n), "peggior_mese": [mesi[peg], round(rend[peg], 2)],
            "medio_anno": round(m * 12, 2), "ic_anno": [round((m - err) * 12, 2), round((m + err) * 12, 2)],
            "curva": curva, "dal": mesi[0], "al": mesi[-1]}


def studio(per_val, prezzi, cot_righe=None):
    """Backtest mensile del carry sulle 8 valute. Restituisce {varianti, stress, paniere, regole} o None."""
    px = chiusure_mensili(prezzi)
    if any(v not in per_val for v in G8) or any(v not in px for v in G8 if v != "USD"):
        mancano = [v for v in G8 if v not in per_val or (v != "USD" and v not in px)]
        log.warning("carry: studio non calcolato, mancano tassi o prezzi di %s", ", ".join(mancano))
        return None
    cotm = cot_mensile(cot_righe) if cot_righe else {}
    prezzo = lambda v, me: 1.0 if v == "USD" else px[v].get(me)
    mesi = sorted(set.intersection(*[set(px[v]) for v in px]))
    mesi = [me for me in mesi if all(_mese_prec(me) in per_val[v] for v in G8)]
    risultati = {k: {"r": [], "m": [], "pesi": {}} for k, _ in VARIANTI}
    for i in range(3, len(mesi) - 1):
        me, dopo = mesi[i], mesi[i + 1]
        if _mese_succ(me) != dopo:                 # buco nei dati: si salta (non si inventano mesi)
            continue
        tasso = {v: per_val[v][_mese_prec(me)] for v in G8}       # noto a fine mese
        ordine = sorted(G8, key=lambda v: tasso[v])
        lunghe, corte = ordine[-N_LATO:], ordine[:N_LATO]
        # trend relativo a 3 mesi: variazione contro dollaro meno la media delle 8 valute (dollaro = 0)
        tre = mesi[i - 3]
        mom = {v: (prezzo(v, me) / prezzo(v, tre) - 1) if prezzo(v, tre) else 0 for v in G8}
        media = sum(mom.values()) / len(G8)
        rel = {v: mom[v] - media for v in G8}
        cs = {v: (cotm.get(v) or {}).get(me) for v in G8}
        filtri = {"classico": lambda v, lato: True,
                  "trend": lambda v, lato: rel[v] * lato > 0,
                  "cot": lambda v, lato: not (cs[v] is not None and cs[v] * lato <= -COT_CONTRO)}
        resa = {v: (prezzo(v, dopo) / prezzo(v, me) - 1) * 100 + tasso[v] / 12 for v in G8}
        for k, f in filtri.items():
            L = [v for v in lunghe if f(v, 1)]
            S = [v for v in corte if f(v, -1)]
            pesi = {**{v: 1 / len(L) for v in L}, **{v: -1 / len(S) for v in S}}
            vecchi = risultati[k]["pesi"]
            giro = sum(abs(pesi.get(v, 0) - vecchi.get(v, 0)) for v in set(pesi) | set(vecchi))
            lordo = sum(abs(w) for w in pesi.values())
            r = sum(w * resa[v] for v, w in pesi.items()) - giro * COSTO_CAMBIO - lordo * RICARICO / 12 / 2
            risultati[k]["r"].append(r)
            risultati[k]["m"].append(dopo)
            risultati[k]["pesi"] = pesi
    out = {"varianti": {}, "stress": [], "regole": {"valute": list(G8), "n_lato": N_LATO, "costo": COSTO_CAMBIO,
                                                    "ricarico": RICARICO, "cot_contro": COT_CONTRO}}
    for k, nome in VARIANTI:
        st = _stat(risultati[k]["r"], risultati[k]["m"])
        if not st:
            continue
        st["nome"] = nome
        st["verdetto"] = "si" if st["ic_anno"][0] > 0 else "peggio" if st["ic_anno"][1] < 0 else "no"
        rr = dict(zip(risultati[k]["m"], risultati[k]["r"]))
        ult = risultati[k]["r"][-60:]                 # ultimi 5 anni
        st["ultimi5"] = round((math.prod(1 + x / 100 for x in ult) ** (12 / len(ult)) - 1) * 100, 2)   # % annuo
        st["stress"] = []
        for nm, a, b in STRESS:
            xs = [x for me, x in rr.items() if a <= me <= b]
            if xs:
                st["stress"].append([nm, round((math.prod(1 + x / 100 for x in xs) - 1) * 100, 1)])
        out["varianti"][k] = st
    # paniere di OGGI: tassi piu' recenti disponibili
    oggi = {v: per_val[v][max(per_val[v])] for v in G8}
    ordine = sorted(G8, key=lambda v: oggi[v])
    out["paniere"] = {"compra": [[v, round(oggi[v], 2)] for v in reversed(ordine[-N_LATO:])],
                      "vendi": [[v, round(oggi[v], 2)] for v in ordine[:N_LATO]],
                      "carry": round(sum(oggi[v] for v in ordine[-N_LATO:]) / N_LATO - sum(oggi[v] for v in ordine[:N_LATO]) / N_LATO, 2)}
    return out if out["varianti"] else None


# --------------------------------------------------------------------------- punto d'ingresso (pagina.py)
NOMI = {"USD": "Dollaro USA", "EUR": "Euro", "JPY": "Yen", "GBP": "Sterlina", "CHF": "Franco svizzero",
        "CAD": "Dollaro canadese", "AUD": "Dollaro australiano", "NZD": "Dollaro neozelandese",
        "MXN": "Peso messicano", "ZAR": "Rand sudafricano", "BRL": "Real brasiliano"}


def tassi_demo():
    """Archivio finto per la modalita' demo e i test: tassi costanti plausibili dal 1999."""
    tipici = {"USD": 3.0, "EUR": 1.5, "JPY": 0.1, "GBP": 3.2, "CHF": 0.3, "CAD": 2.5, "AUD": 4.0, "NZD": 4.2,
              "MXN": 7.0, "ZAR": 7.0, "BRL": 11.0}
    serie = {}
    for v, lista in CANDIDATI.items():
        serie[lista[0]] = [[f"{a}-{m:02d}-01", tipici[v]] for a in range(1999, date.today().year + 1)
                           for m in range(1, 13) if f"{a}-{m:02d}" < date.today().isoformat()[:7]]
    return {"scaricato": None, "serie": serie, "errori": {}, "demo": True}


POLITICA_MESI = 3        # v6.89: direzione della politica monetaria = variazione del tasso negli ultimi 3 mesi
POLITICA_SOGLIA = 0.15   # punti %: sotto questa variazione la politica e' "ferma"


def politica(per_val, mesi=POLITICA_MESI):
    """v6.89 {valuta: {"d": variazione del tasso in punti negli ultimi `mesi` mesi disponibili, "stato": rialzo /
    taglio / ferma, "al": ultimo mese}}. Serve al riepilogo del grafico: per una coppia conta la DIFFERENZA tra base e
    quotata (la valuta che alza i tassi, o li taglia meno, attira capitali). Dati mensili, 1-2 mesi di ritardo."""
    out = {}
    for val, m in per_val.items():
        ks = sorted(m)
        if len(ks) <= mesi:
            continue
        d = m[ks[-1]] - m[ks[-1 - mesi]]
        out[val] = {"d": round(d, 2), "al": ks[-1],
                    "stato": "rialzo" if d >= POLITICA_SOGLIA else "taglio" if d <= -POLITICA_SOGLIA else "ferma"}
    return out


def calcola(pairs, prezzi, cot_righe=None, scarica=None, cartella=CARTELLA):
    """Tutto il carry in un passo. scarica = fonti.get_fred (sito) oppure None (demo: archivio salvato o finto).
    Aggiunge carry e carry_cot alle coppie; restituisce (dati per la pagina, studio storico per la Verifica)."""
    arch = aggiorna_tassi(scarica, cartella) if scarica else leggi(cartella)
    if not arch.get("serie"):
        arch = tassi_demo()
    per_val, ultimo = mensili(arch)
    coppie(pairs, ultimo)
    st = None
    try:
        st = studio(per_val, prezzi, cot_righe)
    except Exception as e:                         # lo studio non deve mai togliere il carry dalla tabella
        log.warning("carry: studio storico non calcolato (%s: %s)", type(e).__name__, e)
    pag = {"tassi": {v: dict(x, nome=NOMI.get(v, v)) for v, x in ultimo.items()},
           "politica": politica(per_val),
           "paniere": st["paniere"] if st else None, "min": MIN_CARRY,
           "verdetto": {k: x["verdetto"] for k, x in (st or {}).get("varianti", {}).items()}}
    return pag, st
