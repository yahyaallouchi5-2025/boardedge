# -*- coding: utf-8 -*-
"""
fondamentali.py - BILANCI DELLE AZIENDE USA (fatturato, utile, anni in perdita, debito netto) dalla SEC

IDEA
  Nella scheda Azionario, aprendo un titolo USA (S&P 500 e Nasdaq-100) si vede la "salute" dell'azienda negli
  ultimi 5 anni fiscali: ricavi, utile netto, anni in perdita, debito, liquidita', debito netto e un giudizio
  semplice (SOLIDA / NELLA MEDIA / INDEBITATA). Fonte gratuita e ufficiale: la SEC (l'ente di vigilanza della borsa
  USA), API "companyfacts" con i dati XBRL dei bilanci depositati (moduli 10-K annuali).

RITARDO (perche' i dati non sono "di oggi")
  Le aziende depositano il bilancio annuale (10-K) 60-90 giorni dopo la fine dell'anno fiscale, le trimestrali
  (10-Q) 40-45 giorni dopo il trimestre. La SEC pubblica i dati pochi minuti dopo il deposito. Qui si usano gli
  ANNUALI, riscaricati una volta a settimana per titolo (giorno fisso per titolo, sparso sui 5 giorni feriali):
  un bilancio nuovo compare al massimo una settimana dopo il deposito.

REGOLE DELLA SEC (rispettate)
  - User-Agent con nome del servizio e un contatto email (obbligatorio): Secret SEC_CONTATTO del workflow;
    senza contatto il modulo NON scarica nulla (lo dice nel registro) e la scheda mostra "non disponibile".
  - Massimo 10 richieste al secondo: qui una ogni 0,15 secondi.

GIUDIZIO (semplice e spiegato nella scheda)
  - SOLIDA: utile positivo in tutti gli anni disponibili (almeno 3) e debito netto <= 3 volte l'utile medio
    (o liquidita' maggiore del debito);
  - INDEBITATA: patrimonio netto negativo, oppure debito netto > 6 volte l'utile medio, oppure utile medio <= 0
    con debito netto positivo;
  - NELLA MEDIA: tutto il resto. Banche e assicurazioni: il debito fa parte del mestiere, il giudizio sul debito
    non si applica (settore "fin") e conta solo la continuita' degli utili.

USCITA (nel ramo "azioni", copiata nel sito): pubblico/bilanci/<T>.json e pubblico/bilanci.json (indice).
DEBUG: python -c "from cot_radar import fondamentali; help(fondamentali.estrai)"
"""
import json
import os
import time
import urllib.request
import zlib
from datetime import date, timedelta

from . import azioni as A
from .log import log

URL_CIK = "https://www.sec.gov/files/company_tickers.json"
URL_FATTI = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
ANNI = 5
PAUSA = 0.15
GIORNI_CIK = 7                  # la tabella ticker -> CIK si riscarica una volta a settimana
# concetti XBRL (us-gaap) in ordine di preferenza: il primo con un valore per quell'anno vince
RICAVI = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
          "RevenueFromContractWithCustomerIncludingAssessedTax", "RevenuesNetOfInterestExpense",
          "TotalRevenuesAndOtherIncome", "InterestAndDividendIncomeOperating"]
UTILE = ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"]
DEBITO_TOT = ["LongTermDebt", "DebtLongtermAndShorttermCombinedAmount"]
DEBITO_LUNGO = ["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"]
DEBITO_BREVE = ["LongTermDebtCurrent", "DebtCurrent"]
CASSA = ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
         "CashAndDueFromBanks"]
PN = ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]
EPS = ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted", "EarningsPerShareBasic"]
URL_DEPOSITI = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
# v7.51 COPERTURA DEL DIVIDENDO (idea da "Get Rich with Dividends", Lichtenfeld): dividendi pagati confrontati con
# utile e flusso di cassa libero (flusso di cassa operativo meno investimenti in impianti)
DIVIDENDI = ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends", "PaymentsOfOrdinaryDividends"]
FCO = ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"]
CAPEX = ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"]
PAYOUT_ALTO = 75                # % : sopra questa soglia il dividendo ha poco margine (regola del libro)
SALTO = 25                      # punti: payout salito di colpo rispetto alla media dei 2 anni prima = segnale di allarme
TRIMESTRI = 8                   # trimestri conservati: 4 da mostrare + 4 per il confronto con l'anno prima
FINESTRA_CONTI = 21             # giorni dopo la data stimata dei conti in cui il titolo si riscarica ogni giorno


def _ua():
    c = os.environ.get("SEC_CONTATTO", "").strip()
    return f"BoardEdge (analisi di mercato) {c}" if "@" in c else None


def _get(url, ua, timeout=40, tentativi=2):
    """JSON dalla SEC. 404 = azienda senza dati: nessun nuovo tentativo. Altri errori: 1 solo nuovo tentativo."""
    for n in range(tentativi):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            log.warning("SEC %s: HTTP %s (tentativo %d/%d)", url.rsplit("/", 1)[-1], e.code, n + 1, tentativi)
        except Exception as e:
            log.warning("SEC %s: %s (tentativo %d/%d)", url.rsplit("/", 1)[-1], type(e).__name__, n + 1, tentativi)
        if n + 1 < tentativi:                            # niente attesa inutile dopo l'ultimo tentativo
            time.sleep(3)
    return None


# --------------------------------------------------------------------------- estrazione dai "companyfacts"
def _annuali(fatti, concetti, durata=True):
    """{data di fine anno fiscale: valore} dal primo concetto utile. Solo bilanci annuali (10-K, fp=FY).
    durata=True per i flussi (ricavi, utile: periodo di ~1 anno), False per i saldi (debito, cassa: a una data).
    Per la stessa data vince il valore depositato per ULTIMO (le correzioni successive)."""
    usgaap = (fatti or {}).get("facts", {}).get("us-gaap", {})
    out = {}                                               # data di fine -> (valore, depositato il, priorita')
    for prio, c in enumerate(concetti):                    # in ordine di preferenza: un concetto dopo non sovrascrive
        for f in (usgaap.get(c) or {}).get("units", {}).get("USD") or []:
            if not str(f.get("form", "")).startswith("10-K") or f.get("fp") != "FY" or f.get("val") is None:
                continue
            fine = f.get("end")
            if not fine:
                continue
            if durata:
                ini = f.get("start")
                if not ini:
                    continue
                giorni = (date.fromisoformat(fine) - date.fromisoformat(ini)).days
                if not 330 <= giorni <= 400:                # solo periodi di circa un anno (no trimestri, no cumulati)
                    continue
            cur = out.get(fine)
            if cur is None or (cur[2] == prio and f.get("filed", "") >= cur[1]):
                out[fine] = (f["val"], f.get("filed", ""), prio)
    return {k: v[0] for k, v in out.items()}


def estrai(fatti, settore=None):
    """Sintesi degli ultimi ANNI anni fiscali: {anni: [{a, fine, ricavi, utile, debito, cassa, pn, dn}], perdite,
    crescita (% annua dei ricavi), giudizio, motivo}. None se mancano ricavi o utile."""
    ric, ut = _annuali(fatti, RICAVI), _annuali(fatti, UTILE)
    if not ric or not ut:
        return None
    dt, dl, db = _annuali(fatti, DEBITO_TOT, False), _annuali(fatti, DEBITO_LUNGO, False), _annuali(fatti, DEBITO_BREVE, False)
    cs, pn = _annuali(fatti, CASSA, False), _annuali(fatti, PN, False)
    fini = sorted(set(ric) & set(ut))[-ANNI:]
    anni = []
    for f in fini:
        deb = dt.get(f)
        if deb is None and (f in dl or f in db):
            deb = (dl.get(f) or 0) + (db.get(f) or 0)
        cassa = cs.get(f)
        anni.append({"a": int(f[:4]), "fine": f, "ricavi": ric[f], "utile": ut[f], "debito": deb, "cassa": cassa,
                     "pn": pn.get(f), "dn": (deb or 0) - (cassa or 0) if deb is not None or cassa is not None else None})
    if len(anni) < 2:
        return None
    perdite = sum(1 for x in anni if x["utile"] < 0)
    n = len(anni) - 1
    crescita = round(((anni[-1]["ricavi"] / anni[0]["ricavi"]) ** (1 / n) - 1) * 100, 1) \
        if anni[0]["ricavi"] and anni[-1]["ricavi"] and anni[0]["ricavi"] > 0 and anni[-1]["ricavi"] > 0 else None
    giudizio, motivo = _giudizio(anni, perdite, settore)
    out = {"anni": anni, "perdite": perdite, "crescita": crescita, "giudizio": giudizio, "motivo": motivo}
    try:                                                   # v7.54 tipo di azienda secondo Lynch (descrittivo)
        tipo = tipo_lynch(anni, settore)
        if tipo:
            out["lynch"] = tipo
    except Exception as e:
        log.info("tipo Lynch non calcolato (%s: %s)", type(e).__name__, e)
    try:                                                   # extra: mai bloccante per il bilancio
        cop = copertura_dividendo(fatti, fini, ut, settore)
        if cop:
            out["dividendo"] = cop
    except Exception as e:
        log.info("copertura dividendo non calcolata (%s: %s)", type(e).__name__, e)
    return out


CICLICI = ("mat", "ener")      # materiali ed energia: utili legati al ciclo economico e ai prezzi delle materie prime


def tipo_lynch(anni, settore=None):
    """v7.54 TIPO DI AZIENDA secondo Peter Lynch ("One Up on Wall Street"), solo descrittivo (non entra nella Forza):
    dice che cosa aspettarsi dal titolo. Regole fissate qui (crescita = utile annuo composto sugli anni disponibili):
      IN RIPRESA      : una perdita negli ultimi 3 anni e utile di nuovo positivo nell'ultimo anno;
      CICLICA         : settori materiali ed energia (utili che seguono il ciclo);
      CRESCITA RAPIDA : utile in crescita di almeno il 20% l'anno;
      SOLIDA          : utile in crescita tra il 10% e il 20% l'anno;
      CRESCITA LENTA  : utile in crescita sotto il 10% l'anno (o in calo).
    None con meno di 3 anni o con l'ultimo anno in perdita."""
    if len(anni) < 3 or anni[-1]["utile"] <= 0:
        return None
    if any(x["utile"] <= 0 for x in anni[-3:-1]):
        return {"tipo": "IN RIPRESA", "motivo": "tornata in utile dopo una perdita negli ultimi anni"}
    if settore in CICLICI:
        return {"tipo": "CICLICA", "motivo": "utili legati al ciclo economico e ai prezzi delle materie prime"}
    pos = [x for x in anni if x["utile"] > 0]
    n = anni[-1]["a"] - pos[0]["a"]
    if n < 2:
        return None
    cr = ((anni[-1]["utile"] / pos[0]["utile"]) ** (1 / n) - 1) * 100
    tipo = "CRESCITA RAPIDA" if cr >= 20 else "SOLIDA" if cr >= 10 else "CRESCITA LENTA"
    return {"tipo": tipo, "crescita": round(cr, 1), "anni": n,
            "motivo": f"utile {'+' if cr >= 0 else ''}{cr:.0f}% l'anno in {n} anni".replace(".", ",")}


def copertura_dividendo(fatti, fini, utile, settore=None):
    """v7.51 Quanto dell'utile e del flusso di cassa libero se ne va in dividendi, anno per anno (ultimi anni fiscali).
    -> {"anni": [{a, pagati, pu (% dell'utile), pf (% del flusso libero)}], "giudizio", "motivo"} o None se l'azienda
    non paga dividendi. Giudizio (soglie fissate prima, dal libro):
      A RISCHIO  : dividendi > 100% del flusso di cassa libero, oppure flusso libero o utile <= 0 con dividendo pagato;
      ATTENZIONE : payout > 75% (sull'utile o sul flusso libero) o salito di oltre 25 punti rispetto ai 2 anni prima;
      COPERTO    : tutto il resto.
    Banche e assicurazioni ("fin"): il flusso di cassa libero non e' significativo, conta solo l'utile.
    Immobiliare ("imm", REIT): per legge distribuiscono quasi tutto e l'utile contabile e' basso (ammortamenti):
    si usa solo il flusso di cassa libero."""
    div = _annuali(fatti, DIVIDENDI)
    fco, capex = _annuali(fatti, FCO), _annuali(fatti, CAPEX)
    righe = []
    for f in fini:
        d = div.get(f)
        if not d or d <= 0:
            continue
        u = utile.get(f)
        fl = fco.get(f) - (capex.get(f) or 0) if fco.get(f) is not None else None
        righe.append({"a": int(f[:4]), "pagati": d,
                      "pu": round(d / u * 100) if u and u > 0 else None,
                      "pf": round(d / fl * 100) if fl and fl > 0 else None, "u_neg": bool(u is not None and u <= 0),
                      "f_neg": bool(fl is not None and fl <= 0)})
    if not righe:
        return None
    ult = righe[-1]
    usa_u, usa_f = settore != "imm", settore != "fin"
    pay = [x for x in ((ult["pu"] if usa_u else None), (ult["pf"] if usa_f else None)) if x is not None]
    prima = [r for r in righe[-3:-1]]
    def media(k):
        v = [r[k] for r in prima if r[k] is not None]
        return sum(v) / len(v) if v else None
    salto = max([ult[k] - media(k) for k in (("pu",) if not usa_f else ("pf",) if not usa_u else ("pu", "pf"))
                 if ult[k] is not None and media(k) is not None] or [0])
    if (usa_f and (ult["f_neg"] or (ult["pf"] or 0) > 100)) or (usa_u and ult["u_neg"]):
        g, m = "A RISCHIO", ("dividendo pagato con flusso di cassa libero negativo" if usa_f and ult["f_neg"]
                             else "dividendo pagato in un anno in perdita" if usa_u and ult["u_neg"]
                             else f"dividendi pari al {ult['pf']}% del flusso di cassa libero")
    elif pay and max(pay) > PAYOUT_ALTO:
        g, m = "ATTENZIONE", f"payout del {max(pay)}%: poco margine se gli utili calano"
    elif salto >= SALTO:
        g, m = "ATTENZIONE", f"payout salito di {round(salto)} punti rispetto ai 2 anni prima"
    elif pay:
        g, m = "COPERTO", f"payout del {max(pay)}%: margine per mantenere e far crescere il dividendo"
    else:
        return {"anni": righe, "giudizio": None, "motivo": "dati di utile o flusso di cassa non disponibili"}
    return {"anni": righe, "giudizio": g, "motivo": m}


def _giudizio(anni, perdite, settore):
    medio = sum(x["utile"] for x in anni) / len(anni)
    ult = anni[-1]
    dn, pn = ult.get("dn"), ult.get("pn")
    finanza = settore == "fin"
    if not finanza and pn is not None and pn < 0:
        return "INDEBITATA", "patrimonio netto negativo (i debiti superano il valore di tutto l'attivo)"
    if not finanza and dn is not None and medio <= 0 and dn > 0:
        return "INDEBITATA", "utile medio negativo e debiti superiori alla liquidita'"
    if not finanza and dn is not None and medio > 0 and dn > 6 * medio:
        return "INDEBITATA", f"debito netto pari a {dn / medio:.1f} anni di utile medio"
    if perdite == 0 and len(anni) >= 3 and (finanza or dn is None or dn <= 3 * medio):
        if finanza:
            return "SOLIDA", "utile in tutti gli anni (banca/assicurazione: il debito fa parte dell'attivita')"
        if dn is None:                                  # debito e cassa non dichiarati nel formato standard XBRL
            return "SOLIDA", "utile in tutti gli anni (debito non indicato nel bilancio)"
        return "SOLIDA", "utile in tutti gli anni e " + ("piu' liquidita' che debiti" if dn <= 0
                                                          else f"debito netto ripagabile in {dn / medio:.1f} anni di utile")
    return "NELLA MEDIA", ((f"{perdite} anno" if perdite == 1 else f"{perdite} anni") + f" in perdita su {len(anni)}" if perdite else "utile costante ma debito netto superiore a 3 anni di utile")


# --------------------------------------------------------------------------- giro settimanale
def _cik(cartella, ua, oggi):
    f = os.path.join(cartella, "sec_cik.json")
    c = A._leggi(f) or {}
    if c.get("agg", "") < (oggi - timedelta(days=GIORNI_CIK)).isoformat() or not c.get("mappa"):
        dati = _get(URL_CIK, ua)
        if dati:
            c = {"agg": oggi.isoformat(), "mappa": {v["ticker"].upper(): int(v["cik_str"]) for v in dati.values()}}
            A._scrivi(f, c)
    return c.get("mappa") or {}


def titoli_usa(el=None):
    """Titoli USA dell'elenco (S&P 500 e Nasdaq-100: niente suffisso di borsa estera)."""
    return [x for x in (el if el is not None else A.elenco()) if ("sp500" in x["l"] or "ndx" in x["l"]) and "." not in x["t"]]


# --------------------------------------------------------------------------- trimestrali (v6.54)
VERSIONE_TRIM = 3               # v7.51: copertura del dividendo (rifare tutti i file). v7.15: concetto SEC piu' recente per i trimestri (vedi _periodi)


def _periodi(fatti, concetti, unita="USD"):
    """Tutti i periodi con durata dal primo concetto utile: {(inizio, fine): valore}. Vince il deposito piu' recente
    (correzioni). Prende sia i 10-Q (trimestri 1-3) sia i 10-K (anno intero, serve per ricavare il 4o trimestre)."""
    usgaap = (fatti or {}).get("facts", {}).get("us-gaap", {})
    # v7.15: si sceglie il concetto con i dati PIU' RECENTI (a parita', il primo della lista). Prima vinceva il primo
    # concetto con dati qualsiasi: chi ha cambiato concetto nel tempo (es. NVIDIA, Broadcom) restava fermo al 2019-2020.
    # Niente mescolanze tra concetti (le definizioni cambiano).
    migliore, fine_migliore = {}, ""
    for c in concetti:
        righe = (usgaap.get(c) or {}).get("units", {}).get(unita) or []
        out = {}
        for f in righe:
            if not str(f.get("form", "")).startswith(("10-Q", "10-K")) or f.get("val") is None:
                continue
            ini, fine = f.get("start"), f.get("end")
            if not ini or not fine:
                continue
            k = (ini, fine)
            if k not in out or f.get("filed", "") >= out[k][1]:
                out[k] = (f["val"], f.get("filed", ""))
        if out:
            ultima = max(f for _, f in out)
            if ultima > fine_migliore:
                migliore, fine_migliore = {k: v[0] for k, v in out.items()}, ultima
    return migliore


def _giorni(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def _trimestrali(per):
    """{fine: (inizio, valore, ricavato)} dei trimestri. I trimestri 1-3 arrivano dai 10-Q (periodi di ~3 mesi);
    il 4o NON viene depositato da solo: si ricava come anno intero meno i tre trimestri precedenti (ricavato=True)."""
    q = {f: (i, v, False) for (i, f), v in per.items() if 80 <= _giorni(i, f) <= 100}
    for (i, f), v in per.items():
        if not 330 <= _giorni(i, f) <= 400 or f in q:
            continue
        dentro = sorted((qf, qv) for qf, (qi, qv, _) in q.items() if qi >= i and qf < f)   # trimestri di quell'anno
        if len(dentro) == 3 and 250 <= _giorni(i, dentro[-1][0]) <= 300:
            ini4 = (date.fromisoformat(dentro[-1][0]) + timedelta(days=1)).isoformat()
            q[f] = (ini4, v - sum(x[1] for x in dentro), True)
    return q


def trimestri(fatti):
    """Ultimi TRIMESTRI trimestri: [{ini, fine, ricavi, utile, eps, r4 (4o trimestre ricavato)}] dal piu' vecchio.
    Le variazioni sull'anno prima le calcola il sito (stesso trimestre di ~1 anno prima)."""
    ric = _trimestrali(_periodi(fatti, RICAVI))
    ut = _trimestrali(_periodi(fatti, UTILE))
    eps = _trimestrali(_periodi(fatti, EPS, "USD/shares"))
    fini = sorted(set(ric) & set(ut))[-TRIMESTRI:]
    out = []
    for f in fini:
        e = eps.get(f)
        out.append({"ini": ric[f][0], "fine": f, "ricavi": ric[f][1], "utile": ut[f][1],
                    "eps": round(e[1], 2) if e else None, "r4": ric[f][2] or ut[f][2]})
    return out


def conti(depositi, oggi):
    """Date dei risultati dagli 8-K con voce 2.02 ("Results of Operations"): ultimo comunicato e prossimo STIMATO
    (la stessa data di un anno prima + 52 settimane). La SEC non pubblica il calendario: e' una stima, e il sito lo dice."""
    r = ((depositi or {}).get("filings") or {}).get("recent") or {}
    date_ = sorted({d for fo, d, it in zip(r.get("form", []), r.get("filingDate", []), r.get("items", []))
                    if fo == "8-K" and "2.02" in str(it)})
    if not date_:
        return None
    ultimo = date_[-1]
    candidati = [date.fromisoformat(d) + timedelta(days=364) for d in date_ if d > (oggi - timedelta(days=430)).isoformat()]
    # il prossimo e' a circa un trimestre dall'ultimo (60-120 giorni); se l'anno prima manca, ultimo + 13 settimane
    futuri = [c for c in candidati if 60 <= _giorni(ultimo, c.isoformat()) <= 120]
    prossimo = min(futuri) if futuri else date.fromisoformat(ultimo) + timedelta(days=91)
    return {"ultimo": ultimo, "prossimo": prossimo.isoformat(), "stima": True}


def aggiorna(cartella, oggi=None, el=None, scarica=None, pausa=PAUSA):
    """Riscarica (al massimo una volta a settimana per titolo) e scrive pubblico/bilanci/<T>.json + bilanci.json.
    Restituisce {ok, aggiornati, falliti, saltato}. Mai bloccante per il resto del workflow."""
    oggi = oggi or date.today()
    ua = _ua()
    if not ua and scarica is None:
        log.warning("bilanci SEC: manca il Secret SEC_CONTATTO (email richiesta dalla SEC): nessun download")
        return {"ok": 0, "aggiornati": 0, "falliti": [], "saltato": True}
    get = scarica or (lambda url: _get(url, ua))
    mappa = _cik(cartella, ua, oggi) if scarica is None else (scarica("CIK") or {})
    usa = titoli_usa(el)
    indice, aggiornati, falliti = {}, 0, []
    for x in usa:
        t = x["t"]
        f = os.path.join(cartella, "pubblico", "bilanci", A._nome_file(t) + ".json")
        vecchio = A._leggi(f) or {}
        giorno = zlib.crc32(("sec" + t).encode()) % 5                     # ogni titolo il suo giorno della settimana
        # v7.15: i file fatti prima della correzione dei trimestri (campo "v" assente) si rifanno subito
        scaduto = vecchio.get("agg", "") < (oggi - timedelta(days=8)).isoformat() or vecchio.get("v") != VERSIONE_TRIM
        pc = (vecchio.get("conti") or {}).get("prossimo")
        # stagione dei conti: dalla data stimata e per FINESTRA_CONTI giorni si riscarica ogni giorno (trimestrale fresca)
        stagione = bool(pc) and 0 <= _giorni(pc, oggi.isoformat()) <= FINESTRA_CONTI and vecchio.get("agg") != oggi.isoformat()
        if not vecchio or (oggi.weekday() == giorno and vecchio.get("agg") != oggi.isoformat()) or scaduto or stagione \
                or (vecchio.get("anni") and "trim" not in vecchio):        # v6.54: file vecchi senza trimestrali
            cik = mappa.get(t.upper()) or mappa.get(t.upper().replace("-", "."))
            fatti = get(URL_FATTI.format(cik=cik)) if cik else None
            if pausa and cik:
                time.sleep(pausa)
            try:                                         # un'azienda con dati strani NON deve fermare le altre
                sintesi = estrai(fatti, x.get("s")) if fatti else None
            except Exception as e:
                log.warning("bilanci SEC: %s non elaborato (%s: %s)", t, type(e).__name__, e)
                sintesi = None
            if sintesi:
                try:                                     # trimestrali e date dei conti: extra, mai bloccanti
                    sintesi["trim"] = trimestri(fatti)
                    dep = get(URL_DEPOSITI.format(cik=cik))
                    sintesi["conti"] = conti(dep, oggi)
                except Exception as e:
                    log.warning("trimestrali SEC: %s non elaborato (%s: %s)", t, type(e).__name__, e)
                vecchio = dict(sintesi, t=t, agg=oggi.isoformat(), fonte="SEC EDGAR (10-K, 10-Q, 8-K)", v=VERSIONE_TRIM)
                A._scrivi(f, vecchio)
                aggiornati += 1
            else:
                falliti.append(t)
        if vecchio.get("anni"):
            u = vecchio["anni"][-1]
            indice[t] = {"g": vecchio["giudizio"], "p": vecchio["perdite"], "c": vecchio.get("crescita"), "a": u["a"]}
    A._scrivi(os.path.join(cartella, "pubblico", "bilanci.json"), {"aggiornato": oggi.isoformat(), "titoli": indice})
    if falliti:
        log.warning("bilanci SEC: %d titoli senza dati (%s%s)", len(falliti), ", ".join(falliti[:15]), "..." if len(falliti) > 15 else "")
    log.info("bilanci SEC: %d titoli con bilancio, %d aggiornati oggi", len(indice), aggiornati)
    return {"ok": len(indice), "aggiornati": aggiornati, "falliti": falliti, "saltato": False}


# --------------------------------------------------------------------------- STORICO COMPLETO (v6.64, per gli studi)
# Per i backtest sulla QUALITA' dei bilanci serve tutta la storia (dal 2009 circa) e soprattutto la DATA in cui ogni
# bilancio e' stato PUBBLICATO: un dato si puo' usare solo da quel giorno in poi (niente sguardi al futuro).
# Per ogni anno fiscale si tiene il valore PUBBLICATO PER PRIMO (il 10-K originale), non le correzioni arrivate anni
# dopo: e' quello che un investitore vedeva davvero in quel momento. File: pubblico/bilanci_storia/<T>.json
# {"t", "agg", "serie": {voce: [[fine anno fiscale, valore, depositato il], ...]}}. Non cambia nulla nel sito.
FLUSSO_CASSA = ["NetCashProvidedByUsedInOperatingActivities",
                "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"]
VOCI_STORIA = {"ricavi": (RICAVI, True), "utile": (UTILE, True), "fco": (FLUSSO_CASSA, True),
               "debito": (DEBITO_TOT, False), "debito_lungo": (DEBITO_LUNGO, False), "debito_breve": (DEBITO_BREVE, False),
               "cassa": (CASSA, False), "pn": (PN, False)}
STORIA_GIORNI = 30              # ogni azienda si riscarica al massimo una volta al mese
STORIA_MAX_SECONDI = 1500       # tetto di tempo per giro (25 minuti): le altre aziende al giro dopo


def _prima_pubblicazione(fatti, concetti, durata):
    """[[fine, valore, depositato]] per anno fiscale: il valore del PRIMO deposito (10-K) che lo riporta.
    I concetti sono in ordine di preferenza: uno dopo riempie solo gli anni che mancano ai precedenti."""
    usgaap = (fatti or {}).get("facts", {}).get("us-gaap", {})
    out = {}
    for c in concetti:
        trovati = {}
        for f in (usgaap.get(c) or {}).get("units", {}).get("USD") or []:
            if not str(f.get("form", "")).startswith("10-K") or f.get("val") is None or not f.get("end") or not f.get("filed"):
                continue
            if durata:                                     # flussi: solo periodi di circa un anno
                if not f.get("start"):
                    continue
                g = (date.fromisoformat(f["end"]) - date.fromisoformat(f["start"])).days
                if not 330 <= g <= 400:
                    continue
            fine = f["end"]
            if fine not in trovati or f["filed"] < trovati[fine][1]:
                trovati[fine] = (f["val"], f["filed"])
        for fine, (v, dep) in trovati.items():
            out.setdefault(fine, [fine, v, dep])          # il concetto preferito non viene sovrascritto
    return [out[k] for k in sorted(out)]


def estrai_storia(fatti):
    """{voce: [[fine, valore, depositato]]} per tutte le VOCI_STORIA (voci assenti = lista vuota)."""
    return {k: _prima_pubblicazione(fatti, c, d) for k, (c, d) in VOCI_STORIA.items()}


def storia(cartella, oggi=None, el=None, scarica=None, pausa=PAUSA, max_secondi=STORIA_MAX_SECONDI):
    """Scarica lo storico completo dei bilanci delle aziende USA (al massimo una volta al mese ciascuna, entro un tetto
    di tempo). Restituisce {ok, nuove, mancanti}. Mai bloccante: un'azienda che fallisce non ferma le altre."""
    oggi = oggi or date.today()
    ua = _ua()
    if not ua and scarica is None:
        return {"ok": 0, "nuove": 0, "mancanti": 0, "saltato": True}
    get = scarica or (lambda url: _get(url, ua))
    mappa = _cik(cartella, ua, oggi) if scarica is None else (scarica("CIK") or {})
    inizio, ok, nuove, mancanti = time.time(), 0, 0, 0
    for x in titoli_usa(el):
        t = x["t"]
        f = os.path.join(cartella, "pubblico", "bilanci_storia", A._nome_file(t) + ".json")
        vecchio = A._leggi(f) or {}
        if vecchio.get("agg", "") >= (oggi - timedelta(days=STORIA_GIORNI)).isoformat():
            ok += 1
            continue
        if time.time() - inizio > max_secondi:            # tempo finito: le altre al prossimo giro
            mancanti += 1
            continue
        cik = mappa.get(t.upper()) or mappa.get(t.upper().replace("-", "."))
        fatti = get(URL_FATTI.format(cik=cik)) if cik else None
        if pausa and cik:
            time.sleep(pausa)
        try:
            serie = estrai_storia(fatti) if fatti else None
        except Exception as e:
            log.warning("storico bilanci: %s non elaborato (%s: %s)", t, type(e).__name__, e)
            serie = None
        if serie and serie["ricavi"]:
            A._scrivi(f, {"t": t, "agg": oggi.isoformat(), "serie": serie, "fonte": "SEC EDGAR companyfacts (10-K)"})
            ok += 1
            nuove += 1
        else:
            mancanti += 1
    log.info("storico bilanci: %d aziende pronte (%d scaricate ora), %d da completare", ok, nuove, mancanti)
    return {"ok": ok, "nuove": nuove, "mancanti": mancanti}
