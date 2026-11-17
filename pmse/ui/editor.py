"""Finestra "Aggiornamento Archivio": scorre, modifica, aggiunge ed elimina
le estrazioni una alla volta."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QIntValidator, QPainter, QPixmap
from PySide6.QtWidgets import (QDateEdit, QDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QToolButton, QVBoxLayout)

from ..core.db import Archivio
from ..core.modello import GIORNI, Estrazione, valida

GIALLO = "background:#fff59d;"
LATO_PULSANTE = 78          # pulsanti quadrati in alto
LATO_ICONA = 34


def icona_testo(simbolo: str, colore: str) -> QIcon:
    """Disegna un simbolo (carattere/emoji) come icona."""
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    f = QFont("Segoe UI Symbol", 40)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(colore))
    p.drawText(pm.rect(), Qt.AlignCenter, simbolo)
    p.end()
    return QIcon(pm)


def _pulsante_quadrato(testo: str, simbolo: str, colore: str) -> QToolButton:
    b = QToolButton()
    b.setText(testo)
    b.setIcon(icona_testo(simbolo, colore))
    b.setIconSize(QSize(LATO_ICONA, LATO_ICONA))
    b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
    b.setFixedSize(LATO_PULSANTE, LATO_PULSANTE)
    f = b.font()
    f.setBold(True)
    f.setPointSize(10)
    b.setFont(f)
    return b


class CasellaNumero(QLineEdit):
    """Casella grande per un numero da 1 a 90 (vuota = 0)."""

    def __init__(self, larghezza: int = 62):
        super().__init__()
        self.setValidator(QIntValidator(0, 90, self))
        self.setMaxLength(2)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(larghezza, 50)
        f = QFont("Segoe UI", 20)
        f.setBold(True)
        self.setFont(f)
        self.setStyleSheet("QLineEdit { background:white; border:1px solid #888; padding:0px; }")

    def value(self) -> int:
        t = self.text().strip()
        return int(t) if t.isdigit() else 0

    def setValue(self, n: int):
        self.setText(str(n) if n else "")


def _casella_numero(larghezza: int = 62) -> CasellaNumero:
    return CasellaNumero(larghezza)


def _etichetta(testo: str, punti: int = 13) -> QLabel:
    l = QLabel(testo)
    f = QFont("Segoe UI", punti)
    f.setBold(True)
    l.setFont(f)
    return l


class EditorEstrazione(QDialog):
    def __init__(self, archivio: Archivio, data_iniziale: date | None = None, nuova: bool = False, parent=None):
        super().__init__(parent)
        self.arch = archivio
        self.setWindowTitle("Aggiornamento Archivio")
        self.date = archivio.date_ordinate()
        self.indice = -1
        self.in_inserimento = False
        self.modificato = False
        self.corrente: Estrazione | None = None
        self._costruisci()
        if nuova or not self.date:
            self.nuova()
        else:
            d = data_iniziale if data_iniziale in self.date else self.date[-1]
            self.vai(self.date.index(d))

    # ------------------------------------------------------------------ layout
    def _costruisci(self):
        v = QVBoxLayout(self)
        v.setSpacing(14)
        barra = QHBoxLayout()
        self.b_primo = _pulsante_quadrato("Primo", "⏮", "#1565c0")
        self.b_prec = _pulsante_quadrato("Prec.", "◀", "#1565c0")
        self.b_succ = _pulsante_quadrato("Succ.", "▶", "#1565c0")
        self.b_ultimo = _pulsante_quadrato("Ultimo", "⏭", "#1565c0")
        self.b_agg = _pulsante_quadrato("Aggiungi", "✚", "#2e7d32")
        self.b_eli = _pulsante_quadrato("Elimina", "▬", "#c62828")
        for b in (self.b_primo, self.b_prec, self.b_succ, self.b_ultimo):
            barra.addWidget(b)
        barra.addStretch()
        barra.addWidget(self.b_agg)
        barra.addWidget(self.b_eli)
        v.addLayout(barra)
        self.b_primo.clicked.connect(lambda: self._sposta(0))
        self.b_ultimo.clicked.connect(lambda: self._sposta(len(self.date) - 1))
        self.b_prec.clicked.connect(lambda: self._sposta(self.indice - 1))
        self.b_succ.clicked.connect(lambda: self._sposta(self.indice + 1))
        self.b_agg.clicked.connect(self.nuova)
        self.b_eli.clicked.connect(self.elimina)

        # Posizione, concorso e data: caselle grandi, contenuto in grassetto
        testa = QGridLayout()
        testa.setHorizontalSpacing(10)
        testa.addWidget(_etichetta("Pos."), 0, 0, Qt.AlignCenter)
        testa.addWidget(_etichetta("Conc."), 0, 1, Qt.AlignCenter)
        testa.addWidget(_etichetta("Data"), 0, 2, Qt.AlignCenter)
        grande = QFont("Segoe UI", 18)
        grande.setBold(True)
        self.l_pos = QLabel()
        self.l_conc = QLabel()
        for l, larg in ((self.l_pos, 110), (self.l_conc, 90)):
            l.setFont(grande)
            l.setStyleSheet(GIALLO + "border:1px solid #888; padding:4px;")
            l.setAlignment(Qt.AlignCenter)
            l.setFixedSize(larg, 50)
        self.e_data = QDateEdit()
        self.e_data.setCalendarPopup(True)
        self.e_data.setDisplayFormat("dd/MM/yyyy")
        self.e_data.setFont(grande)
        self.e_data.setAlignment(Qt.AlignCenter)
        self.e_data.setFixedSize(210, 50)
        self.e_data.setStyleSheet("QDateEdit {" + GIALLO + "}")
        self.e_data.dateChanged.connect(self._data_cambiata)
        self.l_giorno = _etichetta("", 12)
        self.l_giorno.setAlignment(Qt.AlignCenter)
        testa.addWidget(self.l_pos, 1, 0)
        testa.addWidget(self.l_conc, 1, 1)
        testa.addWidget(self.e_data, 1, 2)
        testa.addWidget(self.l_giorno, 2, 2)
        testa.setColumnStretch(3, 1)
        v.addLayout(testa)

        v.addSpacing(26)   # combinazione vincente più in basso

        # Combinazione vincente: caselle e numeri più grandi, in grassetto
        v.addWidget(_etichetta("Combinazione Vincente", 14))
        h = QHBoxLayout()
        h.setSpacing(6)
        self.s_num = [_casella_numero() for _ in range(6)]
        for s in self.s_num:
            h.addWidget(s)
        self.s_jolly = _casella_numero()
        self.s_ss = _casella_numero()
        h.addSpacing(18)
        h.addWidget(_etichetta("Jolly", 14))
        h.addWidget(self.s_jolly)
        h.addSpacing(18)
        h.addWidget(_etichetta("SuperStar", 14))
        h.addWidget(self.s_ss)
        h.addStretch()
        v.addLayout(h)

        self.l_avvisi = QLabel()
        self.l_avvisi.setStyleSheet("color:#b71c1c;")
        self.l_avvisi.setWordWrap(True)
        v.addWidget(self.l_avvisi)
        v.addStretch()

        basso = QHBoxLayout()
        self.b_ok = QPushButton("✔ Ok (salva)")
        self.b_annulla = QPushButton("✖ Annulla")
        self.b_aiuto = QPushButton("? Aiuto")
        basso.addStretch()
        for b in (self.b_ok, self.b_annulla, self.b_aiuto):
            f = b.font()
            f.setBold(True)
            b.setFont(f)
            b.setMinimumHeight(34)
            basso.addWidget(b)
        v.addLayout(basso)
        self.b_ok.clicked.connect(self.salva)
        self.b_annulla.clicked.connect(self._annulla)
        self.b_aiuto.clicked.connect(self._aiuto)

    # ---------------------------------------------------------------- dati
    def _data_cambiata(self, qd: QDate):
        d = qd.toPython()
        self.l_giorno.setText(GIORNI[d.weekday()])

    def _sposta(self, i: int):
        if 0 <= i < len(self.date):
            self.vai(i)

    def vai(self, i: int):
        self.indice = i
        self.in_inserimento = False
        e = self.arch.per_data(self.date[i])
        self.corrente = e
        self.l_pos.setText(str(i + 1))
        self.l_conc.setText(str(e.concorso or ""))
        self.e_data.setDate(QDate(e.data.year, e.data.month, e.data.day))
        for s, n in zip(self.s_num, e.numeri):
            s.setValue(n)
        self.s_jolly.setValue(e.jolly or 0)
        self.s_ss.setValue(e.superstar or 0)
        self.l_avvisi.setText(f"Fonte: {e.fonte}" if e.fonte else "")
        self._aggiorna_pulsanti()

    def nuova(self):
        self.in_inserimento = True
        self.corrente = None
        ultima = self.arch.ultima()
        self.l_pos.setText(str(len(self.date) + 1))
        self.l_conc.setText("auto")
        oggi = date.today()
        self.e_data.setDate(QDate(oggi.year, oggi.month, oggi.day))
        for s in self.s_num + [self.s_jolly, self.s_ss]:
            s.setValue(0)
        self.l_avvisi.setText("Nuova estrazione: inserisci data, 6 numeri, Jolly e SuperStar, poi premi Ok."
                              + (f"  (Ultima in archivio: {ultima.data:%d/%m/%Y})" if ultima else ""))
        self.s_num[0].setFocus()
        self._aggiorna_pulsanti()

    def _aggiorna_pulsanti(self):
        nav = not self.in_inserimento and bool(self.date)
        self.b_primo.setEnabled(nav and self.indice > 0)
        self.b_prec.setEnabled(nav and self.indice > 0)
        self.b_succ.setEnabled(nav and self.indice < len(self.date) - 1)
        self.b_ultimo.setEnabled(nav and self.indice < len(self.date) - 1)
        self.b_eli.setEnabled(nav)

    def _leggi(self) -> Estrazione:
        e = Estrazione(
            data=self.e_data.date().toPython(),
            numeri=[s.value() for s in self.s_num],
            jolly=self.s_jolly.value() or None,
            superstar=self.s_ss.value() or None,
            fonte="manuale",
        )
        if self.corrente is not None:      # conserva eventuali dati non mostrati
            e.montepremi = self.corrente.montepremi
            e.quote = dict(self.corrente.quote)
        return e

    def salva(self):
        e = self._leggi()
        errori, avvisi = valida(e)
        if errori:
            QMessageBox.warning(self, "Dati non validi", "\n".join(errori))
            return
        if avvisi and QMessageBox.question(self, "Attenzione", "\n".join(avvisi) + "\n\nSalvo comunque?") \
                != QMessageBox.Yes:
            return
        originale = None if self.in_inserimento else self.date[self.indice]
        if self.in_inserimento and self.arch.per_data(e.data):
            QMessageBox.warning(self, "Duplicato", "Esiste già un'estrazione con questa data.")
            return
        try:
            self.arch.salva(e, data_originale=originale)
        except ValueError as ex:
            QMessageBox.warning(self, "Errore", str(ex))
            return
        self.modificato = True
        self.date = self.arch.date_ordinate()
        self.vai(self.date.index(e.data))
        self.l_avvisi.setText("✔ Salvato.")

    def elimina(self):
        if self.in_inserimento or not self.date:
            return
        d = self.date[self.indice]
        if QMessageBox.question(self, "Elimina", f"Eliminare definitivamente l'estrazione del {d:%d/%m/%Y}?") \
                != QMessageBox.Yes:
            return
        self.arch.elimina(d)
        self.modificato = True
        self.date = self.arch.date_ordinate()
        if self.date:
            self.vai(min(self.indice, len(self.date) - 1))
        else:
            self.nuova()

    def _annulla(self):
        if self.in_inserimento and self.date:
            self.vai(len(self.date) - 1)
        else:
            self.accept() if self.modificato else self.reject()

    def _aiuto(self):
        QMessageBox.information(self, "Aiuto", (
            "Usa i pulsanti in alto per scorrere l'archivio.\n"
            "Aggiungi: prepara una nuova estrazione vuota.\n"
            "Ok: salva l'estrazione mostrata (nuova o modificata).\n"
            "Elimina: cancella l'estrazione mostrata (con conferma).\n\n"
            "Il numero di concorso viene calcolato automaticamente come progressivo dell'anno."))
