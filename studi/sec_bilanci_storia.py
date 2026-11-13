# -*- coding: utf-8 -*-
"""
sec_bilanci_storia.py - ARCHIVIO DEI BILANCI SEC DI TUTTE LE AZIENDE USA (anche fallite o comprate) per lo studio
"Buffett" (riacquisti di azioni, owner earnings, debito, ROE). Ya, 13/11/2026. Solo studio: il sito non cambia.

FONTE: "Financial Statement Data Sets" della SEC (un archivio zip a trimestre dal 2009: tutti i 10-K e 10-Q depositati
in quel trimestre, con la DATA DI DEPOSITO = il giorno in cui il pubblico ha visto i numeri). Le aziende uscite dalla
borsa restano negli archivi: nessun bias di sopravvivenza.
COSA SI TIENE (solo i valori dell'azienda intera: niente segmenti, niente societa' collegate):
  azioni in circolazione, valore di mercato del flottante, utile netto, ammortamenti, investimenti (capex), riacquisti ed emissioni di azioni, dividendi pagati,
  flusso di cassa operativo, debito a lungo termine, cassa, patrimonio netto.
USCITA (scritta riga per riga: poca memoria anche con 17 anni di archivi):
  <cartella>/sec_valori_<anno>.csv.gz  righe "cik,deposito,fine_periodo,trimestri,voce,valore"
    ("trimestri" = 0 per i valori di fine periodo (azioni, debito...), 1-4 per i flussi;
     di ogni deposito si tiene solo il periodo nuovo, non i confronti con gli anni prima)
  <cartella>/sec_nomi.json      {cik: [nomi usati nel tempo]} per abbinare le aziende ai ticker
CONTATTO: la SEC chiede un User-Agent con un'email: Secret SEC_CONTATTO (mai nel codice o nei log).
USO: python studi/sec_bilanci_storia.py <cartella uscita>
"""
import csv
import gzip
import io
import json
import os
import sys
import time
import urllib.request
import zipfile
from datetime import date

URL = "https://www.sec.gov/files/dera/data/financial-statement-data-sets/{q}.zip"
VOCI = {
    "EntityCommonStockSharesOutstanding": "azioni", "CommonStockSharesOutstanding": "azioni_bil",
    "WeightedAverageNumberOfDilutedSharesOutstanding": "azioni_medie",
    "NetIncomeLoss": "utile", "ProfitLoss": "utile_tot",
    "DepreciationDepletionAndAmortization": "ammort", "DepreciationAndAmortization": "ammort2",
    "DepreciationAmortizationAndAccretionNet": "ammort3", "Depreciation": "ammort4",
    "PaymentsToAcquirePropertyPlantAndEquipment": "capex", "PaymentsToAcquireProductiveAssets": "capex2",
    "PaymentsForRepurchaseOfCommonStock": "riacquisti", "ProceedsFromIssuanceOfCommonStock": "emissioni",
    "EntityPublicFloat": "flottante",            # valore di mercato del flottante (per la capitalizzazione vera)
    "PaymentsOfDividends": "dividendi", "PaymentsOfDividendsCommonStock": "dividendi2",
    "NetCashProvidedByUsedInOperatingActivities": "fco",
    "LongTermDebt": "debito", "LongTermDebtNoncurrent": "debito_lungo",
    "CashAndCashEquivalentsAtCarryingValue": "cassa", "StockholdersEquity": "pn",
}
MODULI = ("10-K", "10-Q")


def trimestri(oggi=None):
    oggi = oggi or date.today()
    a, q = 2009, 2
    while (a, q) <= (oggi.year, (oggi.month - 1) // 3 + 1):
        yield f"{a}q{q}"
        a, q = (a, q + 1) if q < 4 else (a + 1, 1)


def scarica(q, ua, tentativi=3):
    for n in range(tentativi):
        try:
            req = urllib.request.Request(URL.format(q=q), headers={"User-Agent": ua, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read()
        except Exception as e:
            if getattr(e, "code", None) == 404:
                return None                          # trimestre non ancora pubblicato
            print(q, "tentativo", n + 1, "non riuscito:", getattr(e, "code", type(e).__name__), flush=True)
            time.sleep(10 * (n + 1))
    return None


def leggi_trimestre(grezzo, scrittore, nomi):
    """Scrive le righe utili del trimestre; aggiorna nomi {cik: set}. Restituisce quante righe."""
    z = zipfile.ZipFile(io.BytesIO(grezzo))
    sub = {}
    with z.open("sub.txt") as f:
        for r in csv.DictReader(io.TextIOWrapper(f, "utf-8", errors="replace"), delimiter="\t"):
            if r.get("form") in MODULI:
                sub[r["adsh"]] = (r["cik"], r.get("filed", ""))
                nomi.setdefault(r["cik"], set()).add(r.get("name", ""))
    righe = {}                                           # adsh -> righe (si tiene solo il periodo piu' recente)
    with z.open("num.txt") as f:
        for r in csv.DictReader(io.TextIOWrapper(f, "utf-8", errors="replace"), delimiter="\t"):
            voce = VOCI.get(r.get("tag"))
            s = sub.get(r.get("adsh"))
            if not voce or not s or (r.get("coreg") or "").strip() or (r.get("segments") or "").strip():
                continue
            try:
                v = float(r["value"])
            except (TypeError, ValueError):
                continue
            righe.setdefault(r["adsh"], []).append((r.get("ddate") or "", int(r.get("qtrs") or 0), voce, v))
    # i confronti con gli anni prima (stesse cifre gia' depositate allora) si scartano: resta il periodo nuovo
    n = 0
    for adsh, rr in righe.items():
        cik, dep = sub[adsh]
        ultimo = {}                                      # per voce: le azioni "di copertina" hanno una data loro
        for d, q, voce, v in rr:
            ultimo[voce] = max(ultimo.get(voce, ""), d)
        for d, q, voce, v in rr:
            if d == ultimo[voce]:
                scrittore.writerow([cik, f"{dep[:4]}-{dep[4:6]}-{dep[6:8]}", f"{d[:4]}-{d[4:6]}-{d[6:8]}",
                                    q, voce, f"{v:.6g}"])
                n += 1
    return n


def main():
    uscita = sys.argv[1] if len(sys.argv) > 1 else "studio_out"
    c = os.environ.get("SEC_CONTATTO", "").strip()
    if "@" not in c:
        print("manca SEC_CONTATTO")
        return 1
    ua = f"BoardEdge (studio bilanci) {c}"
    os.makedirs(uscita, exist_ok=True)
    nomi, tot, mancanti = {}, 0, []
    fh, anno = None, None
    try:
        for q in trimestri():
            if q[:4] != anno:                            # un file per anno: ognuno resta piccolo
                if fh:
                    fh.close()
                anno = q[:4]
                fh = gzip.open(os.path.join(uscita, f"sec_valori_{anno}.csv.gz"), "wt", newline="")
                w = csv.writer(fh)
                w.writerow(["cik", "deposito", "fine_periodo", "trimestri", "voce", "valore"])
            t0 = time.time()
            g = scarica(q, ua)
            if not g:
                print(q, "assente", flush=True)
                mancanti.append(q)
                continue
            n = leggi_trimestre(g, w, nomi)
            tot += n
            print(f"{q}: {len(g) / 1e6:.0f} MB, {n} valori, aziende finora {len(nomi)} ({time.time() - t0:.0f}s)",
                  flush=True)
            del g
            time.sleep(1)                                # gentile con la SEC (limite 10 richieste al secondo)
    finally:
        if fh:
            fh.close()
    with open(os.path.join(uscita, "sec_nomi.json"), "w") as fh:
        json.dump({k: sorted(v) for k, v in nomi.items()}, fh, separators=(",", ":"))
    print("aziende:", len(nomi), "valori:", tot, "trimestri mancanti:", mancanti)
    return 0 if tot else 1


if __name__ == "__main__":
    sys.exit(main())
