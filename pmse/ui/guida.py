"""Help → Guida all'uso: capitoli a sinistra, testo a destra, ricerca e salvataggio in PDF."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox,
                               QPushButton, QSplitter, QTextBrowser, QVBoxLayout)

from ..core import guida
from ..core.gioco import Gioco
from .schermo import adatta_schermo


class FinestraGuida(QDialog):
    def __init__(self, g: Gioco, parent=None, capitolo: str | None = None):
        super().__init__(parent)
        self.g = g
        self.cap = guida.capitoli(g)
        self.setWindowTitle(f"📖 Guida all'uso – {g.nome_app}")
        adatta_schermo(self, 1100, 780)
        v = QVBoxLayout(self)
        h = QHBoxLayout()
        h.addWidget(QLabel("Cerca nella guida:"))
        self.e_cerca = QLineEdit()
        self.e_cerca.setPlaceholderText("per esempio: sistema, backup, intelligenza artificiale...")
        self.e_cerca.returnPressed.connect(self.cerca)
        h.addWidget(self.e_cerca, 1)
        b = QPushButton("Cerca")
        b.clicked.connect(self.cerca)
        h.addWidget(b)
        b = QPushButton("💾 Salva in PDF")
        b.clicked.connect(self.salva_pdf)
        h.addWidget(b)
        v.addLayout(h)
        sp = QSplitter(Qt.Horizontal)
        self.elenco = QListWidget()
        self.elenco.setMaximumWidth(330)
        for _, titolo, _ in self.cap:
            self.elenco.addItem(titolo)
        self.elenco.currentRowChanged.connect(self._mostra)
        sp.addWidget(self.elenco)
        self.testo = QTextBrowser()
        self.testo.document().setDefaultStyleSheet(guida.STILE)
        sp.addWidget(self.testo)
        sp.setStretchFactor(1, 1)
        v.addWidget(sp, 1)
        h = QHBoxLayout()
        h.addStretch()
        b = QPushButton("Chiudi")
        b.clicked.connect(self.accept)
        h.addWidget(b)
        v.addLayout(h)
        riga = next((i for i, (c, _, _) in enumerate(self.cap) if c == capitolo), 0)
        self.elenco.setCurrentRow(riga)

    def _mostra(self, riga: int):
        if 0 <= riga < len(self.cap):
            self.testo.setHtml(self.cap[riga][2])

    def cerca(self):
        """Cerca il testo: dal capitolo aperto in avanti, poi dall'inizio."""
        q = self.e_cerca.text().strip().lower()
        if not q:
            return
        if self.testo.find(q):
            return
        n = len(self.cap)
        for passo in range(1, n + 1):
            i = (self.elenco.currentRow() + passo) % n
            if q in self.cap[i][2].lower() or q in self.cap[i][1].lower():
                self.elenco.setCurrentRow(i)
                self.testo.moveCursor(QTextCursor.Start)
                self.testo.find(q)
                return
        QMessageBox.information(self, "Cerca", f"«{self.e_cerca.text()}» non compare nella guida.")

    def salva_pdf(self):
        nome, _ = QFileDialog.getSaveFileName(self, "Salva la guida in PDF", f"Guida {self.g.nome_app}.pdf",
                                              "PDF (*.pdf)")
        if not nome:
            return
        doc = QTextDocument()
        doc.setHtml(guida.pagina(self.g))
        stampante = QPrinter(QPrinter.HighResolution)
        stampante.setOutputFormat(QPrinter.PdfFormat)
        stampante.setOutputFileName(nome)
        doc.print_(stampante)
        QMessageBox.information(self, "Guida", f"Guida salvata in:\n{nome}")
