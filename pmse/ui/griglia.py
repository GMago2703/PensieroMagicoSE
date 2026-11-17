"""Tabella dei 90 numeri (9 righe x 10 colonne), usata sia a sinistra
(numeri selezionabili) sia a destra (risultato Magico Pensiero)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QGridLayout, QLabel, QSizePolicy, QWidget

CELLA_BASE = "#7ff0f6"
CELLA_SEL = "#1e90ff"
COLORI_SESTINE = ["#e53935", "#43a047", "#8e24aa"]   # sestina 1, 2, 3
COLORE_JOLLY = "#fb8c00"
COLORE_SUPERSTAR = "#fdd835"


class Cella(QLabel):
    cliccata = Signal(int)

    def __init__(self, numero: int):
        super().__init__(str(numero))
        self.numero = numero
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(30, 26)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        f = QFont("Segoe UI", 11)
        self.setFont(f)
        self.imposta(CELLA_BASE, "#0b2a6b")

    def imposta(self, sfondo: str, testo: str = "#0b2a6b", bordo: str | None = None, tooltip: str = ""):
        b = f"2px solid {bordo}" if bordo else "1px solid transparent"
        self.setStyleSheet(f"QLabel {{ background:{sfondo}; color:{testo}; border:{b}; border-radius:3px; }}")
        self.setToolTip(tooltip)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.cliccata.emit(self.numero)
        super().mousePressEvent(ev)


class Griglia90(QWidget):
    selezione_cambiata = Signal(list)

    def __init__(self, selezionabile: bool = True, parent=None):
        super().__init__(parent)
        self.selezionabile = selezionabile
        self.selezionati: set[int] = set()
        self.celle: dict[int, Cella] = {}
        lay = QGridLayout(self)
        lay.setSpacing(2)
        lay.setContentsMargins(4, 4, 4, 4)
        for n in range(1, 91):
            c = Cella(n)
            c.cliccata.connect(self._clic)
            self.celle[n] = c
            lay.addWidget(c, (n - 1) // 10, (n - 1) % 10)
        self.setStyleSheet("Griglia90 { background:#7ff0f6; }")

    # ----------------------------------------------------------- selezione
    def _clic(self, n: int):
        if not self.selezionabile:
            return
        if n in self.selezionati:
            self.selezionati.discard(n)
        else:
            self.selezionati.add(n)
        self._ridisegna_selezione()

    def _ridisegna_selezione(self):
        for n, c in self.celle.items():
            if n in self.selezionati:
                c.imposta(CELLA_SEL, "white")
            else:
                c.imposta(CELLA_BASE)
        self.selezione_cambiata.emit(sorted(self.selezionati))

    def seleziona_tutti(self):
        self.selezionati = set(range(1, 91))
        self._ridisegna_selezione()

    def azzera(self):
        self.selezionati.clear()
        self._ridisegna_selezione()

    # ------------------------------------------------------- visualizzazioni
    def mostra_sestine(self, sestine: list[list[int]], jolly: int | None, superstar: int | None):
        """Colora le 3 sestine; un numero presente in più sestine prende il colore della prima."""
        for c in self.celle.values():
            c.imposta(CELLA_BASE)
        for i in reversed(range(len(sestine))):
            for n in sestine[i]:
                self.celle[n].imposta(COLORI_SESTINE[i % 3], "white", tooltip=f"Sestina {i + 1}")
        if jolly:
            self.celle[jolly].imposta(COLORE_JOLLY, "white", bordo="#000", tooltip="Jolly")
        if superstar:
            c = self.celle[superstar]
            c.imposta(COLORE_SUPERSTAR, "#000", bordo="#b8860b", tooltip="SuperStar")

    def mostra_punteggi(self, punteggi: dict[int, float]):
        """Mappa di calore: dal bianco (punteggio basso) al rosso (alto)."""
        if not punteggi:
            for c in self.celle.values():
                c.imposta(CELLA_BASE)
            return
        lo, hi = min(punteggi.values()), max(punteggi.values())
        for n, c in self.celle.items():
            v = punteggi.get(n, lo)
            t = 0.5 if hi == lo else (v - lo) / (hi - lo)
            r, g, b = 255, int(255 - 200 * t), int(255 - 220 * t)
            c.imposta(f"rgb({r},{g},{b})", "#000" if t < 0.6 else "white", tooltip=f"Punteggio: {round(v, 3)}")

    def evidenzia(self, numeri: set[int], colore: str = CELLA_SEL):
        for n, c in self.celle.items():
            c.imposta(colore, "white") if n in numeri else c.imposta(CELLA_BASE)
