"""Menu Analisi: esegue le analisi (predefinite e personalizzate) e mostra
tabella + griglia: clic su una riga = evidenzia i numeri interessati."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
                               QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import personalizzate, vincite
from ..core.gioco import Storico
from ..core.db import Archivio
from .griglia import Griglia90
from .schermo import adatta_schermo

RUOLO_NUMERI = Qt.UserRole + 1


class ElementoNumerico(QTableWidgetItem):
    """Ordina le colonne numeriche come numeri e non come testo."""

    def __lt__(self, other):
        try:
            return float(self.text()) < float(other.text())
        except ValueError:
            return super().__lt__(other)


def riempi_tabella(tab: QTableWidget, colonne: list[str], righe: list[list], numeri_riga=None):
    tab.setSortingEnabled(False)
    tab.clear()
    tab.setColumnCount(len(colonne))
    tab.setHorizontalHeaderLabels(colonne)
    tab.setRowCount(len(righe))
    for r, riga in enumerate(righe):
        for c, val in enumerate(riga):
            it = ElementoNumerico(str(val))
            it.setTextAlignment(Qt.AlignCenter)
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if c == 0 and numeri_riga and r < len(numeri_riga):
                it.setData(RUOLO_NUMERI, numeri_riga[r])
            tab.setItem(r, c, it)
    tab.setSortingEnabled(True)
    tab.resizeColumnsToContents()


def numeri_selezionati(tab: QTableWidget) -> set[int]:
    numeri: set[int] = set()
    for r in {i.row() for i in tab.selectedItems()}:
        it = tab.item(r, 0)
        if it and it.data(RUOLO_NUMERI):
            numeri.update(it.data(RUOLO_NUMERI))
    return numeri


class FinestraAnalisi(QDialog):
    def __init__(self, archivio: Archivio, codice: str | None = None, parent=None):
        super().__init__(parent)
        self.arch = archivio
        self.risultato = None
        self.setWindowTitle(f"Analisi – {archivio.gioco.nome}")
        adatta_schermo(self, 1150, 680)
        v = QVBoxLayout(self)
        h = QHBoxLayout()
        h.addWidget(QLabel("Analisi:"))
        self.c_analisi = QComboBox()
        h.addWidget(self.c_analisi, 1)
        b_cost = QPushButton("🛠 Costruttore analisi personalizzate...")
        b_cost.clicked.connect(self._costruttore)
        h.addWidget(b_cost)
        v.addLayout(h)
        self.l_desc = QLabel()
        self.l_desc.setWordWrap(True)
        self.l_desc.setStyleSheet("color:#333; font-style:italic;")
        v.addWidget(self.l_desc)
        self.c_gruppo = QComboBox()
        self.c_gruppo.addItems(["tutti i concorsi", "★ solo i concorsi con il 6", "tutti tranne quelli con il 6"])
        self.c_gruppo.setToolTip("Esegue l'analisi solo sul gruppo dei concorsi in cui è stato vinto il 6 "
                                 "(o su tutti gli altri)")
        self.c_gruppo.currentIndexChanged.connect(lambda _: self.esegui())
        if not archivio.gioco.is_ej:
            hg = QHBoxLayout()
            hg.addWidget(QLabel("Concorsi da analizzare:"))
            hg.addWidget(self.c_gruppo)
            hg.addStretch()
            v.addLayout(hg)
        self.box_param = QWidget()
        self.form = QFormLayout(self.box_param)
        v.addWidget(self.box_param)
        b = QPushButton("▶ Esegui analisi")
        b.clicked.connect(self.esegui)
        v.addWidget(b, 0, Qt.AlignLeft)

        div = QSplitter()
        self.tab = QTableWidget()
        self.tab.verticalHeader().setVisible(False)
        self.tab.setSelectionBehavior(QTableWidget.SelectRows)
        self.tab.itemSelectionChanged.connect(self._riga_scelta)
        div.addWidget(self.tab)
        destra = QWidget()
        dv = QVBoxLayout(destra)
        self.l_griglia = QLabel()
        self.l_griglia.setWordWrap(True)
        dv.addWidget(self.l_griglia)
        self.griglia = Griglia90(selezionabile=False, n=archivio.gioco.n)
        self.griglia.setFixedSize(380, 33 * ((archivio.gioco.n + 9) // 10) + 3)
        dv.addWidget(self.griglia, 0, Qt.AlignTop)
        b_mappa = QPushButton("Mostra la mappa dei punteggi")
        b_mappa.clicked.connect(self._mappa)
        dv.addWidget(b_mappa)
        dv.addStretch()
        div.addWidget(destra)
        div.setSizes([720, 400])
        v.addWidget(div, 1)
        self.l_nota = QLabel()
        self.l_nota.setWordWrap(True)
        v.addWidget(self.l_nota)
        self.campi: dict = {}
        self._carica_elenco(codice)
        self.c_analisi.currentIndexChanged.connect(self._cambia)
        self._cambia()

    def _carica_elenco(self, codice=None):
        self.analisi = personalizzate.tutte_le_analisi(self.arch)
        self.c_analisi.blockSignals(True)
        self.c_analisi.clear()
        for d in self.analisi.values():
            self.c_analisi.addItem(d.nome, d.codice)
        if codice:
            i = self.c_analisi.findData(codice)
            if i >= 0:
                self.c_analisi.setCurrentIndex(i)
        self.c_analisi.blockSignals(False)

    def _cambia(self):
        d = self.analisi[self.c_analisi.currentData()]
        self.l_desc.setText(d.descrizione)
        while self.form.rowCount():
            self.form.removeRow(0)
        self.campi = {}
        for p in d.parametri:
            if p.scelte:
                w = QComboBox()
                w.addItems(p.scelte)
                w.setCurrentIndex(p.predefinito)
            else:
                w = QSpinBox()
                w.setRange(p.minimo, p.massimo)
                w.setValue(p.predefinito)
            w.setToolTip(p.aiuto)
            self.form.addRow(p.etichetta, w)
            self.campi[p.nome] = w
        self.esegui()

    def _valori(self) -> dict:
        return {k: (w.currentIndex() if isinstance(w, QComboBox) else w.value()) for k, w in self.campi.items()}

    def esegui(self):
        d = self.analisi[self.c_analisi.currentData()]
        storico = self.arch.sestine()
        if not storico:
            self.l_nota.setText("L'archivio è vuoto: carica prima le estrazioni (menu Internet o Archivio).")
            return
        if not self.arch.gioco.is_ej and self.c_gruppo.currentIndex():
            con6 = {x for x in vincite.date_con_6(self.arch)}
            voglio = self.c_gruppo.currentIndex() == 1
            storico = Storico([r for r in storico if (r[0] in con6) == voglio], storico.gioco)
            if len(storico) < 2:
                self.l_nota.setText("Nessun concorso con il 6 noto: aggiorna i vincitori (menu Internet).")
                return
        ris = d.funzione(storico, **self._valori())
        self.risultato = ris
        riempi_tabella(self.tab, ris.colonne, ris.righe, ris.numeri_riga)
        self.setWindowTitle(f"Analisi {self.arch.gioco.nome} – {ris.titolo}")
        gruppo = ["", " [solo i concorsi con il 6]", " [esclusi i concorsi con il 6]"][self.c_gruppo.currentIndex()]
        self.l_nota.setText(ris.nota + (f"\nAnalisi eseguita su {len(storico)} concorsi{gruppo}." if gruppo else ""))
        self._mappa()

    def _mappa(self):
        if self.risultato and self.risultato.punteggi:
            self.griglia.mostra_punteggi(self.risultato.punteggi)
            self.l_griglia.setText("<b>Mappa dei punteggi</b> (rosso = punteggio più alto). "
                                   "Clic su una riga per evidenziare i numeri interessati.")
        else:
            self.griglia.evidenzia(set())
            self.l_griglia.setText("<b>Numeri interessati</b>: fai clic su una riga della tabella")

    def _riga_scelta(self):
        numeri = numeri_selezionati(self.tab)
        if numeri:
            self.griglia.evidenzia(numeri)
            self.l_griglia.setText(f"<b>Numeri interessati</b>: {' '.join(map(str, sorted(numeri)))}")

    def _costruttore(self):
        from .costruttore import FinestraCostruttore
        FinestraCostruttore(self.arch, self).exec()
        codice = self.c_analisi.currentData()
        self._carica_elenco(codice)
        self._cambia()
