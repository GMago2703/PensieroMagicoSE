"""Consultazione dell'archivio: tabella ordinabile e filtrabile."""
from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QSpinBox,
                               QTableView, QVBoxLayout)

from ..core.db import Archivio
from ..core.modello import GIORNI_BREVI
from .editor import EditorEstrazione

COLONNE = ["Pos.", "Conc.", "Data", "Giorno", "N1", "N2", "N3", "N4", "N5", "N6", "Jolly", "SuperStar",
           "Ordine di estrazione", "Fonte"]


class ModelloArchivio(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.righe = []          # (pos, estrazione)
        self.evidenziato = 0

    def carica(self, righe, evidenziato: int = 0):
        self.beginResetModel()
        self.righe = righe
        self.evidenziato = evidenziato
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self.righe)

    def columnCount(self, parent=QModelIndex()):
        return len(COLONNE)

    def headerData(self, s, o, ruolo=Qt.DisplayRole):
        if o == Qt.Horizontal and ruolo == Qt.DisplayRole:
            return COLONNE[s]
        return None

    def data(self, idx, ruolo=Qt.DisplayRole):
        pos, e = self.righe[idx.row()]
        c = idx.column()
        if ruolo == Qt.DisplayRole:
            s = e.sestina
            valori = [pos, e.concorso, e.data.strftime("%d/%m/%Y"), GIORNI_BREVI[e.data.weekday()],
                      *s, e.jolly, e.superstar or "",
                      " ".join(map(str, e.numeri)) if e.numeri != s else "", e.fonte]
            return valori[c]
        if ruolo == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        if ruolo == Qt.BackgroundRole:
            n = self.evidenziato
            if n and ((4 <= c <= 9 and e.sestina[c - 4] == n) or (c == 10 and e.jolly == n)
                      or (c == 11 and e.superstar == n)):
                return QBrush(QColor("#1e90ff"))
            if c == 10:
                return QBrush(QColor("#ffe0b2"))
            if c == 11:
                return QBrush(QColor("#fff59d"))
        if ruolo == Qt.ForegroundRole:
            n = self.evidenziato
            if n and 4 <= c <= 11:
                pos_val = {**{4 + i: v for i, v in enumerate(e.sestina)}, 10: e.jolly, 11: e.superstar}
                if pos_val.get(c) == n:
                    return QBrush(QColor("white"))
        return None


class FinestraArchivio(QDialog):
    def __init__(self, archivio: Archivio, parent=None):
        super().__init__(parent)
        self.arch = archivio
        self.crescente = False
        self.modificato = False
        self.setWindowTitle("Archivio estrazioni")
        self.resize(1050, 650)
        v = QVBoxLayout(self)

        filtri = QHBoxLayout()
        self.b_ordine = QPushButton()
        self.b_ordine.clicked.connect(self._inverti)
        filtri.addWidget(self.b_ordine)
        filtri.addSpacing(16)
        filtri.addWidget(QLabel("Anno:"))
        self.c_anno = QComboBox()
        self.c_anno.currentIndexChanged.connect(self.aggiorna)
        filtri.addWidget(self.c_anno)
        filtri.addSpacing(16)
        filtri.addWidget(QLabel("Cerca numero:"))
        self.s_num = QSpinBox()
        self.s_num.setRange(0, 90)
        self.s_num.setSpecialValueText("—")
        self.s_num.valueChanged.connect(self.aggiorna)
        filtri.addWidget(self.s_num)
        self.c_dove = QComboBox()
        self.c_dove.addItems(["solo estrazioni che lo contengono", "evidenzia soltanto"])
        self.c_dove.currentIndexChanged.connect(self.aggiorna)
        filtri.addWidget(self.c_dove)
        filtri.addStretch()
        self.l_info = QLabel()
        filtri.addWidget(self.l_info)
        v.addLayout(filtri)

        self.modello = ModelloArchivio()
        self.tabella = QTableView()
        self.tabella.setModel(self.modello)
        self.tabella.setAlternatingRowColors(True)
        self.tabella.setSelectionBehavior(QTableView.SelectRows)
        self.tabella.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tabella.horizontalHeader().setStretchLastSection(True)
        self.tabella.verticalHeader().setVisible(False)
        self.tabella.doubleClicked.connect(self._apri)
        v.addWidget(self.tabella)

        basso = QHBoxLayout()
        b_nuova = QPushButton("➕ Nuova estrazione")
        b_nuova.clicked.connect(lambda: self._editor(None, True))
        b_mod = QPushButton("✎ Modifica selezionata")
        b_mod.clicked.connect(lambda: self._apri(self.tabella.currentIndex()))
        b_chiudi = QPushButton("Chiudi")
        b_chiudi.clicked.connect(self.accept)
        basso.addWidget(b_nuova)
        basso.addWidget(b_mod)
        basso.addStretch()
        basso.addWidget(QLabel("Doppio clic su una riga per aprirla."))
        basso.addWidget(b_chiudi)
        v.addLayout(basso)
        self._ricarica_anni()

    def _ricarica_anni(self):
        self.c_anno.blockSignals(True)
        corrente = self.c_anno.currentText()
        self.c_anno.clear()
        self.c_anno.addItem("Tutti")
        for a in reversed(self.arch.anni()):
            self.c_anno.addItem(str(a))
        i = self.c_anno.findText(corrente)
        self.c_anno.setCurrentIndex(max(i, 0))
        self.c_anno.blockSignals(False)
        self.aggiorna()

    def _inverti(self):
        self.crescente = not self.crescente
        self.aggiorna()

    def aggiorna(self):
        self.b_ordine.setText("Ordine: dal più vecchio ▲" if self.crescente else "Ordine: dal più recente ▼")
        tutte = self.arch.tutte(crescente=True)
        righe = [(i + 1, e) for i, e in enumerate(tutte)]
        anno = self.c_anno.currentText()
        if anno and anno != "Tutti":
            righe = [r for r in righe if r[1].data.year == int(anno)]
        n = self.s_num.value()
        if n and self.c_dove.currentIndex() == 0:
            righe = [r for r in righe if n in r[1].numeri or r[1].jolly == n or r[1].superstar == n]
        if not self.crescente:
            righe.reverse()
        self.modello.carica(righe, n)
        self.l_info.setText(f"{len(righe)} estrazioni mostrate su {len(tutte)}")

    def _apri(self, idx):
        if not idx.isValid():
            return
        _, e = self.modello.righe[idx.row()]
        self._editor(e.data, False)

    def _editor(self, data, nuova):
        dlg = EditorEstrazione(self.arch, data, nuova, self)
        dlg.exec()
        if dlg.modificato:
            self.modificato = True
            self._ricarica_anni()
