"""Menu "Le mie giocate": elenco delle combinazioni generate e giocate, verifica sull'archivio,
nascondi / mostra, elimina, ricarica nel programma, registra come giocata."""
from __future__ import annotations

from datetime import date, datetime
from html import escape
from math import comb

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QInputDialog, QLabel,
                               QMessageBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
                               QTextBrowser, QVBoxLayout)

from ..core import giocate as gc
from ..core import mie_giocate as mg
from ..core import sistemi as sis
from ..core.db import Archivio
from .giocate import colonna_txt, euro
from .schermo import adatta_schermo
from .stampa import pulsanti_stampa

FILTRI = [("visibili", "Tutte (tranne le nascoste)"), ("generate", "Solo le generate"),
          ("giocate", "Solo le giocate"), ("nascoste", "Le nascoste"), ("tutto", "Proprio tutte")]
MAX_INTEGRALE = 20_000          # colonne oltre le quali un sistema casuale va sviluppato prima di giocarlo


class LavoroVerifica(QThread):
    finito = Signal(object)

    def __init__(self, g, voce, righe, modo, quote, prezzi):
        super().__init__()
        self.args = (g, voce, righe, modo, quote, prezzi)
        self.errore = ""

    def run(self):
        g, voce, righe, modo, quote, prezzi = self.args
        try:
            self.finito.emit(mg.verifica(g, voce, righe, modo, quote, prezzi))
        except Exception as ex:          # noqa: BLE001 – mostrato all'utente
            self.errore = str(ex)
            self.finito.emit(None)


class FinestraMieGiocate(QDialog):
    def __init__(self, arch: Archivio, parent=None, categoria: str | None = None, filtro: str = "visibili"):
        super().__init__(parent)
        self.arch = arch
        self.g = arch.gioco
        self.f = parent                 # finestra principale (per ricaricare nell'editor o in home)
        self.thread = None
        self.verifiche: dict[str, tuple[str, mg.Verifica]] = {}
        self.setWindowTitle(f"🎟 Le mie giocate – {self.g.nome}")
        adatta_schermo(self, 1260, 800)
        v = QVBoxLayout(self)
        h = QHBoxLayout()
        h.addWidget(QLabel("Sezione:"))
        self.c_cat = QComboBox()
        self.c_cat.addItem("Tutte le sezioni", "")
        for c, n in mg.CATEGORIE:
            self.c_cat.addItem(n, c)
        self.c_cat.setCurrentIndex(max(0, self.c_cat.findData(categoria or "")))
        h.addWidget(self.c_cat)
        h.addSpacing(20)
        h.addWidget(QLabel("Mostra:"))
        self.c_filtro = QComboBox()
        for c, n in FILTRI:
            self.c_filtro.addItem(n, c)
        self.c_filtro.setCurrentIndex(max(0, self.c_filtro.findData(filtro)))
        h.addWidget(self.c_filtro)
        h.addStretch()
        leg = QLabel("<span style='background:#c8e6c9'>&nbsp;🎟 Giocata&nbsp;</span> &nbsp; "
                     "<span style='background:#fff8e1'>&nbsp;✨ Generata&nbsp;</span> &nbsp; "
                     "<span style='color:#9e9e9e'><i>nascosta</i></span>")
        h.addWidget(leg)
        v.addLayout(h)
        sp = QSplitter(Qt.Vertical)
        self.t = QTableWidget(0, 6)
        self.t.setHorizontalHeaderLabels(["Creata", "Stato", "Sezione", "Descrizione", "Colonne",
                                          "Dalla creazione a oggi"])
        self.t.verticalHeader().setVisible(False)
        self.t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.t.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.t.setSelectionMode(QAbstractItemView.SingleSelection)
        self.t.itemSelectionChanged.connect(self._dettaglio)
        sp.addWidget(self.t)
        self.dett = QTextBrowser()
        sp.addWidget(self.dett)
        sp.setSizes([420, 330])
        v.addWidget(sp, 1)
        h = QHBoxLayout()
        self.pulsanti = {}
        for chiave, testo, fun in (("dopo", "🔍 Verifica dalla creazione", lambda: self.verifica("dopo")),
                                   ("storico", "📜 Verifica su tutto l'archivio", lambda: self.verifica("storico")),
                                   ("ricarica", "📤 Ricarica nel programma", self.ricarica_voce),
                                   ("registra", "🎟 Registra come giocata", self.registra),
                                   ("simula", "📈 E se l'avessi giocata…", self.simula),
                                   ("nascondi", "🙈 Nascondi", self.nascondi),
                                   ("note", "✏ Nome e note...", self.note),
                                   ("elimina", "🗑 Elimina", self.elimina)):
            b = QPushButton(testo)
            b.clicked.connect(fun)
            h.addWidget(b)
            self.pulsanti[chiave] = b
        h.addStretch()
        v.addLayout(h)
        h = QHBoxLayout()
        self.l_info = QLabel()
        h.addWidget(self.l_info)
        h.addStretch()
        h.addWidget(pulsanti_stampa(self, self._da_stampare))
        b = QPushButton("Chiudi")
        b.clicked.connect(self.reject)
        h.addWidget(b)
        v.addLayout(h)
        self.c_cat.currentIndexChanged.connect(self.ricarica)
        self.c_filtro.currentIndexChanged.connect(self.ricarica)
        self.righe = list(arch.sestine())
        self.quote = gc.Quote(arch)
        from .sistemi import leggi_prezzi
        self.prezzi = leggi_prezzi(arch)
        self.ricarica()

    # ---------------------------------------------------------------- elenco
    def ricarica(self, *_):
        tutte = mg.sincronizza(self.arch)
        cat, filtro = self.c_cat.currentData(), self.c_filtro.currentData()
        voci = [x for x in tutte if not cat or x.categoria == cat]
        conta = (sum(1 for x in voci if not x.giocata), sum(1 for x in voci if x.giocata),
                 sum(1 for x in voci if x.nascosta))
        voci = [x for x in voci if {"visibili": not x.nascosta, "generate": not x.giocata and not x.nascosta,
                                    "giocate": x.giocata, "nascoste": x.nascosta, "tutto": True}[filtro]]
        self.voci = sorted(voci, key=lambda x: x.creata, reverse=True)
        self.l_info.setText(f"Generate: <b>{conta[0]}</b> &nbsp; Giocate: <b>{conta[1]}</b> &nbsp; "
                            f"Nascoste: <b>{conta[2]}</b>")
        self.t.setRowCount(len(self.voci))
        for i, x in enumerate(self.voci):
            try:
                rias = mg.riassunto(self.g, mg.verifica(self.g, x, self.righe, "dopo", None, self.prezzi))
            except Exception:            # noqa: BLE001
                rias = "—"
            celle = [datetime.fromisoformat(x.creata).strftime("%d/%m/%Y %H:%M"),
                     "🎟 Giocata" if x.giocata else "✨ Generata", mg.NOMI.get(x.categoria, x.categoria),
                     x.titolo + (f"  ({x.note})" if x.note else ""),
                     f"{x.n_colonne:,}".replace(",", ".") + (" (integrale)" if x.integrale() else ""), rias]
            for j, c in enumerate(celle):
                it = QTableWidgetItem(c)
                it.setBackground(QColor("#c8e6c9" if x.giocata else "#fff8e1"))
                if x.nascosta:
                    it.setForeground(QColor("#9e9e9e"))
                    f = it.font()
                    f.setItalic(True)
                    it.setFont(f)
                if j == 4:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if j == 5 and "vincite" in c and "nessuna" not in c:
                    it.setForeground(QColor("#1b5e20"))
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                self.t.setItem(i, j, it)
        self.t.resizeColumnsToContents()
        self.t.setColumnWidth(3, min(self.t.columnWidth(3), 420))
        self.t.horizontalHeader().setStretchLastSection(True)
        if self.voci:
            self.t.selectRow(0)
        else:
            self.dett.setHtml("<p>Nessuna combinazione in questa sezione.</p><p style='color:#555'>Si riempie "
                              "da sola: le combinazioni estratte con la macchina, le proposte di Magico Pensiero "
                              "(anche con l'AI), i sistemi sviluppati e le giocate registrate finiscono qui.</p>")
        self._pulsanti()

    def _scelta(self) -> mg.Voce | None:
        i = self.t.currentRow()
        return self.voci[i] if 0 <= i < len(self.voci) else None

    def _pulsanti(self):
        x = self._scelta()
        for b in self.pulsanti.values():
            b.setEnabled(x is not None)
        if x is not None:
            self.pulsanti["nascondi"].setText("👁 Mostra di nuovo" if x.nascosta else "🙈 Nascondi")
            self.pulsanti["registra"].setEnabled(not x.giocata)

    def _dettaglio(self):
        self._pulsanti()
        x = self._scelta()
        if x is None:
            return
        g = self.g
        h = [f"<h3>{escape(x.titolo)}</h3>",
             f"<p><b>{'🎟 Giocata' if x.giocata else '✨ Generata'}</b> – {mg.NOMI.get(x.categoria, '')} – "
             f"creata il {datetime.fromisoformat(x.creata):%d/%m/%Y alle %H:%M}"
             + (f" – primo concorso utile {date.fromisoformat(x.dal):%d/%m/%Y}" if x.dal else "")
             + (" – <i>nascosta</i>" if x.nascosta else "") + "</p>"]
        if x.note:
            h.append(f"<p>📝 {escape(x.note)}</p>")
        if x.giocata:
            gi = next((y for y in gc.carica(self.arch) if y.id == x.giocata_id), None)
            if gi:
                e = gc.esito(g, gi, self.righe, self.quote)
                vinto = gi.vinto_manuale if gi.vinto_manuale is not None else e.vinto
                h.append(f"<p>Nel registro: «{escape(gi.nome)}», {gi.concorsi} concorsi dal "
                         f"{date.fromisoformat(gi.dal):%d/%m/%Y} – spesa {euro(e.spesa)}, vinto {euro(vinto)}"
                         + (f", {e.concorsi_mancanti} concorsi ancora da estrarre" if e.concorsi_mancanti else "")
                         + "</p>")
        ver = self.verifiche.get(x.id)
        if ver:
            h.append(self._html_verifica(x, *ver))
        if x.integrale():
            eu = f" + Euronumeri {' '.join(map(str, x.numeri_extra))}" if x.numeri_extra else ""
            h.append(f"<h4>Numeri del sistema ({len(x.numeri)})</h4><pre>{' '.join(f'{n:2d}' for n in x.numeri)}"
                     f"{eu}</pre><p style='color:#555'>Integrale: {comb(len(x.numeri), g.k):,} colonne"
                     .replace(",", ".") + ". Si verifica con un calcolo esatto, senza sviluppare le colonne.</p>")
        elif x.colonne:
            mostra = x.colonne[:300]
            h.append(f"<h4>Colonne ({len(x.colonne):,})</h4><pre>".replace(",", ".") + "\n".join(
                f"{k + 1:4d}) {colonna_txt(g, c, x.extra[k] if x.extra and k < len(x.extra) else [])}"
                for k, c in enumerate(mostra)) + ("\n..." if len(x.colonne) > 300 else "") + "</pre>")
        else:
            h.append("<p>Le colonne di questo sistema erano troppe per essere salvate: con «Ricarica nel "
                     "programma» si riapre nell'editor e si risviluppa.</p>")
        self.dett.setHtml("".join(h))

    def _html_verifica(self, x, modo, v: mg.Verifica) -> str:
        g = self.g
        titolo = "dalla creazione a oggi" if modo == "dopo" else "su tutto l'archivio"
        if not v.concorsi:
            return f"<h4>Verifica {titolo}</h4><p>Nessun concorso ancora estratto dopo la creazione.</p>"
        t = v.totale
        h = [f"<h4>Verifica {titolo}: {len(v.concorsi)} concorsi "
             f"({v.concorsi[0]:%d/%m/%Y} – {v.concorsi[-1]:%d/%m/%Y})</h4>"]
        if t:
            h.append("<table cellpadding=3 border=1 style='border-collapse:collapse'><tr><th>Categoria</th>"
                     "<th>Volte</th></tr>")
            for c in mg._ordine(g):
                if t.get(c):
                    h.append(f"<tr><td>{gc.nome_categoria(c)}</td><td align=right>{t[c]:,}</td></tr>"
                             .replace(",", "."))
            h.append("</table>")
        else:
            h.append(f"<p>Nessuna vincita: al massimo <b>{v.migliore}</b> punti.</p>")
        h.append(f"<p>Spesa se giocata ogni concorso: {euro(v.spesa)} – vinto con le quote note: "
                 f"<b>{euro(v.vinto)}</b> – saldo "
                 f"<span style='color:{'#2e7d32' if v.vinto >= v.spesa else '#c62828'}'>{euro(v.vinto - v.spesa)}"
                 "</span>" + (f"<br>{v.ignote:,} vincite con quota non nota (concorsi senza quote in archivio)."
                              .replace(",", ".") if v.ignote else "") + "</p>")
        vinc = [(d, c, imp) for d, c, imp in zip(v.concorsi, v.per_concorso, v.importi) if c]
        if vinc:
            h.append("<p><b>Concorsi con vincite</b>" + (" (gli ultimi 150)" if len(vinc) > 150 else "") + ":<br>")
            for d, c, imp in vinc[-150:][::-1]:
                parti = ", ".join(f"{gc.nome_categoria(k)} ×{n}" for k, n in
                                  sorted(c.items(), key=lambda kv: mg._ordine(g).index(kv[0])))
                h.append(f"{d:%d/%m/%Y}: {parti}" + (f" – {euro(imp)}" if imp else "") + "<br>")
            h.append("</p>")
        return "".join(h)

    # ---------------------------------------------------------------- azioni
    def verifica(self, modo):
        x = self._scelta()
        if x is None or (self.thread and self.thread.isRunning()):
            return
        if not x.colonne and not x.numeri:
            QMessageBox.information(self, "Verifica", "Ricarica il sistema e risviluppalo per verificarlo.")
            return
        self.setCursor(Qt.WaitCursor)
        self.pulsanti["dopo"].setEnabled(False)
        self.pulsanti["storico"].setEnabled(False)
        self.thread = LavoroVerifica(self.g, x, self.righe, modo, self.quote, self.prezzi)
        self.in_verifica = (x, modo)
        self.thread.finito.connect(self._verificata)          # metodo: eseguito nel thread della finestra
        self.thread.start()

    def _verificata(self, v):
        x, modo = self.in_verifica
        self.unsetCursor()
        self._pulsanti()
        if v is None:
            QMessageBox.warning(self, "Verifica", f"Verifica non riuscita: {self.thread.errore}")
            return
        self.verifiche[x.id] = (modo, v)
        if self._scelta() is x:
            self._dettaglio()

    def _colonne_giocabili(self, x) -> tuple[list, list] | None:
        if x.colonne:
            return x.colonne, x.extra or [[] for _ in x.colonne]
        if x.numeri:
            n = comb(len(x.numeri), self.g.k)
            if n > MAX_INTEGRALE:
                QMessageBox.information(self, "Sistema", f"L'integrale ha {n:,} colonne: riducilo prima "
                                                         "(Ricarica nel programma → sviluppa).".replace(",", "."))
                return None
            from itertools import combinations
            cols = [list(c) for c in combinations(sorted(x.numeri), self.g.k)]
            return cols, [list(x.numeri_extra) if x.numeri_extra else [] for _ in cols]
        QMessageBox.information(self, "Sistema", "Ricarica il sistema e risviluppalo.")
        return None

    def registra(self):
        x = self._scelta()
        if x is None or x.giocata:
            return
        c = self._colonne_giocabili(x)
        if c is None:
            return
        from .giocate import registra
        gi = registra(self.arch, self, c[0], c[1], x.titolo)
        if gi:
            mg.collega(self.arch, x.id, gi)
            self.ricarica()

    def simula(self):
        x = self._scelta()
        c = self._colonne_giocabili(x) if x else None
        if c:
            from .giocate import FinestraSimulatore
            FinestraSimulatore(self.arch, self, c[0], c[1]).exec()

    def nascondi(self):
        x = self._scelta()
        if x is None:
            return
        mg.modifica(self.arch, x.id, nascosta=not x.nascosta)
        if not x.nascosta and self.c_filtro.currentData() in ("visibili", "generate", "giocate"):
            QMessageBox.information(self, "Nascosta", "La combinazione è nascosta: la ritrovi con «Mostra: Le "
                                                      "nascoste» e la fai tornare con «Mostra di nuovo».")
        self.ricarica()

    def note(self):
        x = self._scelta()
        if x is None:
            return
        titolo, ok = QInputDialog.getText(self, "Nome", "Nome della combinazione:", text=x.titolo)
        if not ok:
            return
        nota, ok = QInputDialog.getText(self, "Note", "Note (facoltative):", text=x.note)
        if ok:
            mg.modifica(self.arch, x.id, titolo=titolo.strip() or x.titolo, note=nota.strip())
            self.ricarica()

    def elimina(self):
        x = self._scelta()
        if x is None:
            return
        anche = False
        if x.giocata:
            r = QMessageBox.question(self, "Elimina", f"«{x.titolo}» è una giocata registrata.\n\nEliminarla anche "
                                                      "dal registro delle giocate (Ricevitoria)?\n"
                                                      "Sì = da entrambi, No = solo da qui",
                                     QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.No)
            if r == QMessageBox.Cancel:
                return
            anche = r == QMessageBox.Yes
        elif QMessageBox.question(self, "Elimina", f"Eliminare «{x.titolo}»?\nSe vuoi solo toglierla dalla vista "
                                                   "usa «Nascondi».") != QMessageBox.Yes:
            return
        if anche:
            gc.elimina(self.arch, x.giocata_id)
        mg.elimina(self.arch, x.id)
        self.verifiche.pop(x.id, None)
        self.ricarica()

    def ricarica_voce(self):
        """Riporta la combinazione nel programma: colonne → memoria della macchina (usabili in verifica,
        registro, editor), sistemi → editor dei sistemi, Magico Pensiero → home."""
        x = self._scelta()
        if x is None:
            return
        g = self.g
        if x.previsione and self.f is not None and hasattr(self.f, "mostra_previsione"):
            self.f.mostra_previsione(x.previsione)
            QMessageBox.information(self, "Ricaricata", "Le combinazioni sono di nuovo in home.")
            return
        if x.sistema or x.categoria in ("sistemi", "sistemi_casuali") or len(x.colonne) > 10:
            if x.sistema:
                s = sis.Sistema.da_json(x.sistema)
            else:
                nums = x.numeri or sorted({n for c in x.colonne for n in c})
                s = sis.Sistema(tipo="condizionato", gioco=g.codice, numeri=nums, note=x.titolo)
            s.gioco = g.codice
            if self.f is not None and hasattr(self.f, "nuovo_sistema"):
                self.accept()
                self.f.nuovo_sistema(s.tipo, s)
            return
        from .macchina import CASUALI
        CASUALI[g.codice] = {"modo": "sestine", "risultati": [
            {"numeri": list(c), "extra": list(x.extra[k]) if x.extra and k < len(x.extra) else []}
            for k, c in enumerate(x.colonne)]}
        QMessageBox.information(self, "Ricaricata", "Le colonne sono pronte: le trovi con il pulsante «Macchina "
                                                    "dell'estrazione» in Verifica colonne casuali, nel registro "
                                                    "delle giocate, nel simulatore e nell'editor dei sistemi.")

    def _da_stampare(self):
        x = self._scelta()
        if x is None:
            return "Le mie giocate", "Nessuna combinazione scelta.", "le mie giocate"
        doc = QTextBrowser()
        doc.setHtml(self.dett.toHtml())
        return f"{x.titolo} – {self.g.nome}", doc.toPlainText(), "la mia giocata"

    def closeEvent(self, ev):
        if self.thread and self.thread.isRunning():
            ev.ignore()
            return
        super().closeEvent(ev)

    def reject(self):
        if self.thread and self.thread.isRunning():
            return
        super().reject()
