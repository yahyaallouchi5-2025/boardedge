# -*- coding: utf-8 -*-
"""
eodhd_capitalizzazione.py - PREZZI PER LA CAPITALIZZAZIONE VERA (studio Buffett) - Ya, 13/11/2026. Solo studio.

PERCHE': lo studio Buffett ha bisogno della capitalizzazione di ogni azienda mese per mese (owner earnings / prezzo).
  Il prezzo "rettificato" che abbiamo e' corretto anche per i dividendi: moltiplicato per le azioni darebbe un valore
  sbagliato. Qui si scaricano da EODHD, solo per i titoli abbinati a un bilancio SEC:
    - chiusure mensili corrette SOLO per i frazionamenti (campo "close");
    - elenco dei frazionamenti (data e rapporto).
  Capitalizzazione = chiusura x azioni dichiarate alla SEC x frazionamenti avvenuti DOPO la data di quelle azioni.
USCITA: <uscita>/cap_prezzi.json.gz = {ticker: {"c": [[AAAA-MM, chiusura]], "s": [[AAAA-MM-GG, rapporto]]}}
CHIAVE: solo EODHD_API_KEY dai Secrets (eodhd.py non la scrive mai nei log).
USO: python studi/eodhd_capitalizzazione.py <cartella delistate> <cartella bilanci SEC> <uscita>
"""
import gzip
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cot_radar import eodhd                     # noqa: E402
import studio_buffett as B                      # noqa: E402
import studio_onesto as O                       # noqa: E402


def rapporto(testo):
    """'2.000000/1.000000' -> 2.0 (nuove azioni per ogni vecchia). None se illeggibile."""
    try:
        a, b = (float(x) for x in str(testo).split("/"))
        return a / b if a > 0 and b > 0 else None
    except (ValueError, TypeError):
        return None


def uno(t):
    sym = t + ".US"
    c = eodhd.get("eod/" + sym, {"period": "m", "from": "2008-01-01"}, timeout=90)
    s = eodhd.get("splits/" + sym, {"from": "2008-01-01"}, timeout=90)
    chiusure = [[x["date"][:7], round(float(x["close"]), 4)] for x in (c or [])
                if isinstance(x, dict) and x.get("date") and x.get("close")]
    fraz = []
    for x in s or []:
        r = rapporto(x.get("split")) if isinstance(x, dict) else None
        if r and x.get("date"):
            fraz.append([x["date"][:10], round(r, 6)])
    return t, {"c": chiusure, "s": fraz}


def main():
    cart, csec, uscita = sys.argv[1], sys.argv[2], sys.argv[3]
    if not eodhd.attivo():
        print("manca EODHD_API_KEY")
        return 1
    el, dati = O.carica(cart)
    tt = O.titoli(dati)
    nomi = json.load(open(os.path.join(csec, "sec_nomi.json")))
    scambi = {c: sum(cv.values()) for c, (_, cv) in tt.items()}
    tick = sorted(t for t in B.abbina(el, nomi, scambi) if t in tt)
    print("titoli da scaricare:", len(tick), flush=True)
    out = {}
    with ThreadPoolExecutor(4) as ex:
        for i, (t, v) in enumerate(ex.map(uno, tick)):
            if v["c"]:
                out[t] = v
            if i % 500 == 0:
                print(i, "/", len(tick), "con prezzi:", len(out), "chiamate:", eodhd.CHIAMATE, flush=True)
    os.makedirs(uscita, exist_ok=True)
    with gzip.open(os.path.join(uscita, "cap_prezzi.json.gz"), "wt") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print("fatto:", len(out), "titoli; con frazionamenti:", sum(1 for v in out.values() if v["s"]),
          "chiamate:", eodhd.CHIAMATE)
    return 0 if out else 1


if __name__ == "__main__":
    sys.exit(main())
