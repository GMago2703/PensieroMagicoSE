"""Finestra principale: a sinistra la tabella dei numeri del gioco, a destra Magico Pensiero.
In alto a sinistra il selettore tra Pensiero Magico SE (SuperEnalotto) e Pensiero Magico EJ (Eurojackpot):
i due programmi usano archivi, impostazioni e previsioni completamente separati."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                               QInputDialog, QLabel, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
                               QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from .. import __version__
from ..core import internet, magico, personalizzate
from ..core.db import Archivio, verifica_integrita
from ..core.gioco import EJ, GIOCHI, SE, Gioco
from ..core.importatore import esporta_csv
from .analisi import FinestraAnalisi
from .archivio import FinestraArchivio
from .editor import EditorEstrazione
from .griglia import COLORE_JOLLY, COLORE_SUPERSTAR, COLORI_SESTINE, Griglia90
from .importa import FinestraImporta
from .internet import FinestraInternet, Scaricatore
from .schermo import adatta_schermo

# Colori ispirati alla palette del sito sisal.it (verdi, verde lime, arancio, grigio ardesia)
VERDE_SCURO, VERDE, LIME, ARANCIO, ARDESIA = "#00653B", "#0B7D3E", "#BED62F", "#FF8E0D", "#2F3C43"

SFONDO = """
QToolButton#selettore { font-weight: bold; padding: 2px 8px; }
QFrame#pannello { background: white; border: 2px solid #2F3C43; border-radius: 6px; }
QLabel#titolo { font-family: 'Segoe UI Black', 'Segoe UI'; font-size: 26px; font-weight: 900;
                font-style: italic; }
QPushButton[class="lato"] { text-align: left; padding: 6px 10px; font-size: 12px; min-width: 100px; }
"""

MENU_VUOTI = ["Metodi"]

# Menu in stile Enavision, inseriti ma non ancora attivi ("-" = separatore,
# (nome, [voci]) = sottomenu). La voce "SUPERSTAR" diventa il nome giusto per ogni gioco.
MENU_DISATTIVI: list = []
MENU_VUOTI_DOPO = ["Ricevitoria", "Impostazioni"]


FINESTRE: list = []        # riferimenti alle finestre aperte (evita che vengano distrutte)


class SfondoHome(QWidget):
    """Sfondo della home: colori in stile sisal.it e il nome del gioco scritto in grande, in parte
    nascosto dalle tabelle che gli stanno davanti."""

    def __init__(self, gioco: Gioco):
        super().__init__()
        self.g = gioco

    def paintEvent(self, ev):
        from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()
        grad = QLinearGradient(0, 0, r.width(), r.height())
        if self.g.is_ej:
            grad.setColorAt(0, QColor(ARDESIA))
            grad.setColorAt(0.55, QColor("#24323A"))
            grad.setColorAt(1, QColor(VERDE_SCURO))
        else:
            grad.setColorAt(0, QColor(VERDE_SCURO))
            grad.setColorAt(0.55, QColor(VERDE))
            grad.setColorAt(1, QColor("#0E9A4C"))
        p.fillRect(r, QBrush(grad))
        # striscia lime in basso, come le barre del sito
        p.fillRect(0, r.height() - 10, r.width(), 10, QColor(LIME))
        # nome del gioco a caratteri giganti
        testo = self.g.nome
        f = QFont("Segoe UI Black")
        f.setBold(True)
        f.setItalic(True)
        f.setPixelSize(max(60, int(r.width() / (len(testo) * 0.62))))
        p.setFont(f)
        metrica = p.fontMetrics()
        larghezza = metrica.horizontalAdvance(testo)
        x = (r.width() - larghezza) / 2
        for y, colore in ((r.height() * 0.30, LIME if not self.g.is_ej else ARANCIO),
                          (r.height() * 0.92, "#FFFFFF")):
            percorso = QPainterPath()
            percorso.addText(x, y, f, testo)
            p.setPen(QPen(QColor(0, 0, 0, 70), 10))
            p.drawPath(percorso.translated(6, 6))          # ombra
            p.setPen(QPen(QColor(ARANCIO if colore != ARANCIO else LIME), 4))
            c = QColor(colore)
            c.setAlpha(235)
            p.setBrush(c)
            p.drawPath(percorso)
        p.end()


def apri_programma(codice: str, avvio_automatico: bool = True) -> "FinestraPrincipale":
    """Apre Pensiero Magico SE o EJ con il proprio archivio (cartelle dati separate)."""
    g = GIOCHI.get(codice, SE)
    w = FinestraPrincipale(Archivio(gioco=g), avvio_automatico=avvio_automatico)
    QSettings("PensieroMagico", "Avvio").setValue("ultimo_programma", g.codice)
    FINESTRE.append(w)
    w.show()
    return w


class Pannello(QFrame):
    def __init__(self, titolo: str, colore_titolo: str, selezionabile: bool, gioco: Gioco = SE):
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
        self.griglia = Griglia90(selezionabile=selezionabile, n=gioco.n)
        righe = (gioco.n + 9) // 10
        self.griglia.setFixedSize(360, 32 * righe + 2)   # dimensioni come nella schermata di riferimento
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
        self.g: Gioco = self.arch.gioco
        self.scaricatore: Scaricatore | None = None
        self.setWindowTitle(f"{self.g.nome_app} {__version__}")
        adatta_schermo(self, 1250, 680)
        self.setProperty("gioco", self.g.codice)
        self.setStyleSheet(SFONDO)
        self._menu()
        self._centro()
        self.aggiorna_stato()
        self._mostra_ultima_previsione()
        if avvio_automatico:
            QTimer.singleShot(200, self._valuta_nuove)
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

    def _riempi_disattivo(self, menu, voci):
        for v in voci:
            if v == "-":
                menu.addSeparator()
            elif isinstance(v, tuple):
                sotto = menu.addMenu(v[0])
                self._riempi_disattivo(sotto, v[1] or ["(in preparazione)"])
                sotto.setEnabled(False)
            else:
                if v == "SUPERSTAR":
                    v = "Numeri SuperStar" if self.g.codice == "SE" else "Euronumeri"
                a = QAction(v, self)     # il testo dopo \t compare come scorciatoia, senza attivarla
                a.setEnabled(False)
                a.setToolTip("In preparazione")
                menu.addAction(a)

    # ------------------------------------------------------------- sistemi
    CONDIZIONI_MENU = [("Fisse", "gruppo", ""), ("Somme", "somme", "Ctrl+S"),
                       ("Consecutività numerica", "consecutivi", ""), ("Numero di sequenze", "sequenze", ""),
                       ("Pari e dispari", "pari", "Ctrl+P"), ("Numero di cifre", "cifre", ""),
                       ("Consecutività differenziata", "differenziata", ""),
                       ("Presenza delle distanze", "presenza_distanze", ""), ("Distanze globali", "distanza_globale", ""),
                       ("Distanze specifiche", "distanza_massima", ""), ("Posizioni", "posizione", ""),
                       ("Interruzioni (decine occupate)", "decine", ""), ("Simmetrie", "simmetrie", ""),
                       ("Ripetizioni (in comune con l'archivio)", "ripetizioni", ""),
                       ("Ripetizioni dall'ultima estrazione", "ultima", ""), ("Ritardi e IC", "ritardatari", ""),
                       ("Combinazioni speciali: numeri alti", "alti", ""),
                       ("Combinazioni speciali: numeri primi", "primi", ""),
                       ("Combinazioni filtro", "filtro", "Ctrl+F"), ("Sequele", "gruppo", ""),
                       ("Popolarità (quanto è giocata)", "popolarita", "")]

    def _menu_sistemi(self):
        mb = self.menuBar()
        m = mb.addMenu("&Sistemi")
        nuovo = m.addMenu("Nuovo")
        for testo, tipo in (("Condizionati...", "condizionato"), ("Condizionati ridotti...", "condizionato_ridotto"),
                            ("Ridotti (integrali a garanzia)...", "ridotto"), ("Ridotti immediati...", "immediato")):
            nuovo.addAction(testo, lambda t=tipo: self.nuovo_sistema(t))
        m.addSeparator()
        a = m.addAction("Carica...", self.sistemi_salvati)
        a.setShortcut(QKeySequence("F3"))
        a = m.addAction("Salva", self._salva_sistema)
        a.setShortcut(QKeySequence("F2"))
        m.addAction("Salva come...", self._salva_sistema)
        m.addAction("Cancella...", self.sistemi_salvati)
        m.addSeparator()
        m.addAction("Uscita", self.close)

        m = mb.addMenu("&Condizioni")
        m.addAction("📊 Analisi di tutte le condizioni sull'archivio...", self.analisi_condizioni)
        m.addSeparator()
        for testo, codice, tasto in self.CONDIZIONI_MENU:
            if codice == "popolarita" and self.g.is_ej:
                continue
            a = m.addAction(testo, lambda c=codice: self.apri_condizione(c))
            if tasto:
                a.setShortcut(QKeySequence(tasto))
        m.addSeparator()
        for testo in ("Personalizzata", "Quadri"):
            a = m.addAction(testo + " (in preparazione)")
            a.setEnabled(False)

        m = mb.addMenu("S&viluppo")
        m.addAction("Impostazioni (prezzi)...", self._prezzi)
        a = m.addAction("Sviluppo", self._sviluppa)
        a.setShortcut(QKeySequence("F5"))
        m.addSeparator()
        m.addAction("Calcolo garanzie (ultimo sistema sviluppato)", lambda: self._ultimo("garanzie"))
        m.addAction("Analisi statistica condizionato...", self.analisi_condizioni)
        m.addAction("Rendimento delle condizioni", self._rendimento)
        m.addSeparator()
        a = m.addAction("🎲 Verifica colonne casuali...", self.verifica_colonne)
        a.setShortcut(QKeySequence("Ctrl+K"))
        m.addSeparator()
        a = m.addAction("Editor di formazioni numeriche (in preparazione)")
        a.setEnabled(False)

        m = mb.addMenu("C&ombinazioni")
        m.addAction("Visualizzazione (ultimo sistema sviluppato)", lambda: self._ultimo(None))
        m.addSeparator()
        m.addAction("Spoglio sull'ultima estrazione", lambda: self._ultimo("spoglio_ultima"))
        m.addAction("Spoglio su una combinazione...", lambda: self._ultimo("spoglio_combinazione"))
        m.addAction("Spoglio storico...", lambda: self._ultimo("spoglio_storico"))
        m.addSeparator()
        m.addAction("Salva / Conversione formati (TXT, CSV)...", lambda: self._ultimo("esporta"))
        m.addAction("Sistemi memorizzati...", self.sistemi_salvati)
        m.addSeparator()
        for testo in ("Spoglio multiplo", "Combinazione test", "Operazioni", "Editor di combinazioni",
                      "Editor basi e varianti"):
            a = m.addAction(testo + " (in preparazione)")
            a.setEnabled(False)

    def nuovo_sistema(self, tipo, sistema=None):
        from .sistemi import EditorSistema
        if len(self.arch.tutte()) < 30 and tipo in ("condizionato", "condizionato_ridotto"):
            QMessageBox.information(self, "Sistemi", "Per i condizionati serve l'archivio: aggiornalo prima "
                                                     "(le condizioni si analizzano sulle estrazioni reali).")
        self.editor_sistema = EditorSistema(self.arch, tipo, sistema, self)
        self.editor_sistema.setAttribute(Qt.WA_DeleteOnClose, False)
        self.editor_sistema.show()
        return self.editor_sistema

    def _editor_aperto(self):
        e = getattr(self, "editor_sistema", None)
        return e if e is not None and e.isVisible() else None

    def apri_condizione(self, codice):
        e = self._editor_aperto()
        if e is None or e.s.tipo not in ("condizionato", "condizionato_ridotto"):
            e = self.nuovo_sistema("condizionato")
        if codice in ("gruppo", "filtro"):
            e._gruppo(codice)
        else:
            e.apri_condizione(codice)

    def sistemi_salvati(self):
        from .sistemi import FinestraSalvati
        FinestraSalvati(self.arch, self, lambda tipo, s: self.nuovo_sistema(tipo, s)).exec()

    def _salva_sistema(self):
        e = self._editor_aperto()
        if e is None:
            QMessageBox.information(self, "Sistemi", "Apri o crea un sistema (Sistemi → Nuovo) per salvarlo.")
            return
        e._memorizza_impostazioni()

    def _sviluppa(self):
        e = self._editor_aperto()
        if e is None:
            QMessageBox.information(self, "Sviluppo", "Apri o crea un sistema (Sistemi → Nuovo) da sviluppare.")
            return
        e.sviluppa()

    def _rendimento(self):
        e = self._editor_aperto()
        if e is None or e.s.tipo not in ("condizionato", "condizionato_ridotto"):
            QMessageBox.information(self, "Rendimento", "Apri un sistema condizionato con delle condizioni.")
            return
        e.rendimento()

    def _prezzi(self):
        from .sistemi import FinestraPrezzi
        FinestraPrezzi(self.arch, self).exec()

    def analisi_condizioni(self):
        from .sistemi import FinestraAnalisiCondizioni
        if len(self.arch.tutte()) < 30:
            QMessageBox.information(self, "Condizioni", "Archivio troppo piccolo: aggiornalo prima.")
            return
        FinestraAnalisiCondizioni(self.arch, self, self.apri_condizione).exec()

    # ------------------------------------------------------------- statistiche e stampe
    def _menu_statistiche(self):
        from ..core import statistiche as st
        m = self.menuBar().addMenu("S&tatistiche")
        voci = {s.codice: s for s in st.statistiche_del_gioco(self.g)}
        for gruppo in (("numeri", "speciali"), ("tabellone", "caldi", "posizione", "condizioni", "anni")):
            for c in gruppo:
                self._azione(m, voci[c].nome + "...", lambda _=False, c=c: self.statistica(c))
            m.addSeparator()
        sotto = m.addMenu("Combinazioni")
        for c in ("ambi_f", "ambi_r", "terni_f"):
            self._azione(sotto, voci[c].nome + "...", lambda _=False, c=c: self.statistica(c))

    def statistica(self, codice):
        from .statistiche import FinestraStatistica
        if self.arch.conta() < 10:
            QMessageBox.information(self, "Statistiche", "Servono almeno 10 estrazioni in archivio.")
            return
        FinestraStatistica(self.arch, codice, self).exec()

    def verifica_colonne(self):
        from .statistiche import FinestraVerificaColonne
        FinestraVerificaColonne(self.arch, self).exec()

    def _menu_stampe(self):
        m = self.menuBar().addMenu("Sta&mpe")
        a = self._azione(m, "🖨 Tabulato di un sistema (stampante, PDF, TXT)...", self.tabulato)
        a.setShortcut(QKeySequence("Ctrl+T"))
        self._azione(m, "Estrazioni dell'archivio...", self.stampa_estrazioni)
        m.addSeparator()
        self._azione(m, "Le statistiche si stampano dalla loro finestra (pulsante Stampa)", abilitata=False)

    def tabulato(self):
        from .sistemi import ULTIMO
        from .statistiche import FinestraTabulato
        FinestraTabulato(self.arch, self, ultimo=ULTIMO.get(self.g.codice)).exec()

    def stampa_estrazioni(self):
        from .stampa import stampa
        from .statistiche import stampa_estrazioni
        n, ok = QInputDialog.getInt(self, "Stampa estrazioni", "Quante estrazioni recenti? (0 = tutto l'archivio)",
                                    100, 0, 100000)
        if ok:
            stampa(self, f"Estrazioni {self.g.nome}" + (f" – ultime {n}" if n else ""),
                   stampa_estrazioni(self, self.arch, n), f"estrazioni {self.g.codice}")

    def _ultimo(self, azione):
        from .sistemi import ULTIMO, FinestraSviluppo
        dato = ULTIMO.get(self.g.codice)
        if not dato:
            QMessageBox.information(self, "Combinazioni", "Nessun sistema sviluppato in questa sessione: sviluppane "
                                                          "uno (Sistemi → Nuovo) o aprine uno memorizzato (F3).")
            return
        f = FinestraSviluppo(self.arch, dato[0], dato[1], self)
        if azione:
            getattr(f, azione)()
        f.exec()

    def _menu_disattivo(self, nome, voci):
        m = self.menuBar().addMenu(nome)
        m.setToolTipsVisible(True)
        self._riempi_disattivo(m, voci)

    def _selettore(self):
        """Menu in alto a sinistra: scelta tra Pensiero Magico SE e Pensiero Magico EJ."""
        b = QToolButton(self)
        b.setObjectName("selettore")
        b.setText(f"🍀 {self.g.nome_app} ▾")
        icona = QApplication.windowIcon()
        if not icona.isNull():
            b.setIcon(icona)
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setText(f"{self.g.nome_app} ▾")
        b.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(b)
        for g in (SE, EJ):
            a = menu.addAction(f"{g.nome_app} — {g.nome}")
            a.setCheckable(True)
            a.setChecked(g.codice == self.g.codice)
            a.triggered.connect(lambda _=False, c=g.codice: self.cambia_programma(c))
        b.setMenu(menu)
        self.menuBar().setCornerWidget(b, Qt.TopLeftCorner)
        self.selettore = b

    def cambia_programma(self, codice: str):
        if codice == self.g.codice:
            return
        if self.scaricatore and self.scaricatore.isRunning():
            QMessageBox.information(self, "Attendi", "È in corso un aggiornamento da Internet: riprova tra poco.")
            return
        apri_programma(codice)
        self.close()

    def _menu(self):
        mb = self.menuBar()
        self._selettore()
        self._menu_sistemi()
        self._menu_statistiche()
        for nome, voci in MENU_DISATTIVI:
            self._menu_disattivo(nome, voci)
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
        self._azione(m, f"Scarica archivio completo dal {self.g.prima_estrazione.year}",
                     lambda: self.apri_internet(True))
        if not self.g.is_ej:
            self._azione(m, "★ Aggiorna i vincitori del 6 (per i concorsi che mancano)", self.vincitori_sei)
        m.addSeparator()
        self.a_avvio = self._azione(m, "Aggiorna automaticamente all'avvio", self._cambia_avvio)
        self.a_avvio.setCheckable(True)
        self.a_avvio.setChecked(self.arch.leggi_impostazione("aggiorna_avvio", "1") == "1")

        self.m_analisi = mb.addMenu("A&nalisi")
        self.m_analisi.aboutToShow.connect(self._menu_analisi)
        self._menu_analisi()

        m = mb.addMenu("&Magico Pensiero")
        cosa = "la cinquina e gli Euronumeri" if self.g.is_ej else "le 3 sestine"
        self._azione(m, f"✨ Genera {cosa} Magico Pensiero", self.genera)
        self._azione(m, f"Come sono nate le {self.g.nome_comb_pl} (spiegazione)...", self.spiegazione)
        self._azione(m, "🤖 Magico Pensiero + intelligenza artificiale (Gemini o Claude)...", self.claude)
        self._azione(m, "💡 Suggerimenti AI: un piccolo sistema per intuizione...", self.suggerimenti_ai)
        m.addSeparator()
        self._azione(m, "Impostazioni dell'algoritmo...", self.impostazioni_magico)
        self._azione(m, "Verifica storica (previsioni su quanto già avvenuto)...", self.verifica_magico)
        self._azione(m, "Storico delle previsioni...", self.storico_magico)
        self._azione(m, "📈 Analisi delle previsioni e apprendimento...", self.apprendimento)
        m.addSeparator()
        self._azione(m, "🧪 Laboratorio: la casualità è davvero casuale?...", self.laboratorio)

        self._menu_stampe()
        for nome in MENU_VUOTI_DOPO:
            self._menu_vuoto(nome)
        m = mb.addMenu("&Help")
        self._azione(m, f"Informazioni su {self.g.nome_app}", self.informazioni)

    # -------------------------------------------------------------- centro
    def _centro(self):
        w = SfondoHome(self.g)
        esterno = QVBoxLayout(w)
        esterno.addStretch()
        h = QHBoxLayout()
        esterno.addLayout(h)
        esterno.addStretch()
        h.setSpacing(40)
        h.addStretch()

        g = self.g
        self.p_sx = Pannello(g.nome, ARANCIO if g.is_ej else VERDE, selezionabile=True, gioco=g)
        self.p_sx.pulsante("📚  Archivio", self.apri_archivio)
        self.p_sx.pulsante("🔍  Analisi", lambda: self.apri_analisi(None))
        self.p_sx.pulsante(f"📋  {g.C(plurale=True)}", self.mie_sestine)
        self.p_sx.pulsante("✔  Tutti", self.p_sx.griglia.seleziona_tutti)
        self.p_sx.pulsante("🟥  Azzera", self.p_sx.griglia.azzera)
        self.p_sx.lato.addStretch()
        self.p_sx.griglia.selezione_cambiata.connect(lambda s: self.l_sel.setText(f"Numeri selezionati: {len(s)}"))

        self.p_dx = Pannello("Magico Pensiero", ARDESIA, selezionabile=False, gioco=g)
        self.p_dx.pulsante("✨  Genera", self.genera)
        self.p_dx.pulsante("❓  Perché", self.spiegazione)
        self.p_dx.pulsante("🤖  AI", self.claude)
        legenda = QLabel()
        if g.is_ej:
            voci = [(COLORI_SESTINE[0], "Cinquina"), ("#1565c0", "Euronumeri")]
        else:
            voci = [(COLORI_SESTINE[i], f"Sestina {i + 1}") for i in range(3)] + \
                   [(COLORE_JOLLY, "Jolly"), (COLORE_SUPERSTAR, "SuperStar")]
        legenda.setText("<br>".join(f"<span style='background:{c};'>&nbsp;&nbsp;&nbsp;&nbsp;</span> {t}"
                                    for c, t in voci))
        self.p_dx.lato.addWidget(legenda)
        self.p_dx.lato.addStretch()
        self.griglia_euro = None
        if g.is_ej:          # griglia dei 12 Euronumeri sotto quella dei numeri
            etichetta = QLabel("<b>Euronumeri</b>")
            self.griglia_euro = Griglia90(selezionabile=False, n=12, colonne=12)
            self.griglia_euro.setFixedSize(360, 34)
            self.p_dx.layout().addWidget(etichetta, 4, 0, 1, 3)
            self.p_dx.layout().addWidget(self.griglia_euro, 5, 0, 1, 3)
        testo = ("La cinquina e gli Euronumeri compariranno qui dopo l'elaborazione." if g.is_ej
                 else "Le 3 sestine compariranno qui dopo l'elaborazione.")
        self.l_sestine = QLabel(testo)
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
            if self.g.is_ej:
                spec = f"  Euro {u.jolly} {u.superstar}"
            else:
                spec = f"  J {u.jolly}" + (f"  SS {u.superstar}" if u.superstar else "")
            self.l_ultima.setText(f"Ultima: conc. {u.concorso}/{u.data.year} del {u.data:%d/%m/%Y} — "
                                  f"{' '.join(map(str, u.sestina))}{spec}")
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
            self._valuta_nuove()

    def _valuta_nuove(self):
        """Dopo ogni aggiornamento dell'archivio: confronta le previsioni con le estrazioni uscite
        e corregge Magico Pensiero (apprendimento)."""
        from ..core import apprendimento
        try:
            nuove = apprendimento.elabora_nuove(self.arch)
        except Exception as ex:     # l'apprendimento non deve mai bloccare il programma
            self.statusBar().showMessage(f"Analisi delle previsioni non riuscita: {ex}", 10000)
            return
        if nuove:
            from .magico import FinestraApprendimento
            FinestraApprendimento(self.arch, nuove, self).exec()

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
        p, _ = QFileDialog.getSaveFileName(self, "Esporta archivio",
                                           f"{self.g.nome.lower()}_{date.today():%Y%m%d}.csv", "CSV (*.csv)")
        if p:
            esporta_csv(self.arch.tutte(), p, self.g)
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
        p, _ = QFileDialog.getSaveFileName(self, "Salva backup",
                                           f"{self.g.cartella}_backup_{date.today():%Y%m%d}.db", "Archivio (*.db)")
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
        self._azione(m, f"📋 Le mie {self.g.nome_comb_pl}: confronto con l'archivio e ricerca...",
                     self.mie_sestine)
        if not self.g.is_ej:
            m.addSeparator()
            self._azione(m, "★ I concorsi con il 6: confronto con l'archivio...", self.analisi_sei)

    def analisi_sei(self):
        from .sei import FinestraSei
        FinestraSei(self.arch, self).exec()

    def vincitori_sei(self):
        from .sei import FinestraVincitori
        FinestraVincitori(self.arch, self).exec()

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
        if self.g.is_ej:
            self.p_dx.griglia.mostra_sestine([s.numeri for s in r.sestine], None, None)
            self.griglia_euro.mostra_euronumeri([r.jolly, r.superstar])
            righe = [f"<i>{origine}</i>",
                     f"<span style='color:{COLORI_SESTINE[0]}'>■</span> Cinquina: "
                     f"<b>{' '.join(f'{n:2d}' for n in r.sestine[0].numeri)}</b>",
                     f"<span style='color:#1565c0'>■</span> Euronumeri: <b>{r.jolly} {r.superstar}</b>"]
            self.l_sestine.setText("<br>".join(righe))
            return
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
                               "Proposta dell'algoritmo" if o == "Algoritmo" else f"Scelta di {o.split(' ')[0]}")

    def suggerimenti_ai(self):
        from .intuizione import FinestraIntuizione
        FinestraIntuizione(self.arch, self, self.nuovo_sistema).exec()

    def claude(self):
        from .claude import FinestraClaude
        dlg = FinestraClaude(self.arch, self)
        dlg.exec()
        if dlg.applicato:
            self.mostra_magico(dlg.applicato, f"Scelta di {getattr(dlg, 'origine_applicata', 'AI')}")

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

    def laboratorio(self):
        from .laboratorio import FinestraLaboratorio
        FinestraLaboratorio(self.arch, self).exec()

    def verifica_magico(self):
        from .magico import FinestraVerifica
        FinestraVerifica(self.arch, self).exec()

    def apprendimento(self):
        from .magico import FinestraApprendimento
        FinestraApprendimento(self.arch, parent=self).exec()

    def storico_magico(self):
        from .magico import FinestraStorico
        FinestraStorico(self.arch, self).exec()

    def informazioni(self):
        QMessageBox.about(self, self.g.nome_app, (
            f"<b>{self.g.nome_app}</b> versione {__version__}<br><br>"
            f"Archivio e analisi delle estrazioni del {self.g.nome}.<br>"
            f"Archivio dati: {self.arch.percorso}<br><br>"
            "Le estrazioni sono casuali: nessun programma può garantire vincite. Gioca responsabilmente."))

    # ---------------------------------------------------------- all'avvio
    def _all_avvio(self):
        if self.arch.conta() == 0:
            r = QMessageBox.question(self, "Archivio vuoto", (
                f"L'archivio {self.g.nome} è vuoto.\n\nVuoi scaricare ora da Internet tutte le estrazioni dal "
                f"{self.g.prima_estrazione.year} a oggi?\n"
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
        self.scaricatore = Scaricatore(internet.anni_da_aggiornare(ultima.data if ultima else None, self.g), self.g)
        self.scaricatore.finito.connect(self._aggiornato_in_background)
        self.scaricatore.errore.connect(
            lambda m: self.statusBar().showMessage("Aggiornamento automatico non riuscito (rete?)", 8000))
        self.scaricatore.start()

    def _aggiornato_in_background(self, estrazioni):
        esito = self.arch.unisci(estrazioni)
        self.arch.scrivi_impostazione("ultimo_aggiornamento", date.today().isoformat())
        self.aggiorna_stato()
        if esito.nuove:
            self._valuta_nuove()
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
        if self in FINESTRE:
            FINESTRE.remove(self)
            self.arch.chiudi()
