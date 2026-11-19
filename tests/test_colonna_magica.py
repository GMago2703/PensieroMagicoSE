"""Colonna magica: fonti diverse per ogni numero, sostituzioni se l'AI manca, salvataggio in Le mie giocate."""
import pytest

from pmse.core import claude_ai, magico
from pmse.core import colonna_magica as cm
from pmse.core import mie_giocate as mg
from pmse.core import sistemi as sis
from pmse.core.db import Archivio
from pmse.core.gioco import EJ, SE
from tests.test_sistemi import archivio_finto


def _prepara(tmp_path, g):
    a = Archivio(tmp_path / f"cm_{g.codice}.db", g)
    a.unisci(archivio_finto(g, 300))
    st = a.sestine()
    return a, cm.Tabella(g, sis.contesto_da_archivio(a)), magico.genera(st)


def _ai(g):
    return lambda esc: (next(n for n in range(g.n, 0, -1) if n not in esc), "motivo", "Finto")


@pytest.mark.parametrize("g", [SE, EJ])
def test_colonna_completa_senza_doppioni(tmp_path, g):
    a, tab, base = _prepara(tmp_path, g)
    c = cm.genera(g, tab, base, _ai(g), None if g.is_ej else _ai(g))
    assert [n.fonte for n in c.numeri] == cm.fonti_del_gioco(g)
    assert len(c.numeri) == g.k and len(set(c.colonna)) == g.k
    assert all(1 <= x <= g.n for x in c.colonna)
    assert all(not n.sostituito for n in c.numeri)
    assert bool(c.euronumeri) == g.is_ej
    assert ("ai" in [n.fonte for n in c.numeri]) == (not g.is_ej)
    a.chiudi()


def test_ai_assente_o_rotta_sostituita(tmp_path):
    a, tab, base = _prepara(tmp_path, SE)

    def rotta(esc):
        raise claude_ai.ErroreClaude("limite raggiunto")
    c = cm.genera(SE, tab, base, rotta, None)
    sost = {n.fonte: n for n in c.numeri if n.sostituito}
    assert set(sost) == {"magico_ai", "ai"}
    assert "limite raggiunto" in sost["magico_ai"].nota and "non disponibile" in sost["ai"].nota
    assert len(set(c.colonna)) == 6
    a.chiudi()


def test_chiedi_numero_corregge_una_volta():
    risposte = iter(['{"numero": 99, "motivazione": "x"}', '{"numero": 7, "motivazione": "ok"}'])
    n, mot, mod = cm.chiedi_numero(lambda m: (next(risposte), "m", 0, 0), "dossier", SE, {3})
    assert (n, mot) == (7, "ok")
    with pytest.raises(claude_ai.ErroreClaude):
        cm.chiedi_numero(lambda m: ("non json", "m", 0, 0), "dossier", SE, set())


def test_salvataggio_con_origini(tmp_path):
    a, tab, base = _prepara(tmp_path, EJ)
    c = cm.genera(EJ, tab, base, _ai(EJ), None)
    v = mg.aggiungi_colonna_magica(a, c)
    voci = [x for x in mg.carica(a) if x.categoria == "colonna_magica"]
    assert len(voci) == 1 and voci[0].colonne == [c.colonna] and len(voci[0].origini) == 5
    assert voci[0].extra == [c.euronumeri]
    assert v.id == voci[0].id
    a.chiudi()
