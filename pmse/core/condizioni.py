"""Condizioni per i sistemi condizionati.

Ogni condizione assegna a ogni colonna (combinazione ordinata) un VALORE numerico, per esempio
"quanti numeri pari" o "somma". Nel sistema si scelgono i valori accettati (elenco o intervallo).
Una colonna che non rispetta una condizione fa un "errore"; il sistema accetta le colonne con un
numero di errori compreso tra errori minimi e massimi (di solito 0-0: tutte rispettate).

Tutto è vettoriale (numpy): si filtrano milioni di colonne in pochi secondi.

Per ogni condizione c'è anche l'ANALISI sull'archivio: come si è distribuito quel valore nelle
estrazioni reali, quanto ci si aspetta dal caso e un SUGGERIMENTO (il valore più frequente e i
valori che coprono la gran parte delle estrazioni).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from itertools import combinations

import numpy as np

from .gioco import SE, Gioco

PRIMI = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89}


# ------------------------------------------------------------------ contesto (dati dall'archivio)
@dataclass
class Contesto:
    gioco: Gioco = SE
    estrazioni: list = field(default_factory=list)       # Estrazione in ordine di data
    popolarita: object = None                             # ModelloPopolarita (solo SE) o None
    _sotto: dict = field(default_factory=dict)

    @property
    def ultime(self):
        return [sorted(e.numeri) for e in self.estrazioni]

    def sottoinsiemi(self, t: int, finestra: int = 0) -> np.ndarray:
        """Codici dei t-sottoinsiemi di tutte le estrazioni (o delle ultime 'finestra')."""
        chiave = (t, finestra)
        if chiave not in self._sotto:
            righe = self.ultime[-finestra:] if finestra else self.ultime
            codici = set()
            for r in righe:
                for s in combinations(r, t):
                    codici.add(_codice(s))
            self._sotto[chiave] = np.fromiter(codici, dtype=np.int64, count=len(codici))
        return self._sotto[chiave]

    def ritardi(self) -> np.ndarray:
        """Ritardo attuale di ogni numero (indice 1..N)."""
        N = self.gioco.n
        rit = np.zeros(N + 1, dtype=np.int64)
        visto = np.zeros(N + 1, dtype=bool)
        for i, r in enumerate(reversed(self.ultime)):
            for x in r:
                if not visto[x]:
                    visto[x] = True
                    rit[x] = i
        rit[~visto] = len(self.estrazioni)
        return rit


def _codice(nums) -> int:
    c = 0
    for x in nums:
        c = c * 128 + int(x)
    return c


def _codici_sotto(C: np.ndarray, t: int) -> np.ndarray:
    """Per ogni colonna, i codici di tutti i suoi t-sottoinsiemi: matrice m x C(k,t)."""
    k = C.shape[1]
    out = []
    for idx in combinations(range(k), t):
        c = np.zeros(len(C), dtype=np.int64)
        for j in idx:
            c = c * 128 + C[:, j].astype(np.int64)
        out.append(c)
    return np.stack(out, axis=1)


# ------------------------------------------------------------------ funzioni valore (vettoriali)
def _diff(C):
    return np.diff(C, axis=1)


def _distinti(M):
    S = np.sort(M, axis=1)
    return 1 + (np.diff(S, axis=1) != 0).sum(axis=1)


def _coppie_diff(C):
    k = C.shape[1]
    i, j = np.triu_indices(k, 1)
    return C[:, j] - C[:, i]


def v_somma(C, ctx, p):
    return C.sum(axis=1)


def v_pari(C, ctx, p):
    return (C % 2 == 0).sum(axis=1)


def v_consecutivi(C, ctx, p):
    return (_diff(C) == 1).sum(axis=1)


def v_sequenze(C, ctx, p):
    d = _diff(C) == 1
    inizi = d[:, 0].astype(int)
    if d.shape[1] > 1:
        inizi = inizi + (d[:, 1:] & ~d[:, :-1]).sum(axis=1)
    return inizi


def v_cifre(C, ctx, p):
    return _distinti(C % 10)


def v_differenziata(C, ctx, p):
    return (_coppie_diff(C) == max(2, int(p or 2))).sum(axis=1)


def v_presenza_distanze(C, ctx, p):
    return _distinti(_diff(C))


def v_distanza_globale(C, ctx, p):
    return C[:, -1] - C[:, 0]


def v_distanza_massima(C, ctx, p):
    return _diff(C).max(axis=1)


def v_decine(C, ctx, p):
    return _distinti((C - 1) // 10)


def v_simmetrie(C, ctx, p):
    N = ctx.gioco.n
    k = C.shape[1]
    i, j = np.triu_indices(k, 1)
    return (C[:, i] + C[:, j] == N + 1).sum(axis=1)


def v_alti(C, ctx, p):
    return (C > ctx.gioco.n // 2).sum(axis=1)


def v_primi(C, ctx, p):
    return np.isin(C, list(PRIMI)).sum(axis=1)


def v_ultima(C, ctx, p):
    if not ctx.estrazioni:
        return np.zeros(len(C), dtype=int)
    ult = sorted(ctx.estrazioni[-1].numeri)
    return np.isin(C, ult).sum(axis=1)


def v_ripetizioni(C, ctx, p):
    """Massimo di numeri in comune con una qualsiasi estrazione dell'archivio (tutte o le ultime p)."""
    finestra = int(p or 0)
    k = C.shape[1]
    out = np.full(len(C), min(2, k), dtype=int)
    for t in range(3, k + 1):
        presenti = np.isin(_codici_sotto(C, t), ctx.sottoinsiemi(t, finestra)).any(axis=1)
        out[presenti] = t
    return out


def v_ritardatari(C, ctx, p):
    soglia = int(p or 30)
    rit = ctx.ritardi()
    return (rit[C] >= soglia).sum(axis=1)


def v_popolarita(C, ctx, p):
    if ctx.popolarita is None:
        return np.full(len(C), 50, dtype=int)
    return np.asarray(ctx.popolarita.percentili(C), dtype=int) // 10 * 10        # decine di percentile


def v_posizione(C, ctx, p):
    return C[:, int(p or 1) - 1]


@dataclass
class TipoCondizione:
    codice: str
    nome: str
    descrizione: str
    funzione: object
    modo: str = "valori"           # "valori" (elenco) o "intervallo"
    param_nome: str = ""           # parametro facoltativo
    param_min: int = 0
    param_max: int = 0
    param_def: int = 0
    menu: str = ""                 # voce del menu Condizioni che la apre
    solo: str = ""                 # "SE" se vale solo per il SuperEnalotto


TIPI: list[TipoCondizione] = [
    TipoCondizione("somme", "Somme", "Somma dei numeri della colonna.", v_somma, "intervallo", menu="Somme"),
    TipoCondizione("consecutivi", "Consecutività numerica", "Quante coppie di numeri consecutivi (es. 14-15).",
                   v_consecutivi, menu="Consecutività numerica"),
    TipoCondizione("sequenze", "Numero di sequenze", "Quanti blocchi di numeri consecutivi (es. 3-4-5 e 20-21 = 2).",
                   v_sequenze, menu="Numero di sequenze"),
    TipoCondizione("pari", "Pari e dispari", "Quanti numeri pari (gli altri sono dispari).", v_pari,
                   menu="Pari e dispari"),
    TipoCondizione("cifre", "Numero di cifre", "Quante cifre finali diverse (es. 3, 13, 23 hanno la stessa cifra 3).",
                   v_cifre, menu="Numero di cifre"),
    TipoCondizione("differenziata", "Consecutività differenziata",
                   "Quante coppie di numeri distano esattamente d (es. d=2: 10 e 12).", v_differenziata,
                   param_nome="Distanza d", param_min=2, param_max=20, param_def=2,
                   menu="Consecutività differenziata"),
    TipoCondizione("presenza_distanze", "Presenza delle distanze",
                   "Quante distanze diverse tra numeri vicini (in ordine crescente).", v_presenza_distanze,
                   menu="Presenza delle distanze"),
    TipoCondizione("distanza_globale", "Distanze globali", "Distanza tra il numero più piccolo e il più grande.",
                   v_distanza_globale, "intervallo", menu="Distanze globali"),
    TipoCondizione("distanza_massima", "Distanze specifiche",
                   "La distanza più grande tra due numeri vicini (in ordine crescente).", v_distanza_massima,
                   "intervallo", menu="Distanze specifiche"),
    TipoCondizione("posizione", "Posizioni",
                   "Valore del numero in una posizione (in ordine crescente): 1ª = il più piccolo.", v_posizione,
                   "intervallo", param_nome="Posizione", param_min=1, param_max=6, param_def=1, menu="Posizioni"),
    TipoCondizione("decine", "Interruzioni (decine occupate)",
                   "Quante decine diverse (1-10, 11-20, ...) sono occupate.", v_decine, menu="Interruzioni"),
    TipoCondizione("simmetrie", "Simmetrie", "Quante coppie di numeri simmetrici (la cui somma è N+1, es. 1 e 90).",
                   v_simmetrie, menu="Simmetrie"),
    TipoCondizione("ripetizioni", "Ripetizioni (in comune con l'archivio)",
                   "Massimo di numeri in comune con una qualsiasi estrazione passata (0 = tutte le estrazioni, "
                   "altrimenti le ultime N).", v_ripetizioni, param_nome="Ultime estrazioni (0 = tutte)",
                   param_min=0, param_max=5000, param_def=0, menu="Ripetizioni"),
    TipoCondizione("ultima", "Ripetizioni dall'ultima estrazione", "Quanti numeri dell'ultima estrazione.",
                   v_ultima, menu="Ripetizioni"),
    TipoCondizione("ritardatari", "Ritardi e IC", "Quanti numeri hanno un ritardo attuale di almeno R estrazioni.",
                   v_ritardatari, param_nome="Ritardo R", param_min=1, param_max=500, param_def=30,
                   menu="Ritardi e IC"),
    TipoCondizione("alti", "Combinazioni speciali: numeri alti", "Quanti numeri nella metà alta (46-90 / 26-50).",
                   v_alti, menu="Combinazioni speciali"),
    TipoCondizione("primi", "Combinazioni speciali: numeri primi", "Quanti numeri primi.", v_primi,
                   menu="Combinazioni speciali"),
    TipoCondizione("popolarita", "Popolarità (quanto è giocata)",
                   "Percentile di popolarità stimato (0 = tra le meno giocate, 90 = tra le più giocate), a decine.",
                   v_popolarita, menu="Personalizzata", solo="SE"),
]
TIPI_PER_CODICE = {t.codice: t for t in TIPI}


def tipi_del_gioco(g: Gioco) -> list[TipoCondizione]:
    return [t for t in TIPI if not t.solo or t.solo == g.codice]


# ------------------------------------------------------------------ impostazione di una condizione
@dataclass
class Condizione:
    codice: str
    attiva: bool = True
    valori: list[int] = field(default_factory=list)   # modo "valori": valori accettati
    minimo: int = 0                                    # modo "intervallo"
    massimo: int = 0
    param: int = 0
    # gruppi (Fisse, Sequele) e filtro combinazioni hanno dati propri
    numeri: list[int] = field(default_factory=list)
    combinazioni: list[list[int]] = field(default_factory=list)

    @property
    def tipo(self):
        return TIPI_PER_CODICE.get(self.codice)

    def descrivi(self) -> str:
        if self.codice == "gruppo":
            return f"Gruppo {sorted(self.numeri)}: da {self.minimo} a {self.massimo} presenti"
        if self.codice == "filtro":
            return (f"Filtro con {len(self.combinazioni)} combinazioni: da {self.minimo} a {self.massimo} "
                    "numeri in comune")
        t = self.tipo
        par = f" ({t.param_nome} {self.param})" if t and t.param_nome else ""
        if t and t.modo == "intervallo":
            return f"{t.nome}{par}: da {self.minimo} a {self.massimo}"
        return f"{t.nome if t else self.codice}{par}: {', '.join(map(str, sorted(self.valori)))}"

    def rispetta(self, C: np.ndarray, ctx: Contesto) -> np.ndarray:
        if self.codice == "gruppo":
            v = np.isin(C, self.numeri).sum(axis=1)
            return (v >= self.minimo) & (v <= self.massimo)
        if self.codice == "filtro":
            if not self.combinazioni:
                return np.ones(len(C), dtype=bool)
            F = np.zeros((len(self.combinazioni), ctx.gioco.n + 1), dtype=np.float32)
            for i, c in enumerate(self.combinazioni):
                F[i, c] = 1
            v = np.zeros(len(C), dtype=int)
            for a in range(0, len(C), 200000):
                P = np.zeros((min(200000, len(C) - a), ctx.gioco.n + 1), dtype=np.float32)
                np.put_along_axis(P, C[a:a + 200000].astype(np.int64), 1, axis=1)
                v[a:a + 200000] = (P @ F.T).max(axis=1)
            return (v >= self.minimo) & (v <= self.massimo)
        v = self.tipo.funzione(C, ctx, self.param)
        if self.tipo.modo == "intervallo":
            return (v >= self.minimo) & (v <= self.massimo)
        return np.isin(v, self.valori)


def gruppo(numeri, minimo, massimo) -> Condizione:
    """Fisse / Sequele: un gruppo di numeri di cui ne devono essere presenti da minimo a massimo."""
    return Condizione("gruppo", numeri=sorted(numeri), minimo=minimo, massimo=massimo)


def filtra(C: np.ndarray, condizioni: list[Condizione], ctx: Contesto, errori_min: int = 0,
           errori_max: int = 0) -> np.ndarray:
    """Maschera delle colonne accettate: numero di condizioni NON rispettate tra errori_min e errori_max."""
    attive = [c for c in condizioni if c.attiva]
    if not attive:
        return np.ones(len(C), dtype=bool)
    errori = np.zeros(len(C), dtype=np.int16)
    for c in attive:
        errori += ~c.rispetta(C, ctx)
    return (errori >= errori_min) & (errori <= errori_max)


def a_json(condizioni: list[Condizione]) -> list[dict]:
    return [asdict(c) for c in condizioni]


def da_json(dati) -> list[Condizione]:
    if isinstance(dati, str):
        dati = json.loads(dati)
    return [Condizione(**d) for d in (dati or [])]


# ------------------------------------------------------------------ analisi sull'archivio
@dataclass
class AnalisiCondizione:
    codice: str
    nome: str
    estrazioni: int
    righe: list[tuple[int, int, float, float]]   # valore, uscite in archivio, % archivio, % atteso dal caso
    piu_frequente: int
    copertura: tuple[int, int]                   # intervallo o insieme che copre ~80%
    valori_80: list[int]
    suggerimento: str


def _valori_archivio(tipo: TipoCondizione, ctx: Contesto, param: int, ultime: int = 0) -> np.ndarray:
    """Valore della condizione per ogni estrazione dell'archivio, calcolato con i dati disponibili PRIMA di
    ciascuna estrazione quando la condizione dipende dal passato (ripetizioni, ultima, ritardi)."""
    estr = ctx.estrazioni[-ultime:] if ultime else ctx.estrazioni
    C = np.array([sorted(e.numeri) for e in estr], dtype=np.int64)
    if tipo.codice not in ("ripetizioni", "ultima", "ritardatari"):
        return tipo.funzione(C, ctx, param)
    tutte = [sorted(e.numeri) for e in ctx.estrazioni]
    inizio = len(tutte) - len(C)
    out = np.zeros(len(C), dtype=int)
    if tipo.codice == "ultima":
        for i in range(len(C)):
            j = inizio + i
            out[i] = len(set(tutte[j]) & set(tutte[j - 1])) if j > 0 else 0
        return out
    if tipo.codice == "ritardatari":
        N = ctx.gioco.n
        ultimo = np.full(N + 1, -10**6)
        for j, r in enumerate(tutte):
            if j >= inizio:
                rit = j - ultimo
                rit[ultimo < 0] = j
                out[j - inizio] = int((rit[r] >= int(param or 30)).sum())
            ultimo[r] = j
        return out
    # ripetizioni: massimo in comune con le estrazioni precedenti (finestra param)
    k = len(tutte[0])
    finestra = int(param or 0)
    insiemi: dict[int, set] = {t: set() for t in range(3, k + 1)}
    storia = []
    for j, r in enumerate(tutte):
        if j >= inizio:
            if finestra:
                insiemi = {t: set() for t in range(3, k + 1)}
                for s in storia[-finestra:]:
                    for t in range(3, k + 1):
                        insiemi[t].update(_codice(x) for x in combinations(s, t))
            m = min(2, k)
            for t in range(3, k + 1):
                if any(_codice(x) in insiemi[t] for x in combinations(r, t)):
                    m = t
            out[j - inizio] = m
        storia.append(r)
        if not finestra:
            for t in range(3, k + 1):
                insiemi[t].update(_codice(x) for x in combinations(r, t))
    return out


def _casuali(g: Gioco, quante: int = 60000) -> np.ndarray:
    rng = np.random.default_rng(11)
    return np.sort(np.argsort(rng.random((quante, g.n)), axis=1)[:, :g.k] + 1, axis=1)


def analizza(codice: str, ctx: Contesto, param: int = 0, ultime: int = 0, copertura: float = 0.8
             ) -> AnalisiCondizione:
    tipo = TIPI_PER_CODICE[codice]
    v = _valori_archivio(tipo, ctx, param, ultime)
    n = len(v)
    if tipo.codice in ("ripetizioni", "ultima", "ritardatari"):
        teorico = None          # dipende dalla storia: il confronto è con l'archivio stesso
    else:
        teorico = tipo.funzione(_casuali(ctx.gioco), ctx, param)
    valori = sorted(set(v.tolist()) | (set(teorico.tolist()) if teorico is not None else set()))
    righe = []
    for x in valori:
        c = int((v == x).sum())
        t = float((teorico == x).mean() * 100) if teorico is not None else float("nan")
        righe.append((int(x), c, c / n * 100 if n else 0.0, t))
    piu = max(righe, key=lambda r: r[1])[0] if righe else 0
    # valori più frequenti fino alla copertura richiesta
    ordinati = sorted(righe, key=lambda r: -r[1])
    acc, scelti = 0, []
    for r in ordinati:
        if acc >= copertura * n:
            break
        scelti.append(r[0])
        acc += r[1]
    lo, hi = (int(np.percentile(v, (1 - copertura) / 2 * 100)), int(np.percentile(v, (1 + copertura) / 2 * 100))) \
        if n else (0, 0)
    perc_piu = next(r[2] for r in righe if r[0] == piu) if righe else 0
    if tipo.modo == "intervallo":
        sugg = (f"Il valore più frequente è {piu} ({perc_piu:.1f}% delle estrazioni). "
                f"L'{int(copertura * 100)}% delle estrazioni ha un valore tra {lo} e {hi}: è l'intervallo consigliato.")
    else:
        sugg = (f"Il valore più comune è {piu} ({perc_piu:.1f}% delle estrazioni). "
                f"I valori {', '.join(map(str, sorted(scelti)))} insieme coprono il {acc / n * 100:.0f}% delle "
                "estrazioni: sono quelli consigliati.")
    return AnalisiCondizione(codice, tipo.nome, n, righe, piu, (lo, hi), sorted(scelti), sugg)


def consigliata(codice: str, ctx: Contesto, param: int = 0, copertura: float = 0.8) -> Condizione:
    """La condizione impostata secondo il suggerimento dell'analisi."""
    a = analizza(codice, ctx, param, copertura=copertura)
    t = TIPI_PER_CODICE[codice]
    if t.modo == "intervallo":
        return Condizione(codice, minimo=a.copertura[0], massimo=a.copertura[1], param=param)
    return Condizione(codice, valori=a.valori_80, param=param)


def rendimento(condizioni: list[Condizione], ctx: Contesto, ultime: int = 0) -> list[tuple[str, float]]:
    """Percentuale delle estrazioni dell'archivio che avrebbero rispettato ogni condizione (e tutte insieme).
    Per le condizioni legate al passato si usa lo stato attuale (approssimazione)."""
    estr = ctx.estrazioni[-ultime:] if ultime else ctx.estrazioni
    C = np.array([sorted(e.numeri) for e in estr], dtype=np.int64)
    if not len(C):
        return []
    out, tutte = [], np.ones(len(C), dtype=bool)
    for c in condizioni:
        if not c.attiva:
            continue
        if c.codice in ("ripetizioni", "ultima", "ritardatari"):
            v = _valori_archivio(c.tipo, ctx, c.param, ultime)
            ok = (v >= c.minimo) & (v <= c.massimo) if c.tipo.modo == "intervallo" else np.isin(v, c.valori)
        else:
            ok = c.rispetta(C, ctx)
        out.append((c.descrivi(), float(ok.mean() * 100)))
        tutte &= ok
    out.append(("Tutte le condizioni insieme", float(tutte.mean() * 100)))
    return out
