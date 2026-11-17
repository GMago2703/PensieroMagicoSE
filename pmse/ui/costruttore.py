"""Costruttore di analisi personalizzate: semplice "ricetta" fatta di
misure pesate + filtri sui numeri."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton, QSpinBox,
                               QSplitter, QTableWidget, QVBoxLayout, QWidget)

from ..core import personalizzate as pz
from ..core.db import Archivio
from .analisi import riempi_tabella
from .griglia import Griglia90

AIUTO = (
    "<b>Come funziona</b><br>"
    "1. Dai un nome all'analisi e scegli il periodo (ultime N estrazioni, 0 = tutto l'archivio).<br>"
    "2. Aggiungi uno o più <b>ingredienti</b>: ogni ingrediente è una misura calcolata per ognuno dei 90 "
    "numeri (frequenza, ritardo, numeri successivi...). Il <b>peso</b> dice quanto conta: "
    "con peso negativo vengono favoriti i valori bassi (es. ritardo -1 = preferisci i numeri usciti da poco).<br>"
    "3. Con i <b>filtri</b> scegli quali numeri sono ammessi.<br>"
    "4. Premi <b>Prova</b> per vedere il risultato, <b>Salva</b> per aggiungerla al menu Analisi.<br>"
    "Il punteggio finale di ogni numero è la somma dei pesi per le misure riportate in scala 0-1. "
    "Le analisi salvate si possono usare in Magico Pensiero con un loro peso.")


class RigaIngrediente(QWidget):
    def __init__(self, ing: pz.Ingrediente, rimuovi):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        self.c_misura = QComboBox()
        for m in pz.MISURE.values():
            self.c_misura.addItem(m.nome, m.codice)
        self.c_misura.setCurrentIndex(max(self.c_misura.findData(ing.misura), 0))
        self.l_param = QLabel()
        self.s_param = QSpinBox()
        self.s_peso = QDoubleSpinBox()
        self.s_peso.setRange(-10, 10)
        self.s_peso.setSingleStep(0.1)
        self.s_peso.setValue(ing.peso)
        b = QPushButton("✖")
        b.setFixedWidth(28)
        b.setToolTip("Togli questo ingrediente")
        b.clicked.connect(lambda: rimuovi(self))
        h.addWidget(self.c_misura, 3)
        h.addWidget(self.l_param)
        h.addWidget(self.s_param)
        h.addWidget(QLabel("peso"))
        h.addWidget(self.s_peso)
        h.addWidget(b)
        self.c_misura.currentIndexChanged.connect(self._misura_cambiata)
        self._misura_cambiata(param=ing.param)

    def _misura_cambiata(self, *_, param: int | None = None):
        m = pz.MISURE[self.c_misura.currentData()]
        self.c_misura.setToolTip(m.descrizione)
        attivo = m.param_etichetta is not None
        self.l_param.setVisible(attivo)
        self.s_param.setVisible(attivo)
        if attivo:
            self.l_param.setText(m.param_etichetta)
            self.s_param.setRange(m.param_min, m.param_max)
            self.s_param.setValue(param if param else m.param_predefinito)

    def valore(self) -> pz.Ingrediente:
        m = pz.MISURE[self.c_misura.currentData()]
        return pz.Ingrediente(m.codice, self.s_param.value() if m.param_etichetta else 0, self.s_peso.value())


class FinestraCostruttore(QDialog):
    def __init__(self, archivio: Archivio, parent=None):
        super().__init__(parent)
        self.arch = archivio
        self.ricette = pz.carica(archivio)
        self.setWindowTitle("Costruttore di analisi personalizzate")
        self.resize(1250, 760)
        div = QSplitter(self)
        lay = QVBoxLayout(self)
        lay.addWidget(div)

        # --- elenco ricette
        sx = QWidget()
        sv = QVBoxLayout(sx)
        sv.addWidget(QLabel("<b>Analisi salvate</b>"))
        self.lista = QListWidget()
        self.lista.currentRowChanged.connect(self._scegli)
        sv.addWidget(self.lista, 1)
        for testo, f in (("➕ Nuova", self.nuova), ("⧉ Duplica", self.duplica), ("🗑 Elimina", self.elimina)):
            b = QPushButton(testo)
            b.clicked.connect(f)
            sv.addWidget(b)
        div.addWidget(sx)

        # --- editor
        cx = QWidget()
        cv = QVBoxLayout(cx)
        aiuto = QLabel(AIUTO)
        aiuto.setWordWrap(True)
        aiuto.setStyleSheet("background:#fffde7; padding:6px; border:1px solid #e0d080;")
        cv.addWidget(aiuto)
        f = QFormLayout()
        self.e_nome = QLineEdit()
        self.e_desc = QLineEdit()
        self.s_ultime = QSpinBox()
        self.s_ultime.setRange(0, 100000)
        self.s_ultime.setSpecialValueText("tutto l'archivio")
        f.addRow("Nome", self.e_nome)
        f.addRow("Descrizione", self.e_desc)
        f.addRow("Periodo: ultime N estrazioni", self.s_ultime)
        cv.addLayout(f)

        g_ing = QGroupBox("Ingredienti (misure pesate)")
        self.v_ing = QVBoxLayout(g_ing)
        b_agg = QPushButton("➕ Aggiungi ingrediente")
        b_agg.clicked.connect(lambda: self._aggiungi_ing(pz.Ingrediente("frequenza")))
        self.v_ing.addWidget(b_agg)
        cv.addWidget(g_ing)
        self.righe_ing: list[RigaIngrediente] = []

        g_fil = QGroupBox("Filtri sui numeri")
        gf = QGridLayout(g_fil)
        self.c_parita = QComboBox()
        self.c_parita.addItems(["Tutti", "Solo pari", "Solo dispari"])
        self.s_da = QSpinBox()
        self.s_da.setRange(1, 90)
        self.s_a = QSpinBox()
        self.s_a.setRange(1, 90)
        self.s_a.setValue(90)
        gf.addWidget(QLabel("Parità"), 0, 0)
        gf.addWidget(self.c_parita, 0, 1)
        gf.addWidget(QLabel("Numeri da"), 0, 2)
        gf.addWidget(self.s_da, 0, 3)
        gf.addWidget(QLabel("a"), 0, 4)
        gf.addWidget(self.s_a, 0, 5)
        gf.addWidget(QLabel("Decine (nessuna = tutte)"), 1, 0)
        hd = QHBoxLayout()
        self.ck_decine = []
        for d in range(1, 10):
            c = QCheckBox(f"{(d - 1) * 10 + 1}-{d * 10}")
            self.ck_decine.append(c)
            hd.addWidget(c)
        gf.addLayout(hd, 1, 1, 1, 5)
        gf.addWidget(QLabel("Finali (nessuno = tutti)"), 2, 0)
        hf = QHBoxLayout()
        self.ck_finali = []
        for k in range(10):
            c = QCheckBox(str(k))
            self.ck_finali.append(c)
            hf.addWidget(c)
        gf.addLayout(hf, 2, 1, 1, 5)
        self.s_escl = QSpinBox()
        self.s_escl.setRange(0, 1000)
        self.s_escl.setSpecialValueText("no")
        self.s_solo = QSpinBox()
        self.s_solo.setRange(0, 1000)
        self.s_solo.setSpecialValueText("no")
        gf.addWidget(QLabel("Escludi i numeri usciti nelle ultime"), 3, 0)
        gf.addWidget(self.s_escl, 3, 1)
        gf.addWidget(QLabel("Ammetti solo i numeri usciti nelle ultime"), 3, 2, 1, 2)
        gf.addWidget(self.s_solo, 3, 4)
        cv.addWidget(g_fil)

        hb = QHBoxLayout()
        b_prova = QPushButton("▶ Prova")
        b_prova.clicked.connect(self.prova)
        b_salva = QPushButton("💾 Salva")
        b_salva.clicked.connect(self.salva)
        b_chiudi = QPushButton("Chiudi")
        b_chiudi.clicked.connect(self.accept)
        hb.addWidget(b_prova)
        hb.addWidget(b_salva)
        hb.addStretch()
        hb.addWidget(b_chiudi)
        cv.addLayout(hb)
        cv.addStretch()
        div.addWidget(cx)

        # --- anteprima
        dx = QWidget()
        dv = QVBoxLayout(dx)
        dv.addWidget(QLabel("<b>Anteprima del risultato</b>"))
        self.griglia = Griglia90(selezionabile=False)
        self.griglia.setFixedSize(330, 260)
        dv.addWidget(self.griglia)
        self.tab = QTableWidget()
        self.tab.verticalHeader().setVisible(False)
        dv.addWidget(self.tab, 1)
        self.l_nota = QLabel()
        self.l_nota.setWordWrap(True)
        dv.addWidget(self.l_nota)
        div.addWidget(dx)
        div.setSizes([200, 640, 400])

        self._ricarica_lista()
        if self.ricette:
            self.lista.setCurrentRow(0)
        else:
            self._mostra(pz.esempio())

    # ------------------------------------------------------------ elenco
    def _ricarica_lista(self, seleziona: str | None = None):
        self.lista.blockSignals(True)
        self.lista.clear()
        for r in self.ricette:
            self.lista.addItem(r.nome)
        self.lista.blockSignals(False)
        if seleziona:
            for i, r in enumerate(self.ricette):
                if r.nome == seleziona:
                    self.lista.setCurrentRow(i)

    def _scegli(self, i: int):
        if 0 <= i < len(self.ricette):
            self._mostra(self.ricette[i])

    def nuova(self):
        self.lista.clearSelection()
        self._mostra(pz.Ricetta("Nuova analisi", ingredienti=[pz.Ingrediente("frequenza")]))
        self.e_nome.setFocus()
        self.e_nome.selectAll()

    def duplica(self):
        r = self._leggi()
        r.nome += " (copia)"
        self._mostra(r)

    def elimina(self):
        i = self.lista.currentRow()
        if i < 0:
            return
        if QMessageBox.question(self, "Elimina", f"Eliminare l'analisi «{self.ricette[i].nome}»?") \
                != QMessageBox.Yes:
            return
        del self.ricette[i]
        pz.salva_tutte(self.arch, self.ricette)
        self._ricarica_lista()
        self.nuova()

    # ------------------------------------------------------------- editor
    def _aggiungi_ing(self, ing: pz.Ingrediente):
        r = RigaIngrediente(ing, self._togli_ing)
        self.righe_ing.append(r)
        self.v_ing.insertWidget(self.v_ing.count() - 1, r)

    def _togli_ing(self, riga):
        self.righe_ing.remove(riga)
        riga.setParent(None)
        riga.deleteLater()

    def _mostra(self, r: pz.Ricetta):
        self.e_nome.setText(r.nome)
        self.e_desc.setText(r.descrizione)
        self.s_ultime.setValue(r.ultime)
        for riga in list(self.righe_ing):
            self._togli_ing(riga)
        for ing in r.ingredienti:
            self._aggiungi_ing(ing)
        fl = r.filtri
        self.c_parita.setCurrentIndex(fl.parita)
        self.s_da.setValue(fl.da)
        self.s_a.setValue(fl.a)
        for d, c in enumerate(self.ck_decine, start=1):
            c.setChecked(d in fl.decine)
        for k, c in enumerate(self.ck_finali):
            c.setChecked(k in fl.finali)
        self.s_escl.setValue(fl.escludi_usciti_ultime)
        self.s_solo.setValue(fl.solo_usciti_ultime)
        self.prova()

    def _leggi(self) -> pz.Ricetta:
        fl = pz.Filtri(
            parita=self.c_parita.currentIndex(), da=self.s_da.value(), a=self.s_a.value(),
            decine=[d for d, c in enumerate(self.ck_decine, start=1) if c.isChecked()],
            finali=[k for k, c in enumerate(self.ck_finali) if c.isChecked()],
            escludi_usciti_ultime=self.s_escl.value(), solo_usciti_ultime=self.s_solo.value())
        return pz.Ricetta(self.e_nome.text().strip() or "Senza nome", self.e_desc.text().strip(),
                          self.s_ultime.value(), [r.valore() for r in self.righe_ing], fl)

    def prova(self):
        r = self._leggi()
        storico = self.arch.sestine()
        if not storico:
            self.l_nota.setText("Archivio vuoto.")
            return
        if not r.ingredienti:
            self.l_nota.setText("Aggiungi almeno un ingrediente.")
            return
        ris = pz.esegui(r, storico)
        riempi_tabella(self.tab, ris.colonne, ris.righe, ris.numeri_riga)
        self.griglia.mostra_punteggi(ris.punteggi)
        self.l_nota.setText(ris.nota)

    def salva(self):
        r = self._leggi()
        if not r.ingredienti:
            QMessageBox.warning(self, "Salva", "Aggiungi almeno un ingrediente.")
            return
        esistente = [i for i, x in enumerate(self.ricette) if x.nome == r.nome]
        if esistente:
            if QMessageBox.question(self, "Salva", f"Esiste già un'analisi «{r.nome}». Sostituirla?") \
                    != QMessageBox.Yes:
                return
            self.ricette[esistente[0]] = r
        else:
            self.ricette.append(r)
        pz.salva_tutte(self.arch, self.ricette)
        self._ricarica_lista(r.nome)
        QMessageBox.information(self, "Salva", f"Analisi «{r.nome}» salvata: la trovi nel menu Analisi.")
