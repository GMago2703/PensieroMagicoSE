"""Motore delle analisi.

Ogni analisi riceve lo storico (in ordine crescente di data) e restituisce un
RisultatoAnalisi con:
- una tabella (colonne + righe);
- per ogni riga, i numeri "interessati" da evidenziare sulla griglia;
- un PUNTEGGIO per ciascuno dei 90 numeri: è il linguaggio comune con cui
  Magico Pensiero combina analisi diverse (anche quelle create dall'utente).

Per aggiungere un'analisi: scrivere una funzione e decorarla con @registra.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from math import comb
from typing import Callable

import numpy as np

from .gioco import SE, Gioco, Storico, gioco_di  # noqa: F401  (Storico: elenco che conosce il gioco)

# riga dello storico: (data, numeri ordinati, jolly/euro1, superstar/euro2, numeri in ordine di estrazione)
Riga = tuple[date, list[int], int, int | None, list[int]]


@dataclass
class Parametro:
    nome: str
    etichetta: str
    predefinito: int
    minimo: int = 0
    massimo: int = 10000
    aiuto: str = ""
    scelte: list[str] | None = None      # se presente: menu a tendina (valore = indice)


@dataclass
class RisultatoAnalisi:
    titolo: str
    colonne: list[str]
    righe: list[list]
    punteggi: dict[int, float] = field(default_factory=dict)   # numero -> punteggio (alto = "favorito")
    nota: str = ""
    numeri_riga: list[list[int]] = field(default_factory=list)  # numeri da evidenziare per ogni riga


@dataclass
class DefinizioneAnalisi:
    codice: str
    nome: str
    descrizione: str
    funzione: Callable[..., RisultatoAnalisi]
    parametri: list[Parametro] = field(default_factory=list)
    giochi: tuple = ("SE", "EJ")           # giochi per cui l'analisi ha senso


REGISTRO: dict[str, DefinizioneAnalisi] = {}
P_ULTIME = Parametro("ultime", "Considera le ultime N estrazioni (0 = tutte)", 0)


def registra(codice: str, nome: str, descrizione: str, parametri: list[Parametro] | None = None,
             giochi: tuple = ("SE", "EJ")):
    def deco(f):
        REGISTRO[codice] = DefinizioneAnalisi(codice, nome, descrizione, f, parametri or [], giochi)
        return f
    return deco


def analisi_del_gioco(g: Gioco) -> dict[str, DefinizioneAnalisi]:
    return {c: d for c, d in REGISTRO.items() if g.codice in d.giochi}


def numeri(storico) -> range:
    return range(1, gioco_di(storico).n + 1)


def finestra(storico: Storico, ultime: int) -> Storico:
    return storico[-ultime:] if ultime and ultime < len(storico) else storico


def normalizza(punteggi: dict[int, float]) -> dict[int, float]:
    """Porta i punteggi nell'intervallo 0..1 (utile per combinare analisi diverse)."""
    if not punteggi:
        return {}
    lo, hi = min(punteggi.values()), max(punteggi.values())
    if hi == lo:
        return {n: 0.5 for n in punteggi}
    return {n: (v - lo) / (hi - lo) for n, v in punteggi.items()}


def ritardi_evento(esiti: list[bool]) -> tuple[int, int, int]:
    """Per un evento che accade o no in ogni estrazione: (volte, ritardo attuale, ritardo massimo)."""
    volte, ultimo, rmax = 0, -1, 0
    for i, s in enumerate(esiti):
        if s:
            rmax = max(rmax, i - ultimo - 1)
            ultimo = i
            volte += 1
    attuale = len(esiti) - 1 - ultimo
    return volte, attuale, max(rmax, attuale)


def pct(a: int, b: int) -> float:
    return round(100 * a / b, 2) if b else 0.0


# --------------------------------------------------------------------------
@registra("frequenze_ritardi", "Frequenze e ritardi",
          "Per ogni numero: quante volte è uscito, da quante estrazioni manca (ritardo attuale), "
          "il ritardo massimo e quello medio storico.", [P_ULTIME])
def frequenze_ritardi(storico: Storico, ultime: int = 0) -> RisultatoAnalisi:
    dati = finestra(storico, ultime)
    tot = len(dati)
    righe, punteggi = [], {}
    for n in numeri(storico):
        volte, rit, rmax = ritardi_evento([n in r[1] for r in dati])
        medio = round((tot - volte) / (volte + 1), 1)
        righe.append([n, volte, pct(volte, tot), rit, rmax, medio])
        punteggi[n] = volte
    return RisultatoAnalisi(
        f"Frequenze e ritardi su {tot} estrazioni",
        ["Numero", "Frequenza", "% uscite", "Ritardo attuale", "Ritardo max", "Ritardo medio"],
        righe, punteggi, "Punteggio = frequenza nel periodo scelto. Clic su una riga per evidenziare il numero.",
        [[r[0]] for r in righe])


@registra("ritardatari", "Numeri ritardatari",
          "Classifica dei numeri per ritardo attuale rapportato al loro ritardo medio "
          "(indice > 1 = più in ritardo del solito).", [P_ULTIME])
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
                            "Punteggio = ritardo attuale / ritardo medio.", [[r[0]] for r in righe])


def matrice_transizione(dati: Storico, distanza: int) -> dict[int, Counter]:
    trans: dict[int, Counter] = {n: Counter() for n in numeri(dati)}
    for i in range(len(dati) - distanza):
        for a in dati[i][1]:
            trans[a].update(dati[i + distanza][1])
    return trans


@registra("successivi", "Numeri successivi (nesso tra estrazioni)",
          "Dati i numeri dell'ultima estrazione, conta quali numeri sono usciti più spesso "
          "nell'estrazione che segue (a distanza N) ogni volta che quei numeri erano usciti.",
          [Parametro("distanza", "Distanza in estrazioni", 1, 1, 50), P_ULTIME])
def successivi(storico: Storico, distanza: int = 1, ultime: int = 0) -> RisultatoAnalisi:
    dati = finestra(storico, ultime)
    if len(dati) <= distanza:
        return RisultatoAnalisi("Numeri successivi", ["Numero", "Conteggio"], [], {})
    trans = matrice_transizione(dati, distanza)
    ultima = dati[-1][1]
    totale = Counter()
    for a in ultima:
        totale.update(trans[a])
    righe = [[n, totale[n]] for n in numeri(storico)]
    righe.sort(key=lambda r: -r[1])
    return RisultatoAnalisi(
        f"Numeri seguiti a {distanza} estrazione/i dall'ultima estrazione {' '.join(map(str, ultima))}",
        ["Numero", "Volte uscito dopo"], righe, {n: float(totale[n]) for n in numeri(storico)},
        "Punteggio = quante volte il numero è uscito dopo i numeri dell'ultima estrazione.",
        [[r[0]] for r in righe])


@registra("ripetuti", "Numeri ripetuti dall'estrazione precedente",
          "Distribuzione di quanti numeri di ogni estrazione erano già usciti in quella precedente.", [P_ULTIME])
def ripetuti(storico: Storico, ultime: int = 0) -> RisultatoAnalisi:
    dati = finestra(storico, ultime)
    coppie = list(zip(dati, dati[1:]))
    righe, numeri = [], []
    for k in range(0, gioco_di(storico).k + 1):
        esiti = [len(set(a[1]) & set(b[1])) == k for a, b in coppie]
        volte, rit, rmax = ritardi_evento(esiti)
        righe.append([k, volte, pct(volte, len(coppie)), rit, rmax])
        ultimo = next((sorted(set(a[1]) & set(b[1])) for a, b in reversed(coppie)
                       if len(set(a[1]) & set(b[1])) == k), [])
        numeri.append(ultimo)
    return RisultatoAnalisi("Numeri ripetuti dalla precedente",
                            ["Numeri ripetuti", "Volte", "%", "Ritardo attuale", "Ritardo max"], righe, {},
                            "Clic su una riga: evidenzia i numeri ripetuti l'ultima volta che è successo.", numeri)


# ---------------------------------------------------------- nuove analisi
@registra("consecutivi", "Consecutività numerica",
          "Coppie di numeri consecutivi (es. 23-24) uscite nella stessa sestina: quante volte, "
          "da quanto mancano. Nella nota la distribuzione di quante coppie consecutive ha ogni estrazione.",
          [P_ULTIME])
def consecutivi(storico: Storico, ultime: int = 0) -> RisultatoAnalisi:
    dati = finestra(storico, ultime)
    tot = len(dati)
    righe, numeri, punteggi = [], [], Counter()
    for n in range(1, gioco_di(storico).n):
        volte, rit, rmax = ritardi_evento([n in r[1] and n + 1 in r[1] for r in dati])
        righe.append([f"{n}-{n + 1}", volte, pct(volte, tot), rit, rmax])
        numeri.append([n, n + 1])
        punteggi[n] += volte
        punteggi[n + 1] += volte
    ordine = sorted(range(len(righe)), key=lambda i: -righe[i][1])
    righe = [righe[i] for i in ordine]
    numeri = [numeri[i] for i in ordine]
    distr = Counter(sum(1 for x, y in zip(r[1], r[1][1:]) if y - x == 1) for r in dati)
    nota = "Coppie consecutive per estrazione: " + ", ".join(
        f"{k}: {pct(distr[k], tot)}%" for k in range(0, gioco_di(storico).k) if distr[k])
    return RisultatoAnalisi("Consecutività numerica",
                            ["Coppia", "Volte", "% estrazioni", "Ritardo attuale", "Ritardo max"],
                            righe, {n: float(punteggi[n]) for n in range(1, gioco_di(storico).n + 1)}, nota, numeri)


@registra("somme", "Somme",
          "Somma dei numeri di ogni estrazione, raggruppata in classi: frequenza, ritardo di ogni classe "
          "e numeri dell'ultima estrazione caduta nella classe.",
          [Parametro("ampiezza", "Ampiezza delle classi di somma", 20, 5, 100), P_ULTIME])
def somme(storico: Storico, ampiezza: int = 20, ultime: int = 0) -> RisultatoAnalisi:
    dati = finestra(storico, ultime)
    tot = len(dati)
    sm = [sum(r[1]) for r in dati]
    if not sm:
        return RisultatoAnalisi("Somme", ["Classe"], [], {})
    righe, numeri = [], []
    inizio = (min(sm) // ampiezza) * ampiezza
    for lo in range(inizio, max(sm) + 1, ampiezza):
        hi = lo + ampiezza - 1
        esiti = [lo <= s <= hi for s in sm]
        volte, rit, rmax = ritardi_evento(esiti)
        if not volte:
            continue
        righe.append([f"{lo}-{hi}", volte, pct(volte, tot), rit, rmax])
        numeri.append(next(r[1] for r, e in zip(reversed(dati), reversed(esiti)) if e))
    ss = sorted(sm)
    # punteggio: quanto spesso il numero compare nelle estrazioni con somma "tipica" (50% centrale)
    q1, q3 = ss[len(ss) // 4], ss[3 * len(ss) // 4]
    punteggi = Counter()
    for r, s in zip(dati, sm):
        if q1 <= s <= q3:
            punteggi.update(r[1])
    nota = (f"Ultima somma: {sm[-1]}. Minima {ss[0]}, media {round(sum(ss) / tot, 1)}, massima {ss[-1]}. "
            f"Il 50% delle estrazioni ha somma tra {q1} e {q3}.")
    return RisultatoAnalisi("Somme", ["Classe di somma", "Volte", "%", "Ritardo attuale", "Ritardo max"],
                            righe, {n: float(punteggi[n]) for n in range(1, gioco_di(storico).n + 1)}, nota, numeri)


def progressioni(sestina: list[int], lunghezza_min: int, passo_max: int) -> list[tuple[int, list[int]]]:
    """Progressioni aritmetiche massimali (passo, numeri) contenute nella sestina."""
    s = sorted(sestina)
    insieme = set(s)
    trovate = []
    for i, a in enumerate(s):
        for b in s[i + 1:]:
            d = b - a
            if d > passo_max or (a - d) in insieme:     # non massimale: inizia prima
                continue
            seq = [a, b]
            while seq[-1] + d in insieme:
                seq.append(seq[-1] + d)
            if len(seq) >= lunghezza_min:
                trovate.append((d, seq))
    return trovate


@registra("sequenze", "Sequenze",
          "Sequenze di numeri a passo costante nella stessa sestina (es. 12-13-14 passo 1, "
          "10-20-30 passo 10): quali sono uscite, quante volte e quando.",
          [Parametro("lunghezza", "Lunghezza minima della sequenza", 3, 3, 6),
           Parametro("passo", "Passo massimo", 10, 1, 44), P_ULTIME])
def sequenze(storico: Storico, lunghezza: int = 3, passo: int = 10, ultime: int = 0) -> RisultatoAnalisi:
    dati = finestra(storico, ultime)
    tot = len(dati)
    conteggio: Counter = Counter()
    ultima: dict[tuple, int] = {}
    per_passo: Counter = Counter()
    con_sequenza = 0
    for i, r in enumerate(dati):
        trovate = progressioni(r[1], lunghezza, passo)
        if trovate:
            con_sequenza += 1
        for d, seq in trovate:
            k = tuple(seq)
            conteggio[k] += 1
            ultima[k] = i
            per_passo[d] += 1
    righe, numeri, punteggi = [], [], Counter()
    for k, volte in sorted(conteggio.items(), key=lambda kv: (-kv[1], -ultima[kv[0]])):
        righe.append([" - ".join(map(str, k)), k[1] - k[0], len(k), volte, tot - 1 - ultima[k],
                      dati[ultima[k]][0].strftime("%d/%m/%Y")])
        numeri.append(list(k))
        punteggi.update(k)
    nota = (f"Estrazioni con almeno una sequenza: {con_sequenza} su {tot} ({pct(con_sequenza, tot)}%). "
            "Per passo: " + ", ".join(f"passo {d}: {v}" for d, v in sorted(per_passo.items())))
    return RisultatoAnalisi("Sequenze", ["Sequenza", "Passo", "Lunghezza", "Volte", "Estrazioni fa", "Ultima"],
                            righe, {n: float(punteggi[n]) for n in range(1, gioco_di(storico).n + 1)}, nota, numeri)


@registra("pari_dispari", "Pari e dispari",
          "Quanti numeri pari e dispari contiene ogni estrazione: frequenza reale, frequenza attesa "
          "dal calcolo delle probabilità e ritardo di ogni combinazione.", [P_ULTIME])
def pari_dispari(storico: Storico, ultime: int = 0) -> RisultatoAnalisi:
    dati = finestra(storico, ultime)
    g = gioco_di(storico)
    tot = len(dati)
    righe, numeri = [], []
    for k in range(g.k, -1, -1):
        esiti = [sum(1 for n in r[1] if n % 2 == 0) == k for r in dati]
        volte, rit, rmax = ritardi_evento(esiti)
        atteso = round(100 * comb(g.n // 2, k) * comb(g.n - g.n // 2, g.k - k) / comb(g.n, g.k), 2)
        righe.append([f"{k} pari - {g.k - k} dispari", volte, pct(volte, tot), atteso, rit, rmax])
        numeri.append(next((r[1] for r, e in zip(reversed(dati), reversed(esiti)) if e), []))
    pari_usciti = sum(1 for r in dati for n in r[1] if n % 2 == 0)
    punteggi = {n: (1.0 if n % 2 == 0 else 0.0) for n in range(1, g.n + 1)}
    # il punteggio favorisce la parità meno uscita nelle ultime estrazioni
    if pari_usciti > g.k / 2 * tot:
        punteggi = {n: 1 - v for n, v in punteggi.items()}
    return RisultatoAnalisi("Pari e dispari",
                            ["Composizione", "Volte", "% reale", "% attesa", "Ritardo attuale", "Ritardo max"],
                            righe, punteggi,
                            f"Numeri pari usciti: {pct(pari_usciti, g.k * tot)}% del totale. Clic su una riga: "
                            "evidenzia l'ultima sestina con quella composizione.", numeri)


@registra("posizioni", "Posizioni",
          "Frequenza di ogni numero in ciascuna posizione: in ordine crescente (1ª = numero più "
          "piccolo) oppure nell'ordine in cui i numeri sono stati estratti.",
          [Parametro("tipo", "Posizioni", 0, 0, 1, scelte=["In ordine crescente", "In ordine di estrazione"]),
           P_ULTIME])
def posizioni(storico: Storico, tipo: int = 0, ultime: int = 0) -> RisultatoAnalisi:
    dati = finestra(storico, ultime)
    g = gioco_di(storico)
    K = g.k
    freq = [Counter() for _ in range(K)]
    for r in dati:
        seq = r[4] if tipo == 1 else r[1]
        for p, n in enumerate(seq):
            freq[p][n] += 1
    righe = []
    for n in range(1, g.n + 1):
        valori = [freq[p][n] for p in range(K)]
        migliore = max(range(K), key=lambda p: valori[p]) + 1 if any(valori) else "-"
        righe.append([n, *valori, sum(valori), migliore])
    nota = []
    for p in range(K):
        if freq[p]:
            usati = sorted(freq[p].elements())
            top = ", ".join(str(n) for n, _ in freq[p].most_common(3))
            nota.append(f"{p + 1}ª: min {usati[0]}, media {round(sum(usati) / len(usati), 1)}, "
                        f"max {usati[-1]}, più frequenti {top}")
    ultima = dati[-1][4] if (tipo == 1 and dati) else (dati[-1][1] if dati else [])
    return RisultatoAnalisi(
        "Posizioni " + ("(ordine di estrazione)" if tipo == 1 else "(ordine crescente)"),
        ["Numero", *[f"{p + 1}ª" for p in range(K)], "Totale", "Posizione preferita"],
        righe, {n: float(sum(freq[p][n] for p in range(K))) for n in range(1, g.n + 1)},
        " | ".join(nota) + (f"  — Ultima estrazione: {' '.join(map(str, ultima))}" if ultima else ""),
        [[r[0]] for r in righe])


@registra("struttura", "Struttura delle combinazioni",
          "Riepilogo: pari/dispari, alti (metà superiore)/bassi, coppie consecutive.", [P_ULTIME])
def struttura(storico: Storico, ultime: int = 0) -> RisultatoAnalisi:
    dati = finestra(storico, ultime)
    pari, alti, cons = Counter(), Counter(), Counter()
    for r in dati:
        s = r[1]
        pari[sum(1 for n in s if n % 2 == 0)] += 1
        alti[sum(1 for n in s if n > gioco_di(storico).soglia_alti)] += 1
        cons[sum(1 for x, y in zip(s, s[1:]) if y - x == 1)] += 1
    tot = len(dati) or 1
    righe = [[k, pari[k], pct(pari[k], tot), alti[k], pct(alti[k], tot), cons[k], pct(cons[k], tot)]
             for k in range(gioco_di(storico).k + 1)]
    return RisultatoAnalisi("Struttura delle combinazioni",
                            ["Quantità", "Pari", "% pari", "Alti", "% alti", "Coppie consecutive", "%"],
                            righe, {}, "")


# ------------------------------------------------- somiglianza con l'archivio
def massimi_in_comune(storico: Storico, ultime: int = 0) -> list[int]:
    """Per ogni estrazione (delle ultime N): il massimo di numeri in comune con UNA QUALSIASI
    delle estrazioni precedenti. Indica quanto una sestina vincente "somiglia" all'archivio."""
    n = len(storico)
    m = np.zeros((n, gioco_di(storico).n + 1), dtype=np.float32)
    for i, r in enumerate(storico):
        m[i, r[1]] = 1
    inizio = max(1, n - ultime) if ultime else 1
    risultati = []
    for a in range(inizio, n, 400):                      # a blocchi per non usare troppa memoria
        b = min(a + 400, n)
        comuni = m[a:b] @ m[:b].T                        # blocco x tutte le precedenti
        for k in range(b - a):
            i = a + k
            risultati.append(int(comuni[k, :i].max()))
    return risultati


def limiti_consigliati(massimi: list[int], soglia: float = 90.0) -> tuple[int, int]:
    """Intervallo [minimo, massimo] di "numeri in comune con l'archivio" che copre almeno
    la soglia % delle estrazioni, togliendo i valori rari alle due estremità."""
    if not massimi:
        return 0, 6
    c = Counter(massimi)
    tot = len(massimi)
    lo, hi = min(c), max(c)
    coperti = tot
    while lo < hi:
        togli_lo, togli_hi = c[lo], c[hi]
        if togli_lo <= togli_hi and 100 * (coperti - togli_lo) / tot >= soglia:
            coperti -= togli_lo
            lo += 1
        elif 100 * (coperti - togli_hi) / tot >= soglia:
            coperti -= togli_hi
            hi -= 1
        elif 100 * (coperti - togli_lo) / tot >= soglia:
            coperti -= togli_lo
            lo += 1
        else:
            break
    return lo, hi


@registra("somiglianza", "Somiglianza con l'archivio",
          "Per ogni estrazione: il massimo di numeri in comune con una qualsiasi estrazione precedente. "
          "Mostra quanto le combinazioni vincenti 'assomigliano' a quelle già uscite e da qui ricava "
          "il limite consigliato per le combinazioni di Magico Pensiero.",
          [Parametro("ultime", "Considera le ultime N estrazioni (0 = tutte)", 500),
           Parametro("soglia", "Copertura richiesta per il limite consigliato (%)", 90, 50, 100)])
def somiglianza(storico: Storico, ultime: int = 500, soglia: int = 90) -> RisultatoAnalisi:
    if len(storico) < 2:
        return RisultatoAnalisi("Somiglianza con l'archivio", ["Massimo in comune"], [], {})
    massimi = massimi_in_comune(storico, ultime)
    dati = storico[-len(massimi):]
    tot = len(massimi)
    lo, hi = limiti_consigliati(massimi, soglia)
    righe, numeri = [], []
    cumulata = 0
    for k in range(0, gioco_di(storico).k + 1):
        esiti = [x == k for x in massimi]
        volte, rit, rmax = ritardi_evento(esiti)
        if not volte and not (lo <= k <= hi):
            continue
        cumulata += volte
        righe.append([k, volte, pct(volte, tot), pct(cumulata, tot), rit, rmax,
                      "✔ consigliato" if lo <= k <= hi else ""])
        numeri.append(next((r[1] for r, e in zip(reversed(dati), reversed(esiti)) if e), []))
    nota = (f"Su {tot} estrazioni, ogni nuova combinazione vincente aveva al massimo da {min(massimi)} a "
            f"{max(massimi)} numeri in comune con le precedenti. Limite consigliato (copre almeno il {soglia}%): "
            f"da {lo} a {hi} numeri in comune. Ultima estrazione: {massimi[-1]}. "
            "Nota: più l'archivio cresce, più è facile trovare un'estrazione passata con 3 o 4 numeri uguali.")
    return RisultatoAnalisi("Somiglianza con l'archivio",
                            ["Max numeri in comune", "Volte", "%", "% cumulata", "Ritardo attuale", "Ritardo max",
                             "Limite"], righe, {}, nota, numeri)


# --------------------------------------------------- numeri speciali per gioco
@registra("euronumeri", "Euronumeri",
          "Frequenza e ritardo dei due Euronumeri. Con «solo formula attuale» si considerano solo le "
          "estrazioni con Euronumeri da 1 a 12 (dal 25/03/2022).",
          [Parametro("attuale", "Periodo", 1, 0, 1, scelte=["Tutte le estrazioni", "Solo formula attuale (1-12)"]),
           P_ULTIME], giochi=("EJ",))
def euronumeri(storico: Storico, attuale: int = 1, ultime: int = 0) -> RisultatoAnalisi:
    g = gioco_di(storico)
    dati = [r for r in storico if not attuale or g.euro_max(r[0]) == 12]
    dati = dati[-ultime:] if ultime else dati
    tot = len(dati)
    righe = []
    for e in range(1, 13):
        volte, rit, rmax = ritardi_evento([e in (r[2], r[3]) for r in dati])
        medio = round((tot - volte) / (volte + 1), 1)
        righe.append([e, volte, pct(volte, tot), rit, rmax, medio])
    coppie = Counter((r[2], r[3]) for r in dati)
    nota = (f"{tot} estrazioni considerate. Coppie di Euronumeri più frequenti: " +
            ", ".join(f"{a}-{b} ({v})" for (a, b), v in coppie.most_common(8)) +
            (f". Ultimi Euronumeri: {dati[-1][2]}-{dati[-1][3]}." if dati else ""))
    return RisultatoAnalisi("Euronumeri", ["Euronumero", "Uscite", "% estrazioni", "Ritardo attuale",
                                           "Ritardo max", "Ritardo medio"], righe, {}, nota, [])


@registra("jolly_superstar", "Jolly e SuperStar",
          "Per ogni numero: quante volte è uscito come Jolly e come SuperStar e da quante estrazioni manca.",
          [P_ULTIME], giochi=("SE",))
def jolly_superstar(storico: Storico, ultime: int = 0) -> RisultatoAnalisi:
    dati = finestra(storico, ultime)
    con_ss = [r for r in dati if r[3]]
    righe = []
    for n in range(1, 91):
        vj, rj, _ = ritardi_evento([r[2] == n for r in dati])
        vs, rs, _ = ritardi_evento([r[3] == n for r in con_ss])
        righe.append([n, vj, rj, vs, rs])
    return RisultatoAnalisi("Jolly e SuperStar", ["Numero", "Volte Jolly", "Ritardo Jolly", "Volte SuperStar",
                                                  "Ritardo SuperStar"], righe,
                            {n: float(r[1]) for n, r in zip(range(1, 91), righe)},
                            "Punteggio = volte uscito come Jolly.", [[r[0]] for r in righe])
