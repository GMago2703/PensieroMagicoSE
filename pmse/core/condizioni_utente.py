"""Le mie condizioni: condizioni scelte e battezzate dall'utente, conservate nell'archivio del gioco (SuperEnalotto ed
Eurojackpot hanno ciascuno le proprie) e attivabili in ogni sistema come tutte le altre.

Ogni voce: {id, nome, condizione (dati di una Condizione), creata}. La condizione può essere di qualunque tipo:
un insieme di numeri (Fisse), i Quadri, un filtro o una condizione standard con i valori scelti dall'utente."""
from __future__ import annotations

import json
import secrets
from dataclasses import asdict
from datetime import datetime

from .condizioni import Condizione

CHIAVE = "condizioni_utente"


def carica(arch, codici: tuple[str, ...] | None = None) -> list[dict]:
    try:
        voci = json.loads(arch.leggi_impostazione(CHIAVE, "") or "[]")
    except ValueError:
        voci = []
    voci = [v for v in voci if isinstance(v, dict) and "condizione" in v]
    if codici:
        voci = [v for v in voci if v["condizione"].get("codice") in codici]
    return voci


def _scrivi(arch, voci: list[dict]) -> None:
    arch.scrivi_impostazione(CHIAVE, json.dumps(voci))


def condizione(voce: dict) -> Condizione:
    """La condizione della voce, con il nome dell'utente (copia indipendente)."""
    d = dict(voce["condizione"])
    d["nome"] = voce.get("nome", d.get("nome", ""))
    d["attiva"] = True
    return Condizione(**{k: v for k, v in d.items() if k in Condizione.__dataclass_fields__})


def aggiungi(arch, nome: str, c: Condizione) -> dict:
    """Salva una condizione con un nome. Se il nome esiste già (stesso tipo) la sostituisce."""
    nome = (nome or "").strip() or f"Condizione del {datetime.now():%d/%m/%Y %H:%M}"
    d = asdict(c)
    d["nome"] = nome
    voci = carica(arch)
    for v in voci:
        if v["nome"].lower() == nome.lower() and v["condizione"].get("codice") == c.codice:
            v["condizione"] = d
            _scrivi(arch, voci)
            return v
    voce = {"id": secrets.token_hex(4), "nome": nome, "condizione": d, "creata": datetime.now().isoformat()}
    voci.append(voce)
    _scrivi(arch, voci)
    return voce


def elimina(arch, id_: str) -> None:
    _scrivi(arch, [v for v in carica(arch) if v["id"] != id_])


def rinomina(arch, id_: str, nome: str) -> None:
    voci = carica(arch)
    for v in voci:
        if v["id"] == id_:
            v["nome"] = nome.strip() or v["nome"]
            v["condizione"]["nome"] = v["nome"]
    _scrivi(arch, voci)


def duplica(arch, id_: str) -> dict | None:
    for v in carica(arch):
        if v["id"] == id_:
            return aggiungi(arch, v["nome"] + " (copia)", condizione(v))
    return None
