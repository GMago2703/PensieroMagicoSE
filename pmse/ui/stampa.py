"""Stampa su stampante (con anteprima), PDF e TXT di un testo a colonne (tabulati, statistiche, verifiche)."""
from __future__ import annotations

from html import escape

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QFont, QPageLayout, QPageSize, QPdfWriter, QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import QFileDialog, QMessageBox, QPushButton

LARGHEZZA_MM = 184          # A4 verticale con margini di 13 mm


def _punti(testo: str) -> float:
    """Dimensione del carattere perché la riga più lunga entri nella pagina."""
    lunga = max((len(r) for r in testo.splitlines()), default=80)
    pt = LARGHEZZA_MM / (max(lunga, 60) * 0.6 * 0.3528)
    return max(5.0, min(10.0, pt))


def documento(titolo: str, testo: str) -> QTextDocument:
    pt = _punti(testo)
    doc = QTextDocument()
    f = QFont("Consolas")
    f.setStyleHint(QFont.Monospace)
    f.setPointSizeF(pt)
    doc.setDefaultFont(f)
    doc.setHtml(f"<p style=\"font-family:'Segoe UI'; font-size:12pt\"><b>{escape(titolo)}</b></p>"
                f"<pre style=\"font-family:Consolas,'Courier New',monospace; font-size:{pt:.1f}pt\">"
                f"{escape(testo)}</pre>")
    return doc


def _stampante(alta: bool = True) -> QPrinter:
    p = QPrinter(QPrinter.HighResolution if alta else QPrinter.ScreenResolution)
    p.setPageSize(QPageSize(QPageSize.A4))
    p.setPageOrientation(QPageLayout.Portrait)
    p.setPageMargins(QMarginsF(13, 13, 13, 13), QPageLayout.Millimeter)
    return p


def _stampa_doc(doc: QTextDocument, printer: QPrinter):
    (getattr(doc, "print_", None) or getattr(doc, "print"))(printer)


def salva_pdf(percorso: str, titolo: str, testo: str) -> None:
    doc = documento(titolo, testo)
    w = QPdfWriter(percorso)
    w.setTitle(titolo)
    w.setCreator("Pensiero Magico")
    w.setResolution(600)
    w.setPageSize(QPageSize(QPageSize.A4))
    w.setPageMargins(QMarginsF(13, 13, 13, 13), QPageLayout.Millimeter)
    _stampa_doc(doc, w)
    del w


def salva_txt(percorso: str, titolo: str, testo: str) -> None:
    with open(percorso, "w", encoding="utf-8") as f:
        f.write(titolo + "\n\n" + testo + "\n")


def anteprima(parent, titolo: str, testo: str) -> None:
    """Anteprima di stampa: da qui si sceglie la stampante e si stampa."""
    p = _stampante()
    p.setDocName(titolo)
    doc = documento(titolo, testo)
    d = QPrintPreviewDialog(p, parent)
    d.setWindowTitle(f"Anteprima di stampa – {titolo}")
    d.paintRequested.connect(lambda pr: _stampa_doc(doc, pr))
    d.resize(1000, 760)
    d.exec()


def _nome_file(t: str) -> str:
    return "".join(c if c.isalnum() or c in " -_" else "_" for c in t).strip() or "stampa"


def stampa(parent, titolo: str, testo: str, nome_file: str = "") -> None:
    """Chiede dove mandare il testo: stampante (con anteprima), PDF o TXT."""
    m = QMessageBox(parent)
    m.setWindowTitle("Stampa")
    m.setIcon(QMessageBox.Question)
    m.setText(f"<b>{escape(titolo)}</b><br>Dove vuoi mandarlo?")
    b_st = m.addButton("🖨 Stampante (anteprima)", QMessageBox.AcceptRole)
    b_pdf = m.addButton("📄 File PDF", QMessageBox.AcceptRole)
    b_txt = m.addButton("📝 File TXT", QMessageBox.AcceptRole)
    m.addButton("Annulla", QMessageBox.RejectRole)
    m.exec()
    scelto = m.clickedButton()
    if scelto is b_st:
        anteprima(parent, titolo, testo)
    elif scelto in (b_pdf, b_txt):
        pdf = scelto is b_pdf
        est = "pdf" if pdf else "txt"
        nome, _ = QFileDialog.getSaveFileName(parent, "Salva come " + est.upper(),
                                              f"{_nome_file(nome_file or titolo)}.{est}",
                                              "PDF (*.pdf)" if pdf else "Testo (*.txt)")
        if not nome:
            return
        try:
            (salva_pdf if pdf else salva_txt)(nome, titolo, testo)
        except Exception as ex:
            QMessageBox.warning(parent, "Stampa", f"Non riesco a salvare il file:\n{ex}")
            return
        QMessageBox.information(parent, "Stampa", f"Salvato in:\n{nome}")


def pulsanti_stampa(parent, funzione) -> QPushButton:
    """Pulsante "Stampa / PDF / TXT" che chiama funzione() -> (titolo, testo, nome_file)."""
    b = QPushButton("🖨 Stampa / PDF / TXT...")
    b.clicked.connect(lambda: stampa(parent, *funzione()))
    return b
