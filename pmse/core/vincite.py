"""Vincitori per categoria di ogni concorso del SuperEnalotto (fonte: superenalotto.com).

Per ogni concorso si conservano i vincitori di 6, 5+1, 5, 4, 3 punti e il premio del 6.
Servono a:
  - riconoscere i concorsi in cui è stato vinto il jackpot (il "6") ed evidenziarli in archivio;
  - studiare quanto era "giocata" ogni sestina: il numero di vincitori con 3 o 4 punti, rispetto a
    quanto ci si aspetta dal numero di giocate, dice se la sestina estratta era tra quelle che la
    gente sceglie spesso (date, numeri bassi, schemi) o tra quelle poco giocate.

Un archivio iniziale già pronto è incluso nel programma (pmse/dati/vincite_se.json); l'app
scarica solo i concorsi successivi.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date
from html import unescape
from pathlib import Path

from .rete import contesto_ssl

URL = "https://www.superenalotto.com/risultati-estrazione/{:%d-%m-%Y}"
INTESTAZIONI = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PensieroMagico"}
FILE_INCLUSO = Path(__file__).resolve().parent.parent / "dati" / "vincite_se.json"
CHIAVE_DB = "vincite_se"
CATEGORIE = [("6 punti", "p6"), ("5 punti + Jolly", "p51"), ("5 punti", "p5"), ("4 punti", "p4"),
             ("3 punti", "p3"), ("2 punti", "p2")]
LIRE_PER_EURO = 1936.27
_RE_SS = re.compile(r"([0-5]) punti \+ SuperStar\s+(-|[\d.]+(?:,\d+)?\s*€)\s+([\d.]+)")
_RE_JACKPOT = re.compile(r"prossimo jackpot del SuperEnalotto è di\s*([\d.]+(?:,\d+)?)\s*€", re.I)
_RE_CAT = re.compile(r"(6 punti|5 punti \+ Jolly|5 punti|4 punti|3 punti|2 punti)\s+(-|[\d.]+(?:,\d+)?\s*€)\s+([\d.]+)")


@dataclass
class Vincite:
    data: str                 # AAAA-MM-GG
    p6: int = 0
    p51: int = 0
    p5: int = 0
    p4: int = 0
    p3: int = 0
    p2: int | None = None
    premio6: str = ""         # come scritto sul sito (euro; prima del 2002 in lire)
    # quote (premio per vincitore) in EURO; None = non nota. Prima del 2002 il sito riporta lire: convertite
    q6: float | None = None
    q51: float | None = None
    q5: float | None = None
    q4: float | None = None
    q3: float | None = None
    q2: float | None = None
    qs: dict | None = None    # SuperStar: {"5": quota, "4": ..., "0": ...} in euro

    @property
    def vinto_6(self) -> bool:
        return self.p6 > 0


def analizza_pagina(html: str, d: date) -> Vincite | None:
    testo = re.sub(r"<(script|style).*?</\1>", " ", html, flags=re.S | re.I)
    testo = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", testo)))
    i = testo.find("Quote SuperEnalotto")
    if i < 0:
        return None
    fine = testo.find("Quote SuperStar", i)
    sezione = testo[i:fine if fine > 0 else i + 2000]
    v = Vincite(data=d.isoformat())
    visti = set()
    for m in _RE_CAT.finditer(sezione):
        nome = m.group(1)
        if nome in visti:
            continue
        visti.add(nome)
        campo = dict(CATEGORIE)[nome]
        setattr(v, campo, int(m.group(3).replace(".", "")))
        setattr(v, "q" + campo[1:], _importo(m.group(2), d))
        if campo == "p6" and m.group(2) != "-":
            v.premio6 = m.group(2).strip()
    if fine > 0:
        ss = {}
        for m in _RE_SS.finditer(testo[fine:fine + 1500]):
            q = _importo(m.group(2), d)
            if m.group(1) not in ss and q is not None:
                ss[m.group(1)] = q
        v.qs = ss or None
    return v if "6 punti" in visti else None


def _importo(s: str, d: date) -> float | None:
    s = s.replace("€", "").strip()
    if not s or s == "-":
        return None
    try:
        x = float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return None
    return round(x / LIRE_PER_EURO, 2) if d.year < 2002 else x


def jackpot_da_pagina(html: str) -> float | None:
    """Il jackpot del prossimo concorso scritto nelle pagine di superenalotto.com."""
    testo = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))
    m = _RE_JACKPOT.search(testo) or re.search(r"JACKPOT\s+([\d.]+(?:,\d+)?)\s*€", testo)
    if not m:
        return None
    return float(m.group(1).replace(".", "").replace(",", "."))


def quota(v: "Vincite", categoria: str) -> float | None:
    """Quota in euro di una categoria ("6", "5+1", "5", "4", "3", "2" oppure "SS3" = 3 punti + SuperStar)."""
    if categoria.startswith("SS"):
        return (v.qs or {}).get(categoria[2:])
    return getattr(v, {"6": "q6", "5+1": "q51", "5": "q5", "4": "q4", "3": "q3", "2": "q2"}[categoria], None)


def scarica_concorso(d: date, timeout: int = 30) -> Vincite | None:
    req = urllib.request.Request(URL.format(d), headers=INTESTAZIONI)
    with urllib.request.urlopen(req, timeout=timeout, context=contesto_ssl()) as r:
        return analizza_pagina(r.read().decode("utf-8", errors="replace"), d)


def scarica(date_concorsi, avanzamento=None, interrompi=None, pausa: float = 0.25) -> dict[str, Vincite]:
    """Scarica le pagine dei concorsi indicati (una alla volta, con una piccola pausa per cortesia)."""
    out: dict[str, Vincite] = {}
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
            avanzamento(f"Vincitori del {d:%d/%m/%Y}", i + 1, len(date_concorsi))
        time.sleep(pausa)
    return out


# ------------------------------------------------------------------ memoria (archivio + file incluso)
def da_json(testo: str | None) -> dict[str, Vincite]:
    if not testo:
        return {}
    try:
        campi = set(Vincite.__dataclass_fields__)
        return {k: Vincite(**{a: b for a, b in v.items() if a in campi}) for k, v in json.loads(testo).items()}
    except Exception:
        return {}


def a_json(dati: dict[str, Vincite]) -> str:
    return json.dumps({k: asdict(v) for k, v in sorted(dati.items())}, separators=(",", ":"))


def incluse() -> dict[str, Vincite]:
    try:
        return da_json(FILE_INCLUSO.read_text(encoding="utf-8"))
    except OSError:
        return {}


def carica(archivio) -> dict[str, Vincite]:
    """Vincite note: file incluso nel programma + quelle scaricate dopo (salvate nell'archivio SE)."""
    dati = incluse()
    dati.update(da_json(archivio.leggi_impostazione(CHIAVE_DB)))
    return dati


def mancanti(archivio) -> list[date]:
    """Concorsi in archivio di cui non si conoscono ancora i vincitori o le quote (solo SuperEnalotto)."""
    if archivio.gioco.codice != "SE":
        return []
    noti = carica(archivio)
    return [e.data for e in archivio.tutte(True) if e.data.year >= 1998 and
            (e.data.isoformat() not in noti or noti[e.data.isoformat()].q3 is None)]


def salva(archivio, nuovi: dict[str, Vincite]) -> None:
    if not nuovi or archivio.gioco.codice != "SE":
        return
    propri = da_json(archivio.leggi_impostazione(CHIAVE_DB))
    propri.update(nuovi)
    archivio.scrivi_impostazione(CHIAVE_DB, a_json(propri))


def aggiorna(archivio, avanzamento=None, interrompi=None) -> int:
    """Scarica e salva i vincitori dei concorsi in archivio che non sono ancora noti. Solo SuperEnalotto."""
    da_fare = mancanti(archivio)
    if not da_fare:
        return 0
    nuovi = scarica(da_fare, avanzamento, interrompi)
    salva(archivio, nuovi)
    return len(nuovi)


def date_con_6(archivio) -> set[date]:
    return {date.fromisoformat(k) for k, v in carica(archivio).items() if v.vinto_6}
