# -*- coding: utf-8 -*-
"""
studio_belveal_oi.py - LE REGOLE "PREZZO + OPEN INTEREST" DI BELVEAL ("Charting Commodity Market Price Behavior",
cap. 5 e 8) MESSE ALLA PROVA - Ya, 13/11/2026. Solo studio, dati gia' archiviati (stessi dello studio COT Bible).

REGOLE DEL LIBRO (fissate prima di vedere i risultati):
  prezzo SU  + open interest SU  = denaro nuovo che compra  -> rialzo "forte"   -> COMPRA   (R1)
  prezzo GIU + open interest SU  = denaro nuovo che vende   -> ribasso "forte"  -> VENDI    (R2)
  prezzo SU  + open interest GIU = ricoperture              -> rialzo "debole"  -> il libro dice: non seguire (R3)
  prezzo GIU + open interest GIU = liquidazioni             -> ribasso "debole" -> il libro dice: non seguire (R4)
MISURA: variazioni su 4 settimane (prezzo: chiusura del martedi' del rapporto; open interest: dal rapporto COT);
  ingresso alla prima seduta dopo la PUBBLICAZIONE del rapporto (venerdi' sera a Roma), tenuta 4 settimane, costi del
  sito. Un segnale per rapporto. Per R3 e R4 si misura il verso del prezzo (per vedere se "debole" e' vero).
CONFRONTO: il solo verso del prezzo (momentum 4 settimane, senza open interest): l'open interest aggiunge qualcosa
  solo se R1+R2 rende piu' di R3+R4 in ENTRAMBI i periodi (studio fino al 2014, verifica dal 2015) con t >= 4
  (le operazioni di 4 settimane si sovrappongono 4 a 4: il t "vero" e' circa la meta' di quello stampato).
USO: python studi/studio_belveal_oi.py <cartella dati>
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import studio_cot_bible as C   # noqa: E402

N = 4


def eventi(m):
    rapp = [x[0] for x in m.cot]
    oi = [x[3] for x in m.cot]
    out = []
    for t in range(N, len(rapp)):
        pub = C.pubblicazione(rapp[t])
        if pub is None or (rapp[t] - rapp[t - N]).days > 7 * N + 7:
            continue
        p1, p0 = m.prezzo_al(rapp[t]), m.prezzo_al(rapp[t - N])
        if not p1 or not p0 or p1 == p0 or oi[t] == oi[t - N]:
            continue
        su, oi_su = (p1 > p0) == (m.segno > 0), oi[t] > oi[t - N]   # verso del FUTURE (USD/JPY sale = yen scende)
        regola = "R1" if su and oi_su else "R2" if not su and oi_su else "R3" if su else "R4"
        out.append((pub, regola, 1 if su else -1))
    return out


def prezzo_al(m, d):
    """Ultima chiusura nota fino alla data d (compresa)."""
    import bisect
    i = bisect.bisect_right(m.date, d) - 1
    return m.px[i][2] if i >= 0 else None


def main():
    mer = C.carica(sys.argv[1])
    ops = []
    for m in mer.values():
        m.prezzo_al = lambda d, m=m: prezzo_al(m, d)
        ops += C.operazioni(m, eventi(m), (N,))
    print(f"mercati {len(mer)}, operazioni {len(ops)}")
    print(f"{'':28}{'STUDIO -2014':^26}|{'VERIFICA 2015+':^26}|")
    print(f"{'':28}" + ("     n  media%  vinte     t|" * 2))
    def riga(nome, sel):
        s = ""
        for studio in (True, False):
            rs = [o[4][N] for o in ops if sel(o) and ((o[2] <= C.FINE_STUDIO) == studio) and o[4][N] is not None]
            st = C.stat(rs)
            s += f"{st['n']:6}{st.get('media', 0):8.3f}{st.get('vinte', 0):7.1f}{st.get('t', 0):6.2f}|"
        print(f"{nome:28}{s}")
    riga("R1 prezzo su, OI su", lambda o: o[0] == "R1")
    riga("R2 prezzo giu, OI su", lambda o: o[0] == "R2")
    riga("R3 prezzo su, OI giu", lambda o: o[0] == "R3")
    riga("R4 prezzo giu, OI giu", lambda o: o[0] == "R4")
    riga("FORTI (R1+R2)", lambda o: o[0] in ("R1", "R2"))
    riga("DEBOLI (R3+R4)", lambda o: o[0] in ("R3", "R4"))
    riga("solo prezzo (tutte)", lambda o: True)
    # differenza forti - deboli (t di Welch) per periodo
    for studio in (True, False):
        a = [o[4][N] for o in ops if o[0] in ("R1", "R2") and ((o[2] <= C.FINE_STUDIO) == studio) and o[4][N] is not None]
        b = [o[4][N] for o in ops if o[0] in ("R3", "R4") and ((o[2] <= C.FINE_STUDIO) == studio) and o[4][N] is not None]
        ma, mb = sum(a) / len(a), sum(b) / len(b)
        va = sum((x - ma) ** 2 for x in a) / (len(a) - 1)
        vb = sum((x - mb) ** 2 for x in b) / (len(b) - 1)
        t = (ma - mb) / math.sqrt(va / len(a) + vb / len(b))
        print(f"{'studio' if studio else 'verifica'}: forti - deboli = {(ma - mb):+.3f}% a operazione, t = {t:.2f}")


if __name__ == "__main__":
    main()
