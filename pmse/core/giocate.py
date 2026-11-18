"""Registro delle giocate e simulatore "E se avessi giocato…".

Una giocata: colonne giocate (con SuperStar o Euronumeri), primo concorso, quanti concorsi, costo.
Lo spoglio usa l'archivio delle estrazioni; gli importi vengono dalle quote reali di ogni concorso
(SuperEnalotto: superenalotto.com, Eurojackpot: euro-jackpot.net). Se una quota non è nota la vincita
è segnata "da verificare". SuperEnalotto ed Eurojackpot hanno registri separati (archivi separati).
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime

import numpy as np

from . import sistemi as sis
from .gioco import Gioco

CHIAVE = "giocate"
ORDINE_SE = ["6", "5+1", "5", "4", "3", "2"] + [f"SS{k}" for k in (5, 4, 3, 2, 1, 0)]
ORDINE_EJ = ["5+2", "5+1", "5+0", "4+2", "4+1", "4+0", "3+2", "2+2", "3+1", "3+0", "1+2", "2+1"]


def nome_categoria(c: str) -> str:
    if c.startswith("SS"):
        return f"{c[2:]} punti + SuperStar"
    if "+" in c and c not in ("5+1",):
        a, b = c.split("+")
        return f"{a} + {b}" if b != "0" else f"{a} numeri"
    return {"5+1": "5 + Jolly"}.get(c, f"{c} punti")


@dataclass
class Giocata:
    gioco: str
    colonne: list[list[int]]
    extra: list[list[int]] = field(default_factory=list)   # per colonna: SE [SuperStar] o []; EJ [e1, e2]
    dal: str = ""                       # data (AAAA-MM-GG) del primo concorso giocato
    concorsi: int = 1                   # quanti concorsi consecutivi
    costo: float = 0.0                  # costo per concorso
    nome: str = ""
    origine: str = ""
    note: str = ""
    vinto_manuale: float | None = None  # se l'utente scrive lui quanto ha incassato
    controllata: str = ""               # ultima estrazione già controllata (per gli avvisi)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    creata: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    @property
    def costo_totale(self) -> float:
        return self.costo * self.concorsi


def costo_giocata(g: Gioco, colonne, extra, prezzi: dict | None = None) -> float:
    prezzi = prezzi or {}
    if g.is_ej:
        return sis.costo(len(colonne), g, prezzi)
    con_ss = sum(1 for e in extra if e)
    return sis.costo(len(colonne) - con_ss, g, prezzi) + sis.costo(con_ss, g, prezzi, superstar=True)


# ------------------------------------------------------------------ memoria
def carica(archivio) -> list[Giocata]:
    try:
        d = json.loads(archivio.leggi_impostazione(CHIAVE) or "[]")
    except ValueError:
        d = []
    campi = set(Giocata.__dataclass_fields__)
    return [Giocata(**{k: v for k, v in x.items() if k in campi}) for x in d]


def salva_tutte(archivio, giocate: list[Giocata]) -> None:
    archivio.scrivi_impostazione(CHIAVE, json.dumps([asdict(x) for x in giocate], ensure_ascii=False))


def aggiungi(archivio, giocata: Giocata) -> None:
    tutte = carica(archivio)
    tutte.append(giocata)
    salva_tutte(archivio, tutte)


def elimina(archivio, id_: str) -> None:
    salva_tutte(archivio, [x for x in carica(archivio) if x.id != id_])


# ------------------------------------------------------------------ spoglio
@dataclass
class Vincita:
    data: date
    colonna: int
    categoria: str
    importo: float | None       # None = quota non nota


@dataclass
class Esito:
    concorsi_estratti: list[date]
    concorsi_mancanti: int
    vincite: list[Vincita]
    spesa: float

    @property
    def vinto(self) -> float:
        return sum(v.importo or 0 for v in self.vincite)

    @property
    def da_verificare(self) -> int:
        return sum(1 for v in self.vincite if v.importo is None)

    def per_categoria(self) -> dict[str, tuple[int, float]]:
        out: dict[str, list] = {}
        for v in self.vincite:
            x = out.setdefault(v.categoria, [0, 0.0])
            x[0] += 1
            x[1] += v.importo or 0
        return {k: (a, b) for k, (a, b) in out.items()}

    def migliore(self) -> Vincita | None:
        return max(self.vincite, key=lambda v: v.importo or 0, default=None)


class Quote:
    """Quote reali per data e categoria, dal modulo vincite (SE) o vincite_ej (EJ)."""

    def __init__(self, archivio=None, g: Gioco | None = None, dati: dict | None = None):
        self.g = g or archivio.gioco
        if dati is None and archivio is not None:
            if self.g.is_ej:
                from . import vincite_ej
                dati = vincite_ej.carica(archivio)
            else:
                from . import vincite
                dati = vincite.carica(archivio)
        self.dati = dati or {}

    def __call__(self, d: date, categoria: str) -> float | None:
        v = self.dati.get(d.isoformat())
        if v is None:
            return None
        if self.g.is_ej:
            return v.quote.get(categoria)
        from . import vincite
        return vincite.quota(v, categoria)


def categorie(g: Gioco, colonne: np.ndarray, extra, righe) -> list[tuple[int, int, str]]:
    """(indice estrazione, indice colonna, categoria) delle colonne vincenti nelle estrazioni 'righe'
    (righe = (data, numeri ordinati, jolly/euro1, superstar/euro2, ...))."""
    if not len(righe) or not len(colonne):
        return []
    M = np.zeros((len(righe), g.n + 1), dtype=bool)
    for i, r in enumerate(righe):
        M[i, r[1]] = True
    C = np.asarray(colonne, dtype=np.int64)
    punti = M[:, C].sum(axis=2)                          # estrazioni × colonne
    out = []
    if g.is_ej:
        e1 = np.array([r[2] or 0 for r in righe])
        e2 = np.array([r[3] or 0 for r in righe])
        ex = [list(x) if x else [] for x in (extra or [[]] * len(C))]
        for j in range(len(C)):
            eu = np.zeros(len(righe), dtype=int)
            for x in ex[j] if j < len(ex) else []:
                eu += (e1 == x) | (e2 == x)
            for i in np.flatnonzero(punti[:, j] >= 1):
                c = f"{punti[i, j]}+{eu[i]}"
                if c in ORDINE_EJ:
                    out.append((int(i), j, c))
        return out
    jolly = np.array([r[2] or 0 for r in righe])
    ss = np.array([r[3] or 0 for r in righe])
    for j in range(len(C)):
        sj = (extra[j][0] if extra and j < len(extra) and extra[j] else None)
        hj = np.isin(jolly, C[j])
        for i in range(len(righe)):
            p = int(punti[i, j])
            if sj and ss[i] == sj and p < 6:
                out.append((i, j, f"SS{p}"))
            elif p == 6:
                out.append((i, j, "6"))
            elif p == 5:
                out.append((i, j, "5+1" if hj[i] else "5"))
            elif p >= 2:
                if p == 2 and righe[i][0] < date(2016, 2, 1):      # il premio "2 punti" esiste dal 2016
                    continue
                out.append((i, j, str(p)))
    return out


def esito(g: Gioco, giocata: Giocata, righe_archivio, quote: Quote | None = None) -> Esito:
    """Spoglio della giocata sui concorsi già estratti tra quelli giocati."""
    dal = date.fromisoformat(giocata.dal) if giocata.dal else date.min
    giocate = [r for r in righe_archivio if r[0] >= dal][:giocata.concorsi]
    viste = categorie(g, giocata.colonne, giocata.extra, giocate)
    vinc = [Vincita(giocate[i][0], j, c, quote(giocate[i][0], c) if quote else None) for i, j, c in viste]
    return Esito([r[0] for r in giocate], giocata.concorsi - len(giocate), vinc,
                 giocata.costo * len(giocate))


def nuove_vincite(g: Gioco, giocate: list[Giocata], righe_archivio, quote: Quote | None = None):
    """Per gli avvisi dopo l'aggiornamento: estrazioni nuove (dopo 'controllata') con le loro vincite.
    Restituisce [(giocata, [Vincita...], estrazioni_controllate)] e aggiorna 'controllata'."""
    out = []
    for gi in giocate:
        e = esito(g, gi, righe_archivio, quote)
        nuove = [d for d in e.concorsi_estratti if d.isoformat() > (gi.controllata or "")]
        if nuove:
            v = [x for x in e.vincite if x.data.isoformat() > (gi.controllata or "")]
            out.append((gi, v, nuove))
            gi.controllata = max(d.isoformat() for d in nuove)
    return out


# ------------------------------------------------------------------ simulatore
@dataclass
class Simulazione:
    estrazioni: int
    spesa: float
    vincite: list[Vincita]
    per_anno: dict[int, tuple[float, float]]           # anno -> (spesa, vinto)
    dal: date | None
    al: date | None

    @property
    def vinto(self) -> float:
        return sum(v.importo or 0 for v in self.vincite)

    @property
    def da_verificare(self) -> int:
        return sum(1 for v in self.vincite if v.importo is None)

    def per_categoria(self) -> dict[str, tuple[int, float]]:
        return Esito([], 0, self.vincite, 0).per_categoria()


def simula(g: Gioco, colonne, extra, righe_archivio, dal: date, al: date, quote: Quote | None,
           costo_per_concorso: float) -> Simulazione:
    righe = [r for r in righe_archivio if dal <= r[0] <= al]
    viste = categorie(g, colonne, extra, righe)
    vinc = [Vincita(righe[i][0], j, c, quote(righe[i][0], c) if quote else None) for i, j, c in viste]
    per_anno: dict[int, list] = {}
    for r in righe:
        per_anno.setdefault(r[0].year, [0.0, 0.0])[0] += costo_per_concorso
    for v in vinc:
        per_anno.setdefault(v.data.year, [0.0, 0.0])[1] += v.importo or 0
    return Simulazione(len(righe), costo_per_concorso * len(righe), vinc,
                       {k: (a, b) for k, (a, b) in sorted(per_anno.items())},
                       righe[0][0] if righe else None, righe[-1][0] if righe else None)


def prossimo_concorso(g: Gioco, ultima: date | None, oggi: date | None = None) -> date:
    """Data del prossimo concorso secondo i giorni abituali di estrazione."""
    from datetime import timedelta
    oggi = oggi or date.today()
    d = max(oggi, (ultima + timedelta(days=1)) if ultima else oggi)
    while d.weekday() not in g.giorni_estrazione:
        d += timedelta(days=1)
    return d
