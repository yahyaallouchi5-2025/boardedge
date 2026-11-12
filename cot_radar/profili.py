"""PROFILO DELLE AZIENDE (v6.52): la scheda "chi e'" di ogni titolo dell'Azionario.

Cosa contiene (solo il necessario, in italiano dove possibile):
  - descrizione breve (cosa fa e cosa produce): riassunto di Wikipedia in italiano (in inglese se manca);
  - anno di fondazione, sede e paese, amministratore delegato (CEO), numero di dipendenti (ultimo dato);
  - borse dove e' quotata;
  - se negli ultimi 10 anni e' stata acquistata, da chi e in che anno.
Fonti libere e gratuite: Wikidata (dati strutturati, interrogazione SPARQL) e Wikipedia (riassunto della voce).
Il settore e il listino arrivano gia' dai dati di BoardEdge (azioni.py).

Come lavora (dentro il workflow Azioni, mai bloccante):
  - il ticker di Yahoo viene tradotto nel ticker di borsa di Wikidata (es. 0700.HK -> 700 su Hong Kong) e la borsa
    giusta e' riconosciuta dal suffisso, cosi' due aziende con lo stesso ticker su borse diverse non si confondono;
  - ogni profilo si riscarica al massimo una volta ogni 30 giorni, al massimo 300 titoli per giro (i dati cambiano
    di rado: CEO, dipendenti, acquisizioni);
  - User-Agent onesto con il nome del servizio e il contatto (Secret SEC_CONTATTO), come chiede Wikimedia.
Limite noto: "in vendita" non e' un dato pubblico affidabile, quindi non viene mostrato.
File scritto: pubblico/profili/<TICKER>.json (letto dalla scheda del titolo, solo quando la si apre)."""
import json
import re
import logging
import os
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta

from . import azioni as A

log = logging.getLogger(__name__)
SPARQL = "https://query.wikidata.org/sparql"
RIASSUNTO = "https://{lingua}.wikipedia.org/api/rest_v1/page/summary/{titolo}"
GIORNI_VALIDITA = 30            # un profilo si riscarica dopo 30 giorni
VERSIONE = 2                    # v6.73: profili con ISIN e abbinamento migliorato (i vecchi si rifanno una volta)
RIPROVA_VUOTI = 7               # titolo non trovato su Wikidata: si riprova dopo 7 giorni
RICERCA = 3                     # v7.13: anche la descrizione cercata su Wikipedia quando l'elemento non ha la voce; v7.7: ricerca anche su Wikipedia; i titoli senza descrizione si riprovano subito
RIPROVA_DESC = 3                # trovato ma riassunto Wikipedia non scaricato: si riprova dopo 3 giorni
MAX_PER_GIRO = 2000             # titoli aggiornati al massimo in un giro (v6.54: prima 300, troppo lento)
TEMPO_MAX = 600                 # secondi massimi per giro: oltre si riprende al giro dopo
LOTTO = 60                      # ticker per interrogazione SPARQL
PAUSA = 0.2                     # secondi tra le richieste a Wikipedia

# suffisso del ticker Yahoo -> parole che devono comparire nel nome (inglese) della borsa su Wikidata
BORSE = {"": ("nasdaq", "new york stock exchange", "nyse"), "MI": ("borsa italiana", "milan", "italian"),
         "DE": ("frankfurt", "xetra"), "PA": ("paris",), "AS": ("amsterdam",), "MC": ("madrid", "spanish"),
         "BR": ("brussels",), "HE": ("helsinki",), "T": ("tokyo",), "HK": ("hong kong",),
         "SS": ("shanghai",), "SZ": ("shenzhen",), "NS": ("national stock exchange of india", "bombay"),
         "L": ("london",), "TO": ("toronto",), "AX": ("australian securities exchange", "australian stock exchange")}


def _ua():
    c = os.environ.get("SEC_CONTATTO", "").strip()
    return "BoardEdge/1.0 (https://github.com/" + (os.environ.get("GITHUB_REPOSITORY") or "yahyaallouchi5-2025/cot-radar") + (f"; {c}" if "@" in c else "") + ")"


def _get(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": _ua(), "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _sparql(q):
    return _get(SPARQL + "?format=json&query=" + urllib.parse.quote(q))["results"]["bindings"]


def ticker_borsa(t):
    """Ticker Yahoo -> (ticker come su Wikidata, suffisso). Hong Kong senza zeri iniziali (0700.HK -> 700).
    v6.73: il trattino diventa punto SOLO per gli USA (BRK-B -> BRK.B); in India il trattino fa parte del
    ticker (BAJAJ-AUTO.NS) e prima veniva rovinato."""
    base, _, suf = t.partition(".")
    if suf == "HK":
        base = base.lstrip("0") or "0"
    # v7.23 classi di azioni a Londra e Toronto: Yahoo BT-A.L, RCI-B.TO -> su Wikidata BT.A, RCI.B
    return (base.replace("-", ".") if suf in ("", "L", "TO") else base), suf


def varianti(t):
    """v6.73: ticker alternativi con cui Wikidata registra lo stesso titolo (zeri iniziali a Hong Kong,
    ticker USA con il trattino originale)."""
    tk, suf = ticker_borsa(t)
    base = t.partition(".")[0]
    altri = {tk}
    if suf == "HK":
        altri |= {base, tk.zfill(4)}
    elif suf in ("", "L", "TO"):
        altri.add(base)
    return sorted(altri)


def _v(b, k):
    return (b.get(k) or {}).get("value")


def _qid(url):
    return url.rsplit("/", 1)[-1] if url else None


def trova_item(lotto):
    """{ticker Yahoo: QID} per un lotto di ticker, scegliendo la borsa coerente con il suffisso."""
    per_tk = {}
    for t in lotto:
        suf = ticker_borsa(t)[1]
        for tk in varianti(t):
            per_tk.setdefault(tk, []).append((t, suf))
    valori = " ".join(json.dumps(k) for k in per_tk)
    righe = _sparql(f"""SELECT ?tk ?item ?exL WHERE {{ VALUES ?tk {{ {valori} }}
      ?item p:P414 ?st . ?st ps:P414 ?ex; pq:P249 ?tk . ?ex rdfs:label ?exL FILTER(lang(?exL)="en") }}""")
    candidati = {}
    for b in righe:
        candidati.setdefault(_v(b, "tk"), []).append((_qid(_v(b, "item")), (_v(b, "exL") or "").lower()))
    out = {}
    for tk, lista in per_tk.items():
        for t, suf in lista:
            if t in out:
                continue                                  # gia' trovato con un'altra variante del ticker
            c = candidati.get(tk, [])
            buoni = [q for q, ex in c if any(p in ex for p in BORSE.get(suf, ()))]
            scelta = buoni or ([c[0][0]] if len({q for q, _ in c}) == 1 and c else [])
            if scelta:
                out[t] = scelta[0]
    return out


# v6.73 RICERCA PER NOME (quando il ticker non e' su Wikidata): si accetta un risultato SOLO se e' un'azienda
# quotata (borsa P414 o ISIN P946) e, se Wikidata indica il paese, e' lo stesso della borsa del titolo.
PAESE = {"": {"Q30"}, "MI": {"Q38"}, "DE": {"Q183"}, "PA": {"Q142"}, "AS": {"Q55"}, "MC": {"Q29"}, "BR": {"Q31"},
         "HE": {"Q33"}, "T": {"Q17"}, "HK": {"Q148", "Q8646"}, "SS": {"Q148"}, "SZ": {"Q148"}, "NS": {"Q668"},
         "L": {"Q145"}, "TO": {"Q16"}, "AX": {"Q408"}}
CERCA = "https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&type=item&limit=5&language=en&search="
FORME = r"[,.]?\s+(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|s\.?p\.?a|ag|sa|se|nv|n\.v|holdings? co|group co)\.?$"


def pulisci_nome(n):
    """'Kikkoman Corporation' -> 'Kikkoman', 'Bajaj Auto Ltd.' -> 'Bajaj Auto' (forme societarie in coda)."""
    import re
    n = (n or "").strip()
    for _ in range(3):
        n2 = re.sub(FORME, "", n, flags=re.I).strip(" ,.")
        if n2 == n:
            break
        n = n2
    return n


# v7.7 RICERCA SU WIKIPEDIA (inglese): molte aziende asiatiche, indiane e italiane hanno la voce su Wikipedia ma
# la ricerca per nome di Wikidata non le trova (es. "JD.com", "Campari", "PetroChina"). Dai primi risultati di
# Wikipedia si prende l'elemento Wikidata collegato alla voce, che deve superare lo STESSO controllo di per_nome
# (azienda quotata, paese della borsa): nessun abbinamento a caso.
CERCA_WP = "https://en.wikipedia.org/w/api.php?action=query&format=json&list=search&srlimit=3&srsearch="
PROPS_WP = "https://en.wikipedia.org/w/api.php?action=query&format=json&prop=pageprops&ppprop=wikibase_item&titles="


def candidati_wikipedia(nome):
    """QID Wikidata delle prime voci di Wikipedia trovate per il nome dell'azienda (in ordine di pertinenza)."""
    r = _get(CERCA_WP + urllib.parse.quote(nome), timeout=20) or {}
    titoli = [x["title"] for x in (r.get("query") or {}).get("search", [])]
    if not titoli:
        return []
    pp = (_get(PROPS_WP + urllib.parse.quote("|".join(titoli)), timeout=20) or {}).get("query") or {}
    per_titolo = {x.get("title"): (x.get("pageprops") or {}).get("wikibase_item") for x in (pp.get("pages") or {}).values()}
    norm = {x.get("to"): x.get("from") for x in pp.get("normalized") or []}
    return [q for q in (per_titolo.get(t) or per_titolo.get(norm.get(t)) for t in titoli) if q]


def _norm(x):
    """minuscolo, senza accenti (Mondelēz -> mondelez, Tōkyū -> tokyu)."""
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", str(x or "")) if not unicodedata.combining(c)).lower()


def pertinente(testo, nome, t):
    """v7.22 La descrizione parla davvero di QUESTA azienda? Deve citare una parola significativa del nome, il nome
    intero o il ticker. Evita le voci sbagliate trovate per nome (es. Baycurrent -> Toyota, Mediobanca -> Mindbody,
    l'indice SSE 50 al posto dell'azienda). Senza nome non si giudica (True)."""
    if not testo or not nome:
        return bool(testo)
    from .notizie_az import VUOTE
    txt = _norm(testo)
    parole = set(re.findall(r"[a-z0-9][a-z0-9&'-]+", txt))
    sign = [w for w in re.findall(r"[a-z][a-z&'-]+", _norm(nome)) if len(w) >= 3 and w not in VUOTE]
    base = t.split(".")[0].lower()
    compatto = re.sub(r"[^a-z0-9]", "", _norm(nome))
    return (any(w in parole for w in sign) or (len(compatto) >= 2 and compatto in re.sub(r"[^a-z0-9]", "", txt))
            or (len(base) >= 2 and base.isalpha() and base in parole))


def desc_da_wikipedia(t, nome, qid=None):
    """v7.13 Descrizione quando l'elemento Wikidata trovato non ha la voce italiana/inglese collegata (es. la
    "holding" invece dell'azienda): si cerca il nome su Wikipedia inglese e si prende la prima voce il cui elemento
    Wikidata e' lo stesso trovato prima oppure supera il controllo di _accetta (azienda quotata, paese giusto)."""
    q = pulisci_nome(nome)
    if len(q) < 3:
        return None
    r = _get(CERCA_WP + urllib.parse.quote(q), timeout=20) or {}
    titoli = [x["title"] for x in (r.get("query") or {}).get("search", [])]
    if not titoli:
        return None
    pp = (_get(PROPS_WP + urllib.parse.quote("|".join(titoli)), timeout=20) or {}).get("query") or {}
    per_titolo = {x.get("title"): (x.get("pageprops") or {}).get("wikibase_item") for x in (pp.get("pages") or {}).values()}
    for ti in titoli:
        c = per_titolo.get(ti)
        if c and (c == qid or _accetta(t, [c])):
            return riassunto("https://en.wikipedia.org/wiki/" + urllib.parse.quote(ti.replace(" ", "_")))
    return None


def _accetta(t, cand):
    """Il primo candidato che e' un'azienda quotata (borsa P414 o ISIN P946) del paese della borsa, oppure None."""
    if not cand:
        return None
    righe = _sparql(f"""SELECT ?item (SAMPLE(?pa) AS ?paese) (COUNT(?b) AS ?nb) (COUNT(?i) AS ?ni) WHERE {{
      VALUES ?item {{ {" ".join("wd:" + c for c in cand)} }}
      OPTIONAL{{?item wdt:P414 ?b}} OPTIONAL{{?item wdt:P946 ?i}} OPTIONAL{{?item wdt:P17 ?pa}} }} GROUP BY ?item""")
    info = {_qid(_v(b, "item")): (int(_v(b, "nb") or 0) + int(_v(b, "ni") or 0), _qid(_v(b, "paese"))) for b in righe}
    paesi = PAESE.get(ticker_borsa(t)[1], set())
    for c in cand:                                        # nell'ordine di pertinenza della ricerca
        quotata, pa = info.get(c, (0, None))
        if quotata and (pa is None or not paesi or pa in paesi):
            return c
    return None


def per_nome(titoli):
    """{ticker: QID} cercando il nome dell'azienda su Wikidata e poi (v7.7) su Wikipedia; titoli = [(ticker, nome)]."""
    out = {}
    for t, nome in titoli:
        q = pulisci_nome(nome)
        if len(q) < 3:
            continue
        for fonte in ("wikidata", "wikipedia"):
            try:
                cand = ([x["id"] for x in _get(CERCA + urllib.parse.quote(q), timeout=20).get("search", [])]
                        if fonte == "wikidata" else candidati_wikipedia(q))
                c = _accetta(t, cand)
            except Exception as e:
                log.warning("profili: ricerca per nome (%s) non riuscita per %s (%s)", fonte, t, type(e).__name__)
                c = None
            if c:
                out[t] = c
                break
            time.sleep(PAUSA)
    return out


# ISIN: prefisso del paese atteso per ogni borsa (Hong Kong: molte societa' sono registrate alle Cayman o Bermuda)
PREFISSO_ISIN = {"": ("US",), "MI": ("IT",), "DE": ("DE",), "PA": ("FR",), "AS": ("NL",), "MC": ("ES",), "BR": ("BE",),
                 "HE": ("FI",), "T": ("JP",), "HK": ("HK", "KY", "BM", "CN"), "SS": ("CN",), "SZ": ("CN",), "NS": ("IN",),
                 "L": ("GB", "JE", "GG", "IE", "IM"), "TO": ("CA",), "AX": ("AU", "NZ")}


def scegli_isin(lista, t):
    """L'ISIN del titolo: quello con il prefisso del paese della borsa, altrimenti il primo (in ordine)."""
    lista = sorted({x for x in lista if x and len(x) == 12})
    pref = PREFISSO_ISIN.get(ticker_borsa(t)[1], ())
    for p in pref:
        for x in lista:
            if x.startswith(p):
                return x
    return lista[0] if lista else None


def fatti(qids):
    """Dati strutturati per una lista di QID: fondazione, CEO, sede, paese, sito, voci Wikipedia, borse,
    dipendenti (ultimo dato), acquisizioni fatte e subite negli ultimi 10 anni."""
    val = " ".join("wd:" + q for q in qids)
    out = {q: {"ceo": [], "borse": [], "acq": [], "da": [], "dip": [], "isin": []} for q in qids}
    for b in _sparql(f"""SELECT ?item (MIN(?inc) AS ?fond) (SAMPLE(?hqL) AS ?sede) (SAMPLE(?paL) AS ?paese)
      (SAMPLE(?itA) AS ?it) (SAMPLE(?enA) AS ?en) (SAMPLE(?sito) AS ?web) WHERE {{ VALUES ?item {{ {val} }}
      OPTIONAL{{?item wdt:P571 ?inc}}
      OPTIONAL{{?item wdt:P159 ?h. ?h rdfs:label ?hqL FILTER(lang(?hqL)="it")}}
      OPTIONAL{{?item wdt:P17 ?p. ?p rdfs:label ?paL FILTER(lang(?paL)="it")}}
      OPTIONAL{{?itA schema:about ?item; schema:isPartOf <https://it.wikipedia.org/>}}
      OPTIONAL{{?enA schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>}}
      OPTIONAL{{?item wdt:P856 ?sito}} }} GROUP BY ?item"""):
        q = _qid(_v(b, "item"))
        out[q].update({"fond": (_v(b, "fond") or "")[:4] or None, "sede": _v(b, "sede"), "paese": _v(b, "paese"),
                       "it": _v(b, "it"), "en": _v(b, "en"), "web": _v(b, "web")})
    for b in _sparql(f"""SELECT ?item ?l WHERE {{ VALUES ?item {{ {val} }} ?item wdt:P169 ?c.
      ?c rdfs:label ?l FILTER(lang(?l)="en") }}"""):
        out[_qid(_v(b, "item"))]["ceo"].append(_v(b, "l"))
    for b in _sparql(f"""SELECT ?item ?l WHERE {{ VALUES ?item {{ {val} }} ?item wdt:P414 ?e.
      ?e rdfs:label ?l FILTER(lang(?l)="it") }}"""):
        out[_qid(_v(b, "item"))]["borse"].append(_v(b, "l"))
    for b in _sparql(f"""SELECT ?item ?i WHERE {{ VALUES ?item {{ {val} }} ?item wdt:P946 ?i }}"""):   # v6.73 ISIN
        out[_qid(_v(b, "item"))]["isin"].append(_v(b, "i"))
    for b in _sparql(f"""SELECT ?item ?n ?d WHERE {{ VALUES ?item {{ {val} }} ?item p:P1128 ?s. ?s ps:P1128 ?n.
      OPTIONAL{{?s pq:P585 ?d}} }}"""):
        out[_qid(_v(b, "item"))]["dip"].append((_v(b, "d") or "", _v(b, "n")))
    anno_min = date.today().year - 10
    # "acquisita da" negli ultimi 10 anni (proprietario con data d'inizio). Le acquisizioni FATTE dall'azienda
    # su Wikidata sono troppo incomplete (e l'interrogazione inversa e' lenta): non vengono mostrate.
    try:
        for b in _sparql(f"""SELECT ?item ?xL ?inizio WHERE {{ VALUES ?item {{ {val} }}
          ?item p:P127 ?s. ?s ps:P127 ?x; pq:P580 ?inizio. FILTER(YEAR(?inizio) >= {date.today().year - 10})
          ?x rdfs:label ?xL FILTER(lang(?xL)="en") }}"""):
            voce = {"nome": _v(b, "xL"), "anno": int((_v(b, "inizio") or "0")[:4])}
            lista = out[_qid(_v(b, "item"))]["da"]
            if voce["nome"] not in [x["nome"] for x in lista]:
                lista.append(voce)
    except Exception as e:
        log.warning("profili: proprietari non scaricati (%s)", type(e).__name__)
    return out


def riassunto(url_voce):
    """Prime 2 frasi del riassunto di Wikipedia (max ~360 caratteri). None se la voce non c'e'."""
    if not url_voce:
        return None
    lingua = url_voce.split("//", 1)[1].split(".", 1)[0]
    titolo = url_voce.rsplit("/wiki/", 1)[-1]
    try:
        testo = (_get(RIASSUNTO.format(lingua=lingua, titolo=titolo)) or {}).get("extract") or ""
    except Exception as e:
        log.warning("profili: riassunto %s non scaricato (%s)", titolo, type(e).__name__)
        return None
    frasi, out = testo.replace("\n", " ").split(". "), ""
    for f in frasi:
        if len(out) + len(f) > 360 and out:
            break
        out += f.rstrip(".") + ". "
    return {"testo": out.strip(), "lingua": lingua, "url": url_voce} if out.strip() else None


URL_TRADUCI = "https://translate.googleapis.com/translate_a/single?client=gtx&sl={da}&tl=it&dt=t&q={q}"


def traduci(desc):
    """v6.54c: aggiunge alla descrizione non italiana la traduzione automatica (campo "trad"). Servizio gratuito
    senza chiave; se non risponde la scheda si arrangia da sola (traduce nel browser). Mai bloccante."""
    if not desc or desc.get("lingua") == "it" or desc.get("trad"):
        return desc
    try:
        r = _get(URL_TRADUCI.format(da=desc.get("lingua") or "auto", q=urllib.parse.quote(desc["testo"])), timeout=20)
        it = "".join(x[0] for x in (r[0] or []) if x and x[0]).strip()
        if it:
            desc = dict(desc, trad=it)
    except Exception as e:
        log.warning("profili: traduzione non riuscita (%s)", type(e).__name__)
    return desc


def componi(t, f, desc, oggi):
    """Il profilo pubblicato (compatto). Dipendenti: il dato piu' recente."""
    dip = sorted((d, n) for d, n in f.get("dip", []) if n)
    return {"t": t, "agg": oggi.isoformat(), "desc": desc, "fondata": f.get("fond"), "sede": f.get("sede"),
            "paese": f.get("paese"), "ceo": sorted(set(f.get("ceo", [])))[:2],
            "dipendenti": {"n": int(float(dip[-1][1])), "anno": dip[-1][0][:4] or None} if dip else None,
            "borse": sorted(set(f.get("borse", [])))[:4],
            "acquisita_da": sorted(f.get("da", []), key=lambda x: -x["anno"])[:1],
            "sito": f.get("web"), "isin": scegli_isin(f.get("isin", []), t), "v": VERSIONE, "rv": RICERCA,
            "fonte": "Wikidata e Wikipedia"}


def aggiorna(cartella, oggi=None, el=None, pausa=PAUSA):
    """Aggiorna i profili scaduti (piu' vecchi di 30 giorni o mancanti), al massimo MAX_PER_GIRO per giro."""
    oggi = oggi or date.today()
    titoli = [x["t"] for x in (el if el is not None else A.elenco())]
    file_di = lambda t: os.path.join(cartella, "pubblico", "profili", A._nome_file(t) + ".json")
    limite = (oggi - timedelta(days=GIORNI_VALIDITA)).isoformat()
    # v6.54: prima i titoli USA (ticker senza suffisso di borsa), poi gli altri; quelli senza voce su Wikidata
    # ricevono un file "vuoto" con la data, cosi' non vengono richiesti a ogni giro
    lim_vuoti = (oggi - timedelta(days=RIPROVA_VUOTI)).isoformat()
    lim_desc = (oggi - timedelta(days=RIPROVA_DESC)).isoformat()

    nomi = {x["t"]: x.get("nome") for x in (el if el is not None else A.elenco())}

    def scaduto(t):                              # vecchio di 30 giorni, oppure in inglese senza traduzione (v6.54c)
        p = A._leggi(file_di(t)) or {}
        d = p.get("desc") or {}
        agg = p.get("agg") or ""
        if p.get("vuoto"):                       # v6.73: i titoli non trovati si riprovano ogni settimana
            return agg < lim_vuoti or p.get("rv") != RICERCA            # v7.7: e subito con la ricerca nuova
        return (agg < limite or p.get("v") != VERSIONE or (not d and (agg < lim_desc or p.get("rv") != RICERCA))
                or (d.get("lingua") not in (None, "it") and not d.get("trad"))
                or (d and not pertinente(d.get("testo"), nomi.get(t), t)))     # v7.22: descrizione di un'altra azienda
    da_fare = [t for t in titoli if scaduto(t)]
    da_fare = sorted(da_fare, key=lambda t: "." in t)[:MAX_PER_GIRO]
    fatti_ok, mancanti, inizio = 0, [], time.time()
    for i in range(0, len(da_fare), LOTTO):
        if time.time() - inizio > TEMPO_MAX:
            log.warning("profili: tempo massimo raggiunto, %d titoli rimandati al prossimo giro", len(da_fare) - i)
            break
        lotto = da_fare[i:i + LOTTO]
        try:
            qid = trova_item(lotto)
            persi = [(t, nomi.get(t)) for t in lotto if t not in qid and nomi.get(t)]
            if persi:                               # v6.73: ticker non su Wikidata -> ricerca per nome
                qid.update(per_nome(persi))
            if i == 0:
                log.warning("profili: primo lotto, %d ticker su %d trovati su Wikidata", len(qid), len(lotto))
            dati = fatti(sorted(set(qid.values()))) if qid else {}
        except Exception as e:                      # Wikidata lento o giu': riprova al prossimo giro, niente blocchi
            log.warning("profili: lotto %d non scaricato (%s: %s)", i // LOTTO + 1, type(e).__name__, e)
            continue
        for t in lotto:
            if t not in qid:
                mancanti.append(t)
                A._scrivi(file_di(t), {"t": t, "agg": oggi.isoformat(), "vuoto": 1, "rv": RICERCA})   # il sito mostra i dati base
                continue
            f = dati.get(qid[t], {})
            desc = riassunto(f.get("it")) or riassunto(f.get("en"))
            if not desc and nomi.get(t):                # v7.13: voce non collegata all'elemento -> ricerca per nome
                try:
                    desc = desc_da_wikipedia(t, nomi[t], qid[t])
                except Exception as e:
                    log.warning("profili: descrizione da Wikipedia non trovata per %s (%s)", t, type(e).__name__)
            if desc and not pertinente(desc.get("testo"), nomi.get(t), t):   # v7.22: voce di un'altra azienda
                log.warning("profili: descrizione scartata per %s (parla di un'altra azienda)", t)
                desc = None
            desc = traduci(desc)
            if pausa:
                time.sleep(pausa)
            A._scrivi(file_di(t), componi(t, f, desc, oggi))
            fatti_ok += 1
    # riepilogo sempre visibile nel registro del workflow (livello warning: le info non vengono stampate)
    log.warning("profili aziende: %d da aggiornare, %d aggiornati, %d senza voce su Wikidata%s", len(da_fare), fatti_ok,
                len(mancanti), (" (es. " + ", ".join(mancanti[:8]) + ")") if mancanti else "")
    return {"aggiornati": fatti_ok, "mancanti": mancanti}
