"""Prova di avvio dell'interfaccia (senza schermo). Eseguita dalla build su GitHub."""
import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtCore import Qt  # noqa: E402

from pmse.core.db import Archivio  # noqa: E402
from pmse.core.internet import analizza_pagina_anno  # noqa: E402

DATI = Path(__file__).parent / "dati"


def foto(nome, widget):
    """Se FOTO_DIR è impostata salva un'immagine della finestra (per controllo visivo nella build)."""
    cartella = os.environ.get("FOTO_DIR")
    if cartella:
        os.makedirs(cartella, exist_ok=True)
        widget.grab().save(os.path.join(cartella, nome + ".png"))


def entra_nello_schermo(finestra, app):
    """La finestra (e la sua dimensione minima) non deve uscire dallo schermo, nemmeno su 1366x768."""
    libero = finestra.screen().availableGeometry()
    assert finestra.width() <= libero.width() and finestra.height() <= libero.height()
    minimo = finestra.minimumSizeHint()
    assert minimo.width() <= min(libero.width(), 1300), minimo
    assert minimo.height() <= min(libero.height(), 700), minimo


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
    entra_nello_schermo(imp, app)
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
    v.thread.wait(120000)
    app.processEvents()
    assert v.esito and v.esito.prove == 30 and v.tab.rowCount() == 30
    assert v.tab.item(0, 1).data(Qt.UserRole + 2)            # numeri evidenziati
    assert "Dettaglio degli ultimi" in arch.leggi_impostazione("magico_ultima_verifica")
    foto("magico_verifica", v)
    entra_nello_schermo(v, app)
    v.c_filtro.setCurrentIndex(1)
    app.processEvents()
    v.close()
    from pmse.core import laboratorio
    from pmse.ui.laboratorio import FinestraLaboratorio
    lab = FinestraLaboratorio(arch, w)
    lab.s_sim.setValue(50)
    lab.show()
    lab.avvia()
    lab.thread.wait(300000)
    app.processEvents()
    assert lab.risultato.prove and "VERDETTO" in arch.leggi_impostazione(laboratorio.CHIAVE_LAB + "_testo")
    assert arch.leggi_impostazione(laboratorio.CHIAVE_LAB)
    foto("laboratorio", lab)
    entra_nello_schermo(lab, app)
    lab.close()
    # concorsi con il 6: evidenziati in archivio, filtro, confronto
    import random as _r
    from pmse.core import vincite
    from pmse.ui.archivio import FinestraArchivio
    from pmse.ui.sei import FinestraSei
    rnd = _r.Random(1)
    dati = {e.data.isoformat(): vincite.Vincite(e.data.isoformat(), p6=int(rnd.random() < 0.05),
                                                p3=rnd.randint(15000, 25000), premio6="1.000.000,00 €")
            for e in arch.tutte(True)}
    vincite.salva(arch, dati)
    con6 = sum(1 for v in dati.values() if v.p6)
    fa = FinestraArchivio(arch, w)
    fa.c_sei.setCurrentIndex(1)
    assert fa.modello.rowCount() == con6 > 0
    assert "★" in fa.modello.data(fa.modello.index(0, len(fa.modello.colonne) - 1))
    foto("archivio_solo_6", fa)
    fa.close()
    fs = FinestraSei(arch, w)
    fs.show()
    app.processEvents()
    assert fs.risultato and len(fs.risultato.sei) == con6
    foto("concorsi_con_il_6", fs)
    entra_nello_schermo(fs, app)
    fs.close()
    fan = FinestraAnalisi(arch, None, w)
    fan.c_gruppo.setCurrentIndex(1)
    assert "solo i concorsi con il 6" in fan.l_nota.text()
    fan.close()
    from pmse.core import claude_ai
    from pmse.ui.claude import FinestraClaude
    cl = FinestraClaude(arch, w)
    cl.show()
    assert cl.fornitore == "gemini" and not cl.e_ws.isVisible()
    cl.c_fornitore.setCurrentIndex(1)
    assert cl.fornitore == "claude" and cl.c_modello.currentData().startswith("claude")
    cl.c_fornitore.setCurrentIndex(0)
    assert cl.c_modello.currentData().startswith("gemini")
    assert cl._prepara()
    cl.nome_usato = "Gemini"
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
    ulteriori = storico_finto(620)
    # (l'archivio di prova contiene anche un'estrazione del 2026: si fissa il punto di partenza a mano)
    arch.scrivi_impostazione(ap.CHIAVE_APPRESO, ulteriori[599].data.isoformat())
    arch.unisci(ulteriori[600:])                 # 20 nuove estrazioni
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


def test_pensiero_magico_ej(app, tmp_path):
    """Pensiero Magico EJ: finestre adattate all'Eurojackpot e selettore in alto a sinistra."""
    from unittest import mock

    from test_ej import storico_ej

    from pmse.core.db import Archivio
    from pmse.core.gioco import EJ
    from pmse.core import personalizzate as pz
    from pmse.ui import finestra as fin
    from pmse.ui.analisi import FinestraAnalisi
    from pmse.ui.archivio import FinestraArchivio
    from pmse.ui.claude import FinestraClaude
    from pmse.ui.costruttore import FinestraCostruttore
    from pmse.ui.editor import EditorEstrazione
    from pmse.ui.importa import FinestraImporta
    from pmse.ui.internet import FinestraInternet
    from pmse.ui.magico import (FinestraApprendimento, FinestraImpostazioni, FinestraSpiegazione, FinestraStorico,
                                FinestraVerifica)
    from pmse.ui.sestine import FinestraSestine

    arch = Archivio(tmp_path / "ej.db", gioco=EJ)
    arch.unisci(storico_ej(400))
    pz.salva_tutte(arch, [pz.esempio()])
    w = fin.FinestraPrincipale(arch, avvio_automatico=False)
    w.show()
    assert w.selettore.text().startswith("🍀 Pensiero Magico EJ") or "Pensiero Magico EJ" in w.selettore.text()
    assert len(w.p_sx.griglia.celle) == 50 and len(w.griglia_euro.celle) == 12
    w.genera()
    r = w.ultimo_magico
    assert len(r.sestine) == 1 and len(r.sestine[0].numeri) == 5 and r.superstar <= 12
    app.processEvents()
    foto("ej_home", w)

    ed = EditorEstrazione(arch, parent=w)
    ed.show()
    assert len(ed.s_num) == 5
    e = ed._leggi()
    assert e.gioco is EJ
    app.processEvents()
    foto("ej_aggiornamento_archivio", ed)
    ed.close()
    a = FinestraArchivio(arch, w)
    a.show()
    a.s_num.setValue(7)
    app.processEvents()
    foto("ej_archivio", a)
    a.close()
    for codice in pz.tutte_le_analisi(arch):
        f = FinestraAnalisi(arch, codice, w)
        f.show()
        f.tab.selectRow(0)
        app.processEvents()
        if codice in ("euronumeri", "posizioni"):
            foto("ej_analisi_" + codice, f)
        f.close()
    c = FinestraCostruttore(arch, w)
    c.show()
    assert len(c.ck_decine) == 5
    c.close()
    s = FinestraSestine(arch, [3, 14, 27, 38, 49], w)
    s.show()
    s._aggiungi_home()
    s.schede.setCurrentIndex(1)
    s.cerca()
    assert s.tab_r.rowCount() == 10
    app.processEvents()
    foto("ej_cerca", s)
    s.close()
    FinestraImporta(arch, w).close()
    FinestraInternet(arch, parent=w).close()
    imp = FinestraImpostazioni(arch, w)
    imp.show()
    app.processEvents()
    foto("ej_impostazioni", imp)
    imp.close()
    FinestraSpiegazione(r, w).close()
    v = FinestraVerifica(arch, w)
    v.s_n.setValue(30)
    v.show()
    v.avvia()
    v.thread.wait(120000)
    app.processEvents()
    assert v.tab.rowCount() == 30
    foto("ej_verifica", v)
    v.close()
    cl = FinestraClaude(arch, w)
    cl.show()
    assert cl._prepara()
    from pmse.core import claude_ai
    rc = claude_ai.RispostaClaude([[3, 14, 27, 38, 49]], 4, 11, ["Motivazione di prova"], "Prova euro",
                                  "Analisi di prova.", "", "", "claude-opus-5-5", 3000, 500)
    cl._risposta(rc)
    with mock.patch("pmse.ui.claude.QMessageBox.information"):
        cl._applica()
    app.processEvents()
    foto("ej_claude", cl)
    cl.close()
    FinestraStorico(arch, w).close()
    FinestraApprendimento(arch, parent=w).close()

    # selettore: scegliendo SE si apre l'altro programma e questa finestra si chiude
    with mock.patch.object(fin, "apri_programma") as apri:
        w.cambia_programma("SE")
        apri.assert_called_once_with("SE")
    w.close()


def test_menu_disattivi(app, tmp_path):
    """Menu in stile Enavision: Sistemi, Condizioni, Sviluppo, Combinazioni attivi; Statistiche ancora disattivato."""
    from pmse.core.gioco import EJ, SE
    from pmse.ui.finestra import FinestraPrincipale

    escluse = {"Commento", "Partecipanti", "Agenda delle giocate", "Preset", "Resti", "Baricentri",
               "Specchi", "Vortici", "Link", "Super link", "Punti tra", "Gemelli tra", "Exit poll",
               "Inserimento picchetti", "Genera da picchetto", "Trasmissione al terminale Sisal",
               "Tutti gli ambi", "Ritardo di primo livello", "Ricerca per fasce", "Elaborazione"}
    for g in (SE, EJ):
        a = Archivio(tmp_path / f"m_{g.codice}.db", gioco=g)
        w = FinestraPrincipale(a, avvio_automatico=False)
        menu = {m.title().replace("&", ""): m for m in
                (x.menu() for x in w.menuBar().actions()) if m is not None}
        for nome in ("Sistemi", "Condizioni", "Sviluppo", "Combinazioni", "Statistiche"):
            m = menu[nome]
            voci = [x for x in m.actions() if not x.isSeparator()]
            assert len(voci) >= 4, nome
            for x in voci:
                testo = x.text().split("\t")[0]
                if nome == "Statistiche":
                    assert not x.isEnabled(), (nome, testo)          # ancora da fare
                assert testo.lower() not in {e.lower() for e in escluse}, (nome, testo)
        # i menu dei sistemi sono attivi
        nuovo = next(x.menu() for x in menu["Sistemi"].actions() if x.menu())
        assert [x.text() for x in nuovo.actions()] == ["Condizionati...", "Condizionati ridotti...",
                                                      "Ridotti (integrali a garanzia)...", "Ridotti immediati..."]
        cond = [x.text() for x in menu["Condizioni"].actions() if x.isEnabled() and not x.isSeparator()]
        assert "Somme" in cond and "Pari e dispari" in cond and len(cond) >= 18
        assert ("Popolarità (quanto è giocata)" in cond) == (g is SE)
        stat = [x.text() for x in menu["Statistiche"].actions()]
        assert ("Numeri SuperStar" in stat) == (g is SE)
        assert ("Euronumeri" in stat) == (g is EJ)
        assert "Elaborazione" not in menu
        # le funzioni attive restano attive
        assert any(x.isEnabled() for x in menu["Archivio"].actions())
        w.show()
        app.processEvents()
        if g is SE:
            for nome in ("Sistemi", "Condizioni", "Sviluppo", "Combinazioni", "Statistiche"):
                m = menu[nome]
                m.popup(w.mapToGlobal(w.rect().topLeft()))
                app.processEvents()
                foto("menu_" + nome.lower(), m)
                m.close()
        w.close()
        a.chiudi()



def test_sistemi(app, tmp_path):
    """Editor dei sistemi, scheda di una condizione, sviluppo, memorizzazione, sistemi salvati."""
    import random as _r
    from datetime import date as _d, timedelta as _td
    from pmse.core import condizioni as cnd, sistemi as sis
    from pmse.core.gioco import EJ, SE
    from pmse.core.modello import Estrazione
    from pmse.ui import sistemi as us
    from pmse.ui.finestra import FinestraPrincipale
    for g in (SE, EJ):
        a = Archivio(tmp_path / f"s_{g.codice}.db", gioco=g)
        rnd, ests, d = _r.Random(2), [], _d(2015, 1, 6)
        while len(ests) < 600:
            if d.weekday() in g.giorni_estrazione:
                n = rnd.sample(range(1, g.n + 1), g.k)
                if g.is_ej:
                    e = rnd.sample(range(1, g.euro_max(d) + 1), 2)
                    ests.append(Estrazione(d, n, e[0], e[1], gioco=EJ))
                else:
                    resto = [x for x in range(1, 91) if x not in n]
                    ests.append(Estrazione(d, n, rnd.choice(resto), rnd.randint(1, 90)))
            d += _td(days=1)
        a.unisci(ests)
        w = FinestraPrincipale(a, avvio_automatico=False)
        # condizionato con la scheda della condizione Pari e dispari (suggerimento applicato)
        ed = w.nuovo_sistema("condizionato")
        ed.griglia.imposta(list(range(1, 21)), [3])
        sc = us.SchedaCondizione(ed.ctx, "pari", None, ed)
        assert sc.analisi.righe and "più comune" in sc.l_sugg.text()
        sc._ok()
        conds = ed._conds() + [sc.risultato]
        ed._salva_conds(conds)
        assert ed.lista.count() == 1
        if g is SE:
            foto("sistemi_scheda_condizione", sc)
            foto("sistemi_editor_condizionato", ed)
        s = ed._raccogli()
        sv = sis.sviluppa(s, ed.ctx)
        assert 0 < len(sv.colonne) < sis.numero_integrale(20, g.k, 1)
        assert all(3 in c for c in sv.colonne.tolist())
        s.colonne = sv.colonne.tolist()
        fs = us.FinestraSviluppo(a, s, None, ed)
        fs.garanzie()
        assert "CALCOLO GARANZIE" in fs.risultati.toPlainText()
        fs.spoglio_ultima()
        if g is SE:
            foto("sistemi_sviluppo", fs)
        s.nome = "prova"
        sis.salva(a, s)
        fs.close()
        ed.close()
        # ridotto immediato: 10 numeri, garanzia n-1 già pronta
        ed = w.nuovo_sistema("immediato")
        ed.griglia.imposta(list(range(5, 15)), [])
        ed.c_gar.setCurrentIndex(ed.c_gar.findData(1))
        assert ed.t_pronti.rowCount() >= 3 and "pronto" in ed.l_info.text()
        s2 = ed._raccogli()
        sv2 = sis.sviluppa(s2)
        ver = sis.verifica_garanzia(sv2.colonne, np.vstack(list(sis.integrale(s2.numeri, g.k))))
        assert ver.garantiti >= g.k - 1
        if g is SE:
            foto("sistemi_ridotto_immediato", ed)
        ed.close()
        fsal = us.FinestraSalvati(a, w)
        assert fsal.t.rowCount() == 1
        fac = us.FinestraAnalisiCondizioni(a, w)
        assert fac.t.rowCount() >= 15
        if g is SE:
            foto("sistemi_analisi_condizioni", fac)
        for f in (fsal, fac):
            f.close()
        w.close()
        a.chiudi()
