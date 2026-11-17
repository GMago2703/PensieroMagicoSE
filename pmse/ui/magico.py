"""Finestre di Magico Pensiero: impostazioni, spiegazione, verifica storica, storico previsioni."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QDialog, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton, QSpinBox, QTableWidget, QVBoxLayout)

from ..core import magico, personalizzate
from ..core.db import Archivio
from .analisi import riempi_tabella


def carica_impostazioni(arch: Archivio) -> magico.Impostazioni:
    return magico.Impostazioni.da_json(arch.leggi_impostazione(magico.CHIAVE_IMP))


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
        v = QVBoxLayout(self)
        spieg = QLabel(magico.__doc__.split("Il risultato")[0].strip())
        spieg.setWordWrap(True)
        spieg.setStyleSheet("background:#f3e5f5; padding:6px; font-size:11px;")
        v.addWidget(spieg)
        g = QGroupBox("Pesi delle voci (0 = ignora)")
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
        f2.addRow("Nitidezza (più alta = sestine più concentrate sui numeri migliori)", self.s_nit)
        f2.addRow("Numeri in comune ammessi tra le 3 sestine", self.s_com)
        v.addWidget(g2)
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
        v.addLayout(h)

    def _predefiniti(self):
        imp = magico.Impostazioni()
        for k, s in self.pesi.items():
            s.setValue(imp.pesi[k])
        for s in self.pers.values():
            s.setValue(0)
        self.s_tend.setValue(imp.finestra_tendenza)
        self.s_eco.setValue(imp.profondita_eco)
        self.s_nit.setValue(imp.nitidezza)
        self.s_com.setValue(imp.max_comuni)

    def _salva(self):
        imp = magico.Impostazioni(
            pesi={k: s.value() for k, s in self.pesi.items()},
            finestra_tendenza=self.s_tend.value(), profondita_eco=self.s_eco.value(),
            personalizzate={k: s.value() for k, s in self.pers.items() if s.value()},
            nitidezza=self.s_nit.value(), max_comuni=self.s_com.value())
        if not any(imp.pesi.values()) and not imp.personalizzate:
            QMessageBox.warning(self, "Impostazioni", "Almeno una voce deve avere peso maggiore di zero.")
            return
        self.arch.scrivi_impostazione(magico.CHIAVE_IMP, imp.a_json())
        self.accept()


class FinestraSpiegazione(QDialog):
    def __init__(self, r: magico.RisultatoMagico, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Magico Pensiero – come sono nate le sestine")
        self.resize(950, 620)
        v = QVBoxLayout(self)
        testo = [f"Calcolo eseguito su {r.estrazioni_usate} estrazioni, fino al concorso del "
                 f"{r.basata_su:%d/%m/%Y}." if r.basata_su else ""]
        for i, s in enumerate(r.sestine, 1):
            det = ", ".join(f"{k} {v:.2f}" for k, v in s.dettaglio.items())
            testo.append(f"Sestina {i}: {' '.join(map(str, s.numeri))}  — voto {s.voto:.3f} ({det})")
        testo.append(f"Jolly: {r.jolly} (miglior numero fuori dalla 1ª sestina)    SuperStar: {r.superstar or '-'}")
        l = QLabel("\n".join(testo))
        l.setWordWrap(True)
        v.addWidget(l)
        tab = QTableWidget()
        tab.verticalHeader().setVisible(False)
        voci = list(r.voci.keys())
        nomi = [magico.VOCI.get(k, k) for k in voci]
        righe = sorted(([n, *[r.voci[k][n] for k in voci], r.punteggi[n]] for n in range(1, 91)),
                       key=lambda x: -x[-1])
        riempi_tabella(tab, ["Numero", *nomi, "Punteggio finale"], righe, [[x[0]] for x in righe])
        v.addWidget(tab, 1)


class Verificatore(QThread):
    avanzamento = Signal(int, int)
    finito = Signal(object)

    def __init__(self, storico, concorsi, imp):
        super().__init__()
        self.storico, self.concorsi, self.imp = storico, concorsi, imp
        self._stop = False

    def run(self):
        es = magico.verifica_storica(self.storico, self.concorsi, self.imp,
                                     lambda i, n: self.avanzamento.emit(i, n), lambda: self._stop)
        self.finito.emit(es)


class FinestraVerifica(QDialog):
    def __init__(self, arch: Archivio, parent=None):
        super().__init__(parent)
        self.arch = arch
        self.thread = None
        self.setWindowTitle("Magico Pensiero – verifica storica")
        self.resize(900, 640)
        v = QVBoxLayout(self)
        v.addWidget(QLabel(
            "Rifà il calcolo «come se» fossimo prima di ognuno degli ultimi N concorsi (usando solo le estrazioni "
            "precedenti) e confronta i punti delle 3 sestine con quelli di 3 sestine scelte a caso."))
        h = QHBoxLayout()
        h.addWidget(QLabel("Ultimi concorsi da provare:"))
        self.s_n = QSpinBox()
        self.s_n.setRange(10, 3000)
        self.s_n.setValue(200)
        h.addWidget(self.s_n)
        self.b_via = QPushButton("▶ Avvia verifica")
        self.b_via.clicked.connect(self.avvia)
        h.addWidget(self.b_via)
        h.addStretch()
        v.addLayout(h)
        self.barra = QProgressBar()
        v.addWidget(self.barra)
        self.testo = QPlainTextEdit()
        self.testo.setReadOnly(True)
        v.addWidget(self.testo, 1)
        self.tab = QTableWidget()
        self.tab.verticalHeader().setVisible(False)
        v.addWidget(self.tab, 1)

    def avvia(self):
        storico = self.arch.sestine()
        if len(storico) < 150:
            QMessageBox.warning(self, "Verifica", "Servono almeno 150 estrazioni in archivio.")
            return
        self.b_via.setEnabled(False)
        self.testo.setPlainText("Calcolo in corso...")
        self.thread = Verificatore(storico, self.s_n.value(), carica_impostazioni(self.arch))
        self.thread.avanzamento.connect(lambda i, n: (self.barra.setMaximum(n), self.barra.setValue(i)))
        self.thread.finito.connect(self._finito)
        self.thread.start()

    def _finito(self, es: magico.EsitoVerifica):
        self.b_via.setEnabled(True)
        self.testo.setPlainText(es.testo())
        if es.prove:      # l'esito viene passato a Claude come informazione
            self.arch.scrivi_impostazione("magico_ultima_verifica", es.testo())
        righe = [[d.strftime("%d/%m/%Y"), " ".join(map(str, estr)),
                  *[" ".join(map(str, s)) for s in sest], *punti, max(punti)]
                 for d, sest, estr, punti in reversed(es.dettagli)]
        riempi_tabella(self.tab, ["Concorso del", "Estratti", "Sestina 1", "Sestina 2", "Sestina 3",
                                  "Punti 1", "Punti 2", "Punti 3", "Migliore"], righe)

    def closeEvent(self, ev):
        if self.thread and self.thread.isRunning():
            self.thread._stop = True
            self.thread.wait(5000)
        super().closeEvent(ev)


class FinestraStorico(QDialog):
    def __init__(self, arch: Archivio, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Magico Pensiero – storico delle previsioni")
        self.resize(1050, 500)
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Ogni volta che generi le sestine vengono salvate qui (una per concorso). "
                           "Appena l'estrazione successiva entra in archivio vengono confrontate in automatico."))
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
                esito = [f"{e.data:%d/%m/%Y}: {' '.join(map(str, e.sestina))} J{e.jolly} SS{e.superstar or '-'}",
                         *punti, "sì" if p["jolly"] in e.numeri else "no",
                         "sì" if p.get("superstar") and p["superstar"] == e.superstar else "no"]
            else:
                esito = ["in attesa dell'estrazione", "", "", "", "", ""]
            righe.append([p.get("origine", "Algoritmo"), p.get("generata", ""),
                          dopo.strftime("%d/%m/%Y") if dopo else "",
                          *[" ".join(map(str, s)) for s in sest], p["jolly"], p.get("superstar") or "-", *esito])
        riempi_tabella(tab, ["Origine", "Generata il", "Dopo il concorso del", "Sestina 1", "Sestina 2", "Sestina 3",
                             "Jolly", "SuperStar", "Estrazione successiva", "Punti 1", "Punti 2", "Punti 3",
                             "Jolly tra i 6", "SuperStar preso"], righe)
        v.addWidget(tab, 1)
