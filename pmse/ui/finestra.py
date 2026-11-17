"""Finestra principale: a sinistra la tabella dei 90 numeri, a destra Magico Pensiero."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QPlainTextEdit, QPushButton, QDialog, QSizePolicy, QVBoxLayout, QWidget)

from .. import __version__
from ..core import internet, magico, personalizzate
from ..core.db import Archivio, verifica_integrita
from ..core.importatore import esporta_csv
from .analisi import FinestraAnalisi
from .archivio import FinestraArchivio
from .editor import EditorEstrazione
from .griglia import COLORE_JOLLY, COLORE_SUPERSTAR, COLORI_SESTINE, Griglia90
from .importa import FinestraImporta
from .internet import FinestraInternet, Scaricatore

SFONDO = """
QMainWindow { background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
              stop:0 #b8860b, stop:0.35 #f4d35e, stop:0.6 #d4a017, stop:1 #8b6508); }
QFrame#pannello { background: white; border: 2px solid #555; }
QLabel#titolo { font-family: 'Segoe UI'; font-size: 24px; font-weight: bold; }
QPushButton[class="lato"] { text-align: left; padding: 6px 10px; font-size: 12px; min-width: 100px; }
"""

MENU_VUOTI = ["Sistemi", "Condizioni", "Elaborazione", "Combinazioni", "Statistiche", "Metodi"]
MENU_VUOTI_DOPO = ["Stampe", "Ricevitoria", "Impostazioni"]


class Pannello(QFrame):
    def __init__(self, titolo: str, colore_titolo: str, selezionabile: bool):
        super().__init__()
        self.setObjectName("pannello")
        g = QGridLayout(self)
        g.setContentsMargins(10, 10, 10, 10)
        self.box_conc = QLabel()
        self.box_conc.setAlignment(Qt.AlignCenter)
        self.box_conc.setStyleSheet("border:2px solid black; padding:2px 6px; font-size:11px;")
        self.box_conc.setMinimumWidth(70)
        g.addWidget(self.box_conc, 0, 0)
        t = QLabel(titolo)
        t.setObjectName("titolo")
        t.setStyleSheet(f"color:{colore_titolo};")
        t.setAlignment(Qt.AlignCenter)
        g.addWidget(t, 0, 1)
        self.griglia = Griglia90(selezionabile=selezionabile)
        self.griglia.setFixedSize(360, 290)        # dimensioni come nella schermata di riferimento
        g.addWidget(self.griglia, 1, 0, 1, 2)
        self.lato = QVBoxLayout()
        g.addLayout(self.lato, 0, 2, 2, 1)
        self.sotto = QLabel()
        self.sotto.setAlignment(Qt.AlignCenter)
        g.addWidget(self.sotto, 2, 0, 1, 3)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def pulsante(self, testo: str, funzione) -> QPushButton:
        b = QPushButton(testo)
        b.setProperty("class", "lato")
        b.clicked.connect(funzione)
        self.lato.addWidget(b)
        return b


class FinestraPrincipale(QMainWindow):
    def __init__(self, archivio: Archivio | None = None, avvio_automatico: bool = True):
        super().__init__()
        self.arch = archivio or Archivio()
        self.scaricatore: Scaricatore | None = None
        self.setWindowTitle(f"Pensiero Magico SE {__version__}")
        self.resize(1250, 680)
        self.setStyleSheet(SFONDO)
        self._menu()
        self._centro()
        self.aggiorna_stato()
        self._mostra_ultima_previsione()
        if avvio_automatico:
            QTimer.singleShot(400, self._all_avvio)

    # ------------------------------------------------------------------ menu
    def _azione(self, menu, testo, funzione=None, abilitata=True):
        a = QAction(testo, self)
        if funzione:
            a.triggered.connect(funzione)
        a.setEnabled(abilitata)
        menu.addAction(a)
        return a

    def _menu_vuoto(self, nome):
        m = self.menuBar().addMenu(nome)
        self._azione(m, "(in preparazione)", abilitata=False)

    def _menu(self):
        mb = self.menuBar()
        for nome in MENU_VUOTI:
            self._menu_vuoto(nome)

        m = mb.addMenu("&Archivio")
        self._azione(m, "Consulta archivio...", self.apri_archivio)
        self._azione(m, "Aggiornamento archivio (inserisci / modifica)...", self.apri_editor)
        m.addSeparator()
        self._azione(m, "Importa da file (CSV, TXT, Excel)...", self.importa)
        self._azione(m, "Esporta in CSV...", self.esporta)
        m.addSeparator()
        self._azione(m, "Verifica integrità archivio...", self.verifica)
        self._azione(m, "Backup archivio...", self.backup)
        self._azione(m, "Ripristina da backup...", self.ripristina)
        m.addSeparator()
        self._azione(m, "Svuota archivio...", self.svuota)

        m = mb.addMenu("&Internet")
        self._azione(m, "Aggiorna ora (estrazioni mancanti)", lambda: self.apri_internet(False))
        self._azione(m, "Scarica archivio completo dal 1997", lambda: self.apri_internet(True))
        m.addSeparator()
        self.a_avvio = self._azione(m, "Aggiorna automaticamente all'avvio", self._cambia_avvio)
        self.a_avvio.setCheckable(True)
        self.a_avvio.setChecked(self.arch.leggi_impostazione("aggiorna_avvio", "1") == "1")

        self.m_analisi = mb.addMenu("A&nalisi")
        self.m_analisi.aboutToShow.connect(self._menu_analisi)
        self._menu_analisi()

        m = mb.addMenu("&Magico Pensiero")
        self._azione(m, "✨ Genera le 3 sestine Magico Pensiero", self.genera)
        self._azione(m, "Come sono nate le sestine (spiegazione)...", self.spiegazione)
        self._azione(m, "🤖 Magico Pensiero + Claude (intelligenza artificiale)...", self.claude)
        m.addSeparator()
        self._azione(m, "Impostazioni dell'algoritmo...", self.impostazioni_magico)
        self._azione(m, "Verifica storica dell'algoritmo...", self.verifica_magico)
        self._azione(m, "Storico delle previsioni...", self.storico_magico)

        for nome in MENU_VUOTI_DOPO:
            self._menu_vuoto(nome)
        m = mb.addMenu("&Help")
        self._azione(m, "Informazioni su Pensiero Magico SE", self.informazioni)

    # -------------------------------------------------------------- centro
    def _centro(self):
        w = QWidget()
        esterno = QVBoxLayout(w)
        esterno.addStretch()
        h = QHBoxLayout()
        esterno.addLayout(h)
        esterno.addStretch()
        h.setSpacing(40)
        h.addStretch()

        self.p_sx = Pannello("SuperEnalotto", "#d81b60", selezionabile=True)
        self.p_sx.pulsante("📚  Archivio", self.apri_archivio)
        self.p_sx.pulsante("🔍  Analisi", lambda: self.apri_analisi(None))
        self.p_sx.pulsante("📋  Sestine", self.mie_sestine)
        self.p_sx.pulsante("✔  Tutti", self.p_sx.griglia.seleziona_tutti)
        self.p_sx.pulsante("🟥  Azzera", self.p_sx.griglia.azzera)
        self.p_sx.lato.addStretch()
        self.p_sx.griglia.selezione_cambiata.connect(lambda s: self.l_sel.setText(f"Numeri selezionati: {len(s)}"))

        self.p_dx = Pannello("Magico Pensiero", "#6a1b9a", selezionabile=False)
        self.p_dx.pulsante("✨  Genera", self.genera)
        self.p_dx.pulsante("❓  Perché", self.spiegazione)
        self.p_dx.pulsante("🤖  Claude", self.claude)
        legenda = QLabel()
        voci = [(COLORI_SESTINE[i], f"Sestina {i + 1}") for i in range(3)] + \
               [(COLORE_JOLLY, "Jolly"), (COLORE_SUPERSTAR, "SuperStar")]
        legenda.setText("<br>".join(f"<span style='background:{c};'>&nbsp;&nbsp;&nbsp;&nbsp;</span> {t}"
                                    for c, t in voci))
        self.p_dx.lato.addWidget(legenda)
        self.p_dx.lato.addStretch()
        self.l_sestine = QLabel("Le 3 sestine compariranno qui dopo l'elaborazione.")
        self.l_sestine.setFont(QFont("Consolas", 11))
        self.l_sestine.setWordWrap(True)
        self.p_dx.sotto.setText("")
        self.p_dx.layout().addWidget(self.l_sestine, 3, 0, 1, 3)

        h.addWidget(self.p_sx)
        h.addWidget(self.p_dx)
        h.addStretch()
        self.setCentralWidget(w)

        sb = self.statusBar()
        self.l_sel = QLabel("Numeri selezionati: 0")
        self.l_arch = QLabel()
        self.l_ultima = QLabel()
        sb.addWidget(self.l_sel, 1)
        sb.addWidget(self.l_arch, 1)
        sb.addWidget(self.l_ultima, 2)

    def aggiorna_stato(self):
        n = self.arch.conta()
        u = self.arch.ultima()
        self.l_arch.setText(f"Estrazioni in archivio: {n}")
        if u:
            ss = f"  SS {u.superstar}" if u.superstar else ""
            self.l_ultima.setText(f"Ultima: conc. {u.concorso}/{u.data.year} del {u.data:%d/%m/%Y} — "
                                  f"{' '.join(map(str, u.sestina))}  J {u.jolly}{ss}")
            prossimo = u.concorso + 1 if u.data.year == date.today().year else 1
            self.p_sx.box_conc.setText(f"Concorso N°\n<b>{prossimo}</b>".replace("\n", "<br>"))
            self.p_dx.box_conc.setText(f"per il<br><b>{prossimo}</b>")
        else:
            self.l_ultima.setText("Archivio vuoto")
            self.p_sx.box_conc.setText("Concorso N°<br>–")
            self.p_dx.box_conc.setText("per il<br>–")

    # ------------------------------------------------------------- azioni
    def _dopo(self, dlg):
        if getattr(dlg, "modificato", False):
            self.aggiorna_stato()

    def apri_archivio(self):
        dlg = FinestraArchivio(self.arch, self)
        dlg.exec()
        self._dopo(dlg)

    def apri_editor(self):
        dlg = EditorEstrazione(self.arch, parent=self)
        dlg.exec()
        self._dopo(dlg)

    def importa(self):
        dlg = FinestraImporta(self.arch, self)
        dlg.exec()
        self._dopo(dlg)

    def esporta(self):
        p, _ = QFileDialog.getSaveFileName(self, "Esporta archivio", f"superenalotto_{date.today():%Y%m%d}.csv",
                                           "CSV (*.csv)")
        if p:
            esporta_csv(self.arch.tutte(), p)
            QMessageBox.information(self, "Esportazione", f"Esportate {self.arch.conta()} estrazioni in:\n{p}")

    def verifica(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Verifica integrità archivio")
        dlg.resize(650, 500)
        v = QVBoxLayout(dlg)
        t = QPlainTextEdit("\n".join(verifica_integrita(self.arch)))
        t.setReadOnly(True)
        v.addWidget(t)
        dlg.exec()

    def backup(self):
        p, _ = QFileDialog.getSaveFileName(self, "Salva backup", f"PensieroMagicoSE_backup_{date.today():%Y%m%d}.db",
                                           "Archivio (*.db)")
        if p:
            self.arch.backup(p)
            QMessageBox.information(self, "Backup", f"Backup salvato in:\n{p}")

    def ripristina(self):
        p, _ = QFileDialog.getOpenFileName(self, "Scegli il backup", "", "Archivio (*.db)")
        if not p:
            return
        if QMessageBox.question(self, "Ripristino", "L'archivio attuale verrà sostituito dal backup. Continuare?") \
                != QMessageBox.Yes:
            return
        try:
            self.arch.ripristina(p)
        except Exception as ex:   # file non valido
            QMessageBox.warning(self, "Errore", f"Il file scelto non è un backup valido:\n{ex}")
            return
        self.aggiorna_stato()

    def svuota(self):
        if QMessageBox.question(self, "Svuota archivio",
                                "Cancellare TUTTE le estrazioni? (consiglio: fai prima un backup)") \
                == QMessageBox.Yes:
            self.arch.svuota()
            self.aggiorna_stato()

    def apri_internet(self, completo: bool):
        dlg = FinestraInternet(self.arch, completo=completo, parent=self)
        dlg.exec()
        self._dopo(dlg)

    def _cambia_avvio(self, stato: bool):
        self.arch.scrivi_impostazione("aggiorna_avvio", "1" if stato else "0")

    def apri_analisi(self, codice):
        FinestraAnalisi(self.arch, codice, self).exec()

    def _menu_analisi(self):
        m = self.m_analisi
        m.clear()
        for d in personalizzate.tutte_le_analisi(self.arch).values():
            self._azione(m, d.nome + "...", lambda _=False, c=d.codice: self.apri_analisi(c))
        m.addSeparator()
        self._azione(m, "🛠 Costruttore di analisi personalizzate...", self.costruttore)
        self._azione(m, "📋 Le mie sestine: confronto con l'archivio e ricerca...", self.mie_sestine)

    def costruttore(self):
        from .costruttore import FinestraCostruttore
        FinestraCostruttore(self.arch, self).exec()

    def mie_sestine(self):
        from .sestine import FinestraSestine
        FinestraSestine(self.arch, sorted(self.p_sx.griglia.selezionati), self).exec()

    def genera(self):
        from .magico import genera
        if self.arch.conta() < 30:
            QMessageBox.information(self, "Magico Pensiero", "Servono almeno 30 estrazioni in archivio.")
            return
        try:
            r = genera(self.arch)
        except ValueError as ex:
            QMessageBox.warning(self, "Magico Pensiero", str(ex))
            return
        self.ultimo_magico = r
        magico.salva_previsione(self.arch, r)
        self.mostra_magico(r)

    def mostra_magico(self, r, origine: str = "Proposta dell'algoritmo"):
        self.p_dx.griglia.mostra_sestine([s.numeri for s in r.sestine], r.jolly, r.superstar)
        righe = [f"<i>{origine}</i>"] + [f"<span style='color:{COLORI_SESTINE[i]}'>■</span> Sestina {i + 1}: "
                 f"<b>{' '.join(f'{n:2d}' for n in s.numeri)}</b>" for i, s in enumerate(r.sestine)]
        righe.append(f"<span style='color:{COLORE_JOLLY}'>■</span> Jolly <b>{r.jolly}</b>"
                     f" &nbsp; <span style='color:#b8860b'>■</span> SuperStar <b>{r.superstar or '-'}</b>")
        self.l_sestine.setText("<br>".join(righe))

    def _mostra_ultima_previsione(self):
        """All'avvio ripropone le sestine già generate per il prossimo concorso."""
        from types import SimpleNamespace
        ultima = self.arch.ultima()
        prev = magico.leggi_previsioni(self.arch)
        if ultima and prev and prev[-1].get("dopo") == ultima.data.isoformat():
            p = prev[-1]
            o = p.get("origine", "Algoritmo")
            self.mostra_magico(SimpleNamespace(sestine=[SimpleNamespace(numeri=s) for s in p["sestine"]],
                                               jolly=p["jolly"], superstar=p.get("superstar")),
                               "Scelta di Claude" if o.startswith("Claude") else "Proposta dell'algoritmo")

    def claude(self):
        from .claude import FinestraClaude
        dlg = FinestraClaude(self.arch, self)
        dlg.exec()
        if dlg.applicato:
            self.mostra_magico(dlg.applicato, "Scelta di Claude")

    def spiegazione(self):
        from .magico import FinestraSpiegazione
        if not getattr(self, "ultimo_magico", None):
            self.genera()
        if getattr(self, "ultimo_magico", None):
            FinestraSpiegazione(self.ultimo_magico, self).exec()

    def impostazioni_magico(self):
        from .magico import FinestraImpostazioni
        if FinestraImpostazioni(self.arch, self).exec():
            self.ultimo_magico = None
            if self.arch.conta() >= 30:
                self.genera()

    def verifica_magico(self):
        from .magico import FinestraVerifica
        FinestraVerifica(self.arch, self).exec()

    def storico_magico(self):
        from .magico import FinestraStorico
        FinestraStorico(self.arch, self).exec()

    def informazioni(self):
        QMessageBox.about(self, "Pensiero Magico SE", (
            f"<b>Pensiero Magico SE</b> versione {__version__}<br><br>"
            "Archivio e analisi delle estrazioni del SuperEnalotto.<br>"
            f"Archivio dati: {self.arch.percorso}<br><br>"
            "Le estrazioni sono casuali: nessun programma può garantire vincite. Gioca responsabilmente."))

    # ---------------------------------------------------------- all'avvio
    def _all_avvio(self):
        if self.arch.conta() == 0:
            r = QMessageBox.question(self, "Archivio vuoto", (
                "L'archivio è vuoto.\n\nVuoi scaricare ora da Internet tutte le estrazioni dal 1997 a oggi?\n"
                "(In alternativa puoi importare un file dal menu Archivio.)"))
            if r == QMessageBox.Yes:
                self.apri_internet(True)
            return
        if self.arch.leggi_impostazione("aggiorna_avvio", "1") != "1":
            return
        if self.arch.leggi_impostazione("ultimo_aggiornamento") == date.today().isoformat():
            return
        ultima = self.arch.ultima()
        self.statusBar().showMessage("Controllo nuove estrazioni su Internet...", 0)
        self.scaricatore = Scaricatore(internet.anni_da_aggiornare(ultima.data if ultima else None))
        self.scaricatore.finito.connect(self._aggiornato_in_background)
        self.scaricatore.errore.connect(
            lambda m: self.statusBar().showMessage("Aggiornamento automatico non riuscito (rete?)", 8000))
        self.scaricatore.start()

    def _aggiornato_in_background(self, estrazioni):
        esito = self.arch.unisci(estrazioni)
        self.arch.scrivi_impostazione("ultimo_aggiornamento", date.today().isoformat())
        self.aggiorna_stato()
        msg = f"Aggiornamento automatico: {esito.nuove} nuove estrazioni" if esito.nuove else \
            "Archivio già aggiornato"
        if esito.conflitti:
            msg += f" — {len(esito.conflitti)} conflitti (vedi Internet → Aggiorna ora)"
        self.statusBar().showMessage(msg, 10000)

    def closeEvent(self, ev):
        if self.scaricatore and self.scaricatore.isRunning():
            self.scaricatore.ferma()
            self.scaricatore.wait(3000)
        super().closeEvent(ev)
