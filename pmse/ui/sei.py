"""Finestre dedicate ai concorsi in cui è stato vinto il 6 (solo SuperEnalotto)."""
from __future__ import annotations

import html

from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QTextBrowser,
                               QVBoxLayout)

from ..core import analisi_sei, popolarita, vincite
from ..core.db import Archivio
from .internet import ScaricaVincitori
from .schermo import adatta_schermo

COLORI = {"ANOMALIA": "#c62828", "da tenere d'occhio": "#ef6c00", "compatibile con il caso": "#2e7d32"}


def rapporto_html(r: analisi_sei.RapportoSei) -> str:
    e = html.escape
    p = [f"<h2>★ I concorsi con il 6 – SuperEnalotto</h2>",
         f"<p>Concorsi con i vincitori noti: <b>{r.con_vincite}</b> su {r.concorsi}. Concorsi con almeno un 6: "
         f"<b>{len(r.sei)}</b> (vincitori del 6 in tutto: {sum(c.vincitori for c in r.sei)}).</p>",
         "<p style='color:#555'>Il 6 c'è quando qualcuno ha giocato la sestina estratta: il gruppo dei 6 dipende "
         "dalla macchina <i>e</i> da come giocano le persone. Ogni confronto mette il gruppo dei 6 contro migliaia "
         "di gruppi della stessa grandezza presi a caso dagli altri concorsi; p è la probabilità che la differenza "
         "sia solo fortuna (corretta con Holm per le molte prove).</p>",
         "<div style='background:#fffde7; padding:6px'><b>Verdetto</b><br>" +
         "<br>".join(e(n) for n in r.note) + "</div>",
         "<h3>Confronti</h3><table cellspacing='0' cellpadding='4' border='1' style='border-collapse:collapse'>"
         "<tr style='background:#eee'><th>Esito</th><th>Caratteristica</th><th>Risultato</th><th>p</th>"
         "<th>p corr.</th></tr>"]
    for pr in r.prove:
        esito = "DIFFERENZA REALE" if pr.esito == "ANOMALIA" else pr.esito
        p.append(f"<tr><td style='color:{COLORI[pr.esito]}'><b>{e(esito)}</b></td><td>{e(pr.nome)}</td>"
                 f"<td>{e(pr.risultato)}</td><td>{pr.p:.4f}</td><td>{pr.p_holm:.4f}</td></tr>")
    p.append("</table>")
    if r.numeri_frequenti:
        p.append("<p><b>Numeri più presenti nelle sestine del 6</b> (informativo: con pochi concorsi sono "
                 "soprattutto caso): " + ", ".join(f"{n} ({k} volte, attese {a:.1f})"
                                                   for n, k, a in r.numeri_frequenti[:10]) + "</p>")
    p.append("<h3>Elenco dei concorsi con il 6</h3><table cellspacing='0' cellpadding='3' border='1' "
             "style='border-collapse:collapse'><tr style='background:#ffd54f'><th>Data</th><th>Sestina</th>"
             "<th>Jolly</th><th>SuperStar</th><th>Vincitori</th><th>Premio del 6</th><th>Popolarità</th></tr>")
    for c in reversed(r.sei):
        pop = f"{c.popolarita:.2f}" if c.popolarita else "–"
        p.append(f"<tr><td>{c.data:%d/%m/%Y}</td><td><b>{' '.join(map(str, sorted(c.numeri)))}</b></td>"
                 f"<td>{c.jolly}</td><td>{c.superstar or ''}</td><td align='center'>{c.vincitori}</td>"
                 f"<td>{e(c.premio)}</td><td align='center'>{pop}</td></tr>")
    p.append("</table><p style='color:#555'>Popolarità = vincitori di 3 punti di quel concorso divisi per la "
             "mediana dei concorsi vicini: sopra 1 la sestina estratta era più giocata del solito.</p>")
    return "".join(p)


class FinestraSei(QDialog):
    def __init__(self, arch: Archivio, parent=None):
        super().__init__(parent)
        self.arch = arch
        self.setWindowTitle("★ I concorsi con il 6 – confronto con l'archivio")
        adatta_schermo(self, 1100, 800)
        v = QVBoxLayout(self)
        h = QHBoxLayout()
        b = QPushButton("▶ Esegui il confronto")
        b.clicked.connect(self.esegui)
        h.addWidget(b)
        b2 = QPushButton("Archivio con i 6 evidenziati...")
        b2.clicked.connect(self._archivio)
        h.addWidget(b2)
        h.addStretch()
        v.addLayout(h)
        self.testo = QTextBrowser()
        v.addWidget(self.testo, 1)
        self.risultato = None
        self.esegui()

    def esegui(self):
        try:
            self.risultato = analisi_sei.esegui(self.arch.tutte(True), vincite.carica(self.arch), volte=3000)
        except ValueError as ex:
            self.testo.setHtml(f"<p>{html.escape(str(ex))}</p><p>Usa <b>Internet → Aggiorna i vincitori del 6</b> "
                               "e, se l'archivio è vuoto, scarica prima le estrazioni.</p>")
            return
        extra = ""
        m = popolarita.per_archivio(self.arch)
        if m:
            piu = ", ".join(f"{n} (+{e:.0f}%)" for n, e in m.numeri()[:12])
            meno = ", ".join(f"{n} ({e:.0f}%)" for n, e in m.numeri()[-12:])
            extra = ("<h3>Quanto sono giocati i numeri</h3>"
                     f"<p>Stima dai vincitori di 3 punti di {m.concorsi} concorsi (qualità del modello, R² fuori "
                     f"campione: <b>{m.r2:.2f}</b>; 0 = nessuna capacità, 1 = perfetta).</p>"
                     f"<p><b>Più giocati:</b> {piu}<br><b>Meno giocati:</b> {meno}</p>"
                     "<p style='color:#555'>Nelle impostazioni di Magico Pensiero puoi chiedere di evitare le "
                     "combinazioni molto giocate: non aumenta la probabilità di vincere, ma in caso di vincita il "
                     "premio si divide con meno persone.</p>")
        self.testo.setHtml(rapporto_html(self.risultato) + extra)

    def _archivio(self):
        from .archivio import FinestraArchivio
        f = FinestraArchivio(self.arch, self)
        f.c_sei.setCurrentIndex(1)
        f.exec()


class FinestraVincitori(QDialog):
    """Scarica i vincitori dei concorsi che mancano (una pagina per concorso)."""

    def __init__(self, arch: Archivio, parent=None):
        super().__init__(parent)
        self.arch = arch
        self.setWindowTitle("★ Aggiorna i vincitori del 6")
        adatta_schermo(self, 560, 200)
        v = QVBoxLayout(self)
        self.da_fare = vincite.mancanti(arch)
        self.l = QLabel(f"Concorsi di cui mancano i vincitori: {len(self.da_fare)}"
                        + (" (circa un secondo ciascuno)." if self.da_fare else " – tutto aggiornato."))
        self.l.setWordWrap(True)
        v.addWidget(self.l)
        self.barra = QProgressBar()
        self.barra.setMaximum(max(1, len(self.da_fare)))
        v.addWidget(self.barra)
        h = QHBoxLayout()
        self.b_via = QPushButton("Scarica")
        self.b_via.setEnabled(bool(self.da_fare))
        self.b_via.clicked.connect(self.avvia)
        h.addWidget(self.b_via)
        self.b_stop = QPushButton("Ferma")
        self.b_stop.setEnabled(False)
        self.b_stop.clicked.connect(lambda: self.thread.ferma())
        h.addWidget(self.b_stop)
        h.addStretch()
        b = QPushButton("Chiudi")
        b.clicked.connect(self.accept)
        h.addWidget(b)
        v.addLayout(h)
        self.thread = None

    def avvia(self):
        self.b_via.setEnabled(False)
        self.b_stop.setEnabled(True)
        self.thread = ScaricaVincitori(self.da_fare)
        self.thread.avanzamento.connect(lambda m, i, n: (self.barra.setValue(i), self.l.setText(m)))
        self.thread.finito.connect(self._finito)
        self.thread.start()

    def _finito(self, dati):
        vincite.salva(self.arch, dati)
        self.b_stop.setEnabled(False)
        sei = sum(1 for x in dati.values() if x.vinto_6)
        self.l.setText(f"Letti i vincitori di {len(dati)} concorsi; tra questi {sei} con il 6.")
        if len(dati) < len(self.da_fare):
            QMessageBox.information(self, "Vincitori", "Alcuni concorsi non sono stati letti: puoi riprovare.")

    def closeEvent(self, ev):
        if self.thread and self.thread.isRunning():
            self.thread.ferma()
            self.thread.wait(5000)
        super().closeEvent(ev)
