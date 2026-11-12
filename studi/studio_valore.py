# -*- coding: utf-8 -*-
"""
studio_valore.py - BILANCI FORTI *E* PREZZO BASSO BATTONO IL MERCATO? (GARP: "Growth at a Reasonable Price",
The Long and Short of It cap. A5; Lynch). Seguito di studio_qualita.py: i bilanci forti DA SOLI non battono la
media (-1,5% l'anno, 12/11/2026) perche' sono gia' nel prezzo. Qui si aggiunge la valutazione.

DEFINIZIONI (calcolate ogni 31 marzo SOLO con dati gia' depositati quel giorno):
  - punteggio qualita' 0-5: identico a studio_qualita.py (stesse funzioni, stessi bilanci_storia del sito);
  - rendimento degli utili = utile per azione diluito dell'ultimo anno fiscale (SEC, prima pubblicazione) / prezzo;
    e' l'inverso del P/E: piu' alto = titolo piu' a buon mercato. Utile negativo = escluso dai "convenienti".
REGOLE FISSATE PRIMA DI VEDERE I RISULTATI
  - CONVENIENTI = 30% dei titoli con rendimento degli utili piu' alto quell'anno;
  - FORTI = punteggio >= 4;   GARP = forti E convenienti;   TUTTI = media dei titoli con entrambi i dati;
  - misura principale: GARP meno TUTTI a 12 mesi, un'osservazione per anno; sviluppo 2010-2017, verifica 2018-2025;
  - VANTAGGIO solo se la media e' > 0 in ENTRAMBI i periodi E il limite basso (z = 2,81) e' > 0 sull'intero periodo.
  - esclusi finanziari e immobiliari. Limite noto: titoli presenti oggi negli indici (sopravvissuti).
DATI: SEC companyfacts (Secret SEC_CONTATTO), bilanci_storia del sito, prezzi EODHD (Secret EODHD_API_KEY).
USO: python studi/studio_valore.py
"""
import json
import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cot_radar import azioni as A, eodhd, fondamentali as F   # noqa: E402
from studio_qualita import ANNI, ESCLUSI, TAGLIO, punteggio, rend12, sintesi, storia   # noqa: E402

QUOTA_CONVENIENTI = 0.30
FORTE = 4


def utili_per_azione(fatti):
    """[(fine anno fiscale, utile per azione, data della PRIMA pubblicazione)] dai 10-K, diluito (o base)."""
    g = (fatti or {}).get("facts", {}).get("us-gaap", {})
    for c in ("EarningsPerShareDiluted", "EarningsPerShareBasic"):
        righe = (g.get(c) or {}).get("units", {}).get("USD/shares") or []
        primo = {}
        for r in righe:
            try:
                giorni = (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days
            except (KeyError, ValueError):
                continue
            if str(r.get("form", "")).startswith("10-K") and 330 <= giorni <= 400 and r.get("val") is not None:
                if r["end"] not in primo or r["filed"] < primo[r["end"]][1]:
                    primo[r["end"]] = (r["val"], r["filed"])
        if primo:
            return sorted((f, v, d) for f, (v, d) in primo.items())
    return []


def prezzo_al(px, data):
    """ultima chiusura <= data."""
    p = None
    for d, v in px:
        if d > data:
            break
        p = v
    return p


def main():
    ua = F._ua()
    if not eodhd.attivo() or not ua:
        print("mancano EODHD_API_KEY o SEC_CONTATTO")
        return 1
    mappa = F._cik(tempfile.mkdtemp(), ua, date.today()) or {}
    usa = [x for x in F.titoli_usa(A.elenco()) if x.get("s") not in ESCLUSI]
    dati = {}
    for x in usa:
        t = x["t"]
        cik = mappa.get(t) or mappa.get(t.replace(".", "-"))
        s = storia(t)
        fatti = F._get(F.URL_FATTI.format(cik=int(cik)), ua) if cik and s else None
        eps = utili_per_azione(fatti)
        px = (eodhd.serie(t.replace(".", "-") + ".US", "2009-01-01") or []) if eps else []
        if s and eps and len(px) > 300:
            dati[t] = (s, eps, px)
    print("titoli con bilanci, utili per azione e prezzi:", len(dati), "su", len(usa), flush=True)
    per_anno = {}
    for a in ANNI:
        data = f"{a}-03-31"
        righe = []
        for t, (s, eps, px) in dati.items():
            p = punteggio(s, data)
            noti = [(f, v) for f, v, dep in eps if dep <= data]
            prezzo = prezzo_al(px, data)
            r = rend12(px, data)
            if p is None or not noti or not prezzo or r is None or noti[-1][0] < str(a - 2):
                continue
            righe.append({"p": p, "ry": noti[-1][1] / prezzo, "r": r})
        if len(righe) < 50:
            continue
        soglia = sorted((x["ry"] for x in righe), reverse=True)[int(QUOTA_CONVENIENTI * len(righe))]
        g = {"tutti": [x["r"] for x in righe],
             "convenienti": [x["r"] for x in righe if x["ry"] > 0 and x["ry"] >= soglia],
             "forti": [x["r"] for x in righe if x["p"] >= FORTE],
             "garp": [x["r"] for x in righe if x["p"] >= FORTE and x["ry"] > 0 and x["ry"] >= soglia]}
        if min(len(v) for v in g.values()) < 5:
            continue
        m = {k: sum(v) / len(v) for k, v in g.items()}
        per_anno[a] = {"n": {k: len(v) for k, v in g.items()},
                       **{k + "_meno_tutti": m[k] - m["tutti"] for k in ("garp", "convenienti", "forti")}}
        print(a, per_anno[a]["n"], {k: round(v * 100, 1) for k, v in per_anno[a].items() if k != "n"}, flush=True)
    out = {}
    for misura in ("garp_meno_tutti", "convenienti_meno_tutti", "forti_meno_tutti"):
        out[misura] = {per: sintesi([v[misura] for a, v in per_anno.items() if ok(a)])
                       for per, ok in (("sviluppo", lambda a: a < TAGLIO), ("verifica", lambda a: a >= TAGLIO),
                                       ("tutto", lambda a: True))}
    p = out["garp_meno_tutti"]
    out["VANTAGGIO"] = bool(p["sviluppo"] and p["verifica"] and p["tutto"] and p["sviluppo"]["media_%"] > 0
                            and p["verifica"]["media_%"] > 0 and p["tutto"]["ic_%"][0] > 0)
    print(json.dumps(out, indent=1))
    os.makedirs("studio_out", exist_ok=True)
    with open("studio_out/valore.json", "w", encoding="utf-8") as fh:
        json.dump({"per_anno": per_anno, "sintesi": out}, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
