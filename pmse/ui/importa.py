"""Importazione da file con anteprima e riepilogo."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
                               QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from ..core.db import Archivio
from ..core.importatore import RisultatoLettura, leggi_file

FILTRO = "Dati estrazioni (*.csv *.txt *.xlsx *.xlsm *.dat);;Tutti i file (*.*)"


class FinestraImporta(QDialog):
    def __init__(self, archivio: Archivio, parent=None):
        super().__init__(parent)
        self.arch = archivio
        self.lettura: RisultatoLettura | None = None
        self.modificato = False
        self.setWindowTitle("Importa estrazioni da file")
        self.resize(900, 600)
        v = QVBoxLayout(self)
        v.addWidget(QLabel(
            "Scegli un file CSV, TXT o Excel: il programma riconosce da solo date, separatori e colonne, "
            "scarta le righe non valide ed evita i duplicati."))
        h = QHBoxLayout()
        b_scegli = QPushButton("📂 Scegli file...")
        b_scegli.clicked.connect(self.scegli)
        self.l_file = QLabel("Nessun file scelto")
        h.addWidget(b_scegli)
        h.addWidget(self.l_file, 1)
        v.addLayout(h)

        self.tab = QTableWidget(0, 6)
        self.tab.setHorizontalHeaderLabels(["Riga", "Data", "Sestina (ordine nel file)", "Jolly", "SuperStar",
                                            "Stato"])
        self.tab.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.tab.verticalHeader().setVisible(False)
        v.addWidget(self.tab, 3)

        self.c_sost = QCheckBox("In caso di conflitto (stessa data ma numeri diversi) usa i dati del file")
        v.addWidget(self.c_sost)
        self.esito = QPlainTextEdit()
        self.esito.setReadOnly(True)
        self.esito.setMaximumHeight(140)
        v.addWidget(self.esito, 1)

        basso = QHBoxLayout()
        self.b_importa = QPushButton("✔ Importa nell'archivio")
        self.b_importa.setEnabled(False)
        self.b_importa.clicked.connect(self.importa)
        b_chiudi = QPushButton("Chiudi")
        b_chiudi.clicked.connect(self.accept)
        basso.addStretch()
        basso.addWidget(self.b_importa)
        basso.addWidget(b_chiudi)
        v.addLayout(basso)

    def scegli(self):
        percorso, _ = QFileDialog.getOpenFileName(self, "Scegli il file di dati", "", FILTRO)
        if not percorso:
            return
        self.l_file.setText(percorso)
        try:
            self.lettura = leggi_file(percorso)
        except Exception as ex:   # file illeggibile o formato non supportato
            QMessageBox.warning(self, "Errore", f"Impossibile leggere il file:\n{ex}")
            return
        self._anteprima()

    def _anteprima(self):
        righe = [r for r in self.lettura.righe if r.testo.strip()]
        self.tab.setRowCount(len(righe))
        nuove = dup = confl = 0
        for i, r in enumerate(righe):
            e = r.estrazione
            if e:
                es = self.arch.per_data(e.data)
                if es is None:
                    stato, colore = "nuova", "#c8e6c9"
                    nuove += 1
                elif es.chiave_numeri() == e.chiave_numeri():
                    stato, colore = "già in archivio", "#eeeeee"
                    dup += 1
                else:
                    stato = f"CONFLITTO: in archivio {' '.join(map(str, es.sestina))} J{es.jolly}"
                    colore = "#ffcdd2"
                    confl += 1
                valori = [r.numero_riga, e.data.strftime("%d/%m/%Y"), " ".join(map(str, e.numeri)), e.jolly,
                          e.superstar or "", stato]
            else:
                colore = "#fff9c4"
                valori = [r.numero_riga, "", r.testo[:60], "", "", f"ignorata: {r.motivo}"]
            for c, val in enumerate(valori):
                it = QTableWidgetItem(str(val))
                it.setBackground(QColor(colore))
                it.setFlags(Qt.ItemIsEnabled)
                self.tab.setItem(i, c, it)
        self.tab.resizeColumnsToContents()
        self.esito.setPlainText(
            f"Estrazioni riconosciute: {len(self.lettura.estrazioni)}\n"
            f"  nuove: {nuove}   già presenti: {dup}   conflitti: {confl}\n"
            f"Righe ignorate (intestazioni, testo, righe incomplete): {len(self.lettura.ignorate)}")
        self.b_importa.setEnabled(bool(self.lettura.estrazioni))

    def importa(self):
        if not self.lettura:
            return
        esito = self.arch.unisci(self.lettura.estrazioni, sostituisci_conflitti=self.c_sost.isChecked())
        self.modificato = True
        testo = esito.riepilogo()
        for e, errori in esito.scartate[:20]:
            testo += f"\n  scartata {e.data:%d/%m/%Y}: {'; '.join(errori)}"
        for vecchia, nuova in esito.conflitti[:20]:
            testo += (f"\n  conflitto {vecchia.data:%d/%m/%Y}: archivio {vecchia.sestina} J{vecchia.jolly}"
                      f" / file {nuova.sestina} J{nuova.jolly}")
        self.esito.setPlainText(testo)
        self.b_importa.setEnabled(False)
        QMessageBox.information(self, "Importazione completata", esito.riepilogo())
