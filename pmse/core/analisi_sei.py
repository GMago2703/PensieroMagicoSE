"""Analisi dei concorsi in cui è stato vinto il "6" (SuperEnalotto).

Idea da verificare: le sestine che hanno dato un 6 hanno qualcosa in comune tra loro o rispetto al
resto dell'archivio? Ogni caratteristica del gruppo dei 6 viene confrontata con migliaia di gruppi
della stessa grandezza estratti a caso dagli altri concorsi (test di permutazione): se il gruppo
dei 6 è diverso solo per caso, la differenza sparisce; se è diverso davvero, resta.

Attenzione a come si legge: il 6 c'è quando QUALCUNO ha giocato la sestina estratta. Il gruppo dei
6 quindi dipende anche da come giocano le persone (numeri preferiti, quante giocate ci sono).
Per misurarlo si usa la "popolarità" di ogni sestina estratta: quanti hanno fatto 3 punti rispetto
ai concorsi vicini nel tempo. Se la sestina contiene numeri molto giocati, i 3 punti sono di più.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from .laboratorio import Prova, holm, norm_p2
from .vincite import Vincite

GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
        "ottobre", "novembre", "dicembre"]


def caratteristiche(s: list[int]) -> dict[str, float]:
    s = sorted(s)
    return {
        "Numeri da 1 a 31 (date di nascita)": sum(1 for x in s if x <= 31),
        "Numeri da 1 a 12 (mesi)": sum(1 for x in s if x <= 12),
        "Numeri pari": sum(1 for x in s if x % 2 == 0),
        "Somma dei numeri": sum(s),
        "Coppie di numeri consecutivi": sum(1 for a, b in zip(s, s[1:]) if b - a == 1),
        "Decine diverse occupate": len({(x - 1) // 10 for x in s}),
        "Numeri multipli di 5": sum(1 for x in s if x % 5 == 0),
        "Distanza tra il più piccolo e il più grande": s[-1] - s[0],
    }


@dataclass
class ConcorsoSei:
    data: date
    numeri: list[int]
    jolly: int
    superstar: int | None
    vincitori: int
    premio: str
    popolarita: float | None


@dataclass
class RapportoSei:
    concorsi: int
    con_vincite: int
    sei: list[ConcorsoSei]
    prove: list[Prova]
    medie: list[tuple[str, float, float]]          # caratteristica, media nei 6, media negli altri
    numeri_frequenti: list[tuple[int, int, float]]  # numero, uscite nei 6, attese
    note: list[str] = field(default_factory=list)

    def testo(self) -> str:
        r = [f"I CONCORSI CON IL 6 – SuperEnalotto",
             f"Concorsi con i vincitori noti: {self.con_vincite} su {self.concorsi}; concorsi con almeno un 6: "
             f"{len(self.sei)} (vincitori del 6 in tutto: {sum(c.vincitori for c in self.sei)}).", ""]
        r += ["Ogni confronto mette il gruppo dei 6 contro migliaia di gruppi uguali per grandezza presi a caso "
              "dagli altri concorsi. p = probabilità che la differenza sia solo fortuna (corretta con Holm).", ""]
        r.append("CONFRONTI")
        r.append("---------")
        for p in self.prove:
            r.append(f"[{p.esito.upper()}] {p.nome}")
            r.append(f"   {p.risultato}")
            r.append(f"   p = {p.p:.4f}   p corr. = {p.p_holm:.4f}")
        r.append("")
        if self.numeri_frequenti:
            r.append("Numeri più presenti nelle sestine del 6 (informativo: con pochi concorsi le differenze "
                     "sono soprattutto caso): " + ", ".join(f"{n} ({k} volte, attese {a:.1f})"
                                                            for n, k, a in self.numeri_frequenti[:8]))
            r.append("")
        r.append("VERDETTO")
        r.append("--------")
        r += self.note
        r.append("")
        r.append("ELENCO DEI CONCORSI CON IL 6")
        for c in self.sei:
            pop = f"popolarità {c.popolarita:.2f}" if c.popolarita else "popolarità n.d."
            r.append(f"{c.data:%d/%m/%Y}  {' '.join(f'{n:2d}' for n in sorted(c.numeri))}  vincitori {c.vincitori}"
                     f"  {c.premio}  {pop}")
        return "\n".join(r)


def popolarita(estrazioni, vinc: dict[str, Vincite], finestra: int = 10) -> dict[date, float]:
    """Vincitori di 3 punti divisi per la mediana dei concorsi vicini (±finestra): >1 = sestina più giocata
    del solito. Il rapporto toglie l'effetto del numero di giocate, che cambia nel tempo."""
    serie = [(e.data, vinc[e.data.isoformat()].p3) for e in estrazioni
             if e.data.isoformat() in vinc and vinc[e.data.isoformat()].p3 > 0]
    out = {}
    valori = [v for _, v in serie]
    for i, (d, v) in enumerate(serie):
        vicini = valori[max(0, i - finestra):i] + valori[i + 1:i + 1 + finestra]
        if len(vicini) >= 5:
            out[d] = v / float(np.median(vicini))
    return out


def _permutazione(valori: np.ndarray, gruppo: np.ndarray, rng, volte: int = 5000) -> tuple[float, float, float]:
    """Media del gruppo, media degli altri e p a due code (gruppi casuali della stessa grandezza)."""
    k = int(gruppo.sum())
    oss = valori[gruppo].mean()
    altri = valori[~gruppo].mean()
    tutti = valori
    medie = np.array([tutti[rng.choice(len(tutti), k, replace=False)].mean() for _ in range(volte)])
    centro = medie.mean()
    p = (1 + int((np.abs(medie - centro) >= abs(oss - centro)).sum())) / (volte + 1)
    return float(oss), float(altri), p


def esegui(estrazioni, vinc: dict[str, Vincite], volte: int = 5000) -> RapportoSei:
    estrazioni = sorted(estrazioni, key=lambda e: e.data)
    rng = np.random.default_rng(6)
    noti = [e for e in estrazioni if e.data.isoformat() in vinc]
    if len(noti) < 200:
        raise ValueError("Servono i vincitori di almeno 200 concorsi: aggiorna i dati delle vincite.")
    gruppo = np.array([vinc[e.data.isoformat()].p6 > 0 for e in noti])
    if gruppo.sum() < 5:
        raise ValueError("Troppo pochi concorsi con il 6 per un confronto.")
    pop = popolarita(noti, vinc)
    prove, medie = [], []
    nomi = list(caratteristiche(noti[0].numeri).keys())
    matrice = np.array([[v for v in caratteristiche(e.numeri).values()] for e in noti], dtype=float)
    for j, nome in enumerate(nomi):
        a, b, p = _permutazione(matrice[:, j], gruppo, rng, volte)
        medie.append((nome, a, b))
        prove.append(Prova("Sei", "", nome, "", f"media nei concorsi con il 6: {a:.2f}  –  negli altri: {b:.2f}", p))
    # popolarità della sestina (quanti 3 punti rispetto ai concorsi vicini)
    con_pop = np.array([e.data in pop for e in noti])
    if con_pop.sum() > 100:
        valori = np.array([pop[e.data] for e in noti if e.data in pop])
        g2 = gruppo[con_pop]
        a, b, p = _permutazione(valori, g2, rng, volte)
        medie.append(("Popolarità della sestina", a, b))
        prove.append(Prova("Sei", "", "Popolarità della sestina (vincitori di 3 punti rispetto al solito)", "",
                           f"concorsi con il 6: {a:.2f} volte il solito  –  altri: {b:.2f}", p))
    # legami tra le sestine del 6
    sei_num = [set(e.numeri) for e, g in zip(noti, gruppo) if g]
    comuni = [len(x & y) for i, x in enumerate(sei_num) for y in sei_num[i + 1:]]
    atteso = 36 / 90
    var = 6 * (6 / 90) * (84 / 90) * (84 / 89)
    z = (np.mean(comuni) - atteso) / math.sqrt(var / len(comuni))
    prove.append(Prova("Sei", "", "Numeri in comune tra le sestine del 6", "",
                       f"in media {np.mean(comuni):.3f} numeri in comune tra due sestine del 6 (caso {atteso:.3f})",
                       norm_p2(float(z))))
    # legame con il concorso precedente
    prec = []
    for i, e in enumerate(noti):
        if i > 0:
            prec.append(len(set(e.numeri) & set(noti[i - 1].numeri)))
    prec = np.array([0] + prec, dtype=float)
    a, b, p = _permutazione(prec, gruppo, rng, volte)
    prove.append(Prova("Sei", "", "Numeri in comune con il concorso precedente", "",
                       f"concorsi con il 6: {a:.3f}  –  altri: {b:.3f}", p))
    # giorno della settimana e mese
    for etich, chiave, nomi_v in (("Giorno della settimana", lambda d: d.weekday(), GIORNI),
                                  ("Mese dell'anno", lambda d: d.month - 1, MESI)):
        cat = np.array([chiave(e.data) for e in noti])
        valori = sorted(set(cat))
        oss = np.array([((cat == v) & gruppo).sum() for v in valori], dtype=float)
        att = np.array([(cat == v).sum() for v in valori], dtype=float) * gruppo.sum() / len(noti)
        chi = float(((oss - att) ** 2 / np.where(att > 0, att, 1)).sum())
        from .laboratorio import chi2_p
        dett = ", ".join(f"{nomi_v[v]} {int(o)} (attesi {a_:.1f})" for v, o, a_ in zip(valori, oss, att))
        prove.append(Prova("Sei", "", etich, "", dett, chi2_p(chi, len(valori) - 1)))
    for p, ph in zip(prove, holm([p.p for p in prove])):
        p.p_holm = ph
    # numeri più presenti nei 6 (informativo)
    conta = np.zeros(91)
    for s in sei_num:
        for x in s:
            conta[x] += 1
    att_n = len(sei_num) * 6 / 90
    freq = sorted(((int(n), int(conta[n]), att_n) for n in range(1, 91)), key=lambda t: -t[1])
    sei = []
    for e in noti:
        v = vinc[e.data.isoformat()]
        if v.p6 > 0:
            sei.append(ConcorsoSei(e.data, list(e.numeri), e.jolly, e.superstar, v.p6, v.premio6, pop.get(e.data)))
    note = _verdetto(prove, medie)
    return RapportoSei(len(estrazioni), len(noti), sei, prove, medie, freq, note)


def _verdetto(prove: list[Prova], medie) -> list[str]:
    forti = [p for p in prove if p.p_holm < 0.05]
    note = []
    if not forti:
        note.append("Nessuna differenza solida: le sestine che hanno dato il 6 non hanno caratteristiche proprie "
                    "rispetto alle altre estrazioni. Non emergono 'variabili' che le accomunino.")
    else:
        note.append("Differenze solide trovate: " + "; ".join(p.nome for p in forti) + ".")
        pop = next((p for p in forti if p.nome.startswith("Popolarità")), None)
        if pop:
            note.append("La più importante è la popolarità: il 6 arriva più spesso quando la sestina estratta "
                        "contiene numeri che molte persone giocano. Non è la macchina a 'scegliere' quelle sestine: "
                        "semplicemente, se più persone le hanno giocate, è più probabile che una di loro vinca.")
        if any(p.nome.startswith("Numeri da 1 a 31") for p in forti):
            note.append("Le sestine del 6 contengono più numeri da 1 a 31: è l'impronta delle date di nascita, "
                        "che molti giocatori usano.")
    note.append("Conseguenza pratica: la probabilità di vincere è la stessa per ogni combinazione, ma le "
                "combinazioni poco giocate, se escono, si dividono con meno persone.")
    return note
