"""Motore delle analisi.

Ogni analisi riceve lo storico (in ordine crescente) e restituisce un
RisultatoAnalisi: una tabella da mostrare e, soprattutto, un PUNTEGGIO per
ciascuno dei 90 numeri. Il punteggio è il linguaggio comune che permetterà a
Magico Pensiero di combinare analisi diverse (anche quelle create dall'utente).

Per aggiungere un'analisi: scrivere una funzione e decorarla con @registra.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

Storico = list[tuple[date, list[int], int, int | None]]   # (data, sestina, jolly, superstar)


@dataclass
class Parametro:
    nome: str
    etichetta: str
    predefinito: int
    minimo: int = 0
    massimo: int = 10000
    aiuto: str = ""


@dataclass
class RisultatoAnalisi:
    titolo: str
    colonne: list[str]
    righe: list[list]
    punteggi: dict[int, float] = field(default_factory=dict)   # numero -> punteggio (più alto = più "favorito")
    nota: str = ""


@dataclass
class DefinizioneAnalisi:
    codice: str
    nome: str
    descrizione: str
    funzione: Callable[..., RisultatoAnalisi]
    parametri: list[Parametro] = field(default_factory=list)


REGISTRO: dict[str, DefinizioneAnalisi] = {}


def registra(codice: str, nome: str, descrizione: str, parametri: list[Parametro] | None = None):
    def deco(f):
        REGISTRO[codice] = DefinizioneAnalisi(codice, nome, descrizione, f, parametri or [])
        return f
    return deco


def _finestra(storico: Storico, ultime: int) -> Storico:
    return storico[-ultime:] if ultime and ultime < len(storico) else storico


def normalizza(punteggi: dict[int, float]) -> dict[int, float]:
    """Porta i punteggi nell'intervallo 0..1 (utile per combinare analisi diverse)."""
    if not punteggi:
        return {}
    lo, hi = min(punteggi.values()), max(punteggi.values())
    if hi == lo:
        return {n: 0.5 for n in punteggi}
    return {n: (v - lo) / (hi - lo) for n, v in punteggi.items()}


# --------------------------------------------------------------------------
@registra("frequenze_ritardi", "Frequenze e ritardi",
          "Per ogni numero: quante volte è uscito, da quante estrazioni manca (ritardo attuale), "
          "il ritardo massimo e quello medio storico.",
          [Parametro("ultime", "Considera le ultime N estrazioni (0 = tutte)", 0)])
def frequenze_ritardi(storico: Storico, ultime: int = 0) -> RisultatoAnalisi:
    dati = _finestra(storico, ultime)
    freq = Counter()
    ultima_pos: dict[int, int] = {}
    rit_max = Counter()
    for i, (_, sestina, _, _) in enumerate(dati):
        for n in sestina:
            prec = ultima_pos.get(n, -1)
            rit_max[n] = max(rit_max[n], i - prec - 1)
            ultima_pos[n] = i
            freq[n] += 1
    tot = len(dati)
    righe = []
    punteggi = {}
    for n in range(1, 91):
        rit = tot - 1 - ultima_pos[n] if n in ultima_pos else tot
        rmax = max(rit_max[n], rit)
        medio = round((tot - freq[n]) / (freq[n] + 1), 1)
        righe.append([n, freq[n], round(100 * freq[n] / tot, 2) if tot else 0, rit, rmax, medio])
        punteggi[n] = freq[n]
    return RisultatoAnalisi(
        f"Frequenze e ritardi su {tot} estrazioni",
        ["Numero", "Frequenza", "% uscite", "Ritardo attuale", "Ritardo max", "Ritardo medio"],
        righe, punteggi,
        "Punteggio = frequenza nel periodo scelto.")


@registra("ritardatari", "Numeri ritardatari",
          "Classifica dei numeri per ritardo attuale rapportato al loro ritardo medio "
          "(indice > 1 = più in ritardo del solito).",
          [Parametro("ultime", "Considera le ultime N estrazioni (0 = tutte)", 0)])
def ritardatari(storico: Storico, ultime: int = 0) -> RisultatoAnalisi:
    base = frequenze_ritardi(storico, ultime)
    righe, punteggi = [], {}
    for n, fr, _, rit, rmax, medio in base.righe:
        indice = round(rit / medio, 2) if medio else 0
        righe.append([n, rit, medio, rmax, indice])
        punteggi[n] = indice
    righe.sort(key=lambda r: -r[4])
    return RisultatoAnalisi("Numeri ritardatari", ["Numero", "Ritardo attuale", "Ritardo medio",
                                                   "Ritardo max", "Indice ritardo"], righe, punteggi,
                            "Punteggio = ritardo attuale / ritardo medio.")


@registra("successivi", "Numeri successivi (nesso tra estrazioni)",
          "Dati i numeri dell'ultima estrazione, conta quali numeri sono usciti più spesso "
          "nell'estrazione che segue (a distanza N) ogni volta che quei numeri erano usciti.",
          [Parametro("distanza", "Distanza in estrazioni", 1, 1, 50),
           Parametro("ultime", "Considera le ultime N estrazioni (0 = tutte)", 0)])
def successivi(storico: Storico, distanza: int = 1, ultime: int = 0) -> RisultatoAnalisi:
    dati = _finestra(storico, ultime)
    if len(dati) <= distanza:
        return RisultatoAnalisi("Numeri successivi", ["Numero", "Conteggio"], [], {})
    # matrice di transizione: da numero a -> numero b uscito 'distanza' estrazioni dopo
    trans: dict[int, Counter] = {n: Counter() for n in range(1, 91)}
    for i in range(len(dati) - distanza):
        for a in dati[i][1]:
            trans[a].update(dati[i + distanza][1])
    ultima = dati[-1][1]
    totale = Counter()
    for a in ultima:
        totale.update(trans[a])
    righe = [[n, totale[n]] for n in range(1, 91)]
    righe.sort(key=lambda r: -r[1])
    return RisultatoAnalisi(
        f"Numeri seguiti a {distanza} estrazione/i dall'ultima sestina {' '.join(map(str, ultima))}",
        ["Numero", "Volte uscito dopo"], righe, {n: float(totale[n]) for n in range(1, 91)},
        "Punteggio = quante volte il numero è uscito dopo i numeri dell'ultima estrazione.")


@registra("ripetuti", "Numeri ripetuti dall'estrazione precedente",
          "Distribuzione di quanti numeri di ogni estrazione erano già usciti in quella precedente.",
          [Parametro("ultime", "Considera le ultime N estrazioni (0 = tutte)", 0)])
def ripetuti(storico: Storico, ultime: int = 0) -> RisultatoAnalisi:
    dati = _finestra(storico, ultime)
    distr = Counter()
    for a, b in zip(dati, dati[1:]):
        distr[len(set(a[1]) & set(b[1]))] += 1
    tot = sum(distr.values()) or 1
    righe = [[k, distr[k], round(100 * distr[k] / tot, 2)] for k in range(0, 7)]
    return RisultatoAnalisi("Numeri ripetuti dalla precedente", ["Numeri ripetuti", "Volte", "%"], righe, {},
                            "Analisi descrittiva: non assegna punteggi ai numeri.")


@registra("struttura", "Struttura delle sestine",
          "Somma, pari/dispari, alti (46-90)/bassi, decine e consecutivi delle estrazioni.",
          [Parametro("ultime", "Considera le ultime N estrazioni (0 = tutte)", 0)])
def struttura(storico: Storico, ultime: int = 0) -> RisultatoAnalisi:
    dati = _finestra(storico, ultime)
    pari, alti, cons, somme = Counter(), Counter(), Counter(), []
    for _, s, _, _ in dati:
        pari[sum(1 for n in s if n % 2 == 0)] += 1
        alti[sum(1 for n in s if n > 45)] += 1
        cons[sum(1 for x, y in zip(s, s[1:]) if y - x == 1)] += 1
        somme.append(sum(s))
    tot = len(dati) or 1
    righe = []
    for k in range(7):
        righe.append([k, pari[k], round(100 * pari[k] / tot, 1), alti[k], round(100 * alti[k] / tot, 1),
                      cons[k], round(100 * cons[k] / tot, 1)])
    nota = ""
    if somme:
        ss = sorted(somme)
        nota = (f"Somma dei 6 numeri: minima {ss[0]}, media {round(sum(ss) / len(ss), 1)}, "
                f"massima {ss[-1]}; il 50% centrale è tra {ss[len(ss) // 4]} e {ss[3 * len(ss) // 4]}.")
    return RisultatoAnalisi("Struttura delle sestine",
                            ["Quantità", "Pari", "% pari", "Alti", "% alti", "Coppie consecutive", "%"],
                            righe, {}, nota)
