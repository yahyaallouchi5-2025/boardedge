# -*- coding: utf-8 -*-
"""
studio_cot_bible.py - IL METODO DEL LIBRO "THE COMMITMENTS OF TRADERS BIBLE" (Stephen Briese, 2008), MESSO ALLA PROVA
(richiesta di Ya, 13/11/2026). Solo offline: nessun download, dati gia' archiviati dal sito (ramo "storico").

REGOLE FISSATE PRIMA DI GUARDARE I RISULTATI (prese dal libro, capitoli 6, 7 e 9):
  COT Index (cap. 6)      = 100 x (netto attuale - minimo) / (massimo - minimo) del netto del gruppo nelle ultime
                            156 settimane (3 anni, il periodo "standard" del libro). Netto = long - short (appendice A, es. 1).
  Movement Index (cap. 7) = COT Index di oggi - COT Index di 6 settimane fa (il libro usa 6).
  S1 ESTREMI COMMERCIAL   compra quando il COT Index dei commercial entra sopra 90, vendi quando entra sotto 5.
  S2 SURGE COMMERCIAL     compra quando il Movement Index dei commercial arriva a +40, vendi a -40.
  S3 ESTREMI + TREND      come S1, ma in rialzo (prezzo sopra la media a 200 giorni) solo acquisti, in ribasso solo
                          vendite: "in un trend rialzista i segnali di vendita COT sono prematuri" (cap. 6).
  S4 SURGE + TREND        come S2 con lo stesso filtro: le regole dei 40 punti valgono "nel verso del trend" (cap. 7).
  S5 FONDI MEDIE MOBILI   (cap. 9) due medie mobili (in giorni di borsa) del COT Index dei grandi speculatori:
                          media veloce sopra la lenta = lungo, sotto = corto, sempre a mercato. Il libro sceglie la coppia
                          migliore mercato per mercato SULLO STESSO PERIODO che misura (tabella 9.1, senza costi): qui la
                          coppia si sceglie solo sul periodo di studio e si misura sulla verifica (walk-forward onesto).
  Un segnale S1-S4 nasce solo all'INGRESSO nella zona (la settimana dopo, se resta nella zona, non e' un segnale nuovo).
  Tenuta: 1, 2, 4 e 8 settimane (Wang, citato al cap. 8: rendimenti fino a 8 settimane). Principale = 4 settimane.

TEMPI (ora di Roma): il COT fotografa il martedi' e la CFTC lo pubblica il venerdi' alle 15:30 di New York
  (21:30 a Roma, 20:30 nelle settimane in cui l'ora legale USA ed europea non coincidono). Se c'e' una festivita'
  federale USA tra il lunedi' della settimana del dato e il venerdi', la pubblicazione slitta al lunedi' dopo.
  Ingresso = APERTURA della prima candela giornaliera DOPO la pubblicazione (forex: candela del lunedi', che apre
  all'01:00 di Roma, 02:00 con l'ora legale). Dove esiste solo la chiusura (future di cereali, soft, bestiame, tassi,
  ETF), ingresso = CHIUSURA della prima seduta dopo la pubblicazione (un giorno in piu' di ritardo: piu' prudente).
  Uscita: stessa misura (apertura o chiusura) della prima seduta a 7 x H giorni dall'ingresso.
  Settimane con pubblicazione fuori calendario (chiusure del governo USA 2013, 2018-19, 2025): ESCLUSE (date di uscita
  reali non note -> rischio di usare dati prima che fossero pubblici).
COSTI: stessi del sito (motore.py: forex 0,02%, peso messicano 0,15%, indici ed ETF 0,05%, energia 0,08%, gas 0,20%,
  materie prime e tassi 0,10%, crypto 0,20%) andata e ritorno, per operazione.
PERIODI: studio fino al 31/12/2014, verifica dal 2015 (mai usata per scegliere nulla).
CONFRONTO CON IL CASO: stessi ingressi e stesse durate con verso casuale (1.000 estrazioni): quante volte il caso fa
  meglio = "p" (sotto 0,05 = probabilmente non e' fortuna).
STRESS TEST: costi doppi, ingresso un giorno dopo, finestra 26 e 52 settimane, soglie 80/20, periodi di 5 anni,
  per classe di mercato, senza il mercato migliore.
LIMITI DICHIARATI: i future continui di Yahoo (=F) NON sono "back-adjusted": al cambio di contratto il prezzo salta e
  quel salto non e' un guadagno vero (il libro usa serie aggiustate). Per questo i risultati sono dati anche
  separatamente per i mercati con salti di roll e con lo stress "salti tagliati". I prezzi forex sono quelli di Yahoo.
USO: python studi/studio_cot_bible.py <cartella dati>   (COT.csv, yahoo/*.csv, DEXMXUS.csv, pat/*.json.gz)
"""
import csv
import gzip
import json
import math
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone

# --------------------------------------------------------------------------- mercati
# chiave: (codice CFTC, fonte prezzi, segno, classe, costo %, ha_apertura)
#   fonte "pat:XXX" = candele giornaliere OHLC salvate; "y:XXX" = chiusure Yahoo; "fred:XXX" = chiusure FRED
#   segno -1 = il future e' sulla valuta contro il dollaro ma la coppia quotata e' USD/valuta (es. USDJPY)
M = {
    "EUR": ("099741", "pat:EURUSD", 1, "valute", 0.02), "GBP": ("096742", "pat:GBPUSD", 1, "valute", 0.02),
    "JPY": ("097741", "pat:USDJPY", -1, "valute", 0.02), "CHF": ("092741", "pat:USDCHF", -1, "valute", 0.02),
    "CAD": ("090741", "pat:USDCAD", -1, "valute", 0.02), "AUD": ("232741", "pat:AUDUSD", 1, "valute", 0.02),
    "NZD": ("112741", "pat:NZDUSD", 1, "valute", 0.02), "MXN": ("095741", "fred:DEXMXUS", -1, "valute", 0.15),
    "DXY": ("098662", "y:UUP", 1, "valute", 0.05),
    "SP500": ("13874A", "y:_GSPC", 1, "indici", 0.05), "NASDAQ": ("209742", "y:QQQ", 1, "indici", 0.05),
    "DOW": ("124603", "y:DIA", 1, "indici", 0.05), "RUSSELL": ("239742", "y:IWM", 1, "indici", 0.05),
    "EAFE": ("244041", "y:EFA", 1, "indici", 0.05), "EM": ("244042", "y:EEM", 1, "indici", 0.05),
    "US2Y": ("042601", "y:ZT=F", 1, "tassi", 0.10), "US5Y": ("044601", "y:ZF=F", 1, "tassi", 0.10),
    "US10Y": ("043602", "y:ZN=F", 1, "tassi", 0.10), "USBOND": ("020601", "y:ZB=F", 1, "tassi", 0.10),
    "WTI": ("067651", "pat:WTI", 1, "energia", 0.08), "BRENT": ("06765T", "pat:BRENT", 1, "energia", 0.08),
    "NATGAS": ("023651", "pat:NATGAS", 1, "energia", 0.20), "HEATOIL": ("022651", "y:HO=F", 1, "energia", 0.08),
    "GASOLINE": ("111659", "y:RB=F", 1, "energia", 0.08),
    "GOLD": ("088691", "pat:XAUUSD", 1, "metalli", 0.10), "SILVER": ("084691", "pat:XAGUSD", 1, "metalli", 0.10),
    "COPPER": ("085692", "pat:COPPER", 1, "metalli", 0.10), "PLATINUM": ("076651", "pat:PLATINUM", 1, "metalli", 0.10),
    "PALLADIUM": ("075651", "y:PA=F", 1, "metalli", 0.10),
    "CORN": ("002602", "y:ZC=F", 1, "agricoli", 0.10), "SOY": ("005602", "y:ZS=F", 1, "agricoli", 0.10),
    "SOYOIL": ("007601", "y:ZL=F", 1, "agricoli", 0.10), "SOYMEAL": ("026603", "y:ZM=F", 1, "agricoli", 0.10),
    "WHEAT": ("001602", "y:ZW=F", 1, "agricoli", 0.10), "KCWHEAT": ("001612", "y:KE=F", 1, "agricoli", 0.10),
    "SUGAR": ("080732", "y:SB=F", 1, "agricoli", 0.10), "COFFEE": ("083731", "y:KC=F", 1, "agricoli", 0.10),
    "COCOA": ("073732", "y:CC=F", 1, "agricoli", 0.10), "COTTON": ("033661", "y:CT=F", 1, "agricoli", 0.10),
    "OJ": ("040701", "y:OJ=F", 1, "agricoli", 0.10),
    "CATTLE": ("057642", "y:LE=F", 1, "bestiame", 0.10), "FEEDER": ("061641", "y:GF=F", 1, "bestiame", 0.10),
    "HOGS": ("054642", "y:HE=F", 1, "bestiame", 0.10),
    "BTC": ("133741", "y:BTC-USD", 1, "crypto", 0.20),
}
FINE_STUDIO = date(2014, 12, 31)
ORIZZ = (1, 2, 4, 8)
PRINC = 4
# chiusure del governo USA: pubblicazioni COT arretrate con date d'uscita non note -> settimane escluse
ESCLUSE = [(date(2013, 9, 30), date(2013, 11, 22)), (date(2018, 12, 17), date(2019, 3, 8)),
           (date(2025, 9, 29), date(2026, 1, 30))]


# --------------------------------------------------------------------------- festivita' federali USA (calendario CFTC)
def _nesimo(anno, mese, giorno_sett, n):
    """n-esimo giorno della settimana del mese (lun=0); n=-1 = ultimo."""
    if n > 0:
        d = date(anno, mese, 1)
        d += timedelta(days=(giorno_sett - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    d = date(anno + (mese == 12), mese % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - giorno_sett) % 7)


def _osservato(d):
    """Festa che cade di sabato -> venerdi'; di domenica -> lunedi'."""
    return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d


def festivita(anno):
    f = {_osservato(date(anno, 1, 1)), _nesimo(anno, 1, 0, 3), _nesimo(anno, 2, 0, 3), _nesimo(anno, 5, 0, -1),
         _osservato(date(anno, 7, 4)), _nesimo(anno, 9, 0, 1), _nesimo(anno, 10, 0, 2), _osservato(date(anno, 11, 11)),
         _nesimo(anno, 11, 3, 4), _osservato(date(anno, 12, 25))}
    if anno >= 2021:
        f.add(_osservato(date(anno, 6, 19)))
    return f


FEST = set()
for _a in range(1985, 2028):
    FEST |= festivita(_a)


def pubblicazione(rap):
    """Data (New York) in cui il COT del martedi' `rap` e' uscito: venerdi', o lunedi' dopo se c'e' una festa federale
    tra il lunedi' della settimana del dato e il venerdi'. None nelle settimane escluse."""
    if any(a <= rap <= b for a, b in ESCLUSE):
        return None
    ven = rap + timedelta(days=(4 - rap.weekday()) % 7)
    lun = rap - timedelta(days=rap.weekday())
    if any(lun + timedelta(days=k) in FEST for k in range(5)):
        return ven + timedelta(days=3)
    return ven


# --------------------------------------------------------------------------- dati
def leggi_cot(f):
    """{codice: [(data rapporto, netto commercial, netto grandi speculatori, open interest)]} in ordine di data."""
    per = {}
    for r in csv.DictReader(open(f)):
        try:
            per.setdefault(r["cftc_contract_market_code"].strip(), {})[date.fromisoformat(r["report_date_as_yyyy_mm_dd"][:10])] = (
                float(r["comm_positions_long_all"]) - float(r["comm_positions_short_all"]),
                float(r["noncomm_positions_long_all"]) - float(r["noncomm_positions_short_all"]),
                float(r["open_interest_all"]))
        except (KeyError, ValueError):
            continue
    return {c: [(d,) + v[d] for d in sorted(v)] for c, v in per.items()}


def leggi_prezzi(cart, fonte):
    """[(data, apertura o None, chiusura)] in ordine. Le candele salvate hanno l'ora 00:00 UTC del giorno."""
    tipo, nome = fonte.split(":", 1)
    out = []
    if tipo == "pat":
        x = json.load(gzip.open(os.path.join(cart, "pat", nome + ".json.gz"), "rt"))
        for ts, o, h, l, c in x["d"]:
            if o and c:
                out.append((datetime.fromtimestamp(ts, tz=timezone.utc).date(), float(o), float(c)))
    else:
        f = os.path.join(cart, "yahoo", nome + ".csv") if tipo == "y" else os.path.join(cart, nome + ".csv")
        for r in csv.DictReader(open(f)):
            try:
                v = float(r.get("valore") or r.get(nome) or "")
            except ValueError:
                continue
            if v > 0:
                out.append((date.fromisoformat(r["data"]), None, v))
    out.sort()
    # una sola riga per giorno
    pul = []
    for x in out:
        if pul and pul[-1][0] == x[0]:
            pul[-1] = x
        else:
            pul.append(x)
    return pul


def taglia_salti(px, k=5.0):
    """Stress "salti tagliati": un giorno con movimento oltre k volte la mediana dei movimenti degli ultimi 60 giorni
    (tipico salto di roll dei future Yahoo non aggiustati) viene annullato spostando tutta la serie successiva."""
    out, fatt, mv = [], 1.0, []
    for i, (d, o, c) in enumerate(px):
        if i:
            r = c / px[i - 1][2] - 1
            med = sorted(mv[-60:])[len(mv[-60:]) // 2] if len(mv) >= 20 else None
            if med and abs(r) > k * med:
                fatt *= px[i - 1][2] / c                # elimina il salto: la chiusura resta quella di ieri
            mv.append(abs(r))
        out.append((d, o * fatt if o else None, c * fatt))
    return out


# --------------------------------------------------------------------------- indicatori del libro
def cot_index(v, t, n):
    w = v[max(0, t - n + 1): t + 1]
    lo, hi = min(w), max(w)
    return 50.0 if hi == lo else 100 * (v[t] - lo) / (hi - lo)


def sma(v, n):
    out, s = [], 0.0
    for i, x in enumerate(v):
        s += x
        if i >= n:
            s -= v[i - n]
        out.append(s / n if i >= n - 1 else None)
    return out


def sma_vuoti(v, n):
    """Media mobile che ignora i giorni iniziali senza dato (None): None finche' la finestra non e' piena di dati."""
    out, w = [], []
    for x in v:
        if x is None:
            w = []
            out.append(None)
            continue
        w.append(x)
        if len(w) > n:
            w.pop(0)
        out.append(sum(w) / n if len(w) == n else None)
    return out


# --------------------------------------------------------------------------- simulazione
class Mercato:
    def __init__(self, k, cot, px, ritardo=0):
        self.k = k
        self.cod, _, self.segno, self.classe, self.costo = M[k]
        self.cot = cot
        self.px = px
        self.date = [x[0] for x in px]
        self.ha_open = px[0][1] is not None
        self.ma200 = sma([x[2] for x in px], 200)
        self.ritardo = ritardo

    def giorno_dopo(self, d):
        """Indice della prima seduta con data > d (ingresso dopo la pubblicazione) + eventuale ritardo di stress."""
        import bisect
        i = bisect.bisect_right(self.date, d)
        i += self.ritardo
        return i if i < len(self.date) else None

    def prezzo(self, i):
        return self.px[i][1] if self.ha_open else self.px[i][2]

    def trend(self, d):
        """+1 sopra la media a 200 giorni, -1 sotto, usando l'ultima chiusura NOTA prima della pubblicazione."""
        import bisect
        i = bisect.bisect_right(self.date, d) - 1
        if i < 0 or self.ma200[i] is None:
            return 0
        return 1 if self.px[i][2] > self.ma200[i] else -1

    def operazione(self, i0, verso, settimane):
        """Rendimento % netto di un'operazione aperta alla seduta i0 e chiusa alla prima seduta >= 7*settimane giorni."""
        import bisect
        d1 = self.date[i0] + timedelta(days=7 * settimane)
        i1 = bisect.bisect_left(self.date, d1)
        if i1 >= len(self.date) or (self.date[i1] - d1).days > 7:
            return None
        r = (self.prezzo(i1) / self.prezzo(i0) - 1) * 100
        return verso * self.segno * r - self.costo


def segnali(m, n=156, alto=90, basso=5, surge=40, mov=6):
    """Lista di eventi (data pubblicazione, strategia, verso +1/-1) per S1-S4 con le regole del libro."""
    rapp = [x[0] for x in m.cot]
    comm = [x[1] for x in m.cot]
    out = []
    ci = [cot_index(comm, t, n) if t >= n - 1 else None for t in range(len(comm))]
    zona_prima, mi_prima = 0, 0
    for t in range(len(comm)):
        if ci[t] is None:
            continue
        zona = 1 if ci[t] >= alto else -1 if ci[t] <= basso else 0
        mi = None
        if t >= mov and ci[t - mov] is not None:
            mi = ci[t] - ci[t - mov]
        mzona = 0 if mi is None else (1 if mi >= surge else -1 if mi <= -surge else 0)
        pub = pubblicazione(rapp[t])
        if pub is not None:
            tr = m.trend(pub)
            if zona and zona != zona_prima:
                out.append((pub, "S1", zona))
                if tr == zona:
                    out.append((pub, "S3", zona))
            if mzona and mzona != mi_prima:
                out.append((pub, "S2", mzona))
                if tr == mzona:
                    out.append((pub, "S4", mzona))
        zona_prima, mi_prima = zona, mzona
    return out


def operazioni(m, ev, settimane=ORIZZ):
    """[(strategia, mercato, data ingresso, verso, {settimane: rendimento})]"""
    out = []
    for pub, s, v in ev:
        i0 = m.giorno_dopo(pub)
        if i0 is None:
            continue
        r = {h: m.operazione(i0, v, h) for h in settimane}
        out.append((s, m.k, m.date[i0], v, r, i0))
    return out


# ---- S5: medie mobili sul COT Index dei grandi speculatori, giornaliero "a scalini" come nel libro (cap. 9)
def fondi_giornaliero(m, n=156):
    """Per ogni seduta: COT Index dei grandi speculatori NOTO quel giorno (l'ultimo pubblicato prima della seduta)."""
    rapp = [x[0] for x in m.cot]
    spec = [x[2] for x in m.cot]
    idx = [(pubblicazione(rapp[t]), cot_index(spec, t, n)) for t in range(n - 1, len(spec))]
    idx = [x for x in idx if x[0] is not None]
    out, j, cur = [], 0, None
    for d in m.date:
        while j < len(idx) and idx[j][0] < d:          # pubblicato il giorno prima (o prima): usabile oggi
            cur = idx[j][1]
            j += 1
        out.append(cur)
    return out


def s5_curva(m, ci, f, s, dal, al, costo_x=1.0):
    """Sempre a mercato: lungo se media veloce > lenta. Rendimenti giornalieri % (apertura->apertura o chiusura->chiusura)
    tra le date dal-al, con costo a ogni cambio di verso. Il cambio si esegue alla seduta DOPO quella del segnale."""
    mf, ms = sma_vuoti(ci, f), sma_vuoti(ci, s)
    rend, pos = [], 0
    scambi = 0
    for i in range(1, len(m.date)):
        p0, p1 = m.prezzo(i - 1), m.prezzo(i)
        if dal <= m.date[i] <= al and pos:
            rend.append(pos * m.segno * (p1 / p0 - 1) * 100)
        elif dal <= m.date[i] <= al:
            rend.append(0.0)
        a, b = mf[i - 1], ms[i - 1]                    # segnale visto alla seduta i-1, eseguito alla i
        nuovo = pos
        if a is not None and b is not None:
            nuovo = 1 if a > b else -1 if a < b else pos
        if nuovo != pos:
            if dal <= m.date[i] <= al and rend:
                rend[-1] -= m.costo * costo_x            # un costo (andata+ritorno) a ogni cambio: prudente
            scambi += 1
            pos = nuovo
    return rend, scambi


# --------------------------------------------------------------------------- statistiche
def stat(rs):
    rs = [r for r in rs if r is not None]
    n = len(rs)
    if n < 5:
        return {"n": n}
    m = sum(rs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in rs) / (n - 1)) if n > 1 else 0
    return {"n": n, "media": m, "vinte": 100 * sum(r > 0 for r in rs) / n, "t": m / sd * math.sqrt(n) if sd else 0}


def caso(ops, h, prove=1000, seme=7):
    """p = quota di estrazioni con verso casuale che fanno una media >= di quella vera (stessi ingressi e durate)."""
    rnd = random.Random(seme)
    base = [(o[4][h] + 0) for o in ops if o[4].get(h) is not None]
    if len(base) < 5:
        return None
    vero = sum(base) / len(base)
    # rendimento lordo nel verso del mercato (senza costo), poi verso casuale e costo
    lordi = []
    for o in ops:
        r = o[4].get(h)
        if r is None:
            continue
        c = M[o[1]][4]
        lordi.append(((r + c) * o[3], c))             # (rendimento del mercato nel verso +1, costo)
    meglio = 0
    for _ in range(prove):
        tot = sum((g if rnd.random() < 0.5 else -g) - c for g, c in lordi)
        if tot / len(lordi) >= vero:
            meglio += 1
    return meglio / prove


def riga(nome, ops, h=PRINC):
    s = stat([o[4].get(h) for o in ops])
    if s["n"] < 5:
        return f"  {nome:<34} n={s['n']:>4}  (troppo poche)"
    p = caso(ops, h)
    return (f"  {nome:<34} n={s['n']:>4}  media {s['media']:+6.2f}%  vinte {s['vinte']:4.0f}%  t {s['t']:+5.2f}"
            f"  p(caso) {p:.3f}")


# --------------------------------------------------------------------------- programma
def carica(cart, ritardo=0, salti=False):
    cot = leggi_cot(os.path.join(cart, "COT.csv"))
    mer = {}
    for k, (cod, fonte, *_r) in M.items():
        if cod not in cot:
            continue
        try:
            px = leggi_prezzi(cart, fonte)
        except FileNotFoundError:
            continue
        if len(px) < 400:
            continue
        if salti and "=F" in fonte:                   # solo i future continui Yahoo non aggiustati
            px = taglia_salti(px)
        mer[k] = Mercato(k, cot[cod], px, ritardo)
    return mer


def tutte(mer, **kw):
    ops = []
    for m in mer.values():
        ops += operazioni(m, segnali(m, **kw))
    return ops


def per_periodo(ops, s, studio=True):
    return [o for o in ops if o[0] == s and ((o[2] <= FINE_STUDIO) == studio)]


def main():
    cart = sys.argv[1]
    mer = carica(cart)
    print(f"Mercati con COT e prezzi: {len(mer)} -> {', '.join(sorted(mer))}")
    print("Senza apertura (ingresso alla chiusura del giorno dopo):",
          ", ".join(k for k, m in sorted(mer.items()) if not m.ha_open))
    ops = tutte(mer)
    nomi = {"S1": "S1 estremi commercial 90/5", "S2": "S2 surge commercial +-40",
            "S3": "S3 estremi + trend", "S4": "S4 surge + trend"}

    print("\n=== RISULTATI PRINCIPALI (tenuta 4 settimane, costi inclusi) ===")
    for s in nomi:
        print(nomi[s])
        print(riga("studio (fino al 2014)", per_periodo(ops, s, True)))
        print(riga("VERIFICA (dal 2015)", per_periodo(ops, s, False)))

    print("\n=== TENUTE DIVERSE (verifica dal 2015) ===")
    for s in nomi:
        for h in ORIZZ:
            print(riga(f"{s} tenuta {h} sett.", per_periodo(ops, s, False), h))

    print("\n=== PER CLASSE (tutto il periodo, tenuta 4 settimane) ===")
    for s in ("S3", "S4"):
        for c in sorted({v[3] for v in M.values()}):
            print(riga(f"{s} {c}", [o for o in ops if o[0] == s and M[o[1]][3] == c]))

    print("\n=== STRESS TEST (verifica dal 2015, 4 settimane) ===")
    var = {"base": (mer, {}), "finestra 26 sett.": (mer, {"n": 26}), "finestra 52 sett.": (mer, {"n": 52}),
           "soglie 80/20": (mer, {"alto": 80, "basso": 20})}
    for nome, (mm, kw) in var.items():
        o2 = tutte(mm, **kw)
        for s in nomi:
            print(riga(f"{nome:<18} {s}", per_periodo(o2, s, False)))
    m_rit = carica(cart, ritardo=1)
    o2 = tutte(m_rit)
    for s in nomi:
        print(riga(f"{'ingresso +1 giorno':<18} {s}", per_periodo(o2, s, False)))
    m_sal = carica(cart, salti=True)
    o2 = tutte(m_sal)
    for s in nomi:
        print(riga(f"{'salti roll tagliati':<18} {s}", per_periodo(o2, s, False)))
    # costi doppi: si toglie un altro costo a ogni operazione
    for s in nomi:
        o3 = [(o[0], o[1], o[2], o[3], {h: (r - M[o[1]][4] if r is not None else None) for h, r in o[4].items()}, o[5])
              for o in per_periodo(ops, s, False)]
        print(riga(f"{'costi doppi':<18} {s}", o3))
    for s in nomi:
        tutti = [o for o in ops if o[0] == s]
        st = {k: stat([o[4].get(PRINC) for o in tutti if o[1] == k]) for k in mer}
        migliore = max((k for k in st if st[k].get("n", 0) >= 5), key=lambda k: st[k]["media"] * st[k]["n"], default=None)
        print(riga(f"senza {migliore:<12} {s}", [o for o in tutti if o[1] != migliore and o[2] > FINE_STUDIO]))

    print("\n=== PERIODI DI 5 ANNI (tutto, 4 settimane) ===")
    for s in nomi:
        for a in (2001, 2006, 2011, 2016, 2021):
            print(riga(f"{s} {a}-{a + 4}", [o for o in ops if o[0] == s and a <= o[2].year <= a + 4]))

    print("\n=== S5 MEDIE MOBILI SUL COT INDEX DEI FONDI (cap. 9) ===")
    griglia = [(f, s) for f in (5, 7, 10, 14, 21) for s in (10, 14, 16, 22, 30, 45) if s > f]
    tot_v, tot_vb, tot_fisso, righe = [], [], [], []
    for k, m in sorted(mer.items()):
        ci = fondi_giornaliero(m)
        if sum(x is not None for x in ci) < 500:
            continue
        studio_da = m.date[0]
        migl, best = None, -1e9
        for f, s in griglia:
            r, _ = s5_curva(m, ci, f, s, studio_da, FINE_STUDIO)
            g = sum(r)
            if g > best:
                best, migl = g, (f, s)
        r_v, sc = s5_curva(m, ci, migl[0], migl[1], FINE_STUDIO + timedelta(days=1), date(2100, 1, 1))
        r_f, _ = s5_curva(m, ci, 10, 14, FINE_STUDIO + timedelta(days=1), date(2100, 1, 1))
        # riferimento: sempre lungo nello stesso periodo (il "drift" del mercato)
        bh = [m.segno * (m.prezzo(i) / m.prezzo(i - 1) - 1) * 100 for i in range(1, len(m.date))
              if m.date[i] > FINE_STUDIO]
        if not r_v:
            continue
        anni = len(r_v) / 252
        righe.append((k, migl, sum(r_v) / anni, sum(r_f) / anni, sum(bh) / anni, sc / anni))
        tot_v.append(sum(r_v) / anni)
        tot_fisso.append(sum(r_f) / anni)
        tot_vb.append(sum(bh) / anni)
    print("  mercato    coppia scelta  verifica %/anno  coppia fissa 10/14  sempre lungo  scambi/anno")
    for k, mg, a, b, c, sc in righe:
        print(f"  {k:<10} {mg[0]:>3}/{mg[1]:<3}        {a:+7.2f}          {b:+7.2f}          {c:+7.2f}      {sc:5.1f}")
    if tot_v:
        n = len(tot_v)
        sd = math.sqrt(sum((x - sum(tot_v) / n) ** 2 for x in tot_v) / (n - 1))
        print(f"  MEDIA {n} mercati: scelta sullo studio {sum(tot_v) / n:+.2f}%/anno (t tra mercati "
              f"{sum(tot_v) / n / sd * math.sqrt(n):+.2f}), fissa 10/14 {sum(tot_fisso) / n:+.2f}%, "
              f"sempre lungo {sum(tot_vb) / n:+.2f}%; mercati positivi {sum(x > 0 for x in tot_v)}/{n}")


if __name__ == "__main__":
    main()
