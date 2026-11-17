"""Menu Internet: scaricamento completo e aggiornamento automatico."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
                               QProgressBar, QPushButton, QVBoxLayout)

from ..core import internet
from ..core.db import Archivio


class Scaricatore(QThread):
    avanzamento = Signal(str, int, int)
    finito = Signal(list)
    errore = Signal(str)

    def __init__(self, anni: list[int], gioco=None):
        super().__init__()
        from ..core.gioco import SE
        self.anni = anni
        self.gioco = gioco or SE
        self._stop = False

    def ferma(self):
        self._stop = True

    def run(self):
        try:
            estr = internet.scarica_anni(self.anni, lambda m, i, n: self.avanzamento.emit(m, i, n),
                                         lambda: self._stop, self.gioco)
            self.finito.emit(estr)
        except Exception as ex:  # errore di rete o di formato
            self.errore.emit(str(ex))


class FinestraInternet(QDialog):
    def __init__(self, archivio: Archivio, completo: bool = False, automatico: bool = False, parent=None):
        super().__init__(parent)
        self.arch = archivio
        self.modificato = False
        self.thread: Scaricatore | None = None
        self.automatico = automatico
        self.setWindowTitle("Aggiornamento da Internet")
        self.resize(560, 380)
        v = QVBoxLayout(self)
        v.addWidget(QLabel(f"{archivio.gioco.nome} – fonte: archivio pubblico annuale di "
                           f"{internet.FONTE[archivio.gioco.codice]}\nEstrazioni in archivio: {archivio.conta()}"))
        self.barra = QProgressBar()
        v.addWidget(self.barra)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        v.addWidget(self.log)
        self.c_avvio = QCheckBox("Aggiorna automaticamente all'avvio del programma")
        self.c_avvio.setChecked(archivio.leggi_impostazione("aggiorna_avvio", "1") == "1")
        self.c_avvio.toggled.connect(lambda s: archivio.scrivi_impostazione("aggiorna_avvio", "1" if s else "0"))
        v.addWidget(self.c_avvio)
        h = QHBoxLayout()
        self.b_agg = QPushButton("🔄 Aggiorna (solo estrazioni mancanti)")
        self.b_tutto = QPushButton(f"⬇ Scarica archivio completo (dal {archivio.gioco.prima_estrazione.year})")
        self.b_stop = QPushButton("Interrompi")
        self.b_chiudi = QPushButton("Chiudi")
        self.b_agg.clicked.connect(lambda: self.avvia(completo=False))
        self.b_tutto.clicked.connect(lambda: self.avvia(completo=True))
        self.b_stop.clicked.connect(self._ferma)
        self.b_chiudi.clicked.connect(self.accept)
        self.b_stop.setEnabled(False)
        for b in (self.b_agg, self.b_tutto, self.b_stop, self.b_chiudi):
            h.addWidget(b)
        v.addLayout(h)
        if completo or automatico:
            self.avvia(completo=completo)

    def _scrivi(self, testo: str):
        self.log.appendPlainText(testo)

    def avvia(self, completo: bool):
        if self.thread and self.thread.isRunning():
            return
        ultima = None if completo else self.arch.ultima()
        anni = internet.anni_da_aggiornare(ultima.data if ultima else None, self.arch.gioco)
        self._scrivi(f"Anni da controllare: {anni[0]}–{anni[-1]}" if len(anni) > 1 else f"Anno: {anni[0]}")
        self.barra.setRange(0, len(anni))
        self.barra.setValue(0)
        self.thread = Scaricatore(anni, self.arch.gioco)
        self.thread.avanzamento.connect(self._avanza)
        self.thread.finito.connect(self._finito)
        self.thread.errore.connect(self._errore)
        for b in (self.b_agg, self.b_tutto, self.b_chiudi):
            b.setEnabled(False)
        self.b_stop.setEnabled(True)
        self.thread.start()

    def _avanza(self, msg, i, n):
        self.barra.setValue(i)
        self._scrivi(msg)

    def _fine_lavoro(self):
        for b in (self.b_agg, self.b_tutto, self.b_chiudi):
            b.setEnabled(True)
        self.b_stop.setEnabled(False)

    def _finito(self, estrazioni):
        self._fine_lavoro()
        esito = self.arch.unisci(estrazioni)
        if esito.nuove or esito.completate:
            self.modificato = True
        self.arch.scrivi_impostazione("ultimo_aggiornamento", date.today().isoformat())
        self._scrivi("")
        self._scrivi(esito.riepilogo())
        for vecchia, nuova in esito.conflitti[:20]:
            self._scrivi(f"  conflitto {vecchia.data:%d/%m/%Y}: archivio {vecchia.sestina} / web {nuova.sestina}")
        self.barra.setValue(self.barra.maximum())
        if self.automatico and not esito.conflitti:
            self.accept()

    def _errore(self, msg):
        self._fine_lavoro()
        self._scrivi("ERRORE: " + msg)
        if not self.automatico:
            QMessageBox.warning(self, "Errore di collegamento",
                                msg + "\n\nPuoi riprovare più tardi oppure importare un file (Archivio → Importa).")

    def _ferma(self):
        if self.thread:
            self.thread.ferma()
            self._scrivi("Interruzione richiesta...")

    def closeEvent(self, ev):
        if self.thread and self.thread.isRunning():
            self.thread.ferma()
            self.thread.wait(5000)
        super().closeEvent(ev)
