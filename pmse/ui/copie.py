"""Menu Impostazioni: copia dei dati (backup), ripristino e copie automatiche."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QSpinBox, QVBoxLayout)

from ..core import backup
from .schermo import adatta_schermo

IMPOSTAZIONI = ("PensieroMagico", "Copie")
NOMI = {"SE": "Pensiero Magico SE (SuperEnalotto)", "EJ": "Pensiero Magico EJ (Eurojackpot)"}


def preferenze() -> tuple[bool, int, int]:
    s = QSettings(*IMPOSTAZIONI)
    return (str(s.value("attive", "1")) == "1", int(s.value("ogni_giorni", 7)), int(s.value("quante", 10)))


def copia_automatica() -> Path | None:
    """All'avvio: fa la copia automatica se è il momento (mai più di una per sessione)."""
    attive, ogni, quante = preferenze()
    if not attive:
        return None
    try:
        return backup.automatica_se_serve(ogni, quante)
    except Exception:
        return None


def _descrivi(c: backup.Contenuto) -> str:
    righe = []
    try:
        quando = datetime.fromisoformat(c.creato).strftime("%d/%m/%Y alle %H:%M")
    except ValueError:
        quando = c.creato
    righe.append(f"Copia del {quando}" + (f" ({c.nota})" if c.nota else ""))
    for k, v in c.programmi.items():
        ultima = v.get("ultima", "")
        try:
            ultima = date.fromisoformat(ultima).strftime("%d/%m/%Y")
        except ValueError:
            pass
        righe.append(f"• {NOMI.get(k, k)}: {v.get('estrazioni', 0)} estrazioni (ultima {ultima}), "
                     f"{v.get('sistemi', 0)} sistemi memorizzati, {v.get('giocate', 0)} giocate registrate")
    righe.append("Chiavi dell'intelligenza artificiale: " + ("incluse" if c.chiavi else "non incluse"))
    return "\n".join(righe)


def salva_copia(parent) -> None:
    nome, _ = QFileDialog.getSaveFileName(parent, "Salva una copia dei dati",
                                          str(Path.home() / f"PensieroMagico_copia_{date.today():%Y-%m-%d}.zip"),
                                          "Copia di Pensiero Magico (*.zip)")
    if not nome:
        return
    r = QMessageBox.question(parent, "Chiavi dell'intelligenza artificiale",
                             "Vuoi includere nella copia anche le chiavi dell'intelligenza artificiale (Gemini, "
                             "Claude)?\n\nSì: ripristinando la copia su un altro computer funzionano subito, ma il "
                             "file va custodito con cura.\nNo: la copia non contiene segreti; le chiavi andranno "
                             "reinserite.", QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
    if r == QMessageBox.Cancel:
        return
    try:
        c = backup.crea(nome, chiavi=r == QMessageBox.Yes)
    except Exception as ex:
        QMessageBox.warning(parent, "Copia dei dati", f"Non riesco a creare la copia:\n{ex}")
        return
    QMessageBox.information(parent, "Copia dei dati", f"Copia salvata in:\n{nome}\n\n{_descrivi(c)}\n\n"
                                                      "Conservala anche fuori dal computer (chiavetta, cloud).")


class FinestraRipristino(QDialog):
    """Mostra cosa contiene una copia e quali programmi ripristinare."""

    def __init__(self, file: str, parent=None):
        super().__init__(parent)
        self.file = file
        self.cont = backup.leggi(file)
        self.setWindowTitle("Ripristina i dati da una copia")
        adatta_schermo(self, 640, 360)
        v = QVBoxLayout(self)
        t = QLabel(_descrivi(self.cont))
        t.setWordWrap(True)
        v.addWidget(t)
        v.addWidget(QLabel("<b>Cosa vuoi ripristinare?</b> I dati attuali dei programmi scelti verranno "
                           "sostituiti (prima ne faccio comunque una copia di sicurezza)."))
        self.scelte = {}
        for k in ("SE", "EJ"):
            cb = QCheckBox(NOMI[k])
            cb.setEnabled(k in self.cont.programmi)
            cb.setChecked(k in self.cont.programmi)
            v.addWidget(cb)
            self.scelte[k] = cb
        v.addStretch()
        h = QHBoxLayout()
        h.addStretch()
        b = QPushButton("♻ Ripristina")
        b.clicked.connect(self.accept)
        h.addWidget(b)
        b = QPushButton("Annulla")
        b.clicked.connect(self.reject)
        h.addWidget(b)
        v.addLayout(h)

    def programmi(self) -> list[str]:
        return [k for k, cb in self.scelte.items() if cb.isChecked() and cb.isEnabled()]


def scegli_e_ripristina(finestra, file: str | None = None) -> bool:
    """Ripristino guidato. 'finestra' è la finestra principale: il suo archivio viene chiuso e il
    programma riaperto con i dati ripristinati."""
    if file is None:
        file, _ = QFileDialog.getOpenFileName(finestra, "Scegli la copia da ripristinare",
                                              str(Path.home()), "Copia di Pensiero Magico (*.zip)")
        if not file:
            return False
    try:
        d = FinestraRipristino(file, finestra)
    except ValueError as ex:
        QMessageBox.warning(finestra, "Ripristino", str(ex))
        return False
    if not d.exec() or not d.programmi():
        return False
    scelti = d.programmi()
    if QMessageBox.question(finestra, "Ripristino", "Confermi? I dati attuali di " +
                            " e ".join(NOMI[k] for k in scelti) + " verranno sostituiti con quelli della copia "
                            "(una copia di sicurezza dei dati attuali viene salvata prima).") != QMessageBox.Yes:
        return False
    finestra.arch.chiudi()
    try:
        backup.ripristina(file, scelti)
    except Exception as ex:
        QMessageBox.warning(finestra, "Ripristino", f"Ripristino non riuscito: {ex}\n\nI dati non sono stati "
                                                    "cambiati o sono nella copia di sicurezza.")
    from .finestra import apri_programma
    QMessageBox.information(finestra, "Ripristino", "Dati ripristinati. Il programma si riapre con i dati della "
                                                    "copia.")
    finestra._riapri = True
    apri_programma(finestra.g.codice, avvio_automatico=False)
    finestra.close()
    return True


class FinestraCopieAutomatiche(QDialog):
    def __init__(self, finestra):
        super().__init__(finestra)
        self.finestra = finestra
        self.setWindowTitle("Copie automatiche dei dati")
        adatta_schermo(self, 680, 520)
        attive, ogni, quante = preferenze()
        v = QVBoxLayout(self)
        spieg = QLabel("Ogni tanto, all'avvio, il programma salva da solo una copia di tutti i dati (archivi, "
                       "sistemi, giocate, impostazioni) nella cartella delle copie. Le più vecchie vengono "
                       "cancellate.")
        spieg.setWordWrap(True)
        v.addWidget(spieg)
        self.cb = QCheckBox("Copie automatiche attive")
        self.cb.setChecked(attive)
        v.addWidget(self.cb)
        h = QHBoxLayout()
        h.addWidget(QLabel("Una copia ogni"))
        self.sp_ogni = QSpinBox()
        self.sp_ogni.setRange(1, 90)
        self.sp_ogni.setValue(ogni)
        h.addWidget(self.sp_ogni)
        h.addWidget(QLabel("giorni; tieni le ultime"))
        self.sp_quante = QSpinBox()
        self.sp_quante.setRange(1, 100)
        self.sp_quante.setValue(quante)
        h.addWidget(self.sp_quante)
        h.addWidget(QLabel("copie"))
        h.addStretch()
        v.addLayout(h)
        v.addWidget(QLabel("Copie presenti:"))
        self.lista = QListWidget()
        v.addWidget(self.lista, 1)
        h = QHBoxLayout()
        for testo, fun in (("Fai una copia adesso", self.adesso), ("♻ Ripristina la copia scelta", self.ripristina),
                           ("📂 Apri la cartella", self.cartella)):
            b = QPushButton(testo)
            b.clicked.connect(fun)
            h.addWidget(b)
        h.addStretch()
        b = QPushButton("Chiudi")
        b.clicked.connect(self.accept)
        h.addWidget(b)
        v.addLayout(h)
        self._elenco()

    def _elenco(self):
        self.lista.clear()
        for p in sorted(backup.cartella_copie().glob("*.zip"), key=lambda x: x.stat().st_mtime, reverse=True):
            q = datetime.fromtimestamp(p.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
            it = QListWidgetItem(f"{q}  –  {p.name}  ({p.stat().st_size / 1024:.0f} KB)")
            it.setData(Qt.UserRole, str(p))
            self.lista.addItem(it)

    def accept(self):
        s = QSettings(*IMPOSTAZIONI)
        s.setValue("attive", "1" if self.cb.isChecked() else "0")
        s.setValue("ogni_giorni", self.sp_ogni.value())
        s.setValue("quante", self.sp_quante.value())
        super().accept()

    def adesso(self):
        try:
            backup.crea(backup.cartella_copie() / f"{backup.PREFISSO_AUTO}{datetime.now():%Y-%m-%d_%H%M%S}.zip",
                        nota="copia manuale")
        except Exception as ex:
            QMessageBox.warning(self, "Copia", str(ex))
        self._elenco()

    def ripristina(self):
        it = self.lista.currentItem()
        if it is None:
            QMessageBox.information(self, "Ripristino", "Scegli prima una copia dall'elenco.")
            return
        self.accept()
        scegli_e_ripristina(self.finestra, it.data(Qt.UserRole))

    def cartella(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(backup.cartella_copie())))
