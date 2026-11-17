"""Modello dati di una estrazione SuperEnalotto e regole di validazione."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .gioco import SE, Gioco

PRIMA_ESTRAZIONE = date(1997, 12, 3)
GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
GIORNI_BREVI = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]

# Categorie premi come nella scheda "Aggiornamento Archivio"
CATEGORIE = ["Due", "Tre", "Quattro", "Cinque", "Cinque+", "Sei"]


@dataclass
class Estrazione:
    """Un concorso. Per l'Eurojackpot 'jolly' e 'superstar' contengono i due Euronumeri (vedi gioco.py)."""
    data: date
    numeri: list[int]                      # numeri in ordine di estrazione (se noto)
    jolly: int | None
    superstar: int | None = None
    concorso: int | None = None           # numero progressivo nell'anno
    montepremi: float | None = None
    fonte: str = "manuale"
    quote: dict[str, tuple[int | None, float | None]] = field(default_factory=dict)
    id: int | None = None
    gioco: Gioco = SE

    def __post_init__(self):
        if self.gioco.is_ej and self.jolly and self.superstar and self.jolly > self.superstar:
            self.jolly, self.superstar = self.superstar, self.jolly     # Euronumeri in ordine crescente

    @property
    def sestina(self) -> list[int]:
        """Sestina ordinata in modo crescente."""
        return sorted(self.numeri)

    @property
    def anno(self) -> int:
        return self.data.year

    def chiave_numeri(self) -> tuple:
        if self.gioco.is_ej:
            return tuple(self.sestina) + (self.jolly, self.superstar)
        return tuple(self.sestina) + (self.jolly,)


def valida(e: Estrazione) -> tuple[list[str], list[str]]:
    """Restituisce (errori, avvisi). Con errori l'estrazione non va salvata."""
    g = e.gioco
    errori: list[str] = []
    avvisi: list[str] = []
    if not isinstance(e.data, date):
        errori.append("Data non valida")
    else:
        if e.data < g.prima_estrazione:
            errori.append(f"Data precedente al primo concorso ({g.prima_estrazione:%d/%m/%Y})")
        if e.data > date.today():
            errori.append("Data nel futuro")
        if e.data.weekday() not in g.giorni_estrazione:
            avvisi.append(f"Giorno insolito per un'estrazione ({GIORNI[e.data.weekday()]})")
    if len(e.numeri) != g.k:
        errori.append(f"La {g.nome_comb} deve avere {g.k} numeri")
    if any((not isinstance(n, int)) or n < 1 or n > g.n for n in e.numeri):
        errori.append(f"I numeri devono essere compresi tra 1 e {g.n}")
    if len(set(e.numeri)) != len(e.numeri):
        errori.append(f"Numeri ripetuti nella {g.nome_comb}")
    if g.is_ej:
        em = g.euro_max(e.data if isinstance(e.data, date) else None)
        if not e.jolly or not e.superstar:
            errori.append("Mancano gli Euronumeri")
        elif not (1 <= e.jolly <= em and 1 <= e.superstar <= em):
            errori.append(f"Gli Euronumeri devono essere compresi tra 1 e {em} per questa data")
        elif e.jolly == e.superstar:
            errori.append("I due Euronumeri devono essere diversi")
        return errori, avvisi
    if e.jolly is None:
        errori.append("Manca il numero Jolly")
    elif not 1 <= e.jolly <= 90:
        errori.append("Jolly fuori intervallo 1-90")
    elif e.jolly in e.numeri:
        errori.append("Il Jolly non può essere uno dei 6 numeri")
    if e.superstar is not None and not 1 <= e.superstar <= 90:
        errori.append("SuperStar fuori intervallo 1-90")
    return errori, avvisi


def formatta_data(d: date) -> str:
    return d.strftime("%d/%m/%Y")
