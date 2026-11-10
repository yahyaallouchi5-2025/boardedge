# -*- coding: utf-8 -*-
"""
eventi_titoli.py - v7.27 FRAZIONAMENTI E TITOLI TOLTI DALLA BORSA, rilevati in automatico.

PERCHE'
  Nell'ottobre 2026 Beazley e Schroders sono state comprate e tolte dalla borsa di Londra: sono rimaste per giorni
  nell'elenco con il prezzo fermo, e ce ne siamo accorti solo guardando a mano. Un frazionamento (es. 10 azioni
  nuove per 1 vecchia) invece fa sembrare un drawdown del -90% se lo storico non viene rettificato subito.

TRE CONTROLLI (dal giro delle azioni, mai bloccanti)
  1) FRAZIONAMENTI (giro USA della sera, ogni giorno): EODHD "eod-bulk-last-day/{borsa}?type=splits" per le borse
     dei nostri titoli (ultime 3 sedute, ognuna una volta sola). Se un nostro titolo si e' frazionato dopo l'ultimo
     download completo, il suo storico viene RISCARICATO TUTTO al giro successivo (prezzi rettificati corretti).
  2) TOLTI DALLA BORSA (una volta a settimana): "exchange-symbol-list/{borsa}" attivi e "?delisted=1".
     Delistato = presente tra i delistati E assente tra gli attivi (un codice riusato da un'altra societa' resta attivo).
  3) PREZZI FERMI (ogni giro, zero chiamate): ultimo prezzo piu' vecchio di FERMO_GIORNI rispetto agli altri titoli
     della stessa borsa (le feste fermano tutti insieme, quindi non danno falsi allarmi). Copre anche Milano e l'Asia,
     che EODHD non ha.
  Delistati e fermi escono da vetrina, titoli in sconto e 5 azioni dei portafogli; restano in tabella con l'etichetta
  e la sorveglianza avvisa l'admin di toglierli dall'elenco.

FILE: pubblico/eventi_titoli.json
  {"agg", "agg_delist", "delistati": {t: {"nome", "ultimo"}}, "fermi": {t: data}, "split": {t: {"data", "r", "f"}},
   "visti": {borsa: [date controllate]}}
  r = testo del rapporto ("10:1" = 10 azioni nuove per 1 vecchia), f = fattore sul prezzo (1/10).

DEBUG: python -c "from cot_radar import eventi_titoli as E; print(E.rapporto('10.000000/1.000000'))"
"""
import os
from datetime import date, datetime, timedelta, timezone

from . import azioni as A
from . import eodhd
from .log import log

FERMO_GIORNI = 7          # giorni di calendario senza prezzi mentre gli altri titoli della borsa si muovono
MIN_PARI = 3              # titoli minimi della stessa borsa per poter dire "fermo"
DELIST_GIORNI = 7         # elenchi attivi/delistati: una volta a settimana
SPLIT_SEDUTE = 3          # sedute controllate a ritroso (recupera un giro saltato)
SPLIT_TIENI = 60          # giorni per cui un frazionamento resta segnalato nella scheda


def file_eventi(cartella):
    return os.path.join(cartella, "pubblico", "eventi_titoli.json")


def codice(t):
    """Ticker Yahoo -> (codice, borsa EODHD) per gli elenchi e i frazionamenti; None se EODHD non lo copre."""
    if t.endswith(".L"):
        return t[:-2], "LSE"
    s = eodhd.simbolo(t)
    if not s or s.endswith((".INDX", ".CC")):
        return None
    c, b = s.rsplit(".", 1)
    return c, b


def rapporto(testo):
    """'10.000000/1.000000' (nuove/vecchie) -> ("10:1", 0.1) = fattore sul prezzo. None se non leggibile."""
    try:
        nuove, vecchie = (float(x) for x in str(testo).split("/"))
        if nuove <= 0 or vecchie <= 0 or nuove == vecchie:
            return None
    except (ValueError, TypeError):
        return None
    g = lambda x: ("%g" % x)
    return "%s:%s" % (g(nuove), g(vecchie)), round(vecchie / nuove, 8)


def ultime_sedute(oggi, n=SPLIT_SEDUTE):
    """Le ultime n date feriali fino a oggi compreso ('AAAA-MM-GG', dalla piu' recente)."""
    out, g = [], oggi
    while len(out) < n:
        if g.weekday() < 5:
            out.append(g.isoformat())
        g -= timedelta(days=1)
    return out


def fermi(ultimi):
    """{ticker: ultima data} -> {ticker: ultima data} dei titoli fermi da oltre FERMO_GIORNI rispetto alla loro borsa.
    La borsa e' il suffisso del ticker ("" = USA); serve un riferimento di almeno MIN_PARI titoli."""
    suff = lambda t: t.rsplit(".", 1)[1] if "." in t else ""
    gruppi = {}
    for t, d in ultimi.items():
        if d:
            gruppi.setdefault(suff(t), []).append(d)
    out = {}
    for t, d in ultimi.items():
        pari = sorted(gruppi.get(suff(t), []))
        if not d or len(pari) < MIN_PARI:
            continue
        rif = pari[len(pari) // 2]                     # mediana: un solo titolo "nel futuro" non sposta il riferimento
        if (date.fromisoformat(rif) - date.fromisoformat(d)).days > FERMO_GIORNI:
            out[t] = d
    return out


def delistati(nostri, attivi, tolti):
    """nostri = {ticker: (codice, borsa)}; attivi/tolti = {borsa: {codice: nome}} (borse senza elenco: saltate).
    -> {ticker: nome EODHD} dei titoli presenti tra i delistati e assenti tra gli attivi."""
    out = {}
    for t, (c, b) in nostri.items():
        if b in attivi and b in tolti and c in tolti[b] and c not in attivi[b]:
            out[t] = tolti[b][c] or ""
    return out


def _elenco(borsa, tolti=False):
    """{codice: nome} di una borsa (attivi o delistati), None se la risposta e' vuota o rotta."""
    js = eodhd.get("exchange-symbol-list/" + borsa, {"delisted": 1} if tolti else None, timeout=90, tentativi=2)
    if not isinstance(js, list) or (not tolti and len(js) < 20):
        return None
    return {str(x.get("Code")): x.get("Name") for x in js if isinstance(x, dict) and x.get("Code")}


def _split_borsa(borsa, giorno):
    js = eodhd.get("eod-bulk-last-day/" + borsa, {"type": "splits", "date": giorno}, timeout=60, tentativi=2)
    return js if isinstance(js, list) else None


def aggiorna(cartella, el=None, oggi=None, frazionamenti=True, scarica_elenco=_elenco, scarica_split=_split_borsa):
    """Aggiorna pubblico/eventi_titoli.json e, sui frazionamenti nuovi, forza lo storico completo. Mai bloccante.
    frazionamenti=False (giri Asia/Europa): solo prezzi fermi + elenchi settimanali se scaduti."""
    oggi = oggi or date.today()
    elenco = el if el is not None else A.elenco()
    f = file_eventi(cartella)
    ev = A._leggi(f) or {}
    ev.setdefault("visti", {})
    nostri = {x["t"]: codice(x["t"]) for x in elenco}
    nostri = {t: c for t, c in nostri.items() if c}
    borse = sorted({b for _, b in nostri.values()})
    grezzi = lambda t: os.path.join(cartella, "grezzi", A._nome_file(t) + ".json")

    # 1) frazionamenti
    split = {t: s for t, s in (ev.get("split") or {}).items()
             if s.get("data", "") >= (oggi - timedelta(days=SPLIT_TIENI)).isoformat()}
    if frazionamenti and eodhd.attivo():
        per_codice = {(c, b): t for t, (c, b) in nostri.items()}
        sedute = ultime_sedute(oggi)
        for b in borse:
            visti = set(ev["visti"].get(b) or [])
            for g in sedute:
                if g in visti:
                    continue
                righe = scarica_split(b, g)
                if righe is None:
                    continue                            # riprova al giro dopo
                if g != oggi.isoformat():               # la seduta di oggi si ricontrolla (EODHD la completa la sera)
                    visti.add(g)
                for x in righe:
                    t = per_codice.get((str(x.get("code")), b))
                    r = rapporto(x.get("split"))
                    d = str(x.get("date") or g)[:10]
                    if t and r:
                        split[t] = {"data": d, "r": r[0], "f": r[1]}
            ev["visti"][b] = sorted(visti)[-10:]
        for t, s in split.items():                      # storico da riscaricare se scaricato prima del frazionamento
            rec = A._leggi(grezzi(t))
            if rec and rec.get("agg_full", "") <= s["data"] and not s.get("rifatto"):
                rec["agg_full"] = ""
                A._scrivi(grezzi(t), rec)
                s["rifatto"] = oggi.isoformat()
                log.warning("frazionamento %s %s del %s: storico riscaricato al prossimo giro", t, s["r"], s["data"])
    ev["split"] = split

    # 2) tolti dalla borsa (settimanale)
    scaduto = ev.get("agg_delist", "") < (oggi - timedelta(days=DELIST_GIORNI)).isoformat()
    if scaduto and eodhd.attivo():
        attivi, tolti = {}, {}
        for b in borse:
            a, d = scarica_elenco(b), scarica_elenco(b, tolti=True)
            if a is not None and d is not None:
                attivi[b], tolti[b] = a, d
        if attivi:
            vecchi = ev.get("delistati") or {}
            nuovi = delistati(nostri, attivi, tolti)
            # borse non scaricate stavolta: si tiene l'esito precedente
            ev["delistati"] = {t: {"nome": n} for t, n in nuovi.items()}
            ev["delistati"].update({t: v for t, v in vecchi.items() if nostri.get(t, (0, None))[1] not in attivi})
            ev["agg_delist"] = oggi.isoformat()

    # 3) prezzi fermi (sempre) + ultima data dei delistati
    ultimi = {}
    for x in elenco:
        d = (A._leggi(grezzi(x["t"])) or {}).get("d") or []
        ultimi[x["t"]] = d[-1][0] if d else None
    ev["fermi"] = fermi(ultimi)
    for t, v in (ev.get("delistati") or {}).items():
        v["ultimo"] = ultimi.get(t)
    ev["agg"] = datetime.now(timezone.utc).isoformat(timespec="minutes")
    A._scrivi(f, ev)
    if ev.get("delistati") or ev["fermi"]:
        log.warning("titoli da controllare: delistati %s, prezzi fermi %s",
                    ", ".join(sorted(ev.get("delistati") or {})) or "-", ", ".join(sorted(ev["fermi"])) or "-")
    return ev


def sospesi(ev):
    """Titoli da tenere fuori da vetrina e portafogli: delistati + prezzi fermi."""
    ev = ev or {}
    return set(ev.get("delistati") or {}) | set(ev.get("fermi") or {})
