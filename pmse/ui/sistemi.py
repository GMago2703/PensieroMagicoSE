"""Sistemi (Windows): Condizionati, Condizionati ridotti, Ridotti, Ridotti immediati.

- EditorSistema: numeri, fisse, condizioni (con la scheda di analisi di ogni condizione), riduzione.
- SchedaCondizione: analisi della condizione sull'archivio, suggerimento, scelta dei valori.
- FinestraSviluppo: colonne sviluppate, costo, verifica della garanzia, spoglio, memorizza/scarta, esporta.
- FinestraSalvati: sistemi memorizzati (apri, modifica, elimina).
"""
from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QThread, Signal
from PySide6.QtGui import QBrush, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QSlider, QSpinBox, QTableView, QTableWidget, QTableWidgetItem,
                               QTabWidget, QVBoxLayout, QWidget)

from ..core import condizioni as cnd
from ..core import ridotti_pronti
from ..core import sistemi as sis
from ..core.db import Archivio
from .griglia import CELLA_BASE, CELLA_SEL, Griglia90
from .schermo import adatta_schermo

COLORE_FISSA = "#c62828"
ULTIMO: dict = {}          # gioco -> (ultimo sistema sviluppato, combinazioni possibili) per i menu
VERDE_OK = "#c8e6c9"
NOMI_TIPO = {"condizionato": "Sistema condizionato", "condizionato_ridotto": "Sistema condizionato ridotto",
             "ridotto": "Sistema ridotto (integrale a garanzia)", "immediato": "Sistema ridotto immediato"}


def _numeri_da_testo(t: str) -> list[int]:
    out = []
    for p in t.replace(",", " ").replace(";", " ").replace("-", " ").split():
        if p.isdigit():
            out.append(int(p))
    return out


# ------------------------------------------------------------------ griglia numeri / fisse
class GrigliaSistema(Griglia90):
    """Clic: libero → numero giocato → fissa → libero."""
    cambiata = Signal()

    def __init__(self, n: int, parent=None):
        super().__init__(True, parent, n=n)
        self.fisse: set[int] = set()

    def _clic(self, n: int):
        if n in self.fisse:
            self.fisse.discard(n)
            self.selezionati.discard(n)
        elif n in self.selezionati:
            self.fisse.add(n)
        else:
            self.selezionati.add(n)
        self._ridisegna_selezione()

    def _ridisegna_selezione(self):
        for n, c in self.celle.items():
            if n in self.fisse:
                c.imposta(COLORE_FISSA, "white", tooltip="Fissa (in tutte le colonne)")
            elif n in self.selezionati:
                c.imposta(CELLA_SEL, "white", tooltip="Numero giocato")
            else:
                c.imposta(CELLA_BASE)
        self.cambiata.emit()

    def imposta(self, numeri, fisse):
        self.selezionati = set(numeri) | set(fisse)
        self.fisse = set(fisse)
        self._ridisegna_selezione()

    def azzera(self):
        self.fisse.clear()
        super().azzera()


# ------------------------------------------------------------------ lavori in background
class Lavoro(QThread):
    avanzamento = Signal(str, int, int)
    finito = Signal(object)
    errore = Signal(str)

    def __init__(self, funzione):
        super().__init__()
        self.funzione = funzione
        self._stop = False

    def run(self):
        try:
            self.finito.emit(self.funzione(lambda t, i, n: self.avanzamento.emit(t, int(i), int(n)),
                                           lambda: self._stop))
        except InterruptedError as ex:
            self.errore.emit(str(ex))
        except Exception as ex:
            self.errore.emit(str(ex) or ex.__class__.__name__)


# ------------------------------------------------------------------ scheda di una condizione
class SchedaCondizione(QDialog):
    """Analisi della condizione sull'archivio + scelta dei valori accettati."""

    def __init__(self, ctx: cnd.Contesto, codice: str, attuale: cnd.Condizione | None = None, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.tipo = cnd.TIPI_PER_CODICE[codice]
        self.risultato: cnd.Condizione | None = None
        self.analisi = None
        self.setWindowTitle(f"Condizione: {self.tipo.nome}")
        adatta_schermo(self, 760, 720)
        v = QVBoxLayout(self)
        d = QLabel(f"<b>{self.tipo.nome}</b> – {self.tipo.descrizione}")
        d.setWordWrap(True)
        v.addWidget(d)
        h = QHBoxLayout()
        self.s_param = QSpinBox()
        if self.tipo.param_nome:
            h.addWidget(QLabel(self.tipo.param_nome + ":"))
            mx = ctx.gioco.k if codice == "posizione" else self.tipo.param_max
            self.s_param.setRange(self.tipo.param_min, mx)
            self.s_param.setValue(attuale.param if attuale else self.tipo.param_def)
            self.s_param.valueChanged.connect(self._analizza)
            h.addWidget(self.s_param)
            h.addSpacing(16)
        h.addWidget(QLabel("Analisi sulle ultime"))
        self.s_ultime = QSpinBox()
        self.s_ultime.setRange(0, 100000)
        self.s_ultime.setSpecialValueText("tutte le estrazioni")
        self.s_ultime.setSuffix(" estrazioni")
        self.s_ultime.valueChanged.connect(self._analizza)
        h.addWidget(self.s_ultime)
        h.addStretch()
        v.addLayout(h)
        self.l_sugg = QLabel()
        self.l_sugg.setWordWrap(True)
        self.l_sugg.setStyleSheet("background:#fff8e1; border:1px solid #ffb300; padding:6px; font-weight:bold;")
        v.addWidget(self.l_sugg)
        self.tab = QTableWidget(0, 4)
        self.tab.setHorizontalHeaderLabels(["Valore (✔ = accettato)", "Uscite in archivio", "% archivio",
                                            "% atteso dal caso"])
        self.tab.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tab.verticalHeader().setVisible(False)
        self.tab.setEditTriggers(QAbstractItemView.NoEditTriggers)
        v.addWidget(self.tab, 1)
        self.box_int = QWidget()
        hi = QHBoxLayout(self.box_int)
        hi.setContentsMargins(0, 0, 0, 0)
        self.s_min, self.s_max = QSpinBox(), QSpinBox()
        for s in (self.s_min, self.s_max):
            s.setRange(-100000, 100000)
        hi.addWidget(QLabel("Valori accettati: da"))
        hi.addWidget(self.s_min)
        hi.addWidget(QLabel("a"))
        hi.addWidget(self.s_max)
        hi.addStretch()
        v.addWidget(self.box_int)
        self.box_int.setVisible(self.tipo.modo == "intervallo")
        self.l_cop = QLabel()
        v.addWidget(self.l_cop)
        h = QHBoxLayout()
        b_s = QPushButton("💡 Applica il suggerimento")
        b_s.clicked.connect(self._applica_suggerimento)
        h.addWidget(b_s)
        h.addStretch()
        b_ok = QPushButton("✔ Usa questa condizione")
        b_ok.clicked.connect(self._ok)
        h.addWidget(b_ok)
        b_no = QPushButton("Annulla")
        b_no.clicked.connect(self.reject)
        h.addWidget(b_no)
        v.addLayout(h)
        self._attuale = attuale
        self._analizza()
        if attuale:
            self._carica(attuale)
        else:
            self._applica_suggerimento()
        self.tab.itemChanged.connect(lambda *_: self._copertura())
        self.s_min.valueChanged.connect(lambda *_: self._copertura())
        self.s_max.valueChanged.connect(lambda *_: self._copertura())

    def _analizza(self, *_):
        try:
            self.analisi = cnd.analizza(self.tipo.codice, self.ctx, self.s_param.value(), self.s_ultime.value())
        except Exception as ex:
            self.l_sugg.setText(f"Analisi non disponibile: {ex}")
            return
        a = self.analisi
        self.l_sugg.setText("💡 " + a.suggerimento)
        scelti = self._valori_scelti() if self.tab.rowCount() else set()
        self.tab.blockSignals(True)
        self.tab.setRowCount(len(a.righe))
        for i, (val, c, perc, teo) in enumerate(a.righe):
            it = QTableWidgetItem(str(val))
            if self.tipo.modo == "valori":
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Checked if val in scelti else Qt.Unchecked)
            self.tab.setItem(i, 0, it)
            self.tab.setItem(i, 1, QTableWidgetItem(str(c)))
            self.tab.setItem(i, 2, QTableWidgetItem(f"{perc:.2f}"))
            self.tab.setItem(i, 3, QTableWidgetItem("–" if math.isnan(teo) else f"{teo:.2f}"))
            if val == a.piu_frequente:
                for j in range(4):
                    self.tab.item(i, j).setBackground(QBrush(QColor("#ffe082")))
                    self.tab.item(i, j).setToolTip("Il valore più frequente in archivio")
        self.tab.blockSignals(False)
        self._copertura()

    def _valori_scelti(self) -> set[int]:
        out = set()
        for i in range(self.tab.rowCount()):
            it = self.tab.item(i, 0)
            if it and it.checkState() == Qt.Checked:
                out.add(int(it.text()))
        return out

    def _carica(self, c: cnd.Condizione):
        if self.tipo.modo == "intervallo":
            self.s_min.setValue(c.minimo)
            self.s_max.setValue(c.massimo)
        else:
            self.tab.blockSignals(True)
            for i in range(self.tab.rowCount()):
                it = self.tab.item(i, 0)
                it.setCheckState(Qt.Checked if int(it.text()) in set(c.valori) else Qt.Unchecked)
            self.tab.blockSignals(False)
        self._copertura()

    def _applica_suggerimento(self):
        if not self.analisi:
            return
        a = self.analisi
        self._carica(cnd.Condizione(self.tipo.codice, valori=a.valori_80, minimo=a.copertura[0],
                                    massimo=a.copertura[1]))

    def _condizione(self) -> cnd.Condizione:
        if self.tipo.modo == "intervallo":
            return cnd.Condizione(self.tipo.codice, minimo=self.s_min.value(), massimo=self.s_max.value(),
                                  param=self.s_param.value())
        return cnd.Condizione(self.tipo.codice, valori=sorted(self._valori_scelti()), param=self.s_param.value())

    def _copertura(self):
        if not self.analisi or not self.analisi.estrazioni:
            return
        c = self._condizione()
        tot = sum(r[1] for r in self.analisi.righe if
                  (c.minimo <= r[0] <= c.massimo if self.tipo.modo == "intervallo" else r[0] in c.valori))
        self.l_cop.setText(f"Con questa scelta sarebbero state accettate <b>{tot / self.analisi.estrazioni * 100:.1f}%"
                           f"</b> delle estrazioni dell'archivio ({tot} su {self.analisi.estrazioni}).")

    def _ok(self):
        c = self._condizione()
        if self.tipo.modo == "valori" and not c.valori:
            QMessageBox.warning(self, "Condizione", "Spunta almeno un valore accettato.")
            return
        if self.tipo.modo == "intervallo" and c.minimo > c.massimo:
            QMessageBox.warning(self, "Condizione", "Il minimo è maggiore del massimo.")
            return
        self.risultato = c
        self.accept()


class SchedaGruppo(QDialog):
    """Fisse / Sequele (gruppi di numeri con presenze minime e massime) e Combinazioni filtro."""

    def __init__(self, g, tipo: str, attuale: cnd.Condizione | None = None, parent=None):
        super().__init__(parent)
        self.tipo = tipo
        self.risultato = None
        k = g.k
        filtro = tipo == "filtro"
        self.setWindowTitle("Combinazioni filtro" if filtro else "Gruppo di numeri (Fisse / Sequele)")
        adatta_schermo(self, 620, 480)
        v = QVBoxLayout(self)
        spieg = QLabel("Incolla le combinazioni (una per riga). La colonna è accettata se il MASSIMO di numeri in "
                       "comune con queste combinazioni è tra il minimo e il massimo indicati." if filtro else
                       "Scrivi i numeri del gruppo. La colonna è accettata se contiene da 'minimo' a 'massimo' numeri "
                       "del gruppo (es. gruppo di 10 numeri, da 1 a 2 presenti).")
        spieg.setWordWrap(True)
        v.addWidget(spieg)
        self.testo = QPlainTextEdit()
        if attuale:
            self.testo.setPlainText("\n".join(" ".join(map(str, c)) for c in attuale.combinazioni) if filtro
                                    else " ".join(map(str, attuale.numeri)))
        v.addWidget(self.testo, 1)
        f = QFormLayout()
        self.s_min, self.s_max = QSpinBox(), QSpinBox()
        for s in (self.s_min, self.s_max):
            s.setRange(0, k)
        self.s_min.setValue(attuale.minimo if attuale else (0 if filtro else 1))
        self.s_max.setValue(attuale.massimo if attuale else (3 if filtro else k))
        f.addRow("Minimo", self.s_min)
        f.addRow("Massimo", self.s_max)
        v.addLayout(f)
        h = QHBoxLayout()
        h.addStretch()
        b = QPushButton("✔ Usa")
        b.clicked.connect(self._ok)
        h.addWidget(b)
        b2 = QPushButton("Annulla")
        b2.clicked.connect(self.reject)
        h.addWidget(b2)
        v.addLayout(h)
        self.g = g

    def _ok(self):
        if self.tipo == "filtro":
            comb = [sorted(set(_numeri_da_testo(r))) for r in self.testo.toPlainText().splitlines()]
            comb = [c for c in comb if c and all(1 <= x <= self.g.n for x in c)]
            if not comb:
                QMessageBox.warning(self, "Filtro", "Nessuna combinazione valida.")
                return
            self.risultato = cnd.Condizione("filtro", combinazioni=comb, minimo=self.s_min.value(),
                                            massimo=self.s_max.value())
        else:
            nums = sorted({x for x in _numeri_da_testo(self.testo.toPlainText()) if 1 <= x <= self.g.n})
            if not nums:
                QMessageBox.warning(self, "Gruppo", "Scrivi almeno un numero.")
                return
            self.risultato = cnd.gruppo(nums, self.s_min.value(), self.s_max.value())
        self.accept()


# ------------------------------------------------------------------ editor del sistema
class EditorSistema(QDialog):
    def __init__(self, arch: Archivio, tipo: str, sistema: sis.Sistema | None = None, parent=None):
        super().__init__(parent)
        self.arch = arch
        self.g = arch.gioco
        self.s = sistema or sis.Sistema(tipo=tipo, gioco=self.g.codice)
        self.s.tipo = sistema.tipo if sistema else tipo
        self._ctx = None
        self.lavoro = None
        self.setWindowTitle(f"{NOMI_TIPO[self.s.tipo]} – {self.g.nome}")
        adatta_schermo(self, 1180, 760)
        v = QVBoxLayout(self)
        h0 = QHBoxLayout()
        h0.addWidget(QLabel("Nome:"))
        self.e_nome = QLineEdit(self.s.nome)
        self.e_nome.setPlaceholderText("(lo chiederò quando memorizzi)")
        h0.addWidget(self.e_nome, 1)
        v.addLayout(h0)
        corpo = QHBoxLayout()
        v.addLayout(corpo, 1)
        # sinistra: numeri
        sx = QVBoxLayout()
        sx.addWidget(QLabel("<b>Numeri da giocare</b>: clic = numero, 2° clic = <span style='color:#c62828'>"
                            "fissa</span>, 3° clic = toglie"))
        self.griglia = GrigliaSistema(self.g.n)
        self.griglia.cambiata.connect(self._aggiorna_info)
        sx.addWidget(self.griglia)
        hn = QHBoxLayout()
        self.e_num = QLineEdit()
        self.e_num.setPlaceholderText("oppure scrivi i numeri: 3 7 15 22 ...")
        self.e_num.returnPressed.connect(self._da_testo)
        hn.addWidget(self.e_num, 1)
        b = QPushButton("Inserisci")
        b.clicked.connect(self._da_testo)
        hn.addWidget(b)
        b = QPushButton("Azzera")
        b.clicked.connect(self.griglia.azzera)
        hn.addWidget(b)
        sx.addLayout(hn)
        corpo.addLayout(sx, 0)
        # destra: condizioni e riduzione
        self.tabs = QTabWidget()
        corpo.addWidget(self.tabs, 1)
        self._tab_condizioni()
        self._tab_riduzione()
        # info e comandi
        self.l_info = QLabel()
        self.l_info.setWordWrap(True)
        self.l_info.setStyleSheet("background:#e3f2fd; padding:6px;")
        v.addWidget(self.l_info)
        self.barra = QProgressBar()
        self.barra.setVisible(False)
        v.addWidget(self.barra)
        h = QHBoxLayout()
        self.b_svil = QPushButton("▶ Sviluppa (F5)")
        self.b_svil.setStyleSheet("font-weight:bold; padding:6px 18px;")
        self.b_svil.clicked.connect(self.sviluppa)
        h.addWidget(self.b_svil)
        b = QPushButton("💾 Memorizza impostazioni...")
        b.setToolTip("Memorizza il sistema con le impostazioni (le colonne si memorizzano dopo lo sviluppo)")
        b.clicked.connect(self._memorizza_impostazioni)
        h.addWidget(b)
        h.addStretch()
        b = QPushButton("Chiudi")
        b.clicked.connect(self.close)
        h.addWidget(b)
        v.addLayout(h)
        QShortcut(QKeySequence("F5"), self, activated=self.sviluppa)
        self.griglia.imposta(self.s.numeri, self.s.fisse)
        self._aggiorna_condizioni()
        self._aggiorna_info()

    # ---------------------------------------------------------- dati
    @property
    def ctx(self) -> cnd.Contesto:
        if self._ctx is None:
            self._ctx = sis.contesto_da_archivio(self.arch)
        return self._ctx

    def _da_testo(self):
        nums = [x for x in _numeri_da_testo(self.e_num.text()) if 1 <= x <= self.g.n]
        self.griglia.imposta(sorted(set(self.griglia.selezionati) | set(nums)), self.griglia.fisse)
        self.e_num.clear()

    def _raccogli(self) -> sis.Sistema:
        s = self.s
        s.nome = self.e_nome.text().strip()
        s.numeri = sorted(self.griglia.selezionati)
        s.fisse = sorted(self.griglia.fisse)
        s.errori_min, s.errori_max = self.s_emin.value(), self.s_emax.value()
        s.garanzia = self.c_gar.currentData() or 0
        s.qualita = self.sl_q.value()
        return s

    # ---------------------------------------------------------- scheda condizioni
    def _tab_condizioni(self):
        w = QWidget()
        v = QVBoxLayout(w)
        cond = self.s.tipo in ("condizionato", "condizionato_ridotto")
        if not cond:
            l = QLabel("Questo tipo di sistema non usa condizioni: sviluppa l'integrale dei numeri giocati "
                       "(con le fisse) ridotto con la garanzia scelta.")
            l.setWordWrap(True)
            v.addWidget(l)
            v.addStretch()
            self.tabs.addTab(w, "Condizioni")
            self.lista = QListWidget()
            self.s_emin, self.s_emax = QSpinBox(), QSpinBox()
            self.tabs.setTabEnabled(0, False)
            return
        v.addWidget(QLabel("Condizioni applicate (doppio clic per aprire la scheda con l'analisi):"))
        self.lista = QListWidget()
        self.lista.itemDoubleClicked.connect(lambda *_: self._modifica())
        v.addWidget(self.lista, 1)
        h = QHBoxLayout()
        b = QPushButton("➕ Aggiungi condizione")
        menu = QMenu(b)
        for t in cnd.tipi_del_gioco(self.g):
            menu.addAction(t.nome, lambda c=t.codice: self.apri_condizione(c))
        menu.addSeparator()
        menu.addAction("Fisse / Sequele (gruppo di numeri)", lambda: self._gruppo("gruppo"))
        menu.addAction("Combinazioni filtro", lambda: self._gruppo("filtro"))
        b.setMenu(menu)
        h.addWidget(b)
        b = QPushButton("Apri scheda")
        b.clicked.connect(self._modifica)
        h.addWidget(b)
        b = QPushButton("Attiva / disattiva")
        b.clicked.connect(self._attiva)
        h.addWidget(b)
        b = QPushButton("Elimina")
        b.clicked.connect(self._elimina)
        h.addWidget(b)
        v.addLayout(h)
        h = QHBoxLayout()
        h.addWidget(QLabel("Errori ammessi: da"))
        self.s_emin, self.s_emax = QSpinBox(), QSpinBox()
        for s in (self.s_emin, self.s_emax):
            s.setRange(0, 30)
        self.s_emin.setValue(self.s.errori_min)
        self.s_emax.setValue(self.s.errori_max)
        h.addWidget(self.s_emin)
        h.addWidget(QLabel("a"))
        h.addWidget(self.s_emax)
        h.addWidget(QLabel("(condizioni non rispettate accettate per colonna)"))
        h.addStretch()
        v.addLayout(h)
        b = QPushButton("📊 Rendimento delle condizioni sull'archivio")
        b.clicked.connect(self.rendimento)
        v.addWidget(b)
        self.tabs.addTab(w, "Condizioni")

    def _conds(self) -> list[cnd.Condizione]:
        return self.s.lista_condizioni()

    def _salva_conds(self, conds):
        self.s.condizioni = cnd.a_json(conds)
        self._aggiorna_condizioni()

    def _aggiorna_condizioni(self):
        self.lista.clear()
        for c in self._conds():
            it = QListWidgetItem(("✔ " if c.attiva else "✖ (disattivata) ") + c.descrivi())
            if not c.attiva:
                it.setForeground(QBrush(QColor("#888")))
            self.lista.addItem(it)

    def apri_condizione(self, codice: str, indice: int | None = None):
        """Apre la scheda della condizione (con l'analisi sull'archivio)."""
        if self.s.tipo not in ("condizionato", "condizionato_ridotto"):
            QMessageBox.information(self, "Condizioni", "Le condizioni si usano nei sistemi condizionati.")
            return
        conds = self._conds()
        if indice is None and codice not in ("posizione", "gruppo", "filtro"):   # stesso tipo: si modifica
            indice = next((i for i, c in enumerate(conds) if c.codice == codice), None)
        attuale = conds[indice] if indice is not None else None
        if codice in ("gruppo", "filtro"):
            d = SchedaGruppo(self.g, codice, attuale, self)
        else:
            d = SchedaCondizione(self.ctx, codice, attuale, self)
        if d.exec() and d.risultato:
            if indice is None:
                conds.append(d.risultato)
            else:
                d.risultato.attiva = conds[indice].attiva
                conds[indice] = d.risultato
            self._salva_conds(conds)

    def _gruppo(self, tipo):
        if self.s.tipo not in ("condizionato", "condizionato_ridotto"):
            QMessageBox.information(self, "Condizioni", "Le condizioni si usano nei sistemi condizionati.")
            return
        d = SchedaGruppo(self.g, tipo, None, self)
        if d.exec() and d.risultato:
            conds = self._conds()
            conds.append(d.risultato)
            self._salva_conds(conds)

    def _modifica(self):
        i = self.lista.currentRow()
        conds = self._conds()
        if 0 <= i < len(conds):
            self.apri_condizione(conds[i].codice, i)

    def _attiva(self):
        i = self.lista.currentRow()
        conds = self._conds()
        if 0 <= i < len(conds):
            conds[i].attiva = not conds[i].attiva
            self._salva_conds(conds)
            self.lista.setCurrentRow(i)

    def _elimina(self):
        i = self.lista.currentRow()
        conds = self._conds()
        if 0 <= i < len(conds):
            del conds[i]
            self._salva_conds(conds)

    def rendimento(self):
        conds = [c for c in self._conds() if c.attiva]
        if not conds:
            QMessageBox.information(self, "Rendimento", "Nessuna condizione attiva.")
            return
        righe = cnd.rendimento(conds, self.ctx)
        testo = "\n".join(f"{p:6.1f}%  {d}" for d, p in righe)
        QMessageBox.information(self, "Rendimento delle condizioni",
                                "Percentuale delle estrazioni dell'archivio che avrebbero rispettato ogni condizione:"
                                "\n\n" + testo + "\n\n(Più è alta la percentuale 'tutte insieme', più spesso le "
                                "condizioni scelte sono state rispettate dalle combinazioni vincenti.)")

    # ---------------------------------------------------------- scheda riduzione
    def _tab_riduzione(self):
        w = QWidget()
        v = QVBoxLayout(w)
        k = self.g.k
        f = QFormLayout()
        self.c_gar = QComboBox()
        if self.s.tipo == "condizionato":
            self.c_gar.addItem("Nessuna riduzione (tutte le colonne condizionate)", 0)
        for j in range(1, k - 1):
            self.c_gar.addItem(f"n-{j}: almeno un {k - j} se i {k} vincenti sono tra le combinazioni possibili", j)
        i = self.c_gar.findData(self.s.garanzia)
        self.c_gar.setCurrentIndex(max(0, i))
        self.c_gar.currentIndexChanged.connect(self._aggiorna_info)
        f.addRow("Garanzia", self.c_gar)
        self.sl_q = QSlider(Qt.Horizontal)
        self.sl_q.setRange(1, 30)
        self.sl_q.setValue(self.s.qualita)
        self.l_q = QLabel()
        self.sl_q.valueChanged.connect(lambda v_: self.l_q.setText(
            "rapidissima" if v_ == 1 else ("accurata (meno colonne)" if v_ >= 16 else "equilibrata")))
        self.sl_q.valueChanged.emit(self.sl_q.value())
        hq = QHBoxLayout()
        hq.addWidget(self.sl_q, 1)
        hq.addWidget(self.l_q)
        if self.s.tipo != "immediato":
            f.addRow("Riduzione", hq)
        v.addLayout(f)
        spieg = QLabel(
            "La garanzia vale se la combinazione vincente è tra quelle possibili del sistema: tutti i numeri estratti "
            "tra quelli giocati, fisse comprese" + (", e condizioni rispettate." if self.s.tipo ==
                                                    "condizionato_ridotto" else "."))
        spieg.setWordWrap(True)
        v.addWidget(spieg)
        if self.s.tipo == "immediato":
            v.addWidget(QLabel("<b>Riduzioni già pronte</b> (numeri giocati, fisse, garanzia → colonne). "
                               "Doppio clic per impostare la garanzia:"))
            self.t_pronti = QTableWidget(0, 4)
            self.t_pronti.setHorizontalHeaderLabels(["Numeri", "Fisse", "Garanzia", "Colonne"])
            self.t_pronti.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.t_pronti.verticalHeader().setVisible(False)
            self.t_pronti.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.t_pronti.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.t_pronti.itemDoubleClicked.connect(self._scegli_pronto)
            v.addWidget(self.t_pronti, 1)
        else:
            v.addStretch()
        self.tabs.addTab(w, "Riduzione e garanzia")
        if self.s.tipo in ("ridotto", "immediato", "condizionato_ridotto"):
            self.tabs.setCurrentIndex(1 if self.s.tipo != "condizionato_ridotto" else 0)

    def _scegli_pronto(self, it):
        r = it.row()
        punti = int(self.t_pronti.item(r, 2).data(Qt.UserRole))
        i = self.c_gar.findData(self.g.k - punti)
        if i >= 0:
            self.c_gar.setCurrentIndex(i)

    def _aggiorna_info(self, *_):
        if not hasattr(self, "c_gar"):
            return
        n, f = len(self.griglia.selezionati), len(self.griglia.fisse)
        k = self.g.k
        tot = sis.numero_integrale(n, k, f)
        testo = f"Numeri giocati: <b>{n}</b> (fisse {f}) – integrale: <b>{tot:,}</b> colonne".replace(",", ".")
        if self.s.tipo == "immediato":
            self.t_pronti.setRowCount(0)
            righe = [r for r in ridotti_pronti.disponibili(k) if r[0] == n and r[1] == f]
            for nn, ff, p, col in righe:
                i = self.t_pronti.rowCount()
                self.t_pronti.insertRow(i)
                it = QTableWidgetItem(f"{k - p} → n-{k - p}: almeno {p} se {k}")
                it.setData(Qt.UserRole, p)
                for j, val in enumerate([str(nn), str(ff), None, str(col)]):
                    self.t_pronti.setItem(i, j, it if val is None else QTableWidgetItem(val))
            gar = self.c_gar.currentData() or 0
            pronta = next((r for r in righe if r[2] == k - gar), None)
            if not righe:
                testo += (" – <span style='color:#c62828'>riduzioni pronte disponibili per "
                          f"{min(ridotti_pronti.NUMERI[k])}-{max(ridotti_pronti.NUMERI[k])} numeri e 0-4 fisse</span>")
            elif pronta:
                testo += f" – sistema pronto: <b>{pronta[3]}</b> colonne"
        self.l_info.setText(testo)

    # ---------------------------------------------------------- sviluppo
    def sviluppa(self):
        if self.lavoro and self.lavoro.isRunning():
            self.lavoro._stop = True
            return
        s = self._raccogli()
        try:
            sis.valida(s)
        except ValueError as ex:
            QMessageBox.warning(self, "Sistema", str(ex))
            return
        ctx = self.ctx if s.tipo in ("condizionato", "condizionato_ridotto") else cnd.Contesto(self.g)
        copia = sis.Sistema.da_json(s.a_json())
        self.lavoro = Lavoro(lambda av, stop: sis.sviluppa(copia, ctx, av, stop))
        self.lavoro.avanzamento.connect(self._avanza)
        self.lavoro.finito.connect(lambda sv: self._finito(copia, sv))
        self.lavoro.errore.connect(self._errore)
        self.b_svil.setText("⏹ Ferma")
        self.barra.setVisible(True)
        self.barra.setRange(0, 0)
        self.lavoro.start()

    def _avanza(self, testo, i, n):
        self.barra.setRange(0, max(n, 1))
        self.barra.setValue(i)
        self.barra.setFormat(testo)

    def _fine(self):
        self.b_svil.setText("▶ Sviluppa (F5)")
        self.barra.setVisible(False)

    def _errore(self, msg):
        self._fine()
        QMessageBox.warning(self, "Sviluppo", msg)

    def _finito(self, s, sv):
        self._fine()
        s.colonne = sv.colonne.tolist()
        s.info = {"integrale": sv.integrale, "possibili": sv.possibili, "secondi": round(sv.secondi, 2)}
        ULTIMO[self.g.codice] = (s, sv.possibili_colonne)
        FinestraSviluppo(self.arch, s, sv.possibili_colonne, self).exec()

    def _memorizza_impostazioni(self):
        s = self._raccogli()
        nome, ok = QInputDialog.getText(self, "Memorizza", "Nome del sistema:", text=s.nome)
        if ok and nome.strip():
            s.nome = nome.strip()
            self.e_nome.setText(s.nome)
            sis.salva(self.arch, s)
            QMessageBox.information(self, "Memorizza", f"Sistema «{s.nome}» memorizzato.")

    def closeEvent(self, ev):
        if self.lavoro and self.lavoro.isRunning():
            self.lavoro._stop = True
            self.lavoro.wait(5000)
        super().closeEvent(ev)


# ------------------------------------------------------------------ risultato dello sviluppo
class ModelloColonne(QAbstractTableModel):
    def __init__(self, colonne: np.ndarray, k: int):
        super().__init__()
        self.c = colonne
        self.k = k
        self.evidenzia: set[int] = set()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.c)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else self.k

    def data(self, idx, ruolo=Qt.DisplayRole):
        if not idx.isValid():
            return None
        v = int(self.c[idx.row(), idx.column()])
        if ruolo == Qt.DisplayRole:
            return str(v)
        if ruolo == Qt.TextAlignmentRole:
            return int(Qt.AlignCenter)
        if ruolo == Qt.BackgroundRole and v in self.evidenzia:
            return QBrush(QColor("#ffd54f"))
        return None

    def headerData(self, s, o, ruolo=Qt.DisplayRole):
        if ruolo != Qt.DisplayRole:
            return None
        return f"N{s + 1}" if o == Qt.Horizontal else str(s + 1)


class FinestraSviluppo(QDialog):
    def __init__(self, arch: Archivio, s: sis.Sistema, possibili: np.ndarray | None = None, parent=None):
        super().__init__(parent)
        self.arch = arch
        self.s = s
        self.g = s.G
        self.possibili = possibili
        self.C = np.array(s.colonne, dtype=np.int16).reshape(-1, self.g.k)
        self.setWindowTitle(f"Sviluppo – {s.nome or NOMI_TIPO.get(s.tipo, s.tipo)} – {self.g.nome}")
        adatta_schermo(self, 1100, 780)
        v = QVBoxLayout(self)
        self.l_sint = QLabel()
        self.l_sint.setWordWrap(True)
        self.l_sint.setTextFormat(Qt.RichText)
        v.addWidget(self.l_sint)
        corpo = QHBoxLayout()
        v.addLayout(corpo, 1)
        self.modello = ModelloColonne(self.C, self.g.k)
        self.vista = QTableView()
        self.vista.setModel(self.modello)
        self.vista.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        corpo.addWidget(self.vista, 1)
        dx = QVBoxLayout()
        self.risultati = QPlainTextEdit()
        self.risultati.setReadOnly(True)
        self.risultati.setPlainText(s.descrizione())
        dx.addWidget(self.risultati, 1)
        for testo, fun in (("🛡 Calcolo garanzie", self.garanzie),
                           ("🎯 Spoglio sull'ultima estrazione", self.spoglio_ultima),
                           ("🎯 Spoglio su una combinazione...", self.spoglio_combinazione),
                           ("📜 Spoglio storico (archivio)...", self.spoglio_storico),
                           ("📄 Esporta (TXT / CSV)...", self.esporta)):
            b = QPushButton(testo)
            b.clicked.connect(fun)
            dx.addWidget(b)
        corpo.addLayout(dx, 1)
        h = QHBoxLayout()
        self.cb_ss = QCheckBox("con SuperStar")
        self.cb_ss.toggled.connect(self._sintesi)
        if not self.g.is_ej:
            h.addWidget(self.cb_ss)
        h.addStretch()
        b = QPushButton("💾 Memorizza...")
        b.clicked.connect(self.memorizza)
        h.addWidget(b)
        b = QPushButton("🗑 Scarta")
        b.clicked.connect(self.reject)
        h.addWidget(b)
        v.addLayout(h)
        self._sintesi()

    def _sintesi(self, *_):
        prezzi = leggi_prezzi(self.arch)
        n = len(self.C)
        euro = sis.costo(n, self.g, prezzi, self.cb_ss.isChecked())
        info = self.s.info or {}
        parti = [f"<b>{NOMI_TIPO.get(self.s.tipo, self.s.tipo)}</b> – {self.g.nome}: "
                 f"<span style='font-size:15px'><b>{n:,}</b> colonne</span> – costo <b>{euro:,.2f} €</b>"
                 .replace(",", "X").replace(".", ",").replace("X", ".")]
        if info:
            parti.append(f"Integrale {info.get('integrale', 0):,} colonne; possibili (condizioni rispettate) "
                         f"{info.get('possibili', 0):,}; sviluppato in {info.get('secondi', 0)} s.".replace(",", "."))
        if self.s.garanzia:
            parti.append(f"Garanzia n-{self.s.garanzia}: almeno {self.s.punti_garantiti} punti se la combinazione "
                         "vincente è tra quelle possibili.")
        self.l_sint.setText("<br>".join(parti))

    def _possibili(self) -> np.ndarray:
        """Le combinazioni vincenti 'possibili' del sistema (per verificare la garanzia)."""
        if self.possibili is not None:
            return self.possibili
        s = sis.Sistema.da_json(self.s.a_json())
        if s.tipo in ("condizionato", "condizionato_ridotto"):
            s.tipo, s.garanzia = "condizionato", 0
            self.possibili = sis.sviluppa(s, sis.contesto_da_archivio(self.arch)).colonne
        else:
            if sis.numero_integrale(len(s.numeri), self.g.k, len(s.fisse)) > sis.LIMITE_INTEGRALE:
                raise ValueError("Integrale troppo grande per la verifica.")
            self.possibili = np.vstack(list(sis.integrale(s.numeri, self.g.k, s.fisse)))
        return self.possibili

    def garanzie(self):
        try:
            P = self._possibili()
        except Exception as ex:
            QMessageBox.warning(self, "Garanzie", str(ex))
            return
        e = sis.verifica_garanzia(self.C, P)
        self.risultati.setPlainText(self.s.descrizione() + "\n\nCALCOLO GARANZIE\n" + e.testo(self.g.k))

    def _mostra_spoglio(self, titolo, numeri, jolly=None, euro=()):
        r = sis.spoglio(self.C, numeri, jolly, self.g, euro)
        self.modello.evidenzia = set(numeri)
        self.modello.layoutChanged.emit()
        righe = [f"{titolo}: {' '.join(map(str, sorted(numeri)))}" + (f"  Jolly {jolly}" if jolly and not self.g.is_ej
                                                                      else "")]
        righe += [f"  {cat:>4} punti: {c} colonne" for cat, c in r.items() if c]
        if not any(r.values()):
            righe.append("  nessuna colonna vincente")
        self.risultati.setPlainText(self.s.descrizione() + "\n\nSPOGLIO\n" + "\n".join(righe))

    def spoglio_ultima(self):
        e = self.arch.ultima()
        if not e:
            QMessageBox.information(self, "Spoglio", "Archivio vuoto.")
            return
        self._mostra_spoglio(f"Estrazione del {e.data:%d/%m/%Y}", e.numeri, e.jolly,
                             (e.jolly, e.superstar) if self.g.is_ej else ())

    def spoglio_combinazione(self):
        t, ok = QInputDialog.getText(self, "Spoglio", f"Combinazione vincente ({self.g.k} numeri, Jolly facoltativo):")
        if not ok:
            return
        nums = _numeri_da_testo(t)
        if len(nums) < self.g.k:
            QMessageBox.warning(self, "Spoglio", f"Servono {self.g.k} numeri.")
            return
        self._mostra_spoglio("Combinazione", nums[:self.g.k], nums[self.g.k] if len(nums) > self.g.k else None)

    def spoglio_storico(self):
        n, ok = QInputDialog.getInt(self, "Spoglio storico", "Su quante estrazioni recenti? (0 = tutto l'archivio)",
                                    500, 0, 100000)
        if not ok:
            return
        r = sis.spoglio_storico(self.C, self.arch.tutte(True), self.g, n)
        righe = [f"SPOGLIO STORICO su {r['estrazioni']} estrazioni"]
        for p in sorted(r["colonne_vincenti"], reverse=True):
            righe.append(f"  {p} punti: {r['colonne_vincenti'][p]} colonne vincenti in {r['concorsi_con'][p]} "
                         "concorsi")
        top = sorted(r["migliori"], key=lambda t: -t[1])[:10]
        righe.append("Migliori concorsi: " + ", ".join(f"{d:%d/%m/%Y} ({p})" for d, p in top))
        self.risultati.setPlainText(self.s.descrizione() + "\n\n" + "\n".join(righe))

    def esporta(self):
        nome, filtro = QFileDialog.getSaveFileName(self, "Esporta sistema", (self.s.nome or "sistema") + ".txt",
                                                   "Testo (*.txt);;CSV (*.csv)")
        if not nome:
            return
        if nome.lower().endswith(".csv"):
            testo = "\n".join(";".join(str(int(x)) for x in c) for c in self.C)
        else:
            testo = sis.esporta_testo(self.s, self.C)
        with open(nome, "w", encoding="utf-8") as f:
            f.write(testo)
        QMessageBox.information(self, "Esporta", f"Salvate {len(self.C)} colonne in {nome}")

    def memorizza(self):
        nome, ok = QInputDialog.getText(self, "Memorizza sistema", "Nome del sistema:", text=self.s.nome)
        if not ok or not nome.strip():
            return
        if nome.strip() in sis.salvati(self.arch) and QMessageBox.question(
                self, "Memorizza", f"Esiste già «{nome.strip()}». Sostituirlo?") != QMessageBox.Yes:
            return
        self.s.nome = nome.strip()
        sis.salva(self.arch, self.s)
        QMessageBox.information(self, "Memorizza", f"Sistema «{self.s.nome}» memorizzato ({len(self.C)} colonne).")
        self.accept()


# ------------------------------------------------------------------ sistemi memorizzati
class FinestraSalvati(QDialog):
    def __init__(self, arch: Archivio, parent=None, apri_editor=None):
        super().__init__(parent)
        self.arch = arch
        self.apri_editor = apri_editor
        self.setWindowTitle(f"Sistemi memorizzati – {arch.gioco.nome}")
        adatta_schermo(self, 820, 520)
        v = QVBoxLayout(self)
        self.t = QTableWidget(0, 5)
        self.t.setHorizontalHeaderLabels(["Nome", "Tipo", "Numeri", "Colonne", "Memorizzato"])
        self.t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.t.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.t.verticalHeader().setVisible(False)
        self.t.itemDoubleClicked.connect(lambda *_: self.vedi())
        v.addWidget(self.t, 1)
        h = QHBoxLayout()
        for testo, fun in (("📋 Vedi colonne", self.vedi), ("✏ Modifica / risviluppa", self.modifica),
                           ("🗑 Cancella", self.cancella)):
            b = QPushButton(testo)
            b.clicked.connect(fun)
            h.addWidget(b)
        h.addStretch()
        b = QPushButton("Chiudi")
        b.clicked.connect(self.accept)
        h.addWidget(b)
        v.addLayout(h)
        self.carica()

    def carica(self):
        self.tutti = sis.salvati(self.arch)
        self.t.setRowCount(0)
        for nome, s in sorted(self.tutti.items()):
            i = self.t.rowCount()
            self.t.insertRow(i)
            for j, val in enumerate([nome, NOMI_TIPO.get(s.tipo, s.tipo), f"{len(s.numeri)} (fisse {len(s.fisse)})",
                                     str(len(s.colonne)) if s.colonne else "non sviluppato",
                                     s.creato.replace("T", " ")]):
                self.t.setItem(i, j, QTableWidgetItem(val))

    def _scelto(self) -> sis.Sistema | None:
        r = self.t.currentRow()
        if r < 0:
            QMessageBox.information(self, "Sistemi", "Seleziona un sistema.")
            return None
        return self.tutti.get(self.t.item(r, 0).text())

    def vedi(self):
        s = self._scelto()
        if not s:
            return
        if not s.colonne:
            QMessageBox.information(self, "Sistemi", "Sistema non ancora sviluppato: usa 'Modifica / risviluppa'.")
            return
        ULTIMO[self.arch.gioco.codice] = (s, None)
        FinestraSviluppo(self.arch, s, None, self).exec()
        self.carica()

    def modifica(self):
        s = self._scelto()
        if s and self.apri_editor:
            self.accept()
            self.apri_editor(s.tipo, s)

    def cancella(self):
        s = self._scelto()
        if s and QMessageBox.question(self, "Cancella", f"Cancellare il sistema «{s.nome}»?") == QMessageBox.Yes:
            sis.elimina(self.arch, s.nome)
            self.carica()


# ------------------------------------------------------------------ analisi di tutte le condizioni
class FinestraAnalisiCondizioni(QDialog):
    """Per ogni condizione: valore più frequente e valori consigliati, calcolati sull'archivio."""

    def __init__(self, arch: Archivio, parent=None, editor_cb=None):
        super().__init__(parent)
        self.arch = arch
        self.editor_cb = editor_cb
        self.setWindowTitle(f"Analisi delle condizioni sull'archivio – {arch.gioco.nome}")
        adatta_schermo(self, 1100, 680)
        v = QVBoxLayout(self)
        l = QLabel("Per ogni condizione: il valore più frequente nelle estrazioni reali e i valori consigliati (che "
                   "insieme coprono circa l'80% delle estrazioni). Doppio clic per aprire la scheda completa.")
        l.setWordWrap(True)
        v.addWidget(l)
        self.t = QTableWidget(0, 3)
        self.t.setHorizontalHeaderLabels(["Condizione", "Più frequente", "Suggerimento"])
        self.t.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.t.setWordWrap(True)
        self.t.verticalHeader().setVisible(False)
        self.t.itemDoubleClicked.connect(self._apri)
        v.addWidget(self.t, 1)
        ctx = sis.contesto_da_archivio(arch)
        self.ctx = ctx
        if len(ctx.estrazioni) < 30:
            l.setText("Archivio troppo piccolo: aggiorna prima le estrazioni.")
            return
        self.codici = []
        for tp in cnd.tipi_del_gioco(arch.gioco):
            if tp.codice == "popolarita" and ctx.popolarita is None:
                continue
            a = cnd.analizza(tp.codice, ctx, tp.param_def)
            i = self.t.rowCount()
            self.t.insertRow(i)
            self.t.setItem(i, 0, QTableWidgetItem(tp.nome + (f" ({tp.param_nome} {tp.param_def})"
                                                             if tp.param_nome else "")))
            it = QTableWidgetItem(str(a.piu_frequente))
            it.setBackground(QBrush(QColor("#ffe082")))
            self.t.setItem(i, 1, it)
            self.t.setItem(i, 2, QTableWidgetItem(a.suggerimento))
            self.codici.append(tp.codice)
        self.t.resizeRowsToContents()
        self.t.resizeColumnToContents(0)

    def _apri(self, it):
        codice = self.codici[it.row()]
        if self.editor_cb:
            self.editor_cb(codice)
        else:
            SchedaCondizione(self.ctx, codice, None, self).exec()


# ------------------------------------------------------------------ prezzi
def leggi_prezzi(arch) -> dict:
    import json
    try:
        return json.loads(arch.leggi_impostazione(sis.CHIAVE_PREZZI) or "{}")
    except ValueError:
        return {}


class FinestraPrezzi(QDialog):
    def __init__(self, arch: Archivio, parent=None):
        super().__init__(parent)
        self.arch = arch
        self.setWindowTitle("Impostazioni dello sviluppo – prezzi")
        v = QVBoxLayout(self)
        f = QFormLayout()
        p = leggi_prezzi(arch)
        self.s = {}
        voci = [("EJ", "Prezzo di una colonna (Eurojackpot)", 2.0)] if arch.gioco.is_ej else [
            ("SE", "Prezzo di una colonna (SuperEnalotto)", 1.0), ("superstar", "Supplemento SuperStar", 0.5)]
        for chiave, testo, defa in voci:
            sp = QDoubleSpinBox()
            sp.setRange(0, 100)
            sp.setDecimals(2)
            sp.setSuffix(" €")
            sp.setValue(float(p.get(chiave, defa)))
            f.addRow(testo, sp)
            self.s[chiave] = sp
        v.addLayout(f)
        l = QLabel("I prezzi servono solo a calcolare il costo dei sistemi: aggiornali se cambiano.")
        l.setWordWrap(True)
        v.addWidget(l)
        h = QHBoxLayout()
        h.addStretch()
        b = QPushButton("💾 Salva")
        b.clicked.connect(self._salva)
        h.addWidget(b)
        v.addLayout(h)

    def _salva(self):
        import json
        p = leggi_prezzi(self.arch)
        p.update({k: s.value() for k, s in self.s.items()})
        self.arch.scrivi_impostazione(sis.CHIAVE_PREZZI, json.dumps(p))
        self.accept()
