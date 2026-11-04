# -*- coding: utf-8 -*-
"""
satellite.py - LE 5 AZIONI DEI PORTAFOGLI MODELLO (quota "Azioni scelte" di conservativo, moderato e aggressivo)

IDEA
  Ogni mese i portafogli tengono, accanto alla base di ETF, una quota di 5 azioni prese dall'Azionario
  (10% conservativo, 20% moderato, 40% aggressivo: i pesi stanno in portafogli.py). Questo modulo gira nel
  workflow serale delle azioni (azioni.yml), dove ci sono gli storici di tutti i ~1.000 titoli, e scrive
  pubblico/satellite.json, che il sito legge quando calcola i portafogli.

REGOLA (uguale per lo storico simulato e per il live)
  Alla chiusura del mese t, per ogni titolo, usando SOLO prezzi mensili fino a t:
    - rendimento a 12 mesi > 0, a 3 mesi > 0, prezzo sopra la media degli ultimi 10 mesi (~200 giorni);
    - non piu' del 15% sotto il massimo degli ultimi 12 mesi;
    - il mese che entra e' stato positivo in almeno il 60% degli anni passati, con almeno 8 anni e media > 0;
  tra quelli che passano, punteggio dell'Azionario (percentili pesati, azioni.PESI), poi i primi 5 con al massimo
  1 titolo per settore, a pari peso. Se ne passano meno di 5 i posti vuoti restano in liquidita'.
  Il filtro di MERCATO (S&P 500 sotto la media a 200 giorni -> tutta la quota in liquidita') lo applica
  portafogli.py a ogni rotazione, come per gli ETF della base.

STORICO SIMULATO vs LIVE
  - storico: dal 2005 all'ultimo mese chiuso prima del LIVE_DAL, ricalcolato a ogni giro. E' OTTIMISTICO:
    usa i titoli che OGGI stanno negli indici (le aziende fallite o uscite non ci sono = "survivorship bias").
  - live: dal LIVE_DAL ogni scelta viene REGISTRATA (satellite_registro.json, mai riscritto) con il prezzo di
    chiusura del giorno in cui e' fatta. L'ultimo giorno di borsa del mese, dopo la chiusura, si registrano i 5
    titoli del mese dopo (cosi' sono pronti per la rotazione del primo giorno di borsa); se quel giro salta,
    si registrano al primo giro utile del mese con il prezzo di quel giorno (niente prezzi gia' passati).

DEBUG: python -c "from cot_radar import satellite; help(satellite.calcola)"
"""
import json
import os
from bisect import bisect_right
from datetime import date, timedelta

from . import azioni as A
from .log import log

N = 5                          # titoli nella quota
COSTO = 0.002                  # 0,20% su ogni titolo che entra o esce (commissioni + spread delle azioni)
DAL = "2005-01"                # primo mese di decisione dello storico simulato
LIVE_DAL = "2026-11"           # primo mese registrato dal vivo
MIN_ANNI = A.MIN_ANNI_STAG     # anni minimi di stagionalita' (8)
REGISTRO = "satellite_registro.json"
SFIDANTE = "satellite_sfidante.json"   # registro separato dello sfidante a 10 titoli (Forecaster), mai riscritto
SFIDANTE_N = 10
# v6.57: borse di solito NON accessibili ai privati dai broker europei (India, Cina continentale): i loro titoli
# restano nell'Azionario ma non entrano nelle 5 azioni dei portafogli (non si potrebbero comprare davvero).
# v6.90: anche TOKYO (.T) e HONG KONG (.HK): su Scalable Capital (il broker di riferimento) si comprano solo titoli
# con ISIN quotati in euro, e le azioni giapponesi/di Hong Kong di solito non ci sono (es. Baycurrent, novembre 2026).
# Se il migliore non e' acquistabile si passa al candidato successivo che supera gli stessi filtri, anche di un
# altro settore (sempre al massimo 1 titolo per settore).
NON_UE = (".NS", ".BO", ".SS", ".SZ", ".T", ".HK")
# v6.90 SOSTITUZIONI nei mesi gia' registrati PRIMA della regola nuova (il registro non si riscrive mai): i titoli non
# acquistabili sono sostituiti dal candidato acquistabile che la regola v6.90 avrebbe scelto alla stessa data, con
# il prezzo di chiusura del giorno di registrazione (stessa partenza degli altri titoli del mese).
SOSTITUZIONI = {"2026-11": {"6532.T": "EXPD", "2801.T": "LYB"}}


# --------------------------------------------------------------------------- mesi come numeri interi
def _n(ym):
    """'AAAA-MM' -> numero progressivo del mese."""
    return int(ym[:4]) * 12 + int(ym[5:7]) - 1


def _ym(n):
    return "%d-%02d" % (n // 12, n % 12 + 1)


# --------------------------------------------------------------------------- storico mensile di un titolo
def serie_mensile(rec):
    """{mese intero: prezzo di fine mese} dal record grezzo. Gli ultimi ~24 mesi vengono dai prezzi GIORNALIERI
    (aggiornati ogni sera, mentre lo storico mensile si riscarica una volta a settimana): chiusura dell'ultimo giorno
    di ogni mese. Lo storico mensile piu' vecchio viene riscalato sul giornaliero (i prezzi rettificati per i
    dividendi cambiano all'indietro), usando un mese chiuso presente in entrambi."""
    m = rec.get("m") or []
    if not A.mensile_ok(m):
        return None
    out = {_n(x): v for x, v in m}
    d = rec.get("d") or []
    if d:
        fine = {}
        for x, v in d:
            fine[_n(x[:7])] = v                      # l'ultimo giorno di ogni mese vince
        chiusi = [k for k in sorted(fine) if k in out and k < max(fine)]
        if chiusi:
            k = chiusi[-1]
            f = fine[k] / out[k] if out[k] else 1.0
            out = {x: v * f for x, v in out.items()}
        out.update(fine)
    return out


class Titolo:
    """Prezzi mensili + stagionalita' cumulata (per sapere in O(log n) la stagionalita' fino a un certo mese)."""

    def __init__(self, t, nome, settore, s):
        self.t, self.nome, self.s, self.p = t, nome, settore, s
        self.cal = {}                                  # mese di calendario -> ([mese], [somma r], [n positivi])
        for k in sorted(s):
            if k - 1 in s and s[k - 1]:
                r = s[k] / s[k - 1] - 1
                mesi, somme, pos = self.cal.setdefault(k % 12, ([], [], []))
                mesi.append(k)
                somme.append((somme[-1] if somme else 0) + r)
                pos.append((pos[-1] if pos else 0) + (r > 0))

    def stag(self, mese_cal, fino):
        """(n anni, media, % positivi) del mese di calendario (0-11) con dati fino al mese intero `fino` incluso."""
        c = self.cal.get(mese_cal)
        if not c:
            return 0, None, None
        i = bisect_right(c[0], fino)
        if not i:
            return 0, None, None
        return i, c[1][i - 1] / i, 100 * c[2][i - 1] / i

    def riga(self, t):
        """Indicatori alla chiusura del mese t per scegliere il mese t+1 (None se mancano dati)."""
        p = self.p
        ser = [p.get(t - k) for k in range(13)]
        if any(v is None or v <= 0 for v in ser):
            return None
        v = ser[0]
        n, med, pos = self.stag((t + 1) % 12, t)
        return {"t": self.t, "n": self.nome, "s": self.s,
                "v1a": v / ser[12] - 1, "v3m": v / ser[3] - 1, "t200": v / (sum(ser[:10]) / 10) - 1,
                "dmax": v / max(ser[:12]) - 1, "st_media": med, "st_pos": pos, "st_n": n}


def carica(cartella, titoli=None):
    """[Titolo] dalle copie grezze (cartella/grezzi/<T>.json). Senza storico mensile valido il titolo e' escluso."""
    out = []
    for x in titoli if titoli is not None else A.elenco():
        if x["t"].endswith(NON_UE):
            continue
        rec = A._leggi(os.path.join(cartella, "grezzi", A._nome_file(x["t"]) + ".json"))
        s = serie_mensile(rec) if rec else None
        if s:
            out.append(Titolo(x["t"], rec.get("nome") or x["nome"], x["s"], s))
    return out


def candidati(titoli, t):
    """Titoli che passano i filtri della regola alla chiusura del mese t, ordinati per punteggio."""
    righe = [r for r in (x.riga(t) for x in titoli) if r]
    if not righe:
        return []
    A.punteggi(righe)
    ok = [r for r in righe if r["v1a"] > 0 and r["v3m"] > 0 and r["t200"] > 0 and r["dmax"] > -0.15
          and (r["st_media"] or -1) > 0 and (r["st_pos"] or 0) >= 60 and r["st_n"] >= MIN_ANNI]
    return sorted(ok, key=lambda x: (-x["pt"], x["t"]))


def scelta_libera(titoli, t, n=None):
    """SFIDANTE del Forecaster: stessa regola ma 10 titoli e nessun limite per settore."""
    return candidati(titoli, t)[:n or SFIDANTE_N]


def scelta(titoli, t, n=N):
    """I titoli scelti alla chiusura del mese intero t (per il mese t+1): righe con punteggio 'pt'."""
    ok = candidati(titoli, t)
    out, settori = [], set()
    for r in ok:
        if r["s"] in settori:
            continue
        settori.add(r["s"])
        out.append(r)
        if len(out) == n:
            break
    return out


# --------------------------------------------------------------------------- storico simulato
def storico(titoli, fino):
    """[[mese 'AAAA-MM', rendimento del mese, [ticker]]] dal DAL al mese intero `fino` incluso (mesi chiusi).
    Rendimento = media dei titoli scelti alla fine del mese prima (posti vuoti = 0), meno i costi di cambio."""
    per = {x.t: x for x in titoli}
    out, prima = [], set()
    for t in range(_n(DAL), fino):
        sc = scelta(titoli, t)
        r = sum(per[x["t"]].p[t + 1] / per[x["t"]].p[t] - 1 for x in sc if t + 1 in per[x["t"]].p) / N
        ora = {x["t"] for x in sc}
        r -= COSTO * len(ora ^ prima) / N
        prima = ora
        # 4o elemento (v6.52): rendimento del mese di ogni titolo scelto, per il dettaglio "Ultime rotazioni"
        det = {x["t"]: round(per[x["t"]].p[t + 1] / per[x["t"]].p[t] - 1, 5) for x in sc if t + 1 in per[x["t"]].p}
        out.append([_ym(t + 1), round(r, 5), sorted(ora), det])
    return out


def mese_chiuso(oggi):
    """True se nel mese di 'oggi' non restano giorni di borsa: weekend dopo l'ultimo feriale, oppure l'ultimo feriale
    dopo la chiusura di Wall Street (21 UTC)."""
    return _ultimo_giorno_mese(oggi) and (oggi.weekday() >= 5 or ora_utc(oggi) >= 21)


def ora_utc(oggi):
    """Ora UTC adesso se 'oggi' e' davvero oggi; 0 per date passate o future (test): niente chiusura anticipata."""
    from datetime import datetime, timezone
    adesso = datetime.now(timezone.utc)
    return adesso.hour if adesso.date() == oggi else 0


# --------------------------------------------------------------------------- live (registro immutabile)
def _ultimo_giorno_mese(oggi):
    """True se oggi e' l'ultimo giorno feriale del mese (le festivita' di borsa non sono considerate)."""
    d = oggi + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.month != oggi.month


def _ultimo_prezzo(cartella, t):
    rec = A._leggi(os.path.join(cartella, "grezzi", A._nome_file(t) + ".json")) or {}
    d = rec.get("d") or []
    return (d[-1][0], d[-1][1]) if d else (None, None)


def _dopo_chiusura(oggi, ora=None):
    """True se e' l'ultimo giorno feriale del mese e Wall Street ha gia' chiuso (21 UTC) o e' weekend.
    ora = ora UTC; se manca: quella vera per oggi, 24 per i giorni passati (gia' chiusi)."""
    if ora is None:
        from datetime import datetime, timezone
        adesso = datetime.now(timezone.utc)
        ora = adesso.hour if adesso.date() == oggi else 24
    return _ultimo_giorno_mese(oggi) and (oggi.weekday() >= 5 or ora >= 21)


def registra(cartella, titoli, oggi, ora=None):
    """Aggiunge al registro la scelta del mese giusto se manca (vedi docstring del modulo). Mai riscritto.
    v6.65: la scelta del mese dopo si registra solo DOPO la chiusura dell'ultimo giorno (prima un giro partito dopo la
    mezzanotte UTC registrava novembre 2026 con le chiusure USA del 29 ottobre invece che del 30)."""
    f = os.path.join(cartella, REGISTRO)
    reg = A._leggi(f) or {}
    cur = _n(oggi.strftime("%Y-%m"))
    if _dopo_chiusura(oggi, ora):
        mese, t = cur + 1, cur                 # dopo la chiusura dell'ultimo giorno: il mese corrente e' completo
    else:
        mese, t = cur, cur - 1                 # ripiego: primo giro utile del mese, dati fino al mese prima
    if _ym(mese) < LIVE_DAL or _ym(mese) in reg:
        return reg
    sc = scelta(titoli, t)
    voci = []
    for x in sc:
        giorno, p0 = _ultimo_prezzo(cartella, x["t"])
        if p0:
            voci.append({"t": x["t"], "n": x["n"], "s": x["s"], "p0": p0, "pt": x["pt"],
                         "v1a": round(x["v1a"] * 100, 1), "st_pos": round(x["st_pos"]), "st_n": x["st_n"]})
    giorni = [_ultimo_prezzo(cartella, v["t"])[0] for v in voci]
    reg[_ym(mese)] = {"dal": max(giorni) if giorni else oggi.isoformat(), "registrato": A.ora_italia().strftime("%Y-%m-%d %H:%M"),
                      "titoli": voci}
    A._scrivi(f, reg)
    log.info("satellite: registrati %d titoli per %s (%s)", len(voci), _ym(mese), ", ".join(v["t"] for v in voci))
    return reg


def con_sostituzioni(cartella, reg, titoli):
    """Copia del registro con le SOSTITUZIONI applicate (il file del registro resta com'e'). Ogni titolo sostituito
    porta "sost" e "sost_n" (ticker e nome del titolo registrato all'origine) per la pagina."""
    nomi = {x.t: (x.nome, x.s) for x in titoli or []}
    out = {}
    for mese, v in reg.items():
        cambi = SOSTITUZIONI.get(mese) or {}
        voci = []
        for x in v["titoli"]:
            nuovo = cambi.get(x["t"])
            p0 = _prezzo_al_giorno(cartella, nuovo, v["dal"]) if nuovo else None
            if nuovo and p0:
                n, s = nomi.get(nuovo, (nuovo, x["s"]))
                voci.append({"t": nuovo, "n": n, "s": s, "p0": p0, "sost": x["t"], "sost_n": x["n"]})
            else:
                voci.append(x)
        out[mese] = dict(v, titoli=voci)
    return out


def _prezzo_al_giorno(cartella, t, giorno):
    """Ultimo prezzo di chiusura del titolo entro il giorno 'AAAA-MM-GG' (None se manca)."""
    rec = A._leggi(os.path.join(cartella, "grezzi", A._nome_file(t) + ".json")) or {}
    d = [x for x in rec.get("d") or [] if x[0] <= giorno]
    return d[-1][1] if d else None


def live(cartella, reg):
    """Indice giornaliero della quota dal primo mese registrato: [[data, valore]] (parte da 1).
    Ogni mese: media dei titoli registrati (prezzo / prezzo di registrazione; posti vuoti = 1), concatenata."""
    out, v0, prima = [], 1.0, set()
    for mese in sorted(reg):
        voci = reg[mese]["titoli"]
        dal = reg[mese]["dal"]
        ora = {x["t"] for x in voci}
        v0 *= 1 - COSTO * len(ora ^ prima) / N
        prima = ora
        serie = {}
        for x in voci:
            rec = A._leggi(os.path.join(cartella, "grezzi", A._nome_file(x["t"]) + ".json")) or {}
            serie[x["t"]] = {d: p for d, p in rec.get("d") or [] if d > dal and d[:7] <= mese}
        giorni = sorted({d for s in serie.values() for d in s})
        if not out:
            out.append([dal, round(v0, 5)])
        ultimo = {x["t"]: x["p0"] for x in voci}
        val = v0
        for d in giorni:
            for x in voci:
                if d in serie[x["t"]]:
                    ultimo[x["t"]] = serie[x["t"]][d]
            val = v0 * (sum(ultimo[x["t"]] / x["p0"] for x in voci) + (N - len(voci))) / N
            out.append([d, round(val, 5)])
        v0 = val
    return out


# --------------------------------------------------------------------------- sfidante a 10 titoli (Forecaster)
def _prezzo_al(cartella, t, ym):
    """(data, prezzo) dell'ultimo prezzo giornaliero del titolo entro il mese 'AAAA-MM'."""
    rec = A._leggi(os.path.join(cartella, "grezzi", A._nome_file(t) + ".json")) or {}
    d = [x for x in rec.get("d") or [] if x[0][:7] <= ym]
    return (d[-1][0], d[-1][1]) if d else (None, None)


def sfidante(cartella, titoli, reg, oggi):
    """Registro separato dello sfidante (10 titoli, nessun limite per settore): per ogni mese gia' registrato dalla
    regola vera si registra anche la scelta libera, con i soli prezzi fino alla chiusura del mese prima (prezzo di
    ingresso = ultima chiusura di quel mese). Restituisce i rendimenti dei mesi chiusi e del mese in corso."""
    f = os.path.join(cartella, SFIDANTE)
    sr = A._leggi(f) or {}
    nuovi = False
    for mese in sorted(reg):
        if mese in sr or not titoli:
            continue
        t = _n(mese) - 1
        voci = []
        for x in scelta_libera(titoli, t):
            d, p0 = _prezzo_al(cartella, x["t"], _ym(t))
            if p0:
                voci.append({"t": x["t"], "n": x["n"], "s": x["s"], "p0": p0, "d0": d, "pt": x["pt"]})
        sr[mese] = {"registrato": A.ora_italia().strftime("%Y-%m-%d %H:%M"), "titoli": voci}
        nuovi = True
    if nuovi:
        A._scrivi(f, sr)
    cur = oggi.strftime("%Y-%m")
    mesi, corrente, prima = {}, None, set()
    for mese in sorted(sr):
        voci = sr[mese]["titoli"]
        ora = {x["t"] for x in voci}
        c = COSTO * len(ora ^ prima) / SFIDANTE_N if prima else 0.0      # il primo mese parte senza costi
        prima = ora
        rr, al = [], None
        for x in voci:
            d, p = _prezzo_al(cartella, x["t"], mese)
            if p and d > x["d0"]:
                rr.append(p / x["p0"] - 1)
                al = max(al or d, d)
        r = round(sum(rr) / SFIDANTE_N - c, 5)                          # posti vuoti = liquidita' (0)
        if mese < cur or (mese == cur and mese_chiuso(oggi)):
            mesi[mese] = r
        elif al:
            corrente = {"mese": mese, "r": r, "al": al}
    return {"n": SFIDANTE_N, "registro": sr, "mesi": mesi, "corrente": corrente}


# --------------------------------------------------------------------------- giro completo
def calcola(cartella, oggi=None, titoli=None, anomalia=False):
    """Scrive cartella/pubblico/satellite.json e restituisce il dizionario. Con l'anomalia di Yahoo (dati vecchi)
    non registra nuove scelte live: le registrera' il primo giro buono."""
    oggi = oggi or date.today()
    tt = carica(cartella, titoli)
    reg = A._leggi(os.path.join(cartella, REGISTRO)) or {}
    if not anomalia and tt:
        reg = registra(cartella, tt, oggi)
    reg_eff = con_sostituzioni(cartella, reg, tt)          # v6.90: titoli acquistabili su Scalable
    cur = _n(oggi.strftime("%Y-%m"))
    # v6.62: il mese corrente e' CHIUSO anche prima del 1 del mese dopo se non restano giorni di borsa (es. sabato 31
    # ottobre, o venerdi' 30 dopo la chiusura): prima ottobre restava fuori fino a novembre e nel portafoglio la quota
    # "Azioni scelte" risultava piatta (0%) per tutto il mese.
    fino = min(cur if mese_chiuso(oggi) else cur - 1, _n(LIVE_DAL) - 1)   # solo mesi chiusi e prima del live
    st = storico(tt, fino) if tt else []
    # ANTEPRIMA dei titoli del mese prossimo: la stessa regola applicata ai prezzi di OGGI (mese non ancora chiuso).
    # Serve a chi vuole prepararsi: e' PROVVISORIA, la lista che conta e' quella registrata l'ultimo giorno di borsa.
    ante = None
    if tt and _ym(cur + 1) not in reg:
        ante = {"mese": _ym(cur + 1), "al": oggi.isoformat(),
                "titoli": [{"t": x["t"], "n": x["n"], "s": x["s"], "pt": x["pt"], "v1a": round(x["v1a"] * 100, 1)}
                           for x in scelta(tt, cur)]}
    sf10 = None
    try:                                     # isolato: un errore dello sfidante non tocca la quota vera
        sf10 = sfidante(cartella, tt if not anomalia else [], reg, oggi)
    except Exception as e:
        log.warning("satellite: sfidante a 10 titoli non calcolato: %s", e)
    dati = {"aggiornato": oggi.isoformat(), "n": N, "costo": COSTO, "live_dal": LIVE_DAL, "titoli_universo": len(tt),
            "storico": st, "live": live(cartella, reg_eff), "registro": reg_eff, "anteprima": ante,
            "sfidante10": sf10,
            # nomi dei titoli scelti negli ultimi 13 mesi dello storico (per mostrarli nelle rotazioni)
            "nomi": {x.t: x.nome for x in tt if any(x.t in m[2] for m in st[-13:])},
            "nota": "Azioni scelte: storico simulato con i titoli che oggi stanno negli indici, quindi ottimistico "
                    "(le aziende fallite o uscite non ci sono). Da " + A.MESI_IT[int(LIVE_DAL[5:]) - 1] + " " + LIVE_DAL[:4]
                    + " contano solo le scelte registrate dal vivo."}
    A._scrivi(os.path.join(cartella, "pubblico", "satellite.json"), dati)
    return dati


def leggi(cartella_locale=None, ramo="azioni"):
    """satellite.json per il sito: da una cartella (prova sul PC) o dal ramo git "azioni" (GitHub). None se manca."""
    if cartella_locale:
        return A._leggi(os.path.join(cartella_locale, "pubblico", "satellite.json"))
    import subprocess
    try:
        subprocess.run(["git", "fetch", "-q", "--depth", "1", "origin", ramo], check=True, timeout=120,
                       capture_output=True)
        txt = subprocess.run(["git", "show", "FETCH_HEAD:pubblico/satellite.json"], check=True, timeout=60,
                             capture_output=True).stdout
        return json.loads(txt)
    except Exception as e:
        log.warning("satellite: dati del ramo %s non disponibili (%s)", ramo, type(e).__name__)
        return None
