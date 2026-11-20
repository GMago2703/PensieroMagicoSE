"""Avvio di Pensiero Magico SE."""
import sys
import traceback


def main():
    from PySide6.QtWidgets import QApplication, QMessageBox

    from PySide6.QtCore import QSettings

    from pmse.ui.finestra import apri_programma

    app = QApplication(sys.argv)
    app.setApplicationName("Pensiero Magico SE")
    app.setStyle("Fusion")
    from pmse.ui.stile import applica
    applica(app)
    from pmse.ui.icone import installa
    installa(app)
    from pathlib import Path

    from PySide6.QtGui import QIcon
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    app.setWindowIcon(QIcon(str(base / "pmse" / "icona.png")))

    def errore_non_gestito(tipo, valore, tb):
        testo = "".join(traceback.format_exception(tipo, valore, tb))
        QMessageBox.critical(None, "Errore imprevisto", testo[-3000:])

    sys.excepthook = errore_non_gestito
    # si riapre l'ultimo programma usato (Pensiero Magico SE o Pensiero Magico EJ)
    ultimo = QSettings("PensieroMagico", "Avvio").value("ultimo_programma", "SE")
    apri_programma(ultimo if ultimo in ("SE", "EJ") else "SE")
    from PySide6.QtCore import QTimer

    from pmse.ui.copie import copia_automatica
    QTimer.singleShot(5000, copia_automatica)      # copia automatica dei dati, se è il momento
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
