"""Prova di avvio dell'interfaccia (senza schermo). Eseguita dalla build su GitHub."""
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from pmse.core.db import Archivio  # noqa: E402
from pmse.core.internet import analizza_pagina_anno  # noqa: E402

DATI = Path(__file__).parent / "dati"


def foto(nome, widget):
    """Se FOTO_DIR è impostata salva un'immagine della finestra (per controllo visivo nella build)."""
    cartella = os.environ.get("FOTO_DIR")
    if cartella:
        os.makedirs(cartella, exist_ok=True)
        widget.grab().save(os.path.join(cartella, nome + ".png"))


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def arch(tmp_path):
    a = Archivio(tmp_path / "g.db")
    a.unisci(analizza_pagina_anno((DATI / "pagina_1997.html").read_text(encoding="utf-8")))
    yield a
    a.chiudi()


def test_finestre(app, arch):
    from pmse.core import analisi
    from pmse.ui.analisi import FinestraAnalisi
    from pmse.ui.archivio import FinestraArchivio
    from pmse.ui.editor import EditorEstrazione
    from pmse.ui.finestra import FinestraPrincipale
    from pmse.ui.importa import FinestraImporta
    from pmse.ui.internet import FinestraInternet

    w = FinestraPrincipale(arch, avvio_automatico=False)
    w.show()
    app.processEvents()
    foto("home", w)
    w.p_sx.griglia.seleziona_tutti()
    w.p_sx.griglia.azzera()
    w.p_dx.griglia.mostra_sestine([[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12], [13, 14, 15, 16, 17, 18]], 19, 20)

    a = FinestraArchivio(arch, w)
    a.show()
    a._inverti()
    a.s_num.setValue(86)
    a.c_dove.setCurrentIndex(1)
    a.c_anno.setCurrentIndex(1)
    app.processEvents()
    a.close()

    ed = EditorEstrazione(arch, parent=w)
    ed.show()
    app.processEvents()
    foto("aggiornamento_archivio", ed)
    ed._sposta(0)
    ed._sposta(1)
    e = ed._leggi()
    assert len(e.numeri) == 6
    ed.nuova()
    ed._annulla()
    ed.close()

    for codice in analisi.REGISTRO:
        f = FinestraAnalisi(arch, codice, w)
        f.show()
        app.processEvents()
        assert f.tab.columnCount() > 0
        f.close()

    FinestraImporta(arch, w).close()
    FinestraInternet(arch, parent=w).close()
    w.aggiorna_stato()
    w.close()
