"""Modello dati di una estrazione SuperEnalotto e regole di validazione."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

PRIMA_ESTRAZIONE = date(1997, 12, 3)
GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
GIORNI_BREVI = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]

# Categorie premi come nella scheda "Aggiornamento Archivio"
CATEGORIE = ["Due", "Tre", "Quattro", "Cinque", "Cinque+", "Sei"]


@dataclass
class Estrazione:
    data: date
    numeri: list[int]                      # sestina in ordine di estrazione (se nota)
    jolly: int | None
    superstar: int | None = None
    concorso: int | None = None           # numero progressivo nell'anno
    montepremi: float | None = None
    fonte: str = "manuale"
    quote: dict[str, tuple[int | None, float | None]] = field(default_factory=dict)
    id: int | None = None

    @property
    def sestina(self) -> list[int]:
        """Sestina ordinata in modo crescente."""
        return sorted(self.numeri)

    @property
    def anno(self) -> int:
        return self.data.year

    def chiave_numeri(self) -> tuple:
        return tuple(self.sestina) + (self.jolly,)


def valida(e: Estrazione) -> tuple[list[str], list[str]]:
    """Restituisce (errori, avvisi). Con errori l'estrazione non va salvata."""
    errori: list[str] = []
    avvisi: list[str] = []
    if not isinstance(e.data, date):
        errori.append("Data non valida")
    else:
        if e.data < PRIMA_ESTRAZIONE:
            errori.append("Data precedente al primo concorso (03/12/1997)")
        if e.data > date.today():
            errori.append("Data nel futuro")
        if e.data.weekday() in (0, 6):
            avvisi.append(f"Giorno insolito per un'estrazione ({GIORNI[e.data.weekday()]})")
    if len(e.numeri) != 6:
        errori.append("La sestina deve avere 6 numeri")
    if any((not isinstance(n, int)) or n < 1 or n > 90 for n in e.numeri):
        errori.append("I numeri devono essere compresi tra 1 e 90")
    if len(set(e.numeri)) != len(e.numeri):
        errori.append("Numeri ripetuti nella sestina")
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
