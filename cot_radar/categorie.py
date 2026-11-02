# -*- coding: utf-8 -*-
"""
categorie.py - CHI TIENE LE VALUTE: banche dealer, hedge fund e asset manager (report TFF della CFTC), v6.80.

PERCHE' (studio tools/studio_cot_categorie.py, 02/11/2026): il segnale COT del sito usa i "Non Commercial" del report
Legacy, cioe' tutti gli speculatori insieme. Il report TFF ("Traders in Financial Futures", futures + opzioni) li
separa. Dal 2018 la posizione delle BANCHE DEALER ha anticipato le valute meglio di quella degli speculatori (che e'
diventata un indicatore contrario). Prima del 2018 era il contrario: per questo il dato qui e' INFORMATIVO, non entra
nel punteggio ne' nei segnali finche' non e' verificato sul registro live.

CATEGORIE (per ogni valuta del report: EUR, GBP, JPY, CHF, CAD, AUD, NZD, MXN, BRL, ZAR, indice del dollaro)
  dealer = banche dealer (stanno dall'altra parte dei clienti e si coprono)
  lev    = hedge fund e CTA con leva ("leveraged funds"): veloci, seguono il trend
  asset  = asset manager (fondi pensione, assicurazioni, gestori): lenti
COSA SI CALCOLA per ogni categoria, con i soli dati gia' pubblicati:
  pct = netto (long - short) in % dei contratti aperti (positivo = net long sulla valuta, cioe' contro il dollaro)
  idx = COT Index a 3 anni (0 = mai cosi' short, 100 = mai cosi' long), come per gli speculatori del sito
  d1  = variazione del netto % rispetto alla settimana prima (punti di open interest)
  stato = "massimo" (idx >= 80: la posizione piu' LONG degli ultimi 3 anni, anche se il netto e' ancora short),
          "minimo" (idx <= 20: la piu' SHORT degli ultimi 3 anni), altrimenti "norma"
FONTE: archivio storico/TFF.csv, aggiornato a ogni giro del sito da storico.aggiorna_extra (gia' esistente).
  Se l'archivio manca o e' vecchio il blocco semplicemente non compare: il resto del sito non cambia.
"""
from .calcoli import cot_index
from .config import ASSETS

CATEGORIE = {"dealer": ("dealer_positions_long_all", "dealer_positions_short_all"),
             "lev": ("lev_money_positions_long", "lev_money_positions_short"),
             "asset": ("asset_mgr_positions_long", "asset_mgr_positions_short")}
MIN_SETTIMANE = 60          # sotto questo storico il COT Index non e' affidabile: la valuta si salta


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def calcola(righe):
    """righe TFF (dizionari CFTC) -> {"data": martedi' del report, "valute": {chiave: {categoria: {...}}}} o None."""
    if not righe:
        return None
    valute = {a[1]: a[0] for a in ASSETS if a[3] == "Valute"}          # codice CFTC -> chiave del sito (EUR, ...)
    per = {}
    for r in righe:
        k = valute.get((r.get("cftc_contract_market_code") or "").strip())
        oi = _num(r.get("open_interest_all"))
        if k and oi and oi > 0:
            per.setdefault(k, {})[r["report_date_as_yyyy_mm_dd"][:10]] = r     # stessa data due volte: vince l'ultima
    out, ultima = {}, None
    for k, giorni in per.items():
        serie = [giorni[d] for d in sorted(giorni)][-160:]                    # ~3 anni: bastano per il COT Index
        if len(serie) < MIN_SETTIMANE:
            continue
        cat = {}
        for nome, (cl, cs) in CATEGORIE.items():
            n = []
            for r in serie:
                lo, sh, oi = _num(r.get(cl)), _num(r.get(cs)), _num(r.get("open_interest_all"))
                n.append(None if lo is None or sh is None else (lo - sh) / oi * 100)
            if n[-1] is None or n[-2] is None:
                continue
            storia = [x for x in n if x is not None]
            idx = round(cot_index(storia))
            cat[nome] = {"pct": round(n[-1], 1), "idx": idx, "d1": round(n[-1] - n[-2], 1),
                         "stato": "massimo" if idx >= 80 else "minimo" if idx <= 20 else "norma"}
        if cat:
            out[k] = cat
            d = serie[-1]["report_date_as_yyyy_mm_dd"][:10]
            ultima = max(ultima or d, d)
    return {"data": ultima, "valute": out} if out else None
