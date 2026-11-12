# -*- coding: utf-8 -*-
"""
studio_regime_macro.py - IL REGIME MACRO (CRESCITA E INFLAZIONE) DICE COSA TENERE NEL MESE SUCCESSIVO?

IDEA (libri sugli hedge fund macro, Investor's Passport cap. 4: "crescita, inflazione e tassi guidano tutto").
Quattro fasi, dalla DIREZIONE di crescita e inflazione:
  RIPRESA          crescita in aumento, inflazione in calo
  SURRISCALDAMENTO crescita in aumento, inflazione in aumento
  STAGFLAZIONE     crescita in calo,    inflazione in aumento
  RALLENTAMENTO    crescita in calo,    inflazione in calo
REGOLE FISSATE PRIMA DI VEDERE I RISULTATI
  - crescita = variazione annua della produzione industriale (FRED INDPRO), inflazione = variazione annua dei
    prezzi al consumo (FRED CPIAUCSL); "in aumento" = valore piu' alto di 3 mesi prima;
  - a fine mese m si usa il dato del mese m-2 (escono a meta' del mese dopo: niente "futuro");
  - attivi, rendimento del mese m+1 meno la liquidita' (titoli a 3 mesi, DTB3):
      AZIONI = SPY (dividendi inclusi), OBBLIGAZIONI = Treasury 10 anni ricostruito dal rendimento (DGS10,
      durata modificata 7,5 + cedola), ORO = GLD (dal 2005);
  - sviluppo 1994-2010, verifica 2011-2026;
  - STRATEGIA: in ogni fase si tiene l'attivo che nello SVILUPPO ha reso di piu' in quella fase (liquidita' se
    nessuno batte la liquidita'); confronto in verifica con 60% azioni / 40% obbligazioni, ribilanciato ogni mese;
  - VANTAGGIO solo se nella verifica la strategia ha Sharpe E Calmar piu' alti del 60/40.
LIMITE NOTO: INDPRO e CPI sono i valori di oggi, con le revisioni successive (le revisioni del CPI sono minime,
  quelle di INDPRO piccole); il ritardo di 2 mesi le attenua. Niente costi: la strategia cambia attivo di rado.
USO: STORICO=<cartella con i csv FRED e yahoo/> python studi/studio_regime_macro.py
"""
import csv
import json
import math
import os

STOR = os.environ.get("STORICO", "storico")
FASI = ("RIPRESA", "SURRISCALDAMENTO", "STAGFLAZIONE", "RALLENTAMENTO")
TAGLIO = "2011-01"
DURATA = 7.5


def leggi(nome, cartella=STOR):
    """[(data, valore)] da un csv (prima colonna data, ultima colonna valore), saltando valori vuoti o '.'."""
    out = []
    with open(os.path.join(cartella, nome), encoding="utf-8") as fh:
        for r in csv.reader(fh):
            try:
                out.append((r[0][:10], float(r[-1])))
            except (ValueError, IndexError):
                continue
    return out


def fine_mese(serie):
    """{aaaa-mm: ultimo valore del mese}."""
    m = {}
    for d, v in serie:
        m[d[:7]] = v
    return m


def mesi_prima(ym, k):
    a, m = int(ym[:4]), int(ym[5:]) - k
    while m < 1:
        a, m = a - 1, m + 12
    return f"{a:04d}-{m:02d}"


def annua(m, ym):
    """variazione annua in % della serie mensile m al mese ym, None se manca."""
    a, b = m.get(ym), m.get(mesi_prima(ym, 12))
    return (a / b - 1) * 100 if a and b else None


def fase(ind, cpi, ym):
    """fase nota a fine mese ym (usa i dati di ym-2 e ym-5)."""
    g1, g0 = annua(ind, mesi_prima(ym, 2)), annua(ind, mesi_prima(ym, 5))
    i1, i0 = annua(cpi, mesi_prima(ym, 2)), annua(cpi, mesi_prima(ym, 5))
    if None in (g1, g0, i1, i0):
        return None
    su_g, su_i = g1 > g0, i1 > i0
    return FASI[0] if su_g and not su_i else FASI[1] if su_g else FASI[2] if su_i else FASI[3]


def stat(r):
    """rendimento annuo, volatilita', Sharpe (r gia' in eccesso? no: r totale, rf a parte), max drawdown, Calmar."""
    v, picco, dd = 1.0, 1.0, 0.0
    for x in r:
        v *= 1 + x
        picco = max(picco, v)
        dd = min(dd, v / picco - 1)
    n = len(r)
    cagr = v ** (12 / n) - 1
    return cagr, dd


def main():
    ind = {d[:7]: v for d, v in leggi("INDPRO.csv")}
    cpi = {d[:7]: v for d, v in leggi("CPIAUCSL.csv")}
    t10 = fine_mese(leggi("DGS10.csv"))
    t3m = fine_mese(leggi("DTB3.csv"))
    spy = fine_mese(leggi(os.path.join("yahoo", "SPY.csv")))
    gld = fine_mese(leggi(os.path.join("yahoo", "GLD.csv")))
    mesi = sorted(m for m in spy if m >= "1994-01" and m in t10 and m in t3m)
    righe = []
    for a, b in zip(mesi[:-1], mesi[1:]):
        f = fase(ind, cpi, a)
        if f is None:
            continue
        rf = t3m[a] / 100 / 12
        az = spy[b] / spy[a] - 1
        ob = t10[a] / 100 / 12 - DURATA * (t10[b] - t10[a]) / 100
        oro = gld[b] / gld[a] - 1 if a in gld and b in gld else None
        righe.append({"m": b, "fase": f, "rf": rf, "AZIONI": az, "OBBLIGAZIONI": ob, "ORO": oro})
    out = {"mesi": len(righe), "dal": righe[0]["m"], "al": righe[-1]["m"], "per_fase": {}}
    # 1) rendimento medio in eccesso sulla liquidita', per fase e periodo (in % l'anno)
    for per, ok in (("sviluppo", lambda m: m < TAGLIO), ("verifica", lambda m: m >= TAGLIO)):
        tab = {}
        for f in FASI:
            rr = [x for x in righe if x["fase"] == f and ok(x["m"])]
            tab[f] = {"mesi": len(rr)}
            for k in ("AZIONI", "OBBLIGAZIONI", "ORO"):
                e = [x[k] - x["rf"] for x in rr if x[k] is not None]
                if len(e) >= 12:
                    mu = sum(e) / len(e)
                    sd = math.sqrt(sum((v - mu) ** 2 for v in e) / (len(e) - 1))
                    tab[f][k] = {"eccesso_anno_%": round(mu * 1200, 1), "t": round(mu / (sd / math.sqrt(len(e))), 2)}
        out["per_fase"][per] = tab
    # 2) strategia: in ogni fase l'attivo migliore dello sviluppo (ORO solo se ha dati nello sviluppo)
    scelta = {}
    for f in FASI:
        cand = {k: v["eccesso_anno_%"] for k, v in out["per_fase"]["sviluppo"][f].items() if isinstance(v, dict)}
        best = max(cand, key=cand.get) if cand else None
        scelta[f] = best if best and cand[best] > 0 else "LIQUIDITA"
    out["scelta"] = scelta
    ver = [x for x in righe if x["m"] >= TAGLIO]
    strat = [x["rf"] if scelta[x["fase"]] == "LIQUIDITA" else x[scelta[x["fase"]]] for x in ver]
    bench = [0.6 * x["AZIONI"] + 0.4 * x["OBBLIGAZIONI"] for x in ver]
    soloaz = [x["AZIONI"] for x in ver]
    rf = [x["rf"] for x in ver]
    res = {}
    for nome, r in (("strategia", strat), ("60_40", bench), ("solo_azioni", soloaz)):
        e = [a - b for a, b in zip(r, rf)]
        mu, sd = sum(e) / len(e), math.sqrt(sum((v - sum(e) / len(e)) ** 2 for v in e) / (len(e) - 1))
        cagr, dd = stat(r)
        res[nome] = {"rend_anno_%": round(cagr * 100, 1), "max_dd_%": round(dd * 100, 1),
                     "sharpe": round(mu / sd * math.sqrt(12), 2), "calmar": round(cagr / abs(dd), 2) if dd else None}
    out["verifica"] = res
    out["VANTAGGIO"] = res["strategia"]["sharpe"] > res["60_40"]["sharpe"] and res["strategia"]["calmar"] > res["60_40"]["calmar"]
    out["fase_oggi"] = fase(ind, cpi, max(ind))
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return out


if __name__ == "__main__":
    main()
