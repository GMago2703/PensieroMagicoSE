"""Menu Ricevitoria: registro delle giocate (con spoglio automatico e bilancio) e simulatore
"E se avessi giocato…"."""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QAbstractItemView, QDateEdit, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout,
                               QHeaderView, QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox, QPlainTextEdit,
                               QProgressBar, QPushButton, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem,
                               QTextBrowser, QVBoxLayout, QWidget)

from ..core import giocate as gc
from ..core import sistemi as sis
from ..core.db import Archivio
from ..core.testo import leggi_riga
from .schermo import adatta_schermo
from .stampa import pulsanti_stampa


def euro(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{x:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _qd(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def _d(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


def colonna_txt(g, c, e) -> str:
    s = " ".join(f"{x:2d}" for x in c)
    if g.is_ej and e:
        return s + "  + " + " ".join(map(str, e))
    if e:
        return s + f"   SuperStar {e[0]}"
    return s


# ------------------------------------------------------------------ editor delle colonne (comune)
class EditorColonne(QWidget):
    """Casella di testo con le colonne (una per riga) e i pulsanti per prenderle da altre parti del
    programma, senza copia-incolla."""

    def __init__(self, arch: Archivio, parent=None):
        super().__init__(parent)
        self.arch = arch
        self.g = arch.gioco
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        h = QHBoxLayout()
        h.addWidget(QLabel("Prendi le colonne da:"))
        for testo, fun in (("🎱 Macchina dell'estrazione", self.da_macchina),
                           ("📋 Ultimo sistema sviluppato", self.da_ultimo_sistema),
                           ("💾 Sistema memorizzato...", self.da_sistema_salvato),
                           ("✨ Magico Pensiero", self.da_magico)):
            b = QPushButton(testo)
            b.clicked.connect(fun)
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)
        self.ed = QPlainTextEdit()
        f = QFont("Consolas")
        f.setStyleHint(QFont.Monospace)
        self.ed.setFont(f)
        self.ed.setPlaceholderText("Una colonna per riga, es. 3 15 27 44 61 88" +
                                   ("   (Eurojackpot: 3 15 27 44 49 + 2 11)" if self.g.is_ej else
                                    "   (con la SuperStar: 3 15 27 44 61 88 SuperStar 42)"))
        v.addWidget(self.ed, 1)
        self.l_info = QLabel()
        v.addWidget(self.l_info)
        self.ed.textChanged.connect(self._info)
        self.origine = ""

    def imposta(self, colonne, extra=None, origine=""):
        extra = extra or [[] for _ in colonne]
        self.ed.setPlainText("\n".join(colonna_txt(self.g, c, e) for c, e in zip(colonne, extra)))
        self.origine = origine

    def leggi(self) -> tuple[list[list[int]], list[list[int]]]:
        g = self.g
        cols, extra = [], []
        for i, riga in enumerate(self.ed.toPlainText().splitlines(), 1):
            x = leggi_riga(riga, g.k)
            if x is None:
                continue
            nums, sp = x
            princ = nums[:g.k]
            if len(princ) != g.k or len(set(princ)) != g.k or not all(1 <= n <= g.n for n in princ):
                raise ValueError(f"Riga {i}: servono {g.k} numeri diversi da 1 a {g.n}.")
            if g.is_ej:
                eu = nums[g.k:] or sp.get("euro", [])
                if eu and (len(eu) != 2 or eu[0] == eu[1] or not all(1 <= n <= 12 for n in eu)):
                    raise ValueError(f"Riga {i}: gli Euronumeri devono essere 2, diversi, da 1 a 12.")
                e = sorted(eu)
            else:
                if len(nums) > g.k:
                    raise ValueError(f"Riga {i}: troppi numeri (ne servono {g.k}; la SuperStar si scrive "
                                     "«SuperStar 42»).")
                s = sp.get("superstar", [])
                if s and not 1 <= s[0] <= 90:
                    raise ValueError(f"Riga {i}: la SuperStar va da 1 a 90.")
                e = s[:1]
            cols.append(sorted(princ))
            extra.append(e)
        if not cols:
            raise ValueError("Scrivi almeno una colonna.")
        if g.is_ej and any(not e for e in extra):
            raise ValueError("Nell'Eurojackpot ogni colonna ha bisogno dei 2 Euronumeri (es. «+ 2 11»).")
        return cols, extra

    def _info(self):
        try:
            cols, extra = self.leggi()
            from .sistemi import leggi_prezzi
            self.l_info.setText(f"{len(cols)} colonne – costo per concorso "
                                f"{euro(gc.costo_giocata(self.g, cols, extra, leggi_prezzi(self.arch)))}")
            self.l_info.setStyleSheet("color:#1b5e20")
        except ValueError as ex:
            self.l_info.setText(str(ex) if self.ed.toPlainText().strip() else "")
            self.l_info.setStyleSheet("color:#b71c1c")

    # ---------------------------------------------------------------- sorgenti
    def da_macchina(self):
        from .macchina import CASUALI
        d = CASUALI.get(self.g.codice)
        if not d:
            QMessageBox.information(self, "Macchina", "Nessuna estrazione con la macchina in questa sessione "
                                                      "(Combinazioni casuali).")
            return
        rr = d["risultati"]
        if d["modo"] == "sistema":
            self._da_sistema_numeri(rr[0]["numeri"], rr[0]["extra"], "Sistema dalla macchina")
            return
        self.imposta([r["numeri"] for r in rr], [r["extra"] for r in rr], "Macchina dell'estrazione")

    def _da_sistema_numeri(self, numeri, euro_, origine):
        QMessageBox.information(self, "Sistema", "Dalla macchina è uscito un sistema di numeri: sviluppalo "
                                                 "(pulsante «Sviluppa il sistema») e poi registra le sue colonne "
                                                 "dalla finestra dello sviluppo, oppure usa «Ultimo sistema "
                                                 "sviluppato».")

    def da_ultimo_sistema(self):
        from .sistemi import ULTIMO
        u = ULTIMO.get(self.g.codice)
        if not u:
            QMessageBox.information(self, "Sistema", "Nessun sistema sviluppato in questa sessione.")
            return
        self._da_sistema(u[0])

    def _da_sistema(self, s: sis.Sistema):
        cols = [list(map(int, c)) for c in s.colonne]
        if len(cols) > 5000:
            QMessageBox.warning(self, "Sistema", f"Il sistema ha {len(cols)} colonne: troppe da registrare qui.")
            return
        extra = [[] for _ in cols]
        if self.g.is_ej:
            eu, ok = QInputDialog.getText(self, "Euronumeri", "Euronumeri da giocare con tutte le colonne (es. 2 11):")
            if not ok:
                return
            nums = [int(x) for x in eu.replace(",", " ").split() if x.isdigit()]
            if len(nums) != 2:
                QMessageBox.warning(self, "Euronumeri", "Servono 2 Euronumeri.")
                return
            extra = [sorted(nums) for _ in cols]
        self.imposta(cols, extra, f"Sistema «{s.nome}»" if s.nome else "Sistema sviluppato")

    def da_sistema_salvato(self):
        salvati = sis.salvati(self.arch)
        if not salvati:
            QMessageBox.information(self, "Sistemi", "Nessun sistema memorizzato.")
            return
        nome, ok = QInputDialog.getItem(self, "Sistema memorizzato", "Scegli il sistema:", list(salvati), 0, False)
        if ok:
            self._da_sistema(salvati[nome])

    def da_magico(self):
        from ..core import magico
        prev = magico.leggi_previsioni(self.arch)
        if not prev:
            QMessageBox.information(self, "Magico Pensiero", "Nessuna previsione di Magico Pensiero salvata.")
            return
        p = prev[-1]
        cols = [sorted(s) for s in p["sestine"]]
        if self.g.is_ej:
            extra = [sorted([p.get("jolly"), p.get("superstar")]) for _ in cols]
        else:
            extra = [[p["superstar"]] if p.get("superstar") else [] for _ in cols]
        self.imposta(cols, extra, f"Magico Pensiero ({p.get('origine', 'Algoritmo')})")


# ------------------------------------------------------------------ nuova giocata
class DialogoGiocata(QDialog):
    def __init__(self, arch: Archivio, parent=None, colonne=None, extra=None, origine=""):
        super().__init__(parent)
        self.arch = arch
        self.g = arch.gioco
        self.giocata: gc.Giocata | None = None
        self.setWindowTitle(f"Registra una giocata – {self.g.nome}")
        adatta_schermo(self, 860, 600)
        v = QVBoxLayout(self)
        f = QFormLayout()
        self.e_nome = QLineEdit()
        self.e_nome.setPlaceholderText("es. Sistema del venerdì")
        f.addRow("Nome", self.e_nome)
        ultima = arch.ultima()
        self.d_dal = QDateEdit(_qd(gc.prossimo_concorso(self.g, ultima.data if ultima else None)))
        self.d_dal.setCalendarPopup(True)
        self.d_dal.setDisplayFormat("dd/MM/yyyy")
        f.addRow("Primo concorso giocato", self.d_dal)
        self.sp_conc = QSpinBox()
        self.sp_conc.setRange(1, 200)
        f.addRow("Concorsi consecutivi", self.sp_conc)
        self.sp_costo = QDoubleSpinBox()
        self.sp_costo.setRange(0, 1_000_000)
        self.sp_costo.setDecimals(2)
        self.sp_costo.setSuffix(" €")
        f.addRow("Costo per concorso", self.sp_costo)
        v.addLayout(f)
        self.colonne = EditorColonne(arch, self)
        self.colonne.ed.textChanged.connect(self._costo)
        v.addWidget(self.colonne, 1)
        h = QHBoxLayout()
        h.addStretch()
        b = QPushButton("✔ Registra")
        b.clicked.connect(self._ok)
        h.addWidget(b)
        b = QPushButton("Annulla")
        b.clicked.connect(self.reject)
        h.addWidget(b)
        v.addLayout(h)
        if colonne:
            self.colonne.imposta(colonne, extra, origine)
            self.e_nome.setText(origine)

    def _costo(self):
        from .sistemi import leggi_prezzi
        try:
            cols, extra = self.colonne.leggi()
        except ValueError:
            return
        self.sp_costo.setValue(gc.costo_giocata(self.g, cols, extra, leggi_prezzi(self.arch)))

    def _ok(self):
        try:
            cols, extra = self.colonne.leggi()
        except ValueError as ex:
            QMessageBox.warning(self, "Giocata", str(ex))
            return
        self.giocata = gc.Giocata(self.g.codice, cols, extra, _d(self.d_dal.date()).isoformat(),
                                  self.sp_conc.value(), self.sp_costo.value(),
                                  self.e_nome.text().strip() or "Giocata", self.colonne.origine)
        gc.aggiungi(self.arch, self.giocata)
        self.accept()


def chiedi_euronumeri(parent, quante: int) -> list[list[int]] | None:
    """Eurojackpot: Euronumeri da giocare con tutte le colonne di un sistema."""
    eu, ok = QInputDialog.getText(parent, "Euronumeri", "Euronumeri da giocare con tutte le colonne (es. 2 11):")
    if not ok:
        return None
    nums = sorted({int(x) for x in eu.replace(",", " ").replace("+", " ").split() if x.isdigit()})
    if len(nums) != 2 or not all(1 <= x <= 12 for x in nums):
        QMessageBox.warning(parent, "Euronumeri", "Servono 2 Euronumeri diversi da 1 a 12.")
        return None
    return [nums for _ in range(quante)]


def registra(arch: Archivio, parent, colonne, extra=None, origine="") -> bool:
    """Apre il dialogo di registrazione già compilato (da Sviluppo, macchina, ecc.)."""
    if arch.gioco.is_ej and (not extra or not all(extra)):
        extra = chiedi_euronumeri(parent, len(colonne))
        if extra is None:
            return False
    d = DialogoGiocata(arch, parent, colonne, extra, origine)
    if d.exec():
        QMessageBox.information(parent, "Giocata registrata", "La giocata è nel registro (Ricevitoria → Registro "
                                                              "delle giocate): dopo ogni estrazione il programma "
                                                              "la controlla da solo.")
        return True
    return False


# ------------------------------------------------------------------ scaricamento delle quote
class ScaricaQuote(QThread):
    avanzamento = Signal(str, int, int)
    finito = Signal(dict)

    def __init__(self, gioco, date_):
        super().__init__()
        self.gioco = gioco
        self.date_ = date_

    def run(self):
        try:
            if self.gioco.is_ej:
                from ..core import vincite_ej as mod
            else:
                from ..core import vincite as mod
            self.finito.emit(mod.scarica(self.date_, lambda m, i, n: self.avanzamento.emit(m, i, n)))
        except Exception:
            self.finito.emit({})


def quote_mancanti(arch: Archivio, giorni) -> list[date]:
    """Concorsi tra quelli indicati di cui non si conoscono le quote."""
    q = gc.Quote(arch)
    out = []
    for d in sorted(set(giorni)):
        v = q.dati.get(d.isoformat())
        if v is None or (not arch.gioco.is_ej and v.q3 is None) or (arch.gioco.is_ej and not v.quote):
            out.append(d)
    return out


def salva_quote(arch: Archivio, dati: dict):
    if arch.gioco.is_ej:
        from ..core import vincite_ej as mod
    else:
        from ..core import vincite as mod
    mod.salva(arch, dati)


# ------------------------------------------------------------------ registro
class FinestraGiocate(QDialog):
    def __init__(self, arch: Archivio, parent=None):
        super().__init__(parent)
        self.arch = arch
        self.g = arch.gioco
        self.thread = None
        self.setWindowTitle(f"📝 Registro delle giocate – {self.g.nome}")
        adatta_schermo(self, 1180, 760)
        v = QVBoxLayout(self)
        self.tabs = QTabWidget()
        v.addWidget(self.tabs, 1)
        # elenco
        w = QWidget()
        lv = QVBoxLayout(w)
        self.t = QTableWidget(0, 8)
        self.t.setHorizontalHeaderLabels(["Primo concorso", "Nome", "Colonne", "Concorsi (usciti/tot.)", "Spesa",
                                          "Vinto", "Saldo", "Origine"])
        self.t.verticalHeader().setVisible(False)
        self.t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.t.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.t.itemSelectionChanged.connect(self._dettaglio)
        self.t.doubleClicked.connect(lambda *_: self.tabs.setCurrentIndex(1))
        lv.addWidget(self.t, 1)
        h = QHBoxLayout()
        for testo, fun in (("➕ Nuova giocata", self.nuova), ("🗑 Elimina", self.elimina),
                           ("✍ Vinto incassato...", self.vinto_manuale),
                           ("🌐 Aggiorna le quote da Internet", self.aggiorna_quote)):
            b = QPushButton(testo)
            b.clicked.connect(fun)
            h.addWidget(b)
        h.addStretch()
        lv.addLayout(h)
        self.tabs.addTab(w, "Giocate")
        # dettaglio
        self.dett = QTextBrowser()
        self.tabs.addTab(self.dett, "Dettaglio della giocata")
        # bilancio
        wb = QWidget()
        lb = QVBoxLayout(wb)
        self.l_bil = QLabel()
        self.l_bil.setWordWrap(True)
        f = self.l_bil.font()
        f.setPointSize(f.pointSize() + 1)
        self.l_bil.setFont(f)
        lb.addWidget(self.l_bil)
        self.t_bil = QTableWidget(0, 4)
        self.t_bil.setHorizontalHeaderLabels(["Mese", "Spesa", "Vinto", "Saldo"])
        self.t_bil.verticalHeader().setVisible(False)
        self.t_bil.setEditTriggers(QAbstractItemView.NoEditTriggers)
        lb.addWidget(self.t_bil, 1)
        nota = QLabel("Il gioco è un passatempo: stabilisci un tetto di spesa mensile e rispettalo. Le vincite "
                      "sono calcolate con le quote ufficiali di ogni concorso; quelle segnate «da verificare» "
                      "aspettano le quote (pulsante «Aggiorna le quote»).")
        nota.setWordWrap(True)
        nota.setStyleSheet("color:#555")
        lb.addWidget(nota)
        self.tabs.addTab(wb, "Bilancio")
        self.barra = QProgressBar()
        self.barra.setVisible(False)
        v.addWidget(self.barra)
        h = QHBoxLayout()
        h.addWidget(pulsanti_stampa(self, self._da_stampare))
        h.addStretch()
        b = QPushButton("Chiudi")
        b.clicked.connect(self.reject)
        h.addWidget(b)
        v.addLayout(h)
        self.ricarica()

    # ---------------------------------------------------------------- dati
    def ricarica(self):
        self.giocate = gc.carica(self.arch)
        self.righe = list(self.arch.sestine())
        self.quote = gc.Quote(self.arch)
        self.esiti = [gc.esito(self.g, x, self.righe, self.quote) for x in self.giocate]
        self.t.setRowCount(len(self.giocate))
        for i, (x, e) in enumerate(zip(self.giocate, self.esiti)):
            vinto = x.vinto_manuale if x.vinto_manuale is not None else e.vinto
            saldo = vinto - e.spesa
            celle = [date.fromisoformat(x.dal).strftime("%d/%m/%Y") if x.dal else "", x.nome, str(len(x.colonne)),
                     f"{len(e.concorsi_estratti)}/{x.concorsi}", euro(e.spesa),
                     euro(vinto) + (" *" if e.da_verificare and x.vinto_manuale is None else ""), euro(saldo),
                     x.origine]
            for j, c in enumerate(celle):
                it = QTableWidgetItem(c)
                if j in (4, 5, 6):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if j == 5 and vinto > 0:
                    it.setBackground(QColor("#c8e6c9"))
                self.t.setItem(i, j, it)
        self.t.resizeColumnsToContents()
        self.t.horizontalHeader().setStretchLastSection(True)
        self._bilancio()

    def _bilancio(self):
        mesi: dict[str, list] = {}
        spesa = vinto = 0.0
        for x, e in zip(self.giocate, self.esiti):
            costo = x.costo
            for d in e.concorsi_estratti:
                mesi.setdefault(f"{d:%Y-%m}", [0.0, 0.0])[0] += costo
            if x.vinto_manuale is not None:
                if e.concorsi_estratti:
                    mesi.setdefault(f"{e.concorsi_estratti[-1]:%Y-%m}", [0.0, 0.0])[1] += x.vinto_manuale
                vinto += x.vinto_manuale
            else:
                for vv in e.vincite:
                    mesi.setdefault(f"{vv.data:%Y-%m}", [0.0, 0.0])[1] += vv.importo or 0
                vinto += e.vinto
            spesa += e.spesa
        da_ver = sum(e.da_verificare for x, e in zip(self.giocate, self.esiti) if x.vinto_manuale is None)
        self.l_bil.setText(f"<b>Giocate:</b> {len(self.giocate)} &nbsp; <b>Spesa:</b> {euro(spesa)} &nbsp; "
                           f"<b>Vinto:</b> {euro(vinto)} &nbsp; <b>Saldo:</b> "
                           f"<span style='color:{'#2e7d32' if vinto >= spesa else '#c62828'}'>{euro(vinto - spesa)}"
                           "</span>" + (f"<br>{da_ver} vincite con quota ancora da verificare." if da_ver else ""))
        self.t_bil.setRowCount(len(mesi))
        for i, (m, (s, v)) in enumerate(sorted(mesi.items(), reverse=True)):
            a, mm = m.split("-")
            for j, c in enumerate([f"{mm}/{a}", euro(s), euro(v), euro(v - s)]):
                it = QTableWidgetItem(c)
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter if j else Qt.AlignCenter)
                self.t_bil.setItem(i, j, it)
        self.t_bil.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def _scelta(self) -> int:
        i = self.t.currentRow()
        return i if 0 <= i < len(self.giocate) else -1

    def _dettaglio(self):
        i = self._scelta()
        if i < 0:
            return
        x, e = self.giocate[i], self.esiti[i]
        g = self.g
        h = [f"<h3>{x.nome}</h3><p>{len(x.colonne)} colonne – {x.concorsi} concorsi dal "
             f"{date.fromisoformat(x.dal):%d/%m/%Y} – costo per concorso {euro(x.costo)}"
             + (f" – origine: {x.origine}" if x.origine else "") + "</p>"]
        if not e.concorsi_estratti:
            h.append("<p>Nessun concorso ancora estratto: verrà controllata da sola dopo l'estrazione.</p>")
        for d in e.concorsi_estratti:
            r = next(r for r in self.righe if r[0] == d)
            uscita = " ".join(map(str, r[1])) + (f" + {r[2]} {r[3]}" if g.is_ej else
                                                  f" – Jolly {r[2]} – SuperStar {r[3] or '-'}")
            vv = [v for v in e.vincite if v.data == d]
            h.append(f"<p><b>{d:%d/%m/%Y}</b>: {uscita}<br>")
            if vv:
                for v in vv:
                    h.append(f"&nbsp;&nbsp;🎉 colonna {v.colonna + 1} "
                             f"({colonna_txt(g, x.colonne[v.colonna], x.extra[v.colonna] if x.extra else [])}): "
                             f"<b>{gc.nome_categoria(v.categoria)}</b> – "
                             f"{euro(v.importo) if v.importo is not None else 'quota da verificare'}<br>")
            else:
                h.append("&nbsp;&nbsp;nessuna vincita<br>")
            h.append("</p>")
        if e.concorsi_mancanti:
            h.append(f"<p>Concorsi ancora da estrarre: {e.concorsi_mancanti}.</p>")
        h.append("<h4>Colonne</h4><pre>" + "\n".join(
            f"{k + 1:4d}) {colonna_txt(g, c, x.extra[k] if x.extra else [])}" for k, c in enumerate(x.colonne[:500]))
                 + ("\n..." if len(x.colonne) > 500 else "") + "</pre>")
        self.dett.setHtml("".join(h))

    # ---------------------------------------------------------------- azioni
    def nuova(self):
        if DialogoGiocata(self.arch, self).exec():
            self.ricarica()

    def elimina(self):
        i = self._scelta()
        if i >= 0 and QMessageBox.question(self, "Elimina", f"Eliminare la giocata «{self.giocate[i].nome}»?") \
                == QMessageBox.Yes:
            gc.elimina(self.arch, self.giocate[i].id)
            self.ricarica()

    def vinto_manuale(self):
        i = self._scelta()
        if i < 0:
            return
        x = self.giocate[i]
        val, ok = QInputDialog.getDouble(self, "Vinto incassato", "Quanto hai incassato davvero con questa "
                                                                  "giocata? (-1 = usa il calcolo automatico)",
                                         x.vinto_manuale if x.vinto_manuale is not None else -1, -1, 1e9, 2)
        if ok:
            tutte = gc.carica(self.arch)
            for t in tutte:
                if t.id == x.id:
                    t.vinto_manuale = None if val < 0 else val
            gc.salva_tutte(self.arch, tutte)
            self.ricarica()

    def aggiorna_quote(self):
        giorni = [d for e in self.esiti for d in e.concorsi_estratti]
        da_fare = quote_mancanti(self.arch, giorni)
        if not da_fare:
            QMessageBox.information(self, "Quote", "Le quote dei concorsi giocati sono già tutte note.")
            return
        self.barra.setVisible(True)
        self.barra.setRange(0, len(da_fare))
        self.thread = ScaricaQuote(self.g, da_fare)
        self.thread.avanzamento.connect(lambda m, i, n: self.barra.setValue(i))
        self.thread.finito.connect(self._quote_finite)
        self.thread.start()

    def _quote_finite(self, dati):
        self.barra.setVisible(False)
        salva_quote(self.arch, dati)
        self.ricarica()
        QMessageBox.information(self, "Quote", f"Quote lette per {len(dati)} concorsi.")

    def _da_stampare(self):
        g = self.g
        r = [f"REGISTRO DELLE GIOCATE – {g.nome}", ""]
        for x, e in zip(self.giocate, self.esiti):
            vinto = x.vinto_manuale if x.vinto_manuale is not None else e.vinto
            r.append(f"{date.fromisoformat(x.dal):%d/%m/%Y}  {x.nome[:30]:30s} {len(x.colonne):5d} col.  "
                     f"{len(e.concorsi_estratti)}/{x.concorsi} conc.  spesa {euro(e.spesa):>12s}  "
                     f"vinto {euro(vinto):>14s}")
        r += ["", self.l_bil.text().replace("<b>", "").replace("</b>", "").replace("&nbsp;", " ")
              .replace("<br>", "\n").split("<span")[0]]
        return "Registro delle giocate", "\n".join(r), "registro giocate"

    def closeEvent(self, ev):
        if self.thread and self.thread.isRunning():
            ev.ignore()
            return
        super().closeEvent(ev)

    def reject(self):
        if self.thread and self.thread.isRunning():
            return
        super().reject()


# ------------------------------------------------------------------ simulatore
class FinestraSimulatore(QDialog):
    def __init__(self, arch: Archivio, parent=None, colonne=None, extra=None):
        super().__init__(parent)
        self.arch = arch
        self.g = arch.gioco
        self.sim: gc.Simulazione | None = None
        self.thread = None
        self.setWindowTitle(f"📈 E se avessi giocato… – {self.g.nome}")
        adatta_schermo(self, 1150, 780)
        v = QVBoxLayout(self)
        spieg = QLabel("Scegli una o più colonne (anche un sistema) e un periodo: il programma le gioca a ogni "
                       "concorso dell'archivio e ti dice quanto avresti speso e quanto avresti vinto, con le "
                       "quote reali di ogni concorso.")
        spieg.setWordWrap(True)
        v.addWidget(spieg)
        self.colonne = EditorColonne(arch, self)
        self.colonne.setMaximumHeight(200)
        v.addWidget(self.colonne)
        h = QHBoxLayout()
        righe = list(arch.sestine())
        ultima = righe[-1][0] if righe else date.today()
        prima = righe[0][0] if righe else date.today()
        h.addWidget(QLabel("Dal"))
        self.d_dal = QDateEdit(_qd(max(prima, ultima - timedelta(days=365 * 5))))
        h.addWidget(QLabel("al"))
        self.d_al = QDateEdit(_qd(ultima))
        for d in (self.d_dal, self.d_al):
            d.setCalendarPopup(True)
            d.setDisplayFormat("dd/MM/yyyy")
        h.insertWidget(1, self.d_dal)
        h.addWidget(self.d_al)
        b = QPushButton("▶ Simula")
        f = b.font()
        f.setBold(True)
        b.setFont(f)
        b.clicked.connect(self.simula)
        h.addWidget(b)
        self.b_quote = QPushButton("🌐 Scarica le quote mancanti")
        self.b_quote.clicked.connect(self.scarica_quote)
        self.b_quote.setEnabled(False)
        h.addWidget(self.b_quote)
        h.addStretch()
        v.addLayout(h)
        self.barra = QProgressBar()
        self.barra.setVisible(False)
        v.addWidget(self.barra)
        corpo = QHBoxLayout()
        self.l_ris = QTextBrowser()
        corpo.addWidget(self.l_ris, 1)
        self.t_cat = QTableWidget(0, 3)
        self.t_cat.setHorizontalHeaderLabels(["Categoria", "Volte", "Importo"])
        self.t_cat.verticalHeader().setVisible(False)
        self.t_cat.setEditTriggers(QAbstractItemView.NoEditTriggers)
        corpo.addWidget(self.t_cat, 1)
        self.t_anni = QTableWidget(0, 4)
        self.t_anni.setHorizontalHeaderLabels(["Anno", "Spesa", "Vinto", "Saldo"])
        self.t_anni.verticalHeader().setVisible(False)
        self.t_anni.setEditTriggers(QAbstractItemView.NoEditTriggers)
        corpo.addWidget(self.t_anni, 1)
        v.addLayout(corpo, 1)
        h = QHBoxLayout()
        h.addWidget(pulsanti_stampa(self, self._da_stampare))
        b = QPushButton("📝 Registra come giocata")
        b.clicked.connect(self.registra)
        h.addWidget(b)
        h.addStretch()
        b = QPushButton("Chiudi")
        b.clicked.connect(self.reject)
        h.addWidget(b)
        v.addLayout(h)
        if colonne:
            self.colonne.imposta(colonne, extra)

    def simula(self):
        try:
            cols, extra = self.colonne.leggi()
        except ValueError as ex:
            QMessageBox.warning(self, "Simulatore", str(ex))
            return
        from .sistemi import leggi_prezzi
        costo = gc.costo_giocata(self.g, cols, extra, leggi_prezzi(self.arch))
        righe = list(self.arch.sestine())
        dal, al = _d(self.d_dal.date()), _d(self.d_al.date())
        self.sim = gc.simula(self.g, cols, extra, righe, dal, al, gc.Quote(self.arch), costo)
        self._mostra()

    def _mostra(self):
        s = self.sim
        if not s.estrazioni:
            self.l_ris.setHtml("<p>Nessun concorso nel periodo scelto.</p>")
            return
        saldo = s.vinto - s.spesa
        m = max(s.vincite, key=lambda v: v.importo or 0, default=None)
        h = [f"<h3>{s.estrazioni} concorsi dal {s.dal:%d/%m/%Y} al {s.al:%d/%m/%Y}</h3>",
             f"<p>Avresti speso <b>{euro(s.spesa)}</b> e vinto <b>{euro(s.vinto)}</b>.<br>Saldo: "
             f"<b style='color:{'#2e7d32' if saldo >= 0 else '#c62828'}'>{euro(saldo)}</b> "
             + (f"(rientro del {s.vinto / s.spesa * 100:.0f}% di quanto speso)" if s.spesa else "") + ".</p>"]
        if m and (m.importo or 0) > 0:
            h.append(f"<p>Vincita più alta: <b>{gc.nome_categoria(m.categoria)}</b> il {m.data:%d/%m/%Y} "
                     f"({euro(m.importo)}).</p>")
        h.append(f"<p>Vincite totali: {len(s.vincite)} (una ogni {s.estrazioni / max(1, len(s.vincite)):.1f} "
                 "concorsi).</p>")
        if s.da_verificare:
            h.append(f"<p style='color:#b26a00'>{s.da_verificare} vincite hanno la quota ancora sconosciuta (non "
                     "contate nel vinto): usa «Scarica le quote mancanti».</p>")
        h.append("<p style='color:#555'>Nel lungo periodo le lotterie restituiscono in media meno di quanto si "
                 "spende: il simulatore lo mostra con i numeri veri.</p>")
        self.l_ris.setHtml("".join(h))
        ordine = gc.ORDINE_EJ if self.g.is_ej else gc.ORDINE_SE
        pc = s.per_categoria()
        ign = gc.Esito([], 0, s.vincite, 0).ignote()
        cats = [c for c in ordine if c in pc]
        self.t_cat.setRowCount(len(cats))
        for i, c in enumerate(cats):
            imp = euro(pc[c][1]) if not ign.get(c) else (
                "da verificare" if ign[c] == pc[c][0] else f"{euro(pc[c][1])} + {ign[c]} da verificare")
            for j, x in enumerate([gc.nome_categoria(c), str(pc[c][0]), imp]):
                it = QTableWidgetItem(x)
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter if j else Qt.AlignLeft | Qt.AlignVCenter)
                self.t_cat.setItem(i, j, it)
        self.t_cat.resizeColumnsToContents()
        self.t_anni.setRowCount(len(s.per_anno))
        for i, (a, (sp, vi)) in enumerate(sorted(s.per_anno.items(), reverse=True)):
            for j, x in enumerate([str(a), euro(sp), euro(vi), euro(vi - sp)]):
                it = QTableWidgetItem(x)
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.t_anni.setItem(i, j, it)
        self.t_anni.resizeColumnsToContents()
        self.b_quote.setEnabled(bool(s.da_verificare))

    def scarica_quote(self):
        if not self.sim:
            return
        da_fare = quote_mancanti(self.arch, [v.data for v in self.sim.vincite if v.importo is None])
        if not da_fare:
            return
        if len(da_fare) > 400 and QMessageBox.question(
                self, "Quote", f"Servono le quote di {len(da_fare)} concorsi: ci vorrà qualche minuto. "
                               "Procedo?") != QMessageBox.Yes:
            return
        self.barra.setVisible(True)
        self.barra.setRange(0, len(da_fare))
        self.thread = ScaricaQuote(self.g, da_fare)
        self.thread.avanzamento.connect(lambda m, i, n: self.barra.setValue(i))
        self.thread.finito.connect(self._quote)
        self.thread.start()

    def _quote(self, dati):
        self.barra.setVisible(False)
        salva_quote(self.arch, dati)
        self.simula()

    def registra(self):
        try:
            cols, extra = self.colonne.leggi()
        except ValueError as ex:
            QMessageBox.warning(self, "Giocata", str(ex))
            return
        registra(self.arch, self, cols, extra, self.colonne.origine or "Simulatore")

    def _da_stampare(self):
        s = self.sim
        if not s or not s.estrazioni:
            return "E se avessi giocato…", "Nessuna simulazione.", "simulazione"
        r = [f"E SE AVESSI GIOCATO… – {self.g.nome}", f"{s.estrazioni} concorsi dal {s.dal:%d/%m/%Y} al "
             f"{s.al:%d/%m/%Y}", f"Spesa {euro(s.spesa)} – Vinto {euro(s.vinto)} – Saldo {euro(s.vinto - s.spesa)}",
             "", "Colonne:", self.colonne.ed.toPlainText(), "", "Per categoria:"]
        for c, (n, imp) in s.per_categoria().items():
            r.append(f"  {gc.nome_categoria(c):24s} {n:6d}  {euro(imp):>16s}")
        r += ["", "Per anno:"] + [f"  {a}: spesa {euro(sp)}  vinto {euro(vi)}" for a, (sp, vi) in s.per_anno.items()]
        return "E se avessi giocato…", "\n".join(r), "simulazione"

    def reject(self):
        if self.thread and self.thread.isRunning():
            return
        super().reject()
