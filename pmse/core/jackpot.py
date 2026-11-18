"""Jackpot del prossimo concorso e "valore medio" di una colonna.

SuperEnalotto: il jackpot del prossimo concorso è scritto su superenalotto.com.
Eurojackpot: euro-jackpot.net riporta il jackpot dell'ultimo concorso e se è stato vinto; il prossimo
è quindi indicato in modo approssimato (se è stato vinto riparte da circa 10 milioni, altrimenti cresce).

Il valore medio di una colonna è la somma, su tutte le categorie, di probabilità × premio (premi medi
degli ultimi concorsi; per il primo premio il jackpot), dopo la ritenuta del 20% sulla parte di ogni
vincita oltre 500 €. È una stima semplificata (non tiene conto dei jackpot divisi tra più vincitori).
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta

from .gioco import Gioco
from .rete import contesto_ssl

CHIAVE = "jackpot"
URL_SE = "https://www.superenalotto.com/"
INTESTAZIONI = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PensieroMagico"}


@dataclass
class Jackpot:
    gioco: str
    importo: float | None             # jackpot del prossimo concorso (stima per l'Eurojackpot)
    preciso: bool                     # False = stima
    nota: str = ""
    letto: str = ""                   # quando è stato letto (ISO)
    valore_colonna: float | None = None
    costo_colonna: float | None = None


def netto(premio: float) -> float:
    """Premio dopo la ritenuta del 20% sulla parte oltre 500 € (regola italiana)."""
    return premio if premio <= 500 else premio - 0.2 * (premio - 500)


def _quote_medie(dati: dict, chiavi, ultime: int = 50) -> dict[str, float]:
    recenti = [dati[k] for k in sorted(dati)[-ultime:]]
    out = {}
    for cat, fun in chiavi.items():
        vals = [x for x in (fun(v) for v in recenti) if x]
        if vals:
            out[cat] = sum(vals) / len(vals)
    return out


def valore_colonna(g: Gioco, jackpot: float | None, dati_quote: dict) -> float | None:
    """Valore medio (netto) di una colonna con il jackpot indicato."""
    from . import statistiche as st
    if g.is_ej:
        pr = st.probabilita_ej(12)
        medie = _quote_medie(dati_quote, {c: (lambda v, c=c: v.quote.get(c)) for c in pr if c != "5+2"})
        primo = "5+2"
    else:
        pr = st.probabilita_se()
        campi = {"5+1": "q51", "5": "q5", "4": "q4", "3": "q3", "2": "q2"}
        medie = _quote_medie(dati_quote, {c: (lambda v, f=f: getattr(v, f, None)) for c, f in campi.items()})
        primo = "6"
    if not medie or not jackpot:
        return None
    ev = pr[primo] * netto(jackpot)
    for c, p in pr.items():
        if c != primo and c in medie:
            ev += p * netto(medie[c])
    return ev


def leggi_se(timeout: int = 20) -> float | None:
    from . import vincite
    req = urllib.request.Request(URL_SE, headers=INTESTAZIONI)
    with urllib.request.urlopen(req, timeout=timeout, context=contesto_ssl()) as r:
        return vincite.jackpot_da_pagina(r.read().decode("utf-8", errors="replace"))


def stima_ej(ultimo) -> tuple[float | None, str]:
    """Dal jackpot dell'ultimo concorso (VinciteEJ) una stima del prossimo."""
    if ultimo is None or not ultimo.jackpot:
        return None, "Jackpot non disponibile"
    if ultimo.vincitori_jackpot:
        return 10_000_000.0, (f"Il jackpot di {ultimo.jackpot:,.0f} € è stato vinto il "
                              f"{date.fromisoformat(ultimo.data):%d/%m/%Y}: il prossimo riparte da circa "
                              "10 milioni").replace(",", ".")
    return ultimo.jackpot, (f"Nell'ultimo concorso ({date.fromisoformat(ultimo.data):%d/%m/%Y}) il jackpot di "
                            f"{ultimo.jackpot:,.0f} € non è stato vinto: il prossimo sarà più alto "
                            "(massimo 120 milioni)").replace(",", ".")


def aggiorna(archivio, forza: bool = False, timeout: int = 20) -> Jackpot | None:
    """Legge il jackpot da Internet (al massimo ogni 6 ore) e calcola il valore medio di una colonna."""
    g = archivio.gioco
    vecchio = carica(archivio)
    if vecchio and not forza:
        try:
            if datetime.now() - datetime.fromisoformat(vecchio.letto) < timedelta(hours=6):
                return vecchio
        except ValueError:
            pass
    from .sistemi import costo
    if g.is_ej:
        from . import vincite_ej
        dati = vincite_ej.carica(archivio)
        u = archivio.ultima()
        ultimo = dati.get(u.data.isoformat()) if u else None
        if u and ultimo is None:
            ultimo = vincite_ej.scarica_concorso(u.data, timeout)
            if ultimo:
                vincite_ej.salva(archivio, {ultimo.data: ultimo})
                dati[ultimo.data] = ultimo
        importo, nota = stima_ej(ultimo)
        j = Jackpot("EJ", importo, False, nota)
    else:
        from . import vincite
        dati = vincite.carica(archivio)
        importo = leggi_se(timeout)
        j = Jackpot("SE", importo, True, "")
    j.letto = datetime.now().isoformat(timespec="seconds")
    j.costo_colonna = costo(1, g)
    j.valore_colonna = valore_colonna(g, j.importo, dati)
    archivio.scrivi_impostazione(CHIAVE, json.dumps(asdict(j)))
    return j


def carica(archivio) -> Jackpot | None:
    try:
        d = json.loads(archivio.leggi_impostazione(CHIAVE) or "null")
        return Jackpot(**d) if d else None
    except (ValueError, TypeError):
        return None


def testo(j: Jackpot) -> tuple[str, str]:
    """(riga principale, dettaglio) per la home."""
    if j is None or not j.importo:
        return "", ""
    imp = f"{j.importo:,.0f} €".replace(",", ".")
    riga = (f"💰 Jackpot del prossimo concorso: {imp}" if j.preciso else f"💰 Jackpot: circa {imp}")
    return riga, j.nota
