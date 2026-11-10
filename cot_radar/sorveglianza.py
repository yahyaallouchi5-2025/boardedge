# -*- coding: utf-8 -*-
"""
sorveglianza.py - v7.24 ALLARME QUANDO QUALCOSA SI FERMA (per l'admin, non per gli iscritti).

PERCHE'
  Nel novembre 2026 il sito e' rimasto fermo per ore (pubblicazione di GitHub Pages bloccata) e i giri automatici
  delle azioni sono partiti con 9 ore di ritardo: ce ne siamo accorti solo guardando a mano. Ora un controllo
  automatico ogni ora lo segnala.

COSA CONTROLLA (workflow sorveglianza.yml, ogni ora)
  1) sito pubblicato: stato.json del sito, campo "creato" (UTC), non piu' vecchio di ORE_SITO;
  2) Azionario: azioni/indice.json, campo "generato" (ora italiana), non piu' vecchio di ORE_AZIONI;
  3) prezzi live: live.json nel ramo "live", campo "quando" (secondi), fresco durante le ore di borsa;
  4) ultimo giro CONCLUSO dei workflow principali (Sito, Azioni, Prezzi live, Test): nessuno fallito.
  Nel fine settimana (e il lunedi' mattina) le soglie si allungano: le borse sono chiuse e i giri non partono.

COME AVVISA
  - apre una "issue" su GitHub con l'etichetta "sorveglianza" (GitHub manda una mail e una notifica sull'app):
    una sola issue aperta alla volta; se cambiano i problemi aggiunge un commento, mai doppioni;
  - quando tutto torna a posto commenta "risolto" e la CHIUDE da sola;
  - se nei Secrets ci sono TELEGRAM_BOT_TOKEN e TELEGRAM_ADMIN_CHAT manda anche un messaggio Telegram privato.
  Nessuna chiave nel codice: il token di GitHub e' quello del workflow.

USO: python -m cot_radar.sorveglianza            (giro normale, nel workflow)
     python -m cot_radar.sorveglianza --prova    (stampa i problemi senza aprire issue)
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

SITO = "https://yahyaallouchi5-2025.github.io/cot-radar/"
REPO = "yahyaallouchi5-2025/cot-radar"
LIVE = "https://raw.githubusercontent.com/" + REPO + "/live/live.json"
ORE_SITO = 30            # il sito si ricostruisce almeno 2 volte al giorno nei feriali
ORE_AZIONI = 30          # tre giri al giorno (Asia, Europa, USA)
ORE_FINE_SETTIMANA = 64  # venerdi' sera -> lunedi' mattina
MIN_LIVE = 75            # prezzi live: ogni 15 minuti a borsa aperta (GitHub puo' ritardare)
WORKFLOW = {"sito.yml": "Sito", "azioni.yml": "Azioni", "prezzi-live.yml": "Prezzi live", "test.yml": "Test"}
ETICHETTA = "sorveglianza"
UA = {"User-Agent": "cot-radar/sorveglianza"}


# --------------------------------------------------------------------------- regole (pure, testate)
def soglia_ore(adesso, base):
    """Ore massime di "vecchiaia" accettate: base nei feriali, ORE_FINE_SETTIMANA da sabato a lunedi' alle 12 UTC."""
    wd = adesso.weekday()                      # 0 = lunedi'
    if wd >= 5 or (wd == 0 and adesso.hour < 12):
        return max(base, ORE_FINE_SETTIMANA)
    return base


def borsa_aperta(adesso):
    """True tra le 08:00 e le 20:30 UTC dei giorni feriali (Europa + Wall Street, con margine)."""
    return adesso.weekday() < 5 and (8, 0) <= (adesso.hour, adesso.minute) <= (20, 30)


def _ore(adesso, quando):
    return (adesso - quando).total_seconds() / 3600


def problemi(adesso, stato=None, indice=None, live=None, giri=None):
    """Lista di frasi (in italiano) con cio' che non va. Vuota = tutto regolare.
    stato = stato.json del sito; indice = azioni/indice.json; live = live.json; giri = {nome: (conclusione, url)}."""
    out = []
    # 1) sito
    try:
        creato = datetime.strptime(stato["creato"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        h = _ore(adesso, creato)
        if h > soglia_ore(adesso, ORE_SITO):
            out.append("Sito non aggiornato da %d ore (ultima pubblicazione %s UTC)." % (h, stato["creato"][:16]))
        if stato.get("esito") in ("errori", "critico"):
            out.append("Ultimo aggiornamento del sito con esito \"%s\"." % stato["esito"])
    except (TypeError, KeyError, ValueError):
        out.append("stato.json del sito non leggibile: il sito potrebbe essere giu'.")
    # 2) Azionario (ora italiana: si confronta con un margine di 2 ore, il fuso non conta a queste soglie)
    try:
        gen = datetime.strptime(indice["generato"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc) - timedelta(hours=1)
        h = _ore(adesso, gen)
        if h > soglia_ore(adesso, ORE_AZIONI) + 2:
            out.append("Azionario non aggiornato da %d ore (ultimo giro %s ora italiana)." % (h, indice["generato"]))
        if indice.get("anomalia"):
            out.append("Azionario in anomalia (codice %s)." % (indice["anomalia"] or {}).get("codice", "?"))
    except (TypeError, KeyError, ValueError):
        out.append("azioni/indice.json non leggibile.")
    # 3) prezzi live (solo a borsa aperta)
    if borsa_aperta(adesso):
        try:
            m = (adesso.timestamp() - float(live["quando"])) / 60
            if m > MIN_LIVE:
                out.append("Prezzi live fermi da %d minuti a borsa aperta." % m)
        except (TypeError, KeyError, ValueError):
            out.append("live.json non leggibile a borsa aperta.")
    # 4) workflow
    for nome, (concl, url) in sorted((giri or {}).items()):
        if concl in ("failure", "timed_out", "startup_failure"):
            out.append("Ultimo giro \"%s\" fallito: %s" % (nome, url))
    return out


def testo_issue(prob, adesso):
    righe = "\n".join("- " + p for p in prob)
    return ("Controllo automatico del %s UTC.\n\n%s\n\nLa issue si chiude da sola quando tutto torna regolare."
            % (adesso.strftime("%Y-%m-%d %H:%M"), righe))


# --------------------------------------------------------------------------- rete
def _json(url, token=None, metodo="GET", corpo=None):
    h = dict(UA)
    if token:
        h.update({"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json"})
    dati = json.dumps(corpo).encode() if corpo is not None else None
    if dati:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=dati, headers=h, method=metodo)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _prova(fn):
    try:
        return fn()
    except Exception:
        return None


def giri_workflow(token):
    """{nome: (conclusione, url)} dell'ultimo giro CONCLUSO di ogni workflow sorvegliato."""
    out = {}
    for f, nome in WORKFLOW.items():
        js = _prova(lambda: _json("https://api.github.com/repos/%s/actions/workflows/%s/runs?status=completed&per_page=1"
                                  % (REPO, f), token))
        runs = (js or {}).get("workflow_runs") or []
        if runs:
            out[nome] = (runs[0].get("conclusion"), runs[0].get("html_url"))
    return out


def telegram(testo, env):
    tok, chat = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_ADMIN_CHAT")
    if not tok or not chat:
        return
    _prova(lambda: _json("https://api.telegram.org/bot%s/sendMessage" % tok, metodo="POST",
                         corpo={"chat_id": chat, "text": "BoardEdge - sorveglianza\n\n" + testo,
                                "disable_web_page_preview": True}))


def avvisa(prob, adesso, token, env):
    """Apre/aggiorna/chiude l'unica issue "sorveglianza"."""
    api = "https://api.github.com/repos/%s/issues" % REPO
    aperte = _json(api + "?state=open&labels=" + ETICHETTA, token) or []
    issue = aperte[0] if aperte else None
    if prob:
        corpo = testo_issue(prob, adesso)
        if issue is None:
            _json(api, token, "POST", {"title": "Sorveglianza: qualcosa si e' fermato", "body": corpo,
                                       "labels": [ETICHETTA]})
            telegram("\n".join(prob), env)
        else:
            ultimo = _json(issue["comments_url"], token) or []
            precedente = (ultimo[-1]["body"] if ultimo else issue.get("body") or "")
            if any(p not in precedente for p in prob):        # problemi nuovi: commento + Telegram
                _json(issue["comments_url"], token, "POST", {"body": corpo})
                telegram("\n".join(prob), env)
    elif issue is not None:
        _json(issue["comments_url"], token, "POST", {"body": "Tutto di nuovo regolare (%s UTC). Chiudo."
                                                              % adesso.strftime("%Y-%m-%d %H:%M")})
        _json(issue["url"], token, "PATCH", {"state": "closed"})
        telegram("Tutto di nuovo regolare.", env)


def main(argv):
    adesso = datetime.now(timezone.utc)
    env = os.environ
    token = env.get("GITHUB_TOKEN")
    stato = _prova(lambda: _json(SITO + "stato.json?t=%d" % adesso.timestamp()))
    indice = _prova(lambda: _json(SITO + "azioni/indice.json?t=%d" % adesso.timestamp()))
    live = _prova(lambda: _json(LIVE))
    giri = giri_workflow(token) if token else {}
    prob = problemi(adesso, stato, indice, live, giri)
    print("\n".join(prob) if prob else "Tutto regolare.")
    if "--prova" not in argv and token:
        avvisa(prob, adesso, token, env)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
