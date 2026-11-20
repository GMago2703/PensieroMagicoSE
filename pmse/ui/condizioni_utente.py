"""Condizioni scelte dall'utente: Quadri (più gruppi di numeri con una regola), insiemi di numeri personali e la
raccolta «Le mie condizioni» (salvare, caricare, duplicare, eliminare, aggiungere ai sistemi)."""
from __future__ import annotations

import html

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QFrame,
                               QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMenu, QMessageBox, QPushButton, QRadioButton, QScrollArea,
                               QSpinBox, QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget)

from ..core import condizioni as cnd
from ..core import condizioni_utente as cu
from ..core import sistemi as sis
from .schermo import adatta_schermo
from .sistemi import COLORI_GRUPPI, VERDE_OK, SchedaCondizione, SchedaGruppiTra, _numeri_da_testo

SELEZIONE = "background:#263238; color:white; font-weight:bold; border:2px solid #ffca28;"


class BarraInsiemi(QWidget):
    """I gruppi di numeri più comuni (decine, finali, pari...) con un clic, più taglia / copia / incolla dei numeri
    scelti. Lavora su una selezione esterna tramite le due funzioni 'leggi' e 'scrivi'."""

    def __init__(self, g, leggi, scrivi, disponibili=None, parent=None):
        super().__init__(parent)
        self.g, self.leggi, self.scrivi = g, leggi, scrivi
        self.disponibili = set(disponibili) if disponibili else set(range(1, g.n + 1))
        self.nome_ultimo = ""
        self.insiemi = cnd.insiemi_comuni(g)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        riga = QHBoxLayout()
        riga.addWidget(QLabel("<b>Gruppi comuni, con un clic:</b>"))
        for titolo, prefisso in (("Decine ▾", "Decina"), ("Finali ▾", "Finale")):
            b = QPushButton(titolo)
            b.setProperty("senza_icona", True)
            m = QMenu(b)
            for nome in self.insiemi:
                if nome.startswith(prefisso):
                    m.addAction(nome, lambda n=nome: self.metti(n))
            b.setMenu(m)
            riga.addWidget(b)
        for nome in ("Pari", "Dispari"):
            self._bottone(riga, nome, nome)
        for nome in self.insiemi:
            if nome.startswith(("Bassi", "Alti")):
                self._bottone(riga, nome.split(" ")[0], nome)
        self._bottone(riga, "Primi", "Primi")
        b = QPushButton("Altri ▾")
        b.setProperty("senza_icona", True)
        m = QMenu(b)
        for nome in self.insiemi:
            if nome.startswith(("Multipli", "Quadrati", "Numeri doppi", "Tutti")):
                m.addAction(nome, lambda n=nome: self.metti(n))
        b.setMenu(m)
        riga.addWidget(b)
        riga.addStretch()
        v.addLayout(riga)
        riga = QHBoxLayout()
        self.cb_somma = QCheckBox("Aggiungi ai numeri già scelti (senza sostituirli)")
        riga.addWidget(self.cb_somma)
        for testo, f in (("Taglia numeri", self.taglia), ("Copia numeri", self.copia), ("Incolla numeri", self.incolla),
                         ("Inverti", self.inverti), ("Pulisci", self.pulisci)):
            b = QPushButton(testo)
            b.clicked.connect(f)
            if testo == "Inverti":
                b.setProperty("senza_icona", True)
                b.setText("↔ Inverti")
            riga.addWidget(b)
        riga.addStretch()
        v.addLayout(riga)

    def _bottone(self, riga, testo, nome):
        b = QPushButton(testo)
        b.setProperty("senza_icona", True)
        b.clicked.connect(lambda _=False, n=nome: self.metti(n))
        riga.addWidget(b)

    def metti(self, nome: str):
        nuovi = set(self.insiemi[nome]) & self.disponibili
        self.nome_ultimo = "" if self.cb_somma.isChecked() else nome
        self.scrivi((set(self.leggi()) | nuovi) if self.cb_somma.isChecked() else nuovi)

    def copia(self):
        QApplication.clipboard().setText(" ".join(map(str, sorted(self.leggi()))))

    def taglia(self):
        self.copia()
        self.scrivi(set())

    def incolla(self):
        nuovi = {x for x in _numeri_da_testo(QApplication.clipboard().text()) if x in self.disponibili}
        if nuovi:
            self.scrivi((set(self.leggi()) | nuovi) if self.cb_somma.isChecked() else nuovi)

    def inverti(self):
        self.scrivi(self.disponibili - set(self.leggi()))

    def pulisci(self):
        self.scrivi(set())


# ------------------------------------------------------------------ Quadri
COLONNE_INIZIALI = 7


def apri_aiuto(parent, g, capitolo="sistemi"):
    from .guida import FinestraGuida
    FinestraGuida(g, parent, capitolo).exec()


RADIO_REGOLE = (("AND (Tutte)", "tutte"), ("OR (Almeno una)", "almeno_una"),
                ("XOR (Soltanto una)", "una_sola"), ("NOT (Esclusione)", "nessuna"))


class SchedaQuadri(QDialog):
    """Quadri: colonne verticali numerate (001, 002...), ognuna con un gruppo di numeri scelti dall'utente (anche con
    i gruppi comuni a un clic). Un gruppo è verificato se la colonna sviluppata ne contiene da un minimo a un
    massimo; la regola dice quanti gruppi devono esserlo."""
    CLIP_GRUPPO: dict | None = None

    def __init__(self, g, ctx, numeri, attuale=None, parent=None, arch=None):
        super().__init__(parent)
        self.g, self.ctx, self.arch = g, ctx, arch
        self.numeri = sorted(set(numeri)) or list(range(1, g.n + 1))
        self.risultato: cnd.Condizione | None = None
        self.gruppi: list[dict] = [dict(x) for x in (attuale.gruppi if attuale and attuale.codice == "quadri" else [])]
        while len(self.gruppi) < COLONNE_INIZIALI:
            self.gruppi.append(self._vuoto())
        self.corrente = 0
        self.setWindowTitle("Quadro")
        adatta_schermo(self, 1240, 900)
        v = QVBoxLayout(self)

        alto = QHBoxLayout()
        box = QGroupBox("Relazione tra le condizioni")
        bl = QGridLayout(box)
        self.radio = {}
        for i, (testo, k) in enumerate(RADIO_REGOLE):
            r = QRadioButton(testo)
            r.toggled.connect(lambda on, k=k: on and self._da_radio(k))
            bl.addWidget(r, i // 2, i % 2)
            self.radio[k] = r
        self.c_regola = QComboBox()
        for k, (testo, _) in cnd.REGOLE_QUADRI.items():
            self.c_regola.addItem(testo, k)
        self.c_regola.addItem("Personalizzata: scelgo io da quanti a quanti gruppi", "")
        self.s_n = QSpinBox()
        self.s_n.setRange(0, 26)
        self.s_n.setValue(1)
        self.s_gmin, self.s_gmax = QSpinBox(), QSpinBox()
        for s in (self.s_gmin, self.s_gmax):
            s.setRange(0, 26)
        altre = QHBoxLayout()
        altre.addWidget(QLabel("Altre regole:"))
        altre.addWidget(self.c_regola, 1)
        altre.addWidget(QLabel("N ="))
        altre.addWidget(self.s_n)
        altre.addWidget(QLabel("da"))
        altre.addWidget(self.s_gmin)
        altre.addWidget(QLabel("a"))
        altre.addWidget(self.s_gmax)
        bl.addLayout(altre, 2, 0, 1, 2)
        alto.addWidget(box, 3)
        box = QGroupBox("Stato")
        sl = QVBoxLayout(box)
        self.r_attivo, self.r_disattivo = QRadioButton("Attivato"), QRadioButton("Disattivato")
        self.r_attivo.setChecked(attuale is None or attuale.attiva)
        self.r_disattivo.setChecked(attuale is not None and not attuale.attiva)
        sl.addWidget(self.r_attivo)
        sl.addWidget(self.r_disattivo)
        alto.addWidget(box, 1)
        v.addLayout(alto)

        self.barra = BarraInsiemi(g, lambda: set(self.gruppi[self.corrente]["numeri"]), self._scrivi_corrente,
                                  self.numeri, self)
        v.addWidget(self.barra)

        corpo = QHBoxLayout()
        sx = QVBoxLayout()
        sx.addWidget(QLabel(f"<b>Numeri del sistema</b> ({len(self.numeri)}) – clicca per metterli o toglierli "
                            "nella colonna selezionata"))
        gl = QGridLayout()
        gl.setSpacing(3)
        self.bottoni = {}
        col = 10 if len(self.numeri) > 40 else 8
        for i, n in enumerate(self.numeri):
            b = QPushButton(str(n))
            b.setProperty("senza_icona", True)
            b.setFixedSize(38, 30)
            b.clicked.connect(lambda _=False, n=n: self._clic(n))
            gl.addWidget(b, i // col, i % col)
            self.bottoni[n] = b
        scheda = QWidget()
        scheda.setLayout(gl)
        sx.addWidget(scheda)
        self.l_sel = QLabel()
        self.l_sel.setWordWrap(True)
        sx.addWidget(self.l_sel)
        riga = QHBoxLayout()
        for testo, f in (("Taglia colonna", self._taglia_gruppo), ("Copia colonna", self._copia_gruppo),
                         ("Incolla colonna", self._incolla_gruppo), ("Duplica colonna", self._duplica_gruppo),
                         ("◀ Sposta", lambda: self._sposta(-1)), ("Sposta ▶", lambda: self._sposta(1)),
                         ("Aggiungi colonna", self._aggiungi_colonna), ("Elimina colonna", self._elimina_colonna)):
            b = QPushButton(testo)
            b.clicked.connect(f)
            riga.addWidget(b)
        sx.addLayout(riga)
        riga = QHBoxLayout()
        riga.addWidget(QLabel("Crea tutte le colonne in un colpo:"))
        for testo, f in (("Le decine", cnd.decine), ("I finali 0-9", cnd.finali)):
            b = QPushButton(testo)
            b.setProperty("senza_icona", True)
            b.clicked.connect(lambda _=False, f=f: self._crea_tutti(f(g)))
            riga.addWidget(b)
        riga.addStretch()
        sx.addLayout(riga)
        corpo.addLayout(sx, 3)

        dx = QVBoxLayout()
        icone = QHBoxLayout()
        for testo, tip, f in (("Carica", "Carica un mio quadro", self._carica_quadro),
                              ("Salva", "Salva questo quadro tra Le mie condizioni", self._salva_quadro)):
            b = QPushButton(testo)
            b.setToolTip(tip)
            b.clicked.connect(f)
            icone.addWidget(b)
        dx.addLayout(icone)
        dx.addWidget(QLabel("Nome del quadro"))
        self.e_nome = QLineEdit(attuale.nome if attuale else "")
        self.e_nome.setPlaceholderText("Quadro")
        dx.addWidget(self.e_nome)
        for testo, f in (("Archivio", self._archivio), ("Analisi", self._analisi), ("Azzera", self._svuota)):
            b = QPushButton(testo)
            b.setMinimumHeight(40)
            b.clicked.connect(f)
            dx.addWidget(b)
        dx.addStretch()
        corpo.addLayout(dx, 1)
        v.addLayout(corpo)

        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setMinimumHeight(250)
        v.addWidget(self.area, 1)
        self.l_info = QLabel()
        self.l_info.setWordWrap(True)
        v.addWidget(self.l_info)

        fondo = QHBoxLayout()
        fondo.addStretch()
        for testo, f in (("OK", self._ok), ("Annulla", self.reject), ("Aiuto", lambda: apri_aiuto(self, g))):
            b = QPushButton(testo)
            b.clicked.connect(f)
            fondo.addWidget(b)
        v.addLayout(fondo)

        if attuale and attuale.codice == "quadri":
            i = self.c_regola.findData(attuale.regola)
            self.c_regola.setCurrentIndex(i if i >= 0 else self.c_regola.count() - 1)
            if attuale.regola in ("almeno_n", "esattamente_n"):
                self.s_n.setValue(attuale.minimo)
            elif attuale.regola == "al_massimo_n":
                self.s_n.setValue(attuale.massimo)
            elif not attuale.regola:
                self.s_gmin.setValue(attuale.minimo)
                self.s_gmax.setValue(attuale.massimo)
        self.c_regola.currentIndexChanged.connect(self._regola)
        self.s_n.valueChanged.connect(self._regola)
        self._ricostruisci()
        self._regola()

    # ---------------------------------------------------------------- colonne
    def _vuoto(self) -> dict:
        return {"numeri": [], "minimo": 1, "massimo": 1, "nome": ""}

    def _ricostruisci(self):
        corpo = QWidget()
        h = QHBoxLayout(corpo)
        h.setSpacing(6)
        self.liste, self.intest, self.s_lo, self.s_hi = [], [], [], []
        for i, gr in enumerate(self.gruppi):
            col = QFrame()
            col.setFrameShape(QFrame.StyledPanel)
            cl = QVBoxLayout(col)
            cl.setContentsMargins(4, 4, 4, 4)
            b = QPushButton(f"{i + 1:03d}" + (f"\n{gr['nome']}" if gr.get("nome") else ""))
            b.setProperty("senza_icona", True)
            b.clicked.connect(lambda _=False, i=i: self._seleziona(i))
            cl.addWidget(b)
            lista = QListWidget()
            lista.setMinimumWidth(62)
            lista.setMaximumWidth(86)
            lista.setFocusPolicy(Qt.NoFocus)
            lista.itemClicked.connect(lambda *_, i=i: self._seleziona(i))
            for n in sorted(gr["numeri"]):
                lista.addItem(f"{n:>3}")
            cl.addWidget(lista, 1)
            lo, hi = QSpinBox(), QSpinBox()
            for s, val in ((lo, gr["minimo"]), (hi, gr["massimo"])):
                s.setRange(0, self.g.k)
                s.setValue(min(val, self.g.k))
            lo.valueChanged.connect(lambda x, i=i: self._cambia_limite(i, "minimo", x))
            hi.valueChanged.connect(lambda x, i=i: self._cambia_limite(i, "massimo", x))
            f = QFormLayout()
            f.addRow("da", lo)
            f.addRow("a", hi)
            cl.addLayout(f)
            h.addWidget(col)
            self.liste.append(lista)
            self.intest.append((col, b))
            self.s_lo.append(lo)
            self.s_hi.append(hi)
        h.addStretch()
        self.area.setWidget(corpo)
        self._colori()

    def _cambia_limite(self, i, chiave, x):
        if 0 <= i < len(self.gruppi):
            self.gruppi[i][chiave] = x
            gr = self.gruppi[i]
            if gr["minimo"] > gr["massimo"]:
                altro = "massimo" if chiave == "minimo" else "minimo"
                gr[altro] = x
                (self.s_hi if chiave == "minimo" else self.s_lo)[i].blockSignals(True)
                (self.s_hi if chiave == "minimo" else self.s_lo)[i].setValue(x)
                (self.s_hi if chiave == "minimo" else self.s_lo)[i].blockSignals(False)

    def _seleziona(self, i):
        if 0 <= i < len(self.gruppi):
            self.corrente = i
            self._colori()

    def _colori(self):
        for i, (col, b) in enumerate(self.intest):
            c = COLORI_GRUPPI[i % len(COLORI_GRUPPI)]
            b.setStyleSheet(f"background:{c}; color:white; font-weight:bold;" +
                            (" border:3px solid #ffca28;" if i == self.corrente else ""))
            col.setStyleSheet("QFrame{background:#e3f2fd;}" if i == self.corrente else "")
        cur = set(self.gruppi[self.corrente]["numeri"])
        for n, b in self.bottoni.items():
            ing = [i for i, x in enumerate(self.gruppi) if n in x["numeri"]]
            if n in cur:
                c = COLORI_GRUPPI[self.corrente % len(COLORI_GRUPPI)]
                b.setStyleSheet(f"background:{c}; color:white; font-weight:bold; border:2px solid #ffca28;")
            elif ing:
                b.setStyleSheet(f"background:{COLORI_GRUPPI[ing[0] % len(COLORI_GRUPPI)]}55;")
            else:
                b.setStyleSheet("")
        self.l_sel.setText(f"Colonna selezionata: <b>{self.corrente + 1:03d}</b> – {len(cur)} numeri"
                           + (f": {' '.join(map(str, sorted(cur)))}" if cur else ""))

    def _aggiorna_colonna(self, i):
        gr = self.gruppi[i]
        self.liste[i].clear()
        for n in sorted(gr["numeri"]):
            self.liste[i].addItem(f"{n:>3}")
        self.s_hi[i].setMaximum(self.g.k)
        if gr["numeri"] and gr["massimo"] > len(gr["numeri"]):
            gr["massimo"] = len(gr["numeri"])
        gr["minimo"] = min(gr["minimo"], gr["massimo"])
        for s, val in ((self.s_lo[i], gr["minimo"]), (self.s_hi[i], gr["massimo"])):
            s.blockSignals(True)
            s.setValue(val)
            s.blockSignals(False)
        b = self.intest[i][1]
        b.setText(f"{i + 1:03d}" + (f"\n{gr['nome']}" if gr.get("nome") else ""))
        self._colori()
        self._regola()

    def _imposta_numeri(self, i, nuovi):
        gr = self.gruppi[i]
        prima = len(gr["numeri"])
        era_pieno = gr["massimo"] >= prima             # il massimo seguiva il numero di numeri del gruppo
        gr["numeri"] = sorted(set(nuovi) & set(self.numeri))
        if gr["numeri"] and (not prima or era_pieno):
            gr["minimo"] = max(1, min(gr["minimo"], len(gr["numeri"]))) if prima else 1
            gr["massimo"] = min(len(gr["numeri"]), self.g.k)
        self._aggiorna_colonna(i)

    def _scrivi_corrente(self, nuovi):
        nome = self.barra.nome_ultimo
        self._imposta_numeri(self.corrente, nuovi)
        if nome and self.gruppi[self.corrente]["numeri"]:
            self.gruppi[self.corrente]["nome"] = nome
            self._aggiorna_colonna(self.corrente)
        self.barra.nome_ultimo = ""

    def _clic(self, n):
        self.barra.nome_ultimo = ""
        cur = set(self.gruppi[self.corrente]["numeri"])
        self._imposta_numeri(self.corrente, cur ^ {n})

    def _aggiungi_colonna(self):
        if len(self.gruppi) < 26:
            self.gruppi.append(self._vuoto())
            self.corrente = len(self.gruppi) - 1
            self._ricostruisci()
            self._regola()

    def _elimina_colonna(self):
        if len(self.gruppi) > 1:
            del self.gruppi[self.corrente]
            self.corrente = min(self.corrente, len(self.gruppi) - 1)
            self._ricostruisci()
            self._regola()

    def _copia_gruppo(self):
        SchedaQuadri.CLIP_GRUPPO = dict(self.gruppi[self.corrente])
        QApplication.clipboard().setText(" ".join(map(str, self.gruppi[self.corrente]["numeri"])))

    def _taglia_gruppo(self):
        self._copia_gruppo()
        self.gruppi[self.corrente] = self._vuoto()
        self._aggiorna_colonna(self.corrente)

    def _incolla_gruppo(self):
        c = SchedaQuadri.CLIP_GRUPPO
        if c is None:
            nuovi = sorted({x for x in _numeri_da_testo(QApplication.clipboard().text()) if x in self.numeri})
            if not nuovi:
                QMessageBox.information(self, "Quadro", "Niente da incollare: copia prima una colonna.")
                return
            c = {"numeri": nuovi, "minimo": 1, "massimo": min(len(nuovi), self.g.k), "nome": ""}
        nuovo = dict(c)
        nuovo["numeri"] = [n for n in c["numeri"] if n in self.numeri]
        self.gruppi[self.corrente] = nuovo
        self._ricostruisci()
        self._regola()

    def _duplica_gruppo(self):
        if len(self.gruppi) < 26:
            self.gruppi.insert(self.corrente + 1, dict(self.gruppi[self.corrente]))
            self.corrente += 1
            self._ricostruisci()
            self._regola()

    def _sposta(self, d):
        i, j = self.corrente, self.corrente + d
        if 0 <= j < len(self.gruppi):
            self.gruppi[i], self.gruppi[j] = self.gruppi[j], self.gruppi[i]
            self.corrente = j
            self._ricostruisci()

    def _svuota(self):
        if QMessageBox.question(self, "Quadro", "Azzerare tutte le colonne?") != QMessageBox.Yes:
            return
        self.gruppi = [self._vuoto() for _ in range(COLONNE_INIZIALI)]
        self.corrente = 0
        self._ricostruisci()
        self._regola()

    def _crea_tutti(self, gruppi: list[dict]):
        nuovi = []
        for x in gruppi:
            nums = [n for n in x["numeri"] if n in self.numeri]
            if nums:
                nuovi.append({"nome": x.get("nome", ""), "numeri": nums, "minimo": 1,
                              "massimo": min(len(nums), self.g.k)})
        if not nuovi:
            QMessageBox.information(self, "Quadro", "Nessuno dei numeri del sistema rientra in questi gruppi.")
            return
        self.gruppi = nuovi[:26]
        while len(self.gruppi) < COLONNE_INIZIALI:
            self.gruppi.append(self._vuoto())
        self.corrente = 0
        self._ricostruisci()
        self._regola()

    def _piene(self) -> list[dict]:
        return [gr for gr in self.gruppi if gr["numeri"]]

    # ---------------------------------------------------------------- regola
    def _da_radio(self, k):
        i = self.c_regola.findData(k)
        if i >= 0:
            self.c_regola.setCurrentIndex(i)

    def _regola(self, *_):
        k = self.c_regola.currentData()
        n_g = len(self._piene())
        for chiave, r in self.radio.items():
            r.blockSignals(True)
            r.setAutoExclusive(False)
            r.setChecked(chiave == k)
            r.setAutoExclusive(True)
            r.blockSignals(False)
        self.s_n.setEnabled(bool(k) and cnd.REGOLE_QUADRI[k][1])
        manuale = not k
        self.s_gmin.setEnabled(manuale)
        self.s_gmax.setEnabled(manuale)
        self.s_n.setMaximum(max(n_g, 1))
        if k:
            lo, hi = cnd.regola_intervallo(k, n_g, self.s_n.value())
            for s, x in ((self.s_gmin, lo), (self.s_gmax, hi)):
                s.blockSignals(True)
                s.setValue(x)
                s.blockSignals(False)
        self.l_info.setText(f"{n_g} colonne con numeri. " + (cnd.testo_regola(
            k or "", n_g, self.s_gmin.value(), self.s_gmax.value()) if n_g else "Aggiungi dei numeri a una colonna."))

    # ---------------------------------------------------------------- condizione, archivio, analisi
    def _condizione(self) -> cnd.Condizione | None:
        piene = self._piene()
        if not piene:
            return None
        k = self.c_regola.currentData()
        nome = self.e_nome.text().strip()
        if k:
            c = cnd.quadri(piene, k, self.s_n.value(), nome)
        else:
            lo, hi = sorted((self.s_gmin.value(), self.s_gmax.value()))
            c = cnd.quadri(piene, "tutte", 1, nome)
            c.regola, c.minimo, c.massimo = "", lo, hi
        c.attiva = self.r_attivo.isChecked()
        return c

    def _archivio(self):
        c = self._condizione()
        if c is None or self.ctx is None or not self.ctx.estrazioni:
            QMessageBox.information(self, "Archivio", "Servono almeno una colonna con numeri e un archivio.")
            return
        estr = self.ctx.estrazioni[-300:][::-1]
        C = np.array([sorted(e.numeri) for e in estr], dtype=np.int64)
        quanti = cnd.verificati(C, c.gruppi)
        ok = c.rispetta(C, self.ctx)
        d = QDialog(self)
        d.setWindowTitle("Archivio: le ultime estrazioni e il quadro")
        adatta_schermo(d, 900, 640)
        v = QVBoxLayout(d)
        v.addWidget(QLabel(f"Le ultime {len(estr)} estrazioni: quali gruppi avrebbero verificato e se l'intero quadro "
                           f"sarebbe stato rispettato ({int(ok.sum())} su {len(estr)})."))
        n = len(c.gruppi)
        t = QTableWidget(len(estr), 3 + n)
        t.setHorizontalHeaderLabels(["Data", "Estrazione"] + [f"{i + 1:03d}" for i in range(n)] + ["Quadro"])
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for r, e in enumerate(estr):
            t.setItem(r, 0, QTableWidgetItem(e.data.strftime("%d/%m/%Y")))
            t.setItem(r, 1, QTableWidgetItem(" ".join(map(str, sorted(e.numeri)))))
            for j, gr in enumerate(c.gruppi):
                q = int(np.isin(C[r], gr["numeri"]).sum())
                it = QTableWidgetItem(str(q))
                it.setTextAlignment(Qt.AlignCenter)
                if gr["minimo"] <= q <= gr["massimo"]:
                    it.setBackground(QColor(VERDE_OK))
                t.setItem(r, 2 + j, it)
            it = QTableWidgetItem("sì" if ok[r] else "no")
            it.setTextAlignment(Qt.AlignCenter)
            it.setBackground(QColor(VERDE_OK if ok[r] else "#ffcdd2"))
            t.setItem(r, 2 + n, it)
        t.resizeColumnsToContents()
        v.addWidget(t, 1)
        b = QPushButton("Chiudi")
        b.clicked.connect(d.accept)
        v.addWidget(b)
        d.exec()

    def _analisi(self):
        c = self._condizione()
        if c is None or self.ctx is None or not self.ctx.estrazioni:
            QMessageBox.information(self, "Analisi", "Servono almeno una colonna con numeri e un archivio.")
            return
        an = cnd.analizza_quadri(c.gruppi, self.ctx)
        parti = [f"<h3>Quadro: quanti gruppi verificati per estrazione</h3><p>{html.escape(an.suggerimento)}</p>",
                 "<table border='1' cellpadding='4'><tr><th>Gruppi verificati</th><th>Estrazioni</th>"
                 "<th>% archivio</th></tr>"]
        lo, hi = c.minimo, c.massimo
        for val, usc, pa, _ in an.righe:
            colore = " style='background:#c8e6c9'" if lo <= val <= hi else ""
            parti.append(f"<tr{colore}><td align='center'>{val}</td><td align='center'>{usc}</td>"
                         f"<td align='center'>{pa:.1f}</td></tr>")
        parti.append("</table><h3>Ogni colonna</h3><ul>")
        for i, gr in enumerate(c.gruppi):
            a = cnd.analizza_gruppo(gr["numeri"], self.ctx)
            parti.append(f"<li><b>{i + 1:03d}</b> ({len(gr['numeri'])} numeri): {html.escape(a.suggerimento)}</li>")
        parti.append("</ul>")
        d = QDialog(self)
        d.setWindowTitle("Analisi del quadro sull'archivio")
        adatta_schermo(d, 820, 640)
        v = QVBoxLayout(d)
        tb = QTextBrowser()
        tb.setHtml("".join(parti))
        v.addWidget(tb, 1)
        b = QPushButton("Chiudi")
        b.clicked.connect(d.accept)
        v.addWidget(b)
        d.exec()

    # ---------------------------------------------------------------- salvataggio nei «miei quadri»
    def _salva_quadro(self):
        c = self._condizione()
        if c is None:
            QMessageBox.information(self, "Quadro", "Metti dei numeri in almeno una colonna.")
            return
        if self.arch is None:
            return
        nome, ok = QInputDialog.getText(self, "Salva questo quadro", "Nome:", text=self.e_nome.text() or "")
        if ok and nome.strip():
            cu.aggiungi(self.arch, nome, c)
            self.e_nome.setText(nome.strip())
            QMessageBox.information(self, "Quadro", f"Quadro «{nome.strip()}» salvato in Le mie condizioni.")

    def _carica_quadro(self):
        if self.arch is None:
            return
        voci = cu.carica(self.arch, ("quadri",))
        if not voci:
            QMessageBox.information(self, "Quadro", "Non hai ancora salvato nessun quadro.")
            return
        nomi = [v["nome"] for v in voci]
        nome, ok = QInputDialog.getItem(self, "Carica un mio quadro", "Quadro:", nomi, 0, False)
        if ok:
            c = cu.condizione(voci[nomi.index(nome)])
            self.gruppi = [dict(x) for x in c.gruppi]
            while len(self.gruppi) < COLONNE_INIZIALI:
                self.gruppi.append(self._vuoto())
            self.corrente = 0
            self.e_nome.setText(c.nome)
            i = self.c_regola.findData(c.regola)
            self.c_regola.setCurrentIndex(i if i >= 0 else self.c_regola.count() - 1)
            if c.regola in ("almeno_n", "esattamente_n"):
                self.s_n.setValue(c.minimo)
            elif c.regola == "al_massimo_n":
                self.s_n.setValue(c.massimo)
            self._ricostruisci()
            self._regola()

    def _ok(self):
        if not self._piene():
            QMessageBox.warning(self, "Quadro", "Metti dei numeri in almeno una colonna.")
            return
        self.risultato = self._condizione()
        self.accept()


# ------------------------------------------------------------------ Quadri speciali
class SchedaQuadriSpeciali(QDialog):
    """Quadri speciali: tre quadri sugli archivi (completo, solo vincenti, completo senza vincenti). In ognuno si
    sceglie quanti numeri in comune con le combinazioni di quell'archivio sono ammessi (o non ammessi)."""

    def __init__(self, g, ctx, attuale: cnd.Condizione | None = None, parent=None):
        super().__init__(parent)
        self.g, self.ctx = g, ctx
        self.risultato: cnd.Condizione | None = None
        voci = cnd.voci_speciali_vuote()
        if attuale and attuale.codice == "quadri_speciali":
            for v in attuale.gruppi:
                for x in voci:
                    if x["archivio"] == v.get("archivio"):
                        x.update(v)
        self.setWindowTitle("Quadri speciali")
        adatta_schermo(self, 1100, 760)
        v = QVBoxLayout(self)
        s = QLabel("<b>Quadri speciali</b> – tre quadri sugli archivi. In ognuno scegli quanti numeri in comune "
                   "con le combinazioni di quell'archivio sono <b>ammessi</b> oppure <b>non ammessi</b> nelle "
                   "colonne sviluppate (con «fino a 2» si intendono 0, 1 o 2 numeri in comune).")
        s.setWordWrap(True)
        v.addWidget(s)
        nv = len(ctx.vincenti) if ctx is not None else 0
        ne = len(ctx.estrazioni) if ctx is not None else 0
        v.addWidget(QLabel(f"Archivio: {ne} combinazioni, di cui {nv} vincenti (con il jackpot vinto)."
                           + ("" if nv or g.is_ej else " Per avere le vincenti usa «Aggiorna i vincitori del 6» "
                                                        "nel menu Internet.")))
        self.pannelli = []
        riga = QHBoxLayout()
        for voce in voci:
            box = QGroupBox(cnd.ARCHIVI_SPECIALI[voce["archivio"]])
            bl = QVBoxLayout(box)
            attivo = QCheckBox("Quadro attivo")
            attivo.setChecked(bool(voce["attivo"]))
            bl.addWidget(attivo)
            r1, r2 = QRadioButton("Numeri in comune AMMESSI"), QRadioButton("Numeri in comune NON ammessi")
            (r2 if voce["modo"] == "non_ammessi" else r1).setChecked(True)
            bl.addWidget(r1)
            bl.addWidget(r2)
            cbs = {}
            for q in range(min(2, g.k), g.k + 1):
                cb = QCheckBox("fino a 2" if q == 2 else str(q))
                cb.setChecked(q in voce["valori"])
                bl.addWidget(cb)
                cbs[q] = cb
            b = QPushButton("Mostra l'analisi")
            ris = QLabel()
            ris.setWordWrap(True)
            t = QTableWidget(0, 3)
            t.setHorizontalHeaderLabels(["In comune", "Estrazioni", "% archivio"])
            t.verticalHeader().setVisible(False)
            t.setEditTriggers(QAbstractItemView.NoEditTriggers)
            b.clicked.connect(lambda _=False, a=voce["archivio"], t=t, ris=ris, cbs=cbs: self._analisi(a, t, ris, cbs))
            bl.addWidget(b)
            bl.addWidget(t)
            bl.addWidget(ris)
            riga.addWidget(box)
            self.pannelli.append((voce["archivio"], attivo, r1, cbs))
        v.addLayout(riga, 1)
        h = QHBoxLayout()
        h.addWidget(QLabel("Nome:"))
        self.e_nome = QLineEdit(attuale.nome if attuale else "")
        self.e_nome.setPlaceholderText("facoltativo")
        h.addWidget(self.e_nome, 1)
        box = QGroupBox("Stato")
        sl = QHBoxLayout(box)
        self.r_attivo, self.r_disattivo = QRadioButton("Attivato"), QRadioButton("Disattivato")
        self.r_attivo.setChecked(attuale is None or attuale.attiva)
        self.r_disattivo.setChecked(attuale is not None and not attuale.attiva)
        sl.addWidget(self.r_attivo)
        sl.addWidget(self.r_disattivo)
        h.addWidget(box)
        for testo, f in (("OK", self._ok), ("Annulla", self.reject), ("Aiuto", lambda: apri_aiuto(self, g))):
            b = QPushButton(testo)
            b.clicked.connect(f)
            h.addWidget(b)
        v.addLayout(h)

    def _analisi(self, quale, tabella, ris, cbs):
        if self.ctx is None or not self.ctx.estrazioni:
            return
        a = cnd.analizza_speciale(self.ctx, quale)
        tabella.setRowCount(len(a.righe))
        for r, (val, usc, pa, _) in enumerate(a.righe):
            for c, x in enumerate(("fino a 2" if val == 2 else str(val), str(usc), f"{pa:.1f}")):
                it = QTableWidgetItem(x)
                it.setTextAlignment(Qt.AlignCenter)
                tabella.setItem(r, c, it)
        tabella.resizeColumnsToContents()
        ris.setText(a.suggerimento)

    def _voci(self) -> list[dict]:
        out = []
        for quale, attivo, r1, cbs in self.pannelli:
            out.append({"archivio": quale, "attivo": attivo.isChecked(),
                        "modo": "ammessi" if r1.isChecked() else "non_ammessi",
                        "valori": [q for q, cb in cbs.items() if cb.isChecked()]})
        return out

    def _ok(self):
        voci = self._voci()
        if not any(x["attivo"] and x["valori"] for x in voci):
            QMessageBox.warning(self, "Quadri speciali", "Attiva almeno un quadro e scegli i numeri in comune.")
            return
        c = cnd.quadri_speciali(voci, self.e_nome.text().strip())
        c.attiva = self.r_attivo.isChecked()
        self.risultato = c
        self.accept()


# ------------------------------------------------------------------ Controllo condizioni
class FinestraControllo(QDialog):
    """Controllo condizioni: per ogni condizione attiva di un sistema mostra se lavora davvero o se è inutile
    perché le sue colonne sono già scartate da altre, e quante colonne scarta ciascuna."""
    LIMITE = 400_000

    def __init__(self, g, ctx, sistema, parent=None):
        super().__init__(parent)
        self.g, self.ctx, self.s = g, ctx, sistema
        self.rapporto = None
        self.setWindowTitle("Controllo condizioni")
        adatta_schermo(self, 1200, 760)
        v = QVBoxLayout(self)
        self.l_tot = QLabel()
        self.l_tot.setWordWrap(True)
        v.addWidget(self.l_tot)
        self.t = QTableWidget(0, 7)
        self.t.setHorizontalHeaderLabels(["#", "Condizione", "Stato", "Scarta da sola", "Solo lei", "In più delle "
                                          "precedenti", "Note"])
        self.t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.t.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.t.verticalHeader().setVisible(False)
        v.addWidget(self.t, 3)
        self.dettaglio = QTextBrowser()
        v.addWidget(self.dettaglio, 2)
        h = QHBoxLayout()
        h.addStretch()
        for testo, f in (("Ricalcola", self.calcola), ("Copia il rapporto", self._copia),
                         ("Aiuto", lambda: apri_aiuto(self, g)), ("Chiudi", self.accept)):
            b = QPushButton(testo)
            b.clicked.connect(f)
            h.addWidget(b)
        v.addLayout(h)
        self.t.itemSelectionChanged.connect(self._dettaglio)
        QTimer.singleShot(0, self.calcola)

    def _colonne(self):
        s, k = self.s, self.g.k
        tot = sis.numero_integrale(len(s.numeri), k, len(s.fisse))
        if tot <= self.LIMITE:
            return np.vstack(list(sis.integrale(s.numeri, k, s.fisse))), False, tot
        rng = np.random.default_rng(5)
        fisse = sorted(set(s.fisse))
        resto = np.array(sorted(set(s.numeri) - set(fisse)))
        r = k - len(fisse)
        M = np.argsort(rng.random((self.LIMITE, len(resto))), axis=1)[:, :r]
        C = np.sort(np.hstack([resto[M]] + ([np.tile(fisse, (self.LIMITE, 1))] if fisse else [])), axis=1)
        return C.astype(np.int64), True, tot

    def calcola(self):
        conds = self.s.lista_condizioni()
        self.t.setRowCount(0)
        if not conds:
            self.l_tot.setText("Il sistema non ha condizioni da controllare.")
            return
        if len(self.s.numeri) < self.g.k:
            self.l_tot.setText(f"Scegli prima i numeri del sistema (almeno {self.g.k}).")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            C, campione, tot = self._colonne()
            self.rapporto = cnd.controllo(C, conds, self.ctx, self.s.errori_min, self.s.errori_max, campione)
        finally:
            QApplication.restoreOverrideCursor()
        r = self.rapporto
        perc = r.ammesse / r.totale * 100 if r.totale else 0
        self.l_tot.setText(
            f"<b>Colonne esaminate: {r.totale:,}</b>".replace(",", ".")
            + (f" (campione casuale: l'integrale ne ha {tot:,})".replace(",", ".") if campione else
               " (tutto l'integrale del sistema)")
            + f".<br>Ammesse da tutte le condizioni attive: <b>{r.ammesse:,}</b> ({perc:.1f}%); scartate "
              f"{r.totale - r.ammesse:,}.".replace(",", "."))
        colori = {"operante": VERDE_OK, "inoperante": "#ffcdd2", "assorbita": "#ffe0b2", "disattivata": "#eeeeee"}
        self.t.setRowCount(len(r.righe))
        for i, x in enumerate(r.righe):
            celle = [str(x.indice + 1), x.descrizione, x.stato.upper(), f"{x.escluse:,}".replace(",", "."),
                     f"{x.uniche:,}".replace(",", "."), f"{x.nuove_in_sequenza:,}".replace(",", "."), x.nota]
            for j, testo in enumerate(celle):
                it = QTableWidgetItem(testo)
                if j in (0, 2, 3, 4, 5):
                    it.setTextAlignment(Qt.AlignCenter)
                if j == 2:
                    it.setBackground(QColor(colori[x.stato]))
                self.t.setItem(i, j, it)
        self.t.resizeColumnsToContents()
        self.t.setColumnWidth(1, min(self.t.columnWidth(1), 420))
        if r.righe:
            self.t.selectRow(0)
        self._dettaglio()

    def _dettaglio(self):
        if self.rapporto is None:
            return
        i = self.t.currentRow()
        if not 0 <= i < len(self.rapporto.righe):
            self.dettaglio.setPlainText(cnd.testo_controllo(self.rapporto))
            return
        x = self.rapporto.righe[i]
        parti = [f"<h3>{html.escape(x.descrizione)}</h3><p><b>{x.stato.upper()}</b> – {html.escape(x.nota)}</p>"]
        if x.assorbita_da:
            parti.append("<p>Le sue colonne scartate sono già scartate da:</p><ul>"
                         + "".join(f"<li>{html.escape(a)}</li>" for a in x.assorbita_da) + "</ul>")
        parti.append("<p style='color:#555'><b>Come leggere:</b> «Scarta da sola» = colonne che non rispettano questa "
                     "condizione. «Solo lei» = colonne che tornerebbero ammesse se la togliessi (nessun'altra le "
                     "scarta). «In più delle precedenti» = colonne scartate in aggiunta a quelle delle condizioni "
                     "sopra di lei nell'elenco.</p>")
        self.dettaglio.setHtml("".join(parti))

    def _copia(self):
        if self.rapporto is not None:
            QApplication.clipboard().setText(cnd.testo_controllo(self.rapporto))


# ------------------------------------------------------------------ insieme di numeri personale
class SchedaInsieme(QDialog):
    """Una condizione sua: «quanti numeri della colonna appartengono ai numeri che scelgo io» (da un minimo a un
    massimo), con i gruppi comuni a un clic e l'analisi sull'archivio."""

    def __init__(self, g, ctx: cnd.Contesto | None, attuale: cnd.Condizione | None = None, parent=None):
        super().__init__(parent)
        self.g, self.ctx = g, ctx
        self.risultato: cnd.Condizione | None = None
        self.scelti: set[int] = set(attuale.numeri) if attuale else set()
        self.setWindowTitle("Condizione personale: numeri scelti da me")
        adatta_schermo(self, 980, 760)
        v = QVBoxLayout(self)
        s = QLabel("<b>Numeri scelti da me</b> – scegli i numeri (uno a uno o con i gruppi comuni). La colonna è "
                   "accettata se contiene da un minimo a un massimo di questi numeri.")
        s.setWordWrap(True)
        v.addWidget(s)
        riga = QHBoxLayout()
        riga.addWidget(QLabel("Nome:"))
        self.e_nome = QLineEdit(attuale.nome if attuale else "")
        self.e_nome.setPlaceholderText("per esempio: I miei fortunati")
        riga.addWidget(self.e_nome, 1)
        v.addLayout(riga)
        gl = QGridLayout()
        gl.setSpacing(3)
        self.bottoni = {}
        for n in range(1, g.n + 1):
            b = QPushButton(str(n))
            b.setFixedSize(38, 30)
            b.clicked.connect(lambda _=False, n=n: self._clic(n))
            gl.addWidget(b, (n - 1) // 10, (n - 1) % 10)
            self.bottoni[n] = b
        box = QWidget()
        box.setLayout(gl)
        v.addWidget(box)
        self.barra = BarraInsiemi(g, lambda: self.scelti, self._scrivi, None, self)
        v.addWidget(self.barra)
        self.l_sel = QLabel()
        v.addWidget(self.l_sel)
        riga = QHBoxLayout()
        riga.addWidget(QLabel("Presenti nella colonna da"))
        self.s_min, self.s_max = QSpinBox(), QSpinBox()
        for x in (self.s_min, self.s_max):
            x.setRange(0, g.k)
            x.valueChanged.connect(self._copertura)
        self.s_min.setValue(attuale.minimo if attuale else 1)
        self.s_max.setValue(attuale.massimo if attuale else g.k)
        riga.addWidget(self.s_min)
        riga.addWidget(QLabel("a"))
        riga.addWidget(self.s_max)
        b = QPushButton("Applica il suggerimento")
        b.clicked.connect(self._suggerimento)
        riga.addWidget(b)
        riga.addStretch()
        v.addLayout(riga)
        self.l_an = QLabel()
        self.l_an.setWordWrap(True)
        v.addWidget(self.l_an)
        self.t = QTableWidget(0, 4)
        self.t.setHorizontalHeaderLabels(["Usciti dell'insieme", "Estrazioni", "% archivio", "% atteso dal caso"])
        self.t.verticalHeader().setVisible(False)
        self.t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        v.addWidget(self.t, 1)
        riga = QHBoxLayout()
        riga.addStretch()
        b = QPushButton("Usa questa condizione")
        b.clicked.connect(self._ok)
        riga.addWidget(b)
        b = QPushButton("Annulla")
        b.clicked.connect(self.reject)
        riga.addWidget(b)
        v.addLayout(riga)
        self._colori()

    def _scrivi(self, nuovi):
        self.scelti = set(nuovi)
        self._colori()

    def _clic(self, n):
        self.scelti ^= {n}
        self._colori()

    def _colori(self):
        for n, b in self.bottoni.items():
            b.setStyleSheet(SELEZIONE if n in self.scelti else "")
        self.l_sel.setText(f"Numeri scelti ({len(self.scelti)}): {' '.join(map(str, sorted(self.scelti)))}"
                           if self.scelti else "Clicca i numeri oppure usa i gruppi comuni.")
        for x in (self.s_min, self.s_max):
            x.setMaximum(max(1, min(self.g.k, len(self.scelti))))
        self._analisi()

    def _analisi(self):
        self.t.setRowCount(0)
        if not self.scelti or self.ctx is None or not self.ctx.estrazioni:
            self.l_an.setText("")
            return
        a = cnd.analizza_gruppo(sorted(self.scelti), self.ctx)
        self.an = a
        self.l_an.setText(a.suggerimento)
        self.t.setRowCount(len(a.righe))
        lo, hi = self.s_min.value(), self.s_max.value()
        for r, (val, usc, pa, pc) in enumerate(a.righe):
            for c, x in enumerate((str(val), str(usc), f"{pa:.1f}", f"{pc:.1f}")):
                it = QTableWidgetItem(x)
                it.setTextAlignment(Qt.AlignCenter)
                if lo <= val <= hi:
                    it.setBackground(QColor(VERDE_OK))
                self.t.setItem(r, c, it)
        self.t.resizeColumnsToContents()

    def _copertura(self, *_):
        if hasattr(self, "an"):
            self._analisi()

    def _suggerimento(self):
        if self.scelti and self.ctx is not None and self.ctx.estrazioni:
            a = cnd.analizza_gruppo(sorted(self.scelti), self.ctx)
            self.s_min.setValue(a.copertura[0])
            self.s_max.setValue(a.copertura[1])

    def _ok(self):
        if not self.scelti:
            QMessageBox.warning(self, "Condizione personale", "Scegli almeno un numero.")
            return
        lo, hi = sorted((self.s_min.value(), self.s_max.value()))
        c = cnd.gruppo(sorted(self.scelti), lo, hi)
        c.nome = self.e_nome.text().strip()
        self.risultato = c
        self.accept()


# ------------------------------------------------------------------ Le mie condizioni
def salva_come_mia(parent, arch, c: cnd.Condizione) -> bool:
    nome, ok = QInputDialog.getText(parent, "Salva tra Le mie condizioni", "Nome della condizione:", text=c.nome)
    if ok and nome.strip():
        cu.aggiungi(arch, nome, c)
        return True
    return False


class FinestraMieCondizioni(QDialog):
    """Elenco delle condizioni personali: nuova, modifica, duplica, rinomina, elimina, aggiungi al sistema."""

    def __init__(self, arch, parent=None, usa=None):
        super().__init__(parent)
        self.arch, self.g, self.usa = arch, arch.gioco, usa
        self.setWindowTitle(f"Le mie condizioni – {self.g.nome}")
        adatta_schermo(self, 900, 600)
        v = QVBoxLayout(self)
        s = QLabel("Le condizioni che hai creato tu: si attivano nei sistemi condizionati come tutte le altre. "
                   "Le puoi salvare anche dalle schede delle condizioni (pulsante «Salva come mia condizione»).")
        s.setWordWrap(True)
        v.addWidget(s)
        self.lista = QListWidget()
        self.lista.itemDoubleClicked.connect(lambda *_: self.modifica())
        v.addWidget(self.lista, 1)
        riga = QHBoxLayout()
        b = QPushButton("Nuova")
        m = QMenu(b)
        m.addAction("Numeri scelti da me (insieme)", self._nuova_insieme)
        m.addAction("Quadri (più gruppi con una regola)", self._nuova_quadri)
        m.addAction("Quadri speciali (i tre archivi)", self._nuova_speciali)
        m.addAction("Da una condizione standard (scelgo io i valori)...", self._nuova_standard)
        b.setMenu(m)
        riga.addWidget(b)
        for testo, f in (("Modifica", self.modifica), ("Duplica", self.duplica), ("Rinomina", self.rinomina),
                         ("Elimina", self.elimina)):
            b = QPushButton(testo)
            b.clicked.connect(f)
            riga.addWidget(b)
        riga.addStretch()
        if usa is not None:
            b = QPushButton("Aggiungi al sistema")
            b.clicked.connect(self.aggiungi_al_sistema)
            riga.addWidget(b)
        b = QPushButton("Chiudi")
        b.clicked.connect(self.accept)
        riga.addWidget(b)
        v.addLayout(riga)
        self.aggiorna()

    def _ctx(self) -> cnd.Contesto:
        return sis.contesto_da_archivio(self.arch)

    def aggiorna(self):
        self.lista.clear()
        for voce in cu.carica(self.arch):
            c = cu.condizione(voce)
            it = QListWidgetItem(f"{voce['nome']}  –  {c.descrivi().split(': ', 1)[-1][:150]}")
            it.setData(Qt.UserRole, voce["id"])
            self.lista.addItem(it)
        if not self.lista.count():
            self.lista.addItem("(nessuna: premi «Nuova» per crearne una)")

    def _voce(self) -> dict | None:
        it = self.lista.currentItem()
        if it is None or it.data(Qt.UserRole) is None:
            return None
        return next((v for v in cu.carica(self.arch) if v["id"] == it.data(Qt.UserRole)), None)

    def _salva(self, c: cnd.Condizione, nome: str = ""):
        nome = nome or c.nome
        if not nome:
            nome, ok = QInputDialog.getText(self, "Nome", "Nome della condizione:")
            if not ok or not nome.strip():
                return
        cu.aggiungi(self.arch, nome, c)
        self.aggiorna()

    def _nuova_insieme(self):
        d = SchedaInsieme(self.g, self._ctx(), None, self)
        if d.exec() and d.risultato:
            self._salva(d.risultato)

    def _nuova_quadri(self):
        d = SchedaQuadri(self.g, self._ctx(), [], None, self, self.arch)
        if d.exec() and d.risultato:
            self._salva(d.risultato)

    def _nuova_speciali(self):
        d = SchedaQuadriSpeciali(self.g, self._ctx(), None, self)
        if d.exec() and d.risultato:
            self._salva(d.risultato)

    def _nuova_standard(self):
        tipi = cnd.tipi_del_gioco(self.g)
        nomi = [t.nome for t in tipi]
        nome, ok = QInputDialog.getItem(self, "Condizione standard", "Su quale misura?", nomi, 0, False)
        if ok:
            d = SchedaCondizione(self._ctx(), tipi[nomi.index(nome)].codice, None, self)
            if d.exec() and d.risultato:
                self._salva(d.risultato)

    def modifica(self):
        voce = self._voce()
        if voce is None:
            return
        c = cu.condizione(voce)
        ctx = self._ctx()
        if c.codice == "quadri":
            d = SchedaQuadri(self.g, ctx, [], c, self, self.arch)
        elif c.codice == "quadri_speciali":
            d = SchedaQuadriSpeciali(self.g, ctx, c, self)
        elif c.codice == "gruppo":
            d = SchedaInsieme(self.g, ctx, c, self)
        elif c.tipo is not None:
            d = SchedaCondizione(ctx, c.codice, c, self)
        else:
            QMessageBox.information(self, "Le mie condizioni", "Questa condizione si modifica dal sistema.")
            return
        if d.exec() and d.risultato:
            d.risultato.nome = voce["nome"]
            cu.aggiungi(self.arch, voce["nome"], d.risultato)
            self.aggiorna()

    def duplica(self):
        voce = self._voce()
        if voce:
            cu.duplica(self.arch, voce["id"])
            self.aggiorna()

    def rinomina(self):
        voce = self._voce()
        if voce:
            nome, ok = QInputDialog.getText(self, "Rinomina", "Nuovo nome:", text=voce["nome"])
            if ok and nome.strip():
                cu.rinomina(self.arch, voce["id"], nome)
                self.aggiorna()

    def elimina(self):
        voce = self._voce()
        if voce and QMessageBox.question(self, "Elimina", f"Eliminare «{voce['nome']}»?") == QMessageBox.Yes:
            cu.elimina(self.arch, voce["id"])
            self.aggiorna()

    def aggiungi_al_sistema(self):
        voce = self._voce()
        if voce and self.usa:
            self.usa(cu.condizione(voce))
