"""Lettura di combinazioni scritte o incollate come testo.

Riconosce il numero d'ordine iniziale ("1)", "2.", "#3"), le parole "Sistema", "Sestina", ecc. e le parti
speciali: "SuperStar 42", "Jolly 7", "Euronumeri 3 9" (o "+ 3 9" dopo i numeri principali dell'Eurojackpot),
così un testo copiato dal programma o da un'altra fonte si può incollare senza errori.
"""
from __future__ import annotations

import re

_ORDINE = re.compile(r"^\s*(?:#\s*)?\d{1,3}\s*[).:\]-]\s+")
_SPECIALI = re.compile(r"(superstar|super star|ss|jolly|euronumer[oi]|euro)\s*:?\s*((?:\d{1,2}[\s,;-]*){1,2})", re.I)


def leggi_riga(riga: str, k: int) -> tuple[list[int], dict[str, list[int]]] | None:
    """Numeri principali e parti speciali di una riga. None se la riga non contiene numeri."""
    r = _ORDINE.sub("", riga)
    speciali: dict[str, list[int]] = {}
    for m in _SPECIALI.finditer(r):
        nome = m.group(1).lower()
        nome = "superstar" if nome in ("superstar", "super star", "ss") else (
            "jolly" if nome == "jolly" else "euro")
        speciali[nome] = [int(x) for x in re.findall(r"\d+", m.group(2))]
    r = _SPECIALI.sub(" ", r)
    if "+" in r:                       # Eurojackpot: "3 15 27 44 49 + 2 11"
        a, b = r.split("+", 1)
        euro = [int(x) for x in re.findall(r"\d+", b)]
        if euro:
            speciali.setdefault("euro", euro)
        r = a
    numeri = [int(x) for x in re.findall(r"\d+", r)]
    if not numeri and not speciali:
        return None
    return numeri, speciali


def numeri_da_testo(t: str) -> list[int]:
    """Tutti i numeri principali di un testo (una o più righe), senza ordine, SuperStar, Jolly, Euronumeri."""
    out = []
    for riga in t.splitlines():
        x = leggi_riga(riga, 6)
        if x:
            out += x[0]
    return out
