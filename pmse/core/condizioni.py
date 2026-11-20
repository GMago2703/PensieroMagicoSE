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
    vincenti: set = field(default_factory=set)            # date delle estrazioni in cui è stato vinto il jackpot
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

    def righe_archivio(self, quale: str) -> list:
        """Le combinazioni di uno dei tre archivi: 'completo', 'vincenti' (solo quelle che hanno vinto il
        jackpot) o 'senza_vincenti' (l'archivio completo meno le vincenti)."""
        if quale == "completo":
            return self.ultime
        if quale == "vincenti":
            return [sorted(e.numeri) for e in self.estrazioni if e.data in self.vincenti]
        return [sorted(e.numeri) for e in self.estrazioni if e.data not in self.vincenti]

    def sottoinsiemi_di(self, t: int, quale: str) -> np.ndarray:
        chiave = (t, "arch", quale)
        if chiave not in self._sotto:
            codici = set()
            for r in self.righe_archivio(quale):
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
    # "Gruppi tra": più gruppi, ognuno {"numeri": [...], "minimo": a, "massimo": b};
    # minimo/massimo della condizione = quanti gruppi devono essere rispettati
    gruppi: list[dict] = field(default_factory=list)
    nome: str = ""                 # nome scelto dall'utente (condizioni personalizzate e Quadri)
    regola: str = ""               # Quadri: regola sui gruppi (vedi REGOLE_QUADRI)

    @property
    def tipo(self):
        return TIPI_PER_CODICE.get(self.codice)

    def descrivi(self) -> str:
        testo = self._descrivi()
        return f"«{self.nome}»: {testo}" if self.nome else testo

    def _descrivi(self) -> str:
        if self.codice == "quadri_speciali":
            return descrivi_speciali(self.gruppi, 6)
        if self.codice == "quadri":
            n = len(self.gruppi)
            parti = [f"{LETTERE[i]}{(' ' + gr['nome']) if gr.get('nome') else ''}: "
                     f"{len(gr['numeri'])} numeri, da {gr['minimo']} a {gr['massimo']}"
                     for i, gr in enumerate(self.gruppi)]
            return (f"Quadri ({n} gruppi) – {testo_regola(self.regola, n, self.minimo, self.massimo)}; "
                    + "; ".join(parti))
        if self.codice == "gruppi_tra":
            parti = [f"{LETTERE[i]}: {' '.join(map(str, sorted(gr['numeri'])))} da {gr['minimo']} a {gr['massimo']}"
                     for i, gr in enumerate(self.gruppi)]
            n = len(self.gruppi)
            quanti = ("tutti rispettati" if self.minimo >= n else
                      f"rispettati da {self.minimo} a {self.massimo} gruppi su {n}")
            return f"Gruppi tra ({n}, {quanti}) – " + "; ".join(parti)
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
        if self.codice == "quadri_speciali":
            return rispetta_speciali(C, ctx, self.gruppi)
        if self.codice in ("gruppi_tra", "quadri"):
            if not self.gruppi:
                return np.ones(len(C), dtype=bool)
            ok = np.zeros(len(C), dtype=np.int16)
            for gr in self.gruppi:
                v = np.isin(C, gr["numeri"]).sum(axis=1)
                ok += (v >= gr["minimo"]) & (v <= gr["massimo"])
            if self.regola == "pari":
                return ok % 2 == 0
            if self.regola == "dispari":
                return ok % 2 == 1
            return (ok >= self.minimo) & (ok <= self.massimo)
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


LETTERE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gruppi_tra(gruppi: list[tuple[list[int], int, int]], minimo: int | None = None,
               massimo: int | None = None) -> Condizione:
    """Gruppi tra: ogni gruppo (numeri, minimo, massimo) di presenze; minimo/massimo = gruppi da rispettare
    (predefinito: tutti)."""
    gr = [{"numeri": sorted(set(int(x) for x in n)), "minimo": int(a), "massimo": int(b)} for n, a, b in gruppi]
    n = len(gr)
    return Condizione("gruppi_tra", gruppi=gr, minimo=n if minimo is None else minimo,
                      massimo=n if massimo is None else massimo)


# ------------------------------------------------------------------ Quadri
# regola -> (etichetta, serve un numero N)
REGOLE_QUADRI = {
    "tutte": ("Tutte le condizioni devono essere verificate", False),
    "almeno_una": ("Almeno una condizione deve essere verificata", False),
    "una_sola": ("Soltanto una condizione deve essere verificata", False),
    "nessuna": ("Nessuna delle condizioni deve essere verificata", False),
    "almeno_n": ("Almeno N condizioni devono essere verificate", True),
    "esattamente_n": ("Esattamente N condizioni devono essere verificate", True),
    "al_massimo_n": ("Al massimo N condizioni possono essere verificate", True),
    "tutte_tranne_una": ("Tutte tranne una (una sola non verificata)", False),
    "pari": ("Un numero pari di condizioni verificate", False),
    "dispari": ("Un numero dispari di condizioni verificate", False),
}


def regola_intervallo(regola: str, n_gruppi: int, n: int = 1) -> tuple[int, int]:
    """Quanti gruppi devono essere verificati (minimo, massimo) secondo la regola. 'pari'/'dispari' sono
    approssimate dall'intervallo (la verifica esatta è in Condizione.rispetta tramite il campo regola)."""
    G = n_gruppi
    n = max(0, min(int(n), G))
    return {"tutte": (G, G), "almeno_una": (min(1, G), G), "una_sola": (min(1, G), min(1, G)),
            "nessuna": (0, 0), "almeno_n": (n, G), "esattamente_n": (n, n), "al_massimo_n": (0, n),
            "tutte_tranne_una": (max(G - 1, 0), max(G - 1, 0)), "pari": (0, G), "dispari": (min(1, G), G)
            }.get(regola, (G, G))


def testo_regola(regola: str, n_gruppi: int, minimo: int, massimo: int) -> str:
    if regola in REGOLE_QUADRI:
        e = REGOLE_QUADRI[regola][0]
        if REGOLE_QUADRI[regola][1]:
            e = e.replace("N", str(minimo if regola != "al_massimo_n" else massimo), 1)
        return e.lower()
    return f"da {minimo} a {massimo} gruppi verificati su {n_gruppi}"


def quadri(gruppi: list[dict], regola: str = "tutte", n: int = 1, nome: str = "") -> Condizione:
    """Quadri: più gruppi di numeri scelti dall'utente. Ogni gruppo {"numeri", "minimo", "massimo", "nome"} è
    «verificato» se la colonna ne contiene da minimo a massimo. La regola dice quanti gruppi devono esserlo."""
    gr = [{"numeri": sorted(set(int(x) for x in g["numeri"])), "minimo": int(g.get("minimo", 1)),
           "massimo": int(g.get("massimo", len(g["numeri"]))), "nome": str(g.get("nome", ""))} for g in gruppi]
    lo, hi = regola_intervallo(regola, len(gr), n)
    return Condizione("quadri", gruppi=gr, minimo=lo, massimo=hi, regola=regola, nome=nome)


def verificati(C: np.ndarray, gruppi: list[dict]) -> np.ndarray:
    """Per ogni colonna, quanti gruppi sono verificati."""
    ok = np.zeros(len(C), dtype=np.int16)
    for gr in gruppi:
        v = np.isin(C, gr["numeri"]).sum(axis=1)
        ok += (v >= gr["minimo"]) & (v <= gr["massimo"])
    return ok


def analizza_quadri(gruppi: list[dict], ctx: Contesto) -> AnalisiCondizione:
    """Quanti gruppi dei Quadri sono verificati in ogni estrazione dell'archivio (con l'atteso dal caso)."""
    g = ctx.gioco
    n_g = len(gruppi)
    C = np.array([sorted(e.numeri) for e in ctx.estrazioni], dtype=np.int64).reshape(-1, g.k)
    v = verificati(C, gruppi) if len(C) else np.zeros(0, dtype=int)
    teorico = verificati(_casuali(g), gruppi)
    n = len(v)
    righe = []
    for x in range(0, n_g + 1):
        c = int((v == x).sum())
        righe.append((x, c, c / n * 100 if n else 0.0, float((teorico == x).mean() * 100)))
    piu = max(righe, key=lambda r: r[1])[0] if n else 0
    ordine = sorted(righe, key=lambda r: -r[1])
    scelti, acc = [], 0.0
    for r in ordine:
        scelti.append(r[0])
        acc += r[2]
        if acc >= 80:
            break
    lo, hi = (min(scelti), max(scelti)) if scelti else (0, n_g)
    sug = (f"Il numero di gruppi verificati più comune è {piu} ({ordine[0][2]:.1f}% delle estrazioni). Con da {lo} "
           f"a {hi} gruppi verificati si copre il {sum(r[2] for r in righe if lo <= r[0] <= hi):.0f}% delle "
           "estrazioni.") if n else "Archivio vuoto: nessuna analisi."
    return AnalisiCondizione("quadri", f"Quadri ({n_g} gruppi)", n, righe, piu, (lo, hi), sorted(scelti), sug)


def insiemi_comuni(g: Gioco) -> dict[str, list[int]]:
    """Gruppi di numeri usati più spesso, per formarli con un clic (etichetta -> numeri)."""
    N = g.n
    tutti = list(range(1, N + 1))
    out: dict[str, list[int]] = {}
    for d in range(0, (N + 9) // 10):
        nums = [x for x in tutti if (x - 1) // 10 == d]
        out[f"Decina {d * 10 + 1}-{min(d * 10 + 10, N)}"] = nums
    for f in range(10):
        out[f"Finale {f}"] = [x for x in tutti if x % 10 == f]
    out["Pari"] = [x for x in tutti if x % 2 == 0]
    out["Dispari"] = [x for x in tutti if x % 2]
    out[f"Bassi (1-{N // 2})"] = [x for x in tutti if x <= N // 2]
    out[f"Alti ({N // 2 + 1}-{N})"] = [x for x in tutti if x > N // 2]
    out["Primi"] = [x for x in tutti if x in PRIMI]
    for m in (3, 5, 7):
        out[f"Multipli di {m}"] = [x for x in tutti if x % m == 0]
    out["Quadrati perfetti"] = [x for x in tutti if int(x ** 0.5) ** 2 == x]
    out["Numeri doppi (11, 22...)"] = [x for x in tutti if x >= 11 and x % 11 == 0]
    out["Tutti i numeri"] = tutti
    return out


def decine(g: Gioco) -> list[dict]:
    """Un gruppo per ogni decina."""
    return [{"nome": n.replace("Decina ", ""), "numeri": v, "minimo": 1, "massimo": min(len(v), g.k)}
            for n, v in insiemi_comuni(g).items() if n.startswith("Decina")]


def finali(g: Gioco) -> list[dict]:
    """Un gruppo per ogni cifra finale (0-9)."""
    return [{"nome": f"finale {n[-1]}", "numeri": v, "minimo": 1, "massimo": min(len(v), g.k)}
            for n, v in insiemi_comuni(g).items() if n.startswith("Finale")]


def analizza_gruppo(numeri, ctx: Contesto, ultime: int = 0, copertura: float = 0.8) -> AnalisiCondizione:
    """Quanti numeri di un gruppo sono usciti in ogni estrazione dell'archivio, con l'atteso dal caso
    (ipergeometrica) e il suggerimento."""
    from math import comb
    g = ctx.gioco
    numeri = sorted(set(numeri))
    m = len(numeri)
    estr = ctx.estrazioni[-ultime:] if ultime else ctx.estrazioni
    C = np.array([sorted(e.numeri) for e in estr], dtype=np.int64).reshape(-1, g.k)
    v = np.isin(C, numeri).sum(axis=1) if len(C) else np.zeros(0, dtype=int)
    n = len(v)
    tot = comb(g.n, g.k)
    righe = []
    for x in range(0, min(m, g.k) + 1):
        caso = comb(m, x) * comb(g.n - m, g.k - x) / tot * 100
        usc = int((v == x).sum())
        righe.append((x, usc, usc / n * 100 if n else 0.0, caso))
    ordine = sorted(righe, key=lambda r: -r[1])
    piu = ordine[0][0] if n else 0
    scelti, cum = [], 0.0
    for r in ordine:
        scelti.append(r[0])
        cum += r[2]
        if cum >= copertura * 100:
            break
    lo, hi = min(scelti), max(scelti)
    sug = (f"Il valore più comune è {piu} ({ordine[0][2]:.1f}% delle estrazioni). Con da {lo} a {hi} numeri del "
           f"gruppo si copre il {sum(r[2] for r in righe if lo <= r[0] <= hi):.0f}% delle estrazioni: è "
           "l'intervallo consigliato.") if n else "Archivio vuoto: nessuna analisi."
    return AnalisiCondizione("gruppo", f"Gruppo di {m} numeri", n, righe, piu, (lo, hi), sorted(scelti), sug)


def gruppo(numeri, minimo, massimo) -> Condizione:
    """Fisse / Sequele: un gruppo di numeri di cui ne devono essere presenti da minimo a massimo."""
    return Condizione("gruppo", numeri=sorted(numeri), minimo=minimo, massimo=massimo)


# ------------------------------------------------------------------ Quadri speciali (tre archivi)
ARCHIVI_SPECIALI = {"completo": "Archivio completo",
                    "vincenti": "Archivio delle sole combinazioni vincenti",
                    "senza_vincenti": "Archivio completo senza le combinazioni vincenti"}


def massimo_in_comune(C: np.ndarray, ctx: Contesto, quale: str) -> np.ndarray:
    """Per ogni colonna, il massimo di numeri in comune con una qualsiasi combinazione dell'archivio scelto.
    Il valore minimo riportato è 2, che significa 'al massimo 2'."""
    k = C.shape[1]
    out = np.full(len(C), min(2, k), dtype=int)
    for t in range(3, k + 1):
        sotto = ctx.sottoinsiemi_di(t, quale)
        if len(sotto):
            out[np.isin(_codici_sotto(C, t), sotto).any(axis=1)] = t
    return out


def quadri_speciali(voci: list[dict], nome: str = "") -> Condizione:
    """Tre quadri, uno per archivio. Ogni voce: {"archivio", "attivo", "modo": "ammessi"|"non_ammessi",
    "valori": [quantità di numeri in comune]}."""
    return Condizione("quadri_speciali", gruppi=[dict(v) for v in voci], nome=nome)


def voci_speciali_vuote() -> list[dict]:
    return [{"archivio": a, "attivo": False, "modo": "ammessi", "valori": []} for a in ARCHIVI_SPECIALI]


def _ammessi_speciale(voce: dict, k: int) -> list[int]:
    val = set(voce.get("valori", []))
    tutti = set(range(min(2, k), k + 1))
    return sorted(val if voce.get("modo", "ammessi") == "ammessi" else tutti - val)


def rispetta_speciali(C: np.ndarray, ctx: Contesto, voci: list[dict]) -> np.ndarray:
    ok = np.ones(len(C), dtype=bool)
    for voce in voci:
        if not voce.get("attivo") or not voce.get("valori"):
            continue
        v = massimo_in_comune(C, ctx, voce["archivio"])
        ok &= np.isin(v, _ammessi_speciale(voce, C.shape[1]))
    return ok


def descrivi_speciali(voci: list[dict], k: int) -> str:
    parti = []
    for v in voci:
        if v.get("attivo") and v.get("valori"):
            q = ", ".join(("fino a 2" if x == 2 else str(x)) for x in sorted(v["valori"]))
            parti.append(f"{ARCHIVI_SPECIALI[v['archivio']]}: numeri in comune {q} "
                         f"{'ammessi' if v.get('modo') == 'ammessi' else 'NON ammessi'}")
    return "Quadri speciali – " + ("; ".join(parti) if parti else "nessun quadro attivo")


def analizza_speciale(ctx: Contesto, quale: str) -> AnalisiCondizione:
    """Quante volte ogni estrazione ha avuto N numeri in comune con le combinazioni PRECEDENTI dello stesso archivio
    (per 'vincenti' e 'senza_vincenti' si contano solo le precedenti appartenenti a quell'archivio)."""
    k = ctx.gioco.k
    insiemi = {t: set() for t in range(3, k + 1)}
    vincenti = ctx.vincenti
    valori = []
    for e in ctx.estrazioni:
        r = sorted(e.numeri)
        m = min(2, k)
        for t in range(3, k + 1):
            if any(_codice(x) in insiemi[t] for x in combinations(r, t)):
                m = t
        valori.append(m)
        vinta = e.data in vincenti
        if quale == "completo" or (quale == "vincenti") == vinta:
            for t in range(3, k + 1):
                insiemi[t].update(_codice(x) for x in combinations(r, t))
    v = np.array(valori, dtype=int)
    n = len(v)
    righe = [(x, int((v == x).sum()), float((v == x).mean() * 100) if n else 0.0, float("nan"))
             for x in range(min(2, k), k + 1)]
    piu = max(righe, key=lambda r: r[1])[0] if righe else 0
    ordinati = sorted(righe, key=lambda r: -r[1])
    acc, scelti = 0, []
    for r in ordinati:
        if n and acc >= 0.8 * n:
            break
        scelti.append(r[0])
        acc += r[1]
    sugg = (f"Con {ARCHIVI_SPECIALI[quale].lower()}, il caso più comune è {piu} numeri in comune. "
            f"I valori {', '.join(map(str, sorted(scelti)))} coprono il {acc / n * 100 if n else 0:.0f}% delle "
            "estrazioni." + (" Nessuna combinazione vincente nell'archivio: scarica i vincitori del 6."
                             if quale == "vincenti" and not vincenti else ""))
    return AnalisiCondizione("quadri_speciali", ARCHIVI_SPECIALI[quale], n, righe, piu,
                             (min(scelti, default=0), max(scelti, default=0)), sorted(scelti), sugg)


# ------------------------------------------------------------------ Controllo condizioni
@dataclass
class RigaControllo:
    indice: int
    descrizione: str
    attiva: bool
    escluse: int            # colonne che questa condizione, da sola, non rispetta
    uniche: int             # colonne che tornerebbero ammesse togliendo SOLO questa condizione
    nuove_in_sequenza: int  # colonne in più scartate rispetto alle condizioni che la precedono nell'elenco
    stato: str              # "operante" | "inoperante" | "assorbita" | "disattivata"
    assorbita_da: list[str]
    nota: str


@dataclass
class RapportoControllo:
    totale: int
    ammesse: int
    righe: list[RigaControllo]
    campione: bool = False


def controllo(C: np.ndarray, condizioni: list[Condizione], ctx: Contesto, errori_min: int = 0,
              errori_max: int = 0, campione: bool = False) -> RapportoControllo:
    """Verifica quali condizioni lavorano davvero sulle colonne C: quante ne scartano da sole, quante solo
    loro, quante in più rispetto alle precedenti, e quali sono inoperanti o assorbite da altre."""
    n = len(C)
    rispetti = [(c.rispetta(C, ctx) if c.attiva else np.ones(n, dtype=bool)) for c in condizioni]
    attive = [i for i, c in enumerate(condizioni) if c.attiva]
    errori = np.zeros(n, dtype=np.int16)
    for i in attive:
        errori += ~rispetti[i]
    base = (errori >= errori_min) & (errori <= errori_max)
    righe = []
    prec = np.ones(n, dtype=bool) if not attive else None
    cum = np.zeros(n, dtype=np.int16)
    ammesse_prec = np.ones(n, dtype=bool)
    for i, c in enumerate(condizioni):
        if not c.attiva:
            righe.append(RigaControllo(i, c.descrivi(), False, 0, 0, 0, "disattivata", [], "Disattivata."))
            continue
        fallisce = ~rispetti[i]
        senza = errori - fallisce.astype(np.int16)
        ammesse_senza = (senza >= errori_min) & (senza <= errori_max)
        uniche = int((ammesse_senza & ~base).sum())
        cum += fallisce
        ammesse_ora = (cum >= errori_min) & (cum <= errori_max)
        nuove = int((ammesse_prec & ~ammesse_ora).sum())
        ammesse_prec = ammesse_ora
        escluse = int(fallisce.sum())
        assorb = []
        if escluse and not uniche:
            for j in attive:
                if j != i and ((~rispetti[j]) & fallisce).sum() / escluse >= 0.5:
                    assorb.append(f"{condizioni[j].descrivi()} ({((~rispetti[j]) & fallisce).sum() / escluse * 100:.0f}%)")
        if not escluse:
            stato, nota = "inoperante", "Non scarta nessuna colonna: è sempre rispettata, quindi è inutile."
        elif not uniche:
            stato = "assorbita"
            nota = ("Le colonne che scarta sono già scartate da altre condizioni: toglierla non cambia il "
                    "risultato." if errori_max == 0 else
                    "Con gli errori ammessi, toglierla non cambia le colonne accettate.")
        else:
            stato, nota = "operante", f"Scarta davvero {uniche} colonne che nessun'altra condizione scarta."
        righe.append(RigaControllo(i, c.descrivi(), True, escluse, uniche, nuove, stato, assorb, nota))
    return RapportoControllo(n, int(base.sum()), righe, campione)


def testo_controllo(r: RapportoControllo) -> str:
    def p(x):
        return f"{x / r.totale * 100:.1f}%" if r.totale else "-"
    out = [f"Colonne esaminate: {r.totale}{' (campione casuale)' if r.campione else ''}",
           f"Colonne ammesse da tutte le condizioni: {r.ammesse} ({p(r.ammesse)}); scartate {r.totale - r.ammesse}", ""]
    for x in r.righe:
        out.append(f"{x.indice + 1}. {x.descrizione}")
        if x.attiva:
            out.append(f"   da sola scarta {x.escluse} ({p(x.escluse)}); solo lei {x.uniche}; "
                       f"in più delle precedenti {x.nuove_in_sequenza} – {x.stato.upper()}")
        out.append(f"   {x.nota}")
        for a in x.assorbita_da:
            out.append(f"   coperta da: {a}")
    return "\n".join(out)


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
