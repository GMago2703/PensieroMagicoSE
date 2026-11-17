"""Dimensioni delle finestre adattate allo schermo (anche portatili piccoli o con lo zoom di Windows)."""
from PySide6.QtGui import QGuiApplication


def adatta_schermo(finestra, larghezza: int, altezza: int) -> None:
    """Ridimensiona alla misura desiderata senza mai superare lo spazio libero dello schermo."""
    schermo = finestra.screen() if hasattr(finestra, "screen") and finestra.screen() else \
        QGuiApplication.primaryScreen()
    if schermo is None:
        finestra.resize(larghezza, altezza)
        return
    libero = schermo.availableGeometry()
    finestra.resize(min(larghezza, int(libero.width() * 0.96)), min(altezza, int(libero.height() * 0.90)))
