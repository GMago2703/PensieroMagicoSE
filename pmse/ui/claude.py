"""Finestra "Magico Pensiero + Claude": invia il dossier a Claude e mostra la sua scelta."""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                               QProgressBar, QPushButton, QTextBrowser, QVBoxLayout)

from ..core import claude_ai, magico
from ..core.db import Archivio
from .griglia import COLORE_JOLLY, COLORI_SESTINE, Griglia90
from .magico import carica_impostazioni, punteggi_personalizzati

INFO_CHIAVE = (
    "Per far intervenire Claude serve una <b>chiave API</b> personale (a pagamento, separata dall'abbonamento "
    "a claude.ai): 1) accedi a <b>platform.claude.com</b> e acquista del credito (Settings → Billing); "
    "2) apri <b>platform.claude.com/settings/keys</b> → <b>Create key</b>, dai un nome, scegli la scadenza e "
    "<b>lega la chiave a un workspace</b> (es. Default) così non serve l'ID workspace; 3) copia la chiave "
    "(inizia con <b>sk-ant-</b>), incollala qui sotto e premi <b>Prova la chiave</b>. "
    "La chiave resta salvata solo su questo computer.")


class Interrogatore(QThread):
    finito = Signal(object)
    errore = Signal(str)

    def __init__(self, chiave, modello, dossier, gia_uscite, m, limiti, workspace=""):
        super().__init__()
        self.args = (chiave, modello, dossier, gia_uscite, m, limiti)
        self.workspace = workspace

    def run(self):
        try:
            self.finito.emit(claude_ai.chiedi_a_claude(*self.args, workspace=self.workspace))
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
        self.setWindowTitle("Magico Pensiero + Claude (intelligenza artificiale)")
        self.resize(1150, 760)
        v = QVBoxLayout(self)

        info = QLabel(INFO_CHIAVE)
        info.setWordWrap(True)
        info.setStyleSheet("background:#ede7f6; padding:6px; border:1px solid #b39ddb;")
        v.addWidget(info)
        h = QHBoxLayout()
        h.addWidget(QLabel("Chiave API:"))
        self.e_chiave = QLineEdit(claude_ai.chiave_api(arch))
        self.e_chiave.setEchoMode(QLineEdit.Password)
        self.e_chiave.setPlaceholderText("sk-ant-...")
        h.addWidget(self.e_chiave, 2)
        b_salva = QPushButton("Salva chiave")
        b_salva.clicked.connect(self._salva_chiave)
        h.addWidget(b_salva)
        b_prova = QPushButton("🔌 Prova la chiave")
        b_prova.clicked.connect(self._prova_chiave)
        h.addWidget(b_prova)
        h.addWidget(QLabel("ID workspace (facoltativo):"))
        self.e_ws = QLineEdit(arch.leggi_impostazione(claude_ai.CHIAVE_WORKSPACE) or "")
        self.e_ws.setPlaceholderText("wrkspc_... solo se richiesto")
        self.e_ws.setMaximumWidth(200)
        h.addWidget(self.e_ws)
        h.addSpacing(20)
        h.addWidget(QLabel("Modello:"))
        self.c_modello = QComboBox()
        for codice, nome in claude_ai.MODELLI:
            self.c_modello.addItem(nome, codice)
        salvato = arch.leggi_impostazione(claude_ai.CHIAVE_MODELLO)
        if salvato and self.c_modello.findData(salvato) >= 0:
            self.c_modello.setCurrentIndex(self.c_modello.findData(salvato))
        h.addWidget(self.c_modello, 2)
        v.addLayout(h)

        h2 = QHBoxLayout()
        self.b_chiedi = QPushButton("🤖  Chiedi a Claude le 3 sestine")
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
        self.griglia = Griglia90(selezionabile=False)
        self.griglia.setFixedSize(360, 290)
        sx.addWidget(self.griglia)
        self.l_sestine = QLabel()
        self.l_sestine.setFont(QFont("Consolas", 11))
        self.l_sestine.setTextInteractionFlags(Qt.TextSelectableByMouse)
        sx.addWidget(self.l_sestine)
        sx.addStretch()
        h3.addLayout(sx)
        self.testo = QTextBrowser()
        self.testo.setHtml("<p>Premi <b>Chiedi a Claude</b>: il programma calcola prima la proposta "
                           "dell'algoritmo, poi invia il dossier a Claude, che sceglie le sestine definitive.</p>"
                           "<p>Suggerimento: esegui prima la <i>Verifica storica</i> (menu Magico Pensiero): il "
                           "suo esito viene incluso nel dossier e aiuta Claude a capire quali indicatori hanno "
                           "funzionato.</p>")
        h3.addWidget(self.testo, 1)
        v.addLayout(h3, 1)

    # ----------------------------------------------------------------- azioni
    def _salva_chiave(self, avvisa: bool = True):
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
            QMessageBox.warning(self, "Claude", "Servono almeno 100 estrazioni in archivio.")
            return None
        imp = carica_impostazioni(self.arch)
        self.base = magico.genera(storico, imp, punteggi_personalizzati(self.arch, imp, storico))
        self.gia_uscite = {tuple(x[1]) for x in storico}
        self.matrice = magico.matrice(storico)
        from ..core import apprendimento
        return claude_ai.costruisci_dossier(storico, self.base,
                                            self.arch.leggi_impostazione(claude_ai.CHIAVE_VERIFICA),
                                            lezioni=apprendimento.riepilogo_per_claude(self.arch), imp=imp)

    def _mostra_dossier(self):
        dossier = self._prepara()
        if dossier is None:
            return
        d = QDialog(self)
        d.setWindowTitle("Dati inviati a Claude")
        d.resize(900, 700)
        lay = QVBoxLayout(d)
        t = QPlainTextEdit(claude_ai.SISTEMA + "\n\n" + "=" * 80 + "\n\n" + dossier)
        t.setReadOnly(True)
        t.setFont(QFont("Consolas", 9))
        lay.addWidget(t)
        d.exec()

    def chiedi(self):
        chiave = self.e_chiave.text().strip()
        if not chiave:
            QMessageBox.warning(self, "Claude", "Inserisci prima la chiave API.")
            return
        dossier = self._prepara()
        if dossier is None:
            return
        self.arch.scrivi_impostazione(claude_ai.CHIAVE_MODELLO, self.c_modello.currentData())
        if self.arch.leggi_impostazione(claude_ai.CHIAVE_API) != chiave:
            self.arch.scrivi_impostazione(claude_ai.CHIAVE_API, chiave)
        self.b_chiedi.setEnabled(False)
        self.b_applica.setEnabled(False)
        self.barra.setVisible(True)
        self.testo.setHtml("<p>Claude sta studiando l'archivio... (di solito meno di un minuto)</p>")
        self.thread = Interrogatore(chiave, self.c_modello.currentData(), dossier, self.gia_uscite,
                                    self.matrice, self.base.limiti_archivio, self.e_ws.text().strip())
        self.thread.finito.connect(self._risposta)
        self.thread.errore.connect(self._errore)
        self.thread.start()

    def _fine(self):
        self.b_chiedi.setEnabled(True)
        self.barra.setVisible(False)

    def _errore(self, msg):
        self._fine()
        self.testo.setHtml(f"<p style='color:#b71c1c'><b>Errore:</b> {msg}</p>")

    def _risposta(self, rc: claude_ai.RispostaClaude):
        self._fine()
        self.risposta = rc
        self.b_applica.setEnabled(True)
        self.griglia.mostra_sestine(rc.sestine, rc.jolly, rc.superstar)
        righe = [f"<span style='color:{COLORI_SESTINE[i]}'>■</span> Sestina {i + 1}: "
                 f"<b>{' '.join(f'{n:2d}' for n in s)}</b>" for i, s in enumerate(rc.sestine)]
        righe.append(f"<span style='color:{COLORE_JOLLY}'>■</span> Jolly <b>{rc.jolly}</b> &nbsp; "
                     f"<span style='color:#b8860b'>■</span> SuperStar <b>{rc.superstar}</b>")
        self.l_sestine.setText("<br>".join(righe))
        esc = lambda t: t.replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br>")   # noqa: E731
        html = [f"<h3>La scelta di Claude</h3>"]
        comuni = rc.in_comune_archivio or [None] * 3
        for i, (s, m, k) in enumerate(zip(rc.sestine, rc.motivazioni + [""] * 3, comuni), 1):
            extra = f" <span style='color:#555'>(max {k} numeri in comune con l'archivio)</span>" if k is not None \
                else ""
            html.append(f"<p><b>Sestina {i}: {' '.join(map(str, s))}</b>{extra}<br>{esc(m)}</p>")
        html.append(f"<p><b>Jolly {rc.jolly} e SuperStar {rc.superstar}</b><br>{esc(rc.jolly_superstar)}</p>")
        html.append(f"<h4>Analisi</h4><p>{esc(rc.analisi)}</p>")
        html.append(f"<h4>Scartati</h4><p>{esc(rc.scartati)}</p>")
        html.append(f"<h4>Affidabilità</h4><p>{esc(rc.affidabilita)}</p>")
        if rc.avvisi:
            html.append("<p style='color:#b71c1c'><b>Attenzione:</b> " + " ".join(map(esc, rc.avvisi)) + "</p>")
        if rc.corretta:
            html.append("<p style='color:#555'>La prima risposta di Claude non rispettava tutte le regole: "
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
        magico.salva_previsione(self.arch, r, origine=f"Claude ({self.risposta.modello})")
        self.applicato = r
        self.b_applica.setEnabled(False)
        QMessageBox.information(self, "Claude", "Sestine di Claude mostrate in home e salvate nello storico "
                                                "delle previsioni.")

    def closeEvent(self, ev):
        if self.thread and self.thread.isRunning():
            QMessageBox.information(self, "Claude", "Attendi la risposta di Claude prima di chiudere.")
            ev.ignore()
            return
        super().closeEvent(ev)

    def reject(self):
        if self.thread and self.thread.isRunning():
            return
        super().reject()
