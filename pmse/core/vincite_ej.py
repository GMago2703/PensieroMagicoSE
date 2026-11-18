"""Quote (premi per vincitore) dei concorsi Eurojackpot e valore del jackpot (fonte: euro-jackpot.net).

Servono al registro delle giocate (quanto si è vinto), al simulatore "E se avessi giocato…" e alla home
(jackpot). Un archivio iniziale è incluso nel programma (pmse/dati/vincite_ej.json); l'app scarica solo
i concorsi successivi. Rigidamente separato dal SuperEnalotto: si salva solo nell'archivio EJ.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import date
from html import unescape
from pathlib import Path

from .rete import contesto_ssl

URL = "https://www.euro-jackpot.net/it/risultati/{:%d-%m-%Y}"
INTESTAZIONI = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PensieroMagico"}
FILE_INCLUSO = Path(__file__).resolve().parent.parent / "dati" / "vincite_ej.json"
CHIAVE_DB = "vincite_ej"
CATEGORIE = ["5+2", "5+1", "5+0", "4+2", "4+1", "4+0", "3+2", "2+2", "3+1", "3+0", "1+2", "2+1"]
_RE = re.compile(r"(\d) numer[oi](?: più (\d) Euronumer[oi])?\s+†?\s*(-|[\d.]+(?:,\d+)?\s*€)\s+([\d.]+)")
_RE_JACK = re.compile(r"Valore del jackpot\s+([\d.]+)\s*€")
_RE_VJ = re.compile(r"Vincitori del jackpot\s+([\d.]+)")


@dataclass
class VinciteEJ:
    data: str
    quote: dict = field(default_factory=dict)        # "4+2" -> euro per vincitore
    vincitori: dict = field(default_factory=dict)    # "4+2" -> numero di vincitori
    jackpot: float | None = None                     # jackpot in palio in quel concorso
    vincitori_jackpot: int | None = None


def _testo(html: str) -> str:
    t = re.sub(r"<(script|style).*?</\1>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", t)))


def analizza_pagina(html: str, d: date) -> VinciteEJ | None:
    testo = _testo(html)
    i = testo.find("Lista dei premi")
    if i < 0:
        return None
    fine = testo.find("Totale", i)
    sezione = testo[i:fine if fine > 0 else i + 2500]
    v = VinciteEJ(d.isoformat())
    for m in _RE.finditer(sezione):
        cat = f"{m.group(1)}+{m.group(2) or 0}"
        if cat not in CATEGORIE or cat in v.vincitori:
            continue
        v.vincitori[cat] = int(m.group(4).replace(".", ""))
        q = m.group(3).replace("€", "").strip()
        if q and q != "-":
            v.quote[cat] = float(q.replace(".", "").replace(",", "."))
    m = _RE_JACK.search(testo)
    if m:
        v.jackpot = float(m.group(1).replace(".", ""))
    m = _RE_VJ.search(testo)
    if m:
        v.vincitori_jackpot = int(m.group(1).replace(".", ""))
    return v if v.vincitori else None


def scarica_concorso(d: date, timeout: int = 30) -> VinciteEJ | None:
    req = urllib.request.Request(URL.format(d), headers=INTESTAZIONI)
    with urllib.request.urlopen(req, timeout=timeout, context=contesto_ssl()) as r:
        return analizza_pagina(r.read().decode("utf-8", errors="replace"), d)


def scarica(date_concorsi, avanzamento=None, interrompi=None, pausa: float = 0.25) -> dict[str, VinciteEJ]:
    out: dict[str, VinciteEJ] = {}
    date_concorsi = list(date_concorsi)
    for i, d in enumerate(date_concorsi):
        if interrompi and interrompi():
            break
        for tentativo in range(3):
            try:
                v = scarica_concorso(d)
                if v:
                    out[v.data] = v
                break
            except Exception:
                time.sleep(2 * (tentativo + 1))
        if avanzamento:
            avanzamento(f"Quote del {d:%d/%m/%Y}", i + 1, len(date_concorsi))
        time.sleep(pausa)
    return out


def da_json(testo: str | None) -> dict[str, VinciteEJ]:
    if not testo:
        return {}
    try:
        return {k: VinciteEJ(**v) for k, v in json.loads(testo).items()}
    except Exception:
        return {}


def a_json(dati: dict[str, VinciteEJ]) -> str:
    return json.dumps({k: asdict(v) for k, v in sorted(dati.items())}, separators=(",", ":"))


def incluse() -> dict[str, VinciteEJ]:
    try:
        return da_json(FILE_INCLUSO.read_text(encoding="utf-8"))
    except OSError:
        return {}


def carica(archivio) -> dict[str, VinciteEJ]:
    dati = incluse()
    dati.update(da_json(archivio.leggi_impostazione(CHIAVE_DB)))
    return dati


def mancanti(archivio) -> list[date]:
    if archivio.gioco.codice != "EJ":
        return []
    noti = carica(archivio)
    return [e.data for e in archivio.tutte(True) if e.data.isoformat() not in noti]


def salva(archivio, nuovi: dict[str, VinciteEJ]) -> None:
    if not nuovi or archivio.gioco.codice != "EJ":
        return
    propri = da_json(archivio.leggi_impostazione(CHIAVE_DB))
    propri.update(nuovi)
    archivio.scrivi_impostazione(CHIAVE_DB, a_json(propri))


def aggiorna(archivio, avanzamento=None, interrompi=None) -> int:
    da_fare = mancanti(archivio)
    if not da_fare:
        return 0
    nuovi = scarica(da_fare, avanzamento, interrompi)
    salva(archivio, nuovi)
    return len(nuovi)
