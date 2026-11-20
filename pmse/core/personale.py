"""Colonne diverse per ogni utente: ogni installazione ha un codice personale casuale (creato la prima volta e
conservato con i dati) che entra nel calcolo di Magico Pensiero. A parità di archivio e impostazioni, due persone
ottengono colonne diverse; la stessa persona ottiene sempre le stesse (storico e verifiche restano coerenti).

La variazione sposta di poco i pesi delle voci e la nitidezza, aggiunge un lieve "rumore" agli spareggi tra le
candidate e cambia il seme del campionamento. Non cambia la probabilità di vincere, uguale per ogni colonna."""
from __future__ import annotations

import dataclasses
import secrets
import zlib

import numpy as np

CHIAVE_CODICE = "codice_personale"

# livello -> (variazione relativa dei pesi, della nitidezza, rumore sul voto in deviazioni standard)
LIVELLI = {"nessuna": (0.0, 0.0, 0.0), "moderata": (0.15, 0.10, 0.10), "media": (0.30, 0.20, 0.25),
           "forte": (0.50, 0.30, 0.50)}
NOMI_LIVELLI = {"nessuna": "Nessuna (uguale per tutti)", "moderata": "Moderata (consigliata)", "media": "Media",
                "forte": "Forte"}
# intensità dell'opzione «evita le colonne molto giocate»: percentile massimo di popolarità ammesso
POPOLARI = {"bassa": 60, "moderata": 40, "forte": 25}
NOMI_POPOLARI = {"bassa": "Bassa (scarta solo le più giocate)", "moderata": "Moderata (consigliata)",
                 "forte": "Forte (solo le meno giocate)"}


def codice(arch) -> str:
    """Il codice personale di questa installazione e di questo gioco (creato alla prima richiesta)."""
    c = arch.leggi_impostazione(CHIAVE_CODICE, "")
    if not c:
        c = secrets.token_hex(8)
        arch.scrivi_impostazione(CHIAVE_CODICE, c)
    return c


def rigenera(arch) -> str:
    """Nuovo codice: tutte le colonne future dell'utente cambiano."""
    c = secrets.token_hex(8)
    arch.scrivi_impostazione(CHIAVE_CODICE, c)
    return c


def mostra(c: str) -> str:
    """Il codice in forma breve e leggibile, per le impostazioni (non serve ricordarlo)."""
    c = c.upper()
    return "-".join(c[i:i + 4] for i in range(0, min(len(c), 8), 4))


def applica(arch, imp):
    """Mette nelle impostazioni il codice personale (da chiamare quando si caricano dall'archivio)."""
    imp.codice_personale = codice(arch)
    return imp


def _rng(imp, sale: str) -> np.random.Generator:
    return np.random.default_rng(zlib.crc32(f"{imp.codice_personale}|{sale}".encode()))


def attiva(imp) -> bool:
    return bool(getattr(imp, "codice_personale", "")) and getattr(imp, "variazione", "moderata") in LIVELLI \
        and LIVELLI[getattr(imp, "variazione", "moderata")][0] > 0


def variato(imp):
    """Copia delle impostazioni con pesi e nitidezza spostati in modo personale (l'originale non cambia)."""
    if not attiva(imp):
        return imp
    a, b, _ = LIVELLI[imp.variazione]
    rng = _rng(imp, "pesi")
    pesi = {k: max(0.0, w * (1 + a * float(rng.uniform(-1, 1)))) for k, w in sorted(imp.pesi.items())}
    somma_prima, somma_dopo = sum(imp.pesi.values()), sum(pesi.values())
    if somma_dopo > 0:
        pesi = {k: w * somma_prima / somma_dopo for k, w in pesi.items()}
    nit = max(0.5, imp.nitidezza * (1 + b * float(rng.uniform(-1, 1))))
    return dataclasses.replace(imp, pesi=pesi, nitidezza=nit)


def rumore(voto: np.ndarray, imp) -> np.ndarray:
    """Spareggi personali: piccolo disturbo sul voto delle candidate (in unità di deviazione standard)."""
    if not attiva(imp) or len(voto) < 2:
        return voto
    s = LIVELLI[imp.variazione][2]
    return voto + s * float(np.std(voto)) * _rng(imp, f"voto{len(voto)}").standard_normal(len(voto))


def per_seme(imp) -> str:
    """Le impostazioni come testo per il seme: senza il codice personale quando la variazione è spenta
    (così con «nessuna» tutti ottengono le stesse colonne)."""
    import json
    d = dataclasses.asdict(imp)
    if not attiva(imp):
        d["codice_personale"] = ""
    return json.dumps(d)
