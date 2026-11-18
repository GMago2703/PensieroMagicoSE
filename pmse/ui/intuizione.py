"""Magico Pensiero → Suggerimenti AI: l'intelligenza artificiale registrata propone per intuizione un
piccolo sistema (tipo, numeri, fisse, condizioni, riduzione), che il programma sviluppa e controlla."""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton, QTextBrowser, QVBoxLayout)

from ..core import claude_ai
from ..core import intuizione as it
from ..core import sistemi as sis
from ..core.db import Archivio
from .schermo import adatta_schermo
from .sistemi import ULTIMO, FinestraSviluppo, GrigliaSistema, leggi_prezzi

CONVERSA_FINTA = None          # solo per le prove automatiche: funzione conversa(messaggi)


def impostazioni_ai(arch: Archivio) -> tuple[str, str, str, str]:
    """(fornitore, chiave, modello, workspace) dell'intelligenza artificiale già registrata."""
    forn = arch.leggi_impostazione(claude_ai.CHIAVE_FORNITORE, "gemini") or "gemini"
    if forn == "gemini":
        return (forn, claude_ai.chiave_gemini(arch),
                arch.leggi_impostazione(claude_ai.CHIAVE_MODELLO_GEMINI) or claude_ai.MODELLI_GEMINI[0][0], "")
    return (forn, claude_ai.chiave_api(arch),
            arch.leggi_impostazione(claude_ai.CHIAVE_MODELLO) or claude_ai.MODELLI[0][0],
            arch.leggi_impostazione(claude_ai.CHIAVE_WORKSPACE) or "")


def _esc(t: str) -> str:
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br>")


class Pensatore(QThread):
    stato = Signal(str)
    finito = Signal(object)
    errore = Signal(str)

    def __init__(self, arch: Archivio, budget: float, indicazione: str, candidate: bool, solo_quadro=False):
        super().__init__()
        self.arch, self.budget, self.indicazione, self.candidate = arch, budget, indicazione, candidate
        self.solo_quadro = solo_quadro
        self.quadro = ""
        self.ctx = None

    def _prepara(self):
        g = self.arch.gioco
        self.stato.emit("Preparo il quadro: analisi delle condizioni sull'archivio...")
        righe = list(self.arch.sestine())
        self.ctx = sis.contesto_da_archivio(self.arch)
        cand = None
        if self.candidate:
            try:
                from ..core import magico, popolarita
                from .magico import carica_impostazioni, punteggi_personalizzati
                storico = self.arch.sestine()
                imp = carica_impostazioni(self.arch)
                r = magico.genera(storico, imp, punteggi_personalizzati(self.arch, imp, storico),
                                  popolarita=popolarita.per_archivio(self.arch))
                cand = [s.numeri for s in r.sestine] + [m[0] for m in r.migliori[:3]]
            except Exception:
                cand = None
        self.quadro = it.quadro(g, righe, self.ctx, self.budget, leggi_prezzi(self.arch), cand, self.indicazione)

    def run(self):
        try:
            self._prepara()
            if self.solo_quadro:
                self.finito.emit(self.quadro)
                return
            g = self.arch.gioco
            if CONVERSA_FINTA is not None:
                conversa = CONVERSA_FINTA
            else:
                forn, chiave, modello, ws = impostazioni_ai(self.arch)
                conversa = it.conversatore(forn, chiave, modello, it.istruzioni(g), ws)
            self.finito.emit(it.proponi(conversa, self.quadro, g, self.ctx, self.budget, leggi_prezzi(self.arch),
                                        avanzamento=self.stato.emit))
        except claude_ai.ErroreClaude as ex:
            self.errore.emit(str(ex))
        except Exception as ex:
            self.errore.emit(f"Errore imprevisto: {ex}")


class FinestraIntuizione(QDialog):
    def __init__(self, arch: Archivio, parent=None, apri_editor=None):
        super().__init__(parent)
        self.arch = arch
        self.g = arch.gioco
        self.apri_editor = apri_editor
        self.thread: Pensatore | None = None
        self.esito: it.Esito | None = None
        self.setWindowTitle(f"💡 Suggerimenti AI – {self.g.nome}")
        adatta_schermo(self, 1150, 760)
        v = QVBoxLayout(self)
        intro = QLabel("<b>L'intuizione dell'intelligenza artificiale.</b> Il programma le mostra un quadro "
                       "sintetico (ultime estrazioni, ritardi, analisi e suggerimenti di ogni condizione, candidate di "
                       "Magico Pensiero, riduzioni pronte) e le chiede di <i>non rifare le analisi</i> ma di seguire "
                       "il suo fiuto e proporti <b>un piccolo sistema</b>: numeri, fisse, condizioni e riduzione. Il "
                       "programma lo sviluppa davvero e, se sfora il budget o non è valido, le fa correggere la "
                       "proposta.")
        intro.setWordWrap(True)
        intro.setStyleSheet("background:#fff8e1; padding:6px; border:1px solid #ffcc80;")
        v.addWidget(intro)
        h = QHBoxLayout()
        self.l_ai = QLabel()
        h.addWidget(self.l_ai)
        b = QPushButton("Cambia intelligenza artificiale o chiave...")
        b.clicked.connect(self._configura)
        h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        h = QHBoxLayout()
        h.addWidget(QLabel("Budget massimo (€)"))
        self.sp_budget = QDoubleSpinBox()
        self.sp_budget.setRange(1, 5000)
        self.sp_budget.setDecimals(2)
        try:
            self.sp_budget.setValue(float(arch.leggi_impostazione(it.CHIAVE_BUDGET) or (40 if self.g.is_ej else 20)))
        except ValueError:
            self.sp_budget.setValue(20)
        h.addWidget(self.sp_budget)
        h.addSpacing(12)
        h.addWidget(QLabel("Una tua indicazione (facoltativa)"))
        self.e_ind = QLineEdit()
        self.e_ind.setPlaceholderText("es. metti il 7 tra le fisse, preferisco una garanzia del 4, solo numeri alti...")
        h.addWidget(self.e_ind, 1)
        self.cb_cand = QCheckBox("con le candidate di Magico Pensiero")
        self.cb_cand.setChecked(True)
        h.addWidget(self.cb_cand)
        v.addLayout(h)
        h = QHBoxLayout()
        self.b_chiedi = QPushButton("✨ Chiedi un'intuizione")
        f = self.b_chiedi.font()
        f.setBold(True)
        f.setPointSize(11)
        self.b_chiedi.setFont(f)
        self.b_chiedi.setMinimumHeight(36)
        self.b_chiedi.clicked.connect(self.chiedi)
        h.addWidget(self.b_chiedi)
        self.b_quadro = QPushButton("Mostra il quadro che verrà inviato")
        self.b_quadro.clicked.connect(self.mostra_quadro)
        h.addWidget(self.b_quadro)
        h.addStretch()
        v.addLayout(h)
        self.barra = QProgressBar()
        self.barra.setRange(0, 0)
        self.barra.setVisible(False)
        v.addWidget(self.barra)
        self.l_stato = QLabel()
        self.l_stato.setStyleSheet("color:#555")
        v.addWidget(self.l_stato)
        corpo = QHBoxLayout()
        sx = QVBoxLayout()
        self.griglia = GrigliaSistema(self.g.n)
        self.griglia.setEnabled(False)
        self.griglia.setFixedSize(380, 34 * self.g.decine + 2)
        sx.addWidget(self.griglia)
        self.l_sint = QLabel()
        self.l_sint.setWordWrap(True)
        self.l_sint.setMaximumWidth(380)
        sx.addWidget(self.l_sint)
        sx.addStretch()
        corpo.addLayout(sx)
        self.testo = QTextBrowser()
        self.testo.setHtml("<p>Imposta il budget e premi <b>Chiedi un'intuizione</b>. Ogni richiesta può dare "
                           "un sistema diverso: è proprio un'intuizione.</p>")
        corpo.addWidget(self.testo, 1)
        v.addLayout(corpo, 1)
        h = QHBoxLayout()
        self.b_colonne = QPushButton("📋 Vedi le colonne (memorizza, stampa, spoglio)...")
        self.b_colonne.clicked.connect(self.vedi_colonne)
        self.b_editor = QPushButton("✏ Apri nell'editor dei sistemi")
        self.b_editor.clicked.connect(self.apri_nell_editor)
        for b in (self.b_colonne, self.b_editor):
            b.setEnabled(False)
            h.addWidget(b)
        h.addStretch()
        b = QPushButton("Chiudi")
        b.clicked.connect(self.reject)
        h.addWidget(b)
        v.addLayout(h)
        self._aggiorna_ai()

    # ---------------------------------------------------------------- AI registrata
    def _aggiorna_ai(self):
        forn, chiave, modello, _ = impostazioni_ai(self.arch)
        nome = "Gemini (Google)" if forn == "gemini" else "Claude (Anthropic)"
        stato = "" if chiave else " – <span style='color:#b71c1c'>chiave non impostata</span>"
        self.l_ai.setText(f"Intelligenza artificiale: <b>{nome}</b>, modello {modello}{stato}")

    def _configura(self):
        from .claude import FinestraClaude
        FinestraClaude(self.arch, self).exec()
        self._aggiorna_ai()

    # ---------------------------------------------------------------- richiesta
    def _avvia(self, solo_quadro: bool):
        if self.arch.conta() < 100:
            QMessageBox.information(self, "Suggerimenti AI", "Servono almeno 100 estrazioni in archivio.")
            return False
        if not solo_quadro and CONVERSA_FINTA is None and not impostazioni_ai(self.arch)[1]:
            QMessageBox.information(self, "Suggerimenti AI", "Imposta prima la chiave dell'intelligenza "
                                                             "artificiale (pulsante «Cambia intelligenza artificiale "
                                                             "o chiave»).")
            return False
        self.arch.scrivi_impostazione(it.CHIAVE_BUDGET, str(self.sp_budget.value()))
        self.thread = Pensatore(self.arch, self.sp_budget.value(), self.e_ind.text(), self.cb_cand.isChecked(),
                                solo_quadro)
        self.thread.stato.connect(self.l_stato.setText)
        self.thread.errore.connect(self._errore)
        self.thread.finito.connect(self._quadro if solo_quadro else self._risposta)
        for b in (self.b_chiedi, self.b_quadro, self.b_colonne, self.b_editor):
            b.setEnabled(False)
        self.barra.setVisible(True)
        self.thread.start()
        return True

    def chiedi(self):
        if self._avvia(False):
            self.testo.setHtml("<p>L'intelligenza artificiale sta guardando il quadro e seguendo il suo fiuto... "
                               "(di solito meno di un minuto)</p>")

    def mostra_quadro(self):
        self._avvia(True)

    def _fine(self):
        self.barra.setVisible(False)
        self.b_chiedi.setEnabled(True)
        self.b_quadro.setEnabled(True)
        self.l_stato.setText("")

    def _errore(self, msg):
        self._fine()
        self.testo.setHtml(f"<p style='color:#b71c1c'><b>Errore:</b> {_esc(msg)}</p>")

    def _quadro(self, testo):
        self._fine()
        d = QDialog(self)
        d.setWindowTitle("Quadro inviato all'intelligenza artificiale")
        adatta_schermo(d, 950, 700)
        lay = QVBoxLayout(d)
        t = QPlainTextEdit(it.istruzioni(self.g) + "\n\n" + "=" * 80 + "\n\n" + testo)
        t.setReadOnly(True)
        lay.addWidget(t)
        d.exec()

    def _risposta(self, e: it.Esito):
        self._fine()
        self.esito = e
        p, s = e.proposta, e.proposta.sistema
        self.griglia.imposta(s.numeri, s.fisse)
        euro = f"{e.costo:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        self.l_sint.setText(f"<b>{_esc(p.titolo) or 'Sistema'}</b><br>{sis.TIPI.get(s.tipo, s.tipo)}<br>"
                            f"{len(s.numeri)} numeri, {len(s.fisse)} fisse → <b>{len(s.colonne)} colonne</b>, "
                            f"{euro} €")
        html = [f"<h3>💡 {_esc(p.titolo) or 'La sua intuizione'}</h3>",
                f"<p>{_esc(p.intuizione)}</p>",
                "<h4>Il sistema</h4><pre style='font-family:Consolas'>" + _esc(s.descrizione()) + "</pre>",
                f"<p><b>{len(s.colonne)} colonne</b> – costo {euro} € (integrale "
                f"{sis._migliaia(int(s.info.get('integrale', 0)))}, possibili "
                f"{sis._migliaia(int(s.info.get('possibili', 0)))})</p>"]
        for titolo, t in (("Perché questi numeri", p.perche_numeri), ("Perché queste condizioni", p.perche_condizioni),
                          ("Perché questa riduzione", p.perche_riduzione), ("Affidabilità", p.affidabilita)):
            if t:
                html.append(f"<h4>{titolo}</h4><p>{_esc(t)}</p>")
        if e.correzioni:
            html.append("<p style='color:#555'><b>Correzioni chieste dal programma:</b><br>" +
                        "<br>".join("• " + _esc(c) for c in e.correzioni) + "</p>")
        if p.avvisi:
            html.append("<p style='color:#8d6e63'>" + "<br>".join("• " + _esc(a) for a in p.avvisi) + "</p>")
        html.append(f"<p style='color:#777; font-size:10px'>Modello {e.modello} – token inviati {e.token_ingresso:,}, "
                    f"ricevuti {e.token_uscita:,} – {e.secondi:.0f} s. Un'intuizione non cambia le probabilità: "
                    "gioca con moderazione.</p>".replace(",", "."))
        self.testo.setHtml("".join(html))
        ULTIMO[self.g.codice] = (s, e.sviluppo.possibili_colonne)
        self.b_colonne.setEnabled(True)
        self.b_editor.setEnabled(self.apri_editor is not None)

    # ---------------------------------------------------------------- dopo
    def vedi_colonne(self):
        if self.esito:
            s = self.esito.proposta.sistema
            FinestraSviluppo(self.arch, s, self.esito.sviluppo.possibili_colonne, self).exec()

    def apri_nell_editor(self):
        if self.esito and self.apri_editor:
            s = sis.Sistema.da_json(self.esito.proposta.sistema.a_json())
            self.accept()
            self.apri_editor(s.tipo, s)

    def closeEvent(self, ev):
        if self.thread and self.thread.isRunning():
            ev.ignore()
            return
        super().closeEvent(ev)

    def reject(self):
        if self.thread and self.thread.isRunning():
            return
        super().reject()
