# -*- coding: utf-8 -*-
"""
studio_pattern_eodhd.py - RIPROVA dello studio del Pattern Detector con candele EODHD come quelle di un broker.

PERCHE': il primo studio (11/11/2026) usava candele daily Yahoo, che per il forex si chiudono a mezzanotte di
Londra; i broker (MT4/MT5) chiudono la giornata alle 17:00 di New York (23:00 in Italia). Per un pattern a 3
candele il confine della candela cambia la forma: il verdetto va rifatto con dati allineati come un broker.
L'H4 non era mai stato studiato sul lungo periodo.

DATI: EODHD, candele ORARIE (endpoint intraday, interval=1h) di forex, oro, argento e platino spot.
  - H4: aggregate con la stessa funzione del sito (pattern.h4): 17-21, 21-01, 01-05, 05-09, 09-13, 13-17 di New York;
  - D1: giornata 17:00 -> 17:00 di New York (come i broker), weekend scartato come nell'H4.
REGOLE (fissate PRIMA di vedere i risultati, identiche allo studio del sito, funzione pattern.studio):
  ingresso alla chiusura della candela 3, stop all'estremo del pattern, target 1R o 2R, uscita entro 10 candele,
  costi forex 0,02% e metalli 0,06% del prezzo; varianti: tutti, a favore del trend (media 200 candele),
  contro trend, solo BUY, solo SELL. Incertezza su blocchi di 2 settimane con z = 2,81 (Bonferroni).
  Sviluppo = fino al 31/12/2018, verifica = dal 01/01/2019 (mai usata per decidere niente).
  VANTAGGIO solo se il limite basso dell'intervallo e' sopra zero nello sviluppo E il risultato resta sopra zero
  nella verifica.
USO: python studi/studio_pattern_eodhd.py   (serve EODHD_API_KEY: solo dai Secrets, mai nel codice o nei log)
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cot_radar import eodhd, pattern as PT   # noqa: E402

VALUTE = ["EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF", "JPY"]
FOREX = [a + b for i, a in enumerate(VALUTE) for b in VALUTE[i + 1:]]          # 28 coppie
METALLI = ["XAUUSD", "XAGUSD", "XPTUSD"]                                       # spot: niente salti da rollover
DAL = datetime(2000, 1, 1, tzinfo=timezone.utc)
PEZZO = timedelta(days=3 * 365)          # richieste a pezzi di 3 anni (limite EODHD per l'orario: ~7.200 giorni)
TAGLIO = "2019-01-01"                    # sviluppo / verifica


def orarie(sym):
    """[(ts, o, h, l, c)] orarie EODHD dal 2000 a oggi, ordinate e senza doppioni. [] se il simbolo non c'e'."""
    out, inizio, fine = {}, DAL, datetime.now(timezone.utc)
    while inizio < fine:
        a, b = inizio, min(inizio + PEZZO, fine)
        js = eodhd.get(f"intraday/{sym}.FOREX", {"interval": "1h", "from": int(a.timestamp()), "to": int(b.timestamp())})
        for x in js or []:
            try:
                ts = int(x["timestamp"])
                o, h, l, c = (float(x[k]) for k in ("open", "high", "low", "close"))
            except (KeyError, TypeError, ValueError):
                continue
            if min(o, h, l, c) > 0 and h >= l:
                out[ts] = (ts, o, h, l, c)
        inizio = b
    return [out[k] for k in sorted(out)]


def giornaliere_ny(oo):
    """Candele daily come un broker: la giornata finisce alle 17:00 di New York; weekend scartato."""
    gruppi = {}
    for ts, o, h, l, c in oo:
        d = datetime.fromtimestamp(ts, PT.NY)
        if (d.weekday() == 4 and d.hour >= 17) or d.weekday() == 5 or (d.weekday() == 6 and d.hour < 17):
            continue
        giorno = (d + timedelta(hours=7)).date()          # dalle 17:00 inizia la giornata successiva
        g = gruppi.get(giorno)
        gruppi[giorno] = (ts, o, h, l, c) if g is None else (g[0], g[1], max(g[2], h), min(g[3], l), c)
    giorni = sorted(gruppi)
    return [gruppi[g] for g in giorni[:-1]]               # l'ultima giornata potrebbe essere ancora aperta


def dividi(serie, prima):
    """Stesse serie, tenendo solo le operazioni prima/dopo il taglio (le candele precedenti servono alla media 200)."""
    res = {}
    for tr in (1, 2):
        ops = []
        for gruppo, c in serie:
            ops += [o for o in PT.operazioni(c, gruppo, tr) if (o[0] < TAGLIO) == prima]
        res[f"{tr}R"] = {"tutti": PT._sintesi(ops),
                         "trend": PT._sintesi([o for o in ops if o[3] is True]),
                         "contro_trend": PT._sintesi([o for o in ops if o[3] is False]),
                         "buy": PT._sintesi([o for o in ops if o[2] == "BUY"]),
                         "sell": PT._sintesi([o for o in ops if o[2] == "SELL"])}
    return res


def main():
    if not eodhd.attivo():
        print("manca EODHD_API_KEY")
        return 1
    t0 = time.time()
    serie = {"D1": [], "H4": []}
    copertura = {}
    for sym in FOREX + METALLI:
        oo = orarie(sym)
        if len(oo) < 1000:
            copertura[sym] = "non disponibile"
            continue
        gruppo = "forex" if sym in FOREX else "materie"
        h4 = PT.h4(oo)
        d1 = giornaliere_ny(oo)
        serie["H4"].append((gruppo, h4))
        serie["D1"].append((gruppo, d1))
        copertura[sym] = {"dal": datetime.fromtimestamp(oo[0][0], timezone.utc).date().isoformat(),
                          "orarie": len(oo), "h4": len(h4), "d1": len(d1)}
        print(sym, copertura[sym], flush=True)
    out = {"copertura": copertura, "chiamate": eodhd.CHIAMATE, "secondi": round(time.time() - t0)}
    for tf, s in serie.items():
        out[tf] = {"sviluppo": dividi(s, True), "verifica": dividi(s, False)}
    # stampa leggibile (il log del workflow e' il risultato)
    print("\n==== RISULTATI (R medio per blocco di 2 settimane, intervallo z=2,81) ====")
    for tf in ("D1", "H4"):
        for tr in ("1R", "2R"):
            for var in ("tutti", "trend", "contro_trend", "buy", "sell"):
                a, b = out[tf]["sviluppo"][tr][var], out[tf]["verifica"][tr][var]
                f = lambda x: "n/d" if not x else f"n={x['n']:6} vinte={x['vinte']:3}% R={x['r_giorno']:+.3f} IC[{x['ic'][0]:+.3f},{x['ic'][1]:+.3f}] dal {x['dal']}" if x.get("ic") else f"n={x['n']}"
                print(f"{tf} {tr} {var:12} | SVILUPPO {f(a)} | VERIFICA {f(b)}")
    os.makedirs("studio_out", exist_ok=True)
    with open("studio_out/pattern_eodhd.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
