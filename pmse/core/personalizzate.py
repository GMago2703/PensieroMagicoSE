"""Analisi personalizzate create dall'utente.

Un'analisi personalizzata è una "ricetta":
- un periodo (ultime N estrazioni, 0 = tutte);
- uno o più INGREDIENTI: una misura calcolata per ogni numero (frequenza,
  ritardo, numeri successivi, ...) con un PESO (negativo = favorisce i valori bassi);
- dei FILTRI che decidono quali numeri sono ammessi.
Il punteggio finale di un numero è la somma pesata delle misure normalizzate 0..1.
Le ricette si salvano nell'archivio e compaiono nel menu Analisi; Magico Pensiero
le può usare come ingredienti.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field

from .analisi import (REGISTRO, DefinizioneAnalisi, RisultatoAnalisi, Storico, finestra, matrice_transizione,
                      normalizza, ritardi_evento)
from .modello import GIORNI


@dataclass
class Misura:
    codice: str
    nome: str
    descrizione: str
    param_etichetta: str | None = None
    param_predefinito: int = 0
    param_min: int = 0
    param_max: int = 100


MISURE: dict[str, Misura] = {m.codice: m for m in [
    Misura("frequenza", "Frequenza", "Quante volte il numero è uscito nel periodo."),
    Misura("ritardo", "Ritardo attuale", "Da quante estrazioni il numero non esce."),
    Misura("ritardo_max", "Ritardo massimo", "Il ritardo più lungo registrato nel periodo."),
    Misura("indice_ritardo", "Indice di ritardo", "Ritardo attuale diviso ritardo medio (>1 = più del solito)."),
    Misura("tendenza", "Tendenza recente",
           "Uscite nelle ultime N estrazioni rispetto a quelle attese in base al periodo (positivo = 'caldo').",
           "Ultime estrazioni", 30, 5, 500),
    Misura("successivi", "Numeri successivi",
           "Quante volte il numero è uscito N estrazioni dopo i numeri dell'ultima estrazione.",
           "Distanza", 1, 1, 50),
    Misura("posizione", "Frequenza in posizione",
           "Uscite del numero nella posizione indicata della sestina ordinata (1 = il più piccolo).",
           "Posizione (1-6)", 1, 1, 6),
    Misura("amici", "Uscito insieme a...",
           "Quante volte il numero è uscito nella stessa sestina con il numero indicato.",
           "Numero", 1, 1, 90),
    Misura("amici_ultima", "Uscito insieme ai numeri dell'ultima estrazione",
           "Quante volte il numero è uscito nella stessa sestina con i numeri dell'ultima estrazione."),
    Misura("giorno", "Frequenza in un giorno della settimana",
           "Uscite nelle estrazioni di un dato giorno (1 = lunedì ... 7 = domenica).", "Giorno (1-7)", 2, 1, 7),
    Misura("jolly", "Frequenza come Jolly", "Quante volte il numero è uscito come Jolly."),
    Misura("superstar", "Frequenza come SuperStar", "Quante volte il numero è uscito come SuperStar."),
]}


def calcola_misura(codice: str, dati: Storico, param: int = 0) -> dict[int, float]:
    tot = len(dati)
    nums = range(1, 91)
    if not dati:
        return {n: 0.0 for n in nums}
    if codice == "frequenza":
        c = Counter(n for r in dati for n in r[1])
        return {n: float(c[n]) for n in nums}
    if codice in ("ritardo", "ritardo_max", "indice_ritardo"):
        out = {}
        for n in nums:
            volte, rit, rmax = ritardi_evento([n in r[1] for r in dati])
            if codice == "ritardo":
                out[n] = float(rit)
            elif codice == "ritardo_max":
                out[n] = float(rmax)
            else:
                medio = (tot - volte) / (volte + 1)
                out[n] = rit / medio if medio else 0.0
        return out
    if codice == "tendenza":
        breve = max(1, min(param or 30, tot))
        c_tot = Counter(n for r in dati for n in r[1])
        c_br = Counter(n for r in dati[-breve:] for n in r[1])
        return {n: c_br[n] - c_tot[n] * breve / tot for n in nums}
    if codice == "successivi":
        d = max(1, param or 1)
        if tot <= d:
            return {n: 0.0 for n in nums}
        trans = matrice_transizione(dati, d)
        c = Counter()
        for a in dati[-d][1]:
            c.update(trans[a])
        return {n: float(c[n]) for n in nums}
    if codice == "posizione":
        p = min(max(param or 1, 1), 6) - 1
        c = Counter(r[1][p] for r in dati)
        return {n: float(c[n]) for n in nums}
    if codice in ("amici", "amici_ultima"):
        bersagli = set(dati[-1][1]) if codice == "amici_ultima" else {param or 1}
        c = Counter()
        for r in dati:
            presenti = bersagli & set(r[1])
            if presenti:
                for n in r[1]:
                    c[n] += len(presenti - {n})
        return {n: float(c[n]) for n in nums}
    if codice == "giorno":
        g = min(max(param or 1, 1), 7) - 1
        c = Counter(n for r in dati if r[0].weekday() == g for n in r[1])
        return {n: float(c[n]) for n in nums}
    if codice == "jolly":
        c = Counter(r[2] for r in dati)
        return {n: float(c[n]) for n in nums}
    if codice == "superstar":
        c = Counter(r[3] for r in dati if r[3])
        return {n: float(c[n]) for n in nums}
    raise ValueError(f"Misura sconosciuta: {codice}")


@dataclass
class Ingrediente:
    misura: str
    param: int = 0
    peso: float = 1.0


@dataclass
class Filtri:
    parita: int = 0                 # 0 tutti, 1 solo pari, 2 solo dispari
    da: int = 1
    a: int = 90
    decine: list[int] = field(default_factory=list)       # 1 = 1-10 ... 9 = 81-90 (vuoto = tutte)
    finali: list[int] = field(default_factory=list)       # cifra finale 0-9 (vuoto = tutte)
    escludi_usciti_ultime: int = 0  # escludi i numeri usciti nelle ultime K estrazioni
    solo_usciti_ultime: int = 0     # ammetti solo i numeri usciti nelle ultime K estrazioni

    def ammessi(self, dati: Storico) -> set[int]:
        s = set(range(max(1, self.da), min(90, self.a) + 1))
        if self.parita == 1:
            s = {n for n in s if n % 2 == 0}
        elif self.parita == 2:
            s = {n for n in s if n % 2 == 1}
        if self.decine:
            s = {n for n in s if min((n - 1) // 10, 8) + 1 in self.decine}
        if self.finali:
            s = {n for n in s if n % 10 in self.finali}
        if self.escludi_usciti_ultime:
            s -= {n for r in dati[-self.escludi_usciti_ultime:] for n in r[1]}
        if self.solo_usciti_ultime:
            s &= {n for r in dati[-self.solo_usciti_ultime:] for n in r[1]}
        return s


@dataclass
class Ricetta:
    nome: str
    descrizione: str = ""
    ultime: int = 0
    ingredienti: list[Ingrediente] = field(default_factory=list)
    filtri: Filtri = field(default_factory=Filtri)

    @property
    def codice(self) -> str:
        return "pers:" + self.nome

    def a_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def da_dict(d: dict) -> "Ricetta":
        return Ricetta(nome=d["nome"], descrizione=d.get("descrizione", ""), ultime=d.get("ultime", 0),
                       ingredienti=[Ingrediente(**i) for i in d.get("ingredienti", [])],
                       filtri=Filtri(**d.get("filtri", {})))


def esegui(ricetta: Ricetta, storico: Storico) -> RisultatoAnalisi:
    dati = finestra(storico, ricetta.ultime)
    ammessi = ricetta.filtri.ammessi(dati)
    colonne = ["Numero"]
    valori_misure = []
    totale = {n: 0.0 for n in range(1, 91)}
    for ing in ricetta.ingredienti:
        m = MISURE[ing.misura]
        etichetta = m.nome + (f" ({ing.param})" if m.param_etichetta else "")
        colonne.append(f"{etichetta} ×{ing.peso:g}")
        grezzi = calcola_misura(ing.misura, dati, ing.param)
        valori_misure.append(grezzi)
        norm = normalizza({n: grezzi[n] for n in ammessi}) if ammessi else {}
        for n, v in norm.items():
            totale[n] += ing.peso * v          # peso negativo: favorisce i valori bassi
    colonne.append("Punteggio")
    righe, numeri = [], []
    for n in sorted(ammessi, key=lambda x: -totale[x]):
        righe.append([n, *[round(vm[n], 2) for vm in valori_misure], round(totale[n], 3)])
        numeri.append([n])
    punteggi = {n: (totale[n] if n in ammessi else min(totale.values(), default=0) - 1) for n in range(1, 91)}
    nota = (f"{len(ammessi)} numeri ammessi dai filtri su {len(dati)} estrazioni. "
            "Punteggio = somma dei pesi × misure normalizzate (0-1).")
    return RisultatoAnalisi(ricetta.nome, colonne, righe, punteggi, nota, numeri)


# ------------------------------------------------------------- salvataggio
CHIAVE = "analisi_personalizzate"


def carica(archivio) -> list[Ricetta]:
    testo = archivio.leggi_impostazione(CHIAVE, "[]")
    try:
        return [Ricetta.da_dict(d) for d in json.loads(testo)]
    except (ValueError, KeyError, TypeError):
        return []


def salva_tutte(archivio, ricette: list[Ricetta]) -> None:
    archivio.scrivi_impostazione(CHIAVE, json.dumps([r.a_dict() for r in ricette], ensure_ascii=False))


def come_definizione(r: Ricetta) -> DefinizioneAnalisi:
    """Rende una ricetta utilizzabile come un'analisi qualsiasi."""
    return DefinizioneAnalisi(r.codice, "★ " + r.nome, r.descrizione or "Analisi personalizzata",
                              lambda storico, _r=r: esegui(_r, storico), [])


def tutte_le_analisi(archivio) -> dict[str, DefinizioneAnalisi]:
    out = dict(REGISTRO)
    for r in carica(archivio):
        out[r.codice] = come_definizione(r)
    return out


def esempio() -> Ricetta:
    return Ricetta(
        "Esempio: caldi e successivi",
        "Numeri usciti spesso di recente e che seguono di solito i numeri dell'ultima estrazione.",
        0,
        [Ingrediente("tendenza", 30, 1.0), Ingrediente("successivi", 1, 1.0), Ingrediente("ritardo", 0, -0.5)],
        Filtri())


GIORNI_SETTIMANA = GIORNI
