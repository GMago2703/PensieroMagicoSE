"""Ridotti immediati: riduzioni a garanzia già calcolate (con la massima cura) e incluse nel programma.

Ogni riduzione è salvata come schema di posizioni (0 = primo numero scelto, ...): basta inserire i numeri
e il sistema è pronto all'istante. Le fisse occupano le prime posizioni e sono in ogni colonna.
Chiave: "k/n/f/punti" (es. "6/10/0/5" = SuperEnalotto, 10 numeri, nessuna fissa, garanzia 5 se 6).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

FILE = Path(__file__).resolve().parent.parent / "dati" / "ridotti_pronti.json"
NUMERI = {6: range(7, 21), 5: range(6, 21)}       # quanti numeri giocati (SE: 7-20, EJ: 6-20)
FISSE = range(0, 5)


def chiave(k: int, n: int, f: int, punti: int) -> str:
    return f"{k}/{n}/{f}/{punti}"


@lru_cache(maxsize=1)
def tabella() -> dict[str, list[list[int]]]:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except OSError:
        return {}


def disponibili(k: int) -> list[tuple[int, int, int, int]]:
    """(numeri, fisse, punti garantiti, colonne) delle riduzioni pronte per un gioco con k numeri."""
    out = []
    for c, schema in tabella().items():
        kk, n, f, p = map(int, c.split("/"))
        if kk == k:
            out.append((n, f, p, len(schema)))
    return sorted(out)


def applica(numeri, fisse, k: int, punti: int) -> np.ndarray | None:
    fisse = sorted(set(fisse))
    resto = sorted(set(numeri) - set(fisse))
    ordine = fisse + resto
    schema = tabella().get(chiave(k, len(ordine), len(fisse), punti))
    if schema is None:
        return None
    C = np.array([[ordine[i] for i in col] for col in schema], dtype=np.int16)
    C.sort(axis=1)
    return C


def calcola(k: int, n: int, f: int, punti: int, tentativi: int = 12, qualita: int = 24) -> list[list[int]]:
    """Calcolo (lento, una volta sola) di una riduzione sugli indici 0..n-1, fisse = 0..f-1."""
    from . import sistemi
    numeri = list(range(1, n + 1))
    C = np.vstack(list(sistemi.integrale(numeri, k, list(range(1, f + 1)))))
    best = sistemi.riduci(C, punti, 1)
    for t in range(tentativi):
        q = (2, 4, 8, 16, 32, qualita)[t % 6]
        R = sistemi.riduci(C, punti, q, seme=t + 1)
        if len(R) < len(best):
            best = R
    return [[int(x) - 1 for x in col] for col in best]
