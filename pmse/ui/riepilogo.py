"""Riepilogo delle sezioni attive e scelta di cosa stampare.

Una sola finestra elenca ciò che il programma ha "in mano" in questo momento: le combinazioni di Magico
Pensiero (algoritmo e intelligenza artificiale) per il prossimo concorso, le combinazioni casuali della
macchina, l'ultimo sistema sviluppato (anche dai Suggerimenti AI), l'editor dei sistemi aperto, le giocate
registrate e i sistemi memorizzati. Per ognuna: apri, stampa (stampante, PDF, TXT), registra come giocata,
chiudi.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
                               QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import giocate as gc
from ..core import magico
from ..core import sistemi as sis
from .schermo import adatta_schermo

CHIAVE_NASCOSTA = "home_previsione_chiusa"


@dataclass
class Sezione:
    codice: str
    nome: str
    stato: str
    attiva: bool = True
    testo: Callable[[], str] | None = None                      # testo da stampare
    colonne: Callable[[], tuple] | None = None                  # (colonne, extra, origine) per registrare
    apri: Callable[[], None] | None = None
    chiudi: Callable[[], None] | None = None
    nota_chiudi: str = ""
    extra: dict = field(default_factory=dict)


def _fmt(c) -> str:
    return " ".join(f"{x:2d}" for x in c)


def testo_previsione(g, p: dict, titolo: str) -> str:
    r = [titolo, f"Gioco: {g.nome}"]
    if p.get("dopo"):
        r.append(f"Per il concorso dopo quello del {date.fromisoformat(p['dopo']):%d/%m/%Y}")
    gen = p.get("generata", "")
    try:
        gen = date.fromisoformat(gen).strftime("%d/%m/%Y")
    except ValueError:
        pass
    r.append(f"Origine: {p.get('origine', 'Algoritmo')} – generata il {gen}")
    r.append("")
    if g.is_ej:
        r.append(f"Cinquina:    {_fmt(p['sestine'][0])}")
        r.append(f"Euronumeri:  {p.get('jolly')} {p.get('superstar')}")
    else:
        for i, s in enumerate(p["sestine"], 1):
            r.append(f"Sestina {i}:  {_fmt(s)}")
        r.append(f"Jolly:      {p.get('jolly')}")
        r.append(f"SuperStar:  {p.get('superstar') or '-'}")
    return "\n".join(r)


def colonne_previsione(g, p: dict) -> tuple:
    cols = [sorted(s) for s in p["sestine"]]
    if g.is_ej:
        extra = [sorted([p.get("jolly"), p.get("superstar")]) for _ in cols]
    else:
        extra = [[p["superstar"]] if p.get("superstar") else [] for _ in cols]
    return cols, extra, f"Magico Pensiero ({p.get('origine', 'Algoritmo')})"


def raccogli(f) -> list[Sezione]:
    """Le sezioni del programma per la finestra principale f."""
    from .macchina import CASUALI
    from .sistemi import ULTIMO
    arch, g = f.arch, f.g
    out: list[Sezione] = []
    ultima = arch.ultima()
    prev = magico.leggi_previsioni(arch)
    attuali = [p for p in prev if ultima and p.get("dopo") == ultima.data.isoformat()]
    nascosta = arch.leggi_impostazione(CHIAVE_NASCOSTA) or ""
    for nome, filtro in (("Magico Pensiero (algoritmo)", lambda p: p.get("origine", "Algoritmo") == "Algoritmo"),
                         ("Magico Pensiero + intelligenza artificiale",
                          lambda p: p.get("origine", "Algoritmo") != "Algoritmo")):
        scelte = [p for p in attuali if filtro(p)]
        if scelte:
            p = scelte[-1]
            chiave = f"{p.get('dopo')}|{p.get('origine', 'Algoritmo')}"
            in_home = nascosta != chiave
            stato = (f"{len(p['sestine'])} {g.nome_comb_pl if len(p['sestine']) > 1 else g.nome_comb} per il "
                     f"prossimo concorso" + (" – mostrata in home" if in_home else " – chiusa"))
            out.append(Sezione(
                "magico" if "algoritmo" in nome else "magico_ai", nome, stato, in_home,
                testo=lambda p=p, nome=nome: testo_previsione(g, p, nome.upper()),
                colonne=lambda p=p: colonne_previsione(g, p),
                apri=lambda p=p: f.mostra_previsione(p),
                chiudi=lambda chiave=chiave: f.chiudi_previsione(chiave),
                nota_chiudi="Toglie le combinazioni dalla home (restano nello storico delle previsioni, per "
                            "l'apprendimento)."))
        else:
            out.append(Sezione("magico" if "algoritmo" in nome else "magico_ai", nome,
                               "nessuna proposta per il prossimo concorso", False,
                               apri=f.genera if "algoritmo" in nome else f.claude))
    cas = CASUALI.get(g.codice)
    if cas:
        rr = cas["risultati"]

        def testo_cas(rr=rr, cas=cas):
            r = ["COMBINAZIONI CASUALI (macchina dell'estrazione)", f"Gioco: {g.nome}", ""]
            for i, x in enumerate(rr, 1):
                ex = (f"  + {' '.join(map(str, x['extra']))}" if g.is_ej else
                      (f"   SuperStar {x['extra'][0]}" if x["extra"] else ""))
                r.append(f"{'Sistema' if cas['modo'] == 'sistema' else f'{i:2d})'} {_fmt(x['numeri'])}{ex}")
            return "\n".join(r)
        modo = "numeri per un sistema" if cas["modo"] == "sistema" else (
            "1 combinazione estratta" if len(rr) == 1 else f"{len(rr)} combinazioni estratte")
        out.append(Sezione("casuali", "Combinazioni casuali (macchina)", f"{modo} in questa sessione",
                           testo=testo_cas,
                           colonne=(lambda rr=rr: ([x["numeri"] for x in rr], [x["extra"] for x in rr],
                                                   "Macchina dell'estrazione")) if cas["modo"] != "sistema" else None,
                           apri=lambda: f.macchina(cas["modo"]),
                           chiudi=lambda: CASUALI.pop(g.codice, None),
                           nota_chiudi="Dimentica le combinazioni estratte con la macchina."))
    else:
        out.append(Sezione("casuali", "Combinazioni casuali (macchina)", "nessuna estrazione in questa sessione",
                           False, apri=lambda: f.macchina("sestine")))
    u = ULTIMO.get(g.codice)
    if u:
        s = u[0]
        out.append(Sezione("sistema", "Ultimo sistema sviluppato",
                           f"{sis.TIPI.get(s.tipo, s.tipo)} – {len(s.numeri)} numeri, {len(s.colonne):,} colonne"
                           .replace(",", ".") + (f" – «{s.nome}»" if s.nome else ""),
                           testo=lambda s=s: sis.tabulato(s, s.colonne),
                           colonne=lambda s=s: ([list(map(int, c)) for c in s.colonne], None,
                                                f"Sistema «{s.nome}»" if s.nome else "Sistema sviluppato"),
                           apri=lambda: f._ultimo(None),
                           chiudi=lambda: ULTIMO.pop(g.codice, None),
                           nota_chiudi="Dimentica l'ultimo sistema sviluppato (quelli memorizzati restano)."))
    else:
        out.append(Sezione("sistema", "Ultimo sistema sviluppato", "nessuno in questa sessione", False,
                           apri=lambda: f.nuovo_sistema("ridotto")))
    e = f._editor_aperto()
    if e is not None:
        out.append(Sezione("editor", "Editor dei sistemi (finestra aperta)", e.windowTitle(),
                           apri=lambda: (e.raise_(), e.activateWindow()), chiudi=e.close,
                           nota_chiudi="Chiude la finestra dell'editor (le impostazioni non memorizzate si "
                                       "perdono)."))
    tutte = gc.carica(arch)
    righe = list(arch.sestine())
    in_attesa = [x for x in tutte if gc.esito(g, x, righe).concorsi_mancanti > 0]
    out.append(Sezione("giocate", "Giocate registrate", f"{len(tutte)} giocate, {len(in_attesa)} in attesa di "
                       "estrazione" if tutte else "nessuna giocata registrata", bool(tutte),
                       testo=(lambda: _testo_giocate(f)) if tutte else None, apri=f.registro_giocate))
    salvati = sis.salvati(arch)
    out.append(Sezione("salvati", "Sistemi memorizzati", f"{len(salvati)} sistemi" if salvati else "nessuno",
                       bool(salvati), apri=f.sistemi_salvati,
                       testo=(lambda: "\n\n".join(sis.tabulato(s, s.colonne, con_presenze=False)
                                                  for s in salvati.values())) if salvati else None))
    out.append(Sezione("estrazioni", "Estrazioni dell'archivio", f"{arch.conta()} estrazioni", arch.conta() > 0,
                       testo=lambda: _testo_estrazioni(f), apri=f.apri_archivio))
    return out


def _testo_giocate(f) -> str:
    from .giocate import FinestraGiocate
    w = FinestraGiocate(f.arch)
    try:
        return w._da_stampare()[1]
    finally:
        w.deleteLater()


def _testo_estrazioni(f) -> str:
    from .statistiche import stampa_estrazioni
    return f"ESTRAZIONI – {f.g.nome} (ultime 100)\n\n" + stampa_estrazioni(None, f.arch, 100)


class FinestraRiepilogo(QDialog):
    def __init__(self, finestra, evidenzia: str | None = None):
        super().__init__(finestra)
        self.f = finestra
        self.g = finestra.g
        self.setWindowTitle(f"📋 Sezioni attive e stampe – {self.g.nome}")
        adatta_schermo(self, 1150, 720)
        v = QVBoxLayout(self)
        spieg = QLabel("Qui vedi cosa è attivo nel programma in questo momento. Scegli una sezione per aprirla, "
                       "stamparla (stampante, PDF o TXT), registrarne le colonne tra le giocate o chiuderla.")
        spieg.setWordWrap(True)
        v.addWidget(spieg)
        div = QSplitter(Qt.Horizontal)
        self.t = QTableWidget(0, 2)
        self.t.setHorizontalHeaderLabels(["Sezione", "Stato"])
        self.t.verticalHeader().setVisible(False)
        self.t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.t.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.t.setSelectionMode(QAbstractItemView.SingleSelection)
        self.t.itemSelectionChanged.connect(self._scelta)
        div.addWidget(self.t)
        self.anteprima = QPlainTextEdit()
        self.anteprima.setReadOnly(True)
        self.anteprima.setLineWrapMode(QPlainTextEdit.NoWrap)
        fnt = QFont("Consolas")
        fnt.setStyleHint(QFont.Monospace)
        self.anteprima.setFont(fnt)
        div.addWidget(self.anteprima)
        div.setSizes([520, 600])
        v.addWidget(div, 1)
        self.l_nota = QLabel()
        self.l_nota.setWordWrap(True)
        self.l_nota.setStyleSheet("color:#555")
        v.addWidget(self.l_nota)
        h = QHBoxLayout()
        self.b_apri = QPushButton("📂 Apri")
        self.b_stampa = QPushButton("🖨 Stampa / PDF / TXT...")
        self.b_registra = QPushButton("📝 Registra come giocata...")
        self.b_chiudi = QPushButton("✖ Chiudi la sezione")
        self.b_tutte = QPushButton("Chiudi tutte le sezioni temporanee")
        for b, fun in ((self.b_apri, self.apri), (self.b_stampa, self.stampa), (self.b_registra, self.registra),
                       (self.b_chiudi, self.chiudi), (self.b_tutte, self.chiudi_tutte)):
            b.clicked.connect(fun)
            h.addWidget(b)
        h.addStretch()
        b = QPushButton("Chiudi")
        b.clicked.connect(self.accept)
        h.addWidget(b)
        v.addLayout(h)
        self.ricarica(evidenzia)

    def ricarica(self, evidenzia: str | None = None):
        self.sezioni = raccogli(self.f)
        self.t.setRowCount(len(self.sezioni))
        riga = 0
        for i, s in enumerate(self.sezioni):
            a = QTableWidgetItem(("🟢 " if s.attiva else "⚪ ") + s.nome)
            b = QTableWidgetItem(s.stato)
            b.setToolTip(s.stato)
            if not s.attiva:
                a.setForeground(QColor("#777"))
                b.setForeground(QColor("#777"))
            self.t.setItem(i, 0, a)
            self.t.setItem(i, 1, b)
            if s.codice == evidenzia:
                riga = i
        self.t.resizeColumnToContents(0)
        self.t.horizontalHeader().setStretchLastSection(True)
        self.t.selectRow(riga)
        self._scelta()

    def attuale(self) -> Sezione | None:
        i = self.t.currentRow()
        return self.sezioni[i] if 0 <= i < len(self.sezioni) else None

    def _scelta(self):
        s = self.attuale()
        if s is None:
            return
        self.b_apri.setEnabled(s.apri is not None)
        self.b_stampa.setEnabled(s.testo is not None)
        self.b_registra.setEnabled(s.colonne is not None)
        self.b_chiudi.setEnabled(s.chiudi is not None)
        self.l_nota.setText(s.nota_chiudi)
        try:
            t = s.testo() if s.testo else "(niente da stampare per questa sezione)"
        except Exception as ex:
            t = f"Anteprima non disponibile: {ex}"
        if len(t) > 400_000:
            t = t[:400_000] + "\n... (anteprima troncata: la stampa contiene tutto)"
        self.anteprima.setPlainText(t)

    def apri(self):
        s = self.attuale()
        if s and s.apri:
            self.accept()
            s.apri()

    def stampa(self):
        s = self.attuale()
        if s and s.testo:
            from .stampa import stampa
            stampa(self, f"{s.nome} – {self.g.nome}", s.testo(), s.nome)

    def registra(self):
        s = self.attuale()
        if s and s.colonne:
            from .giocate import registra
            cols, extra, origine = s.colonne()
            registra(self.f.arch, self, cols, extra, origine)
            self.ricarica(s.codice)

    def chiudi(self):
        s = self.attuale()
        if s and s.chiudi:
            if QMessageBox.question(self, "Chiudi la sezione", f"Chiudere «{s.nome}»?\n\n{s.nota_chiudi}") \
                    != QMessageBox.Yes:
                return
            s.chiudi()
            self.ricarica(s.codice)

    def chiudi_tutte(self):
        temporanee = [s for s in self.sezioni if s.chiudi and s.attiva]
        if not temporanee:
            QMessageBox.information(self, "Sezioni", "Non ci sono sezioni temporanee aperte.")
            return
        if QMessageBox.question(self, "Chiudi tutte", "Chiudere: " + ", ".join(s.nome for s in temporanee) +
                                "?\n\nLe giocate registrate, i sistemi memorizzati e lo storico delle previsioni "
                                "restano.") != QMessageBox.Yes:
            return
        for s in temporanee:
            try:
                s.chiudi()
            except Exception:
                pass
        self.ricarica()
