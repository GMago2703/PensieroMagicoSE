"""Scaricamento delle estrazioni da Internet.

Fonti (archivi annuali pubblici):
- SuperEnalotto: https://www.superenalotto.com/archivio/estrazioni-AAAA (dal 1997, con
  Jolly, SuperStar e numeri nell'ordine di estrazione);
- Eurojackpot: https://www.euro-jackpot.net/it/risultati-archivio-AAAA (dal 23/03/2012,
  con i 2 Euronumeri).

Se il sito cambia struttura basta aggiornare questo modulo; l'import da file
resta sempre disponibile come alternativa.
"""
from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from datetime import date
from typing import Callable

from .gioco import SE, Gioco
from .modello import MESI, Estrazione
from .rete import contesto_ssl

URL_ANNO = "https://www.superenalotto.com/archivio/estrazioni-{anno}"
URL_ANNO_EJ = "https://www.euro-jackpot.net/it/risultati-archivio-{anno}"
PRIMO_ANNO = 1997
PRIMO_ANNO_EJ = 2012
FONTE = {"SE": "superenalotto.com", "EJ": "euro-jackpot.net"}
INTESTAZIONI = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PensieroMagicoSE/0.1",
    "Accept-Language": "it-IT,it;q=0.9",
}

_RE_BLOCCO = re.compile(r'class="boxArchiveNumbers"(.*?)(?=class="boxArchiveNumbers"|class="boxArchiveTitle"|$)',
                        re.S)
_RE_DATA = re.compile(r'class="boxarchiveDate"[^>]*>\s*(\d{1,2})\s+([a-zà]+)\s+(\d{4})', re.I)
_RE_NUM = re.compile(r'class="boxArchiveNumber(?P<tipo>[^"]*)"[^>]*>\s*(?P<n>\d+)')


class ErroreInternet(Exception):
    pass


def scarica_pagina(url: str, tentativi: int = 3) -> str:
    ultimo = None
    for i in range(tentativi):
        try:
            req = urllib.request.Request(url, headers=INTESTAZIONI)
            with urllib.request.urlopen(req, timeout=30, context=contesto_ssl()) as r:
                return r.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as ex:
            ultimo = ex
            time.sleep(1.5 * (i + 1))
    raise ErroreInternet(f"Impossibile scaricare {url}: {ultimo}")


def analizza_pagina_anno(html: str) -> list[Estrazione]:
    risultati: list[Estrazione] = []
    for blocco in _RE_BLOCCO.findall(html):
        m = _RE_DATA.search(blocco)
        if not m:
            continue
        mese = m.group(2).lower()
        if mese not in MESI:
            continue
        d = date(int(m.group(3)), MESI.index(mese) + 1, int(m.group(1)))
        numeri, jolly, superstar = [], None, None
        for n in _RE_NUM.finditer(blocco):
            tipo = n.group("tipo").lower()
            valore = int(n.group("n"))
            if "red" in tipo:
                jolly = valore
            elif "star" in tipo:
                superstar = valore if valore > 0 else None
            else:
                numeri.append(valore)
        if len(numeri) == 6 and jolly:
            risultati.append(Estrazione(data=d, numeri=numeri, jolly=jolly, superstar=superstar,
                                        fonte="superenalotto.com"))
    return risultati


_RE_RIGA_EJ = re.compile(r"<tr>(.*?)</tr>", re.S)
_RE_DATA_EJ = re.compile(r"(\d{1,2})\s+([a-zà]+)\s+(\d{4})\s*</a>", re.I)
_RE_PALLA_EJ = re.compile(r'<li class="(ball|euro)"[^>]*>\s*<span>\s*(\d+)\s*</span>', re.I)


def analizza_pagina_anno_ej(html: str) -> list[Estrazione]:
    from .gioco import EJ
    risultati: list[Estrazione] = []
    for riga in _RE_RIGA_EJ.findall(html):
        m = _RE_DATA_EJ.search(riga)
        if not m or m.group(2).lower() not in MESI:
            continue
        d = date(int(m.group(3)), MESI.index(m.group(2).lower()) + 1, int(m.group(1)))
        palle = _RE_PALLA_EJ.findall(riga)
        numeri = [int(v) for t, v in palle if t.lower() == "ball"]
        euro = [int(v) for t, v in palle if t.lower() == "euro"]
        if len(numeri) == 5 and len(euro) == 2:
            risultati.append(Estrazione(data=d, numeri=numeri, jolly=euro[0], superstar=euro[1],
                                        fonte="euro-jackpot.net", gioco=EJ))
    return risultati


def scarica_anni(anni: list[int], avanzamento: Callable[[str, int, int], None] | None = None,
                 interrompi: Callable[[], bool] | None = None, gioco: Gioco = SE) -> list[Estrazione]:
    tutte: list[Estrazione] = []
    for i, anno in enumerate(anni, start=1):
        if interrompi and interrompi():
            break
        if avanzamento:
            avanzamento(f"Scarico l'anno {anno}...", i - 1, len(anni))
        if gioco.is_ej:
            estr = analizza_pagina_anno_ej(scarica_pagina(URL_ANNO_EJ.format(anno=anno)))
        else:
            estr = analizza_pagina_anno(scarica_pagina(URL_ANNO.format(anno=anno)))
        if not estr and anno < date.today().year:
            raise ErroreInternet(f"Nessuna estrazione riconosciuta per il {anno}: "
                                 "forse il sito ha cambiato struttura.")
        tutte.extend(estr)
        if avanzamento:
            avanzamento(f"Anno {anno}: {len(estr)} estrazioni", i, len(anni))
        time.sleep(0.4)   # cortesia verso il sito
    return tutte


def anni_da_aggiornare(ultima_data: date | None, gioco: Gioco = SE) -> list[int]:
    oggi = date.today()
    inizio = ultima_data.year if ultima_data else (PRIMO_ANNO_EJ if gioco.is_ej else PRIMO_ANNO)
    return list(range(inizio, oggi.year + 1))
