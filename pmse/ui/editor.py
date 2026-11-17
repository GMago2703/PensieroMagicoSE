"""Finestra "Aggiornamento Archivio": scorre, modifica, aggiunge ed elimina
le estrazioni una alla volta (sul modello della foto 2)."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QDateEdit, QDialog, QDoubleSpinBox, QGridLayout, QGroupBox, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

from ..core.db import Archivio
from ..core.modello import CATEGORIE, GIORNI, Estrazione, valida

GIALLO = "background:#fff59d;"


def _num(v: str):
    v = v.strip().replace("€", "").replace(" ", "")
    if not v:
        return None
    v = v.replace(".", "").replace(",", ".")
    return float(v)


def _euro(v: float | None) -> str:
    if v is None:
        return ""
    s = f"{v:,.2f}"
    return "€ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


class EditorEstrazione(QDialog):
    def __init__(self, archivio: Archivio, data_iniziale: date | None = None, nuova: bool = False, parent=None):
        super().__init__(parent)
        self.arch = archivio
        self.setWindowTitle("Aggiornamento Archivio")
        self.setMinimumWidth(520)
        self.date = archivio.date_ordinate()
        self.indice = -1
        self.in_inserimento = False
        self.modificato = False
        self._costruisci()
        if nuova or not self.date:
            self.nuova()
        else:
            d = data_iniziale if data_iniziale in self.date else self.date[-1]
            self.vai(self.date.index(d))

    # ------------------------------------------------------------------ layout
    def _costruisci(self):
        v = QVBoxLayout(self)
        barra = QHBoxLayout()
        self.b_primo = QPushButton("⏮ Primo")
        self.b_prec = QPushButton("◀ Prec.")
        self.b_succ = QPushButton("Succ. ▶")
        self.b_ultimo = QPushButton("Ultimo ⏭")
        self.b_agg = QPushButton("➕ Aggiungi")
        self.b_eli = QPushButton("➖ Elimina")
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

        testa = QGridLayout()
        testa.addWidget(QLabel("<b>Pos.</b>"), 0, 0)
        testa.addWidget(QLabel("<b>Conc.</b>"), 0, 1)
        testa.addWidget(QLabel("<b>Data</b>"), 0, 2)
        testa.addWidget(QLabel("Montepremi"), 0, 3)
        self.l_pos = QLabel()
        self.l_conc = QLabel()
        for l in (self.l_pos, self.l_conc):
            l.setStyleSheet(GIALLO + "padding:3px; font-weight:bold;")
            l.setAlignment(Qt.AlignCenter)
        self.e_data = QDateEdit()
        self.e_data.setCalendarPopup(True)
        self.e_data.setDisplayFormat("dd/MM/yyyy")
        self.e_data.setStyleSheet(GIALLO)
        self.e_data.dateChanged.connect(self._data_cambiata)
        self.l_giorno = QLabel()
        self.e_monte = QLineEdit()
        self.e_monte.setStyleSheet(GIALLO + "font-weight:bold;")
        testa.addWidget(self.l_pos, 1, 0)
        testa.addWidget(self.l_conc, 1, 1)
        testa.addWidget(self.e_data, 1, 2)
        testa.addWidget(self.e_monte, 1, 3)
        testa.addWidget(self.l_giorno, 2, 2)
        v.addLayout(testa)

        box = QGroupBox("Combinazione Vincente")
        h = QHBoxLayout(box)
        self.s_num = []
        for _ in range(6):
            s = QSpinBox()
            s.setRange(0, 90)
            s.setSpecialValueText(" ")
            s.setButtonSymbols(QSpinBox.NoButtons)
            s.setAlignment(Qt.AlignCenter)
            s.setFixedWidth(42)
            self.s_num.append(s)
            h.addWidget(s)
        self.s_jolly = QSpinBox()
        self.s_ss = QSpinBox()
        for s in (self.s_jolly, self.s_ss):
            s.setRange(0, 90)
            s.setSpecialValueText(" ")
            s.setButtonSymbols(QSpinBox.NoButtons)
            s.setAlignment(Qt.AlignCenter)
            s.setFixedWidth(42)
        h.addSpacing(12)
        h.addWidget(QLabel("Jolly"))
        h.addWidget(self.s_jolly)
        h.addSpacing(12)
        h.addWidget(QLabel("SuperStar"))
        h.addWidget(self.s_ss)
        v.addWidget(box)

        self.t_quote = QTableWidget(len(CATEGORIE), 3)
        self.t_quote.setHorizontalHeaderLabels(["Categoria", "Vincitori", "Quota"])
        self.t_quote.verticalHeader().setVisible(False)
        self.t_quote.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for i, cat in enumerate(CATEGORIE):
            it = QTableWidgetItem(cat)
            it.setFlags(Qt.ItemIsEnabled)
            self.t_quote.setItem(i, 0, it)
        self.t_quote.setStyleSheet("QTableWidget { background:#fff9c4; }")
        v.addWidget(self.t_quote)

        self.l_avvisi = QLabel()
        self.l_avvisi.setStyleSheet("color:#b71c1c;")
        self.l_avvisi.setWordWrap(True)
        v.addWidget(self.l_avvisi)

        basso = QHBoxLayout()
        self.b_ok = QPushButton("✔ Ok (salva)")
        self.b_annulla = QPushButton("✖ Annulla")
        self.b_aiuto = QPushButton("? Aiuto")
        basso.addStretch()
        basso.addWidget(self.b_ok)
        basso.addWidget(self.b_annulla)
        basso.addWidget(self.b_aiuto)
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
        self.l_pos.setText(str(i + 1))
        self.l_conc.setText(str(e.concorso or ""))
        self.e_data.setDate(QDate(e.data.year, e.data.month, e.data.day))
        self.e_monte.setText(_euro(e.montepremi))
        for s, n in zip(self.s_num, e.numeri):
            s.setValue(n)
        self.s_jolly.setValue(e.jolly or 0)
        self.s_ss.setValue(e.superstar or 0)
        for r, cat in enumerate(CATEGORIE):
            vinc, quota = e.quote.get(cat, (None, None))
            self.t_quote.setItem(r, 1, QTableWidgetItem("" if vinc is None else f"{vinc:,}".replace(",", ".")))
            self.t_quote.setItem(r, 2, QTableWidgetItem(_euro(quota)))
        self.l_avvisi.setText(f"Fonte: {e.fonte}" if e.fonte else "")
        self._aggiorna_pulsanti()

    def nuova(self):
        self.in_inserimento = True
        ultima = self.arch.ultima()
        self.l_pos.setText(str(len(self.date) + 1))
        self.l_conc.setText("auto")
        oggi = date.today()
        self.e_data.setDate(QDate(oggi.year, oggi.month, oggi.day))
        self.e_monte.clear()
        for s in self.s_num + [self.s_jolly, self.s_ss]:
            s.setValue(0)
        for r in range(len(CATEGORIE)):
            self.t_quote.setItem(r, 1, QTableWidgetItem(""))
            self.t_quote.setItem(r, 2, QTableWidgetItem(""))
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
        quote = {}
        for r, cat in enumerate(CATEGORIE):
            tv = (self.t_quote.item(r, 1).text() if self.t_quote.item(r, 1) else "").replace(".", "").strip()
            tq = self.t_quote.item(r, 2).text() if self.t_quote.item(r, 2) else ""
            vinc = int(tv) if tv.isdigit() else None
            quota = _num(tq)
            if vinc is not None or quota is not None:
                quote[cat] = (vinc, quota)
        return Estrazione(
            data=self.e_data.date().toPython(),
            numeri=[s.value() for s in self.s_num],
            jolly=self.s_jolly.value() or None,
            superstar=self.s_ss.value() or None,
            montepremi=_num(self.e_monte.text()),
            fonte="manuale",
            quote=quote,
        )

    def salva(self):
        try:
            e = self._leggi()
        except ValueError:
            QMessageBox.warning(self, "Dati non validi", "Controlla montepremi e quote: devono essere numeri.")
            return
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

    def closeEvent(self, ev):
        if self.modificato:
            self.setResult(QDialog.Accepted)
        super().closeEvent(ev)

    def _aiuto(self):
        QMessageBox.information(self, "Aiuto", (
            "Usa le frecce per scorrere l'archivio.\n"
            "Aggiungi: prepara una nuova estrazione vuota.\n"
            "Ok: salva l'estrazione mostrata (nuova o modificata).\n"
            "Elimina: cancella l'estrazione mostrata (con conferma).\n\n"
            "Il numero di concorso viene calcolato automaticamente come progressivo dell'anno.\n"
            "Montepremi e quote sono facoltativi."))
