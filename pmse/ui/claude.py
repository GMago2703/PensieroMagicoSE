"""Finestra "Magico Pensiero + intelligenza artificiale": invia il dossier a Claude (Anthropic) oppure a
Gemini (Google) e mostra la sua scelta."""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                               QProgressBar, QPushButton, QTextBrowser, QVBoxLayout)

from ..core import claude_ai, laboratorio, magico
from ..core.db import Archivio
from .griglia import COLORE_JOLLY, COLORI_SESTINE, Griglia90
from .magico import carica_impostazioni, punteggi_personalizzati
from .schermo import adatta_schermo

INFO_GEMINI = (
    "Per far intervenire Gemini serve una <b>chiave API di Google</b>: 1) apri <b>aistudio.google.com</b> e "
    "accedi con il tuo account Google; 2) nel menu a sinistra apri <b>API keys</b> (Dashboard → API keys) e "
    "premi <b>Create API key</b>; 3) copia la chiave, incollala qui sotto e premi <b>Prova la chiave</b>. "
    "Il livello gratuito non richiede carta di credito ma ha un numero limitato di richieste al giorno; il "
    "modello più potente può richiedere il piano a pagamento. "
    "La chiave resta salvata solo su questo computer, separatamente per Pensiero Magico SE ed EJ.")

INFO_CHIAVE = (
    "Per far intervenire Claude serve una <b>chiave API</b> personale (a pagamento, separata dall'abbonamento "
    "a claude.ai): 1) accedi a <b>platform.claude.com</b> e acquista del credito (Settings → Billing); "
    "2) apri <b>platform.claude.com/settings/keys</b> → <b>Create key</b>, dai un nome, scegli la scadenza e "
    "<b>lega la chiave a un workspace</b> (es. Default) così non serve l'ID workspace; 3) copia la chiave "
    "(inizia con <b>sk-ant-</b>), incollala qui sotto e premi <b>Prova la chiave</b>. "
    "La chiave resta salvata solo su questo computer, separatamente per Pensiero Magico SE ed EJ.")


class Interrogatore(QThread):
    finito = Signal(object)
    errore = Signal(str)

    def __init__(self, chiave, modello, dossier, gia_uscite, m, limiti, workspace="", gioco=None,
                 fornitore="claude"):
        super().__init__()
        self.args = (chiave, modello, dossier, gia_uscite, m, limiti)
        self.workspace = workspace
        self.gioco = gioco
        self.fornitore = fornitore

    def run(self):
        try:
            if self.fornitore == "gemini":
                self.finito.emit(claude_ai.chiedi_a_gemini(*self.args, g=self.gioco))
            else:
                self.finito.emit(claude_ai.chiedi_a_claude(*self.args, workspace=self.workspace, g=self.gioco))
        except claude_ai.ErroreClaude as ex:
            self.errore.emit(str(ex))
        except Exception as ex:   # qualunque imprevisto di rete o di formato
            self.errore.emit(f"Errore imprevisto: {ex}")


class FinestraClaude(QDialog):
    def __init__(self, arch: Archivio, parent=None):
        super().__init__(parent)
        self.arch = arch
        self.thread = None
        self.risposta: claude_ai.RispostaClaude | None = None
        self.base: magico.RisultatoMagico | None = None
        self.applicato = None
        self.setWindowTitle(f"Magico Pensiero {arch.gioco.nome} + intelligenza artificiale")
        adatta_schermo(self, 1150, 760)
        v = QVBoxLayout(self)

        hf = QHBoxLayout()
        hf.addWidget(QLabel("<b>Intelligenza artificiale:</b>"))
        self.c_fornitore = QComboBox()
        self.c_fornitore.addItem("Gemini (Google)", "gemini")
        self.c_fornitore.addItem("Claude (Anthropic)", "claude")
        scelto = arch.leggi_impostazione(claude_ai.CHIAVE_FORNITORE, "gemini")
        self.c_fornitore.setCurrentIndex(max(self.c_fornitore.findData(scelto), 0))
        hf.addWidget(self.c_fornitore)
        hf.addStretch()
        v.addLayout(hf)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setStyleSheet("background:#ede7f6; padding:6px; border:1px solid #b39ddb;")
        v.addWidget(self.info)
        h = QHBoxLayout()
        h.addWidget(QLabel("Chiave API:"))
        self.e_chiave = QLineEdit()
        self.e_chiave.setEchoMode(QLineEdit.Password)
        h.addWidget(self.e_chiave, 2)
        b_salva = QPushButton("Salva chiave")
        b_salva.clicked.connect(self._salva_chiave)
        h.addWidget(b_salva)
        b_prova = QPushButton("🔌 Prova la chiave")
        b_prova.clicked.connect(self._prova_chiave)
        h.addWidget(b_prova)
        self.l_ws = QLabel("ID workspace (facoltativo):")
        h.addWidget(self.l_ws)
        self.e_ws = QLineEdit(arch.leggi_impostazione(claude_ai.CHIAVE_WORKSPACE) or "")
        self.e_ws.setPlaceholderText("wrkspc_... solo se richiesto")
        self.e_ws.setMaximumWidth(200)
        h.addWidget(self.e_ws)
        h.addSpacing(20)
        h.addWidget(QLabel("Modello:"))
        self.c_modello = QComboBox()
        h.addWidget(self.c_modello, 2)
        v.addLayout(h)

        h2 = QHBoxLayout()
        g = arch.gioco
        self.b_chiedi = QPushButton()
        f = self.b_chiedi.font()
        f.setBold(True)
        f.setPointSize(11)
        self.b_chiedi.setFont(f)
        self.b_chiedi.setMinimumHeight(38)
        self.b_chiedi.clicked.connect(self.chiedi)
        b_dossier = QPushButton("Mostra i dati che verranno inviati")
        b_dossier.clicked.connect(self._mostra_dossier)
        self.b_applica = QPushButton("✔ Mostra in home e salva nello storico")
        self.b_applica.setEnabled(False)
        self.b_applica.clicked.connect(self._applica)
        h2.addWidget(self.b_chiedi)
        h2.addWidget(b_dossier)
        h2.addStretch()
        h2.addWidget(self.b_applica)
        v.addLayout(h2)
        self.barra = QProgressBar()
        self.barra.setRange(0, 0)
        self.barra.setVisible(False)
        v.addWidget(self.barra)

        h3 = QHBoxLayout()
        sx = QVBoxLayout()
        self.griglia = Griglia90(selezionabile=False, n=g.n)
        self.griglia.setFixedSize(360, 32 * g.decine + 2)
        sx.addWidget(self.griglia)
        self.l_sestine = QLabel()
        self.l_sestine.setFont(QFont("Consolas", 11))
        self.l_sestine.setTextInteractionFlags(Qt.TextSelectableByMouse)
        sx.addWidget(self.l_sestine)
        sx.addStretch()
        h3.addLayout(sx)
        self.testo = QTextBrowser()
        self.testo.setHtml("<p>Scegli l'intelligenza artificiale e premi <b>Chiedi</b>: il programma calcola prima "
                           "la proposta dell'algoritmo, poi invia il dossier all'intelligenza artificiale, che "
                           f"sceglie le {g.nome_comb_pl} definitive.</p>"
                           "<p>Suggerimento: esegui prima la <i>Verifica storica</i> (menu Magico Pensiero): il "
                           "suo esito viene incluso nel dossier e aiuta l'intelligenza artificiale a capire quali indicatori hanno "
                           "funzionato.</p>")
        h3.addWidget(self.testo, 1)
        v.addLayout(h3, 1)
        self.c_fornitore.currentIndexChanged.connect(self._cambia_fornitore)
        self._cambia_fornitore()

    # ------------------------------------------------------------- fornitore
    @property
    def fornitore(self) -> str:
        return self.c_fornitore.currentData()

    @property
    def nome_ai(self) -> str:
        return "Gemini" if self.fornitore == "gemini" else "Claude"

    def _cambia_fornitore(self, *_):
        gem = self.fornitore == "gemini"
        self.arch.scrivi_impostazione(claude_ai.CHIAVE_FORNITORE, self.fornitore)
        self.info.setText(INFO_GEMINI if gem else INFO_CHIAVE)
        self.e_chiave.setText(claude_ai.chiave_gemini(self.arch) if gem else claude_ai.chiave_api(self.arch))
        self.e_chiave.setPlaceholderText("AIza... / chiave di Google AI Studio" if gem else "sk-ant-...")
        self.l_ws.setVisible(not gem)
        self.e_ws.setVisible(not gem)
        self.c_modello.clear()
        for codice, nome in (claude_ai.MODELLI_GEMINI if gem else claude_ai.MODELLI):
            self.c_modello.addItem(nome, codice)
        salvato = self.arch.leggi_impostazione(claude_ai.CHIAVE_MODELLO_GEMINI if gem else claude_ai.CHIAVE_MODELLO)
        if salvato and self.c_modello.findData(salvato) >= 0:
            self.c_modello.setCurrentIndex(self.c_modello.findData(salvato))
        cosa = "cinquina ed Euronumeri" if self.arch.gioco.is_ej else "le 3 sestine"
        self.b_chiedi.setText(f"🤖  Chiedi a {self.nome_ai} {cosa}")

    # ----------------------------------------------------------------- azioni
    def _salva_chiave(self, avvisa: bool = True):
        if self.fornitore == "gemini":
            self.arch.scrivi_impostazione(claude_ai.CHIAVE_GEMINI, self.e_chiave.text().strip())
            self.arch.scrivi_impostazione(claude_ai.CHIAVE_MODELLO_GEMINI, self.c_modello.currentData())
        else:
            self.arch.scrivi_impostazione(claude_ai.CHIAVE_API, self.e_chiave.text().strip())
            self.arch.scrivi_impostazione(claude_ai.CHIAVE_WORKSPACE, self.e_ws.text().strip())
            self.arch.scrivi_impostazione(claude_ai.CHIAVE_MODELLO, self.c_modello.currentData())
        if avvisa:
            QMessageBox.information(self, "Chiave API", "Chiave salvata su questo computer.")

    def _prova_chiave(self):
        from PySide6.QtWidgets import QApplication
        self._salva_chiave(avvisa=False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if self.fornitore == "gemini":
                esito = claude_ai.prova_chiave_gemini(self.e_chiave.text().strip(), self.c_modello.currentData())
            else:
                esito = claude_ai.prova_chiave(self.e_chiave.text().strip(), self.c_modello.currentData(),
                                               self.e_ws.text().strip())
            QMessageBox.information(self, "Prova della chiave", "✔ " + esito)
        except claude_ai.ErroreClaude as ex:
            QMessageBox.warning(self, "Prova della chiave", f"La chiave non funziona ancora:\n\n{ex}")
        finally:
            QApplication.restoreOverrideCursor()

    def _prepara(self) -> str | None:
        storico = self.arch.sestine()
        if len(storico) < 100:
            QMessageBox.warning(self, self.nome_ai, "Servono almeno 100 estrazioni in archivio.")
            return None
        imp = carica_impostazioni(self.arch)
        self.base = magico.genera(storico, imp, punteggi_personalizzati(self.arch, imp, storico))
        self.gia_uscite = {tuple(x[1]) for x in storico}
        self.matrice = magico.matrice(storico)
        from ..core import apprendimento
        return claude_ai.costruisci_dossier(storico, self.base,
                                            self.arch.leggi_impostazione(claude_ai.CHIAVE_VERIFICA),
                                            lezioni=apprendimento.riepilogo_per_claude(self.arch), imp=imp,
                                            laboratorio=self.arch.leggi_impostazione(laboratorio.CHIAVE_LAB))

    def _mostra_dossier(self):
        dossier = self._prepara()
        if dossier is None:
            return
        d = QDialog(self)
        d.setWindowTitle(f"Dati inviati a {self.nome_ai}")
        d.resize(900, 700)
        lay = QVBoxLayout(d)
        t = QPlainTextEdit(claude_ai.istruzioni(self.arch.gioco) + "\n\n" + "=" * 80 + "\n\n" + dossier)
        t.setReadOnly(True)
        t.setFont(QFont("Consolas", 9))
        lay.addWidget(t)
        d.exec()

    def chiedi(self):
        chiave = self.e_chiave.text().strip()
        if not chiave:
            QMessageBox.warning(self, self.nome_ai, "Inserisci prima la chiave API.")
            return
        dossier = self._prepara()
        if dossier is None:
            return
        self._salva_chiave(avvisa=False)
        self.b_chiedi.setEnabled(False)
        self.b_applica.setEnabled(False)
        self.barra.setVisible(True)
        self.testo.setHtml(f"<p>{self.nome_ai} sta studiando l'archivio... (di solito meno di un minuto)</p>")
        self.c_fornitore.setEnabled(False)
        self.nome_usato = self.nome_ai
        self.thread = Interrogatore(chiave, self.c_modello.currentData(), dossier, self.gia_uscite,
                                    self.matrice, self.base.limiti_archivio, self.e_ws.text().strip(),
                                    self.arch.gioco, self.fornitore)
        self.thread.finito.connect(self._risposta)
        self.thread.errore.connect(self._errore)
        self.thread.start()

    def _fine(self):
        self.c_fornitore.setEnabled(True)
        self.b_chiedi.setEnabled(True)
        self.barra.setVisible(False)

    def _errore(self, msg):
        self._fine()
        self.testo.setHtml(f"<p style='color:#b71c1c'><b>Errore:</b> {msg}</p>")

    def _risposta(self, rc: claude_ai.RispostaClaude):
        self._fine()
        self.risposta = rc
        self.b_applica.setEnabled(True)
        g = self.arch.gioco
        if g.is_ej:
            self.griglia.mostra_sestine(rc.sestine, None, None)
            righe = [f"<span style='color:{COLORI_SESTINE[0]}'>■</span> Cinquina: "
                     f"<b>{' '.join(f'{n:2d}' for n in rc.sestine[0])}</b>",
                     f"<span style='color:#1565c0'>■</span> Euronumeri <b>{rc.jolly} {rc.superstar}</b>"]
        else:
            self.griglia.mostra_sestine(rc.sestine, rc.jolly, rc.superstar)
            righe = [f"<span style='color:{COLORI_SESTINE[i]}'>■</span> Sestina {i + 1}: "
                     f"<b>{' '.join(f'{n:2d}' for n in s)}</b>" for i, s in enumerate(rc.sestine)]
            righe.append(f"<span style='color:{COLORE_JOLLY}'>■</span> Jolly <b>{rc.jolly}</b> &nbsp; "
                         f"<span style='color:#b8860b'>■</span> SuperStar <b>{rc.superstar}</b>")
        self.l_sestine.setText("<br>".join(righe))
        esc = lambda t: t.replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br>")   # noqa: E731
        nome = getattr(self, "nome_usato", self.nome_ai)
        html = [f"<h3>La scelta di {nome}</h3>"]
        comuni = rc.in_comune_archivio or [None] * 3
        for i, (s, m, k) in enumerate(zip(rc.sestine, rc.motivazioni + [""] * 3, comuni), 1):
            extra = f" <span style='color:#555'>(max {k} numeri in comune con l'archivio)</span>" if k is not None \
                else ""
            html.append(f"<p><b>{g.C()} {i}: {' '.join(map(str, s))}</b>{extra}<br>{esc(m)}</p>")
        titolo_spec = (f"Euronumeri {rc.jolly} e {rc.superstar}" if g.is_ej
                       else f"Jolly {rc.jolly} e SuperStar {rc.superstar}")
        html.append(f"<p><b>{titolo_spec}</b><br>{esc(rc.jolly_superstar)}</p>")
        html.append(f"<h4>Analisi</h4><p>{esc(rc.analisi)}</p>")
        html.append(f"<h4>Scartati</h4><p>{esc(rc.scartati)}</p>")
        html.append(f"<h4>Affidabilità</h4><p>{esc(rc.affidabilita)}</p>")
        if rc.avvisi:
            html.append("<p style='color:#b71c1c'><b>Attenzione:</b> " + " ".join(map(esc, rc.avvisi)) + "</p>")
        if rc.corretta:
            html.append(f"<p style='color:#555'>La prima risposta di {nome} non rispettava tutte le regole: "
                        "il programma gli ha chiesto di correggerla.</p>")
        if self.base:
            lo, hi = self.base.limiti_archivio
            html.append(f"<p style='color:#555'>Limite di somiglianza con l'archivio applicato: da {lo} a {hi} "
                        "numeri in comune.</p>")
            prop = " | ".join(" ".join(map(str, s.numeri)) for s in self.base.sestine)
            html.append(f"<p style='color:#555'>Proposta di partenza dell'algoritmo: {prop}</p>")
        html.append(f"<p style='color:#777; font-size:10px'>Modello {rc.modello} — token inviati "
                    f"{rc.token_ingresso:,}, ricevuti {rc.token_uscita:,}</p>".replace(",", "."))
        self.testo.setHtml("".join(html))

    def _applica(self):
        if not (self.risposta and self.base):
            return
        r = claude_ai.come_risultato(self.risposta, self.base)
        nome = getattr(self, "nome_usato", self.nome_ai)
        magico.salva_previsione(self.arch, r, origine=f"{nome} ({self.risposta.modello})")
        self.origine_applicata = nome
        self.applicato = r
        self.b_applica.setEnabled(False)
        QMessageBox.information(self, nome, f"La scelta di {nome} è mostrata in home e salvata nello storico "
                                                "delle previsioni.")

    def closeEvent(self, ev):
        if self.thread and self.thread.isRunning():
            QMessageBox.information(self, self.nome_ai, "Attendi la risposta prima di chiudere.")
            ev.ignore()
            return
        super().closeEvent(ev)

    def reject(self):
        if self.thread and self.thread.isRunning():
            return
        super().reject()
