# -*- coding: utf-8 -*-
"""
studio_insider.py - GLI ACQUISTI DEI MANAGER CON SOLDI PROPRI ANTICIPANO RENDIMENTI MIGLIORI?

IDEA (Peter Lynch, "One Up on Wall Street"): "quando gli insider comprano, e' il segnale migliore". Qui lo si misura
sui titoli USA del sito (S&P 500 e Nasdaq-100). Acquisti: archivi trimestrali ufficiali della SEC (moduli 3/4/5, dal
2006; l'endpoint insider di EODHD non e' nel piano: 12/11/2026). Prezzi: EODHD.

REGOLE FISSATE PRIMA DI VEDERE I RISULTATI
  - evento = ACQUISTO sul mercato (codice "P") di un insider, valore del deposito >= 50.000 $; si usa la data di
    DEPOSITO del modulo (quando il pubblico lo vede), non quella dell'operazione; piu' acquisti dello stesso titolo nello stesso
    mese = un solo evento (il primo);
  - ingresso alla chiusura del giorno di borsa DOPO il deposito; risultato a 3, 6 e 12 mesi (63, 126, 252 sedute)
    MENO quello dell'S&P 500 (SPY) nello stesso periodo = rendimento in eccesso;
  - incertezza: media per MESE di calendario (gli eventi dello stesso mese sono legati), blocchi di 3 mesi,
    intervallo z = 2,81 (Bonferroni per 3 orizzonti x 2 periodi + margine);
  - sviluppo = eventi fino al 31/12/2018, verifica = dal 01/01/2019;
  - VANTAGGIO solo se a 6 mesi il limite basso e' sopra zero nello sviluppo E la media resta sopra zero nella verifica.
LIMITE NOTO: i titoli sono quelli presenti OGGI negli indici (sopravvissuti): il risultato e' ottimista per tutti,
  per questo il confronto e' anche con TUTTI i titoli dello stesso elenco (stesse date, senza acquisti).
USO: python studi/studio_insider.py   (EODHD_API_KEY e SEC_CONTATTO solo dai Secrets)
"""
import io
import json
import os
import sys
import time
import urllib.request
import zipfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cot_radar import azioni as A, eodhd, fondamentali as F   # noqa: E402

DAL = "2006-01-01"
MIN_VALORE = 50_000
ORIZZONTI = {"3m": 63, "6m": 126, "12m": 252}
TAGLIO = "2019-01-01"
Z = 2.81
TEMPO_MAX = 4800                 # secondi: il workflow ha 90 minuti


def prezzi(sym):
    """[(data, prezzo rettificato)] EODHD dal DAL, oppure []."""
    return eodhd.serie(sym, DAL) or []


MESI = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
URL_SEC = ("https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{q}_form345.zip",
           "https://www.sec.gov/files/datastandardsinnovation/data/insider-transactions-data-sets/{q}_form345.zip")


def _data(s):
    """'2019-03-31' oppure '31-MAR-2019' -> '2019-03-31'; '' se non e' una data."""
    s = str(s or "").strip()[:11]
    try:
        if len(s) >= 10 and s[4] == "-":
            return date.fromisoformat(s[:10]).isoformat()
        g, m, a = s.split("-")
        return date(int(a), MESI[m.upper()], int(g)).isoformat()
    except (KeyError, ValueError):
        return ""


def _tabella(z, nome):
    """Righe (dict per nome di colonna) di un file .tsv dello zip, senza caricarlo tutto in memoria."""
    vero = next((n for n in z.namelist() if n.upper().endswith(nome)), None)
    if not vero:
        return
    with z.open(vero) as fh:
        testa = None
        for riga in io.TextIOWrapper(fh, encoding="utf-8", errors="replace"):
            campi = riga.rstrip("\r\n").split("\t")
            if testa is None:
                testa = [c.strip().upper() for c in campi]
                continue
            yield dict(zip(testa, campi))


def trimestre_sec(q, ua, simboli):
    """{simbolo: [(data di deposito, valore in $)]} degli acquisti 'P' di un trimestre (dati SEC, moduli 3/4/5)."""
    grezzo = None
    for u in URL_SEC:
        try:
            req = urllib.request.Request(u.format(q=q), headers={"User-Agent": ua, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=120) as r:
                grezzo = r.read()
            break
        except Exception as e:                      # 404 sul primo indirizzo: si prova il secondo
            ultimo = getattr(e, "code", type(e).__name__)
    if grezzo is None:
        print(q, "non scaricato:", ultimo, flush=True)
        return {}
    z = zipfile.ZipFile(io.BytesIO(grezzo))
    dep = {}                                        # deposito -> (simbolo, data di deposito)
    for x in _tabella(z, "SUBMISSION.TSV"):
        s = str(x.get("ISSUERTRADINGSYMBOL", "")).strip().upper().replace(".", "-")
        d = _data(x.get("FILING_DATE"))
        if s in simboli and d:
            dep[x.get("ACCESSION_NUMBER")] = (s, d)
    out = {}
    for x in _tabella(z, "NONDERIV_TRANS.TSV"):
        k = dep.get(x.get("ACCESSION_NUMBER"))
        if not k or str(x.get("TRANS_CODE", "")).strip().upper() != "P":
            continue
        try:
            valore = float(x.get("TRANS_SHARES") or 0) * float(x.get("TRANS_PRICEPERSHARE") or 0)
        except ValueError:
            continue
        if valore > 0:
            out.setdefault(k[0], []).append((k[1], valore))
    time.sleep(0.5)
    return out


def eventi_sec(ua, simboli):
    """{simbolo: [date di deposito]}: acquisti dello stesso deposito sommati, soglia MIN_VALORE, uno per mese."""
    tutti = {}
    oggi = date.today()
    for anno in range(2006, oggi.year + 1):
        for t in range(1, 5):
            if (anno, t) >= (oggi.year, (oggi.month - 1) // 3 + 1):
                break
            for s, righe in trimestre_sec(f"{anno}q{t}", ua, simboli).items():
                tutti.setdefault(s, []).extend(righe)
        print(anno, "titoli con acquisti finora:", len(tutti), flush=True)
    out = {}
    for s, righe in tutti.items():
        per_giorno = {}
        for d, v in righe:
            per_giorno[d] = per_giorno.get(d, 0) + v
        visti, ev = set(), []
        for d in sorted(per_giorno):
            if per_giorno[d] >= MIN_VALORE and d >= DAL and d[:7] not in visti:
                visti.add(d[:7])
                ev.append(d)
        if ev:
            out[s] = ev
    return out


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
    ua = F._ua()
    if not ua:
        print("manca SEC_CONTATTO")
        return 1
    spy = prezzi("SPY.US")
    usa = F.titoli_usa(A.elenco())
    acquisti = eventi_sec(ua, {x["t"].replace(".", "-").upper() for x in usa})
    print("titoli con almeno un evento:", len(acquisti), "eventi:", sum(len(v) for v in acquisti.values()), flush=True)
    righe, base, coperti = [], [], 0
    for x in usa:
        if time.time() - t0 > TEMPO_MAX:
            print("tempo massimo: studio parziale")
            break
        sym = x["t"].replace(".", "-") + ".US"
        ev = acquisti.get(x["t"].replace(".", "-").upper(), [])
        px = prezzi(sym)                            # anche senza acquisti: serve al confronto "tutti"
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
    out = {"titoli": coperti, "eventi": len(righe), "chiamate": eodhd.CHIAMATE, "secondi": round(time.time() - t0)}
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
