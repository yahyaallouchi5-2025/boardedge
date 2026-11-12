# -*- coding: utf-8 -*-
"""
studio_insider.py - GLI ACQUISTI DEI MANAGER CON SOLDI PROPRI ANTICIPANO RENDIMENTI MIGLIORI?

IDEA (Peter Lynch, "One Up on Wall Street"): "quando gli insider comprano, e' il segnale migliore". Qui lo si misura
sui titoli USA del sito (S&P 500 e Nasdaq-100) con i dati EODHD (moduli Form 4 della SEC).

REGOLE FISSATE PRIMA DI VEDERE I RISULTATI
  - evento = ACQUISTO sul mercato (codice "P") di un insider, valore >= 50.000 $; si usa la data di DEPOSITO del
    modulo (quando il pubblico lo vede), non quella dell'operazione; piu' acquisti dello stesso titolo nello stesso
    mese = un solo evento (il primo);
  - ingresso alla chiusura del giorno di borsa DOPO il deposito; risultato a 3, 6 e 12 mesi (63, 126, 252 sedute)
    MENO quello dell'S&P 500 (SPY) nello stesso periodo = rendimento in eccesso;
  - incertezza: media per MESE di calendario (gli eventi dello stesso mese sono legati), blocchi di 3 mesi,
    intervallo z = 2,81 (Bonferroni per 3 orizzonti x 2 periodi + margine);
  - sviluppo = eventi fino al 31/12/2018, verifica = dal 01/01/2019;
  - VANTAGGIO solo se a 6 mesi il limite basso e' sopra zero nello sviluppo E la media resta sopra zero nella verifica.
LIMITE NOTO: i titoli sono quelli presenti OGGI negli indici (sopravvissuti): il risultato e' ottimista per tutti,
  per questo il confronto e' anche con TUTTI i titoli dello stesso elenco (stesse date, senza acquisti).
USO: python studi/studio_insider.py   (EODHD_API_KEY solo dai Secrets)
"""
import json
import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cot_radar import azioni as A, eodhd, fondamentali as F   # noqa: E402

DAL = "2008-01-01"
MIN_VALORE = 50_000
ORIZZONTI = {"3m": 63, "6m": 126, "12m": 252}
TAGLIO = "2019-01-01"
Z = 2.81
TEMPO_MAX = 4800                 # secondi: il workflow ha 90 minuti


def prezzi(sym):
    """[(data, prezzo rettificato)] EODHD dal DAL, oppure []."""
    return eodhd.serie(sym, DAL) or []


def eventi(sym):
    """[data di deposito] degli acquisti >= MIN_VALORE, uno per mese."""
    js = eodhd.get("insider-transactions", {"code": sym, "from": DAL, "limit": 1000}, timeout=60, tentativi=2)
    visti, out = set(), []
    for x in js if isinstance(js, list) else []:
        try:
            if str(x.get("transactionCode", "")).upper() != "P":
                continue
            valore = float(x.get("transactionAmount") or 0) * float(x.get("transactionPrice") or 0)
            d = str(x.get("reportDate") or x.get("date") or "")[:10]
            date.fromisoformat(d)
        except (TypeError, ValueError):
            continue
        if valore >= MIN_VALORE and d[:7] not in visti:
            visti.add(d[:7])
            out.append(d)
    return sorted(out)


def eccesso(px, spy, giorno):
    """{orizzonte: rendimento del titolo - SPY} dall'ingresso (chiusura del giorno di borsa dopo 'giorno')."""
    date_t = [d for d, _ in px]
    i = next((k for k, d in enumerate(date_t) if d > giorno), None)
    if i is None:
        return {}
    sp = dict(spy)
    out = {}
    for nome, n in ORIZZONTI.items():
        if i + n < len(px) and px[i][0] in sp and px[i + n][0] in sp:
            out[nome] = (px[i + n][1] / px[i][1] - 1) - (sp[px[i + n][0]] / sp[px[i][0]] - 1)
    return out


def sintesi(righe, orizzonte):
    """n eventi, media in % e intervallo sulle medie mensili (blocchi di 3 mesi)."""
    per_mese = {}
    for g, e in righe:
        if orizzonte in e:
            per_mese.setdefault(g[:7], []).append(e[orizzonte])
    mesi = sorted(per_mese)
    if len(mesi) < 12:
        return None
    medie = [sum(per_mese[m]) / len(per_mese[m]) for m in mesi]
    blocchi = [sum(medie[i:i + 3]) / len(medie[i:i + 3]) for i in range(0, len(medie), 3)]
    nb = len(blocchi)
    mu = sum(blocchi) / nb
    sd = (sum((x - mu) ** 2 for x in blocchi) / (nb - 1)) ** 0.5
    err = Z * sd / nb ** 0.5
    return {"eventi": sum(len(v) for v in per_mese.values()), "mesi": len(mesi),
            "media": round(mu * 100, 2), "ic": [round((mu - err) * 100, 2), round((mu + err) * 100, 2)]}


def main():
    if not eodhd.attivo():
        print("manca EODHD_API_KEY")
        return 1
    t0 = time.time()
    spy = prezzi("SPY.US")
    usa = F.titoli_usa(A.elenco())
    righe, base, coperti = [], [], 0
    for x in usa:
        if time.time() - t0 > TEMPO_MAX:
            print("tempo massimo: studio parziale")
            break
        sym = x["t"].replace(".", "-") + ".US"
        ev = eventi(sym)
        px = prezzi(sym) if ev else []
        if not px:
            continue
        coperti += 1
        for g in ev:
            e = eccesso(px, spy, g)
            if e:
                righe.append((g, e))
        # confronto: lo stesso titolo il primo giorno di ogni trimestre (senza condizione sugli acquisti)
        for d, _ in px[::63]:
            e = eccesso(px, spy, d)
            if e:
                base.append((d, e))
    out = {"titoli_con_acquisti": coperti, "chiamate": eodhd.CHIAMATE, "secondi": round(time.time() - t0)}
    for per, filtro in (("sviluppo", lambda g: g < TAGLIO), ("verifica", lambda g: g >= TAGLIO)):
        out[per] = {o: {"acquisti": sintesi([r for r in righe if filtro(r[0])], o),
                        "tutti": sintesi([r for r in base if filtro(r[0])], o)} for o in ORIZZONTI}
    print(json.dumps(out, indent=1))
    os.makedirs("studio_out", exist_ok=True)
    with open("studio_out/insider.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
