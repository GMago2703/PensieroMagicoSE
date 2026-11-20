"""Condizioni scelte dall'utente: Quadri (più gruppi di numeri con una regola), insiemi di numeri personali e la
raccolta «Le mie condizioni» (salvare, caricare, duplicare, eliminare, aggiungere ai sistemi)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QGridLayout,
                               QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu,
                               QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

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
        self.scrivi((set(self.leggi()) | nuovi) if self.cb_somma.isChecked() else nuovi)
        self.nome_ultimo = "" if self.cb_somma.isChecked() else nome

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
class SchedaQuadri(SchedaGruppiTra):
    """Quadri: più gruppi di numeri scelti dall'utente (anche con un clic: decine, finali...), ognuno verificato
    se la colonna ne contiene da un minimo a un massimo, e una regola su quanti gruppi devono esserlo."""
    CLIP_GRUPPO: dict | None = None

    def __init__(self, g, ctx, numeri, attuale=None, parent=None, arch=None):
        super().__init__(g, ctx, numeri, attuale, parent)
        self.arch = arch
        self.nome_corrente = ""
        self.setWindowTitle("Condizione: Quadri")
        v = self.layout()
        spieg = v.itemAt(0).widget()
        spieg.setText("<b>Quadri</b> – forma uno o più gruppi di numeri (clicca i numeri oppure usa i gruppi comuni: "
                      "decine, finali, pari, primi...). Un gruppo è <i>verificato</i> se la colonna contiene da un "
                      "minimo a un massimo dei suoi numeri. Poi scegli la <b>regola</b>: tutti i gruppi verificati, "
                      "almeno uno, uno solo, nessuno... Per ogni gruppo l'analisi mostra come si è comportato "
                      "nell'archivio.")
        self.barra = BarraInsiemi(g, lambda: self.scelti, self._scrivi_scelti, set(self.numeri), self)
        v.insertWidget(1, self.barra)

        op = QHBoxLayout()
        for testo, f in (("Taglia gruppo", self._taglia_gruppo), ("Copia gruppo", self._copia_gruppo),
                         ("Incolla gruppo", self._incolla_gruppo), ("Duplica gruppo", self._duplica_gruppo),
                         ("Modifica numeri del gruppo", self._riprendi_gruppo), ("Sposta su", lambda: self._sposta(-1)),
                         ("Sposta giù", lambda: self._sposta(1)), ("Svuota tutto", self._svuota)):
            b = QPushButton(testo)
            b.clicked.connect(f)
            op.addWidget(b)
        op.addStretch()
        v.insertLayout(3, op)
        crea = QHBoxLayout()
        crea.addWidget(QLabel("Crea tutti i gruppi in un colpo:"))
        for testo, f in (("Le decine", cnd.decine), ("I finali 0-9", cnd.finali)):
            b = QPushButton(testo)
            b.setProperty("senza_icona", True)
            b.clicked.connect(lambda _=False, f=f: self._crea_tutti(f(g)))
            crea.addWidget(b)
        crea.addStretch()
        b = QPushButton("Salva questo quadro...")
        b.clicked.connect(self._salva_quadro)
        crea.addWidget(b)
        b = QPushButton("Carica un mio quadro...")
        b.clicked.connect(self._carica_quadro)
        crea.addWidget(b)
        v.insertLayout(4, crea)

        riga = QHBoxLayout()
        riga.addWidget(QLabel("Nome:"))
        self.e_nome = QLineEdit(attuale.nome if attuale else "")
        self.e_nome.setPlaceholderText("facoltativo")
        riga.addWidget(self.e_nome)
        riga.addWidget(QLabel("Regola:"))
        self.c_regola = QComboBox()
        for k, (testo, _) in cnd.REGOLE_QUADRI.items():
            self.c_regola.addItem(testo, k)
        self.c_regola.addItem("Personalizzata: scelgo io da quanti a quanti gruppi", "")
        self.s_n = QSpinBox()
        self.s_n.setRange(0, 26)
        self.s_n.setValue(1)
        riga.addWidget(self.c_regola, 1)
        riga.addWidget(QLabel("N ="))
        riga.addWidget(self.s_n)
        v.insertLayout(v.count() - 1, riga)
        self.c_regola.currentIndexChanged.connect(self._regola)
        self.s_n.valueChanged.connect(self._regola)
        if attuale and attuale.codice == "quadri":
            i = self.c_regola.findData(attuale.regola)
            self.c_regola.setCurrentIndex(i if i >= 0 else self.c_regola.count() - 1)
            if attuale.regola in ("almeno_n", "esattamente_n"):
                self.s_n.setValue(attuale.minimo)
            elif attuale.regola == "al_massimo_n":
                self.s_n.setValue(attuale.massimo)
        elif attuale:
            self.c_regola.setCurrentIndex(self.c_regola.count() - 1)
        self._regola()
        adatta_schermo(self, 1180, 860)

    # ---------------------------------------------------------------- selezione e gruppi
    def _scrivi_scelti(self, nuovi):
        self.scelti = set(nuovi) & set(self.numeri)
        self._colori()

    def _clic(self, n):
        self.barra.nome_ultimo = ""
        super()._clic(n)

    def _aggiungi(self):
        nome = self.barra.nome_ultimo
        prima = len(self.gruppi)
        super()._aggiungi()
        if len(self.gruppi) > prima:
            self.gruppi[-1]["nome"] = nome
            self.barra.nome_ultimo = ""
            self._tabella()
            self.t.selectRow(len(self.gruppi) - 1)
            self._regola()

    def _elimina(self):
        super()._elimina()
        self._regola()

    def _riga(self) -> int:
        i = self.t.currentRow()
        return i if 0 <= i < len(self.gruppi) else -1

    def _copia_gruppo(self):
        i = self._riga()
        if i >= 0:
            SchedaQuadri.CLIP_GRUPPO = dict(self.gruppi[i])
            QApplication.clipboard().setText(" ".join(map(str, self.gruppi[i]["numeri"])))

    def _taglia_gruppo(self):
        i = self._riga()
        if i >= 0:
            self._copia_gruppo()
            self._elimina()

    def _incolla_gruppo(self):
        c = SchedaQuadri.CLIP_GRUPPO
        if c is None:
            nuovi = sorted({x for x in _numeri_da_testo(QApplication.clipboard().text()) if x in self.numeri})
            if not nuovi:
                QMessageBox.information(self, "Quadri", "Niente da incollare: copia prima un gruppo.")
                return
            c = {"numeri": nuovi, "minimo": 1, "massimo": min(len(nuovi), self.g.k), "nome": ""}
        if len(self.gruppi) < 26:
            nuovo = dict(c)
            nuovo["numeri"] = [n for n in c["numeri"] if n in self.numeri] or list(c["numeri"])
            self.gruppi.append(nuovo)
            self._tabella()
            self.t.selectRow(len(self.gruppi) - 1)
            self._colori()
            self._regola()

    def _duplica_gruppo(self):
        i = self._riga()
        if i >= 0 and len(self.gruppi) < 26:
            self.gruppi.insert(i + 1, dict(self.gruppi[i]))
            self._tabella()
            self.t.selectRow(i + 1)
            self._colori()
            self._regola()

    def _riprendi_gruppo(self):
        """Rimette i numeri del gruppo nel selettore per cambiarli (il gruppo viene tolto dall'elenco)."""
        i = self._riga()
        if i >= 0:
            self.scelti = set(self.gruppi[i]["numeri"]) & set(self.numeri)
            self.s_min.setValue(self.gruppi[i]["minimo"])
            self.s_max.setValue(self.gruppi[i]["massimo"])
            del self.gruppi[i]
            self._tabella()
            self._colori()
            self._regola()

    def _sposta(self, d):
        i = self._riga()
        j = i + d
        if i >= 0 and 0 <= j < len(self.gruppi):
            self.gruppi[i], self.gruppi[j] = self.gruppi[j], self.gruppi[i]
            self._tabella()
            self.t.selectRow(j)
            self._colori()

    def _svuota(self):
        if self.gruppi and QMessageBox.question(self, "Quadri", "Eliminare tutti i gruppi?") != QMessageBox.Yes:
            return
        self.gruppi.clear()
        self.scelti.clear()
        self._tabella()
        self._colori()
        self._regola()

    def _crea_tutti(self, gruppi: list[dict]):
        nuovi = []
        for x in gruppi:
            nums = [n for n in x["numeri"] if n in self.numeri]
            if nums:
                nuovi.append({"nome": x.get("nome", ""), "numeri": nums, "minimo": 1,
                              "massimo": min(len(nums), self.g.k)})
        if not nuovi:
            QMessageBox.information(self, "Quadri", "Nessuno dei numeri del sistema rientra in questi gruppi.")
            return
        self.gruppi = nuovi
        self._tabella()
        self._colori()
        self._regola()

    def _tabella(self):
        super()._tabella()
        for i, gr in enumerate(self.gruppi):
            it = self.t.item(i, 0)
            if it is not None and gr.get("nome"):
                it.setText(f"{cnd.LETTERE[i]} · {gr['nome']}")
        self.t.resizeColumnsToContents()

    # ---------------------------------------------------------------- regola
    def _regola(self, *_):
        if not hasattr(self, "c_regola"):
            return
        k = self.c_regola.currentData()
        n_g = len(self.gruppi)
        richiede_n = bool(k) and cnd.REGOLE_QUADRI[k][1]
        self.s_n.setEnabled(richiede_n)
        manuale = not k
        self.s_gmin.setEnabled(manuale)
        self.s_gmax.setEnabled(manuale)
        self.s_n.setMaximum(max(n_g, 1))
        if k:
            lo, hi = cnd.regola_intervallo(k, n_g, self.s_n.value())
            self.s_gmin.setValue(lo)
            self.s_gmax.setValue(hi)

    # ---------------------------------------------------------------- salvataggio nei «miei quadri»
    def _condizione(self) -> cnd.Condizione | None:
        if not self.gruppi:
            return None
        k = self.c_regola.currentData()
        nome = self.e_nome.text().strip()
        if k:
            return cnd.quadri(self.gruppi, k, self.s_n.value(), nome)
        lo, hi = sorted((self.s_gmin.value(), self.s_gmax.value()))
        c = cnd.quadri(self.gruppi, "tutte", 1, nome)
        c.regola, c.minimo, c.massimo = "", lo, hi
        return c

    def _salva_quadro(self):
        c = self._condizione()
        if c is None:
            QMessageBox.information(self, "Quadri", "Aggiungi almeno un gruppo.")
            return
        if self.arch is None:
            return
        nome, ok = QInputDialog.getText(self, "Salva questo quadro", "Nome:", text=self.e_nome.text() or "")
        if ok and nome.strip():
            cu.aggiungi(self.arch, nome, c)
            self.e_nome.setText(nome.strip())
            QMessageBox.information(self, "Quadri", f"Quadro «{nome.strip()}» salvato in Le mie condizioni.")

    def _carica_quadro(self):
        if self.arch is None:
            return
        voci = cu.carica(self.arch, ("quadri",))
        if not voci:
            QMessageBox.information(self, "Quadri", "Non hai ancora salvato nessun quadro.")
            return
        nomi = [v["nome"] for v in voci]
        nome, ok = QInputDialog.getItem(self, "Carica un mio quadro", "Quadro:", nomi, 0, False)
        if ok:
            c = cu.condizione(voci[nomi.index(nome)])
            self.gruppi = [dict(x) for x in c.gruppi]
            self.e_nome.setText(c.nome)
            i = self.c_regola.findData(c.regola)
            self.c_regola.setCurrentIndex(i if i >= 0 else self.c_regola.count() - 1)
            if c.regola in ("almeno_n", "esattamente_n"):
                self.s_n.setValue(c.minimo)
            elif c.regola == "al_massimo_n":
                self.s_n.setValue(c.massimo)
            self._tabella()
            self._colori()
            self._regola()

    def _ok(self):
        if not self.gruppi:
            QMessageBox.warning(self, "Quadri", "Aggiungi almeno un gruppo.")
            return
        self.risultato = self._condizione()
        self.accept()


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
