"""Finestra del Laboratorio: la casualità delle estrazioni è davvero casuale?"""
from __future__ import annotations

import html

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QSpinBox,
                               QTextBrowser, QVBoxLayout)

from ..core import laboratorio
from ..core.db import Archivio
from .schermo import adatta_schermo

COLORI = {"ANOMALIA": "#c62828", "da tenere d'occhio": "#ef6c00", "compatibile con il caso": "#2e7d32"}

INTRODUZIONE = (
    "<p><b>Il laboratorio interroga l'archivio con il metodo scientifico.</b> Una macchina estrattrice è un "
    "sistema fisico deterministico: con variabili identiche darebbe sempre lo stesso risultato. Ma è anche "
    "caotica: differenze minime (un millesimo di millimetro, un soffio d'aria) crescono a ogni urto e rendono "
    "impossibile calcolare la traiettoria delle palline. Un <b>difetto sistematico</b> però sopravvive al caos e "
    "lascia un'impronta nei numeri: è quella che il laboratorio cerca.</p>"
    "<p><b>1. La macchina</b>: palline più frequenti, posizione di uscita (per il SuperEnalotto fino al 2009 le sei "
    "ruote del Lotto), coppie, numeri vicini, decine, somme, cambiamenti nel tempo, giorno della settimana, numeri "
    "speciali. <b>2. La memoria</b>: ripetizioni, vicini, ritardi. <b>3. La previsione</b>: una gara tra regole "
    "(compreso un modello di apprendimento automatico) giudicate solo sui concorsi che non hanno mai visto.</p>"
    "<p>Ogni prova dà una p: la probabilità di un risultato così se le estrazioni fossero perfettamente casuali. "
    "Con molte prove qualche p piccola esce per fortuna: si dichiara <span style='color:#c62828'><b>ANOMALIA"
    "</b></span> solo dopo la correzione di Holm. L'esito viene passato anche all'intelligenza artificiale.</p>")


class Laboratorista(QThread):
    avanzamento = Signal(str, int, int)
    finito = Signal(object)
    errore = Signal(str)

    def __init__(self, estrazioni, gioco, simulazioni):
        super().__init__()
        self.args = (estrazioni, gioco, simulazioni)
        self._stop = False

    def run(self):
        try:
            r = laboratorio.esegui(*self.args, avanzamento=lambda t, i, n: self.avanzamento.emit(t, i, n),
                                   interrompi=lambda: self._stop)
            self.finito.emit(r)
        except Exception as ex:
            self.errore.emit(str(ex))


def rapporto_html(r: laboratorio.Rapporto) -> str:
    e = html.escape
    parti = [f"<h2>Laboratorio – {e(r.gioco)}</h2>",
             f"<p>{r.estrazioni} estrazioni; epoche: " +
             "; ".join(f"{e(n)} ({k} concorsi)" for n, k in r.epoche) +
             f". {len(r.prove)} prove, confronto con {r.simulazioni} archivi simulati perfettamente casuali.</p>"]
    for ep, pct in r.sensibilita:
        parti.append(f"<p style='color:#555'>Sensibilità ({e(ep)}): un difetto diventa visibile se una pallina esce "
                     f"almeno il {pct:.0f}% più (o meno) del normale.</p>")
    an = r.anomalie
    if an:
        parti.append("<p style='background:#ffebee; padding:6px'><b>Verdetto: trovate "
                     f"{len(an)} anomalie statisticamente solide</b> – " +
                     ", ".join(e(f"{p.nome} ({p.epoca})") for p in an) +
                     ". Vanno confermate sulle estrazioni future prima di usarle.</p>")
    else:
        parti.append("<p style='background:#e8f5e9; padding:6px'><b>Verdetto: nessuna anomalia "
                     "statisticamente solida.</b> Con questi dati le estrazioni si comportano come una sorgente "
                     "perfettamente casuale e nessuna regola batte il caso sui concorsi che non ha visto.</p>")
    titoli = {"Macchina": "1. La macchina (impronte di difetti fisici)",
              "Memoria": "2. La memoria (legami tra un concorso e i successivi)",
              "Previsione": "3. La previsione (gara tra regole, giudicate solo sul futuro)"}
    for gruppo, titolo in titoli.items():
        prove = [p for p in r.prove if p.gruppo == gruppo]
        if not prove:
            continue
        parti.append(f"<h3>{titolo}</h3><table cellspacing='0' cellpadding='4' border='1' "
                     "style='border-collapse:collapse; border-color:#ccc'>"
                     "<tr style='background:#eee'><th>Esito</th><th>Prova</th><th>Epoca</th><th>Che cosa cerca</th>"
                     "<th>Che cosa si è misurato</th><th>p</th><th>p corr.</th></tr>")
        for p in prove:
            dettagli = "".join(f"<br><span style='color:#666'>· {e(s)}</span>" for s in p.sospetti[:3])
            parti.append(f"<tr><td style='color:{COLORI[p.esito]}'><b>{e(p.esito)}</b></td><td>{e(p.nome)}</td>"
                         f"<td>{e(p.epoca)}</td><td>{e(p.domanda)}</td><td>{e(p.risultato)}{dettagli}</td>"
                         f"<td>{p.p:.4f}</td><td>{p.p_holm:.4f}</td></tr>")
        parti.append("</table>")
    return "".join(parti)


class FinestraLaboratorio(QDialog):
    def __init__(self, arch: Archivio, parent=None):
        super().__init__(parent)
        self.arch = arch
        self.thread = None
        self.setWindowTitle(f"Laboratorio {arch.gioco.nome} – la casualità è davvero casuale?")
        adatta_schermo(self, 1200, 800)
        v = QVBoxLayout(self)
        h = QHBoxLayout()
        h.addWidget(QLabel("Archivi casuali simulati per il confronto:"))
        self.s_sim = QSpinBox()
        self.s_sim.setRange(50, 1000)
        self.s_sim.setSingleStep(50)
        self.s_sim.setValue(200)
        self.s_sim.setToolTip("Più archivi = confronto più preciso, ma calcolo più lungo")
        h.addWidget(self.s_sim)
        self.b_via = QPushButton("🧪 Avvia il laboratorio")
        self.b_via.clicked.connect(self.avvia)
        h.addWidget(self.b_via)
        h.addStretch()
        v.addLayout(h)
        self.barra = QProgressBar()
        self.barra.setFormat("%p%  %v/%m")
        v.addWidget(self.barra)
        self.stato = QLabel("")
        v.addWidget(self.stato)
        self.testo = QTextBrowser()
        self.testo.setHtml(INTRODUZIONE)
        v.addWidget(self.testo, 1)

    def avvia(self):
        if self.thread and self.thread.isRunning():
            self.thread._stop = True
            return
        estrazioni = self.arch.tutte(True)
        if len(estrazioni) < 200:
            QMessageBox.warning(self, "Laboratorio", "Servono almeno 200 estrazioni in archivio.")
            return
        self.b_via.setText("⏹ Ferma")
        self.testo.setHtml(INTRODUZIONE + "<p><i>Calcolo in corso...</i></p>")
        self.thread = Laboratorista(estrazioni, self.arch.gioco, self.s_sim.value())
        self.thread.avanzamento.connect(self._avanza)
        self.thread.finito.connect(self._finito)
        self.thread.errore.connect(self._errore)
        self.thread.start()

    def _avanza(self, testo, i, n):
        self.barra.setMaximum(n)
        self.barra.setValue(i)
        self.stato.setText(testo)

    def _errore(self, msg):
        self.b_via.setText("🧪 Avvia il laboratorio")
        QMessageBox.warning(self, "Laboratorio", msg)

    def _finito(self, r):
        self.b_via.setText("🧪 Avvia il laboratorio")
        self.stato.setText("Laboratorio completato." if not self.thread._stop else "Interrotto: risultato parziale.")
        self.risultato = r
        self.arch.scrivi_impostazione(laboratorio.CHIAVE_LAB, laboratorio.riassunto_per_ai(r))
        self.arch.scrivi_impostazione(laboratorio.CHIAVE_LAB + "_testo", r.testo())
        self.testo.setHtml(rapporto_html(r))

    def closeEvent(self, ev):
        if self.thread and self.thread.isRunning():
            self.thread._stop = True
            self.thread.wait(10000)
        super().closeEvent(ev)
