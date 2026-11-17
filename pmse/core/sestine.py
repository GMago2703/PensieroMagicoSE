"""Confronto di sestine con l'archivio e ricerca di sestine con caratteristiche date.

Usa numpy: l'archivio è una matrice (estrazioni x 91) di 0/1, così i "punti"
di migliaia di sestine contro tutte le estrazioni si calcolano in un colpo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np

from .analisi import Storico, progressioni
from .gioco import SE, Gioco, gioco_di


def caratteristiche(s: list[int], g: Gioco = SE) -> dict:
    s = sorted(s)
    decine = [0] * g.decine
    for n in s:
        decine[(n - 1) // 10] += 1
    return {
        "somma": sum(s),
        "pari": sum(1 for n in s if n % 2 == 0),
        "alti": sum(1 for n in s if n > g.soglia_alti),
        "consecutivi": sum(1 for x, y in zip(s, s[1:]) if y - x == 1),
        "decine_diverse": sum(1 for d in decine if d),
        "max_stessa_decina": max(decine),
        "finali_diversi": len({n % 10 for n in s}),
        "sequenze": len(progressioni(s, 3, 10)),
    }


class IndiceArchivio:
    def __init__(self, storico: Storico):
        self.storico = storico
        self.gioco = gioco_di(storico)
        self.date: list[date] = [r[0] for r in storico]
        self.n = len(storico)
        self.m = np.zeros((self.n, self.gioco.n + 1), dtype=np.int16)
        self.jolly = np.zeros(self.n, dtype=np.int16)
        for i, r in enumerate(storico):
            self.m[i, r[1]] = 1
            self.jolly[i] = r[2] or 0
        self.chiavi = {tuple(r[1]) for r in storico}

    def vettori(self, sestine: list[list[int]]) -> np.ndarray:
        v = np.zeros((len(sestine), self.gioco.n + 1), dtype=np.int16)
        for i, s in enumerate(sestine):
            v[i, s] = 1
        return v

    def punti(self, sestine: list[list[int]]) -> np.ndarray:
        """Matrice (sestine x estrazioni) con i numeri indovinati."""
        if not self.n:
            return np.zeros((len(sestine), 0), dtype=np.int16)
        return self.vettori(sestine) @ self.m.T

    def confronta(self, sestina: list[int]) -> "Confronto":
        s = sorted(sestina)
        p = self.punti([s])[0] if self.n else np.zeros(0, dtype=np.int16)
        c = Confronto(sestina=s, caratteristiche=caratteristiche(s, self.gioco))
        for k in range(self.gioco.k + 1):
            c.distribuzione[k] = int((p == k).sum())
        c.max_punti = int(p.max()) if self.n else 0
        if self.n:
            idx = np.where(p == c.max_punti)[0]
            c.date_max = [self.date[i] for i in idx[-5:]][::-1]
            tre = np.where(p >= 3)[0]
            c.ultima_almeno3 = self.date[tre[-1]] if len(tre) else None
            c.ritardo_almeno3 = int(self.n - 1 - tre[-1]) if len(tre) else self.n
            if not self.gioco.is_ej:
                cinque = np.where(p == 5)[0]
                c.cinque_piu_jolly = int(sum(1 for i in cinque if self.jolly[i] in s))
        c.gia_uscita = tuple(s) in self.chiavi
        return c


@dataclass
class Confronto:
    sestina: list[int]
    caratteristiche: dict
    distribuzione: dict[int, int] = field(default_factory=dict)
    max_punti: int = 0
    date_max: list[date] = field(default_factory=list)
    ultima_almeno3: date | None = None
    ritardo_almeno3: int = 0
    cinque_piu_jolly: int = 0
    gia_uscita: bool = False


@dataclass
class Criteri:
    pool: list[int] = field(default_factory=lambda: list(range(1, 91)))   # numeri ammessi
    obbligatori: list[int] = field(default_factory=list)
    mai_uscita: bool = True
    max_punti_archivio: int = 6          # es. 3 = nessuna estrazione passata con 4 o più numeri in comune
    min_punti_archivio: int = 0          # es. 3 = deve aver già "fatto terno" almeno una volta
    somma_min: int = 21
    somma_max: int = 519
    pari_min: int = 0
    pari_max: int = 6
    alti_min: int = 0
    alti_max: int = 6
    consecutivi_max: int = 5
    max_stessa_decina: int = 6
    max_comuni_tra_risultati: int = 6    # quanti numeri possono condividere due sestine trovate


def cerca(indice: IndiceArchivio, criteri: Criteri, quante: int = 10, seed: int | None = None,
          max_tentativi: int = 400_000, pesi: dict[int, float] | None = None) -> tuple[list[list[int]], int]:
    """Genera combinazioni casuali (pesate se 'pesi' è dato) che rispettano i criteri.
    Restituisce (combinazioni trovate, combinazioni provate)."""
    g = indice.gioco
    K = g.k
    rng = np.random.default_rng(seed)
    obblig = sorted(set(criteri.obbligatori))
    pool = np.array(sorted(n for n in set(criteri.pool) - set(obblig) if 1 <= n <= g.n), dtype=np.int16)
    da_scegliere = K - len(obblig)
    if da_scegliere < 0 or len(pool) < da_scegliere:
        return [], 0
    p = None
    if pesi:
        w = np.array([max(pesi.get(int(n), 0.0), 1e-6) for n in pool], dtype=float)
        p = w / w.sum()
    trovate: list[list[int]] = []
    viste: set[tuple] = set()
    provate = 0
    lotto = 4000
    while len(trovate) < quante and provate < max_tentativi:
        if da_scegliere == 0:
            cand = np.tile(np.array(obblig, dtype=np.int16), (1, 1))
        elif p is None:
            chiavi = rng.random((lotto, len(pool)))
            scelte = pool[np.argpartition(chiavi, da_scegliere - 1, axis=1)[:, :da_scegliere]]
            cand = np.hstack([scelte, np.tile(np.array(obblig, dtype=np.int16), (lotto, 1))]) if obblig else scelte
        else:
            # campionamento pesato senza ripetizione (metodo Efraimidis-Spirakis)
            chiavi = rng.random((lotto, len(pool))) ** (1.0 / (p * len(pool)))
            scelte = pool[np.argpartition(-chiavi, da_scegliere - 1, axis=1)[:, :da_scegliere]]
            cand = np.hstack([scelte, np.tile(np.array(obblig, dtype=np.int16), (lotto, 1))]) if obblig else scelte
        cand = np.sort(cand, axis=1)
        provate += len(cand)
        somma = cand.sum(axis=1)
        pari = (cand % 2 == 0).sum(axis=1)
        alti = (cand > g.soglia_alti).sum(axis=1)
        cons = (np.diff(cand, axis=1) == 1).sum(axis=1)
        dec = (cand - 1) // 10
        max_dec = np.zeros(len(cand), dtype=np.int16)
        for d in range(g.decine):
            max_dec = np.maximum(max_dec, (dec == d).sum(axis=1))
        ok = ((somma >= criteri.somma_min) & (somma <= criteri.somma_max)
              & (pari >= criteri.pari_min) & (pari <= criteri.pari_max)
              & (alti >= criteri.alti_min) & (alti <= criteri.alti_max)
              & (cons <= criteri.consecutivi_max) & (max_dec <= criteri.max_stessa_decina))
        cand = cand[ok]
        if len(cand) and indice.n and (criteri.max_punti_archivio < K or criteri.min_punti_archivio > 0
                                       or criteri.mai_uscita):
            pm = indice.punti([list(map(int, c)) for c in cand]).max(axis=1)
            limite = min(criteri.max_punti_archivio, K - 1 if criteri.mai_uscita else K)
            cand = cand[(pm <= limite) & (pm >= criteri.min_punti_archivio)]
        for c in cand:
            t = tuple(int(x) for x in c)
            if t in viste:
                continue
            viste.add(t)
            if any(len(set(t) & set(f)) > criteri.max_comuni_tra_risultati for f in trovate):
                continue
            trovate.append(list(t))
            if len(trovate) >= quante:
                break
        if da_scegliere == 0:
            break
    return trovate, provate
