# -*- coding: utf-8 -*-
"""
scarica_giornaliero.py - RACCOLTA UNA TANTUM DEI PREZZI GIORNALIERI PER LO STUDIO (solo dati: il sito non cambia)

Serve al punto 2 dello studio sulle "Azioni scelte": provare stop loss, trailing stop e uscite per volatilita' con i
gap di apertura. Per questo servono apertura, massimo, minimo e chiusura di OGNI giorno dal 2005, non solo i mesi.

Cosa fa:
  - prende i titoli della scheda Azioni (azioni_elenco.csv, come satellite.py: niente titoli fuori Europa/USA/Asia
    esclusi dal satellite) piu' SPY (filtro di mercato) e RSP (S&P 500 a pari peso reale, per stimare la sopravvivenza)
  - scarica da Yahoo le barre giornaliere dal 2005 con period1/period2 (con range=max Yahoo comprime le barre)
  - RETTIFICA apertura/massimo/minimo con lo stesso fattore della chiusura (adjclose/close): dividendi e split
    non creano finti gap
  - salva <cartella>/giornaliero/<T>.csv.gz (data,apertura,massimo,minimo,chiusura rettificati) e stato.json

USO: python tools/scarica_giornaliero.py <cartella di uscita>     (lo lancia .github/workflows/studio-giornaliero.yml)
"""
import csv
import gzip
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cot_radar import azioni as A          # noqa: E402
from cot_radar import satellite as S       # noqa: E402

INIZIO = int(datetime(2004, 12, 1, tzinfo=timezone.utc).timestamp())   # un mese prima del 2005 per le medie
EXTRA = ["SPY", "RSP"]
PAUSA = 0.4                 # secondi tra una richiesta e l'altra (gentili con Yahoo)
TENTATIVI = 3


def scarica_ohlc(ticker, timeout=25):
    """[(data, o, h, l, c)] rettificati, oppure None. Stesso User-Agent dichiarato del resto del progetto."""
    q = urllib.parse.urlencode({"period1": INIZIO, "period2": int(time.time()), "interval": "1d",
                                "includeAdjustedClose": "true", "events": "div,split"})
    for n in range(TENTATIVI):
        try:
            req = urllib.request.Request(A.YAHOO.format(t=urllib.parse.quote(ticker), q=q),
                                         headers={"User-Agent": "cot-radar/studio"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                res = json.load(r)["chart"]["result"][0]
            off = res["meta"].get("gmtoffset", 0)
            qt = res["indicators"]["quote"][0]
            adj = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose") or qt["close"]
            righe = {}
            for i, ts in enumerate(res.get("timestamp") or []):
                o, h, l, c, ac = qt["open"][i], qt["high"][i], qt["low"][i], qt["close"][i], adj[i]
                if not c or c <= 0 or not ac or ac <= 0:
                    continue
                k = ac / c                                    # fattore di rettifica del giorno
                o = o if o and o > 0 else c                   # apertura mancante: si usa la chiusura (nessun gap)
                h = max(h if h and h > 0 else c, o, c)        # massimo/minimo coerenti con apertura e chiusura
                l = min(l if l and l > 0 else c, o, c)
                d = datetime.fromtimestamp(ts + off, tz=timezone.utc).date().isoformat()
                righe[d] = tuple(float(f"{v * k:.6g}") for v in (o, h, l, c))
            pts = sorted(righe.items())
            if len(pts) >= 250 and quotidiane(pts):
                return pts
            print(f"  {ticker}: storico corto o non giornaliero ({len(pts)} barre)")
            return None
        except Exception as e:                                # rete/Yahoo: si riprova con attesa crescente
            print(f"  {ticker}: {getattr(e, 'code', type(e).__name__)} (tentativo {n + 1}/{TENTATIVI})")
            time.sleep(2 * (3 ** n))
    return None


def quotidiane(pts):
    """Barre davvero giornaliere: distanza mediana tra due barre al massimo 4 giorni."""
    dd = sorted((datetime.fromisoformat(b[0]) - datetime.fromisoformat(a[0])).days for a, b in zip(pts, pts[1:]))
    return dd[len(dd) // 2] <= 4


def salva(cartella, ticker, pts):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["data", "o", "h", "l", "c"])
    for d, v in pts:
        w.writerow([d, *v])
    with gzip.open(os.path.join(cartella, "giornaliero", A._nome_file(ticker) + ".csv.gz"), "wt", encoding="utf-8") as f:
        f.write(buf.getvalue())


def main(cartella):
    os.makedirs(os.path.join(cartella, "giornaliero"), exist_ok=True)
    titoli = [x["t"] for x in A.elenco() if not x["t"].endswith(S.NON_UE)] + EXTRA
    ok, ko, t0 = [], [], time.time()
    for i, t in enumerate(titoli, 1):
        pts = scarica_ohlc(t)
        if pts:
            salva(cartella, t, pts)
            ok.append(t)
        else:
            ko.append(t)
        if i % 50 == 0:
            print(f"{i}/{len(titoli)} titoli, {len(ko)} falliti, {time.time() - t0:.0f} s")
        time.sleep(PAUSA)
    stato = {"agg": datetime.now(timezone.utc).isoformat(timespec="seconds"), "titoli": len(titoli),
             "ok": len(ok), "falliti": ko, "secondi": round(time.time() - t0)}
    with open(os.path.join(cartella, "stato.json"), "w", encoding="utf-8") as f:
        json.dump(stato, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in stato.items() if k != "falliti"}), "falliti:", len(ko))
    # piu' del 20% di titoli mancanti = raccolta da rifare (codice 1 -> il job fallisce e si vede in Actions)
    return 0 if len(ko) <= 0.2 * len(titoli) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
