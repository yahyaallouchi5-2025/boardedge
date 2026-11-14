# -*- coding: utf-8 -*-
"""
stagionalita_orari.py - v7.62 STAGIONALITA' IN ORA DI ROMA dalle candele orarie (orari.py).

DOMANDA (Ya, 13/11/2026): "per questo strumento, in questa fascia oraria / in questo giorno / settimana / mese,
quante volte e' salito nello storico, e di quanto in media?" Tutto in ORA DI ROMA, con l'ora legale gestita da sola.

CONVERSIONE: le candele sono salvate in UTC; qui ogni candela prende l'ora di Roma con zoneinfo("Europe/Rome")
  (regole ufficiali dell'ora legale, anche per gli anni passati). controlla_ora_legale() verifica a ogni giro che i
  cambi d'ora cadano davvero l'ultima domenica di marzo e di ottobre alle 01:00 UTC: se no, log CRITICO -> email.

TABELLE (per strumento)
  orario     fascia di Roma hh:00-hh:59, per giorno della settimana e "tutti i giorni":
             rendimento della candela = chiusura / apertura - 1 (candele con almeno 30 minuti di dati)
  giornaliero giornata di Roma 00:00-24:00: prima apertura -> ultima chiusura (almeno 4 ore di mercato), divisa per
             giorno della settimana, giorno del mese e stessa data (mese-giorno)
  settimanale settimana ISO (lunedi'-domenica di Roma), per numero di settimana dell'anno
  mensile    mese di Roma, per mese dell'anno
COLONNE (come il backtester di MT5): N casi, % rialzo, media %, media dei rialzi, media dei ribassi,
  rapporto rialzi/ribassi (somma dei rialzi / somma dei ribassi, come il "profit factor"), z, affidabile.
AFFIDABILE (filtri contro le coincidenze, decisi prima di vedere i risultati):
  - abbastanza casi (orario e giorno della settimana 200, giorno del mese 60, data/settimana/mese 10);
  - la % di rialzo e' diversa da quella NORMALE dello strumento (stessa unita', tutte le celle insieme) oltre il caso:
    test binomiale z con correzione di Bonferroni sul numero di celle della tabella (5% complessivo); per ORE e
    GIORNI DELLA SETTIMANA soglia fissa |z| >= 2,58 (v7.64, vedi Z_FISSO: verificata fuori campione);
  - stabile: nella prima meta' e nella seconda meta' dello storico la differenza ha lo stesso verso.
  Le celle che non passano restano visibili in grigio (scelta di Ya).
USO: python -m cot_radar.stagionalita_orari <cartella orari> <cartella uscita>
"""
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from statistics import NormalDist
from zoneinfo import ZoneInfo

from . import orari
from .log import log

ROMA = ZoneInfo("Europe/Rome")
MIN_MINUTI = 30
MIN_ORE_GIORNO = 4
MIN_N = {"ora": 200, "gsett": 200, "gmese": 60, "data": 10, "sett": 10, "mese": 10}
ALFA = 0.05
# v7.64 STUDIO FUORI CAMPIONE (13/11/2026, 81 strumenti): una tendenza trovata nella prima meta' dello storico con
# |z| >= 2,58 si e' ripetuta nella seconda meta' il 75% delle volte per le ORE (439 casi) e il 93% per i GIORNI DELLA
# SETTIMANA (46 casi). Per giorno del mese, settimana e mese invece ~50% (= caso): li' resta la soglia corretta
# per il numero di caselle (Bonferroni), piu' severa. Con la sola Bonferroni le ore vere risultavano quasi tutte "neutre".
Z_FISSO = 2.58
NOMI = {"EUR": "Euro", "GBP": "Sterlina", "AUD": "Dollaro australiano", "NZD": "Dollaro neozelandese",
        "USD": "Dollaro USA", "CAD": "Dollaro canadese", "CHF": "Franco svizzero", "JPY": "Yen",
        "XAU": "Oro", "XAG": "Argento", "XPT": "Platino", "XPD": "Palladio"}


# --------------------------------------------------------------------------- ora legale
def controlla_ora_legale(anni=None):
    """Lista di problemi (vuota = tutto giusto). Regola UE: +1 d'inverno, +2 d'estate, cambio l'ultima domenica di
    marzo e di ottobre alle 01:00 UTC. Si controllano l'anno corrente e il successivo."""
    oggi = datetime.now(timezone.utc).year
    problemi = []
    for a in anni or (oggi, oggi + 1):
        for mese, prima, dopo in ((3, 1, 2), (10, 2, 1)):
            g = max(d for d in range(25, 32) if datetime(a, mese, d).weekday() == 6)
            t = datetime(a, mese, g, 1, 0, tzinfo=timezone.utc).timestamp()
            o1 = datetime.fromtimestamp(t - 60, ROMA).utcoffset().total_seconds() / 3600
            o2 = datetime.fromtimestamp(t + 60, ROMA).utcoffset().total_seconds() / 3600
            if (o1, o2) != (prima, dopo):
                problemi.append(f"{a}-{mese:02d}-{g:02d}: Roma UTC+{o1:g} -> UTC+{o2:g} (atteso +{prima} -> +{dopo})")
    return problemi


# --------------------------------------------------------------------------- statistiche
def cella(rs, p0, k_celle, minimo, z_fisso=None):
    """[N, % rialzo, media %, media rialzi, media ribassi, rapporto, z, affidabile] di una lista di rendimenti %
    ordinati nel tempo. p0 = quota di rialzi normale dello strumento per questa unita'."""
    n = len(rs)
    if not n:
        return None
    su = [r for r in rs if r > 0]
    giu = [r for r in rs if r < 0]
    k = len(su)
    pct = 100 * k / n
    media = sum(rs) / n
    rap = (sum(su) / -sum(giu)) if giu else None
    z = (k - n * p0) / math.sqrt(n * p0 * (1 - p0)) if 0 < p0 < 1 else 0.0
    # z_fisso (v7.64, ore e giorni della settimana): soglia fissa invece di quella corretta per il numero di caselle
    zc = z_fisso if z_fisso else NormalDist().inv_cdf(1 - ALFA / (2 * max(1, k_celle)))
    met = n // 2
    a, b = rs[:met], rs[met:]
    stab = bool(a and b) and ((sum(r > 0 for r in a) / len(a) - p0) * (sum(r > 0 for r in b) / len(b) - p0) > 0)
    ok = n >= minimo and abs(z) >= zc and stab
    r2 = lambda x: None if x is None else round(x, 4)   # noqa: E731
    return [n, round(pct, 1), r2(media), r2(sum(su) / k if k else None), r2(sum(giu) / len(giu) if giu else None),
            None if rap is None else round(rap, 2), round(z, 2), ok]


def tabella(gruppi, minimo, z_fisso=None):
    """{chiave: [rendimenti]} -> {chiave: cella}, con p0 = quota di rialzi su tutte le celle."""
    tutti = [r for v in gruppi.values() for r in v]
    if not tutti:
        return {}
    p0 = sum(r > 0 for r in tutti) / len(tutti)
    k = sum(1 for v in gruppi.values() if v)
    return {str(c): cella(v, p0, k, minimo, z_fisso) for c, v in gruppi.items() if v}


def calcola_simbolo(ore):
    """{ts UTC: [o, h, l, c, n]} -> tabelle in ora di Roma."""
    ora_g = {}                                  # (giorno sett., ora) -> rendimenti
    ora_t = {}                                  # ora -> rendimenti (tutti i giorni)
    giorni = {}                                 # data Roma -> [prima apertura, ultima chiusura, ore]
    for ts in sorted(ore):
        o, h, l, c, n = ore[ts]
        d = datetime.fromtimestamp(ts, ROMA)
        if n >= MIN_MINUTI:
            r = (c / o - 1) * 100
            ora_g.setdefault((d.weekday(), d.hour), []).append(r)
            ora_t.setdefault(d.hour, []).append(r)
        g = giorni.get(d.date())
        if g is None:
            giorni[d.date()] = [o, c, 1]
        else:
            g[1], g[2] = c, g[2] + 1
    gs, gm, gd, sett, mese = {}, {}, {}, {}, {}
    sett_acc, mese_acc = {}, {}
    for d in sorted(giorni):
        o, c, n = giorni[d]
        iso = d.isocalendar()
        s = sett_acc.setdefault((iso[0], iso[1]), [o, c])
        s[1] = c
        m = mese_acc.setdefault((d.year, d.month), [o, c])
        m[1] = c
        if n < MIN_ORE_GIORNO:
            continue
        r = (c / o - 1) * 100
        gs.setdefault(d.weekday(), []).append(r)
        gm.setdefault(d.day, []).append(r)
        gd.setdefault(f"{d.month:02d}-{d.day:02d}", []).append(r)
    # l'ultima settimana e l'ultimo mese possono essere ancora in corso: si tolgono
    for acc, out, chiave in ((sett_acc, sett, lambda k: k[1]), (mese_acc, mese, lambda k: k[1])):
        ks = sorted(acc)[:-1]
        for k in ks:
            o, c = acc[k]
            out.setdefault(chiave(k), []).append((c / o - 1) * 100)
    giorni_sett = sorted({k[0] for k in ora_g})
    return {
        "ora": {"tutti": tabella(ora_t, MIN_N["ora"], Z_FISSO),
                **{str(g): tabella({h: v for (gg, h), v in ora_g.items() if gg == g}, MIN_N["ora"], Z_FISSO)
                   for g in giorni_sett}},
        "gsett": tabella(gs, MIN_N["gsett"], Z_FISSO), "gmese": tabella(gm, MIN_N["gmese"]),
        "data": tabella(gd, MIN_N["data"]), "sett": tabella(sett, MIN_N["sett"]), "mese": tabella(mese, MIN_N["mese"]),
    }


# --------------------------------------------------------------------------- v7.64 giornaliero da Yahoo
# EODHD non fornisce piu' candele orarie di oro e argento dopo ottobre 2020 (e il venerdi' sera manca): per le viste
# Giornaliero, Settimanale e Mensile si usano i future continui di Yahoo (COMEX, dal 2000). L'Orario resta EODHD.
# ORA DI ROMA: la sessione COMEX va dalle 18:00 alle 17:00 di New York = dalle 00:00 alle 23:00 di Roma (6 ore di
# scarto quasi tutto l'anno), quindi la data di Yahoo (fuso di New York, ora legale compresa) e' la giornata di Roma.
# La "chiusura" giornaliera di Yahoo e' il prezzo di regolamento COMEX delle 13:30 di New York (19:30 di Roma):
# verificato il 13/11/2026 confrontando 2013-2020 con le candele orarie EODHD (correlazione massima su quell'ora).
# RENDIMENTO = chiusura / chiusura del giorno prima: l'apertura di Yahoo nei primi anni e' spesso uguale alla
# chiusura (non affidabile). Settimana e mese = ultima chiusura / ultima chiusura del periodo prima; quelli in corso
# si tolgono. Il cambio di scadenza del future aggiunge un piccolo salto in alcuni giorni (oro: circa lo 0,3%).
YAHOO_GIORNO = {"XAUUSD.FOREX": "GC=F", "XAGUSD.FOREX": "SI=F", "NZDUSD.FOREX": "NZDUSD=X",
                "GSPC.INDX": "^GSPC", "NDX.INDX": "^NDX", "DJI.INDX": "^DJI", "GDAXI.INDX": "^GDAXI",
                "FCHI.INDX": "^FCHI", "STOXX50E.INDX": "^STOXX50E", "FTSE.INDX": "^FTSE", "N225.INDX": "^N225",
                "HSI.INDX": "^HSI", "FTSEMIB.INDX": "FTSEMIB.MI", "VIX.INDX": "^VIX"}
# v7.65 FOREX, ORE DELLA CHIUSURA DI NEW YORK (17:00 di New York = 23:00 di Roma, 22:00 nelle settimane di ora legale
# sfasata, piu' l'ora dopo): gli spread si allargano e il prezzo fa un movimento meccanico che si ripete ogni giorno.
# Studio del 14/11/2026 su 27 coppie: il 61% delle operazioni "affidabili" e quasi tutto il guadagno lordo cadevano
# in queste ore; tolte, il lordo scende da +0,013% a +0,004% a operazione (costo ~0,015%). E' un effetto dei dati,
# non una tendenza prendibile: le caselle restano visibili ma senza il bordo oro.
ORE_CHIUSURA_NY = ("22", "23", "0")
MIN_ANNI = 10                                            # v7.64: sotto i 10 anni di storico una tabella non si mostra
YAHOO_URL = "https://{h}.finance.yahoo.com/v8/finance/chart/{t}?{q}"


def yahoo_chiusure(ticker, cartella, tentativi=3):
    """{data ISO: chiusura} dei future giornalieri di Yahoo dal 2000. Copia in <cartella>/_yahoo_<ticker>.json:
    se Yahoo non risponde si usa l'ultima copia salvata (lo storico non cambia)."""
    copia = os.path.join(cartella, "_yahoo_" + ticker.replace("=", "_").replace("^", "") + ".json")
    time.sleep(1)                                       # una richiesta al secondo: Yahoo limita chi chiede troppo
    q = urllib.parse.urlencode({"period1": 0, "period2": int(time.time()), "interval": "1d"})
    for n in range(tentativi):
        try:
            req = urllib.request.Request(YAHOO_URL.format(h=("query1", "query2")[n % 2], t=urllib.parse.quote(ticker), q=q),
                                         headers={"User-Agent": "cot-radar/stagionalita"})
            with urllib.request.urlopen(req, timeout=30) as r:
                res = json.load(r)["chart"]["result"][0]
            # ATTENZIONE: gmtoffset e' lo scarto di OGGI (-5 h d'inverno): applicato alle candele estive (mezzanotte di
            # New York = 04:00 UTC) le sposterebbe al giorno prima. Si usa il fuso della borsa con l'ora legale giusta.
            fuso = ZoneInfo(res["meta"].get("exchangeTimezoneName") or "America/New_York")
            qq = res["indicators"]["quote"][0]
            out, prima = {}, None
            for ts, c, v in zip(res.get("timestamp") or [], qq.get("close") or [], qq.get("volume") or []):
                if c is None or c <= 0:
                    continue
                if prima is not None and c == prima and not v:      # festivo: riga copiata senza scambi
                    continue
                out[datetime.fromtimestamp(ts, fuso).date().isoformat()] = float(c)
                prima = c
            if len(out) > 1000:
                with open(copia, "w") as fh:
                    json.dump(out, fh, separators=(",", ":"))
                return out
            log.warning("Yahoo %s: storico troppo corto (%d giorni)", ticker, len(out))
        except Exception as e:
            log.warning("Yahoo %s: %s (tentativo %d/%d)", ticker, getattr(e, "code", type(e).__name__), n + 1, tentativi)
        time.sleep(2 * (3 ** n))
    try:
        with open(copia) as fh:
            log.info("Yahoo %s: uso la copia salvata", ticker)
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def calcola_giorni(chiusure):
    """{data ISO: chiusura} -> tabelle gsett, gmese, data, sett, mese (stesse colonne e filtri delle tabelle orarie)."""
    gs, gm, gd, sett, mese = {}, {}, {}, {}, {}
    fine_s, fine_m = {}, {}                                  # ultima chiusura di ogni settimana ISO e di ogni mese
    prec = None
    for ds in sorted(chiusure):
        d = datetime.strptime(ds, "%Y-%m-%d").date()
        c = chiusure[ds]
        if prec is not None:
            r = (c / prec - 1) * 100
            gs.setdefault(d.weekday(), []).append(r)
            gm.setdefault(d.day, []).append(r)
            gd.setdefault(f"{d.month:02d}-{d.day:02d}", []).append(r)
        prec = c
        iso = d.isocalendar()
        fine_s[(iso[0], iso[1])] = c
        fine_m[(d.year, d.month)] = c
    for fine, out in ((fine_s, sett), (fine_m, mese)):
        ks = sorted(fine)[:-1]                               # l'ultimo periodo puo' essere ancora in corso
        for a, b in zip(ks, ks[1:]):
            out.setdefault(b[1], []).append((fine[b] / fine[a] - 1) * 100)
    return {"gsett": tabella(gs, MIN_N["gsett"], Z_FISSO), "gmese": tabella(gm, MIN_N["gmese"]),
            "data": tabella(gd, MIN_N["data"]), "sett": tabella(sett, MIN_N["sett"]), "mese": tabella(mese, MIN_N["mese"])}


def nome(sym):
    s = sym.split(".")[0]
    if sym.endswith(".FOREX") and len(s) == 6:
        return f"{NOMI.get(s[:3], s[:3])} / {NOMI.get(s[3:], s[3:])}"
    return s


def calcola(cartella, uscita):
    """Calcola tutti i simboli scaricati e scrive <uscita>/<simbolo>.json + indice.json. Controlla l'ora legale."""
    problemi = controlla_ora_legale()
    if problemi:
        log.critical("stagionalita' oraria: ORA LEGALE DI ROMA NON CORRISPONDE (%s): calcolo sospeso",
                     "; ".join(problemi))
        return None
    os.makedirs(uscita, exist_ok=True)
    indice = []
    for sym, fase, _ in orari.universo():
        ore = orari.utc_vero(sym, orari.leggi(orari.nome_file(cartella, sym)))   # v7.65 forex vecchio: da ora di New York a UTC
        # v7.64 REGOLA DEI 10 ANNI (scelta di Ya): una tabella si mostra solo con almeno 10 anni di storico.
        #  - candele orarie EODHD >= 10 anni -> tutte le viste (Orario compreso);
        #  - meno di 10 anni ma Yahoo ha >= 10 anni di chiusure giornaliere -> solo Giornaliero, Settimanale, Mensile;
        #  - altrimenti lo strumento non compare.
        anni_ore = (max(ore) - min(ore)) / (365.25 * 86400) if ore else 0
        ch = yahoo_chiusure(YAHOO_GIORNO[sym], cartella) if sym in YAHOO_GIORNO else {}
        anni_g = ((datetime.strptime(max(ch), "%Y-%m-%d") - datetime.strptime(min(ch), "%Y-%m-%d")).days / 365.25
                  if ch else 0)
        con_ore = anni_ore >= MIN_ANNI and len(ore) >= 24 * 200
        if not con_ore and anni_g < MIN_ANNI:
            continue
        out = {"s": sym, "n": nome(sym), "f": fase}
        if con_ore:
            out.update(calcola_simbolo(ore))
            if sym.endswith(".FOREX"):                  # v7.65 chiusura di New York: mai "affidabile" (vedi ORE_CHIUSURA_NY)
                for tab in out["ora"].values():
                    for h in ORE_CHIUSURA_NY:
                        if tab.get(h):
                            tab[h][7] = False
            out["dal"] = datetime.fromtimestamp(min(ore), ROMA).date().isoformat()
            out["al"] = datetime.fromtimestamp(max(ore), ROMA).date().isoformat()
        else:
            out["solo_giorni"] = True                   # la pagina nasconde l'Orario e la casella della fascia oraria
        if anni_g >= MIN_ANNI:                          # Giornaliero, Settimanale e Mensile da Yahoo (storia piu' lunga)
            out.update(calcola_giorni(ch))
            out["dal_g"], out["al_g"] = min(ch), max(ch)
            if not con_ore:
                out["dal"], out["al"] = out["dal_g"], out["al_g"]
        with open(os.path.join(uscita, sym.replace("/", "_") + ".json"), "w") as fh:
            json.dump(out, fh, separators=(",", ":"))
        indice.append({k: out[k] for k in ("s", "n", "f", "dal", "al")} | ({"solo_giorni": True} if not con_ore else {}))
    with open(os.path.join(uscita, "indice.json"), "w") as fh:
        json.dump({"agg": datetime.now(ROMA).strftime("%Y-%m-%d %H:%M"), "fuso": "Europe/Rome",
                   "simboli": indice}, fh, separators=(",", ":"))
    log.info("stagionalita' oraria: %d strumenti calcolati", len(indice))
    return indice


if __name__ == "__main__":
    from .log import setup                              # messaggi a schermo (log di GitHub Actions)
    setup()
    sys.exit(0 if calcola(sys.argv[1], sys.argv[2]) is not None else 2)   # 2 = ora legale sbagliata -> job fallito
