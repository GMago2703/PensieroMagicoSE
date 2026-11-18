"""Statistiche (menu Statistiche) e verifica di colonne sull'archivio.

Ogni statistica restituisce una Tabella (titolo, colonne, righe, colori facoltativi, nota) che
l'interfaccia mostra, ordina, stampa ed esporta. Tutto è calcolato sull'archivio del gioco aperto
(SuperEnalotto ed Eurojackpot restano separati).

Le note ricordano sempre la stessa cosa verificata nel laboratorio: ritardi, numeri "caldi" e
"freddi" descrivono il passato ma non rendono un numero più o meno probabile.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from itertools import combinations
from math import comb, sqrt
from typing import Callable

import numpy as np

from .gioco import Gioco, SE

NOTA_CASO = ("Ricorda: ogni estrazione è indipendente dalle precedenti. Ritardi e frequenze descrivono il "
             "passato, non rendono un numero più o meno probabile (verificato nel Laboratorio).")


@dataclass
class Tabella:
    titolo: str
    colonne: list[str]
    righe: list[list]
    colori: dict[tuple[int, int], str] = field(default_factory=dict)    # (riga, colonna) -> colore
    nota: str = ""
    griglia: bool = False             # True = tabellone (celle fisse, niente ordinamento)
    ordina: int = -1                  # colonna su cui ordinare all'apertura (-1 = nessuna)
    decrescente: bool = True

    def testo(self) -> str:
        """La tabella in testo a colonne (per stampa e file TXT)."""
        celle = [[_fmt(x) for x in r] for r in self.righe]
        larg = [len(c) for c in self.colonne]
        for r in celle:
            for i, x in enumerate(r):
                larg[i] = max(larg[i], max(len(p) for p in x.split("\n")))
        def riga(vals):
            return "  ".join(v.replace("\n", " ").rjust(larg[i]) for i, v in enumerate(vals))
        out = [self.titolo, "", riga(self.colonne), "  ".join("-" * w for w in larg)]
        out += [riga(r) for r in celle]
        if self.nota:
            out += ["", self.nota]
        return "\n".join(out)

    def csv(self) -> str:
        out = [";".join(self.colonne)]
        out += [";".join(_fmt(x).replace("\n", " ") for x in r) for r in self.righe]
        return "\n".join(out)


def _fmt(x) -> str:
    if isinstance(x, float):
        return f"{x:.2f}".replace(".", ",")
    if isinstance(x, date):
        return f"{x:%d/%m/%Y}"
    return "" if x is None else str(x)


@dataclass
class Parametro:
    nome: str
    etichetta: str
    predefinito: int
    minimo: int = 0
    massimo: int = 100000
    scelte: list[str] | None = None


@dataclass
class Statistica:
    codice: str
    nome: str                  # voce del menu
    descrizione: str
    funzione: Callable
    parametri: list[Parametro] = field(default_factory=list)


@dataclass
class Dati:
    """Dati dell'archivio per le statistiche: righe (data, numeri ordinati, extra1, extra2, ordine)."""
    gioco: Gioco
    righe: list
    archivio: object = None

    @staticmethod
    def da_archivio(archivio) -> "Dati":
        return Dati(archivio.gioco, list(archivio.sestine()), archivio)

    def matrice(self, ultime: int = 0) -> np.ndarray:
        """Presenze: matrice booleana (estrazioni × N+1)."""
        r = self.righe[-ultime:] if ultime else self.righe
        M = np.zeros((len(r), self.gioco.n + 1), dtype=bool)
        for i, x in enumerate(r):
            M[i, x[1]] = True
        return M


# ------------------------------------------------------------------ strumenti
def ritardi_serie(presenze: np.ndarray) -> tuple[int, int, float, int]:
    """Da una serie booleana (in ordine di tempo): ritardo attuale, ritardo massimo (attuale compreso),
    ritardo medio (tra uscite consecutive), uscite."""
    idx = np.flatnonzero(presenze)
    n = len(presenze)
    if not len(idx):
        return n, n, float("nan"), 0
    attuale = n - 1 - int(idx[-1])
    buchi = np.diff(np.concatenate(([-1], idx))) - 1          # prima della prima uscita e tra le uscite
    massimo = max(int(buchi.max()), attuale)
    medio = float(buchi[1:].mean()) if len(buchi) > 1 else float(buchi[0])
    return attuale, massimo, medio, len(idx)


def _calore(v: float, vmax: float, base=(255, 255, 255), forte=(239, 83, 80)) -> str:
    f = 0.0 if vmax <= 0 else max(0.0, min(1.0, v / vmax))
    c = [int(base[i] + (forte[i] - base[i]) * f) for i in range(3)]
    return "#%02x%02x%02x" % tuple(c)


VERDE, ROSSO, GIALLO, AZZURRO = "#c8e6c9", "#ffcdd2", "#ffe082", "#b3e5fc"


# ------------------------------------------------------------------ statistiche dei numeri
def tutti_i_numeri(d: Dati, ultime: int = 0, recenti: int = 100) -> Tabella:
    g = d.gioco
    M = d.matrice(ultime)
    n = len(M)
    p = g.k / g.n
    righe, colori = [], {}
    date_ = [r[0] for r in (d.righe[-ultime:] if ultime else d.righe)]
    for x in range(1, g.n + 1):
        att, mx, med, usc = ritardi_serie(M[:, x])
        atteso = n * p
        z = (usc - atteso) / sqrt(atteso * (1 - p)) if atteso else 0.0
        rec = int(M[-recenti:, x].sum()) if recenti else 0
        ultima = date_[n - 1 - att] if usc else None
        ic = att / med if med and med == med else 0.0
        righe.append([x, usc, usc / n * 100 if n else 0.0, round(atteso, 1), round(z, 2), att, mx,
                      round(med, 1), round(ic, 2), rec, ultima])
        i = len(righe) - 1
        if z >= 2:
            colori[(i, 4)] = ROSSO
        elif z <= -2:
            colori[(i, 4)] = AZZURRO
        if att >= mx and usc:
            colori[(i, 5)] = GIALLO           # ritardo record
    return Tabella(
        f"Tutti i numeri – {g.nome} – {n} estrazioni",
        ["Numero", "Uscite", "% estrazioni", "Atteso", "Scarto (z)", "Ritardo attuale", "Ritardo max",
         "Ritardo medio", "IC (att./medio)", f"Uscite ultime {recenti}", "Ultima uscita"],
        righe, colori,
        "Scarto (z) = quanto le uscite si allontanano dall'atteso in deviazioni standard: tra -2 e +2 è "
        "normale oscillazione del caso (in rosso sopra +2, in azzurro sotto -2). In giallo i numeri al loro "
        "ritardo massimo storico. IC = ritardo attuale / ritardo medio. " + NOTA_CASO)


def speciali(d: Dati, quale: int = 0, ultime: int = 0) -> Tabella:
    """SuperEnalotto: SuperStar (quale=0) o Jolly (quale=1). Eurojackpot: Euronumeri."""
    g = d.gioco
    righe_d = d.righe[-ultime:] if ultime else d.righe
    if g.is_ej:
        nome, massimo = "Euronumeri", 12
        validi = [r for r in righe_d if r[2] and r[3]]
        serie = {x: np.array([x in (r[2], r[3]) for r in validi]) for x in range(1, massimo + 1)}
        possibile = {x: np.array([g.euro_max(r[0]) >= x for r in validi]) for x in range(1, massimo + 1)}
        per_estr = 2
    else:
        col = 3 if quale == 0 else 2
        nome = "SuperStar" if quale == 0 else "Jolly"
        massimo = 90
        validi = [r for r in righe_d if r[col]]
        serie = {x: np.array([r[col] == x for r in validi]) for x in range(1, 91)}
        possibile = {x: np.ones(len(validi), dtype=bool) for x in range(1, 91)}
        per_estr = 1
    righe, colori = [], {}
    for x in range(1, massimo + 1):
        s = serie[x][possibile[x]]
        n = len(s)
        if not n:
            continue
        att, mx, med, usc = ritardi_serie(s)
        quanti = (g.euro_max(validi[-1][0]) if g.is_ej else 90)
        pr = per_estr / quanti if not g.is_ej else None
        if g.is_ej:   # probabilità variabile nel tempo (8, 10, poi 12 Euronumeri)
            atteso = sum(per_estr / g.euro_max(r[0]) for r, ok in zip(validi, possibile[x]) if ok)
        else:
            atteso = n * pr
        ultima = [r for r, ok in zip(validi, possibile[x]) if ok][n - 1 - att][0] if usc else None
        righe.append([x, usc, usc / n * 100, round(atteso, 1), att, mx, round(med, 1),
                      round(att / med, 2) if med and med == med else 0.0, ultima, n])
        if att >= mx and usc:
            colori[(len(righe) - 1, 4)] = GIALLO
    nota = ("In giallo i numeri al loro ritardo massimo storico. ")
    if g.is_ej:
        nota += ("Gli Euronumeri erano 8 fino al 3/10/2014, 10 fino al 18/3/2022, poi 12: per ogni numero si "
                 "contano solo le estrazioni in cui poteva uscire. ")
    elif quale == 0:
        nota += "La SuperStar esiste dal 2006: si contano solo le estrazioni che la hanno. "
    return Tabella(f"{nome} – {g.nome} – {len(validi)} estrazioni",
                   ["Numero", "Uscite", "% estrazioni", "Atteso", "Ritardo attuale", "Ritardo max",
                    "Ritardo medio", "IC (att./medio)", "Ultima uscita", "Estrazioni considerate"],
                   righe, colori, nota + NOTA_CASO, ordina=4)


def tabellone(d: Dati, colonne: int = 10) -> Tabella:
    """Tabellone dei ritardi: ogni casella mostra il numero e il suo ritardo attuale (colore = ritardo)."""
    g = d.gioco
    M = d.matrice()
    rit = {}
    mass = {}
    for x in range(1, g.n + 1):
        att, mx, _, _ = ritardi_serie(M[:, x])
        rit[x], mass[x] = att, mx
    vmax = max(rit.values()) if rit else 1
    righe, colori = [], {}
    for i in range(0, g.n, colonne):
        r = []
        for j in range(colonne):
            x = i + j + 1
            if x > g.n:
                r.append("")
                continue
            r.append(f"{x}\n{rit[x]}")
            colori[(len(righe), j)] = GIALLO if rit[x] >= mass[x] and rit[x] else _calore(rit[x], vmax)
        righe.append(r)
    ordinati = sorted(rit, key=lambda x: -rit[x])[:10]
    nota = ("Ogni casella: il numero e, sotto, quante estrazioni sono passate dalla sua ultima uscita. Più il "
            "rosso è intenso più il ritardo è alto; in giallo i numeri al loro ritardo massimo storico. "
            f"I 10 più ritardatari: {', '.join(f'{x} ({rit[x]})' for x in ordinati)}. " + NOTA_CASO)
    return Tabella(f"Tabellone dei ritardi – {g.nome} – {len(M)} estrazioni",
                   [str(j + 1) for j in range(colonne)], righe, colori, nota, griglia=True)


def caldi_freddi(d: Dati, ultime: int = 100, soglia_z: int = 15) -> Tabella:
    """Numeri caldi e freddi nelle ultime N estrazioni, con la verifica storica: i numeri caldi del
    passato hanno poi continuato a uscire di più?"""
    g = d.gioco
    M = d.matrice()
    n_tot = len(M)
    ultime = max(10, min(ultime, n_tot)) if n_tot else ultime
    p = g.k / g.n
    W = M[-ultime:]
    atteso = ultime * p
    sd = sqrt(atteso * (1 - p)) if atteso else 1
    soglia = soglia_z / 10
    righe, colori = [], {}
    for x in range(1, g.n + 1):
        o = int(W[:, x].sum())
        z = (o - atteso) / sd
        stato = "caldo" if z >= soglia else ("freddo" if z <= -soglia else "")
        righe.append([x, o, round(atteso, 1), round(z, 2), stato, int(M[:, x].sum())])
        if stato:
            colori[(len(righe) - 1, 4)] = ROSSO if stato == "caldo" else AZZURRO
    # verifica storica: i 10 più caldi / freddi di ogni finestra, uscite nelle 10 estrazioni successive
    nota_v = ""
    if n_tot > ultime + 20:
        cum = np.cumsum(M, axis=0, dtype=np.int32)
        caldo_tot = freddo_tot = conta = 0
        for t in range(ultime, n_tot - 10, 5):
            f = cum[t - 1] - (cum[t - 1 - ultime] if t - 1 - ultime >= 0 else 0)
            f = f[1:]
            ordine = np.argsort(f, kind="stable") + 1
            freddi, caldi = ordine[:10], ordine[-10:]
            dopo = M[t:t + 10]
            caldo_tot += int(dopo[:, caldi].sum())
            freddo_tot += int(dopo[:, freddi].sum())
            conta += 1
        if conta:
            att = 10 * 10 * p
            nota_v = (f"Verifica sull'archivio ({conta} prove): nelle 10 estrazioni successive i 10 numeri più "
                      f"caldi sono usciti in media {caldo_tot / conta:.2f} volte, i 10 più freddi "
                      f"{freddo_tot / conta:.2f} volte; il caso prevede {att:.2f} per entrambi. ")
    return Tabella(f"Numeri caldi e freddi – ultime {ultime} estrazioni – {g.nome}",
                   ["Numero", f"Uscite ultime {ultime}", "Atteso", "Scarto (z)", "Stato", "Uscite totali"],
                   righe, colori,
                   f"Caldo = uscito molto più dell'atteso (z ≥ {soglia:.1f}), freddo = molto meno (z ≤ -{soglia:.1f}). "
                   + nota_v + NOTA_CASO, ordina=3)


def ritardo_posizione(d: Dati, posizione: int = 1) -> Tabella:
    """Ritardo di ogni numero in una posizione della combinazione in ordine crescente (1ª = il più piccolo)."""
    g = d.gioco
    pos = max(1, min(posizione, g.k)) - 1
    serie = np.array([r[1][pos] for r in d.righe], dtype=int)
    n = len(serie)
    righe, colori = [], {}
    for x in range(1, g.n + 1):
        s = serie == x
        if not s.any():
            continue
        att, mx, med, usc = ritardi_serie(s)
        righe.append([x, usc, usc / n * 100, att, mx, round(med, 1), round(att / med, 2) if med else 0.0])
        if att >= mx:
            colori[(len(righe) - 1, 3)] = GIALLO
    return Tabella(f"Ritardo di posizione – {pos + 1}ª posizione (in ordine crescente) – {g.nome}",
                   ["Numero", "Uscite in posizione", "% estrazioni", "Ritardo attuale", "Ritardo max",
                    "Ritardo medio", "IC (att./medio)"], righe, colori,
                   f"Posizione {pos + 1}: il {pos + 1}° numero più piccolo dell'estrazione (l'ordine di estrazione del "
                   "sito non è affidabile per tutto l'archivio, vedi Laboratorio). Compaiono solo i numeri usciti "
                   "almeno una volta in questa posizione. In giallo i ritardi record. " + NOTA_CASO, ordina=1)


FASCE = {"somme": 20, "distanza_globale": 10, "distanza_massima": 5, "posizione": 10}


def classifica_condizioni(d: Dati, ultime_ritardo: int = 0) -> Tabella:
    """Per ogni condizione e ogni suo valore: frequenza, ritardo attuale, massimo, medio, IC."""
    from . import condizioni as cnd
    g = d.gioco
    ctx = d.archivio and _contesto(d)
    if ctx is None:
        from .modello import Estrazione
        ctx = cnd.Contesto(g, [Estrazione(r[0], r[1], r[2], r[3], gioco=g) for r in d.righe])
    righe, colori = [], {}
    for t in cnd.tipi_del_gioco(g):
        if t.codice == "popolarita" and ctx.popolarita is None:
            continue
        try:
            v = cnd._valori_archivio(t, ctx, t.param_def)
        except Exception:
            continue
        if not len(v):
            continue
        n = len(v)
        if t.codice in FASCE:
            w = FASCE[t.codice]
            v = (v // w) * w
        for x in sorted(set(v.tolist())):
            s = v == x
            if s.sum() < 5:
                continue
            att, mx, med, usc = ritardi_serie(s)
            nome_val = f"{x}-{x + FASCE[t.codice] - 1}" if t.codice in FASCE else str(x)
            nome = t.nome + (f" ({t.param_nome} {t.param_def})" if t.param_nome else "")
            ic = att / med if med else 0.0
            righe.append([nome, nome_val, usc, usc / n * 100, att, mx, round(med, 1), round(ic, 2)])
            if att >= mx:
                colori[(len(righe) - 1, 4)] = GIALLO
    return Tabella(f"Classifica delle condizioni – {g.nome} – {len(ctx.estrazioni)} estrazioni",
                   ["Condizione", "Valore", "Uscite", "% estrazioni", "Ritardo attuale", "Ritardo max",
                    "Ritardo medio", "IC (att./medio)"], righe, colori,
                   "Per ogni condizione (quelle del menu Condizioni) e ogni valore: quante volte si è presentato e "
                   "da quante estrazioni manca. Le somme e le distanze sono raggruppate in fasce. Ordinata per IC "
                   "(ritardo attuale / ritardo medio): in alto i valori che mancano da più tempo rispetto alla loro "
                   "abitudine; in giallo quelli al ritardo record. " + NOTA_CASO, ordina=7)


def _contesto(d: Dati):
    from . import sistemi
    try:
        return sistemi.contesto_da_archivio(d.archivio)
    except Exception:
        return None


# ------------------------------------------------------------------ ambi e terni
def _codici(righe, t: int) -> tuple[np.ndarray, np.ndarray]:
    """Codici (base 128) delle t-combinazioni di ogni estrazione e indice dell'estrazione."""
    k = len(righe[0][1]) if righe else 0
    idx = list(combinations(range(k), t))
    A = np.array([r[1] for r in righe], dtype=np.int64)
    cod = np.zeros((len(A), len(idx)), dtype=np.int64)
    for j, c in enumerate(idx):
        v = np.zeros(len(A), dtype=np.int64)
        for p in c:
            v = v * 128 + A[:, p]
        cod[:, j] = v
    est = np.repeat(np.arange(len(A)), len(idx))
    return cod.ravel(), est


def _decodifica(c: int, t: int) -> str:
    out = []
    for _ in range(t):
        out.append(c % 128)
        c //= 128
    return " - ".join(str(x) for x in reversed(out))


def combinazioni_frequenti(d: Dati, t: int = 2, ordine: int = 0, quante: int = 100) -> Tabella:
    """Ambi (t=2) o terni (t=3): i più frequenti (ordine 0) o i più ritardatari (ordine 1)."""
    g = d.gioco
    righe_d = d.righe
    n = len(righe_d)
    nome = {2: "Ambi", 3: "Terni"}.get(t, f"Gruppi di {t}")
    singolare = {2: "Ambo", 3: "Terno"}.get(t, "Gruppo")
    if not n:
        return Tabella(nome, ["Combinazione"], [])
    cod, est = _codici(righe_d, t)
    o = np.lexsort((est, cod))
    cod, est = cod[o], est[o]
    inizio = np.concatenate(([True], cod[1:] != cod[:-1]))
    gruppi = np.flatnonzero(inizio)
    uniche = cod[gruppi]
    conte = np.diff(np.concatenate((gruppi, [len(cod)])))
    ultimo = est[np.concatenate((gruppi[1:] - 1, [len(cod) - 1]))]
    primo = est[gruppi]
    # ritardo massimo: buchi tra uscite consecutive dello stesso gruppo, il primo buco e il ritardo attuale
    buchi = np.diff(est) - 1
    stesso = ~inizio[1:]
    mx = primo.astype(np.int64).copy()
    gruppo_di = np.cumsum(inizio) - 1
    np.maximum.at(mx, gruppo_di[1:][stesso], buchi[stesso])
    attuale = n - 1 - ultimo
    mx = np.maximum(mx, attuale)
    possibili = comb(g.n, t)
    atteso = n * comb(g.k, t) / possibili
    mai = possibili - len(uniche)
    if ordine == 0:
        scelta = np.lexsort((attuale, -conte))[:quante]
    else:
        scelta = np.argsort(-attuale, kind="stable")[:quante]
    righe, colori = [], {}
    for i in scelta:
        righe.append([_decodifica(int(uniche[i]), t), int(conte[i]), round(atteso, 2), int(attuale[i]), int(mx[i]),
                      righe_d[int(ultimo[i])][0]])
        if attuale[i] >= mx[i]:
            colori[(len(righe) - 1, 3)] = GIALLO
    cosa = "più frequenti" if ordine == 0 else "più ritardatari (tra quelli usciti almeno una volta)"
    return Tabella(f"{nome} {cosa} – {g.nome} – {n} estrazioni",
                   [singolare, "Uscite", "Atteso", "Ritardo attuale", "Ritardo max",
                    "Ultima uscita"], righe, colori,
                   f"{nome} possibili: {possibili:,}; usciti almeno una volta: {len(uniche):,}; mai usciti: {mai:,}. "
                   .replace(",", ".") + f"Ogni {singolare.lower()} esce in media {atteso:.2f} volte in {n} estrazioni. "
                   "In giallo quelli al loro ritardo record. " + NOTA_CASO)


def distribuzioni(d: Dati, ultime: int = 0) -> Tabella:
    """Riepilogo per anno: estrazioni, somma media, pari medi, numeri usciti/non usciti."""
    g = d.gioco
    per_anno: dict[int, list] = {}
    for r in (d.righe[-ultime:] if ultime else d.righe):
        per_anno.setdefault(r[0].year, []).append(r[1])
    righe = []
    for anno, v in sorted(per_anno.items()):
        A = np.array(v)
        usciti = len(set(A.ravel().tolist()))
        conte = np.bincount(A.ravel(), minlength=g.n + 1)[1:]
        piu = int(np.argmax(conte)) + 1
        righe.append([anno, len(A), round(float(A.sum(axis=1).mean()), 1), round(float((A % 2 == 0).sum(axis=1)
                      .mean()), 2), usciti, g.n - usciti, f"{piu} ({int(conte.max())})"])
    return Tabella(f"Riepilogo per anno – {g.nome}",
                   ["Anno", "Estrazioni", "Somma media", "Pari medi", "Numeri usciti", "Numeri mai usciti",
                    "Più uscito (volte)"], righe, {},
                   f"Somma media attesa dal caso: {g.k * (g.n + 1) / 2:.1f}; pari medi attesi: "
                   f"{g.k * (g.n // 2) / g.n:.2f}.")


# ------------------------------------------------------------------ registro
def statistiche_del_gioco(g: Gioco) -> list[Statistica]:
    P_ULT = Parametro("ultime", "Ultime N estrazioni (0 = tutte)", 0)
    out = [
        Statistica("numeri", "Tutti i numeri", "Frequenza, scarto dall'atteso e ritardi di ogni numero.",
                   tutti_i_numeri, [P_ULT, Parametro("recenti", "Uscite recenti: ultime", 100, 10, 5000)]),
    ]
    if g.is_ej:
        out.append(Statistica("speciali", "Euronumeri", "Frequenza e ritardi degli Euronumeri.", speciali, [P_ULT]))
    else:
        out.append(Statistica("speciali", "Numeri SuperStar e Jolly", "Frequenza e ritardi di SuperStar e Jolly.",
                              speciali, [Parametro("quale", "Numero", 0, scelte=["SuperStar", "Jolly"]), P_ULT]))
    out += [
        Statistica("tabellone", "Tabellone dei ritardi", "Tutti i numeri con il loro ritardo attuale, a colori.",
                   tabellone),
        Statistica("caldi", "Numeri caldi e freddi",
                   "Numeri usciti più o meno dell'atteso di recente, con la verifica sull'archivio.",
                   caldi_freddi, [Parametro("ultime", "Ultime N estrazioni", 100, 10, 5000),
                                  Parametro("soglia_z", "Soglia (z × 10)", 15, 5, 40)]),
        Statistica("posizione", "Ritardo di posizione", "Ritardi dei numeri in ogni posizione (in ordine crescente).",
                   ritardo_posizione, [Parametro("posizione", "Posizione", 1, 1, g.k)]),
        Statistica("condizioni", "Classifica delle condizioni",
                   "Frequenza e ritardo di ogni valore delle condizioni (pari, somme, decine, ...).",
                   classifica_condizioni),
        Statistica("anni", "Riepilogo per anno", "Somme, pari e numeri usciti anno per anno.", distribuzioni),
        Statistica("ambi_f", "Ambi più frequenti", "Le coppie di numeri uscite più volte insieme.",
                   lambda d, quante=100: combinazioni_frequenti(d, 2, 0, quante),
                   [Parametro("quante", "Quanti mostrarne", 100, 10, 5000)]),
        Statistica("ambi_r", "Ambi ritardatari", "Le coppie che mancano da più tempo.",
                   lambda d, quante=100: combinazioni_frequenti(d, 2, 1, quante),
                   [Parametro("quante", "Quanti mostrarne", 100, 10, 5000)]),
        Statistica("terni_f", "Terni più frequenti", "I gruppi di tre numeri usciti più volte insieme.",
                   lambda d, quante=100: combinazioni_frequenti(d, 3, 0, quante),
                   [Parametro("quante", "Quanti mostrarne", 100, 10, 5000)]),
    ]
    return out


def per_codice(g: Gioco, codice: str) -> Statistica:
    return next(s for s in statistiche_del_gioco(g) if s.codice == codice)


# ------------------------------------------------------------------ verifica di colonne sull'archivio
CATEGORIE_EJ_PREMI = ["5+2", "5+1", "5+0", "4+2", "4+1", "4+0", "3+2", "2+2", "3+1", "3+0", "1+2", "2+1"]


def probabilita_se() -> dict[str, float]:
    """Probabilità di ogni categoria per una colonna del SuperEnalotto."""
    tot = comb(90, 6)
    p = {m: comb(6, m) * comb(84, 6 - m) / tot for m in range(7)}
    return {"6": p[6], "5+1": p[5] / 84, "5": p[5] * 83 / 84, "4": p[4], "3": p[3], "2": p[2]}


def probabilita_ej(euro: int = 12) -> dict[str, float]:
    tot = comb(50, 5)
    pm = {m: comb(5, m) * comb(45, 5 - m) / tot for m in range(6)}
    te = comb(euro, 2)
    pe = {e: comb(2, e) * comb(euro - 2, 2 - e) / te for e in range(3)}
    return {c: pm[int(c[0])] * pe[int(c[2])] for c in CATEGORIE_EJ_PREMI}


@dataclass
class EsitoVerifica:
    categorie: list[str]
    per_colonna: list[dict[str, int]]          # categoria -> volte
    migliori: list[list[tuple]]                # per colonna: [(data, categoria)] dei risultati migliori
    estrazioni: int
    attesi: dict[str, float]                   # volte attese per UNA colonna nello stesso numero di estrazioni
    punti: list[dict[int, int]]                # per colonna: punti sui numeri principali -> volte

    def totale(self) -> dict[str, int]:
        return {c: sum(d[c] for d in self.per_colonna) for c in self.categorie}

    def testo(self, colonne, g: Gioco) -> str:
        r = [f"VERIFICA DI {len(colonne)} COLONNE SU {self.estrazioni} ESTRAZIONI – {g.nome}", ""]
        intest = "Colonna".ljust(28) + "".join(c.rjust(7) for c in self.categorie)
        r.append(intest)
        for i, c in enumerate(colonne):
            r.append(_colonna_txt(c, g).ljust(28) + "".join(str(self.per_colonna[i][x]).rjust(7)
                                                           for x in self.categorie))
        tot = self.totale()
        r.append("Totale".ljust(28) + "".join(str(tot[x]).rjust(7) for x in self.categorie))
        r.append("Atteso dal caso".ljust(28) + "".join(f"{self.attesi[x] * len(colonne):7.2f}"
                                                      for x in self.categorie))
        return "\n".join(r)


def _colonna_txt(c, g: Gioco) -> str:
    if g.is_ej and len(c) > g.k:
        return " ".join(map(str, c[:g.k])) + " + " + " ".join(map(str, c[g.k:]))
    return " ".join(map(str, c))


def verifica_colonne(colonne: list[list[int]], righe, g: Gioco = SE, ultime: int = 0) -> EsitoVerifica:
    """Quanti punti avrebbe fatto ogni colonna in ogni estrazione dell'archivio.
    SuperEnalotto: 6, 5+1, 5, 4, 3, 2. Eurojackpot: le 12 categorie di premio (se la colonna ha anche i 2
    Euronumeri) oppure i soli punti sui 5 numeri."""
    righe = righe[-ultime:] if ultime else righe
    n = len(righe)
    M = np.zeros((n, g.n + 1), dtype=bool)
    for i, r in enumerate(righe):
        M[i, r[1]] = True
    ej_euro = g.is_ej and all(len(c) == g.k + 2 for c in colonne)
    if g.is_ej:
        categorie = CATEGORIE_EJ_PREMI if ej_euro else ["5", "4", "3", "2"]
    else:
        categorie = ["6", "5+1", "5", "4", "3", "2"]
    per_col, migliori, punti = [], [], []
    for c in colonne:
        principali = list(c[:g.k])
        m = M[:, principali].sum(axis=1)
        conta = {x: 0 for x in categorie}
        lista = []
        punti.append({p: int((m == p).sum()) for p in range(g.k + 1)})
        if not g.is_ej:
            jolly = np.array([r[2] or 0 for r in righe])
            cj = np.isin(jolly, principali)
            cat = np.full(n, "", dtype=object)
            cat[m == 6] = "6"
            cat[(m == 5) & cj] = "5+1"
            cat[(m == 5) & ~cj] = "5"
            for p in (4, 3, 2):
                cat[m == p] = str(p)
        elif ej_euro:
            eu = set(c[g.k:])
            e = np.array([len(eu & {r[2], r[3]}) for r in righe])
            cat = np.array([f"{a}+{b}" for a, b in zip(m, e)], dtype=object)
            cat[~np.isin(cat, categorie)] = ""
        else:
            cat = np.array([str(x) if x >= 2 else "" for x in m], dtype=object)
        for x in categorie:
            conta[x] = int((cat == x).sum())
        ordine = {x: i for i, x in enumerate(categorie)}
        vinc = [i for i in range(n) if cat[i]]
        vinc.sort(key=lambda i: (ordine[cat[i]], -i))
        lista = [(righe[i][0], cat[i]) for i in vinc[:10]]
        per_col.append(conta)
        migliori.append(lista)
    if g.is_ej:
        pr = probabilita_ej() if ej_euro else {str(m): comb(5, m) * comb(45, 5 - m) / comb(50, 5) for m in (5, 4, 3, 2)}
    else:
        pr = probabilita_se()
    attesi = {x: pr[x] * n for x in categorie}
    return EsitoVerifica(categorie, per_col, migliori, n, attesi, punti)


def colonne_casuali(g: Gioco, quante: int, seme: int | None = None, con_euro: bool = True) -> list[list[int]]:
    rng = np.random.default_rng(seme)
    out = []
    for _ in range(quante):
        c = sorted(int(x) for x in rng.choice(np.arange(1, g.n + 1), g.k, replace=False))
        if g.is_ej and con_euro:
            c += sorted(int(x) for x in rng.choice(np.arange(1, 13), 2, replace=False))
        out.append(c)
    return out
