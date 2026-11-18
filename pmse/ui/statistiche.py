"""Finestre delle Statistiche, della Verifica di colonne sull'archivio e del Tabulato dei sistemi (stampa)."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QFileDialog,
                               QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

from ..core import sistemi as sis
from ..core import statistiche as st
from ..core.db import Archivio
from .schermo import adatta_schermo
from .stampa import pulsanti_stampa, stampa


class _Cella(QTableWidgetItem):
    """Cella che si ordina per valore (numeri come numeri, date come date)."""

    def __init__(self, valore):
        super().__init__(st._fmt(valore))
        self.chiave = valore
        if isinstance(valore, (int, float)):
            self.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def __lt__(self, altra):
        a, b = self.chiave, getattr(altra, "chiave", None)
        try:
            if a is None:
                return True
            if b is None:
                return False
            return a < b
        except TypeError:
            return str(a) < str(b)


def riempi(tw: QTableWidget, t: st.Tabella) -> None:
    tw.setSortingEnabled(False)
    tw.clear()
    tw.setColumnCount(len(t.colonne))
    tw.setRowCount(len(t.righe))
    tw.setHorizontalHeaderLabels(t.colonne)
    for i, r in enumerate(t.righe):
        for j, v in enumerate(r):
            it = _Cella(v)
            if t.griglia:
                it.setTextAlignment(Qt.AlignCenter)
            colore = t.colori.get((i, j))
            if colore:
                it.setBackground(QColor(colore))
                it.setForeground(QColor("#1b1b1b"))
            tw.setItem(i, j, it)
    if t.griglia:
        tw.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tw.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tw.verticalHeader().setVisible(False)
        tw.horizontalHeader().setVisible(False)
        f = QFont(tw.font())
        f.setPointSizeF(f.pointSizeF() + 1)
        f.setBold(True)
        tw.setFont(f)
    else:
        tw.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)
        tw.verticalHeader().setVisible(False)
        tw.horizontalHeader().setVisible(True)
        tw.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        tw.resizeColumnsToContents()
        tw.horizontalHeader().setStretchLastSection(True)
        tw.setSortingEnabled(True)
        if t.ordina >= 0:
            tw.sortItems(t.ordina, Qt.DescendingOrder if t.decrescente else Qt.AscendingOrder)


def _attesa(fun):
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        return fun()
    finally:
        QApplication.restoreOverrideCursor()


# ------------------------------------------------------------------ una statistica
class FinestraStatistica(QDialog):
    def __init__(self, arch: Archivio, codice: str, parent=None):
        super().__init__(parent)
        self.arch = arch
        self.g = arch.gioco
        self.stat = st.per_codice(self.g, codice)
        self.dati = st.Dati.da_archivio(arch)
        self.tabella: st.Tabella | None = None
        self.setWindowTitle(f"Statistiche – {self.stat.nome} – {self.g.nome}")
        griglia = codice == "tabellone"
        adatta_schermo(self, 900 if griglia else 1050, 720)
        v = QVBoxLayout(self)
        d = QLabel(f"<b>{self.stat.nome}</b> – {self.stat.descrizione}")
        d.setWordWrap(True)
        v.addWidget(d)
        h = QHBoxLayout()
        self.controlli = {}
        for p in self.stat.parametri:
            h.addWidget(QLabel(p.etichetta))
            if p.scelte:
                w = QComboBox()
                w.addItems(p.scelte)
                w.setCurrentIndex(p.predefinito)
                w.currentIndexChanged.connect(self.calcola)
            else:
                w = QSpinBox()
                w.setRange(p.minimo, p.massimo)
                w.setValue(p.predefinito)
            self.controlli[p.nome] = w
            h.addWidget(w)
        if self.stat.parametri:
            b = QPushButton("Calcola")
            b.clicked.connect(self.calcola)
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.t = QTableWidget()
        self.t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.t.setAlternatingRowColors(not griglia)
        v.addWidget(self.t, 1)
        self.l_nota = QLabel()
        self.l_nota.setWordWrap(True)
        self.l_nota.setStyleSheet("color:#444")
        v.addWidget(self.l_nota)
        h = QHBoxLayout()
        h.addWidget(pulsanti_stampa(self, self._da_stampare))
        b = QPushButton("Esporta CSV...")
        b.clicked.connect(self.esporta)
        h.addWidget(b)
        h.addStretch()
        b = QPushButton("Chiudi")
        b.clicked.connect(self.accept)
        h.addWidget(b)
        v.addLayout(h)
        self.calcola()

    def parametri(self) -> dict:
        return {k: (w.currentIndex() if isinstance(w, QComboBox) else w.value()) for k, w in self.controlli.items()}

    def calcola(self, *_):
        if not self.dati.righe:
            self.l_nota.setText("Archivio vuoto: aggiornalo da Internet.")
            return
        try:
            self.tabella = _attesa(lambda: self.stat.funzione(self.dati, **self.parametri()))
        except Exception as ex:
            QMessageBox.warning(self, "Statistiche", f"Errore nel calcolo: {ex}")
            return
        riempi(self.t, self.tabella)
        self.l_nota.setText(self.tabella.nota)

    def _da_stampare(self):
        t = self.tabella
        return (t.titolo if t else self.stat.nome), (t.testo() if t else ""), self.stat.nome

    def esporta(self):
        if not self.tabella:
            return
        nome, _ = QFileDialog.getSaveFileName(self, "Esporta CSV", f"{self.stat.nome}.csv", "CSV (*.csv)")
        if nome:
            with open(nome, "w", encoding="utf-8-sig") as f:
                f.write(self.tabella.csv())


# ------------------------------------------------------------------ verifica di colonne
def _numeri(t: str) -> list[int]:
    out = []
    for p in t.replace(",", " ").replace(";", " ").replace("-", " ").replace("+", " ").split():
        if p.isdigit():
            out.append(int(p))
    return out


class FinestraVerificaColonne(QDialog):
    """Sviluppo → Verifica colonne casuali: da 1 a 10 colonne (casuali o scritte) confrontate con tutte le
    estrazioni dell'archivio: quanti 2, 3, 4, 5, 6 avrebbero fatto."""

    def __init__(self, arch: Archivio, parent=None, colonne: list[list[int]] | None = None):
        super().__init__(parent)
        self.arch = arch
        self.g = arch.gioco
        self.esito: st.EsitoVerifica | None = None
        self.colonne: list[list[int]] = []
        self.setWindowTitle(f"Verifica colonne sull'archivio – {self.g.nome}")
        adatta_schermo(self, 1050, 740)
        v = QVBoxLayout(self)
        quale = "6 numeri" if not self.g.is_ej else "5 numeri + 2 Euronumeri (facoltativi)"
        info = QLabel(f"Scegli da 1 a 10 colonne ({quale}): falle generare a caso o scrivile tu, una per riga. Ogni "
                      "colonna viene confrontata con tutte le estrazioni dell'archivio (o con le ultime N).")
        info.setWordWrap(True)
        v.addWidget(info)
        h = QHBoxLayout()
        h.addWidget(QLabel("Colonne"))
        self.sp_n = QSpinBox()
        self.sp_n.setRange(1, 10)
        self.sp_n.setValue(5)
        h.addWidget(self.sp_n)
        self.cb_euro = QCheckBox("con gli Euronumeri")
        self.cb_euro.setChecked(True)
        if self.g.is_ej:
            h.addWidget(self.cb_euro)
        b = QPushButton("🎲 Genera casuali")
        b.clicked.connect(self.genera)
        h.addWidget(b)
        h.addSpacing(20)
        h.addWidget(QLabel("Estrazioni: ultime"))
        self.sp_ult = QSpinBox()
        self.sp_ult.setRange(0, 100000)
        self.sp_ult.setSpecialValueText("tutto l'archivio")
        h.addWidget(self.sp_ult)
        b = QPushButton("▶ Verifica")
        b.setDefault(True)
        b.clicked.connect(self.verifica)
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.ed = QPlainTextEdit()
        self.ed.setPlaceholderText("una colonna per riga, es. 3 15 27 44 61 88" +
                                   ("  oppure  3 15 27 44 49 + 2 11" if self.g.is_ej else ""))
        self.ed.setMaximumHeight(170)
        f = QFont("Consolas")
        f.setStyleHint(QFont.Monospace)
        self.ed.setFont(f)
        v.addWidget(self.ed)
        self.t = QTableWidget()
        self.t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.t.verticalHeader().setVisible(False)
        v.addWidget(self.t, 1)
        self.dettagli = QPlainTextEdit()
        self.dettagli.setReadOnly(True)
        self.dettagli.setMaximumHeight(170)
        v.addWidget(self.dettagli)
        h = QHBoxLayout()
        h.addWidget(pulsanti_stampa(self, self._da_stampare))
        h.addStretch()
        b = QPushButton("Chiudi")
        b.clicked.connect(self.accept)
        h.addWidget(b)
        v.addLayout(h)
        if colonne:
            self.ed.setPlainText("\n".join(st._colonna_txt(c, self.g) for c in colonne))
        else:
            self.genera()

    def genera(self):
        cols = st.colonne_casuali(self.g, self.sp_n.value(), con_euro=self.cb_euro.isChecked())
        self.ed.setPlainText("\n".join(st._colonna_txt(c, self.g) for c in cols))

    def _leggi(self) -> list[list[int]]:
        g = self.g
        out = []
        for i, riga in enumerate(self.ed.toPlainText().splitlines(), 1):
            if not riga.strip():
                continue
            nums = _numeri(riga)
            princ, euro = nums[:g.k], nums[g.k:]
            if len(princ) != g.k or len(set(princ)) != g.k or not all(1 <= x <= g.n for x in princ):
                raise ValueError(f"Riga {i}: servono {g.k} numeri diversi da 1 a {g.n}.")
            if g.is_ej and euro:
                if len(euro) != 2 or euro[0] == euro[1] or not all(1 <= x <= 12 for x in euro):
                    raise ValueError(f"Riga {i}: gli Euronumeri devono essere 2, diversi, da 1 a 12.")
            elif euro:
                raise ValueError(f"Riga {i}: troppi numeri (ne servono {g.k}).")
            out.append(sorted(princ) + sorted(euro))
        if not out:
            raise ValueError("Scrivi o genera almeno una colonna.")
        if len(out) > 10:
            raise ValueError("Al massimo 10 colonne.")
        if g.is_ej and len({len(c) for c in out}) > 1:
            raise ValueError("Metti gli Euronumeri in tutte le colonne o in nessuna.")
        return out

    def verifica(self):
        try:
            self.colonne = self._leggi()
        except ValueError as ex:
            QMessageBox.warning(self, "Verifica colonne", str(ex))
            return
        righe = list(self.arch.sestine())
        if not righe:
            QMessageBox.information(self, "Verifica colonne", "Archivio vuoto: aggiornalo da Internet.")
            return
        e = _attesa(lambda: st.verifica_colonne(self.colonne, righe, self.g, self.sp_ult.value()))
        self.esito = e
        cats = e.categorie
        self.t.clear()
        self.t.setColumnCount(len(cats) + 2)
        self.t.setHorizontalHeaderLabels(["Colonna"] + [f"{c} punti" if "+" not in c else c for c in cats]
                                         + ["Totale"])
        self.t.setRowCount(len(self.colonne) + 2)
        tot = e.totale()
        for i, c in enumerate(self.colonne):
            self.t.setItem(i, 0, QTableWidgetItem(st._colonna_txt(c, self.g)))
            for j, x in enumerate(cats):
                it = _Cella(e.per_colonna[i][x])
                if e.per_colonna[i][x] and j < len(cats) - 2:
                    it.setBackground(QColor(st.VERDE))
                self.t.setItem(i, j + 1, it)
            self.t.setItem(i, len(cats) + 1, _Cella(sum(e.per_colonna[i].values())))
        r = len(self.colonne)
        grassetto = QFont(self.t.font())
        grassetto.setBold(True)
        self.t.setItem(r, 0, QTableWidgetItem("Totale"))
        self.t.setItem(r + 1, 0, QTableWidgetItem("Atteso dal caso (stesse colonne)"))
        for j, x in enumerate(cats):
            self.t.setItem(r, j + 1, _Cella(tot[x]))
            self.t.setItem(r + 1, j + 1, _Cella(round(e.attesi[x] * len(self.colonne), 2)))
        self.t.setItem(r, len(cats) + 1, _Cella(sum(tot.values())))
        self.t.setItem(r + 1, len(cats) + 1, _Cella(round(sum(e.attesi.values()) * len(self.colonne), 2)))
        for c in range(self.t.columnCount()):
            for rr in (r, r + 1):
                it = self.t.item(rr, c)
                if it:
                    it.setFont(grassetto)
                    it.setBackground(QColor("#eeeeee"))
        self.t.resizeColumnsToContents()
        self.t.horizontalHeader().setStretchLastSection(True)
        self.dettagli.setPlainText(self._commento())

    def _commento(self) -> str:
        e = self.esito
        g = self.g
        r = [f"Estrazioni esaminate: {e.estrazioni}."]
        tot = sum(e.totale().values())
        att = sum(e.attesi.values()) * len(self.colonne)
        r.append(f"Vincite totali delle {len(self.colonne)} colonne: {tot}; il caso ne prevede in media {att:.1f}.")
        for i, c in enumerate(self.colonne):
            p = e.punti[i]
            punti = ", ".join(f"{k} punti: {p[k]}" for k in sorted(p, reverse=True) if k >= 1 and p[k])
            migl = ", ".join(f"{cat} il {d:%d/%m/%Y}" for d, cat in e.migliori[i][:3])
            r.append(f"{i + 1}) {st._colonna_txt(c, g)} → {punti}" + (f". Migliori: {migl}" if migl else ""))
        if g.is_ej and self.colonne and len(self.colonne[0]) > g.k:
            r.append("Atteso calcolato con 12 Euronumeri (prima del 2022 erano 8 e poi 10).")
        r.append("Una colonna scelta a caso e una scelta con qualsiasi metodo hanno sull'archivio risultati dello "
                 "stesso ordine: è il modo più semplice per vederlo con i propri occhi.")
        return "\n".join(r)

    def _da_stampare(self):
        if not self.esito:
            return "Verifica colonne", "Nessuna verifica eseguita.", "verifica colonne"
        return ("Verifica colonne sull'archivio – " + self.g.nome,
                self.esito.testo(self.colonne, self.g) + "\n\n" + self._commento(), "verifica colonne")


# ------------------------------------------------------------------ tabulato dei sistemi
class FinestraTabulato(QDialog):
    """Stampe → Tabulato di un sistema: dati, condizioni, riduzione, garanzie, costo e tutte le colonne,
    su stampante, PDF o TXT."""

    def __init__(self, arch: Archivio, parent=None, sistema: sis.Sistema | None = None, possibili=None,
                 ultimo=None):
        super().__init__(parent)
        self.arch = arch
        self.g = arch.gioco
        self.possibili_cache = {}
        self.setWindowTitle(f"Tabulato del sistema – {self.g.nome}")
        adatta_schermo(self, 980, 740)
        v = QVBoxLayout(self)
        h = QHBoxLayout()
        h.addWidget(QLabel("Sistema"))
        self.c_sis = QComboBox()
        self.sistemi: list[tuple[sis.Sistema, object]] = []
        if sistema is not None:
            self.sistemi.append((sistema, possibili))
            self.c_sis.addItem(f"{sistema.nome or 'sistema appena sviluppato'} ({len(sistema.colonne)} colonne)")
        elif ultimo is not None:
            self.sistemi.append(ultimo)
            self.c_sis.addItem(f"Ultimo sviluppato: {ultimo[0].nome or '(senza nome)'} ({len(ultimo[0].colonne)} "
                               "colonne)")
        for nome, s in sis.salvati(arch).items():
            if sistema is not None and s.nome == sistema.nome:
                continue
            self.sistemi.append((s, None))
            self.c_sis.addItem(f"{nome} ({len(s.colonne)} colonne)")
        self.c_sis.currentIndexChanged.connect(self.aggiorna)
        h.addWidget(self.c_sis, 1)
        v.addLayout(h)
        h = QHBoxLayout()
        self.cb_col = QCheckBox("tutte le colonne")
        self.cb_col.setChecked(True)
        self.cb_pres = QCheckBox("presenze dei numeri")
        self.cb_pres.setChecked(True)
        self.cb_gar = QCheckBox("calcolo garanzie")
        self.cb_ss = QCheckBox("con SuperStar")
        for w in (self.cb_col, self.cb_pres, self.cb_gar) + (() if self.g.is_ej else (self.cb_ss,)):
            w.toggled.connect(self.aggiorna)
            h.addWidget(w)
        h.addWidget(QLabel("Colonne per riga"))
        self.sp_riga = QSpinBox()
        self.sp_riga.setRange(1, 8)
        self.sp_riga.setValue(4 if self.g.k == 6 else 5)
        self.sp_riga.valueChanged.connect(self.aggiorna)
        h.addWidget(self.sp_riga)
        h.addStretch()
        v.addLayout(h)
        self.anteprima = QPlainTextEdit()
        self.anteprima.setReadOnly(True)
        self.anteprima.setLineWrapMode(QPlainTextEdit.NoWrap)
        f = QFont("Consolas")
        f.setStyleHint(QFont.Monospace)
        f.setPointSize(9)
        self.anteprima.setFont(f)
        v.addWidget(self.anteprima, 1)
        h = QHBoxLayout()
        for testo, modo in (("🖨 Stampante (anteprima)...", "stampante"), ("📄 Salva PDF...", "pdf"),
                            ("📝 Salva TXT...", "txt")):
            b = QPushButton(testo)
            b.clicked.connect(lambda _=False, m=modo: self.esegui(m))
            h.addWidget(b)
        h.addStretch()
        b = QPushButton("Chiudi")
        b.clicked.connect(self.accept)
        h.addWidget(b)
        v.addLayout(h)
        if not self.sistemi:
            self.anteprima.setPlainText("Nessun sistema: sviluppane uno (Sistemi → Nuovo) o memorizzalo.")
        else:
            self.aggiorna()

    def attuale(self):
        i = self.c_sis.currentIndex()
        return self.sistemi[i] if 0 <= i < len(self.sistemi) else (None, None)

    def _garanzia(self, s, possibili):
        i = self.c_sis.currentIndex()
        if i in self.possibili_cache:
            return self.possibili_cache[i]
        C = np.array(s.colonne, dtype=np.int16).reshape(-1, s.G.k)
        try:
            P = possibili if possibili is not None else sis.possibili_del_sistema(s, sis.contesto_da_archivio(self.arch))
            e = sis.verifica_garanzia(C, P)
        except Exception as ex:
            e = None
            QMessageBox.information(self, "Garanzie", f"Calcolo delle garanzie non possibile: {ex}")
        self.possibili_cache[i] = e
        return e

    def testo(self) -> str:
        s, possibili = self.attuale()
        if s is None:
            return ""
        from .sistemi import leggi_prezzi
        gar = _attesa(lambda: self._garanzia(s, possibili)) if self.cb_gar.isChecked() else None
        return sis.tabulato(s, s.colonne, leggi_prezzi(self.arch), self.cb_ss.isChecked(), gar,
                            self.sp_riga.value(), self.cb_col.isChecked(), self.cb_pres.isChecked())

    def aggiorna(self, *_):
        t = self.testo()
        if len(t) > 3_000_000:
            self.anteprima.setPlainText(t[:3_000_000] + "\n... (anteprima troncata: la stampa contiene tutto)")
        else:
            self.anteprima.setPlainText(t)

    def esegui(self, modo: str):
        s, _ = self.attuale()
        if s is None:
            return
        from . import stampa as sp
        titolo = f"Tabulato – {s.nome or 'sistema'} – {self.g.nome}"
        testo = self.testo()
        if modo == "stampante":
            sp.anteprima(self, titolo, testo)
            return
        est = modo
        nome, _ = QFileDialog.getSaveFileName(self, "Salva " + est.upper(), f"{sp._nome_file(s.nome or 'sistema')}.{est}",
                                              "PDF (*.pdf)" if est == "pdf" else "Testo (*.txt)")
        if not nome:
            return
        try:
            _attesa(lambda: (sp.salva_pdf if est == "pdf" else sp.salva_txt)(nome, titolo, testo))
        except Exception as ex:
            QMessageBox.warning(self, "Tabulato", f"Non riesco a salvare:\n{ex}")
            return
        QMessageBox.information(self, "Tabulato", f"Salvato in:\n{nome}")


def stampa_estrazioni(parent, arch: Archivio, quante: int) -> str:
    """Testo delle ultime N estrazioni (per Stampe → Estrazioni dell'archivio)."""
    g = arch.gioco
    righe = list(arch.sestine())[-quante:] if quante else list(arch.sestine())
    out = []
    for r in reversed(righe):
        extra = (f"   Euronumeri {r[2]} {r[3]}" if g.is_ej else
                 f"   Jolly {r[2] or '-':>2}   SuperStar {r[3] or '-':>2}")
        out.append(f"{r[0]:%d/%m/%Y}   " + " ".join(f"{x:2d}" for x in r[1]) + extra)
    return "\n".join(out)
