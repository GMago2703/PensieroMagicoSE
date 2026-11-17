"""Finestre di Magico Pensiero: impostazioni, spiegazione, verifica storica, storico previsioni."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtGui import QColor, QTextDocument
from PySide6.QtWidgets import (QComboBox, QDialog, QStyle, QStyledItemDelegate, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSpinBox, QTableWidget,
                               QVBoxLayout, QWidget)

from ..core import magico, personalizzate
from ..core.db import Archivio
from .analisi import riempi_tabella
from .schermo import adatta_schermo


def carica_impostazioni(arch: Archivio) -> magico.Impostazioni:
    return magico.Impostazioni.da_json(arch.leggi_impostazione(magico.CHIAVE_IMP), arch.gioco)


def descrizione_algoritmo(g) -> str:
    testo = magico.__doc__.split("Il risultato")[0].strip()
    if g.is_ej:
        testo = (testo.replace("le 3 sestine con voto più alto, con al massimo 2 numeri in comune\n   tra loro. "
                               "Jolly = miglior numero rimasto fuori dalla 1ª sestina. SuperStar =\n   stessa "
                               "logica (eco, tendenza, maturità) applicata alla serie dei SuperStar.",
                               "la cinquina con voto più alto. Euronumeri = i 2 con punteggio più alto\n   "
                               "secondo eco, tendenza e maturità applicate alla serie degli Euronumeri\n   "
                               "(formula attuale 1-12).")
                 .replace("sestine", "cinquine").replace("sestina", "cinquina"))
    return testo


def punteggi_personalizzati(arch: Archivio, imp: magico.Impostazioni, storico) -> dict[str, dict[int, float]]:
    extra = {}
    for r in personalizzate.carica(arch):
        if imp.personalizzate.get(r.nome):
            extra[r.nome] = personalizzate.esegui(r, storico).punteggi
    return extra


def genera(arch: Archivio) -> magico.RisultatoMagico:
    imp = carica_impostazioni(arch)
    storico = arch.sestine()
    return magico.genera(storico, imp, punteggi_personalizzati(arch, imp, storico))


class FinestraImpostazioni(QDialog):
    def __init__(self, arch: Archivio, parent=None):
        super().__init__(parent)
        self.arch = arch
        self.setWindowTitle("Magico Pensiero – impostazioni dell'algoritmo")
        imp = carica_impostazioni(arch)
        esterno = QVBoxLayout(self)
        area = QScrollArea()                 # se lo schermo è basso il contenuto scorre
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        interno = QWidget()
        v = QVBoxLayout(interno)
        area.setWidget(interno)
        esterno.addWidget(area, 1)
        spieg = QLabel(descrizione_algoritmo(arch.gioco))
        spieg.setWordWrap(True)
        spieg.setStyleSheet("background:#f3e5f5; padding:6px; font-size:11px;")
        v.addWidget(spieg)
        g = QGroupBox("Pesi di base delle voci (0 = ignora; l'apprendimento li corregge automaticamente)")
        f = QFormLayout(g)
        self.pesi = {}
        for k, nome in magico.VOCI.items():
            s = QDoubleSpinBox()
            s.setRange(0, 5)
            s.setSingleStep(0.05)
            s.setValue(imp.pesi.get(k, 0))
            f.addRow(nome, s)
            self.pesi[k] = s
        self.pers = {}
        for r in personalizzate.carica(arch):
            s = QDoubleSpinBox()
            s.setRange(-5, 5)
            s.setSingleStep(0.05)
            s.setValue(imp.personalizzate.get(r.nome, 0))
            f.addRow("★ " + r.nome, s)
            self.pers[r.nome] = s
        v.addWidget(g)
        g2 = QGroupBox("Altri parametri")
        f2 = QFormLayout(g2)
        self.s_tend = QSpinBox()
        self.s_tend.setRange(5, 500)
        self.s_tend.setValue(imp.finestra_tendenza)
        self.s_eco = QSpinBox()
        self.s_eco.setRange(1, 10)
        self.s_eco.setValue(imp.profondita_eco)
        self.s_nit = QDoubleSpinBox()
        self.s_nit.setRange(0.5, 10)
        self.s_nit.setSingleStep(0.5)
        self.s_nit.setValue(imp.nitidezza)
        self.s_com = QSpinBox()
        self.s_com.setRange(0, 5)
        self.s_com.setValue(imp.max_comuni)
        f2.addRow("Tendenza: ultime N estrazioni", self.s_tend)
        f2.addRow("Eco: quante estrazioni precedenti", self.s_eco)
        f2.addRow(f"Nitidezza (più alta = {arch.gioco.nome_comb_pl} più concentrate sui numeri migliori)",
                  self.s_nit)
        if not arch.gioco.is_ej:
            f2.addRow("Numeri in comune ammessi tra le 3 sestine", self.s_com)
        v.addWidget(g2)

        g3 = QGroupBox("Somiglianza con l'archivio (numeri in comune con le estrazioni passate)")
        f3 = QFormLayout(g3)
        self.c_lim = QComboBox()
        self.c_lim.addItems(["Automatico, secondo l'analisi delle combinazioni vincenti", "Al massimo 3",
                             "Al massimo 4", "Al massimo 5"])
        self.c_lim.setCurrentIndex(0 if not imp.limite_archivio else imp.limite_archivio - 2)
        self.s_soglia = QDoubleSpinBox()
        self.s_soglia.setRange(50, 100)
        self.s_soglia.setValue(imp.soglia_archivio)
        self.s_soglia.setSuffix(" %")
        self.s_fin = QSpinBox()
        self.s_fin.setRange(50, 10000)
        self.s_fin.setValue(imp.finestra_archivio)
        self.l_lim = QLabel()
        self.l_lim.setWordWrap(True)
        f3.addRow("Limite", self.c_lim)
        f3.addRow("Copertura richiesta (automatico)", self.s_soglia)
        f3.addRow("Estrazioni studiate (automatico)", self.s_fin)
        f3.addRow(self.l_lim)
        for w in (self.c_lim, self.s_soglia, self.s_fin):
            (w.currentIndexChanged if isinstance(w, QComboBox) else w.valueChanged).connect(self._anteprima_limiti)
        v.addWidget(g3)
        self._anteprima_limiti()

        h = QHBoxLayout()
        b_def = QPushButton("Ripristina predefiniti")
        b_def.clicked.connect(self._predefiniti)
        b_ok = QPushButton("💾 Salva")
        b_ok.clicked.connect(self._salva)
        b_ann = QPushButton("Annulla")
        b_ann.clicked.connect(self.reject)
        h.addWidget(b_def)
        h.addStretch()
        h.addWidget(b_ok)
        h.addWidget(b_ann)
        esterno.addLayout(h)               # pulsanti sempre visibili in basso
        dim = interno.sizeHint()
        adatta_schermo(self, dim.width() + 50, dim.height() + 90)

    def _imp_limiti(self) -> magico.Impostazioni:
        i = self.c_lim.currentIndex()
        imp = magico.Impostazioni.predefinite(self.arch.gioco)
        imp.limite_archivio = 0 if i == 0 else i + 2
        imp.soglia_archivio, imp.finestra_archivio = self.s_soglia.value(), self.s_fin.value()
        return imp

    def _anteprima_limiti(self, *_):
        storico = self.arch.sestine()
        if len(storico) < 30:
            self.l_lim.setText("Archivio troppo piccolo per calcolare i limiti.")
            return
        lo, hi = magico.limiti_archivio(storico, self._imp_limiti())
        self.l_lim.setText(f"Con queste impostazioni ogni {self.arch.gioco.nome_comb} dovrà avere, con QUALSIASI estrazione passata, "
                           f"al massimo <b>{hi}</b> numeri in comune, e con almeno una estrazione <b>{lo}</b> o più. "
                           "(Dettagli: menu Analisi → Somiglianza con l'archivio)")

    def _predefiniti(self):
        imp = magico.Impostazioni.predefinite(self.arch.gioco)
        for k, s in self.pesi.items():
            s.setValue(imp.pesi[k])
        for s in self.pers.values():
            s.setValue(0)
        self.s_tend.setValue(imp.finestra_tendenza)
        self.s_eco.setValue(imp.profondita_eco)
        self.s_nit.setValue(imp.nitidezza)
        self.s_com.setValue(imp.max_comuni)
        self.c_lim.setCurrentIndex(0)
        self.s_soglia.setValue(imp.soglia_archivio)
        self.s_fin.setValue(imp.finestra_archivio)

    def _salva(self):
        imp = carica_impostazioni(self.arch)      # conserva statistiche e filtri appresi
        imp.pesi = {k: s.value() for k, s in self.pesi.items()}
        imp.finestra_tendenza, imp.profondita_eco = self.s_tend.value(), self.s_eco.value()
        imp.personalizzate = {k: s.value() for k, s in self.pers.items() if s.value()}
        imp.nitidezza, imp.max_comuni = self.s_nit.value(), self.s_com.value()
        imp.limite_archivio = self._imp_limiti().limite_archivio
        imp.soglia_archivio, imp.finestra_archivio = self.s_soglia.value(), self.s_fin.value()
        if not any(imp.pesi.values()) and not imp.personalizzate:
            QMessageBox.warning(self, "Impostazioni", "Almeno una voce deve avere peso maggiore di zero.")
            return
        self.arch.scrivi_impostazione(magico.CHIAVE_IMP, imp.a_json())
        self.accept()


class FinestraSpiegazione(QDialog):
    def __init__(self, r: magico.RisultatoMagico, parent=None):
        super().__init__(parent)
        from ..core.gioco import GIOCHI
        g = GIOCHI.get(r.gioco)
        self.setWindowTitle(f"Magico Pensiero {g.nome} – come sono nate le {g.nome_comb_pl}")
        adatta_schermo(self, 950, 620)
        v = QVBoxLayout(self)
        testo = [f"Calcolo eseguito su {r.estrazioni_usate} estrazioni, fino al concorso del "
                 f"{r.basata_su:%d/%m/%Y}." if r.basata_su else ""]
        for i, s in enumerate(r.sestine, 1):
            det = ", ".join(f"{k} {v:.2f}" for k, v in s.dettaglio.items())
            testo.append(f"{g.C()} {i}: {' '.join(map(str, s.numeri))}  — voto {s.voto:.3f} ({det})")
        if g.is_ej:
            testo.append(f"Euronumeri: {r.jolly} e {r.superstar} (i 2 con punteggio più alto: eco, tendenza e "
                         "maturità sulla serie degli Euronumeri)")
        else:
            testo.append(f"Jolly: {r.jolly} (miglior numero fuori dalla 1ª sestina)    "
                         f"SuperStar: {r.superstar or '-'}")
        lo, hi = r.limiti_archivio
        testo.append(f"Somiglianza con l'archivio: ogni {g.nome_comb} ha al massimo {hi} numeri in comune con "
                     f"qualsiasi estrazione passata (e almeno {lo} con una di esse), come le combinazioni vincenti "
                     "reali.")
        l = QLabel("\n".join(testo))
        l.setWordWrap(True)
        v.addWidget(l)
        tab = QTableWidget()
        tab.verticalHeader().setVisible(False)
        voci = list(r.voci.keys())
        nomi = [magico.VOCI.get(k, k) for k in voci]
        righe = sorted(([n, *[r.voci[k][n] for k in voci], r.punteggi[n]] for n in range(1, g.n + 1)),
                       key=lambda x: -x[-1])
        riempi_tabella(tab, ["Numero", *nomi, "Punteggio finale"], righe, [[x[0]] for x in righe])
        v.addWidget(tab, 1)


class Verificatore(QThread):
    avanzamento = Signal(int, int)
    finito = Signal(object)

    def __init__(self, storico, concorsi, imp, apprendi: bool = False):
        super().__init__()
        self.storico, self.concorsi, self.imp, self.apprendi = storico, concorsi, imp, apprendi
        self._stop = False

    def run(self):
        es = magico.verifica_storica(self.storico, self.concorsi, self.imp,
                                     lambda i, n: self.avanzamento.emit(i, n), lambda: self._stop)
        appreso = None
        if self.apprendi and es.prove and not self._stop:
            from ..core import apprendimento
            appreso = apprendimento.allena(self.storico, self.imp, self.concorsi, interrompi=lambda: self._stop)
        self.finito.emit((es, appreso))


def _html_numeri(numeri, evidenzia: set, colore: str = "#c62828") -> str:
    """Numeri separati da spazi, con quelli 'presi' evidenziati (sfondo colorato e grassetto)."""
    parti = []
    for n in numeri:
        if n in evidenzia:
            parti.append(f"<span style='background:{colore}; color:white; font-weight:bold'>&nbsp;{n}&nbsp;</span>")
        else:
            parti.append(f"&nbsp;{n}&nbsp;")
    return " ".join(parti)


class DelegatoHtml(QStyledItemDelegate):
    """Disegna le celle della tabella come testo formattato (per evidenziare i numeri)."""

    def paint(self, painter, option, index):
        testo = index.data(Qt.UserRole + 2)
        if not testo:
            return super().paint(painter, option, index)
        self.initStyleOption(option, index)
        painter.save()
        option.text = ""
        option.widget.style().drawControl(QStyle.CE_ItemViewItem, option, painter, option.widget)
        doc = QTextDocument()
        doc.setDefaultFont(option.font)
        doc.setHtml(testo)
        painter.translate(option.rect.left() + 4, option.rect.top() + (option.rect.height() - doc.size().height()) / 2)
        doc.drawContents(painter)
        painter.restore()

    def sizeHint(self, option, index):
        testo = index.data(Qt.UserRole + 2)
        if not testo:
            return super().sizeHint(option, index)
        doc = QTextDocument()
        doc.setDefaultFont(option.font)
        doc.setHtml(testo)
        return QSize(int(doc.idealWidth()) + 10, int(doc.size().height()) + 4)


class FinestraVerifica(QDialog):
    """Verifica storica = previsioni su quanto già avvenuto: per ognuno degli ultimi N concorsi rifà
    Magico Pensiero con i soli dati precedenti e confronta le combinazioni con quella estratta,
    evidenziando i numeri in comune. I risultati possono correggere l'algoritmo e vengono passati all'AI."""

    def __init__(self, arch: Archivio, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QCheckBox
        self.arch = arch
        self.thread = None
        self.esito = None
        g = arch.gioco
        self.setWindowTitle(f"Magico Pensiero {g.nome} – verifica storica (previsioni su quanto già avvenuto)")
        adatta_schermo(self, 1250, 760)
        v = QVBoxLayout(self)
        cosa = "la cinquina e gli Euronumeri" if g.is_ej else "le 3 sestine, il Jolly e il SuperStar"
        spiega = QLabel(
            f"Per ognuno degli ultimi N concorsi il programma rifà il calcolo «come se» fosse il giorno prima, usando "
            f"solo le estrazioni precedenti, e confronta {cosa} che avrebbe proposto con la combinazione realmente "
            "estratta. I numeri in comune sono <span style='background:#c62828; color:white'>&nbsp;evidenziati&nbsp;"
            "</span> sia negli estratti sia nelle combinazioni proposte.")
        spiega.setWordWrap(True)            # va a capo invece di allargare la finestra
        v.addWidget(spiega)
        h = QHBoxLayout()
        h.addWidget(QLabel("Ultimi concorsi da verificare (10-1000):"))
        self.s_n = QSpinBox()
        self.s_n.setRange(10, 1000)
        self.s_n.setValue(200)
        h.addWidget(self.s_n)
        self.ck_appr = QCheckBox("Usa i risultati per correggere l'algoritmo (apprendimento)")
        self.ck_appr.setChecked(True)
        h.addWidget(self.ck_appr)
        self.b_via = QPushButton("▶ Avvia verifica")
        self.b_via.clicked.connect(self.avvia)
        h.addWidget(self.b_via)
        h.addStretch()
        v.addLayout(h)
        h = QHBoxLayout()                   # seconda riga: filtro
        h.addWidget(QLabel("Mostra:"))
        self.c_filtro = QComboBox()
        self.c_filtro.addItems(["tutti i concorsi", "solo con almeno 2 punti", "solo con almeno 3 punti",
                                "solo con almeno 4 punti"])
        self.c_filtro.currentIndexChanged.connect(self._mostra)
        h.addWidget(self.c_filtro)
        h.addStretch()
        v.addLayout(h)
        self.barra = QProgressBar()
        v.addWidget(self.barra)
        self.testo = QPlainTextEdit()
        self.testo.setReadOnly(True)
        self.testo.setMaximumHeight(230)
        v.addWidget(self.testo)
        self.tab = QTableWidget()
        self.tab.verticalHeader().setVisible(False)
        self.tab.setItemDelegate(DelegatoHtml(self.tab))
        self.tab.setSelectionBehavior(QTableWidget.SelectRows)
        v.addWidget(self.tab, 1)

    def avvia(self):
        storico = self.arch.sestine()
        if len(storico) < 150:
            QMessageBox.warning(self, "Verifica", "Servono almeno 150 estrazioni in archivio.")
            return
        self.b_via.setEnabled(False)
        self.testo.setPlainText("Calcolo in corso...")
        self.thread = Verificatore(storico, self.s_n.value(), carica_impostazioni(self.arch), self.ck_appr.isChecked())
        self.thread.avanzamento.connect(lambda i, n: (self.barra.setMaximum(n), self.barra.setValue(i)))
        self.thread.finito.connect(self._finito)
        self.thread.start()

    def _finito(self, risultato):
        es, appreso = risultato
        self.b_via.setEnabled(True)
        self.esito = es
        testo = es.testo()
        if es.prove:      # l'esito (con il dettaglio dei concorsi) viene passato all'intelligenza artificiale
            self.arch.scrivi_impostazione("magico_ultima_verifica", magico.dettaglio_per_ai(es))
        if appreso is not None:
            imp, correzioni, fatti = appreso
            self.arch.scrivi_impostazione(magico.CHIAVE_IMP, imp.a_json())
            testo += (f"\n\nApprendimento: {fatti} concorsi nuovi conteggiati"
                      + (" (gli altri erano già stati conteggiati in precedenza)." if fatti < es.prove else "."))
            testo += ("\nCorrezioni ai filtri: " + "; ".join(correzioni)) if correzioni else \
                "\nNessun filtro ha avuto bisogno di correzioni."
            eff = magico.pesi_effettivi(imp)
            testo += "\nPesi effettivi ora: " + ", ".join(f"{magico.VOCI[k]} {v:.3f}" for k, v in eff.items())
        testo += "\n\nQuesti risultati verranno usati anche dall'intelligenza artificiale (pulsante 🤖 AI)."
        self.testo.setPlainText(testo)
        self._mostra()

    def _mostra(self, *_):
        es = self.esito
        if not es:
            return
        g = self.arch.gioco
        C = g.combinazioni_magico
        minimo = [0, 2, 3, 4][self.c_filtro.currentIndex()]
        nomi = [g.C()] if C == 1 else [f"{g.C()} {i}" for i in range(1, C + 1)]
        punti_col = ["Punti"] if C == 1 else [f"Punti {i}" for i in range(1, C + 1)]
        speciali = ["Euronumeri previsti", "Euronumeri estratti"] if g.is_ej else \
            ["Jolly previsto", "SuperStar previsto", "Jolly / SuperStar estratti"]
        colonne = ["Concorso del", "Estratti", *nomi, *punti_col, "Migliore", *speciali]
        righe, html = [], []
        for d, sest, estr, punti, prev, vero in reversed(es.dettagli):
            if max(punti) < minimo:
                continue
            proposti = {n for s in sest for n in s}
            presi = proposti & set(estr)
            if g.is_ej:
                euro_v = {vero[0], vero[1]}
                sp_testo = [f"{prev[0]} {prev[1]}", f"{vero[0]} {vero[1]}"]
                sp_html = [_html_numeri(prev, euro_v, "#1565c0"), _html_numeri(vero, {prev[0], prev[1]}, "#1565c0")]
            else:
                sp_testo = [prev[0], prev[1] or "-", f"{vero[0]} / {vero[1] or '-'}"]
                j_ok = prev[0] in estr or prev[0] == vero[0]
                ss_ok = prev[1] is not None and prev[1] == vero[1]
                sp_html = [_html_numeri([prev[0]], {prev[0]} if j_ok else set(), "#ef6c00"),
                           _html_numeri([prev[1]] if prev[1] else ["-"], {prev[1]} if ss_ok else set(), "#b8860b"),
                           f"{vero[0]} / {vero[1] or '-'}"]
            righe.append([d.strftime("%d/%m/%Y"), " ".join(map(str, estr)), *[" ".join(map(str, s)) for s in sest],
                          *punti, max(punti), *sp_testo])
            html.append([None, _html_numeri(estr, presi), *[_html_numeri(s, set(estr)) for s in sest],
                         *[None] * (C + 1), *sp_html])
        riempi_tabella(self.tab, colonne, righe)
        self.tab.setSortingEnabled(False)
        for r, riga in enumerate(html):
            migliore = righe[r][2 + 2 * C]
            for c, h in enumerate(riga):
                it = self.tab.item(r, c)
                if it is None:
                    continue
                if h:
                    it.setData(Qt.UserRole + 2, h)
                if migliore >= 3:
                    it.setBackground(QColor("#c8e6c9"))
                elif migliore == 2:
                    it.setBackground(QColor("#f1f8e9"))
        self.tab.resizeColumnsToContents()
        for c in range(1, 2 + C):
            self.tab.setColumnWidth(c, max(self.tab.columnWidth(c), 34 * g.k))

    def closeEvent(self, ev):
        if self.thread and self.thread.isRunning():
            self.thread._stop = True
            self.thread.wait(5000)
        super().closeEvent(ev)


class FinestraStorico(QDialog):
    def __init__(self, arch: Archivio, parent=None):
        super().__init__(parent)
        g = arch.gioco
        C = g.combinazioni_magico
        self.setWindowTitle(f"Magico Pensiero {g.nome} – storico delle previsioni")
        adatta_schermo(self, 1050, 500)
        v = QVBoxLayout(self)
        v.addWidget(QLabel(f"Ogni volta che generi le {g.nome_comb_pl} vengono salvate qui (una per concorso e "
                           "per origine). Appena l'estrazione successiva entra in archivio vengono confrontate in "
                           "automatico."))
        tab = QTableWidget()
        tab.verticalHeader().setVisible(False)
        date_arch = arch.date_ordinate()
        righe = []
        for p in reversed(magico.leggi_previsioni(arch)):
            dopo = date.fromisoformat(p["dopo"]) if p.get("dopo") else None
            succ = next((d for d in date_arch if dopo and d > dopo), None)
            e = arch.per_data(succ) if succ else None
            sest = p["sestine"]
            if e:
                punti = [len(set(e.numeri) & set(s)) for s in sest]
                if g.is_ej:
                    presi = len({p["jolly"], p.get("superstar")} & {e.jolly, e.superstar})
                    esito = [f"{e.data:%d/%m/%Y}: {' '.join(map(str, e.sestina))} Euro {e.jolly} {e.superstar}",
                             *punti, presi]
                else:
                    esito = [f"{e.data:%d/%m/%Y}: {' '.join(map(str, e.sestina))} J{e.jolly} "
                             f"SS{e.superstar or '-'}", *punti, "sì" if p["jolly"] in e.numeri else "no",
                             "sì" if p.get("superstar") and p["superstar"] == e.superstar else "no"]
            else:
                esito = ["in attesa dell'estrazione"] + [""] * (C + (1 if g.is_ej else 2))
            speciali = [f"{p['jolly']} {p.get('superstar')}"] if g.is_ej else [p["jolly"], p.get("superstar") or "-"]
            righe.append([p.get("origine", "Algoritmo"), p.get("generata", ""),
                          dopo.strftime("%d/%m/%Y") if dopo else "",
                          *[" ".join(map(str, s)) for s in sest], *speciali, *esito])
        nomi = [g.C()] if C == 1 else [f"{g.C()} {i}" for i in range(1, C + 1)]
        punti_col = ["Punti"] if C == 1 else [f"Punti {i}" for i in range(1, C + 1)]
        if g.is_ej:
            colonne = ["Origine", "Generata il", "Dopo il concorso del", *nomi, "Euronumeri",
                       "Estrazione successiva", *punti_col, "Euronumeri presi"]
        else:
            colonne = ["Origine", "Generata il", "Dopo il concorso del", *nomi, "Jolly", "SuperStar",
                       "Estrazione successiva", *punti_col, "Jolly tra i 6", "SuperStar preso"]
        riempi_tabella(tab, colonne, righe)
        v.addWidget(tab, 1)


# ---------------------------------------------------------------- apprendimento
class Allenatore(QThread):
    avanzamento = Signal(int, int)
    finito = Signal(object)

    def __init__(self, storico, imp, concorsi):
        super().__init__()
        self.storico, self.imp, self.concorsi = storico, imp, concorsi
        self._stop = False

    def run(self):
        from ..core import apprendimento
        self.finito.emit(apprendimento.allena(self.storico, self.imp, self.concorsi,
                                              lambda i, n: self.avanzamento.emit(i, n), lambda: self._stop))


class FinestraApprendimento(QDialog):
    """Analisi delle previsioni rispetto alle estrazioni uscite e stato dell'apprendimento."""

    def __init__(self, arch: Archivio, nuove=None, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QCheckBox, QSplitter
        self.arch = arch
        self.thread = None
        self.setWindowTitle(f"Magico Pensiero {arch.gioco.nome} – analisi delle previsioni e apprendimento")
        adatta_schermo(self, 1200, 760)
        v = QVBoxLayout(self)
        if nuove:
            l = QLabel(f"<b>Sono uscite {len(nuove)} nuove estrazioni: ecco come le aveva viste Magico Pensiero "
                       "e cosa è stato corretto.</b>")
            l.setStyleSheet("background:#e8f5e9; padding:6px;")
            v.addWidget(l)
        div = QSplitter()
        sx = QVBoxLayout()
        w_sx = QGroupBox("Estrazioni valutate (clic per i dettagli)")
        w_sx.setLayout(sx)
        self.tab = QTableWidget()
        self.tab.verticalHeader().setVisible(False)
        self.tab.setSelectionBehavior(QTableWidget.SelectRows)
        self.tab.itemSelectionChanged.connect(self._dettaglio)
        sx.addWidget(self.tab, 2)
        self.testo = QPlainTextEdit()
        self.testo.setReadOnly(True)
        sx.addWidget(self.testo, 3)
        div.addWidget(w_sx)

        dx = QVBoxLayout()
        w_dx = QGroupBox("Stato dell'apprendimento")
        w_dx.setLayout(dx)
        self.tab_voci = QTableWidget()
        self.tab_voci.verticalHeader().setVisible(False)
        dx.addWidget(QLabel("Come ogni voce ha 'visto' i numeri usciti (50% = come il caso; lo scarto conta "
                            "solo oltre ±1,5):"))
        dx.addWidget(self.tab_voci, 2)
        self.l_filtri = QLabel()
        self.l_filtri.setWordWrap(True)
        dx.addWidget(self.l_filtri)
        f = QFormLayout()
        imp = carica_impostazioni(arch)
        self.ck_att = QCheckBox("Apprendimento automatico attivo")
        self.ck_att.setChecked(imp.apprendimento)
        self.s_forza = QDoubleSpinBox()
        self.s_forza.setRange(0, 2)
        self.s_forza.setSingleStep(0.05)
        self.s_forza.setValue(imp.forza_apprendimento)
        self.s_soglia = QDoubleSpinBox()
        self.s_soglia.setRange(5, 60)
        self.s_soglia.setSuffix(" %")
        self.s_soglia.setValue(imp.soglia_filtri * 100)
        f.addRow(self.ck_att)
        f.addRow("Forza della correzione dei pesi", self.s_forza)
        f.addRow("Allenta un filtro se scarta più vincenti di", self.s_soglia)
        dx.addLayout(f)
        b_salva = QPushButton("💾 Salva queste impostazioni")
        b_salva.clicked.connect(self._salva)
        dx.addWidget(b_salva)
        h = QHBoxLayout()
        h.addWidget(QLabel("Allena sul passato, ultimi"))
        self.s_n = QSpinBox()
        self.s_n.setRange(50, 5000)
        self.s_n.setValue(1000)
        h.addWidget(self.s_n)
        h.addWidget(QLabel("concorsi"))
        self.b_allena = QPushButton("▶ Allena")
        self.b_allena.clicked.connect(self._allena)
        h.addWidget(self.b_allena)
        dx.addLayout(h)
        self.barra = QProgressBar()
        dx.addWidget(self.barra)
        b_azz = QPushButton("Azzera l'apprendimento (torna ai pesi e filtri di base)")
        b_azz.clicked.connect(self._azzera)
        dx.addWidget(b_azz)
        div.addWidget(w_dx)
        div.setSizes([700, 500])
        v.addWidget(div, 1)
        self._ricarica()

    def _ricarica(self):
        from ..core import apprendimento
        self.registro = list(reversed(apprendimento.leggi_registro(self.arch)))
        righe = []
        for r in self.registro:
            alg = [max(p["punti"]) for p in r.get("previsioni", []) if p["origine"] == "Algoritmo"]
            cla = [max(p["punti"]) for p in r.get("previsioni", []) if p["origine"] != "Algoritmo"]
            righe.append([date.fromisoformat(r["data_estrazione"]).strftime("%d/%m/%Y"),
                          " ".join(map(str, r["estratti"])), alg[0] if alg else "-", cla[0] if cla else "-",
                          len(r.get("positivi", [])), len(r.get("mancanze", []))])
        riempi_tabella(self.tab, ["Estrazione", "Numeri usciti", "Punti algoritmo", "Punti AI", "Positivi",
                                  "Mancanze"], righe)
        if self.registro:
            self.tab.selectRow(0)
        else:
            self.testo.setPlainText("Nessuna estrazione valutata finora.\n\nDa oggi in poi, ogni volta che una "
                                    "nuova estrazione entra in archivio, il programma la confronta con le combinazioni "
                                    "generate e corregge l'algoritmo. Puoi anche allenarlo subito sul passato con il "
                                    "pulsante «Allena».")
        imp = carica_impostazioni(self.arch)
        riempi_tabella(self.tab_voci, ["Voce", "Valutazioni", "Posizione media %", "Scarto dal caso",
                                       "Peso di base", "Peso effettivo"], apprendimento.stato_voci(imp))
        descr = magico.descrivi_filtri(imp, self.arch.sestine())
        self.l_filtri.setText("<b>Filtri di forma attuali:</b> " + "; ".join(descr.values()))

    def _dettaglio(self):
        from ..core.apprendimento import Valutazione
        righe = {i.row() for i in self.tab.selectedItems()}
        if not righe:
            return
        r = self.registro[next(iter(righe))]
        val = Valutazione(**{k: r[k] for k in Valutazione.__dataclass_fields__ if k in r})
        self.testo.setPlainText(val.testo())

    def _salva(self):
        imp = carica_impostazioni(self.arch)
        imp.apprendimento = self.ck_att.isChecked()
        imp.forza_apprendimento = self.s_forza.value()
        imp.soglia_filtri = self.s_soglia.value() / 100
        self.arch.scrivi_impostazione(magico.CHIAVE_IMP, imp.a_json())
        self._ricarica()

    def _allena(self):
        storico = self.arch.sestine()
        if len(storico) < 150:
            QMessageBox.warning(self, "Allena", "Servono almeno 150 estrazioni in archivio.")
            return
        self._salva()
        self.b_allena.setEnabled(False)
        self.thread = Allenatore(storico, carica_impostazioni(self.arch), self.s_n.value())
        self.thread.avanzamento.connect(lambda i, n: (self.barra.setMaximum(n), self.barra.setValue(i)))
        self.thread.finito.connect(self._allenato)
        self.thread.start()

    def _allenato(self, esito):
        imp, correzioni, fatti = esito
        self.arch.scrivi_impostazione(magico.CHIAVE_IMP, imp.a_json())
        self.b_allena.setEnabled(True)
        self._ricarica()
        testo = f"Allenamento completato su {fatti} concorsi.\n\n"
        testo += ("Correzioni ai filtri:\n" + "\n".join(correzioni)) if correzioni else \
            "Nessun filtro ha avuto bisogno di correzioni."
        testo += "\n\nI pesi effettivi delle voci sono nella tabella a destra."
        self.testo.setPlainText(testo)

    def _azzera(self):
        if QMessageBox.question(self, "Azzera", "Cancellare le statistiche apprese e tornare ai filtri di base? "
                                                "(I pesi di base restano quelli impostati.)") != QMessageBox.Yes:
            return
        imp = carica_impostazioni(self.arch)
        base = magico.Impostazioni.predefinite(self.arch.gioco)
        imp.stat_voci, imp.stat_filtri = {}, {}
        imp.appreso_da, imp.appreso_a = "", ""
        for campo in ("pari_min", "pari_max", "alti_min", "alti_max", "consecutivi_max", "somma_percentile",
                      "max_stessa_decina"):
            setattr(imp, campo, getattr(base, campo))
        self.arch.scrivi_impostazione(magico.CHIAVE_IMP, imp.a_json())
        self._ricarica()

    def closeEvent(self, ev):
        if self.thread and self.thread.isRunning():
            self.thread._stop = True
            self.thread.wait(5000)
        super().closeEvent(ev)
