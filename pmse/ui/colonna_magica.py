"""Magico Pensiero → Colonna magica: una colonna con un numero per ogni fonte (casuale, Magico Pensiero,
Magico Pensiero + AI, AI, il più e il meno probabile secondo le condizioni), con la provenienza di ognuno."""
from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QProgressBar,
                               QPushButton, QTextBrowser, QVBoxLayout)

from ..core import claude_ai, magico, popolarita
from ..core import colonna_magica as cm
from ..core import intuizione as it
from ..core import mie_giocate as mg
from ..core import sistemi as sis
from ..core.db import Archivio
from .intuizione import impostazioni_ai
from .magico import carica_impostazioni, punteggi_personalizzati
from .schermo import adatta_schermo

CONVERSA_FINTA = None          # solo per le prove automatiche: funzione conversa(messaggi)
COLORI = {"casuale": "#6d4c41", "magico": "#2e7d32", "magico_ai": "#00838f", "ai": "#1565c0",
          "piu_probabile": "#ef6c00", "meno_probabile": "#6a1b9a"}


class Lavoro(QThread):
    finito = Signal(object)
    errore = Signal(str)
    stato = Signal(str)

    def __init__(self, arch: Archivio, usa_ai: bool, tabella):
        super().__init__()
        self.arch, self.usa_ai, self.tabella = arch, usa_ai, tabella
        self.nuova_tabella = None

    def run(self):
        try:
            arch, g = self.arch, self.arch.gioco
            storico = arch.sestine()
            if len(storico) < (100 if self.usa_ai else 30):
                raise ValueError(f"Servono almeno {100 if self.usa_ai else 30} estrazioni in archivio.")
            self.stato.emit("Magico Pensiero sta analizzando l'archivio...")
            imp = carica_impostazioni(arch)
            base = magico.genera(storico, imp, punteggi_personalizzati(arch, imp, storico),
                                 popolarita=popolarita.per_archivio(arch))
            if self.tabella is None:
                self.stato.emit("Studio delle condizioni su tutto l'archivio...")
                self.tabella = cm.Tabella(g, sis.contesto_da_archivio(arch))
            self.nuova_tabella = self.tabella
            ai_magico = ai_sola = None
            if self.usa_ai:
                if CONVERSA_FINTA is not None:
                    conversa, nome = CONVERSA_FINTA, "AI di prova"
                else:
                    forn, chiave, modello, ws = impostazioni_ai(arch)
                    conversa = it.conversatore(forn, chiave, modello, cm.sistema_ai(g), ws,
                                               avviso=self.stato.emit) if chiave else None
                if conversa is not None:
                    from ..core import apprendimento, laboratorio
                    dossier = None

                    def mag(esclusi):
                        nonlocal dossier
                        self.stato.emit("L'AI sceglie un numero con il dossier di Magico Pensiero...")
                        if dossier is None:
                            dossier = claude_ai.costruisci_dossier(
                                storico, base, arch.leggi_impostazione(claude_ai.CHIAVE_VERIFICA),
                                lezioni=apprendimento.riepilogo_per_claude(arch), imp=imp,
                                laboratorio=arch.leggi_impostazione(laboratorio.CHIAVE_LAB))
                        return cm.chiedi_numero(conversa, dossier, g, esclusi)

                    def sola(esclusi):
                        self.stato.emit("L'AI sceglie un numero guardando solo l'archivio...")
                        return cm.chiedi_numero(conversa, cm.testo_ai_sola(g, storico), g, esclusi)
                    ai_magico, ai_sola = mag, sola
            self.stato.emit("Studio il numero più e meno probabile secondo le condizioni...")
            self.finito.emit(cm.genera(g, self.tabella, base, ai_magico, ai_sola))
        except (claude_ai.ErroreClaude, ValueError) as ex:
            self.errore.emit(str(ex))
        except Exception as ex:          # noqa: BLE001 – mostrato all'utente
            self.errore.emit(f"Errore imprevisto: {ex}")


class FinestraColonnaMagica(QDialog):
    def __init__(self, arch: Archivio, parent=None):
        super().__init__(parent)
        self.arch = arch
        self.g = arch.gioco
        self.f = parent
        self.thread: Lavoro | None = None
        self.tabella = None
        self.risultato: cm.ColonnaMagica | None = None
        self.voce: mg.Voce | None = None
        self.setWindowTitle(f"🎩 Colonna magica – {self.g.nome}")
        adatta_schermo(self, 980, 760)
        v = QVBoxLayout(self)
        quanti = self.g.k
        fonti = " + ".join(f"{cm.ICONA_FONTE[c]} {cm.NOME_FONTE[c].lower()}" for c in cm.fonti_del_gioco(self.g))
        extra = (" Nell'Eurojackpot la cinquina ha 5 numeri: l'AI da sola non c'è (c'è già quella con Magico "
                 "Pensiero) e gli Euronumeri sono quelli di Magico Pensiero." if self.g.is_ej else "")
        intro = QLabel(f"<b>Una colonna di {quanti} numeri, ognuno con la sua provenienza:</b> {fonti}. "
                       "«Più/meno probabile» vuol dire: il numero che rende la colonna più (o meno) tipica secondo "
                       "<i>tutte</i> le condizioni (somma, pari/dispari, consecutivi, decine, distanze, ritardi...) "
                       "calcolate sulle estrazioni reali. Non è la probabilità di vincere, uguale per tutte le "
                       "colonne." + extra)
        intro.setWordWrap(True)
        v.addWidget(intro)
        h = QHBoxLayout()
        forn, chiave, modello, _ = impostazioni_ai(arch)
        nome = "Gemini" if forn == "gemini" else "Claude"
        self.cb_ai = QCheckBox(f"Interroga l'intelligenza artificiale ({nome}, {modello})")
        self.cb_ai.setChecked(bool(chiave))
        self.cb_ai.setEnabled(bool(chiave))
        h.addWidget(self.cb_ai)
        if not chiave:
            l = QLabel("<span style='color:#b71c1c'>chiave non impostata (Magico Pensiero → intelligenza "
                       "artificiale): i numeri dell'AI saranno sostituiti</span>")
            h.addWidget(l)
        h.addStretch()
        self.b_gen = QPushButton("🎩 Genera la colonna magica")
        self.b_gen.setDefault(True)
        self.b_gen.clicked.connect(self.genera)
        h.addWidget(self.b_gen)
        v.addLayout(h)
        self.barra = QProgressBar()
        self.barra.setRange(0, 0)
        self.barra.setVisible(False)
        v.addWidget(self.barra)
        self.l_stato = QLabel()
        v.addWidget(self.l_stato)
        self.testo = QTextBrowser()
        self.testo.setHtml("<p style='color:#555'>Premi «Genera la colonna magica». Ogni generazione si salva da "
                           "sola in <i>Le mie giocate → Colonna magica</i>, dove puoi analizzarla, verificarla "
                           "con l'archivio o registrarla come giocata.</p>")
        v.addWidget(self.testo, 1)
        h = QHBoxLayout()
        self.b_reg = QPushButton("🎟 Registra come giocata")
        self.b_reg.clicked.connect(self.registra)
        self.b_mie = QPushButton("📚 Apri in Le mie giocate")
        self.b_mie.clicked.connect(self.apri_mie)
        self.b_copia = QPushButton("📋 Copia")
        self.b_copia.clicked.connect(self.copia)
        for b in (self.b_reg, self.b_mie, self.b_copia):
            b.setEnabled(False)
            h.addWidget(b)
        h.addStretch()
        b = QPushButton("Chiudi")
        b.clicked.connect(self.reject)
        h.addWidget(b)
        v.addLayout(h)

    # ------------------------------------------------------------------ generazione
    def genera(self):
        if self.thread and self.thread.isRunning():
            return
        self.b_gen.setEnabled(False)
        for b in (self.b_reg, self.b_mie, self.b_copia):
            b.setEnabled(False)
        self.barra.setVisible(True)
        self.thread = Lavoro(self.arch, self.cb_ai.isChecked(), self.tabella)
        self.thread.stato.connect(self.l_stato.setText)
        self.thread.finito.connect(self._fatto)
        self.thread.errore.connect(self._errore)
        self.thread.start()

    def _chiudi_attesa(self):
        self.barra.setVisible(False)
        self.l_stato.setText("")
        self.b_gen.setEnabled(True)

    def _errore(self, msg):
        self._chiudi_attesa()
        QMessageBox.warning(self, "Colonna magica", msg)

    def _fatto(self, r: cm.ColonnaMagica):
        self._chiudi_attesa()
        self.tabella = self.thread.nuova_tabella or self.tabella
        self.risultato = r
        try:
            self.voce = mg.aggiungi_colonna_magica(self.arch, r)
        except Exception:            # noqa: BLE001 – il salvataggio non deve impedire di vedere il risultato
            self.voce = None
        for b in (self.b_reg, self.b_copia):
            b.setEnabled(True)
        self.b_mie.setEnabled(self.voce is not None)
        self.testo.setHtml(self._html(r))

    def _html(self, r: cm.ColonnaMagica) -> str:
        h = [f"<h2>🎩 Colonna magica: <span style='color:#1b5e20'>{' &nbsp; '.join(f'{n:2d}' for n in r.colonna)}"
             "</span></h2>"]
        if r.euronumeri:
            h.append(f"<p>Euronumeri suggeriti da Magico Pensiero: <b>{r.euronumeri[0]} {r.euronumeri[1]}</b></p>")
        h.append("<table cellpadding=6 cellspacing=4 width='100%'>")
        for n in r.numeri:
            col = COLORI.get(n.fonte, "#555")
            sost = " <i style='color:#b71c1c'>(sostituito)</i>" if n.sostituito else ""
            h.append(f"<tr><td bgcolor='{col}' align=center width=60><font color='white' size=6><b>{n.numero}</b>"
                     f"</font></td><td bgcolor='#f5f5f5' width='28%'><b>{cm.ICONA_FONTE[n.fonte]} "
                     f"{escape(cm.NOME_FONTE[n.fonte])}</b>{sost}</td><td bgcolor='#f5f5f5'>{escape(n.nota)}"
                     "</td></tr>")
        h.append("</table>")
        if any(n.sostituito for n in r.numeri):
            h.append("<p style='color:#b71c1c'>Almeno un numero dell'intelligenza artificiale non è arrivato e "
                     "è stato sostituito: la scheda spiega con cosa e perché.</p>")
        h.append("<p style='color:#555'>I numeri del lotto sono casuali: la colonna magica è un modo di "
                 "combinare più punti di vista, non una previsione sicura.</p>")
        return "".join(h)

    # ------------------------------------------------------------------ azioni
    def _testo_colonna(self) -> str:
        r = self.risultato
        righe = [f"Colonna magica – {self.g.nome}: {' '.join(map(str, r.colonna))}"]
        if r.euronumeri:
            righe[0] += f" + Euronumeri {r.euronumeri[0]} {r.euronumeri[1]}"
        righe += [f"{n.numero:2d}  {cm.NOME_FONTE[n.fonte]}: {n.nota}" for n in r.numeri]
        return "\n".join(righe)

    def copia(self):
        if self.risultato:
            QApplication.clipboard().setText(self._testo_colonna())

    def registra(self):
        r = self.risultato
        if r is None:
            return
        from .giocate import registra
        extra = [list(r.euronumeri)] if r.euronumeri else [[]]
        gi = registra(self.arch, self, [r.colonna], extra, "Colonna magica")
        if gi and self.voce is not None:
            mg.collega(self.arch, self.voce.id, gi)

    def apri_mie(self):
        from .mie_giocate import FinestraMieGiocate
        FinestraMieGiocate(self.arch, self.f, "colonna_magica").exec()

    def closeEvent(self, ev):
        if self.thread and self.thread.isRunning():
            ev.ignore()
            return
        super().closeEvent(ev)

    def reject(self):
        if self.thread and self.thread.isRunning():
            return
        super().reject()
