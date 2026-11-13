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
    test binomiale z con correzione di Bonferroni sul numero di celle della tabella (5% complessivo);
  - stabile: nella prima meta' e nella seconda meta' dello storico la differenza ha lo stesso verso.
  Le celle che non passano restano visibili in grigio (scelta di Ya).
USO: python -m cot_radar.stagionalita_orari <cartella orari> <cartella uscita>
"""
import json
import math
import os
import sys
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
def cella(rs, p0, k_celle, minimo):
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
    zc = NormalDist().inv_cdf(1 - ALFA / (2 * max(1, k_celle)))
    met = n // 2
    a, b = rs[:met], rs[met:]
    stab = bool(a and b) and ((sum(r > 0 for r in a) / len(a) - p0) * (sum(r > 0 for r in b) / len(b) - p0) > 0)
    ok = n >= minimo and abs(z) >= zc and stab
    r2 = lambda x: None if x is None else round(x, 4)   # noqa: E731
    return [n, round(pct, 1), r2(media), r2(sum(su) / k if k else None), r2(sum(giu) / len(giu) if giu else None),
            None if rap is None else round(rap, 2), round(z, 2), ok]


def tabella(gruppi, minimo):
    """{chiave: [rendimenti]} -> {chiave: cella}, con p0 = quota di rialzi su tutte le celle."""
    tutti = [r for v in gruppi.values() for r in v]
    if not tutti:
        return {}
    p0 = sum(r > 0 for r in tutti) / len(tutti)
    k = sum(1 for v in gruppi.values() if v)
    return {str(c): cella(v, p0, k, minimo) for c, v in gruppi.items() if v}


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
        "ora": {"tutti": tabella(ora_t, MIN_N["ora"]),
                **{str(g): tabella({h: v for (gg, h), v in ora_g.items() if gg == g}, MIN_N["ora"]) for g in giorni_sett}},
        "gsett": tabella(gs, MIN_N["gsett"]), "gmese": tabella(gm, MIN_N["gmese"]),
        "data": tabella(gd, MIN_N["data"]), "sett": tabella(sett, MIN_N["sett"]), "mese": tabella(mese, MIN_N["mese"]),
    }


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
        ore = orari.leggi(orari.nome_file(cartella, sym))
        if len(ore) < 24 * 200:                         # meno di ~200 giorni di candele: niente statistica
            continue
        tab = calcola_simbolo(ore)
        dal = datetime.fromtimestamp(min(ore), ROMA).date().isoformat()
        al = datetime.fromtimestamp(max(ore), ROMA).date().isoformat()
        breve = int(dal[:4]) >= 2020
        out = {"s": sym, "n": nome(sym), "f": fase, "dal": dal, "al": al, "breve": breve, **tab}
        with open(os.path.join(uscita, sym.replace("/", "_") + ".json"), "w") as fh:
            json.dump(out, fh, separators=(",", ":"))
        indice.append({"s": sym, "n": nome(sym), "f": fase, "dal": dal, "al": al, "breve": breve})
    with open(os.path.join(uscita, "indice.json"), "w") as fh:
        json.dump({"agg": datetime.now(ROMA).strftime("%Y-%m-%d %H:%M"), "fuso": "Europe/Rome",
                   "simboli": indice}, fh, separators=(",", ":"))
    log.info("stagionalita' oraria: %d strumenti calcolati", len(indice))
    return indice


if __name__ == "__main__":
    sys.exit(0 if calcola(sys.argv[1], sys.argv[2]) is not None else 2)   # 2 = ora legale sbagliata -> job fallito
