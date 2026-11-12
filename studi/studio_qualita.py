# -*- coding: utf-8 -*-
"""
studio_qualita.py - IL PUNTEGGIO QUALITA' DEGLI HEDGE FUND (criteri "Long and Short of It" + pesi Travers)
ANTICIPA RENDIMENTI MIGLIORI SUI TITOLI USA DEL SITO?

PUNTEGGIO (0-5, un punto per criterio, calcolato SOLO con bilanci gia' depositati alla data di decisione):
  1. ricavi in crescita in ciascuno degli ultimi 3 anni fiscali
  2. utile positivo e in crescita rispetto all'anno prima
  3. ROE (utile / patrimonio netto) >= 15%
  4. flusso di cassa operativo positivo e >= 80% dell'utile (utili "veri", non contabili)
  5. debito a lungo <= 2 volte la cassa (o nessun debito)
REGOLE FISSATE PRIMA DI VEDERE I RISULTATI
  - decisione ogni 31 marzo (dal 2010 al 2025); valori usati solo se la data di deposito e' <= 31 marzo;
  - esclusi finanziari e immobiliari (ROE e debito hanno altro significato);
  - rendimento 12 mesi dal primo giorno di borsa dopo la decisione (prezzi rettificati EODHD);
  - gruppi: FORTE = punteggio 5, DEBOLE = punteggio 0-1, TUTTI = media di tutti i titoli con punteggio;
  - misura principale: FORTE meno TUTTI, una osservazione per anno; sviluppo 2010-2017, verifica 2018-2025;
  - VANTAGGIO solo se la media e' > 0 in ENTRAMBI i periodi E il limite basso (z = 2,81) e' > 0 sull'intero periodo.
LIMITE NOTO: titoli presenti OGGI negli indici (sopravvissuti): pesa su tutti i gruppi, per questo conta la differenza.
DATI: bilanci_storia pubblicati dal sito (SEC), prezzi EODHD. USO: python studi/studio_qualita.py
"""
import json
import math
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cot_radar import azioni as A, eodhd, fondamentali as F   # noqa: E402

SITO = "https://yahyaallouchi5-2025.github.io/" + os.environ.get("GITHUB_REPOSITORY", "x/cot-radar").split("/")[-1] \
    + "/azioni/bilanci_storia/{}.json"     # nome del repository automatico (resta valido se viene rinominato)
ANNI = range(2010, 2026)
TAGLIO = 2018
ESCLUSI = ("fin", "imm")
Z = 2.81


def storia(t):
    """{voce: [(fine anno fiscale, valore, data deposito)]} dal sito, oppure None."""
    try:
        req = urllib.request.Request(SITO.format(t), headers={"User-Agent": "BoardEdge studio"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r).get("serie")
    except Exception:
        return None


def noti(serie, voce, data):
    """{fine: valore} della voce con deposito <= data (cio' che un investitore vedeva quel giorno)."""
    return {f: v for f, v, dep in (serie.get(voce) or []) if dep <= data and v is not None}


def punteggio(serie, data):
    """Punteggio 0-5 alla data, None se mancano i dati base (ricavi di 4 anni, utile, patrimonio)."""
    ric, ut, pn = noti(serie, "ricavi", data), noti(serie, "utile", data), noti(serie, "pn", data)
    fine = sorted(ric)
    if len(fine) < 4 or fine[-1] not in ut or fine[-1] not in pn:
        return None
    f = fine[-1]
    if f < str(int(data[:4]) - 2):                     # bilancio troppo vecchio: niente punteggio
        return None
    p = 0
    p += all(ric[fine[-k]] > ric[fine[-k - 1]] for k in (1, 2, 3))
    prec = sorted(x for x in ut if x < f)
    p += ut[f] > 0 and bool(prec) and ut[f] > ut[prec[-1]]
    p += pn[f] > 0 and ut[f] / pn[f] >= 0.15
    fco = noti(serie, "fco", data).get(f)
    p += fco is not None and fco > 0 and fco >= 0.8 * ut[f]
    dl = noti(serie, "debito_lungo", data).get(f, noti(serie, "debito", data).get(f, 0)) or 0
    cassa = noti(serie, "cassa", data).get(f) or 0
    p += dl <= 2 * cassa
    return int(p)


def rend12(px, data):
    """Rendimento da prima chiusura dopo `data` a ~252 sedute dopo, None se manca."""
    i = next((k for k, (d, _) in enumerate(px) if d > data), None)
    if i is None or i + 252 >= len(px):
        return None
    return px[i + 252][1] / px[i][1] - 1


def sintesi(x):
    n = len(x)
    if n < 3:
        return None
    m = sum(x) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in x) / (n - 1))
    e = Z * sd / math.sqrt(n)
    return {"anni": n, "media_%": round(m * 100, 2), "ic_%": [round((m - e) * 100, 2), round((m + e) * 100, 2)]}


def main():
    if not eodhd.attivo():
        print("manca EODHD_API_KEY")
        return 1
    usa = [x for x in F.titoli_usa(A.elenco()) if x.get("s") not in ESCLUSI]
    dati = {}
    for x in usa:
        s = storia(x["t"])
        if not s:
            continue
        px = eodhd.serie(x["t"].replace(".", "-") + ".US", "2009-01-01") or []
        if len(px) > 300:
            dati[x["t"]] = (s, px)
    print("titoli con bilanci e prezzi:", len(dati), "su", len(usa), flush=True)
    per_anno = {}
    for a in ANNI:
        data = f"{a}-03-31"
        gruppi = {"forte": [], "debole": [], "tutti": []}
        for t, (s, px) in dati.items():
            p = punteggio(s, data)
            r = rend12(px, data) if p is not None else None
            if r is None:
                continue
            gruppi["tutti"].append(r)
            if p == 5:
                gruppi["forte"].append(r)
            if p <= 1:
                gruppi["debole"].append(r)
        med = {k: sum(v) / len(v) for k, v in gruppi.items() if len(v) >= 5}
        if len(med) == 3:
            per_anno[a] = {"n": {k: len(v) for k, v in gruppi.items()},
                           "forte_meno_tutti": med["forte"] - med["tutti"],
                           "debole_meno_tutti": med["debole"] - med["tutti"],
                           "forte_meno_debole": med["forte"] - med["debole"]}
            print(a, per_anno[a]["n"], {k: round(v * 100, 1) for k, v in per_anno[a].items() if k != "n"}, flush=True)
    out = {}
    for misura in ("forte_meno_tutti", "debole_meno_tutti", "forte_meno_debole"):
        out[misura] = {per: sintesi([v[misura] for a, v in per_anno.items() if ok(a)])
                       for per, ok in (("sviluppo", lambda a: a < TAGLIO), ("verifica", lambda a: a >= TAGLIO),
                                       ("tutto", lambda a: True))}
    p = out["forte_meno_tutti"]
    out["VANTAGGIO"] = bool(p["sviluppo"] and p["verifica"] and p["tutto"] and p["sviluppo"]["media_%"] > 0
                            and p["verifica"]["media_%"] > 0 and p["tutto"]["ic_%"][0] > 0)
    print(json.dumps(out, indent=1))
    os.makedirs("studio_out", exist_ok=True)
    with open("studio_out/qualita.json", "w", encoding="utf-8") as fh:
        json.dump({"per_anno": per_anno, "sintesi": out}, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
