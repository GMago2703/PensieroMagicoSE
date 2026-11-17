"""Consultazione dell'archivio: tabella ordinabile e filtrabile."""
from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QSpinBox,
                               QTableView, QVBoxLayout)

from ..core import vincite
from ..core.db import Archivio
from ..core.modello import GIORNI_BREVI
from .editor import EditorEstrazione
from .schermo import adatta_schermo

ORO = "#ffd54f"


def colonne(g) -> list[str]:
    speciali = ["Euro 1", "Euro 2"] if g.is_ej else ["Jolly", "SuperStar"]
    base = ["Pos.", "Conc.", "Data", "Giorno", *[f"N{i}" for i in range(1, g.k + 1)], *speciali,
            "Ordine di estrazione", "Fonte"]
    return base if g.is_ej else base + ["★ 6 vinto"]


class ModelloArchivio(QAbstractTableModel):
    def __init__(self, gioco=None):
        super().__init__()
        from ..core.gioco import SE
        self.g = gioco or SE
        self.colonne = colonne(self.g)
        self.righe = []          # (pos, estrazione)
        self.evidenziato = 0
        self.vincite = {}        # data ISO -> Vincite (solo SuperEnalotto)

    def carica(self, righe, evidenziato: int = 0):
        self.beginResetModel()
        self.righe = righe
        self.evidenziato = evidenziato
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self.righe)

    def columnCount(self, parent=QModelIndex()):
        return len(self.colonne)

    def headerData(self, s, o, ruolo=Qt.DisplayRole):
        if o == Qt.Horizontal and ruolo == Qt.DisplayRole:
            return self.colonne[s]
        return None

    def _valori_numeri(self, e) -> dict[int, int]:
        """Colonna -> numero (per evidenziare il numero cercato)."""
        k = self.g.k
        out = {4 + i: v for i, v in enumerate(e.sestina)}
        out[4 + k], out[5 + k] = e.jolly, e.superstar
        return out

    def data(self, idx, ruolo=Qt.DisplayRole):
        pos, e = self.righe[idx.row()]
        c = idx.column()
        k = self.g.k
        if ruolo == Qt.DisplayRole:
            s = e.sestina
            valori = [pos, e.concorso, e.data.strftime("%d/%m/%Y"), GIORNI_BREVI[e.data.weekday()],
                      *s, e.jolly, e.superstar or "",
                      " ".join(map(str, e.numeri)) if e.numeri != s else "", e.fonte]
            if not self.g.is_ej:
                v = self.vincite.get(e.data.isoformat())
                valori.append(f"★ {v.p6} – {v.premio6}" if v and v.p6 else "")
            return valori[c]
        if ruolo == Qt.ToolTipRole and not self.g.is_ej:
            v = self.vincite.get(e.data.isoformat())
            if v:
                return (f"Vincitori: 6 punti {v.p6}, 5+1 {v.p51}, 5 punti {v.p5}, 4 punti {v.p4}, "
                        f"3 punti {v.p3}" + (f"\nPremio del 6: {v.premio6}" if v.p6 else ""))
        if ruolo == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        n = self.evidenziato
        if ruolo == Qt.BackgroundRole:
            # per l'Eurojackpot si evidenziano solo i numeri principali (gli Euronumeri sono un'altra urna)
            limite = 4 + k if self.g.is_ej else 6 + k
            if n and 4 <= c < limite and self._valori_numeri(e).get(c) == n:
                return QBrush(QColor("#1e90ff"))
            if not self.g.is_ej:
                v = self.vincite.get(e.data.isoformat())
                if v and v.p6:
                    return QBrush(QColor(ORO))           # concorso in cui è stato vinto il 6
            if c == 4 + k:
                return QBrush(QColor("#bbdefb" if self.g.is_ej else "#ffe0b2"))
            if c == 5 + k:
                return QBrush(QColor("#bbdefb" if self.g.is_ej else "#fff59d"))
        if ruolo == Qt.ForegroundRole:
            limite = 4 + k if self.g.is_ej else 6 + k
            if n and 4 <= c < limite and self._valori_numeri(e).get(c) == n:
                return QBrush(QColor("white"))
        return None


class FinestraArchivio(QDialog):
    def __init__(self, archivio: Archivio, parent=None):
        super().__init__(parent)
        self.arch = archivio
        self.crescente = False
        self.modificato = False
        self.setWindowTitle(f"Archivio estrazioni – {archivio.gioco.nome}")
        adatta_schermo(self, 1050, 650)
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
        self.s_num.setRange(0, archivio.gioco.n)
        self.s_num.setSpecialValueText("—")
        self.s_num.valueChanged.connect(self.aggiorna)
        filtri.addWidget(self.s_num)
        self.c_dove = QComboBox()
        self.c_dove.addItems(["solo estrazioni che lo contengono", "evidenzia soltanto"])
        self.c_dove.currentIndexChanged.connect(self.aggiorna)
        filtri.addWidget(self.c_dove)
        self.c_sei = QComboBox()
        self.c_sei.addItems(["tutti i concorsi", "★ solo quelli con il 6", "tutti tranne quelli con il 6"])
        self.c_sei.setToolTip("I concorsi in cui è stato vinto il 6 sono evidenziati in oro")
        self.c_sei.currentIndexChanged.connect(self.aggiorna)
        if not archivio.gioco.is_ej:
            filtri.addSpacing(16)
            filtri.addWidget(self.c_sei)
        filtri.addStretch()
        self.l_info = QLabel()
        filtri.addWidget(self.l_info)
        v.addLayout(filtri)

        self.modello = ModelloArchivio(archivio.gioco)
        self.modello.vincite = vincite.carica(archivio) if not archivio.gioco.is_ej else {}
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
            if self.arch.gioco.is_ej:
                righe = [r for r in righe if n in r[1].numeri]
            else:
                righe = [r for r in righe if n in r[1].numeri or r[1].jolly == n or r[1].superstar == n]
        if not self.arch.gioco.is_ej and self.c_sei.currentIndex():
            con6 = {k for k, v in self.modello.vincite.items() if v.p6}
            voglio = self.c_sei.currentIndex() == 1
            righe = [r for r in righe if (r[1].data.isoformat() in con6) == voglio]
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
