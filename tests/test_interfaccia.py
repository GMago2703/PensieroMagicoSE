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


def test_nuove_finestre(app, arch):
    from test_nucleo import storico_finto

    from pmse.core import personalizzate as pz
    from pmse.ui.costruttore import FinestraCostruttore
    from pmse.ui.finestra import FinestraPrincipale
    from pmse.ui.magico import FinestraImpostazioni, FinestraSpiegazione, FinestraStorico, FinestraVerifica
    from pmse.ui.sestine import FinestraSestine
    from pmse.ui.analisi import FinestraAnalisi

    arch.unisci(storico_finto(600))
    pz.salva_tutte(arch, [pz.esempio()])
    w = FinestraPrincipale(arch, avvio_automatico=False)
    w.show()
    w.p_sx.griglia.selezionati = {3, 8, 15, 22, 41, 67, 70, 88}
    w.p_sx.griglia._ridisegna_selezione()
    w.genera()
    app.processEvents()
    foto("home_magico", w)
    w._menu_analisi()

    for codice in ("consecutivi", "somme", "sequenze", "pari_dispari", "posizioni", "somiglianza",
                   pz.esempio().codice):
        f = FinestraAnalisi(arch, codice, w)
        f.show()
        f.tab.selectRow(0)
        app.processEvents()
        foto("analisi_" + codice.replace(":", "_").replace(" ", "_"), f)
        f.close()

    c = FinestraCostruttore(arch, w)
    c.show()
    c.nuova()
    c._aggiungi_ing(pz.Ingrediente("successivi", 2, 1.5))
    c.ck_decine[2].setChecked(True)
    c.prova()
    app.processEvents()
    foto("costruttore", c)
    c.close()

    s = FinestraSestine(arch, sorted(w.p_sx.griglia.selezionati)[:6], w)
    s.show()
    s.e_nuova.setText("1 2 3 4 5 6")
    s._aggiungi_testo()
    s.aggiungi([[5, 18, 27, 44, 63, 81]])
    s.tab_c.selectRow(0)
    app.processEvents()
    foto("mie_sestine", s)
    s.schede.setCurrentIndex(1)
    s.s_maxp.setValue(3)
    s.c_pesi.setCurrentIndex(1)
    s.cerca()
    assert s.tab_r.rowCount() == 10
    s.tab_r.selectRow(0)
    app.processEvents()
    foto("cerca_sestine", s)
    s.close()

    imp = FinestraImpostazioni(arch, w)
    imp.show()
    app.processEvents()
    foto("magico_impostazioni", imp)
    imp.close()
    sp = FinestraSpiegazione(w.ultimo_magico, w)
    sp.show()
    app.processEvents()
    foto("magico_spiegazione", sp)
    sp.close()
    v = FinestraVerifica(arch, w)
    v.s_n.setValue(30)
    v.show()
    v.avvia()
    v.thread.wait(60000)
    app.processEvents()
    foto("magico_verifica", v)
    v.close()
    from pmse.core import claude_ai
    from pmse.ui.claude import FinestraClaude
    cl = FinestraClaude(arch, w)
    cl.show()
    assert cl._prepara()
    rc = claude_ai.RispostaClaude(
        [[4, 18, 33, 47, 62, 85], [9, 21, 38, 50, 66, 77], [2, 15, 29, 44, 71, 88]], 56, 12,
        ["Motivazione di prova 1", "Motivazione di prova 2", "Motivazione di prova 3"],
        "Prova Jolly/SuperStar", "Analisi di prova.", "Scartati di prova.", "Affidabilità di prova.",
        "claude-opus-5-5", 4100, 900)
    cl._risposta(rc)
    app.processEvents()
    foto("claude", cl)
    from unittest import mock
    with mock.patch("pmse.ui.claude.QMessageBox.information"):
        cl._applica()
    cl.close()
    w.mostra_magico(cl.applicato, "Scelta di Claude")
    from pmse.core import apprendimento as ap
    from pmse.ui.magico import FinestraApprendimento
    ap.elabora_nuove(arch)                       # avvia il conteggio "da oggi"
    arch.unisci(storico_finto(620)[600:])        # 20 nuove estrazioni
    nuove = ap.elabora_nuove(arch)
    assert nuove
    fa = FinestraApprendimento(arch, nuove, w)
    fa.show()
    fa.s_n.setValue(100)
    fa._allena()
    fa.thread.wait(60000)
    app.processEvents()
    fa.tab.selectRow(0)
    app.processEvents()
    foto("apprendimento", fa)
    fa.close()
    st = FinestraStorico(arch, w)
    st.show()
    app.processEvents()
    st.close()
    w.close()
