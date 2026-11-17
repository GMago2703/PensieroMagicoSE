"""Test di Pensiero Magico EJ (Eurojackpot) e della separazione dai dati SuperEnalotto."""
import json
import random
from datetime import date, timedelta
from pathlib import Path

import pytest

from pmse.core import analisi, apprendimento, claude_ai, magico, personalizzate, sestine
from pmse.core.db import Archivio
from pmse.core.gioco import EJ, SE
from pmse.core.importatore import esporta_csv, leggi_file, leggi_testo
from pmse.core.internet import analizza_pagina_anno_ej
from pmse.core.modello import Estrazione, valida

DATI = Path(__file__).parent / "dati"


def storico_ej(n=500, seme=11):
    rnd = random.Random(seme)
    out = []
    d = date(2019, 1, 4)              # venerdì
    while len(out) < n:
        em = EJ.euro_max(d)
        nums = rnd.sample(range(1, 51), 5)
        e = rnd.sample(range(1, em + 1), 2)
        out.append(Estrazione(data=d, numeri=nums, jolly=e[0], superstar=e[1], gioco=EJ))
        d += timedelta(days=3 if d.weekday() == 1 else 4)     # martedì -> venerdì -> martedì
    return out


@pytest.fixture
def arch_ej(tmp_path):
    a = Archivio(tmp_path / "ej.db", gioco=EJ)
    yield a
    a.chiudi()


def test_validazione_ej():
    assert valida(Estrazione(date(2025, 12, 30), [10, 18, 20, 23, 27], 6, 1, gioco=EJ)) == ([], [])
    e = Estrazione(date(2025, 12, 30), [10, 18, 20, 23, 27], 6, 1, gioco=EJ)
    assert (e.jolly, e.superstar) == (1, 6)                 # Euronumeri riordinati
    assert valida(Estrazione(date(2013, 1, 4), [1, 2, 3, 4, 5], 9, 1, gioco=EJ))[0]       # nel 2013 max 8
    assert valida(Estrazione(date(2025, 1, 3), [1, 2, 3, 4, 51], 9, 1, gioco=EJ))[0]
    assert valida(Estrazione(date(2025, 1, 3), [1, 2, 3, 4, 5], 3, 3, gioco=EJ))[0]
    assert valida(Estrazione(date(2025, 1, 3), [1, 2, 3, 4, 5, 6], 3, 4, gioco=EJ))[0]


def test_internet_e_import_ej(arch_ej, tmp_path):
    estr = analizza_pagina_anno_ej((DATI / "pagina_ej_2012.html").read_text(encoding="utf-8"))
    assert len(estr) == 3 and estr[2].numeri == [10, 18, 20, 23, 27] and (estr[2].jolly, estr[2].superstar) == (1, 6)
    assert arch_ej.unisci(estr).nuove == 3
    assert arch_ej.per_data(date(2012, 12, 28)).concorso == 2
    f = tmp_path / "ej.csv"
    esporta_csv(arch_ej.tutte(), f, EJ)
    r = leggi_file(f, EJ)
    assert len(r.estrazioni) == 3 and all(e.gioco is EJ for e in r.estrazioni)
    assert arch_ej.unisci(r.estrazioni).duplicate == 3
    r = leggi_testo("30/12/2025;10;18;20;23;27;1;6\nVenerdì 2 gennaio 2026 10 15 29 34 38 2 9", EJ)
    assert len(r.estrazioni) == 2 and r.estrazioni[1].superstar == 9


def test_separazione(tmp_path):
    p = tmp_path / "x.db"
    a = Archivio(p, gioco=SE)
    a.chiudi()
    with pytest.raises(ValueError):
        Archivio(p, gioco=EJ)                                   # un archivio SE non si apre come EJ
    b = Archivio(tmp_path / "y.db", gioco=EJ)
    se = Estrazione(date(2026, 7, 18), [1, 28, 52, 62, 79, 86], 61, 31)
    assert b.unisci([se]).scartate                             # estrazioni di un altro gioco rifiutate
    with pytest.raises(ValueError):
        b.salva(se)
    b.chiudi()


def test_analisi_ej(arch_ej):
    arch_ej.unisci(storico_ej())
    st = arch_ej.sestine()
    assert st.gioco is EJ and st[:10].gioco is EJ
    elenco = analisi.analisi_del_gioco(EJ)
    assert "euronumeri" in elenco and "jolly_superstar" not in elenco
    for codice, d in elenco.items():
        ris = d.funzione(st)
        assert ris.colonne, codice
        if ris.punteggi:
            assert max(ris.punteggi) <= 50, codice
    pos = analisi.posizioni(st)
    assert len(pos.colonne) == 5 + 3 and len(pos.righe) == 50
    pd = analisi.pari_dispari(st)
    assert len(pd.righe) == 6 and round(sum(r[3] for r in pd.righe)) == 100
    eu = analisi.euronumeri(st)
    assert len(eu.righe) == 12
    assert "jolly" not in personalizzate.misure_del_gioco(EJ)
    r = personalizzate.esempio()
    ris = personalizzate.esegui(r, st)
    assert all(1 <= riga[0] <= 50 for riga in ris.righe)
    idx = sestine.IndiceArchivio(st)
    c = idx.confronta(st[-1][1])
    assert c.gia_uscita and c.max_punti == 5
    trovate, _ = sestine.cerca(idx, sestine.Criteri(max_punti_archivio=3), 5, seed=2)
    assert len(trovate) == 5 and all(len(t) == 5 and max(t) <= 50 for t in trovate)


def test_magico_ej(arch_ej):
    arch_ej.unisci(storico_ej())
    st = arch_ej.sestine()
    r = magico.genera(st)
    assert len(r.sestine) == 1 and len(r.sestine[0].numeri) == 5
    assert all(1 <= x <= 50 for x in r.sestine[0].numeri)
    assert r.jolly < r.superstar and 1 <= r.jolly and r.superstar <= 12
    assert r.gioco == "EJ"
    es = magico.verifica_storica(st, 30)
    assert es.prove == 30 and "Euronumeri indovinati" in es.testo()
    imp = magico.Impostazioni.predefinite(EJ)
    assert imp.gioco == "EJ" and imp.pari_max == 4 and imp.pari_min == 1
    # apprendimento
    arch_ej.scrivi_impostazione(apprendimento.CHIAVE_APPRESO, st[-11][0].isoformat())
    magico.salva_previsione(arch_ej, magico.genera(st[:-10]))
    nuove = apprendimento.elabora_nuove(arch_ej)
    assert len(nuove) == 10 and nuove[0].gioco == "EJ" and nuove[0].previsioni
    assert "Euronumeri" in nuove[0].testo()
    imp2, _, fatti = apprendimento.allena(st, magico.Impostazioni.predefinite(EJ), 100)
    assert fatti == 100


def test_claude_ej(arch_ej):
    arch_ej.unisci(storico_ej(300))
    st = arch_ej.sestine()
    r = magico.genera(st)
    dossier = claude_ai.costruisci_dossier(st, r, imp=magico.Impostazioni.predefinite(EJ))
    assert "EUROJACKPOT" in dossier and "Euronumeri" in dossier and "volte_jolly" not in dossier
    assert "cinquina" in claude_ai.istruzioni(EJ) and "SuperStar" not in claude_ai.istruzioni(EJ)
    d = {"cinquina": [3, 14, 27, 38, 49], "euronumeri": [11, 4], "motivazioni": ["prova"]}
    rc = claude_ai.valida_risposta(d, set(), magico.matrice(st), r.limiti_archivio, EJ)
    assert rc.sestine == [[3, 14, 27, 38, 49]] and (rc.jolly, rc.superstar) == (4, 11)
    with pytest.raises(claude_ai.ErroreClaude):
        claude_ai.valida_risposta({"cinquina": [1, 2, 3, 4, 5], "euronumeri": [13, 2]}, set(), g=EJ)
    ris = claude_ai.come_risultato(rc, r)
    magico.salva_previsione(arch_ej, ris, "Claude (prova)")
    assert json.loads(arch_ej.leggi_impostazione(magico.CHIAVE_PREV))[-1]["superstar"] == 11
