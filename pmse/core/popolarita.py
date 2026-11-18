"""Popolarità delle combinazioni: quanto è "giocata" una combinazione (SuperEnalotto).

La probabilità di vincere è identica per ogni combinazione. Ma se una combinazione è giocata da
molte persone, in caso di vincita il premio si divide tra tutte. Evitare le combinazioni molto
giocate è quindi l'unico vantaggio reale che la matematica concede: non si vince più spesso, ma
quando si vince si vince di più.

Come si stima: per ogni concorso passato si conosce quanto era giocata la sestina estratta
(vincitori di 3 punti rispetto ai concorsi vicini, vedi analisi_sei.popolarita). Una regressione
(ridge) ricava da questi dati quanto pesa ciascuno dei 90 numeri e le coppie di numeri consecutivi.
La bontà del modello si misura su concorsi tenuti da parte (R² fuori campione).
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass

import numpy as np

CHIAVE = "popolarita_modello"


def _riga(comb, N: int = 90) -> np.ndarray:
    x = np.zeros(N + 2)
    s = sorted(int(v) for v in comb)
    for n in s:
        x[n - 1] = 1.0
    x[N] = sum(1 for a, b in zip(s, s[1:]) if b - a == 1)      # coppie consecutive
    x[N + 1] = 1.0                                               # intercetta
    return x


@dataclass
class ModelloPopolarita:
    pesi: list[float]               # 90 numeri + consecutivi + intercetta (scala logaritmica)
    r2: float                       # bontà fuori campione (0 = inutile, 1 = perfetto)
    concorsi: int
    quantili: list[float]           # 101 quantili del punteggio di combinazioni casuali
    firma: str = ""                 # quali dati sono stati usati (per sapere quando ricalcolare)

    def log_punteggio(self, comb) -> float:
        return float(_riga(comb) @ np.array(self.pesi))

    def indice(self, comb) -> float:
        """Popolarità stimata: 1 = come una combinazione media, 1.3 = giocata il 30% più della media."""
        return math.exp(self.log_punteggio(comb) - self.quantili[50])

    def percentile(self, comb) -> int:
        """0-100: percentuale di combinazioni casuali meno giocate di questa."""
        return int(np.searchsorted(np.array(self.quantili), self.log_punteggio(comb)))

    def percentili(self, cand: np.ndarray) -> np.ndarray:
        X = np.zeros((len(cand), 92))
        idx = np.asarray(cand, dtype=np.int64) - 1
        np.put_along_axis(X, idx, 1.0, axis=1)
        s = np.sort(np.asarray(cand), axis=1)
        X[:, 90] = (np.diff(s, axis=1) == 1).sum(axis=1)
        X[:, 91] = 1.0
        return np.searchsorted(np.array(self.quantili), X @ np.array(self.pesi))

    def numeri(self) -> list[tuple[int, float]]:
        """I 90 numeri dal più giocato al meno giocato (effetto in %)."""
        return sorted(((n + 1, (math.exp(self.pesi[n]) - 1) * 100) for n in range(90)), key=lambda t: -t[1])

    def a_json(self) -> str:
        return json.dumps(asdict(self))

    @staticmethod
    def da_json(t: str | None) -> "ModelloPopolarita | None":
        try:
            return ModelloPopolarita(**json.loads(t)) if t else None
        except Exception:
            return None


def costruisci(estrazioni, vinc, lam: float = 8.0) -> ModelloPopolarita:
    from .analisi_sei import popolarita
    estrazioni = sorted(estrazioni, key=lambda e: e.data)
    pop = popolarita(estrazioni, vinc)
    dati = [(e.numeri, pop[e.data]) for e in estrazioni if e.data in pop and pop[e.data] > 0]
    if len(dati) < 300:
        raise ValueError("Servono i vincitori di almeno 300 concorsi per stimare la popolarità.")
    X = np.array([_riga(c) for c, _ in dati])
    y = np.log(np.array([v for _, v in dati]))
    y = np.clip(y, -1.5, 1.5)                                # concorsi eccezionali non devono dominare

    def stima(Xa, ya):
        pen = np.eye(X.shape[1]) * lam
        pen[-1, -1] = 0                                      # l'intercetta non si penalizza
        return np.linalg.solve(Xa.T @ Xa + pen, Xa.T @ ya)

    # bontà fuori campione: 5 gruppi alternati
    pieghe = np.arange(len(y)) % 5
    prev = np.zeros_like(y)
    for k in range(5):
        w = stima(X[pieghe != k], y[pieghe != k])
        prev[pieghe == k] = X[pieghe == k] @ w
    r2 = 1 - ((y - prev) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    w = stima(X, y)
    rng = np.random.default_rng(3)
    casuali = np.sort(np.argsort(rng.random((20000, 90)), axis=1)[:, :6] + 1, axis=1)
    m = ModelloPopolarita(list(map(float, w)), float(r2), len(y), [], "")
    punteggi = np.array([m.log_punteggio(c) for c in casuali[:5000]])
    m.quantili = [float(q) for q in np.percentile(punteggi, np.arange(101))]
    return m


def per_archivio(archivio) -> ModelloPopolarita | None:
    """Modello del SuperEnalotto, ricalcolato solo quando cambiano i dati delle vincite. None per l'EJ."""
    if archivio.gioco.codice != "SE":
        return None
    from . import vincite
    vinc = vincite.carica(archivio)
    firma = f"{len(vinc)}-{max(vinc) if vinc else ''}"
    m = ModelloPopolarita.da_json(archivio.leggi_impostazione(CHIAVE))
    if m and m.firma == firma:
        return m
    try:
        m = costruisci(archivio.tutte(True), vinc)
    except ValueError:
        return None
    m.firma = firma
    archivio.scrivi_impostazione(CHIAVE, m.a_json())
    return m
