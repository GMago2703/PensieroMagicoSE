"""Definizione dei giochi gestiti: SuperEnalotto (Pensiero Magico SE) ed Eurojackpot (Pensiero Magico EJ).

I due giochi condividono il codice ma restano rigidamente separati: ognuno ha la sua
cartella dati, il suo archivio, le sue impostazioni, le sue previsioni e il suo
apprendimento. Tutto ciò che dipende dal gioco (quanti numeri, da quanti, i numeri
speciali) viene letto da qui.

Convenzione per i numeri speciali (campi "jolly" e "superstar" dell'archivio):
- SuperEnalotto: jolly = Jolly (dagli 84 numeri rimasti), superstar = SuperStar (1-90)
- Eurojackpot:   jolly = 1° Euronumero, superstar = 2° Euronumero (in ordine crescente)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Gioco:
    codice: str
    nome: str                     # nome del gioco
    nome_app: str                 # nome del software
    cartella: str                 # cartella dati in %APPDATA%
    n: int                        # numeri estraibili (1..n)
    k: int                        # numeri estratti
    nome_comb: str                # "sestina" / "cinquina"
    nome_comb_pl: str
    prima_estrazione: date
    combinazioni_magico: int      # quante combinazioni produce Magico Pensiero
    nome_extra1: str
    nome_extra2: str
    giorni_estrazione: tuple      # giorni della settimana abituali (0 = lunedì)

    @property
    def is_ej(self) -> bool:
        return self.codice == "EJ"

    @property
    def soglia_alti(self) -> int:     # "alti" = numeri sopra la metà
        return self.n // 2

    @property
    def decine(self) -> int:
        return (self.n + 9) // 10

    def euro_max(self, giorno: date | None = None) -> int:
        """Eurojackpot: gli Euronumeri sono stati 2 su 8 fino al 3/10/2014, 2 su 10 fino al 18/3/2022,
        poi 2 su 12."""
        if not self.is_ej:
            return 0
        giorno = giorno or date.today()
        if giorno <= date(2014, 10, 3):
            return 8
        if giorno <= date(2022, 3, 18):
            return 10
        return 12

    def C(self, maiuscola: bool = True, plurale: bool = False) -> str:
        t = self.nome_comb_pl if plurale else self.nome_comb
        return t[:1].upper() + t[1:] if maiuscola else t


SE = Gioco("SE", "SuperEnalotto", "Pensiero Magico SE", "PensieroMagicoSE", 90, 6, "sestina", "sestine",
           date(1997, 12, 3), 3, "Jolly", "SuperStar", (1, 2, 3, 4, 5))
EJ = Gioco("EJ", "Eurojackpot", "Pensiero Magico EJ", "PensieroMagicoEJ", 50, 5, "cinquina", "cinquine",
           date(2012, 3, 23), 1, "Euronumero 1", "Euronumero 2", (1, 4))
GIOCHI = {"SE": SE, "EJ": EJ}


class Storico(list):
    """Elenco di estrazioni (data, numeri ordinati, extra1, extra2, ordine di estrazione) che sa a
    quale gioco appartiene. Le "fette" (storico[:i]) conservano il gioco."""

    def __init__(self, righe=(), gioco: Gioco = SE):
        super().__init__(righe)
        self.gioco = gioco

    def __getitem__(self, i):
        r = super().__getitem__(i)
        return Storico(r, self.gioco) if isinstance(i, slice) else r


def gioco_di(storico) -> Gioco:
    return getattr(storico, "gioco", SE)
