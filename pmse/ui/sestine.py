"""Le mie sestine: confronto con l'archivio e ricerca di sestine con caratteristiche date."""
from __future__ import annotations

import json
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton, QSpinBox,
                               QSplitter, QTableWidget, QTabWidget, QVBoxLayout, QWidget)

from ..core import personalizzate, sestine as cs
from ..core.db import Archivio
from .analisi import numeri_selezionati, riempi_tabella
from .griglia import Griglia90
from .schermo import adatta_schermo

CHIAVE = "mie_sestine"


def colonne(g) -> list[str]:
    volte = [f"Volte {p}" for p in range(2, g.k)]
    extra = [] if g.is_ej else ["5+Jolly"]
    return [g.C(), "Già uscita", "Max punti", *volte, *extra, "Ultima volta ≥3", "Estrazioni da ≥3", "Somma",
            "Pari", "Alti", "Consecutivi", "Decine", "Sequenze"]


def leggi_sestina(testo: str, g=None) -> list[int] | None:
    from ..core.gioco import SE
    g = g or SE
    nums = [int(x) for x in re.findall(r"\d+", testo)]
    if len(nums) != g.k or len(set(nums)) != g.k or any(n < 1 or n > g.n for n in nums):
        return None
    return sorted(nums)


def riga_confronto(c: cs.Confronto, g=None) -> list:
    from ..core.gioco import SE
    g = g or SE
    k = c.caratteristiche
    return [" ".join(f"{n:2d}" for n in c.sestina), "SÌ" if c.gia_uscita else "no", c.max_punti,
            *[c.distribuzione.get(p, 0) for p in range(2, g.k)], *([] if g.is_ej else [c.cinque_piu_jolly]),
            c.ultima_almeno3.strftime("%d/%m/%Y") if c.ultima_almeno3 else "mai", c.ritardo_almeno3,
            k["somma"], k["pari"], k["alti"], k["consecutivi"], k["decine_diverse"], k["sequenze"]]


class FinestraSestine(QDialog):
    def __init__(self, archivio: Archivio, selezione_home: list[int] | None = None, parent=None):
        super().__init__(parent)
        self.arch = archivio
        self.selezione_home = sorted(selezione_home or [])
        self.g = g = archivio.gioco
        self.COLONNE = colonne(g)
        self.setWindowTitle(f"Le mie {g.nome_comb_pl} ({g.nome}) – confronto e ricerca")
        adatta_schermo(self, 1250, 720)
        self.indice = cs.IndiceArchivio(archivio.sestine())
        v = QVBoxLayout(self)
        div = QSplitter()
        v.addWidget(div)
        self.schede = QTabWidget()
        self.schede.addTab(self._scheda_confronto(), f"Confronta le mie {g.nome_comb_pl} con l'archivio")
        self.schede.addTab(self._scheda_ricerca(), f"Cerca {g.nome_comb_pl} con caratteristiche")
        div.addWidget(self.schede)
        dx = QWidget()
        dv = QVBoxLayout(dx)
        self.griglia = Griglia90(selezionabile=False, n=g.n)
        self.griglia.setFixedSize(330, 29 * g.decine)
        dv.addWidget(self.griglia)
        self.l_dett = QLabel(f"Fai clic su una {g.nome_comb} per vederne i dettagli.")
        self.l_dett.setWordWrap(True)
        self.l_dett.setTextInteractionFlags(Qt.TextSelectableByMouse)
        dv.addWidget(self.l_dett)
        dv.addStretch()
        div.addWidget(dx)
        div.setSizes([880, 350])
        self._carica()

    # ------------------------------------------------------------ confronto
    def _scheda_confronto(self):
        w = QWidget()
        v = QVBoxLayout(w)
        h = QHBoxLayout()
        self.e_nuova = QLineEdit()
        self.e_nuova.setPlaceholderText("Scrivi 5 numeri, es. 5 18 27 44 49" if self.g.is_ej
                                        else "Scrivi 6 numeri, es. 5 18 27 44 63 81")
        self.e_nuova.returnPressed.connect(self._aggiungi_testo)
        h.addWidget(self.e_nuova, 1)
        for testo, f in (("➕ Aggiungi", self._aggiungi_testo),
                         ("➕ Dai numeri selezionati nella home", self._aggiungi_home),
                         ("📂 Da file...", self._da_file)):
            b = QPushButton(testo)
            b.clicked.connect(f)
            h.addWidget(b)
        v.addLayout(h)
        h2 = QHBoxLayout()
        self.lista = QListWidget()
        self.lista.setMaximumWidth(210)
        self.lista.setSelectionMode(QListWidget.ExtendedSelection)
        self.lista.itemSelectionChanged.connect(self._lista_scelta)
        h2.addWidget(self.lista)
        self.tab_c = QTableWidget()
        self.tab_c.verticalHeader().setVisible(False)
        self.tab_c.setSelectionBehavior(QTableWidget.SelectRows)
        self.tab_c.itemSelectionChanged.connect(lambda: self._dettaglio(self.tab_c))
        h2.addWidget(self.tab_c, 1)
        v.addLayout(h2, 1)
        h3 = QHBoxLayout()
        for testo, f in (("🗑 Togli selezionate", self._togli), ("Svuota elenco", self._svuota),
                         ("▶ Confronta con l'archivio", self.confronta)):
            b = QPushButton(testo)
            b.clicked.connect(f)
            h3.addWidget(b)
        h3.addStretch()
        v.addLayout(h3)
        v.addWidget(QLabel("«Max punti» = il massimo dei numeri in comune con una qualunque estrazione passata. "
                           "«Volte 3» = in quante estrazioni avrebbe fatto 3 punti, ecc."))
        return w

    def _carica(self):
        try:
            self.mie = [s for s in json.loads(self.arch.leggi_impostazione(CHIAVE, "[]") or "[]")]
        except ValueError:
            self.mie = []
        self._aggiorna_lista()
        self.confronta()

    def _salva(self):
        self.arch.scrivi_impostazione(CHIAVE, json.dumps(self.mie))

    def _aggiorna_lista(self):
        self.lista.clear()
        for s in self.mie:
            self.lista.addItem(" ".join(f"{n:2d}" for n in s))

    def aggiungi(self, nuove: list[list[int]]):
        aggiunte = 0
        for s in nuove:
            if s not in self.mie:
                self.mie.append(s)
                aggiunte += 1
        self._salva()
        self._aggiorna_lista()
        self.confronta()
        return aggiunte

    def _aggiungi_testo(self):
        s = leggi_sestina(self.e_nuova.text(), self.g)
        if not s:
            QMessageBox.warning(self, self.g.C(), f"Servono {self.g.k} numeri diversi da 1 a {self.g.n}.")
            return
        self.aggiungi([s])
        self.e_nuova.clear()

    def _aggiungi_home(self):
        if len(self.selezione_home) != self.g.k:
            QMessageBox.information(self, self.g.C(), f"Seleziona esattamente {self.g.k} numeri nella tabella "
                                                       "della home "
                                                     f"(ora ne sono selezionati {len(self.selezione_home)}).")
            return
        self.aggiungi([self.selezione_home])

    def _da_file(self):
        p, _ = QFileDialog.getOpenFileName(self, f"File di {self.g.nome_comb_pl} (una per riga)", "",
                                           "Testo (*.txt *.csv)")
        if not p:
            return
        with open(p, encoding="utf-8", errors="replace") as f:
            nuove = [s for s in (leggi_sestina(r, self.g) for r in f) if s]
        n = self.aggiungi(nuove)
        QMessageBox.information(self, "Importazione", f"{self.g.C(plurale=True)} aggiunte: {n}")

    def _togli(self):
        righe = sorted({i.row() for i in self.lista.selectedIndexes()}, reverse=True)
        for r in righe:
            del self.mie[r]
        self._salva()
        self._aggiorna_lista()
        self.confronta()

    def _svuota(self):
        if self.mie and QMessageBox.question(self, "Svuota", f"Togliere tutte le {self.g.nome_comb_pl} dall'elenco?") \
                == QMessageBox.Yes:
            self.mie = []
            self._salva()
            self._aggiorna_lista()
            self.confronta()

    def _lista_scelta(self):
        sel = {i.row() for i in self.lista.selectedIndexes()}
        nums = set()
        for r in sel:
            nums.update(self.mie[r])
        if nums:
            self.griglia.evidenzia(nums)

    def confronta(self):
        conf = [self.indice.confronta(s) for s in self.mie]
        self.confronti = {tuple(c.sestina): c for c in conf}
        riempi_tabella(self.tab_c, self.COLONNE, [riga_confronto(c, self.g) for c in conf],
                       [c.sestina for c in conf])

    def _dettaglio(self, tab):
        nums = numeri_selezionati(tab)
        if not nums:
            return
        self.griglia.evidenzia(nums)
        righe = {i.row() for i in tab.selectedItems()}
        if len(righe) != 1:
            self.l_dett.setText(f"{len(righe)} {self.g.nome_comb_pl} selezionate.")
            return
        s = sorted(tab.item(next(iter(righe)), 0).data(Qt.UserRole + 1))
        c = self.confronti.get(tuple(s)) or self.indice.confronta(s)
        k = c.caratteristiche
        date_max = ", ".join(d.strftime("%d/%m/%Y") for d in c.date_max) or "-"
        self.l_dett.setText(
            f"<b>{' '.join(map(str, c.sestina))}</b><br>"
            f"{'<b>GIÀ USCITA come combinazione vincente!</b><br>' if c.gia_uscita else ''}"
            f"Massimo {c.max_punti} numeri in comune con un'estrazione (ultime volte: {date_max})<br>"
            f"Distribuzione punti sull'archivio: " +
            ", ".join(f"{p}: {c.distribuzione.get(p, 0)}" for p in range(7)) + "<br>"
            f"Somma {k['somma']}, pari {k['pari']}, alti {k['alti']}, consecutivi {k['consecutivi']}, "
            f"decine diverse {k['decine_diverse']}, finali diversi {k['finali_diversi']}, sequenze {k['sequenze']}")

    # -------------------------------------------------------------- ricerca
    def _scheda_ricerca(self):
        w = QWidget()
        v = QVBoxLayout(w)
        g = QGroupBox("Caratteristiche richieste")
        gl = QGridLayout(g)

        def spin(lo, hi, val):
            s = QSpinBox()
            s.setRange(lo, hi)
            s.setValue(val)
            return s

        self.c_pool = QComboBox()
        self.c_pool.addItems([f"Tutti i {self.g.n} numeri", "Solo i numeri selezionati nella home"])
        self.e_obbl = QLineEdit()
        self.e_obbl.setPlaceholderText("es. 7 44")
        self.e_escl = QLineEdit()
        self.e_escl.setPlaceholderText("es. 13 40")
        self.ck_mai = QCheckBox("Mai uscita come combinazione vincente")
        self.ck_mai.setChecked(True)
        K, N = self.g.k, self.g.n
        smin, smax = K * (K + 1) // 2, sum(range(N - K + 1, N + 1))
        self.s_maxp = spin(0, K, 3)
        self.s_minp = spin(0, K, 0)
        self.s_smin, self.s_smax = spin(smin, smax, smin), spin(smin, smax, smax)
        self.s_pmin, self.s_pmax = spin(0, K, 0), spin(0, K, K)
        self.s_amin, self.s_amax = spin(0, K, 0), spin(0, K, K)
        self.s_cons = spin(0, K - 1, K - 1)
        self.s_dec = spin(1, K, K)
        self.s_comuni = spin(0, K - 1, min(3, K - 1))
        self.s_quante = spin(1, 500, 10)
        self.c_pesi = QComboBox()
        self.c_pesi.addItem("Nessuno (tutti i numeri hanno la stessa probabilità)", None)
        for d in personalizzate.tutte_le_analisi(self.arch).values():
            self.c_pesi.addItem("Punteggi di: " + d.nome, d.codice)
        r = 0
        for etichetta, wdg in (("Numeri da usare", self.c_pool), ("Numeri obbligatori", self.e_obbl),
                               ("Numeri esclusi", self.e_escl)):
            gl.addWidget(QLabel(etichetta), r, 0)
            gl.addWidget(wdg, r, 1, 1, 3)
            r += 1
        gl.addWidget(self.ck_mai, r, 0, 1, 2)
        b_lim = QPushButton("Usa i limiti di somiglianza consigliati dall'analisi")
        b_lim.clicked.connect(self._limiti_consigliati)
        gl.addWidget(b_lim, r, 2, 1, 2)
        r += 1
        coppie = [("Al massimo questi numeri in comune con QUALSIASI estrazione passata", self.s_maxp, None),
                  ("Almeno questi numeri in comune con ALMENO UNA estrazione passata", self.s_minp, None),
                  ("Somma da / a", self.s_smin, self.s_smax),
                  ("Numeri pari da / a", self.s_pmin, self.s_pmax),
                  (f"Numeri alti ({self.g.soglia_alti + 1}-{self.g.n}) da / a", self.s_amin, self.s_amax),
                  ("Coppie consecutive al massimo", self.s_cons, None),
                  ("Numeri della stessa decina al massimo", self.s_dec, None),
                  (f"Numeri in comune tra le {self.g.nome_comb_pl} trovate al massimo", self.s_comuni, None),
                  (f"Quante {self.g.nome_comb_pl} trovare", self.s_quante, None)]
        for etichetta, a, b in coppie:
            gl.addWidget(QLabel(etichetta), r, 0)
            gl.addWidget(a, r, 1)
            if b:
                gl.addWidget(b, r, 2)
            r += 1
        gl.addWidget(QLabel("Probabilità dei numeri pesata con"), r, 0)
        gl.addWidget(self.c_pesi, r, 1, 1, 3)
        v.addWidget(g)
        h = QHBoxLayout()
        b = QPushButton("🔎 Cerca")
        b.clicked.connect(self.cerca)
        b2 = QPushButton(f"➕ Aggiungi le selezionate alle mie {self.g.nome_comb_pl}")
        b2.clicked.connect(self._aggiungi_trovate)
        h.addWidget(b)
        h.addWidget(b2)
        self.l_esito = QLabel()
        h.addWidget(self.l_esito, 1)
        v.addLayout(h)
        self.tab_r = QTableWidget()
        self.tab_r.verticalHeader().setVisible(False)
        self.tab_r.setSelectionBehavior(QTableWidget.SelectRows)
        self.tab_r.itemSelectionChanged.connect(lambda: self._dettaglio(self.tab_r))
        v.addWidget(self.tab_r, 1)
        return w

    def _limiti_consigliati(self):
        from ..core.analisi import limiti_consigliati, massimi_in_comune
        if len(self.indice.storico) < 30:
            return
        lo, hi = limiti_consigliati(massimi_in_comune(self.indice.storico, 500), 90)
        self.s_minp.setValue(lo)
        self.s_maxp.setValue(hi)
        self.l_esito.setText(f"Limiti consigliati: da {lo} a {hi} numeri in comune con l'archivio.")

    def cerca(self):
        nums = lambda t: [int(x) for x in re.findall(r"\d+", t) if 1 <= int(x) <= self.g.n]   # noqa: E731
        pool = self.selezione_home if self.c_pool.currentIndex() == 1 else list(range(1, self.g.n + 1))
        pool = [n for n in pool if n not in set(nums(self.e_escl.text()))]
        if len(set(pool) | set(nums(self.e_obbl.text()))) < self.g.k:
            QMessageBox.warning(self, "Ricerca", f"Servono almeno {self.g.k} numeri disponibili "
                                                 "(seleziona più numeri nella home o togli esclusioni).")
            return
        crit = cs.Criteri(
            pool=pool, obbligatori=nums(self.e_obbl.text())[:6], mai_uscita=self.ck_mai.isChecked(),
            max_punti_archivio=self.s_maxp.value(), min_punti_archivio=self.s_minp.value(),
            somma_min=self.s_smin.value(), somma_max=self.s_smax.value(),
            pari_min=self.s_pmin.value(), pari_max=self.s_pmax.value(),
            alti_min=self.s_amin.value(), alti_max=self.s_amax.value(),
            consecutivi_max=self.s_cons.value(), max_stessa_decina=self.s_dec.value(),
            max_comuni_tra_risultati=self.s_comuni.value())
        pesi = None
        codice = self.c_pesi.currentData()
        if codice:
            d = personalizzate.tutte_le_analisi(self.arch)[codice]
            if self.indice.storico:
                pesi = d.funzione(self.indice.storico).punteggi or None
                if pesi:
                    lo = min(pesi.values())
                    pesi = {k: v - lo + 0.01 for k, v in pesi.items()}
        trovate, provate = cs.cerca(self.indice, crit, self.s_quante.value(), pesi=pesi)
        conf = [self.indice.confronta(s) for s in trovate]
        self.confronti = {**getattr(self, "confronti", {}), **{tuple(c.sestina): c for c in conf}}
        riempi_tabella(self.tab_r, self.COLONNE, [riga_confronto(c, self.g) for c in conf],
                       [c.sestina for c in conf])
        self.l_esito.setText(f"Trovate {len(trovate)} {self.g.nome_comb_pl} su {provate:,} provate."
                             .replace(",", ".")
                             + ("" if len(trovate) == self.s_quante.value() else
                                "  Criteri molto restrittivi: prova ad allentarli."))

    def _aggiungi_trovate(self):
        righe = {i.row() for i in self.tab_r.selectedItems()}
        nuove = [sorted(self.tab_r.item(r, 0).data(Qt.UserRole + 1)) for r in righe]
        if not nuove:
            QMessageBox.information(self, "Aggiungi", f"Seleziona prima una o più {self.g.nome_comb_pl} nella "
                                                      "tabella.")
            return
        n = self.aggiungi(nuove)
        self.schede.setCurrentIndex(0)
        QMessageBox.information(self, "Aggiungi", f"{self.g.C(plurale=True)} aggiunte: {n}")
