"""Sistemi: sviluppo integrale, condizionato, ridotto a garanzia; verifica della garanzia; spoglio.

Tipi
- condizionato: tutte le colonne dei numeri scelti (con le fisse) che rispettano le condizioni;
- condizionato ridotto: come sopra, poi ridotto con garanzia n-1 ... n-4;
- ridotto: integrale dei numeri scelti ridotto con garanzia n-1 ... n-4 (eventuali fisse);
- ridotto immediato: come il ridotto, ma da riduzioni già pronte (istantaneo).

Garanzia n-j: se la combinazione vincente è tra quelle "possibili" del sistema (numeri tutti tra quelli
giocati, fisse comprese, e condizioni rispettate per i condizionati), almeno una colonna fa k-j punti
(SuperEnalotto: n-1 = almeno un 5, n-2 = almeno un 4, n-3 = un 3, n-4 = un 2).

Velocità: le colonne si rappresentano come maschere di bit (due interi a 64 bit) e i numeri in comune
si contano con un'unica istruzione (popcount) su milioni di colonne alla volta.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from itertools import combinations, islice
from math import comb

import numpy as np

from . import condizioni as cnd
from .gioco import GIOCHI, SE, Gioco

TIPI = {"condizionato": "Condizionato", "condizionato_ridotto": "Condizionato ridotto",
        "ridotto": "Ridotto (integrale a garanzia)", "immediato": "Ridotto immediato"}
LIMITE_INTEGRALE = 40_000_000          # colonne integrali esaminabili in un condizionato
LIMITE_RIDUZIONE = 3_000_000           # colonne da ridurre con garanzia
BLOCCO = 1_000_000
CHIAVE = "sistemi_salvati"
CHIAVE_PREZZI = "sistemi_prezzi"

_pc = getattr(np, "bitwise_count", None)
_TAB = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)


def _popcount(x: np.ndarray) -> np.ndarray:
    if _pc is not None:
        return _pc(x)
    return _TAB[x.view(np.uint8).reshape(len(x), 8)].sum(axis=1)


def maschere(C: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Colonne (numeri 1..90) -> due maschere a 64 bit (numeri 1-63 e 64-90)."""
    C = np.asarray(C, dtype=np.int64)
    uno = np.uint64(1)
    lo = np.zeros(len(C), dtype=np.uint64)
    hi = np.zeros(len(C), dtype=np.uint64)
    for j in range(C.shape[1]):
        x = C[:, j]
        basso = x < 64
        lo[basso] |= uno << x[basso].astype(np.uint64)
        hi[~basso] |= uno << (x[~basso] - 64).astype(np.uint64)
    return lo, hi


def in_comune(lo, hi, l1, h1) -> np.ndarray:
    return _popcount(lo & l1) + _popcount(hi & h1)


# ------------------------------------------------------------------ sviluppo integrale
def numero_integrale(n: int, k: int, f: int = 0) -> int:
    return comb(n - f, k - f) if 0 <= f <= k <= n else 0


def integrale(numeri, k: int, fisse=(), blocco: int = BLOCCO):
    """Genera l'integrale a blocchi (matrici ordinate). Le fisse sono in ogni colonna."""
    fisse = sorted(set(fisse))
    resto = sorted(set(numeri) - set(fisse))
    r = k - len(fisse)
    if r < 0 or r > len(resto):
        return
    it = combinations(resto, r)
    while True:
        pezzo = list(islice(it, blocco))
        if not pezzo:
            break
        R = np.array(pezzo, dtype=np.int16).reshape(len(pezzo), r)
        if fisse:
            C = np.hstack([R, np.tile(np.array(fisse, dtype=np.int16), (len(R), 1))])
            C.sort(axis=1)
        else:
            C = R
        yield C


# ------------------------------------------------------------------ riduzione a garanzia
def riduci(C: np.ndarray, punti: int, qualita: int = 1, avanzamento=None, interrompi=None,
           seme: int = 1) -> np.ndarray:
    """Sceglie un sottoinsieme di colonne di C tale che OGNI colonna di C abbia almeno 'punti' numeri in
    comune con una colonna scelta (copertura). qualita = quante candidate valutare a ogni passo
    (1 = velocissimo; 8-30 = meno colonne, più tempo)."""
    if len(C) == 0:
        return C
    k = C.shape[1]
    if punti <= 0:
        return C[:1]
    if punti >= k:
        return C
    lo, hi = maschere(C)
    rng = np.random.default_rng(seme)
    scoperte = np.arange(len(C))
    scelte = []
    totale = len(C)
    while len(scoperte):
        if interrompi and interrompi():
            raise InterruptedError("Riduzione interrotta.")
        lo_s, hi_s = lo[scoperte], hi[scoperte]
        if qualita <= 1:
            c = scoperte[0]
            coperte = in_comune(lo_s, hi_s, lo[c], hi[c]) >= punti
        else:
            prova = scoperte[rng.choice(len(scoperte), min(qualita, len(scoperte)), replace=False)]
            migliore, coperte = None, None
            for c_ in prova:
                cop = in_comune(lo_s, hi_s, lo[c_], hi[c_]) >= punti
                if coperte is None or cop.sum() > coperte.sum():
                    migliore, coperte = c_, cop
            c = migliore
        scelte.append(c)
        scoperte = scoperte[~coperte]
        if avanzamento and len(scelte) % 25 == 0:
            avanzamento(f"Riduzione: {len(scelte)} colonne, {totale - len(scoperte)} di {totale} coperte",
                        totale - len(scoperte), totale)
    return C[np.sort(np.array(scelte))]


def migliora(C: np.ndarray, punti: int, tentativi: int = 6, qualita: int = 16, interrompi=None) -> np.ndarray:
    """Più tentativi con semi diversi: tiene la riduzione con meno colonne."""
    best = None
    for s in range(tentativi):
        r = riduci(C, punti, qualita, interrompi=interrompi, seme=s + 1)
        if best is None or len(r) < len(best):
            best = r
    return best


# ------------------------------------------------------------------ garanzia e spoglio
@dataclass
class EsitoGaranzia:
    possibili: int
    garantiti: int                         # punti minimi garantiti
    distribuzione: dict[int, float]        # punti migliori -> % dei casi
    stimata: bool = False                  # True se calcolata su un campione

    def testo(self, k: int) -> str:
        parti = [f"Combinazioni vincenti possibili esaminate: {self.possibili}" +
                 (" (campione)" if self.stimata else ""),
                 f"Punti garantiti in ogni caso: {self.garantiti}"]
        for p in sorted(self.distribuzione, reverse=True):
            parti.append(f"  il miglior risultato è {p} punti nel {self.distribuzione[p]:.2f}% dei casi")
        return "\n".join(parti)


def verifica_garanzia(colonne: np.ndarray, possibili: np.ndarray, campione: int = 300_000) -> EsitoGaranzia:
    """Per ogni combinazione vincente possibile, il miglior punteggio ottenuto dal sistema."""
    stimata = False
    if len(possibili) > campione:
        rng = np.random.default_rng(5)
        possibili = possibili[rng.choice(len(possibili), campione, replace=False)]
        stimata = True
    lo, hi = maschere(possibili)
    lc, hc = maschere(colonne)
    migliore = np.zeros(len(possibili), dtype=np.int8)
    for i in range(len(colonne)):
        np.maximum(migliore, in_comune(lo, hi, lc[i], hc[i]).astype(np.int8), out=migliore)
    valori, conte = np.unique(migliore, return_counts=True)
    distr = {int(v): float(c / len(migliore) * 100) for v, c in zip(valori, conte)}
    return EsitoGaranzia(len(possibili), int(migliore.min()) if len(migliore) else 0, distr, stimata)


CATEGORIE_SE = ["6", "5+1", "5", "4", "3", "2"]
CATEGORIE_EJ = ["5", "4", "3", "2"]          # punti sui 5 numeri (gli Euronumeri non fanno parte del sistema)


def spoglio(colonne: np.ndarray, numeri, jolly=None, g: Gioco = SE) -> dict[str, int]:
    """Quante colonne del sistema vincono in ciascuna categoria per un'estrazione."""
    lo, hi = maschere(colonne)
    l1, h1 = maschere(np.array([sorted(numeri)]))
    p = in_comune(lo, hi, l1[0], h1[0])
    out = {}
    if not g.is_ej:
        con_jolly = np.isin(colonne, [jolly]).any(axis=1) if jolly else np.zeros(len(colonne), dtype=bool)
        out["6"] = int((p == 6).sum())
        out["5+1"] = int(((p == 5) & con_jolly).sum())
        out["5"] = int(((p == 5) & ~con_jolly).sum())
        for x in (4, 3, 2):
            out[str(x)] = int((p == x).sum())
        return out
    # Eurojackpot: i sistemi riguardano i 5 numeri; gli Euronumeri si aggiungono a parte in schedina
    for x in (5, 4, 3, 2):
        out[str(x)] = int((p == x).sum())
    return out


def spoglio_storico(colonne: np.ndarray, estrazioni, g: Gioco = SE, ultime: int = 0) -> dict:
    """Per ogni estrazione dell'archivio, quante colonne del sistema avrebbero fatto 2..k punti."""
    estr = estrazioni[-ultime:] if ultime else estrazioni
    lo, hi = maschere(colonne)
    k = g.k
    totali = {p: 0 for p in range(2, k + 1)}
    concorsi = {p: 0 for p in range(2, k + 1)}        # concorsi con almeno una colonna da p punti
    migliori = []
    for e in estr:
        l1, h1 = maschere(np.array([sorted(e.numeri)]))
        p = in_comune(lo, hi, l1[0], h1[0])
        m = int(p.max()) if len(p) else 0
        migliori.append((e.data, m))
        for x in range(2, k + 1):
            c = int((p == x).sum())
            totali[x] += c
            if c:
                concorsi[x] += 1
    return {"estrazioni": len(estr), "colonne_vincenti": totali, "concorsi_con": concorsi,
            "migliori": migliori}


# ------------------------------------------------------------------ il sistema
@dataclass
class Sistema:
    nome: str = ""
    tipo: str = "condizionato"
    gioco: str = "SE"
    numeri: list[int] = field(default_factory=list)
    fisse: list[int] = field(default_factory=list)
    condizioni: list[dict] = field(default_factory=list)
    errori_min: int = 0
    errori_max: int = 0
    garanzia: int = 0                  # 0 = nessuna riduzione; j = garanzia n-j
    qualita: int = 8                   # riduzione: 1 rapida ... 30 accurata
    colonne: list[list[int]] = field(default_factory=list)
    creato: str = ""
    info: dict = field(default_factory=dict)
    note: str = ""

    @property
    def G(self) -> Gioco:
        return GIOCHI.get(self.gioco, SE)

    @property
    def punti_garantiti(self) -> int:
        return self.G.k - self.garanzia if self.garanzia else 0

    def lista_condizioni(self) -> list[cnd.Condizione]:
        return cnd.da_json(self.condizioni)

    def descrizione(self) -> str:
        g = self.G
        r = [f"{TIPI.get(self.tipo, self.tipo)} – {g.nome}",
             f"Numeri giocati ({len(self.numeri)}): {' '.join(map(str, sorted(self.numeri)))}"]
        if self.fisse:
            r.append(f"Fisse ({len(self.fisse)}): {' '.join(map(str, sorted(self.fisse)))}")
        conds = [c for c in self.lista_condizioni() if c.attiva]
        if conds:
            r.append(f"Condizioni ({len(conds)}), errori ammessi da {self.errori_min} a {self.errori_max}:")
            r += [f"  - {c.descrivi()}" for c in conds]
        if self.garanzia:
            r.append(f"Garanzia n-{self.garanzia}: almeno {self.punti_garantiti} punti se la combinazione "
                     "vincente è tra quelle possibili del sistema")
        return "\n".join(r)

    def a_json(self) -> str:
        return json.dumps(asdict(self))

    @staticmethod
    def da_json(t) -> "Sistema":
        d = json.loads(t) if isinstance(t, str) else t
        s = Sistema()
        for k, v in d.items():
            if hasattr(s, k):
                setattr(s, k, v)
        return s


@dataclass
class Sviluppo:
    colonne: np.ndarray
    integrale: int                 # colonne dell'integrale
    possibili: int                 # colonne che rispettano le condizioni (prima della riduzione)
    secondi: float
    possibili_colonne: np.ndarray | None = None   # per la verifica della garanzia (se non troppe)


def valida(s: Sistema) -> None:
    g = s.G
    k = g.k
    if len(set(s.numeri)) != len(s.numeri):
        raise ValueError("Ci sono numeri ripetuti.")
    if any(not 1 <= x <= g.n for x in s.numeri):
        raise ValueError(f"I numeri devono essere tra 1 e {g.n}.")
    if not set(s.fisse) <= set(s.numeri):
        raise ValueError("Le fisse devono essere tra i numeri giocati.")
    if len(s.numeri) < k:
        raise ValueError(f"Servono almeno {k} numeri.")
    if len(s.fisse) >= k:
        raise ValueError(f"Al massimo {k - 1} fisse.")
    if s.tipo in ("condizionato_ridotto", "ridotto", "immediato") and not 1 <= s.garanzia <= k - 1:
        raise ValueError("Scegli la garanzia (n-1, n-2, ...).")


def sviluppa(s: Sistema, ctx: cnd.Contesto | None = None, avanzamento=None, interrompi=None) -> Sviluppo:
    """Sviluppa il sistema e ne restituisce le colonne."""
    valida(s)
    g = s.G
    k = g.k
    ctx = ctx or cnd.Contesto(g)
    t0 = time.time()
    tot = numero_integrale(len(s.numeri), k, len(s.fisse))
    if s.tipo == "immediato":
        from . import ridotti_pronti
        C = ridotti_pronti.applica(s.numeri, s.fisse, k, s.punti_garantiti)
        if C is None:
            raise ValueError("Riduzione già pronta non disponibile per questa scelta: usa 'Ridotti'.")
        return Sviluppo(C, tot, tot, time.time() - t0)
    condizionato = s.tipo in ("condizionato", "condizionato_ridotto")
    conds = [c for c in s.lista_condizioni() if c.attiva] if condizionato else []
    if tot > LIMITE_INTEGRALE:
        raise ValueError(f"L'integrale ha {tot:,} colonne: troppe (massimo {LIMITE_INTEGRALE:,}). Riduci i numeri "
                         "giocati o aggiungi delle fisse.".replace(",", "."))
    pezzi, fatte = [], 0
    for C in integrale(s.numeri, k, s.fisse):
        if interrompi and interrompi():
            raise InterruptedError("Sviluppo interrotto.")
        if conds:
            C = C[cnd.filtra(C, conds, ctx, s.errori_min, s.errori_max)]
        pezzi.append(C)
        fatte += BLOCCO
        if avanzamento:
            avanzamento(f"Sviluppo: {min(fatte, tot):,} di {tot:,} colonne esaminate".replace(",", "."),
                        min(fatte, tot), tot)
    C = np.vstack(pezzi) if pezzi else np.zeros((0, k), dtype=np.int16)
    possibili = len(C)
    if s.garanzia and s.tipo in ("condizionato", "condizionato_ridotto", "ridotto"):
        if possibili > LIMITE_RIDUZIONE:
            raise ValueError(f"Da ridurre ci sono {possibili:,} colonne: troppe per una riduzione rapida (massimo "
                             f"{LIMITE_RIDUZIONE:,}). Aggiungi condizioni o fisse.".replace(",", "."))
        R = riduci(C, s.punti_garantiti, s.qualita, avanzamento, interrompi)
        return Sviluppo(R, tot, possibili, time.time() - t0, C)
    return Sviluppo(C, tot, possibili, time.time() - t0, None)


def costo(s_colonne: int, g: Gioco, prezzi: dict | None = None, superstar: bool = False) -> float:
    prezzi = prezzi or {}
    if g.is_ej:
        return s_colonne * float(prezzi.get("EJ", 2.0))
    p = float(prezzi.get("SE", 1.0)) + (float(prezzi.get("superstar", 0.5)) if superstar else 0.0)
    return s_colonne * p


# ------------------------------------------------------------------ memoria (nell'archivio del gioco)
def salvati(archivio) -> dict[str, Sistema]:
    try:
        d = json.loads(archivio.leggi_impostazione(CHIAVE) or "{}")
    except ValueError:
        d = {}
    return {k: Sistema.da_json(v) for k, v in d.items()}


def salva(archivio, s: Sistema) -> None:
    if not s.nome.strip():
        raise ValueError("Serve un nome.")
    tutti = {k: asdict(v) for k, v in salvati(archivio).items()}
    s.creato = s.creato or datetime.now().isoformat(timespec="seconds")
    tutti[s.nome.strip()] = asdict(s)
    archivio.scrivi_impostazione(CHIAVE, json.dumps(tutti))


def elimina(archivio, nome: str) -> None:
    tutti = {k: asdict(v) for k, v in salvati(archivio).items() if k != nome}
    archivio.scrivi_impostazione(CHIAVE, json.dumps(tutti))


def esporta_testo(s: Sistema, colonne) -> str:
    righe = [s.descrizione(), f"Colonne: {len(colonne)}", ""]
    righe += [" ".join(f"{int(x):2d}" for x in c) for c in colonne]
    return "\n".join(righe)


def contesto_da_archivio(archivio) -> cnd.Contesto:
    from . import popolarita
    ctx = cnd.Contesto(archivio.gioco, archivio.tutte(True))
    try:
        ctx.popolarita = popolarita.per_archivio(archivio)
    except Exception:
        ctx.popolarita = None
    return ctx
