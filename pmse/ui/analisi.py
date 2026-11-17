"""Menu Analisi: esegue le analisi registrate e mostra tabella + mappa dei punteggi."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
                               QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import analisi
from ..core.db import Archivio
from .griglia import Griglia90


class ElementoNumerico(QTableWidgetItem):
    """Ordina le colonne numeriche come numeri e non come testo."""

    def __lt__(self, other):
        try:
            return float(self.text()) < float(other.text())
        except ValueError:
            return super().__lt__(other)


class FinestraAnalisi(QDialog):
    def __init__(self, archivio: Archivio, codice: str | None = None, parent=None):
        super().__init__(parent)
        self.arch = archivio
        self.setWindowTitle("Analisi")
        self.resize(1100, 640)
        v = QVBoxLayout(self)
        h = QHBoxLayout()
        h.addWidget(QLabel("Analisi:"))
        self.c_analisi = QComboBox()
        for d in analisi.REGISTRO.values():
            self.c_analisi.addItem(d.nome, d.codice)
        h.addWidget(self.c_analisi, 1)
        v.addLayout(h)
        self.l_desc = QLabel()
        self.l_desc.setWordWrap(True)
        self.l_desc.setStyleSheet("color:#333; font-style:italic;")
        v.addWidget(self.l_desc)
        self.box_param = QWidget()
        self.form = QFormLayout(self.box_param)
        v.addWidget(self.box_param)
        b = QPushButton("▶ Esegui analisi")
        b.clicked.connect(self.esegui)
        v.addWidget(b, 0, Qt.AlignLeft)

        div = QSplitter()
        self.tab = QTableWidget()
        self.tab.setSortingEnabled(True)
        self.tab.verticalHeader().setVisible(False)
        div.addWidget(self.tab)
        destra = QWidget()
        dv = QVBoxLayout(destra)
        dv.addWidget(QLabel("<b>Mappa dei punteggi</b> (rosso = punteggio più alto)"))
        self.griglia = Griglia90(selezionabile=False)
        dv.addWidget(self.griglia, 1)
        div.addWidget(destra)
        div.setSizes([620, 460])
        v.addWidget(div, 1)
        self.l_nota = QLabel()
        self.l_nota.setWordWrap(True)
        v.addWidget(self.l_nota)
        self.spin: dict[str, QSpinBox] = {}
        if codice:
            i = self.c_analisi.findData(codice)
            if i >= 0:
                self.c_analisi.setCurrentIndex(i)
        self.c_analisi.currentIndexChanged.connect(self._cambia)
        self._cambia()

    def _cambia(self):
        d = analisi.REGISTRO[self.c_analisi.currentData()]
        self.l_desc.setText(d.descrizione)
        while self.form.rowCount():
            self.form.removeRow(0)
        self.spin = {}
        for p in d.parametri:
            s = QSpinBox()
            s.setRange(p.minimo, p.massimo)
            s.setValue(p.predefinito)
            s.setToolTip(p.aiuto)
            self.form.addRow(p.etichetta, s)
            self.spin[p.nome] = s
        self.esegui()

    def esegui(self):
        d = analisi.REGISTRO[self.c_analisi.currentData()]
        storico = self.arch.sestine()
        if not storico:
            self.l_nota.setText("L'archivio è vuoto: carica prima le estrazioni (menu Internet o Archivio).")
            return
        ris = d.funzione(storico, **{k: s.value() for k, s in self.spin.items()})
        self.tab.setSortingEnabled(False)
        self.tab.clear()
        self.tab.setColumnCount(len(ris.colonne))
        self.tab.setHorizontalHeaderLabels(ris.colonne)
        self.tab.setRowCount(len(ris.righe))
        for r, riga in enumerate(ris.righe):
            for c, val in enumerate(riga):
                it = ElementoNumerico(str(val))
                it.setTextAlignment(Qt.AlignCenter)
                it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.tab.setItem(r, c, it)
        self.tab.setSortingEnabled(True)
        self.tab.resizeColumnsToContents()
        self.griglia.mostra_punteggi(ris.punteggi)
        self.setWindowTitle(f"Analisi – {ris.titolo}")
        self.l_nota.setText(ris.nota)
